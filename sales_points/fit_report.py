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
    "dos_code": "DOS",
    "product": "PRODUCT",
    "insurance_status": "INSURANCE STATUS",
    "patient": "PATIENT INFO",
    "urgency": "URGENCY / INCOMPLETE NOTES",
    "fit_date": "DATE DME REC'D",
}

# The header row is the one carrying both of these.
HEADER_MARKERS = ("patientstatus", "product")

SURGICAL_MARKER = "SURGICAL"

# DOS values that mark an open or litigated case rather than a date.
OPEN_LITIGATED_CODES = {"A", "C"}

# There is no "garment fitted" column; the product description carries it.
NO_GARMENT_MARKERS = ("GARMENT NOT LISTED", "NO GARMENT")
GARMENT_INELIGIBLE_MARKERS = ("GARMENT NON-ELIGIBLE", "GARMENT NOT ELIGIBLE")


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


def surgical_kind(urgency: str, dos: str = "", fit=None) -> str:
    """Classify the surgical scenario, per Allissa's stated rules.

    DOS is the Date Of Surgery; the fit date is DATE DME REC'D (column W).
    Surgery on or after the fit and within 30 days: surgical. Surgery before
    the fit and within 30 days: post-surgical. A surgery outside either
    window is treated like a non-surgical open/litigated case, which is how
    such rows were actually paid. Without a fit date, any surgery date
    counts as surgical, and the URGENCY marker always does.
    """
    if SURGICAL_MARKER in (urgency or "").upper():
        return "surgical"
    surgery = parse_date(dos)
    if surgery is None:
        return ""
    if fit is None:
        return "surgical"
    days = (surgery - fit).days
    if 0 <= days <= 30:
        return "surgical"
    if -30 <= days < 0:
        return "post-surgical"
    return "outside-window"


def is_open_or_litigated(dos: str) -> bool:
    """The DOS column holds 'A' or 'C' far more often than a date.

    The rules call this "DOS or non DOS (A or C)" and treat it as the open or
    litigated scenario. A real date in this column means the case is not one.
    """
    return (dos or "").strip().upper() in OPEN_LITIGATED_CODES


def garment_fitted(product: str) -> bool | None:
    """Whether a garment was fitted, read from the product description.

    Returns None when the product says nothing either way, so the ancillary
    exception only fires on an explicit "no garment" product.
    """
    text = (product or "").upper()
    if any(m in text for m in NO_GARMENT_MARKERS + GARMENT_INELIGIBLE_MARKERS):
        return False
    return None


def garment_not_listed(product: str) -> bool:
    """True only for the 'garment not listed on RX' wording specifically."""
    return any(m in (product or "").upper() for m in NO_GARMENT_MARKERS)


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
        fit_date = parse_date(get("fit_date"))
        kind = surgical_kind(get("urgency"), get("dos_code"), fit_date)
        fit_rows.append(
            FitRow(
                patient=get("patient").split("\n")[0][:60] or f"ROW-{offset}",
                pro=get("pro"),
                rep=get("rep"),
                team=get("team"),
                insurance=get("insurance"),
                type=get("type"),
                date_rx_received=parse_date(get("date_rx_received")),
                fit_date=fit_date,
                dos_code=get("dos_code"),
                surgical_class=kind,
                garment_fitted=garment_fitted(get("product")),
                garment_unlisted=garment_not_listed(get("product")),
                patient_status=patient_status,
                # The provider is the customer for new-customer bonus purposes.
                doc=get("pro"),
                product=get("product"),
                insurance_status=get("insurance_status"),
                fit_status="FIT" if is_fit(patient_status) else patient_status,
                surgical=(kind == "surgical"),
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
