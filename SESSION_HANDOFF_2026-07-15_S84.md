# SESSION HANDOFF — S84 (work date 2026-07-12) — weather scoreboard + NYMEX-canary/Databento data thread + crypto-collector kill

Branch: worked on the harness branch `claude/kalshi-s84-kickoff-ekeu57` (rebased onto the s79 trunk at
session start — harness had cut it from the stale S70 tip `3c70ff5` again). **All work pushed to the
canonical trunk `claude/kalshi-s79-kickoff-ij8t9o`** (default; collectors auto-push there; pull before
push). Commits this session: `8f6a848` (weather scoreboard) -> `db0b272` (fingerprint) -> `5904cbd`
(time-bucket) -> [crypto kill via branch push] -> `3a54189` (NYMEX canary + pyth_backfill) -> `f911aba`
(databento scaffold) -> `278a4fb` (settlement-mechanics correction).

## 1. Weather per-regime scoreboard (DONE) — `weather_regime_score.py`, `WEATHER_REGIME_FINDINGS_S84.md`

Scoreboard-side only (forecaster = Greg's spec, HANDS OFF). 68 settled days/city (DEN/NY/CHI,
2026-05-06 -> 07-12), Kalshi settlement API, leakage gate PASS 66/66. Sharpens the S82 per-regime means.
The load-bearing finding (Greg pushed twice to break the averages down):
- **Lead with the PER-DAY fingerprint, not cell medians.** The per-day Brier is BIMODAL on one
  mechanical signal: did the high land in a wide open-TAIL bucket or a narrow INTERIOR bucket. EDGE
  days (Brier ~0) = 100% open-tail wins across all 3 cities = nobody's edge (crowd prices wide tails
  free). WHIFF days (Brier ~2) = interior-bucket wins, 73-82% WARMING = the operator's room, and
  exactly the forecaster's ">3degF over the upper bound" call.
- **The room is SEASONAL** (time-bucketed): concentrated in the May-June frontal season, near-zero in
  the early-July ridge for DEN/CHI (persistence nails a stable ridge), only NY keeps July room.
  Corrected an earlier draft claim that it "rises into summer" (it reverses for 2/3 cities). Small-n
  caveat; a July heat-dome is a separate sustained-overshoot cell.
- Runner is a drop-in for the operator's `(value,sigma)` (same `gaussian_over_buckets` path). NEXT:
  score Greg's forecaster output per-day, net-of-Kalshi-fee, on the WHIFF (interior-warm-spike) cluster
  — blocked only on a sample of its predicted highs.

## 2. NYMEX-canary data thread (the session's big arc) — `NYMEX_CANARY_NOTES_S84.md`

**Load-bearing principle (Greg):** NYMEX/ICE is the CANARY (leader); Kalshi is the delayed follower.
Gather NYMEX as the leading signal, measure the lag, fire on Kalshi. **Resolution reality:** 1-min is
USELESS (NYMEX moves fast); 1-sec is the historical floor and STILL undersamples -> every 1-sec readout
is a LOWER BOUND, never the full tape. Folded into CLAUDE.md trading rules.

**Settlement-mechanics corrections (verified off Kalshi `rules_primary`):**
- **`KXNATGASD` = a DAILY NG-PRICE market** (settles on the NGDQ6 Henry Hub futures 1-min candle close
  at 5PM EDT), NOT an EIA-storage event. **The strategy is the daily NG-futures lag, traded EVERY DAY;
  EIA Thursday is just the biggest catalyst** (Greg confirmed). Underlying = NG futures.
- **`KXPOWERKWH` = a MONTHLY BLS/EIA retail-electricity macro stat** (~21c/kWh), NOT a futures. No tape,
  no NYMEX canary; it's a release-thread market like CPI. A per-second "electric" backfill does not
  exist to buy.

**Data-source reality (S84 probe):**
- **Pyth**: has WTI (full monthly curve, historical timestamp endpoint WORKS) but **NO natural gas at
  all** — the collector's `NGDQ6` id (`3ea3adf4...`) is BOGUS (resolves to nothing). Brent feeds valid
  but Hermes historical 404s. Public endpoint 429s after ~8 rapid calls. TODO: fix/remove the bogus NG
  id in `pyth_collector.py` FEEDS.
- **`pyth_backfill.py`** (built + canaried): historical per-second WTI tape from Pyth's timestamp
  endpoint, throttled (429/5xx backoff), dedup, live-collector format (src=`pyth_hist_1s`). Canary on
  EIA-crude 2026-07-08 14:30 UTC reconstructed the real move (+14.5bps into the release, 22bps span).
  WTI-only, 1-sec undersamples — a free fallback.
- **`databento_backfill.py`** (scaffold, verified vs databento==0.81 API; NEEDS `DATABENTO_API_KEY`):
  the PRIMARY historical source. CME Globex `GLBX.MDP3` carries **CL crude AND NG Henry Hub** at the
  `trades` schema (every print, nanosecond) — fixes both Pyth gaps (NG coverage + 1-sec undersampling).
  window (sync) + batch (large/cheap) modes, continuous front-month symbology (`CL.c.0`/`NG.c.0`,
  auto-roll), `metadata.get_cost` gate on `--max-cost`. Usage-based $/GB, $125 free credit; NG-year
  `trades` ~= 1-2 GB (very likely within the credit); batch for large multi-year pulls.

## 3. Crypto-collector kill (DONE)

The old coin collectors (btc/eth/alt/book/kraken/bybit/perp + paper_trade) were respawning 1,400+ runs
and hogging runners, holding up the live Kalshi/Pyth collectors. Root cause: they scheduled from ONE
stale branch, `claude/new-session-o3vnm` (the S70 tip), which GitHub's scheduler was pinned to. Deleting
runs/workflows in the UI was futile (the .yml source files respawned them). FIX: pushed a commit
stripping all 11 workflow files off `new-session-o3vnm` (proxy blocks branch deletion, so removed the
files instead); Greg then deleted the branch entirely. Verified: sole crypto scheduler (26 of last 30
scheduled runs), now dead, no respawn. The other ~54 branches carry the files but are inert (never
scheduled). Runners freed.

## OPEN / NEXT (S85)

1. **DATABENTO_API_KEY** (Greg to set as an env-var/secret) -> `databento_backfill.py cost` for a
   full-year NG `trades` (exact $ net of $125, pulls nothing) -> batch-pull the NG year -> then WTI,
   Brent, more years as price/credit allow ("fill in the others free depending on price").
2. **`event_move_baseline.py`** (NOT yet built) — the payoff: per-event move MAGNITUDE + DURATION
   (blip vs long run) on the true-tick tape, per surprise-cell, distributions not means. Expectation-
   setting ("weather head"), not a trade-fire signal. Sizes the energy-lag-scalp hold time.
3. **Pyth live tape** — a send_later check is armed for **2026-07-13 01:45 UTC** (bound to the S84
   session) to grab the first post-reopen tape and run the P1 sub-second lag test on live WTI. NG/Brent
   live also need a non-Pyth source going forward.
4. Score Greg's weather forecaster output through `weather_regime_score.py` (per-day, net-of-fee, WHIFF
   cluster) when a sample of predicted highs is available.
5. Fix the bogus `NGDQ6` id in `pyth_collector.py`.

## RULES (unchanged): NYMEX is the canary (fire on Kalshi); each trade individually / per-cell /
distributions not means; exclude the settle window; leakage gate before any backtest; zero synthetic;
provisional-until-live; weather forecaster = Greg's spec HANDS OFF; keep KALSHI_TRADING.md current;
keep CLAUDE.md lean.
