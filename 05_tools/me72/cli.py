"""Separate entry points; all hardware modes require an explicit --execute."""
import argparse
import json
from pathlib import Path
import sys
import time
from .images import ROOT, PROFILE, load, validate, require, digest, diff, calibration_transition
from .checksum import verify, repair, storage_offsets
from .files import stamp, save_bytes, save_json, update_report
from .transport import Transport, Journal, readonly_policy, ProtocolError
from .protocol import (baseline, authenticate, auth_policy, session_request,
                       erase_request, download_request, transfer_request)
from .reader import read_full
from .writer import CalibrationWriter, UIF_SAMPLE_OFFSET, UIF_SAMPLE_LENGTH
from . import diagnostics


def print_json(value):print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)


def summary(data):
    rows=verify(data)
    return dict(profile=PROFILE['id'],bytes=len(data),sha256=digest(data),
                checksums_ok=all(c['ok'] for c in rows),checksums=rows,
                calibration_end_marker=data[0x1FFFC:0x20000].hex(),
                car_tested_end_marker_present=data[0x1FFFC:0x20000]==bytes.fromhex('5aa5c33c'),
                note='Checksum validity does not establish completeness, origin or suitability for flashing')


def report_paths(kind, directory):
    folder=Path(directory or ROOT/'runs')/(kind+'_'+stamp())
    folder.mkdir(parents=True,exist_ok=False)
    path=folder/'report.json'
    save_json(path,dict(operation=kind,completed=False))
    return folder,path


def need_port(args):
    require(bool(args.port),'--port is required with --execute; no device was opened')


