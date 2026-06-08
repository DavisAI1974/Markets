# S26 ASYNC STATUS — 2026-06-08 (live, for phone / fresh-session pickup)

Branch (work): `claude/crypto-trading-platform-plan-MpqwG`. Plan: `BUILD_PLAN.md`. Master: `CLAUDE (5).md`.
KEEP PAIRS SEPARATE; never pool; never standardize. Incremental validation: canary -> 5/15-min gates -> full.

## (A) DONE — validated 128-dim per-pair dipole at the larger available scale
`E:\refrag\discoveries\operator_discoveries`. Honest tier `preentry_cs100`: mean acc 0.947, perm-null **z=+9.6**, 12/12 z>3 (reproduces S25). Deterministic GROUPED (non-random) split also holds (~0.945) -> not fold-optimism. eth_bybit buy/sell concave (kept). Harness `od_larger_set_val.py`; results `od_larger_set_results.json`. See [[dipole-real-on-128dim-per-pair]].

## (B) STOPPED — too slow at scale; ROOT-CAUSED; needs a chunked restart (a NEW CHAT can do it)
- Ran `--target-size 1075` (suffix `preentry_cs1075`). **KEPT on disk:** `markets_btc_bybit_buy_win_preentry_cs1075` 482 + `_lose_` 726 (only pair 1/12 before stop). Stopped via TaskStop; trades preserved.
- **SLOWDOWN:** per-trade cost rose **2.3 s (cs40) -> 9.2 s (cs1075 win, 482 trades)** -> realistic **~30-40 h**, not 10-11 h.
- **ROOT CAUSE** (full analysis JSON: `E:\refrag\discoveries\_PERF_orchestrator_slowdown_S26.json` + `F:\Factory\knowledge\`): refrag `OperatorOrchestrator` accumulates a PER-DOMAIN evidence graph (`discoveries/evidence_graphs/<domain>_evidence.json`) loaded+rewritten every trade and GROWING within a bucket (super-linear); + global `discoveries/index.json` (2.5 MB) full-rewrite per trade; + closed-loop refinement (max_iterations default 100000); + 4.8 GB artifacts. cs100 stayed fast because accumulation was bounded to 100/bucket.
- **FIX (Greg-approved) — chunked clear-every-100, interleaved across ALL buckets:** build all 24 bucket lists; generate in 100-trade batches each holding ~equal share of EVERY bucket (balanced partial progress if it stops + tiny between-clear accumulation); after each 100, DELETE `discoveries/evidence_graphs/*_evidence.json` (safe: orchestrator starts fresh on missing graph) to reset per-trade cost; resume-safe (skip done UUIDs); KEEP BUCKETS SEPARATE on disk; re-validate the result with `od_larger_set_val.py` permutation null. Caveat: clearing drops cross-trade learning so new coeffs may differ slightly — but closer to the validated cs100 regime; re-validate, don't assume identical.

## (B2) PLANNED — full 44h (all 57,017 btc/eth eligible) in CHUNKS
Pools hold 57,017 total (win ~3,104 / lose ~53,913). The 16k run is the first slice; remaining ~41k lose to be done as SEPARATE chunked runs (Greg's call). Chunk by raising target-size with `--resume`, or by pair-groups, across sessions. ~44 h total at 2.3 s/trade.

## (B3) PLANNED — DOGE + other coins (Greg: "we need doge and the other coins too")
NEEDS UPSTREAM PIPELINE FIRST (heavier than discovery):
- Raw bins EXIST: doge & link x bybit/coinbase/kraken (`E:\Markets\live_data`, and live_data_history).
- MISSING: eligible trade pools (`research\strategy_evolution\per_bucket\markets_doge_*_{win,lose}.json`) = NONE; discovery buckets = NONE.
- Steps: (1) build_realbins for doge/link from live_data_history; (2) run full-pipeline/backtester to produce labeled win/lose trades + per_bucket pools (entry point still to scope — pool post-processors seen: `_split_lose_bucket.py`, `_patch_win_buckets_entry_ts.py`); (3) ADD doge/link pairs to `_run_top20_bottom20_pairs.py` PAIRS (currently hardcoded btc/eth only); (4) discovery run. CANARY each stage.

## STILL OWED (Result Discipline)
Net-of-cost PnL — per-trade discovery JSONs have NO net_bps/timestamp; join to `summary.json` by run_id or use full pipeline.

## QUOTE SERVICE (Greg's "market quoting" workstream — he builds it AFTER the other-coins work)
The quote service = the **markets-watch** platform's market-making layer (T3.1 `mm_passive`) fused with the OD layer. markets-watch is on branch `claude/continue-phase-2-pipeline-UFiGY` (fetched; checked out at worktree `E:\Markets\.claude\worktrees\phase2-quote`; authoritative docs there: `HANDOFF_TO_NEXT_AGENT.md`, `HANDOFF_PHASE1_5_RESULTS.md` Pass-14, `LAUNCH_PLAYBOOK.md` §1.5).
- **THE PLAN IS WRITTEN AND MUST BE FOLLOWED: `QUOTE_SERVICE_PLAN.md`** (architect output: reusable-asset inventory of BOTH parts with exact paths, recommended architecture, 6-phase build sequence each verified via forward paper, constraints/risks, and 6 open questions for Greg).
- Core design: `mm_passive` quotes resting bid/ask on `EQUILIBRIUM_TWO_SIDED` (spread minus 2 fee legs), gated by regime + OI/CB-premium/basis/liq monitors; **OD signals (coupling/lead-lag/decoupling/dipole) are GATES + spread adjusters, NOT entry signals.** Edge lever = maker-rebate spread capture (signals lose net-of-cost; venues synchronous at 1s). Build = new `backend/quote_gate.py` + merge `CouplingStore`/`odcore/` into phase-2 + wire into `poll_all()` + htmx `QuoteStatus` fragment.
- Open Qs awaiting Greg (in the plan): maker-rebate access; paper fee assumption; quote Bybit-perp?; decoupling pull threshold; live-exec location; dipole-integration bar.

## NEXT (-> `KICKOFF_2026-06-09_S27.md`)
1. **Build the chunked coeff-gen driver AS A WORKFLOW** (clear-every-100-trades, interleaved across ALL buckets, resume-safe, buckets separate) -> re-run (A) validation. KEPT: btc_bybit_buy 482 win + 726 lose.
2. doge/link/xrp: upstream trade-gen + discovery HERE (refrag-bound). Then 44h full-set chunks. Net-of-cost still owed.
3. **KB policy (Greg):** every knowledge json -> 2 copies: Factory (`F:\Factory\knowledge`) + OD (`E:\refrag\discoveries` = the OD KB), plus refrag if relevant. Sync OD-relevant Factory jsons into OD.
4. Quote service (separate): Greg builds per `QUOTE_SERVICE_PLAN.md` (phase-2 branch); answer its 6 open questions.
