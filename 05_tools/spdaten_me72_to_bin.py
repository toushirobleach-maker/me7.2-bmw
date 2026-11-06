#!/usr/bin/env python3
"""Offline analysis reconstruction, NOT a directly writable full-flash image.
DAT columns: assembly ZUSB, type, hardware, revision, data ID. The program
filename uses hardware+revision, not the assembly ZUSB. Strict record parsing
is shared with me72.spdaten; bad records and ambiguous selections fail closed.
"""
from dataclasses import dataclass
from pathlib import Path
import argparse,json
from me72.spdaten import reconstruct
from me72.images import digest,require
from me72.files import save_bytes,save_json
from me72.cli import entry


@dataclass
class DatEntry:
    zb:str
    type_number:str
    hardware:str
    prog_rev:str
    data_id:str
    raw:str
    @property
    def program_name(self):return f'{self.hardware}{self.prog_rev}.0PA'
    @property
    def data_name(self):return 'G'+self.data_id.removesuffix('DA')+'.0DA'


def parse_dat(path):
    result=[]
    for line in Path(path).read_text(encoding='latin-1').splitlines():
        parts=[p.strip() for p in line.strip().split(',')]
        if len(parts)<5 or not all(parts[i].isdigit() for i in (0,1,2)):continue
        require(len(parts[3])==1 and parts[3].isalnum(),'Invalid program revision')
        require(parts[4].endswith('DA') and parts[4][:-2].isdigit(),'Unsupported data filename mapping')
        result.append(DatEntry(parts[0],parts[1],parts[2],parts[3],parts[4],line.strip()))
    return result


def find_files(root,entry):
    found={entry.program_name.lower():[],entry.data_name.lower():[]}
    for path in Path(root).rglob('*'):
        if path.is_file() and path.name.lower() in found:found[path.name.lower()].append(path)
    values=[]
    for name in (entry.program_name.lower(),entry.data_name.lower()):
        choices=found[name]
        require(choices,'Source file missing: '+name)
        require(len({digest(p.read_bytes()) for p in choices})==1,'Ambiguous different files named '+name)
        values.append(choices[0])
    return tuple(values)


def intel_hex_to_me72(paths):
    require(len(paths)==2,'Exactly program .0PA and data .0DA are required')
    image,_,_,report=reconstruct(*paths)
    return bytearray(image),dict(report,sha256=digest(image),epk_ascii='6901I41D',flash_base='0x800000',flash_size='0x80000')


def filtered(args):
    rows=parse_dat(args.dat)
    if args.zb:rows=[r for r in rows if r.zb==args.zb]
    if args.hw:rows=[r for r in rows if r.hardware==args.hw]
    if getattr(args,'data_id',None):rows=[r for r in rows if r.data_id.removesuffix('DA')==args.data_id.removesuffix('DA')]
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    listing=sub.add_parser('list');listing.add_argument('--dat',type=Path,required=True)
    build=sub.add_parser('build');build.add_argument('--dat',type=Path);build.add_argument('--pa',type=Path);build.add_argument('--da',type=Path)
    build.add_argument('--data-id');build.add_argument('--sp-root',type=Path);build.add_argument('--epk');build.add_argument('--expected-sha256')
    build.add_argument('-o','--output',type=Path,required=True)
    for parser in (listing,build):
        parser.add_argument('--zb',help='Assembly ZUSB, e.g.7533625 (DAT column1)')
        parser.add_argument('--hw',help='Hardware number, e.g.7532675 (DAT column3)')
    args=p.parse_args()
    if args.command=='list':
        print('ZUSB       TYPE       HW         PROGRAM          DATA')
        for row in filtered(args):print(row.zb,row.type_number,row.hardware,row.program_name,row.data_name)
        return 0
    report_path=args.output.with_suffix(args.output.suffix+'.json')
    require(not args.output.exists() and not report_path.exists(),'Refusing overwrite of output/report')
    require(bool(args.pa)==bool(args.da),'Provide both --pa and --da')
    selected=None
    if args.pa:
        require(not args.dat and not args.zb and not args.hw,'Choose explicit files OR DAT selection')
        pa,da=args.pa,args.da
    else:
        require(args.dat and (args.zb or args.hw),'Provide --dat and --zb or --hw')
        rows=filtered(args)
        require(len(rows)==1,'DAT selection must identify exactly one row; refine --zb/--hw/--data-id')
        selected=rows[0];pa,da=find_files(args.sp_root or args.dat.parent,selected)
    image,info=intel_hex_to_me72([pa,da])
    require(not args.epk or args.epk==info['epk_ascii'],'EPK does not match supported layout')
    require(not args.expected_sha256 or digest(image)==args.expected_sha256.lower(),'SHA-256 mismatch; output not created')
    info.update(operation='analysis_reconstruction_not_flash_ready',program=pa.name,data=da.name,
                output=str(args.output),no_ecu_access=True)
    if selected:info['identity']=dict(zusb=selected.zb,type_number=selected.type_number,hardware=selected.hardware,
        revision=selected.prog_rev,data_id=selected.data_id)
    save_bytes(args.output,image);save_json(report_path,info);print(json.dumps(info,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':raise SystemExit(entry(main))
