# COT FUTURES-AND-OPTIONS COMBINED - build notes (DATA_GATE_S98 feed H, family P)

Built 2026-07-20 by the feed H subagent. Module: `research/kalshi/cot_combined_feed.py`.
Store: `data/cot_combined/ng_cot_combined_023651.json` (+ raw zips in `data/cot_combined/raw/`).
NOT committed (builder discipline); not wired (the orchestrator's serial pass extends `cot_asof`
output additively with this module's `cot_combined_asof`). The existing `cot_feed.py` and
`data/cot/` were NOT modified by this build; the futures-only store is consumed READ-ONLY.

## Why this feed exists

The S97 COT build is FUTURES-ONLY. Options positioning is a separate picture, and expiry-week
mechanics (G13, the squeeze test carrying the Feb 25 2026 opex/expiry pair) are exactly where the
two diverge: a crowd that looks moderate in futures can be violently short via options. The G11
squeeze (NGG26 3.0 -> 7.460 settle) is the standing motivating instance. This feed closes the
OPTIONS half of COT limit #9.

## Source (investigated first, per gate doctrine)

- CFTC Disaggregated Commitments of Traders, futures-AND-options-combined variant:
  `https://www.cftc.gov/files/dea/history/com_disagg_txt_<YEAR>.zip`, one `c_year.txt` per zip
  (the futures-only variant `cot_feed.py` pulls is `fut_disagg_txt_<YEAR>.zip` / `f_year.txt`).
- Verified 2026-07-20 on the 2026 file: identical 191-column layout to the futures-only file;
  all twelve columns this feed parses are present under the SAME names, so
  `cot_feed.parse_archives` is reused verbatim (format drift still FATALs, never guesses).
- Contract: `023651` = "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE" (same code as the futures
  store; the ICE and penultimate contracts remain deliberately excluded, as in `cot_feed.py`).
- DOWNLOAD MECHANICS CHANGE (found 2026-07-20): cftc.gov now returns HTTP 403 to python's
  default User-Agent on BOTH variants. This module's downloader sends a browser User-Agent.
  `cot_feed.py`'s downloader predates the block and was NOT edited (its raw zips are already on
  disk); if it is ever re-run with `--force`, it will need the same header.

## What "combined" means (field semantics)

The CFTC converts options positions into futures-equivalents using each option's risk factor
(delta) and adds them to futures positions. Every `*_combined` field is therefore in
futures-equivalent contracts, directly comparable to the futures-only fields, and:

    <field>_options_implied = <field>_combined - <field>(futures-only)

is the options-positioning read - computed AT READ TIME inside `cot_combined_asof` against
`data/cot/ng_cot_023651.json` (READ-ONLY), always on the SAME report_date on both sides, never
across vintages. Where either side is missing the derived value is None, never 0.

Percentile discipline: the derived read's 1y/3y percentiles are percentiles OF the
options-implied series (trailing window ending at the report date, cot_feed's min-obs bars
45/140). Differencing the two sides' percentiles is deliberately NOT done - the two rank spaces
differ, so a percentile difference is not an options-implied percentile.

Scope boundary (factual): this is delta-NETTED aggregate positioning. It is not a strike-level
options map - per-strike OI / pin walls are feed I's job, not this feed's.

## Blind wall

Identical to `cot_feed.py` and IMPORTED from it, never re-derived: all COT variants are released
together, Friday 15:30 ET for Tuesday positions (naive report-date keying would leak three days
of future positioning into every Wed/Thu). The 2025 appropriations-lapse handling is replicated
by the same import: publication suspended 2025-10-01 to 2025-11-12, cleared on the CFTC's
accelerated catch-up table (`cot_feed.PUBLICATION_OVERRIDES`, 13 reports,
`publication_confidence="published_schedule"`); the naive Friday rule would have opened a 47-day
leak. During the lapse this feed goes STALE, not silently fresh (age_days tells the agent).

Audit results (2026-07-20, `--audit` + `--selftest`):
- Blind-wall violations: 0 (store-level publication sanity + exhaustive probe walk,
  6 decision times per day over every day 2025-01-01..2026-03-01).
- Wednesday leak check: a Wednesday decision never sees the same-week Tuesday report.
- Shutdown-era leak probes: no lapse-caught report visible at its naive Friday minute.

## Coverage (per gate rules: gaps named, never percentaged)

