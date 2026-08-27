# Open questions for Allissa

---

## RULINGS FROM ALLISSA (ten-question email, 2026-08-27) - all implemented

She answered all ten row-level questions. Two more paid-sheet errors
confirmed, four new rules learned, and the Gold Pair rule is now fully
validated (her June list of seven patients matches the engine's seven
exactly; April 10, May 11, July 15 also match her counts).

New rules wired in:

- **Derrick Plummer (April) was underpaid: 300 paid, 500 correct.** An RX
  written BEFORE the surgery makes the fit a Post-Surgical fitting, and the
  30-day window counts from the patient's EARLIEST device fit that month
  (his MZ, 27 days post-op). Implemented in `surgical_kind`. Corrected
  April paid total: 15,950 (Giordano +400, Plummer +200).
- **Electrodes Only / Wrap Only = 0 points** (Patricia Elbayly). Supplies
  shipped for an existing device never earn points. `SUPPLY_ONLY` gate.
- **Self Pay = 0 points for any product** (Justin Carrick). `SELF_PAY_ZERO`.
- **FIT/INCOMPLETE still earns points when the insurance status is
  billable** (David McClintock, May: FIT/INCOMPLETE + O/A/B paid 500).
  This single rule closed most of May's gap.
- **Garment wording distinction refined**: "GARMENT NOT ELIGIBLE" (e.g.
  due to the TPA - Joel Houston, standard 500) means no garment was sent
  and the row leaves the ancillary program; hyphenated "GARMENT
  NON-ELIGIBLE" stays ancillary on work comp (Wright, Strickland).
- **June MZ Auto count confirmed**: her "2 were split accounts" are
  Witcop and Marion Williams, whose REP column reads `LOPICCOLO / HOUSE
  EAST` - the engine already splits them. No change needed.
- **New-customer bonus source**: the Last Referral column (Q) on the
  Affecto Tracker (link in her email). Not yet integrated.
- **Honorarium folder ingested**: `rules/honorariums.csv` now holds all
  15 honorarium contracts (rep, provider, rate, signed date). Paul
  Lopiccolo holds Steven Regal ($1,000) and Tyler Watson ($500); July's
  sheet deducted exactly 500 = 50% of Regal's $1,000, independently
  confirming the deduction rule. Which months a check is actually issued
  still comes from the monthly QuickBooks process (per the Honorarium
  SOP), so per-month payouts remain a needed input.
- **Affecto Tracker ingested** (via an xlsx copy, since the owner's
  security limitations block viewer downloads and API access):
  `rules/provider_referral_history.csv` holds all 2,502 providers from
  the + PRO/REP tab with their LAST REFERRAL dates and FFW flags.
  Structural finding: the tracker stores only the LATEST referral date,
  overwritten on each new referral - so "was this account new in month
  X" can only be checked against a snapshot taken AT month X. The saved
  CSV is the first such baseline (as of 2026-08-27); the engine needs a
  fresh snapshot each month before scoring. July's two new-customer
  accounts therefore cannot be reconstructed from today's data - ask
  Allissa which two they were (11 of Paul's 20 July providers now show
  July-or-later dates). For permanent automation she still needs to
  share the live sheet with download enabled for viewers.

Still open after this round (the last four gaps):

- **April -400**: her corrected sheet has 7 surgical TCTs; the engine
  finds 6 with surgery dates. One of the six DOS="A" rows (Marple, Werner,
  Martin, Daymude, Dach, Knapp) she counts as surgical - the report gives
  no surgery date for any of them. Need: which patient, and where the
  surgery date comes from.
- **May +300**: the sheet pays only 21 standard MZ WCs to the engine's 22
  (Courtney Walker via Brian Stone DO - unstarred in the report but on the
  FFW list pending W9 - is the likely difference), and the sheet has a
  third ancillary TCT the engine scores 0 (Joel Houston's TCT, blank
  patient status). Two row-status questions.
- **June -800**: Theresa Schaffer's May FP2A pair is paid IN JUNE when
  both device statuses moved to billable - a cross-month mechanic the
  engine cannot see from one month's report (worth ~550 of the gap: her
  MZ 500 + the 8th Gold Pair 50). Needs month-over-month status tracking
  or her confirmation of the remaining ~250.
- **July -400**: the two new-customer bonuses (1,000, needs the Affecto
  Tracker), offset by ~600 the engine scores that the sheet does not -
  she says only 2 of the 3 starred MZ WCs count ancillary (Strickland
  plus one; which of Hendal/Christian is standard, and why?). Her "200"
  for Strickland also conflicts with the June rate change to 300.

---

## RULINGS FROM ALLISSA (star-marker email) - all implemented

Her answers to the star/ancillary questions, received 2026-08-26:

- **The star designation in the fit report is reliable.** "There is either a
  star (*) or a plus (+) sign" next to the provider name. `*` = FFW 2.0
  ancillary provider, `+` = AMP MI ancillary provider (Michigan program).
  The engine now treats either marker as ancillary
  (`ancillary_marker = *|+` in `rules/settings.csv`).
