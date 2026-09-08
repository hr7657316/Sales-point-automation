"""Command line entry point: ``python -m sales_points``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import PointEngine
from .fit_report import load_fit_report_workbook
from .loaders import (
    load_awarded_customers,
    load_fit_report,
    load_honorariums,
    load_rep_roster,
    load_rx_history,
)
from .report import (
    write_master_sheet,
    write_rep_sheets,
    write_review_queue,
    write_summary,
)
from .rules import RuleBook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sales_points",
        description=(
            "Calculate monthly sales commission points from a Fit Report export. "
            "Reads local CSV files and writes local CSV files only."
        ),
    )
    parser.add_argument("fit_report", type=Path,
                        help="Monthly Fit Report (.xlsx export, or CSV)")
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("output"),
                        help="Directory for the generated point sheets")
    parser.add_argument("--rules-dir", type=Path, default=None,
                        help="Directory holding the rule CSVs (default: ./rules)")
    parser.add_argument("--rx-history", type=Path, default=None,
                        help="CSV of customer -> most recent prior RX date")
    parser.add_argument("--awarded-customers", type=Path, default=None,
                        help="CSV of customers that already used their new-customer bonus")
    parser.add_argument("--honorariums", type=Path, default=None,
                        help="CSV of rep honorarium payouts for the month")
    parser.add_argument("--rep-roster", type=Path, default=None,
                        help="CSV mapping Rep ID to the rep's full name")
    parser.add_argument("--month", default=None,
                        help='Month label for the workbook, e.g. "AUGUST 2026"')
    return parser


def _load_csv(path: Path) -> list:
    """A CSV is either a real Fit Report export (banner rows, PATIENT STATUS /
    PRODUCT header) or the tidy sample layout; detect which."""
    import csv

    from .fit_report import find_header_row, rows_from_grid

    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        grid = list(csv.reader(handle))
    try:
        find_header_row(grid)
    except ValueError:
        return load_fit_report(path)
    return rows_from_grid(grid)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # .xlsx exports go through the Fit Report reader, which knows about the
    # banner rows, repeated headers and the URGENCY surgical marker.
    if args.fit_report.suffix.lower() in {".xlsx", ".xlsm"}:
        rows = load_fit_report_workbook(args.fit_report)
    else:
        rows = _load_csv(args.fit_report)
    engine = PointEngine(
        rulebook=RuleBook.load(args.rules_dir),
        rx_history=load_rx_history(args.rx_history),
        awarded_customers=load_awarded_customers(args.awarded_customers),
        honorariums=load_honorariums(args.honorariums),
        rep_names=load_rep_roster(args.rep_roster),
    )
    results, summaries = engine.run(rows)

    master = write_master_sheet(args.out_dir, results)
    rep_sheets = write_rep_sheets(args.out_dir, summaries)
    summary = write_summary(args.out_dir, summaries)
    review = write_review_queue(args.out_dir, results)

    # The Allissa-style workbook: one tab per rep, plus audit trail.
    workbook_path = None
    try:
        from .workbook import build_workbook
        label = args.month or args.fit_report.stem.upper()
        workbook_path = build_workbook(
            results, label, args.out_dir / f"{label.replace(' ', '_')}_Point_Sheets_ENGINE.xlsx",
            comp_plans_path=str((args.rules_dir or Path("rules")) / "comp_plans.csv"),
        )
    except ImportError:
        pass  # openpyxl missing: CSV outputs above are still written

    flagged = sum(1 for r in results if r.review_needed)
    print(f"Rows processed:        {len(results)}")
    print(f"Reps with points:      {len(summaries)}")
    print(f"Rows needing review:   {flagged}")
    print(f"Master point sheet:    {master}")
    print(f"Rep point sheets:      {len(rep_sheets)} in {args.out_dir / 'rep_point_sheets'}")
    print(f"Commission summary:    {summary}")
    print(f"Review queue:          {review}")
    if workbook_path:
        print(f"Point sheet workbook:  {workbook_path}")
    if flagged:
        print("\nReview the flagged rows before sending point sheets to RSMs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
