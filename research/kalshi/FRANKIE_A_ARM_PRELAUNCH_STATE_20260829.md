# Frankie A-Arm State and File Map

Date: 2026-08-29 UTC (revised at close)
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Status: **NOTHING LAUNCHED — CALCULATION LAYER BUILT — DRIVER IS A DRAFT — TWO DECISIONS OPEN**

This supersedes the first version of this file, which listed five decisions as open that
are now closed. It is both the state record and the file map: **nothing below should need
searching for, and nothing below should be rebuilt.**

No workflow has been dispatched, no model invoked, no lock, freeze, handoff or score taken.

---

## 1. The architecture correction that reframes the rest

**The Sol run is not an API run.** It works the way the group blind/refine walks worked: an
agent session reads committed files and emits committed artifacts. There is no provider
call.

Consequences, because most of the A-arm papers were written assuming an API:

- The papers say three times that a valid run requires a **provider-originated** response
  (§2.1, §4 step 7, §12). That describes an API call and does not describe how the walk
  actually ran. It needs generalizing before it is used as an acceptance criterion.
- `validate_principal_execution` in the execution gate requires `provider`,
  `requested_model`, `served_model`, `principal_invocation_id` and reconciling token
  `usage`. None of these exist in an agent-session run.
- **The proof problem does not disappear, it changes shape.** In the walk, what proved a
  specialist ran was that it read a committed staged state and emitted a committed artifact
  at a known path in a known schema, which the coordinator consumed and hard-failed on if
  missing or malformed. That is a real execution record - file-based rather than
  provider-attested - and it is the model to build to.
- **D7 (cadence) mostly dissolves.** It was a blocker only under per-cutoff API calls
  against 4.26M groups. In the walk model a specialist reads a staged state and emits one
  forecast; cadence is the staging boundary.
- `native_replay_driver.py`'s `on_invoke` callback is shaped like "call the model here" and
  is probably the wrong abstraction for the walk shape, which is "stage a state file here,
  spawn later."

**Build to the walk machinery in section 5, not to the API design in the papers.**

---

## 2. Decisions — closed

| | Decision | Resolution |
|---|---|---|
| D1 | A-clean was not clean | **Closed.** The leak was far larger than the capsule: mission §5 was a per-day family census of the scored days, `ALWAYS_LOAD` for both arms. Family vocabulary kept, per-day counts removed. A-clean's capsule is now generated from a method-only source. |
| D2 | Arms differed three ways | **Closed.** A-clean retrieves nothing derived from the four scored days; A-memory keeps its prior-run artifacts because that is the treatment. The asymmetry is now the experiment. |
| D4 | Execution gate stale at 24 surfaces | **Closed at 97.** `SURFACE_IDS` is generated from the registry; `MANDATORY` (55) derives from the `CAUSAL_STREAM_REQUIRED` policy. Sealing now checks all 9 sealed layers instead of one representative. |
| D8 | Prior-memory package hash unreproducible | **Closed.** The data was never the problem - `REPOSITORY_RECEIPT_HASH` reproduces exactly. Identity is now a canonical hash over the sorted per-member manifest; the tar digest is transport provenance and gates nothing. |
| R7 | Manifest schema had no room for §5.1 fields | **Closed** by the roster migration; see D-roster below. |
| — | All four days scored | **Decided.** One role `SCORED_FINDINGS_DAY`; `roster_position` carries stream order. This forced D1 and D2 to resolve as they did. |
| — | Carried vocabulary is a ceiling | **Closed.** Phases, states and dispositions can now grow; depth never had a cap. |

## 3. Decisions — open

**D6. Session and phase boundaries. This is the blocker.**
`session_phase` is a caller-supplied string and nothing in the tree defines RTH/ETH/reopen
for October 2021 CME. Section 2 says session boundaries start new continuity segments, and
segments decide where lifecycles are censored, where runs restart and where replenishment
horizons are cut. The driver cannot be finished without a rule. A workable starting
proposal: the 21:00 UTC boundary the data already exhibits is the session anchor, and
everything between two anchors is one segment. That is a proposal, not a decision.

**D5. Clustering mode.** Softer than first stated: the runner takes discovery as optional,
so if the A arms do not cluster the gate skips it. Only a decision if you want clustering in
this run. `mode` is `INCREMENTAL` or `RETROSPECTIVE`, hash-bound into the schema.

**D7. Cadence.** Mostly dissolved by section 1. What remains: at which staging boundary
does Sol read and emit.

