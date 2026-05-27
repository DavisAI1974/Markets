# Session Handoff — 2026-05-23 (Evidence Loop v1 + Refrag Integration Plan)

## TL;DR for the next chat (phone-friendly)

Built a structural per-canonical-key evidence ledger that gates admission by Wilson lower bound vs break-even win rate. Seeded from yesterday's day-1 backtest (1,137 outcomes, 117 unique keys). Currently re-running historical backtest with the gate active — early signal at 3.6% of tape: bank trades down 6x, **bank PnL flipped from -$13 to +$210**. Re-run continues; day-1 watcher armed.

**Next-session direction:** integrate the full refrag stack at `E:\refrag` (not just chunk analyzer — full compress/sense/expand pipeline + operator discovery + 20-ish davisai-components). User explicitly said no shortcutting to two pieces.

## Open the new chat from `E:\Markets`

So plugin agents (pnl-architect, admission-reviewer, exit-reviewer, backtest-orchestrator, pnl-leak-watcher) auto-load. The `pnl-review` skill loads policy ground truth automatically.

Suggested opener: *"Read HANDOFF_SESSION_20260523_EVIDENCE_LOOP_AND_REFRAG.md, check the day-1 rerun result, then read E:\refrag adapters and propose the markets integration."*

## What was built this session

### v1: Per-canonical-key evidence ledger (DONE, IN BACKTEST)

New module `oracle_winner_evidence.py`:
- Append-only jsonl ledger at `research/strategy_evolution/oracle_winner_evidence_ledger.jsonl`
- Per-key posterior with Wilson lower bound (z=1.6449, 90% confidence)
- Break-even win rate derived from rolling avg_win_bps / avg_loss_bps (NOT fit to any window — recomputes from ledger)
- `decide_admission(key)` returns `admit_bank | admit_shadow | reject`
- Cold-start logic: N=0 → admit_shadow; N<10 → admit_shadow; N≥10 → Wilson LB ≥ break_even → admit_bank

Wired into:
- `mock_trade_replay.py:close_trade` (~line 510): appends every close to ledger
- `oracle_winner_trade_memory.py:match_oracle_winner`: gates match via new `_apply_evidence_gate` helper. Gate respects scenario flag `oracle_winner_evidence_gate_enabled` (default False; live RT unaffected unless explicitly enabled)
- `live_mock_trade_replay.py:_bank_entry_shadow_reason_for_trade` (~line 159): honors `evidence_decision` — anything other than `admit_bank` forces shadow regardless of legacy flags
- `run_historical_rt_run2.py`: sets `oracle_winner_evidence_gate_enabled = True` on all backtest scenarios after `_prepare_settings`

Seeded from day-1 trades:
- 1,137 outcomes loaded into ledger from `historical_rt_run2_20260523_205247_utc/historical_rt_run2_trades.jsonl`
- 117 unique canonical keys
- Distribution at seed time: 1 admit_bank, 102 admit_shadow, **14 reject**
- The biggest reject: `BUY_UP_CONTINUATION|ETH|buy|early_probe|none|none|flat_0|flat_0|flat_0|neutral|neutral|neutral|none` — 364 observations, 65W/299L (17.9% win rate). This one key drove ~$3k of yesterday's loss alone.

### Files modified
- `oracle_winner_evidence.py` (NEW)
- `mock_trade_replay.py` (+24 lines, +1 import)
- `oracle_winner_trade_memory.py` (+30 lines, +1 import — added `_apply_evidence_gate` helper; also added `canonical_trade_key` field to indexed-route returns)
- `live_mock_trade_replay.py` (+6 lines in `_bank_entry_shadow_reason_for_trade`)
- `run_historical_rt_run2.py` (+5 lines after `_prepare_settings`)

**Nothing committed yet** (per user instruction "no git pushes this session").

## Current rerun state

- Process: PID 89876 (started 22:12:06 UTC), python.exe running `run_historical_rt_run2.py`
- Run dir: `research/strategy_evolution/historical_rt_run2/historical_rt_run2_20260523_221206_utc/`
- Last seen step: 475/13166 (3.61%)
- **Trade snapshot at 3.6%:**
  - 61 trades total (51 closed, 10 open)
  - Roles: 4 bank, 57 shadow
  - **PnL: bank +$210.04, all -$22.80**
