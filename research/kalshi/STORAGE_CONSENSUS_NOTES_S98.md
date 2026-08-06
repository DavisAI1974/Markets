# STORAGE CONSENSUS NOTES - S98 (DATA_GATE_S98 feed D)

Build date 2026-07-20. Builder: feed D subagent (STEP C discipline, AGENT_RUNBOOK_S95).
Store: `data/storage_consensus/storage_consensus.json` (+ `raw/te_extract.json` provenance).
Module: `research/kalshi/storage_consensus.py`, `storage_consensus_asof(date) -> dict | None`.
Selftest: PASS, blind-wall violations 0 (store audit + daily sweep 2025-08-15..2026-03-15).

WHY (from the gate spec): the market prices actual-minus-SURVEY-CONSENSUS, not
actual-minus-5yr-proxy. The motivating instance re-measured: on 2026-01-29 the print was -15.2
Bcf vs the SEASONAL comparison; vs the surveyed consensus it was -10 (as-printed -242 vs TE
consensus -232; FF had -237, NGI -238, so -4..-10 across houses). The seasonal proxy and the
street number tell materially different stories on several walked print days (see table).

This feed is an INPUT. Nothing here scores whether consensus "works"; disagreeing sources are
carried side by side, never averaged; missing weeks are None and named.

---

## 1. Sources USED (all point-in-time archived; per-row URLs in the store)

1. **TradingEconomics calendar via Wayback** (primary for coverage, mechanical choice - it is
   the only house with rows for every week). The page was crawled near-DAILY at ~06:20-10:00
   UTC (01:20-05:00 ET) through the window, i.e. strictly PRE-print on print mornings. Each
   snapshot shows the upcoming release row (consensus posted, actual blank = pre-print proof)
   plus the prior ~2 releases with actuals. 51 snapshots fetched; extraction in
   `raw/te_extract.json`. Two values derived per week: `consensus_pre_print_bcf` (latest
   strictly-pre-print capture, with its timestamp) and the final frozen consensus
   (`consensus_chg_bcf`, from the first post-print capture, verified byte-identical across all
   later snapshots - 0 instabilities).
2. **investing.com event page 386 via Wayback** (second house). Old server-rendered mirrors
   carry 6-row history tables: mx.investing.com 2025-10-01 (pre-print for Oct 2),
   es.investing.com 2025-10-23 06:14 ET (pre-print print-morning), www 2025-12-04 (Nov 6-Dec 4
   rows). The 2026 React build carries only the latest-release header (Feb 19, Feb 26, Mar 5
   captures). Live cross-validation: the current live page's Jul 2026 rows exactly match our own
   ForexFactory collector's forward polls (fc 45B / prev 61B for Jul 16) - the page displays
   genuine survey consensus.
3. **ForexFactory via Wayback** (third house). Event page `/calendar/26-us-natural-gas-storage`
   snapshot 2026-01-29 18:19 UTC carries an 8-row history table (Dec 11 - Jan 29) with
   consensus + as-printed actuals. Weekly-calendar snapshots give strictly-pre-print captures
   for Dec 4 (-18, Wed Dec 3) and Dec 29 (-169, Sun Dec 28). FF event datelines (epoch)
   independently confirm every holiday-shifted print datetime.
4. **Natural Gas Intelligence (NGI)** via Wayback: storage preview published 2026-01-26 2:29 pm
   ET - NGI house forecast -238 for the Jan 29 print (strictly pre-print).
5. **S&P Global Platts survey** for the record Feb 5 print: consensus -366, obtained SECONDARY
   via indexbox.io (pub. 2026-02-06) quoting the survey. Named individual estimates for the same
   week from NGI coverage: Celsius Energy -370, GasFundies -414 (published ~Jan 21, early-week
   projections, strictly pre-print but 15 days early).
