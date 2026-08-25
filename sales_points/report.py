"""Output writers.

Everything is written to local CSV files. Nothing in this package writes back
to Google Sheets or any other live system - the reviewed output is copied into
the official commission sheet by hand, exactly as the SOP requires.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

# Column order matches the POINT SUMMARY TEMPLATE tab of the cheat sheet.
POINT_SHEET_COLUMNS = [
    "Patient", "Pro", "Rep", "Team", "Insurance", "Type", "Date RX Rcvd",
    "Patient Status", "DOC", "Product", "Insurance Status", "Base Points",
    "Bonus Points", "Total Applicable Points", "Split?", "Rep 1", "Rep 1 ID",
    "Rep 1 Points", "Rep 2", "Rep 2 ID", "Rep 2 Points", "Adjustment",
    "Final Points", "Rule Used", "Review Needed?", "AI Explanation",
]

SUMMARY_COLUMNS = [
    "Rep ID", "Rep Name", "Row Points", "Rep-Level Bonus", "Gross Points",
    "Honorarium Deduction", "Final Points", "Rows", "Rows Needing Review", "Notes",
]


def _date(value) -> str:
    return value.isoformat() if value else ""


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "UNKNOWN").strip())
    return cleaned.strip("_") or "UNKNOWN"


def result_to_row(result, rep_points_override=None) -> dict:
    """Render one RowResult in POINT SUMMARY TEMPLATE shape."""
    row = result.row
    allocations = result.rep_allocations
    record = {
        "Patient": row.patient,
        "Pro": row.pro,
        "Rep": row.rep,
        "Team": row.team,
        "Insurance": row.insurance,
        "Type": row.type,
        "Date RX Rcvd": _date(row.date_rx_received),
        "Patient Status": row.patient_status,
        "DOC": row.doc,
        "Product": row.product,
        "Insurance Status": row.insurance_status,
        "Base Points": result.base_points,
        "Bonus Points": result.bonus_points,
        "Total Applicable Points": result.total_points,
        "Split?": "Yes" if result.is_split else "No",
        "Adjustment": 0,
        "Final Points": (
            rep_points_override
            if rep_points_override is not None
            else result.total_points
        ),
        "Rule Used": result.rule_used,
        "Review Needed?": "Yes" if result.review_needed else "No",
        "AI Explanation": result.explanation.strip(),
    }
    for index in (0, 1):
        prefix = f"Rep {index + 1}"
        if index < len(allocations):
            rep, points = allocations[index]
            record[prefix] = rep.name
            record[f"{prefix} ID"] = rep.rep_id
            record[f"{prefix} Points"] = points
        else:
            record[prefix] = ""
            record[f"{prefix} ID"] = ""
            record[f"{prefix} Points"] = ""
    return record


def write_csv(path: Path, columns: list, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def write_master_sheet(out_dir: Path, results: list) -> Path:
    path = Path(out_dir) / "master_point_sheet.csv"
    write_csv(path, POINT_SHEET_COLUMNS, [result_to_row(r) for r in results])
    return path


def write_rep_sheets(out_dir: Path, summaries: dict) -> list:
    """One point sheet per rep, showing that rep's share of every row."""
    written = []
    rep_dir = Path(out_dir) / "rep_point_sheets"
    for summary in summaries.values():
        records = [
            result_to_row(result, rep_points_override=points)
            for result, _rep, points in summary.rows
        ]
        label = _safe_filename(summary.rep_id or summary.rep_name)
        path = rep_dir / f"point_sheet_{label}.csv"
        write_csv(path, POINT_SHEET_COLUMNS, records)
        written.append(path)
    return written


def write_summary(out_dir: Path, summaries: dict) -> Path:
    path = Path(out_dir) / "commission_summary.csv"
    records = []
    for summary in sorted(
        summaries.values(), key=lambda s: -s.final_points
    ):
        review_count = sum(
            1 for result, _rep, _pts in summary.rows if result.review_needed
        )
        records.append({
            "Rep ID": summary.rep_id,
            "Rep Name": summary.rep_name,
            "Row Points": summary.row_points,
            "Rep-Level Bonus": summary.rep_level_bonus,
            "Gross Points": summary.gross_points,
            "Honorarium Deduction": summary.honorarium_deduction,
            "Final Points": summary.final_points,
            "Rows": len(summary.rows),
            "Rows Needing Review": review_count,
            "Notes": " | ".join(summary.notes),
        })
    write_csv(path, SUMMARY_COLUMNS, records)
    return path


def write_review_queue(out_dir: Path, results: list) -> Path:
    path = Path(out_dir) / "review_queue.csv"
    flagged = [result_to_row(r) for r in results if r.review_needed]
    write_csv(path, POINT_SHEET_COLUMNS, flagged)
    return path
