# WEATHER per-regime scoreboard — findings (S84, 2026-07-12)

Scoreboard-side only (the FORECASTER is Greg's spec, HANDS OFF). Runner:
`research/kalshi/weather_regime_score.py`; data `research/kalshi/weather_regime.json`. 68 settled
days per city (2026-05-06 -> 07-12), Kalshi settlement API, zero synthetic. Leakage gate PASS
(66/66 days each city — every walk-forward `(value,sigma)` proven byte-invariant to future days).

This SHARPENS `WEATHER_BASELINE_S82.md`, which reported per-regime **means** of persistence only.
Per Greg's rule (never lead with an average — even a per-cell median is an average), the headline is
the **per-DAY fingerprint**, and the cell medians are demoted to the footnote they should be. The
cell median blends two clusters that behave nothing alike and describes neither.

## THE HEADLINE — the per-day fingerprint (best-naive Brier, broken to the individual day)

The per-day Brier distribution is BIMODAL, and the split is a single mechanical structural signal:
**did the realized high land in a wide open-ended TAIL bucket (`<=X` / `>=Y`) or a narrow 2°F INTERIOR
bucket?**

| city | EDGE days (best Brier <0.5) | tail-bucket win | warm | WHIFF days (best >1.5) | tail-bucket win | warm |
|------|-----------------------------|-----------------|------|------------------------|-----------------|------|
| **NY**  | 17/66 (26%) | **100%** | 29% | 8/66 (12%)  | **0%**  | 75% |
| **DEN** | 12/66 (18%) | **100%** | 25% | 11/66 (17%) | 18%     | 82% |
| **CHI** | 8/66 (12%)  | **100%** | 12% | 15/66 (23%) | **0%**  | 73% |

- **Every near-perfect day (Brier ~0) is a wide open-TAIL win.** A diffuse forecast collects its mass
  in an unbounded bucket for free (NY 07-05 `<=98` 0.00, 06-08 `<=87` 0.02). **These are NOBODY's edge
  — the crowd prices a wide tail just as easily. No room.**
- **Every blind day (Brier ~2) is a narrow INTERIOR-bucket win, and 73-82% are WARMING.** A warm spike
  into a 2°F interior bucket the re-centered ladder under-weighted (NY 07-03 `99-100` +7°F Brier 1.82;
  05-17 `80-81` +14°F; 06-12 `90-91` +9°F). **THIS is the operator's room — and it is exactly the
  ">3°F over the upper bound" call the forecaster is built to make.**

The signal is pre-observable from the forecast's OWN predicted bucket: if it predicts a wide tail,
the market is already there (skip); if it predicts a warm spike into an interior/near-top bucket the
ladder centered too cool, that is the trade. Tail-vs-interior + swing is a LIVE gate, not a post-hoc
label.

## THE ROOM IS SEASONAL (time-bucketed — the pooled 68-day number flattened this too)

The whole-window fingerprint above STILL flattens across spring-frontal season -> summer ridge, two
different synoptic worlds. The operator's room (whiff = interior-bucket warm-spike miss) by half-month:

| city | 05a | 05b | 06a | 06b | 07a |
|------|-----|-----|-----|-----|-----|
| DEN | 3 | 1 | 3 | 2 | **0** |
| NY  | 0 | 3 | 1 | 0 | **2** |
| CHI | 3 | 4 | 2 | 2 | **0** |

**The room lives in the SPRING FRONTAL season (May-June) and largely DISAPPEARS in the early-July
ridge** — DEN and CHI both drop to ZERO whiffs in 07a (the persistent summer ridge means persistence
nails it: no misses, no room), only NY keeps some. This CORRECTS an earlier draft claim that the room
"rises into peak-summer heat" — measured, it is the opposite for 2/3 cities (Result Discipline: I
asserted a seasonal direction without measuring; the data reversed it). CAVEATS: (1) small-n —
buckets are 8-16 days, whiff counts 0-5, so the pattern is suggestive not settled; the summer fills it
in as bins/settlements accrue. (2) A July HEAT-DOME is a DIFFERENT overshoot mode than a spring
frontal swing (sustained record highs stacking above the ladder vs a one-day swing) and would be its
own cell — if the forecaster is lighting up mid-July, check whether it is catching a heat-dome
overshoot, not the May-June frontal whiff characterized here.

## Why the cell averages hid it (the demoted footnote)

`mkt*` (post-hoc settled last-price) is ~0.003 in every cell — a near-certain placeholder, NOT the
real lead-time bar (activates once `data/kalshi-bins` accrues across settled `KXHIGH*` events; the
branch currently holds only a ~13h rolling window, 3 events/city).

| city | cell | n | persistence med | climatology med |
|------|------|---|-----------------|-----------------|
| NY | calm | 29 | 1.02 | 1.21 |
| NY | transition | 37 | 1.52 | 1.27 |
| DEN | calm | 22 | 1.17 | 1.35 |
| DEN | transition | 44 | 1.42 | 1.42 |
| CHI | calm | 24 | 1.07 | 1.43 |
| CHI | transition | 42 | 1.58 | 1.56 |

Read as an average, "climatology wins NY transition 1.27 vs persistence 1.52" is TRUE but useless — it
is the mean of a 26% free-win cluster (Brier ~0) and a 12% blind cluster (Brier ~2). The switch of
baseline by regime (persistence=calm, climatology=transition) is real but SECONDARY: climatology only
"wins transition" because it hedges wider and its seasonal anchor happens to sit in the cooling-tail
buckets — it is not forecasting the front, and it does nothing on the warming-spike interior days that
ARE the room. Never size off these medians.

## What this means for the operator's bar (when Greg's forecaster emits (value,sigma))

- Score it PER DAY through this runner (drop-in: same `gaussian_over_buckets` path), and judge it on
  the **WHIFF cluster** — the interior-bucket warming-spike days where the naive is blind. Beating the
  naive on the EDGE (open-tail) days is worthless: the crowd is already there, no room.
- The operator's tradeable cell is **interior-bucket, warming-spike days** (the ">3°F over the upper
  bound" call). When the forecast predicts a warm spike into a bucket the ladder centered too cool,
  the YES is cheap and pays big (S82 `KXHIGHNY-26JUN29`: realized 88, `>=86` YES, +$87). This is
  low-frequency (NY 8/66, DEN 11/66, CHI 15/66) and high-payoff, and SEASONAL — concentrated in the
  May-June frontal season, near-zero in the early-July ridge for DEN/CHI (see the seasonal split). A
  July heat-dome overshoot is a separate cell to watch, not this frontal whiff.
- NY is the transition-rich book (biggest naive failure = biggest room); Denver is a stable July
  ridge (thin). Report "room on {interior-bucket x warming-spike}, none on {open-tail}", never a
  pooled or per-cell mean.
- Next scoreboard build (needs the forecaster's per-day output): score the ">3°F over upper bound ->
  buy top/interior YES" rule per-day, NET-OF-KALSHI-FEE, so we see the dollar capture on the days it
  fires, not just Brier. Blocked only on a sample of the forecaster's predicted highs.

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
