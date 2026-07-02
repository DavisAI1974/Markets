# S50 FINDINGS — per-cell DOLLAR-capacity model (Coinbase-first / SOL-focus decision)

`scripts/_capacity_model.py` (+ `_capacity_model_results.json`). Reuses the deployable pipeline
(`build_channels` → `detect_flips` → `simulate_swing_maker`, cover-grace, sized OFF) to get the real swing
legs, then overlays a size-dependent fill **bounded by the ACTUAL opposing trade flow per leg** (a passive
quote of size S fills only as much as the real opposing $ that trades through it before the turn). mk0/tk5,
same 29.2h window as S49 (btc = its 196h control book). Answers Greg's "same volume to make the same money?"

## The deployable zone (clean fills, ~85–93% fill = realistic sizes)
| cell | turns/hr | net/leg | median leg-cap $ | $/hr @ $500/leg | $/hr @ $1k/leg | saturation (≥90% fill) |
|------|----------|---------|------------------|-----------------|----------------|------------------------|
| **SOL** | 155 | +1.75 bps | $5,005 | **+13** | **+24** | ~$500/leg |
| XRP  | 140 | +1.16 | $3,536 | +7  | +14 | ~$500 |
| ETH  | 162 | +0.55 | $10,976 | +4  | +9  | ~$1,000 |
| DOGE | 53  | +1.35 | $934   | +3  | +5  | ~$0 (thin) |
| BTC  | 40  | +0.52 | $15,598 | +1  | +2  | ~$1,000 |

**In the realistic zone SOL leads** — best net/leg (real spread), high turn rate, and enough depth to fill
$500–1k/leg cleanly. SOL flat @ ~$1k/leg ≈ **+$24/hr ≈ ~$17k/mo** (mk0, one/two windows, optimistic fill).

## The size-scaling curve + the WRONG-TAIL CEILING (the load-bearing finding)
$/hr rises with deploy size (fewer fills, more $ per turn) but does NOT rise forever. At S→∞ (capture all
opposing flow) the cells split:

| cell | $/hr @ $50k/leg | ceiling (S→∞) | win-leg mean-cap | lose-leg mean-cap | corr(cap, net) |
|------|-----------------|---------------|------------------|-------------------|----------------|
| **SOL** | +242 | **−204** | $11,950 | **$21,534** | **−0.12** |
| ETH  | +263 | +868 | $29,174 | $28,110 | +0.12 |
| XRP  | +116 | +89  | — | — | + |
| BTC  | +52  | +67  | — | — | + |
| DOGE | +29  | +15  | — | — | + |

**On SOL the losing legs carry ~2× the flow of the winners** (big swings that keep going = the wrong-tail =
the high-volume moves), so **uncapped size fills losers hardest and flips the strategy negative** (flow-weighted
net −$5,966/window). This is a capacity-level proof that naive size-maxing on SOL is self-defeating, and a hard
argument FOR (a) a per-leg size CAP and (b) the conviction SIZING we already built (`size_legs`, size up
predicted winners / keep losers small) — flat sizing is exactly what produces the negative tail. ETH's ceiling
looks huge only because its flow is uncorrelated with losing, but that edge is thin TIMING on a spread-starved
book (0.06 bps spread) — the number most exposed to the model's optimism.

## Answers to the two questions
1. **"Same volume on the top coins to make the same money?" NO.** Volume/depth is wildly uneven and does not
   line up with per-trade edge. SOL is the standout in the realistic zone; DOGE has the 2nd-best net/leg but
   almost no capacity (saturates at ~$0/leg, med leg-cap $934); BTC/ETH have depth but thin (timing) edge.
2. **SOL-first is the right initial focus** — best realistic $/hr, real spread (structural edge, least
   model-dependent). Modest in absolute $ at clean fills (~$17k/mo flat), scales with a size cap + conviction
   sizing up to an optimal per-leg cap, beyond which the wrong-tail drags it down.

## CAVEATS (honest)
- **All mk0 (zero maker).** On Coinbase that needs the $250M+/30d VIP tier or the ~$500K/mo upgrade program —
  **not realistically reachable → the rebate-venue pivot** (Greg S50). These $/hr are the *deployable-venue*
  numbers, contingent on securing maker fee ≤ 0.
- **Fill model is OPTIMISTIC** (full net_bps on the filled portion, no walk-the-book / price-impact markdown for
  resting deeper than top-of-book). Real numbers are LOWER, most so at large size and on ETH/BTC (spread-starved).
  A v2 adverse-selection-with-depth markdown is the next refinement.
- **One/two windows.** The forward ledger keeps accruing (paper cron); capacity should be re-measured as it grows.

## NEXT
1. **SOL-first**: pick 1–2 rebate venues (market-maker-agreement path, not a volume wall), collect their SOL
   book, re-measure spread + fill there (per-cell rule — a rebate on a tight/deep book won't print).
2. Wire a per-leg **size cap** + the conviction `size_legs` into the deploy sizing (the wrong-tail ceiling says
   this is mandatory on SOL).
3. v2 fill model: walk-the-book / adverse-selection markdown so the $/hr at large size is honest.
