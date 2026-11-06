#!/usr/bin/env python3
"""Export compact LLM review packs from review_queue.jsonl (max ~4KB each)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from paths import FR_DIR, PACK_DIR, REVIEW_QUEUE, XREF_HITS


MICRO_PROMPT = """You are reviewing ONE ME7.2 6901I41D calibration candidate.
Return ONLY JSON: {"name":"...","verdict":"PROVEN|STRUCT|HYP|UNLINKED","addr":"0x..."|null,"equation":"X","notes":"..."}.
Rules: need consumer+FR+falsifier for PROVEN. Do not invent addresses. No XDF edits.
"""


def snippet_fr(name: str, pages: list[int], max_chars: int = 400) -> list[dict]:
    pages_path = FR_DIR / "pages.jsonl"
    if not pages_path.exists() or not pages:
        return []
    want = set(pages[:3])
    out = []
    for line in pages_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        p = json.loads(line)
        if p["pdf_page"] not in want:
            continue
        text = p["text"]
        idx = text.upper().find(name.upper())
        if idx < 0:
            frag = text[:max_chars]
        else:
            frag = text[max(0, idx - 80) : idx + max_chars - 80]
        out.append({"pdf_page": p["pdf_page"], "snippet": frag.replace("\n", " ")[:max_chars]})
        if len(out) >= 2:
            break
    return out


def main() -> None:
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    if not REVIEW_QUEUE.exists():
        print("no review queue")
        return
    rows = [json.loads(l) for l in REVIEW_QUEUE.read_text(encoding="utf-8").splitlines() if l]
    xref = json.loads(XREF_HITS.read_text(encoding="utf-8")) if XREF_HITS.exists() else {}
    xref_by_name = {s["name"]: s for s in xref.get("by_symbol", [])}

    packs = []
    for i, row in enumerate(rows[:n]):
        name = row.get("name")
        xh = xref_by_name.get(name, {})
        pack = {
            "micro_prompt": MICRO_PROMPT,
            "candidate": row,
            "fr_snippets": snippet_fr(name or "", row.get("fr_pages") or []),
            "xref": {
                "extp206_hits": (xh.get("extp206_hits") or row.get("extp206_hits") or [])[:2],
                "imm16_code_hits": (xh.get("imm16_code_hits") or [])[:4],
            },
        }
        path = PACK_DIR / f"pack_{i:02d}_{name or 'unknown'}.json"
        raw = json.dumps(pack, ensure_ascii=False, indent=2)
        path.write_text(raw + "\n", encoding="utf-8")
        packs.append({"file": str(path.name), "bytes": len(raw.encode("utf-8")), "name": name})
        print(f"{path.name}: {len(raw.encode('utf-8'))} bytes")

    summary = PACK_DIR / "packs_summary.json"
    summary.write_text(json.dumps({"packs": packs, "micro_prompt_chars": len(MICRO_PROMPT)}, indent=2) + "\n")
    print(f"wrote {len(packs)} packs -> {PACK_DIR}")


if __name__ == "__main__":
    main()
