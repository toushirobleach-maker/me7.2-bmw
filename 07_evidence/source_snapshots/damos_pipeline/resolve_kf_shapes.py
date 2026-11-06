#!/usr/bin/env python3
"""Resolve KF map shapes: STD_AXIS (B704+header) vs COM_AXIS (B524+Z-only).

Gold standard on 6901: KFETRD far-ptr → header `ncols,nrows,X[],Y[],Z[]`
  MOV R12,#hdr; MOV R13,#0x206; R14/R15 inputs; CALLS 0x01,0xB704

COM_AXIS / 1-input path:
  MOV R12,#z; MOV R13,#0x206; R14 input; CALLS 0x01,0xB524
  R12 points at Z only — do NOT parse first bytes as ncols/nrows.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

from paths import BIN_PATH, DAMOS_LITE, OUT_DIR, PROVEN_DIR, ROOT, STOCK_PATH

REPORT = OUT_DIR / "KF_SHAPE_RESOLUTION.json"
REPORT_RU = OUT_DIR / "KF_SHAPE_RESOLUTION_RU.md"
A2L_PATH = ROOT / "02_definitions/BMW-XDFs/Me7.2/BMW ME7.2 X5 4.4 V8/E5A0_000.a2l"


def mono(b: bytes) -> bool:
    if len(b) < 2:
        return True
    up = all(b[i] <= b[i + 1] for i in range(len(b) - 1))
    dn = all(b[i] >= b[i + 1] for i in range(len(b) - 1))
    return up or dn


def parse_std(stock: bytes, fo: int) -> dict | None:
    if fo + 2 >= len(stock):
        return None
    cols, rows = stock[fo], stock[fo + 1]
    if not (2 <= cols <= 24 and 2 <= rows <= 24):
        return None
    x0, y0, z0 = fo + 2, fo + 2 + cols, fo + 2 + cols + rows
    zlen = cols * rows
    if z0 + zlen > len(stock):
        return None
    x, y = stock[x0:y0], stock[y0:z0]
    ok = (
        mono(x)
        and mono(y)
        and len(set(x)) >= max(2, cols // 2)
        and len(set(y)) >= max(2, rows // 2)
        and zlen >= 6
    )
    return {
        "ok": ok,
        "cols": cols,
        "rows": rows,
        "x_off": hex(x0),
        "y_off": hex(y0),
        "z_off": hex(z0),
        "header_off": hex(fo),
        "z_len": zlen,
        "span": 2 + cols + rows + zlen,
        "x_hex": x.hex(),
        "y_hex": y.hex(),
    }


def scan_far_calls(buf: bytes) -> dict[int, list[dict]]:
    """file_off(Z or hdr) -> consumer sites.

    Patterns:
      R12/R13 #206 … CALLS B704 / B524
      R12/R13 #206; R14/R15 #page … CALLS BB94/BB20 (COM_AXIS + explicit AXIS_PTS)
    """
    hits: dict[int, list[dict]] = defaultdict(list)
    i, n = 0, len(buf)
    while i < n - 32:
        if buf[i] == 0xE6 and buf[i + 1] == 0xFC and buf[i + 4] == 0xE6 and buf[i + 5] == 0xFD:
            off = buf[i + 2] | (buf[i + 3] << 8)
            page = buf[i + 6] | (buf[i + 7] << 8)
            if page == 0x206:
                fo = 0x206 * 0x4000 + (off & 0x3FFF) - 0x800000
                if 0x10000 <= fo <= 0x1FFFF:
                    callee = None
                    seg = cof = None
                    axis = None
                    # optional R14/R15 far-ptr (axis) before CALLS
                    if (
                        i + 16 < n
                        and buf[i + 8] == 0xE6
                        and buf[i + 9] == 0xFE
                        and buf[i + 12] == 0xE6
                        and buf[i + 13] == 0xFF
                    ):
                        a_off = buf[i + 10] | (buf[i + 11] << 8)
                        a_page = buf[i + 14] | (buf[i + 15] << 8)
                        a_phys = a_page * 0x4000 + (a_off & 0x3FFF)
                        a_fo = a_phys - 0x800000
                        axis = {
                            "off": hex(a_off),
                            "page": hex(a_page),
                            "phys": hex(a_phys),
                            "file_off": hex(a_fo) if 0 <= a_fo < 0x80000 else None,
                        }
                        scan_from = 16
                    else:
                        scan_from = 8
                    for j in range(scan_from, scan_from + 16):
                        if i + j + 3 < n and buf[i + j] == 0xDA:
                            seg = buf[i + j + 1]
                            cof = buf[i + j + 2] | (buf[i + j + 3] << 8)
                            if seg == 1 and cof == 0xB704:
                                callee = "B704_2D"
                            elif seg == 1 and cof == 0xB524:
                                callee = "B524_1IN"
                            elif seg == 1 and cof in (0xBB94, 0xBB20):
                                callee = "BB94_COM_EXPLICIT" if cof == 0xBB94 else "BB20_COM_EXPLICIT"
                            else:
                                callee = f"CALLS_{seg:02X}_{cof:04X}"
                            break
                    hits[fo].append(
                        {
                            "ea": hex(0x800000 + i),
                            "raw_hex": buf[i : i + (16 if axis else 8)].hex(),
                            "off": hex(off),
                            "seg": seg,
                            "cof": cof,
                            "callee": callee,
                            "axis_far": axis,
                        }
                    )
            i += 8
        else:
            i += 1
    return hits


def parse_a2l_shapes(path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    out = {}
    for m in re.finditer(
        r"/begin CHARACTERISTIC\s+(\w+)\s+\"([^\"]*)\"\s+(\w+)\s+(0x[0-9A-Fa-f]+)",
        text,
    ):
        name, desc, typ, cpu = m.group(1), m.group(2), m.group(3), int(m.group(4), 16)
        block = text[m.end() : m.end() + 1600]
        end = block.find("/end CHARACTERISTIC")
        if end >= 0:
            block = block[:end]
        axes = []
        for ax in re.findall(r"/begin AXIS_DESCR(.*?)/end AXIS_DESCR", block, re.S):
            at = re.search(r"\b(STD_AXIS|COM_AXIS|FIX_AXIS|RES_AXIS)\b", ax)
            refs = re.findall(r"AXIS_PTS_REF\s+(\w+)", ax)
            # count: digit line after conversion often
            lines = [l.strip() for l in ax.splitlines() if l.strip()]
            n = None
            for i, l in enumerate(lines):
                if l.isdigit() and int(l) <= 64:
                    # prefer digit after axis type/name/conversion
                    n = int(l)
            # more reliable: after AXIS type name conversion
            m2 = re.search(
                r"(?:STD_AXIS|COM_AXIS)\s+\S+\s+\S+\s+(\d+)", ax
            )
            if m2:
                n = int(m2.group(1))
            axes.append({"type": at.group(1) if at else None, "n": n, "refs": refs})
        blob = re.search(r"DP_BLOB\s+0x[0-9A-Fa-f]+\s+0x([0-9A-Fa-f]+)", block)
        out[name] = {
            "a2l_type": typ,
            "file": cpu - 0x800000,
            "axes": axes,
            "blob": int(blob.group(1), 16) if blob else None,
            "desc": desc[:80],
            "axis_mode_a2l": (
                "COM_AXIS"
                if any(a.get("type") == "COM_AXIS" for a in axes)
                else "STD_AXIS"
                if any(a.get("type") == "STD_AXIS" for a in axes)
                else None
            ),
            "cols": axes[0]["n"] if axes else None,
            "rows": axes[1]["n"] if len(axes) > 1 else (1 if axes else None),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    buf = BIN_PATH.read_bytes()
    stock = STOCK_PATH.read_bytes()
    damos = json.loads(DAMOS_LITE.read_text(encoding="utf-8"))
    far = scan_far_calls(buf)
    a2l = parse_a2l_shapes(A2L_PATH) if A2L_PATH.exists() else {}

    resolved = []
    stats = Counter()

    for sym in damos["symbols"]:
        if not sym["name"].upper().startswith("KF"):
            continue
        if not sym.get("addr"):
            continue
        # find best far hit near addr / header / evidence
        a = int(sym["addr"], 16)
        candidates = []
        for fo, sites in far.items():
            for s in sites:
                d = min(abs(fo - a), abs(fo - (a - 2)), abs(fo - (a + 2)))
                sh = (sym.get("evidence") or {}).get("shape")
                if isinstance(sh, dict) and sh.get("header_off"):
                    d = min(d, abs(fo - int(sh["header_off"], 16)))
                if d <= 16:
                    candidates.append((d, fo, s))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (x[0], 0 if x[2].get("callee") == "B704_2D" else 1))
        dist, fo, site = candidates[0]
        callee = site.get("callee") or "UNKNOWN"
        std = parse_std(stock, fo)
        a2 = a2l.get(sym["name"], {})

        if callee == "B704_2D" and std and std["ok"]:
            mode = "STD_AXIS"
            shape_status = "PROVEN"
            shape = {
                "axis_mode": mode,
                "cols": std["cols"],
                "rows": std["rows"],
                "header_off": std["header_off"],
                "x_off": std["x_off"],
                "y_off": std["y_off"],
                "z_off": std["z_off"],
                "z_len": std["z_len"],
                "span": std["span"],
                "shape_status": shape_status,
                "callee": callee,
                "consumer_ea": site["ea"],
                "falsifier": "monotonic X/Y + diversity + zlen>=6; matches KFETRD layout",
            }
            # apply to symbol
            sym["addr"] = std["z_off"]
            sym["rows"] = std["rows"]
            sym["cols"] = std["cols"]
            sym["x"] = std["x_off"]
            sym["y"] = std["y_off"]
            stats["STD_AXIS_PROVEN"] += 1

        elif callee in ("B524_1IN", "BB94_COM_EXPLICIT", "BB20_COM_EXPLICIT") or site.get("axis_far"):
            mode = "COM_AXIS"
            cols, rows = a2.get("cols"), a2.get("rows")
            blob = a2.get("blob")
            z_len = None
            shape_status = "HYP_dims"
            if cols and rows:
                if blob == cols * rows:
                    z_len = cols * rows
                    shape_status = "STRUCT_dims_blob_match"
                elif blob == 2 * cols * rows:
                    z_len = cols * rows
                    shape_status = "STRUCT_dims_blob_match_word"
                else:
                    z_len = cols * rows

            axis_far = site.get("axis_far")
            axis_proven = None
            if axis_far and axis_far.get("file_off"):
                afo = int(axis_far["file_off"], 16)
                # Prefer packed X[n]+Y[m] when A2L dims known
                if cols and rows and afo + cols + rows <= len(stock):
                    xb = stock[afo : afo + cols]
                    yb = stock[afo + cols : afo + cols + rows]
                    if mono(xb) and mono(yb):
                        axis_proven = {
                            "x_off": hex(afo),
                            "y_off": hex(afo + cols),
                            "cols": cols,
                            "rows": rows,
                            "x_hex": xb.hex(),
                            "y_hex": yb.hex(),
                            "status": "PROVEN",
                        }
                        shape_status = "PROVEN_axes_Z_STRUCT_or_blob"
                        z_len = cols * rows
                if axis_proven is None:
                    # single monotonic run length 4..24
                    for n in range(24, 3, -1):
                        xb = stock[afo : afo + n]
                        if mono(xb) and len(set(xb)) >= max(2, n // 2):
                            axis_proven = {
                                "x_off": hex(afo),
                                "n": n,
                                "x_hex": xb.hex(),
                                "status": "PROVEN_one_axis",
                            }
                            break

            if axis_proven and axis_proven.get("status") == "PROVEN":
                stats["COM_AXIS_AXES_PROVEN"] += 1
            else:
                stats["COM_AXIS"] += 1

            shape = {
                "axis_mode": mode,
                "cols": cols if not axis_proven or "cols" not in axis_proven else axis_proven["cols"],
                "rows": rows if not axis_proven or "rows" not in axis_proven else axis_proven["rows"],
                "header_off": None,
                "x_off": (axis_proven or {}).get("x_off"),
                "y_off": (axis_proven or {}).get("y_off"),
                "z_off": hex(fo),
                "z_len": z_len,
                "axis_pts_ref": [r for ax in a2.get("axes", []) for r in ax.get("refs", [])],
                "axis_far": axis_far,
                "axis_proven": axis_proven,
                "shape_status": shape_status,
                "callee": callee,
                "consumer_ea": site["ea"],
                "a2l_note": "Z via far-ptr; dims from AXIS_PTS on 6901 if proven else E5A0 transfer",
                "falsifier": "STD ncols/nrows at Z rejected; COM path uses separate AXIS_PTS",
            }
            sym["addr"] = hex(fo)
            sym["rows"] = shape["rows"]
            sym["cols"] = shape["cols"]
            sym["x"] = shape.get("x_off")
            sym["y"] = shape.get("y_off")

        elif callee == "B704_2D":
            # B704 but header not STD_ok — do not invent dims
            mode = "STD_AXIS_UNRESOLVED"
            shape_status = "UNRESOLVED_dims"
            shape = {
                "axis_mode": mode,
                "cols": None,
                "rows": None,
                "header_off": hex(fo),
                "x_off": None,
                "y_off": None,
                "z_off": None,
                "z_len": None,
                "raw_head": stock[fo : fo + 8].hex(),
                "std_attempt": std,
                "shape_status": shape_status,
                "callee": callee,
                "consumer_ea": site["ea"],
                "a2l_hint": {
                    "cols": a2.get("cols"),
                    "rows": a2.get("rows"),
                    "blob": a2.get("blob"),
                    "mode": a2.get("axis_mode_a2l"),
                },
                "note": "B704 consumer proven; local ubyte STD header failed (word axes / other packing)",
            }
            sym["addr"] = hex(fo)
            sym["rows"] = None
            sym["cols"] = None
            sym["x"] = None
            sym["y"] = None
            stats["STD_UNRESOLVED"] += 1
        else:
            mode = "UNKNOWN_CALLEE"
            shape = {
                "axis_mode": mode,
                "callee": callee,
                "consumer_ea": site["ea"],
                "header_off": hex(fo),
                "shape_status": "UNKNOWN",
            }
            stats["UNKNOWN"] += 1

        ev = sym.setdefault("evidence", {})
        ev["shape"] = shape
        ev["shape_resolution"] = "KF_SHAPE_RESOLUTION.json"
        # keep PROVEN for consumer; shape_status separate
        if sym.get("status") == "PROVEN" and shape.get("shape_status") == "UNRESOLVED_dims":
            # still PROVEN addr/consumer; annotate title
            if "shape?" not in (sym.get("title") or ""):
                sym["title"] = (sym.get("title") or sym["name"]) + " [shape?]"

        resolved.append(
            {
                "name": sym["name"],
                "status": sym.get("status"),
                "callee": callee,
                "far_off": hex(fo),
                "match_dist": dist,
                "shape": shape,
                "a2l": {
                    "mode": a2.get("axis_mode_a2l"),
                    "cols": a2.get("cols"),
                    "rows": a2.get("rows"),
                    "blob": a2.get("blob"),
                },
            }
        )

    damos["kf_shape_stats"] = dict(stats)
    DAMOS_LITE.write_text(json.dumps(damos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "epk": "6901I41D",
        "method": {
            "STD_AXIS": "CALLS B704 + monotonic ubyte header ncols,nrows,X,Y,Z (KFETRD @0x19B80)",
            "COM_AXIS_B524": "CALLS B524 + R12=Z only; dims A2L/blob",
            "COM_AXIS_EXPLICIT": "CALLS BB94/BB20 + R12/R13=Z#206 + R14/R15=AXIS_PTS far (often #204)",
            "UNRESOLVED": "B704 but ubyte-STD header fail (word axes etc.)",
        },
        "stats": dict(stats),
        "items": resolved,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (PROVEN_DIR / REPORT.name).write_text(REPORT.read_text(encoding="utf-8"), encoding="utf-8")

    lines = [
        "# KF shape resolution (COM_AXIS vs STD_AXIS)",
        "",
        f"Stats: `{dict(stats)}`",
        "",
        "## Правила (доказано кодом на 6901)",
        "",
        "1. **STD_AXIS**: `MOV R12,#hdr; MOV R13,#0x206; R14/R15; CALLS B704` → "
        "заголовок `ncols,nrows,X[],Y[],Z[]` (эталон KFETRD @`0x19B80`).",
        "2. **COM_AXIS**: `… CALLS B524` (один вход R14) → R12 указывает на **Z**, "
        "не на ncols/nrows. Размерности из E5A0 — перенос, пока нет AXIS_PTS на 6901.",
        "3. **UNRESOLVED**: B704 есть, но ubyte-STD заголовок не сходится (часто word-оси).",
        "",
        "| Name | Callee | Mode | Shape status | Dims | Z/hdr |",
        "|---|---|---|---|---|---|",
    ]
    for it in resolved:
        sh = it["shape"]
        dims = f"{sh.get('rows')}x{sh.get('cols')}" if sh.get("cols") else "-"
        lines.append(
            f"| {it['name']} | {it['callee']} | {sh.get('axis_mode')} | "
            f"{sh.get('shape_status')} | {dims} | {sh.get('z_off') or sh.get('header_off')} |"
        )
    REPORT_RU.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (PROVEN_DIR / REPORT_RU.name).write_text(REPORT_RU.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps({"stats": dict(stats), "n": len(resolved)}, indent=2))
    # focus print
    for name in ("KFLF", "KFLAMFA", "KFLMSKH", "KFLMSKH2", "KFMIRED", "KFMIRED1", "KFRI", "KFRTV", "KFETRD"):
        it = next((x for x in resolved if x["name"] == name), None)
        if it:
            print(name, it["callee"], it["shape"].get("axis_mode"), it["shape"].get("shape_status"),
                  it["shape"].get("rows"), it["shape"].get("cols"), it["shape"].get("z_off") or it["shape"].get("header_off"))


if __name__ == "__main__":
    main()
