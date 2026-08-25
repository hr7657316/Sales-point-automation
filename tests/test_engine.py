"""Tests asserting the engine reproduces the cheat sheet's own worked examples."""

from datetime import date

import pytest

from sales_points.engine import (
    BMV_OVERRIDE,
    NO_RULE_MATCH,
    NOT_FIT,
    PointEngine,
)
from sales_points.models import FitRow
from sales_points.parsing import parse_reps
from sales_points.rules import RuleBook


def make_row(**kwargs) -> FitRow:
    defaults = {
        "patient": "P-1",
        "pro": "SMITH ORTHO",
        "rep": "LOPICCOLO (M1-11-69)",
        "team": "East",
        "insurance": "Work Comp",
        "type": "Surgical",
        "fit_date": date(2026, 8, 5),
        "date_rx_received": date(2026, 3, 1),
        "doc": "DR SMITH",
        "product": "TCT",
        "insurance_status": "Eligible",
        "fit_status": "FIT",
    }
    defaults.update(kwargs)
    return FitRow(**defaults)


@pytest.fixture
def engine():
    return PointEngine(rulebook=RuleBook.load())


def evaluate(engine, row):
    return engine.evaluate_row(row, {})


# --- POINT RULES tab -------------------------------------------------------

@pytest.mark.parametrize(
    "product,insurance,type_,expected,rule_id",
    [
        ("TCT", "Work Comp", "Surgical", 700, "TCT_WC_SURGICAL"),
        ("TCT", "Work Comp", "Post-Surgical", 500, "TCT_WC_POST_SURGICAL"),
        ("TCT", "Work Comp", "Non-Surgical", 100, "TCT_WC_NONSURG_TRICARE_USDL_COLD"),
        ("TCT", "Tricare", "Non-Surgical", 100, "TCT_WC_NONSURG_TRICARE_USDL_COLD"),
        ("TCT", "Work Comp", "Litigated", 300, "TCT_NONSURG_WC_AUTO_LITIGATED"),
        ("TCT", "Michigan Auto", "Non-Litigated", 500, "TCT_MICH_AUTO_NON_LITIGATED"),
        ("MZ", "Work Comp", "", 500, "MZ_WORK_COMP"),
        ("MZ", "Medicare", "", 50, "MZ_GOV_AND_COMMERCIAL"),
        ("MZ", "Commercial", "", 50, "MZ_GOV_AND_COMMERCIAL"),
        ("MZ", "PA Auto", "", 250, "MZ_PA_MI_FL_AUTO"),
        ("MZ", "FL Auto", "", 250, "MZ_PA_MI_FL_AUTO"),
        ("MZ", "OH Work Comp", "13 Month Rental", 50, "MZ_OH_WC_RENTAL_TRIAL"),
        ("SportZ", "", "", 0, "SPORTZ"),
        ("Bone Stim", "Work Comp", "", 500, "BONE_STIM_OR_LASER"),
        ("Back Brace", "Medicare", "", 250, "BACK_BRACE_WC_MEDICARE"),
    ],
)
def test_standard_base_points(engine, product, insurance, type_, expected, rule_id):
    result = evaluate(engine, make_row(product=product, insurance=insurance,
                                       type=type_))
    assert result.rule_used == rule_id
    assert result.base_points == expected
    assert result.review_needed is False


def test_more_specific_rule_wins_over_general_one(engine):
    """MZ PA/MI/FL Auto (250) must beat the generic MZ Auto row (50)."""
    result = evaluate(engine, make_row(product="MZ", insurance="MI Auto", type=""))
    assert result.rule_used == "MZ_PA_MI_FL_AUTO"
    assert result.base_points == 250


def test_ohio_wc_rental_beats_plain_mz_work_comp(engine):
    result = evaluate(engine, make_row(product="MZ", insurance="OH Work Comp",
                                       type="Trial"))
    assert result.base_points == 50


