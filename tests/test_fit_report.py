"""Tests for reading the real Monthly Fit Report layout."""

import pytest

from sales_points.engine import PointEngine
from sales_points.fit_report import (
    build_column_index,
    find_header_row,
    is_fit,
    is_surgical,
    rows_from_grid,
)

# Mirrors the real export: banner rows on top, repeated PRO/REP/TYPE headers,
# fit state inside PATIENT STATUS, surgical marker in URGENCY.
HEADER = [
    "", "", "AFFECTO", "", "PRO / REP / TEAM", "PRO", "REP", "TEAM", "INS",
    "TYPE", "DATE RX REC'D", "PATIENT STATUS", "DOS", "PRODUCT",
    "INSURANCE STATUS", "PATIENT INFO", "URGENCY / INCOMPLETE NOTES",
    "PRO", "REP", "TYPE",
]


def grid(*data_rows):
    banner = [[""] * len(HEADER) for _ in range(3)]
    return banner + [HEADER] + [list(r) for r in data_rows]


def row(pro="SMITH MD", rep="LOPICCOLO (M1-11-69)", ins="SEDGWICK",
        type_="PA WC", status="(8.1) FIT", dos="03-14-26",
        product="TCT-RT KNEE-30 DAY RX DUAL", ins_status="BILLED",
        patient="JANE DOE 01-01-70", urgency=""):
    cells = [""] * len(HEADER)
    for index, value in {
        5: pro, 6: rep, 7: "ROYLE (PA)", 8: ins, 9: type_, 10: "03-01-26",
        11: status, 12: dos, 13: product, 14: ins_status, 15: patient,
        16: urgency,
    }.items():
        cells[index] = value
    return cells


def test_header_row_is_found_beneath_the_banner_rows():
    assert find_header_row(grid(row())) == 3


def test_missing_header_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="header row"):
        find_header_row([["a", "b"], ["c", "d"]])


def test_duplicate_headers_resolve_to_the_first_occurrence():
    columns = build_column_index(HEADER)
    assert columns["pro"] == 5
    assert columns["rep"] == 6
    assert columns["type"] == 9


@pytest.mark.parametrize(
    "status,expected",
    [
        ("(8.1) FIT", True),
        ("FIT", True),
        ("FIT/INCOMPLETE", False),
        ("RETURNED", False),
        ("PATIENT DEMO", False),
        ("", False),
    ],
)
def test_fit_state_read_from_patient_status(status, expected):
    assert is_fit(status) is expected


@pytest.mark.parametrize(
    "urgency,expected",
    [("SURGICAL", True), ("IMMEDIATE", False), ("", False), ("surgical", True)],
)
def test_surgical_marker_read_from_urgency_column(urgency, expected):
    assert is_surgical(urgency) is expected


def test_row_fields_map_across_correctly():
    parsed = rows_from_grid(grid(row(urgency="SURGICAL")))
    assert len(parsed) == 1
    fit = parsed[0]
    assert fit.pro == "SMITH MD"
    assert fit.rep == "LOPICCOLO (M1-11-69)"
    assert fit.insurance == "SEDGWICK"
    assert fit.type == "PA WC"
    assert fit.product.startswith("TCT")
    assert fit.fit_status == "FIT"
    assert fit.surgical is True
    # The provider doubles as the customer key for new-customer bonuses.
    assert fit.doc == "SMITH MD"


def test_spacer_rows_are_skipped():
    parsed = rows_from_grid(grid(row(), [""] * len(HEADER), row()))
    assert len(parsed) == 2


def test_surgical_marker_reaches_the_point_rules():
    """A TCT PA WC row scores 700 only when URGENCY says SURGICAL."""
    engine = PointEngine()
    surgical, plain = rows_from_grid(
        grid(row(urgency="SURGICAL"), row(urgency="IMMEDIATE"))
    )
    assert engine.evaluate_row(surgical, {}).base_points == 700
    # Without the marker the surgical/non-surgical split is unknown, so the
    # row is flagged rather than scored.
    assert engine.evaluate_row(plain, {}).review_needed is True


def test_non_fit_rows_score_nothing():
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(status="RETURNED", urgency="SURGICAL")))
    assert engine.evaluate_row(parsed[0], {}).total_points == 0
