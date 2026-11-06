#!/usr/bin/env python3
"""Seed damos_lite.json from XDF_MANIFEST.json + PROMOTION_* reports."""
from __future__ import annotations

import json
import re
import datetime
from pathlib import Path

from paths import DAMOS_LITE, MANIFEST, OUT_DIR, PROVEN_DIR, FR_DIR


TAG_RE = re.compile(r"^\[(PROVEN|STRUCT|HYP|HYPOTHESIS)\]\s*")
NAME_RE = re.compile(
    r"\b(CWKONLS|CWKONABG|CWDKAT|CDAGR|CWDAGR|ESKONF|MSLBAS|MSLUB|"
    r"CLALSH2?|CLALASH2?|CLAHSH2?|CLASLPE|CLASLVE|CLAHSV2?|CLATEVE|DTEVE|"
    r"TARAU|TASHS|TMSHS|TLRHS|TMRA[12K]?|CLRZWTMS|DTMR|DTMTMRW|"
    r"KFZWOP2?|KFZW[12]|KFETRD|KFETRT|TAMLTKA|CRC32|SAP)\b"
)


def strip_tag(title: str) -> str:
    return TAG_RE.sub("", title).strip()


def guess_name(title: str) -> str:
    body = strip_tag(title)
    m = NAME_RE.search(body)
    if m:
        return m.group(1)
    # first token-ish
    body = re.sub(r"@.*", "", body)
    body = re.sub(r"—.*", "", body)
    body = re.sub(r"\(.*", "", body)
    return body.strip()[:64] or "unnamed"


def load_promotion_addrs() -> dict[str, dict]:
    """addr(lower hex) -> {consumer_ea, fr_hint, report}"""
    out: dict[str, dict] = {}
    for p in PROVEN_DIR.glob("PROMOTION_*_REPORT.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("items") or []
        if not items and isinstance(data.get("claim_tested"), dict):
            items = [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            addr = it.get("addr") or (it.get("consumer") or {}).get("phys")
            if not addr:
                continue
            key = hex(int(str(addr), 16)).lower()
            cons = it.get("consumer") or {}
            out[key] = {
                "consumer_ea": cons.get("ea"),
                "consumer_raw": cons.get("raw_hex"),
                "consumer_decoded": cons.get("decoded"),
                "phys": cons.get("phys") or addr,
                "verdict": it.get("verdict"),
                "report": p.name,
                "semantic": it.get("semantic"),
            }
    return out


def fr_pages_for(name: str) -> list[int]:
    sym = FR_DIR / "symbol_pages.json"
    if not sym.exists():
        return []
    data = json.loads(sym.read_text(encoding="utf-8"))
    pages = data.get(name) or data.get(name.upper()) or []
    return list(pages)[:20]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    promo = load_promotion_addrs()
    symbols = []
    for it in man["items"]:
        title = it.get("title", "")
        kind_map = {"constant": "scalar", "table": "map", "patch": "patch"}
        kind = kind_map.get(it.get("kind", ""), it.get("kind", "scalar"))
        addr = it.get("addr")
        name = guess_name(title)
        status = it.get("status", "STRUCT")
        if status == "HYPOTHESIS":
            status = "HYP"
        entry = {
            "name": name,
            "title": title,
            "addr": addr,
            "kind": kind,
            "status": status,
            "equation": it.get("equation", "X"),
            "sizebits": it.get("sizebits"),
            "rows": it.get("rows"),
            "cols": it.get("cols"),
            "x": it.get("x"),
            "y": it.get("y"),
            "le": it.get("le", False),
            "signed": it.get("signed", False),
            "stock_hex": it.get("stock_hex"),
            "fr_pages": fr_pages_for(name),
            "evidence": {
                "note": it.get("evidence"),
                "promotion_ref": it.get("promotion_ref") or it.get("last_attempt"),
                "blocked_reason": it.get("blocked_reason"),
            },
            "source": "XDF_MANIFEST",
        }
        if addr:
            key = hex(int(addr, 16)).lower()
            # also try cpu phys form
            phys_key = hex(0x800000 + int(addr, 16)).lower()
            hit = promo.get(key) or promo.get(phys_key)
            # match by file offset derived from phys 0x81xxxx
            if not hit:
                for pk, pv in promo.items():
                    try:
                        paddr = int(pk, 16)
                    except ValueError:
                        continue
                    if 0x810000 <= paddr <= 0x81FFFF and (paddr - 0x800000) == int(addr, 16):
                        hit = pv
                        break
            if hit:
                entry["consumer_ea"] = hit.get("consumer_ea")
                entry["evidence"]["consumer"] = {
                    "ea": hit.get("consumer_ea"),
                    "raw_hex": hit.get("consumer_raw"),
                    "decoded": hit.get("consumer_decoded"),
                    "phys": hit.get("phys"),
                }
                entry["evidence"]["promo_verdict"] = hit.get("verdict")
                entry["evidence"]["promo_report"] = hit.get("report")
        if kind == "patch":
            entry["entries"] = it.get("entries", [])
            entry["addr"] = entry.get("addr")  # patches may lack single addr
        # tag hard blockers so LLM skips
        br = entry["evidence"].get("blocked_reason")
        if br in {"no_address_consumer_6901", "ews_name_unproven", "units_unproven", "timebase_unproven"}:
            entry["skip_llm"] = True
            entry["needs"] = {
                "no_address_consumer_6901": "needs_damos_oem",
                "ews_name_unproven": "needs_live",
                "units_unproven": "needs_live",
                "timebase_unproven": "needs_live",
            }.get(br, "needs_human")
        symbols.append(entry)

    doc = {
        "epk": man.get("epk", "6901I41D"),
        "hw_zb": man.get("hw_zb", "7532675"),
        "created_utc": datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ"),
        "policy": man.get("policy"),
        "bin_region": man.get("bin_region"),
        "status_counts": {},
        "symbols": symbols,
    }
    from collections import Counter

    doc["status_counts"] = dict(Counter(s["status"] for s in symbols))
    DAMOS_LITE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DAMOS_LITE} symbols={len(symbols)} counts={doc['status_counts']}")


if __name__ == "__main__":
    main()
