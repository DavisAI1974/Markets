# GRID STACK FEED - BUILDER NOTES (feed Q, S99, built 2026-07-20)

Module: `research/kalshi/grid_stack.py`. Store: `data/grid_stack/grid_stack.json.gz` (2,758 days
2019-01-01 -> 2026-07-20, 7 respondents x fuel mix + demand + day-ahead forecast), S3 prefix
`grid_stack/`. Wired as decision_state block `grid_stack`; audit class `grid_wall`. Module
selftest PASS; harness selftest PASS; audit 0 violations / 101 days, present on all 101.

## WHAT IT IS

EIA-930 daily per-BA state: demand (loads - Greg's direct ask), the BA's own DAY-AHEAD DEMAND
FORECAST (type DF - leading information EIA republishes free; a quiet find of this build),
generation by fuel (gas/solar/wind/coal/nuclear), gas + solar shares, 7d changes, and for US48
the labeled power-burn ESTIMATE (gas MWh x 7,900 Btu/kWh STEO-implied heat rate / 1.035e9 - the
sweep's stated method verbatim). Scope: US48 + ERCO/CISO/MISO/PJM/SWPP/SOCO, per-BA always,
US48 is a respondent row never a computed pool.

## MEASURED MECHANICS AND TRAPS

1. WALL = knowable_from period + 2 calendar days: the S98 sweep observed T+2 on the daily fuel
   route; build day showed T+1 (improving intraday) - +2 is the measured worst case. EIA revises
   early days at the margin; store is retrieval-dated (feed-K-class note).
2. TIMEZONE FRAMING = Eastern on every respondent - aligns day boundaries with the desk's ET
   clock and reproduces the sweep's demonstration values exactly. A per-BA local-time variant is
   a possible refinement, noted not built.
3. EIA v2 strings-for-numerics trap (same as feed R) - coerced at store time.
4. BUILD BUG CAUGHT BY THE SELFTEST PINS: first cut multiplied MWh x 1000 before the heat rate,
   inflating est burn 1000x (28,343 vs 28.3). The sweep's method takes MWh directly. The pin
   architecture (assert against independently-recorded values) did exactly its job.
5. ISO DAY-AHEAD MARKET CLOCK (Greg's 10 AM hypothesis): NOT added to information_clock yet -
   per-ISO deadlines must be verified from each ISO's published schedule, never assumed. QUEUED,
   with the 10:00-10:30 ET non-Thursday tape characterization (live-coach material).

## VERIFIED ANCHORS (selftest-pinned)

- The sweep's squeeze demonstration reproduced: US48 gas gen 3.71M MWh (Jan 10) -> 5.39M (Jan 20)
  -> 5.60M (Jan 25) -> 5.46M (Jan 28); est burn 28.3 -> 41.1 -> 42.8 -> 41.7 Bcf/d.
- Harness: on 2026-01-22 the agent sees period 2026-01-20 (age 2) with est burn 41.1; on
  2026-01-12 it sees 28.3 - the freeze's +12.8 Bcf/d power-burn ramp was decision-time-visible
  across G11's build-up.
- CISO solar nonzero mid-January (the duck curve's home); ERCO demand + DF present.
- Blind-wall walk Nov 3 - Feb 27: 0 violations.
