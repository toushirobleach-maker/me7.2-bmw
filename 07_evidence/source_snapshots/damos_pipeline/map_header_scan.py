#!/usr/bin/env python3
"""Scan calibration region for Bosch-style map headers (ncols nrows)."""
from __future__ import annotations

import json

from paths import BIN_PATH, MAP_HEADERS, OUT_DIR, STOCK_PATH


def scan(buf: bytes, base: int = 0x10000, end: int = 0x1F000) -> list[dict]:
    out = []
    i = base
    while i < end - 2:
        cols, rows = buf[i], buf[i + 1]
        # typical small maps
        if 2 <= cols <= 24 and 2 <= rows <= 24:
            z0 = i + 2 + cols + rows
            zlen = cols * rows
            if z0 + zlen <= end:
                # heuristic: axes look non-trivial (not all 0/FF)
                x = buf[i + 2 : i + 2 + cols]
                y = buf[i + 2 + cols : i + 2 + cols + rows]
                if len(set(x)) >= 2 and len(set(y)) >= 2:
                    out.append(
                        {
                            "header_off": hex(i),
                            "cols": cols,
                            "rows": rows,
                            "x_off": hex(i + 2),
                            "y_off": hex(i + 2 + cols),
                            "z_off": hex(z0),
                            "z_len": zlen,
                            "x_hex": x.hex(),
                            "y_hex": y.hex(),
                        }
                    )
                    # skip past this map to reduce duplicates
                    i = z0 + zlen
                    continue
        i += 1
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stock = STOCK_PATH.read_bytes() if STOCK_PATH.exists() else BIN_PATH.read_bytes()
    headers = scan(stock)
    # also 1-row curves: header single count byte 04..10 then axis+values
    curves = []
    buf = stock
    for off in range(0x10000, 0x1F000):
        n = buf[off]
        if 4 <= n <= 16:
            axis = buf[off + 1 : off + 1 + n]
            vals = buf[off + 1 + n : off + 1 + 2 * n]
            if len(axis) == n and len(vals) == n and len(set(axis)) >= 3:
                curves.append(
                    {
                        "header_off": hex(off),
                        "n": n,
                        "axis_off": hex(off + 1),
                        "values_off": hex(off + 1 + n),
                    }
                )
    # dedupe curves densely
    filtered = []
    last = -100
    for c in curves:
        o = int(c["header_off"], 16)
        if o - last < 8:
            continue
        filtered.append(c)
        last = o
        if len(filtered) >= 400:
            break

    doc = {
        "maps_2d": headers[:500],
        "maps_2d_count": len(headers),
        "curves_1d": filtered[:400],
        "curves_1d_count": len(filtered),
    }
    MAP_HEADERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"maps={len(headers)} curves~={len(filtered)} -> {MAP_HEADERS}")


if __name__ == "__main__":
    main()