- Compare to prior run at ~7%: 775 trades, -$6,899 all / -$405 bank
- Evidence gate working — drastically fewer trades, bank PnL positive

## Watchers (will end with this chat — re-arm if needed)

- `b4tz24gxa` (Bash background): polls log for step ≥ 1371 (day 1 of tape ≈ 24h of 230.58h). Fires once with snapshot.
- `bx6jps227` (Monitor): tails logs, filters for step boundaries (1000/2000/...) + failure signals (Traceback/Killed/OOM)

The backtest itself (PID 89876) will keep running regardless of chat lifecycle. New chat can re-arm watchers or just check periodically.

## Background context — see prior handoffs

- `HANDOFF_SESSION_20260523_FULL_GIT_SYNC.md` — the morning's git sync + open Path 1/2 decision (Path 1 was chosen and shipped earlier today as commit 56d3c9d)
- `HANDOFF_SESSION_20260523_PNL_PLUGIN_AND_FIXES.md` — plugin + exit logic fixes

## Live processes (unchanged from morning)

- PID 49916: live RT, started 06:39 today, still on OLD in-memory code (pre-C3 fix, pre-Path-1, pre-evidence-gate). 394 open trades all `oracle_shadow` (admission too narrow), still leaking.
- PID 76100: hindsight evolve worker, healthy, periodically rebuilds `oracle_winner_trade_list.json`
- PIDs 35228 / 49060 / 49700: backend uvicorns, untouched
- PID 89876: NEW — the backtest re-run with evidence gate

Live RT restart is still pending. **Don't restart it until evidence gate v2/v3 are ready** — restarting now would push v1 evidence-gating into production with cold-start ledger.

## Architecture decisions made this session

### Core principle (user, verbatim)
> "we can't fit to just that window, these have to be rules we trade by in real time"

All constants must be derived from economics (fees) or statistics (confidence bounds), NEVER tuned to a specific tape. Backtest results are sanity checks, never fitting targets.

### Cold-start
Pure shadow until N≥10, no provisional micro-bank. Simpler rule = more durable. Greg confirmed "evidence based on more than one trade" is the right bar.

### The 0.30 bps/min rule — deferred, not abandoned
Counterfactual on day-1 data showed the 0.30 floor would have blocked only 3 trades / $24 of $11,275 lost. The matched oracle entries were already mostly above 0.30 — the leak wasn't there. The 0.30 rule is still correct policy (entries that can't cover fees shouldn't exist), but its impact is small. **Build script change is still queued** as hygiene work for later, not a priority for the leak.

### Path 1 (drop trade_stage) — possibly to be reverted
Day-1 data: diff-stage matches lost 2.3x more per trade than same-stage. BUT same-stage matches also lost money. Path 1 is contributing factor, not root cause. The evidence loop subsumes the need to decide on Path 1 — the posterior corrects either way.

## Next-session work (in priority order)

### 1. Read the day-1 rerun result (when watcher fires)
- Final PnL vs prior run's -$11,275
- Trade count split (bank vs shadow)
- Win rate evolution chronologically
- Distribution of admission decisions

### 2. v2 — Hierarchical evidence (smaller change)
- Extend `record_close` to write outcomes at all 5 levels (entry + trait + shape + context + route from `oracle_winner_route_keys`)
- Extend `decide_admission` to walk the hierarchy: try most-specific first, fall back to broader when N insufficient
- ~50 lines of code
- Lets new keys with 0 observations inherit evidence from their broader route
- Re-seed + re-run

### 3. v3 / refrag integration — THE BIG ONE

**Location:** `E:\refrag` (DavisAI1974/agent repo, branch `codex/build-and-test-refrag-architecture-in-sandbox`)

**Brand note from refrag README:** "ReFRAG is now branded as `NOVA DeepSource`. Package names and file paths remain unchanged."

**Layered surface to integrate:**

Layer 1 — `refrag_core` (compress-sense-expand pipeline):
- chunking, encoder, projector (the "3D piece"), retrieval, selector, metrics, cache, decoder_runner, prompt_builder, training/

