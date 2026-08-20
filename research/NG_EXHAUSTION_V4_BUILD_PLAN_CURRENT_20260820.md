# NG Exhaustion V4 — Current Build Plan — 2026-08-20

Status: **CURRENT IMPLEMENTATION PLAN. BUILD/PREPARATION AUTHORIZED. NO V4 EMPIRICAL LAUNCH, PERMANENT FRANKIE MUTATION, OR PROTECTED-ARTIFACT MUTATION IS AUTHORIZED BY THIS FILE.**

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/ng-exhaustion-entry-timing-revival-20260818`

This plan consolidates the clean-source gap work, planning-agent outputs, completed isolated builds, five-year MBO acquisition, and the user's latest pilot-first execution protocol. It is additive to the current proposal, clean-source gates, unified-framework audit, P0 boundary and protected-artifact rules.

Companion run protocol:

- `research/NG_EXHAUSTION_V4_PER_D_CHUNKED_RUN_PROTOCOL_20260820.md`
- `research/NG_EXHAUSTION_V4_PER_D_CHUNKED_RUN_PROTOCOL_20260820.json`

## 1. Current objective

Finish the remaining V4 engineering and provenance machinery first. Use only small frozen verification samples when a result-bearing pilot is later explicitly authorized. Do **not** start full D0-D5, full-year, or full-multi-year empirical runs now. Save the large runs for the final empirical phase.

The execution hierarchy is:

`mechanical builds -> exact candidate freeze -> small frozen pilot -> targeted D/year slice only if needed -> additional bounded slices -> full D/year reconciliation -> full multi-year D runs LAST`

The pilot verifies the pipeline, not predictive superiority or trade edge.

## 2. Work already built / mechanically green

### 2.1 Causal discovery / event-known-by boundary

Built in isolated V4 modules without modifying the frozen detector or frozen runway.

The mechanical suite previously reached **30/30 green tests** on the exact causal-entry candidate `2a95ab21dda9080c765248a3c0bdfe50127a52ad`.

Mechanically covered:

- causal `event_known_by` / detector-mark receipt;
- retrospective canonical `t0` kept separate;
- receive-order availability;
- no backdating of V4 evaluation to retrospective `t0`;
- isolated bridge to the frozen runway only after causal discovery;
- deterministic receipt/identity checks.

This is mechanical closure only; it is not an empirical receipt.

### 2.2 Unified V4 runtime contract

Built as one registry / one engine / one reconciler with target-specific adapters only.

The unified adversarial suite reached **11/11 green tests** after a mutable-registry defect was found and corrected.

Mechanically covered:

- immutable lane registration/identity;
- one shared execution contract;
- D4/D5 through the same engine in `CASE_STUDY_NO_ADAPTATION`;
- POX/posthoc oracle-conditioned lane permanently non-promotable;
- probability/lock identity binding;
- sealed execution handoff;
- reveal embargo;
- recomputed reconciliation / tamper rejection.

### 2.3 Missingness-safe causal state assembler

Receipt:

`research/kalshi/NG_EXHAUSTION_V4_STATE_ASSEMBLER_RECEIPT_20260820.json`

Exact runner commit:

`654fc2c0fc9e4e79f70e545e7fe59d92f70d9e67`

Result: **7/7 green tests**.

Mechanically proven:

- true numerical zero is distinct from missing;
- `OBSERVED`, `PAST_CARRY`, `STALE`, `MISSING`, `STRUCTURALLY_NOT_YET_KNOWN`, and `NOT_APPLICABLE` are distinct;
- future observations cannot backfill an earlier frozen second;
- frozen state movie is append-only/immutable.

### 2.4 Run-orchestration protocol

The binding per-D/per-year/pilot-first protocol is written in the companion files listed above.

It requires:

- one D per top-level run;
- optional predeclared year partitions;
- bounded chronological chunks;
- small frozen pilot before a large D/year run;
- exact manifest/receipt hashes;
- resumability at failed-chunk scope;
- strict union/reconciliation invariants;
- completed D/year work may move downstream without waiting for unrelated runs;
- full multi-year D runs are last.

## 3. Five-year historical MBO acquisition — active data work

Historical acquisition has been approved and submitted separately from live entitlement.

Target:

- Databento dataset: `GLBX.MDP3`
- schema: `mbo`
- requested continuous symbol: `NG.v.0`
- range: `2021-08-20` through `2026-08-20`
- canonical store: native Databento `.dbn.zst`
- S3 prefix: `nymex/ng_mbo_5y_v0/`

Account-specific clean five-year quote: approximately **$145.74**. Early resume-key migration created a small number of duplicate/overlapping jobs; those are preserved/accounted rather than hidden.

Latest compact audit:

`research/kalshi/NG_MBO_5Y_COMPACT_AUDIT_20260820.json`

Current durable facts from that audit:

- consolidation state: `COMPLETE`;
- expected canonical intervals: 61;
- intervals with canonical Databento jobs: 61;
- missing expected intervals: 0;
- unresolved reservations: 0;
- native DBN objects already present: 102;
- native bytes already present: 1,470,112,040;
- canonical intervals with complete final manifest at that snapshot: 1;
- exact duplicate expected intervals: 3;
- estimated exact-duplicate quote overhead: about $4.40;
- four additional partial-August overlapping intervals are retained for accounting/provenance;
- `safe_to_cancel_databento = false`.

**Do not cancel Databento until every intended canonical interval is drained to S3, native hashes/manifests are independently verified, exact contract/roll coverage is built, and the cancellation audit flips safe.**

## 4. Remaining build sequence — do this before large empirical work

### Build A — pilot manifest / D-year-chunk guardrail

Implement one immutable run-manifest/reconciliation layer that mechanically enforces the new protocol.

Required:

- `run_scope` in `PILOT | D_YEAR_SLICE | FULL_D_MULTIYEAR`;
- one `depth_target` only;
- explicit year/date span;
- exact candidate/engine/adapter/reconciler/ruleset/model/snapshot/source hashes;
- frozen pilot-selection identity;
- frozen chunk membership;
- split/reveal/lock/channel identities;
- fail closed unless exact user launch authorization matches candidate commit + workflow + ruleset;
- exact parent/child reconciliation with no missing/duplicate instances.

The near-term build may test this contract synthetically. Do not dispatch a result-bearing D pilot merely to test the manifest code.

### Build B — five-year source/contract/roll/coverage manifest

Finish draining the purchased MBO jobs and create exact per-session coverage/provenance.

For every covered session bind at minimum:

- dataset/publisher/schema;
- requested continuous symbol;
- continuous-series rule;
- resolved raw symbol/contract;
- instrument ID;
- effective definition interval;
- source DBN object and SHA-256;
- source timestamp/message range;
- transform/builder revision;
- MBO channel availability status.

`NG.v.0`, `NG.n.0`, `NG.c.0` or any other basis may never be silently substituted.

### Build C — actual adapter integration of clocks/state/lifecycle/ledger

The underlying contracts exist; finish the real isolated V4 adapter/orchestrator wiring so one causal case can flow through:

`event_known_by -> source availability -> immutable state movie -> unresolved predecessor lifecycle -> probability movie -> independently recomputed first-lock/no-lock -> sealed handoff -> reveal wall -> reconciler`

The frozen detector/runway remain untouched.

### Build D — detector-intensity semantic resolution

Before any field is called detector/native exhaustion intensity:

1. prove a frozen causal detector-native per-second stream with revision + lawful availability; or
2. omit that name and use an explicitly named V4 proxy such as polarity-oriented roll-20/dipole trajectory.

No retrospective endpoint milestones may be interpolated into a fake native continuous intensity.

### Build E — exact nine-gate integration verifier / red-team

Recompute every clean-source gate from typed artifacts. Do not accept self-reported booleans.

Required red-team checks include:

- causal clock substitution;
- multi-clock premature availability;
- source/roll substitution;
- missingness backfill;
- future-descendant lifecycle leakage;
- proxy/native intensity confusion;
- probability/lock mutation;
- execution re-prediction/re-timing;
- alternate D4/D5 engine;
- registry/reconciler tampering.

A mechanically green nine-gate receipt still does **not** authorize empirical launch or satisfy P0 empirical readiness.

### Build F — full engineering regression / exact candidate freeze

On one exact candidate commit:

- focused V4 tests;
- unified runtime tests;
- causal-state tests;
- pilot-manifest/reconciliation tests;
- full applicable Frankie suite;
- selftest;
- registry/invariant checks;
- protected-artifact hash comparison;
- exact candidate/workflow/ruleset receipt.

Only after this is a candidate eligible for a tiny result-bearing pilot, and that pilot still requires a separate exact launch authorization.

## 5. Pilot policy — next empirical work is intentionally tiny

When all mechanics relevant to the pilot are green and the user explicitly authorizes the exact candidate/workflow/ruleset:

- choose a deliberately small, predeclared, non-output-dependent sample;
- do not consume the virgin/release holdout;
- run one D only;
- bind one year/date span only;
- use small chronological chunks;
- seal blind artifacts before reveal;
- verify restart/resume and exact reconciliation;
- inspect integrity/provenance first;
- if the pipeline is verified, move to the next unresolved build/check rather than launching all D runs.

Allowed pilot conclusion:

`PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE`

Forbidden pilot conclusions:

- model superiority;
- calibration adequacy;
- universal D timing/geometry law;
- trade edge;
- permanent Frankie readiness;
- population D4/D5 validation.

## 6. Full empirical phase — LAST

The large runs are deliberately deferred.

When eventually authorized:

- D0, D1, D2, D3, D4, D5 remain separate top-level runs;
- split each D by predeclared year/date span;
- split each D/year into bounded chronological chunks;
- completed D/year slices may enter downstream integrity/adjudication work immediately;
- do not wait for all D0-D5 to finish before progressing completed work;
- full-D claims require exact reconciliation across all predeclared year slices;
- preserve every negative, weak, losing, censored, no-lock, wrong-lock, missing-channel and model-disagreement case;
- D4/D5 remain case-study lanes unless materially larger lawful support plus separate adjudication changes that status.

## 7. P0 empirical evidence — plan complete, real execution still gated

The P0 planning lane is complete but correctly remains externally blocked until real dependencies exist.

Six real receipts remain:

1. untouched held-out paired performance;
2. calibration / selective risk;
3. planted-null contamination;
4. complete protected retention matrix;
5. evaluator-independence canary;
6. non-vacuous byte-exact live rollback.

Before execution, bind one immutable evaluation-plan identity across candidate, baseline, runner, independent evaluator, partitions, controls, budgets, seeds, policies and all six validators.

Do not consume the release holdout during development/pilot work.

External dependencies include:

- real model/tool callbacks with metering authority;
- independent locked evaluator + canaries;
- disposable authorized mutation/rollback target.

Synthetic/unit tests do not satisfy these six receipts.

## 8. Live MBO — viable choices exist; final certification deferred until needed

The current Databento Standard live key remains trades-only for this use case; `mbp-10` and `mbo` were not authorized. The user's relevant Databento live benchmark is approximately $1,799/month.

Current viable lower-cost live candidates identified in public research:

- DTN/IQFeed — leading low-cost candidate, final exact order-field/licensing/non-display certification still required;
- Rithmic — technically strong MBO candidate, final data-only/API/access/licensing price still required;
- dxFeed — strong order-level API semantics, custom Frankie/API commercial price still required;
- CME Smart Stream SBE — robust direct fallback;
- Databento — expensive fallback.

Historical and live providers do not need to be the same company. Final live-provider certification can wait until live MBO is actually needed.

## 9. Planning-agent disposition

Five planning lanes were defined:

- `causal_clock` — BUILD_READY and substantially built;
- `v4_mechanics` — BUILD_READY and substantially built;
- `history_support` — BUILD_READY and active through the five-year MBO acquisition/provenance work;
- `integration_redteam` — BUILD_READY and partially built;
- `p0_evidence` — PLAN_COMPLETE but not BUILD_READY for real execution until external dependencies exist.

Do not restart another generic research cycle. Convert remaining concrete BUILD_READY items into isolated code/tests/receipts in the dependency order above.

## 10. Protected boundaries

Do not modify or retune without explicit authorization:

- frozen exhaustion detector;
- frozen canonical evidence/rows;
- finalized Phase-1/Phase-2 findings;
- frozen exhaustion runway clock;
- permanent Frankie / Frankie 1;
- `research/kalshi/spawn.py`;
- frozen V3 benchmark artifacts;
- other explicitly protected play/workflow artifacts.

The preservation policy remains:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

No chain/case disappears because a result is negative, weak, losing, censored, sparse or inconvenient.

## 11. Exact next-chat build order

1. Read the current handoff, this build plan, and the per-D/per-year/pilot-first protocol first.
2. Verify the current pushed branch state and do not redo completed mechanical work.
3. Finish Build A: pilot manifest / D-year-chunk guardrail and its adversarial tests.
4. In parallel continue Build B: drain/verify the already-purchased five-year MBO archive and build exact coverage/provenance.
5. Finish Builds C-D: actual isolated adapter integration and detector-intensity semantic resolution.
6. Finish Build E: recomputed nine-gate verifier/red-team.
7. Finish Build F: full engineering regression and freeze one exact candidate.
8. Stop before any result-bearing V4 pilot unless the user separately authorizes the exact candidate commit/workflow/ruleset.
9. If/when a pilot is authorized, use only a tiny non-release sample, one D and one year/date span at a time.
10. Save all full D/year and full multi-year empirical runs for the last phase.
11. Execute the six real P0 receipts only when their external dependencies and protected evaluation partitions are ready.

