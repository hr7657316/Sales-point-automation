"""Loading and matching of the commission rule tables.

The rule tables are plain CSV so they can be maintained in Google Sheets and
exported without touching any code. Nothing here writes back to a spreadsheet.
"""

from __future__ import annotations

import csv
import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

AUTO_KEYWORDS = ("auto", "no-fault", "no fault")


def _split_list(value: str) -> list:
    return [part.strip().lower() for part in (value or "").split("|") if part.strip()]


# "Non-Litigated" contains "litigated" and "Non-Surgical" contains "surgical",
# so a plain substring test silently matches the opposite scenario. A keyword is
# only treated as present when it is not negated by a preceding "non"/"not".
_NEGATION_PREFIX = re.compile(r"(?:non|not)[\s\-_]*$")


def _contains_any(haystack: str, needles: list) -> bool:
    text = (haystack or "").lower()
    for needle in needles:
        if not needle:
            continue
        # A needle that is itself negated ("non-surgical") needs no guard.
        guarded = not needle.startswith(("non", "not"))
        start = 0
        while True:
            index = text.find(needle, start)
            if index == -1:
                break
            if not guarded or not _NEGATION_PREFIX.search(text[:index]):
                return True
            start = index + 1
    return False


@dataclass
class PointRule:
    """One row of the POINT RULES tab."""

    rule_id: str
    description: str
    product_any: list
    ancillary: bool
    insurance_any: list
    type_any: list
    type_none: list
    insurance_status_any: list
    base_points_wc: int
    base_points_auto: int
    priority: int
    source: str = ""
    effective_from: datetime.date | None = None
    effective_to: datetime.date | None = None

    def applies_on(self, when) -> bool:
        """Rates change between commission periods; blank bounds mean always.

        A rule with bounds cannot be evaluated without a date, so it does not
        apply - the row is then flagged rather than priced from the wrong
        period.
        """
        if self.effective_from is None and self.effective_to is None:
            return True
        if when is None:
            return False
        if self.effective_from and when < self.effective_from:
            return False
        return not (self.effective_to and when > self.effective_to)

    def matches(self, product: str, insurance: str, type_: str,
                insurance_status: str, is_ancillary: bool) -> bool:
        """A rule matches only when every populated condition is satisfied.

        An empty condition means "any value", per the cheat sheet's own
        convention of leaving the clue columns blank.
        """
        if self.ancillary != is_ancillary:
            return False
        if self.product_any and not _contains_any(product, self.product_any):
            return False
        # Insurance clues appear in either the Insurance Company or Type column.
        if self.insurance_any and not (
            _contains_any(insurance, self.insurance_any)
            or _contains_any(type_, self.insurance_any)
        ):
            return False
        if self.type_any and not (
            _contains_any(type_, self.type_any) or _contains_any(product, self.type_any)
        ):
            return False
        if self.type_none and _contains_any(type_, self.type_none):
            return False
        return not (
            self.insurance_status_any
            and not _contains_any(insurance_status, self.insurance_status_any)
        )

    def points_for(self, insurance: str, type_: str) -> int:
        """Ancillary rules pay different points for Work Comp vs Auto."""
        combined = f"{insurance} {type_}"
        if _contains_any(combined, list(AUTO_KEYWORDS)):
            return self.base_points_auto
        return self.base_points_wc


@dataclass
class BonusRule:
    """One row of the BONUSES & EXCEPTIONS tab."""

    bonus_id: str
    description: str
    points: int
    applies_to_products: list
    requires_new_customer: bool
    excludes_ancillary: bool
    doubles_in_dec_jan: bool
    scope: str
    source: str = ""

    def applies_to_product(self, product: str) -> bool:
        if not self.applies_to_products:
            return True
        return _contains_any(product, self.applies_to_products)


@dataclass
class Settings:
    """Tunable values from the settings tab."""

    fit_status_values: list = field(
        default_factory=lambda: ["fit", "fit complete", "fitted"]
    )
    ancillary_marker: str = "*"
    honorarium_deduction_rate: float = 0.5
    honorarium_points_per_dollar: float = 1.0
    five_plus_window_days: int = 30
    gold_pair_window_days: int = 30
    double_bonus_months: list = field(default_factory=lambda: [12, 1])
    split_separator: str = "/"


def _as_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"yes", "y", "true", "1"}


def _as_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    return datetime.datetime.strptime(text, "%Y-%m-%d").date()


