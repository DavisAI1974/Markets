# Session Handoff — 2026-05-23 (Protective Evidence Gate v1)

## TL;DR for the next chat

Built and replay-validated a K-NN-augmented admission gate ("protective" mode) over the existing per-key Wilson gate. On the 67,728-trade 7-day historic tape at $10k notional:

| Strategy | PnL | Trades placed | Saved vs ungated |
|---|---|---|---|
| Ungated | **-$743,679** | 67,728 | — |
| Wilson (v1, default) | **-$198,249** | 17,276 | +$545,430 |
| **Protective (new)** | **-$3,216** | 264 | **+$740,463** |

Protective is strictly dominant across every bucket: 7 days, 2 assets (BTC/ETH), 3 venues (Bybit/Coinbase/Kraken), 2 sides, 6 strategies. By hour 48 of tape it plateaus at -$3,216 and stays flat for the next 5 days — phase transition once K-NN neighbor coverage densifies.

**Greg's redirect (read first)**: defense isn't enough. Next target is *best outcome*, not break-even. Improvements queued at bottom of this doc.

## What's running

- **PID 89876** (`_historical_rt_run2_stdout.log`): in-flight wilson backtest, writing to default ledger. Was at step 2,330/13,166 (17.7%) at handoff time.
- **PID 96124** (`_historical_rt_run2_protective_stdout.log`): parallel protective backtest, writing to `oracle_winner_evidence_ledger_protective.jsonl`. Was at step 104/13,166 (0.8%) at handoff time.
- Both will run for hours. Compare final PnL when both complete.
- **Live RT (PID 49916)** still untouched — do not restart until protective is validated against live data.

Both ledgers diverge cleanly — the per-run ledger path override (added this session) prevents cross-contamination.

## Files created or modified this session

| file | what |
|---|---|
| [markets_evidence_knn.py](markets_evidence_knn.py) | new — sparse-cosine K-NN over canonical-key components, identity-gated by (strategy, asset, side). Exposes `decide_admission_protective` and `decide_admission_knn` |
| [oracle_winner_evidence.py:31-46](oracle_winner_evidence.py:31) | added `set_active_ledger_path()` process-level override + `mode` param to `decide_admission` |
| [oracle_winner_trade_memory.py:269](oracle_winner_trade_memory.py:269) | `_apply_evidence_gate` reads `oracle_winner_evidence_mode` scenario flag |
| [run_historical_rt_run2.py:140-160](run_historical_rt_run2.py:140) | `--evidence-mode {wilson,protective}` and `--evidence-ledger-path` CLI flags |
| [replay_evidence_comparison.py](replay_evidence_comparison.py) | seed-data replay (1,353 trades, validates structural design) |
| [replay_spotcheck_full_historic.py](replay_spotcheck_full_historic.py) | full-tape replay (67,728 trades) with incremental O(N) index. Validates generality across all dimensions |
| [_pnl_totals.py](_pnl_totals.py) | running-PnL track (6h cumulative buckets, ungated vs wilson vs protective) |

Nothing committed to git per Greg's session rule.

## Protective design (the principles, not the implementation)

Two structural constraints, no tuned parameters:

1. **Identity gate**: K-NN neighbors must match on (strategy, asset, side) — positions 0,1,2 of `canonical_trade_key`. Without this, a winning chop key matches losing continuation keys via tail-position overlap (caught in cross-strategy spot check: MEAN_REVERSION_CHOP regressed -91 bps before the identity gate, was fixed structurally not by tuning).

2. **Asymmetric use** (this is the one Greg wants revisited): K-NN is a *reject enhancer*, not a bank promoter. Wilson keeps authority over bank. K-NN escalates marginal Wilson admissions to reject when same-identity neighbors are clearly losing.

Constants are statistical, not tuned:
- K = round(sqrt(unique_keys))
- min_similarity = 0.5
- n_min_for_bank = 10 (same as v1)
- Wilson z = 1.6449 (90%)
- effective N = (sum w_i)² / sum(w_i²) — kernel effective sample size

## Spot-check generality (the proof that constants aren't tuned)

Re-bucketed the 67k-trade replay six different ways. Protective dominates Wilson on every bucket independently:

| Slice | n buckets | smallest lift | largest lift |
|---|---|---|---|
| Day-of-tape | 7 | +$17,130 | +$49,575 |
| Asset | 2 | +$87,968 | +$107,065 |
| Venue | 3 | +$39,844 | +$78,926 |
| Side | 2 | +$94,312 | +$100,721 |
| Strategy | 6 | +$27,715 | +$37,216 |

Running cumulative track shows protective plateaus at -$3,216 at hour 48; Wilson bleeds from -$56k to -$198k over the next 5 days.

## Greg's redirect: target best outcome, not break-even

The current protective gate is **defensive**. It rejects everything that doesn't clear EV ≥ 0 at confidence. On the 67k tape this saved $740k but generated zero gain — bank trades = 0 for both wilson and protective.

To make money, the system has to identify winners and admit them aggressively. Greg's instruction was clear: "we might as well not bother with this if we gain absolutely nothing."

### Three queued improvements (in priority order)

#### 1. Symmetric identity-gated K-NN (HIGHEST PRIORITY)

The earlier rationale for K-NN-as-reject-only was that structural correlation in canonical keys overstated evidence on the positive side. BUT the identity gate (strategy+asset+side must match) controls for that — same-identity neighbors *are* structurally independent.

