#!/usr/bin/env python3
"""Audit references in historical reports, not just DAMOS evidence basenames.
Presence by relocated basename is distinguished from exact path resolution.
Intentionally excluded private inputs remain explicit missing dependencies.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlparse
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'.git','__pycache__','.venv','runs','workspace','local','private'}
EXT=r'(?:jsonl?|md|asm|py|cjs|sh|xdf|pdf|txt|csv|png|a2l|bin|prg|ipo|b2v|0PA|0DA|DAT|7z|rar)'
PLAIN=re.compile(r'[A-Za-z0-9_./+%-]+\.'+EXT+r'\b',re.I)


def classify(ref,report,root,by_name,source_map,asset_aliases):
    ref=unquote(ref).strip().strip('<>')
    if ref.startswith(('https://','http://')):return 'external_url',[],None
    clean=ref.split('#')[0].split('?')[0]
    if clean.startswith(('python3 ','python ')):
        return 'symbolic_pattern_or_example',[],None
    if '*' in clean or Path(clean).name in ('_RU.md','_raw_decoder.asm') or clean.startswith('runs/'):
        return 'symbolic_pattern_or_example',[],None
    if clean.startswith('file://'):clean=clean[7:]
    direct=[report.parent/clean,root/clean]
    for path in direct:
        if path.is_file() and path.resolve().is_relative_to(root.resolve()):
            return 'bundled_exact',[str(path.resolve().relative_to(root.resolve()))],None
    normalized=clean.removeprefix('research/').removeprefix('repo/')
    if normalized in source_map:
        path=source_map[normalized]
        if (root/path).is_file():return 'bundled_relocated',[path],None
    basename=Path(clean).name
    if basename in by_name:return 'bundled_by_basename',by_name[basename],None
    if basename in asset_aliases:
        asset=asset_aliases[basename]
        return 'local_input_not_distributed',[],asset
    lower=clean.lower()
    if lower.endswith('.bin') or '06_firmware/' in lower or '09_patched/' in lower or any(s in lower for s in ['build_me72_v3','verify_me72_v3','live_adapt','live_lreb','live_dtc','live_probe','lambda_live','lambda_ram','auth-test_','preflight_','write_v3_','write_minimal_','finalize_checksum_']):
        return 'private_artifact_not_distributed',[],None
    if lower.endswith(('.prg','.ipo','.0pa','.0da','.pdf','.a2l','.7z','.rar')) or basename in ('10EK726_full.asm','EK726Prog_ipo.asm','FR_813_ESKONF.png','FR_885_PROKON.png') or 'fr_relevant_pages' in lower:
        return 'external_input_or_generated_asset_not_distributed',[],None
    return 'missing_research_dependency',[],None


def build(root=ROOT):
    files=[p for p in root.rglob('*') if p.is_file() and not EXCLUDE.intersection(p.relative_to(root).parts)]
    by_name=defaultdict(list)
    for p in files:by_name[p.name].append(str(p.relative_to(root)))
    mapping_path=root/'07_evidence/SOURCE_MAP.json'
    mapping=json.loads(mapping_path.read_text()) if mapping_path.exists() else {'files':[]}
    source_map={r['source']:r['destination'] for r in mapping['files']}
    assets=json.loads((root/'LOCAL_ASSETS.json').read_text())['assets']
    aliases={name:a['id'] for a in assets for name in a.get('aliases',[])}
    reports=[p for p in files if p.suffix.lower() in ('.md','.json') and
        (p.relative_to(root).parts[0]=='04_reports' or any(str(p.relative_to(root)).startswith(s) for s in ['07_evidence/catalog/','07_evidence/reviews/'])) and
        p.name not in ('REPORT_REFERENCES.json','REPORT_REFERENCES_RU.md','MISSING_INPUTS_SUMMARY_RU.md','REPOSITORY_AUDIT_CURRENT.json','PACK_VALIDATION_CURRENT.json','PUBLIC_RELEASE_CHECK.json')]
    found={}
    for report in reports:
        text=report.read_text(errors='replace');candidates=[]
        # Full Markdown and inline-code paths take priority over rough tokens.
        occupied=[]
        for regex in (re.compile(r'\]\(([^)]+)\)'),re.compile(r'`([^`\n]+\.'+EXT+r')`',re.I)):
            for match in regex.finditer(text):
                candidates.append((match.group(1),match.start()));occupied.append(match.span())
        for match in PLAIN.finditer(text):
            if not any(a<=match.start()<b for a,b in occupied):candidates.append((match.group(),match.start()))
        for ref,start in candidates:
            if '/.json' in ref and ref.endswith('.txt/.json'):
                # A human abbreviation denotes two files, not a nested .json.
                ref=ref.replace('.txt/.json','.txt')
            if not re.search(r'\.'+EXT+r'(?:[?#].*)?$',ref,re.I) and not ref.startswith(('http://','https://')):continue
            status,targets,asset=classify(ref,report,root,by_name,source_map,aliases)
            key=(ref,status)
            item=found.setdefault(key,dict(reference=ref,status=status,resolved_to=targets,local_asset=asset,cited_by=[]))
            location=dict(report=str(report.relative_to(root)),line=text.count('\n',0,start)+1)
            if location not in item['cited_by']:item['cited_by'].append(location)
    items=sorted(found.values(),key=lambda x:(x['status'],x['reference']))
    counts=dict(Counter(x['status'] for x in items))
    return dict(reports_scanned=len(reports),unique_references=len(items),status_counts=counts,
        rule='Presence audit only; basename resolution does not certify matching versions or reproducibility.',
        references=items,
        conceptual_missing_inputs=['Internal ROM/IROM image or runtime trace for unresolved page-204 consumers.',
            'Authorized external BMW programming/coding environment for full factory programming and vehicle-specific commissioning.',
            'Original private vehicle trials are not distributed; published conclusions are summaries, not reproducible raw trial evidence.'])


def markdown(result):
    labels={'private_artifact_not_distributed':'Намеренно исключённые материалы машины',
            'local_input_not_distributed':'Локальные исходники и документы',
            'external_input_or_generated_asset_not_distributed':'Внешние материалы / производные файлы',
            'missing_research_dependency':'Действительно недостающие зависимости research'}
    lines=['# Ссылки из отчётов: чего нет в публичном репозитории','',
        f"Проверено отчётов: **{result['reports_scanned']}**. Уникальных ссылок: **{result['unique_references']}**.",
        '','Это проверка наличия, не подтверждение версий/лицензий. Старые пути не считаются исправными только потому, что найден файл с таким basename.',
        '','Полный список, точные исходные отчёты и строки: [REPORT_REFERENCES.json](REPORT_REFERENCES.json).','',
        '| Класс | Ссылок |','| --- | ---: |']
    for status,count in result['status_counts'].items():lines.append(f'| {status} | {count} |')
    for status,title in labels.items():
        rows=[r for r in result['references'] if r['status']==status]
        lines+=['',f'## {title}','']
        if not rows:lines.append('Нет.');continue
        lines+=['| Ссылка | Где упомянута впервые |','| --- | --- |']
        for row in rows:
            where=row['cited_by'][0];link='../'+where['report']
            ref=row['reference'].replace('|','\\|')
            lines.append(f"| `{ref}` | [{where['report']}:{where['line']}]({link}) |")
    lines+=['','## Входы, которые нельзя заменить ещё одним файлом XDF','']
    lines += ['- '+s for s in result['conceptual_missing_inputs']]
    lines+=['','Для локальных импортов см. [LOCAL_ASSETS.json](../LOCAL_ASSETS.json) и [инструкцию](../03_docs/PUBLIC_RELEASE_RU.md).',
        'Отсутствующие private-артефакты не нужно возвращать в публичную сборку. Отчёты, которые от них зависят, остаются историческими утверждениями.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--json-output',type=Path,required=True);p.add_argument('--md-output',type=Path,required=True)
    args=p.parse_args();result=build()
    for path in (args.json_output,args.md_output):
        if path.exists():raise ValueError('Refusing overwrite: '+str(path))
        path.parent.mkdir(parents=True,exist_ok=True)
    with args.json_output.open('x') as handle:json.dump(result,handle,ensure_ascii=False,indent=2);handle.write('\n')
    with args.md_output.open('x') as handle:handle.write(markdown(result))
    print(json.dumps(result['status_counts'],ensure_ascii=False))


if __name__=='__main__':main()
