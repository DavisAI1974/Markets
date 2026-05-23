# RT Live Mock Memory

Last updated: 2026-05-21

This file is the first-stop handoff for a new chat working on the RT/live mock trade system in `E:\Markets`.

## Current Goal

Run live-data-only mock trading to find the most profitable entry and exit behavior. The system should execute eligible mock opportunities aggressively, track PnL after fees, clone executed opportunities across exit variants, catalog missed winners, and promote repeated missed patterns into strategy/family memory.

## Next Chat Snapshot

Updated for new chat on 2026-05-21 around 09:05 UTC.

Current audit status: opportunities exist, but live capture is still the problem. Latest audit shows:

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

The top four audit gaps have been closed as "unmapped family" gaps, but not fully closed as profitable live-capture gaps:

```text
SMALL_MOVE_FADE: code/catalog closed, profitable shadow evidence exists, no clear single execution exit yet.
BUY_UP_CONTINUATION: code/catalog closed, but retained compare evidence is negative; evolve must build/test a new exit.
BUY_FADE: code/catalog closed, but retained compare evidence is negative; evolve must build/test a new exit.
SELL_DOWN_CONTINUATION: code/catalog closed, top 3-4 shadow exits exist, but family overall is still negative.
```

Current pattern-family audit table:

```text
SMALL_MOVE_FADE: 421 rows, 420 missed, $2485.20 oracle PnL, $2487.28 incremental.
BUY_UP_CONTINUATION: 360 rows, 253 missed, $1682.88 oracle PnL, $1781.05 incremental.
BUY_FADE: 112 rows, 46 missed, $530.07 oracle PnL, $611.75 incremental.
SELL_DOWN_CONTINUATION: 79 rows, 30 missed, $239.26 oracle PnL, $224.23 incremental.
```

Long/short clarification for next chat: the system is not only taking longs. Main mock trade log had `206` buy trades and `172` sell trades; sell-side trades are being modeled as short-side trades that win when price falls. Before any real execution path, confirm the venue/account supports short/perp/margin behavior the same way.

Next audit item after this oracle-runtime closure: confirm whether the live oracle route can "trade up" when an existing mock position is open but a newer candidate has better expected oracle performance. Current assumption is that entries/exits are captured and sidecar variants run independently, but position replacement/upgrading is not yet a first-class runtime rule.

The latest code updates made these families explicit in live strategy selection, sidecar compare, audit queueing, and evolve queueing:

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

`BUY_UP_CONTINUATION` now has a real testable exit profile:

```text
buy_up_continuation_fast_fail_exits_v1
```

It is shadow/evolve only. It cuts failed follow-through quickly, takes partial profit early, and trails the remainder. It is not execution-enabled in `_family_exit_pairings.json`.

## Non-Negotiable Runtime Rules

- Live data only. Do not replay old/backfill data as a current run.
- Mock only: `actual_execution=false` and `actual_notional=0`.
- Use fixed mock notional of `$1000` for eligible route-evidence trades.
- Bank/daily limits must not block eligible mock learning trades.
- Stale daily news must not block route-evidence mock execution.
- Bucket health must not block eligible route-evidence mock execution.
- Main live mock PnL should not be polluted by forced probes. Sidecar/evolve can run forced mock-only probes for discovery, and those must stay separate from main PnL.
- Every possible RT mock scenario evaluation should be logged to `research/strategy_evolution/_live_mock_opportunities.jsonl`, whether opened, blocked, or skipped.
- PnL must be tracked per trade, including fees. A gross winner can still be a net loser if fees exceed edge.
- Do not stop main trading during analysis unless the user explicitly says to stop everything.

## Source Of Truth

Primary live mock runner:

```text
E:\Markets\live_mock_trade_replay.py
```

Primary live files:

```text
E:\Markets\live_data\*_bins.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json
E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl
E:\Markets\research\strategy_evolution\_live_mock_opportunities.jsonl
```

Legacy/history only:

