#!/usr/bin/env python3
"""Scan BIN for cal offset immediates and EXTP#206 memory forms.

Does not claim semantics — only structural hits for later judging.
"""
from __future__ import annotations

import json
import struct
from collections import defaultdict

from paths import BIN_PATH, DAMOS_LITE, FR_CATALOG, OUT_DIR, XREF_HITS


def find_le16(buf: bytes, value: int) -> list[int]:
    needle = struct.pack("<H", value & 0xFFFF)
    out = []
    start = 0
    while True:
        i = buf.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
        if len(out) >= 50:
            break
    return out


def scan_extp206_mem(buf: bytes) -> dict[int, list[dict]]:
    """Find EXTP #0x206,#n followed within window by mem16 access; map mem -> sites."""
    hits: dict[int, list[dict]] = defaultdict(list)
    # D7 40 xx xx with page 0x0206 LE => 06 02
    i = 0
    n = len(buf)
    while i < n - 8:
        if buf[i] == 0xD7 and (buf[i + 1] & 0xC0) == 0x40:
            page = buf[i + 2] | (buf[i + 3] << 8)
            count = ((buf[i + 1] >> 4) & 3) + 1
            if page == 0x206:
                # scan following up to count*8+16 bytes for 4-byte mem ops
                j = i + 4
                end = min(n - 4, j + count * 12 + 24)
                while j < end:
                    op = buf[j]
                    # common mem16 forms used by review_decode
                    if op in (0xF2, 0xF3, 0xF6, 0xF7, 0xC2, 0x42, 0x43) and j + 3 < n:
                        mem = buf[j + 2] | (buf[j + 3] << 8)
                        phys = 0x206 * 0x4000 + (mem & 0x3FFF)
                        file_off = phys - 0x800000
                        hits[file_off].append(
                            {
                                "extp_file": i,
                                "extp_ea": hex(0x800000 + i),
                                "mem": hex(mem),
                                "phys": hex(phys),
                                "file_off": hex(file_off),
                                "op": hex(op),
                                "raw": buf[i : j + 4].hex(),
                            }
                        )
                        j += 4
                    else:
                        j += 1
                i = end
                continue
        i += 1
    return hits


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    buf = BIN_PATH.read_bytes()
    assert len(buf) == 0x80000

    # offsets of interest: from damos_lite addrs in cal + common FR-linked seeds
    offsets: set[int] = set()
    if DAMOS_LITE.exists():
        damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
        for s in damos.get("symbols", []):
            a = s.get("addr")
            if a:
                offsets.add(int(a, 16))

    # also low 16-bit of cal addresses (0x1xxxx -> 0xxxx for DPP/EXTP forms)
    cal_imm: set[int] = set()
    for off in list(offsets):
        if 0x10000 <= off <= 0x1FFFF:
            cal_imm.add(off & 0xFFFF)
            cal_imm.add(off - 0x10000)  # relative within 64k cal image sometimes

    imm_hits = {}
    for imm in sorted(cal_imm):
        sites = find_le16(buf, imm)
        # filter to code-ish region
        code_sites = [hex(0x800000 + s) for s in sites if 0x20000 <= s < 0x7F000]
        if code_sites:
            imm_hits[hex(imm)] = code_sites[:20]

    extp = scan_extp206_mem(buf)
    # keep only cal file offsets that match known symbols or look like cal
    extp_cal = {
        hex(k): v[:10]
        for k, v in extp.items()
        if 0x10000 <= k <= 0x1FFFF and (k in offsets or len(v) >= 1)
    }

    # Index: for each known symbol addr, attach extp hits
    by_symbol = []
    if DAMOS_LITE.exists():
        damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
        for s in damos.get("symbols", []):
            a = s.get("addr")
            if not a:
                continue
            off = int(a, 16)
            rec = {
                "name": s.get("name"),
                "addr": a,
                "extp206_hits": extp.get(off, [])[:8],
                "imm16_code_hits": imm_hits.get(hex(off & 0xFFFF), [])[:8],
            }
            by_symbol.append(rec)

    doc = {
        "bin": str(BIN_PATH.name),
        "extp206_cal_addrs": len(extp_cal),
        "imm_hit_keys": len(imm_hits),
        "by_symbol": by_symbol,
        "extp206_sample": dict(list(extp_cal.items())[:40]),
    }
    XREF_HITS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"xref symbols={len(by_symbol)} extp_cal={len(extp_cal)} -> {XREF_HITS}")


if __name__ == "__main__":
    main()
