"""Quarterly "FIT COMPLETE" report in Allissa's RSM layout.

One workbook, one tab per team plus ALL. Each tab carries her three blocks:

    DME / M1Sx / Pharmacy / Total summary
    DME table  - every fit row of the quarter, in the Fit Report's own
                 columns, plus POINT TOTAL, FFW PROVIDER (Y OR N) and NOTES
    M1Sx table - from the Surgical Tracker (optional CSV)
    Pharmacy   - provider x month Rx counts, 5 points each (optional CSV)

POINT TOTAL is the row's full value (base + gold pair) before any split, so
a split account appears once, at full value, with the split named in NOTES.
Read-only with respect to every Google Sheet: inputs are local exports.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .engine import PointEngine
from .fit_report import load_fit_report_workbook
from .loaders import load_new_providers
from .rules import RuleBook
from .workbook import CATEGORY_LABELS

# Fit Report columns echoed in the DME table, in Allissa's order.
DME_SOURCE_COLUMNS = [
    "PATIENT INFO", "PRO/REP/TEAM", "PRO", "REP", "TEAM", "INS", "TYPE",
    "DATE RX REC'D", "PATIENT STATUS", "DOS", "PRODUCT", "INSURANCE STATUS",
    "DATE DME REC'D", "SERIAL NUMBER",
]
DME_HEADERS = [
    "PATIENT NAME / DOB", "PRO/REP/TEAM", "PRO", "REP", "TEAM", "INS", "TYPE",
    "DATE RX REC'D", "PATIENT STATUS", "DOS", "PRODUCT", "INS STATUS",
    "DATE DME REC'D", "SERIAL NUMBER", "POINT TOTAL", "FFW PROVIDER (Y OR N)",
    "NOTES:",
]
PHARMACY_POINTS_PER_RX = 5

HEAD = Font(bold=True)
FILL = PatternFill("solid", fgColor="DDEBF7")
ZERO_FILL = PatternFill("solid", fgColor="F2F2F2")
REVIEW_FILL = PatternFill("solid", fgColor="FFF2CC")


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
    """reports: [(month_label, path)] -> list of dicts, one per fit row."""
    records = []
    for label, path in reports:
        rows = _load_rows(path)
        declared = (new_providers or {}).get(label)
        engine = PointEngine(rulebook=RuleBook.load(Path(rules_dir)),
                             new_providers=declared)
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


def _write_tab(ws, title: str, records: list, m1sx: list, pharmacy: list,
               months: list, include_extras: bool) -> None:
    dme_total = sum(r["points"] for r in records)
    m1sx_total = 0
    for row in m1sx[1:]:
        try:
            m1sx_total += int(str(row[7]).replace(",", "") or 0)
        except (ValueError, IndexError):
            pass
    rx_total = 0
    for row in pharmacy[1:]:
        for cell in row[1:]:
            try:
                rx_total += int(str(cell).replace(",", "") or 0)
            except ValueError:
                pass
    pharmacy_total = rx_total * PHARMACY_POINTS_PER_RX if include_extras else 0
    m1sx_total = m1sx_total if include_extras else 0

    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    for label, value in (("DME", dme_total), ("M1Sx", m1sx_total),
                         ("Pharmacy", pharmacy_total),
                         ("Total", dme_total + m1sx_total + pharmacy_total)):
        ws.append(["", "", label, "-", value])
        ws.cell(row=ws.max_row, column=3).font = HEAD
    ws.append([])

    ws.append(DME_HEADERS)
    for col in range(1, len(DME_HEADERS) + 1):
        cell = ws.cell(row=ws.max_row, column=col)
        cell.font = HEAD; cell.fill = FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for rec in records:
        ws.append(rec["cells"] + [rec["points"], rec["ffw"], rec["notes"]])
        if rec["review"]:
            for col in range(1, len(DME_HEADERS) + 1):
                ws.cell(row=ws.max_row, column=col).fill = REVIEW_FILL
        elif rec["points"] == 0:
            ws.cell(row=ws.max_row, column=15).fill = ZERO_FILL
    ws.append([""] * 14 + [dme_total, "", f"TOTAL: {dme_total:,}"])
    ws.cell(row=ws.max_row, column=15).font = HEAD
    ws.cell(row=ws.max_row, column=17).font = HEAD
    ws.append([])

    if include_extras:
        ws.append(["M1Sx (Surgical Tracker)"]); ws.cell(row=ws.max_row, column=1).font = HEAD
        for i, row in enumerate(m1sx or [["PATIENT NAME", "PROVIDER", "REP", "TEAM",
                                          "PRODUCT", "VENDOR", "SX DATE", "POINT TOTAL", "NOTES:"]]):
            ws.append(list(row))
            if i == 0:
                for col in range(1, len(row) + 1):
                    ws.cell(row=ws.max_row, column=col).font = HEAD
        ws.append(["", "", "", "", "", "", "TOTAL:", m1sx_total])
        ws.append([])
        ws.append([f"Pharmacy (Rx counts x {PHARMACY_POINTS_PER_RX} points)"])
        ws.cell(row=ws.max_row, column=1).font = HEAD
        header = ["PROVIDER:"] + [f"{m} TOTAL" for m in months] + ["TOTAL:", "NOTES:"]
        rows = pharmacy or [header]
        for i, row in enumerate(rows):
            if i == 0:
                ws.append(list(row))
                for col in range(1, len(row) + 1):
                    ws.cell(row=ws.max_row, column=col).font = HEAD
                continue
            counts = []
            for cell in row[1:]:
                try:
                    counts.append(int(str(cell).replace(",", "") or 0))
                except ValueError:
                    counts.append(0)
            ws.append([row[0]] + counts + [sum(counts)])
        ws.append(["", "", "", "TOTAL:", pharmacy_total, f"{rx_total} X {PHARMACY_POINTS_PER_RX}"])

    widths = [30, 40, 26, 30, 14, 18, 12, 12, 16, 10, 36, 22, 12, 14, 12, 12, 60]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A9"


def build_quarterly_report(reports: list, out_path: Path, title: str,
                           new_providers: dict | None = None,
                           m1sx_csv=None, pharmacy_csv=None,
                           rules_dir: str | Path = "rules") -> Path:
    records = score_quarter(reports, rules_dir, new_providers)
    months = [label.split()[0] for label, _ in reports]
    m1sx = _read_csv(m1sx_csv)
    pharmacy = _read_csv(pharmacy_csv)
    wb = Workbook()
    ws = wb.active; ws.title = "ALL"
    _write_tab(ws, title, records, m1sx, pharmacy, months, include_extras=True)
    by_team = defaultdict(list)
    for rec in records:
        by_team[rec["team"]].append(rec)
    for team in sorted(by_team):
        name = "".join(ch for ch in team if ch not in '[]:*?/\\')[:31] or "TEAM"
        _write_tab(wb.create_sheet(name), f"{title} - {team}", by_team[team],
                   m1sx, pharmacy, months, include_extras=False)
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
        description="Build the quarterly FIT COMPLETE report from monthly Fit Reports.")
    parser.add_argument("--report", action="append", required=True,
                        help='"JUNE 2026=path/to/30_JUNE_2026_FITTINGS.csv" (repeat per month)')
    parser.add_argument("--new-providers", action="append", default=[],
                        help='"JUNE 2026=path/to/new_providers.txt" (repeat per month)')
    parser.add_argument("--m1sx", help="CSV of the M1Sx table (Surgical Tracker rows)")
    parser.add_argument("--pharmacy", help="CSV: PROVIDER, <month> counts...")
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
