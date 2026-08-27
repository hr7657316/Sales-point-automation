"""The point calculation pipeline.

Follows the nine ordered steps from the cheat sheet's INSTRUCTIONS tab:
product -> insurance -> type -> insurance status -> PRO/ancillary -> exceptions
-> base points -> bonuses -> deductions/splits. Every row carries the rule that
produced it and a plain-English explanation; anything that does not clearly
match a rule is flagged for human review instead of being guessed at.
"""

from __future__ import annotations

from datetime import date

from .models import FitRow, Rep, RepSummary, RowResult
from .parsing import parse_reps
from .rules import RuleBook

NOT_FIT = "NOT_FIT"
BMV_OVERRIDE = "BMV_OVERRIDE"
ANCILLARY_MZ_AUTO_EXCEPTION = "ANCILLARY_MZ_AUTO_EXCEPTION"
NO_RULE_MATCH = "NO_RULE_MATCH"
INSURANCE_NOT_ELIGIBLE = "INSURANCE_NOT_ELIGIBLE"
SUPPLY_ONLY = "SUPPLY_ONLY"
SELF_PAY_ZERO = "SELF_PAY_ZERO"

# Insurance Status values that earn points; anything else earns none at all.
ELIGIBLE_STATUS_MARKERS = ("O/A/B", "OPEN/ACTIVE/BILLABLE", "BILLED",
                           "OPEN/BILLABLE")

# Supplies shipped to an existing patient: no points (Patricia Elbayly,
# April - "reps do not receive points for Electrodes Only or Wrap Only").
SUPPLY_ONLY_MARKERS = ("ELECTRODE", "WRAP ONLY")

SELF_PAY_MARKERS = ("SELF-PAY", "SELF PAY")
SURGICAL_MARKER = "SURGICAL"
OPEN_LITIGATED_MARKER = "NON-SURGICAL OPEN LITIGATED"


def _match_type(row: FitRow) -> str:
    """Text the Type conditions match against.

    The Fit Report keeps the surgical marker in a separate column, so it is
    folded in here rather than being lost.
    """
    if row.surgical or row.surgical_class == "surgical":
        return f"{row.type} {SURGICAL_MARKER}".strip()
    if row.surgical_class == "post-surgical":
        return f"{row.type} POST-SURGICAL".strip()
    # A DOS of A or C marks an open or litigated, non-surgical case - and a
    # surgery outside the 30-day window is paid the same way.
    if (row.dos_code or "").strip().upper() in {"A", "C"} or row.surgical_class == "outside-window":
        return f"{row.type} {OPEN_LITIGATED_MARKER}".strip()
    return row.type


def _is_auto(row: FitRow) -> bool:
    text = f"{row.insurance} {row.type}".lower()
    return "auto" in text or "no-fault" in text or "no fault" in text


def _split_even(total: int, parts: int) -> list:
    """Split points evenly; any odd point goes to the first rep listed."""
    if parts <= 0:
        return []
    base, remainder = divmod(total, parts)
    return [base + (1 if i < remainder else 0) for i in range(parts)]


