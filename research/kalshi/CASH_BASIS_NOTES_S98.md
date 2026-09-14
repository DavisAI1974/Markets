# CASH BASIS FEED NOTES - S98 FEED G (family DEL)

Build date 2026-07-20. Module `research/kalshi/cash_basis.py`; store `data/cash_basis/hh_cash.json`
(raw source captures under `data/cash_basis/raw/`). Additive standalone; nothing existing edited.
The futures leg is read READ-ONLY from `data/contract_structure/NG_structure.json`.

## 1. THE MEASURED PUBLICATION MECHANICS (the load-bearing finding)

The assumption going in - "EIA publishes daily Henry Hub spot with a short (D-1/D-2) lag" - is
WRONG, and the walked winter sits across a publication-vehicle CHANGE. Everything below was
measured on 2026-07-20 from EIA's own pages, not assumed.

### The series is published in WEEKLY BATCHES, not daily

- The DNAV daily-history page (`eia.gov/dnav/ng/hist/rngwhhdD.htm`) carries its own release stamp,
  observed 2026-07-20: "Release Date: 7/15/2026 / Next Release Date: 7/22/2026" - seven days
  apart - with the newest datum being Monday 2026-07-13 ($2.83). A Wednesday release carrying data
  through the prior Monday = data-through of release-2, and Tue Jul-14 (already traded at release
  time) was NOT included.
- Consequence: a gas day's spot becomes publicly knowable between 2 and 9 days after the fact in
  the steady state, and up to 22 days across the year-end holiday skips (below).

### Era 1 (gas days 2025-09-01 .. 2026-01-21): the Natural Gas Weekly Update (NGWU)

- Weekly issues, normally Thursday, each carrying ONE Thu->Wed week of daily HH spot through
  release-minus-1 (verified per-issue: the 2025-12-04 issue carries Nov 27 - Dec 3 with Nov 27/28
  printed as "Holiday"; the 2026-01-22 issue carries Jan 15 - Jan 21).
- The complete release-date list for the store span, measured from EIA's archive index
  (`/naturalgas/weekly/includes/archive.php`):
  2025: Sep 4, 11, 18, 25; Oct 2, 9, 16, 23, 30; Nov 6, 13, 20; Dec 4, 11, 18.
  2026: Jan 8, 15, 22.
- HOLIDAY SKIPS ARE REAL: the index confirms NO issue exists in Nov 26-28 (Thanksgiving week),
  Dec 22-31, or Jan 1-2. Because each issue carries exactly one week, the skipped weeks' gas days
  never appeared in any NGWU issue at all; their first measured publication event is the NEXT
  release. Measured consequence: gas days 2025-12-18 .. 2025-12-24 and Dec 25-31 were first
  publishable 2026-01-08 - a 15-22 day publication blackout across the New Year.
- The 2026-01-22 issue is the FINAL NGWU (stated on the issue itself): "replaced by a new Weekly
  Natural Gas Storage Report (WNGSR) Supplement launching January 29, 2026."

### Era 2 (gas days from 2026-01-22): the WNGSR Supplement / DNAV weekly stamp

