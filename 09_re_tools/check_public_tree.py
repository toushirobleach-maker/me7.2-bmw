#!/usr/bin/env python3
"""Check the public working-tree payload, excluding ignored local inputs.
No upload or publication. Reports rules/locations, never matched private values.
Git history must be checked separately before first publication.
"""
from pathlib import Path
import argparse,json,re
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'.git','__pycache__','.venv','runs','workspace','local','private'}
ASSET_EXT={'.bin','.pdf','.0pa','.0da','.prg','.ipo','.a2l','.jsonl'}
PATTERNS={
 'personal_home_path':re.compile(r'''/(?:Users|home)/[^/\s"'<>]+/'''),
 'vehicle_vin':re.compile(r'\b(?:WBA|WBS|WBX|5UX|SAL)[A-HJ-NPR-Z0-9]{14}\b'),
 'specific_usb_serial':re.compile(r'/dev/cu\.usbserial-(?!(?:YOUR_CABLE|EXAMPLE|FAKE|XXXX)\b)[A-Za-z0-9]{5,}'),
}


def check(root=ROOT):
    findings=[];checked=0
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if not p.is_file() or EXCLUDE.intersection(rel.parts):continue
        if p.name.lower() in {'fr_relevant_pages.json','fr_relevant_pages.txt','full_text.txt','pages.jsonl'}:
            findings.append(dict(file=rel.as_posix(),rule='reference_page_text_not_distributed'));continue
        if rel.as_posix()=='00_stock/ME72_7532675_6901I41D_stock_from_G7533626_512KiB.bin':
            import hashlib
            value=p.read_bytes()
            if len(value)!=524288 or hashlib.sha256(value).hexdigest()!='5ec2443311b6173e4f0bb770eb1f84c0a15a270d3bd6ac52648a77d450db5dd9':
                findings.append(dict(file=rel.as_posix(),rule='bundled_stock_hash_does_not_match_allowlist'))
            checked+=1;continue
        if p.suffix.lower() in ASSET_EXT:
            findings.append(dict(file=rel.as_posix(),rule='local_or_private_asset_in_public_payload'));continue
        try:text=p.read_text(encoding='utf-8')
        except UnicodeError:
            findings.append(dict(file=rel.as_posix(),rule='unclassified_binary_asset'));continue
        checked+=1
        for match in re.finditer(r'https?://[^\s\"<>\)]+',text):
            address=unquote(match.group()).lower()
            if any(s in address for s in ['funktionsramen','funktionsrahmen','bmw-me7-2-english','me7_2_english']) or ('bmw-xdfs' in address and any(s in address for s in ['zipball','tarball','codeload','/archive/'])):
                findings.append(dict(file=rel.as_posix(),rule='full_fr_download_link_not_allowed',line=text.count('\n',0,match.start())+1))
        for name,regex in PATTERNS.items():
            for match in regex.finditer(text):
                findings.append(dict(file=rel.as_posix(),rule=name,line=text.count('\n',0,match.start())+1))
        if p.name=='synthetic_oem_vectors.json':
            data=json.loads(text)
            if not (data.get('synthetic_only') and data.get('vehicle_data') is False):
                findings.append(dict(file=rel.as_posix(),rule='fixture_is_not_explicitly_synthetic'))
            block=0
            for row in data.get('captured',[]):
                payload=bytes.fromhex(row['payload'])
                if payload[:1]==b'\x36':
                    # The deterministic 256-byte period contains no vehicle data.
                    expected=bytes(((block*128+i)*37+11)&255 for i in range(128));block+=1
                    if payload[1:]!=expected:
                        findings.append(dict(file=rel.as_posix(),rule='transfer_fixture_contains_non_synthetic_bytes'));break
            if block!=512:findings.append(dict(file=rel.as_posix(),rule='incomplete_synthetic_transfer_fixture'))
    return dict(files_checked=checked,ok=not findings,findings=findings,
                scope='Working tree only; not a legal clearance or proof of absence of all possible personal data')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args();result=check(args.root)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