```text
E:\Markets\backend_practice_trades.jsonl
```

Backend `/api/health` is useful but secondary. The live runner and live logs are the health source of truth.

## Entry/Family Rules

Callable strategy families:

```text
SMALL_MOVE_FADE
BUY_UP_CONTINUATION
BUY_FADE
SELL_DOWN_CONTINUATION
MEAN_REVERSION_CHOP
NEWS_BREAKOUT
LIQUIDITY_SQUEEZE
VOL_BREAKOUT
BASIS_DISLOCATION
RELATIVE_STRENGTH
```

`EXACT_CONTEXT_RESOLVER` is not a seventh callable family. It is an attribution/router layer that uses:

```text
E:\Markets\research\strategy_evolution\_routing.json
```

to choose or avoid a callable family for an exact asset/venue/side/session context.

Families are not sacred. Hybrids are allowed. Bad family/context combinations should be quarantined through:

```text
E:\Markets\research\strategy_evolution\_live_family_killlist.json
```

## Continuous Exit-Matrix Sidecar

The sidecar that clones live opportunities across family/hybrid/exit variants is:

```text
E:\Markets\live_family_registry_compare.py
```

It should run continuously alongside the main live mock runner. As of this memory update, `--duration-seconds 0` means continuous and is the default. Do not launch it with `--duration-seconds 900` unless intentionally running a short experiment.

This is internal analysis only. The main live mock runner makes the primary mock execution decision. The sidecar may clone the same live opportunity across every available exit strategy, family, or hybrid to learn which entry/exit contract performs best on that structure, but those sidecar clones must remain mock-only and analytical.

Recommended continuous launch:

```powershell
$ts=(Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_utc')
$runId="hybrid_exit_matrix_1000_pnl_$ts"
Start-Process -FilePath "C:\Python313\python.exe" -WorkingDirectory "E:\Markets" -WindowStyle Hidden -ArgumentList @(
  "E:\Markets\live_family_registry_compare.py",
  "--data-dir","E:\Markets\live_data",
  "--output-root","E:\Markets\research\strategy_evolution\live_family_registry_compare",
  "--exit-params","E:\Markets\research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json",
  "--duration-seconds","0",
  "--poll-seconds","5",
  "--run-id",$runId
)
```

Sidecar outputs:

```text
E:\Markets\research\strategy_evolution\live_family_registry_compare\<run_id>\family_registry_opportunities.jsonl
E:\Markets\research\strategy_evolution\live_family_registry_compare\<run_id>\family_registry_trades.jsonl
E:\Markets\research\strategy_evolution\live_family_registry_compare\<run_id>\state.json
E:\Markets\research\strategy_evolution\live_family_registry_compare\<run_id>\summary.json
```

## Missed Winner Catalog

Keep counts for:

- total possible winning route opportunities
- executed winning route opportunities
- missed winning route opportunities
- skipped winning route opportunities
- blocked winning route opportunities

Use:

```powershell
python E:\Markets\summarize_live_mock_winners.py
python E:\Markets\export_missed_winning_opportunities.py
python E:\Markets\promote_repeated_missed_patterns.py
```

Missed winners should feed the evolution/catalog files:

```text
E:\Markets\research\strategy_evolution\_live_missed_winning_opportunities.jsonl
E:\Markets\research\strategy_evolution\_missed_winning_opportunities_queue.json
E:\Markets\research\strategy_evolution\_candidate_experiments.json
E:\Markets\research\strategy_evolution\_promoted_missed_patterns.json
```

If the same missed winning structure appears more than a few times, promote it as a family/context/hybrid candidate so it can be recognized quickly in RT rather than repeatedly missed.

## Live Trait Ledger

Use this to organize possible winning and losing trades into reusable attributes rather than one-off rows:

```powershell
python E:\Markets\build_live_trade_trait_ledger.py
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.md
```