def read_main(argv=None):
    p=argparse.ArgumentParser(description='Read-only ME7.2 flash, DTC, RAM or lambda snapshot; default is a plan.')
    p.add_argument('--kind',choices=['flash','dtc','ram','lambda'],default='flash')
    p.add_argument('--port');p.add_argument('--execute',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--run-dir',type=Path)
    p.add_argument('--baud',type=int,choices=[9600,124800],default=124800)
    p.add_argument('--samples',type=int,default=16)
    args=p.parse_args(argv)
    require(1<=args.samples<=60,'--samples must be 1..60')
    if not args.execute:
        print_json(dict(mode='plan_no_port_opened',kind=args.kind,port=args.port,
            baud=args.baud if args.kind=='flash' else 9600,
            bytes=524288 if args.kind=='flash' else None));return 0
    need_port(args)
    if args.output:require(not args.output.exists(),'Output exists; refusing overwrite')
    folder,path=report_paths('read_'+args.kind,args.run_dir)
    report=dict(operation='read_'+args.kind,read_only=True,completed=False,port=args.port)
    journal=Journal(folder/'wire.jsonl');link=None
    try:
        link=Transport(args.port,journal,readonly_policy if args.kind=='flash' else diagnostics.policy)
        if args.kind=='flash':
            report['initial_baseline']=baseline(link,minimum_voltage=11.0)
            output=args.output or folder/'full_512KiB.bin'
            data=read_full(link,output,args.baud)
            report.update(binary=str(output.resolve()),image=summary(data))
        else:
            ident=link.request(b'\xa2')
            require(ident[:8]==b'\xe27532675','Unexpected DME identity')
            report['identity']=ident.hex()
            report['data']={'dtc':diagnostics.read_dtcs,'ram':diagnostics.read_ram,
                            'lambda':lambda t:diagnostics.read_lambda(t,args.samples)}[args.kind](link)
            if args.output:save_json(args.output,report['data'])
        report['completed']=True
        print_json(report)
        return 0
    except BaseException as exc:
        report['error']=f'{type(exc).__name__}: {exc}';raise
    finally:
        if link:link.close()
        journal.close();update_report(path,report);print('REPORT',path,flush=True)


def verify_main(argv=None):
    p=argparse.ArgumentParser(description='Offline image/checksum verification or explicit full ECU readback comparison.')
    p.add_argument('image',type=Path);p.add_argument('--base',type=Path)
    p.add_argument('--compare',type=Path);p.add_argument('--report',type=Path)
    p.add_argument('--ecu',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--port');p.add_argument('--run-dir',type=Path)
    args=p.parse_args(argv)
    require(not args.execute or args.ecu,'--execute applies only together with --ecu')
    data=load(args.image,args.base);result=summary(data)
    ok=result['checksums_ok']
    if args.compare:
        other=load(args.compare)
        result['comparison']=dict(file=str(args.compare),sha256=digest(other),
            exact_match=other==data,differing_bytes=sum(a!=b for a,b in zip(data,other)))
        ok=ok and other==data
    if not args.ecu or not args.execute:
        result['mode']='ecu_comparison_plan_no_port_opened' if args.ecu else 'offline'
        if args.report:save_json(args.report,result)
        print_json(result);return 0 if ok else 1
    need_port(args)
    require(result['checksums_ok'],'Target image has invalid checksums')
    folder,path=report_paths('verify_ecu',args.run_dir)
    report=dict(operation='verify_ecu',read_only=True,completed=False,target_sha256=digest(data))
    journal=Journal(folder/'wire.jsonl');link=None
    try:
        link=Transport(args.port,journal)
        report['baseline']=baseline(link,minimum_voltage=11.0)
        actual=read_full(link,folder/'readback_512KiB.bin')
        report.update(actual=summary(actual),exact_match=actual==data,
            differing_bytes=sum(a!=b for a,b in zip(actual,data)))
        report['completed']=actual==data and report['actual']['checksums_ok']
        print_json(report);return 0 if report['completed'] else 1
    except BaseException as exc:
        report['error']=f'{type(exc).__name__}: {exc}';raise
    finally:
        if link:link.close()
        journal.close();update_report(path,report);print('REPORT',path,flush=True)


def checksum_main(argv=None):
    p=argparse.ArgumentParser(description='Offline verification or repair of all 38 checks; never connects to a device.')
    p.add_argument('action',choices=['verify','fix']);p.add_argument('image',type=Path)
    p.add_argument('--base',type=Path);p.add_argument('--output',type=Path);p.add_argument('--report',type=Path)
    args=p.parse_args(argv)
    data=load(args.image,args.base)
    if args.action=='verify':
        require(args.output is None,'--output is only valid for fix')
        result=summary(data)
        if args.report:save_json(args.report,result)
        print_json(result);return 0 if result['checksums_ok'] else 1
    require(args.output is not None,'fix requires --output; input is never modified')
    require(not args.output.exists(),'Output exists; refusing overwrite')
    report_path=args.report or args.output.with_suffix(args.output.suffix+'.json')
    require(not report_path.exists(),'Report exists; refusing overwrite')
    require(report_path.resolve()!=args.output.resolve(),'Binary and report must have different paths')
    repaired=repair(data)
    changes=diff(data,repaired)
    require(all(int(c['offset'],16) in storage_offsets() for c in changes),
            'Repair unexpectedly modified data outside checksum storage')
    short=args.image.stat().st_size==65536
    if short:
        require(data[:0x10000]==repaired[:0x10000] and data[0x20000:]==repaired[0x20000:],
                'The base needs checksum repairs outside calibration; use full 512 KiB input/output')
    output=repaired[0x10000:0x20000] if short else repaired
    result=dict(operation='offline_checksum_repair',input=str(args.image.resolve()),input_sha256=digest(args.image.read_bytes()),
        output=str(args.output.resolve()),output_sha256=digest(output),output_bytes=len(output),
        changed_checksum_bytes=changes,verification=summary(repaired))
    save_bytes(args.output,output);save_json(report_path,result);print_json(result);return 0


def sequence(target):
    cal=target[0x10000:0x20000]
    return ([erase_request(),download_request(0x810000,65536)] +
            [transfer_request(cal[i:i+128]) for i in range(0,65536,128)] + [b'\x37',b'\x31\x01'])


class SequenceLink:
    """Second independent gate: exact transaction payload/order for this image."""
    def __init__(self,link,expected):self.link,self.expected,self.index=link,expected,0
    @property
    def policy(self):return self.link.policy
    @policy.setter
    def policy(self,value):self.link.policy=value
    def request(self,payload,timeout=3):
        destructive=payload[0] in (0x31,0x34,0x36,0x37)
        if destructive:
            require(self.index<len(self.expected) and payload==self.expected[self.index],
                    'Outgoing command differs from image-specific transaction plan')
        response=self.link.request(payload,timeout=timeout)
        if destructive:self.index+=1
        return response
    def read_flash(self,*args,**kwargs):return self.link.read_flash(*args,**kwargs)


def write_main(argv=None):
    p=argparse.ArgumentParser(description='64 KiB calibration writer; default is offline plan. No full-flash writing.')
    p.add_argument('image',type=Path);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--port');p.add_argument('--execute',action='store_true')
    p.add_argument('--run-dir',type=Path);p.add_argument('--plan-out',type=Path)
    p.add_argument('--min-voltage',type=float,default=12.5)
    args=p.parse_args(argv)
    require(11.5<=args.min_voltage<=14.8,'--min-voltage must be 11.5..14.8 V')
    before=load(args.baseline);target=load(args.image,args.baseline)
    changes=calibration_transition(before,target)
    require(all(c['ok'] for c in verify(before)),'Baseline checksum failure')
    require(all(c['ok'] for c in verify(target)),'Target checksum failure')
    expected=sequence(target)
    report=dict(operation='write_calibration_64KiB',profile=PROFILE['id'],baseline_sha256=digest(before),
        target_full_sha256=digest(target),target_cal_sha256=digest(target[0x10000:0x20000]),
        range=['0x810000','0x81FFFF'],bytes=65536,block_size=128,blocks=512,
        payloads=len(expected),changes=changes,min_voltage=args.min_voltage,
        completed=False,erase_may_have_started=False,postcycle_verified=False,
        qualification='Protocol tested on one ECU; packaged refactor tested offline; input semantics require review')
    if args.plan_out:save_json(args.plan_out,report)
    if not args.execute:
        report['mode']='plan_no_port_opened';print_json(report);return 0
    need_port(args)
    require(sys.stdin.isatty(),'--execute requires an interactive terminal for the physical ignition cycle')
    folder,path=report_paths('write_calibration',args.run_dir)
    journal=Journal(folder/'wire.jsonl');link=None;writer=None;programming=False
    update_report(path,report)
    try:
        link=Transport(args.port,journal,auth_policy)
        report['initial_baseline']=baseline(link,args.min_voltage)
        current=read_full(link,folder/'before_512KiB.bin')
        report['fresh_backup_sha256']=digest(current)
        update_report(path,report)
        if current==target:
            report.update(completed=True,postcycle_verified=True,no_write=True,result='target_already_installed')
            print('ALREADY_INSTALLED_EXACT_FULL_IMAGE_MATCH',digest(current),flush=True);return 0
        require(current==before,'Live full image differs from --baseline; no erase allowed')
        observations=[]
        for _ in range(5):
            observations.append(baseline(link,args.min_voltage)['live']['voltage_V']);time.sleep(0.15)
        require(max(observations)-min(observations)<=0.30,'Supply readings fluctuate over 0.30 V')
        report['voltage_samples_V']=observations
        require(link.request(bytes.fromhex('30eb01'))==bytes.fromhex('70eb0101'),'Unexpected programming status')
        metadata=link.request(bytes.fromhex('2101'))
        require(metadata[0x45-4:0x48-4]==bytes.fromhex('81fce5'),'Wrong transfer-limit pointer')
        limit=link.read_flash(0x81FCE5,1,memory_type=True)[0]
        require(limit==240,'Unexpected transfer limit')
        report['authentication']=authenticate(link)
        programming=True
        require(session_request(link,bytes.fromhex('108501'))[:3]==bytes.fromhex('508501'),
                'Programming session not confirmed')
        require(link.read_flash(0x810000,16,memory_type=True)==before[0x10000:0x10010],
                'Programming-session address sample differs')
        uif=link.read_flash(0x810000+UIF_SAMPLE_OFFSET,UIF_SAMPLE_LENGTH,memory_type=True)
        report['pre_erase_uif_reference']=uif.hex()
        writer=CalibrationWriter(before,target,programming_uif_reference=uif)
        writer.arm(authentication_ok=True,session_ok=True,max_block_length=limit,
                   supply_ok=True,erase_boundary_reviewed=True)
        report.update(stage='armed_before_erase',erase_may_have_started=True);update_report(path,report)
        gate=SequenceLink(link,expected)
        writer.run(gate,journal)
        require(gate.index==len(expected),'Incomplete transaction sequence')
        report.update(stage=writer.state,oem_checksum_ok=True,ignition_cycle_required=True)
        update_report(path,report)
        print('Выключи зажигание полностью на 30 секунд, затем включи II. Двигатель не запускай.',flush=True)
        input('После переключения нажми Enter для полного контрольного чтения: ')
        link.policy=auth_policy;programming=False
        report['postcycle_baseline']=baseline(link,minimum_voltage=11.0)
        actual=read_full(link,folder/'after_512KiB.bin')
        report['actual_full_sha256']=digest(actual)
        require(actual==target,'Postcycle full image differs from target; no automatic rewrite')
        require(all(c['ok'] for c in verify(actual)),'Postcycle checksum failure')
        report.update(completed=True,postcycle_verified=True,ignition_cycle_required=False,
                      stage='verified_after_cycle',result='exact_full_image_match')
        print('SUCCESS_EXACT_FULL_IMAGE_MATCH',digest(actual),flush=True);return 0
    except BaseException as exc:
        report.update(error=f'{type(exc).__name__}: {exc}',stage=writer.state if writer else 'before_erase')
        if writer:report['erase_may_have_started']=writer.erase_may_have_started
        if programming:print('STOPPED: не запускай двигатель; сохрани отчёт. Повторного стирания/сброса не будет.',flush=True)
        raise
    finally:
        if link:link.close()
        journal.close()
        if writer:
            report['blocks_acknowledged']=writer.blocks_acknowledged
            if writer.last_readback is not None:
                try:
                    save_bytes(folder/'programming_readback_64KiB.bin',writer.last_readback)
                    report['programming_readback_sha256']=digest(writer.last_readback)
                except OSError as exc:
                    report['readback_save_error']=str(exc)
        update_report(path,report);print('REPORT',path,flush=True)


def entry(main):
    try:return main()
    except (ValueError,OSError,ProtocolError,TimeoutError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 2
    except KeyboardInterrupt:
        print('INTERRUPTED: consult the saved report before any further vehicle action.',file=sys.stderr);return 130
