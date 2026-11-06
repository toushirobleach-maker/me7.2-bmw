#!/usr/bin/env python3
"""Merge xref/FR/headers into statuses; emit review_queue for ambiguous cases."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from paths import (
    DAMOS_LITE,
    FR_CATALOG,
    MAP_HEADERS,
    OUT_DIR,
    REVIEW_QUEUE,
    XREF_HITS,
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
    xref = json.loads(XREF_HITS.read_text(encoding="utf-8")) if XREF_HITS.exists() else {}
    headers = json.loads(MAP_HEADERS.read_text(encoding="utf-8")) if MAP_HEADERS.exists() else {}
    catalog = json.loads(FR_CATALOG.read_text(encoding="utf-8")) if FR_CATALOG.exists() else []

    xref_by_addr = {s["addr"]: s for s in xref.get("by_symbol", []) if s.get("addr")}
    fr_names = {c["name"] for c in catalog}
    map_z = {h["z_off"] for h in headers.get("maps_2d", [])}
    map_hdr = {h["header_off"] for h in headers.get("maps_2d", [])}

    queue = []
    for sym in damos["symbols"]:
        addr = sym.get("addr")
        name = sym.get("name")
        status = sym.get("status")
        # enrich FR pages from catalog if empty
        if name in fr_names and not sym.get("fr_pages"):
            for c in catalog:
                if c["name"] == name:
                    sym["fr_pages"] = c["fr_pages"]
                    break

        xh = xref_by_addr.get(addr or "")
        has_extp = bool(xh and xh.get("extp206_hits"))
        has_fr = bool(sym.get("fr_pages")) or (name in fr_names)
        has_consumer = bool((sym.get("evidence") or {}).get("consumer") or sym.get("consumer_ea"))
        shape_hit = addr in map_z or addr in map_hdr if addr else False

        # already human-proven stays
        if status == "PROVEN":
            sym["judge"] = "keep_PROVEN"
            continue

        # skip_llm hard blockers stay STRUCT, not queued
        if sym.get("skip_llm"):
            sym["judge"] = f"blocked_{sym.get('needs')}"
            sym["status"] = "STRUCT"
            continue

        # auto rules
        if has_consumer and has_fr and status in {"STRUCT", "HYP", "UNLINKED"}:
            # consumer+FR already present from seed/promotion — auto PROVEN only if
            # evidence.consumer exists (real decode), not just xref heuristic
            if (sym.get("evidence") or {}).get("consumer"):
                sym["status"] = "PROVEN"
                sym["judge"] = "auto_PROVEN_consumer_fr"
                continue

        if has_extp and has_fr and not has_consumer:
            sym["status"] = "STRUCT"
            sym["judge"] = "auto_STRUCT_extp_fr"
            # needs human to confirm consumer decode
            queue.append(
                {
                    "reason": "extp_hit_needs_decode",
                    "name": name,
                    "addr": addr,
                    "fr_pages": sym.get("fr_pages", [])[:5],
                    "extp206_hits": (xh or {}).get("extp206_hits", [])[:3],
                    "title": sym.get("title"),
                }
            )
            continue

        if shape_hit and has_fr:
            sym["status"] = "STRUCT"
            sym["judge"] = "auto_STRUCT_shape_fr"
            queue.append(
                {
                    "reason": "map_shape_fr_unlinked_name",
                    "name": name,
                    "addr": addr,
                    "fr_pages": sym.get("fr_pages", [])[:5],
                    "title": sym.get("title"),
                }
            )
            continue

        if status == "STRUCT":
            sym["judge"] = "keep_STRUCT"
            if not sym.get("skip_llm"):
                queue.append(
                    {
                        "reason": "struct_unresolved",
                        "name": name,
                        "addr": addr,
                        "fr_pages": sym.get("fr_pages", [])[:5],
                        "title": sym.get("title"),
                        "blocked_reason": (sym.get("evidence") or {}).get("blocked_reason"),
                    }
                )
            continue

        sym["judge"] = "noop"

    # Add UNLINKED FR candidates not already in damos (cap)
    existing = {s.get("name") for s in damos["symbols"]}
    added = 0
    for c in catalog:
        if c["name"] in existing:
            continue
        if c.get("fr_type") not in {"FW", "KF", "KL", "CW"} and not c["name"].startswith(
            ("CLA", "CW", "CD", "KF", "MSL")
        ):
            continue
        damos["symbols"].append(
            {
                "name": c["name"],
                "title": f"[UNLINKED] {c['name']}",
                "addr": None,
                "kind": "scalar" if c.get("fr_type") in {None, "FW", "CW"} else "map",
                "status": "UNLINKED",
                "fr_pages": c["fr_pages"][:10],
                "fr_type": c.get("fr_type"),
                "source": "fr_catalog",
                "judge": "unlinked_fr",
            }
        )
        queue.append(
            {
                "reason": "fr_unlinked",
                "name": c["name"],
                "addr": None,
                "fr_pages": c["fr_pages"][:5],
                "fr_type": c.get("fr_type"),
            }
        )
        added += 1
        if added >= 80:
            break

    # Cap queue; prefer actionable, drop pure fr_unlinked beyond 15
    actionable = [q for q in queue if q["reason"] != "fr_unlinked"]
    fr_only = [q for q in queue if q["reason"] == "fr_unlinked"][:15]
    # drop skip reasons already blocked
    actionable = [q for q in actionable if not q.get("blocked_reason")]
    final_q = (actionable + fr_only)[:40]

    with REVIEW_QUEUE.open("w", encoding="utf-8") as f:
        for q in final_q:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    damos["status_counts"] = dict(Counter(s["status"] for s in damos["symbols"]))
    damos["judge_stats"] = dict(Counter(s.get("judge", "none") for s in damos["symbols"]))
    damos["review_queue_len"] = len(final_q)
    DAMOS_LITE.write_text(json.dumps(damos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"judge done counts={damos['status_counts']} queue={len(final_q)} "
        f"added_unlinked={added} -> {REVIEW_QUEUE}"
    )


if __name__ == "__main__":
    main()