- **Ancillary status is provider-wide.** When a provider is in an ancillary
  program the designation applies to all their products - but the **ancillary
  point rules themselves only exist for TCT, MZ, and TT**. Other products
  from a starred provider score by their standard rules.
- **She manages the provider lists herself** and shared both trackers. They
  are captured read-only in `rules/ancillary_providers.csv` (70 providers:
  65 FFW 2.0, 5 AMP MI; pending contracts flagged `PENDING` - Kyle Holmberg,
  Brian Stone, Matthew Sardelli).
- **Chelsea Snyder's 500 was a scoring error after all**: "I made an error
  when scoring Chelsea's TCT... it was a group error." March's corrected
  paid total is therefore 18,750 - which the engine already produced.
  **March is now EXACT**, making three paid-sheet errors the engine caught
  (Giordano, Gunter, Snyder).

The `+` marker appears 9 times in the Jan-Jul fit reports (Peter Lasater,
Sabin Shah, Wednesday Hall - exactly the AMP MI tracker), all under Skyler's
Michigan accounts, so Paul Lopiccolo's validation totals were unaffected.

Validation standing after these rulings: **January, February, and March
EXACT**; April -350, May -500, June -800, July -400 - all remaining
differences are the per-row garment/ancillary judgment calls listed below.

---

## FINAL RULINGS FROM ALLISSA (Questions 2 email)

Her answers to the last two row-level questions, all implemented:

- **The 30-day rule applies to TCT and TT only. Surgery dates never affect
  MZ.** A TCT is surgical at 700 when the surgery falls within 30 days of the
  fit date in either direction; outside that it is the open/litigated 300.
- **Christopher Giordano was underpaid.** His TCT was paid 300 but "should
  have been worth 700" - surgery 26 days before the fit. The engine's
  calculation was closer to correct than the paid sheet.
- **Jenny Gunter's TCT is 300**, not the post-surgical 500 the May sheet
  categorized - surgery 37 days before the fit. Again the engine agreed with
  her ruling, not the sheet.
- **Roy Wright's 200 was correct** under the pre-June point sheet: an
  ancillary MZ Work Comp with a non-eligible garment stays ancillary. She
  also confirmed in passing that ancillary MZ WC went 200 to 300 in June -
  the period versioning the engine already implements.
- **Chelsea Snyder's 500 was correct** because she treats that provider as
  non-ancillary for MZ WC, even though the fit report stars them: "MZ Work
  Comp patients with non-ancillary providers are always 500 points,
  regardless of garment." *(Superseded by her star-marker email: she later
  confirmed this was a group scoring error - see the section above.)*
- Garment wording distinction: **garment NOT LISTED** leaves the ancillary
  program entirely (Kenya Willis, standard 500 on WC); **garment
  NON-ELIGIBLE** stays ancillary on work comp (Wright) but standard on auto
  (her earlier answer).

### The most important finding of the whole validation

Two of the seven paid months contained errors that Allissa herself confirmed
when shown the rows: Giordano underpaid by 400 points in April, Gunter
misclassified in May. **The engine caught both.** The remaining differences
against the paid sheets are concentrated in per-row provider-status
judgments (which providers count as ancillary for which product) that the
fit report's star marker does not fully capture.


---

## ALLISSA'S SIX ANSWERS, WIRED IN

1. **Fit date = column W, DATE DME REC'D.** The reader now uses it.
2. **P2A means Fit Prior to Approval** and does not override the star.
   Instead there is a global gate nobody had written down: **if Insurance
   Status is not O/A/B, Billed, or Billed without Auth, the row earns no
   points for any product.** Implemented as a hard gate before every rule.
3. **Surgical = surgery within 30 days of the fit date.** Implemented
   three-way: surgery on/after the fit within 30 days is surgical (700),
   surgery before the fit within 30 days is post-surgical (500), anything
   further out is paid like the open/litigated 300 - which matches how the
   April outlier was actually paid.
4. **Garment "NOT ELIGIBLE" auto from a starred provider = 250**, same as
   garment-not-listed. Marker added.
5. **Splits are provider-level**: the provider's total is split between the
   two reps. July's 2,200 total is larger than the split-marked rows (1,750),
   so some of that provider's rows must sit under a single rep name - see
   remaining questions.
6. **The 06-01-2026 label is just the sheet's validity period.** The
   empirical Jan-May vs Jun-Jul rate difference stands and stays implemented.

Standing after wiring these in: January and February exact, 98.0% across the
seven paid months, every difference still row-traceable.

### Two follow-ups her answers created

- **Which date does the 30-day post-op test use?** May's post-surgical row
  has surgery 04-14 with the RX received exactly 30 days later (05-14) but
  the fit 38 days later - paid 500. April's row (surgery 03-30, RX 24 days
  after, fit 30 days after) was paid 300. The fit-date reading matches
  April; the RX-date reading matches May. One of the two is a one-off.
