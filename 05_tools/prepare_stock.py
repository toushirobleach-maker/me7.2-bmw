#!/usr/bin/env python3
"""Prepare a calibration overlay using your own full baseline and SP-Daten.
Offline only. Never flashes, edits EWS/ISN, or invents missing marker bytes.
"""
import argparse
from pathlib import Path
from me72.images import load,digest
from me72.files import save_bytes,save_json
from me72.spdaten import prepare_calibration
from me72.cli import entry


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--program',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();report_path=args.output.with_suffix(args.output.suffix+'.json')
    if args.output.exists() or report_path.exists():raise ValueError('Refusing overwrite of output/report')
    target,report=prepare_calibration(load(args.baseline),args.program,args.data)
    save_bytes(args.output,target);save_json(report_path,report)
    print('OFFLINE_CANDIDATE',args.output,digest(target));print('REPORT',report_path)
    return 0


if __name__=='__main__':raise SystemExit(entry(main))
