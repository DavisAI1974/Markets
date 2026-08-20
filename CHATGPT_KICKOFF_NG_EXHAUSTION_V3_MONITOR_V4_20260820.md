# ChatGPT Kickoff — NG Exhaustion V3 Monitor / V4 Next — 2026-08-20

Take over on branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

## Read first, in this order

1. `research/NG_EXHAUSTION_V3_V4_CHAT_DECISIONS_ALL_NOTES_20260820.md`
2. `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`
3. `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_ADDENDUM_20260820.md`
4. `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`
5. `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`
6. `CHATGPT_HANDOFF_NG_EXHAUSTION_V3_MONITOR_V4_NEXT_20260820.md`
7. `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`

Current repo state and the 2026-08-20 documents above are truth. Do not redo completed Phase-1/Phase-2 work.

## Immediate priority

**Monitor/recover the pinned V3-T0 core agents.**

Workflow:

`.github/workflows/ng_exhaustion_v3_t0_pinned_core_20260820.yml`

It executes the exact launch commit with `${{ github.sha }}` and runs 14 lanes:

- D0 Logistic / ExtraTrees / KNN
- D1 Logistic / ExtraTrees / KNN
- D2 Logistic / ExtraTrees / KNN
- D3 Logistic / ExtraTrees / KNN
- D4 case study
- D5 case study

Expected durable reconciliation:

`research/generated/ng_exhaustion_v3_t0_pinned_core_20260820/NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_RESULTS_20260820.json`

and

`research/generated/ng_exhaustion_v3_t0_pinned_core_20260820/NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_FINDINGS_20260820.md`

Do not claim the run completed until those files or explicit workflow evidence exists.

If the run fails, inspect the failing job/step and patch only active V3 infrastructure necessary to execute the intended contract. Retrigger with a marker update. Never modify protected artifacts to rescue a run.

## V3 doctrine

Current revision:

`V3_CONTINUOUS_LIVE_MARKET_STATE_T0`

D1-D5 fixed benchmark ladder:

`PRIOR -> T0 -> H+1 -> H+2 -> H+3 -> H+4 -> H+5`

T0 is the birth second, not H=0.

Target polarity is not a primary target. P/O/S/X structural state/family is the primary type target. SAME/FLIP is secondary context only.

The live market movie — price, dense roll20/dipole, signed flow, book and causal/session state — remains visible continuously.

No model vote or probability aggregation. Preserve Logistic, ExtraTrees and KNN independently.

## V4 boundary

V4 is the next architecture:

- no hard-coded PRIOR/H grid;
- timing is discovered per instance and reported after the fact;
- causal second-by-second scoring;
- discovery-frozen confidence/margin/persistence lock rule;
- frozen benchmark versus adaptive learn-after-reveal walk-forward;
- completed cases may train only future instances and never rewrite past calls.

Current V4 files include:

- `research/NG_EXHAUSTION_CONTINUOUS_INSTANCE_TIMING_CORRECTION_20260820.md`
- `research/ng_exhaustion_continuous_instance_features_20260820.py`
- `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`

**Do not launch V4 automatically.** It was deliberately left for a new chat after V3 is under control. Finish/review V4 code before any intentional launch.

## Trade boundary

Older D0 trade research that capped exits at the next canonical exhaustion is hindsight-contaminated for execution and is provenance only.

Corrected trade doctrine:

- model-specific signal;
- causal direction only;
- no realized target polarity;
- fixed horizon;
- no future-event exit cap;
- preserve all losing/no-trade cases.

## Open detector-mark seam

Do not conflate:

- frozen t0;
- actual upstream detector mark time;
- endpoint confirmation.

Read `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`.

Do not retune the protected detector to solve the documentation seam.

## Protected

Do not modify:

- detector;
- canonical rows/evidence;
- Phase 1;
- Phase 2;
- runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- SSOS.

Preserve all true/false/losing/censored/low-support/model-disagreement evidence.

Policy:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

## Deferred

A possible additional Frankie capability was mentioned and deliberately deferred. Do not guess or implement it unless the user brings it back up.

## One-message drop-in

> Take over the NG exhaustion program on `chatgpt/ng-exhaustion-entry-timing-revival-20260818`. Read `research/NG_EXHAUSTION_V3_V4_CHAT_DECISIONS_ALL_NOTES_20260820.md` first, then `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`, `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`, and `CHATGPT_HANDOFF_NG_EXHAUSTION_V3_MONITOR_V4_NEXT_20260820.md`. The immediate priority is monitoring/recovering the exact-commit-pinned V3-T0 core workflow; do not launch V4 until V3 is under control. V4 is the later continuous per-instance timing + frozen/adaptive walk-forward architecture. Do not modify protected artifacts or permanent Frankie. Preserve every true/false/losing/censored/low-support/model-disagreement case and keep `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