The ledger groups live main-run records plus the latest retained sidecar compare runs by platform, route, entry trait bundle, exit shape, move shape, pattern family, family/exit pair, and full trait key. Important trait axes include family, asset, venue, side, session, trade stage, score band, pressure relation, onset/current/recent move bands, dipole bands, volume band, spread band, news coupling, and exit profile. Use it to promote repeated winners and kill repeated losers.

Current ledger behavior: `build_live_trade_trait_ledger.py` now includes the latest five compare runs by default instead of only the most recent run. This prevents the table from forgetting useful earlier sidecar evidence.

## Live Hindsight Missed-Winner Audit

This is the priority-1 gap check between live mock capture and the historical/oracle-style ceiling:

```powershell
python E:\Markets\build_live_hindsight_missed_winner_audit.py
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit_rows.csv
E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit.md
E:\Markets\research\strategy_evolution\_hindsight_missed_winner_queue.json
E:\Markets\research\strategy_evolution\_candidate_experiments.json
```

The audit scans every live opportunity against future bars, tests buy/sell when the live row had no side, and tags `missed_entry`, `exit_missed_or_fee_leak`, `captured_net_win`, and `opened_pending`. It writes critical/high candidate experiments so evolution is aimed at the biggest disconnects, especially `no_trade_side` / `NO_STRATEGY` missed directional moves, `bucket_paper_only` suppression, and opened trades where the live exit failed to capture a path that would have paid after fees. The Practice Feed API now includes `live_hindsight_audit`, and the frontend shows top hindsight misses / exit leaks in the practice trade table area.

Important 2026-05-21 audit snapshot: actual closed mock was negative while hindsight winner pace was about `$86k/week`; this means the issue is capture/entry/exit selection, not lack of opportunities. Biggest gap was `no_trade_side` / `NO_STRATEGY`, so evolution must prioritize a live-observable directional-entry recognizer for those rows.

Important 2026-05-21 disconnect fix: the historical h0-h168 run was not equivalent to the live runner. The historical opportunity ledger had `68,584` scanned opportunities, `5,616` winner rows, and `actual_executions = 0`; the ~$95k figure came from winner-selected opportunity rows / exit assignment, not a live account stream. Live mock was also running with context probes disabled, while the historical workflow used `--allow-context-probes`. Current code updates:

```text
E:\Markets\live_mock_trade_replay.py
E:\Markets\live_family_registry_compare.py
E:\Markets\live_hindsight_evolve_worker.py
E:\Markets\backend_mock_trade_settings.json
E:\Markets\start_live_poc.ps1
```

`live_family_registry_compare.py` now enables context probes and adds buy/sell side-probe matrix accounts so the matrix is closer to the historical all-family/all-side discovery path. Main `live_mock_trade_replay.py` keeps context probes disabled so exploratory probes do not pollute main route PnL. `live_hindsight_evolve_worker.py` consumes `_hindsight_missed_winner_queue.json`, promotes critical/high hindsight misses into `_queue.json`, and should run every 5 minutes from `start_live_poc.ps1`. One-shot check:

```powershell
python E:\Markets\live_hindsight_evolve_worker.py --once --max-candidates 12 --family-budget 6
```

Status:

```text
E:\Markets\research\strategy_evolution\_live_hindsight_evolve_worker_status.json
E:\Markets\research\strategy_evolution\_queue.json
```

Roadmap:

```text
E:\Markets\LIVE_ORACLE_CAPTURE_ROADMAP.md
```

Important accounting rule: main/live PnL, sidecar/shadow probe PnL, and hindsight/oracle PnL must be reported separately. The evolve worker should move candidates through `hindsight candidate -> shadow probe -> live evidence winner -> main route execution`, and only promoted live-evidence routes should affect main PnL. `live_mock_trade_replay.py` now also has a live PnL guard: if a side has enough closed live samples, negative PnL, and poor win rate, that side is blocked from new main route entries while sidecar can keep probing it.

