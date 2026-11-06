#!/usr/bin/env python3
"""Link FR/A2L symbol names → 6901 cal addresses via local E5A0 relocation.

Status policy (evidence rules):
- Never auto-PROVEN from foreign A2L.
- STRUCT: reloc + validation (cluster consistency and/or EXTP/header).
- HYP: reloc only (перенесено из другого SW).
- Existing PROVEN/STRUCT addresses are never overwritten.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from paths import (
    CACHE_DIR,
    DAMOS_LITE,
    FR_CATALOG,
    MAP_HEADERS,
    OUT_DIR,
    ROOT,
    XREF_HITS,
)

A2L_PATH = (
    ROOT
    / "02_definitions/BMW-XDFs/Me7.2/BMW ME7.2 X5 4.4 V8/E5A0_000.a2l"
)
A2L_CACHE = OUT_DIR / "a2l_e5a0_chars.json"
LINK_REPORT = OUT_DIR / "LINK_REPORT.json"

FAMILY_RE = re.compile(
    r"^(?:CW|CD|KF|CLA|MSL|DZW|KR|ESK|LR|TE|SL|TM|TA|FF|FK|NW|ET|ML|ZW|DT|CL)"
    r"[A-Z0-9_]{1,24}$"
)


def parse_a2l(path: Path) -> dict[str, dict]:
    if A2L_CACHE.exists() and A2L_CACHE.stat().st_mtime >= path.stat().st_mtime:
        return json.loads(A2L_CACHE.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8", errors="ignore")
    chars: dict[str, dict] = {}
    for m in re.finditer(
        r"/begin CHARACTERISTIC\s+(\w+)\s+\"([^\"]*)\"\s+(\w+)\s+(0x[0-9A-Fa-f]+)",
        text,
    ):
        name, desc, typ, cpu_s = m.group(1), m.group(2), m.group(3), m.group(4)
        cpu = int(cpu_s, 16)
        block = text[m.end() : m.end() + 1200]
        end = block.find("/end CHARACTERISTIC")
        if end >= 0:
            block = block[:end]
        axes = [int(x) for x in re.findall(r"STD_AXIS\s+\S+\s+\S+\s+(\d+)", block)]
        blob = re.search(r"DP_BLOB\s+0x[0-9A-Fa-f]+\s+0x([0-9A-Fa-f]+)", block)
        rows = cols = None
        if typ == "MAP" and len(axes) >= 2:
            cols, rows = axes[0], axes[1]
        elif typ == "CURVE" and axes:
            cols, rows = axes[0], 1
        elif typ == "VAL_BLK" and axes:
            cols, rows = axes[0], 1
        chars[name] = {
            "type": typ,
            "cpu": cpu,
            "file": cpu - 0x800000,
            "desc": desc[:120],
            "rows": rows,
            "cols": cols,
            "blob_size": int(blob.group(1), 16) if blob else None,
        }
    A2L_CACHE.parent.mkdir(parents=True, exist_ok=True)
    A2L_CACHE.write_text(json.dumps(chars, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return chars


def nearest_deltas(
    file_off: int, anchors: list[tuple[str, int, int]], window: int = 0x400
) -> list[tuple[str, int, int]]:
    """Return (anchor_name, delta, distance) within window, sorted by distance."""
    hits = []
    for name, a_e5, delta in anchors:
        dist = abs(file_off - a_e5)
        if dist <= window:
            hits.append((name, delta, dist))
    hits.sort(key=lambda x: (x[2], abs(x[1])))
    return hits


def predict_addr(file_off: int, near: list[tuple[str, int, int]]) -> tuple[int | None, dict]:
    if not near:
        return None, {"reason": "no_anchor"}
    # Use closest anchor; require agreement among top anchors within 0x80 if multiple
    name0, d0, dist0 = near[0]
    pred = file_off + d0
    agreeing = [n for n in near if n[1] == d0 and n[2] <= max(0x80, dist0)]
    conflicting = [n for n in near[:5] if n[1] != d0 and n[2] <= 0x40]
    meta = {
        "anchor": name0,
        "delta": d0,
        "dist": dist0,
        "agreeing": len(agreeing),
        "conflicts": [(c[0], c[1], c[2]) for c in conflicting],
    }
    if conflicting and conflicting[0][2] < dist0:
        # closer conflict — ambiguous
        return None, {**meta, "reason": "delta_conflict"}
    if not (0x10000 <= pred <= 0x1FFFF):
        return None, {**meta, "reason": "out_of_cal"}
    return pred, {**meta, "reason": "ok"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    chars = parse_a2l(A2L_PATH)
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
    catalog = json.loads(FR_CATALOG.read_text(encoding="utf-8")) if FR_CATALOG.exists() else []
    fr_pages = {c["name"]: c.get("fr_pages", []) for c in catalog}
    # also raw symbol_pages for names not in filtered catalog
    sp = ROOT / "07_analysis/fr_full_index/symbol_pages.json"
    all_fr = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}

    headers = json.loads(MAP_HEADERS.read_text(encoding="utf-8")) if MAP_HEADERS.exists() else {}
    z_set = {h["z_off"] for h in headers.get("maps_2d", [])}
    hdr_set = {h["header_off"] for h in headers.get("maps_2d", [])}
    curve_val = {c["values_off"] for c in headers.get("curves_1d", [])}
    curve_hdr = {c["header_off"] for c in headers.get("curves_1d", [])}

    xref = json.loads(XREF_HITS.read_text(encoding="utf-8")) if XREF_HITS.exists() else {}
    extp_addrs: set[int] = set()
    for k, hits in (xref.get("extp206_sample") or {}).items():
        try:
            extp_addrs.add(int(k, 16))
        except ValueError:
            pass
        for h in hits or []:
            fo = h.get("file_off")
            if fo:
                extp_addrs.add(int(fo, 16))
    for s in xref.get("by_symbol") or []:
        for h in s.get("extp206_hits") or []:
            fo = h.get("file_off")
            if fo:
                extp_addrs.add(int(fo, 16))
    # full EXTP#206 mem index from stock/bin (cheap structural)
    from paths import BIN_PATH, STOCK_PATH

    buf = STOCK_PATH.read_bytes() if STOCK_PATH.exists() else BIN_PATH.read_bytes()
    i = 0
    n = len(buf)
    while i < n - 8:
        if buf[i] == 0xD7 and (buf[i + 1] & 0xC0) == 0x40:
            page = buf[i + 2] | (buf[i + 3] << 8)
            count = ((buf[i + 1] >> 4) & 3) + 1
            if page == 0x206:
                j = i + 4
                end = min(n - 4, j + count * 12 + 24)
                while j < end:
                    op = buf[j]
                    if op in (0xF2, 0xF3, 0xF6, 0xF7, 0xC2, 0x42, 0x43) and j + 3 < n:
                        mem = buf[j + 2] | (buf[j + 3] << 8)
                        phys = 0x206 * 0x4000 + (mem & 0x3FFF)
                        fo = phys - 0x800000
                        if 0x10000 <= fo <= 0x1FFFF:
                            extp_addrs.add(fo)
                        j += 4
                    else:
                        j += 1
                i = end
                continue
        i += 1

    # owned addresses
    owned: dict[str, str] = {}  # addr -> name
    by_name: dict[str, dict] = {}
    for s in damos["symbols"]:
        by_name[s["name"]] = s
        if s.get("addr") and s.get("status") in {"PROVEN", "STRUCT"}:
            owned[hex(int(s["addr"], 16)).lower()] = s["name"]

    # anchors: PROVEN (preferred) + STRUCT with A2L name match
    anchors: list[tuple[str, int, int]] = []
    for s in damos["symbols"]:
        if not s.get("addr") or s.get("status") not in {"PROVEN", "STRUCT"}:
            continue
        n = s["name"]
        if n not in chars:
            continue
        a6901 = int(s["addr"], 16)
        a_e5 = chars[n]["file"]
        anchors.append((n, a_e5, a6901 - a_e5))
    # prefer PROVEN-only for primary; keep STRUCT too but tag
    print(f"anchors={len(anchors)} a2l_chars={len(chars)}")

    # candidates: FR ∩ A2L family OR already UNLINKED in damos
    want_names = set()
    for c in catalog:
        want_names.add(c["name"])
    for n in all_fr:
        if FAMILY_RE.match(n):
            want_names.add(n)
    for s in damos["symbols"]:
        if s.get("status") == "UNLINKED":
            want_names.add(s["name"])
    want_names = {n for n in want_names if n in chars and FAMILY_RE.match(n)}

    linked = []
    skipped = Counter()
    for name in sorted(want_names):
        ch = chars[name]
        existing = by_name.get(name)
        if existing and existing.get("status") == "PROVEN":
            skipped["keep_PROVEN"] += 1
            continue
        if existing and existing.get("kind") == "patch":
            skipped["keep_patch"] += 1
            continue
        if existing and existing.get("addr") and existing.get("status") == "STRUCT":
            # keep human/seed STRUCT; do not relocate over it
            skipped["already_linked"] += 1
            continue

        near = nearest_deltas(ch["file"], anchors, window=0x500)
        pred, meta = predict_addr(ch["file"], near)
        if pred is None:
            skipped[meta.get("reason", "no_pred")] += 1
            continue

        addr_key = hex(pred).lower()
        owner = owned.get(addr_key)
        if owner and owner != name:
            skipped["collision"] += 1
            continue

        # validation
        typ = ch["type"]
        has_extp = pred in extp_addrs
        shape_hit = False
        if typ == "MAP":
            shape_hit = hex(pred) in z_set or hex(pred) in hdr_set or hex(pred - 2) in hdr_set
        elif typ == "CURVE":
            shape_hit = hex(pred) in curve_val or hex(pred) in curve_hdr or hex(pred - 1) in curve_hdr

        strong_cluster = meta.get("agreeing", 0) >= 2 and meta.get("dist", 999) <= 0x100
        close_anchor = meta.get("dist", 999) <= 0x20 and not meta.get("conflicts")

        if shape_hit or (has_extp and typ == "VALUE") or strong_cluster or (
            close_anchor and typ == "VALUE"
        ):
            status = "STRUCT"
            judge = "link_STRUCT_e5a0_reloc"
        else:
            status = "HYP"
            judge = "link_HYP_e5a0_reloc"

        kind = {
            "VALUE": "scalar",
            "MAP": "map",
            "CURVE": "map",
            "VAL_BLK": "map",
        }.get(typ, "scalar")

        pages = fr_pages.get(name) or all_fr.get(name) or []
        entry = {
            "name": name,
            "title": f"[{status}] {name} — {ch.get('desc','')[:60]}",
            "addr": hex(pred),
            "kind": kind,
            "status": status,
            "equation": "X",
            "sizebits": 8 if kind == "scalar" else None,
            "rows": ch.get("rows") if kind == "map" else None,
            "cols": ch.get("cols") if kind == "map" else None,
            "fr_pages": list(pages)[:15],
            "fr_type": typ,
            "source": "link_fr_to_cal",
            "judge": judge,
            "evidence": {
                "note": "E5A0 local reloc; NOT 6901-native proof",
                "fr": {"pages": list(pages)[:10]},
                "a2l_e5a0": {
                    "file": hex(ch["file"]),
                    "type": typ,
                    "desc": ch.get("desc"),
                },
                "reloc": meta,
                "validation": {
                    "extp": bool(has_extp),
                    "shape_hit": bool(shape_hit),
                    "strong_cluster": bool(strong_cluster),
                    "close_anchor": bool(close_anchor),
                },
                "falsifier": {
                    "template": "collision_with_other_proven_or_delta_conflict",
                    "passed": True,
                },
            },
            "skip_llm": status == "HYP",  # don't spam LLM with pure transfer hyps
            "needs": "needs_consumer_decode" if status == "STRUCT" else "needs_damos_oem",
        }

        if existing:
            # upgrade UNLINKED / empty
            existing.update(entry)
            linked.append({"name": name, "addr": hex(pred), "status": status, "action": "update"})
        else:
            damos["symbols"].append(entry)
            linked.append({"name": name, "addr": hex(pred), "status": status, "action": "add"})
        owned[addr_key] = name
        by_name[name] = entry

    damos["status_counts"] = dict(Counter(s["status"] for s in damos["symbols"]))
    damos["link_stats"] = {
        "linked": len(linked),
        "by_status": dict(Counter(x["status"] for x in linked)),
        "skipped": dict(skipped),
        "anchors": len(anchors),
    }
    DAMOS_LITE.write_text(json.dumps(damos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "linked_count": len(linked),
        "linked_by_status": dict(Counter(x["status"] for x in linked)),
        "skipped": dict(skipped),
        "status_counts": damos["status_counts"],
        "symbols_total": len(damos["symbols"]),
        "sample_struct": [x for x in linked if x["status"] == "STRUCT"][:30],
        "sample_hyp": [x for x in linked if x["status"] == "HYP"][:20],
        "policy": "STRUCT/HYP from E5A0 reloc only; never PROVEN; no overwrite of proven addrs",
    }
    LINK_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False)[:3000])
    print(f"wrote {DAMOS_LITE} and {LINK_REPORT}")


if __name__ == "__main__":
    main()
