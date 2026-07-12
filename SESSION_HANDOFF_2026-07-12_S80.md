# SESSION HANDOFF — S80 (2026-07-12) — Kalshi: cron LIVE, historical trades unblock, futures→Kalshi LAG CONFIRMED, level-hit reframe

Branch **`claude/kalshi-s79-kickoff-ij8t9o`** (= the repo DEFAULT now — Greg's click landed; the 6h cron FIRES).
Greg: push to s79 directly (the harness-assigned s80 branch was a stale S70 tip — same trap as S79; do NOT use it).
All work committed + pushed: `ba1d979` (book signal) → `8c0428a` (weather bridge) → `6c625e9` (hist puller) →
`6d1db59` (hist signal test) → `f6601cf` (settle filter) → `de5c5ba` (memory rule) → `7e2bff7` (lag).

## STATE (end S80)

### Infra / data
- **Default branch = s79 → 6h cron fires.** First durable collector run confirmed IN PROGRESS (started 01:40Z,
  ~5h50m; pushes `data/kalshi-bins` at END of each run — data lands in ~6h chunks). Bins + consensus accrue
  continuously now.
- **HISTORICAL Kalshi data is retrievable (the big unblock).** Public API: settled markets enumerable per series;
  `/markets/trades` per ticker = every past fill WITH `taker_side` (yes/no) = **REAL SIGNED taker flow** (the
  original info_dipole input, better than the live book-depth proxy); candlesticks (5000/req cap). Pulled: all
  **46 WTI daily events × top-12 strikes = 496k trades**; 1 natgas + 1 Brent day. `research/kalshi/kalshi_history.py`
  (`--all`, `--top N`, `--skip-candles`); store `data/kalshi_hist_trades/` (LOCAL, gitignored).
- Liquidity map (settled, vol/event): WTI ~1.2M ×46; CPI ~0.94M ×2; natgas ~0.2M ×13(22); Brent ~0.1-0.5M ×37; Fed ~1M.

### Hubs / settlement (Greg asked)
**KXNATGASD = Henry Hub** (NYMEX NG front-month `NGDQ6`, 1-min candle close 5PM EDT, Pyth source);
**KXWTI = Cushing WTI** (ICE daily settlement ~2:30PM ET); **KXBRENTD = Brent** (`BRENTU6`, 5PM EDT, Pyth).
All are DAILY **price**-settled contracts → they trade every day; releases are intraday catalysts, not settlement.
(⇒ the weather→storage-NUMBER edge still awaits a storage-number-settled product; KXNATGASD is LINK-B/price.)

### ⭐ FUTURES→KALSHI LAG — CONFIRMED, ONE-DIRECTIONAL (`research/kalshi/futures_kalshi_lag.py`, turnkey `--fetch CL=F`)
Per-contract (never pooled) cross-cov-over-lag (odcore.leadlag, S19/INFO-066 operator + time-slide null) on 1-min
diffs, settlement window excluded:
- **WTI (Jul 6-10, 41 contracts): 15 significant z≥3; peak lags {0m: 6, +1m: 8, +5m: 1}.** Busy strikes included
  (400+ re-prices/day, z to 16.7).
- **Brent (Jul 8, 10 contracts): 4 significant; lags {0,+1,+1,+2}.** Replicates on a second hub.
- **Natgas (Jul 6): 0/8 significant — tape too THIN that day** (38-78 re-prices vs 300-450 WTI/Brent); evidence
  about the tape, not lag-absence (first-try-not-only-try). Busy natgas days are outside Yahoo's 7-day 1m window.
- **Across 19 significant contracts on 2 hubs, Kalshi NEVER leads.** One-way causality: NYMEX/ICE → Kalshi,
  ~half of liquid contracts re-price a FULL MINUTE late. Lag-0 half may still lag sub-minute (1m bars can't see it).
- ECONOMICS (Greg: fees fine if even a small run): taker ~1.75¢/side at mid; near-ATM the binary transfer function
  is steep → one futures level ≈ 10-25¢ probability move vs ~5¢ toll. The stale-quote reprice can pay the toll
  alone; 1-2 more levels in-direction = profit. Sub-minute infra NOT needed to beat a 60s re-price.

### Signal work (all leakage-gated, zero synthetic)
- **`release_book_signal.py`** (live path): direction=book_imbalance sign on unified YES book; magnitude/fade=
  imbalance+dipole exhaustion (channels = the two BOOK SIDES — no trade tape in live snapshots); calendar gate,
  coarse surprise only. Leakage PASS 0/30; read path validated on real live books. Fires when release-spanning
  bins accrue (first shot: EIA natgas Thu 7/16 14:30 UTC).
- **`release_signal_history.py`** (historical path, REAL signed flow): pooled first pass ~coin-flip — but TWO
  lessons: (1) **settlement-convergence contamination** (Greg's catch): daily contracts snap to 0/100 into the
  daily settle (mechanical, unpredictable-by-flow); filtering it moved placebo 0.443→0.470. Per-series SETTLE_UTC
  + guard now in the harness. (2) The pooled hit-rate is the WRONG LENS (see the new standing rule) — rebuild
  per-trade.
- **`kalshi_weather_forecast.py`**: EIA-based storage-number baselines (climatology MAE 32.2 / persistence 33.7,
  861 real weeks, walk-forward) + kalshi_score bridge. **Greg: his weather forecaster is spec'd separately —
  LEAVE THE WEATHER BUILD ALONE** (this bridge just scores any (value,sigma) forecast; weather nuance > cold-bias,
  deferred to Greg).
- 7/9 natgas print recap: actual +61B vs street +60B (in-line, non-event — the thesis in data).

## NEW STANDING RULES / FRAMES (S80, Greg, load-bearing)

1. **EACH TRADE INDIVIDUALLY, NEVER AVERAGE** — written into CLAUDE.md as a platform rule
   (`each-trade-individually-never-average`). A pooled hit-rate manufactures nulls out of structure. Evaluate per
   trade, conditioned on that trade's own context; characterize distributions + per-trade fingerprints, never lead
   with the mean.
2. **THE LEVEL-HIT REFRAME (Greg's 2.00→1.95 frame):** the prediction unit is a LEVEL-HIT EVENT, not a time
   window. Nat gas bid 2.00 gets hit → predict BEFORE 1.95 trades: does it get hit (momentum vs none)? If yes:
   does the direction continue, big or small? Features at each event: book+flow imbalance, dipole exhaustion,
   velocity (how fast levels are falling), far-side fuel (resting depth below). Two-stage output: (1) next-level
   hit? (2) continuation + size class. News/weather = conditioning factors on the event, not the trigger.
3. **HERD > WHALE for continuation (corrects the Phase-1.5 mapping):** WHALE = one decision-maker, finite
   inventory, incentivized to whipsaw/reverse/end abruptly → do NOT trust continuation; scalp the reprice only.
   HERD = many actors arriving over time = fuel keeps arriving → steep AND sustained; **herd SIZE/BREADTH is the
   magnitude predictor**. Tape discriminators: breadth (many varied clip sizes, accelerating arrival) vs whale
   (repeated similar clips, persistence w/o participation). Key ratio ≈ imbalance × breadth. Kalshi tape has
   sizes+aggressor (breadth inferable); no trader IDs (breadth ≈ clip-diversity proxy). Hypothesis to SCORE on
   the historical tape, not assume.
4. **News taxonomy beyond releases (Greg):** war, pipeline breaks, capacity online, sanctions, LNG, freeze-offs —
   each CATEGORY needs a historical importance score. Two approaches: (a) news-first — extend the S78 RSS
   keyword map to these categories, score each via the coupling engine (excess move vs placebo, direction hit,
   decay time); free timestamped-headline archives are shallow → accrues forward. (b) move-first — scan deep
   underlying history for big moves with NO release/weather driver = the unexplained-jump budget (how much of
   total movement each catalyst class owns). Do both; (b) works on deep history immediately.
5. **Two-layer architecture settled:** underlying futures ladder = the DRIVER (level-hits, whale/herd, news);
   Kalshi book = the VEHICLE (execution + the transfer function). The LAG is the bridge — futures move = leader
   signal, Kalshi stale quote = entry; reprice pays the toll, continuation (herd-gated) is the profit.
6. Weather: **deferred to Greg** (his spec; more nuanced than cold-bias). Historical-data reality: Kalshi history
   gives trades+candles but NOT book depth → flow/exhaustion validates historically; depth-imbalance + fills only
   accrue live.

## NEXT (S81 priorities — Greg delegated the ordering)
1. **Per-trade level-hit dataset on the historical WTI tape** (the each-trade-individually rebuild): every
   level-hit event as its own row — context (moneyness, side, time-of-day, release flag, velocity, breadth/whale
   fingerprint, exhaustion state) + outcome (next level hit before reversal? run length, net of that strike's
   actual spread+fee). Then look at DISTRIBUTIONS / fingerprints of the winners, never a mean. This is the
   foundation for the continuation predictor.
2. **Thursday 7/16 EIA natgas** (14:30 UTC): the live collector spans it → first real release-day book test
   (`release_book_signal.py --test`) + the busy-day natgas lag measurement (live 1m futures + the accruing book).
3. **Sub-minute lag resolution** on the lag-0 WTI half: Pyth (Kalshi's own settlement source) or another fine
   futures feed.
4. News-category importance score: start with move-first (deep history, free) per rule #4b.
5. Standing: consensus_poll near releases (before=forecast, after=actual via EIA — `kalshi_weather_forecast.py`
   fetches EIA actuals already); paper loop RSA creds (Greg, later); AGA pre-2002 (bonus).

## Files this session
New: `research/kalshi/release_book_signal.py`, `kalshi_weather_forecast.py`, `kalshi_history.py`,
`release_signal_history.py`, `futures_kalshi_lag.py`. Edited: `.gitignore` (+`data/kalshi_hist_trades/`),
`CLAUDE.md` (+S80 platform rule). Local-only: `data/kalshi_hist_trades/` (496k+ WTI trades, 1 natgas + 1 Brent day),
`data/kalshi/consensus.jsonl` + `weather_forecasts.json`.