# --- Ancillary (PRO contains '*') -----------------------------------------

@pytest.mark.parametrize(
    "product,insurance,type_,expected",
    [
        # Rates confirmed against a paid rep sheet: every ancillary line is
        # 200 for work comp and 100 for auto. The cheat sheet's 300/200/100
        # with 0 for auto did not match what was actually paid.
        ("TCT", "Work Comp", "Surgical", 200),
        ("TCT", "Auto", "Surgical", 100),
        ("TCT", "Work Comp", "Non-Surgical", 200),
        ("TCT", "Auto", "Non-Surgical", 100),
        ("TCT", "Work Comp", "Cold Therapy", 200),
        ("MZ", "Work Comp", "", 200),
    ],
)
def test_ancillary_points(engine, product, insurance, type_, expected):
    result = evaluate(engine, make_row(pro="*ANCILLARY GRP", product=product,
                                       insurance=insurance, type=type_))
    assert result.is_ancillary is True
    assert result.base_points == expected


def test_ancillary_mz_auto_without_garment_uses_standard_rule(engine):
    """Critical override from the BONUSES & EXCEPTIONS tab."""
    result = evaluate(engine, make_row(pro="*ANCILLARY GRP", product="MZ",
                                       insurance="PA Auto", type="Auto",
                                       garment_fitted=False))
    assert result.is_ancillary is False
    assert result.base_points == 250
    assert "Ancillary exception applied" in result.explanation


def test_ancillary_mz_auto_with_garment_stays_ancillary(engine):
    result = evaluate(engine, make_row(pro="*ANCILLARY GRP", product="MZ",
                                       insurance="PA Auto", type="Auto",
                                       garment_fitted=True))
    assert result.is_ancillary is True


# --- Overrides -------------------------------------------------------------

def test_bmv_awards_no_points(engine):
    result = evaluate(engine, make_row(bmv=True))
    assert result.rule_used == BMV_OVERRIDE
    assert result.total_points == 0


def test_row_not_marked_fit_earns_nothing(engine):
    result = evaluate(engine, make_row(fit_status="In Transit"))
    assert result.rule_used == NOT_FIT
    assert result.total_points == 0
    assert result.review_needed is False


def test_unmatched_row_is_flagged_not_guessed(engine):
    result = evaluate(engine, make_row(product="Widget", insurance="Blue Sky",
                                       type="Unknown"))
    assert result.rule_used == NO_RULE_MATCH
    assert result.review_needed is True
    assert result.total_points == 0


# --- Bonuses ---------------------------------------------------------------

def test_new_customer_bonus_awarded_once_per_customer():
    engine = PointEngine(rx_history={"DR NEW": None})
    first = evaluate(engine, make_row(doc="DR NEW", patient="P-1"))
    second = evaluate(engine, make_row(doc="DR NEW", patient="P-2"))
    assert first.bonus_points == 500
    assert second.bonus_points == 0


def test_new_customer_bonus_withheld_when_rx_within_12_months():
    engine = PointEngine(rx_history={"DR SMITH": date(2026, 7, 15)})
    result = evaluate(engine, make_row(doc="DR SMITH"))
    assert result.bonus_points == 0


def test_new_customer_bonus_when_last_rx_over_12_months_ago():
    engine = PointEngine(rx_history={"DR OLD": date(2024, 1, 10)})
    result = evaluate(engine, make_row(doc="DR OLD"))
    assert result.bonus_points == 500


def test_new_customer_bonus_doubled_in_december():
    engine = PointEngine(rx_history={"DR NEW": None})
    result = evaluate(engine, make_row(doc="DR NEW", fit_date=date(2026, 12, 3)))
    assert result.bonus_points == 1000


def test_ancillary_provider_gets_no_new_customer_bonus():
    engine = PointEngine(rx_history={"DR NEW": None})
    result = evaluate(engine, make_row(pro="*ANCILLARY GRP", doc="DR NEW",
                                       type="Non-Surgical"))
    assert result.bonus_points == 0
    assert "does not apply" in result.explanation