6. **EIA release schedule** (https://ir.eia.gov/ngs/schedule.html): print datetimes. Normal rule
   Thursday 10:30 ET. In-window exceptions verbatim: Nov 14 2025 Fri 10:30 (Veterans Day),
   Nov 26 2025 Wed 12:00 (Thanksgiving), Dec 29 2025 Mon 12:00 (Christmas, marked "Updated"),
   Dec 31 2025 Wed 12:00 (New Year's Day). No Jan/Feb 2026 exceptions (MLK and Presidents Day
   Mondays did NOT shift prints - confirmed against TE/FF release rows, not assumed). Note the
   asymmetry: a Tuesday holiday (Veterans Day) DELAYED the release to Friday; Thursday holidays
   moved it to Wed 12:00 (or Mon 12:00 after Christmas). The Christmas week produced a
   DOUBLE-PRINT week: Mon Dec 29 (week ending Dec 19) and Wed Dec 31 (week ending Dec 26).

## 2. Sources REJECTED (with why)

- **MQL5 calendar**: its "forecast" column is irreconcilable with any analyst survey (-16B for
  an August injection week; 121B where every house was ~80) - evidently their own algorithmic
  forecast. Rejected for consensus use. (Its actuals did match the as-printed values.)
- **myfxbook**: HTTP 403 to fetch; no usable Wayback coverage.
- **investing.com live "more-history" AJAX**: Cloudflare challenge; unreachable for scripted
  retrieval. Superseded by Wayback snapshots.
- **faireconomy.media FF JSON mirror** (the feed consensus_poll.py polls): zero Wayback
  coverage - no history exists.
- **Our own collector store** (`consensus.jsonl.gz` on branch `data/kalshi-bins`): checked;
  it only began accruing 2026-07-12 - nothing for the winter (confirms the eia_surprise.py
  docstring: consensus is only obtainable FORWARD from our collector).
- **FF weekly-calendar snapshots Nov 9 / Nov 25 / Jan 11 / Feb 24**: fetched; the NG forecast
  cell was EMPTY at capture (FF posts the storage forecast late in the week). Only the Dec 3 and
  Dec 28 calendar captures carried values.
- **fr.investing.com 2025-10-25 snapshot**: fetched, table present, but es/mx already covered
  those weeks; not extracted (French date format).
- **Reuters weekly storage poll**: paywalled/not directly fetchable; its numbers surface only in
  secondary snippets. The Desk (LDC survey) likewise paywalled and unarchived. Both remain the
  NAMED GAP for n_estimates and formal survey ranges (see caveats).
- **TradingEconomics API historical consensus**: paid tier - not used (free + Databento rule).

## 3. Per-week coverage (the store's audit table; `--audit` reproduces it)

consensus = final frozen headline (TE); pre = strictly-pre-print captured value (None = no
pre-print snapshot evidence exists, named); printed = actual as printed (archives, mutually
consistent across houses on every overlap); cur = current-vintage EIA series
(data/eia_surprise.json).

| print (actual date) | dow/ET | report wk | consensus | pre | printed | cur | houses |
|---|---|---|---|---|---|---|---|
| 2025-08-21 | Thu 10:30 | 08-15 | +22 | None | +13 | +13 | TE (bonus row, pre-walk) |
| 2025-08-28 | Thu 10:30 | 08-22 | +26 | None | +18 | +18 | TE (bonus row, pre-walk) |
| 2025-09-04 | Thu 10:30 | 08-29 | +54 | +54 | +55 | +45 | TE, investing |
| 2025-09-11 | Thu 10:30 | 09-05 | +68 | +66 | +71 | +71 | TE, investing |
| 2025-09-18 | Thu 10:30 | 09-12 | +81 | None | +90 | +90 | TE, investing |
| 2025-09-25 | Thu 10:30 | 09-19 | +75 | +76 | +75 | +76 | TE, investing |
| 2025-10-02 | Thu 10:30 | 09-26 | +67 | +66 | +53 | +52 | TE, investing (pre, D-1) |
| 2025-10-09 | Thu 10:30 | 10-03 | +76 | +76 | +80 | +80 | TE, investing |
| 2025-10-16 | Thu 10:30 | 10-10 | +81 | +76 | +80 | +81 | TE, investing |
| 2025-10-23 | Thu 10:30 | 10-17 | +83 | +78 | +87 | +86 | TE, investing (pre, print-morning) |
| 2025-10-30 | Thu 10:30 | 10-24 | +71 | +71 | +74 | +74 | TE only |
| 2025-11-06 | Thu 10:30 | 10-31 | +34 | None | +33 | +33 | TE, investing |
| 2025-11-14 | FRI 10:30 | 11-07 | +34 | None | +45 | +45 | TE, investing |
| 2025-11-20 | Thu 10:30 | 11-14 | -12 | None | -14 | -14 | TE, investing |
| 2025-11-26 | WED 12:00 | 11-21 | -1 | -5 | -11 | -12 | TE (pre, print-morning), investing |
| 2025-12-04 | Thu 10:30 | 11-28 | -18 | -18 | -12 | -11 | TE, investing, FF - three-way EXACT |
| 2025-12-11 | Thu 10:30 | 12-05 | -165 | -170 | -177 | -178 | TE, FF |
| 2025-12-18 | Thu 10:30 | 12-12 | -169 | None | -167 | -166 | TE, FF |
| 2025-12-29 | MON 12:00 | 12-19 | -168 | -169 | -166 | -168 | TE, FF (both pre-print) |
| 2025-12-31 | WED 12:00 | 12-26 | -53 | None | -38 | -37 | TE, FF |
| 2026-01-08 | Thu 10:30 | 01-02 | -114 | None | -119 | -120 | TE, FF |
| 2026-01-15 | Thu 10:30 | 01-09 | -90 | None | -71 | -70 | TE, FF |
| 2026-01-22 | Thu 10:30 | 01-16 | -106 | None | -120 | -120 | TE, FF - DISAGREE 16 (see 4) |
| 2026-01-29 | Thu 10:30 | 01-23 | -232 | -232 | -242 | -241 | TE (pre, print-morning), FF, NGI (pre) |
| 2026-02-05 | Thu 10:30 | 01-30 | -374 | -379 | -360 | -359 | TE (pre, print-morning), Platts, Celsius, GasFundies |
| 2026-02-12 | Thu 10:30 | 02-06 | -257 | -256 | -249 | -252 | TE only (pre, print-morning) |
| 2026-02-19 | Thu 10:30 | 02-13 | -146 | None | -144 | -143 | TE, investing |
| 2026-02-26 | Thu 10:30 | 02-20 | -36 | None | -52 | -52 | TE, investing |
| 2026-03-05 | Thu 10:30 | 02-27 | -121 | None | -132 | -131 | TE, investing |

GAPS, named individually (never a percentage):
- No week Sep 2025 - Mar 2026 is missing a consensus value (29/29 present incl. 2 bonus Aug).
- Weeks with NO strictly-pre-print capture (consensus known only from the frozen post-print
  display; the number itself was public pre-print, our EVIDENCE of it is post-print):
  2025-08-21, 2025-08-28, 2025-09-18, 2025-11-06, 2025-11-14, 2025-11-20, 2025-12-18,
  2025-12-31, 2026-01-08, 2026-01-15, 2026-01-22, 2026-02-19, 2026-02-26, 2026-03-05.
- Weeks with a SINGLE house only: 2025-08-21, 2025-08-28, 2025-10-30, 2026-02-12.
- n_estimates: None on every week (no free archived source carries the analyst count).
- range_low/range_high: None on every week (no formal survey range obtainable free); the
  2026-02-05 record week carries three NAMED individual estimates instead (-366 Platts survey,
  -370 Celsius Energy, -414 GasFundies).
- G-block print days all covered: G7 (Nov 6, Nov 14), G8 (Nov 20, Nov 26), G9 (Dec 4, 11, 18,
  29, 31), G10 (Jan 8, 15), G11 (Jan 22, 29), G12 (Feb 5, 12), G13 (Feb 19, 26).

## 4. Cross-check results (per week, honest, nothing averaged away)

Requirement was two independent sources on three weeks; 25 of 29 weeks have >=2 houses.
Highlights, exact values:

- **Three-way EXACT agreement**: 2025-12-04 (-18 TE pre-print, -18 FF pre-print Dec 3, -18
  investing). Exact two-way: Sep 4 (54/54), Oct 9 (76/76), Nov 6 (34/34), Nov 14 (34/34),
  Nov 20 (-12/-12), Feb 26 (-36/-36).
- **Largest house DISAGREEMENT: 2026-01-22, TE -106 vs FF -90 (16 Bcf).** Both carried in the
  store; the headline field is TE by the mechanical coverage rule, with
  `house_disagreement_bcf=16` exposed. Printed -120: beyond both houses, but by very different
  margins (-14 vs -30) - exactly the ambiguity this feed exists to expose, left to the agent.
- Other divergences: Dec 18 (TE -169 vs FF -176, 7), Jan 8 (-114 vs -109, 5), Jan 29 (TE -232,
  FF -237, NGI -238; spread 6), Feb 5 (TE -374 vs Platts -366, 8; individuals -370/-414),
  Dec 31 (-53 vs -51), Feb 19 (TE -146 vs investing -148), Mar 5 (-121 vs -122), Sep 11
  (TE 68 vs investing 69), Sep 18 (81 vs 80).
- **Pre-vs-final within TE** (consensus still moving in the final pre-print hours): Oct 16
  76->81, Oct 23 78->83, Nov 26 -5->-1, Dec 11 -170->-165, Feb 5 -379->-374, Sep 11 66->68,
  Oct 2 66->67, Sep 25 76->75, Dec 29 -169->-168. Weeks where print-morning pre == final:
  Sep 4, Oct 9, Oct 30, Dec 4, Jan 29 (identical -232 at 02:29 ET and after).
- **Mechanical observation** (not a quality score): where a pre-print investing capture exists
  it MATCHES TE's pre value exactly (66, 78, -5, -18), and investing's displayed final often
  stays at that earlier value where TE's final moved (Oct 16: inv 76 vs TE 81; Oct 23: inv 78
  vs TE 83) - consistent with different update cadences across aggregators.
