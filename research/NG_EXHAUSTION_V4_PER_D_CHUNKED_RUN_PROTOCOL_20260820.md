# NG Exhaustion V4 — Per-D / Per-Year / Pilot-First Run Protocol — 2026-08-20

Status: **BINDING ADDITIVE RUN-ORCHESTRATION PROTOCOL. NO V4 EMPIRICAL LAUNCH IS AUTHORIZED BY THIS DOCUMENT.**

This protocol records the user's 2026-08-20 instructions that future D-series runs must use a tighter protocol, must be broken into smaller units, may also be split by year, and must **not begin with full D runs**. The immediate empirical strategy is **small frozen verification samples first; full multi-year D runs last**.

It is additive to:

- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`;
- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`;
- `research/kalshi/FRANKIE_NEXT_CHAT_HANDOFF_CURRENT_20260820.md`;
- the unified-framework audit and all protected-boundary rules.

Nothing here weakens causal, blind/reveal, provenance, retention, sparse-stage, rollback, or launch gates.

## 1. Pilot-first hierarchy

Future result-bearing work follows this hierarchy:

`small frozen verification sample -> D/year slice -> additional bounded slices -> full D/year reconciliation -> full multi-year D run LAST`

The purpose of the first small sample is to verify mechanics, causality, provenance, ledger integrity, reveal separation, artifact production, resource/runtime behavior and reconciliation. It is **not** a substitute for population evidence and must not be described as one.

Until the pilot passes its predeclared integrity criteria, do not dispatch the corresponding full D run.

## 2. One D per top-level empirical run

D0, D1, D2, D3, D4 and D5 must not be dispatched as one monolithic empirical workflow.

Each depth target gets a distinct top-level run identity and durable receipt:

- `D0_TERMINALITY`;
- `D1_CONTINUATION`;
- `D2_CONTINUATION`;
- `D3_CONTINUATION`;
- `D4_CASE`;
- `D5_CASE`.

A completed D slice is allowed to move immediately into its already-authorized integrity/adjudication/gap-decomposition step without waiting for unrelated D runs to finish. Completion of one D does not imply completion, validation or promotion of another D.

No cross-D voting is introduced. No D may borrow a later D's result to revise an earlier frozen prediction ledger.

## 3. Years are independent scheduling partitions

Within a D, the historical chronology may be partitioned by calendar year or another predeclared contiguous year-like span before smaller session/date chunks are formed.

Examples:

- `D0 / 2021`;
- `D0 / 2022`;
- `D1 / 2021`;
- `D2 / 2024`.

Year slicing is for runtime, restartability, source-coverage accounting and faster downstream work. It must not alter model semantics, labels, split membership, feature availability, lock rules or acceptance criteria.

A completed `D × year` slice may enter integrity QA and gap decomposition immediately. Population claims across years require the predeclared multi-year reconciliation.

Year boundaries may not be selected or changed after inspecting prediction quality or truth outcomes.

## 4. Small verification sample before any large D/year run

Before a full D/year slice is allowed to run, create a **small frozen pilot manifest** from eligible chronology using a predeclared non-output-dependent selection rule.

The pilot should be deliberately small enough to finish promptly and exercise the complete pipeline end to end. Its size is an engineering verification parameter, not a model-selection parameter.

The pilot must exercise, where applicable:

- causal `event_known_by` gating;
- multi-clock availability;
- source/contract/roll provenance;
- missing/stale/not-yet-known/true-zero state semantics;
- predecessor lifecycle;
- probability movie and first-lock/no-lock ledger;
- sealed prediction-to-execution object generation without live execution;
- blind-ledger sealing before reveal;
- independent reveal/adjudication path;
- chunk receipt generation;
- deterministic hash/replay checks;
- D/year reconciliation;
- failure/restart/resume path.

The pilot must preserve every selected case, including negative, losing, censored, no-lock, wrong-lock, missing-channel and model-disagreement cases.

A pilot may establish `PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE`; it may not establish model superiority, calibration adequacy, a universal D-law, trade edge or permanent Frankie readiness.

## 5. Chronological chunks inside each D/year slice

Each D/year slice must itself be partitioned into bounded chronological chunks whenever runtime/population warrants it.

Permitted chunk boundaries are natural causal boundaries such as trading session/date or a fixed predeclared consecutive-session block. Chunk membership must be frozen before any predictions from that run are inspected.

The chunk plan must preserve:

- exact chronological order;
- exact eligible population;
- exact discovery/OOT/held-out membership;
- exact source/contract/roll identities;
- every true, false, losing, censored, no-lock, wrong-lock, low-support, missing-channel and model-disagreement case.

Forbidden chunking behavior:

- output-dependent repartitioning;
- moving difficult cases to another chunk after inspection;
- deleting a chunk because its result is inconvenient;
- rebalancing labels using future truth;
- changing feature/channel availability by chunk;
- silently changing model/ruleset/snapshot within one logical run.

## 6. Pre-dispatch sealed run manifest

Every pilot or larger D/year run must have an immutable manifest frozen before dispatch containing at minimum:

