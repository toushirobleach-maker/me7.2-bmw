"""Artificial SP-Daten records and synthetic baselines; no copyrighted BINs."""
from pathlib import Path
import sys,tempfile,unittest,subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_tools'))
from fixtures import synthetic_image
from me72.images import PROFILE
from me72.checksum import repair,verify
from me72.spdaten import read_records,prepare_calibration


def record(address,kind,data=b''):
    body=bytes([len(data)])+address.to_bytes(2,'big')+bytes([kind])+data
    return ':'+(body+bytes([-sum(body)&255])).hex().upper()


def write_records(path,segments):
    lines=['; SYNTHETIC TEST DATA; NOT SP-DATEN FOR A VEHICLE']
    upper=None
    for address,data in sorted(segments):
        if address>>16!=upper:
            upper=address>>16;lines += [record(0,4,upper.to_bytes(2,'big')),record(0,2,b'\0\0')]
        for i in range(0,len(data),16):
            chunk=data[i:i+16];lines.append(record((address+i)&65535,0x10 if i%32 else 0,chunk))
    lines.append(record(0,1));path.write_text('\n'.join(lines)+'\n')


class SPDatenTests(unittest.TestCase):
    def test_dat_assembly_zusb_is_not_hardware_program_number(self):
        import spdaten_me72_to_bin as builder
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'example.DAT'
            path.write_text('7533625,7500213,7532675,A,7533626DA,0FFFFFFFFFD,134,1 E\n')
            rows=builder.parse_dat(path);self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].zb,'7533625');self.assertEqual(rows[0].hardware,'7532675')
            self.assertEqual(rows[0].program_name,'7532675A.0PA')
            self.assertEqual(rows[0].data_name,'G7533626.0DA')

    def test_builder_does_not_create_output_on_expected_hash_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);_,program,data=self.inputs(folder);output=folder/'output.bin'
            result=subprocess.run([sys.executable,str(ROOT/'05_tools/spdaten_me72_to_bin.py'),'build',
                '--pa',str(program),'--da',str(data),'--expected-sha256','0'*64,'-o',str(output)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse(output.exists())

    def inputs(self,folder):
        source=synthetic_image()
        program=folder/'program.0PA';data=folder/'cal.0DA'
        prog=[(0x808010,source[0x8010:0x8038])]
        for offset,raw in PROFILE['erase_bound_vectors'].items():prog.append((0x800000+int(offset,16),bytes.fromhex(raw)))
        cal=[(0x810000,source[0x10000:0x10002]),(0x800000+PROFILE['epk_offset'],b'6901I41D'),(0x819CC4,b'\x57')]
        cal += [(0x800000+r['offset'],source[r['offset']:r['offset']+16]) for r in PROFILE['multipoint']]
        cal += [(0x81FD26,b'FAKE_FACTORY_ID'),(0x81FD54,b'FAKE_FACTORY_UIF')]
        write_records(program,prog);write_records(data,cal)
        return source,program,data

    def test_overlay_preserves_gaps_markers_identity_and_program(self):
        with tempfile.TemporaryDirectory() as folder:
            before,program,data=self.inputs(Path(folder));before=bytearray(before)
            before[0x19010]=0xA7;before[0x1FD26:0x1FD33]=b'SYNTHETIC_ID!'
            before[0x1FD54:0x1FD62]=b'SYNTHETIC_UIF!'
            before=repair(before)
            result,report=prepare_calibration(before,program,data)
            self.assertEqual(result[0x19CC4],0x57)
            self.assertEqual(result[0x19010],0xA7)
            self.assertEqual(result[0x1FD26:0x1FD44],before[0x1FD26:0x1FD44])
            self.assertEqual(result[0x1FD54:0x20000],before[0x1FD54:0x20000])
            self.assertEqual(result[:0x10000],before[:0x10000]);self.assertEqual(result[0x20000:],before[0x20000:])
            self.assertTrue(all(c['ok'] for c in verify(result)))
            self.assertTrue(report['program_covered_bytes_match'])

    def test_different_known_program_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            before,program,data=self.inputs(Path(folder));bad=bytearray(before);bad[0x8018]^=1
            bad=repair(bad)
            with self.assertRaisesRegex(ValueError,'Known .0PA bytes differ'):
                prepare_calibration(bad,program,data)

    def test_unverified_or_missing_marker_baseline_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            before,program,data=self.inputs(Path(folder));bad=bytearray(before);bad[0x1FFFC:0x20000]=b'\xff'*4
            with self.assertRaises(ValueError):prepare_calibration(bad,program,data)
            with self.assertRaises(ValueError):prepare_calibration(repair(bad),program,data)

    def test_hex_checksum_nonzero_segment_and_unknown_types_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invalid.0DA'
            for text in [':0100000000FE\n',record(0,2,b'\0\1')+'\n',record(0,5,b'\0'*4)+'\n']:
                path.write_text(text)
                with self.assertRaises(ValueError):read_records(path)

    def test_conflicting_records_and_out_of_range_data_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invalid.0DA'
            for text in [record(0,4,b'\x00\x81')+'\n'+record(0,0,b'A')+'\n'+record(0,0,b'B')+'\n'+record(0,1),
                         record(0,0,b'A')+'\n'+record(0,1)]:
                path.write_text(text)
                with self.assertRaises(ValueError):read_records(path)


if __name__=='__main__':unittest.main(verbosity=2)
