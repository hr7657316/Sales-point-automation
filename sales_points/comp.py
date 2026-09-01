"""Points-to-dollars commission conversion.

Each rep's worksheet template carries a banded payout table plus bonus
tiers (per Allissa, 09-01): the commission is the band payout for the
rep's monthly points, plus the bonus of the highest tier reached.

Paul Lopiccolo, April 2026: 15,350 points -> band $8,300 + 25% tier
bonus $1,850 = $10,150, matching his sheet. Verified against all six
months carrying a final dollar figure on his 2026 sheets.

Tables differ per rep (and some reps have a second Surgical-division
table, out of scope for now). Bands live in rules/comp_plans.csv; a row
whose note names a bonus tier ("10% Bonus Pay") marks that tier's
threshold (its band_low) and bonus amount.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompPlan:
    rep: str
    # (band_low, band_high, payout)
    bands: list = field(default_factory=list)
    # (threshold_points, bonus_usd), ascending
    bonus_tiers: list = field(default_factory=list)

    def commission_for(self, points: int) -> int | None:
        """Dollar commission for a month's points; None when out of table."""
        payout = None
        for low, high, amount in self.bands:
            if low <= points <= high:
                payout = amount
                break
        if payout is None:
            return None
        bonus = 0
        for threshold, amount in self.bonus_tiers:
            if points >= threshold:
                bonus = amount
        return payout + bonus


def load_comp_plans(path: str | Path = "rules/comp_plans.csv") -> dict:
    plans: dict = {}
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            rep = row["rep"].strip().upper()
            plan = plans.setdefault(rep, CompPlan(rep=rep))
            low = int(row["band_low"])
            high = int(row["band_high"])
            payout = int(row["payout_usd"]) if row["payout_usd"] else 0
            plan.bands.append((low, high, payout))
            if row.get("bonus_usd"):
                plan.bonus_tiers.append((low, int(row["bonus_usd"])))
    for plan in plans.values():
        plan.bands.sort()
        plan.bonus_tiers.sort()
    return plans
