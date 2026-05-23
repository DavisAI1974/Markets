# Clean Slate Handoff: Strategy Evolution Experiment

Date: 2026-05-16
Workspace: `E:\Markets`

## User Goal

Start a clean strategy-evolution experiment focused on profit and learning, not trade volume.

Hard rule: `PRESSURE_CONTINUATION` is removed from the active strategy universe. Do not run it, report it as a candidate, evolve it, or mention “0 trades” as a success metric. It may remain only as an internal kill-switch constant if needed to reject old historical records.

## Current Experiment Direction

The system should self-evolve strategy families through a relay loop:

1. A family touches a BTC/ETH signal.
2. If it is a poor fit, it writes a structured handoff: what it saw, why it failed, what features helped, what was missing/misleading, and what the next family should try.
3. The next family uses that handoff to evolve closer to the right shape.
4. Practice/autoresearch records outcomes.
5. Daily health decides promotion/demotion/kill.
6. Product exposure remains gated by daily health only.

Refrag’s role: strategy memory and invention layer. It may propose experiments, variants, feature combinations, and bucket splits. It must not directly create product trades.

## Active Practice Families

Current active families for the clean experiment:

- `MEAN_REVERSION_CHOP`
- `NEWS_BREAKOUT`
- `LIQUIDITY_SQUEEZE`

Likely next candidates from relay memory:

- `BASIS_DISLOCATION`
- `VOL_BREAKOUT`
- `RELATIVE_STRENGTH`

## Important Files Added/Modified

### Strategy family practice wiring

- `E:\Markets\strategy_library.py`
  - Registers practice strategies.
  - Emits practice signals for:
    - `MEAN_REVERSION_CHOP`
    - `NEWS_BREAKOUT`
    - `LIQUIDITY_SQUEEZE`
  - Tracks debug skip counters.

- `E:\Markets\strategy_switcher.py`
  - Practice mode can call `strategy_library.suggest_practice_strategy(...)`.
  - Added explicit `NEWS_BREAKOUT` and `LIQUIDITY_SQUEEZE` specs.
  - `PRESSURE_CONTINUATION` removed from labels/specs/docs/configs, except internal disabled constant.

- `E:\Markets\mock_trade_replay.py`
  - In learning mode (`--no-enforce-bucket-health --no-enforce-daily-limits`), scenarios are opened enough for practice signals to become trades.
  - Writes strategy debug, open debug, Refrag relay, and evolved-family JSON metadata.

### Refrag relay and self-training memory

- `E:\Markets\strategy_refrag_relay.py`
  - Builds `refrag_strategy_relay_v1`.
  - Produces:
    - family reports
    - poor-fit reasons
    - useful features to preserve
    - missing/misleading features to fix
    - next-family candidates
    - handoff messages

- `E:\Markets\strategy_family_evolution.py`
  - Writes per-family memory cards for self-training.
  - Run-local copies: `<run_dir>\evolved_families\*.json`
  - Shared memory library: `E:\Markets\research\strategy_evolution\*.json`

### Docs updated

- `E:\Markets\TRADE_LOGIC.md`
  - Strategy switcher section updated.
  - Refrag Strategy Memory section added.
  - Implementation hook documents relay + evolved-family JSONs.

- `E:\Markets\HANDOFF_DAILY_HEALTH_FAMILY_DIPOLE_ONCHAIN.md`
  - Refrag relay direction and implementation hook added.

### Config cleanup

Removed active `pressure_continuation` config from:

- `E:\Markets\daily_limits.json`
- `E:\Markets\bucket_thresholds.json`
- `E:\Markets\venue_prefs.json`
- `E:\Markets\dipole_coupling.py` family weights
- `E:\Markets\market_strategy_autoresearch.py` default strategy filter
- visible docs and relay maps

## Clean 6-Hour Test Already Run

Output folder:

`E:\Markets\mock_replay_evolved_family_first6_clean_out`

Command shape:

```powershell
python mock_trade_replay.py --data-dir . --output-dir mock_replay_evolved_family_first6_clean_out --start-hour 0 --hours 6 --stride-minutes 30 --checkpoint-hours 0 --disable-news-context --no-enforce-bucket-health --no-enforce-daily-limits --allowed-strategies MEAN_REVERSION_CHOP,NEWS_BREAKOUT,LIQUIDITY_SQUEEZE

python market_strategy_autoresearch.py --replay-results mock_replay_evolved_family_first6_clean_out\mock_replay_results.json --output-path mock_replay_evolved_family_first6_clean_out\market_strategy_autoresearch_all_results.json --strategies ALL
```

Results:

- 24 statuses evaluated.
- 30 closed practice trades.
- Trades came from `MEAN_REVERSION_CHOP` only.
- `MEAN_REVERSION_CHOP` performed badly in this slice: 0% win rate, about `-104.61R` in the replay strategy summary.
- `NEWS_BREAKOUT` opened no trades because replay used `--disable-news-context`; debug reason: `no_news_bias`.
- `LIQUIDITY_SQUEEZE` opened no trades; skip reasons included:
  - `wrong_regime_or_no_thinness_proxy`
  - `move_still_extending`
  - `move_not_extreme`
- Refrag relay generated handoffs from each family.
- Evolved family JSONs were written.
- No visible `PRESSURE_CONTINUATION` appears in the clean output or evolved family memory.

Key files from clean run:

- `E:\Markets\mock_replay_evolved_family_first6_clean_out\mock_replay_results.json`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\mock_replay_report.md`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\market_strategy_autoresearch_all_results.json`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\evolved_families\_manifest.json`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\evolved_families\mean_reversion_chop.json`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\evolved_families\liquidity_squeeze.json`
- `E:\Markets\mock_replay_evolved_family_first6_clean_out\evolved_families\news_breakout.json`

Shared memory files:

- `E:\Markets\research\strategy_evolution\mean_reversion_chop.json`
- `E:\Markets\research\strategy_evolution\liquidity_squeeze.json`
- `E:\Markets\research\strategy_evolution\news_breakout.json`

## Suggested Next Steps In New Chat

1. Do not restart the week runner yet. Stay with clean 6-hour or targeted slices first.
2. Inspect `research\strategy_evolution\mean_reversion_chop.json` and use its `latest_training_targets` to create the next variant.
3. Consider adding a new family/variant that consumes the bad mean-reversion handoff:
   - fade only when volume/thinness confirms,
   - require on-chain context when available,
   - avoid ETH Coinbase/Kraken first6h buckets until evidence improves,
   - or create a `BASIS_DISLOCATION`/`VOL_BREAKOUT` practice family.
4. Re-run only first 6h after each variant change.
5. Keep product exposure strict: no product trades unless daily health marks family and bucket `ok`.

## Validation Commands

Compile check:

```powershell
python -m py_compile strategy_family_evolution.py strategy_refrag_relay.py strategy_library.py strategy_switcher.py mock_trade_replay.py market_strategy_autoresearch.py build_daily_health_report.py dipole_coupling.py backend\api_server.py
```

Check removed family does not appear in clean outputs/memory:

```powershell
rg -n "PRESSURE_CONTINUATION|pressure_continuation|Pressure continuation" mock_replay_evolved_family_first6_clean_out research\strategy_evolution -g "*.json" -g "*.md"
```

Expected: no matches.

## Notes

- There are many dirty/untracked files in this repo. Do not revert unrelated changes.
- Use `apply_patch` for manual edits.
- The user wants profit and learning, not volume. Fewer trades is fine.
- The old continuation family should not be resurrected.
