#!/usr/bin/env python3
"""Search the packaged DAMOS-lite snapshot; no mutation or ECU access."""
import argparse
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('name',nargs='?',default='');p.add_argument('--status',choices=['PROVEN','STRUCT','HYP','UNLINKED'])
    p.add_argument('--json',action='store_true');args=p.parse_args()
    catalog=json.loads((ROOT/'01_damos/damos_lite.json').read_text())
    rows=[s for s in catalog['symbols'] if args.name.casefold() in s.get('name','').casefold()
          and (args.status is None or s['status']==args.status)]
    if args.json:print(json.dumps(rows,ensure_ascii=False,indent=2))
    else:
        for row in rows:print(f"{row['status']:8} {str(row.get('addr') or 'unlinked'):10} {row['name']}")
        print(f'{len(rows)} matches; PROVEN denotes the recorded claim, not blanket permission for tuning.')


if __name__=='__main__':main()