Important 2026-05-21 note: early exit-matrix results had no net winners because most exit variants collapsed into the same `pressure_flipped` close path before their unique TP/trail/hold behavior could matter. `trade_exit_strategy.py` now supports `defer_unprofitable_pressure_exits`, and `live_family_registry_compare.py` includes `pressure_hold_gated` and `pressure_hold_runner` variants. `start_live_poc.ps1` now starts `live_collectors.py` inside a restart loop so a dead collector does not leave stale `live_data` behind while the wrapper process remains alive. Current pressure-hold sidecar run:

```text
E:\Markets\research\strategy_evolution\live_family_registry_compare\hybrid_exit_matrix_1000_pnl_pressure_hold_20260521_054541_uAc
```

Important 2026-05-21 pattern-family update: `small_up_sell_fade` is now promoted into the `SMALL_MOVE_FADE` pattern family in code and reports. The refreshed hindsight audit shows this is still the biggest oracle blind spot: `421` oracle winner rows, `420` missed entries, about `$2,485.20` oracle PnL, and `$2,487.28` incremental vs actual. This is mostly `NO_STRATEGY` / no-side sell fade structure and must stay separate from `extended_up_sell_fade` and `onset_small_up_sell_fade`, which are not proven live winners.

Important 2026-05-21 four-gap closure status:

- `SMALL_MOVE_FADE`: first-class family in code, sidecar matrix, audit, ledger, and evolve queue. This closes the old unmapped-pattern gap. It is still not execution-enabled because exit pairing is not a clear single winner.
- `BUY_UP_CONTINUATION`: first-class family in code, sidecar matrix, audit, ledger, and evolve queue. This closes the unmapped-pattern gap, but not the capture gap. Retained five-run ledger evidence is negative overall (`1653` closed, `434` net wins, `-$2765.34`), so no prior exit is suggested as a winner. New evolve candidate `buy_up_continuation_fast_fail_exits_v1` was added for shadow testing.
- `BUY_FADE`: first-class family in code, sidecar matrix, audit, ledger, and evolve queue. This closes the unmapped-pattern gap, but not the capture gap. Extended-down buy fade is `evolve_create_exit`; small-down buy fade only has weak/negative diagnostics.
- `SELL_DOWN_CONTINUATION`: first-class family in code, sidecar matrix, audit, ledger, and evolve queue. This closes the unmapped-pattern gap. It has top 3-4 shadow exit candidates, but the family remains negative overall (`774` closed, `358` wins, `-$274.49`), so no execution-enabled active exit.

The trade trait ledger now reports:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_trade_trait_ledger.md
```

It now includes `pattern_catalog`, `by_family_exit_pair`, and `exit_pair_recommendations`. Rule: if a family/exit has a clear winner, show only that winner for execution. If there is no clear single winner but the candidates are meaningful, show the best 3-4 as shadow candidates. If every exit margin is tiny, show no candidate and mark `evolve_create_exit`.

Current pairing catalog:

```text
E:\Markets\research\strategy_evolution\_family_exit_pairings.json
```

`SMALL_MOVE_FADE`, `BUY_UP_CONTINUATION`, `BUY_FADE`, and `SELL_DOWN_CONTINUATION` currently have no execution-enabled active exit. Candidate exits are shadow/evolve only unless `_family_exit_pairings.json` has both `active_candidate_id` set and the selected candidate has `execution_enabled=true`. This is intentional so a second-choice or negative exit cannot accidentally route live.

Novel/unmapped watchlist from the latest refresh:

- `SELL_SHAPE_WATCHLIST`: 38 oracle winner rows in audit, only 3 closed live/shadow samples, tiny positive actual PnL. This is novel but too small/low-margin; evolve should create/test a better exit before promotion.
- `BUY_SHAPE_WATCHLIST`: 63 oracle winner rows, but live/shadow closed PnL is negative. Keep in sidecar only.
- `SMALL_MOVE_FADE_NEIGHBOR` / `onset_small_up_sell_fade`: 7 oracle winner rows but insufficient and live/shadow negative. Do not merge into `SMALL_MOVE_FADE` yet.
- `BUY_UP_CONTINUATION`: no longer considered positive after ledger aggregation was widened to five compare runs. It remains an audit priority because oracle misses are large, but evolve must create/test a new exit or stricter entry gate before any promotion.

## Fast Health Checks

Main and sidecar processes:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*live_mock_trade_replay.py*' -or $_.CommandLine -like '*live_family_registry_compare.py*' } |
  Select-Object ProcessId,Name,CreationDate,CommandLine |
  Format-List
```

