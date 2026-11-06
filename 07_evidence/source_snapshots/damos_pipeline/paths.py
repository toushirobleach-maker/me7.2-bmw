"""Shared paths for DAMOS-lite pipeline."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVEN_DIR = ROOT / "02_definitions" / "6901I41D_proven"
FR_DIR = ROOT / "07_analysis" / "fr_full_index"
OUT_DIR = ROOT / "07_analysis" / "damos_lite"
CACHE_DIR = OUT_DIR / "evidence_cache"
PACK_DIR = OUT_DIR / "review_packs"
BIN_PATH = ROOT / "00_original" / "ME72_7532675_full_512KiB_20261105T164440Z.bin"
STOCK_PATH = (
    ROOT
    / "00_original"
    / "stock_from_SP-Daten_E53_EK726"
    / "ME72_7532675_6901I41D_stock_from_G7533626_512KiB.bin"
)
DECODE_TOOLS = ROOT / "10_review" / "20261106_deep_review" / "tools"

DAMOS_LITE = OUT_DIR / "damos_lite.json"
CANDIDATES = OUT_DIR / "candidates.jsonl"
XREF_HITS = OUT_DIR / "xref_hits.json"
MAP_HEADERS = OUT_DIR / "map_headers.json"
FR_CATALOG = OUT_DIR / "fr_symbol_catalog.json"
REVIEW_QUEUE = OUT_DIR / "review_queue.jsonl"
PIPELINE_REPORT = OUT_DIR / "pipeline_report.json"
GENERATED_XDF = PROVEN_DIR / "ME72_7532675_6901I41D_from_damos.xdf"
MANIFEST = PROVEN_DIR / "XDF_MANIFEST.json"