def test_new_customer_bonus_withheld_without_rx_history():
    """Without history the 12-month test cannot be evaluated, so no bonus."""
    engine = PointEngine()
    result = evaluate(engine, make_row(doc="DR UNKNOWN"))
    assert result.bonus_points == 0


def test_gold_pair_awarded_when_tct_and_mz_appear_in_the_same_month(engine):
    """Validated on seven paid months: the pair is same-month, no date window."""
    state = {}
    tct = engine.evaluate_row(make_row(product="TCT"), state)
    mz = engine.evaluate_row(make_row(product="MZ", type=""), state)
    assert tct.bonus_points == 0
    assert mz.bonus_points == 50


def test_mz_only_products_count_toward_a_gold_pair(engine):
    state = {}
    engine.evaluate_row(make_row(product="TCT"), state)
    mz = engine.evaluate_row(
        make_row(product="MZ ONLY (GARMENT NOT LISTED ON RX) (LT)",
                 insurance="PA Auto", type="PA AUTO"), state
    )
    assert any(b.startswith("GOLD_PAIR") for b in mz.bonuses_applied)


def test_gold_pair_awarded_once_per_patient(engine):
    state = {}
    engine.evaluate_row(make_row(product="TCT"), state)
    first = engine.evaluate_row(make_row(product="MZ", type=""), state)
    second = engine.evaluate_row(make_row(product="MZ", type=""), state)
    assert first.bonus_points == 50
    assert second.bonus_points == 0


def test_gold_pair_needs_both_families(engine):
    state = {}
    a = engine.evaluate_row(make_row(product="MZ", type=""), state)
    b = engine.evaluate_row(make_row(product="MZ", type=""), state)
    assert a.bonus_points == 0 and b.bonus_points == 0


def test_gold_pair_excluded_for_ancillary(engine):
    state = {}
    engine.evaluate_row(
        make_row(pro="*ANC", product="TCT", type="Non-Surgical"), state
    )
    mz = engine.evaluate_row(make_row(pro="*ANC", product="MZ", type=""), state)
    assert mz.bonus_points == 0


def test_five_plus_new_customer_bonus():
    engine = PointEngine(rx_history={f"DR NEW{i}": None for i in range(6)})
    rows = [
        make_row(patient=f"P-{i}", doc=f"DR NEW{i}", fit_date=date(2026, 8, i + 1))
        for i in range(5)
    ]
    _results, summaries = engine.run(rows)
    summary = summaries["M1-11-69"]
    assert summary.rep_level_bonus == 1000
    assert any("FIVE_PLUS" in note for note in summary.notes)


def test_five_plus_bonus_not_awarded_for_four_new_customers():
    engine = PointEngine(rx_history={f"DR NEW{i}": None for i in range(6)})
    rows = [
        make_row(patient=f"P-{i}", doc=f"DR NEW{i}", fit_date=date(2026, 8, i + 1))
        for i in range(4)
    ]
    _results, summaries = engine.run(rows)
    assert summaries["M1-11-69"].rep_level_bonus == 0


# --- Splits ----------------------------------------------------------------

def test_split_divides_total_after_points_are_calculated(engine):
    """Cheat sheet example: MZ Auto = 250 total, two reps = 125 each."""
    result = evaluate(engine, make_row(
        product="MZ", insurance="MI Auto", type="",
        rep="LOPICCOLO (M1-11-69) / HOUSE EAST (M1-21-0)",
    ))
    assert result.is_split is True
    assert result.total_points == 250
    assert [points for _rep, points in result.rep_allocations] == [125, 125]


def test_single_rep_is_not_split(engine):
    result = evaluate(engine, make_row())
    assert result.is_split is False
    assert result.rep_allocations[0][1] == 700