Live mock state:

```powershell
python E:\Markets\summarize_live_mock_winners.py
```

Oracle restart-proof smoke check:

```powershell
python E:\Markets\scripts\verify_oracle_runtime_paths.py
```

Run this before restarting after code/config edits. `live_mock_trade_replay.py` and `live_family_registry_compare.py` also run the same preflight automatically at startup, so a restart fails fast if oracle no-side rescue, oracle strategy-context rescue, forced-route guard bypass, runtime oracle exit configs, long oracle hold windows, setup-blocker deferral for oracle-managed trades, or sidecar oracle exit variants break. Only skip intentionally with `MARKETS_SKIP_ORACLE_PREFLIGHT=1`.

Negative-PnL inspection note: the closed book stayed negative because old stop-loss/setup-blocker closes and fees were still in realized PnL while new long-hold oracle trades were open. Embedded fixes now prevent oracle setup blockers from closing near flat before the oracle profit gate, and exact positive context routes are forced mock-only so live PnL guards do not veto them.

Oracle policy epoch scoreboard:

```powershell
python E:\Markets\summarize_live_oracle_policy_epoch.py
```

Use this report to judge the current oracle-fixed runtime. New live mock opportunities/trades are stamped with `policy_epoch_id`, `policy_epoch_version`, `policy_epoch_started_wall_utc`, and `opened_wall_utc`; older open trades appear under `legacy_carry` so they do not smear the new score. Current main live mock epoch after the allocation-report restart is `oracle_runtime_answer_backed_v5_20260521_112512_utc`.

v4 adds an oracle hard-stop floor so answer-backed oracle trades do not immediately stop out from spread/noise at elapsed `0.0`. The oracle startup preflight asserts this path too.

v5 adds best-position rotation in `live_mock_trade_replay.py`. This is position management only: no gate, strategy, or trade-limit change. Answer-backed incoming candidates are scored, and the weakest open answer-backed position can be closed with `rotation_to_better_answer_backed_position` only when it is flat/underwater after fees and the incoming candidate clears the score advantage. New opened trades carry `best_position_score`, `best_position_score_components`, and `position_manager_version`. First v5 smoke: `4` rotations, `4` opens, `0` blocked, `0` skipped.

Full-bank allocation shadow:

```powershell
python E:\Markets\summarize_live_bank_allocation_shadow.py
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_bank_allocation_shadow.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_bank_allocation_shadow.md
```

This report assumes 100% of the bank is always deployed and compares where to put it: single best current score, top 5 equal, top 10 equal, score-weighted top 5/10, and converge-to-leader only when the leader has both a clear score lead and positive MTM. It also measures how often the 100%-on-one score pick was actually the highest oracle-value trade in same-minute candidate batches.

Latest first run: all matched audited history picked the exact oracle-best trade `45.8%` of the time with 100% on the top score, but the oracle-best trade was inside the top 5 score-ranked candidates `96.9%` of the time. That argues for full-bank deployment split across top 5 as the safer default until the leader has a clearer edge. The fresh v5 epoch has no audited future-label matches yet, so use all-history selection quality until that sample fills in.

`start_live_poc.ps1` now starts a read-only bank allocation shadow reporter that refreshes this report every 120 seconds.

## Sidecar Exit Restatement

Sidecar exit results must feed the table and pairings evidence automatically.

Run:

```powershell
python E:\Markets\build_live_sidecar_exit_restatement.py --target-notional-usd 10000 --compare-run-limit 40 --update-pairings
```

