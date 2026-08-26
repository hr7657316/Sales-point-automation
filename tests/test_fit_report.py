"""Tests for reading the real Monthly Fit Report layout."""

import datetime

import pytest

from sales_points.engine import PointEngine
from sales_points.fit_report import (
    build_column_index,
    find_header_row,
    garment_fitted,
    is_fit,
    is_open_or_litigated,
    rows_from_grid,
    surgical_kind,
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
        type_="PA WC", status="(8.1) FIT", dos="A",
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
    # Without the marker, the DOS code decides. Both rows here carry DOS 'A',
    # so the unmarked one is the open or litigated case at 300.
    assert engine.evaluate_row(plain, {}).base_points == 300


def test_tct_with_neither_marker_nor_dos_code_is_flagged():
    """With no surgical marker and no DOS code there is nothing to go on."""
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(dos="", urgency="IMMEDIATE")))[0]
    assert engine.evaluate_row(parsed, {}).review_needed is True


def test_non_fit_rows_score_nothing():
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(status="RETURNED", urgency="SURGICAL")))
    assert engine.evaluate_row(parsed[0], {}).total_points == 0


# --- DOS is a code, not a date --------------------------------------------


@pytest.mark.parametrize(
    "dos,expected",
    [("A", True), ("C", True), ("a", True), ("03-16-26", False), ("", False)],
)
def test_open_or_litigated_read_from_dos_code(dos, expected):
    assert is_open_or_litigated(dos) is expected


def test_dos_code_is_not_treated_as_a_fit_date():
    """DOS holds 'A' or 'C' far more often than a date, so it is not a date."""
    parsed = rows_from_grid(grid(row(dos="A")))[0]
    assert parsed.dos_code == "A"
    assert parsed.fit_date is None


def test_tct_with_dos_code_a_scores_the_open_litigated_rate():
    """Confirmed against a paid rep sheet: 15 such rows were paid at 300."""
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(dos="A", urgency="")))[0]
    result = engine.evaluate_row(parsed, {})
    assert result.rule_used == "TCT_NONSURG_WC_AUTO_LITIGATED"
    assert result.base_points == 300


def test_ancillary_tct_with_dos_code_a_scores_200():
    """Confirmed against a paid rep sheet: 6 such rows were paid at 200."""
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(pro="THOMAS MD *", dos="A")))[0]
    result = engine.evaluate_row(parsed, {})
    assert result.is_ancillary is True
    assert result.base_points == 200


def test_surgical_marker_still_beats_the_dos_code():
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(dos="A", urgency="SURGICAL")))[0]
    assert engine.evaluate_row(parsed, {}).base_points == 700


# --- garment read from the product description -----------------------------

@pytest.mark.parametrize(
    "product,expected",
    [
        ("MZ ONLY (GARMENT NOT LISTED ON RX) (LT)", False),
        ("MZ ONLY (GARMENT NON-ELIGIBLE)", False),
        ("MZ-RT KNEE (LT) DUAL", None),
    ],
)
def test_garment_read_from_product(product, expected):
    assert garment_fitted(product) is expected


def test_ancillary_mz_auto_with_no_garment_uses_the_standard_250():
    """Confirmed against a paid rep sheet: 3 such rows were paid at 250."""
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(
        pro="HOLMBERG DO *", type_="PA AUTO",
        product="MZ ONLY (GARMENT NOT LISTED ON RX) (LT) DUAL",
    )))[0]
    result = engine.evaluate_row(parsed, {})
    assert result.is_ancillary is False
    assert result.base_points == 250


# --- DOS is the Date Of Surgery -------------------------------------------

FIT = datetime.date(2026, 3, 15)


@pytest.mark.parametrize(
    "urgency,dos,fit,expected",
    [
        ("SURGICAL", "A", None, "surgical"),          # explicit marker wins
        ("", "03-20-26", FIT, "surgical"),            # surgery 5 days after fit
        ("", "04-14-26", FIT, "surgical"),            # 30 days after: still in
        ("", "03-01-26", FIT, "surgical"),            # fit 14 days post-op
        ("", "01-10-26", FIT, "outside-window"),      # surgery too old
        ("", "05-01-26", FIT, "outside-window"),      # surgery too far ahead
        ("", "03-20-26", None, "surgical"),           # no fit date: fall back
        ("", "A", FIT, ""),                           # no surgery at all
        ("IMMEDIATE", "C", FIT, ""),
    ],
)
def test_surgical_kind_from_surgery_vs_fit_date(urgency, dos, fit, expected):
    assert surgical_kind(urgency, dos, fit) == expected


def test_tct_with_a_surgery_date_scores_the_surgical_rate():
    """A surgery date near the fit date is the surgical case at 700."""
    engine = PointEngine()
    parsed = rows_from_grid(grid(row(dos="04-10-26", urgency="")))[0]
    result = engine.evaluate_row(parsed, {})
    assert result.rule_used == "TCT_WC_SURGICAL"
    assert result.base_points == 700
