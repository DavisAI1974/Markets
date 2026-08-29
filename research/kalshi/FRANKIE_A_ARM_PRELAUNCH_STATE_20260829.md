# Frankie A-Arm State and File Map

Date: 2026-08-29 UTC (revised at close; D6a/D5 taken 2026-08-29 in session, see sections 2 and 3)
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Status: **NOTHING LAUNCHED — CALCULATION LAYER BUILT — DRIVER IS A DRAFT — D6 AND D5 CLOSED, NO DECISION BLOCKS THE BUILD**

> **STOP BEFORE LAUNCH.** Do not dispatch a workflow or start either arm. Walk the whole
> thing through with Greg first. See section 0.

This supersedes the first version of this file, which listed five decisions as open that
are now closed. It is both the state record and the file map: **nothing below should need
searching for, and nothing below should be rebuilt.**

No workflow has been dispatched, no model invoked, no lock, freeze, handoff or score taken.

---

## 0. STOP BEFORE LAUNCH — read this first

**Do not dispatch a workflow, invoke a model, or start either arm. Stop and walk the whole
thing through with Greg first.**

This is not a formality and it is not about permission. Two decisions below are unmade
(D6 and D5), the driver is a draft that has never run, three components are wired to
nothing, and the papers still describe an API architecture the Sol run does not use. A
launch from this state would produce artifacts that look complete and are not.

Before anything runs, sit down with Greg and confirm, item by item:

1. **D6 session boundaries AND phase: DONE.** Both decided and implemented in
   `native_session.py` (41 tests). Every boundary is taken from the exchange and cited in
   the module docstring; see D51 in the root `DECISIONS.md` for the rule behind it.
2. **D5 clustering: DONE.** Not in this run; the runner takes discovery as optional and the
   gate skips it.
3. **The driver is rebuilt against the walk machinery** in section 5, not against the API
   design in the papers, and it has tests.
4. **The checkpointer and the execution gate are actually wired.** Verify by search, not by
   assumption: today both are referenced by nothing.
5. **The provider-receipt requirement is reconciled** with an agent-session run - both in
   the papers and in `validate_principal_execution`.
6. **The helper path is built as a tool available to RT and Forecaster**, not as four live
   roles, and the ingestion paper's Question 3 is updated to say so.
7. **Every section from 4.6 to 4.16 is fed by the traversal.** Today only clocks and
   coverage are.
8. **Compute is settled** - which machine runs this, and whether it is sized for sixteen
   sections over 4.26M groups. See section 10a: the A-arm workflows currently dispatch
   nothing, and the recorded box is a t3.xlarge (4 vCPU / 16 GB), unverified.
9. **A dry run over a small slice completes and the eight gates pass**, before anything
   touches the full roster.

When you think you are ready, go back through this document from section 1 and confirm each
claim still holds. Several things in here were true when written and were made false by the
next decision - that is exactly how the first version of this file went stale.

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

**Two roles, no specialists, helpers are tools.**

The five-specialist structure (A-E) is **not** used for the A arms. There are exactly two
roles - `REAL_TIME_FRANKIE` and `FORECASTER_FRANKIE` - and the knowledge manifest already
carries only those two, with four profiles across the two arms. Nothing needs changing
there.

The four helper scouts are **not** live roles either. RT and Forecaster may **call an agent
helper from their tools**; a helper is a tool invocation inside a role, not a parallel lane
with its own knowledge profile or its own output. This answers open Question 3 in the
ingestion paper ("are those helpers active, shadow-only, or carried architecture?"), which
should be updated to say so.

The registry is already closer to right than the papers are: `helper_role_configuration`
holds its four entries as `STATIC_REQUIRED_INPUT` on a `DIRECT` route - configuration
delivered pre-call, not a separate execution lane. Those four are the entries that take 93
inventory layers to 97.