## 4. Parked by decision (not blockers for Sol)

- **D3 / `ALLOWED_BOSSES`.** `EXPECTED_MODEL = "gpt-5.6-sol"` is a single-value constant
  enforced in three places. Sol *is* that value, so nothing blocks the Sol run.
- **Native-build execution for B0/B1/B2.** Nothing in the repo anticipates non-API,
  non-agent execution: no weights, checkpoint, torch, vllm or transformers references
  anywhere in the Frankie runtime. When it matters, `validate_principal_execution` will need
  more than one proof mode - the registry already uses a `proof_mode` vocabulary that never
  reached the execution gate.
- **A-memory prior-run reports** still cite the pre-fix package hashes in their prose. They
  are records of what was true when written, not live inputs.

---

## 5. File map — the walk machinery (BUILD TO THIS)

The templates the Sol run should follow, because this is what ran 24 group cycles.

| Path | What it is |
|---|---|
| `research/kalshi/agents/RUN_SOP.md` | **The spec book.** 895 lines. Verbatim spawn templates, slots by lookup, nothing runs off-SOP. |
| `research/kalshi/agents/README.md` | Agent handbook for the 5-specialist era. |
| `research/kalshi/spawn.py` | Fills every SOP slot **by lookup**. `slots(gid, day, spec)`, `day_inventory`, `cal_facts`, `mission_brief`. This is the template mechanism. |
| `research/kalshi/stage_group.py` | One-command staging so a group is completely ready. |
| `research/kalshi/forecast_harness.py` | The decision-state builder the specialists read. |
| `research/kalshi/agents/mbo_refine_shared.md` | Shared specialist rules, blind and refine both. |
| `research/kalshi/agents/mbo_specialist_{A..E}.md` | The five canonical specialist files. |
| `research/kalshi/agents/refine.md`, `state_auditor.md`, `failure_judge.md` | The other canonical roles. |
| `research/kalshi/agents/refine_gold_s105/` | The frozen gold vault (chmod 0444 + sha256 manifest). |
| `research/kalshi/agents/QC_CHECKLIST.md` | Small-model, report-only QC. |

## 6. File map — A-arm governing inputs (model-visible)

| Path | Role |
|---|---|
| `agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md` | RT mission. `ALWAYS_LOAD` both arms. Now carries the 16-section calculation surface (§5) and the open-world doctrine (§6). |
| `agents/frankie_native_raw_mbo_calculation_contract_20260828.md` | The 16 sections, 7 artifact layers, 8 acceptance gates. `ALWAYS_LOAD` both arms. |
| `agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md` | Forecaster directive. `ALWAYS_LOAD` both arms. |
| `agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json` | **The spec.** Edit this, then run the refresh - never hand-edit a capsule. |
| `agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json` | **Generated.** Hash-bound artifacts, profiles, external bindings. |
| `agents/frankie_native_raw_mbo_knowledge/A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md` | Generated. Method-only. |
| `agents/frankie_native_raw_mbo_knowledge/A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md` | Generated. Carries prior-run knowledge; that is the treatment. |
| `frankie_raw_mbo_benchmark/ACLEAN_METHOD_ONLY_CAPSULE_SOURCE_20260829.md` | The registered source A-clean's capsule is generated from. |
| `agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` | 105 entries = 97 concrete layers + 8 arm/control bindings. 90 is the declared floor. |

**To regenerate the capsules and manifest after editing the spec:**

```
python3 research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \
  --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \
  --repo-root . --write
```

Use `--check` instead of `--write` to verify without changing anything. The tool enforces
three integrity rules that each caught a real error this session: every capsule source must
be a registered artifact, no managed glob may claim an unregistered file, and a profile may
not list an artifact whose arms exclude that profile's arm.

## 7. File map — the calculation layer (BUILT, TESTED, NOT WIRED)

All under `research/kalshi/frankie_raw_mbo_benchmark/`. **441 tests pass.**