- **As-printed actuals**: TE, investing, and FF agree EXACTLY on every one of the 13
  overlapping weeks; EIA Today in Energy independently confirms Feb 5 printed -360 ("stocks
  fell 360 Bcf... largest weekly net withdrawal in WNGSR history"; prior record -359 wk-ending
  2018-01-05).

## 5. Honest caveats

1. **Post-print capture of "final" consensus.** For 14 named weeks the only evidence of the
   consensus is the frozen value displayed on post-print snapshots. Freeze behavior was
   verified programmatically (consensus/actual never change across any later snapshot - 0
   instabilities across 51 TE snapshots), but "frozen at print" vs "backfilled at print"
   cannot be distinguished from archives alone. The strictly-pre-print values (15/29 weeks,
   timestamped) are the blind-clean evidence; `final_capture_is_post_print` flags the rest.
2. **Consensus moves pre-print.** The TE pre-vs-final deltas (up to 5 Bcf, listed above) show
   the survey number updating into the print. A print-morning ~02:30 ET snapshot is the state
   then, not necessarily the 10:29 ET state. Nothing in the store claims otherwise.
3. **"The" consensus is plural.** TE/investing/FF are aggregators with undisclosed survey
   provenance; Platts/Reuters/WSJ/NGI run their own surveys; desks watch The Desk's LDC
   survey. What the market "was positioned against" is a distribution across houses (Jan 22
   spans 16 Bcf). Per-source rows are the primitive; the headline TE pick is mechanical
   (coverage), stated in `_meta` and here. Reuters/The Desk histories remain the named
   unobtainable gap (paywalled, unarchived).
