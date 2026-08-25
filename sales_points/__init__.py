"""Sales point automation for the Match One DME monthly commission cycle.

Implements the rule pipeline described in
``MASTER SALES COMMISSION AND CALCULATION SOP 06-19-26`` and the
``TRITON COMMISSION / POINT SHEET CHEAT SHEET`` rule tables.
"""

from .engine import PointEngine
from .models import FitRow, RepSummary, RowResult
from .rules import RuleBook

__all__ = ["FitRow", "PointEngine", "RepSummary", "RowResult", "RuleBook"]
__version__ = "0.1.0"
