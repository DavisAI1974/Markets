# S48 FINDINGS — job #2 done: COVER-GRACE cuts the taker rate to ~0% and lifts net-of-fee on all 5 cells

Branch `claude/crypto-liquidity-signals-s48-2h9hx8` (ff-merged up from the S47 tip e4a5f51 — the harness landed
stale on S37). ALL numbers PROVISIONAL on the SAME ~11.7h S46/S47 window (the alt book branches have not rolled
forward — collection cron is alive but mid-run; see `KICKOFF_2026-07-01_S48_UNBLOCK_CHECKLIST.md`). The 2nd-window
gate is still outstanding; this is an EXECUTION-mechanics change (measured as a structural improvement on one
window), NOT a signal/sizing edge, so it is safe under "never tune off one window."

## The problem (S47): the taker rate is the cost sink
The maker-at-the-turn executor crosses the spread + pays the taker fee whenever the cover quote does not fill
before the next turn (a "forced-taker flatten"). Per cell that was: sol 8%, eth 7%, btc 4%, xrp 12%, **doge 36%**.
DOGE was net-negative at mk0/tk5 (-510 bps) **on execution, not signal** — the S47 verdict was "signal real,
47% taker kills it." Job #2 = cut the taker rate.

## The fix: COVER-GRACE (the "smarter last-option"), `simulate_swing_maker(cover_grace=cells)`
When the cover quote would be forced to taker, DON'T cross immediately. Keep the maker cover resting up to
`cover_grace` cells past the turn and take the first opposing trade as a MAKER (earn the half-spread instead of
crossing it); cross as taker only if still unfilled at the grace cap. Cover-ONLY (no late new leg — S47: late
entries degrade), inventory capped to one swing, intervening flips skipped (no leg overlap, `hold_until` cursor).

Faithful to the existing fill model (same `_next_positive`, fixed limit at the post cell) → an apples-to-apples
execution improvement within the executor's own model, not new optimism. `cover_grace=0` is **bit-identical** to
the prior behavior (verified: reproduces the production seed sol +3053 / doge -510 / xrp +1208 / eth +654 /
btc +2434 exactly).

## Result (flat sizing, net-of-fee mk0/tk5, one window)
| cell | taker% 0→best | net/leg 0→best | TOTAL net 0→best | win% | grace |
|------|---------------|----------------|------------------|------|-------|
| sol  | 8 → 0  | +1.45 → +1.94 | +3053 → **+3795** (+24%) | 60→63 | 300 (30s) |
| **doge** | **36 → 2** | **-0.56 → +1.41** | **-510 → +1011** (LOSING→PROFITABLE) | 44→57 | 600 (60s) |
| xrp  | 12 → 0 | +0.60 → +1.32 | +1208 → **+2371** (+96%) | 57→62 | 300 |
| eth  | 7 → 0  | +0.32 → +0.69 | +654 → **+1324** (+102%) | 48→51 | 300 |
| btc  | 4 → 0  | +0.35 → +0.55 | +2434 → **+3689** (+52%) | 56→58 | 300 |

- **DOGE flips from losing to profitable on execution alone** — directly solves the kickoff's doge blocker.
- Taker rate → 0–2% everywhere. Win% up on all 5. Monotone in grace; saturates ~G=300 (30s) for sol/xrp/eth/btc;
  doge keeps improving to 600 (60s) — its falling-knife tail is longer (p90 grace ~50s).
- **Inventory stays contained**: mean hold barely moves (sol 21.7→22.1s, xrp 22.9→23.8s, eth 22.3→22.6s,
  btc 24.9→25.3s; doge 43→49s). p90 hold rises only modestly (doge 90.7→99.9s).

## What this is / isn't (honesty)
- The win is mostly STRUCTURAL: per converted leg you swing the half-spread from paid to earned plus save the
  taker fee (~2·hs + taker per converted leg) — a mechanical saving, more robust than a signal edge.
- The fill model (any opposing trade lifts the fixed limit via `_next_positive`) is OPTIMISTIC, but it is the
  SAME model the production executor already uses — so this is a fair within-model improvement. A price-level-
  aware venue queue would convert fewer covers; the true win sits between G=0 and these numbers.
- The downside (a failed-grace leg crosses LATER at a possibly worse price) is real and window-dependent; the
  monotone-positive, low-inventory result says the saved cost dominates ON THIS WINDOW. The **2nd window must
  confirm** the falling-knife cost doesn't dominate in a trendier regime (esp. doge at G=600).

## Wired
- `odcore/swing_maker.py`: `simulate_swing_maker(cover_grace=0)` — opt-in, default = prior behavior.
- `scripts/paper_trade.py`: per-cell `GRACE` map (sol/xrp/eth/btc 300, doge 600), `--grace` override; ledger
  rows now carry `grace`. Ledger RE-SEEDED under the grace executor (the old G=0 seed was the same one window,
  not forward data; backed up to scratchpad). The forward ledger now accrues the DEPLOYABLE executor.

## Still gated (unchanged from S47)
2nd window (THE gate before sizing for real); confirm maker fee ≤ 0 venue; then wire conviction→SIZE
(`assert_no_leakage` first) into `simulate_swing_maker` + the per-cell emit path. Cutting the taker rate does
NOT lift the one-window gate — it just makes the deployable executor cheaper so the forward test runs the real thing.
