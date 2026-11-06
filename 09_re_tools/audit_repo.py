#!/usr/bin/env python3
"""Offline inventory/audit of all catalog entries, XDF objects and bundled BINs.
Recorded PROVEN statuses are counted, not independently re-promoted by this audit.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_tools'))
from me72.checksum import verify
from me72.images import digest,load


def build_audit(root=ROOT,image=None):
    catalog=json.loads((root/'01_damos/damos_lite.json').read_text())
    proven=json.loads((root/'01_damos/damos_proven_only.json').read_text())
    symbols=catalog['symbols'];counts=dict(Counter(s['status'] for s in symbols))
    assert counts==catalog['status_counts']
    expected=[s for s in symbols if s['status']=='PROVEN']
    assert proven['symbols']==expected
    with (root/'01_damos/damos_proven_index.csv').open() as handle:
        csv_rows=list(csv.DictReader(handle))
    assert len(csv_rows)==len(expected)==proven['proven_count']
    xdfs=[]
    for path in sorted((root/'02_xdf').glob('*.xdf')):
        tree=ET.parse(path).getroot()
        items=[x for x in tree if x.tag in ('XDFCONSTANT','XDFTABLE','XDFPATCH')]
        statuses=Counter()
        for item in items:
            title=item.findtext('title','');match=re.match(r'\[([A-Z]+)\]',title)
            statuses[match.group(1) if match else 'NO_TAG']+=1
            for data in item.iter('EMBEDDEDDATA'):
                addr=int(data.attrib.get('mmedaddress','0'),0)
                assert 0<=addr<524288,(path,hex(addr))
        xdfs.append(dict(file=str(path.relative_to(root)),objects=len(items),status_counts=dict(statuses)))
    images=[]
    if image is None:
        candidates=list((root/'00_stock').glob('*.bin'))
        image=candidates[0] if candidates else None
    if image is not None:
        data=load(image);checks=verify(data)
        images.append(dict(file='bundled analysis stock' if (root/'00_stock') in Path(image).parents else 'user-supplied local input',bytes=len(data),sha256=digest(data),
            checks_passed=sum(r['ok'] for r in checks),checks_total=len(checks),
            failed=[r for r in checks if not r['ok']],calibration_end_marker=data[0x1FFFC:0x20000].hex()))
    excluded={'.git','__pycache__','.venv','runs','workspace','local','private'}
    all_files=[p for p in root.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(root).parts)]
    by_basename={}
    for p in all_files:by_basename.setdefault(p.name,[]).append(str(p.relative_to(root)))
    refs={}
    for symbol in symbols:
        for value in symbol.get('evidence',{}).values():
            if isinstance(value,str):
                for name in re.findall(r'[A-Za-z0-9_/-]+\.(?:json|asm|md)',value):
                    refs[name]=by_basename.get(Path(name).name,[])
    supplied_image=load(image) if image is not None else None
    consumers=[]
    for symbol in expected:
        consumer=symbol.get('evidence',{}).get('consumer')
        if not isinstance(consumer,dict):continue
        raw=(consumer.get('raw_hex') or '').replace(' ','')
        ea=consumer.get('ea')
        if not raw or not re.fullmatch(r'(?:[0-9a-fA-F]{2})+',raw) or not isinstance(ea,str):continue
        try:offset=int(ea,0)-0x800000
        except ValueError:continue
        b=bytes.fromhex(raw);matches={}
        for label,data in ([('local_input',supplied_image)] if supplied_image is not None else []):
            found=data.find(b,max(0,offset-16),min(len(data),offset+len(b)+16))
            matches[label]=hex(found+0x800000) if found>=0 else None
        consumers.append(dict(symbol=symbol['name'],declared_ea=ea,raw_hex=raw,matches=matches))
    known=[
        'No vehicle BINs, calibration transfer logs or personal identifiers are distributed.',
        'Only the stock analysis BIN is distributed; raw SP-Daten/PDF/complete FR text require local inputs.',
        'The known analysis SP-Daten reconstruction has 37/38 checks and a missing cal end marker.',
        'PROVEN statuses are inherited claims; consumer-byte spot checks against analysis stock do not re-establish semantics.',
        'Legacy reports may refer to deliberately excluded private or external artifacts; see REPORT_REFERENCES.json.',
        'The packaged writer and stock-overlay preparer have offline tests, not a new physical stock-restore qualification.'
    ]
    missing={k:v for k,v in refs.items() if not v}
    return dict(catalog_symbols=len(symbols),status_counts=counts,proven_symbols=len(expected),
        proven_csv_rows=len(csv_rows),xdf=xdfs,images=images,evidence_reference_resolution=refs,
        missing_referenced_basenames=missing,consumer_byte_spot_checks=consumers,
        consumer_byte_spot_checks_not_matched=[r for r in consumers if image is not None and not any(r['matches'].values())],
        consumer_bytes_independently_reverified=image is not None,vehicle_images_distributed=False,
        known_limitations=known,not_a_semantic_reaudit=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--image',type=Path)
    args=p.parse_args();result=build_audit(image=args.image);text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as handle:handle.write(text)
    else:print(text,end='')


if __name__=='__main__':main()
