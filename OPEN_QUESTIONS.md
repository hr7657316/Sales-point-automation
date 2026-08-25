# Open questions for Allissa

These are the points where the source documents are ambiguous or disagree. Each
one is implemented against a stated assumption so the engine runs today, but each
needs confirmation before a real payroll month is calculated from it.

Nothing here was resolved by guessing inside the calculation — where a row cannot
be decided, it is flagged into `review_queue.csv` instead.

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
