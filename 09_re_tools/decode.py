#!/usr/bin/env python3
"""Linear C166 listing with corrected bit-address/EXTP forms, explicit image."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'05_tools'))
from me72.images import load
from review_decode import decode


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path);p.add_argument('--start',type=lambda x:int(x,0),required=True)
    p.add_argument('--end',type=lambda x:int(x,0),required=True);p.add_argument('--output',type=Path)
    args=p.parse_args();data=load(args.image)
    text=decode(args.start,args.end,data)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as handle:handle.write(text)
    else:print(text,end='')


if __name__=='__main__':main()
