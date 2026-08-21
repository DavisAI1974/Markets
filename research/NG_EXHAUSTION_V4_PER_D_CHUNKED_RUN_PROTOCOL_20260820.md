# NG Exhaustion V4 — Per-D / Per-Year / Pilot-First Prediction Protocol — 2026-08-20

Status: **BINDING ADDITIVE PREDICTION-RUN PROTOCOL. NO V4 EMPIRICAL LAUNCH IS AUTHORIZED BY THIS DOCUMENT.**

This file supersedes the ambiguous interpretation of the earlier version of this same protocol. It does **not** supersede frozen historical Phase-1/Phase-2 findings.

## 0. Scope boundary — Step-1 census comes first

This protocol governs **later blind/result-bearing V4 prediction/testing after a structural population has been constructed and frozen**.

It does **not** govern the initial expanded structural census that discovers/freezes chain membership, ancestry, reset structure and realized depth.

The required high-level order is:

`verified expanded chronology`
`-> Step-1 structural census`
`-> frozen population / realized depth registry`
`-> small V4 prediction pilots`
`-> D-specific/year-specific predictive runs`
`-> full empirical validation last`

Therefore the initial structural census is **not** required to choose `D0`, `D1`, `D2`, etc. before it runs. D membership/depth is an output of the frozen census and a target for later causal prediction.

Current Step-1 authority:

- `research/NG_EXHAUSTION_CHAIN_STEP1_ORIGINAL_FILE_MAP_20260820.md`
- `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.md`
- `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json`
- `research/NG_EXHAUSTION_V4_BUILD_PLAN_STEP1_ADDENDUM_20260820.md`

The structural census may itself be sharded by year/week/date span for runtime and restartability, but those are execution partitions only. All shards reconcile into one complete frozen census population per census view.

## 1. Pilot-first hierarchy for prediction runs

After Step 1 freezes the population, future result-bearing prediction work follows:

`small frozen verification sample -> D/year slice -> additional bounded slices -> full D/year reconciliation -> full multi-year D run LAST`

The first small sample verifies mechanics, causality, provenance, ledger integrity, reveal separation, artifact production, runtime behavior, restart/resume and reconciliation. It does not establish population performance.

Allowed pilot conclusion:

`PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE`

A pilot may not establish model superiority, calibration adequacy, universal D law, trade edge, permanent Frankie readiness or population D4/D5 validation.

## 2. One D per top-level predictive run

Only after Step 1:

- `D0_TERMINALITY`;
- `D1_CONTINUATION`;
- `D2_CONTINUATION`;
- `D3_CONTINUATION`;
- `D4_CASE`;
- `D5_CASE`.

D0-D5 must not be dispatched as one monolithic predictive workflow.

A completed D slice may move immediately into its already-authorized integrity/adjudication/gap-decomposition step without waiting for unrelated D runs. Completion of one D does not imply validation or promotion of another D.

No cross-D voting is introduced. No later-D result may rewrite an earlier frozen prediction ledger.

## 3. Year/date partitions are scheduling partitions

Within a D, chronology may be partitioned by predeclared calendar year or another contiguous date span and then into smaller chronological chunks.

Year/date slicing is for runtime, restartability, source-coverage accounting and faster downstream work. It may not alter model semantics, labels, split membership, feature availability, lock rules or acceptance criteria.

A completed `D x year` slice may enter integrity QA and gap decomposition immediately. Multi-year claims require predeclared reconciliation.

Year/date boundaries may not be changed after inspecting prediction quality or truth outcomes.

## 4. Small frozen verification sample before large prediction work

Before a full D/year predictive slice, create a small frozen pilot manifest from eligible chronology using a predeclared non-output-dependent selection rule.

The pilot must exercise, where applicable:

- causal `event_known_by` gating;
- multi-clock availability;
- source/contract/roll provenance;
- full V4 channel manifest including MBO availability;
- missing/stale/not-yet-known/true-zero semantics;
- predecessor lifecycle;
- probability movie and first-lock/no-lock ledger;
- sealed prediction-to-execution object generation without live execution;
- blind-ledger sealing before reveal;
- independent reveal/adjudication;
- chunk receipts;
- deterministic replay/hash checks;
- D/year reconciliation;
- failure/restart/resume.

Every selected negative, losing, censored, no-lock, wrong-lock, missing-channel and model-disagreement case remains preserved.