Outputs:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement.md
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv
```

This does two jobs:

- restates every current-day main live mock trade at `$10,000` notional and adds best executable / best any-oracle counterfactual exit columns
- injects sidecar exit candidates into `E:\Markets\research\strategy_evolution\_family_exit_pairings.json` as shadow evidence, while leaving actual runtime closes factual

Historic parity check: the h0-h168 winner CSV used `$10,000` notional on every row (`5616/5616` rows had `notional=10000` and `hypothetical_notional=10000`). The current main mock was previously pinned to `$1,000`, so raw live PnL was 10x smaller than historic parity.

Latest restatement after adding retired-state reads: `910` closed current-day main/retired-state trades had runtime net `$-4,962.84` at `$10,000`; best executable counterfactual exits would be `$+22,758.05`; best any/oracle counterfactual exits would be `$+36,671.11`. This confirms the exit answer was present in the data but was not being applied back into the main trade table.

`start_live_poc.ps1` now starts this restatement worker every 300 seconds, and final preflight requires `live_sidecar_exit_restatement.json` to be fresh.

## Live Ledger Split

`live_mock_trade_replay.py` now runs two active accounts after restart:

- `historic_parity_live`: `$10,000` notional, six original historical families only, exact-context routing only, oracle-distilled routes disabled, bucket/daily enforcement on, best-position rotation off, family exit pairing off, historical best-executable exit selector on.
- `evolve_live`: `$10,000` notional, all current/evolved/oracle families, oracle-distilled routes on, bucket/daily enforcement off for learning, best-position rotation on, historical parity selector off.

Old blended `route_evidence` state is moved into `retired_accounts` so it does not keep contaminating the live scorecard.

The historical exit selector is embedded in `trade_exit_strategy.py` and is sourced from:

```text
E:\Markets\research\strategy_evolution\_winner_trade_pnl_strategy_assignments_h0_h168.json
```

For `historic_parity_live`, new trades are stamped with `historic_parity_exit_selection`. If the historical selector chose a fixed hold such as `fixed_hold_60m_after_actual_exit`, the runtime waits that many minutes after the first normal exit signal before closing, unless a hard stop/early-loss cut fires.

Live data freshness:

```powershell
Get-ChildItem E:\Markets\live_data\*_bins.json |
  Select-Object Name,Length,LastWriteTime |
  Sort-Object Name |
  Format-Table -AutoSize
```

## Counterfactual Exit Contract Fix - 2026-05-21 13:37 UTC

We found the thing working against runtime exits: the offline answer table and live runtime were not enforcing the same contract.

Root causes fixed:

- best-position rotation directly closed trades before counterfactual exits could mature
- runtime selector allowed `120/240/360m` holds during a short validation window
- stale open trades from prior epochs could survive restart and close immediately under the new selector
- sidecar clean scorecard and policy-source rows were blended together
- `fixed_hold_*m_after_runtime_exit` was not consistently tied to the first runtime exit/degradation signal

Current active clean epoch after the final restart:

```text
oracle_runtime_answer_backed_v5_20260521_133922_utc
```

Current runtime contract:

- active live accounts are `historic_parity_live` and `evolve_live`
- both use `$10,000` notional
- both have `counterfactual_exit_selector_enabled=true`
- both have `counterfactual_exit_selector_allowed_horizons_minutes=[10,30,60]`
- counterfactual validation mode has best-position rotation off
- pre-existing trades from older epochs are retired out of active accounts on restart
- all active open trades must have `runtime_counterfactual_exit_selection`

The sidecar restatement now writes two tables:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv
E:\Markets\research\strategy_evolution\live_mock_replay\live_counterfactual_exit_policy_rows.csv
```

Use `live_sidecar_exit_restatement_rows.csv` as the clean active-epoch scorecard. Use `live_counterfactual_exit_policy_rows.csv` as the learned executable policy source; it can include retired/current-day policy evidence so the selector still has answers before the clean epoch has many closes.

