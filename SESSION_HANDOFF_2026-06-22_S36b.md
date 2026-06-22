# SESSION HANDOFF — S36b (2026-06-22) — net-of-cost → SWING reframe → TIMING edge → harness → all 4 Architect edges

Branch `claude/divergence-exhaustion-backtest-wj65sm` (PUSHED). Continues S36. Read order: `CLAUDE.md`
(S36b delta top) → `S36_NETCOST_BACKTEST_FINDINGS.md` (the detailed findings) → `BUILD_PLAN.md` PART 4 →
this file. All S35/S36 memories apply. Crypto platform only; zero synthetic; per-cell deploy; git is truth.

## WHAT THIS SESSION DID (in order)
1. **Net-of-cost backtest of the divergence/exhaustion reversal gate, per cell** (KICKOFF #1).
   `_info_dipole_netcost_backtest.py`. 64% reversal does NOT clear 10 bps pooled (FLOW −5.97 bps/trade;
   breakeven ≈4 bps); flow gate adds +3 over blind follow; clears per-cell on **btc_bybit_sell** (+9.1 t=3.1)
   and **btc_bybit_buy** (fade gate +25.7 t=4.6), both walk-forward halves. eth clears are single-regime artifacts.
2. **Greg's SWING reframe** — markets oscillate: buy valleys / short peaks / flip at each turn, NO clock
   horizon; ride straight runs, don't fight. `_info_dipole_trailing_backtest.py` (horizon-free ride+flip),
   `_info_dipole_swing_backtest.py` (ORACLE + dipole detector; reads 1-min test_bars OR 1-sec realbins).
   ORACLE proves the opportunity: perfect swings net thousands of bps, beat the 10 bps fee 3–13×.
3. **TIMING is the edge** (`_info_dipole_timing_test.py`). Corrected an earlier artifact: order-flow imbalance
   is a MID-SWING trigger (~18 bps off at any resolution); PRICE reversing is what fires AT the turn and it
   sharpens with resolution. Same turns + same data, only the clock: **1-sec enters ~5.6–6.5 bps off vs
   ~9.2–11.0 at 1-min = +4.2 bps/entry (~8/round-trip swing), growing with volatility.** Per-second required.
4. **FEE-FLOOR logic** (`_info_dipole_fee_floor.py`). Never trade sub-fee. R (reversal confirm) = timing only.
   Per-leg asymmetric: maker-rest at the turn drops the floor 22(taker)→4 bps(maker/maker) = **1.6–3.5× the
   oracle opportunity** (fill-risk caveat).
5. **QUANTUM question resolved by the Architect — *for the dipole turn-detector*: precision NOT speed.** Merge-
   math says classical-∞-dim and quantum ML are the same operator on different substrates → forbids a quantum-
   execution edge (build classical, no quantum tick→order). SCOPED (Greg): conditional on the LOW-DIM detector;
   Greg's broader merge-math idea is something OTHER than the dipole and stays OPEN (he's digging with the Architect).
6. **Falsification harness** (`_info_dipole_harness.py`, Architect test D). OD dipole filter vs classical OFI
   champion, SAME timing trigger, frozen 1-sec, OOS. Dipole wins on FILTERING (precision 0.690 vs 0.649,
   timing 13.9 vs 17.5) — matches the Architect's prediction — but modest. Neither clears TAKER; **maker flips
   the champion to +334**. "Max net" is degenerate near breakeven (drives to no-trade).
7. **All 4 Architect actionable edges DONE:** (1) fee floor; (2) regime master-gate (`_info_dipole_regime_gate.py`,
   per-cell — rescues bleeders, leave winners un-gated); (3) **incremental operator** (`odcore/incremental.py`
   `RollingFlow` + `_canary_incremental.py`: O(1)/tick, bit-faithful, 1.70 µs/tick); (4) **leakage check**
   (`odcore/leakage.py` + `_canary_leakage.py`: clears the dipole, catches look-ahead 40/40 — the mandatory gate).
8. **AWS placement recorded** (BUILD_PLAN PART 4 "LIVE EXECUTION"): speed to the turn = REGION/PLACEMENT +
   network, not CPU count. Same region/AZ as each exchange (Coinbase=us-east-1; confirm Kraken/Bybit);
   higher-clock not more-cores; incremental update. More cores only help offline research. ACTION: confirm venues' regions.

## STATE / HONEST VERDICT
- The swing opportunity is REAL (oracle). OD's edge is on turn FILTERING (modest), not timing; fine-res PRICE
  pins timing near the fee floor. **MAKER execution is the decisive economic lever** — un-gated dipole at the
  maker floor is ~breakeven pooled and POSITIVE on 3/6 venues (btc_kraken +466, eth_bybit_perp +670, eth_coinbase +392).
- **The bottleneck is data:** can't tune/validate a near-breakeven swing strategy on ONE 1-sec window without
  overfitting ("trade less = lose less"). The local 1-sec MULTI-regime onset history is the gating resource.

## NEXT (priority)
1. **Get the local 1-sec MULTI-regime history** (E:\ / refrag-side, not in git) → re-run the harness + swing +
   regime gate per cell on it. Unblocks everything (#2 below is hostage to it).
2. **Build the gated swing strategy as the unified challenger** (dipole filter arms the 1-sec price-reversal
   trigger + per-leg maker floor + per-cell regime gate) and score it on the harness with `assert_no_leakage`.
3. **Confirm exchange hosting regions** (Coinbase/Kraken/Bybit) + maker-fill modeling for the live maker path.
4. **Greg's broader merge-math thread** (separate from the dipole) — his dig with the Architect.

## TOOLS (all bar-free off committed data; realbins = 1-sec, in git)
`_info_dipole_netcost_backtest.py`, `_info_dipole_trailing_backtest.py`, `_info_dipole_swing_backtest.py [realbins]`,
`_info_dipole_timing_test.py`, `_info_dipole_fee_floor.py`, `_info_dipole_harness.py`, `_info_dipole_regime_gate.py`,
`_canary_incremental.py`, `_canary_leakage.py`. Operators: `odcore/info_dipole.py`, `odcore/incremental.py`, `odcore/leakage.py`.