4. **Vintage.** As-printed actuals differ from the current EIA API series on 17 of 29 weeks
   (usually 1-3 Bcf; 2025-09-04 by +10: printed +55 - corroborated by TE, investing, and MQL5
   independently - vs +45 in today's series; also note the Nov 26/Dec 4 pair CROSSES: printed
   -11/-12 vs current -12/-11). Both `surprise_vs_consensus_bcf` (current vintage, per the
   feed spec's join instruction) and `surprise_as_printed_vs_consensus_bcf` (the number the
   market compared at 10:30) are exposed; the store carries `vintage_diff_bcf` per week.
   Feed K owns the full vintage audit; these weeks are corroborating evidence for it.
5. **Platts row is secondary-sourced** (IndexBox quoting the survey, published Feb 6). The
   Celsius/GasFundies numbers are early-week projections published ~Jan 21 for the week then
   in progress - genuinely pre-print but 15 days early; labeled as such in their rows.
6. **2026-02-26 near-miss**: the investing crawl at 10:29 ET (one minute pre-print) shows only
   the PRIOR release's header - no pre-print capture of that week's own consensus exists.
7. **Bonus rows** 2025-08-21/28 predate the requested window (kept; labeled).
8. Raw provenance: every store row carries its Wayback/article URL (the archive is the durable
   evidence store); the TE extraction JSON is copied to `data/storage_consensus/raw/`. Fetched
   HTML lives only in the session scratchpad (re-fetchable from the named URLs).

## 6. Blind wall (exact mechanics, as implemented)

- Consensus for an upcoming print is PUBLIC before the print (surveys publish Tue/Wed), so
  `next_print` on a print-day morning carries that day's consensus - per the feed spec.
- The print's ACTUAL lands at the print datetime (Thu 10:30 ET; four named holiday shifts from
  EIA's schedule, each independently confirmed by FF epoch datelines and TE/investing release
  rows). `next_print` never carries actual/surprise/vintage fields, and post-print-captured
  per-source rows have the page-displayed actual STRIPPED so a print's own number can never
  reach its own morning. `last_print` (strictly before D) carries the realized actual
  (read-only join from data/eia_surprise.json) + both surprises.
