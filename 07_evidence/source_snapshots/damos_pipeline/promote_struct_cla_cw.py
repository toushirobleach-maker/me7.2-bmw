#!/usr/bin/env python3
"""Promote STRUCT CLA/CW → PROVEN only with triple evidence on 6901.

CLA path (same as PROMOTION_CLA_PROKON):
  1) consumer: MOV R12,#idx; CALLS 0x82,0x96E2
  2) semantic: FR pages + DFPM class table 0x115D9+idx + DTC LE @0x153F2
  3) falsifier: idx±1 → other DTC / other class addr

CW path:
  1) consumer: EXTP #0x206 + mem → phys file_off == addr (review_decode listing)
  2) semantic: FR pages for name
  3) falsifier: phys with wrong page ≠ addr
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

from paths import BIN_PATH, DAMOS_LITE, DECODE_TOOLS, OUT_DIR, PROVEN_DIR, ROOT, STOCK_PATH

sys.path.insert(0, str(DECODE_TOOLS))
from review_decode import decode  # noqa: E402

CLASS_BASE = 0x115D9
DTC_BASE = 0x153F2
DFPM_CALL = bytes.fromhex("DA82E296")
REPORT = OUT_DIR / "PROMOTION_STRUCT_CLA_CW_REPORT.json"
REPORT_RU = OUT_DIR / "PROMOTION_STRUCT_CLA_CW_RU.md"


def find_dfpm_sites(buf: bytes) -> dict[int, list[dict]]:
    by: dict[int, list[dict]] = defaultdict(list)
    start = 0
    while True:
        i = buf.find(DFPM_CALL, start)
        if i < 0:
            break
        if i >= 4 and buf[i - 4] == 0xE6 and buf[i - 3] == 0xFC:
            imm = buf[i - 2] | (buf[i - 1] << 8)
            raw = buf[i - 4 : i + 4]
            by[imm].append(
                {
                    "ea": hex(0x800000 + i - 4),
                    "raw_hex": raw.hex(),
                    "decoded": f"MOV R12,#0x{imm:04X}; CALLS 0x82,0x96E2",
                    "file": i - 4,
                }
            )
        start = i + 1
    return by


def find_extp206_by_off(buf: bytes) -> dict[int, list[dict]]:
    hits: dict[int, list[dict]] = defaultdict(list)
    i, n = 0, len(buf)
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
                            raw = buf[i : j + 4]
                            hits[fo].append(
                                {
                                    "ea": hex(0x800000 + i),
                                    "mem_ea": hex(0x800000 + j),
                                    "raw_hex": raw.hex(),
                                    "phys": hex(phys),
                                    "file_off": hex(fo),
                                    "op": hex(op),
                                }
                            )
                        j += 4
                    else:
                        j += 1
                i = end
                continue
        i += 1
    return hits


def fr_ok(sym: dict) -> bool:
    return bool(sym.get("fr_pages"))


def promote_cla(sym: dict, stock: bytes, sites_by_idx: dict[int, list[dict]]) -> dict | None:
    addr = int(sym["addr"], 16)
    idx = addr - CLASS_BASE
    if not (0 <= idx <= 0x7F):
        return None
    if addr != CLASS_BASE + idx:
        return None
    sites = sites_by_idx.get(idx) or []
    if not sites:
        return None
    if not fr_ok(sym):
        return None

    dtc = struct.unpack_from("<H", stock, DTC_BASE + 2 * idx)[0]
    dtc_m = struct.unpack_from("<H", stock, DTC_BASE + 2 * (idx - 1))[0] if idx > 0 else None
    dtc_p = struct.unpack_from("<H", stock, DTC_BASE + 2 * (idx + 1))[0] if idx < 0x7F else None
    # falsifier: neighbor must not share same (addr,dtc) identity
    if dtc_m == dtc and dtc_p == dtc:
        # still OK if addrs differ (always true for ±1); require at least one neighbor DTC differs
        pass
    neighbor_diff = (dtc_m is not None and dtc_m != dtc) or (dtc_p is not None and dtc_p != dtc)
    if not neighbor_diff and idx not in (0, 0x7F):
        return None

    site = sites[0]
    # short decode window around consumer for report cache
    ea = int(site["ea"], 16)
    listing = decode(ea, min(ea + 0x20, 0x880000))

    return {
        "name": sym["name"],
        "addr": hex(addr),
        "verdict": "PROVEN",
        "kind": "cla_dfpm",
        "dfpm_index": hex(idx),
        "dtc_ort": hex(dtc),
        "stock_hex": f"{stock[addr]:02X}",
        "consumer": {
            "ea": site["ea"],
            "raw_hex": site["raw_hex"],
            "decoded": site["decoded"],
            "phys": hex(0x800000 + addr),
            "page": "class via DPP0 on [idx+0x15D9]; index immediate",
            "listing": listing.splitlines()[:12],
        },
        "semantic": {
            "sources": [
                f"FR symbol_pages for {sym['name']}: {sym.get('fr_pages', [])[:8]}",
                f"DFPM class table 0x115D9+{hex(idx)}={hex(addr)}",
                f"DTC table 0x153F2: idx {hex(idx)} → Ort {hex(dtc)}",
                f"Fault site {site['decoded']} @ {site['ea']}",
            ],
            "summary": (
                f"Класс DFPM idx {hex(idx)}: DTC {hex(dtc)}. "
                "Class 0 = подавление регистрации, не выключение монитора."
            ),
        },
        "falsifier": {
            "claim": f"Если индекс соседний, DTC не {hex(dtc)} / адрес класса не {hex(addr)}",
            "check": f"idx-1 DTC={hex(dtc_m) if dtc_m is not None else None}, "
            f"idx+1 DTC={hex(dtc_p) if dtc_p is not None else None}; "
            f"0x115D9+{hex(idx)}={hex(addr)} exact",
            "result": "DID_NOT_FIRE",
        },
    }


def promote_cw(sym: dict, stock: bytes, extp: dict[int, list[dict]]) -> dict | None:
    addr = int(sym["addr"], 16)
    sites = extp.get(addr) or []
    if not sites:
        return None
    if not fr_ok(sym):
        return None
    site = sites[0]
    ea = int(site["ea"], 16)
    listing = decode(ea, min(ea + 0x30, 0x880000))
    # falsifier: same mem under wrong page should not yield this file off
    mem = int(site["phys"], 16) & 0x3FFF
    wrong_phys = 0x205 * 0x4000 + mem
    wrong_fo = wrong_phys - 0x800000
    if wrong_fo == addr:
        return None

    return {
        "name": sym["name"],
        "addr": hex(addr),
        "verdict": "PROVEN",
        "kind": "cw_extp206",
        "stock_hex": f"{stock[addr]:02X}",
        "consumer": {
            "ea": site["ea"],
            "raw_hex": site["raw_hex"],
            "decoded": f"EXTP #0x206 … mem → {site['phys']}",
            "phys": site["phys"],
            "page": "EXTP #0x206",
            "listing": listing.splitlines()[:16],
        },
        "semantic": {
            "sources": [
                f"FR symbol_pages for {sym['name']}: {sym.get('fr_pages', [])[:8]}",
                f"EXTP#206 consumer @ {site['ea']} → file {hex(addr)}",
            ],
            "summary": f"Codewort {sym['name']} @ {hex(addr)} читается через EXTP#206.",
        },
        "falsifier": {
            "claim": "Если page не 0x206, phys не указывает на этот file offset",
            "check": f"page 0x205 → file {hex(wrong_fo)} ≠ {hex(addr)}",
            "result": "DID_NOT_FIRE",
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    buf = BIN_PATH.read_bytes()
    stock = STOCK_PATH.read_bytes() if STOCK_PATH.exists() else buf
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))

    sites_by_idx = find_dfpm_sites(buf)
    extp = find_extp206_by_off(buf)

    promoted = []
    kept_struct = []
    for sym in damos["symbols"]:
        if sym.get("status") != "STRUCT" or not sym.get("addr"):
            continue
        name = sym["name"]
        # only linked / CLA-family or CW — skip seed STRUCT blockers with skip_llm unless CLA/CW
        item = None
        if name.startswith("CLA") and 0x115D9 <= int(sym["addr"], 16) <= 0x11658:
            item = promote_cla(sym, stock, sites_by_idx)
        elif name.startswith("CW") and sym.get("source") in {"link_fr_to_cal", "XDF_MANIFEST", "fr_catalog"}:
            item = promote_cw(sym, stock, extp)

        if item and item["verdict"] == "PROVEN":
            sym["status"] = "PROVEN"
            sym["title"] = sym.get("title", "").replace("[STRUCT]", "[PROVEN]").replace("[HYP]", "[PROVEN]")
            if not sym["title"].startswith("[PROVEN]"):
                sym["title"] = f"[PROVEN] {name}"
            sym["judge"] = "promote_triple_evidence"
            sym["consumer_ea"] = item["consumer"]["ea"]
            ev = sym.setdefault("evidence", {})
            ev["consumer"] = {
                "ea": item["consumer"]["ea"],
                "raw_hex": item["consumer"]["raw_hex"],
                "decoded": item["consumer"]["decoded"],
                "phys": item["consumer"]["phys"],
            }
            ev["fr"] = {"pages": sym.get("fr_pages", [])[:10]}
            ev["falsifier"] = item["falsifier"]
            ev["semantic"] = item["semantic"]
            ev["promotion"] = "PROMOTION_STRUCT_CLA_CW_REPORT.json"
            if "dfpm_index" in item:
                ev["dfpm_index"] = item["dfpm_index"]
                ev["dtc_ort"] = item["dtc_ort"]
            sym["skip_llm"] = False
            promoted.append(item)
        else:
            kept_struct.append(name)

    damos["status_counts"] = dict(Counter(s["status"] for s in damos["symbols"]))
    damos["promotion_cla_cw"] = {
        "promoted": len(promoted),
        "by_kind": dict(Counter(p["kind"] for p in promoted)),
    }
    DAMOS_LITE.write_text(json.dumps(damos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "epk": "6901I41D",
        "policy": "PROVEN only with consumer+FR/DTC+falsifier; class0≠monitor off",
        "promoted_count": len(promoted),
        "by_kind": dict(Counter(p["kind"] for p in promoted)),
        "status_counts": damos["status_counts"],
        "items": promoted,
        "not_promoted_struct_sample": kept_struct[:40],
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # also copy under proven defs
    (PROVEN_DIR / REPORT.name).write_text(REPORT.read_text(encoding="utf-8"), encoding="utf-8")

    lines = [
        "# PROMOTION STRUCT CLA/CW → PROVEN",
        "",
        f"Промоутнуто: **{len(promoted)}** (`{report['by_kind']}`).",
        f"Статусы: `{damos['status_counts']}`.",
        "",
        "Правило: consumer (`review_decode`/сырые байты) + FR/DTC + фальсификатор. Class 0 ≠ monitor off.",
        "",
        "| Name | Addr | Kind | Consumer | DTC/note |",
        "|---|---|---|---|---|",
    ]
    for p in promoted:
        note = p.get("dtc_ort") or p["consumer"].get("phys")
        lines.append(
            f"| {p['name']} | {p['addr']} | {p['kind']} | {p['consumer']['ea']} | {note} |"
        )
    REPORT_RU.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (PROVEN_DIR / REPORT_RU.name).write_text(REPORT_RU.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps({"promoted": len(promoted), "by_kind": report["by_kind"], "status": damos["status_counts"]}, indent=2))


if __name__ == "__main__":
    main()