**Build to the walk machinery in section 5, not to the API design in the papers** - but take
the *staging and artifact contract* from it, not the five-specialist role structure.

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
| D6a | Session boundary undefined | **Closed 2026-08-29 (Greg).** Follow the exchange, not our tape. CME Globex energy trades Sun-Fri 17:00-16:00 CT with a 60-minute halt at 16:00 CT, Mon-Fri; the CME **trade date** begins 17:00 CT on the previous calendar day and runs to 16:00 CT. `continuity_segment` is the trade date's ordinal, because one trade date is exactly one continuous book. Built as `native_session.py`. |
| D6b | Session phase undefined | **Closed 2026-08-29 (Greg).** Derived from the same authority as D6a. The NYMEX Energy Futures Daily Settlement Procedure fixes the NG settlement window at **14:28:00-14:30:00 Eastern**; with the 16:00/17:00 CT session hours that carves the trade date into `PRE_OPEN`, `PRE_SETTLEMENT`, `SETTLEMENT`, `POST_SETTLEMENT`, `POST_CLOSE`. Settlement is resolved in **ET** and the session in **CT**, each in the zone the exchange states it in. `CARRIED_PHASES` is a starting vocabulary, never a validator. |
| D5 | Clustering mode | **Closed 2026-08-29 (Greg).** Not in this run. Discovery stays optional and the gate skips it; keep the first launch to the smallest thing that can succeed. |

## 3. Decisions — open

**No open decision blocks the build.** D6 and D5 closed on 2026-08-29; what remains is
wiring, section 8.

Two things settled along the way, recorded because they were live questions:

* `H6`'s pre-boundary / mass-withdrawal / post-boundary proposal was **not** implementable
  as written - viewed from the boundary that opens a segment every group is post-boundary,
  and from the one that closes it every group is pre-boundary, so the same interval carried
  both labels. Anchoring on the exchange's own instants instead of on a boundary's
  perspective dissolves it.
* An `in_halt_window` helper was written and then **removed under review**: it tested the
  local clock alone, so it read True at 16:30 CT on a Saturday while `session_phase` read
  `PRE_OPEN` for the same instant. Two fields in one output dict disagreeing about the same
  fact is the shape of the S109 `session_b_share` defect - both present, both plausible,
  silently incompatible. `session_phase == POST_CLOSE` is the single answer, and a test pins
  the weekend case.
* **`PRE_OPEN` appears only where the gap exceeds the daily halt** - weekends, and holidays
  once the calendar is wired. On a normal weekday the hour before a session opens is the
  PRIOR trade date's `POST_CLOSE`. A ~49h censoring gap and a 1h one are now
  distinguishable, which matters because segments decide where lifecycles are censored.

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
| `research/kalshi/agents/mbo_refine_shared.md` | Shared rules. **Reference for the artifact contract and staging discipline only** - the A arms do not use the specialist role structure. |
| `research/kalshi/agents/mbo_specialist_{A..E}.md` | The five walk specialists. **Not used by the A arms.** Read for how a role is briefed and what it must emit, not as roles to run. |
| `research/kalshi/agents/refine.md`, `state_auditor.md`, `failure_judge.md` | Other walk roles. Same caveat. |
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
| §2 | `native_session.py` | 270 | D6a+D6b. Boundaries exchange-local, so they survive DST. Segment is the CME trade date. Phase from the settlement window and session hours. Non-monotonic input refused. |
| §5/§6 | `native_calculation_runner.py` | 519 | Seven layers, eight gates, no partial promotion. |
| — | `periodic_checkpointer.py` | 380 | Save points on record or clock interval, refused mid-group. |
| — | `native_replay_driver.py` | 305 | **DRAFT. Untested, nothing calls it.** See section 8. |

Sections 4.1-4.4 already existed in `a_memory_member_first_recalculation_20260828.py`, which
ran the full roster: 5,667,689 records into 4,256,603 groups, 4,758 candidate families, in
2,985s, with `daily_averaged_companion_verification: EXACT_MATCH`.

**482 tests** as of 2026-08-29 (441 + 41 for `native_session`).

Tests are one file per module under `frankie_raw_mbo_benchmark/tests/`, plus
`test_open_world_growth.py` (the vocabulary must grow) and
`test_raw_mbo_source_manifest_roles.py` (roster and hash split).

## 8. What is NOT wired — the remaining build

Verified by search on 2026-08-29. The execution gate is referenced by nothing but itself
and its test. `native_replay_driver` is referenced by **no Python at all**. **Correction to
the previous version of this file:** `periodic_checkpointer` is *not* referenced by nothing
- `native_replay_driver.py` imports it. The conclusion is unchanged, since the driver never
runs, but the claim as written was wrong. No driver feeds the sixteen sections.

1. **The driver.** `native_replay_driver.py` is a draft: it imports and breaks no tests, but
   has no tests of its own, feeds only clocks and coverage, and its invocation abstraction
   assumes an API call. Rebuild its spawn path against section 5's walk machinery.
2. **Wire the checkpointer** into both launch workflows. It is already imported by the
   draft driver; what is missing is a path on which that driver executes.
