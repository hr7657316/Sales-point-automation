# Open questions for Allissa

---

## VALIDATED AGAINST A PAID SHEET

`Paul Lopiccolo Monthly Points Worksheet`, MARCH 2026 tab - the sheet that was
actually paid. Total paid: **19,050 points**. The engine now produces **18,350
on the same month, 96.3%, with no rows flagged.**

| Rule | Paid | Engine | |
| --- | --- | --- | --- |
| TCT Work Comp Surgical | 3 / 2100 | 3 / 2100 | match |
| TCT Non-Surg WC/Auto open or litigated | 15 / 4500 | 15 / 4500 | match |
| MZ Work Comp | 17 / 8500 | 16 / 8000 | 1 row |
| MZ PA, MI, FL Auto | 3 / 750 | 3 / 750 | match |
| Ancillary TCT Surgical Post-OP | 1 / 200 | 1 / 200 | match |
| Ancillary TCT Non-Surgical | 6 / 1200 | 6 / 1200 | match |
| Ancillary MZ Work Comp | 7 / 1400 | 8 / 1600 | 1 row |
| Gold Pair | 8 / 400 | not scored | needs a fit date |

### What the paid sheet corrected

**The DOS column is not a date.** It holds `A` or `C` on 182 of 231 March rows.
The rules call this "DOS or non DOS (A or C)" and it marks the open or
litigated case. This single discovery resolved the entire surgical question:
a TCT row is surgical when URGENCY says so, and open/litigated at 300 when DOS
is A or C. All 25 of Lopiccolo's TCT rows then matched the paid sheet exactly.

**Ancillary rates were wrong in the cheat sheet.** The paid sheet shows
`200\100` (work comp \ auto) on every ancillary line. The cheat sheet said
300/200/100 with 0 for auto. The engine was overpaying every ancillary row.

**Back Brace is 250, not 300.**

**TENS is counted with MZ**, matching the sheet's own "MZ/TENS" line.

**"Garment not listed" lives in the product description**, not in a column of
its own, which is what triggers the ancillary MZ Auto exception at 250.

### The 700 points still unaccounted for

- **400** - Gold Pair. The rule needs both a TCT and an MZ fit within 30
  calendar days, but no column in the Fit Report reliably holds a fit date
  (DOS is the A/C code). **Which column is the fit date?**
- **300** - one row typed `PA WC P2A` from a starred provider. Allissa scored
  it as standard MZ Work Comp, not ancillary. **Does a P2A/FP2A case override
  the ancillary marker?**

### Categories on the paid sheet that are in no rulebook

MISx (SurGenTec, Tenon, Omnia, Eliquence), Work Comp Pharmacy, Pharmacy RX,
Wound Kit, TCT AT sold, Recruit and install a 1099 contractor, and an entire
**FP2A section with negative points** (`-250` PA WC TCT, `-100` PA WC MZ or TT,
`-250` licensed TCT unit, `-250` TCT patient demo, `-75` Sport-Z demo).

Deductions of that kind are not in the cheat sheet at all. **Do they need to be
in scope?**


These are the points where the source documents are ambiguous or disagree. Each
one is implemented against a stated assumption so the engine runs today, but each
needs confirmation before a real payroll month is calculated from it.

Nothing here was resolved by guessing inside the calculation — where a row cannot
be decided, it is flagged into `review_queue.csv` instead.

---

### 0. Post-surgical vs non-surgical on TCT rows — BLOCKING

Validated against the real **27) MARCH 2026 FITTINGS** export (231 rows).

The surgical marker was found: it lives in the **`URGENCY / INCOMPLETE NOTES`**
column, which holds exactly three values — blank, `IMMEDIATE`, and `SURGICAL`.
`SURGICAL` appears on TCT rows only (20 of them in March), and the engine now
reads it, scoring those at 700.

But the point rules need a **three-way** split:

| Scenario | Points |
| --- | --- |
| WC Surgical | 700 |
| WC Post-Surgical, MD/DO/PA/NP/OPM, <30 day post-op | 500 |
| WC Non-Surgical | 100 |

The column only distinguishes surgical from everything else. That leaves **66
TCT rows in March** that cannot be scored, because there is no way to tell a
500 from a 100 — a 5x difference.

**Question:** for a TCT Work Comp row that is not marked `SURGICAL`, how do you
decide post-surgical vs non-surgical? Is it on the RX, is it the `30 DAY RX` in
the product name, or does it come from another report?

This is the single biggest remaining blocker: it is roughly 29% of the month.

---

### 0b. Products with no rule

Also surfaced by the March export:

- **`LSO`** (4 rows) — a lumbar-sacral orthosis. Should this use the Back Brace
  rule (300 WC/Medicare)? Not assumed, because it is a guess.
- **`PERSON INJURY` / `PERSONAL INJURY`** (2 rows) — there is no personal-injury
  rule anywhere in the cheat sheet. What should these score?
- **`MZ ONLY (GARMENT NOT LISTED ON RX)` + `PA AUTO`, ancillary** (5 rows) —
  this looks exactly like the ancillary MZ Auto "no garment fitted" exception,
  which would make it the standard 250. Is that reading correct?

---

### Validation across seven months (Jan-Jul 2026)

All seven 2026 Fit Reports were run through the engine: **1,375 rows, zero parse
failures**. The layout is identical every month, so the reader is stable.

| Month | Rows | Scored | Coverage |
| --- | --- | --- | --- |
| January | 162 | 112 | 71% |
| February | 165 | 113 | 68% |
| March | 231 | 139 | 61% |
| April | 209 | 136 | 66% |
| May | 196 | 122 | 64% |
| June | 185 | 118 | 65% |
| July | 227 | 143 | 64% |
| **Total** | **1,375** | **883** | **65%** |

