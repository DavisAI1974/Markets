# NG Exhaustion V4 — Per-D Chunked Run Protocol — 2026-08-20

Status: **BINDING ADDITIVE RUN-ORCHESTRATION PROTOCOL. NO V4 EMPIRICAL LAUNCH IS AUTHORIZED BY THIS DOCUMENT.**

This protocol records the user's 2026-08-20 instruction that future D-series runs must use a tighter protocol and be broken into smaller units so completed work can advance without waiting for one hours-long D0-D5 monolith.

It is additive to:

- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`;
- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`;
- `research/kalshi/FRANKIE_NEXT_CHAT_HANDOFF_CURRENT_20260820.md`;
- the unified-framework audit and all protected-boundary rules.

Nothing here weakens causal, blind/reveal, provenance, retention, sparse-stage, rollback, or launch gates.

## 1. One D per top-level empirical run

D0, D1, D2, D3, D4 and D5 must not be dispatched as one monolithic empirical workflow.

Each depth target gets a distinct top-level run identity and durable receipt:

- `D0_TERMINALITY`;
- `D1_CONTINUATION`;
- `D2_CONTINUATION`;
- `D3_CONTINUATION`;
- `D4_CASE`;
- `D5_CASE`.

A completed D is allowed to move immediately into its already-authorized downstream validation/adjudication/gap-decomposition step without waiting for unrelated D runs to finish. Completion of one D does not imply completion, validation, or promotion of another D.

No cross-D voting is introduced. No D may borrow a later D's result to revise an earlier frozen prediction ledger.

## 2. Chronological chunks inside each D

Each D must itself be partitioned into bounded chronological chunks before dispatch whenever its runtime or population is large enough to make a single job slow or fragile.

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
- silently changing model/ruleset/snapshot within one logical D run.

## 3. Pre-dispatch sealed run manifest

Every D run must have an immutable manifest frozen before dispatch containing at minimum:

- `run_id`;
- `depth_target`;
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

## 4. Chunk execution contract

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

## 5. Incremental progress without premature claims

Two different progress levels are allowed and must not be confused:

### Chunk-complete

A completed chunk may immediately enter integrity QA, provenance QA and failure/gap decomposition. This is operational progress only. Population performance claims for the full D remain provisional until the predeclared required chunk set for that D is complete.

### D-complete

Once all required chunks for a D are complete and reconcile exactly to its frozen population manifest, that D may immediately enter its next authorized stage without waiting for D0-D5 as a group.

Examples of next stages include:

- blind-output sealing;
- independent adjudication/reveal;
- retention accounting;
- calibration/selective-risk analysis;
- model/channel/gap decomposition;
- proposal generation for a later research candidate.

Those stages remain subject to their own authority gates. D completion alone does not authorize permanent Frankie mutation, V4 promotion, trade promotion, or live deployment.

## 6. Strict reconciliation before a D is complete

The D-level reconciler must prove that the union of chunk receipts equals the frozen D population manifest exactly.

Required invariants:

- no duplicate instance across chunks;
- no missing eligible instance;
- no cross-split contamination;
- no chronology inversion;
- no mixed commit/ruleset/model/source identity;
- no mutated earlier probability or lock record;
- total preserved counts reconcile exactly;
- every exclusion is predeclared or explicitly retained as a technical/integrity record;
- raw chunk artifacts remain immutable after receipt creation.

If reconciliation fails, the D is `NOT_COMPLETE` even if every worker job exited successfully.

## 7. Pipeline scheduling rule

The orchestration goal is a staggered pipeline rather than an all-or-nothing batch.

Permitted example:

1. D0 chunks execute.
2. As soon as D0 fully reconciles, D0 adjudication/gap work begins.
3. D1 execution can already be underway independently.
4. D2 may start when its own exact prerequisites and authorization are satisfied; it need not wait for D0/D1 downstream analysis unless the binding causal contract explicitly makes that dependency necessary.
5. The same pattern continues through D3.
6. D4/D5 remain preserved case-study lanes and may complete early or late without gating population claims for D0-D3.

Do not create an artificial serial dependency merely for workflow convenience. Do not remove a real causal or validation dependency merely for speed.

## 8. Tighter blind/reveal and change-control rules

For each D:

- exact candidate commit and run manifest freeze before dispatch;
- blind prediction artifacts become append-only/immutable at creation;
- target/reveal information remains unavailable to the predictor until the blind ledger is sealed;
- runner and adjudicator identities remain distinct where required by the unified audit;
- results never authorize in-place model edits during an active instance/run;
- any accepted research candidate applies only to later causal instances under a new snapshot/version;
- rejected candidates and negative/inconclusive findings remain durable evidence;
- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains binding.

## 9. Runtime-size policy

The system must prefer small, resumable units over hours-long single jobs.

Chunk size is a preflight engineering parameter, not an empirical tuning knob. It may be chosen from observed execution cost/runtime on non-result-bearing smoke/preflight work, then frozen before the empirical run. It must not be changed after inspecting prediction quality or truth outcomes.

The objective is:

- bounded failure domain;
- prompt receipt availability;
- resumability;
- faster downstream start for completed D targets;
- no loss of exact chronology or evidence integrity.

## 10. Sparse-stage rule remains unchanged

D4 and D5 remain case-study evidence until support materially changes. Faster/smaller execution does not upgrade their evidentiary status. No D4/D5 result may be used to manufacture population calibration or a universal deep-chain law.

## 11. Launch boundary

This protocol is **preparation only**.

It does not authorize V4 empirical dispatch. The current handoff still requires a separate explicit user authorization naming the exact candidate commit/workflow/ruleset after all required prelaunch gates are mechanically green.
