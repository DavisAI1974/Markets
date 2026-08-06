# VOL_REGIME_NOTES_S98 - feed B (vol / range regime), DATA_GATE_S98

Built 2026-07-20. Module `research/kalshi/vol_regime.py`; store `data/vol_regime/vol_regime.json`
(201 KB: per-session table + per-date asof rows + meta with per-basis coverage). Family: tape
conditioner. The feed CONDITIONS magnitude expectations; it never calls direction (Tier 3 usage
doctrine: vol = band scaler, never direction).

WHY (the motivating instances): the brain's magnitude bands were overshot on 1119 (+1700), 1128
(+2340), 1211, 1223 (+2210), 0121 (+3820 vs band 3000), 0130 (+5020 vs 2200) - bands calibrated
in one vol regime were applied in another, with no state variable saying which regime the day
opened in. This store is that state variable, computed strictly from prior sessions.

## 1. Definitions (exact)

- SESSION = one continuous-tape day-file = one UTC calendar day (the walk's own day convention).
  open/close = first/last trade print of the file; verified identical to
  `data/nymex_cont/roll_meta_NG.json` first/last on the days both exist.
- net = (close - open) x 10000 $ per contract (int); range = (high - low) of trade prints x
  10000 $ (int); trades_n = ts-deduplicated trade prints (the codebase's standard count from
  `event_move_baseline.load_cont_day` / the `fast_tape` npz caches - verified equal on 20260118:
  4438 both paths).
- net_sigma_w = population sigma (ddof=0) of session nets over the prior w sessions, $.
- range_w_mean / range_20_max = mean / max session range over the prior window, $.
- range_pctile = share of the prior <=60 sessions' ranges <= the PRIOR session's range, x100
  (the prior session is inside the window, so the floor is 100/n, never 0); actual n in
  range_pctile_n.
- activity_trend = mean(trades_n, prior 5) / mean(trades_n, prior 20).
- BLIND WALL: every value for date D derives ONLY from sessions strictly before D. D's own tape
  is never an input; trailing windows end at the prior session's close.
- MISSING IS EXPLICIT: any window short of its full prior-session count is None with the actual
  count in win_n_5/10/20 (range_pctile is the one by-spec exception: computed on up to 60 with n
  exposed). A basis with no coverage is None-per-field - never zero, never the other basis.
- Two bases, never mixed, field prefixes carry the basis: `n0_*` = NG.n.0 (OI-continuous front,
  `data/nymex_cont_n0/`, the G11+ walk basis); `v0_*` = NG.v.0 (volume-continuous,
  `data/nymex_cont/`, the G3-G10 walk basis).

## 2. Coverage per basis (gaps named)

| basis | local files | valid | span | in-span non-Saturday gaps |
|---|---|---|---|---|
| n0 (NG.n.0) | 102 | 102 | 2025-11-02 .. 2026-02-27 | none |
| v0 (NG.v.0) | 13 | 13 | 2026-01-16 .. 2026-01-30 | none |

Named absences vs the feed span (2025-09-01 .. 2026-02-27):

- n0: 2025-09-01 .. 2025-11-01 - no n0 tape on local disk (the n0 store begins at the Nov 2
  Sunday reopen).
- v0: 2025-09-01 .. 2026-01-15 AND 2026-01-31 .. 2026-02-27 - no local v0 tape. The G3-G10 v0
  corpus lives on S3 only (the S89-S91 year pull); NO AWS credentials were available in this
  build session, so nothing was restored (restore-not-re-pull remains the standing rule). Until
  a restore, every v0 20-session field is None over the whole span (v0 never accumulates 20
  local sessions; win_n_20 tops out at 13) and v0 5-session fields exist only 2026-01-22 ..
  2026-02-27 (stale after 01-31, see caveat 5).
- Saturdays are not sessions (no Globex day-file; Fri 22:00 UTC close -> Sun 23:00 UTC reopen)
  and are excluded from the gap expectation, not counted as gaps.
- Thin HOLIDAY sessions (real data, kept, named): 2025-12-25 (168 trades, Sunday-like reopen
  hour), 2026-01-01 (377, same), 2026-02-16 (Presidents Day, 2,630 - thin but more than the
  reopen hour). Zero-trade files: none.

## 3. Selftest / audit results (2026-07-20)

- (a) Blind-wall audit over the whole store: **0 violations** across 180 dates x 2 bases (6,480
  field recomputes; independent strictly-prior filter + raw-table prev/win checks + full
  field-equality recompute). Build-time integrity assertion additionally pins every session's
  tape ts inside its own UTC day (protects against a mis-dated file).
- (b) Known-day sanity anchor - G9 crest/crash (2025-12-05 .. 12-11): the spec's literal
  late-September base needs v0 Sep/Oct tape, which is not on local disk - NAMED GAP, and the
  base falls back (named, direction-only, no fitted threshold) to the earliest full-20-window
  date, 2025-11-25 (sigma_20 $814, range_20_mean $1,578; window = November sessions). Every
  crest date sits ABOVE on both measures: sigma_20 1.28-1.68x, range_20_mean 1.09-1.24x. PASS.
  Note the fallback base is CONSERVATIVE: late November already contains G8 winter action
  (1119, 1121, 1125), so the true September contrast would be larger, not smaller.
- (c) Missing-basis explicitness at 2025-11-15 (n0 live 12 sessions, v0 zero): all v0 fields
  None with win_n 0, n0 sigma_10 populated, and the partial-window rule shown on the same row
  (n0_net_sigma_20 = None with win_n_20 = 12). Staleness visibility: asof 2026-02-10 carries
  v0_prev_date 2026-01-30 with v0_prev_age_days 11 - a dead basis is visible, not silent. PASS.

## 4. The walked winter's vol arc (n0, factual per-date reads from the store)

Season anchors (asof-date state; sigma/range in $ per contract):

| asof | net_sigma_20 | range_20_mean | range_20_max | activity_trend |
|---|---|---|---|---|
| 2025-11-25 | 814 | 1578 | 2740 | 1.686 |
| 2025-12-01 | 1015 | 1654 | 2880 | 1.305 |
| 2025-12-10 | 1366 | 1955 | 4690 | 1.037 |
| 2026-01-02 | 1016 | 1382 | 2810 | 1.006 |
| 2026-01-16 | 798 | 1302 | 2630 | 1.324 |
| 2026-01-30 | 1240 | 2104 | 4680 | 1.456 |
| 2026-02-02 | 1592 | 2346 | 6070 | 1.351 |
| 2026-02-09 | 1825 | 2666 | 6070 | 0.803 |
| 2026-02-13 | 1812 | 2630 | 6070 | 0.564 |
| 2026-02-18 | 1617 | 2216 | 6070 | 0.260 |
| 2026-02-27 | 680 | 1378 | 2840 | 0.758 |

The read, factually: vol built into the G9 crest/crash (814 -> 1366), cooled through January to
the walked winter's MINIMUM on exactly the G11 open (2026-01-16 sigma_20 = 798, range_20_mean =
1302 - the lowest 20-session state in the store), then the G11 squeeze drove it to the arc's
maximum two weeks later (1825 on 02-09), followed by a February collapse (680 by 02-27, with
activity_trend bottoming at 0.260) - G12/G13 open in a regime the January tape does not
resemble. Bands calibrated on the walk's November-January sessions were applied on a block that
opened at the winter's vol floor and finished 2x above it: that is the miss mechanism this feed
exists to expose, stated here as state, not as a rule.