Of the 471 rows flagged across all seven months:

| Rows | Cause |
| --- | --- |
| **413** | TCT / Cold Therapy - surgical vs non-surgical unknown |
| 35 | Ancillary MZ Auto, garment not listed |
| 12 | Products and insurance types with no rule (below) |
| 7 | `LSO` |
| 4 | Personal Injury |

**88% of everything unscored is the single surgical question.** Answer it and
coverage goes from 65% to roughly **96%**.

### 0c. Further products and insurance types with no rule

Only visible once all seven months were checked:

- **`KNEE SCOOTER`** (4 rows, CO WC) - no rule
- **`TENS ONLY`** (1 row) - no rule
- **`GARMENT ONLY`** (1 row, Medicare) - no rule
- **`SPORT-Z`** with insurance type `SELF-PAY` - the rules cover SportZ at 0
  points, but is self-pay treated the same?
- Insurance types absent from the rulebook: **`RAILROAD CLAIM`**,
  **`SLIP & FALL`**, **`SELF-PAY`**, **`CO WC P2A`**, **`IL AUTO`**

`IL AUTO` matters: the rules name PA, MI and FL Auto at 250. Illinois Auto is
not listed, so those rows score nothing. Is that deliberate or an omission?

---

### 0d. Rep full names

The Fit Report identifies reps by surname and ID only, in all seven months
checked: `LOPICCOLO (M1-11-69)`, `LIPUT (M1-21-08)`, `THAPA (M1-11-31)`. There
are no first names anywhere in the file.

Point sheets go to the reps themselves, so they should carry proper names. The
engine now accepts a roster (`--rep-roster`) mapping Rep ID to full name, and
falls back to the surname for anyone not listed. Nothing is invented.

**Question:** can we have the rep roster - each Rep ID with the rep's full name?
Sixteen IDs appear across the seven months, plus the house accounts
(`HOUSE EAST`, `HOUSE WEST`), which may want a different label entirely.

---

### 1. FFW adjustment vs. the ancillary table — the two sources disagree

The Master SOP (§5.2) gives this example:

> Standard TCT WC Surgical = 700, **FFW adjusted = 200**

The cheat sheet's ancillary table gives, for the same family:

| Scenario | WC | Auto |
| --- | --- | --- |
| TCT WC Surgical – Post OP (<30 day post op) | 300 | 0 |
| TCT WC Non-Surgical | 200 | 0 |

**Assumption used:** the cheat sheet's ancillary table is authoritative, because it
is newer and more detailed. So an ancillary TCT WC Surgical row scores **300**, not
the SOP's 200.

**Question:** is the SOP's `700 → 200` example simply out of date, or is there a
separate FFW adjustment that applies on top of the ancillary table? Related: is
"FFW 2.0 provider" always the same set as "PRO contains `*`", or are they two
different lists that need to be checked separately?

---

### 2. Honorarium deduction — dollars to points

The rule is "50% of any honorarium payout will be deducted from rep points". The
payout is a dollar amount; the deduction is in points.

**Assumption used:** $1 = 1 point, so a $1,000 honorarium deducts 500 points.
Configurable via `honorarium_points_per_dollar` in `rules/settings.csv`.

**Question:** what is the correct conversion?

---

### 3. Can a rep's points go negative?

With the assumption above, a rep with 450 points and a $1,000 honorarium ends the
month at **-50 points**. (This is exactly what the bundled sample produces for
MATT R, deliberately.)

**Assumption used:** the arithmetic is reported faithfully, negative included.

**Question:** should the total floor at 0, or should the remainder carry into the
next month?

---

### 4. The 5+ new customer bonus — 30 days from when?

The rule reads "5 or more fit complete in the first 30 calendar days".

**Assumption used:** 30 calendar days from the rep's **first** qualifying
new-customer Fit Complete, counted within the month being processed.

**Question:** is the window the first 30 days of the month, 30 days from the rep's
first new account, or 30 days from the rep's start date? And is the bonus awarded
once per month or once per rep, ever?

---

### 5. Gold Pair — per patient or per rep?

The POINT RULES tab calls it a "Gold Pair Patient Bonus"; the exceptions tab notes
"Per Sales Rep".

**Assumption used:** awarded once per **patient**, when that patient has both a TCT
and an MZ fit within 30 calendar days, non-ancillary only. Credited on the later of
the two rows.

**Question:** is it per patient (as implemented) or a per-rep bonus?

---

### 6. New customer — keyed on the DOC?

"New customer" means no RX in the last 12 months, applied once per customer.

**Assumption used:** the customer is the **DOC** (falling back to PRO), and the
12-month test needs an RX history export. Without that file the bonus is withheld
rather than guessed.

**Question:** is DOC the right key? And is there an existing report that gives each
provider's last RX date, so the 12-month test can run without manual input?

---

### 7. Odd-numbered splits

A 3-way split of 700 points does not divide evenly.

**Assumption used:** split as evenly as possible with the remainder going to the
first rep listed (234 / 233 / 233), so the row still totals 700.

**Question:** correct, or should splits round down and drop the remainder?

---

### 8. Rows excluded from the Fit Report

Per §3.3, the FFW filter view removes USDL patients and Medicare/Tricare/government
programs, and includes auto cases only if a garment was dispensed.

**Assumption used:** the engine scores whatever rows it is given. It does **not**
apply the FFW filter view itself.

**Question:** should that filtering happen inside the automation, or does the Fit
Report export already have it applied?

---

## Next step

The SOP's own validation approach still applies: run a previous month's Fit Report
through the tool and compare its output against the point sheet that was actually
paid. Differences will either be a rule to fix or one of the questions above.
