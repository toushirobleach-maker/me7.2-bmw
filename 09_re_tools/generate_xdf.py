#!/usr/bin/env python3
"""Generate TunerPro XDF from damos_lite.json (no hand-maintained map list)."""
from __future__ import annotations

import json
import re
from collections import Counter

from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#013;&#010;")
        .replace("'", "&apos;")
    )


def status_tag(status: str) -> str:
    return {
        "PROVEN": "[PROVEN]",
        "STRUCT": "[STRUCT]",
        "HYP": "[HYP]",
        "HYPOTHESIS": "[HYP]",
        "UNLINKED": "[UNLINKED]",
    }.get(status, "[STRUCT]")


def title_for(sym: dict) -> str:
    status = sym.get("status", "STRUCT")
    name = sym.get("name") or "unnamed"
    title = sym.get("title") or f"{status_tag(status)} {name}"
    body = re.sub(r"^\[(PROVEN|STRUCT|HYP|HYPOTHESIS|UNLINKED)\]\s*", "", title).strip() or name
    return f"{status_tag(status)} {body}"


def cat_for(name: str, kind: str) -> int:
    n = (name or "").upper()
    if kind == "patch":
        return 7
    if n.startswith("CLA") or "DFPM" in n:
        return 2
    if n.startswith(("CW", "CD", "ESK", "MSL", "SAP")):
        return 1
    if n.startswith(("TA", "TM", "TL", "DT", "CLR", "LR")):
        return 3
    if "KFZW" in n or "IGN" in n:
        return 4
    if n.startswith(("KFE", "TAM", "FAN")) or "THERM" in n or "88C" in n:
        return 5
    if "SPEED" in n or "VMAX" in n:
        return 6
    return 0


