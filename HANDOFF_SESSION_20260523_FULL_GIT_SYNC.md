# Session Handoff — 2026-05-23 (Full Git Sync + Open Path 1/2 Decision)

## TL;DR for the next chat (phone-friendly)

All local Markets work is now committed and pushed to `origin/claude/run-pass-14-classifier-nTViL`. The repo had ~5.5 GB of run artifacts plus many untracked core files; `.gitignore` was expanded with an allowlist for `research/strategy_evolution/` policy files, and the rest was committed in 7 thematic commits.

**One unanswered decision is waiting for you** — see "Open Decision" below.

## Branch + sync state

- Branch: `claude/run-pass-14-classifier-nTViL`
- Remote: `origin = https://github.com/DavisAI1974/Markets.git`
- Local == origin (all commits pushed at end of session)

## Commits added this session (in order)

| Commit | What |
|---|---|
| `0615501` | RT exit logic: shadow protection + quality gates + news fix + preflight tightening (earlier today) |
| `261b824` | markets-pnl plugin: 5 agents + pnl-review skill (earlier today) |
| `3165345` | HANDOFF 2026-05-23 PnL plugin + exit logic fixes (earlier today) |
| `063450a` | gitignore: cover mock_replay outputs, strategy_evolution_workflow runs, pass-N analysis dirs, live_data, logs, large research/ artifacts |
| `75a4268` | core engine: strategy_library, strategy_switcher, mock_trade_replay, exit_engine, feature_store, dipole/oracle/news/onchain modules, builders, live runners, scripts (57 files) |
| `aefce88` | backend: dipole + pressure-watch + trade-stage wiring, evolve request server, signal allocator (4 files) |
| `cffc403` | frontend: LiveTape/SignalCard/EvolveLab/TapeDetail, route error boundary, mock backend (29 files) |
| `4d1154e` | docs: 10 HANDOFFs + 8 production notes/schemas/roadmaps (18 files) |
| `47a9f2f` | policy: research/strategy_evolution allowlist (oracle list + strategy specs + routing + killlists) + the three on-disk analyses (30 files; per_trade.csv excluded) |
| `ae931d9` | config: scenario params, news events + policy, daily limits, venue prefs, modified discord poster + cells runtime controls (16 files) |

## What .gitignore now covers (so you don't see noise on phone)

- `mock_replay_*_out/`, `mock_replay_*/` and `mock_replay_clean_*/`, `mock_replay_exit_capture_*/` (each can be 6–16 MB)
- `strategy_evolution_workflow_runs*` (many per-pass dirs)
- `pass*_analysis_out/`, `pass*_dipole_canary_*/`, `pass*_present_signal_strength_*/`, `pass*_news_*/`
- `news_dipole_replay_*_out/`, `news_raw_ingest.jsonl`
- `historical_rt_run2/` (large state + per-bar trades)
- `live_data/`, `live_data_history/` (~60 MB total)
- `backend_{cb_premium,edge,funding,oi}_history.jsonl`
- `*.log`, `_*_stderr.log`, `_*_stdout.log`, `frontend/vite-phone.log`
- `runtime_logs/`, `_attempts.jsonl`, `reports/`
- `markets-list.txt`, `markets-tree.txt`
- `_analysis_*/per_trade.csv` (the 53 MB CSV — md/summary.json kept)
- `research/*` except an explicit allowlist under `research/strategy_evolution/` (oracle list + strategy specs + routing/queue/variants/killlists + policy markdown)

## Files that auto-update during live RT (expect drift)

These were committed at session end but the live engine rewrites them; the next sync will show new diffs:

- `cells_runtime_controls.json` — live RT rewrites `generated_utc` + per-cell `updated_utc` every audit pass (~6 min)
- `frontend/public/live-preload.js` — auto-rewritten on frontend build/preload pass

Don't chase these as "session work" — they're heartbeats.

## Live process state (at end of session — same as morning handoff)

- **Live RT**: PID 49916, still running OLD in-memory code (started before today's exit fixes). 30 oracle_shadow open trades, 0 bank. **Needs restart** to pick up the new exit logic — most impactful is C3 (shadow trailing/15m protection). Until restarted, those 30 shadows have no trailing safety net or 15m fee-cover cut.
- Live collectors PID 73408 (or similar): healthy
- Live hindsight evolve worker PID 76100: healthy, audits every 300s
- Backend uvicorns: 35228 (8000), 49700 (8001), 49060 (8002): untouched
- Historical RT: NOT running

## Open decision (start here next session)

### Background

The historical RT run 2 produces **zero trades** because today's 287-key oracle list and May 4–14's 189 structural patterns have **zero overlap**. The matching code is verified date-agnostic — `_news_state` was the only date leak and is now hardcoded `"none"`. The canonical key has 14 categorical fields, none of which read a calendar timestamp.

### Audit result (this session)

Every field in `oracle_winner_canonical_trade_key` was traced. None read a calendar timestamp. The remaining divergence between today's oracle JSON and May 4–14's patterns is in:

- `trade_stage` (`onset` vs `late`) — derived from `age_chunks`, the *number of chunks the candidate setup has been on the same side before a trade opens*. Time-derived in a soft sense (chunks ≈ 1 min), but it's **setup-persistence time**, not **trade duration time**.
- bps move bands (`up_extended_10_20` vs `up_extreme_ge_20`) — actual market state, derived from price differences.
- dipole/acl1/volume bands — market signals.

You said: *"the only thing we are worried about concerning 'time' is trade duration time. The date should have nothing to do with decision tree as far as matching trades whether it's past or present."* And separately: *"just don't throw out time duration in the trade. it's important."*

`horizon_minutes` (= trade duration time) is **NOT** in the canonical key — it lives in `selected_exit` metadata and drives the hold-to-horizon rule. Path 1 below does not touch it.

### Two clean paths to non-zero historical trades

**Path 1 — Drop `trade_stage` from canonical key.** True to your "no time gates" rule (setup age is time-like). The remaining 13 fields still discriminate by strategy/asset/side/score/pressure/market-shape/signals. Surgical 1-line edit in `oracle_winner_trade_memory.py:131` + rebuild `oracle_winner_trade_list.json` via `scripts/build_oracle_winner_trade_list.py`. `horizon_minutes` is untouched.

**Path 2 — Add `shape`-level fallback for historical RT only.** Canonical key unchanged. When exact 14-field fails, fall back to 11-field shape match (which still includes `stage` and `move`). Adds 3 lines to `run_historical_rt_run2.py` to set `oracle_winner_match_levels = ["entry", "shape"]` per scenario. Doesn't actually answer "is stage a time gate" — it just bypasses it on historical only.

**Recommendation: Path 1** — directly answers your stated rule. After rebuild, historical and live use the same admission contract with no fallback hacks.

## Suggested first actions next session

1. Read this handoff.
2. Confirm Path 1 or Path 2 (or "let me think about it more").
3. If Path 1: 1-line edit + rebuild oracle JSON + run `backtest-orchestrator` agent.
4. If Path 2: 3-line edit in `run_historical_rt_run2.py` + run `backtest-orchestrator`.
5. Decide whether to restart live RT to pick up the C3 shadow-protection fix that's still only in committed code, not the running engine.

## Plugin available

`markets-pnl` plugin auto-loads at session start. Five agents (pnl-architect, admission-reviewer, exit-reviewer, backtest-orchestrator, pnl-leak-watcher) + pnl-review skill with the three on-disk analyses as policy ground truth.