G9 crest/crash window (n0; prev_* = the prior session):

| asof | prev_date | prev_net | prev_trades | sigma_5 | sigma_20 | range_5_mean | range_20_mean | range_pctile | act_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2025-12-01 | 11-30 Sun | -590 | 1916 | 1441 | 1015 | 1890 | 1654 | 20.0 | 1.305 |
| 2025-12-02 | 12-01 | +890 | 70192 | 1003 | 1019 | 1702 | 1684 | 61.5 | 1.141 |
| 2025-12-03 | 12-02 | -710 | 57030 | 1120 | 1036 | 1656 | 1752 | 55.6 | 1.068 |
| 2025-12-04 | 12-03 | +1520 | 61928 | 1187 | 1060 | 1830 | 1748 | 78.6 | 1.273 |
| 2025-12-05 | 12-04 | +1100 | 63862 | 915 | 1042 | 1802 | 1726 | 82.8 | 1.374 |
| 2025-12-08 | 12-07 Sun | +130 | 347 | 1094 | 1149 | 2288 | 1832 | 12.9 | 1.457 |
| 2025-12-09 | 12-08 | -2910 | 19867 | 1840 | 1328 | 2654 | 1896 | 96.9 | 1.283 |
| 2025-12-10 | 12-09 | -1340 | 16773 | 1864 | 1366 | 2588 | 1955 | 45.5 | 1.037 |
| 2025-12-11 | 12-10 | +30 | 14674 | 1771 | 1323 | 2368 | 1918 | 26.5 | 0.807 |
| 2025-12-12 | 12-11 | -1440 | 15577 | 1117 | 1371 | 1786 | 1928 | 51.4 | 0.338 |
| 2025-12-15 | 12-14 Sun | +240 | 201 | 803 | 1363 | 1360 | 1838 | 2.7 | 0.347 |

