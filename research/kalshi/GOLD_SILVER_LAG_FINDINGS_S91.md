# Gold + Silver depth-add — lag validation (S91)

Greg S91: expand the proven futures->Kalshi LAG edge onto more Kalshi markets (depth). Gold/silver
(KXGOLDD/KXSILVERD) settle on the SAME "Pyth 1-min candle @5PM EDT" mechanic as KXNATGASD, so the
lag-join + settlement-oracle pipelines reuse verbatim. Two edges tested, both FREE (no paid tape):

## 1. Cross-strike (Kalshi-internal) — WEAK on metals (an NG thing)
`lag_exploit_backtest --mode crossstrike`, 5 days each, leakage PASS, real lead-lag present.
The per-cell numbers recorded here were net of the spread toll, which was removed from the program
(2026-11-16). They are not kept. Rerun gross if the cross-strike read is wanted again.

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
cross-strike (secondary) edge does not transfer. Remaining validation: the lag at sub-minute resolution -> needs the
tick tape (free 1-sec Pyth first; paid COMEX GC/SI to nail it). Feeds now collected: Pyth XAU/XAG live
(pyth_collector) + KXGOLDD/KXSILVERD books (kalshi_collector).

Data: Kalshi ladders `data/kalshi_hist_trades/KX{GOLD,SILVER}D/` (local, re-pullable). Scans in scratchpad.
