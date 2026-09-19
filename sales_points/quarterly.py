"""Quarterly "FIT COMPLETE" report in Allissa's RSM layout and styling.

Mirrors her Q2 2026 workbook exactly: twelve tabs -

    MASTER-GRAND TOTAL, MASTER - DME, MASTER - M1SX, MASTER - PHARMACY
    EAST REGION - GRAND TOTAL, EAST REGION - DME, ... - M1SX, ... - PHARMACY
    WEST REGION - GRAND TOTAL, WEST REGION - DME, ... - M1SX, ... - PHARMACY

DME      every fit row of the quarter in the Fit Report's own columns plus
         POINT TOTAL, FFW PROVIDER (Y OR N) and NOTES. POINT TOTAL is the
         row's full value (base + Gold Pair) before any split; the split is
         named in NOTES so a shared account appears once.
M1SX     rows copied from the Surgical Tracker (CSV).
PHARMACY provider x month Rx counts, 5 points each (CSV).
GRAND TOTAL  DME / M1Sx / Pharmacy / Total, as formulas over the other tabs.

Her colours: light-blue bold headers (CFE2F3), yellow bold on an ancillary
provider (FFFF00), orange bold on the FIT status (FF9900) and on TCT products
(FF6D01), green bold on a billable status (B6D7A8), bright green on every
TOTAL (00FF00), and the FP2A "P2A" type in yellow. Region: a TEAM containing
"MICH" is WEST, everything else EAST (Q2: West = 20,450 of 215,580).
Read-only with respect to every Google Sheet: inputs are local exports.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .engine import PointEngine
from .fit_report import load_fit_report_workbook
from .loaders import load_new_providers
from .rules import RuleBook
from .workbook import CATEGORY_LABELS

DME_HEADERS = [
    "PATIENT NAME / DOB", "PRO/REP/TEAM", "PRO", "REP", "TEAM", "INS", "TYPE",
    "DATE RX REC'D", "PATIENT STATUS", "DOS", "PRODUCT", "INS STATUS",
    "DATE DME REC'D", "SERIAL NUMBER", "POINT TOTAL", "FFW PROVIDER (Y OR N)",
    "NOTES:",
]
DME_WIDTHS = [26, 44, 26, 30, 14, 20, 12, 12, 16, 10, 38, 24, 12, 16, 12, 12, 70]
M1SX_HEADERS = ["PATIENT NAME", "PROVIDER", "REP", "TEAM", "PRODUCT", "VENDOR",
                "SX DATE", "POINT TOTAL", "NOTES:"]
M1SX_WIDTHS = [18.4, 16, 12, 15.8, 34, 14, 12, 12, 40]
PHARMACY_POINTS_PER_RX = 5
REGIONS = ("EAST", "WEST")

FONT = "Calibri"
HEADER_FILL = PatternFill("solid", fgColor="CFE2F3")
PHARMACY_HEADER_FILL = PatternFill("solid", fgColor="A4C2F4")
TOTAL_FILL = PatternFill("solid", fgColor="00FF00")
ANCILLARY_FILL = PatternFill("solid", fgColor="FFFF00")
FIT_FILL = PatternFill("solid", fgColor="FF9900")
TCT_FILL = PatternFill("solid", fgColor="FF6D01")
BILLABLE_FILL = PatternFill("solid", fgColor="B6D7A8")
REVIEW_FILL = PatternFill("solid", fgColor="F4CCCC")
ZERO_FILL = PatternFill("solid", fgColor="EFEFEF")
THIN = Side(style="thin", color="BFBFBF")
GRID = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _font(bold=False, size=10, color=None):
    return Font(name=FONT, size=size, bold=bold, color=color)


def region_of(team: str) -> str:
    return "WEST" if "MICH" in (team or "").upper() else "EAST"


def _load_rows(path: Path) -> list:
    from .cli import _load_csv
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return load_fit_report_workbook(path)
    return _load_csv(path)


def _raw(row, header: str) -> str:
    for key, value in (row.raw or {}).items():
        if key.strip().upper() == header.upper():
            return (value or "").replace("\n", " ").strip()
    return ""


def _first_line(text: str) -> str:
    return (text or "").split("\n")[0].strip()


def score_quarter(reports: list, rules_dir: str | Path = "rules",
                  new_providers: dict | None = None) -> list:
    """reports: [(month_label, path)] -> one dict per fit row, in fit order."""
    records = []
    for label, path in reports:
        rows = _load_rows(path)
        engine = PointEngine(rulebook=RuleBook.load(Path(rules_dir)),
                             new_providers=(new_providers or {}).get(label))
        results, _summaries = engine.run(rows)
        for result in results:
            row = result.row
            notes = [label, CATEGORY_LABELS.get(result.rule_used, result.rule_used)]
            if result.bonus_points:
                notes.append(f"Gold Pair +{result.bonus_points}")
            if result.is_split:
                notes.append("Split: " + " / ".join(
                    f"{rep.name} {pts}" for rep, pts in result.rep_allocations))
            if "Rep override" in (result.explanation or ""):
                notes.append("Rep override applied")
            if result.total_points == 0:
                notes.append(result.explanation.split(".")[0])
            if result.review_needed:
                notes.append("REVIEW")
            records.append({
                "month": label,
                "team": _first_line(row.team) or "(no team)",
                "region": region_of(row.team),
                "cells": [_first_line(_raw(row, "PATIENT INFO")) or row.patient,
                          _raw(row, "PRO/REP/TEAM") or " ".join(
                              x for x in (row.pro, row.rep, row.team) if x),
                          _first_line(row.pro), _first_line(row.rep),
                          _first_line(row.team), row.insurance, row.type,
                          _raw(row, "DATE RX REC'D"), row.patient_status,
                          row.dos_code, row.product, row.insurance_status,
                          _raw(row, "DATE DME REC'D"), _raw(row, "SERIAL NUMBER")],
                "points": result.total_points,
                "ffw": "Y" if result.is_ancillary else "N",
                "notes": " | ".join(n for n in notes if n),
                "review": result.review_needed,
                "sort": (row.fit_date or row.date_rx_received, row.row_number),
            })
    records.sort(key=lambda r: (str(r["sort"][0]), r["sort"][1]))
    return records


def _read_csv(path) -> list:
    if not path:
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.reader(handle) if any(c.strip() for c in row)]


def _int(text) -> int:
    try:
        return int(str(text).replace(",", "").strip() or 0)
    except ValueError:
        return 0


def _header_row(ws, headers: list, fill=HEADER_FILL) -> None:
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _font(bold=True)
        cell.fill = fill
        cell.alignment = CENTER
        cell.border = GRID
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"


def _widths(ws, widths: list) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def write_dme(ws, records: list) -> str:
    """DME tab; returns the address of the POINT TOTAL sum cell."""
    _header_row(ws, DME_HEADERS)
    for rec in records:
        ws.append(rec["cells"] + [rec["points"], rec["ffw"], rec["notes"]])
        r = ws.max_row
        for col in range(1, len(DME_HEADERS) + 1):
            cell = ws.cell(row=r, column=col)
            cell.font = _font()
            cell.alignment = WRAP
            cell.border = GRID
        pro = ws.cell(row=r, column=3)
        if any(m in (pro.value or "") for m in ("*", "+")) or rec["ffw"] == "Y":
            pro.fill = ANCILLARY_FILL
            pro.font = _font(bold=True)
        status = ws.cell(row=r, column=9)
        if "FIT" in str(status.value or "").upper() and "INCOMPLETE" not in str(status.value).upper():
            status.fill = FIT_FILL
            status.font = _font(bold=True)
        product = ws.cell(row=r, column=11)
        if str(product.value or "").upper().startswith("TCT"):
            product.fill = TCT_FILL
            product.font = _font(bold=True)
        ins_status = ws.cell(row=r, column=12)
        if any(m in str(ins_status.value or "").upper()
               for m in ("O/A/B", "OPEN/ACTIVE", "BILLED", "OPEN/BILLABLE")):
            ins_status.fill = BILLABLE_FILL
            ins_status.font = _font(bold=True)
        type_cell = ws.cell(row=r, column=7)
        if "P2A" in str(type_cell.value or "").upper():
            type_cell.fill = ANCILLARY_FILL
            type_cell.font = _font(bold=True)
        points = ws.cell(row=r, column=15)
        points.number_format = "#,##0"
        points.alignment = Alignment(horizontal="right", vertical="top")
        ws.cell(row=r, column=16).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=16).font = _font(bold=True)
        if rec["review"]:
            for col in range(1, len(DME_HEADERS) + 1):
                ws.cell(row=r, column=col).fill = REVIEW_FILL
        elif rec["points"] == 0:
            points.fill = ZERO_FILL
    first, last = 2, max(ws.max_row, 2)
    total_row = last + 2  # one blank row, then the total
    ws.cell(row=total_row, column=14, value="TOTAL:").font = _font(bold=True)
    ws.cell(row=total_row, column=14).alignment = Alignment(horizontal="right")
    total = ws.cell(row=total_row, column=15,
                    value=f"=SUM(O{first}:O{last})" if records else 0)
    total.font = _font(bold=True)
    total.fill = TOTAL_FILL
    total.number_format = "#,##0"
    ws.cell(row=total_row, column=17,
            value=f"{len(records)} fit rows - POINT TOTAL is the full row value; "
                  "split accounts are named in NOTES").font = _font(size=9)
    _widths(ws, DME_WIDTHS)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(DME_HEADERS))}{last}"
    return f"O{total_row}"


def write_m1sx(ws, rows: list) -> str:
    _header_row(ws, M1SX_HEADERS)
    for row in rows:
        ws.append(list(row[:9]) + [""] * max(0, 9 - len(row)))
        r = ws.max_row
        for col in range(1, 10):
            cell = ws.cell(row=r, column=col)
            cell.font = _font()
            cell.border = GRID
            cell.alignment = WRAP
        ws.cell(row=r, column=8).value = _int(ws.cell(row=r, column=8).value)
        ws.cell(row=r, column=8).number_format = "#,##0"
        ws.cell(row=r, column=7).alignment = Alignment(horizontal="right")
    first, last = 2, max(ws.max_row, 2)
    total_row = ws.max_row + 1
    ws.cell(row=total_row, column=7, value="TOTAL:").font = _font(bold=True)
    total = ws.cell(row=total_row, column=8, value=f"=SUM(H{first}:H{last})" if rows else 0)
    total.font = _font(bold=True)
    total.fill = TOTAL_FILL
    total.number_format = "#,##0"
    _widths(ws, M1SX_WIDTHS)
    return f"H{total_row}"


def write_pharmacy(ws, header: list, rows: list) -> str:
    """rows: [provider, count_month1, count_month2, count_month3, ...]."""
    months = header[1:]
    headers = ["PROVIDER:"] + [f"{m} TOTAL" for m in months] + ["TOTAL:", "NOTES:"]
    _header_row(ws, headers, fill=PHARMACY_HEADER_FILL)
    n = len(months)
    for row in rows:
        counts = [_int(c) for c in row[1:1 + n]] + [0] * max(0, n - len(row) + 1)
        ws.append([row[0]] + counts)
        r = ws.max_row
        ws.cell(row=r, column=n + 2,
                value=f"=SUM({get_column_letter(2)}{r}:{get_column_letter(n + 1)}{r})")
        for col in range(1, n + 4):
            cell = ws.cell(row=r, column=col)
            cell.font = _font()
            cell.border = GRID
            if col > 1:
                cell.alignment = Alignment(horizontal="right")
    first, last = 2, max(ws.max_row, 2)
    total_row = ws.max_row + 1
    total_col = get_column_letter(n + 2)
    ws.cell(row=total_row, column=n + 1, value="TOTAL:").font = _font(bold=True)
    ws.cell(row=total_row, column=n + 1).alignment = Alignment(horizontal="right")
    rx = ws.cell(row=total_row, column=n + 2,
                 value=f"=SUM({total_col}{first}:{total_col}{last})" if rows else 0)
    rx.font = _font(bold=True)
    points = ws.cell(row=total_row, column=n + 3,
                     value=f"={total_col}{total_row}*{PHARMACY_POINTS_PER_RX}")
    points.font = _font(bold=True)
    points.fill = TOTAL_FILL
    points.number_format = "#,##0"
    ws.cell(row=total_row + 1, column=n + 3,
            value=f"Rx total x {PHARMACY_POINTS_PER_RX} = points").font = _font(size=9)
    _widths(ws, [30] + [14] * n + [12, 28])
    return f"{get_column_letter(n + 3)}{total_row}"


def write_grand_total(ws, dme_ref: str, m1sx_ref: str, pharmacy_ref: str,
                      title: str) -> None:
    ws.column_dimensions["A"].width = 2.6
    ws.column_dimensions["B"].width = 2.0
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 2.8
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["G"].width = 60
    for r, (label, ref) in enumerate((("DME", dme_ref), ("M1Sx", m1sx_ref),
                                      ("Pharmacy", pharmacy_ref), ("Total", None)), start=1):
        ws.cell(row=r, column=3, value=label).font = _font(bold=True)
        ws.cell(row=r, column=4, value="-").font = _font()
        cell = ws.cell(row=r, column=5, value=ref if ref else "=SUM(E1:E3)")
        cell.font = _font(bold=(label == "Total"))
        cell.number_format = "#,##0"
        if label == "Total":
            cell.fill = TOTAL_FILL
    ws.cell(row=1, column=7, value=title).font = _font(bold=True, size=12)
    ws.cell(row=2, column=7, value="Generated by the point engine from the monthly "
            "Fit Reports; M1Sx from the Surgical Tracker; Pharmacy from the "
            "quarterly pharmacy totals.").font = _font(size=9)
    ws.freeze_panes = "E1"


def build_quarterly_report(reports: list, out_path: Path, title: str,
                           new_providers: dict | None = None,
                           m1sx_csv=None, pharmacy_csv=None,
                           rules_dir: str | Path = "rules") -> Path:
    records = score_quarter(reports, rules_dir, new_providers)
    m1sx = _read_csv(m1sx_csv)
    m1sx_rows = m1sx[1:] if m1sx else []
    pharmacy = _read_csv(pharmacy_csv)
    if pharmacy:
        ph_header, ph_rows = pharmacy[0], pharmacy[1:]
        region_col = next((i for i, h in enumerate(ph_header) if h.strip().upper() == "REGION"), None)
    else:
        ph_header, ph_rows, region_col = ["PROVIDER:"] + [l.split()[0] for l, _ in reports], [], None

    def ph_for(region):
        header = [h for i, h in enumerate(ph_header) if i != region_col]
        rows = []
        for row in ph_rows:
            reg = (row[region_col].strip().upper() if region_col is not None and region_col < len(row) else "EAST")
            if region is None or reg == region:
                rows.append([c for i, c in enumerate(row) if i != region_col])
        return header, rows

    def m1sx_for(region):
        if region is None:
            return m1sx_rows
        return [r for r in m1sx_rows if len(r) > 3 and r[3].strip().upper() == region]

    wb = Workbook()
    wb.remove(wb.active)
    for prefix, region in (("MASTER", None), ("EAST REGION", "EAST"), ("WEST REGION", "WEST")):
        recs = records if region is None else [r for r in records if r["region"] == region]
        gt = wb.create_sheet(f"{prefix}-GRAND TOTAL" if prefix == "MASTER" else f"{prefix} - GRAND TOTAL")
        dme_ws = wb.create_sheet(f"{prefix} - DME")
        m1_ws = wb.create_sheet(f"{prefix} - M1SX")
        ph_ws = wb.create_sheet(f"{prefix} - PHARMACY")
        dme_ref = write_dme(dme_ws, recs)
        m1_ref = write_m1sx(m1_ws, m1sx_for(region))
        header, rows = ph_for(region)
        ph_ref = write_pharmacy(ph_ws, header, rows)
        scope = "ALL REGIONS" if region is None else f"{region} REGION"
        write_grand_total(gt, f"='{dme_ws.title}'!{dme_ref}", f"='{m1_ws.title}'!{m1_ref}",
                          f"='{ph_ws.title}'!{ph_ref}", f"{title} - {scope}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def _pairs(values: list) -> list:
    out = []
    for item in values or []:
        label, _, path = item.partition("=")
        if not path:
            raise SystemExit(f"expected LABEL=PATH, got {item!r}")
        out.append((label.strip(), Path(path.strip())))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the quarterly FIT COMPLETE report (RSM layout) from monthly Fit Reports.")
    parser.add_argument("--report", action="append", required=True,
                        help='"JUNE 2026=path/to/30_JUNE_2026_FITTINGS.csv" (repeat per month)')
    parser.add_argument("--new-providers", action="append", default=[],
                        help='"JUNE 2026=path/to/new_providers.txt" (repeat per month)')
    parser.add_argument("--m1sx", help="CSV of the M1Sx table (Surgical Tracker rows, TEAM = EAST/WEST)")
    parser.add_argument("--pharmacy", help="CSV: PROVIDER, <month> counts..., optional REGION column")
    parser.add_argument("--title", default="QUARTERLY FIT COMPLETE")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args(argv)
    declared = {label: load_new_providers(path) for label, path in _pairs(args.new_providers)}
    out = build_quarterly_report(_pairs(args.report), Path(args.out), args.title,
                                 new_providers=declared, m1sx_csv=args.m1sx,
                                 pharmacy_csv=args.pharmacy)
    print(f"Quarterly report: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
