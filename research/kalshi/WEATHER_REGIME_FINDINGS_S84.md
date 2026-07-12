# WEATHER per-regime scoreboard — findings (S84, 2026-07-12)

Scoreboard-side only (the FORECASTER is Greg's spec, HANDS OFF). Runner:
`research/kalshi/weather_regime_score.py`; data `research/kalshi/weather_regime.json`. 68 settled
days per city (2026-05-06 -> 07-12), Kalshi settlement API, zero synthetic. Leakage gate PASS
(66/66 days each city — every walk-forward `(value,sigma)` proven byte-invariant to future days).

This SHARPENS `WEATHER_BASELINE_S82.md`, which reported per-regime **means** of persistence only.
Reporting the **distribution** per cell (median / IQR / max + right-bucket hit-rate) and adding
**climatology per regime + swing direction** flips the headline.

## The per-cell table (persistence vs climatology; Brier median(IQR)max, lower better; mkt* = post-hoc placeholder)

| city | cell | n | persistence med(IQR)max | pers hit | climatology med(IQR)max | clim hit |
|------|------|---|-------------------------|----------|--------------------------|----------|
| DEN | calm | 22 | **1.17**(1.08-1.24)1.51 | 0.18 | 1.35(1.15-1.63)1.85 | 0.14 |
| DEN | transition | 44 | 1.42(1.32-1.70)2.00 | 0.14 | **1.42**(1.05-1.65)1.92 | 0.19 |
| DEN | transition x warm | 26 | **1.46**(1.36-1.74)2.00 | 0.12 | 1.52(1.12-1.70)1.92 | 0.12 |
| DEN | transition x cool | 18 | 1.40(1.27-1.57)1.93 | 0.17 | **1.31**(0.53-1.50)1.73 | 0.28 |
| NY | calm | 29 | **1.02**(0.25-1.13)1.31 | 0.35 | 1.21(1.10-1.63)1.98 | 0.17 |
| NY | transition | 37 | 1.52(1.31-1.80)2.00 | 0.08 | **1.27**(0.98-1.50)2.00 | 0.19 |
| NY | transition x warm | 20 | 1.71(1.43-1.81)2.00 | 0.00 | **1.37**(1.21-1.90)2.00 | 0.05 |
| NY | transition x cool | 17 | 1.33(1.08-1.64)2.00 | 0.18 | **1.16**(0.19-1.27)1.83 | 0.38 |
| CHI | calm | 24 | **1.07**(1.01-1.21)1.43 | 0.17 | 1.43(1.22-1.67)1.98 | 0.17 |
| CHI | transition | 42 | 1.58(1.37-1.86)2.00 | 0.00 | **1.56**(1.21-1.78)2.00 | 0.10 |
| CHI | transition x warm | 24 | 1.61(1.43-1.87)2.00 | 0.00 | **1.61**(1.26-1.90)2.00 | 0.00 |
| CHI | transition x cool | 18 | 1.53(1.18-1.86)2.00 | 0.00 | **1.29**(0.75-1.60)1.82 | 0.22 |

`mkt*` (post-hoc settled last-price) is ~0.003 in every cell — a near-certain placeholder, NOT the
real lead-time bar. The real market baseline activates once `data/kalshi-bins` accrues across many
settled `KXHIGH*` events (right now the branch holds only a ~13h rolling window, 3 events/city).

## The two load-bearing findings (distributions revealed them; the S82 means hid them)

1. **The naive bar is REGIME-CONDITIONAL — it switches baseline.** Persistence wins **calm**
   (NY 1.02 vs clim 1.21; today ~ yesterday). Climatology wins **transition** (NY 1.27 vs pers 1.52;
   CHI/DEN similar). So the benchmark the operator must beat is a regime-switched
   `max(persistence, climatology)`, never either alone. S82's single "best naive bar per city" (NY
   1.12) is the average of two different worlds and describes neither.

2. **Climatology's transition edge is COOLING mean-reversion into the wide tail buckets — NOT a front
   forecast, and it does nothing for warming spikes.** The per-event tape shows climatology's
   transition wins concentrate on big cooling days where the realized drops into an open-ended tail
   (`<=X`) and the seasonal-mean anchor sits in that same tail (NY 05-29 clim 0.13, 06-08 0.02,
   06-16 0.43, 07-05 0.00, 07-06 0.21 — all cooling, all tail-bucket winners). It wins there for two
   reasons, honest about both: (a) it hedges WIDER (trailing std of realized values ~ 2x persistence's
   std of day-over-day deltas) so it avoids the confident-wrong 2.0, and (b) genuine central-tendency
   capture — a cooling front reverts toward the seasonal mean, which IS climatology's estimate.

3. **WARMING transitions are where BOTH naive baselines (and, per the S82 example, the market) go
   blind — that is the operator's real room.** Persistence hit-rate is **0.00** on warming
   transitions in NY and CHI; climatology only 0.00-0.05. A warm spike prints a NEW high above the
   re-centered ladder (NY 07-03: realized 100, +7; pers Brier 1.82, clim 1.997 — the `99-100` bucket
   neither reached). This is exactly the `KXHIGHNY-26JUN29` worked example in S82 (hot spike -> `>=86`
   top bucket underpriced). Persistence CANNOT hit a transition bucket almost by construction (it bets
   yesterday; the day moved away).

## What this means for the operator's bar (when Greg's forecaster emits (value,sigma))

- Score it PER CELL through this runner (drop-in: same `gaussian_over_buckets` path). Beating the
  **pooled** persistence bar is trivial and meaningless.
- The bar to clear on **transition** is CLIMATOLOGY (~1.27 NY / ~1.56 CHI / ~1.42 DEN), not
  persistence. On **calm** it is PERSISTENCE (~1.0 NY) and there is little room — the market is
  already sharp there.
- The biggest room is **warming-transition / hot-spike** cells (both baselines ~2.0, hit ~0): call
  the magnitude of a warm spike and the top/tail bucket is cheap. Secondary room: call cooling-front
  magnitude better than the seasonal anchor.
- Denver is a stable July ridge (small swings, edge thin); NY is the transition-rich book (biggest
  swings, biggest naive-baseline failure -> biggest room). Report "room on {NY x transition x warm},
  thin on {DEN x calm}", never a pooled Brier.

## Caveats (Result Discipline)
- Regime label (|realized - yesterday| > 3 degF) is POST-HOC — it characterizes the baseline's
  failure mode; a LIVE signal must classify the front PRE-hoc (operator's job). No leakage in the
  baselines themselves (gate PASS).
- Absolute Brier depends on the sigma calibration (SIGMA_FLOOR=1.5; persistence sigma = trailing std
  of deltas, climatology sigma = trailing std of values). The regime SWITCH and the hit-rate gaps are
  robust to this; the absolute levels are not — do not size off the absolute numbers.
- Market baseline is still the post-hoc placeholder; "beat climatology on transition" is NECESSARY,
  not SUFFICIENT until the real lead-time market ladder (accruing bins) replaces it.
- Two regimes is the S82 minimum; the warm/cool swing split already sharpens it. Refine toward the
  synoptic types (ridge / cold-frontal / warm-front / marine-clamp / post-frontal) as a pre-hoc
  classifier and more history allow.

## Reproduce
```
python research/kalshi/weather_regime_score.py --cities KXHIGHDEN,KXHIGHNY,KXHIGHCHI \
    --lookback-days 400 --clim-window 21 --transition-threshold 3 --out research/kalshi/weather_regime.json
```
