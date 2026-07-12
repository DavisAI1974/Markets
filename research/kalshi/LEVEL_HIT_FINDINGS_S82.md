# LEVEL-HIT DATASET — findings (S82, 2026-07-13)

The per-trade LEVEL-HIT continuation dataset (the S80 priority-1 reframe, finally built). Builder:
`research/kalshi/level_hit_dataset.py`; output `data/level_hits_KXWTI.json` (local). Ran on the full
re-pulled 496,306-trade WTI tape (46 daily events × top-12 strikes). Per-cell, distributions not means,
leakage-gated. Zero synthetic. **Provisional — this is a research map, not a live edge.**

## What a level-hit event is
Each 1¢ price transition on a strike's trade tape = a level-hit at level L travelling in a direction.
The question (Greg's reframe): does the move CONTINUE to the next level (L+dir) before it REVERSES
below entry (L−dir)? Context is measured strictly PRE-hit over the last 20 trades (leakage-gated);
outcome is the forward trailing-exit walk, bounded by the daily-settle exclusion.

- `continued` = reached L+dir before L−dir (the 1-level poke).
- `big_run` = run_length ≥ 2 levels (the paying tail; a poke that round-trips still loses the toll).
- `net_cents` / `net_maker` = trailing-exit P&L net of the strike's REAL Kalshi fee, taker vs maker entry.

## Headline (Result Discipline — this is a fee-bound / weak-internal-edge result, honestly)
1. **200,421 level-hits, leakage PASS (0/… fails).** The context closure is invariant to future trades.
2. **Level-hits MEAN-REVERT at the 1¢ scale.** Overall continue_rate **0.383 < 0.5**; big-run rate **0.24**;
   run-length median **0** (most reverse immediately). At 1-cent granularity the bid/ask bounce dominates.
3. **No cell pays on average — even at MAKER fees.** Best cell maker-mean **−0.63¢**; cross-cell aggregate
   maker-mean **−1.45¢**, maker pos_frac **0.13**. Trading level-hits blindly loses in every one of 60 cells.
   This **confirms S81 at per-trade granularity: the edge is SIZE-vs-FEE, not raw continuation.**
4. **Cell splits barely move net** — the toll dominates everywhere:
   - release −1.45 vs non-release −1.45 (rel continues slightly LESS: sell-the-news / spike already spent)
   - fast −1.52 vs slow −1.40 (fast moves continue no better once you pay to chase them)
   - deep-moneyness −1.24 vs mid −1.61 (deep loses LEAST — tiny fee — but continues LEAST, 0.33 vs 0.39)
   The winner cells (least-negative) cluster on **deep-moneyness × release** = smallest fee × catalyst.
5. **The pre-hit ORDER-FLOW context barely predicts a big run.** Winner-fingerprint lift (share among
   run≥2 minus base share) is weak: herd/whale +0.00…+0.01, dipole exhaustion/expect +0.00…+0.03. The
   single strongest feature is **`aggr`** (the aggressor side of the *hitting* trade, +0.05) — i.e. the
   momentum of the hit itself, not the prior flow (and it is near-tautological with `dir`, so discount it).

## The meta-conclusion (what this tells the program)
The **Kalshi-INTERNAL continuation predictor is weak and fee-bound.** Herd/whale breadth, dipole
exhaustion, and pre-hit imbalance — the internal microstructure context — do NOT strongly separate the
level-hits that run from the ones that revert. This is not a failure of the dataset; it is a real,
disciplined negative that **sharpens the case that the tradeable edge is EXTERNAL** — the futures→Kalshi
LAG (S80/S81), not the Kalshi book's own flow. The level-hit that becomes a run is most plausibly the one
driven by a NYMEX/ICE move — which is NOT in this tape.

## NEXT (the natural upgrade)
Join the **Pyth futures move** onto each level-hit as a context feature (needs `data/pyth-ticks`, priority
#1, accruing from Sun-eve reopen): a `futures_move_bps` / `lag_seconds` column per level-hit event. The
hypothesis this dataset sets up: **continuation big-runs concentrate on level-hits that TRAIL a fresh
futures move** — the internal context is weak precisely because the driver is external. That join turns
this scaffold into the real continuation predictor.

## Reproduce
```
python research/kalshi/kalshi_history.py --series KXWTI --all --top 12 --skip-candles      # ~7 min, 496k trades
python research/kalshi/level_hit_dataset.py --series KXWTI --min-cell 40 --out data/level_hits_KXWTI.json
```
Knobs: `--window` (pre-hit trades), `--big-run` (run threshold), `--entry-slip`, `--max-forward-s`,
`--settle-guard-s`, `--min-cell`. Cells = moneyness × side × velocity-regime × release.