## 5. Chronological chunks inside each D/year predictive slice

Each D/year predictive slice should be broken into bounded chronological chunks whenever population/runtime warrants it.

Permitted boundaries are natural causal boundaries such as session/date/week or a fixed predeclared consecutive-session block. Chunk membership freezes before predictions are inspected.

Forbidden:

- output-dependent repartitioning;
- moving difficult cases after inspection;
- deleting inconvenient chunks/cases;
- future-truth label balancing;
- changing feature/channel availability by chunk;
- silently changing candidate/model/ruleset/source within a logical run.

## 6. Pre-dispatch sealed run manifest

Every predictive pilot or larger D/year run must freeze, at minimum:

- `run_id`;
- `run_scope` = `PILOT`, `D_YEAR_SLICE`, or `FULL_D_MULTIYEAR`;
- `population_registry_hash` from the frozen Step-1 census/crosswalk;
- `census_view_identity`;
- `depth_target`;
- `year_or_date_span`;
- exact candidate commit SHA;
- runner/adjudicator identities;
- ruleset/engine/adapter/reconciler hashes;
- model/snapshot/head identities;
- source/contract/roll/coverage manifest hash;
- population/split identities;
- pilot-selection identity;
- chunk list/hashes;
- discovery/OOT/held-out boundaries;
- channel/view manifest;
- reveal/lock rules;
- timeout/resource envelope;
- restart/resume policy;
- protected-boundary assertion;
- exact `v4_empirical_launch_authorized` receipt.

Fail closed if launch authorization does not match the exact candidate/workflow/ruleset.

## 7. Chunk receipts and restart

Each chunk gets stable `chunk_id` + frozen input manifest and must emit a durable receipt containing:

- input manifest hash;
- population registry/census view identity;
- first/last causal session/timestamp;
- eligible/processed/preserved counts;
- omissions with explicit reasons;
- model/snapshot/head/ruleset identities;
- source/provenance hash;
- probability ledger hash;
- first-lock/no-lock ledger hash;
- output artifact hashes;
- execution/integrity status;
- technical failure reason.

A technical failure retries/resumes only that exact chunk if identities are unchanged. Changed code/ruleset/source/model creates a new logical run identity.

## 8. Progress states

- **PILOT_COMPLETE**: pipeline integrity only; no population claim.
- **CHUNK_COMPLETE**: integrity/provenance QA may proceed; population claims provisional.
- **D_YEAR_COMPLETE**: all required chunks for one D/year reconcile; next authorized work may begin immediately.
- **FULL_D_COMPLETE**: all predeclared D/year slices reconcile exactly to the frozen full-D population.

## 9. Strict reconciliation

At every level prove child union equals frozen parent population exactly:

- no duplicate instance;
- no missing eligible instance;
- no cross-split contamination;
- no chronology inversion;
- no mixed commit/ruleset/model/source/census identity;
- no mutated earlier probability/lock record;
- exact preserved-count reconciliation;
- every exclusion accounted for;
- raw child artifacts immutable.

Reconciliation failure means `NOT_COMPLETE` even when workers exited successfully.

## 10. Blind/reveal and change control

For every predictive run:

- exact candidate + manifest freeze pre-dispatch;
- blind prediction artifacts append-only at creation;
- target/reveal unavailable to predictor until blind ledger sealed;
- runner/adjudicator separation where required;
- no in-place model edits mid-instance/mid-run;
- accepted changes apply only to later instances under a new snapshot/version;
- rejected/negative/inconclusive findings remain durable;
- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains binding.

## 11. Runtime-size policy

Prefer small resumable units over hours-long jobs. Pilot/chunk sizes are engineering preflight parameters, not empirical tuning knobs. Freeze them before result inspection.

Completed `D x year` slices may flow downstream while unrelated slices continue. Do not create artificial serial dependencies; do not remove real causal/validation dependencies for speed.

## 12. Sparse-stage rule

D4/D5 remain case-study evidence until lawful support materially changes and separate adjudication changes their status. Faster/smaller execution does not upgrade evidence.

## 13. Launch boundary

This protocol is preparation only.

A generic `Proceed` authorizes build/preparation work, not a result-bearing V4 prediction run. Result-bearing dispatch requires the separately established exact candidate/workflow/ruleset authorization.

Full D/year and full multi-year prediction runs remain intentionally deferred until the final empirical phase.