- Assertions run inside every `storage_consensus_asof` call; `--selftest` audits the whole
  store (schedule fields, per-source pre_print timestamps vs print datetimes) plus a daily
  sweep 2025-08-15..2026-03-15, and prints the violation count: **0**.
- Source-level schedule check at build time: across all 51 TE snapshots, no snapshot captured
  BEFORE a print datetime ever shows that print's actual (0 hits) - which independently
  validates the four holiday-shift datetimes (a wrong shift would have surfaced as a
  "pre-print" snapshot containing an actual).

## 7. For the orchestrator (not done here, per STEP C rules)

- Wire `storage_consensus_asof` into `forecast_harness.py::decision_state` in the serial pass.
- `KALSHI_TRADING.md` index entry (builders do not touch existing files).
- The store ends at the 2026-03-05 print; forward accrual now exists via consensus_poll.py
  (running since 2026-07-12) but there is a NAMED HOLE Mar 2026 - Jul 2026 if the walk ever
  extends there.
- eia_surprise.py's KXNATGASD release keys are NOMINAL Thursdays (its `next_weekday_after`
  mapping); this store carries both `nominal_release_date` (join key, matching eia_surprise)
  and the true `print_date`/`print_datetime_utc`. Any join by release date must pick the right
  key - the four holiday weeks differ.

---

# S101 EXTENSION - THE FORWARD HOLE CLOSED (Mar 2026 - Jul 2026)

Build date 2026-07-21. Builder: STEP-C data-feed extension agent. The section-7 NAMED HOLE
(prints after 2026-03-05 with no consensus rows, consensus_poll.py live only since
2026-07-12) is closed: 18 records appended, prints 2026-03-12 .. 2026-07-09 (report weeks
2026-03-06 .. 2026-07-03). Store now 47 reports, consensus 47/47. Pre-existing 29 records
byte-unchanged (asserted against the S3 copy `consensus/storage_consensus.json` at write
time). Selftest PASS, blind-wall violations 0; the daily sweep was extended to
2025-08-15..2026-07-19 to cover the new span.

## Schedule

EIA schedule page (re-fetched 2026-07-21) lists NO exceptions Mar-Jul 2026: Memorial Day is
a Monday (never shifts), Juneteenth 2026 falls Friday, July 4 falls Saturday. All 18 prints
are normal Thu 10:30 ET (EDT -> 14:30Z). Independently confirmed three ways: (a) zero
pre-print TE snapshots showing an actual across all 61 snapshots (the S98 leak test,
re-run); (b) investing.com occurrence_time = T14:30:00Z on every hole print; (c) the TE
first-post-print snapshot dates.

## Sources

1. **TradingEconomics via Wayback** (primary, same near-daily ~06:22 UTC crawl as S98):
   61 unique snapshots 2026-03-06 .. 2026-07-10 fetched and extracted
   (`raw/te_extract_s101_hole.json`). Final frozen consensus recovered for all 18 weeks
   (frozen verified: single value across every post-print snapshot, 0 instabilities);
   strictly-pre-print print-morning captures for 9 weeks (Mar 12, Mar 26, Apr 2, Apr 23,
   May 21, Jun 4, Jun 11, Jun 25, Jul 2 -- see table).
2. **investing.com via Wayback** (second house, ALL 18 weeks). THE NEW FIND: the 2026 React
   build embeds a full `occurrences` history array (forecast + actual per past release), not
   just the latest-release header the S98 build could read. Snapshots 20260604145143
   (rows through Jun 4), 20260611151155 (through Jun 11), and 20260721002122 (through
   Jul 16; this build triggered the Wayback save) cover every hole week
   (`raw/investing_extract_s101_hole.json`). Forecast values frozen across snapshots on
   every overlap. Cross-validation is embedded in the 0721 snapshot itself: its Jul 16
   forecast 45B equals our own consensus_poll collector row (the S98 live-route check, now
   archived).
3. **ForexFactory: structurally DEAD for this window** -- zero Wayback captures of the event
   page or usable weekly-calendar pages Mar-Jul 2026 (CDX empty). Named gap, not proxied.
4. EIA schedule page + `data/eia_surprise.json` (read-only) for current-vintage actuals.

