from datetime import date

from openpyxl import load_workbook

from sales_points.fit_report import rows_from_grid
from sales_points.quarterly import build_quarterly_report, score_quarter

GRID = [
    ["Monthly Fit Report", "", ""],
    ["", "", ""],
    ["PATIENT INFO", "PRO", "REP", "TEAM", "INS", "TYPE", "DATE RX REC'D",
     "PATIENT STATUS", "DOS", "PRODUCT", "INSURANCE STATUS", "DATE DME REC'D",
     "SERIAL NUMBER", "URGENCY / INCOMPLETE NOTES"],
    ["JANE DOE 01-01-80", "DR SMITH", "LOPICCOLO (M1-11-69)", "ROYLE (PITT)", "ONECALL/PO",
     "PA WC", "06-01-26", "(8.1) FIT", "A", "TCT-RT KNEE-30 DAY RX DUAL", "BILLED",
     "06-10-26", "TCT-1234", ""],
    ["JANE DOE 01-01-80", "DR SMITH", "LOPICCOLO (M1-11-69)", "ROYLE (PITT)", "ONECALL/PO",
     "PA WC", "06-01-26", "(8.1) FIT", "A", "MZ-RT KNEE(LT) DUAL", "BILLED",
     "06-10-26", "MZ-9999", ""],
    ["JOHN ROE 02-02-70", "DR JONES", "HOUSE WEST (M1-21-2)", "MICH", "AAA",
     "MI AUTO", "06-03-26", "(8.1) FIT", "A", "TCT-LUMBAR-30 DAY RX", "BILLED",
     "06-12-26", "TCT-5555", ""],
]


def test_raw_columns_are_kept():
    rows = rows_from_grid(GRID)
    assert rows[0].raw["SERIAL NUMBER"] == "TCT-1234"
    assert rows[0].raw["DATE DME REC'D"] == "06-10-26"


def test_quarterly_report_has_all_and_team_tabs(tmp_path):
    import csv
    report = tmp_path / "june.csv"
    with open(report, "w", newline="") as handle:
        csv.writer(handle).writerows(GRID)
    out = build_quarterly_report([("JUNE 2026", report)], tmp_path / "q.xlsx", "Q TEST")
    wb = load_workbook(out)
    assert wb.sheetnames == ["ALL", "MICH", "ROYLE (PITT)"]
    ws = wb["ALL"]
    # summary block: DME total = 300 + 550 (gold pair) + 500
    values = {ws.cell(row=r, column=3).value: ws.cell(row=r, column=5).value for r in range(3, 7)}
    assert values["DME"] == 300 + 550 + 500
    assert values["Total"] == values["DME"]
    header = [c.value for c in ws[8]]
    assert header[0] == "PATIENT NAME / DOB" and header[14] == "POINT TOTAL"
    assert ws.cell(row=9, column=14).value in {"TCT-1234", "MZ-9999"}


def test_score_quarter_marks_split_and_ffw(tmp_path):
    import csv
    grid = [row[:] for row in GRID]
    grid[3][1] = "DR SMITH *"
    grid[3][2] = "LOPICCOLO (M1-11-69) / HOUSE EAST (M1-21-0)"
    report = tmp_path / "m.csv"
    with open(report, "w", newline="") as handle:
        csv.writer(handle).writerows(grid)
    recs = score_quarter([("JUNE 2026", report)])
    first = [r for r in recs if r["cells"][13] == "TCT-1234"][0]
    assert first["ffw"] == "Y"
    assert "Split:" in first["notes"]
    assert first["sort"][0] == date(2026, 6, 10)
