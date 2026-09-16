# REVISION VINTAGE AUDIT - S98 (DATA_GATE_S98 feed K)

Build date 2026-07-20. Builder: feed K subagent (STEP C discipline).
Store: `data/storage_vintage/storage_vintage.json` (+ `raw/wayback_extract.json` provenance).
Module: `research/kalshi/storage_vintage.py`, `storage_vintage_asof(date) -> dict | None`
(exposes `*_as_printed` AND `*_current` for national + all five regions + salt/nonsalt).
Selftest: PASS. Store audit: 0 violations on all five checks. Unrecoverable weeks: NONE
(36/36 report weeks recovered, prints 2025-07-03 through 2026-03-05).

WHY (from the gate spec / S97 concern #1): the blind wall governs WHEN a report becomes visible,
not WHICH VINTAGE. Our storage stores (national `data/eia_surprise.json` lineage, regional
`data/storage_regional/`) carry EIA's latest revised estimates, so the walk's agent may have seen
numbers nobody had at the time. This audit recovers the AS-FIRST-PRINTED values from EIA's own
report pages and names every difference per week, per region.

---

## 1. THE HEADLINE: the entire vintage difference is ONE EIA revision event, published 2026-04-23

EIA's own notice, verbatim, printed on the 2026-04-23 WNGSR (Wayback capture 20260423170241, with
"R" flags on the Mountain and Total prior-week columns):

> "Working gas stocks were revised to reflect resubmissions of data for the 33-week period from
> August 29, 2025 to April 10, 2026, in large part because of respondent resubmissions reflecting
> restatements of natural gas in storage from working gas to base gas. Excluding the week ending
> August 29, 2025, the effect of revisions on the weekly implied net change averaged 0 Bcf in
> magnitude, because the working gas levels were revised downward by 10 Bcf on average each week
> during this period."

