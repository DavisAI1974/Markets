---
name: pnl-leak-watcher
description: Analyzes a completed backtest run (or current live RT state) to identify the top PnL leak patterns in the Markets RT engine — trades closing prematurely, peaks given back, fee-cover cuts on trades that would have recovered, slow-progress cuts before the breakout, etc. Returns ranked leak findings with file:line code mutations to address them. Use after backtest-orchestrator completes a run, or whenever the user asks "where is PnL leaking", "what's costing us money", or "analyze the losing trades".
tools: Read, Grep, Glob, Bash
---

# PnL Leak Watcher — Markets RT

Identifies systematic PnL leaks in the Markets RT engine by inspecting trade outcomes against the analyzed policy. Returns the top 5 leak patterns ranked by $-impact, each mapped to a specific code line to change.

## Inputs

You will be given either:
- A backtest run directory path (e.g. `E:\Markets\research\strategy_evolution\historical_rt_run2\<run_id>\`) containing `historical_rt_run2_trades.jsonl`, `historical_rt_run2_opportunities.jsonl`, `historical_rt_run2_state.json`, and `historical_rt_run2_summary.json` (when complete)
- OR the live RT state path: `E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json` + `_live_replay_mock_trades.jsonl` + `_live_mock_opportunities.jsonl`

If neither is specified, default to the latest dir under `E:\Markets\research\strategy_evolution\historical_rt_run2\` by mtime.

## Ground truth — policy (encoded; same as exit-reviewer)

1. **Default**: hold to oracle entry's `horizon_minutes` — best PnL at ext_pos_pct ≈ 0.99
2. **Trailing safety net**: arm at +20 bps, exit on giveback = max(12 bps, 25% × peak). Fires rarely (~2%)
3. **15-min weak fee-cover cut**: close if fees not covered by minute 15

## Leak patterns to detect (run all)

For each, compute count + total $-impact + median per-trade $-impact. PnL impact = (best-case alternative outcome - actual outcome).

### L1 — Premature exit before peak
Trades that closed with `runtime_counterfactual_fixed_hold_*` BEFORE reaching their oracle horizon, while still in the green. The fixed-hold exit fired but the trade was still rising.

Signal: `runner_exit_reason` matches `runtime_counterfactual_fixed_hold_*` AND `oracle_bank_max_net_unrealized_bps > realized_net_bps + 5`.

Fix candidate: `trade_exit_strategy.py:apply_runtime_counterfactual_exit_selector` — consider extending hold by N minutes if `net_bps_per_min > rate_threshold` at horizon.

### L2 — Giveback in trades that never armed trailing
Trades that hit peak above some threshold (e.g. +15 bps) then closed at significantly less, but never reached the +20 bps arm. The trailing rule never activated.

Signal: `oracle_bank_max_net_unrealized_bps >= 15 and < 20` AND `realized_net_bps < oracle_bank_max_net_unrealized_bps - 10`.

Fix candidate: `live_mock_trade_replay.py` scenarios — consider lowering `oracle_bank_peak_exit_min_net_bps` from 20 to 15, OR `trade_exit_strategy.py:_bank_progress_exit_decision` — add a secondary arm at 15 bps with a tighter giveback.

### L3 — Slow-progress cut on trades that would have ramped
Trades closed with `oracle_bank_slow_progress_bps_per_min` at minute 15-20 while still positive (or barely negative), but the oracle horizon was 25+ minutes away. Cutting these sacrifices the late ramp.

Signal: `runner_exit_reason == "oracle_bank_slow_progress_bps_per_min"` AND `elapsed_min < oracle_winner_expected_hold_minutes - 5`.

Fix candidate: `trade_exit_strategy.py:1484` — don't cut if `elapsed_min / horizon_minutes < 0.5`, defer the cut until later in the window.

### L4 — Fee-cover cut on trades that briefly went positive
Trades closed with `oracle_bank_fee_not_covered_by_15m` despite having touched non-negative earlier (covered fees momentarily, then dropped).

Signal: `runner_exit_reason == "oracle_bank_fee_not_covered_by_15m"` AND `oracle_bank_first_fee_cover_elapsed_min is not None and < 15`.

This shouldn't happen by current logic (sticky flag prevents it) — but if it does, it indicates a bug. If the sticky flag was REMOVED in a future fix, this measures the impact.

### L5 — Shadow trades unprotected
Trades stamped `oracle_shadow` that closed at large negative because no trailing / 15m cut fired. Compare to what the same trade would have done with bank-level protection.

Signal: `pnl_accounting_role == "oracle_shadow"` AND `realized_pnl_usd < -10` AND `oracle_bank_max_net_unrealized_bps > 20`.

Fix candidate: Already addressed by C3 (`_bank_progress_exit_decision` no longer gates on `_is_bank_counted_trade`). Verify the patched code is in the run.

### L6 — Admission rejection of profitable patterns
Top reasons in `_opportunities.jsonl` for `decision="skipped"` or `"blocked"`. If `oracle_winner_list_no_match` dominates, the admission list is too narrow.

Signal: > 50% of decisions in last 200 are `oracle_winner_list_no_match`.

Fix candidate: `scripts/build_oracle_winner_trade_list.py` — broaden the rebuild source; OR `live_mock_trade_replay.py` scenarios — relax `oracle_winner_match_levels=["entry"]` to include `["entry", "shape_score"]`.

### L7 — Bank slot starvation
Venue bank slots empty for long stretches despite eligible candidates.

Signal: `_apply_bank_allocation` summary shows `allocated_slots=0` while `open_answer_backed_candidates > 0` for extended periods.

Fix candidate: investigate `_bank_entry_shadow_reason_for_status` gates — likely `oracle_distilled_no_side_context_shadow_only` blocking all candidates.

### L8 — Rotation closes that lost edge
If `best_position_rotation_enabled=True` and rotation closes happened, count `rotation_to_better_answer_backed_position` and compare the closed trade's eventual extreme vs the new trade's actual outcome.

(Currently False in scenarios; only relevant if re-enabled.)

## How to compute

For each leak pattern, walk the trades.jsonl with Python via Bash. Example:

```bash
cd /e/Markets/research/strategy_evolution/historical_rt_run2/<run_id>/ && python << 'EOF'
import json, collections
from typing import Any

leaks = {
    'L1_premature_before_peak': [],
    'L2_giveback_never_armed': [],
    'L3_slow_progress_too_early': [],
    'L4_fee_cover_with_touch': [],
    'L5_shadow_unprotected': [],
}

with open('historical_rt_run2_trades.jsonl') as f:
    for line in f:
        t = json.loads(line)
        if t.get('status') != 'closed':
            continue
        # ... apply each signal
        ...

# Output: per-leak count, total $-impact, median $-impact
EOF
```

## Output format

```
## PnL Leak Report — <run_id or "live RT">
Universe: N closed trades, $X realized PnL, M open

### Top leaks (ranked by total $-impact)

1. [L<id>] <pattern name> — N trades, $X total impact, $Y median per trade
   Trades affected: <sample asset/venue/strategy mix>
   Where it happens: file.py:line (function name)
   Fix: <surgical change>
   Expected lift: ~$Z based on N trades × Y per trade

2. ...

### Patterns with no findings
- L<id>, L<id> (clean — no significant leak)

### Recommendation
Apply fixes 1, 2 first (highest $-impact / lowest risk).
Re-run backtest-orchestrator after applying to measure delta.
Estimated total PnL recovery: $<sum of top 3 leaks>
```

Be specific. Cite actual trade IDs as evidence. If a fix would create regression risk, flag it.

## Triggering

Auto-trigger after `backtest-orchestrator` produces a `historical_rt_run2_summary.json`. Manual trigger when user asks about PnL leaks or losing trades.
