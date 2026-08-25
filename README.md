# Sales Point Automation

Automates the monthly commission point calculation described in
**MASTER SALES COMMISSION AND CALCULATION SOP 06-19-26** and the rule tables in
**TRITON COMMISSION / POINT SHEET CHEAT SHEET (August 2026)**.

It takes the Monthly Fit Report, applies the point rules, bonuses, ancillary
overrides, splits and honorarium deductions, and produces rep-level point sheets
plus a review queue for anything it cannot decide on its own.

> **Read-only by design.** This tool reads local CSV exports and writes local CSV
> files. It never writes back to Google Sheets, the Affecto Tracker, or any live
> system. Approved numbers are still copied into the official commission sheet by
> a person, exactly as Steps 7–8 of the SOP require.

## The process it automates

The manual cycle today looks like this:

| Step | Today (manual) | With this tool |
| --- | --- | --- |
| 1 | Verify devices are marked **FIT** in the Affecto Tracker | unchanged — still a human check |
| 2 | Get the Monthly Fit Report from Ben Guyon | unchanged — export it as CSV |
| 3 | Filter the report by Rep ID, classify product/insurance/type | **automated** |
| 4 | Assign points, bonuses, splits, FFW/ancillary adjustments | **automated** |
| 5 | RSM + rep review | unchanged — review the generated sheets |
| 6 | Copy approved totals to the official commission sheet | unchanged — human step |
| 7 | Submit to HR, lock the sheets | unchanged — human step |

The automation replaces steps 3 and 4, which is where the manual filtering and
arithmetic actually happens. Everything that requires judgement or sign-off stays
with a person.

## How a row is scored

The engine follows the nine ordered steps from the cheat sheet's INSTRUCTIONS tab.
Order matters — no field decides the points on its own.

1. **Is it Fit?** A row scores nothing unless its fit status is a Fit Complete
   value. Non-fit rows are reported with rule `NOT_FIT`.
2. **BMV check (critical).** Below Market Value wins over every other rule:
   0 points, no commission.
3. **Ancillary check.** If `PRO` contains `*`, the ancillary rule table applies.
4. **Ancillary exception (critical).** An ancillary MZ Auto RX with **no garment
   fitted** is not processed through the Ancillary Program — the standard MZ Auto
   rule (250) is used instead.
5. **Base points.** Product → insurance → type → insurance status are matched
   together against `rules/point_rules.csv`. The most specific rule wins.
6. **Bonuses**, kept separate from base points: new customer (+500), Gold Pair
   (+50), and the rep-level 5+ new customers bonus (+1,000). New-account bonuses
   double in December and January.
7. **Splits.** The full point value is calculated **first**, then divided equally
   between the reps listed in the Rep column.
8. **Honorarium deduction.** 50% of the rep's honorarium payout for the month is
   deducted from their points.
9. **Anything unmatched is flagged, never guessed.** Rows that do not clearly
   match a rule get `Review Needed? = Yes` and 0 points.

Every output row carries the `Rule Used` and a plain-English `AI Explanation`, so
a rep or RSM can see exactly why a number came out the way it did.

## Running it

```bash
python -m sales_points "27) MARCH 2026 FITTINGS.xlsx" \
  --rx-history        path/to/rx_history.csv \
  --awarded-customers path/to/awarded_customers.csv \
  --honorariums       path/to/honorariums.csv \
  --out-dir           output/2026-08
```

Try it against the bundled sample first:

```bash
python -m sales_points sample_data/fit_report_sample.csv \
  --rx-history sample_data/rx_history_sample.csv \
  --honorariums sample_data/honorariums_sample.csv \
  -o output/sample
```

### Inputs

| File | Required | What it is |
| --- | --- | --- |
| Monthly Fit Report | yes | The month's fits — pass the `.xlsx` export directly, or a CSV |
| `--rx-history` | no | Customer → most recent prior RX date. Needed for the 12-month new-customer test |
| `--awarded-customers` | no | Customers that already used their one-time new-customer bonus |
| `--honorariums` | no | Rep honorarium payouts for the month |
| `--rep-roster` | no | Rep ID to full name. The Fit Report holds surnames only |

Fit Report column headers change month to month, so the loader matches them
loosely (`Fit Date`, `Date Fit`, `Fit Complete Date` all work). If the new-customer
column is absent, the RX history file supplies the answer; without either, the
bonus is withheld rather than guessed.

### Outputs

| File | Contents |
| --- | --- |
| `master_point_sheet.csv` | Every row, in POINT SUMMARY TEMPLATE column order |
| `rep_point_sheets/point_sheet_<REPID>.csv` | One sheet per rep — what you send for review |
| `commission_summary.csv` | Per rep: row points, bonuses, honorarium deduction, final points |
| `review_queue.csv` | Only the rows needing a human decision — work this first |

## Maintaining the rules

The rules live in CSV, not in code, so they can be maintained in Google Sheets and
exported when they change:

- `rules/point_rules.csv` — the POINT RULES table (base points per scenario)
- `rules/bonuses.csv` — the BONUSES & EXCEPTIONS table
- `rules/settings.csv` — fit statuses, the ancillary marker, deduction rate, windows

To change a point value or add a product line, edit the CSV. No code change is
needed. Rules are matched by keyword; `|` separates alternatives and a blank cell
means "any value". `priority` breaks ties — the highest number wins, which is how
*MZ PA/MI/FL Auto* (250) beats the general *MZ Auto* row (50).

Keyword matching is negation-aware: `Non-Litigated` does not match a `litigated`
rule, and `Non-Surgical` does not match a `surgical` rule.

## Tests

```bash
python -m pytest
```

49 tests assert the engine reproduces the cheat sheet's own worked examples —
every row of the POINT RULES table, the ancillary overrides, the split example
(MZ Auto 250 → 125 each), the bonus rules, and the honorarium deduction.

## Before this runs a real month

See [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md). A handful of rules are ambiguous in
the source documents and are currently implemented against a stated assumption —
those need Allissa's confirmation, and the SOP's own instruction to validate
against historical months still applies.

## Reading the real Fit Report

The Affecto export is not a tidy table, so `sales_points/fit_report.py` handles
its quirks rather than requiring anyone to clean the file up by hand:

- three banner rows sit above the header, so the header row is detected by
  looking for the row carrying both `PATIENT STATUS` and `PRODUCT`
- `PRO`, `REP` and `TYPE` each appear twice; the first occurrence wins
- the fit state is inside `PATIENT STATUS` as `(8.1) FIT` — `FIT/INCOMPLETE`,
  `RETURNED` and `PATIENT DEMO` correctly score nothing
- the insurance **category** (`PA WC`, `MI AUTO`, `MEDICARE`) is in `TYPE`;
  `INS` holds the payer name (`SEDGWICK`, `BROADSPIRE`) and is not used for
  rule matching
- the **surgical marker** is in `URGENCY / INCOMPLETE NOTES`, not in `TYPE`

Reading `.xlsx` requires `openpyxl` (`pip install openpyxl`). CSV input needs
no dependencies.

### Validated against a real month

`27) MARCH 2026 FITTINGS` — 231 rows, **142 scored automatically (61%)**. Of the
89 flagged, 66 are TCT rows whose surgical status cannot be determined from the
report; see question 0 in `OPEN_QUESTIONS.md`. That number should rise sharply
once that one question is answered.