def _as_int(value: str, default: int = 0) -> int:
    text = (value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


class RuleBook:
    """The full set of rules the engine evaluates against."""

    def __init__(self, point_rules: list, bonuses: list, settings: Settings):
        # Highest priority first so the most specific rule wins deterministically.
        self.point_rules = sorted(point_rules, key=lambda r: -r.priority)
        self.bonuses = bonuses
        self.settings = settings

    @classmethod
    def load(cls, rules_dir: Path | None = None) -> RuleBook:
        rules_dir = Path(rules_dir) if rules_dir else DEFAULT_RULES_DIR
        return cls(
            point_rules=cls._load_point_rules(rules_dir / "point_rules.csv"),
            bonuses=cls._load_bonuses(rules_dir / "bonuses.csv"),
            settings=cls._load_settings(rules_dir / "settings.csv"),
        )

    @staticmethod
    def _load_point_rules(path: Path) -> list:
        rules = []
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if not (row.get("rule_id") or "").strip():
                    continue
                rules.append(
                    PointRule(
                        rule_id=row["rule_id"].strip(),
                        description=row.get("description", "").strip(),
                        product_any=_split_list(row.get("product_any", "")),
                        ancillary=_as_bool(row.get("ancillary", "")),
                        insurance_any=_split_list(row.get("insurance_any", "")),
                        type_any=_split_list(row.get("type_any", "")),
                        type_none=_split_list(row.get("type_none", "")),
                        insurance_status_any=_split_list(
                            row.get("insurance_status_any", "")
                        ),
                        base_points_wc=_as_int(row.get("base_points_wc")),
                        base_points_auto=_as_int(row.get("base_points_auto")),
                        priority=_as_int(row.get("priority"), 50),
                        source=row.get("source", "").strip(),
                        effective_from=_as_date(row.get("effective_from", "")),
                        effective_to=_as_date(row.get("effective_to", "")),
                    )
                )
        return rules

    @staticmethod
    def _load_bonuses(path: Path) -> list:
        bonuses = []
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if not (row.get("bonus_id") or "").strip():
                    continue
                bonuses.append(
                    BonusRule(
                        bonus_id=row["bonus_id"].strip(),
                        description=row.get("description", "").strip(),
                        points=_as_int(row.get("points")),
                        applies_to_products=_split_list(
                            row.get("applies_to_products", "")
                        ),
                        requires_new_customer=_as_bool(
                            row.get("requires_new_customer", "")
                        ),
                        excludes_ancillary=_as_bool(row.get("excludes_ancillary", "")),
                        doubles_in_dec_jan=_as_bool(row.get("doubles_in_dec_jan", "")),
                        scope=row.get("scope", "").strip(),
                        source=row.get("source", "").strip(),
                    )
                )
        return bonuses

    @staticmethod
    def _load_settings(path: Path) -> Settings:
        raw = {}
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                key = (row.get("setting") or "").strip()
                if key:
                    raw[key] = (row.get("value") or "").strip()

        settings = Settings()
        if "fit_status_values" in raw:
            settings.fit_status_values = _split_list(raw["fit_status_values"])
        if "ancillary_marker" in raw:
            settings.ancillary_marker = raw["ancillary_marker"]
        if "honorarium_deduction_rate" in raw:
            settings.honorarium_deduction_rate = float(raw["honorarium_deduction_rate"])
        if "honorarium_points_per_dollar" in raw:
            settings.honorarium_points_per_dollar = float(
                raw["honorarium_points_per_dollar"]
            )
        if "five_plus_window_days" in raw:
            settings.five_plus_window_days = _as_int(raw["five_plus_window_days"], 30)
        if "gold_pair_window_days" in raw:
            settings.gold_pair_window_days = _as_int(raw["gold_pair_window_days"], 30)
        if "double_bonus_months" in raw:
            settings.double_bonus_months = [
                _as_int(m) for m in raw["double_bonus_months"].split("|") if m.strip()
            ]
        if "split_separator" in raw:
            settings.split_separator = raw["split_separator"] or "/"
        return settings

    def find(self, product: str, insurance: str, type_: str,
             insurance_status: str, is_ancillary: bool,
             on=None) -> PointRule | None:
        for rule in self.point_rules:
            if not rule.applies_on(on):
                continue
            if rule.matches(product, insurance, type_, insurance_status, is_ancillary):
                return rule
        return None

    def bonus(self, bonus_id: str) -> BonusRule | None:
        for rule in self.bonuses:
            if rule.bonus_id == bonus_id:
                return rule
        return None