3. **Wire the gate** into the launcher. An unreferenced gate is not a gate.
4. **Feed `continuity_segment`, `trade_day` and `session_phase` from `native_session`** into
   the traversal. Today every section still takes them as caller-supplied arguments, so the
   D6 rules are available but not yet applied anywhere. Until this is done a driver can
   still pass a constant phase and collapse the stratum silently - the tests guard the
   derivation, not its use.
5. **Wire an exchange holiday calendar.** `native_session` consults none. The roster spans
   no holiday so nothing is wrong today, but any wider window needs it.

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

---

## 10a. Compute — where the run would actually execute (UNRESOLVED)

Two findings, both worth settling before launch.

**The A-arm launch workflows never reach the AWS box.** Neither
`frankie_a_clean_rt_native_launch_20260828.yml` nor its A-memory twin contains a single
reference to `ssm`, `ec2`, `send-command` or `INSTANCE_ID`. Their steps are: checkout,
verify branch, install the DBN reader, fetch and hash-bind the roster, seal the packet and
the pre-call checkpoint, push to S3, publish, report. **They stage and stop.** No compute is
dispatched, no calculation runs, no model is called. By contrast the October fullstack
workflow does carry `INSTANCE_ID: i-08cee7171c0a76a04` and drives it over SSM.

So today there is no execution path at all - which compounds section 8: the driver is a
draft, the checkpointer and gate are wired to nothing, and the workflow that would carry
them dispatches nothing.

**The recorded box is smaller than assumed.** `LIVE_TELEMETRY_S100.md` records
`i-08cee7171c0a76a04` as a **t3.xlarge** in us-east-2, which is **4 vCPU / 16 GB** - not
8 CPU / 64 GB. `CLAUDE.md` refers to the same instance with 200 GB, which is disk, not RAM.
**This could not be verified live**: this session had no resolvable AWS credentials, so what
is stated here is what is written down. If the instance was resized, the record was not
updated, and the record is what the next session will believe.

Why it matters: the member-first recalculation covering 5 of 16 sections took 2,985s and
produced a 1.5 GB exact-members file. Sixteen sections over 4.26M groups on 16 GB is at
least worth sizing before it is attempted, and `ubuntu-latest` - which is what the A-arm
workflows currently use - is smaller again.

**A likely explanation for the four helper lanes.** A t3.xlarge has exactly 4 vCPUs and the
registry carries exactly 4 helper scouts. That is circumstantial, but it fits: the "four
live helpers" may be a parallelism artifact of the box rather than a research design. Since
helpers are now tools callable by RT and Forecaster rather than lanes, nothing depends on
the number four - and if anything still does, that is a bug rather than a design.

## 11. Where this session ended, and housekeeping

**Ended at:** the calculation layer complete and tested, the driver a draft, nothing wired,
nothing launched. Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`, working tree clean,
everything pushed.

**Test state, stated exactly.** 441 pass in
`research/kalshi/frankie_raw_mbo_benchmark/tests/`. Seven failures in the wider
`research/kalshi/tests/` suite are pre-existing and unrelated - verified by running that
suite at `d5b7b51`, the pre-session tip, where the same seven fail. Do not treat them as
regressions and do not "fix" them as part of this work without checking that history first.

**What was deliberately left alone.** The original review findings file, the historical
handoffs, and the A-memory prior-run reports all still carry superseded hashes and
superseded claims. They are records of what was true when written. Do not sweep them for
consistency - that would destroy the audit trail that shows what changed and why.

**The warmup-scoped capsule proposal** at
`agents/frankie_native_raw_mbo_knowledge/A_CLEAN_WARMUP_SCOPED_CAPSULE_PROPOSAL_20260829.md`
is superseded by the all-days-scored decision and is not registered in any manifest or
managed glob. It is kept as the record of that analysis. Do not wire it.

**Housekeeping before the next working session:**

- Re-read section 0 and this section before touching anything.
- Confirm the branch tip matches what is stated here; if it does not, something landed after
  this was written and this document is behind.
- Run the A-arm suite first. If it is not 441 green, stop and find out why before building.
- Run the knowledge refresh with `--check`. It should report `CURRENT`. If it reports
  `UPDATED`, someone hand-edited a generated capsule and that needs understanding, not
  overwriting.
- If you change any decision in section 2 or 3, **update this file in the same commit.**
  The first version of this document went stale because that did not happen.