| § | Module | Lines | What it enforces that prose could not |
|---|---|---:|---|
| §3 | `native_stratum.py` | 391 | Pooling is a key collision. Declarations mandatory. Max never approximated. |
| 4.5 | `native_clocks.py` | 310 | First lawful availability is F_LAST receive. Unclosed group refused. |
| 4.6 | `native_queue.py` | 485 | Two FIFO identities self-check. Kaplan-Meier with at-risk counts. |
| 4.7 | `native_replenishment.py` | 422 | Deferred emission. Never-restored distinct from not-yet-observed. |
| 4.8 | `native_absorption.py` | 325 | Traded vs withdrawn depletion never pooled. Discovered dispositions. |
| 4.9 | `native_ladder.py` | 366 | Absolute depth and relative imbalance separate. Births as set differences. |
| 4.10 | `native_exhaustion.py` | 529 | Phase in the stratum key. Completed duration raises before completion. |
| 4.11 | `native_recognition.py` | 292 | No method returns a bare detection-time mean; a test asserts none exists. |
| 4.12 | `native_dipole.py` | 317 | Direction from sign only. SAME/FLIP never pool. |
| 4.13 | `native_lineage.py` | 324 | Depth unbounded, reported as a distribution never a mean. |
| 4.14 | `native_recurrence.py` | 328 | Exact gaps canonical; a burst threshold labels, never gates. |
| 4.15 | `native_discovery.py` | 398 | Forbidden features raise at schema construction. Frozen before description. |
| 4.16 | `native_response.py` | 369 | Each horizon written once, with its own at-risk denominator. |
| §5/§6 | `native_calculation_runner.py` | 519 | Seven layers, eight gates, no partial promotion. |
| — | `periodic_checkpointer.py` | 380 | Save points on record or clock interval, refused mid-group. |
| — | `native_replay_driver.py` | 305 | **DRAFT. Untested, nothing calls it.** See section 8. |

Sections 4.1-4.4 already existed in `a_memory_member_first_recalculation_20260828.py`, which
ran the full roster: 5,667,689 records into 4,256,603 groups, 4,758 candidate families, in
2,985s, with `daily_averaged_companion_verification: EXACT_MATCH`.

Tests are one file per module under `frankie_raw_mbo_benchmark/tests/`, plus
`test_open_world_growth.py` (the vocabulary must grow) and
`test_raw_mbo_source_manifest_roles.py` (roster and hash split).

## 8. What is NOT wired — the remaining build

Verified by search: the execution gate is referenced by nothing but itself, the
checkpointer by nothing, and no driver feeds the sixteen sections.

1. **The driver.** `native_replay_driver.py` is a draft: it imports and breaks no tests, but
   has no tests of its own, feeds only clocks and coverage, and its invocation abstraction
   assumes an API call. Rebuild its spawn path against section 5's walk machinery.
2. **Wire the checkpointer** into the driver and both launch workflows.
3. **Wire the gate** into the launcher. An unreferenced gate is not a gate.

## 9. Identity values — do not re-derive, do not guess

| Value | Where pinned |
|---|---|
| `source_identity_hash` `4d02dae63163a43fe0dc093ad0bda9a6d055a455cbc946a59d5b9008dad190ac` | `a_memory_prepare_20260828.py`, A-memory workflow. Constant across runs. |
| `MEMBER_MANIFEST_SHA256` `b487acfbbea8ac8a82f42ceb555e8334057e4004740af91b9127cd2ba71e1cf8` | `a_memory_prepare_20260828.py`. Replaces the unreproducible tar digest. |
| `PROOF_RECEIPT_HASH` `d54c61915c0d85c8b2630eb79d5e1b8911481c80883c56d75ba815fcfab20c05` | `a_memory_prepare_20260828.py`, `a_memory_rt_resume_20260828.py`, KNOWLEDGE_SOURCES. |
| `REPOSITORY_RECEIPT_HASH` `9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b` | Unchanged. Reproduces exactly - this is what proved the package data intact. |
| Source S3 prefix | `s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101` |
| Roster | 20211001 / 20211003 / 20211004 / 20211005, 5,667,689 records total |

The superseded `0a5cddb…` and `e7d8cbc…` remain in historical handoffs and prior-run
reports **on purpose**: those are records of what was true when written.

## 10. Standing constraints

- Workflow timeouts are 350 minutes. GitHub-hosted jobs are hard-capped at 360 regardless,
  which is why save points matter more than the timeout.
- AWS credentials are in GitHub secrets; the run path is Actions to S3, not a local session.
- Seven failures in the wider `research/kalshi/tests` suite are **pre-existing** - verified
  by running that suite at `d5b7b51`, the pre-session tip, where the same seven fail.
- `research/kalshi/FRANKIE_A_ARM_REVIEW_FINDINGS_20260829.md` is the original external review
  and is deliberately unedited, including its now-fixed findings.