class PointEngine:
    """Calculates point sheets for a month of Fit Report rows."""

    def __init__(self, rulebook: RuleBook | None = None,
                 rx_history: dict | None = None,
                 awarded_customers: set | None = None,
                 honorariums: dict | None = None,
                 rep_names: dict | None = None):
        self.rules = rulebook or RuleBook.load()
        # rep id -> full name, so rep-facing sheets are not just surnames
        self.rep_names = {k.upper(): v for k, v in (rep_names or {}).items()}
        # customer key -> date of that customer's most recent prior RX
        self.rx_history = {k.upper(): v for k, v in (rx_history or {}).items()}
        # customers that already consumed their one-time new-customer bonus
        self.awarded_customers = {c.upper() for c in (awarded_customers or set())}
        # rep id (or name) -> total honorarium payout in dollars for the month
        self.honorariums = {k.upper(): v for k, v in (honorariums or {}).items()}

    # ------------------------------------------------------------------
    # Step 5 / Step 6: ancillary detection and the critical MZ Auto override
    # ------------------------------------------------------------------
    def _resolve_ancillary(self, row: FitRow) -> tuple:
        markers = self.rules.settings.ancillary_markers
        is_ancillary = any(m and m in (row.pro or "") for m in markers)
        note = ""

        # Critical override, confirmed against the paid July split: a referral
        # with no garment fitted is not processed through the Ancillary
        # Program at all, so the standard rules apply - for work comp rows as
        # well as auto.
        if (
            is_ancillary
            and "mz" in (row.product or "").lower()
            and row.garment_fitted is False
            and (row.garment_unlisted or _is_auto(row))
        ):
            is_ancillary = False
            note = (
                "Ancillary exception applied: MZ with no garment fitted is not "
                "processed through the Ancillary Program, so the standard rule "
                "was used."
            )
        return is_ancillary, note

    # ------------------------------------------------------------------
    # Step 8: row-level bonuses
    # ------------------------------------------------------------------
    def _is_new_customer(self, row: FitRow) -> bool:
        if row.new_customer is not None:
            return row.new_customer
        if "new" in (row.patient_status or "").lower():
            return True
        key = row.customer_key
        if not key:
            return False
        if not self.rx_history:
            # Without an RX history file the 12-month test cannot be evaluated,
            # so the bonus is withheld rather than guessed at.
            return False
        last_rx = self.rx_history.get(key)
        if last_rx is None:
            # Customer has no prior RX on file at all.
            return True
        reference = row.fit_date or row.date_rx_received or date.today()
        return (reference - last_rx).days > 365

    def _double_bonus(self, row: FitRow) -> bool:
        reference = row.fit_date or row.date_rx_received
        if not reference:
            return False
        return reference.month in self.rules.settings.double_bonus_months

    def _new_customer_bonus(self, row: FitRow, result: RowResult) -> int:
        bonus = self.rules.bonus("NEW_CUSTOMER")
        if not bonus or not bonus.applies_to_product(row.product):
            return 0
        if bonus.excludes_ancillary and result.is_ancillary:
            result.explanation += (
                " Ancillary provider, so the standard new-customer bonus does not apply."
            )
            return 0
        if not self._is_new_customer(row):
            return 0
        key = row.customer_key
        if not key or key in self.awarded_customers:
            return 0

        self.awarded_customers.add(key)
        points = bonus.points
        label = "NEW_CUSTOMER"
        if bonus.doubles_in_dec_jan and self._double_bonus(row):
            points *= 2
            label = "NEW_CUSTOMER (doubled - Dec/Jan)"
        result.bonuses_applied.append(f"{label} +{points}")
        return points

    def _gold_pair_bonus(self, row: FitRow, result: RowResult,
                         gold_pair_state: dict) -> int:
        """Award once per patient with both a TCT and an MZ fit this month.

        Validated against seven paid months (Jan-Jul 2026): the pair is simply
        both product families appearing for the same patient in the same
        month's report - MZ ONLY products count as MZ, ancillary rows do not
        count, and no date window is involved.
        """
        bonus = self.rules.bonus("GOLD_PAIR")
        if not bonus:
            return 0
        product = (row.product or "").upper()
        if product.startswith("TCT"):
            family = "TCT"
        elif product.startswith("MZ"):
            family = "MZ"
        else:
            return 0
        if bonus.excludes_ancillary and result.is_ancillary:
            return 0

        patient = (row.patient or "").split("\n")[0].strip().upper()[:40]
        if not patient:
            return 0

        state = gold_pair_state.setdefault(
            patient, {"TCT": False, "MZ": False, "awarded": False}
        )
        state[family] = True
        if state["awarded"] or not (state["TCT"] and state["MZ"]):
            return 0

        state["awarded"] = True
        result.bonuses_applied.append(f"GOLD_PAIR +{bonus.points}")
        return bonus.points

    # ------------------------------------------------------------------
    # Row evaluation
    # ------------------------------------------------------------------
    def evaluate_row(self, row: FitRow, gold_pair_state: dict,
                     period_ref=None) -> RowResult:
        result = RowResult(row=row)

        # Step 1: points exist only for devices actually marked Fit.
        # FIT/INCOMPLETE still earns points when the insurance status is
        # billable (David McClintock, May: FIT/INCOMPLETE + O/A/B paid 500);
        # the status gate below decides. RETURNED and PATIENT DEMO never do.
        fit_values = self.rules.settings.fit_status_values
        fit_text = (row.fit_status or "").strip().lower()
        fit_incomplete = "fit" in fit_text and "incomplete" in fit_text
        if fit_values and fit_text not in fit_values and not fit_incomplete:
            result.rule_used = NOT_FIT
            result.explanation = (
                f"Fit status is '{row.fit_status or 'blank'}', not a Fit Complete "
                "status, so no points were assigned."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        # Insurance Status gate: without O/A/B, Billed or Billed without
        # Auth, the rep earns no points for the row, whatever the product.
        status = (row.insurance_status or "").upper()
        if status and not any(m in status for m in ELIGIBLE_STATUS_MARKERS):
            result.rule_used = INSURANCE_NOT_ELIGIBLE
            result.explanation = (
                f"Insurance Status is '{row.insurance_status}', not O/A/B, "
                "Billed or Billed without Auth, so no points are earned."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        # Supplies for an existing device earn nothing: Electrodes Only,
        # Wrap Only (per Allissa, Patricia Elbayly ruling).
        if any(m in (row.product or "").upper() for m in SUPPLY_ONLY_MARKERS):
            result.rule_used = SUPPLY_ONLY
            result.explanation = (
                f"Product '{row.product}' is a supply-only shipment "
                "(Electrodes Only / Wrap Only), which earns no points."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        # Anything listed as Self Pay is worth 0 points to the rep,
        # regardless of product (per Allissa, Justin Carrick ruling).
        pay_text = f"{row.insurance} {row.type} {row.insurance_status}".upper()
        if any(m in pay_text for m in SELF_PAY_MARKERS):
            result.rule_used = SELF_PAY_ZERO
            result.explanation = (
                "Self-Pay case: worth 0 points to the rep regardless of "
                "product."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        # Step 6 (critical): BMV wins over everything else.
        if row.bmv:
            result.rule_used = BMV_OVERRIDE
            result.explanation = (
                "Below Market Value: negotiated price is lower than the cost of "
                "providing the equipment, so no commission points are awarded."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        # Step 5 + ancillary exception.
        result.is_ancillary, ancillary_note = self._resolve_ancillary(row)
        if ancillary_note:
            result.bonuses_applied.append(ANCILLARY_MZ_AUTO_EXCEPTION)

        # Steps 1-4 + 7: find the rule and read its base points.
        type_text = _match_type(row)
        rule = self.rules.find(
            row.product, row.insurance, type_text, row.insurance_status,
            result.is_ancillary, on=period_ref or row.date_rx_received,
        )
        if rule is None:
            result.rule_used = NO_RULE_MATCH
            result.review_needed = True
            result.explanation = (
                f"No rule matched Product='{row.product}', "
                f"Insurance='{row.insurance}', Type='{row.type}', "
                f"Insurance Status='{row.insurance_status}', "
                f"Ancillary={'Yes' if result.is_ancillary else 'No'}. "
                "Flagged for human review rather than guessing."
            )
            result.rep_allocations = self._allocate(row, 0, result)
            return result

        result.base_points = rule.points_for(row.insurance, type_text)
        result.rule_used = rule.rule_id
        result.explanation = (
            f"{rule.description} ({rule.rule_id}) matched on Product='{row.product}', "
            f"Insurance='{row.insurance}', Type='{type_text}'"
            f"{', Ancillary provider (PRO contains * or +)' if result.is_ancillary else ''}"
            f" -> {result.base_points} base points."
        )
        if ancillary_note:
            result.explanation += " " + ancillary_note

        # Step 8: bonuses, kept separate from the base points.
        result.bonus_points = (
            self._new_customer_bonus(row, result)
            + self._gold_pair_bonus(row, result, gold_pair_state)
        )
        if result.bonuses_applied:
            result.explanation += " Bonuses: " + ", ".join(result.bonuses_applied) + "."

        # Step 9: split accounts - total first, then divide.
        result.rep_allocations = self._allocate(row, result.total_points, result)
        return result

    def _allocate(self, row: FitRow, total: int, result: RowResult) -> list:
        reps = parse_reps(row.rep, self.rules.settings.split_separator)
        for rep in reps:
            full_name = self.rep_names.get((rep.rep_id or "").upper())
            if full_name:
                rep.name = full_name
        if not reps:
            reps = [Rep(name="UNASSIGNED")]
            result.review_needed = True
            result.explanation += " No rep found on this row; flagged for review."

        result.is_split = len(reps) > 1
        shares = _split_even(total, len(reps))
        if result.is_split:
            result.explanation += (
                f" Split account: {total} total points divided between "
                f"{len(reps)} reps ({', '.join(str(r) for r in reps)})."
            )
        return list(zip(reps, shares, strict=True))

    # ------------------------------------------------------------------
    # Month-level processing
    # ------------------------------------------------------------------
    def run(self, rows: list) -> tuple:
        """Evaluate every row, then apply rep-level bonuses and deductions."""
        ordered = sorted(
            rows, key=lambda r: (r.fit_date or date.max, r.row_number)
        )
        gold_pair_state: dict = {}
        # Rates are versioned by commission period, and the whole report is
        # priced by its month - not row by row, since RX dates often fall in
        # the month before the fit. The latest RX date identifies the month.
        rx_dates = [r.date_rx_received for r in ordered if r.date_rx_received]
        period_ref = max(rx_dates) if rx_dates else None
        results = [
            self.evaluate_row(row, gold_pair_state, period_ref)
            for row in ordered
        ]
        summaries = self._summarise(results)
        return results, summaries

    def _summarise(self, results: list) -> dict:
        summaries: dict = {}
        for result in results:
            for rep, points in result.rep_allocations:
                key = (rep.rep_id or rep.name).upper()
                summary = summaries.setdefault(
                    key, RepSummary(rep_id=rep.rep_id, rep_name=rep.name)
                )
                summary.row_points += points
                summary.rows.append((result, rep, points))

        self._apply_five_plus_bonus(summaries)
        self._apply_honorarium_deductions(summaries)
        return summaries

    def _apply_five_plus_bonus(self, summaries: dict) -> None:
        bonus = self.rules.bonus("FIVE_PLUS_NEW_CUSTOMER")
        if not bonus:
            return
        window = self.rules.settings.five_plus_window_days

        for summary in summaries.values():
            qualifying = [
                result
                for result, _rep, _points in summary.rows
                if any(b.startswith("NEW_CUSTOMER") for b in result.bonuses_applied)
                and bonus.applies_to_product(result.row.product)
            ]
            if len(qualifying) < 5:
                continue

            fit_dates = [r.row.fit_date for r in qualifying if r.row.fit_date]
            if not fit_dates:
                continue
            start = min(fit_dates)
            in_window = [d for d in fit_dates if (d - start).days < window]
            if len(in_window) < 5:
                continue

            points = bonus.points
            label = "FIVE_PLUS_NEW_CUSTOMER"
            if bonus.doubles_in_dec_jan and start.month in self.rules.settings.double_bonus_months:
                points *= 2
                label += " (doubled - Dec/Jan)"
            summary.rep_level_bonus += points
            summary.notes.append(
                f"{label} +{points}: {len(in_window)} new-customer Fit Completes "
                f"within {window} calendar days of {start.isoformat()}."
            )

    def _apply_honorarium_deductions(self, summaries: dict) -> None:
        if not self.honorariums:
            return
        rate = self.rules.settings.honorarium_deduction_rate
        per_dollar = self.rules.settings.honorarium_points_per_dollar

        for summary in summaries.values():
            payout = self.honorariums.get((summary.rep_id or "").upper())
            if payout is None:
                payout = self.honorariums.get((summary.rep_name or "").upper())
            if not payout:
                continue
            deduction = round(payout * rate * per_dollar)
            summary.honorarium_deduction += deduction
            summary.notes.append(
                f"Honorarium deduction -{deduction}: {rate:.0%} of a "
                f"${payout:,.2f} honorarium payout."
            )