Latest clean restatement after the final restart: `5` active-epoch main trades, `0` active-epoch closed trades, policy source has `1407` trades / `953` closed trades / `953` counterfactual rows.

Verification commands:

```powershell
python E:\Markets\build_live_sidecar_exit_restatement.py --target-notional-usd 10000 --compare-run-limit 40 --update-pairings
python E:\Markets\scripts\verify_final_live_mock_preflight.py
```

Final preflight was green after restart. Live state sanity immediately after restart: `historic_parity_live` had `13` open / `0` closed, `evolve_live` had `2` open / `0` closed, and every open trade was stamped with a counterfactual exit selection. The live loop now continuously retires prior-epoch closed rows, not just at startup.

## Selector Quality Guard - 2026-05-21 14:26 UTC

The 13:39 UTC clean epoch still went negative because the counterfactual selector was wired but not quality-gated. It selected fixed holds that were incrementally better than runtime but still negative in absolute PnL, then `fixed_hold_after_entry` forced closes at 10m/30m/60m even when the base exit engine wanted to hold.

Agent/code audit findings:

- current losing clean-epoch closes were all `evolve_live`
- close reasons were `runtime_counterfactual_fixed_hold_10m_after_entry` and `runtime_counterfactual_fixed_hold_30m_after_entry`
- selector had no positive-net floor and no win-rate floor
- stale stamped selections could survive a policy CSV refresh
- policy rows from prior/retired epochs could influence runtime
- sidecar compare had `0` matched clean-epoch main trades, so sidecar variants were not directly rescuing current closes

Dependency / engine map:

```text
Runtime actual:
E:\Markets\live_mock_trade_replay.py
E:\Markets\mock_trade_replay.py
E:\Markets\trade_exit_strategy.py
E:\Markets\live_data
E:\Markets\research\strategy_evolution\live_mock_replay\live_replay_state.json
E:\Markets\research\strategy_evolution\_live_replay_mock_trades.jsonl

Best executable + best any/oracle counterfactual:
E:\Markets\build_live_sidecar_exit_restatement.py
E:\Markets\live_data
E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv
E:\Markets\research\strategy_evolution\live_mock_replay\live_counterfactual_exit_policy_rows.csv

Historic h0-h168 answer map:
E:\Markets\build_winner_pnl_strategy_assignments.py
E:\Markets\reports\exit_trade_level_winners_h0_h168_20260518_164103.csv
E:\Markets\research\strategy_evolution\_winner_trade_pnl_strategy_assignments_h0_h168.json
E:\Markets\research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json
```

Patch made:

- `trade_exit_strategy.py`: selector can filter to active policy epoch; requires positive absolute counterfactual PnL and win-rate floor; `fixed_hold_after_entry` will not blindly close a red trade at timer expiry.
- `mock_trade_replay.py`: counterfactual selections refresh every pass; stale selections and stale fixed-hold clocks are cleared.
- `live_mock_trade_replay.py`: both active accounts now use active-epoch-only selector, positive-net floor, `0.45` win-rate floor, rotation block, and non-negative close floor.
- `scripts\verify_final_live_mock_preflight.py`: preflight now checks selector quality gates.

New clean epoch after patch/restart:

```text
oracle_runtime_answer_backed_v5_20260521_142646_utc
```

Verification:

```text
py_compile ok
final preflight ok=true
active trades=0
active closed=0
active realized PnL=$0.00
```

Next judgement must use this new epoch, not the 13:39 UTC epoch.

Latest three-way comparison:

```text
scope                         closed  runtime     best executable  best runtime-exec  best oracle  exec gap    oracle gap
active_epoch_142646                0  $0.00       $0.00            $0.00              $0.00        $0.00       $0.00
previous_bad_epoch_133922         11  $-288.41    $-132.06         $-132.06           $+55.66      $+156.35    $+344.07
policy_source_all_closed         964  $-6,060.19  $+26,900.04      $+9,214.35         $+52,308.00  $+32,960.23 $+58,368.19
```

