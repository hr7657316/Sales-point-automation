"""Reader for the real Monthly Fit Report workbook (Affecto export).

The export is not a clean table: five banner rows sit above the header, several
column names repeat, the fit state is buried inside PATIENT STATUS, and the
surgical marker lives in the URGENCY / INCOMPLETE NOTES column. This module
isolates all of that so the rest of the engine keeps working on tidy inputs.

Read-only: it opens the workbook and never writes to it.
"""

from __future__ import annotations

from pathlib import Path

from .models import FitRow
from .parsing import normalise_key, parse_date

# Engine field -> the header text used in the Fit Report. Only the FIRST
# occurrence of a repeated header (PRO, REP, TYPE all appear twice) is used.
FIT_REPORT_COLUMNS = {
    "pro": "PRO",
    "rep": "REP",
    "team": "TEAM",
    "insurance": "INS",
    "type": "TYPE",
    "date_rx_received": "DATE RX REC'D",
    "patient_status": "PATIENT STATUS",
    "fit_date": "DOS",
    "product": "PRODUCT",
    "insurance_status": "INSURANCE STATUS",
    "patient": "PATIENT INFO",
    "urgency": "URGENCY / INCOMPLETE NOTES",
}

# The header row is the one carrying both of these.
HEADER_MARKERS = ("patientstatus", "product")

SURGICAL_MARKER = "SURGICAL"


def _require_openpyxl():
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "Reading .xlsx Fit Reports needs openpyxl. Install it with "
            "`pip install openpyxl`, or export the report to CSV and use "
            "load_fit_report() instead."
        ) from exc
    return openpyxl


def _cell(value) -> str:
    return "" if value is None else str(value).strip()


def find_header_row(rows: list) -> int:
    """Locate the header row beneath the banner rows. Raises if absent."""
    for index, row in enumerate(rows):
        keys = {normalise_key(cell) for cell in row}
        if all(marker in keys for marker in HEADER_MARKERS):
            return index
    raise ValueError(
        "Could not find the Fit Report header row (expected a row containing "
        "both 'PATIENT STATUS' and 'PRODUCT')."
    )


def build_column_index(header: list) -> dict:
    """Map engine fields to column positions, keeping the first of duplicates."""
    positions = {}
    for index, cell in enumerate(header):
        key = normalise_key(cell)
        if key and key not in positions:
            positions[key] = index

    mapping = {}
    for field, header_text in FIT_REPORT_COLUMNS.items():
        position = positions.get(normalise_key(header_text))
        if position is not None:
            mapping[field] = position
    return mapping


def is_fit(patient_status: str) -> bool:
    """'(8.1) FIT' counts; 'FIT/INCOMPLETE', 'RETURNED', 'PATIENT DEMO' do not."""
    text = (patient_status or "").upper()
    return "FIT" in text and "INCOMPLETE" not in text


def is_surgical(urgency: str) -> bool:
    """The URGENCY column carries SURGICAL alongside dispatch values."""
    return SURGICAL_MARKER in (urgency or "").upper()


def rows_from_grid(grid: list) -> list:
    """Turn a raw sheet grid into FitRow objects."""
    header_index = find_header_row(grid)
    columns = build_column_index(grid[header_index])

    fit_rows = []
    for offset, raw in enumerate(grid[header_index + 1:], start=header_index + 2):
        if not any(cell for cell in raw):
            continue

        def get(field: str, _row=raw) -> str:
            position = columns.get(field)
            if position is None or position >= len(_row):
                return ""
            return _row[position]

        # Rows with no rep and no product are spacers, not referrals.
        if not get("rep") and not get("product"):
            continue

        patient_status = get("patient_status")
        fit_rows.append(
            FitRow(
                patient=get("patient")[:60] or f"ROW-{offset}",
                pro=get("pro"),
                rep=get("rep"),
                team=get("team"),
                insurance=get("insurance"),
                type=get("type"),
                date_rx_received=parse_date(get("date_rx_received")),
                fit_date=parse_date(get("fit_date")),
                patient_status=patient_status,
                # The provider is the customer for new-customer bonus purposes.
                doc=get("pro"),
                product=get("product"),
                insurance_status=get("insurance_status"),
                fit_status="FIT" if is_fit(patient_status) else patient_status,
                surgical=is_surgical(get("urgency")),
                row_number=offset,
                raw={},
            )
        )
    return fit_rows


def load_fit_report_workbook(path: Path) -> list:
    """Read a Monthly Fit Report .xlsx export into FitRow objects."""
    openpyxl = _require_openpyxl()
    workbook = openpyxl.load_workbook(Path(path), data_only=True, read_only=True)
    try:
        sheet = workbook.active
        grid = [
            [_cell(cell) for cell in row]
            for row in sheet.iter_rows(values_only=True)
        ]
    finally:
        workbook.close()
    return rows_from_grid(grid)
