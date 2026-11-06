"""Offline tests: corruption recovery, wire faults, CLI gates and relocation.
Tests do not open USB/serial devices or execute vehicle operations.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_tools'))
import json
import random
import shutil
import subprocess
import tempfile
import unittest
import atexit
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from me72 import cli
from me72.images import load, validate, digest, diff, calibration_transition
from me72.checksum import verify, repair, storage_offsets, crc_bitwise
from me72.protocol import (BASE,SIZE,erase_request,download_request,derive_key,
                           session_request)
from me72.transport import (Transport,FrameDecoder,ProtocolError,NegativeResponse,
                            encode,readonly_policy)
from me72.writer import (CalibrationWriter,UIF_RANGES,UIF_SAMPLE_OFFSET,UIF_SAMPLE_LENGTH)
from me72.reader import read_full
from me72 import diagnostics
from fakes import FakeECU,FakePort

from fixtures import synthetic_image,synthetic_target
_FIXTURES=tempfile.TemporaryDirectory(prefix='me72_synthetic_')
atexit.register(_FIXTURES.cleanup)
BASELINE=Path(_FIXTURES.name)/'synthetic_baseline.bin'
TARGET=Path(_FIXTURES.name)/'synthetic_target.bin'
BASELINE.write_bytes(synthetic_image());TARGET.write_bytes(synthetic_target())



def arm(w):
    w.arm(authentication_ok=True,session_ok=True,max_block_length=240,
          supply_ok=True,erase_boundary_reviewed=True)


def captured_reference(source):
    data=bytearray(source[0x10000+UIF_SAMPLE_OFFSET:0x10000+UIF_SAMPLE_OFFSET+UIF_SAMPLE_LENGTH])
    for lo,hi in UIF_RANGES:data[lo-UIF_SAMPLE_OFFSET:hi-UIF_SAMPLE_OFFSET]=b'\x42'*(hi-lo)
    return bytes(data)


class ViewECU(FakeECU):
    def __init__(self,source,corrupt=None):
        super().__init__(source);self.corrupt=corrupt
    def request(self,p,timeout=3):
        result=super().request(p,timeout)
        if p[0]==0x23:
            start=int.from_bytes(p[1:4],'big')-BASE
            result=bytearray(result)
            for j in range(1,len(result)):
                pos=start+j-1
                if any(lo<=pos<hi for lo,hi in UIF_RANGES):result[j]=0x42
                if self.blocks and pos==self.corrupt:result[j]^=1
            result=bytes(result)
        return result


class Checksums(unittest.TestCase):
    def test_synthetic_images_have_38_correct_records_and_repair_is_idempotent(self):
        for path in (BASELINE,TARGET):
            data=load(path);rows=verify(data)
            self.assertEqual(len(rows),38);self.assertTrue(all(r['ok'] for r in rows))
            self.assertEqual(repair(data),data)

    def test_missing_end_marker_is_not_fixed_into_a_flashable_image(self):
        data=bytearray(load(BASELINE));data[0x1FFFC:0x20000]=b'\xff'*4
        failed=[r for r in verify(data) if not r['ok']]
        self.assertIn('ROMSYS parameter endpoints',[r['name'] for r in failed])
        fixed=repair(data)
        self.assertTrue(all(r['ok'] for r in verify(fixed)))
        with self.assertRaises(ValueError):calibration_transition(fixed,fixed)

    def test_all_corrupted_storage_bytes_repair_back_to_exact_original(self):
        original=load(BASELINE)
        for seed in range(3):
            damaged=bytearray(original);rng=random.Random(seed)
            for offset in storage_offsets():damaged[offset]=rng.randrange(256)
            self.assertFalse(all(r['ok'] for r in verify(damaged)))
            self.assertEqual(repair(damaged),original)

    def test_self_inclusive_and_cross_inclusive_mp_pairs_are_repaired(self):
        original=load(BASELINE)
        for offset in (0x17C94,0x17C98,0x1EB1E,0x1EB22):
            damaged=bytearray(original);damaged[offset]^=0x6D
            self.assertEqual(repair(damaged),original)

    def test_data_corruption_is_detected_and_repair_changes_only_storage(self):
        original=load(BASELINE)
        for offset in (0x11613,0x50000,0xFFFE,0x37FFE):
            damaged=bytearray(original);damaged[offset]^=1
            self.assertFalse(all(r['ok'] for r in verify(damaged)))
            fixed=repair(damaged)
            self.assertTrue(all(r['ok'] for r in verify(fixed)))
            self.assertEqual(fixed[offset],damaged[offset])
            self.assertTrue(all(int(c['offset'],16) in storage_offsets() for c in diff(damaged,fixed)))

    def test_crc_known_vector_and_incompatible_profile_rejection(self):
        self.assertEqual(crc_bitwise(b'123456789'),0xCBF43926)
        original=load(BASELINE)
        for offset in (0x8010,0x17C7C):
            damaged=bytearray(original);damaged[offset]^=1
            with self.assertRaises(ValueError):repair(damaged)
        with self.assertRaises(ValueError):validate(original[:-1])

    def test_64k_needs_explicit_base_and_merges_exactly(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'cal.bin';p.write_bytes(load(TARGET)[0x10000:0x20000])
            with self.assertRaises(ValueError):load(p)
            self.assertEqual(load(p,BASELINE),load(TARGET))


class Wire(unittest.TestCase):
    def test_exact_oem_payloads_and_synthetic_seed_key_vectors(self):
        report=json.loads((ROOT/'07_evidence/protocol/synthetic_oem_vectors.json').read_text())
        self.assertTrue(report['synthetic_only']);self.assertFalse(report['vehicle_data'])
        pattern=bytes((i*37+11)&255 for i in range(65536))
        image=b'\0'*65536+pattern+b'\0'*(0x80000-0x20000)
        self.assertEqual(cli.sequence(image),[bytes.fromhex(r['payload']) for r in report['captured']])
        self.assertEqual(len(report['seedVectors']),39)
        for v in report['seedVectors']:
            self.assertEqual(derive_key(bytes.fromhex(v['seedFrame'])[4:],v['nonce']).hex(),v['key'])

    def test_fragmentation_checksum_noise_and_local_echo(self):
        valid=encode(b'\xe2ok',0xF1,0x12);bad=valid[:-1]+bytes([valid[-1]^1]);d=FrameDecoder()
        frames=[]
        for b in b'noise'+bad+valid:frames.extend(d.feed(bytes([b])))
        self.assertEqual(frames,[valid])
        port=FakePort(encode(bytes.fromhex('7fa278'),0xF1,0x12)+valid)
        link=Transport('unused',lambda **_:None,port=port)
        self.assertEqual(link.request(b'\xa2'),b'\xe2ok');self.assertEqual(len(port.writes),1)

    def test_echo_only_and_negative_response_do_not_retry(self):
        for response,error in [(b'',TimeoutError),(encode(bytes.fromhex('7fa222'),0xF1,0x12),NegativeResponse)]:
            port=FakePort(response);link=Transport('unused',lambda **_:None,port=port)
            with self.assertRaises(error):link.request(b'\xa2',timeout=0.002)
            self.assertEqual(len(port.writes),1)

    def test_only_explicit_session_busy_repeats_same_request(self):
        class Busy:
            def __init__(self):self.calls=[]
            def request(self,p):
                self.calls.append(p)
                if len(self.calls)==1:raise NegativeResponse(bytes.fromhex('7f1021'))
                return bytes.fromhex('508501')
        link=Busy()
        self.assertEqual(session_request(link,bytes.fromhex('108501')),bytes.fromhex('508501'))
        self.assertEqual(link.calls,[bytes.fromhex('108501')]*2)

    def test_read_only_policies_reject_writes_and_adaptation_resets(self):
        for policy in (readonly_policy,diagnostics.policy):
            for p in (erase_request(),download_request(BASE,SIZE),b'\x36\0',b'\x37',b'\x14\0\0',b'\x11\x01',b'\x3d'+b'\0'*8):
                with self.assertRaises(ValueError):policy(p)


class Writer(unittest.TestCase):
    def make(self):
        before,target=load(BASELINE),load(TARGET)
        return CalibrationWriter(before,target),before,target

    def test_unarmed_never_erases_and_code_changes_are_rejected(self):
        w,b,t=self.make();ecu=FakeECU(b[0x10000:0x20000])
        with self.assertRaises(ValueError):w.run(ecu,lambda **_:None)
        self.assertEqual(ecu.calls,[])
        changed=bytearray(t);changed[0x50000]^=1
        with self.assertRaises(ValueError):CalibrationWriter(b,repair(changed))
        with self.assertRaises(ValueError):CalibrationWriter(b,t,block_size=240)

    def test_successful_transfer_with_exact_512_block_counters(self):
        w,b,t=self.make();arm(w);ecu=FakeECU(b[0x10000:0x20000]);gate=cli.SequenceLink(ecu,cli.sequence(t))
        with redirect_stdout(StringIO()):self.assertEqual(w.run(gate,lambda **_:None),t[0x10000:0x20000])
        self.assertEqual(gate.index,516);self.assertEqual(w.blocks_acknowledged,512)

    def test_timeout_counter_readback_and_checksum_faults_never_reset_or_reerase(self):
        for fault in ('erase_timeout','transfer_timeout','bad_transfer_status','duplicate_counter','readback_corruption','bad_checksum'):
            with self.subTest(fault=fault):
                w,b,t=self.make();arm(w);ecu=FakeECU(b[0x10000:0x20000],fault)
                with redirect_stdout(StringIO()),self.assertRaises((ValueError,ProtocolError,TimeoutError)):
                    w.run(ecu,lambda **_:None)
                self.assertEqual(w.state,'uncertain_after_erase')
                self.assertEqual(sum(p==erase_request() for p in ecu.calls),1)
                self.assertFalse(any(p[0] in (0x10,0x11,0x14,0x82) for p in ecu.calls))

    def test_only_exact_pre_erase_uif_view_is_accepted(self):
        b,t=load(BASELINE),load(TARGET)
        for corrupt in (None,0xFD26,0xFD54,0xFD44,0x1614):
            w=CalibrationWriter(b,t,programming_uif_reference=captured_reference(b));arm(w)
            ecu=ViewECU(b[0x10000:0x20000],corrupt)
            with redirect_stdout(StringIO()):
                if corrupt is None:
                    w.run(ecu,lambda **_:None)
                    self.assertEqual(w.state,'programming_view_verified')
                else:
                    with self.assertRaises(ValueError):w.run(ecu,lambda **_:None)
                    self.assertIsNotNone(w.last_readback)
                    self.assertFalse(any(p==b'\x31\x01' for p in ecu.calls))
        wrong=bytearray(captured_reference(b));wrong[0]^=1
        with self.assertRaises(ValueError):CalibrationWriter(b,t,programming_uif_reference=wrong)


class Reader(unittest.TestCase):
    def test_full_read_repeats_all_calibration_and_restores_default(self):
        image=load(TARGET)
        class Link:
            class Port:baudrate=9600
            def __init__(self):self.port=self.Port();self.calls=[];self.length=0
            def request(self,p):
                self.calls.append(p)
                return {bytes.fromhex('108687'):bytes.fromhex('5086'),bytes.fromhex('108610'):bytes.fromhex('5086'),
                        bytes.fromhex('1081'):bytes.fromhex('5081'),b'\xa2':b'\xe27532675'}[p]
            def read_flash(self,address,length):
                assert 0x800000<=address<address+length<=0x880000
                assert (address&65535)+length<=65536
                self.length+=length;return image[address-0x800000:address-0x800000+length]
        with tempfile.TemporaryDirectory() as folder,redirect_stdout(StringIO()):
            link=Link();path=Path(folder)/'dump.bin'
            self.assertEqual(read_full(link,path),image)
            self.assertEqual(path.read_bytes(),image)
            self.assertEqual(link.length,524288+65536+16*240)
            self.assertEqual(link.port.baudrate,9600)
            self.assertEqual(link.calls[-3:],[bytes.fromhex('108610'),bytes.fromhex('1081'),b'\xa2'])

    def test_diagnostic_ram_flags_are_decoded_from_actual_little_endian_words(self):
        class Link:
            def read_flash(self,address,length):
                self_length=length
                assert self_length==2
                return {0xFD2E:bytes.fromhex('001e'),0xFDD8:bytes.fromhex('1020'),0xFD50:bytes.fromhex('4330')}[address]
        data=diagnostics.read_ram(Link())
        self.assertTrue(data['B_lr']);self.assertTrue(data['B_lr2'])
        self.assertFalse(data['inhibit_bank1']);self.assertFalse(data['inhibit_bank2'])


class CLI(unittest.TestCase):
    def test_offline_commands_do_not_open_ports(self):
        calls=[(cli.read_main,[]),(cli.write_main,[str(TARGET),'--baseline',str(BASELINE)]),
               (cli.verify_main,[str(TARGET)]),(cli.checksum_main,['verify',str(TARGET)])]
        for fn,args in calls:
            with patch.object(cli,'Transport') as transport,redirect_stdout(StringIO()):self.assertEqual(fn(args),0)
            transport.assert_not_called()

    def test_execute_requires_explicit_port_and_interactive_terminal(self):
        with patch.object(cli,'Transport') as transport:
            with self.assertRaises(ValueError):cli.read_main(['--execute'])
            with patch.object(cli.sys.stdin,'isatty',return_value=False),self.assertRaises(ValueError):
                cli.write_main([str(TARGET),'--baseline',str(BASELINE),'--execute','--port','/dev/cu.usbserial-fake'])
            transport.assert_not_called()

    def test_checksum_fix_never_overwrites_input_or_output_and_keeps_64k_size(self):
        with tempfile.TemporaryDirectory() as folder,redirect_stdout(StringIO()):
            folder=Path(folder);data=bytearray(load(TARGET)[0x10000:0x20000]);data[0x1613]^=1
            src=folder/'input.bin';src.write_bytes(data);out=folder/'fixed.bin'
            self.assertEqual(cli.checksum_main(['fix',str(src),'--base',str(TARGET),'--output',str(out)]),0)
            self.assertEqual(out.stat().st_size,65536);self.assertEqual(src.read_bytes(),bytes(data))
            with self.assertRaises(ValueError):cli.checksum_main(['fix',str(src),'--base',str(TARGET),'--output',str(out)])
            with self.assertRaises(ValueError):cli.checksum_main(['fix',str(src),'--base',str(TARGET),'--output',str(src)])

    def test_relocated_offline_tools_do_not_depend_on_sibling_research_or_pyserial(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'standalone'
            for name in ('05_tools',):shutil.copytree(ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__'))
            fixture=root/'synthetic_target.bin';fixture.write_bytes(load(TARGET))
            baseline=root/'synthetic_base.bin';baseline.write_bytes(load(BASELINE))
            commands=[['read.py'],['verify.py',str(fixture)],
                ['write.py',str(fixture),'--baseline',str(baseline)],
                ['checksums.py','verify',str(fixture)]]
            for args in commands:
                result=subprocess.run([sys.executable,'-S',str(root/'05_tools'/args[0]),*args[1:]],cwd=folder,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertNotIn('ME72_6901I41D_research',result.stdout)

    def test_writer_runner_only_succeeds_after_exact_full_postcycle_read(self):
        before,target=load(BASELINE),load(TARGET)
        class ControlECU(ViewECU):
            def __init__(self):
                super().__init__(before[0x10000:0x20000]);self.policy=cli.auth_policy
            def request(self,p,timeout=3):
                if p==bytes.fromhex('30eb01'):
                    self.policy(p);return bytes.fromhex('70eb0101')
                if p==bytes.fromhex('2101'):
                    self.policy(p);meta=bytearray(68);meta[65:68]=bytes.fromhex('81fce5');return bytes(meta)
                return super().request(p,timeout)
            def close(self):pass
        for after in (target,before):
            with self.subTest(exact=after==target),tempfile.TemporaryDirectory() as folder:
                ecu=ControlECU()
                with patch.object(cli,'Transport',return_value=ecu), \
                     patch.object(cli,'baseline',return_value={'live':{'voltage_V':13.87}}), \
                     patch.object(cli,'read_full',side_effect=[before,after]), \
                     patch.object(cli,'authenticate',return_value={'key_accepted':True}), \
                     patch.object(cli,'session_request',return_value=bytes.fromhex('508501')), \
                     patch.object(cli.sys.stdin,'isatty',return_value=True), \
                     patch.object(cli.time,'sleep'),patch('builtins.input',return_value=''),redirect_stdout(StringIO()):
                    args=[str(TARGET),'--baseline',str(BASELINE),'--execute','--port','/dev/cu.usbserial-fake','--run-dir',folder]
                    if after==target:self.assertEqual(cli.write_main(args),0)
                    else:
                        with self.assertRaises(ValueError):cli.write_main(args)
                report=json.loads(next(Path(folder).glob('*/report.json')).read_text())
                self.assertEqual(report['completed'],after==target)
                self.assertEqual(report['postcycle_verified'],after==target)
                self.assertEqual(sum(p==erase_request() for p in ecu.calls),1)
                self.assertEqual(next(Path(folder).glob('*/programming_readback_64KiB.bin')).stat().st_size,65536)

    def test_wrong_live_backup_stops_before_authentication_or_erase(self):
        before=bytearray(load(BASELINE));before[0x11624]^=1
        before=repair(before)
        class NoWrite:
            def request(self,*a,**k):raise AssertionError('No authentication or erase permitted')
            def close(self):pass
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(cli,'Transport',return_value=NoWrite()), \
             patch.object(cli,'baseline',return_value={'live':{'voltage_V':13.87}}), \
             patch.object(cli,'read_full',return_value=before), \
             patch.object(cli.sys.stdin,'isatty',return_value=True),redirect_stdout(StringIO()):
            with self.assertRaises(ValueError):
                cli.write_main([str(TARGET),'--baseline',str(BASELINE),'--execute','--port','/dev/cu.usbserial-fake','--run-dir',folder])
            report=json.loads(next(Path(folder).glob('*/report.json')).read_text())
            self.assertFalse(report['erase_may_have_started']);self.assertFalse(report['completed'])

    def test_repeated_execute_skips_erase_if_target_is_already_installed(self):
        class NoWrite:
            def request(self,*a,**k):raise AssertionError('Already installed: no write permitted')
            def close(self):pass
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(cli,'Transport',return_value=NoWrite()), \
             patch.object(cli,'baseline',return_value={'live':{'voltage_V':13.87}}), \
             patch.object(cli,'read_full',return_value=load(TARGET)), \
             patch.object(cli.sys.stdin,'isatty',return_value=True),redirect_stdout(StringIO()):
            self.assertEqual(cli.write_main([str(TARGET),'--baseline',str(BASELINE),'--execute','--port','/dev/cu.usbserial-fake','--run-dir',folder]),0)
            report=json.loads(next(Path(folder).glob('*/report.json')).read_text())
            self.assertTrue(report['completed']);self.assertTrue(report['no_write']);self.assertFalse(report['erase_may_have_started'])

    def test_live_verifier_never_uses_writer_and_does_not_pass_a_mismatch(self):
        class ReadOnly:
            def request(self,*a,**k):raise AssertionError('No programming service permitted')
            def close(self):pass
        for actual in (load(TARGET),load(BASELINE)):
            with tempfile.TemporaryDirectory() as folder, \
                 patch.object(cli,'Transport',return_value=ReadOnly()), \
                 patch.object(cli,'baseline',return_value={'live':{'voltage_V':13.87}}), \
                 patch.object(cli,'read_full',return_value=actual), \
                 patch.object(cli,'CalibrationWriter') as writer,redirect_stdout(StringIO()):
                code=cli.verify_main([str(TARGET),'--ecu','--execute','--port','/dev/cu.usbserial-fake','--run-dir',folder])
                self.assertEqual(code,0 if actual==load(TARGET) else 1);writer.assert_not_called()


class ResearchTools(unittest.TestCase):
    def test_public_policy_rejects_private_assets_paths_and_fr_links(self):
        sys.path.insert(0,str(ROOT/'09_re_tools'))
        from check_public_tree import check
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'dump.bin').write_bytes(b'not public')
            (root/'notes.txt').write_text('/Users/'+'example/private\n')
            scheme='https';(root/'links.txt').write_text(scheme+'://example.invalid/funktionsrahmen.pdf')
            rules={r['rule'] for r in check(root)['findings']}
            self.assertIn('local_or_private_asset_in_public_payload',rules)
            self.assertIn('personal_home_path',rules)
            self.assertIn('full_fr_download_link_not_allowed',rules)

    def test_repository_manifest_detects_tampering_and_path_escape(self):
        sys.path.insert(0,str(ROOT/'09_re_tools'))
        from manifest import create,check
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'data.txt';p.write_text('original')
            manifest=create(root);self.assertEqual(check(manifest,root),[])
            p.write_text('modified');self.assertTrue(check(manifest,root))
            manifest['files']['../outside']={'bytes':0,'sha256':''}
            self.assertTrue(any('outside repository' in e for e in check(manifest,root)))

    def test_catalog_metadata_matches_records_and_evidence_resolves(self):
        sys.path.insert(0,str(ROOT/'09_re_tools'))
        from audit_repo import build_audit
        report=build_audit()
        self.assertEqual(report['catalog_symbols'],632)
        self.assertEqual(report['proven_symbols'],155)
        self.assertEqual(report['missing_referenced_basenames'],{})
        self.assertFalse(report['vehicle_images_distributed'])
        self.assertTrue(report['consumer_bytes_independently_reverified'])

    def test_corrected_decoder_vectors_and_synthetic_instruction_region(self):
        sys.path.insert(0,str(ROOT/'09_re_tools'))
        from review_decode import D,decode
        vectors=[('9f17','BSET     0xFD2E.9'),('9f2e','BSET     0xFD5C.9'),
                 ('d7400602','EXTP     #0x206,#1'),('dc48','EXTP     R8,#1')]
        for raw,want in vectors:self.assertEqual(D.decode_one(bytes.fromhex(raw),0,0)[2],want)
        image=bytearray(load(BASELINE))
        image[0x75838:0x75840]=bytes.fromhex('f2f4ccb99f6c9e6c')
        text=decode(0x875838,0x875840,image)
        self.assertIn('0xB9CC',text);self.assertIn('0xFDD8.9',text)
        with self.assertRaises(ValueError):decode(0x700000,0x87584E,load(BASELINE))

    def test_xdf_regeneration_exactly_reproduces_packaged_xml(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'generated.xdf'
            command=[sys.executable,'-S',str(ROOT/'09_re_tools/generate_xdf.py'),'--output',str(output)]
            result=subprocess.run(command,cwd=folder,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(output.read_bytes(),(ROOT/'02_xdf/ME72_7532675_6901I41D_from_damos.xdf').read_bytes())
            self.assertNotEqual(subprocess.run(command,cwd=folder,capture_output=True).returncode,0)


if __name__=='__main__':unittest.main(verbosity=2)
