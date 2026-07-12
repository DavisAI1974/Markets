# WEATHER (daily-high temp) — baseline bar + trade mechanics (S82, 2026-07-13)

Scoreboard-side reference for the Kalshi daily-high-temperature markets (`KXHIGH*`). The OD-weather
FORECASTER itself is Greg's spec (HANDS OFF); this records (a) the naive baseline the operator must beat,
and (b) how a trade actually pays, so the "bar to beat" and the economics are on record for when the
operator firms up. All numbers from `kalshi_score.py` on real settled Kalshi events; zero synthetic.

## The market structure
- Product: **daily high temperature** at a city's official station, listed for ~12 cities (`KXHIGHNY`,
  `KXHIGHCHI`, `KXHIGHLAX`, `KXHIGHDEN`, `KXHIGHAUS`, + `KXHIGHT*` ATL/BOS/DAL/HOU/PHX/SATX/SFO).
- Ladder: a **partition** of ~**6 mutually-exclusive buckets, ~2°F wide**, re-centered each day around the
  expected high (open-ended `<=X` / `>=Y` tails). Exactly one resolves YES (100¢), rest NO (0¢). Mid-price
  = market-implied probability.
- Horizon: **same-day** (settles after the afternoon high locks). Capital locks intraday → model annualized
  return; capacity is BREADTH (12 cities × daily × 6 buckets), not depth (books are thin).

## The baseline bar (walk-forward persistence + climatology; 52 events each; Brier 0-2, lower better)
POOLED numbers — kept only to show the range; **the pooled mean is the WRONG lens** (see the per-regime
split below, which is the number that actually matters). NEVER size off these.
| City | Persistence | Climatology | best naive bar |
|------|------------|-------------|----------------|
| NY (`KXHIGHNY`)  | 1.12 | 1.14 | **1.12** |
| Chicago          | 1.31 | 1.33 | **1.31** |
| Denver           | 1.21 | **1.11** | **1.11** |

**Why so high — the load-bearing read:** the ladder is a narrow ~12°F re-centered window, and NY/CHI/DEN
have big **frontal-passage swings** (NY late-May tape: 92→66→68→57→56→73). So the naive baselines are
BIMODAL — near-perfect on calm days (persistence May-24: fc 57 / realized 56 → Brier 0.07), catastrophic on
transition days when yesterday's value falls outside today's re-centered ladder (May-21/May-25 → Brier ≈2.0).
**The edge lives entirely on the transition (frontal) days.** On calm days the market, persistence, and
climatology are all already near-perfect — no room. If the OD operator can call a next-day frontal swing
better than persistence, that is where both the Brier improvement AND the market edge concentrate. Denver's
climatology beating persistence (1.11 < 1.21) fits — it mean-reverts to a hot July climatology.

Caveats (Result Discipline): the absolute Brier depends on sigma calibration; and the market baseline is
still the post-hoc `settled_last_price` placeholder — beating persistence/climatology is NECESSARY, not
SUFFICIENT. The real "beat the market" test activates once `data/kalshi-bins` accrues across live `KXHIGH*`
settled events (the collector watches all 12; a genuine lead-time market distribution then replaces the
placeholder in `kalshi_score.py`).

## PER-BUCKET, NEVER POOLED — the platform rule applied to weather (load-bearing, Greg S82)
`each-trade-individually-never-average` / `deploy-signal-per-cell-not-universal` applies here in full. **Do
NOT measure a yearly or monthly Brier and call it the edge.** A pooled average across a season blends
regimes that behave nothing alike and describes NONE of them — it manufactures a null out of real
structure. Split the history into REGIME CELLS, find the edge PER CELL, and deploy only on the cells that
clear. The pooled baseline table above (NY 1.12, CHI 1.31, DEN 1.11) is exactly the wrong lens; here is the
same persistence baseline split by regime — the number that matters:

| City | calm (\|Δ\|≤3°F) | transition (\|Δ\|>3°F) | pooled (misleading) |
|------|-----------------|------------------------|---------------------|
| NY (`KXHIGHNY`)  | **0.73**  (n=24) | **1.45**  (n=28) | 1.12 |
| Chicago          | **0.91**  (n=21) | **1.58**  (n=31) | 1.31 |
| Denver           | **0.92**  (n=19) | **1.38**  (n=33) | 1.21 |

The pooled 1.12 describes neither the 0.73 calm regime nor the 1.45 transition regime — it is an average of
two different worlds. Persistence's right-bucket hit-rate collapses from ~0.23–0.34 (calm) to ~0.05–0.16
(transition). **The tradeable edge lives in the transition cell**, where the naive baseline (and the market
that leans on it) is weakest — never in the pooled mean.

