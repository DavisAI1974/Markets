# RT Live Mock Trading Handoff

Created: 2026-05-20 late evening ET / 2026-05-21 UTC.

This file is a memory handoff for the next chat. The goal is to continue the RT/live mock trading work without losing the context from this chat.

## User Intent

The user wants live mock trading to run exactly like the historical `h0-h168` mock trade run, except with a real-time data feed.

Important requirements:

- Use the same strategy and exit strategy code/files as the historical run.
- Use the same routing/discovery JSONs from `research/strategy_evolution`.
- Use mock/practice accounting only. No real-money execution.
- Log every possible trade opportunity, including opened, blocked, and skipped decisions, for training/evolution.
- Keep hourly analysis running while trading continues.
- Do not stop live mock trading after one hour; print/report analysis and keep trading.
- Evolve/suggestion machinery should keep producing suggestions while RT trading proceeds.
- Hindsight/oracle is a gap detector, not a live PnL promise. Use it to find repeated missed patterns and then require shadow/live evidence before enabling execution.
- If a family/exit has one clear winner, show/use only that winner. If there is no clear winner but candidates are meaningful, list the best 3-4 as shadow candidates. If all exits are negative or low-margin, do not suggest one as a winner; queue evolve to create/test a better exit.

## Latest 2026-05-21 Next Chat State

Latest audit snapshot around 09:05 UTC:

```text
audited_rows = 1497
oracle_winner_rows_after_fees = 1138
missed_entry_rows = 868
opened_oracle_winner_rows = 270
captured_net_win_rows = 107
exit_missed_or_fee_leak_rows = 162
closed_actual_realized_pnl_usd = -428.73785204
oracle_winner_net_pnl_usd = 5394.15489756
oracle_incremental_vs_closed_actual_usd = 5822.8927496
closed_actual_weekly_pace_usd = -13490.92
oracle_winner_weekly_pace_usd = 169735.73
```

Top audit gaps and current closure status:

```text
SMALL_MOVE_FADE: 421 rows, 420 missed, $2485.20 oracle PnL, $2487.28 incremental.
Status: code/catalog closed; still shadow-only because no single exit is clear enough for execution.

BUY_UP_CONTINUATION: 360 rows, 253 missed, $1682.88 oracle PnL, $1781.05 incremental.
Status: code/catalog closed; capture still open. Five-run ledger evidence is negative, so evolve must test a new exit.

BUY_FADE: 112 rows, 46 missed, $530.07 oracle PnL, $611.75 incremental.
Status: code/catalog closed; capture still open. Extended-down buy fade is evolve_create_exit.

SELL_DOWN_CONTINUATION: 79 rows, 30 missed, $239.26 oracle PnL, $224.23 incremental.
Status: code/catalog closed; capture partially open. Top 3-4 shadow exits exist, but no active execution exit.
```

Other audit gaps not yet closed:

- `EXTENDED_UP_SELL_FADE`: still a candidate/watch item in audit, but live/shadow evidence is bad. Do not merge this into `SMALL_MOVE_FADE`.
- `BUY_SHAPE_WATCHLIST`: still oracle-positive but live/shadow-negative. Keep sidecar/evolve only.
- `SELL_SHAPE_WATCHLIST`: tiny positive sample, too small/low-margin for promotion. Evolve should create/test exits before promotion.
- `SMALL_MOVE_FADE_NEIGHBOR` / `onset_small_up_sell_fade`: insufficient sample and not proven. Keep separate.

Long/short clarification: the system has not only been doing longs. Main mock trade log had `206` buy trades and `172` sell trades; sell-side mock trades are modeled as shorts that win when price falls. Before real execution, confirm the venue/account supports short/perp/margin behavior the same way.

Next audit item after the current oracle-runtime closure: confirm whether the live oracle route can "trade up" when an existing mock position is open but a newer candidate has better expected oracle performance. Current assumption is that entries/exits are captured and sidecar variants run independently, but position replacement/upgrading is not yet a first-class runtime rule.

Latest code paths changed for the four gaps:

```text
E:\Markets\strategy_library.py
E:\Markets\strategy_switcher.py
E:\Markets\mock_trade_replay.py
E:\Markets\backend\api_server.py
E:\Markets\live_family_registry_compare.py
E:\Markets\live_hindsight_evolve_worker.py
E:\Markets\build_live_hindsight_missed_winner_audit.py
E:\Markets\build_live_trade_trait_ledger.py
E:\Markets\trade_exit_strategy.py
E:\Markets\research\strategy_evolution\_family_exit_pairings.json
```

New explicit families:

```text
SMALL_MOVE_FADE
BUY_UP_CONTINUATION
BUY_FADE
SELL_DOWN_CONTINUATION
```