The active epoch has no closed trades yet. Preflight is green with warnings because no current open trade has a qualifying profitable counterfactual selection; that is acceptable after the quality guard and means base/oracle exits remain active instead of forcing a red fixed-hold close.

## 2026-05-23 Exact Oracle Winner Source Of Truth

User clarified the rule: RT opens only exact trades from
`E:\Markets\research\strategy_evolution\oracle_winner_trade_list.json`.
The list had `7907` positive winner entries after the latest rebuild.

Implementation:

- Exact runtime key is `canonical_trade_key`:
  `STRATEGY|ASSET|venue|side|bucket_session|entry_ts_utc|chunk_id`.
- `oracle_winner_trade_memory.match_oracle_winner(...)` in strict mode checks
  exact membership in the JSON `entries` array.
- `live_mock_trade_replay.py` sets strict mode for both `historic_parity_live`
  and `evolve_live`:
  `oracle_winner_exact_entry_required=true`,
  `oracle_winner_proven_entries_only=true`,
  `oracle_winner_match_levels=["entry"]`.
- Route/context/shape/trait aggregate indices remain in the JSON only for
  research summaries. They are not executable admission paths.

Fresh runtime epoch after restart:

```text
oracle_runtime_answer_backed_v5_20260523_033325_utc
```

Sanity check after restart:

```text
historic_parity_live trades=0 open=0 closed=0
evolve_live trades=0 open=0 closed=0
opportunity log shows oracle_winner_list_no_match for non-exact candidates
```

This zero-trade state is intentional. It means broad bucket candidates are no
longer opening. New opens should appear only after the oracle winner list contains
the exact current canonical key.

## 2026-05-23 Live-Hindsight-Oracle-Only Research Feed

The source-of-truth JSON is now live-hindsight-oracle-only by default.

Included sources:

```text
E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit_rows.csv
```

Excluded unless explicitly requested:

```text
E:\Markets\research\strategy_evolution\_winner_trade_pnl_strategy_assignments_h0_h168.json
E:\Markets\research\strategy_evolution\live_mock_replay\live_counterfactual_exit_policy_rows.csv
E:\Markets\research\strategy_evolution\opportunity_ledger_h0_h168_loose_and_dense.json
```

Historical assignments were removed because they were weaker:

```text
live_hindsight_missed_winner_audit: count=2680 avg_net_bps=211.21 median=248.77
winner_trade_pnl_strategy_assignments: count=4560 avg_net_bps=35.72 median=23.33
```

Latest live-hindsight-only rebuild:

```text
entries=2680
by_source.live_hindsight_missed_winner_audit=2680
```

Stopped extra research/reporting loops:

```text
build_live_sidecar_exit_restatement.py
live_family_registry_compare.py
live_hourly_analysis_report.py
summarize_live_bank_allocation_shadow.py
live_stack_health.py
```

Remaining intended loop:

```text
collect live data -> hindsight oracle audit -> oracle winner JSON -> exact-entry RT gate
```

## 2026-05-23 New Chat Handoff

Current state:

```text
active_epoch=oracle_runtime_answer_backed_v5_20260523_033325_utc
RT active trades=0
oracle_winner_trade_list.json entries=2701
winner JSON source=live_hindsight_missed_winner_audit only
RT admission=exact canonical_trade_key only
```

Recent verification:

```text
forced hindsight audit found 0 winners since active epoch start
85 exact-list no-match skips were directly scanned against current future bars
0 were positive after fees so far
6 were still too fresh to judge
```

Historical winners:

```text
Do not add historical assignment winners back into live RT admission.
They lack chunk_id/window_start/window_end in persisted files.
Any reconstruction without a unique verified chunk window is not exact.
```

Next user intent:

```text
Start collecting RT data for additional coins.
Collect-only first.
No new coin RT opens until live hindsight oracle writes exact winner entries for that coin.
Ask user for the coin symbols and venues if not already provided.
```
