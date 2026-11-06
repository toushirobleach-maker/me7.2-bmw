#!/usr/bin/env python3
"""Build FR symbol catalog + candidates.jsonl for families of interest."""
from __future__ import annotations

import json
import re
from pathlib import Path

from paths import CANDIDATES, FR_CATALOG, FR_DIR, OUT_DIR

# Families we care about for ME7 cal/config
FAMILY_RE = re.compile(
    r"^(?:CW|CD|KF|CLA|MSL|DZW|KR|ESK|LR|TE|SL|TM|TA|FF|FK|NW|ET|ML|ZW)"
    r"[A-Z0-9_]{1,20}$"
)
TYPE_HINT = re.compile(
    r"\b([A-Z][A-Z0-9_]{2,})\s+(FW|KF|KL|UM|CW|BIT)\b"
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sym_pages = json.loads((FR_DIR / "symbol_pages.json").read_text(encoding="utf-8"))
    full = (FR_DIR / "full_text.txt").read_text(encoding="utf-8", errors="ignore")

    # type hints from parameter tables
    types: dict[str, str] = {}
    for m in TYPE_HINT.finditer(full):
        name, typ = m.group(1), m.group(2)
        if FAMILY_RE.match(name):
            types.setdefault(name, typ)

    catalog = []
    for name, pages in sorted(sym_pages.items()):
        if not FAMILY_RE.match(name):
            continue
        if len(pages) > 200:
            continue
        catalog.append(
            {
                "name": name,
                "fr_pages": pages[:30],
                "page_count": len(pages),
                "fr_type": types.get(name),
                "family": name[:2] if len(name) >= 2 else name,
            }
        )

    FR_CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # candidates: unlinked FR symbols (no addr yet — judge merges later)
    with CANDIDATES.open("w", encoding="utf-8") as f:
        for c in catalog:
            rec = {
                "name": c["name"],
                "addr": None,
                "status": "UNLINKED",
                "fr_pages": c["fr_pages"],
                "fr_type": c["fr_type"],
                "source": "fr_symbol_catalog",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"catalog={len(catalog)} -> {FR_CATALOG}")
    print(f"candidates={len(catalog)} -> {CANDIDATES}")


if __name__ == "__main__":
    main()
