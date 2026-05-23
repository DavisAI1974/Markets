---
name: backtest-orchestrator
description: Launches the historical RT run 2 backtest harness (E:\Markets\run_historical_rt_run2.py) against the May 4-14 historical bins, monitors progress, and reports final PnL totals + bank/shadow split + exit reasons. Use after any change to live RT exit/admission logic to measure the PnL delta. Compares to prior runs if any.
tools: Read, Grep, Glob, Bash
---

# Backtest Orchestrator — Markets RT

Runs and reports on historical RT run 2 backtests for the E:\Markets engine.

## Harness

- Script: `E:\Markets\run_historical_rt_run2.py` — replays May 4-14 historical bins through current live RT engine, exact rules unchanged, chronological clock, no lookahead. Treats current `oracle_winner_trade_list.json` as the admission list ("pretend already mapped"). Outputs at `E:\Markets\research\strategy_evolution\historical_rt_run2\historical_rt_run2_<timestamp>_utc\`.
- Output files per run:
  - `historical_rt_run2_state.json` — running state
  - `historical_rt_run2_trades.jsonl` — every trade
  - `historical_rt_run2_opportunities.jsonl` — every decision
  - `historical_rt_run2_summary.json` — final summary (only on completion)
- Process logs: `E:\Markets\_historical_rt_run2_stdout.log`, `_historical_rt_run2_stderr.log`
- Tape size: ~13,166 unique chunks. Expected runtime: 30+ minutes depending on host.

## Launch (Git Bash on Windows)

```bash
cd /e/Markets && nohup python run_historical_rt_run2.py > _historical_rt_run2_stdout.log 2> _historical_rt_run2_stderr.log &
echo "PID=$!"
sleep 4 && tail -5 _historical_rt_run2_stdout.log
```

The actual python.exe PID is NOT `$!` (that's the wrapper). Find the real PID with:
```bash
powershell -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -eq 'python.exe' -and \$_.CommandLine -like '*run_historical_rt_run2*' } | Select-Object ProcessId,CommandLine | Format-List"
```

Confirm the main loop entered by seeing `[historical-rt-run2] step=N/13166 (M.MM%)` in stdout.

## Monitor

```bash
tail -5 /e/Markets/_historical_rt_run2_stdout.log
```

## Kill safely

Find the real PID first (see above). Then:
```bash
powershell -Command "Stop-Process -Id <PID> -Force"
```

**Never** kill processes containing `live_mock_trade_replay.py`, `live_collectors.py`, or `live_hindsight_evolve_worker.py` without explicit user instruction.

## Summarize

After completion (summary.json exists), or on demand from state.json, compute per scenario (`historic_parity_live`, `evolve_live`):
- Total trades, open, closed
- **Realized PnL ($)** — headline number
- Bank vs shadow split — count + PnL each
- Top 5 exit reasons by count
- Top 5 strategies by count
- Side distribution
- Top 5 skipped/blocked reasons from opportunities.jsonl

Use Python via Bash for stats. Example:
```bash
cd /e/Markets/research/strategy_evolution/historical_rt_run2/<run_dir>/ && python -c "
import json, collections
totals = collections.Counter()
pnl = 0.0
roles = collections.Counter()
exits = collections.Counter()
with open('historical_rt_run2_trades.jsonl') as f:
    for line in f:
        t = json.loads(line)
        totals[t.get('status','')] += 1
        roles[t.get('pnl_accounting_role','')] += 1
        if t.get('status') == 'closed':
            pnl += float(t.get('realized_pnl_usd') or 0.0)
            exits[t.get('runner_exit_reason','') or t.get('close_reason','')] += 1
print('realized PnL: \$', round(pnl, 2))
print('roles:', dict(roles))
print('top exit reasons:', exits.most_common(5))
"
```

## Compare runs

If multiple completed runs exist in `historical_rt_run2/`:
1. Sort by mtime, take latest two
2. Read both `historical_rt_run2_summary.json` files
3. Report deltas:
   - Δ realized PnL ($)
   - Δ trade count
   - Δ bank/shadow ratio
   - New / removed exit reasons
   - Δ skipped reasons

## Output format

```
## Historical RT Run 2 — <run_id>
Completed: <True/False> | Status: <step / total>
**Realized PnL: $<X.XX>**

### By account
| account            | total | open | closed | bank | shadow | PnL $    | bank PnL $ | shadow PnL $ |
| historic_parity_live |   N |    N |     N  |    N |     N  | $X.XX    | $X.XX      | $X.XX        |
| evolve_live         |   N  |    N |     N  |    N |     N  | $X.XX    | $X.XX      | $X.XX        |

### Top exit reasons
runtime_counterfactual_fixed_hold_22m_after_entry: N
oracle_bank_peak_giveback_exit:                    N
...

### Top skipped reasons (from opportunities.jsonl)
oracle_winner_list_no_match: N
no_trade_side:               N
...

### Delta vs prior run (if any)
Δ PnL: $X (Y%)
Δ trades: N
Δ bank/shadow: ...
```

Lead with the headline PnL. Keep narrative tight.