- The supplement launched Thursday 2026-01-29 and is "published every Thursday afternoon"
  (EIA's own description). The DNAV page today stamps a WEDNESDAY release with data-through
  release-2 (the 7/15 -> through 7/13 observation above), so at some point between February and
  July the effective release day and/or data-through cutoff shifted.
- Per-issue winter release dates for Era 2 could NOT be directly measured from here:
  web.archive.org is unreachable from this environment (tool-level block), and no supplement
  archive with per-issue daily-spot tables was locatable. NAMED GAP.
- The model therefore takes the CONSERVATIVE (later-knowable) weekly grid consistent with both
  measured anchors: release = first THURSDAY R with R >= gas_day + 2 (and R >= 2026-01-29),
  data-through = R - 2. Under it: Mon knowable Fri (T+4), Tue knowable Fri (T+3), Wed knowable
  the NEXT Friday (T+9), Thu/Fri knowable the following Fri (T+8/T+7).
- Residual model risk, named: if EIA actually released Wednesdays in February (as measured in
  July), values became knowable ~1 day EARLIER than the model claims - the error direction is
  conservative and cannot leak. A skipped February release would make the model a day early;
  no evidence of one (no February publication holidays on the Thursday grid; Presidents Day is
  a Monday), but Era-2 winter releases are modeled, not measured, and are tagged as such per row.

### The knowability rule used everywhere

`knowable_from = release_date + 1 calendar day`. The release HOUR is unmeasured for the walk
(NGWU/supplement released in the afternoon, i.e. mid-session), so same-day use is not defensible;
the day-after rule is airtight. Minimum lag anywhere in the store: gas_day + 2. Store-wide lag
min/max: 2 / 22 days.

### What the naive rule would have done

A naive "spot for day T joins at T+1" rule would have been wrong on EVERY one of the 212 rows
(the real floor is +2, the median far later). Concretely, in G11 it would have leaked the
physical blowout itself: the Jan 22/23 cash prints (8.42 / 30.72) were not publishable until
Jan 30, but a T+1 rule hands them to the agent on Jan 23/24 - a week of leaked squeeze. This is
the same class of leak the S97 COT build caught (its 47-day shutdown gap).

## 2. SOURCE ROUTE CHOSEN, AND WHY

- PRIMARY: the public DNAV history page HTML (`rngwhhdD.htm`), captured raw to
  `data/cash_basis/raw/rngwhhdD_2026-07-20.htm` (336 KB) and parsed positionally (Mon-Fri cells
  per week row; every week row verified Monday-anchored; 1540 week rows / 7410 daily values
  1997-01-07 .. 2026-07-13 parse clean; blank/'-'/'NA'/'W' cells are non-values, never zero).
  Chosen because: no API key needed (EIA_API_KEY is NOT set in this environment and the gate
  names DEMO_KEY as quota-broken), full history in one fetch, and the page carries its own
  release stamp (the Era-2 measurement).
- CROSS-CHECK (independent display of the same EIA series): the archived NGWU issues
  (2025-12-04, 2026-01-22), which print the same series in a different vehicle WITH release
  provenance. FRED's DHHNGSP display was the intended cross-check but is network-blocked from
  this environment (connection reset on direct fetch, HTTP 403 via the fetch tool). NAMED
  substitution: NGWU replaces FRED as the independent display; it is arguably stronger for this
  feed because each NGWU value is an AS-FIRST-PRINTED vintage with a known release date.
- Every store row carries `source: eia_dnav_html:rngwhhdD_2026-07-20.htm` and
  `retrieved_at: 2026-07-20T10:04:04+00:00` (raw-file capture time, UTC).

## 3. VINTAGE / REVISION BEHAVIOR (measured, feed-K discipline)

All SEVEN days checked against the archived NGWU issues differ from today's DNAV vintage by
$0.01-0.07:

| gas day | first print (NGWU issue) | current DNAV vintage | delta |
|---|---|---|---|
| 2025-12-01 | 5.05 (Dec 4)  | 5.08 | +0.03 |
| 2025-12-02 | 4.81 (Dec 4)  | 4.83 | +0.02 |
| 2025-12-03 | 4.87 (Dec 4)  | 4.86 | -0.01 |
| 2026-01-15 | 2.95 (Jan 22) | 2.92 | -0.03 |
| 2026-01-16 | 3.13 (Jan 22) | 3.06 | -0.07 |
| 2026-01-20 | 3.98 (Jan 22) | 4.00 | +0.02 |
| 2026-01-21 | 4.98 (Jan 22) | 4.96 | -0.02 |

The store carries the CURRENT vintage (retrieved 2026-07-20) and says so per row; the first-print
values are recorded in `meta.vintage_crosscheck_first_print_vs_current` (revised values stay,
labeled - the feed-K pattern). Whether this is true post-publication revision or two snapshot
conventions of the same Refinitiv assessment is not resolvable from the public displays. Scale
context: cents, on a series that moved $27 intra-window; it does not change any read below, but
per-instance characterization at cent resolution should prefer the first-print column where it
exists. The selftest's independent-display check asserts agreement within the measured 0.07
envelope and prints the deltas.

## 4. COVERAGE, PER DATE

- Store rows: 212 gas days, 2025-09-02 .. 2026-07-13 (current vintage; weekly-batch publication).
- Publication-basis tags: 83 measured_ngwu_release, 11 next_measured_release_holiday_skip,
  118 modeled_thursday_release.
- MISSING WEEKDAYS, each named (no weekend rows exist by construction - Friday's trade covers the
  weekend package; weekend/holiday gas days are None, never bridged):
  - 2025-09-01 Labor Day
  - 2025-11-11 Veterans Day
  - 2025-11-27 Thanksgiving Day
  - 2025-11-28 Day after Thanksgiving (NGWU prints "Holiday")
  - 2025-12-25 Christmas Day
  - 2025-12-26 Day after Christmas (no print in source)
  - 2026-01-01 New Year's Day
  - 2026-01-02 Day after New Year's (no print in source)
  - 2026-01-19 Martin Luther King Jr. Day
  - 2026-02-16 Presidents Day
  - 2026-04-03 Good Friday
  - 2026-05-25 Memorial Day
  - 2026-06-19 Juneteenth
  - 2026-07-03 Independence Day (observed)
- FUTURES LEG coverage: `calendar_front_settle` sessions exist 2025-11-02 .. 2026-02-26 (the
  structure store's span), so the matched-day BASIS is defined only there. Spot rows Sep 2 -
  Oct 31 2025 carry `front_settle: None` with the reason named; asof dates after the structure
  span report the spot leg and a nearest-prior settle informationally, basis None. G12 (Feb 1-13)
  and G13 (Feb 15-27) are fully inside the covered span.
- Futures-leg caveat (documented in `front_settle_source`): the settle is the GLBX ohlcv-1d
  daily-bar CLOSE (~ settle), not the official CME settlement print. Concrete size of the
  approximation at the worst possible spot: NGG26's final session (2026-01-28) close 7.200 vs
  the official final settlement 7.460 (-0.26). Sunday partial-session bars exist in the structure
  store but can never be selected by the matched-day join (spot gas days are Mon-Fri).

## 5. THE G11 WINDOW - THE BASIS PATH, FACTUAL

Gas-day series (current vintage; matched-day settle; basis = spot - settle, $/MMBtu):

| gas day | HH spot | front settle (sym) | basis | first knowable |
|---|---|---|---|---|
| 2026-01-16 | 3.06 | 3.109 (NGG26) | -0.049 | 2026-01-23 |
| 2026-01-19 | None (MLK) | 3.585 (NGG26) | None | - |
| 2026-01-20 | 4.00 | 3.886 (NGG26) | +0.114 | 2026-01-23 |
| 2026-01-21 | 4.96 | 5.080 (NGG26) | -0.120 | 2026-01-23 |
| 2026-01-22 | 8.42 | 4.942 (NGG26) | +3.478 | 2026-01-30 |
| 2026-01-23 | 30.72 | 5.353 (NGG26) | +25.367 | 2026-01-30 |
| 2026-01-26 | 25.01 | 6.690 (NGG26) | +18.320 | 2026-01-30 |
| 2026-01-27 | 17.19 | 6.425 (NGG26) | +10.765 | 2026-01-30 |
| 2026-01-28 | 9.34 | 7.200 (NGG26) | +2.140 | 2026-02-06 |
| 2026-01-29 | 10.25 | 3.917 (NGH26) | +6.333 | 2026-02-06 |
| 2026-01-30 | 7.18 | 4.416 (NGH26) | +2.764 | 2026-02-06 |

(Continuation, for reference: Feb 2 basis +1.169, Feb 3 +0.766 on NGH26.) The Jan 28->29 basis
step is a ROLL (NGG26 -> NGH26), which is why the module's 1/3/5d basis changes void across it
rather than printing a -4.2 "collapse"; Jan 29-30 cash still carries the delivery scramble
against the NEW March front.

Decision-time view (what `cash_basis_asof` actually serves, at the honest wall):

| asof date | latest knowable spot (gas day) | basis | chg_1d/3d/5d |
|---|---|---|---|
| Jan 23 - Jan 29 | 4.96 (Jan 21, age 2-8d) | -0.120 | -0.234 / None (MLK) / None (MLK) |
| Jan 30 - Feb 05 | 17.19 (Jan 27, age 3-9d) | +10.765 | -7.555 / +7.287 / +10.651 |
| Feb 06 | 4.11 (Feb 03, age 3d) | +0.766 | -0.403 / -5.567 / None (roll in window) |

Factually: during the squeeze's peak days (Jan 23-29) the agent's knowable cash picture was still
the pre-blowout Jan 21 print at basis -0.12; the physical market's +25 blowout became visible on
Jan 30 - the walk's largest miss day (+5020, 17x band) - as basis +10.765 with a +7.3 3-day
widening. The feed is a WEEKLY-refresh regime-state variable at 2-9 day staleness, not a daily
nowcast; `age_days` is part of every read.

## 6. STORE / MODULE / SELFTEST

- Store rows: `{gas_day, spot, source, retrieved_at, publication_date_assumed_or_measured,
  publication_basis, knowable_from}`; meta carries the full publication model, the measured
  release list, the vintage table, and every named gap.
- `cash_basis_asof(date) -> dict | None`: latest PUBLISHABLE spot (blind wall `knowable_from <=
  date`, enforced by in-code `_require` assertions on every call), `age_days`, matched-day front
  settle (session/symbol/source named; nearest-prior reported informationally only),
  `hh_cash_minus_front_settle`, `basis_chg_1d/3d/5d` (None unless every business day in the
  window has a matched basis AND the front symbol is constant - never bridge a None, never
  difference across a roll), `note`.
- `--selftest` result 2026-07-20: S1 store integrity (212 rows, lag floor 2d) OK; S2 known-value
  checks - 5 exact vs the DNAV display AND 7 vs the independent NGWU display within the measured
  vintage envelope - all OK; S3 blind-wall audit 0 violations over 317 asof evaluations;
  S4 missing-is-None demonstrated on the Jan 17 weekend + MLK (chg_3d/5d refuse to bridge);
  S5 prints the G11 factual table. PASS.
- NOT wired into decision_state (per the gate: wiring is the orchestrator's serial pass).
  Wiring note: expose `age_days` and the publication basis alongside the basis fields - the
  staleness IS part of the signal's meaning.
