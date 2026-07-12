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