New buy-up continuation exit mutation for evolve/shadow:

```text
buy_up_continuation_fast_fail_exits_v1
```

It is not execution-enabled. It is a test candidate because all retained prior buy-up exits are negative.

## Key Realization

We originally tried to make the backend live-paper path behave like the historical replay. That was wrong.

The backend was opening mock scenario trades and then sweeping them every few seconds through live-only pressure/status logic. Even after wiring `trade_exit_strategy.py`, trades were being closed almost immediately for reasons like:

- `pressure_flipped`
- `present_score_degraded`

Because fees are counted both ways, a trade near flat could close at roughly `-10 bps` net and book about `-$10` on a `$10,000` full-bank mock trade.

This made it look like the system was falling back to the old live-paper code, and that was effectively true at runtime: the exit file was present, but the runtime body was still backend live-paper.

The fix is to use the historical replay engine as the live runtime and only swap the data feed to `E:\Markets\live_data`.

## Current Architecture

The live mock source of truth is now:

```text
E:\Markets\live_mock_trade_replay.py
```

It tails:

```text
E:\Markets\live_data
```

It reuses the historical replay functions from:

```text
E:\Markets\mock_trade_replay.py
```

It imports the current code on disk, so post-historical updates are included automatically:

- `mock_trade_replay.py`
- `strategy_switcher.py`
- `strategy_library.py`
- `trade_exit_strategy.py`
- `research/strategy_evolution/exit_params_h0_h168_v2_promoted_min5.json`
- `research/strategy_evolution/_routing.json`
- `research/strategy_evolution/_study_list.json`
- current evolution JSON files

The backend API can still run for UI/data visibility, but it should not control RT mock scenario opens/closes.

## Code Changes Made

### 1. Added historical-live runner

Added:

```text
E:\Markets\live_mock_trade_replay.py
```

Purpose:

- Reads fresh bars from `E:\Markets\live_data`.
- Uses `mock_trade_replay.current_status_from_visible`.
- Uses `mock_trade_replay.close_open_for_status`.
- Uses `mock_trade_replay.maybe_open`.
- Uses `trade_exit_strategy.py` exactly through the replay path.
- Logs every opportunity to:

```text
E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl
```

- Writes live replay state/results/trade snapshots to:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_mock_replay_results.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_mock_replay_report.md
E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl
```

### 2. Disabled backend mock scenario controller

Edited:

```text
E:\Markets\backend\api_server.py
```

Added/uses setting:

```json
"backend_controller_enabled": false
```

`_maybe_open_mock_trade_scenarios` now returns early when backend controller is disabled.

### 3. Updated mock trade settings

Edited:

```text
E:\Markets\backend_mock_trade_settings.json
```

Current important settings:

```json
{
  "enabled": true,
  "backend_controller_enabled": false,
  "initial_bank_usd": 10000.0,
  "mock_fee_bps": 5.0,
  "exit_params_path": "research/strategy_evolution/exit_params_h0_h168_v2_promoted_min5.json"
}
```

Scenario is still `route_evidence`, with:

```json
{
  "notional_pct_bank": 1.0,
  "stop_loss_bps": 10.0,
  "take_profit_bps": 18.0,
  "exit_score_drop": 12,
  "hold_minutes": 10,
  "enforce_bucket_health": true,
  "enforce_daily_limits": true
}
```

This preserves the historical full-bank hypothetical model:

```text
learning_capital_model = full_bank_hypothetical_no_exposure_lock
actual_execution = false
actual_notional = 0.0
```

## Earlier Important Fixes

These were already made before the final architecture switch:

- `trade_exit_strategy.py` was decoupled from importing backend modules directly.
- Backend mock trades were stamping exit metadata from promoted exit params.
- Backend opportunity logging was added for every opened/blocked/skipped scenario.
- Probes were disabled for live route-evidence mode.
- `strategy_switcher.py` was updated so exact positive JSON route winners return normal non-forced strategy decisions instead of only being reachable through forced probes.
- Backend was patched to block non-exact route trades, because bad PnL was coming from forced probes and no-route decisions.

The architecture switch means future RT mock trading should be evaluated through `live_mock_trade_replay.py`, not backend mock scenario controls.

## Current Running Processes

As of the last check in this chat:

Backend API process:

```text
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

Live historical-replay mock runner:

```text
python E:\Markets\live_mock_trade_replay.py --data-dir E:\Markets\live_data --output-dir E:\Markets\research\strategy_evolution\live_mock_replay --exit-params E:\Markets\research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json --poll-seconds 5 --report-seconds 3600
```

Live collector:

```text
python E:\Markets\live_collectors.py --save-interval 2
```

There are multiple older PowerShell wrapper processes in the process list from prior restarts. The important active Python processes are the collector, uvicorn backend, and `live_mock_trade_replay.py`.

