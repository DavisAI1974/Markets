# S63 KRAKEN PER-COIN DEPLOY MAP (per-cell law — keep what works for each coin)

All at **kr_mk0 (0bp maker)**, one 30d window, net $/hr @ $5k. Fill model is the standing gate on
every row (the ride depends on real 0bp maker fills — books accruing). "Different solution per coin."

| coin | SIGNAL | direction | entry | exit / mgmt | net $/hr | gate | status |
|---|---|---|---|---|---|---|---|
| **ETH** | flow-lean flip detector (W600/REV0.1) | **forward** | early-arm **eps10** | ride to next flow-turn, **no mgmt** | **+9.50** | PASS z=4.0, reversed loses | KEEP |
| **BTC** | flow-lean flip detector | **forward** | early-arm **eps5** | ride to next turn, **no mgmt** | **+8.64** | PASS z=3.0, reversed loses | KEEP |
| **SOL** | flow-lean flip detector | **REVERSED** | **base (NO early-arm — it hurts SOL)** | ride, **no mgmt** | **+2.33** | forward anti (z=−1.6) → reversed | KEEP (fragile) |
| **DOGE** | **fade-the-8h-trend** (different tool) | fade | at entry | ride | **+2.73** | fade PASS p=0.016; flow-lean only marginal (z=1.5) | KEEP (data-limited, 3% tape cov) |
| **XRP** | flow-lean not sig (z=0.7); price-zz ~null; fade-8h marginal | — | — | — | ~0 | nothing clears | STAND ASIDE (needs its own solution) |

## Per-coin decisions that are LOCKED this session
- **ETH/BTC = forward flow-lean zigzag + early-arm entry, ride to the turn.** Early-arm eps is
  per-coin (ETH 10, BTC 5). No loss management.
- **SOL = REVERSED signal** (the forward detector is anti-predictive on Kraken spot — its bybit edge
  was perp+rebate). And SOL does NOT want early-arm (it hurt: −0.68) → SOL rides the base reversed
  detector. SOL is the fragile cell.
- **DOGE = the fade-8h DIRECTION tool, not the flow-lean zigzag** (the zigzag was only marginal on
  DOGE; the fade cleared). A genuinely different solution for this coin.
- **XRP = stand aside for now** — none of the three tools clears; it needs its own solution.

## Dropped (per-cell checked, not global dogma)
- **Flip-or-bail loss management: dropped on ETH/BTC/SOL** — tested each, helps none (the zigzag's own
  turn-exit beats a fixed stop; dips-that-recover get clipped; taker fees on managed legs kill it;
  SOL churns). Not tested where the base signal already fails (XRP/DOGE) — moot there.

## The one gate over all KEEP rows
Every KEEP row assumes **0bp maker fills at the turns**. That is now the decisive, per-coin unknown —
build the maker-fill model from `data/*-kraken-book` (via `odcore/swing_maker.py`) and re-grade each
KEEP cell fill-realistically. A cell that can't get filled at maker drops off the map regardless of
its paper $/hr.

## UPDATE (deep bail — Greg, §15): fire ONLY at big depth
At big negative depth the trade is a DEAD loss (recover-to-PROFIT ~0% by −80). A deep bail clips no
winners and caps the −150/−200 tail for free:
- **BTC: deep bail at −80** (+8.74 vs ride +8.64 — a hair positive + tail cap).
- **ETH: deep bail at −100** (+9.36 ≈ ride +9.50 — ~free tail cap).
- **SOL: no deep bail** (reversed signal churns; taker bail nets negative).
Bail (taker flatten) beats FLIP at depth (continuation only ~58%, not worth the 22bp flip). Fire ONLY
at the deep threshold, never at shallow depths (shallow bail bled — §11/§12).
