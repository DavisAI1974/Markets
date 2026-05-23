---
name: pnl-review
description: Use this skill when the user discusses PnL optimization, exit rules, admission rules, bank vs shadow trade gating, oracle winner admission, or proposes changes to the Markets RT mock trading engine at E:\Markets. Also use when reviewing trade_exit_strategy.py, live_mock_trade_replay.py, mock_trade_replay.py, oracle_winner_trade_memory.py, strategy_switcher.py, or scenario flags like oracle_bank_*, counterfactual_exit_selector_*, oracle_winner_*. Loads policy ground truth from the three on-disk analyses so reviews and proposals match the validated policy.
---

# PnL Review Skill — Markets RT Trading

## When to apply

The user mentions: PnL, "leaking PnL", exit rule, admission rule, oracle winner, bank vs shadow, trailing rule, fee-cover cut, hold-to-horizon, RT engine, live_mock_trade_replay, oracle_winner_trade_list.json, oracle_bank_*, counterfactual_exit_selector_*. Or asks to: "review for PnL", "optimize PnL", "check PnL impact", "audit live RT", "audit historic run", "verify exit logic".

## Policy ground truth (load this every time the skill triggers)

Three on-disk analyses at `E:\Markets\_analysis_*_20260523\`, all convergent:

1. **`_analysis_winner_extrema_20260523\WINNER_EXTREMA_SIGNALS.md`** — Across 5,886 oracle-after-fee winners on BTC/ETH, the extreme bar lands at `ext_pos_pct ≈ 0.94 – 1.00` (the oracle's exit timestamp essentially IS the natural extreme of the visible-tape window). Missed-bps vs oracle is a *price-reference gap*, not a *timing gap*.

2. **`_analysis_historical_rt_trade_shapes_20260523\HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md`** — Across 67,728 simulated trades (5,616 winners, 8.29% base rate), path signals dominate. `reached_20bps_within_30m` = 68% precision / 8.2× lift. `hold_min ≥ 60` = 86% precision / 10× lift. Entry-time signals are all 1.0–1.3× lift (no entry observable separates winners). `cover_by_15m` is a hard negative gate (98% recall — anything that hasn't covered fees by 15m is the 2% loser tail).

3. **`_analysis_exit_rule_validation_20260523\summary.json`** — Simulated 1,311 oracle winners through the 3-part rule (`arm=20bps, giveback=max(12, 25%) of peak, weak-cuts at 15m`). Median time-to-best-PnL = 217 min, `ext_pos_pct = 99%`. Trailing fired on 29/1311 (~2%). If holding to oracle horizon, median give-back = 2.9 bps.

## Policy (treat as authoritative)

1. **Default**: hold each open trade to its oracle entry's `horizon_minutes`
2. **Trailing safety net**: once net P&L ≥ +20 bps, exit on giveback = max(12 bps, 25% × peak)
3. **15-min weak fee-cover cut**: close trades that haven't covered fees by minute 15

## Constants

- Trailing arm: **20 bps** net
- Giveback floor: **12 bps**
- Giveback fraction: **25%** of peak
- Fee-cover cut: **15 min**
- Bank quality min bps/min: **0.30**
- Per-venue bank slots: **1**
- Allowed counterfactual horizons (non-oracle-source): **[10, 30, 60, 120, 240, 360]** min
- Oracle entries' `horizon_minutes` (current 52-entry JSON): **1–40 min, median ~17–22m**

## Available specialist agents

Project-scoped at `E:\Markets\.claude\agents\`:

- **`pnl-architect`** — end-to-end audit. Severity-ranked findings list with file:line edits. Use for broad reviews or before/after a change.
- **`admission-reviewer`** — entry gate + bank-vs-shadow stamping. Use when adjusting admission flags or diagnosing 0-bank states.
- **`exit-reviewer`** — exit logic vs the three on-disk analyses. Use when changing exit rules or scenario flags.
- **`backtest-orchestrator`** — launches `run_historical_rt_run2.py`, monitors, reports final PnL + bank/shadow split + top exits. Compares to prior runs.
- **`pnl-leak-watcher`** — analyzes a completed backtest (or live RT) to identify top PnL leak patterns ranked by $-impact, mapped to file:line code mutations. Auto-trigger after `backtest-orchestrator` completes.

## How to use

- **Broad audit**: dispatch `pnl-architect`
- **Admission-only**: dispatch `admission-reviewer`
- **Exit-only**: dispatch `exit-reviewer`
- **Measure a change**: apply the change, then dispatch `backtest-orchestrator`
- **Validate after fixes**: re-run `backtest-orchestrator` and compare to baseline
- **Find what's leaking PnL after a backtest**: dispatch `pnl-leak-watcher` (auto-triggered post-backtest)

## Standard workflow

1. Make code change
2. `backtest-orchestrator` runs historical RT run 2 against the fixed code
3. `pnl-leak-watcher` analyzes the completed run, returns top leaks ranked by $-impact
4. Apply the recommended fixes from the leak watcher
5. Loop back to step 2 until leaks plateau

## Anti-patterns to catch (every review)

- **Sticky flags that lock out reversals** — e.g. `oracle_bank_first_fee_cover_elapsed_min` set once on a 0.0001 bps positive blip, locks out the 15m cut forever even if trade goes to -50 bps
- **Default-True quality gates with missing data fallthrough** — empty quality dict + `.get("bank_quality_eligible", True)` opens bank trades that should be ineligible
- **Early-returns gating policy rules to bank-only or oracle-source-only** when shadow trades need the same protection (current `_bank_progress_exit_decision` has this — shadow trades skip trailing + 15m cut entirely)
- **Dead-code arms silently activatable via scenario tweaks** — `oracle_bank_require_20bps_by_30m` is dormant but live
- **Stale `runtime_counterfactual_exit_selection`** across epoch changes or policy CSV updates
- **Cross-account venue slot races** in `_apply_bank_allocation` — slots are per-account, not global
- **No demotion path from bank back to shadow** after quality changes
- **Peak persistence bugs** — `oracle_bank_max_net_unrealized_bps` defaulting to current `net_bps` on state rehydration silently resets the trailing peak
- **Small-horizon trap** — 2m × 30 bps = 15 bps/min passes the 0.30 floor; trade opens with 2m hold, fees won't cover before close
- **Preflight false negatives** — flag-only checks miss numeric threshold drift (20 → 18, 12 → 10, etc.)

## Output guidance

When reviewing proposed changes:
1. State explicitly whether the change advances, neutralizes, or regresses the policy
2. Cite the policy constants and the analysis where relevant
3. Suggest the `backtest-orchestrator` as the validation step
4. Flag the failure mode in plain language if regression
5. Recommend the surgical edit (file:line, what to change)

When auditing existing code:
1. Run the anti-pattern checklist above
2. Severity-rank findings (Critical / High / Medium / Low / Nit)
3. Estimate PnL impact where possible
4. Order recommendations by PnL impact × ease of fix
