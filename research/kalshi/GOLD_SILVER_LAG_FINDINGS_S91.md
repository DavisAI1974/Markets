# Gold + Silver depth-add — lag validation (S91)

Greg S91: expand the proven futures->Kalshi LAG edge onto more Kalshi markets (depth). Gold/silver
(KXGOLDD/KXSILVERD) settle on the SAME "Pyth 1-min candle @5PM EDT" mechanic as KXNATGASD, so the
lag-join + settlement-oracle pipelines reuse verbatim. Two edges tested, both FREE (no paid tape):

## 1. Cross-strike (Kalshi-internal) — WEAK on metals (an NG thing)
`lag_exploit_backtest --mode crossstrike`, 5 days each, leakage PASS, real lead-lag present.
Net-of-toll (h2), per-cell:
- **NG (baseline):** down-triggered ITM/ATM/OTM/deepITM pay +1.6..+3.3c mean, 51-64% win.
- **Gold:** only ITM(65-85)|dn (+0.76c, 41% win) + deepITM|dn (+0.16c) scrape positive; most cells bleed.
- **Silver:** only deepITM|dn (+0.92c, 32% win) positive; almost everything bleeds.
Low win rates (32-41%) on the metals "winners" -> +mean rides rare fat tails, fragile. Per per-cell
rule: cross-strike WORKS ON NG, NOT metals. Caveats: trade-reconstructed quote, 5 warm-season days.

## 2. Futures->Kalshi look-ahead LAG — CONFIRMED on both (the real edge)
`futures_kalshi_lag.py` (S19 cross-cov lead-lag + 200x time-slide null), leading feed = FREE Pyth
XAU/XAG 1-min bars (benchmarks endpoint) around each event day; settle-window excluded (settle-1800).
| market | leading feed | contracts | significant z>=3 | direction | reprice +1min |
|--------|--------------|-----------|------------------|-----------|---------------|
| KXGOLDD | Pyth XAU/USD | 60 | 37 | FUTURES LEAD | 15/37 (~40%) a full min late |
| KXSILVERD | Pyth XAG/USD | 54 | 26 | FUTURES LEAD | 5/26 (~19%) a full min late |
Lag histograms: gold {0:20, +1:15, +2:1}; silver {0:18, +1:5, +2:1}. z up to 15.3 (gold) / 20.4 (silver),
cc up to 0.42-0.47. SAME structure as WTI/NG: futures move first, Kalshi reprices 0-1 min later.

**1-MIN = LOWER BOUND** (CLAUDE.md: 1-min undersamples; the "lag 0" contracts co-move WITHIN the minute
where the sub-minute lead hides). The free 1-sec Pyth (Hermes timestamp) or the paid COMEX GC/SI MBP-10
tick tape only sharpens it.

## Verdict
Gold/silver's PRIMARY edge (the lag) transfers cleanly from WTI/NG -> both are valid depth-adds. The
cross-strike (secondary) edge does not transfer. Remaining validation = the same one every lag faces:
does it clear NET-OF-FEE at tradeable SIZE (the size-vs-fee wall) at sub-minute resolution -> needs the
tick tape (free 1-sec Pyth first; paid COMEX GC/SI to nail it). Feeds now collected: Pyth XAU/XAG live
(pyth_collector) + KXGOLDD/KXSILVERD books (kalshi_collector).

Data: Kalshi ladders `data/kalshi_hist_trades/KX{GOLD,SILVER}D/` (local, re-pullable). Scans in scratchpad.
