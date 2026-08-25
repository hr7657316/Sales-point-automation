"""Readers for the monthly input files (all local CSV exports, read-only)."""

from __future__ import annotations

import csv
from pathlib import Path

from .parsing import build_header_map, normalise_key, parse_date, row_from_dict


def load_fit_report(path: Path) -> list:
    """Read a Monthly Fit Report export into FitRow objects."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header_map = build_header_map(reader.fieldnames)
        return [
            row_from_dict(raw, header_map, number)
            for number, raw in enumerate(reader, start=2)
        ]


def _find_column(fieldnames, *aliases):
    lookup = {normalise_key(name): name for name in (fieldnames or [])}
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    return None


def load_rx_history(path: Path) -> dict:
    """customer/provider -> date of their most recent prior RX."""
    history: dict = {}
    if not path or not Path(path).exists():
        return history
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        key_col = _find_column(reader.fieldnames, "customer", "doc", "provider",
                               "customerkey", "doctor")
        date_col = _find_column(reader.fieldnames, "lastrxdate", "lastrx",
                                "daterxrcvd", "date", "rxdate")
        for raw in reader:
            key = (raw.get(key_col) or "").strip().upper() if key_col else ""
            when = parse_date(raw.get(date_col)) if date_col else None
            if not key:
                continue
            # Keep the most recent RX per customer.
            if key not in history or (when and history[key] and when > history[key]):
                history[key] = when
    return history


def load_awarded_customers(path: Path) -> set:
    """Customers that already consumed their one-time new-customer bonus."""
    awarded: set = set()
    if not path or not Path(path).exists():
        return awarded
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        key_col = _find_column(reader.fieldnames, "customer", "doc", "provider",
                               "customerkey", "doctor")
        for raw in reader:
            key = (raw.get(key_col) or "").strip().upper() if key_col else ""
            if key:
                awarded.add(key)
    return awarded


def load_honorariums(path: Path) -> dict:
    """rep id (and rep name) -> total honorarium payout in dollars."""
    payouts: dict = {}
    if not path or not Path(path).exists():
        return payouts
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        id_col = _find_column(reader.fieldnames, "repid", "rep_id")
        name_col = _find_column(reader.fieldnames, "rep", "repname", "salesrep")
        amount_col = _find_column(reader.fieldnames, "amount", "payout",
                                  "honorariumamount", "payoutamount")
        for raw in reader:
            try:
                amount = float(
                    (raw.get(amount_col) or "0").replace("$", "").replace(",", "")
                )
            except (ValueError, AttributeError):
                continue
            for column in (id_col, name_col):
                key = (raw.get(column) or "").strip().upper() if column else ""
                if key:
                    payouts[key] = payouts.get(key, 0.0) + amount
    return payouts


def load_rep_roster(path: Path) -> dict:
    """Rep ID -> the rep's full name, for sheets people actually read.

    The Fit Report stores only a surname and an ID (``LOPICCOLO (M1-11-69)``),
    so full names have to come from a roster the company maintains. Without one
    the surname is used as-is rather than guessed at.
    """
    roster: dict = {}
    if not path or not Path(path).exists():
        return roster
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        id_col = _find_column(reader.fieldnames, "repid", "rep_id", "id")
        name_col = _find_column(reader.fieldnames, "fullname", "name", "repname",
                                "rep")
        for raw in reader:
            rep_id = (raw.get(id_col) or "").strip() if id_col else ""
            full = (raw.get(name_col) or "").strip() if name_col else ""
            if rep_id and full:
                roster[rep_id.upper()] = full
    return roster
