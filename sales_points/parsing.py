"""Normalisation helpers that turn raw Fit Report columns into engine inputs."""

from __future__ import annotations

import re
from datetime import date, datetime

from .models import FitRow, Rep

# Fit Report headers vary month to month, so each engine field accepts several
# spellings. Matching is done on a lower-cased, punctuation-stripped key.
COLUMN_ALIASES = {
    "patient": ("patient", "patientname", "patientid"),
    "pro": ("pro", "provider", "proprovider"),
    "rep": ("rep", "repname", "salesrep", "reps"),
    "team": ("team", "region"),
    "insurance": ("insurance", "insurancecompany", "payer", "carrier"),
    "type": ("type", "casetype", "scenario"),
    "date_rx_received": ("daterxrcvd", "daterxreceived", "rxdate", "rxreceived"),
    "fit_date": ("fitdate", "datefit", "fitcompletedate", "dateoffit"),
    "patient_status": ("patientstatus", "customerstatus", "status"),
    "doc": ("doc", "doctor", "physician", "docname"),
    "product": ("product", "productline", "category"),
    "insurance_status": ("insurancestatus", "insstatus"),
    "fit_status": ("fitstatus", "devicestatus", "affectostatus", "fit"),
    "bmv": ("bmv", "belowmarketvalue"),
    "garment_fitted": ("garmentfitted", "garment", "garmentdispensed"),
    "new_customer": ("newcustomer", "new", "isnewcustomer"),
}

DATE_FORMATS = (
    "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y",
    "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y",
)

_REP_WITH_ID = re.compile(r"^\s*(?P<name>[^()]*?)\s*\(\s*(?P<id>[^)]*?)\s*\)\s*$")


def normalise_key(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (header or "").lower())


def build_header_map(fieldnames) -> dict:
    """Map engine field names to the actual header used in this month's export."""
    lookup = {normalise_key(name): name for name in (fieldnames or [])}
    mapping = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                mapping[field_name] = lookup[alias]
                break
    return mapping


def parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    text = (value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_tribool(value) -> bool | None:
    """Yes/No columns are frequently blank; blank must stay unknown, not False."""
    if isinstance(value, bool):
        return value
    text = (value or "").strip().lower()
    if not text:
        return None
    if text in {"yes", "y", "true", "1", "x", "fitted", "dispensed"}:
        return True
    if text in {"no", "n", "false", "0", "none", "not fitted"}:
        return False
    return None


def parse_reps(value: str, separator: str = "/") -> list:
    """Split ``LOPICCOLO (M1-11-69) / HOUSE EAST (M1-21-0)`` into two reps."""
    reps = []
    for chunk in (value or "").split(separator):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _REP_WITH_ID.match(chunk)
        if match:
            reps.append(Rep(name=match.group("name").strip(), rep_id=match.group("id")))
        else:
            reps.append(Rep(name=chunk))
    return reps


def row_from_dict(raw: dict, header_map: dict, row_number: int) -> FitRow:
    def get(field_name: str) -> str:
        header = header_map.get(field_name)
        return (raw.get(header) or "").strip() if header else ""

    return FitRow(
        patient=get("patient"),
        pro=get("pro"),
        rep=get("rep"),
        team=get("team"),
        insurance=get("insurance"),
        type=get("type"),
        date_rx_received=parse_date(get("date_rx_received")),
        fit_date=parse_date(get("fit_date")),
        patient_status=get("patient_status"),
        doc=get("doc"),
        product=get("product"),
        insurance_status=get("insurance_status"),
        fit_status=get("fit_status"),
        bmv=bool(parse_tribool(get("bmv"))),
        garment_fitted=parse_tribool(get("garment_fitted")),
        new_customer=parse_tribool(get("new_customer")),
        row_number=row_number,
        raw=dict(raw),
    )
