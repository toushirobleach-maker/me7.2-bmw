#!/usr/bin/env python3
"""Import user-supplied references/SP-Daten into gitignored local/, offline."""
import argparse
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_tools'))
from me72.spdaten import reconstruct
from me72.checksum import verify
from me72.images import digest,require
from me72.files import save_bytes,save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program',type=Path);p.add_argument('--data',type=Path)
    p.add_argument('--fr-pdf',type=Path);p.add_argument('--c166-pdf',type=Path)
    p.add_argument('--training-pdf',type=Path);p.add_argument('--a2l',type=Path)
    args=p.parse_args()
    require(bool(args.program)==bool(args.data),'Provide both --program and --data')
    require(any(vars(args).values()),'Select at least one local asset')
    folder=ROOT/'local';copied=[]
    def copy(source,relative,pdf=False):
        source=Path(source);target=folder/relative
        data=source.read_bytes()
        if pdf:require(data.startswith(b'%PDF-'),'Input is not a PDF')
        save_bytes(target,data);copied.append(dict(file=str(target.relative_to(ROOT)),sha256=digest(data)))
    if args.program:
        image,_,_,report=reconstruct(args.program,args.data)
        # Reconstruct/validate BEFORE creating any files. FF gaps remain explicit.
        for target in [folder/'sp_daten/program.0PA',folder/'sp_daten/calibration.0DA',folder/'stock/stock_reconstructed_512KiB.bin',folder/'stock/reconstruction.json']:
            require(not target.exists(),'Local asset already exists: '+str(target))
        copy(args.program,'sp_daten/program.0PA');copy(args.data,'sp_daten/calibration.0DA')
        save_bytes(folder/'stock/stock_reconstructed_512KiB.bin',image)
        report['checksums']=verify(image);report['sha256']=digest(image)
        save_json(folder/'stock/reconstruction.json',report)
    for source,destination in [(args.fr_pdf,'references/BMW_ME72_Funktionsrahmen_1043p.pdf'),
        (args.c166_pdf,'references/Infineon_C166_Instruction_Set.pdf'),
        (args.training_pdf,'references/BMW_ME72_Training.pdf')]:
        if source:copy(source,destination,pdf=True)
    if args.a2l:copy(args.a2l,'definitions/E5A0_000.a2l')
    for item in copied:print('LOCAL_ONLY',item['file'],item['sha256'])
    print('Files are under gitignored local/. They are not part of the public payload.')


if __name__=='__main__':main()
