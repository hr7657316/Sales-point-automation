"""Command line entry point: ``python -m sales_points``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import PointEngine
from .loaders import (
    load_awarded_customers,
    load_fit_report,
    load_honorariums,
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
                        help="Monthly Fit Report exported as CSV")
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
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    rows = load_fit_report(args.fit_report)
    engine = PointEngine(
        rulebook=RuleBook.load(args.rules_dir),
        rx_history=load_rx_history(args.rx_history),
        awarded_customers=load_awarded_customers(args.awarded_customers),
        honorariums=load_honorariums(args.honorariums),
    )
    results, summaries = engine.run(rows)

    master = write_master_sheet(args.out_dir, results)
    rep_sheets = write_rep_sheets(args.out_dir, summaries)
    summary = write_summary(args.out_dir, summaries)
    review = write_review_queue(args.out_dir, results)

    flagged = sum(1 for r in results if r.review_needed)
    print(f"Rows processed:        {len(results)}")
    print(f"Reps with points:      {len(summaries)}")
    print(f"Rows needing review:   {flagged}")
    print(f"Master point sheet:    {master}")
    print(f"Rep point sheets:      {len(rep_sheets)} in {args.out_dir / 'rep_point_sheets'}")
    print(f"Commission summary:    {summary}")
    print(f"Review queue:          {review}")
    if flagged:
        print("\nReview the flagged rows before sending point sheets to RSMs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