## Per-week table (consensus = TE final frozen; pre = strictly-pre-print TE capture;
inv = investing.com forecast; printed = as-printed actual, TE and investing identical on
all 18; cur = current vintage)

| print | report wk | consensus | pre | inv | dis | printed | cur |
|---|---|---|---|---|---|---|---|
| 2026-03-12 | 03-06 | -42 | -42 (print-morning) | -42 | 0 | -38 | -38 |
| 2026-03-19 | 03-13 | 31 | None | 39 | 8 | 35 | 34 |
| 2026-03-26 | 03-20 | -44 | -49 (print-morning) | -49 | 5 | -54 | -54 |
| 2026-04-02 | 03-27 | 34 | 38 (print-morning) | 38 | 4 | 36 | 33 |
| 2026-04-09 | 04-03 | 46 | None | 41 | 5 | 50 | 49 |
| 2026-04-16 | 04-10 | 51 | None | 55 | 4 | 59 | 60 |
| 2026-04-23 | 04-17 | 94 | 96 (print-morning) | 96 | 2 | 103 | 103 |
| 2026-04-30 | 04-24 | 80 | None | 83 | 3 | 79 | 79 |
| 2026-05-07 | 05-01 | 74 | None | 72 | 2 | 63 | 63 |
| 2026-05-14 | 05-08 | 85 | None | 86 | 1 | 85 | 85 |
| 2026-05-21 | 05-15 | 95 | 96 (print-morning) | 96 | 1 | 101 | 101 |
| 2026-05-28 | 05-22 | 96 | None | 96 | 0 | 92 | 92 |
| 2026-06-04 | 05-29 | 101 | 99 (print-morning) | 99 | 2 | 95 | 95 |
| 2026-06-11 | 06-05 | 101 | 101 (print-morning) | 101 | 0 | 108 | 108 |
| 2026-06-18 | 06-12 | 75 | None | 82 | 7 | 73 | 73 |
| 2026-06-25 | 06-19 | 74 | 67 (print-morning) | 67 | 7 | 76 | 76 |
| 2026-07-02 | 06-26 | 81 | 81 (print-morning) | 81 | 0 | 87 | 87 |
| 2026-07-09 | 07-03 | 49 | None | 60 | 11 | 61 | 61 |

## Gaps, named individually

- NO week in the hole is missing a consensus (18/18 recovered, two houses on every week).
- Weeks with no strictly-pre-print capture (final known only from the frozen post-print
  display): 2026-03-19, 2026-04-09, 2026-04-16, 2026-04-30, 2026-05-07, 2026-05-14,
  2026-05-28, 2026-06-18, 2026-07-09.
- n_estimates / range_low / range_high: None on every week (unchanged S98 gap; Reuters /
  The Desk histories remain paywalled and unarchived).
- ForexFactory third house: unobtainable for the whole window (zero Wayback coverage).
- The investing.com rows are all POST-print captures (frozen-forecast evidence); the only
  strictly-pre-print evidence in the window is TE's.

## Cross-check observations (nothing averaged)

- The S98 mechanical observation REPRODUCES: on every week where a TE print-morning
  pre-print value exists alongside investing's frozen forecast, the two are IDENTICAL
  (-42, -49, 38, 96, 96, 99, 101, 67, 81 -- 9/9), while TE's final sometimes moves after
  the morning capture (Mar 26 -49 -> -44; Apr 2 38 -> 34; Jun 25 67 -> 74). Consistent
  with investing freezing an earlier survey state; the houses are NOT independent draws.
- Largest house disagreement: 2026-07-09, TE 49 vs investing 60 (11 Bcf); print 61.
  Also 2026-03-19 (8), Jun 18 / Jun 25 (7 each).
- As-printed actuals: TE and investing agree exactly on all 18; current vintage differs on
  4 (Mar 19 +1, Apr 2 +3, Apr 9 +1, Apr 16 -1), zero on the other 14.

## Caveats

1. Same S98 caveat class applies: for the 9 no-pre-capture weeks the consensus evidence is
   the frozen post-print display (freeze verified programmatically, 0 instabilities).
2. investing.com occurrences `forecast` is taken as that house's final consensus; on every
   S98-era overlap it matches the values the S98 build extracted from server-rendered
   mirrors (e.g. Jan 22 -90 = FF -90; Mar 5 -122; Feb 19 -148), corroborating the field.
3. The 2026-06-04 record carries TE final 101 vs its own print-morning 99 -- the pre-vs-
   final movement class documented in S98, carried as-is.
