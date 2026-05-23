# Session Handoff — 2026-05-23: PnL Plugin + Exit Logic Fixes

## What landed (committable code changes)

### Exit logic — `trade_exit_strategy.py`
- **C3**: `_bank_progress_exit_decision` (~line 1427) — dropped `_is_bank_counted_trade` gate. Trailing safety net + 15m fee-cover cut + slow-progress cut now apply to **shadow** oracle trades too, not just bank-allocated. Was the biggest leak: 100% of production trades are shadow (12/0 split at time of fix), all previously unprotected.
- **C1**: Peak default in same function (~line 1430) changed from `net_bps` → `float("-inf")` as cleaner sentinel.

### Quality gates — `live_mock_trade_replay.py`
- **H1**: `bank_quality_eligible` default `True` → `False` when quality dict missing (line 1173).
- **H2**: `_oracle_winner_quality_from_match` (line 94) — quality now requires `net_bps ≥ 15` AND `horizon ≥ 5m` (new constants `ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS=15.0`, `ORACLE_WINNER_MIN_BANK_ENTRY_HORIZON_MINUTES=5.0`). Closes the small-horizon trap (2m × 30 bps = 15 bps/min passed the 0.30 floor with no absolute floor). Both new floors configurable via scenario flags `oracle_winner_min_bank_entry_net_bps` and `oracle_winner_min_bank_entry_horizon_minutes`.
- **H3**: `_apply_bank_allocation` (line ~1015) — added demotion path. Every rebalance re-checks `bank_quality_eligible` + `bank_entry_shadow_reason`. Stuck-bank trades now flip back to shadow when quality drops.

### Preflight — `scripts/verify_final_live_mock_preflight.py`
- **H5**: Hard require: `oracle_bank_peak_exit_min_net_bps==20.0`, `oracle_bank_peak_exit_giveback_bps==12.0`, `oracle_bank_peak_exit_giveback_fraction==0.25`, `oracle_bank_fee_cover_cut_minutes==15.0`. Catches policy drift.
- Hard require: `oracle_bank_require_20bps_by_30m` must be off (dead-code arm should stay off).
- **H4**: Hard error if any open trade has `runtime_counterfactual_exit_selection_status == "oracle_winner_match_without_runtime_exit"` (silent fallback to historic parity — no horizon protection).

### Oracle admission key — `oracle_winner_trade_memory.py`
- `_news_state(row)` now hardcoded to return `"none"`. Was reading runtime `daily_news_status.stale` flag (loaded from a May-16 stale daily_news_context.json), contaminating 100% of historical replay keys with `|stale_news` while oracle list keys all had `|none`. Per user directive ("strip timestamps from the decision tree"). After fix: all 189 historical keys end correctly in `|none`. Compile-verified.

### Historical RT runner — `run_historical_rt_run2.py`
- Already overwritten earlier to be a clean script that uses the same engine (`live_mock_trade_replay._prepare_settings`, `_maybe_log_and_open`, etc.) and same oracle list. No scenario overrides. Only the data feed differs (May 4-14 bins vs live tape).

## Plugin built — `markets-pnl` at `E:\Markets\.claude\`

Will auto-load on next session start (project-level agents don't hot-load mid-session).

5 specialist agents:
- `pnl-architect` — end-to-end audit, severity-ranked findings, file:line edits
- `admission-reviewer` — entry gates + bank/shadow stamping diagnostics
- `exit-reviewer` — exit logic vs the three on-disk analyses (10-item mandatory checklist)
- `backtest-orchestrator` — launches `run_historical_rt_run2.py`, monitors, reports PnL deltas
- `pnl-leak-watcher` — analyzes completed backtest for top PnL leak patterns (L1-L8), maps each to file:line code mutation

1 skill: `pnl-review` — auto-triggers on PnL/exit/admission discussions. Encodes the three on-disk analyses as policy ground truth + constants (arm 20, giveback max(12, 25%), 15m cut, 0.30 bps/min, etc.)

Standard workflow encoded in skill:
1. Make code change
2. `backtest-orchestrator` runs historical RT
3. `pnl-leak-watcher` analyzes, ranks leaks by $-impact
4. Apply fixes
5. Loop until plateau

## Other actions

- **Pruned 1 contaminated queue entry** from `research/strategy_evolution/_queue.json` (`source_variant_id: historical_run2_live_oracle_json_pretend_mapped`). Atomic write; remaining 10 items are legitimate hindsight-derived.
- **Killed all bad historical runs** (PIDs 75728, 80032, 80972, 50284, 83744, 77812, 82492). Empty/poisoned output dirs cleaned.
- **Cron loops cancelled** (bf1dd606, 651cbddb, 7d8751be). Session-only, gone now.

## Open decision — historical RT zero-trades result

After all fixes, historical RT run 2 produces **0 trades** because:
- Current `oracle_winner_trade_list.json` has 268 unique structural patterns built from a 1-hour audit window today
- May 4-14 historical replay produces 189 unique structural patterns over 230 hours
- **Zero overlap between the two pattern sets** — different market conditions = different specific 14-field patterns

This is NOT a code bug (verified — matching is purely structural after news fix). It's a data property.

User said historical RT should "generate fresh trades on raw data using current rules" but also "same rules as live RT" (which means exact 14-field match). These conflict because exact-match doesn't span time periods.

Three options proposed to user, **no decision yet**:

| | What it does | Rules change? |
|---|---|---|
| **A. Strict (current)** | Exact 14-field match required. 0 trades on historical. | Same as live ✓ |
| **B. Loose levels for historical** | Try `entry` → `shape` (11 fields) → `route` (4 fields) cascade. Trades fire on broader pattern recognition. | Historical scenarios differ from live |
| **C. Both broadened** | Apply B to live RT too. Identical between live and historical. | Both change identically |

User's last message indicated they need to start a new chat soon. Decision pending for next session.

## Process state

- **Live RT**: PID **49916** still running with OLD in-memory code (started before today's fixes). 30 oracle_shadow open trades, 0 bank. Restart needed to pick up the new exit logic (C3 most impactful — currently the shadows have no trailing/15m protection in the running code).
- **Live collectors**: PID 73408 (or similar) running, healthy.
- **Live hindsight evolve worker**: PID 76100 running, every 300s audit.
- **Historical RT**: NOT running (killed). Zero historical artifacts in `historical_rt_run2/` worth keeping from today's runs (all were 0-trade or contaminated).
- **Backend uvicorns**: 35228 (port 8000), 49700 (8001), 49060 (8002) — untouched.

## Files NOT yet committed

```
modified:
  trade_exit_strategy.py
  live_mock_trade_replay.py
  scripts/verify_final_live_mock_preflight.py
  oracle_winner_trade_memory.py
  run_historical_rt_run2.py (this was already in working tree, just updated)

new:
  .claude/agents/pnl-architect.md
  .claude/agents/admission-reviewer.md
  .claude/agents/exit-reviewer.md
  .claude/agents/backtest-orchestrator.md
  .claude/agents/pnl-leak-watcher.md
  .claude/skills/pnl-review/SKILL.md
  HANDOFF_SESSION_20260523_PNL_PLUGIN_AND_FIXES.md (this file)
```

User has not been asked about committing. Recommend committing the exit-logic fixes (5 files) separately from the plugin (6 files) for clean history.

## Next session — start here

1. Read this handoff.
2. Decide A/B/C on historical RT matching.
3. Decide whether to restart live RT to pick up new exit logic.
4. Use `markets-pnl` plugin agents (now auto-loaded) for future PnL reviews.
5. Suggested first agent invocation: `pnl-architect` for an end-to-end audit of the post-fix code state.