## Last Verified State

Last verified around 2026-05-20 11:51 PM ET:

- Live data files were fresh at `11:51:02 PM`.
- Live replay state was advancing.
- `live_replay_state.json` showed:

```text
status_count = 31
seen_chunks = 31
trades = 0
last write = 2026-05-20 11:51:02 PM ET
```

No live replay trades had opened yet at that moment.

Backend `/api/health` was timing out on direct checks, but the backend process was alive. The new live mock runner does not depend on `/api/health`; it reads `E:\Markets\live_data` directly.

## Useful Verification Commands

Run from PowerShell in `E:\Markets`.

Check the three important processes:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like '*uvicorn backend.api_server:app*' -or
    $_.CommandLine -like '*live_mock_trade_replay.py*' -or
    $_.CommandLine -like '*live_collectors.py*'
  } |
  Select-Object ProcessId,Name,CreationDate,CommandLine |
  Format-List
```

Check live data freshness:

```powershell
Get-ChildItem -Path 'E:\Markets\live_data' -File |
  Select-Object Name,Length,LastWriteTime |
  Sort-Object Name |
  Format-Table -AutoSize
```

Check live replay state:

```powershell
$state='E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json'
$s=Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
[pscustomobject]@{
  status_count=$s.status_count
  seen_chunks=($s.seen_chunks | Measure-Object).Count
  trades=(($s.accounts.PSObject.Properties.Value | ForEach-Object { $_.trades.Count }) | Measure-Object -Sum).Sum
  LastWriteTime=(Get-Item $state).LastWriteTime
} | Format-List
```

Check latest live replay trades:

```powershell
Get-Content -LiteralPath 'E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl' -Tail 10
```

Check latest opportunity log rows:

```powershell
Get-Content -LiteralPath 'E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl' -Tail 10
```

## Restart Commands

Restart collector only:

```powershell
$collectors = Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*live_collectors.py*' } |
  Select-Object -ExpandProperty ProcessId
