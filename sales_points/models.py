"""Data structures shared by the point engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Rep:
    """A single sales rep parsed out of the Fit Report ``Rep`` column."""

    name: str
    rep_id: str = ""

    def __str__(self) -> str:
        return f"{self.name} ({self.rep_id})" if self.rep_id else self.name


@dataclass
class FitRow:
    """One row of the Monthly Fit Report, normalised into engine inputs."""

    patient: str = ""
    pro: str = ""
    rep: str = ""
    team: str = ""
    insurance: str = ""
    type: str = ""
    date_rx_received: date | None = None
    fit_date: date | None = None
    patient_status: str = ""
    doc: str = ""
    product: str = ""
    insurance_status: str = ""
    fit_status: str = ""
    bmv: bool = False
    garment_fitted: bool | None = None
    new_customer: bool | None = None
    # Sourced from the Fit Report's URGENCY / INCOMPLETE NOTES column,
    # which is where the surgical marker actually lives.
    surgical: bool | None = None
    row_number: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def customer_key(self) -> str:
        """New-customer bonuses are awarded once per customer (the DOC/provider)."""
        return (self.doc or self.pro or "").strip().upper()


@dataclass
class RowResult:
    """The calculated outcome for a single Fit Report row."""

    row: FitRow
    base_points: int = 0
    bonus_points: int = 0
    rule_used: str = ""
    review_needed: bool = False
    explanation: str = ""
    is_ancillary: bool = False
    is_split: bool = False
    rep_allocations: list = field(default_factory=list)
    bonuses_applied: list = field(default_factory=list)

    @property
    def total_points(self) -> int:
        return self.base_points + self.bonus_points


@dataclass
class RepSummary:
    """Month-end totals for one rep, after rep-level bonuses and deductions."""

    rep_id: str
    rep_name: str
    row_points: int = 0
    rep_level_bonus: int = 0
    honorarium_deduction: int = 0
    rows: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def gross_points(self) -> int:
        return self.row_points + self.rep_level_bonus

    @property
    def final_points(self) -> int:
        return self.gross_points - self.honorarium_deduction
