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
# The two wordings are distinct per Allissa's paid rows: "NOT ELIGIBLE"
# (e.g. due to the TPA) means no garment was sent, so the row leaves the
# ancillary program entirely (Joel Houston, standard 500 on WC); the
# hyphenated "NON-ELIGIBLE" stays ancillary on work comp (Roy Wright 200,
# Carlie Strickland).
NO_GARMENT_MARKERS = ("GARMENT NOT LISTED", "NO GARMENT", "GARMENT NOT ELIGIBLE")
GARMENT_INELIGIBLE_MARKERS = ("GARMENT NON-ELIGIBLE", "GARMENT NON ELIGIBLE",
                              "GARMENT NON-ELIBILE")


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


def surgical_kind(urgency: str, dos: str = "", fit=None, rx=None,
                  min_fit=None) -> str:
    """Classify the surgical scenario, per Allissa's confirmed rules.

    The 30-day rule applies to TCT and TT only (the engine's rules already
    scope it so). Surgery dates never affect MZ. Three paid rulings pin the
    logic down:

    - Christopher Giordano (RX after surgery, fit 26 days after it) is
      Surgical at 700 - the surgery falls within 30 days of the fit.
    - Jenny Gunter (RX after surgery, fit 37 days after it) is outside the
      window and falls to the open/litigated 300.
    - Derrick Plummer (RX three days BEFORE surgery, first device fit 27
      days after it) is Post-Surgical at 500: an RX written pre-op makes
      the fit a post-op fitting, and the patient's earliest fit date is
      what the 30 days are counted against.
    """
    if SURGICAL_MARKER in (urgency or "").upper():
        return "surgical"
    surgery = parse_date(dos)
    if surgery is None:
        return ""
    if fit is None:
        return "surgical"
    if fit <= surgery:
        # Fit ahead of an upcoming surgery: the classic Surgical case.
        return "surgical" if (surgery - fit).days <= 30 else "outside-window"
    if rx is not None and rx < surgery:
        # RX written pre-op, patient fit after the surgery: Post-Surgical,
        # counted against the patient's earliest fit (Plummer).
        window_ref = min_fit or fit
        if 0 <= (window_ref - surgery).days <= 30:
            return "post-surgical"
        return "outside-window"
    if (fit - surgery).days <= 30:
        return "surgical"
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
    """True only for the 'garment not listed on RX' wording specifically.

    Per Allissa: a garment-not-listed referral leaves the ancillary program
    entirely (Kenya Willis, paid standard 500 on work comp), while a
    non-eligible garment from an ancillary provider stays ancillary on work
    comp (Roy Wright, paid the ancillary 200).
    """
    return any(m in (product or "").upper() for m in NO_GARMENT_MARKERS)


def rows_from_grid(grid: list) -> list:
    """Turn a raw sheet grid into FitRow objects."""
    header_index = find_header_row(grid)
    columns = build_column_index(grid[header_index])

    def field_of(raw, field: str) -> str:
        position = columns.get(field)
        if position is None or position >= len(raw):
            return ""
        return raw[position]

    # First pass: each patient's earliest fit date. The post-surgical
    # 30-day window counts from the patient's FIRST device fit that month
    # (Derrick Plummer: MZ fit 27 days post-op, TCT five days later).
    min_fit_by_patient: dict = {}
    for raw in grid[header_index + 1:]:
        patient = field_of(raw, "patient").split("\n")[0][:60]
        fit = parse_date(field_of(raw, "fit_date"))
        if patient and fit:
            prior = min_fit_by_patient.get(patient)
            if prior is None or fit < prior:
                min_fit_by_patient[patient] = fit

    fit_rows = []
    for offset, raw in enumerate(grid[header_index + 1:], start=header_index + 2):
        if not any(cell for cell in raw):
            continue

        def get(field: str, _row=raw) -> str:
            return field_of(_row, field)

        # Rows with no rep and no product are spacers, not referrals.
        if not get("rep") and not get("product"):
            continue

        patient_status = get("patient_status")
        fit_date = parse_date(get("fit_date"))
        patient_key = get("patient").split("\n")[0][:60]
        kind = surgical_kind(
            get("urgency"), get("dos_code"), fit_date,
            rx=parse_date(get("date_rx_received")),
            min_fit=min_fit_by_patient.get(patient_key),
        )
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