Re-test: with identity gating, can K-NN be trusted for *admission* too? If yes, a cold-start key with strong same-identity-neighbor wins gets `admit_bank` immediately — no waiting for self-evidence.

Implementation: extend `decide_admission_protective` to also escalate `admit_shadow` to `admit_bank` when identity-gated K-NN LB ≥ break_even AND effective_N ≥ n_min.

Spot-check criterion: re-run replay against 67k. Protective_v2 should preserve all of Wilson's bank trades AND add new bank trades from same-identity K-NN evidence, without introducing the MEAN_REVERSION_CHOP regression that pre-identity-gate K-NN had.

#### 2. EV-based ranking, not WR-based gating

Stop comparing `p_win_lb_90 ≥ break_even_winrate`. Start comparing `expected_net_bps_lb ≥ meaningful_floor`. The "meaningful floor" should be derived from cost structure (e.g., 2× round-trip fees) — economically motivated, not tape-fit.

This lets the system prefer high-EV trades over low-EV ones even when both clear break-even. Bank slots are limited (1 per venue); we want them held by the best keys, not just the first-admissible ones.

Implementation: compute `expected_net_bps = p_win × avg_win - (1-p_win) × avg_loss` for both Wilson self-posterior and K-NN posterior. Rank candidates. Promote to bank only above the meaningful floor.

#### 3. Per-identity break-even AND per-identity payoff stats

Different strategies have wildly different (avg_win, avg_loss) geometry:
- MEAN_REVERSION_CHOP: high win-rate, small avg-win, small avg-loss → low break-even, low expected EV
- BUY_UP_CONTINUATION: low win-rate, large avg-win, large avg-loss → high break-even, high expected EV per trade

Pooling them into a global break-even mis-prices both. A chop key with WR 0.40 might be admit-worthy under per-identity break-even (0.33) but rejected under global (0.43).

Implementation: replace `global_rolling_payoff(path)` calls with `identity_rolling_payoff(canonical_key, path)` — filters the rolling window to same-identity trades only. Falls back to global if identity has < 30 trades.

This affects BOTH Wilson and Protective because both compute break-even.

### Order to ship them

1. Symmetric K-NN (rerun spot check, verify no regression)
2. Per-identity break-even (rerun spot check, measure offensive gain)
3. EV-based ranking (rerun spot check, measure bank-trade quality)

Each should be a separate replay run. If any regresses on any bucket, revert that one.

## Anti-drift checklist for next chat

- [ ] Read this handoff fully before making decisions
- [ ] Read [markets_evidence_knn.py](markets_evidence_knn.py) docstring + identity-gate logic before modifying
- [ ] Both backtests (PIDs 89876, 96124) are running independently — let them finish or check at meaningful milestones
- [ ] Live RT (PID 49916) still on pre-evidence code — do not restart until protective is validated
- [ ] Don't fit any constants to the 67k replay or in-flight backtest data — verify on multiple slices before keeping
- [ ] Don't push to git this session
- [ ] If improvement #1 (symmetric K-NN) introduces ANY per-bucket regression on the 67k spot check, revert
- [ ] The "best outcome not break-even" principle is now the design target — defensive-only is rejected
- [ ] Use the running-PnL track ([_pnl_totals.py](_pnl_totals.py)) to compare any improvement against current protective baseline of -$3,216

## Backtest comparison plan (when both finish)

Compare final PnL and decision distributions:
- Wilson backtest output: `research/strategy_evolution/historical_rt_run2/historical_rt_run2_20260523_221206_utc/`
- Protective backtest output: `research/strategy_evolution/historical_rt_run2/historical_rt_run2_20260523_232945_utc/` (or similar — check timestamp)

Key questions:
1. Did protective place fewer trades than Wilson? (Expected: yes, by ~3×)
2. Did protective have better bank PnL than Wilson? (Expected: same or better)
3. Did protective have better all-trades PnL than Wilson? (Expected: yes, by reducing shadow bleed)
4. Where are the remaining losses concentrated? (Inform the offensive improvements)

## File paths reference

- Evidence module: [E:\Markets\oracle_winner_evidence.py](oracle_winner_evidence.py)
- K-NN module: [E:\Markets\markets_evidence_knn.py](markets_evidence_knn.py)
- Wilson ledger: `E:\Markets\research\strategy_evolution\oracle_winner_evidence_ledger.jsonl` (1,530 entries at handoff)
- Protective ledger: `E:\Markets\research\strategy_evolution\oracle_winner_evidence_ledger_protective.jsonl` (1,518 entries at handoff — snapshotted)
- Historic CSV: `E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv` (67,728 trades)
- Backtest CLI: `python run_historical_rt_run2.py --evidence-mode protective --evidence-ledger-path <path>`
- Backtest logs: `_historical_rt_run2_stdout.log` (wilson), `_historical_rt_run2_protective_stdout.log` (protective)

## Suggested opener for next chat (from E:\Markets)

*"Read HANDOFF_SESSION_20260523_PROTECTIVE_EVIDENCE_GATE.md. Check both backtests' progress (PIDs 89876, 96124). Then start improvement #1: symmetric identity-gated K-NN. Read markets_evidence_knn.py:decide_admission_protective before modifying. Run the full spot check on per_trade.csv before and after the change."*
