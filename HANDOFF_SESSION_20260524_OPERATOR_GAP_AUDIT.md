# Session Handoff — 2026-05-24 (Phase 1 shipped, Phase 2 parked, gap audit done)

## TL;DR for the new chat

Phase 1 (in-flight shadow→bank promotion) shipped end-to-end: module + wiring + CLI mode + backtest running. Phase 2 (promoted-context allowlist) parked after spot-check showed structural data-source mismatch with the 67k tape. Formal operator-gap audit (via refrag's operator_gap_finder applied to a Markets manifest registry) confirmed two highest-leverage next operators: **bank_demote_in_flight** and **in_flight_reject_on_stall**.

**Plan doc is the source of truth**: [MARKETS_OFFENSIVE_LAYER_PLAN.md](MARKETS_OFFENSIVE_LAYER_PLAN.md). Read it first.

## Recommended new-chat opener (from `E:\Markets`)

> "Read MARKETS_OFFENSIVE_LAYER_PLAN.md and HANDOFF_SESSION_20260524_OPERATOR_GAP_AUDIT.md. Check the in_flight_promote backtest progress (PID 102120). Then either: (a) wait for 20% before analyzer runs, or (b) build bank_demote_in_flight while we wait."

## What shipped this session

| Artifact | Purpose |
|---|---|
| [markets_in_flight_promote.py](markets_in_flight_promote.py) | Phase 1 module: per-tick tracking + shadow→bank promotion on `hold_min≥60` OR `reached_20bps_within_30m`, gated by `net_bps_per_min ≥ 0.3` |
| [mock_trade_replay.py](mock_trade_replay.py) (edit) | Added in-flight promote hook in `close_open_for_status` at line 1213, scenario-flag-gated (`oracle_winner_in_flight_promote_enabled`) |
| [run_historical_rt_run2.py](run_historical_rt_run2.py) (edit) | Added `--evidence-mode in_flight_promote` CLI flag (sets protective + in_flight_promote layer) |
| [markets_allowlist.py](markets_allowlist.py) | Phase 2 module: high-conviction allowlist from `_study_list.json` (parked but kept) |
| [replay_spotcheck_in_flight_promote.py](replay_spotcheck_in_flight_promote.py) | 3-way spot-check on 67k tape |
| [replay_spotcheck_allowlist.py](replay_spotcheck_allowlist.py) | 3-way spot-check (Phase 2 v2) |
| [analyze_sidelined_and_losses.py](analyze_sidelined_and_losses.py) | Post-phase cohort analyzer (fast, ~1 min) |
| [analyze_chunks_winners_vs_losers.py](analyze_chunks_winners_vs_losers.py) | Chunk-level dissection (top 100 winners vs 100 losers, ~3-5 min, uses MarketChunker + MarketChunkEncoder) |
| [markets_operator_gap_audit.py](markets_operator_gap_audit.py) | Markets operator registry adapter → refrag's `operator_gap_finder` |
| [MARKETS_OFFENSIVE_LAYER_PLAN.md](MARKETS_OFFENSIVE_LAYER_PLAN.md) | Plan doc with refrag tool catalog (section 5.5) + post-phase analysis rhythm (section 4.5) |

Nothing committed to git per session rule.

## What's running (do not interrupt)

| PID | What | Last seen |
|---|---|---|
| 89876 | wilson backtest (baseline) | ~23.7% |
| 96124 | protective backtest (current best baseline, +$210 anchor) | ~20.6% |
| **102120** | **in_flight_promote backtest (NEW this session)** | **~5.7%** |
| 76100 | hindsight evolve worker | live, maintains `_hindsight_missed_winner_queue.json` |
| 49916 | live RT (DO NOT restart) | on pre-evidence-gate code |

In-flight backtest is ~8 hours from full completion. Greg's instruction: **start analysis at 20% progress** (currently ~3-4 hours from now).

## Phase 1 spot-check results (preview of backtest)

```
Aggregate: 57 promotions, +$289 bank PnL, 35.1% win rate (vs 8.29% base)
Avg per promotion: +$5.07 (+25 bps avg win, -7 bps avg loss → +4.5 bps EV)
Signal split: 100% reached_20bps_within_30m (Signal B hold_min>=60 didn't fire — quality gate)
Per venue: Coinbase 40% (+$202), Kraken 60% (+$87), Bybit 0%

Trajectory ($10k notional, full 67k tape):
   run 1 ungated         -$743,679
   wilson v1             -$198,249   (+$545,430 saved)
   protective v1          -$3,216    (+$740,463 saved)
   in_flight_promote     same total admitted of which +$289 is BANK
```

**Per-strategy regression on 4 continuation families** (-$322 total): VOL_BREAKOUT, NEWS_BREAKOUT, BASIS_DISLOCATION, RELATIVE_STRENGTH. Top losers were `tte_20bps_min ≈ 1.7 min` "fakeout spikes." Phase 1.5 target.

## Phase 2 finding (parked)

v1 (post-protective upgrade, loose filter): **FAIL** net -$95. Only weak first6h n=20 seeds fired; one (`MEAN_REVERSION_CHOP`, WR=1.00 on n=20) was small-sample noise.

v2 (pre-protective upgrade, tighter filter pnl_R≥100, trades≥30, WR≤0.95): **structural no-op**. 0 upgrades. Data-source mismatch: the allowlist's high-conviction `remaining18h × BUY_UP_CONTINUATION` contexts (pnl_R 376-2059, n 141-228, WR 0.48-0.81) don't appear in wilson-admit-shadow set on 67k tape. They're wilson-REJECTED on this tape (n≥10 with mean<be empirically), even though the live mock workflow says they're winners.

**Implication**: the allowlist's evidence comes from a different evaluation framework than the per_trade.csv tape; they disagree on truth. Allowlist may still fire in live trading where ledger dynamics differ, but offline spot-check can't validate. Park until refrag (Phase 3) gives us continuous-feature similarity that may find positive sub-cohorts inside the wilson-rejected canonical keys.

## Operator gap audit (this session's diagnostic)

Built a Markets operator manifest registry for 7 operators (wilson/protective/in_flight_promote/allowlist + 3 exit operators) and ran refrag's `operator_gap_finder` on it. Output in `_markets_operator_gap_audit_output.txt`.

**Missing domains (severity 0.95):**
1. continuous_feature_similarity (Phase 3 / refrag retrieval)
2. chunk_pattern_matching (Phase 3.5 / chunk-analyzer integration)
3. expected_value_ranking (rankcore territory)
4. **bank_demote_in_flight** — symmetric to in_flight_promote; catches fakeout reversals
5. **in_flight_reject** — mid-trade kill on stall (combines `cover_by_15m` + `net_bps_per_min < 0.1`)
6. drawdown_invariants (guarantee-system territory)
7. operator_lifecycle_tracking (refrag_discovery territory)

**Orphan data types** (computed but not consumed for admission):
- `mfe_bps` — we compute max favorable excursion in exit but don't use it for promote/demote
- `cover_by_15m` — flag computed but no operator hard-cuts on it
- `mae_bps` — similarly orphaned

**Two highest-leverage actionable gaps** (no refrag stack needed, ~50 LOC each):
1. **`markets_in_flight_demote.py`** — symmetric to `markets_in_flight_promote.py`. When a promoted (or wilson-admit_bank) trade reverses (e.g., `current_net_bps < 0.5 × max_net_unrealized_bps` AND `current_net_bps_per_min < 0.1`), flip bank→shadow attribution. Saves the -$322 of Phase 1 fakeouts.
2. **`in_flight_reject_on_stall`** — at 15 min if `cover_by_15m` is false OR `net_bps_per_min < 0.1`, close the trade. Combines policy-ground-truth signals (98% recall on losers from `cover_by_15m`).

## Sequencing options for the new chat

**A. Wait + watch** — Let backtest progress to 20%, then run both analyzers (cohort + chunk + gap audit re-run), then discuss findings. Minimal new code.

**B. Wait + parallel build** — While backtest runs, build `markets_in_flight_demote.py` (Gap #4 from audit). Spot-check it. Have it ready to layer on top of in_flight_promote when Phase 1.5 starts.

**C. Skip waiting, start Phase 3** — Stand up local refrag stack (`python E:\refrag\davisai-components\scripts\run_local_stack.py`), health-check nucleus-engine/rankcore/opportune/feedbackloop, begin `markets_refrag_adapter.py`. Refrag is the strategic track; can run parallel to all of the above.

My read: **B is the highest-ROI immediate**. The demote operator addresses a concrete known regression (-$322 from fakeouts), and the implementation pattern is already proven (mirror in_flight_promote). C is right after.

## Refrag tool catalog (per Greg's "always look at refrag" directive)

Full catalog in [MARKETS_OFFENSIVE_LAYER_PLAN.md](MARKETS_OFFENSIVE_LAYER_PLAN.md#section-55).

Key finding from this session: **refrag_discovery tools (gap_finder, chain_builder, composability_scorer, task_meta_learner) are real implementations but operate on operator manifest registries.** They are meta-tools, not direct domain solvers. Using them on Markets requires the adapter pattern (which we now have a template for in `markets_operator_gap_audit.py`).

The davisai-components services (nucleus-engine, rankcore, opportune, feedbackloop, convertiq, etc.) are FastAPI scaffolds. **convertiq is currently a stub** ("TODO: Implement core logic from src_original/ files") — Greg has the full code on his phone if we want statistical mode comparison.

## Anti-drift checklist for new chat

- [ ] Read [MARKETS_OFFENSIVE_LAYER_PLAN.md](MARKETS_OFFENSIVE_LAYER_PLAN.md) before any decisions
- [ ] Per-platform bank semantics: 3 banks (Bybit/Coinbase/Kraken), 1 slot each, decisions per-trade naturally platform-isolated
- [ ] 100% bank cumulative each time — PnL tracking starts from run 1 baseline (-$743k ungated), not arbitrary history
- [ ] No EV-ranker variants — canonical-key admission gates structurally bounded at 8% base WR (max identity EV_LB = -2.84 on 67k tape)
- [ ] No fitting constants to backtest window
- [ ] No restart of live RT (PID 49916) until net-positive validated
- [ ] No git commits this session
- [ ] Use the cohort + chunk + gap analyzers after every phase (rhythm in plan doc 4.5)
- [ ] Always consider refrag tools (catalog in plan doc 5.5); ask for src_original code if a davisai-component is a stub
- [ ] Phase 1.5 candidates from gap audit: bank_demote_in_flight (catches -$322 fakeouts), in_flight_reject_on_stall (cover_by_15m + stall floor)
- [ ] Phase 2 (allowlist) PARKED until refrag introduces continuous-feature similarity
- [ ] Phase 3 standup parallel track: refrag stack health-check + markets_refrag_adapter.py

## Memory entries persisted across sessions

- [feedback_best_outcome_not_break_even.md](C:\Users\A\.claude\projects\E--\memory\feedback_best_outcome_not_break_even.md) — defensive-only is rejected; rank by EV, use positive evidence for admission
- [feedback_no_window_fit.md](C:\Users\A\.claude\projects\E--\memory\feedback_no_window_fit.md) — constants derive from economics/statistics, never tuned to a tape window
- [reference_refrag_stack.md](C:\Users\A\.claude\projects\E--\memory\reference_refrag_stack.md) — refrag stack layers + components
- [project_markets_watch.md](C:\Users\A\.claude\projects\E--\memory\project_markets_watch.md) — Markets repo context
- [feedback_no_hardcoded_limits.md](C:\Users\A\.claude\projects\E--\memory\feedback_no_hardcoded_limits.md) — never hardcode limits in OD; dynamic convergence

## File reference

- Plan doc: [E:\Markets\MARKETS_OFFENSIVE_LAYER_PLAN.md](MARKETS_OFFENSIVE_LAYER_PLAN.md)
- This handoff: [E:\Markets\HANDOFF_SESSION_20260524_OPERATOR_GAP_AUDIT.md](HANDOFF_SESSION_20260524_OPERATOR_GAP_AUDIT.md)
- Phase 1 module: [E:\Markets\markets_in_flight_promote.py](markets_in_flight_promote.py)
- Phase 2 module (parked): [E:\Markets\markets_allowlist.py](markets_allowlist.py)
- Analyzers: `analyze_sidelined_and_losses.py`, `analyze_chunks_winners_vs_losers.py`, `markets_operator_gap_audit.py`
- Backtest CLI: `python run_historical_rt_run2.py --evidence-mode {wilson|protective|in_flight_promote} --evidence-ledger-path <path>`
- in_flight backtest log: `E:\Markets\_historical_rt_run2_in_flight_stdout.log`
- Refrag root: `E:\refrag\`

---

*End of handoff. Open new chat from `E:\Markets` so plugin agents auto-load.*
