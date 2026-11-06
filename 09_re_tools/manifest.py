#!/usr/bin/env python3
"""Create or verify the repository file manifest; excludes runtime/git caches."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'.git','__pycache__','.venv','runs','workspace','local','private'}


def create(root=ROOT):
    files={}
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root)
        if not path.is_file() or EXCLUDE.intersection(relative.parts):continue
        if path.name in ('MANIFEST_SHA256.json','.DS_Store') or path.suffix in ('.pyc','.pending','.partial'):continue
        data=path.read_bytes()
        files[relative.as_posix()]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    return dict(format=1,algorithm='SHA-256',excluded=sorted(EXCLUDE),files=files)


def check(manifest,root=ROOT):
    errors=[]
    for relative,record in manifest['files'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(relative+': path outside repository');continue
        if not path.is_file():errors.append(relative+': missing');continue
        data=path.read_bytes()
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            errors.append(relative+': size/hash mismatch')
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['create','verify']);p.add_argument('--file',type=Path,default=ROOT/'MANIFEST_SHA256.json')
    args=p.parse_args()
    if args.action=='create':
        data=create()
        args.file.parent.mkdir(parents=True,exist_ok=True)
        with args.file.open('x') as handle:json.dump(data,handle,ensure_ascii=False,indent=2);handle.write('\n')
        print('CREATED',len(data['files']),args.file);return 0
    data=json.loads(args.file.read_text());errors=check(data)
    print(json.dumps(dict(files_checked=len(data['files']),ok=not errors,errors=errors),ensure_ascii=False,indent=2))
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(main())