- Full store: 393 reports, 2019-01-08 .. 2026-07-14 (same year span 2019-2026, same 393 report
  dates as the futures-only store; date sets verified IDENTICAL).
- Required window (2025-01-01..2026-03-01): 60 reports, 2025-01-07 .. 2026-02-24,
  ZERO missing fields on every report.
- Cadence anomalies in the window (named, both also in the futures store, NOT missing weeks):
  - 2025-11-04 -> 2025-11-10: 6-day step (as-of date moved to Monday; Tuesday Nov 11 2025 was
    Veterans Day).
  - 2025-11-10 -> 2025-11-18: 8-day step (the return to Tuesday cadence).
- Market label history: "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE" through 2022-02-01,
  "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE" from 2022-02-08 - identical relabel date in both
  stores; contract code is the stable key.
- Publication confidence in the window: 47 derived (validated rule) + 13 published_schedule
  (the shutdown catch-up table).

## Cross-checks against the futures-only store

- OI cross-check: `open_interest_combined >= open_interest` (futures-only) on ALL 393
  overlapping report dates; 0 violations. (Delta-adjusted options OI is non-negative; a
  violation would indicate a file/contract mismatch and would be named, never dropped.)
- Publication timestamps identical on all 393 shared report dates (variants release together).
- Derived read recomputed independently on every overlapping date in the selftest: exact match.

## Futures vs combined across the walked winter (FACTS ONLY, no interpretation)

Managed-money net (futures-equivalent contracts), each side's own trailing-1y percentile, and
open interest. `mm_net_oi` = managed_money_net_options_implied (combined minus futures-only);
`oi_oi` = open_interest_options_implied. "published" = when the report became visible
(Friday 15:30 ET, or the shutdown catch-up date).

| report_date | published  | mm_net_fut | mm_net_comb | mm_net_oi | pct1y_fut | pct1y_comb | oi_fut    | oi_comb   | oi_oi  |
|-------------|------------|------------|-------------|-----------|-----------|------------|-----------|-----------|--------|
| 2025-11-04  | 2025-12-09 |    -43,986 |     -44,315 |      -329 |     42.45 |      40.57 | 1,576,226 | 1,587,905 | 11,679 |
| 2025-11-10  | 2025-12-10 |    -52,820 |     -52,984 |      -164 |     25.47 |      25.47 | 1,535,138 | 1,548,544 | 13,406 |
| 2025-11-18  | 2025-12-12 |    -59,654 |     -59,648 |        +6 |     21.70 |      21.70 | 1,506,695 | 1,522,819 | 16,124 |
| 2025-11-25  | 2025-12-15 |    -65,346 |     -65,361 |       -15 |     10.38 |      10.38 | 1,493,602 | 1,504,302 | 10,700 |
| 2025-12-02  | 2025-12-17 |    -39,973 |     -39,905 |       +68 |     44.34 |      44.34 | 1,524,306 | 1,535,955 | 11,649 |
| 2025-12-09  | 2025-12-19 |    -31,091 |     -30,862 |      +229 |     53.77 |      53.77 | 1,550,763 | 1,564,010 | 13,247 |
| 2025-12-16  | 2025-12-23 |    -66,328 |     -65,722 |      +606 |      4.72 |       6.60 | 1,574,623 | 1,592,965 | 18,342 |
| 2025-12-23  | 2025-12-29 |   -106,407 |    -105,906 |      +501 |      0.94 |       0.94 | 1,557,649 | 1,575,569 | 17,920 |
| 2025-12-30  | 2026-01-05 |    -83,965 |     -83,730 |      +235 |      4.72 |       4.72 | 1,533,985 | 1,545,577 | 11,592 |
| 2026-01-06  | 2026-01-09 |   -101,384 |    -100,174 |    +1,210 |      2.83 |       2.83 | 1,596,169 | 1,610,205 | 14,036 |
| 2026-01-13  | 2026-01-16 |   -105,134 |    -104,049 |    +1,085 |      2.83 |       2.83 | 1,635,220 | 1,652,342 | 17,122 |
| 2026-01-20  | 2026-01-23 |    -77,101 |     -77,014 |       +87 |     10.38 |      10.38 | 1,614,025 | 1,636,626 | 22,601 |
| 2026-01-27  | 2026-01-30 |    -21,934 |     -21,970 |       -36 |     72.64 |      72.64 | 1,625,943 | 1,646,811 | 20,868 |
| 2026-02-03  | 2026-02-06 |        -47 |        +106 |      +153 |     78.30 |      78.30 | 1,655,983 | 1,676,452 | 20,469 |
| 2026-02-10  | 2026-02-13 |     -8,188 |      -8,128 |       +60 |     78.30 |      78.30 | 1,623,408 | 1,643,074 | 19,666 |
| 2026-02-17  | 2026-02-20 |    -26,765 |     -26,840 |       -75 |     66.98 |      66.98 | 1,613,556 | 1,633,915 | 20,359 |
| 2026-02-24  | 2026-02-27 |    -75,875 |     -75,706 |      +169 |     12.26 |      12.26 | 1,619,531 | 1,630,910 | 11,379 |