- **Provider-level splits:** for July's 2,200 split, which rows made up the
  2,200? The split-marked rows total 1,750.


---

## SOLVED SINCE: Gold Pair, rate periods, honorarium conversion

The June and July tabs of the paid worksheet carry the **Gold Pair patients by
name** - 22 of them across two months. Cross-referencing every named patient
against the fit reports settled the rule empirically:

> A Gold Pair is a patient with both a TCT row and an MZ-family row (MZ ONLY
> products count) in the **same month's report**, non-ancillary. No date
> window is involved.

Tested against all seven paid months - 9, 7, 8, 10, 11, 7, 15 - it matches
**7 of 7 exactly**. Question 5 is closed.

**Rates are versioned by period.** The worksheet header reads "06-01-2026 --
03-31-2027": from June 2026 the ancillary lines pay 300\0, 200\0, 100\0 and
Back Brace pays 300, while January-May paid 200\100 and 250. So the cheat
sheet and the paid sheets were both right, for different periods. The rule
table now carries effective dates and the whole report is priced by its month.

**Honorarium: $1 = 1 point confirmed.** July's total reads "24,050 - 500
POINTS (HONORARIUM)": a 50% deduction of 500 points on a $1,000 payout.
Question 2 is closed.

Current standing against the paid worksheet, all rules included:

| Month | Paid | Engine | |
| --- | --- | --- | --- |
| January | 14,450 | 14,450 | exact |
| February | 12,850 | 12,850 | exact |
| March | 19,050 | 18,750 | -300 |
| April | 15,350 | 15,800 | +450 |
| May | 18,050 | 18,250 | +200 |
| June | 18,750 | 17,700 | -1,050 |
| July | 23,050 | 22,425 | -625 |
| **Seven months** | **121,550** | **120,225** | **98.9%** |

The remaining differences trace to named single rows: the March P2A row, the
April/May surgical-date edge cases, June/July rows of `MZ ONLY (GARMENT NOT
ELIGIBLE AUTO)` from starred providers, and how the July split account was
valued at 2,200 (the engine finds 1,750 across the same rows).


---

## VALIDATED AGAINST FIVE PAID MONTHS

`Paul Lopiccolo Monthly Points Worksheet`, January to May 2026 - the sheets
that were actually paid. Gold Pair is excluded from these figures because the
rule cannot yet be derived (see below).

| Month | Paid (ex Gold Pair) | Engine | Difference |
| --- | --- | --- | --- |
| January | 14,000 | 14,000 | **exact** |
| February | 12,500 | 12,500 | **exact** |
| March | 18,650 | 18,350 | -300 |
| April | 14,850 | 15,300 | +450 |
| May | 17,500 | 17,700 | +200 |
| **Five months** | **77,500** | **77,850** | **+350** |

No rows flagged in any of the five months.

### DOS is the Date Of Surgery

The decisive decode. The `DOS` column holds either a date or the letter `A` or
`C`. It is the Date Of Surgery, which makes the rulebook's phrase "DOS or non
DOS (A or C)" literal:

- a **date** in DOS means there was a surgery, so the surgical rate applies
- **A or C** means there was none, so the open or litigated rate of 300 applies

Tested against five paid months, this reproduces the TCT split on both counts
in January, February and March exactly, and is off by one row in April and May.
It is a better signal than the `URGENCY` marker, which the reader still honours
as well.

## What is still not right, and why we are not forcing it

### Gold Pair - the rule cannot be derived from the data

Paid counts were 9, 7, 8, 10, 11 across the five months. Four different
mechanical readings were tested against all five:

| Interpretation | Months matched |
| --- | --- |
| excluding ancillary, one month at a time | 1 of 5 |
| excluding ancillary, pairs spanning months | 0 of 5 |
| including ancillary, one month at a time | 2 of 5 |
| including ancillary, pairs spanning months | 1 of 5 |

Four candidate date columns were also tested; none matched consistently. March
appearing to match at 8 was a coincidence, which only five months of data
exposed.

**No mechanical interpretation reproduces the paid counts.** Rather than tune
the window until one month agrees, the rule is left unimplemented.

**Question:** how is a Gold Pair actually counted? Which two dates have to fall
within the 30 days, do ancillary patients count, and can a pair span a month
boundary?

### The remaining rows, month by month

- **May, +200.** May paid one row as *WC Post-Surgical (<30 Post-op)* at 500;
  the engine scored it surgical at 700. Distinguishing the two needs the fit
  date and the provider type (MD/DO/PA/NP/DPM). **Which column holds the fit
  date, and where does the provider type come from?**
- **April, +450.** One row with a surgery date was paid at 300 rather than 700.
  Possibly the surgery was more than 30 days before the fit. Same missing
  input as above.
- **March, -300.** One row typed `PA WC P2A` from a starred provider was paid
  as standard MZ Work Comp rather than ancillary. **Does a P2A case override
  the ancillary marker?**

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