Layer 2 — `refrag_discovery/control_plane` (operator discovery):
- operator_lifecycle_tracker, operator_promotion_recommender, operator_lineage_tracker, operator_chain_builder, operator_benchmark_suite, operator_composability_scorer, operator_gap_finder, operator_graph_rewriter, cross_domain_transfer_detector, exploration_policy_controller, manifest_synthesizer, task_meta_learner, pipeline_performance_optimizer, production_readiness

Layer 3 — `refrag_mcp` — MCP server (gateway, public_tools, server). Defer; direct Python import is fine while both projects are local.

Layer 4 — `adapters/od_refrag_adapter.py` — EXISTING adapter showing the OD integration pattern. **READ THIS BEFORE ASSUMING IT'S A TEMPLATE.** Greg noted: "i think the od adapter was to improve od not the other way" — the direction of integration matters and should be confirmed by reading, not guessed.

Layer 5 — `davisai-components/` — 20+ sub-projects. **DO NOT DISMISS WITHOUT READING.** User explicitly said "use the full suite with 20 some different tools." At least these look directly applicable to trading:
- `feedbackloop` — exactly what we built ad-hoc; should use this primitive instead
- `config` — shared config (we have scattered scenario flags)
- `credentials-vault` — live API keys
- `etl-pipeline` — historical bins ingest
- `graphscout` — graph exploration of canonical-key relationships
- `actionpulse` / `ai-action-service` — event streams + AI-driven actions
- `guarantee-system` — SLA/invariant enforcement
- `investment-finder` — possibly candidate sourcing
- `artifacts` — artifact storage
Likely orthogonal to trading: `civic-scraper`, `fsbo-monitor`, `choropleth-api`, `civicfold`, `expired-resurrection`.

**Sequencing recommendation:**
1. Read `od_refrag_adapter.py` to understand the integration direction (Greg's correction is important — do not assume).
2. Read the README of each davisai-component before deciding what to use.
3. Replace `oracle_winner_evidence.py`'s ad-hoc ledger with `feedbackloop`'s primitive.
4. Replace `oracle_winner_trade_memory._entry_match_from_payload`'s exact-match logic with refrag's retrieval (K-nearest historical chunks weighted by similarity).
5. Wire `operator_lifecycle_tracker` + `operator_promotion_recommender` into bank/shadow promotion.
6. Wire `operator_lineage_tracker` into close handler for decision audit trails.
7. Wire `task_meta_learner` + `cross_domain_transfer_detector` for adaptive feature selection.

### 4. v4 — Chunk-level decomposition (depends on refrag chunking)
Once refrag integration provides the chunk primitive, decompose each trade into chunk sequence, build winning-pattern library, match new trades on chunk sequence not just entry features. The 15m fee-cover cut becomes evidence-based ("this in-trade chunk pattern doesn't match winning patterns") instead of rule-based.

## Important file paths

- Evidence module: `E:\Markets\oracle_winner_evidence.py`
- Evidence ledger: `E:\Markets\research\strategy_evolution\oracle_winner_evidence_ledger.jsonl` (1,137 seed entries)
- Current rerun output: `E:\Markets\research\strategy_evolution\historical_rt_run2\historical_rt_run2_20260523_221206_utc\`
- Prior run (seed source): `E:\Markets\research\strategy_evolution\historical_rt_run2\historical_rt_run2_20260523_205247_utc\`
- Refrag: `E:\refrag\` (separate repo, branch `codex/build-and-test-refrag-architecture-in-sandbox`)
- Refrag OD adapter (READ FIRST): `E:\refrag\adapters\od_refrag_adapter.py`
- DavisAI components: `E:\refrag\davisai-components\`
- Backtest stdout: `E:\Markets\_historical_rt_run2_stdout.log`

## Anti-drift checklist for new chat

- [ ] Read this handoff fully before making decisions
- [ ] Read `od_refrag_adapter.py` before assuming integration pattern (Greg corrected this assumption)
- [ ] Don't dismiss davisai-components without reading their READMEs (Greg explicitly said use the full suite)
- [ ] Don't fit constants to backtest data (only use it as sanity check)
- [ ] Don't restart live RT (PID 49916) until evidence loop is fully designed
- [ ] Don't push to git this session (per Greg's instruction)
- [ ] Use pnl-review skill to load policy ground truth
- [ ] Use the plugin agents (pnl-architect, backtest-orchestrator, pnl-leak-watcher) — they should auto-load when starting from E:\Markets