Factual observations carried without interpretation:
- The largest walked-winter mm-net divergences are the two most-crowded-short report weeks:
  2026-01-06 (+1,210) and 2026-01-13 (+1,085); every other week is within +/-650.
- 2026-02-03 is the only week where the two sides sit on opposite signs of zero
  (futures -47, combined +106).
- Options-implied OI runs 10,700..22,601 futures-equivalent contracts (0.7-1.4 percent of
  futures OI); its walked-winter maximum, 22,601, is the 2026-01-20 report week.
- The trailing-1y percentiles of each side's own mm net are equal in 14 of 17 weeks; they
  differ on 2025-11-04 (42.45 vs 40.57), 2025-12-16 (4.72 vs 6.60), and match everywhere else.
- On the options-implied series itself, the 2026-01-13 value (+1,085) sits at the 97.17
  trailing-1y percentile of that series (n=53); this is the report visible from Jan 16 15:30 ET.

Latest report VISIBLE at each remaining block open (publication rule, not report date):
- G12 open (Sun 2026-02-01 reopen): report 2026-01-27 (published Fri 2026-01-30 15:30 ET).
- G13 open (Sun 2026-02-15 reopen): report 2026-02-10 (published Fri 2026-02-13 15:30 ET).
- Inside G13, report 2026-02-17 becomes visible Fri 2026-02-20 15:30 ET; report 2026-02-24
  (as-of the day before the Feb 25 expiry pair) publishes Fri 2026-02-27 15:30 ET, the block's
  final session.

Worked asof example (`--asof "2026-01-19 09:30"`, the Monday after the G11 Sunday reopen):
returns report 2026-01-13, publication 2026-01-16T15:30-05:00, age 2.75 days;
managed_money_net_combined -104,049 (pctile_1y 2.83); managed_money_net_options_implied +1,085
(mm long via options +829, mm short via options -256); open_interest_options_implied 17,122;
swap_dealer_net_options_implied +1,780; other_reportable_net_options_implied -4,058.

## Named limits carried forward

- ICE HENRY HUB REMAINS OUT: ICE LD1/penultimate positioning (023391/023392 and ICE's own
  commitments publication) has NO free historical source. This feed closes only the OPTIONS half
  of COT limit #9; the ICE half stays open, carried forward from S97 unchanged.
- The combined report is delta-adjusted and aggregate: no strike-level view, no P/C split, no
  gamma. Strike-level structure is feed I (Databento GLBX options), not this feed.
- Publication cadence is weekly with a 3-day lag (and 35+ days during the 2025 lapse);
  `age_days_combined` states staleness explicitly - during the lapse the feed reads STALE rather
  than silently fresh, by construction.

## Wiring notes for the orchestrator (build boundary respected: nothing wired here)

- `cot_combined_asof(date, contract_code="023651", data_dir=None, futures_data_dir=None)
  -> dict | None`; None = no combined report public yet (UNKNOWN, not flat).
- Every returned key is suffixed (`*_combined` / `*_options_implied`), so merging into
  `cot_asof` output is collision-free by construction. Metadata keys (`report_date_combined`,
  `publication_ts_combined`, `age_days_combined`, ...) are suffixed at return time.
- The derived fields are same-report-date diffs computed inside this module; consumers should
  use them rather than differencing the two feeds' outputs themselves (which could cross
  vintages if the two stores are ever rebuilt at different times).
- `--selftest` re-runs the imported publication-rule/shutdown/blind-wall tests, the suffix and
  derived-diff unit tests, the exhaustive live-store blind-wall walk, the OI cross-check, and a
  full independent recompute of the derived read (all must pass with 0 violations).
