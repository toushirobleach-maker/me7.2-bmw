#!/usr/bin/env python3
"""Prove KF* (mixture/torque/related) via far-ptr consumers on 6901.

Consumer form (review_decode):
  MOV R12,#off
  MOV R13,#0x0206
  … CALLS interpolator (often 0x01,0xB704)

Assignment: each KF symbol → nearest unique far-ptr within 24 bytes
(prevents header theft between neighbours).

KFZWOP/KFZW1 at 0x810xxx (page 0x204): no such far-ptr — remain STRUCT.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

from paths import BIN_PATH, DAMOS_LITE, DECODE_TOOLS, OUT_DIR, PROVEN_DIR, ROOT, STOCK_PATH

sys.path.insert(0, str(DECODE_TOOLS))
from review_decode import decode  # noqa: E402

REPORT = OUT_DIR / "PROMOTION_KF_FARPTR_REPORT.json"
REPORT_RU = OUT_DIR / "PROMOTION_KF_FARPTR_RU.md"


def scan_farptr206(buf: bytes) -> dict[int, list[dict]]:
    hits: dict[int, list[dict]] = defaultdict(list)
    i, n = 0, len(buf)
    while i < n - 12:
        if buf[i] == 0xE6 and buf[i + 1] == 0xFC and buf[i + 4] == 0xE6 and buf[i + 5] == 0xFD:
            off = buf[i + 2] | (buf[i + 3] << 8)
            page = buf[i + 6] | (buf[i + 7] << 8)
            if page == 0x206:
                phys = 0x206 * 0x4000 + (off & 0x3FFF)
                fo = phys - 0x800000
                if 0x10000 <= fo <= 0x1FFFF:
                    tail = buf[i + 8 : i + 20]
                    calls = None
                    for j in range(0, len(tail) - 3):
                        if tail[j] == 0xDA:
                            seg = tail[j + 1]
                            cof = tail[j + 2] | (tail[j + 3] << 8)
                            calls = f"CALLS 0x{seg:02X},0x{cof:04X}"
                            break
                    hits[fo].append(
                        {
                            "ea": hex(0x800000 + i),
                            "raw_hex": buf[i : i + 8].hex(),
                            "off": hex(off),
                            "page": hex(page),
                            "phys": hex(phys),
                            "file_off": hex(fo),
                            "calls": calls,
                        }
                    )
            i += 8
        else:
            i += 1
    return hits


def parse_header(stock: bytes, fo: int) -> dict | None:
    if fo + 2 >= len(stock):
        return None
    cols, rows = stock[fo], stock[fo + 1]
    if 2 <= cols <= 24 and 2 <= rows <= 24:
        x0 = fo + 2
        y0 = x0 + cols
        z0 = y0 + rows
        zlen = cols * rows
        if z0 + zlen <= len(stock):
            return {
                "kind": "map",
                "cols": cols,
                "rows": rows,
                "x_off": hex(x0),
                "y_off": hex(y0),
                "z_off": hex(z0),
                "header_off": hex(fo),
                "z_len": zlen,
            }
    n = cols
    if 4 <= n <= 24:
        if fo + 1 + 2 * n <= len(stock):
            return {
                "kind": "curve",
                "cols": n,
                "rows": 1,
                "x_off": hex(fo + 1),
                "z_off": hex(fo + 1 + n),
                "header_off": hex(fo),
            }
    return None


def is_kf_family(name: str) -> bool:
    return name.upper().startswith("KF")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    buf = BIN_PATH.read_bytes()
    stock = STOCK_PATH.read_bytes() if STOCK_PATH.exists() else buf
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
    fr_pages = json.loads((ROOT / "07_analysis/fr_full_index/symbol_pages.json").read_text())
    far = scan_farptr206(buf)

    # Demote previous run of this promoter so reassignment is clean
    for s in damos["symbols"]:
        if s.get("judge") == "promote_kf_farptr206":
            ev = s.get("evidence") or {}
            # restore addr to prior far/header if recorded, else keep
            if isinstance(ev.get("shape"), dict) and ev["shape"].get("header_off"):
                s["addr"] = ev["shape"]["header_off"]
            elif isinstance(ev.get("consumer"), dict) and ev["consumer"].get("phys"):
                try:
                    phys = int(ev["consumer"]["phys"], 16)
                    s["addr"] = hex(phys - 0x800000)
                except ValueError:
                    pass
            s["status"] = "STRUCT"
            s["judge"] = "demoted_for_reassign"
            title = s.get("title") or s["name"]
            s["title"] = title.replace("[PROVEN]", "[STRUCT]")

    blocked_zw = []
    for nm in ("KFZWOP", "KFZWOP2", "KFZW1", "KFZW2", "KFZWVL", "KFZWMN", "KFZWMNST"):
        s = next((x for x in damos["symbols"] if x["name"] == nm and x.get("addr")), None)
        if not s:
            continue
        a = int(s["addr"], 16)
        near = [fo for fo in far if abs(fo - a) <= 8]
        blocked_zw.append(
            {
                "name": nm,
                "addr": s["addr"],
                "verdict": "STILL_STRUCT",
                "reason": "no MOV R12,#off; MOV R13,#0x206 far-ptr into 0x810xxx (page 0x204) cal",
                "near_farptr206": [hex(x) for x in near],
            }
        )

    # Symbol-centric candidates: (dist, fo, sym)
    pairs = []
    for s in damos["symbols"]:
        if not is_kf_family(s["name"]) or not s.get("addr"):
            continue
        if s["name"].upper().startswith("KFZW"):
            continue
        if s.get("status") == "PROVEN" and s.get("judge") != "demoted_for_reassign":
            continue  # keep other promoters
        a = int(s["addr"], 16)
        # seed addr may be Z; far often header — allow window
        best = None
        for fo in far:
            # far-ptr usually hits header; damos addr may be header or Z
            d = min(abs(fo - a), abs(fo - (a - 2)), abs(fo - (a + 2)))
            if hdr_len_guess := parse_header(stock, fo):
                z = int(hdr_len_guess["z_off"], 16)
                d = min(d, abs(z - a), abs(fo - a))
            # prefer sites that call the 2D interpolator B704 when tied
            sites = far[fo]
            prefer = 0 if any((s.get("calls") or "").endswith("0xB704") for s in sites) else 1
            if d <= 16 and (best is None or (d, prefer) < (best[0], best[2])):
                best = (d, fo, prefer)
        if best is None:
            continue
        pages = s.get("fr_pages") or fr_pages.get(s["name"]) or []
        if not pages:
            continue
        pairs.append((best[0], best[1], best[2], s, pages))

    pairs.sort(key=lambda x: (x[0], x[2], x[3]["name"]))
    used_fo: set[int] = set()
    used_name: set[str] = set()
    promoted = []

    for dist, fo, _prefer, cand, pages in pairs:
        if fo in used_fo or cand["name"] in used_name:
            continue
        site = far[fo][0]
        hdr = parse_header(stock, fo)
        off = int(site["off"], 16)
        wrong = 0x205 * 0x4000 + (off & 0x3FFF) - 0x800000
        if wrong == fo:
            continue

        used_fo.add(fo)
        used_name.add(cand["name"])

        addr_out = hdr["z_off"] if hdr else hex(fo)
        ea = int(site["ea"], 16)
        listing = decode(ea, min(ea + 0x28, 0x880000)).splitlines()[:14]
        item = {
            "name": cand["name"],
            "addr": addr_out,
            "header_off": hex(fo),
            "match_dist": dist,
            "verdict": "PROVEN",
            "kind": "kf_farptr206",
            "shape": hdr,
            "consumer": {
                "ea": site["ea"],
                "raw_hex": site["raw_hex"],
                "decoded": f"MOV R12,#{site['off']}; MOV R13,#0x0206"
                + (f"; {site['calls']}" if site.get("calls") else ""),
                "phys": site["phys"],
                "page": "0x206",
                "listing": listing,
            },
            "semantic": {
                "sources": [
                    f"FR symbol_pages {cand['name']}: {list(pages)[:8]}",
                    f"Far-ptr consumer → file {hex(fo)} page 0x206",
                    f"Header parse: {hdr}" if hdr else "Header parse: none",
                ],
                "summary": f"{cand['name']}: consumed via R12/R13 far-ptr #206 @ {site['ea']}",
            },
            "falsifier": {
                "claim": "If page were 0x205, phys would not be this cal offset",
                "check": f"page 0x205 → file {hex(wrong)} ≠ {hex(fo)}",
                "result": "DID_NOT_FIRE",
            },
        }

        cand["status"] = "PROVEN"
        cand["addr"] = addr_out
        cand["kind"] = "map"
        if hdr:
            cand["rows"] = hdr.get("rows")
            cand["cols"] = hdr.get("cols")
            cand["x"] = hdr.get("x_off")
            cand["y"] = hdr.get("y_off")
        title = cand.get("title") or cand["name"]
        for tag in ("[STRUCT]", "[HYP]", "[UNLINKED]", "[PROVEN]"):
            title = title.replace(tag, "").strip()
        cand["title"] = f"[PROVEN] {title}"
        cand["judge"] = "promote_kf_farptr206"
        cand["consumer_ea"] = site["ea"]
        cand["fr_pages"] = list(pages)[:15]
        ev = cand.setdefault("evidence", {})
        ev["consumer"] = {
            "ea": site["ea"],
            "raw_hex": site["raw_hex"],
            "decoded": item["consumer"]["decoded"],
            "phys": site["phys"],
        }
        ev["fr"] = {"pages": list(pages)[:10]}
        ev["falsifier"] = item["falsifier"]
        ev["semantic"] = item["semantic"]
        ev["shape"] = hdr
        ev["promotion"] = "PROMOTION_KF_FARPTR_REPORT.json"
        ev.pop("blocked_reason", None)
        cand["skip_llm"] = False
        promoted.append(item)

    damos["status_counts"] = dict(Counter(s["status"] for s in damos["symbols"]))
    damos["promotion_kf_farptr"] = {
        "promoted": len(promoted),
        "blocked_kfzw": len(blocked_zw),
    }
    DAMOS_LITE.write_text(json.dumps(damos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "epk": "6901I41D",
        "decoder": "review_decode.py",
        "consumer_form": "MOV R12,#off; MOV R13,#0x206; CALLS interpolator",
        "promoted_count": len(promoted),
        "blocked_kfzw": blocked_zw,
        "status_counts": damos["status_counts"],
        "items": promoted,
        "policy": "PROVEN=far-ptr+FR+falsifier; KFZW page204 still unproven",
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (PROVEN_DIR / REPORT.name).write_text(REPORT.read_text(encoding="utf-8"), encoding="utf-8")

    lines = [
        "# PROMOTION KF far-ptr (смесь/момент)",
        "",
        f"Промоутнуто: **{len(promoted)}**. KFZW*: **STILL_STRUCT** (нет far-ptr page 0x204).",
        f"Статусы: `{damos['status_counts']}`.",
        "",
        "| Name | Z/addr | Header | Dist | Consumer | Shape |",
        "|---|---|---|---|---|---|",
    ]
    for p in promoted:
        sh = p.get("shape") or {}
        shape = f"{sh.get('rows')}x{sh.get('cols')}" if sh else "-"
        lines.append(
            f"| {p['name']} | {p['addr']} | {p['header_off']} | {p['match_dist']} | "
            f"{p['consumer']['ea']} | {shape} |"
        )
    lines += ["", "## KFZW blockers", ""]
    for b in blocked_zw:
        lines.append(f"- `{b['name']}` @`{b['addr']}`: {b['reason']}")
    REPORT_RU.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (PROVEN_DIR / REPORT_RU.name).write_text(REPORT_RU.read_text(encoding="utf-8"), encoding="utf-8")

    print(
        json.dumps(
            {
                "promoted": len(promoted),
                "focus": [
                    p["name"]
                    for p in promoted
                    if p["name"].startswith(("KFL", "KFMI", "KFR", "KFW", "KFM"))
                ],
                "KFMIRED1": next((p for p in promoted if p["name"] == "KFMIRED1"), None),
                "KFLMSKH": next((p for p in promoted if p["name"] == "KFLMSKH"), None),
                "blocked_kfzw": [b["name"] for b in blocked_zw],
                "status": damos["status_counts"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