This audit measured exactly that, independently, before finding the notice: every one of the 27
differing weeks sits inside Aug 29 2025 - Mar 5 2026 (the walked tail of EIA's 33-week span); the
level offset is +9..+12 Bcf (printed above current), it lives almost entirely in the MOUNTAIN
region (working->base reclassification), and the only week whose CHANGE moved materially is the
week ending Aug 29 2025 (+55 printed -> +45 current, the 10 Bcf step). Bracketing evidence: the
offset is still present at the 2026-04-16 print (week 04-10: printed Mountain 210 vs current 200)
and gone at the 2026-04-23 print (week 04-17: printed 202 == current 202).

**Consequence for the walk: the revised numbers DID NOT EXIST during the walked winter.** Nobody
had them until 2026-04-23. Every current-vintage storage value the walk's agent consumed for the
affected weeks was future information - correctly timed (the blind wall held) but from the wrong
vintage. The direction of the error: the agent's national level input ran 9-12 Bcf BELOW what the
market actually knew (a slightly tighter-than-reality storage picture, all winter), and 18 weekly
changes differed by the amounts named below.

## 2. Routes investigated (per the spec: investigate first, verify, never assume)

1. **EIA's own archive/vintage facility: DOES NOT EXIST.** The WNGSR page links no report archive.
   The revision policy page (`ir.eia.gov/ngs/revisions.html`) states the dissemination rules but
   carries NO history of past revisions. EIA API v2 route `natural-gas/stor/wkly` has facets
   duoarea/product/process/series only - no vintage/revision facility; it serves the current
   vintage (verified against the route metadata with the live key, 2026-07-20).
   - The policy itself is load-bearing doctrine: revisions are DISSEMINATED only when net reported
     changes are >= 4 Bcf (regional or L48); out-of-cycle only >= 10 Bcf; reclassifications are
     reported only in regular releases. Sub-4-Bcf corrections therefore reach the current series
     with NO published notice anywhere - the mechanism behind the scattered 1 Bcf differences.
2. **Wayback Machine snapshots of the report page: THE ROUTE USED.** `ir.eia.gov/ngs/ngs.html`
   directly until 2026-01-06, after which the page moved behind CloudFront signed URLs
   (`ir.eia.gov/secure/ngs/ngs.html?Policy=...`) - both CDX-indexed and captured; route recorded
   per record (`wayback_ngs_html` / `wayback_secure_ngs_html`). Density: several captures per day
   Sep 2025 - Feb 2026 (2,766 + 890 x 200-OK captures; 71 unique page states fetched via digest
   dedup; id_ raw bodies, gzip-decoded where stored compressed). Every report week's earliest
   in-window capture parsed for: week ending, page-stated "Released:" datetime, all 8 table rows
   (5 regions + salt/nonsalt + total) x (level, prior level, net change, implied flow), per-value
   R flags, notice text.
3. **`ir.eia.gov/ngs/wngsr.json` (EIA machine summary): CORROBORATION.** 20 archived captures;
   11 landed in-window. All 11 MATCH the parsed HTML values exactly on every region, and none
   carried EIA revision flags. Independent format, same numbers.

## 3. The full per-week diff table (as-printed vs current vintage; deltas = printed - current)

Region detail lists every region whose level or change differs (delta level / delta chg, Bcf).
Current vintage: `data/storage_regional/storage_regional.json` (API-rebuilt 2026-07-20) with
`data/eia_surprise.json` cross-checked (the two current stores agree on every week - 0
disagreements). Feed D column: national as-printed change vs
`data/storage_consensus/storage_consensus.json` `actual_as_printed_bcf`.

| period | print | chg printed | chg current | d chg | lvl printed | lvl current | d lvl | region detail (delta level/chg) | feed D |
|---|---|---|---|---|---|---|---|---|---|
| 2025-06-27 | 2025-07-03 | +55 | +55 | 0 | 2953 | 2953 | 0 | - | n/a |
| 2025-07-04 | 2025-07-10 | +53 | +53 | 0 | 3006 | 3006 | 0 | - | n/a |
| 2025-07-11 | 2025-07-17 | +46 | +46 | 0 | 3052 | 3052 | 0 | - | n/a |
| 2025-07-18 | 2025-07-24 | +23 | +23 | 0 | 3075 | 3075 | 0 | - | n/a |
| 2025-07-25 | 2025-07-31 | +48 | +48 | 0 | 3123 | 3123 | 0 | - | n/a |
| 2025-08-01 | 2025-08-07 | +7 | +7 | 0 | 3130 | 3130 | 0 | - | n/a |
| 2025-08-08 | 2025-08-14 | +56 | +56 | 0 | 3186 | 3186 | 0 | - | n/a |
| 2025-08-15 | 2025-08-21 | +13 | +13 | 0 | 3199 | 3199 | 0 | - | agree |
| 2025-08-22 | 2025-08-28 | +18 | +18 | 0 | 3217 | 3217 | 0 | - | agree |
| 2025-08-29 | 2025-09-04 | +55 | +45 | +10 | 3272 | 3262 | +10 | mountain +10/+10 | agree |
| 2025-09-05 | 2025-09-11 | +71 | +71 | 0 | 3343 | 3333 | +10 | mountain +11/+1 | agree |
| 2025-09-12 | 2025-09-18 | +90 | +90 | 0 | 3433 | 3423 | +10 | mountain +10/-1 | agree |
| 2025-09-19 | 2025-09-25 | +75 | +76 | -1 | 3508 | 3499 | +9 | mountain +10/0; south_central_nonsalt -1/-1 | agree |
| 2025-09-26 | 2025-10-02 | +53 | +52 | +1 | 3561 | 3551 | +10 | mountain +10/0; south_central_nonsalt 0/+1 | agree |
| 2025-10-03 | 2025-10-09 | +80 | +80 | 0 | 3641 | 3631 | +10 | mountain +11/+1 | agree |
| 2025-10-10 | 2025-10-16 | +80 | +81 | -1 | 3721 | 3712 | +9 | mountain +10/-1; south_central -1/-1; south_central_salt -1/-1 | agree |
| 2025-10-17 | 2025-10-23 | +87 | +86 | +1 | 3808 | 3798 | +10 | mountain +10/0; south_central 0/+1; south_central_salt 0/+1 | agree |
| 2025-10-24 | 2025-10-30 | +74 | +74 | 0 | 3882 | 3872 | +10 | mountain +10/0 | agree |
| 2025-10-31 | 2025-11-06 | +33 | +33 | 0 | 3915 | 3905 | +10 | mountain +11/+1 | agree |
| 2025-11-07 | 2025-11-14 | +45 | +45 | 0 | 3960 | 3950 | +10 | mountain +10/-1 | agree |
| 2025-11-14 | 2025-11-20 | -14 | -14 | 0 | 3946 | 3936 | +10 | mountain +11/+1 | agree |
| 2025-11-21 | 2025-11-26 | -11 | -12 | +1 | 3935 | 3924 | +11 | mountain +10/-1 | agree |
| 2025-11-28 | 2025-12-04 | -12 | -11 | -1 | 3923 | 3913 | +10 | mountain +11/+1 | agree |
| 2025-12-05 | 2025-12-11 | -177 | -178 | +1 | 3746 | 3735 | +11 | mountain +11/0 | agree |
| 2025-12-12 | 2025-12-18 | -167 | -166 | -1 | 3579 | 3569 | +10 | mountain +10/-1 | agree |
| 2025-12-19 | 2025-12-29 | -166 | -168 | +2 | 3413 | 3401 | +12 | midwest +1/+1; mountain +11/+1 | agree |
| 2025-12-26 | 2025-12-31 | -38 | -37 | -1 | 3375 | 3364 | +11 | midwest +1/0; mountain +10/-1 | agree |
| 2026-01-02 | 2026-01-08 | -119 | -120 | +1 | 3256 | 3244 | +12 | midwest +1/0; mountain +10/0 | agree |
| 2026-01-09 | 2026-01-15 | -71 | -70 | -1 | 3185 | 3174 | +11 | midwest 0/-1; mountain +10/0; south_central +1/+1; south_central_salt +1/+1 | agree |
| 2026-01-16 | 2026-01-22 | -120 | -120 | 0 | 3065 | 3054 | +11 | mountain +10/0; south_central 0/-1; south_central_salt 0/-1 | agree |
| 2026-01-23 | 2026-01-29 | -242 | -241 | -1 | 2823 | 2813 | +10 | mountain +9/-1 | agree |
| 2026-01-30 | 2026-02-05 | -360 | -359 | -1 | 2463 | 2454 | +9 | mountain +10/+1; south_central -1/-1; south_central_salt -1/-1 | agree |
| 2026-02-06 | 2026-02-12 | -249 | -252 | +3 | 2214 | 2202 | +12 | east +1/+1; mountain +11/+1; south_central 0/+1; south_central_salt 0/+1 | agree |
| 2026-02-13 | 2026-02-19 | -144 | -143 | -1 | 2070 | 2059 | +11 | east 0/-1; mountain +11/0 | agree |
| 2026-02-20 | 2026-02-26 | -52 | -52 | 0 | 2018 | 2007 | +11 | mountain +10/-1 | agree |
| 2026-02-27 | 2026-03-05 | -132 | -131 | -1 | 1886 | 1876 | +10 | mountain +10/+1 | agree |

Named summary of the differing weeks (27 weeks with any difference; every one inside EIA's
announced 33-week revision span):

- **National LEVEL differs on all 27 weeks from 2025-08-29 through 2026-02-27**: printed runs
  +9 to +12 Bcf above current (per-week values in the table; largest +12 on 2025-12-19,
  2026-01-02, 2026-02-06).
- **National CHANGE differs on 18 weeks**: 2025-08-29 (+10 - the step week), then 1-3 Bcf:
  09-19 (-1), 09-26 (+1), 10-10 (-1), 10-17 (+1), 11-21 (+1), 11-28 (-1), 12-05 (+1), 12-12 (-1),
  12-19 (+2), 12-26 (-1), 01-02 (+1), 01-09 (-1), 01-23 (-1), 01-30 (-1), 02-06 (+3), 02-13 (-1),
  02-27 (-1). The 1-3 Bcf wobble is the week-to-week variation of the level offset (9..12), i.e.
  the SAME single revision event, not separate events.
- **Region attribution**: Mountain carries the entire persistent offset (+9..+11 every affected
  week - the working->base restatement). One-off 1 Bcf level touches: midwest (12-19, 12-26,
  01-02), east (02-06), south_central/salt (10-10 -1, 01-09 +1), nonsalt (09-19 -1). All named in
  the table; all part of the same resubmission wave per EIA's notice ("in large part").
- The l48 delta occasionally differs by 1 from the sum of region deltas (e.g. 11-21 mountain +10,
  l48 +11): EIA's own independent rounding ("Totals may not equal sum of components because of
  independent rounding" - their footer), recorded verbatim, not adjusted.
- **Nov 26 / Dec 4 crossing pair explained**: printed -11/-12 vs current -12/-11 is the level
  offset moving 10->11->10 across the three underlying weeks - one revision event, not two.

## 4. Reconciliation with feed D (per week, named)

Feed D (`storage_consensus.json`) carries `actual_as_printed_bcf` (from TE/investing/FF archived
calendar pages) and `vintage_diff_bcf` for its 29 print weeks (2025-08-21 - 2026-03-05).

- **National as-printed change: AGREE on all 29/29 overlap weeks, exactly** (the store's `feed_d`
  block records the comparison per week; the audit's `feed_d_print_date_mismatch` and agreement
  checks report 0 disagreements). The survey-house pages and EIA's own archived pages carry the
  same as-printed numbers on every overlapping week.
- **Nonzero vintage-diff weeks: identical sets, 18/18.** Feed D's store has nonzero
  `vintage_diff_bcf` on exactly the same 18 periods this audit found, with the same signs and
  magnitudes (incl. Sep 4 +10 and the Nov 26/Dec 4 crossing).
- One label-level correction: feed D's NOTES prose says "17 of 29 weeks" - its own store contains
  18 nonzero rows (the 18 named above). The prose undercounts by one; the stores agree perfectly.
- Feed D could only see the national CHANGE. This audit adds the LEVELS (the persistent +9..12),
  the five-region + salt/nonsalt detail, the Mountain attribution, and the dating of the revision
  event - which converts feed D's "17 weeks of small diffs" picture into the true structure: one
  post-era revision, one step week, a shifted level path.

## 5. What was checked and found CLEAN (the era's own internal stability)

- **No in-era revisions**: for every week, the next print's prior-week column equals the printed
  level exactly (0 changes), no R flags on any in-era page, no notices on any in-era page, and
  `implied flow == net change` on every printed row (no reclassifications reported in-era). The
  printed series was internally stable all winter; the vintage break arrived only on 2026-04-23.
- **Print datetimes**: the page's own "Released:" line matches feed D's schedule on all overlap
  weeks including all four holiday shifts (Nov 14 Fri 10:30; Nov 26 Wed 12:00; Dec 29 Mon 12:00;
  Dec 31 Wed 12:00) - audit check, 0 mismatches.
- **Evidence timing**: every as-printed capture falls inside its print window
  [print datetime, next print datetime) - 0 violations. Median capture lag under an hour (several
  within a minute of the print; 2025-10-03's week captured 1 second after 14:30:00Z). One named
  note: the 2025-12-18 print was captured at 15:29:58Z, 2 seconds before the official stamp, and
  contains the new report - EIA publish jitter (page went live seconds early), not a wall issue;
  tolerance 120s, documented in the module.
- **Salt/nonsalt as printed**: sums match South Central except eight weeks off by exactly 1 Bcf
  (2025-09-12, 09-19, 10-24, 11-14, 12-12, 12-26, 2026-02-20, 02-27) - EIA's independent rounding
  on the printed page, named verbatim. (The API series is reconciled; the printed page is not
  always. Both are EIA's own numbers.)
- **Our two current stores agree with each other**: regional l48 weekly change vs eia_surprise
  actual - 0 disagreements across all 36 weeks.

## 6. Unrecoverable fields

**NONE.** All 36 report weeks in the covered window (prints 2025-07-03 - 2026-03-05, which spans
the walked window Sep 2025 - Mar 2026 plus a 9-week earlier extension) were recovered in full:
national + all five regions + salt/nonsalt, levels and changes, from in-window captures. The
secure-URL era (Jan 6 2026+) thins to 1-6 captures/day but never misses a print window.

## 7. The honest bottom line - how large was the walk's vintage look-ahead, per week

Stated per week (the table above IS the statement; this section reads it, never pools it):

1. **Timing was never violated; vintage was.** The blind wall held (S96/S97 audits were correct),
   but from the first visible day of the Sep 4 print (2025-09-05) to the end of the walk, every
   storage LEVEL the agent consumed was a number that did not exist until 2026-04-23. Per-week
   magnitude: the agent's national level ran 10 Bcf low on 16 weeks, 11 low on 7, 12 low on 3, 9
   low on 1 (table column d lvl, sign: agent input BELOW market-known) - a slightly
   tighter-than-reality picture all winter, concentrated in Mountain.
2. **The one materially contaminated PRINT-day input: 2025-09-04.** The market traded a printed
   +55 build against a +54 consensus (a 1 Bcf miss, near-neutral); our current-vintage store
   records +45, which would re-read that day as a 9-10 Bcf bullish surprise that NOBODY saw. Any
   per-instance characterization of the 09-04 print day that used the stored actual is
   mis-labeled. (Feed D's consensus join re-measures print days; this is the week where the
   VINTAGE side of that join matters most.)
3. **The other 17 differing print days: 1-3 Bcf.** Each is named in the table (largest: Feb 12's
   -249 printed vs -252 current, d = +3; Dec 29's -166 vs -168, d = +2; all others 1 Bcf). At the
   walk's decision surface these sit inside survey-house disagreement (feed D shows houses 5-16
   Bcf apart on several weeks) - but per doctrine that is the agent's call to make, not this
   audit's to score; the store exposes both vintages so the call is makeable.
4. **Derived fields shift too**: vs_5yr / vs_year_ago / salt_share in the regional store are
   computed off revised levels; for the affected weeks their as-printed counterparts differ by the
   same per-week deltas (as-printed level fields are in this store; derived comparisons can be
   recomputed from them where a consumer needs the exact as-printed view).
5. **Pass-2 note (per the gate's deferral list)**: propagating these as-printed vintages through
   the already-walked findings is JOB 4 / second-refinement work, explicitly not done here. The
   affected candidates are any play whose evidence cites storage levels or the 09-04 surprise.

## 8. Store / module / wiring notes (for the orchestrator; not done here, per STEP C rules)

- Store: `data/storage_vintage/storage_vintage.json` - per report week: print date/datetime
  (page-stated), as_printed (national + 8 region rows: level/chg/implied_flow/prior_level),
  second_vintage (next print's view + R flags), corroboration (wngsr.json where in-window),
  current_vintage (both stores), deltas, evidence (route/URL/digest/capture lag/capture counts),
  notices, unrecoverable_fields. `_meta.revision_event` carries the dated EIA notice verbatim
  with bracketing evidence. `raw/wayback_extract.json` = full per-snapshot extraction provenance.
- Module: `storage_vintage_asof(date)` - most recent print STRICTLY BEFORE the decision day
  (same day-level rule as storage_regional_asof), returning `*_as_printed` + `*_current` +
  per-region both-vintage rows + deltas + evidence. Blind wall asserted per call; `--selftest`
  audits the store (0 violations required) incl. the known-week Sep 4 +10 check against feed D;
  `--diff` prints the per-week table; `--audit` the violation counts.
- Wiring: additive only. The gate spec's instruction stands: where differences exist, the
  as-printed overlay lands in the second serial wiring pass as `*_as_printed` fields; the revised
  values STAY, labeled. This module is that overlay's source.
- The walked-era store ends at the 2026-03-05 print. Later prints are current-era (the revision
  landed 2026-04-23; from the 2026-04-23 print onward printed == current vintage as of today -
  verified through the 2026-07-02 capture). If the walk extends past G13 into Mar-Apr 2026, the
  store should be extended over those prints (snapshots exist; same route).