- `run_id`;
- `run_scope` = `PILOT`, `D_YEAR_SLICE`, or `FULL_D_MULTIYEAR`;
- `depth_target`;
- `year_or_date_span`;
- exact candidate commit SHA;
- runner identity;
- adjudicator identity;
- ruleset identity/hash;
- engine identity/hash;
- adapter identity/hash;
- reconciler identity/hash;
- model/snapshot/head identities;
- source/contract/roll/coverage manifest hash;
- population/split identities;
- pilot-selection identity when applicable;
- chronological chunk list and chunk hashes;
- discovery/OOT/held-out boundaries;
- channel/view manifest;
- reveal rule;
- lock rule;
- timeout/resource envelope;
- restart/resume policy;
- explicit protected-boundary assertion;
- `v4_empirical_launch_authorized` flag.

The manifest must fail closed if the exact launch authorization does not match the candidate commit/workflow/ruleset named by the user.

## 7. Chunk execution contract

Each chunk receives a stable `chunk_id` and frozen input manifest.

Each chunk must emit its own durable receipt before it is considered complete. The receipt must include:

- input manifest hash;
- exact first/last causal session or timestamp;
- eligible row/instance counts;
- processed/preserved counts;
- omission count and explicit reasons;
- model/snapshot/head/ruleset identities;
- source coverage/provenance hash;
- immutable probability-ledger hash;
- first-lock/no-lock ledger hash;
- output artifact hashes;
- execution status;
- integrity/test status;
- technical failure reason if any.

A technical failure retries or resumes that exact chunk only. It must not force completed chunks to rerun unless their inputs, code, ruleset or source hashes changed. If any such identity changes, the logical run gets a new run identity rather than silently mixing old and new chunks.

## 8. Incremental progress without premature claims

Four progress levels are distinct:

### Pilot-complete

All selected pilot chunks reconcile and integrity/causal/provenance criteria pass. This allows engineering to move to the next build/check or, after separate exact launch authorization, a larger D/year slice. It does not establish population performance.

### Chunk-complete

A completed chunk may immediately enter integrity QA, provenance QA and failure/gap decomposition. Population performance claims remain provisional.

### D/year-complete

All required chunks for one D/year slice reconcile exactly. That slice may enter its next authorized stage without waiting for another year or D.

### Full-D-complete

All predeclared D/year slices reconcile exactly to the frozen full-D population manifest. Only then may full-D population reporting be treated as complete.

## 9. Strict reconciliation

At each aggregation level, the reconciler must prove that the union of child receipts equals the frozen parent population manifest exactly.

Required invariants:

- no duplicate instance;
- no missing eligible instance;
- no cross-split contamination;
- no chronology inversion;
- no mixed commit/ruleset/model/source identity;
- no mutated earlier probability or lock record;
- total preserved counts reconcile exactly;
- every exclusion is predeclared or explicitly retained as a technical/integrity record;
- raw chunk artifacts remain immutable after receipt creation.

If reconciliation fails, that pilot/D-year/full-D scope is `NOT_COMPLETE` even if every worker exited successfully.

## 10. Pipeline scheduling rule

The orchestration goal is a staggered pipeline rather than an all-or-nothing batch.

Near-term sequence:

1. finish mechanical/prelaunch builds;
2. create one small sealed pilot for the exact candidate when launch authority is available;
3. verify the pilot end to end;
4. move immediately to the next unresolved build/gate rather than launching every D in full;
5. repeat targeted pilots only where a distinct D/adapter/path needs verification;
6. save full year slices and especially full multi-year D runs for the final empirical phase.

When the final empirical phase begins, completed `D × year` slices may flow downstream while other slices execute. Do not create artificial serial dependencies merely for workflow convenience. Do not remove real causal or validation dependencies merely for speed.

## 11. Tighter blind/reveal and change-control rules

For each pilot or larger run:

- exact candidate commit and run manifest freeze before dispatch;
- blind prediction artifacts become append-only/immutable at creation;
- target/reveal information remains unavailable to the predictor until the blind ledger is sealed;
- runner and adjudicator identities remain distinct where required by the unified audit;
- results never authorize in-place model edits during an active instance/run;
- any accepted research candidate applies only to later instances under a new snapshot/version;
- rejected candidates and negative/inconclusive findings remain durable evidence;
- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains binding.

## 12. Runtime-size policy

The system must prefer small, resumable units over hours-long jobs.

Chunk and pilot sizes are preflight engineering parameters, not empirical tuning knobs. They may be chosen from observed execution cost/runtime on non-result-bearing preflight work, then frozen before result-bearing execution. They must not be changed after inspecting prediction quality or truth outcomes.

The objective is bounded failure domain, prompt receipts, resumability, early downstream work and exact evidence preservation.

## 13. Sparse-stage rule remains unchanged

D4 and D5 remain case-study evidence until support materially changes. Faster/smaller execution does not upgrade their evidentiary status. No D4/D5 result may manufacture population calibration or a universal deep-chain law.

## 14. Launch boundary

This protocol is **preparation only**.

It does not authorize V4 empirical dispatch. The current handoff still requires a separate explicit user authorization naming the exact candidate commit/workflow/ruleset after all required prelaunch gates are mechanically green. Full D/year and full multi-year D runs remain intentionally deferred until the final empirical phase.