foreach($pidToStop in $collectors){
  Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -WindowStyle Hidden -WorkingDirectory 'E:\Markets' -ArgumentList @(
  '-NoExit',
  '-Command',
  "cd 'E:\Markets'; python 'E:\Markets\live_collectors.py' --save-interval 2"
)
```

Restart live historical-replay mock runner only:

```powershell
$runners = Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*live_mock_trade_replay.py*' } |
  Select-Object -ExpandProperty ProcessId
foreach($pidToStop in $runners){
  Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -WindowStyle Hidden -WorkingDirectory 'E:\Markets' -ArgumentList @(
  '-NoExit',
  '-Command',
  "cd 'E:\Markets'; python 'E:\Markets\live_mock_trade_replay.py' --data-dir 'E:\Markets\live_data' --output-dir 'E:\Markets\research\strategy_evolution\live_mock_replay' --exit-params 'E:\Markets\research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json' --poll-seconds 5 --report-seconds 3600"
)
```

Restart backend API only:

```powershell
$uv = Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*uvicorn backend.api_server:app*' } |
  Select-Object -ExpandProperty ProcessId
foreach($pidToStop in $uv){
  Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -WindowStyle Hidden -WorkingDirectory 'E:\Markets' -ArgumentList @(
  '-NoExit',
  '-Command',
  "cd 'E:\Markets'; `$env:MARKETS_WATCH_LIVE='1'; `$env:MARKETS_WATCH_LIVE_DATA_DIR='E:\Markets\live_data'; `$env:MARKETS_WATCH_POLL_INTERVAL_S='5'; `$env:MARKETS_WATCH_CHUNK_MIN_SEGMENT='3'; `$env:MARKETS_WATCH_DEMO_MODE='0'; python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000"
)
```

## Hourly Analysis Automation

There is an hourly heartbeat automation named:

```text
hourly-rt-mock-trade-analysis
```

It should analyze the ongoing RT/live mock run without stopping it.

Important update for the next chat: analysis should now prioritize the live replay outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_mock_replay_results.json
E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl
E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl
```

The older `backend_practice_trades.jsonl` contains prior backend-controlled mock trades and older practice trades. It is still useful as history, but it is no longer the primary source of truth for the RT historical-style mock run.

## Things To Watch Next

1. Confirm `status_count` in `live_replay_state.json` keeps increasing.
2. Confirm `_live_mock_opportunities.jsonl` keeps appending from `source = live_mock_trade_replay`.
3. Confirm `_live_replay_mock_trades.jsonl` grows after context probes were enabled.
4. Confirm `_live_hindsight_evolve_worker_status.json` updates every 5 minutes and `_queue.json` contains `source = live_hindsight_evolve_worker`.
5. Confirm the latest sidecar has matrix `__side_buy` / `__side_sell` accounts so it is testing both directions, not only the live pressure side.
6. Confirm no new backend `source = mock_scenario` trades are being opened in `backend_practice_trades.jsonl`.
7. If no trades open for a while, inspect opportunity log blocked/skipped reasons from the new runner.
8. If trades open and close badly, debug through `mock_trade_replay.py` and `trade_exit_strategy.py`, not backend live-paper code.
9. Backend `/api/health` may time out even when the replay runner is healthy. Do not use API health as the sole source of truth for the RT mock run.

## Short Summary For Next Chat

The user asked why RT mock exits were behaving like old live-paper code instead of the historical run. We found that backend live-paper was still the runtime body and was closing trades immediately on live pressure/score flips. We switched architecture by adding `live_mock_trade_replay.py`, a live-tail wrapper around the historical `mock_trade_replay.py` engine. Backend mock scenario control is disabled via `backend_controller_enabled=false`. The live source of truth is now the replay runner reading `E:\Markets\live_data` and writing to `research/strategy_evolution/live_mock_replay` plus `_live_replay_mock_trades.jsonl` and `_live_mock_opportunities.jsonl`.

2026-05-21 follow-up: the current live run was still not equivalent to the historical evidence path because live context probes were disabled while the historical workflow used `--allow-context-probes`, and there was no running worker consuming `_hindsight_missed_winner_queue.json`. The current rule is: main live mock PnL should not be polluted by forced probes, but sidecar/evolve can run mock-only context probes for discovery. `live_family_registry_compare.py` enables probes and adds buy/sell side-probe matrix accounts. `live_hindsight_evolve_worker.py` promotes critical/high hindsight misses into `_queue.json`, and `start_live_poc.ps1` starts it in a restart loop.

## 2026-05-21 Current Memory Pointer

Before continuing this run in a new chat, read:

```text
E:\Markets\RT_LIVE_MOCK_MEMORY.md
```

That file supersedes older 15-minute sidecar assumptions. `live_family_registry_compare.py` now treats `--duration-seconds 0` as continuous and defaults to continuous mode. The sidecar should keep running alongside the main live mock runner so executed live opportunities are cloned across family/hybrid/exit variations and PnL can be compared continuously.

Latest 2026-05-21 update: the top four audit gaps are now first-class pattern families, and reports now map move shape, pattern family, and family plus exit instead of only entry family. New files/fields to inspect:

```text
E:\Markets\research\strategy_evolution\_family_exit_pairings.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.md
```

`live_trade_trait_ledger` now includes `pattern_catalog`, `by_family_exit_pair`, and `exit_pair_recommendations`, and it reads the latest five compare runs by default. Selection rule: clear winner means show only that exit for execution; no clear winner means list best 3-4 shadow candidates; negative or tiny-margin candidates mean no exit selection and evolve should create/test a better one.

Superseding 2026-05-21 update: the oracle-capture pass now uses hindsight/oracle answers as active mock labels and exit distributions while the sidecar keeps all exit variants running. Do not treat older "shadow-only/no active exit" notes for the top audit gaps as current.

## Restart-Proof Oracle Runtime Checks

Oracle capture behavior is now embedded in code, not only in generated JSON or process state:

```text
E:\Markets\strategy_switcher.py
E:\Markets\trade_exit_strategy.py
E:\Markets\mock_trade_replay.py
E:\Markets\backend\api_server.py
E:\Markets\live_mock_trade_replay.py
E:\Markets\live_family_registry_compare.py
E:\Markets\scripts\verify_oracle_runtime_paths.py
```

The live mock runner and sidecar now run this preflight automatically on startup. If it fails, the restarted process should fail fast instead of silently reverting to old no-oracle/short-exit behavior. Only skip it for deliberate debugging with `MARKETS_SKIP_ORACLE_PREFLIGHT=1`.

Before restarting the live mock/sidecar after edits, run:

```powershell
python E:\Markets\scripts\verify_oracle_runtime_paths.py
```

This smoke check confirms:

- no-side oracle contexts produce a forced mock route and inferred side
- strategy-context oracle misses produce a forced mock route
- forced oracle routes bypass mock PnL/bucket/stage guards
- oracle exit configs use long oracle hold windows instead of falling back to short `10m` exits
- oracle-managed setup blockers defer until profit gate, hard stop, or max hold instead of closing near flat and losing fees
- sidecar still contains the oracle p25, median, and p75 runner variants, plus the broader exit matrix

Important embedded rule: `trade_exit_strategy.py` now derives runtime oracle exit configs directly from:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit_rows.csv
```

So if `_family_exit_pairings.json` is stale or missing an active candidate, main mock can still resolve an oracle-derived hold/target/runner config at runtime. Explicit sidecar `exit_variant_id` scenarios still bypass family pairing so every exit variation keeps testing independently.

Follow-up fix from the negative-PnL inspection: exact positive context routes (`context_routing_exact_positive_pnl_instance` and `context_routing_exact_instance_avoided_bad_queue`) are now stamped as forced mock-only routes in `strategy_switcher.py`, and backend mock guard bypass recognizes them. This keeps live PnL guards from vetoing routes that are already answer-backed by historical/oracle routing.

## Oracle Policy Epoch Scoreboard

The mixed all-time trade ledger can stay negative because it includes old bad closes and fees. For current oracle work, use the policy-epoch scoreboard instead:

```powershell
python E:\Markets\summarize_live_oracle_policy_epoch.py
```

The live mock runner now stamps new opportunities and trades with:

```text
policy_epoch_id
policy_epoch_version
policy_epoch_started_wall_utc
opened_wall_utc
```

Current main live mock epoch after the latest restart:

```text
oracle_runtime_answer_backed_v5_20260521_112512_utc
```

This report separates post-fix trades from `legacy_carry` open trades that were opened before epoch stamping. Judge oracle-runtime progress from `answer_backed_opportunities` and `answer_backed_trades` in this report, not the old all-time closed PnL alone.

v4 adds an oracle hard-stop floor so answer-backed oracle trades do not immediately stop out from spread/noise at elapsed `0.0`. The preflight now asserts this path too.

v5 adds best-position rotation in `live_mock_trade_replay.py`:

- same answer-backed signals still qualify the same way
- no gate, strategy, or trade-limit change was made
- when an answer-backed candidate arrives, the position manager scores it
- it may close the weakest open answer-backed position only if that position is flat/underwater after fees and the incoming candidate clears the score advantage
- close reason: `rotation_to_better_answer_backed_position`
- new opened trades get `best_position_score`, `best_position_score_components`, and `position_manager_version`

First v5 smoke after restart showed `4` rotation events and `4` new opens, with `0` blocked and `0` skipped. The rotated-out positions were legacy/pre-v5 open trades, so the v5 epoch trade PnL remains clean while the rotation events are visible in the opportunity log.

## Full-Bank Allocation Shadow

Run this whenever checking whether the bank should be concentrated or split:

```powershell
python E:\Markets\summarize_live_bank_allocation_shadow.py
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_bank_allocation_shadow.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_bank_allocation_shadow.md
```

The allocation report assumes 100% of the bank is always deployed. It compares single best current score, top 5 equal, top 10 equal, score-weighted top 5/10, and converge-to-leader only when the leader has both a clear score lead and positive MTM.

First run result: across all matched audited history, 100% on the top score picked the exact oracle-best trade `45.8%` of the time, while the oracle-best trade appeared inside the top 5 score-ranked candidates `96.9%` of the time. The fresh v5 epoch has no audited future-label matches yet, so use all-history selection quality until that sample fills in. Working default should be full bank deployed across top 5 until a leader has a much clearer score plus MTM edge.

`start_live_poc.ps1` now starts a read-only bank allocation shadow reporter that refreshes this report every 120 seconds.

## Sidecar Exit Restatement / Pairing Feed

The sidecar answer flow is now embedded as a restart-safe worker:

```powershell
python E:\Markets\build_live_sidecar_exit_restatement.py --target-notional-usd 10000 --compare-run-limit 40 --update-pairings
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement.md
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv
```

Behavior:

- reads `E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl`
- reads recent `live_family_registry_compare\*\family_registry_trades.jsonl`
- restates current-day main trades at `$10,000`
- adds best executable and best any/oracle counterfactual exit columns for every closed main trade
- writes sidecar live candidate evidence into `_family_exit_pairings.json`

Important distinction: the raw live trade log remains factual. The restatement table is where we compare runtime closes against oracle/executable exit answers. Pairings get sidecar candidates as shadow evidence; execution still requires `active_candidate_id` plus `execution_enabled=true`.

Historic notional check: the h0-h168 winner artifact was not `$1,000`; it was `$10,000` on all `5616` rows. Latest current-day restatement at `$10,000`: runtime net `$-4,962.84`, best executable counterfactual `$+22,758.05`, best any/oracle counterfactual `$+36,671.11`.

`start_live_poc.ps1` runs this worker every 300 seconds, and `scripts\verify_final_live_mock_preflight.py` now requires the restatement JSON to be fresh.

## Active Live Accounts After Split

The main live mock is no longer one blended `route_evidence` ledger. `live_mock_trade_replay.py` now creates:

- `historic_parity_live`: `$10,000`, original six h0-h168 families only, exact-context route required, oracle-distilled disabled, bucket/daily enforcement on, rotation off, historical best-executable exit selector on.
- `evolve_live`: `$10,000`, all current/evolved/oracle families, oracle-distilled enabled, learning guards loose, best-position rotation on.

On restart, old `route_evidence` is moved into `retired_accounts`. The active trade snapshot now comes from the two new accounts.

Historical exit selector:

```text
E:\Markets\trade_exit_strategy.py
E:\Markets\research\strategy_evolution\_winner_trade_pnl_strategy_assignments_h0_h168.json
```

New `historic_parity_live` trades carry `historic_parity_exit_selection`. Fixed-hold selections defer the first normal close signal by the historical winning hold window (`10m`, `30m`, or `60m` after actual/runtime exit signal). Hard stops and early-loss cuts still close unless `historic_parity_defer_hard_exits` is explicitly enabled.

## Latest Critical Fix: Runtime Counterfactual Exit Contract

Status at handoff: fixed and restarted.

Active clean epoch:

```text
oracle_runtime_answer_backed_v5_20260521_133922_utc
```

What was wrong:

- Offline tests looked great because they used counterfactual exit answers, but live runtime still had competing mechanisms.
- Best-position rotation could close an answer-backed trade directly before the counterfactual exit matured.
- Runtime selector could choose `120/240/360m` holds, which made a 20-minute validation look broken.
- Pre-existing open trades from earlier epochs were being carried into the new epoch and could close immediately under the new fixed-hold policy.
- The restatement scorecard and selector policy source were blended, so a clean epoch with no closes could also erase the policy map.

What changed:

- `live_mock_trade_replay.py` now blocks rotation for counterfactual validation accounts.
- `trade_exit_strategy.py` defaults runtime counterfactual fixed-hold horizons to `10/30/60`.
- `mock_trade_replay.py` has `stamp_runtime_counterfactual_exit_selection(...)`, which refreshes stale selections and clears old fixed-hold clocks when the selected policy changes.
- `build_live_sidecar_exit_restatement.py` now emits both a clean scorecard CSV and a policy-source CSV:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv
E:\Markets\research\strategy_evolution\live_mock_replay\live_counterfactual_exit_policy_rows.csv
```

- `trade_exit_strategy.py` reads `live_counterfactual_exit_policy_rows.csv` when present, so clean active scoring and learned policy source do not fight each other.
- `scripts\verify_final_live_mock_preflight.py` now fails if runtime selector horizons escape the allow-list, rotation closes selected trades, or stale prior-epoch closed trades remain in active accounts.
- Counterfactual validation restart retires pre-existing trades out of active accounts so the scorecard starts clean.
- The live loop continuously retires prior-epoch closed rows if a carried trade closes after startup.

Latest post-restart checks:

```text
historic_parity_live: 13 open, 0 closed, all open stamped
evolve_live: 2 open, 0 closed, all open stamped
preflight: ok=true
```

Latest restatement after final restart:

```text
active scorecard: 5 main trades, 0 closed
policy source: 1407 trades, 953 closed, 953 counterfactual rows
runtime horizons allowed: [10, 30, 60]
```

Run these first in the next chat:

```powershell
python E:\Markets\scripts\verify_final_live_mock_preflight.py
python E:\Markets\build_live_sidecar_exit_restatement.py --target-notional-usd 10000 --compare-run-limit 40 --update-pairings
```

Then judge only the active clean epoch, not retired `route_evidence` or pre-fix closes.

## Superseding Fix: Selector Quality Guard - 2026-05-21 14:26 UTC

Status: patched, restarted, and preflight green.

New active clean epoch:

```text
oracle_runtime_answer_backed_v5_20260521_142646_utc
```

Why the previous clean epoch still went negative:

- The new runtime counterfactual selector was wired, but it promoted exits on positive **incremental** improvement even when the selected candidate was still negative in absolute PnL.
- `fixed_hold_after_entry` could turn a base `hold` into a forced `close` as soon as the 10m/30m/60m timer matured, even if the trade was red.
- Existing stamped selections were not refreshed when `live_counterfactual_exit_policy_rows.csv` changed, so old 10m selections could stay alive.
- Policy rows from retired/prior epochs could influence the selector.
- Sidecar compare evidence is running, but latest clean restatement still had `Sidecar-matched main trades: 0`, so sidecar variants were not directly rescuing current main closes.

The three PnL tiers are now understood as different engines:

1. Runtime actual:
   - Runs from `E:\Markets\live_mock_trade_replay.py`
   - Uses `E:\Markets\mock_trade_replay.py`
   - Calls `E:\Markets\trade_exit_strategy.py`
   - Reads live bars from `E:\Markets\live_data`
   - Writes `E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json`
   - Writes the trade snapshot `E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl`

2. Best executable counterfactual:
   - Runs from `E:\Markets\build_live_sidecar_exit_restatement.py`
   - Reads the same main trade log/state plus future bars from `E:\Markets\live_data`
   - Tests executable fixed holds and actual exits: `fixed_hold_10/30/60/120/240/360m_after_entry`, `fixed_hold_*_after_runtime_exit`, and `actual_exit::*`
   - Writes `E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv`
   - Writes policy source rows to `E:\Markets\research\strategy_evolution\live_mock_replay\live_counterfactual_exit_policy_rows.csv`

3. Best any/oracle counterfactual:
   - Also runs inside `E:\Markets\build_live_sidecar_exit_restatement.py`
   - Uses hindsight future bars to pick `oracle_best_within_*m_*`
   - This is the ceiling / answer key, not directly executable as-is.

Historical h0-h168 answer map:

```text
E:\Markets\build_winner_pnl_strategy_assignments.py
E:\Markets\reports\exit_trade_level_winners_h0_h168_20260518_164103.csv
E:\Markets\research\strategy_evolution\_winner_trade_pnl_strategy_assignments_h0_h168.json
E:\Markets\research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json
```

Dependencies searched for this pass:

```text
live_mock_trade_replay.py -> mock_trade_replay.py -> trade_exit_strategy.py
live_family_registry_compare.py -> live_mock_trade_replay.py + mock_trade_replay.py + trade_exit_strategy.py
build_live_sidecar_exit_restatement.py -> mock_trade_replay.py VENUES + phase1_5_evaluator.load_bars
build_winner_pnl_strategy_assignments.py -> reports/exit_trade_level_winners_h0_h168_20260518_164103.csv
start_live_poc.ps1 -> starts live replay, sidecar compare, restatement worker, health, hourly analysis
```

Patch made:

- `trade_exit_strategy.py`
  - Runtime selector can filter to active `policy_epoch_id`.
  - Runtime selector now requires positive absolute counterfactual net PnL, not just positive incremental improvement.
  - Runtime selector now has a win-rate floor.
  - `fixed_hold_after_entry` no longer blindly closes a red trade at timer expiry; it holds until non-negative unless a hard reason is active.

- `mock_trade_replay.py`
  - `stamp_runtime_counterfactual_exit_selection(...)` now refreshes every pass.
  - If the current policy no longer qualifies, the stale selection is cleared.
  - If selection changes or clears, old fixed-hold clocks are cleared.

- `live_mock_trade_replay.py`
  - Both active accounts now set:
    - `counterfactual_exit_selector_blocks_rotation=true`
    - `counterfactual_exit_selector_policy_epoch_only=true`
    - `counterfactual_exit_selector_min_net_usd_at_target_notional=0.0`
    - `counterfactual_exit_selector_min_win_rate=0.45`
    - `counterfactual_exit_selector_min_close_net_bps=0.0`

- `scripts\verify_final_live_mock_preflight.py`
  - Fails if the runtime selector is not active-epoch-only.
  - Fails if the selector can promote negative absolute PnL candidates.
  - Fails if win-rate floor is too loose.
  - Fails if a stamped fixed-hold selection advertises negative counterfactual net PnL.

Verification:

```powershell
python -m py_compile E:\Markets\trade_exit_strategy.py E:\Markets\mock_trade_replay.py E:\Markets\live_mock_trade_replay.py E:\Markets\scripts\verify_final_live_mock_preflight.py
python E:\Markets\scripts\verify_final_live_mock_preflight.py
python E:\Markets\summarize_live_oracle_policy_epoch.py
```

Result immediately after restart:

```text
preflight ok=true
active epoch=oracle_runtime_answer_backed_v5_20260521_142646_utc
active trades=0
active closed=0
active realized PnL=$0.00
```

Important next check: after new trades open, verify that no trade closes with `runtime_counterfactual_fixed_hold_*_after_entry` while red unless there is a hard-stop/early-loss reason.

Latest side-by-side comparison after refresh:

```text
scope                         closed  runtime     best executable  best runtime-exec  best oracle  exec gap    oracle gap
active_epoch_142646                0  $0.00       $0.00            $0.00              $0.00        $0.00       $0.00
previous_bad_epoch_133922         11  $-288.41    $-132.06         $-132.06           $+55.66      $+156.35    $+344.07
policy_source_all_closed         964  $-6,060.19  $+26,900.04      $+9,214.35         $+52,308.00  $+32,960.23 $+58,368.19
```

Interpretation: the current patched epoch has open trades but no closes yet, so there is no realized three-way score. The prior bad epoch proves the gap: executable improved but was still negative, while oracle was positive. The mixed policy source proves the broader opportunity is real, but it is not a causal live policy by itself.

Preflight after the strict selector patch is `ok=true` with warnings that open trades currently have no qualifying profitable counterfactual selections. That means base/oracle exits stay active instead of forcing unprofitable fixed-hold closes.

## Oracle Winner Exact-Entry Gate - 2026-05-23 03:33 UTC

User directive: RT may open only trades that are exact entries in
`E:\Markets\research\strategy_evolution\oracle_winner_trade_list.json`.
No route/context/shape/trait similarity is executable admission.

Patch made:

- `oracle_winner_trade_memory.py`
  - Added `oracle_winner_canonical_trade_key(...)`.
  - `match_oracle_winner(...)` now supports strict exact-entry mode via
    `oracle_winner_exact_entry_required=true` / `oracle_winner_proven_entries_only=true`.
  - Strict mode checks exact `canonical_trade_key` membership in `entries`.

- `live_mock_trade_replay.py`
  - Both active scenarios now set:
    - `oracle_winner_exact_entry_required=true`
    - `oracle_winner_proven_entries_only=true`
    - `oracle_winner_match_levels=["entry"]`

- `scripts\build_oracle_winner_trade_list.py`
  - Winner-list policy now states runtime admission is exact `canonical_trade_key`
    membership only.
  - Aggregate route/context/shape/trait indices are marked research-only.

Verification:

```text
py_compile ok
known winner entry exact-match=true
current broad-match trade batch exact-list matches=0
oracle winner list entries=7907
```

Restarted RT:

```text
active epoch=oracle_runtime_answer_backed_v5_20260523_033325_utc
live_mock_trade_replay PID=60488
historic_parity_live trades=0 open=0 closed=0
evolve_live trades=0 open=0 closed=0
```

Current expected behavior: candidates not on the exact winner list are skipped with
`oracle_winner_list_no_match`. Opening zero trades is correct until the oracle list
contains the exact current `canonical_trade_key`.

## Research Simplification - 2026-05-23 03:37 UTC

User directive: only current live hindsight oracle research should populate the
winner JSON. Sidecar/counterfactual policy rows, loose opportunity ledger rows,
and weaker historical assignments are no longer source inputs for runtime
source-of-truth.

Patch made:

- `scripts\build_oracle_winner_trade_list.py`
  - Defaults now include only `live_hindsight_missed_winner_audit_rows.csv`.
  - `_winner_trade_pnl_strategy_assignments_h0_h168.json` is excluded unless
    explicitly requested with `--include-assignments`.
  - `live_counterfactual_exit_policy_rows.csv` is excluded unless explicitly
    requested with `--include-policy-rows`.
  - `opportunity_ledger_h0_h168_loose_and_dense.json` is excluded unless
    explicitly requested with `--include-opportunity-ledger`.

Source quality check before removal:

```text
live_hindsight_missed_winner_audit: count=2680 avg_net_bps=211.21 median=248.77
winner_trade_pnl_strategy_assignments: count=4560 avg_net_bps=35.72 median=23.33
```

Latest rebuilt live-hindsight-oracle-only list:

```text
live_hindsight_missed_winner_audit=2680
entries=2680
```

Stopped extra research/report loops:

```text
build_live_sidecar_exit_restatement.py
live_family_registry_compare.py
live_hourly_analysis_report.py
summarize_live_bank_allocation_shadow.py
live_stack_health.py
```

Keep running:

```text
live_collectors.py
live_hindsight_evolve_worker.py
scripts\build_oracle_winner_trade_list.py loop
live_mock_trade_replay.py
```

## Next Chat Starting Point - 2026-05-23 03:50 UTC

Current live RT posture:

```text
active_epoch=oracle_runtime_answer_backed_v5_20260523_033325_utc
RT active trades=0
RT opens only exact canonical_trade_key entries from oracle_winner_trade_list.json
oracle_winner_trade_list.json entries=2701
source=live_hindsight_missed_winner_audit only
historical assignments are excluded
```

Fresh checks:

```text
forced live hindsight audit ran successfully
winners since active epoch start=0
skipped exact-list no-match candidates checked directly=85
positive skipped candidates after fees so far=0
pending too fresh=6
```

Historical assignment reconstruction note:

```text
chunk_id is deterministic from source_id/window_start/window_end
historical assignment/opportunity/replay result files do not preserve chunk_id or window_start/window_end
do not feed historical winners into live RT unless exact chunk keys are later verified, not estimated
```

Next requested work:

```text
Start collecting RT data for additional coins in collect-only mode.
Do not let new coins open RT trades until live hindsight oracle adds exact winner entries for them.
Need user to provide coin symbols before editing collectors.
Likely files when adding symbols:
E:\Markets\live_collectors.py
E:\Markets\mock_trade_replay.py
E:\Markets\backend\api_server.py
```

Important guardrail for new coins: adding coins should expand data collection and
oracle learning only. It must not loosen the exact-entry RT admission rule.