def main() -> None:
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
    parts: list[str] = [
        "<!-- generated from damos_lite.json — do not hand-edit; regenerate -->",
        '<XDFFORMAT version="1.60">',
        "  <XDFHEADER>",
        "    <flags>0x1</flags>",
        "    <fileversion>3</fileversion>",
        "    <deftitle>ME7.2 6901I41D DAMOS-lite generated</deftitle>",
        f"    <description>{esc('Generated from 07_analysis/damos_lite/damos_lite.json. Status tags auto. Full 512KiB file offsets. After patch: multipoint THEN CRC32.')}</description>",
        "    <author>damos_pipeline</author>",
        '    <BASEOFFSET offset="0" subtract="0" />',
        '    <DEFAULTS datasizeinbits="8" sigdigits="2" outputtype="1" signed="0" lsbfirst="0" float="0" />',
        '    <REGION type="0xFFFFFFFF" startaddress="0x0" size="0x80000" regionflags="0x0" name="Full 512KiB flash" desc="cal 0x10000" />',
    ]
    for i, n in [
        (0, "00 Identity"),
        (1, "01 Config"),
        (2, "02 DFPM"),
        (3, "03 LREB"),
        (4, "04 Ignition"),
        (5, "05 Thermo/fan"),
        (6, "06 Limiters"),
        (7, "07 Patches"),
        (8, "08 Unlinked FR"),
    ]:
        parts.append(f'    <CATEGORY index="{hex(i)}" name="{esc(n)}" />')
    parts.append("  </XDFHEADER>")

    uid = 0x6A010000
    counts: Counter[str] = Counter()

    def next_uid() -> int:
        nonlocal uid
        uid += 1
        return uid

    for sym in damos["symbols"]:
        # XDF objects only for linked / patch items (parity with proven manifest)
        kind = sym.get("kind", "scalar")
        status = sym.get("status", "STRUCT")
        name = sym.get("name") or "unnamed"
        title = title_for(sym)
        source = sym.get("source")

        if kind == "patch":
            entries = sym.get("entries") or []
            if not entries:
                continue
            u = next_uid()
            note = (sym.get("evidence") or {}).get("note") or ""
            parts.append(f'  <XDFPATCH uniqueid="{hex(u)}">')
            parts.append(f"    <title>{esc(title)}</title>")
            description = f'STATUS: {status}\\nEVIDENCE: {note}\\nBASEDATA=SP-Daten stock. After apply: multipoint THEN CRC32.'
            parts.append(f"    <description>{esc(description)}</description>")
            parts.append('    <CATEGORYMEM index="0" category="7" />')
            for e in entries:
                a = int(e["addr"], 16)
                ln = int(e["len"])
                parts.append(
                    f'    <XDFPATCHENTRY name="{esc(e.get("name","e"))}" address="{hex(a)}" '
                    f'datasize="{hex(ln)}" patchdata="{e["patch"]}" basedata="{e["base"]}" />'
                )
            parts.append("  </XDFPATCH>")
            counts["patch"] += 1
            continue

        addr = sym.get("addr")
        if not addr:
            continue
        # skip pure FR-unlinked additions (no binary binding)
        if source == "fr_catalog" and status == "UNLINKED":
            continue

        a = int(addr, 16)
        cat = cat_for(name, kind)
        eq = sym.get("equation") or "X"
        sizebits = int(sym.get("sizebits") or 8)
        le = bool(sym.get("le", False))
        signed = bool(sym.get("signed", False))
        rows = sym.get("rows")
        cols = sym.get("cols")
        fr = ",".join(str(p) for p in (sym.get("fr_pages") or [])[:5])
        note = (sym.get("evidence") or {}).get("note") or ""

        if kind == "map" or (rows and cols):
            rows_i = int(rows or 1)
            cols_i = int(cols or 1)
            u = next_uid()
            signed_flag = ' mmedtypeflags="0x1"' if signed else ""
            parts.append(f'  <XDFTABLE uniqueid="{hex(u)}" flags="0x0">')
            parts.append(f"    <title>{esc(title)}</title>")
            description = f'STATUS: {status}\\nEVIDENCE: {note}\\nFR: {fr}\\nFILE: {hex(a)} {rows_i}x{cols_i}'
            parts.append(f"    <description>{esc(description)}</description>")
            parts.append(f'    <CATEGORYMEM index="0" category="{cat}" />')
            parts.append(
                '    <XDFAXIS id="x" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" '
                'mmedmajorstridebits="-32" mmedminorstridebits="0" />'
            )
            parts.append(
                f'      <indexcount>{cols_i}</indexcount><datatype>0</datatype><unittype>0</unittype>'
                f'<DALINK index="0" />'
            )
            for i in range(cols_i):
                parts.append(f'      <LABEL index="{i}" value="{i}" />')
            parts.append('      <MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>')
            parts.append(
                '    <XDFAXIS id="y" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" '
                'mmedmajorstridebits="-32" mmedminorstridebits="0" />'
            )
            parts.append(
                f'      <indexcount>{rows_i}</indexcount><datatype>0</datatype><unittype>0</unittype>'
                f'<DALINK index="0" />'
            )
            for i in range(rows_i):
                parts.append(f'      <LABEL index="{i}" value="{i}" />')
            parts.append('      <MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>')
            parts.append(
                f'    <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="{hex(a)}" mmedelementsizebits="8"'
                f'{signed_flag} mmedrowcount="{rows_i}" mmedcolcount="{cols_i}" '
                f'mmedmajorstridebits="0" mmedminorstridebits="0" />'
            )
            parts.append(
                f'      <decimalpl>2</decimalpl><datatype>0</datatype><unittype>0</unittype>'
                f'<DALINK index="0" /><MATH equation="{esc(eq)}"><VAR id="X" /></MATH></XDFAXIS>'
            )
            parts.append("  </XDFTABLE>")
            counts["table"] += 1
            continue

        # scalar / constant
        flags = (0x01 if signed else 0) | (0x02 if le else 0)
        flagattr = f' mmedtypeflags="{hex(flags)}"' if flags else ""
        u = next_uid()
        parts.append(f'  <XDFCONSTANT uniqueid="{hex(u)}">')
        parts.append(f"    <title>{esc(title)}</title>")
        description = f'STATUS: {status}\\nEVIDENCE: {note}\\nFR: {fr}\\nFILE: {hex(a)}'
        parts.append(f"    <description>{esc(description)}</description>")
        parts.append(f'    <CATEGORYMEM index="0" category="{cat}" />')
        parts.append(
            f'    <EMBEDDEDDATA mmedaddress="{hex(a)}" mmedelementsizebits="{sizebits}"{flagattr} '
            f'mmedmajorstridebits="0" mmedminorstridebits="0" />'
        )
        parts.append('    <datatype>0</datatype><unittype>0</unittype><DALINK index="0" />')
        parts.append(f'    <MATH equation="{esc(eq)}"><VAR id="X" /></MATH>')
        parts.append("  </XDFCONSTANT>")
        counts["constant"] += 1

    parts.append("</XDFFORMAT>")
    GENERATED_XDF.write_text("\n".join(parts) + "\n", encoding="utf-8")

    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"items": []}
    man_counts = Counter(it.get("kind") for it in man.get("items", []))
    seed_syms = [s for s in damos["symbols"] if s.get("source") == "XDF_MANIFEST"]
    seed_counts = Counter(
        ("constant" if s["kind"] == "scalar" else s["kind"]) for s in seed_syms
    )
    report = {
        "generated_xdf": str(GENERATED_XDF),
        "emitted": dict(counts),
        "emitted_total": sum(counts.values()),
        "manifest_kind_counts": dict(man_counts),
        "seed_kind_counts": dict(seed_counts),
        "parity_ok_seed_subset": {
            "constant": seed_counts.get("constant", 0) == man_counts.get("constant", 0),
            "map": seed_counts.get("map", 0) == man_counts.get("table", 0),
            "patch": seed_counts.get("patch", 0) == man_counts.get("patch", 0),
        },
        "parity_note": "Full XDF includes linked STRUCT/HYP; seed subset must match manifest kinds",
        "damos_status_counts": damos.get("status_counts"),
        "damos_symbols": len(damos["symbols"]),
        "manifest_items": len(man.get("items", [])),
    }
    out = PROVEN_DIR / "DAMOS_XDF_GEN_REPORT.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,default=ROOT/'01_damos/damos_lite.json')
    parser.add_argument('--manifest',type=Path,default=ROOT/'02_xdf/XDF_MANIFEST.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    DAMOS_LITE, MANIFEST, GENERATED_XDF = args.catalog, args.manifest, args.output
    PROVEN_DIR=args.output.parent
    if args.output.exists() or (PROVEN_DIR/'DAMOS_XDF_GEN_REPORT.json').exists():
        parser.error('Refusing to overwrite XDF or generation report')
    PROVEN_DIR.mkdir(parents=True,exist_ok=True)
    main()