**The weather cells (analogous to moneyness × side × velocity × release on the level-hit dataset):**
- **Regime: calm vs transition (frontal passage)** — the primary split. TRADEABLE only if classified
  PRE-hoc: recent variance of highs, NWP/ensemble spread, a front in the forecast, or the operator's own
  predicted swing. (The table above splits post-hoc on |realized − yesterday| only to PROVE the pooled mean
  is misleading; a live signal must call the transition before the day resolves.)
- **City** — never pool across cities. LAX (marine-clamped, \|Δ\|~1°F, efficient) and Denver (continental,
  \|Δ\|~5°F, volatile) are different markets; a blended Brier is meaningless.
- **Synoptic season** — spring/fall frontal season vs a stable summer ridge (the same per-regime logic the
  natgas degree-day study used; do NOT pool across the calendar).
- **Bucket moneyness** — center-of-ladder (near-ATM) vs open-ended tail bucket (`>=86`): different edge,
  different fee, different fill.
- **Swing direction** — warming vs cooling transition may score differently; keep them separate until the
  data says they don't.

Rule: report "edge on {transition × Denver × spring}, not on {calm × LAX}", never a single yearly Brier.
Partial coverage is not failure — a cell that clears is kept and deployed on that cell.

## How a trade pays (worked example — REAL event `KXHIGHNY-26JUN29`, realized high = 88°F)
Real ladder that day (6 buckets): `[<=79] [79-80] [81-82] [83-84] [85-86] [>=86]`. Realized 88°F →
the top bucket **`>=86` resolved YES**; the day ran hotter than the ladder was centered.

Illustrative morning prices (¢ = implied prob) vs an OD forecast that called the hot spike:

| bucket | market price | OD forecast fair | edge |
|--------|-------------|------------------|------|
| ≤79    | 8¢  | 2%  | — |
| 79-80  | 12¢ | 5%  | — |
| 81-82  | 22¢ | 10% | — |
| 83-84  | 28¢ | 18% | — |
| 85-86  | 18¢ | 25% | +7¢ |
| **≥86**| **12¢** | **40%** | **+28¢ (underpriced)** |

**The trade:** buy 100 contracts of the `>=86` YES at 12¢.
- Entry cost: 100 × $0.12 = **$12.00**
- Fee (Kalshi: `round_up(0.07 × C × P × (1−P))`): 0.07 × 100 × 0.12 × 0.88 = $0.74
- Total out: **$12.74**

**If it wins (it did — realized 88 ≥ 86):** each contract pays $1.00 → 100 × $1 = **$100.00**.
- Net profit = $100.00 − $12.74 = **+$87.26** on the trade.

**If it had lost (e.g. realized 84, mid-ladder):** `>=86` resolves NO → contracts pay $0 → lose the
**$12.74** stake (max loss = stake; fully collateralized, no margin call).

**Why it's +EV to do repeatedly (the real point — not the one lucky win):** at the forecast's fair prob
0.40, expected value per contract = 0.40 × $1 − $0.12 entry − ~$0.007 fee ≈ **+$0.27/contract**. The edge is
buying the bucket the market under-weighted because it centered the ladder too cool. This is the
transition-day edge from the baseline read: the market (and persistence) both under-weighted the top bucket
on a hot-spike day; a forecaster that called the spike captures `>=86` cheaply.

**Trader economics recap:** profit/contract = (settlement − entry price) − fee, ×$1. Kalshi is a
CFTC-regulated exchange (central limit order book); you trade against other participants/market-makers, not
the house — which is why a real outcome-forecast edge survives (Kalshi's revenue is the trading FEE +
float, not a counterparty vig). You can exit before settlement by selling back into the book. For weather:
small, same-day, breadth-of-cities bets; the binding cost is usually the bid-ask spread (fee is tiny at the
low-priced tail buckets); the binding requirement is a distribution that beats the market's already-sharp
implied ladder on the transition days.

## Reproduce
```
python research/kalshi/kalshi_score.py --series KXHIGHNY --lookback-days 40                       # market self-calib (placeholder until bins accrue)
python research/kalshi/kalshi_score.py --series KXHIGHNY --lookback-days 40 --forecast fc.json    # score a forecast vs realized (+ market)
# fc.json: {"KXHIGHNY-26JUN29": {"value": 87.0, "sigma": 2.5}, ...}   (walk-forward persistence/climatology built the same way)
```
