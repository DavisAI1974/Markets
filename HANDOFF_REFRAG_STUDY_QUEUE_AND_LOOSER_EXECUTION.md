# Refrag Handoff: Study Queue + Looser Execution Fix

## Why this handoff exists

The previous 0-24 run exposed a workflow bug, not just a strategy problem:

- We were logging failed/no-winner contexts as evidence.
- But we were not promoting those contexts into a first-class study list that must be solved before later slices.
- The context router was also too conservative after the last patch, causing broad sweeps to start fewer trades instead of more.

The intended process is:

1. Every possible context/trade is evidence.
2. If no winner is known, put that exact context on the study list.
3. Mine/mutate after the fact, even though the historical trade window has passed.
4. Promote any positive exact-context winner before the next slice.
5. Later runs should execute/refine known and studied contexts, not keep rediscovering families from scratch.

## Rules now reinforced

- Do not tighten execution barriers.
- Practice/calibration should become looser after each run, not stricter.
- Broad sweeps should force the requested family to gather evidence.
- Routed/push-forward mode should use best positive exact-context routes first.
- If no positive route exists, it should use the study queue/probe path instead of silently doing no-trade.
- Do not rerun the same 6-hour slice unless fixing an invalid current-slice behavior bug.

## Code changes made

### `mock_trade_replay.py`

- Added a probe-mode fallback side for quiet contexts.
- When `--allow-context-probes` is enabled and the pressure router has no `buy`/`sell` side, the replay now infers a side from dipole, signed move, current/recent chunk move, volume imbalance, or last aggressor.
- This prevents unresolved/low-pressure contexts from being dropped before the forced learning family can open an evidence trade.

### `run_strategy_evolution_workflow.py`

- Defaults are now looser for the next beginning-again run:
  - `--stride-minutes` defaults to `15` instead of `30`.
  - `--passes-per-family` defaults to `1` instead of `6`.
  - `--min-context-family-samples` defaults to `1` instead of `3`.
- Queue/push-forward mode still passes `allow_context_probes=True`.

### `strategy_switcher.py`

- Removed the strict routed-callable fit/trade thresholds.
- Any positive exact-context route with at least one trade is callable unless it is explicitly `avoid_context`.
- In `--allow-context-probes` broad-sweep mode, a single requested family is now forced even if prior routing memory has another best family or marks the requested family weak.
- If no positive route exists and probes are allowed, the router falls back to a `context_routing_study_queue_probe` instead of blocking.

### `strategy_family_evolution.py`

- Added `build_study_list(...)`.
- `write_evolved_family_jsons(...)` now writes:
  - per-run `evolved_families/_study_list.json`
  - shared `research/strategy_evolution/_study_list.json`
- Study list schema:
  - `promoted_contexts`: exact contexts with a positive route ready to execute/refine.
  - `unresolved_contexts`: contexts that need after-the-fact winner mining before the next slice.
  - policy explicitly says `execution_bias: loosen_after_each_run`.

## Current generated study list

Created from existing routing memory without rerunning:

`research/strategy_evolution/_study_list.json`

Counts at creation:

- promoted contexts: 8
- unresolved contexts: 16

Command used:

```powershell
python - <<'PY'
import json
from pathlib import Path
from strategy_family_evolution import build_study_list
routing_path = Path('research/strategy_evolution/_routing.json')
study_path = Path('research/strategy_evolution/_study_list.json')
routing = json.loads(routing_path.read_text(encoding='utf-8')) if routing_path.exists() else {}
study = build_study_list(routing, source='manual_post_fix_existing_routing', run_id='handoff_fix_no_rerun')
study_path.write_text(json.dumps(study, indent=2), encoding='utf-8')
print(f"wrote {study_path} promoted={len(study['promoted_contexts'])} unresolved={len(study['unresolved_contexts'])}")
PY
```

## Verification

Compile passed:

```powershell
python -m py_compile strategy_switcher.py run_strategy_evolution_workflow.py strategy_family_evolution.py mock_trade_replay.py trade_exit_strategy.py
```

## Last completed historical state

Corrected 0-24 run set completed and stopped at hour 24:

- 0-6 summary: `strategy_evolution_workflow_runs/workflow_summary_20260518_071818.json`
- 6-12 summary: `strategy_evolution_workflow_runs/workflow_summary_20260518_072112.json`
- 12-18 summary: `strategy_evolution_workflow_runs/workflow_summary_20260518_072402.json`
- 18-24 summary: `strategy_evolution_workflow_runs/workflow_summary_20260518_072628.json`

Key result:

- Only qualified route in 0-24 was `NEWS_BREAKOUT` on `ETH|coinbase|sell|remaining18h`, +$24.07 / +2.41R in h6-12.
- Research evidence across 0-24 was negative, but that is not booked PnL.
- Exit runner logic worked on the h6-12 winner: one scale-out, then trailing stop.

## Next recommended action

User requested a new beginning-again run, but do not start it until explicitly told to start.

Prepared loose beginning-again command:

```powershell
python run_strategy_evolution_workflow.py --start-hour 0 --hours 6 --iterations 1 --all-families-until-hit --winner-pnl-r-floor 0 --winner-min-trades 1
```

After that run, inspect:

- `research/strategy_evolution/_study_list.json`
- run `evolved_families/_study_list.json`
- new analysis paper exit summary
- whether trade count increased across families
- whether promoted contexts are being executed/refined instead of rediscovered

## Important caution

The current fix creates and uses the study-list artifact, but deeper background mining can still be improved. The ideal next implementation is a dedicated resolver that takes each unresolved exact context and runs entry/exit mutations against it before the next slice starts.
