# KALSHI NG COVERAGE - FEED L REPORT (DATA_GATE_S98, built 2026-07-20)

Deliverable of feed L (family KAL): inventory of the collector data branch, investigation of the
current Kalshi public API, and backfill of Kalshi-side NG market data for the walked winter
(Nov 1 2025 - Feb 27 2026) and for the KXNATGASD family. Store: `data/kalshi_ng/` (local,
gitignored; S3 push under `kalshi/` is the orchestrator's step - builder has no AWS creds).
Module: `research/kalshi/kalshi_ng_backfill.py` (`--selftest` included). No commits by this
builder. Zero synthetic data; every gap below is named, none silently skipped.

## THE HEADLINE (structural, changes feed M's claim)

**Kalshi had NO daily natural-gas market during the walked winter. The KXNATGASD series did not
exist until 2026-03-27.** Its first market was created 2026-03-27T23:29:42Z (first settle
2026-03-30). KXNATGASW (weekly) first closes 2026-04-03; KXNATGASMON (monthly) first closes
2026-04-30. NG daily was part of Kalshi's late-March 2026 commodity-daily expansion wave
(KXBRENTD first close 2026-03-22, KXGOLDD / KXSILVERD 2026-03-24 - all verified from the
historical archive, which for other series reaches back to 2022, so this is a true launch date,
not an archive truncation; KXWTI by contrast existed through the winter, archive back to
2022-09-09, 240 winter markets).

The only NG-linked Kalshi markets alive at any point in Nov 1 2025 - Feb 27 2026 were three
ANNUAL threshold events (yearly max/min, not daily settle brackets):

| event | strikes | open | closed/settled | result | lifetime volume (contracts) |
|---|---|---|---|---|---|
| KXNGASMAX-25DEC29 (P3, P4) | 2 | 2025-01-01 | settled YES 2025-11-04 | yes/yes | 1,441 |
| KXNGASMAX-B-25DEC29 (P4, P5) | 2 | 2025-11-06 | settled YES 2025-12-04 | yes/yes | 75,674 |
| KXNGASMIN-25DEC29 (N1.50/N1.75/N2.00) | 3 | 2025-01-09 | closed 2025-12-31 18:59 ET, settled 2026-01-01 | all no | 26,169 |

**From 2026-01-01 through 2026-02-27 Kalshi had ZERO natural-gas-linked markets open of any
kind.** The 2026 annuals (KXNGASMAX-26DEC31, KXNGASMIN-26DEC31) opened 2026-03-11. So G10's
January window and the G12/G13 February windows have no Kalshi NG echo, and Nov-Dec 2025 has
only a thin annual-threshold echo (see per-date table). This is a market-existence gap, not a
data-recovery gap: no credential, vendor, or future collector can produce data that was never
generated. **Feed M's echo replay of the walked winter (G7-G11) on Kalshi NG is structurally
impossible.** What feed M CAN measure the lag/fill model on is the KXNATGASD life itself
(2026-03-30 -> present), which this build landed in full (section 4), and the two-coach spec's
lag numbers must come from there (or live-forward), never from a winter reconstruction.

## 1. THE GIT DATA BRANCH (inventory verdict)

- The durable collector pushes to the ORPHAN BRANCH `data/kalshi-bins` (force-push each run,
  cumulative restore-append-push cycle), NOT a directory on the trunk. The trunk tip
  (`claude/kalshi-s79-kickoff-ij8t9o` @ a04e93cc, 2026-07-14) holds no kalshi data at all.
- Branch state at inspection (commit 678404b1): **alive and current** - last update
  2026-07-20T08:02:42Z (run 29712125027), 22 series files + consensus.jsonl.gz, KXNATGASD file
  1.99 MB gz.
- **KXNATGASD accrual: 180,540 snapshot rows spanning 2026-07-12T01:40Z -> 2026-07-20T08:01Z
  ONLY.** Per UTC date: 07-12: 23,780 / 07-13: 25,720 / 07-14: 22,180 / 07-15: 20,560 /
  07-16: 21,340 / 07-17: 11,940 / 07-18: 24,640 / 07-19: 22,220 / 07-20 (partial): 8,160.
  123,648 rows carry a two-sided 10-level book (`book_ok`), ~60s cadence, ~20 strikes/cycle.
- Winter verdict: **the branch holds ZERO winter data - structurally, not by stall.** The
  collectors were first stood up at S78/S79 (first row 2026-07-12), eight months after the
  walked winter ended. The S83 queued-runs concern is moot for the winter window; since
  2026-07-12 accrual has been continuous EXCEPT one named 12-hour collector outage:
  2026-07-16T21:00Z -> 2026-07-17T09:00Z (no snapshot rows; spans the Jul 16 18:00 UTC run's
  tail and the Jul 17 00:00 run's slot). All other hours Jul 12 - Jul 20 have rows.
- Note: each run force-pushes an orphan commit, so the branch has no per-run history to mine -
  but the bins files are append-only cumulative, so nothing is lost by that design.

## 2. THE PUBLIC API TODAY (investigated first, per discipline; verified empirically 2026-07-20)

Base `https://api.elections.kalshi.com/trade-api/v2` (the docs' newer
`external-api.kalshi.com` serves identically; both tested). All endpoints below are PUBLIC -
no auth, no account, no key.

**The two-worlds split (the load-bearing API fact).** Kalshi keeps a LIVE database (~3-month
target window) and a HISTORICAL archive, split by a moving cutoff served at
`GET /historical/cutoff`. On 2026-07-20 all three cutoffs read **2026-05-21T00:00:00Z**
(markets settled / trades created / orders updated before that are archive-side). The worlds
are DISJOINT: regular endpoints return 0 rows / 404 for archived markets and vice versa. Any
puller must route per market and re-route as the cutoff advances (a market in the live window
today is archive-side in three months).

| data | live window (settled after cutoff) | archived (settled before cutoff) |
|---|---|---|
| market definitions | `GET /markets?series_ticker=&status=` (settled/closed/open) | `GET /historical/markets?series_ticker=` |
| trades | `GET /markets/trades?ticker=` | `GET /historical/trades?ticker=` |
| candlesticks | `GET /series/{s}/markets/{t}/candlesticks` | `GET /historical/markets/{t}/candlesticks` |
| orderbook | `GET /markets/{t}/orderbook` - LIVE SNAPSHOT ONLY | **does not exist** |

- Candlesticks: `period_interval` 1/60/1440 minutes; **hard cap 5000 candles per request**
  (HTTP 400 above; chunk at 4500). Sparse markets return sparse grids (only minutes with book
  or trade activity produce candles). Candle rows carry price OHLC + `yes_bid`/`yes_ask` OHLC +
  volume + open_interest - the only book-adjacent history that exists (top-of-book only).
- Trades: `limit` max 1000/page, cursor pagination; rows carry `trade_id`, `count_fp`,
  `yes_price_dollars`, `no_price_dollars`, `taker_outcome_side`, `taker_book_side`, legacy
  `taker_side` (still served), `created_time`, `is_block_trade`.
- Archive depth is real: KXNGAS markets from 2022 still served; KXWTI archive back to
  2022-09-09. The archive did not lose the winter - the winter markets never existed.
- Rate limits: the documented token tiers apply to AUTHENTICATED keys (Basic = 200 read
  tokens/s); unauthenticated limits are undocumented. This build paced at ~7 req/s with
  Retry-After-honoring backoff and saw zero 429s.
- **Structural gap (named): historical orderbook depth does not exist on any endpoint.** Book
  history exists only where a live collector snapshotted it - our branch bins hold 10-level
  books from 2026-07-12 forward, 60s cadence. That is the earliest Kalshi NG book depth that
  exists anywhere in this project.

**Drift of the S80-era code vs the current API** (`kalshi_history.py`, `kalshi_collector.py`):
- Field-level: NO breakage. `taker_side` is still served alongside the newer
  `taker_outcome_side`/`taker_book_side`; dollar fixed-point fields unchanged; the collector's
  orderbook parse (`orderbook_fp`/`yes_dollars`) still matches.
- Behavior-level: **`kalshi_history.py` silently sees only the live window.** Its
  `/markets?status=settled` enumeration now reaches back only to the cutoff (settle >=
  2026-05-21 at inspection); its S80 header survey ("natgas ~0.2M x13 events") was already a
  truncated read. For archived markets it would write empty trade stores without erroring
  (regular trades endpoint returns 0 rows archive-side), and its candle fetch treats the
  archive-side 404 as a skippable chunk. It also reduces rows (drops `no_price_dollars`,
  `trade_id`, `taker_book_side`, block flag). It predates the keep-everything discipline; the
  new module replaces it for backfill work. `kalshi_collector.py` (live snapshots) is
  unaffected by the split and remains correct as the live-forward collector.

## 3. WALKED-WINTER COVERAGE, PER DATE (Nov 1 2025 - Feb 27 2026)

Columns: branch bins (collector snapshots); KXNATGASD family (daily/weekly/monthly brackets);
NG-linked annuals open that date; annual trades recovered that date; annual 1-min candle rows
that date; orderbook depth. "none (series not created)" = the market did not exist to be
collected - a market-existence gap, distinct from a data gap. "-" = no market open, so no data
is possible. All 119 dates listed; every date in this window is a NAMED GAP for the family.

Annual markets open by span: KXNGASMAX-25DEC29 (2 mkts) through 2025-11-04;
KXNGASMAX-B-25DEC29 (2 mkts) 2025-11-06 -> 2025-12-04; KXNGASMIN-25DEC29 (3 mkts) through
2025-12-31. Trades/candles below were recovered in full via `/historical/trades` and
`/historical/markets/{t}/candlesticks` - for these annuals this is COMPLETE recovery of what
existed, not a sample.

| date | dow | branch bins | KXNATGASD family | NG annuals | ann. trades | ann. 1m candles | book |
|---|---|---|---|---|---|---|---|
| 2025-11-01 | Sat | none (collector not built) | none (series not created) | 5 open | 0 | 24 | none |
| 2025-11-02 | Sun | none (collector not built) | none (series not created) | 5 open | 0 | 21 | none |
| 2025-11-03 | Mon | none (collector not built) | none (series not created) | 5 open | 0 | 31 | none |
| 2025-11-04 | Tue | none (collector not built) | none (series not created) | 5 open (MAX settles YES) | 0 | 2 | none |
| 2025-11-05 | Wed | none (collector not built) | none (series not created) | 3 open | 0 | 4 | none |
| 2025-11-06 | Thu | none (collector not built) | none (series not created) | 5 open (MAX-B opens) | 0 | 31 | none |
| 2025-11-07 | Fri | none (collector not built) | none (series not created) | 5 open | 0 | 34 | none |
| 2025-11-08 | Sat | none (collector not built) | none (series not created) | 5 open | 0 | 20 | none |
| 2025-11-09 | Sun | none (collector not built) | none (series not created) | 5 open | 0 | 18 | none |
| 2025-11-10 | Mon | none (collector not built) | none (series not created) | 5 open | 3 | 46 | none |
| 2025-11-11 | Tue | none (collector not built) | none (series not created) | 5 open | 13 | 81 | none |
| 2025-11-12 | Wed | none (collector not built) | none (series not created) | 5 open | 23 | 285 | none |
| 2025-11-13 | Thu | none (collector not built) | none (series not created) | 5 open | 20 | 205 | none |
| 2025-11-14 | Fri | none (collector not built) | none (series not created) | 5 open | 9 | 106 | none |
| 2025-11-15 | Sat | none (collector not built) | none (series not created) | 5 open | 2 | 91 | none |
| 2025-11-16 | Sun | none (collector not built) | none (series not created) | 5 open | 7 | 75 | none |
| 2025-11-17 | Mon | none (collector not built) | none (series not created) | 5 open | 7 | 123 | none |
| 2025-11-18 | Tue | none (collector not built) | none (series not created) | 5 open | 20 | 200 | none |
| 2025-11-19 | Wed | none (collector not built) | none (series not created) | 5 open | 39 | 331 | none |
| 2025-11-20 | Thu | none (collector not built) | none (series not created) | 5 open | 22 | 306 | none |
| 2025-11-21 | Fri | none (collector not built) | none (series not created) | 5 open | 20 | 313 | none |
| 2025-11-22 | Sat | none (collector not built) | none (series not created) | 5 open | 7 | 98 | none |
| 2025-11-23 | Sun | none (collector not built) | none (series not created) | 5 open | 11 | 148 | none |
| 2025-11-24 | Mon | none (collector not built) | none (series not created) | 5 open | 15 | 136 | none |
| 2025-11-25 | Tue | none (collector not built) | none (series not created) | 5 open | 8 | 94 | none |
| 2025-11-26 | Wed | none (collector not built) | none (series not created) | 5 open | 19 | 126 | none |
| 2025-11-27 | Thu | none (collector not built) | none (series not created) | 5 open | 9 | 68 | none |
| 2025-11-28 | Fri | none (collector not built) | none (series not created) | 5 open | 26 | 102 | none |
| 2025-11-29 | Sat | none (collector not built) | none (series not created) | 5 open | 5 | 89 | none |
| 2025-11-30 | Sun | none (collector not built) | none (series not created) | 5 open | 11 | 84 | none |
| 2025-12-01 | Mon | none (collector not built) | none (series not created) | 5 open | 12 | 131 | none |
| 2025-12-02 | Tue | none (collector not built) | none (series not created) | 5 open | 60 | 283 | none |
| 2025-12-03 | Wed | none (collector not built) | none (series not created) | 5 open | 61 | 970 | none |
| 2025-12-04 | Thu | none (collector not built) | none (series not created) | 5 open (MAX-B settles YES) | 4 | 69 | none |
| 2025-12-05 | Fri | none (collector not built) | none (series not created) | 3 open | 13 | 82 | none |
| 2025-12-06 | Sat | none (collector not built) | none (series not created) | 3 open | 6 | 73 | none |
| 2025-12-07 | Sun | none (collector not built) | none (series not created) | 3 open | 9 | 54 | none |
| 2025-12-08 | Mon | none (collector not built) | none (series not created) | 3 open | 13 | 94 | none |
| 2025-12-09 | Tue | none (collector not built) | none (series not created) | 3 open | 19 | 97 | none |
| 2025-12-10 | Wed | none (collector not built) | none (series not created) | 3 open | 15 | 87 | none |
| 2025-12-11 | Thu | none (collector not built) | none (series not created) | 3 open | 18 | 89 | none |
| 2025-12-12 | Fri | none (collector not built) | none (series not created) | 3 open | 11 | 96 | none |
| 2025-12-13 | Sat | none (collector not built) | none (series not created) | 3 open | 11 | 81 | none |
| 2025-12-14 | Sun | none (collector not built) | none (series not created) | 3 open | 8 | 92 | none |
| 2025-12-15 | Mon | none (collector not built) | none (series not created) | 3 open | 27 | 114 | none |
| 2025-12-16 | Tue | none (collector not built) | none (series not created) | 3 open | 12 | 95 | none |
| 2025-12-17 | Wed | none (collector not built) | none (series not created) | 3 open | 4 | 71 | none |
| 2025-12-18 | Thu | none (collector not built) | none (series not created) | 3 open | 23 | 126 | none |
| 2025-12-19 | Fri | none (collector not built) | none (series not created) | 3 open | 11 | 92 | none |
| 2025-12-20 | Sat | none (collector not built) | none (series not created) | 3 open | 12 | 67 | none |
| 2025-12-21 | Sun | none (collector not built) | none (series not created) | 3 open | 16 | 67 | none |
| 2025-12-22 | Mon | none (collector not built) | none (series not created) | 3 open | 17 | 73 | none |
| 2025-12-23 | Tue | none (collector not built) | none (series not created) | 3 open | 23 | 80 | none |
| 2025-12-24 | Wed | none (collector not built) | none (series not created) | 3 open | 4 | 73 | none |
| 2025-12-25 | Thu | none (collector not built) | none (series not created) | 3 open | 6 | 60 | none |
| 2025-12-26 | Fri | none (collector not built) | none (series not created) | 3 open | 5 | 78 | none |
| 2025-12-27 | Sat | none (collector not built) | none (series not created) | 3 open | 4 | 52 | none |
| 2025-12-28 | Sun | none (collector not built) | none (series not created) | 3 open | 4 | 61 | none |
| 2025-12-29 | Mon | none (collector not built) | none (series not created) | 3 open | 10 | 69 | none |
| 2025-12-30 | Tue | none (collector not built) | none (series not created) | 3 open | 4 | 136 | none |
| 2025-12-31 | Wed | none (collector not built) | none (series not created) | 3 open (MIN closes 18:59 ET, all NO) | 8 | 654 | none |
| 2026-01-01 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-02 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-03 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-04 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-05 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-06 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-07 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-08 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-09 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-10 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-11 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-12 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-13 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-14 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-15 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-16 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-17 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-18 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-19 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-20 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-21 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-22 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-23 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-24 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-25 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-26 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-27 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-28 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-29 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-30 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-01-31 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-01 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-02 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-03 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-04 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-05 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-06 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-07 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-08 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-09 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-10 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-11 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-12 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-13 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-14 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-15 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-16 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-17 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-18 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-19 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-20 | Fri | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-21 | Sat | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-22 | Sun | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-23 | Mon | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-24 | Tue | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-25 | Wed | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-26 | Thu | none (collector not built) | none (series not created) | none | - | - | none |
| 2026-02-27 | Fri | none (collector not built) | none (series not created) | none | - | - | none |

Reading: the annual trades/candles columns above are the COMPLETE recovered record (all 793
lifetime trades of the three events landed; the table shows the in-window slice per date).
Zero-trade dates while markets were open are real quiet days on thin annual markets, not
missing pulls. Candle counts are 1-min rows summed across the open markets (sparse grid =
only minutes with activity; these markets often quoted without trading). Weekends show annual
activity because Kalshi trades 24/7 - a reminder that the NG-daily lag game on Kalshi runs on
a different clock than NYMEX; feed M owns that join.

## 4. WHAT WAS BACKFILLED (the store)

All pulls completed 2026-07-20 (one interruption: the first KXNATGASD run was killed at
event 51/61 by a harness stop; the resume pass skip-verified cached events and completed the
remaining MAY events - per-event provenance in `meta/pull_log.jsonl`). Store totals:

| series | events pulled | trades rows | 1-min candle rows | notes |
|---|---|---|---|---|
| KXNATGASD (daily) | 61 (full settled life 2026-03-29 -> 2026-07-16) | 153,803 | 3,691,004 | 2 open events (JUL20/JUL21) defs-only, re-pull after settle |
| KXNATGASW (weekly) | 16 (2026-04-03 -> 2026-07-17) | 11,197 | 823,405 | 1 open event (JUL24) defs-only |
| KXNATGASMON (monthly) | 3 (2026-04-30 -> 2026-06-30) | 2,339 | 412,567 | 1 open event (JUL31) defs-only |
| KXNGASMAX (winter annuals) | 2 (25DEC29 + B-25DEC29) | 412 | 3,063 (Oct-Feb window) | + 60m/1440m full-life candles |
| KXNGASMIN (winter annual) | 1 (25DEC29) | 381 | 5,284 (Oct-Feb window) | + 60m/1440m full-life candles |

Store: `data/kalshi_ng/` - 177 gz files, 48.8 MB (markets/ + trades/ + candles/ + meta/;
layout and usage in the header of `research/kalshi/kalshi_ng_backfill.py`).
Selftest: **PASS 11/11** (readability of all 177 files; known-date 2026-03-30 counts: event
trades file 69 rows, strike T2.845 exactly 2 trades, 29,289 1m candles; raw-field checks on
trades and candles; series-launch invariant min created_time 2026-03-27T23:27:25Z). One
earlier selftest assertion was itself wrong and was fixed, not the data: it asserted the
launch date on a specific STRIKE, but strikes are created intraday as price moves (ladder
churn - T2.845 was added 2026-03-30T18:02Z); the invariant now keys on the series-wide
minimum created_time.

**KXNATGASD life, per event-day** (strikes / trades rows / 1m candle rows / volume in
contracts). Every settled event-day of the series is present - no pull gaps; the API served
trades + candles for every event, both sides of the cutoff.

| date | dow | event | strikes | trades | 1m candles | volume |
|---|---|---|---|---|---|---|
| 2026-03-29 | Sun | KXNATGASD-26MAR2918 | 60 | 8 | 6,313 | 60 |
| 2026-03-30 | Mon | KXNATGASD-26MAR3017 | 70 | 69 | 29,289 | 1,737 |
| 2026-03-31 | Tue | KXNATGASD-26MAR3117 | 60 | 108 | 17,243 | 3,075 |
| 2026-04-01 | Wed | KXNATGASD-26APR0117 | 60 | 187 | 19,206 | 5,161 |
| 2026-04-02 | Thu | KXNATGASD-26APR0217 | 70 | 150 | 15,955 | 2,910 |
| 2026-04-05 | Sun | KXNATGASD-26APR0518 | 80 | 63 | 35,412 | 973 |
| 2026-04-06 | Mon | KXNATGASD-26APR0617 | 80 | 575 | 50,544 | 13,957 |
| 2026-04-07 | Tue | KXNATGASD-26APR0717 | 80 | 361 | 21,913 | 11,899 |
| 2026-04-08 | Wed | KXNATGASD-26APR0817 | 110 | 619 | 24,766 | 15,254 |
| 2026-04-15 | Wed | KXNATGASD-26APR1517 | 100 | 262 | 11,788 | 7,977 |
| 2026-04-16 | Thu | KXNATGASD-26APR1617 | 110 | 316 | 15,064 | 11,438 |
| 2026-04-20 | Mon | KXNATGASD-26APR2017 | 100 | 2,099 | 108,125 | 30,488 |
| 2026-04-21 | Tue | KXNATGASD-26APR2117 | 90 | 2,378 | 49,818 | 47,677 |
| 2026-04-22 | Wed | KXNATGASD-26APR2217 | 70 | 2,269 | 53,335 | 23,177 |
| 2026-04-23 | Thu | KXNATGASD-26APR2317 | 100 | 4,425 | 41,268 | 65,353 |
| 2026-04-27 | Mon | KXNATGASD-26APR2717 | 100 | 2,258 | 168,308 | 28,848 |
| 2026-04-29 | Wed | KXNATGASD-26APR2917 | 110 | 1,422 | 29,667 | 22,593 |
| 2026-04-30 | Thu | KXNATGASD-26APR3017 | 120 | 2,502 | 32,957 | 35,378 |
| 2026-05-04 | Mon | KXNATGASD-26MAY0417 | 80 | 3,410 | 159,335 | 55,926 |
| 2026-05-05 | Tue | KXNATGASD-26MAY0517 | 80 | 2,944 | 44,992 | 53,981 |
| 2026-05-06 | Wed | KXNATGASD-26MAY0617 | 100 | 3,287 | 46,649 | 60,091 |
| 2026-05-07 | Thu | KXNATGASD-26MAY0717 | 100 | 4,758 | 43,564 | 88,123 |
| 2026-05-11 | Mon | KXNATGASD-26MAY1117 | 80 | 2,249 | 110,939 | 48,470 |
| 2026-05-12 | Tue | KXNATGASD-26MAY1217 | 70 | 2,130 | 42,692 | 38,370 |
| 2026-05-13 | Wed | KXNATGASD-26MAY1317 | 70 | 2,920 | 39,710 | 68,705 |
| 2026-05-14 | Thu | KXNATGASD-26MAY1417 | 62 | 1,980 | 40,329 | 30,243 |
| 2026-05-18 | Mon | KXNATGASD-26MAY1817 | 60 | 2,522 | 185,875 | 44,929 |
| 2026-05-19 | Tue | KXNATGASD-26MAY1917 | 100 | 5,694 | 60,741 | 121,567 |
| 2026-05-20 | Wed | KXNATGASD-26MAY2017 | 90 | 2,471 | 35,963 | 40,562 |
| 2026-05-21 | Thu | KXNATGASD-26MAY2117 | 70 | 2,158 | 39,222 | 37,572 |
| 2026-05-26 | Tue | KXNATGASD-26MAY2617 | 60 | 6,423 | 70,143 | 197,176 |
| 2026-05-27 | Wed | KXNATGASD-26MAY2717 | 70 | 4,332 | 68,300 | 61,214 |
| 2026-05-28 | Thu | KXNATGASD-26MAY2817 | 100 | 3,220 | 54,609 | 58,730 |
| 2026-06-01 | Mon | KXNATGASD-26JUN0117 | 110 | 7,502 | 220,923 | 131,955 |
| 2026-06-02 | Tue | KXNATGASD-26JUN0217 | 80 | 2,137 | 55,854 | 24,231 |
| 2026-06-03 | Wed | KXNATGASD-26JUN0317 | 80 | 1,449 | 43,924 | 26,232 |
| 2026-06-04 | Thu | KXNATGASD-26JUN0417 | 120 | 1,639 | 37,920 | 29,818 |
| 2026-06-08 | Mon | KXNATGASD-26JUN0817 | 90 | 2,852 | 116,391 | 114,419 |
| 2026-06-09 | Tue | KXNATGASD-26JUN0917 | 70 | 3,364 | 44,482 | 109,964 |
| 2026-06-10 | Wed | KXNATGASD-26JUN1017 | 80 | 3,801 | 49,948 | 98,632 |
| 2026-06-11 | Thu | KXNATGASD-26JUN1117 | 80 | 2,209 | 52,702 | 90,476 |
| 2026-06-15 | Mon | KXNATGASD-26JUN1517 | 70 | 1,936 | 69,596 | 98,347 |
| 2026-06-16 | Tue | KXNATGASD-26JUN1617 | 90 | 1,915 | 47,230 | 119,113 |
| 2026-06-17 | Wed | KXNATGASD-26JUN1717 | 90 | 3,871 | 61,640 | 210,022 |
| 2026-06-18 | Thu | KXNATGASD-26JUN1817 | 90 | 2,828 | 48,231 | 137,143 |
| 2026-06-22 | Mon | KXNATGASD-26JUN2217 | 110 | 2,171 | 79,770 | 87,944 |
| 2026-06-23 | Tue | KXNATGASD-26JUN2317 | 100 | 1,926 | 33,823 | 91,498 |
| 2026-06-24 | Wed | KXNATGASD-26JUN2417 | 90 | 2,010 | 48,212 | 142,311 |
| 2026-06-25 | Thu | KXNATGASD-26JUN2517 | 110 | 3,365 | 49,709 | 247,713 |
| 2026-06-29 | Mon | KXNATGASD-26JUN2917 | 100 | 3,724 | 108,972 | 193,328 |
| 2026-06-30 | Tue | KXNATGASD-26JUN3017 | 100 | 6,047 | 67,980 | 233,219 |
| 2026-07-01 | Wed | KXNATGASD-26JUL0117 | 90 | 1,974 | 43,867 | 116,086 |
| 2026-07-02 | Thu | KXNATGASD-26JUL0217 | 80 | 1,531 | 36,643 | 75,310 |
| 2026-07-06 | Mon | KXNATGASD-26JUL0617 | 100 | 3,760 | 75,830 | 120,540 |
| 2026-07-07 | Tue | KXNATGASD-26JUL0717 | 100 | 2,917 | 72,183 | 113,989 |
| 2026-07-08 | Wed | KXNATGASD-26JUL0817 | 100 | 2,805 | 63,168 | 100,784 |
| 2026-07-09 | Thu | KXNATGASD-26JUL0917 | 80 | 3,037 | 66,225 | 116,178 |
| 2026-07-13 | Mon | KXNATGASD-26JUL1317 | 60 | 3,050 | 79,831 | 135,889 |
| 2026-07-14 | Tue | KXNATGASD-26JUL1417 | 60 | 2,484 | 83,198 | 123,144 |
| 2026-07-15 | Wed | KXNATGASD-26JUL1517 | 60 | 2,311 | 82,129 | 116,089 |
| 2026-07-16 | Thu | KXNATGASD-26JUL1617 | 70 | 4,619 | 76,589 | 325,988 |
| 2026-07-20 | Mon | KXNATGASD-26JUL2017 | 60 | open, not pulled | open, not pulled | 23,312 |
| 2026-07-21 | Tue | KXNATGASD-26JUL2117 | 60 | open, not pulled | open, not pulled | 1 |

**Weekday dates with NO daily event listed by Kalshi (21, named):** all Fridays in the life
(2026-04-03 [also Good Friday], 04-10, 04-17, 04-24, 05-01, 05-08, 05-15, 05-22, 05-29,
06-05, 06-12, 06-26, 07-10, 07-17 - the WEEKLY market closes Friday and owns that slot;
06-19 [Juneteenth] and 07-03 [July-4 observed] are Fridays that are also market holidays),
plus US holiday 2026-05-25 (Memorial Day, Monday), plus four early-life listing
irregularities: 2026-04-09 (Thu), 04-13 (Mon), 04-14 (Tue), 04-28 (Tue). Two weekend
events exist from the first week (26MAR2918, 26APR0518 - Sundays); after 2026-04-05 the
cadence settles to Mon-Thu daily + Fri weekly.

**Weekly + monthly stores** (trades + 1m candles per event, full life): KXNATGASW 16 settled
events, KXNATGASMON 3 settled events - per-event counts in `meta/pull_log.jsonl`; weekly
candle files span each market's full ~7-day life (multi-chunk stitch verified, e.g.
26APR0317: 39,548 1m candles 2026-03-28 -> 2026-04-03).
## 5. WHAT A LIVE-FORWARD COLLECTOR CAPTURES THAT HISTORY CANNOT (feeds the two-coach spec)

1. **Orderbook depth.** No historical book endpoint exists at all. The API's only backward
   book view is candle-level `yes_bid`/`yes_ask` OHLC (top-of-book, minute floor). The S81/S82
   size-vs-fee question NEEDS depth (how many contracts at the touch when the NYMEX move
   lands); that is answerable only from live snapshots. Our branch collector has been capturing
   10-level books at ~60s since 2026-07-12 - the earliest Kalshi NG depth that exists anywhere.
2. **Sub-minute timing.** Historical candles floor at 1 minute; the lag to measure is
   seconds-to-a-minute. Historical TRADES are timestamped to the microsecond and DO support
   event-level lag reads where trades printed, but quote repricing between trades is invisible
   historically. A live collector (or the Kalshi websocket) sees every book tick.
3. **The 60s poll cadence of the current collector undersamples the lag it exists to measure.**
   For feed M the collector cadence on KXNATGASD should be seconds-scale around NYMEX moves
   (or switch to the websocket channel); the 6h-cron GitHub runner design cannot do that -
   worth carrying into the two-coach spec as a build requirement.
4. **Strike-ladder churn.** Definitions are retained historically (good - settlement values,
   strike ladders, open/close stamps all recovered), but WHEN strikes were added intraday is
   only in `created_time`/`open_time`, not observable as book evolution.

## 6. NAMED BLOCKERS / GAPS (none require credentials)

- **Market-existence gap (the big one):** no Kalshi NG daily bracket before 2026-03-30; zero
  NG-linked Kalshi markets at all 2026-01-01 -> 2026-02-27 (and 2026-02-28 -> 2026-03-10;
  the 2026 annuals open 2026-03-11). Not recoverable by any means. Feed M's winter echo replay
  cannot run; its lag/fill measurement must use the KXNATGASD life from 2026-03-30 (backfilled
  here) plus live-forward collection.
- **Historical orderbook depth:** structurally unobtainable (no endpoint). Top-of-book OHLC at
  1-min via candles is the ceiling for the backfilled period.
- **Friday dailies:** Kalshi lists NO KXNATGASD market on Fridays - the weekly (KXNATGASW,
  closes Friday, Thursday on holiday weeks) is the Friday instrument. A Friday NYMEX->Kalshi
  daily echo does not exist by market design; the weekly bracket is the Friday echo vehicle.
- **No auth-gated arm was needed:** every endpoint used is public. Nothing in feed L waits on
  credentials. (The orchestrator still owns the S3 push of the store.)

## 7. EXACT ENDPOINTS USED

- `GET /trade-api/v2/series` (enumeration sweep; 12,000 series, 11 NG-related identified)
- `GET /trade-api/v2/series/{series_ticker}` (KXNATGASD metadata: Pyth settlement source,
  quadratic fee type)
- `GET /trade-api/v2/markets?series_ticker=&status=settled|closed|open&limit=1000&cursor=`
- `GET /trade-api/v2/historical/markets?series_ticker=&limit=1000&cursor=`
- `GET /trade-api/v2/markets/trades?ticker=&limit=1000&cursor=`
- `GET /trade-api/v2/historical/trades?ticker=&limit=1000&cursor=`
- `GET /trade-api/v2/series/{s}/markets/{t}/candlesticks?start_ts=&end_ts=&period_interval=`
- `GET /trade-api/v2/historical/markets/{t}/candlesticks?start_ts=&end_ts=&period_interval=`
- `GET /trade-api/v2/historical/cutoff` (the live/archive boundary; 2026-05-21T00:00:00Z at
  build time)

Store layout, module usage, selftest: header of `research/kalshi/kalshi_ng_backfill.py`.