def test_odd_split_gives_the_extra_point_to_the_first_rep(engine):
    result = evaluate(engine, make_row(
        product="TCT", insurance="Work Comp", type="Surgical",
        rep="A (M1-1) / B (M1-2) / C (M1-3)",
    ))
    assert [points for _rep, points in result.rep_allocations] == [234, 233, 233]
    assert sum(points for _rep, points in result.rep_allocations) == 700


def test_parse_reps_reads_names_and_ids():
    reps = parse_reps("LOPICCOLO (M1-11-69) / HOUSE EAST (M1-21-0)")
    assert [(r.name, r.rep_id) for r in reps] == [
        ("LOPICCOLO", "M1-11-69"),
        ("HOUSE EAST", "M1-21-0"),
    ]


def test_row_without_a_rep_is_flagged(engine):
    result = evaluate(engine, make_row(rep=""))
    assert result.review_needed is True


# --- Honorarium ------------------------------------------------------------

def test_honorarium_deducts_half_the_payout():
    engine = PointEngine(honorariums={"M1-11-69": 1000.0})
    _results, summaries = engine.run([make_row()])
    summary = summaries["M1-11-69"]
    assert summary.gross_points == 700
    assert summary.honorarium_deduction == 500
    assert summary.final_points == 200


def test_honorarium_matched_by_rep_name_when_id_is_absent():
    engine = PointEngine(honorariums={"LOPICCOLO": 400.0})
    _results, summaries = engine.run([make_row()])
    assert summaries["M1-11-69"].honorarium_deduction == 200


# --- Keyword matching guards ----------------------------------------------

def test_non_litigated_does_not_match_the_litigated_rule(engine):
    """'Non-Litigated' contains 'litigated'; it must not match the litigated rule."""
    result = evaluate(engine, make_row(product="TCT", insurance="Michigan Auto",
                                       type="Non-Litigated"))
    assert result.rule_used == "TCT_MICH_AUTO_NON_LITIGATED"
    assert result.base_points == 500


def test_non_surgical_does_not_match_the_surgical_rule(engine):
    result = evaluate(engine, make_row(product="TCT", insurance="Work Comp",
                                       type="Non-Surgical"))
    assert result.rule_used == "TCT_WC_NONSURG_TRICARE_USDL_COLD"
    assert result.base_points == 100


def test_post_surgical_still_reads_as_surgical_family(engine):
    result = evaluate(engine, make_row(product="TCT", insurance="Work Comp",
                                       type="Post-Surgical"))
    assert result.rule_used == "TCT_WC_POST_SURGICAL"
    assert result.base_points == 500


# --- Rep roster ------------------------------------------------------------

def test_full_name_used_when_the_roster_supplies_one():
    """The Fit Report holds only surnames, so full names come from a roster."""
    engine = PointEngine(rep_names={"M1-11-69": "Maria LoPiccolo"})
    result = evaluate(engine, make_row())
    rep, _points = result.rep_allocations[0]
    assert rep.name == "Maria LoPiccolo"
    assert rep.rep_id == "M1-11-69"


def test_surname_kept_when_the_rep_is_not_in_the_roster():
    engine = PointEngine(rep_names={"M1-99-99": "Someone Else"})
    result = evaluate(engine, make_row())
    assert result.rep_allocations[0][0].name == "LOPICCOLO"


def test_roster_resolves_both_sides_of_a_split():
    engine = PointEngine(rep_names={"M1-1": "Ada Lovelace", "M1-2": "Grace Hopper"})
    result = evaluate(engine, make_row(rep="A (M1-1) / B (M1-2)"))
    assert [rep.name for rep, _pts in result.rep_allocations] == [
        "Ada Lovelace", "Grace Hopper",
    ]


def test_roster_lookup_is_case_insensitive_on_the_id():
    engine = PointEngine(rep_names={"m1-11-69": "Maria LoPiccolo"})
    result = evaluate(engine, make_row())
    assert result.rep_allocations[0][0].name == "Maria LoPiccolo"