G11 window (n0). The state moves DURING the block - by 0122 the open's floor regime is already
gone, well before the 0130 +5020 print:

| asof | prev_date | prev_net | prev_trades | sigma_5 | sigma_20 | range_5_mean | range_20_mean | range_pctile | act_trend |
|---|---|---|---|---|---|---|---|---|---|
| 2026-01-16 | 01-15 | -250 | 28501 | 765 | 798 | 1540 | 1302 | 45.0 | 1.324 |
| 2026-01-19 | 01-18 Sun | -10 | 2232 | 614 | 788 | 1372 | 1290 | 16.7 | 1.178 |
| 2026-01-20 | 01-19 | +550 | 22306 | 642 | 784 | 1464 | 1324 | 63.3 | 1.114 |
| 2026-01-21 | 01-20 | +1930 | 72962 | 774 | 916 | 1636 | 1465 | 96.7 | 1.251 |
| 2026-01-22 | 01-21 | +3820 | 107636 | 1440 | 1270 | 2282 | 1639 | 98.3 | 1.616 |
| 2026-01-23 | 01-22 | -170 | 120525 | 1494 | 1270 | 2658 | 1713 | 93.3 | 1.945 |
| 2026-01-26 | 01-25 Sun | +180 | 4267 | 1424 | 1209 | 3070 | 1789 | 65.0 | 2.113 |
| 2026-01-27 | 01-26 | -620 | 118639 | 1586 | 1213 | 2958 | 1876 | 88.3 | 2.077 |
| 2026-01-28 | 01-27 | -260 | 92833 | 611 | 1210 | 2538 | 1965 | 81.7 | 1.807 |
| 2026-01-29 | 01-28 | -400 | 80626 | 634 | 1209 | 2592 | 2051 | 93.3 | 1.560 |
| 2026-01-30 | 01-29 | +1480 | 79466 | 749 | 1240 | 2488 | 2104 | 68.3 | 1.456 |
| 2026-01-31 | 01-30 | +5020 | 115578 | 2124 | 1618 | 3324 | 2366 | 100.0 | 1.730 |

The two bases through the same window (why they must never be mixed): v0's 0121 session is the
FEBRUARY contract's squeeze day, net +11,940 (146k trades), where the walked n0 basis prints
+3,820 - so asof 2026-01-27 the 5-session sigma reads $4,734 on v0 vs $1,586 on n0, a 3.0x
divergence from the SAME calendar window. Both are true of their own series; neither substitutes
for the other. (This is the S97 v0-whipsaw finding surfacing inside a state variable: v0's
day-to-day instrument identity flipped 1000 <-> 1021 through expiry week per roll_meta_NG.json,
while each single session is internally one instrument, so per-session net/range are real - it
is the cross-session AGGREGATES on v0 through that week that carry mixed-instrument magnitudes.)

## 5. Honest caveats

1. SESSION-BOUNDARY DEFINITION: a session is the UTC calendar-day file. The 23:00-24:00 UTC
   hour of file D (18:00-19:00 ET) belongs to the exchange session dated D+1; open->close of a
   weekday file therefore spans two exchange sessions' edges. This is the walk's own day
   convention (the S94 block-start actual-last-hour anchor; roll_meta first/last matches it) -
   consistency with the walk was chosen over exchange-session purity, and the choice is
   disclosed, not hidden.
2. SUNDAYS AND MONDAY READS: Sundays are real one-hour reopen sessions (17 of them; median 612
   trades, median range $560, vs non-Sunday medians 25,033 and $1,780). They are DATA, not
   gaps - but a Monday's prev_* fields describe that one-hour session, so range_pctile after a
   Sunday reads structurally low (12-08: 12.9; 12-15: 2.7) and prev_net is a reopen-hour net.
   The reader conditions on prev_date/prev_trades, which expose it. The same applies after the
   three named thin holiday sessions (2025-12-25, 2026-01-01, 2026-02-16). Sunday nets also sit
   inside the sigma windows on equal footing with full sessions - the session is the unit here;
   that damping is part of the definition, not an error.
3. TRAILING sigma_20 is a 20-session (about 3.5-week) lag-smoothed state: it confirms a regime
   shift only as fast sessions enter the window (sigma_5 and range_pctile are the fast reads;
   0122's sigma_5 jump 774 -> 1440 leads sigma_20's grind 916 -> 1270). Nothing here nowcasts
   the current day - by design, that is the blind wall.
4. V0 IS A LOCAL STUB: 13 sessions. All its 20-window fields are None over the whole span and
   its 5-window fields exist for nine asof dates only. Its aggregates through expiry week carry
   the mixed-instrument caveat above. Treat v0_* as the G3-G10-basis placeholder awaiting an S3
   restore, not as a populated feed.
5. STALENESS: after 2026-01-31 v0 values freeze at the 2026-01-30 state; v0_prev_age_days grows
   and is the exposure (11 by 02-10). n0_prev_age_days is 1-2 in normal operation (2 after
   Saturdays).
6. trades_n counts ts-DEDUPLICATED trade prints (exact-duplicate timestamps collapse, keep
   last) - the same convention as every existing consumer of these loaders; it slightly
   undercounts raw prints and is internally consistent across both bases and with the
   fingerprint files' scale.
7. NOT BUILT (named, deliberate): (i) intraday realized vol (e.g. n-minute bar RV) - the range
   fields are this feed's intraday-amplitude carriers; a bar-RV extension would be additive on
   the same store; (ii) legs-per-session - DATA_GATE feed B names it as part of the activity
   metric, but it requires the move detector and already exists per walked day in
   `renders/ng_refine_s95/fingerprints.json`; joining it is wiring-pass work, recomputing it
   here would duplicate the tool. trades_n and activity_trend are this build's activity
   metrics; (iii) a settle-based September base from `data/nymex_curve/NG_curve.json` -
   settle-to-settle sigma is a DIFFERENT definition than session open->close nets and was not
   silently substituted.
8. Population sigma (ddof=0). At w=5 a sample-sigma convention would read ~12 percent higher;
   the convention is fixed and disclosed, and comparisons inside the store are like-for-like.

## 6. Wiring notes (for the orchestrator's second serial pass)

`from vol_regime import vol_regime_asof; vol_regime_asof(date) -> dict | None` - store-read
only, never touches tape, no chdir, safe to import from `forecast_harness`. None when the store
is absent or the date is outside 2025-09-01 .. 2026-02-27. All fields additive under the n0_/v0_
prefixes; nothing existing is renamed. The selftest (`python research/kalshi/vol_regime.py
--selftest`) re-audits the blind wall over the built store and must print 0 violations.
