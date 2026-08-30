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

This is not a formality and it is not about permission. **Re-verified 2026-08-29:** the
driver now RUNS a pass end to end and finalizes ACCEPTED (13 tests), and D6 and D5 are both
closed - those three lines were true when first written and are not now. **UPDATED 2026-08-30 (T1):
the driver now CALLS all four built adapters and 4.8, 4.9, 4.13 and 4.14 report on rows that
actually arrived** - `sections_fed` is emitted beside the measures, 12 new tests, package
suite 653 -> 665, wider suite still exactly 7 pre-existing failures. **UPDATED AGAIN
2026-08-30: the six that were still empty - 4.6, 4.7's observation half, 4.10, 4.11, 4.12
and 4.16 - are now fed too, and the execution gate is on the launch path.** Package suite
885. The sentence that was true when this paragraph was written, and is worth keeping
because it names the failure mode: a launch from the earlier state would have produced
artifacts that looked complete and were not, because a section reporting strata off an empty
ingest is indistinguishable from one reporting a real absence. That is why `sections_fed`
emits an ingest count per section rather than letting it be inferred from the measures.
**4.15 stays out of this run under D5 - excluded, not unfed.**

Before anything runs, sit down with Greg and confirm, item by item:

1. **D6 session boundaries AND phase: DONE.** Both decided and implemented in
   `native_session.py` (41 tests). Every boundary is taken from the exchange and cited in
   the module docstring; see D51 in the root `DECISIONS.md` for the rule behind it.
2. **D5 clustering: DONE.** Not in this run; the runner takes discovery as optional and the
   gate skips it.
3. **The driver is rebuilt against the walk machinery** in section 5, not against the API
   design in the papers, and it has tests.
4. **The checkpointer and the execution gate are actually wired.** Verify by search, not by
   assumption. **Re-checked 2026-08-29, and they are no longer in the same state:** the
   checkpointer IS imported by `native_replay_driver`, while the execution gate is still
   imported by nothing outside itself. Neither is on a LAUNCH path - the driver that holds
   the checkpointer is not dispatched by either workflow - so "wired to a module" and "wired
   to an execution path" must not be collapsed here.
5. **The provider-receipt requirement: DECIDED (Greg, 2026-08-29).** Verbatim: *"on invoke
   runs chatgpt 5.6 sol just like you used to run the blind/reveal for the group runs, no
   api call."* So `on_invoke` never calls anything. At a cutoff the driver STAGES a state
   file; Sol runs as an agent session that reads committed files and emits a committed
   artifact; the coordinator hard-fails on missing or malformed. `validate_principal_execution`'s
   provider / model-id / invocation-id / token-usage requirements must be generalized to
   that file contract. **BUILT 2026-08-29.**

   **WHY THIS KEPT COMING BACK, and it is now fixed.** Greg, this session: *"we're not
   using the openai api!!! we are running 5.6sol like you ran the blind/refine groups. i
   have said this every session."* The reason it needed saying every session is that **the
   execution gate still ENFORCED the API architecture.** `validate_principal_execution`
   required `provider`, `requested_model`, `served_model`, `principal_invocation_id` and
   reconciling token `usage` with a provider usage receipt. None of those exist in an
   agent-session run, so the gate would have **rejected a correct Sol run and accepted only
   an API one.** A decision recorded in prose while the check demands the opposite is a
   decision that has not landed - the same shape as the S114 do/dont rule that silently
   expired because it was never made a schema rule.

   It is now file-based, matching `native_staging.py`: a committed staged request at a
   known path and a committed artifact at a known path in the expected schema, both
   hash-bound. A request and artifact hashing identically is refused, because a run that
   returned its own input produced no findings. The lock and freeze gates moved with it
   (`principal_response_id` -> `principal_artifact_path`, `principal_output_sha256` ->
   `principal_findings_sha256`). **The token-usage test was REPLACED, not dropped**, and a
   new test pins that a provider-shaped record is now REFUSED, so the API shape cannot
   quietly return.

   **Audited for the rest of the surface:** the four MODEL-VISIBLE papers carry no provider
   acceptance language - the surviving "provider-originated" instances are in review
   records, which are deliberately not edited. **One item remains and it is Greg's call,
   not a unilateral edit:** the registry surface id
   `output_provider_invocation_response_receipts` still carries the API vocabulary in its
   NAME, and renaming it changes `surface_inventory_hash` and the manifest.
6. **The helper path is built as a tool available to RT and Forecaster**, not as four live
   roles, and the ingestion paper's Question 3 is updated to say so.
7. **Every section from 4.6 to 4.16 is fed by the traversal.** **CLOSED 2026-08-30.** 4.8,
   4.9, 4.13 and 4.14 went first, then 4.7's observation half, then 4.10/4.11/4.12/4.16 on
   the causal candidate unit (D66), then 4.6 on a per-instrument `ReplayBook` the traversal
   owns and advances action by action. Plus clocks, coverage, sessions and 4.7's horizon
   maturation. `traversal.sections_fed` names every one with its own ingest count, and two
   driver tests pin that inventory exactly, so a section cannot join or leave it quietly.
   **4.15 is unchanged and stays OUT of this run under D5** - discovery is optional to the
   runner and the gate skips it, so it is not an unfed section, it is an excluded one.
8. **Compute is settled** - which machine runs this, and whether it is sized for sixteen
   sections over 4.26M groups. See section 10a: the box was PROBED LIVE on 2026-08-29 (D55)
   as an **r6i.2xlarge**, 8 cores / 61.8 GiB / 32 GiB swap - not the t3.xlarge this line used
   to record. The resize to `r6i.8xlarge` is armed and NOT fired, so compute is still not
   settled. **The workflows now dispatch** (T4), and as of 2026-08-30 there are two MEASURED
   numbers to size against rather than estimates read off the code:

   **THROUGHPUT, and 4.6 costs 72% of it.** Two canaries, same roster, same 50,001-record
   slice, one variable changed. Run 33304621724 without 4.6 fed: **256 seconds**. Run
   33304995387 with it: **440 seconds**, or **8.8 ms per record**. The roster is **5,667,689
   records**, so the full traversal is **roughly 13.9 hours** - not the 8.1 the first figure
   implied. The cost is where 4.6's own report said it would be: the adapter advances a
   `ReplayBook` one action at a time and refreshes the queue positions behind the touched
   order, which is O(tracked_at_level x level_depth) per mutating row. That is the price of
   reading a queue position as a live feed saw it rather than as the closed group left it,
   and it is the reason the section exists.

   **A GitHub-hosted job is hard-capped at 360 minutes and this workflow is set to 350, so
   the full roster CANNOT finish on a runner** - not as a policy, as arithmetic. That is why
   `mode=full` dispatches to the box and why the checkpointer is on the path. **And the SSM
   execution timeout is the one that matters**: `send-command --timeout-seconds` is the
   DELIVERY timeout, while `AWS-RunShellScript`'s own `executionTimeout` parameter defaults
   to 3600, so a command sent without it is killed at one hour whatever the send says. It is
   set to 172800, the maximum, because 13.9 hours is projected from one slice on a different
   machine and a generous execution timeout costs nothing.

   **ARTIFACT SIZE, and this is the one that decides the volume.** That same canary produced
   a packet of **1,205,197,795 bytes for 50,001 records** - about 24 KB per record, which at
   full roster is **on the order of 136 GB of exact ledgers**. It is DISK, not RAM: D65 put
   the ledgers on `RowSink` so they stream. The armed 128 GiB figure was a MEMORY decision
   and does not cover this; the box's volume has to be sized for it separately, and a run
   that fills the disk at hour six loses the same way a timeout does.

   Both numbers are per-record extrapolations from one 50k slice on four October days. They
   are the right order of magnitude to plan with and are not a substitute for watching the
   real run - which is what D56's live monitor is for.
9. **A dry run over a small slice completes and the eight gates pass**, before anything
   touches the full roster.

When you think you are ready, go back through this document from section 1 and confirm each
claim still holds. Several things in here were true when written and were made false by the
next decision - that is exactly how the first version of this file went stale.

## 0b. THE PROCEDURAL CORRECTION (Greg, 2026-08-29) - READ WITH SECTION 1

**On the first run Frankie was never called and the runner stood in for it.** Greg:
*"frankie wasn't even called and the runner basically replaced frankie and that's not the
correct procedure"*, and *"we don't want the runner doing the work instead of frankie.
frankie should be called and doing the work."*

Two things in `native_calculation_runner.py` allowed it, and they compounded:

* `add_finding` let whatever drove the traversal author the positive findings report. That
  layer is Frankie's output, so the method should never have existed on the run.
* `_gate_not_a_model_run` **always returned True**. Its docstring said the point was that
  the distinction is "asserted in the output rather than inferred" - which is the hole. The
  assertion was true of the calculation layer and said nothing about whether a principal had
  produced the findings above it. **A label is not a check.** Same shape as the phase
  collapse and the b_share encoding: present, well formed, attesting nothing.

**The division, now enforced.** The calculation layer produces EVIDENCE. Frankie produces
FINDINGS. `add_finding` raises; `attach_principal_findings` is the only route in and demands
a named principal, a committed artifact path and that artifact's hash; `controller_only`
work and an unproven invocation are both refused; the gate REJECTS findings that carry no
principal; and every result states `completion_status` - `EVIDENCE_ONLY` or
`PRINCIPAL_FINDINGS_ATTACHED` - so evidence cannot be read as a finished run.

**`native_staging.py` is how Frankie gets called** (12 tests). `stage_spawn_request` writes a
committed request at a deterministic path from the cutoff; `load_principal_artifact` reads
the artifact back and hard-fails on missing, malformed, wrong-schema, wrong-evidence,
controller-only, or EMPTY. A missing artifact is never zero findings - a spawn that produced
nothing did not happen, and treating it as success is exactly how the runner came to stand
in. A round-trip test proves what the loader returns is what the runner accepts, so there is
no second way into the findings layer.

**PROVISIONAL dropped from findings** (Greg): a status word identical on every row carries no
information and invites the S114 mismatch where a live status sat above a discharged
falsifier. **The falsifier is the retirement mechanism.** Two other `provisional` senses are
NOT changed and need Greg's call - see section 3.

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
* **`PRE_OPEN` appears only where the gap exceeds the daily halt** - weekends, and now
  holidays too, the calendar being wired as of 2026-08-29. On a normal weekday the hour before a session opens is the
  PRIOR trade date's `POST_CLOSE`. A ~49h censoring gap and a 1h one are now
  distinguishable, which matters because segments decide where lifecycles are censored.

**Two `provisional` labels Greg has not ruled on**, flagged because they are different in
kind from the findings status and both have consequences:

* **`PROVISIONAL_SHADOW` - THIS ENTRY WAS WRONG, CORRECTED 2026-08-29 AGAINST THE CODE.**
  It said the policy sat on `extra_agent_corrected_information_and_gap_diagnoses` and
  `extra_agent_four_helper_architecture_roles`, both `model_visible: False`. **It does not,
  and they are not.** Read from
  `frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` and
  `native_ingestion_layer_registry.py`:
  * The two `PROVISIONAL_SHADOW` layers are **`s137_cognitive_shadow_runtime`** and
    **`hipporag_associative_retrieval`** (group `provisional_shadow`, `principal_route:
    SHADOW_ONLY`, `activation_stage: EXPLICIT_IDENTICAL_ARM_OPT_IN_ONLY`). Computed policy
    counts match `EXPECTED_POLICY_COUNTS` exactly, so those two are the whole set.
  * **Both `extra_agent_*` layers are `STATIC_REQUIRED_INPUT`** in group
    `corrected_extra_agent_carryforward`, `principal_route: DIRECT`, `activation_stage:
    PRE_CALL`, on BOTH arms. `native_ingestion_layer_registry.py:348` enforces
    `("AVAILABLE", model_visible=True, "SHA")` for that policy. **So Frankie already SEES
    both, and a pre-call receipt that reports either one invisible FAILS the gate** - the
    exact opposite of what this document said.
  **CLOSED 2026-08-30 (Greg, D64): THE FOUR HELPERS ARE OUT OF THE REGISTRY.** Greg, asked
  the open question below directly: *"get any mention of the 4 helpers out. He can call with
  different persona options as part of his tools. We've covered this more than once."* Six
  layer identities removed - `extra_agent_four_helper_architecture_roles`, the whole
  `helper_role_configuration` group of four scouts, and `output_helper_evidence_movie`.
  Union layer count **105 -> 99**, arms **102/104 -> 96/98**, policy counts
  `STATIC_REQUIRED_INPUT` **24 -> 19** and `APPEND_ONLY_OUTPUT` **11 -> 10**, plus a new
  `EXPECTED_LAYER_ID_SET_SHA256`, a new `registry_sha256` and six surfaces out of the
  execution gate. `ALLOWED_V3_LAYER_IDS` now has one member.
  **NOTHING SOURCE-LEVEL WAS DROPPED (D60).** The removed carryforward layer named exactly
  the same three V3 files as `extra_agent_corrected_information_and_gap_diagnoses`, which
  stays required and model-visible - and those files contain **no helper text at all**. The
  four-helper architecture lived in a layer DESCRIPTION and in feed-inventory section 10,
  never in the evidence. What was removed is the instruction to read those files as a helper
  architecture. **The second half of D59 - does the corrected-information layer itself stay
  required and model-visible - was NOT asked again and is unchanged.**
  Feed inventory section 10 is retired in place (number kept, so cross-references still
  resolve) and the canonical monthly procedure goes to **version 2**: step 11's four-helper
  concurrency, the role-to-CPU invariant, the four-thread limb of the step-12 gate and the
  Nucleus-replacement paragraph are all retired. The record of what it said:

  **CONSEQUENCE - D54 WAS CONTRADICTED BY THE ENFORCEMENT LAYER AND WAS NOT LANDED.** D54
  records that `extra_agent_four_helper_architecture_roles` "stays shadow and
  `model_visible: False`" because it documents a superseded architecture. The registry
  requires the opposite and no registry change was made. This is the S115 lesson in its
  worse form: not a decision nothing enforces, but a decision something enforces the
  **reverse** of. Nothing has failed yet only because no run has reached the pre-call gate.
  **WHAT IS ACTUALLY OPEN, and it is one question asked twice** - for the helper-roles layer
  and for the corrected-information layer, each: **does it stay a required, model-visible
  input, or does it move to shadow?** Both are `v3_derived: true` and are the only two
  members of `ALLOWED_V3_LAYER_IDS`; their sources include
  `NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md`, so
  "required and visible" means Frankie reads V3 carryforward marked NONAUTHORITATIVE as a
  binding input on every run. Moving either one changes `EXPECTED_POLICY_COUNTS`,
  `EXPECTED_ARM_LAYER_COUNTS`, `EXPECTED_LAYER_ID_SET_SHA256`, the surface inventory hash
  and the manifest - which is why it is a ruling and not an edit.
* **"provisional strategy hypotheses"** in the RT mission and the discovery addendum are
  `ALWAYS_LOAD` instructions telling Frankie what to PRODUCE. Editing them changes Frankie's
  job and requires regenerating hash-bound capsules.

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
| `agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` | **99 entries = 91 concrete layers + 8 arm/control bindings** (was 105/97; D64 removed six helper layers 2026-08-30). 90 is the declared floor, so the margin is nine. |

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

All under `research/kalshi/frankie_raw_mbo_benchmark/`. **576 tests pass** (2026-08-29).

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
| §2 | `native_session.py` | 417 | D6a+D6b. Boundaries exchange-local, so they survive DST. Segment is the CME trade date. Phase from the settlement window and session hours. Non-monotonic input refused. CME holiday calendar consulted; a shortened session refuses rather than answering from ordinary hours. |
| §5/§6 | `native_calculation_runner.py` | 519 | Seven layers, eight gates, no partial promotion. |
| — | `native_staging.py` | 195 | The spawn contract. A missing or empty principal artifact is a HARD failure, never zero findings. |
| — | `periodic_checkpointer.py` | 380 | Save points on record or clock interval, refused mid-group. |
| 4.8/4.9/4.13/4.14 | `native_group_adapters.py` | 314 | Raw MBO to constructed domain objects on the F_LAST unit. Ladder scope travels ON the value. No mean, ratio-of-sums or rate anywhere. 22 tests. **2026-08-30: CALLED BY THE DRIVER.** Wiring found a defect reading could not: a group opening on a row with `order_id` 0 parented on `ord-0`, a node nobody adds, and `LineageGraph.add` raised - it would have killed the traversal on real tape. |
| 4.6 (input) | `native_rt_book.py` | 262 | The RT view. Advanced one action at a time, so a level is read as a live feed saw it, never as the closed group left it. Mirrors `InstrumentBook` on every mutation; refuses a negative size where it clamps. 24 tests incl. an executable no-lookahead property. |
| — | `native_replay_driver.py` | 358 | Runs end to end and finalizes ACCEPTED. **2026-08-30: calls all four built adapters** - 4.14, 4.9, 4.8, 4.13 - and emits `sections_fed` so an empty ingest is visible rather than inferred. 26 tests. See section 8. |

Sections 4.1-4.4 already existed in `a_memory_member_first_recalculation_20260828.py`, which
ran the full roster: 5,667,689 records into 4,256,603 groups, 4,758 candidate families, in
2,985s, with `daily_averaged_companion_verification: EXACT_MATCH`.

**552 tests** as of 2026-08-29 (529 + 20 group adapters + 3 gate/state).

Tests are one file per module under `frankie_raw_mbo_benchmark/tests/`, plus
`test_open_world_growth.py` (the vocabulary must grow) and
`test_raw_mbo_source_manifest_roles.py` (roster and hash split).

## 8. What is NOT wired — the remaining build

Verified by search on 2026-08-29. The execution gate is referenced by nothing but itself
and its test. `native_replay_driver` is referenced by **no Python at all**. **Correction to
the previous version of this file:** `periodic_checkpointer` is *not* referenced by nothing
- `native_replay_driver.py` imports it. The conclusion is unchanged, since the driver never
runs, but the claim as written was wrong. No driver feeds the sixteen sections.

1. **The driver.** **Partly done.** It now RUNS - a pass executes end to end and finalizes
   ACCEPTED, which it had never done - and it has 14 tests. `ExchangeSessionRule` supplies
   the D6 rule and the traversal reports its assignments, so the reconciliation gate passes
   on the real rule. **A defect was fixed in the process:** `SessionRule.classify` offered
   only `recv_ns`, which would have keyed session membership on the feed's serialization
   rather than on the market; it now takes both clocks and decides on `event_ns`.
   It now also uses the CANONICAL family identity: `_family_id` was the bare action string,
   a different vocabulary from the `candidate_family_id` the member-first run used when it
   produced the roster's 4,758 families. Nothing would have failed - the strata would simply
   have been cut differently here than in the run this one must reconcile against. Measured
   cost of the canonical detector: 88s over the full roster.

   **STILL OPEN, and the first item is NOT mechanical:** sections 4.6 to 4.16 are closed at
   boundaries but never fed.

   **BUILT AND FED ARE DIFFERENT LAYERS - do not read "unfed" as "unbuilt."** This wording
   has already misled once (2026-08-29). **All sixteen sections ARE built and tested** and
   none of that is to be redone: `native_queue` 23 tests, `native_replenishment` 25,
   `native_exhaustion` 24, `native_recognition` 17, `native_dipole` 25, `native_discovery`
   22, `native_response` 20 - 156 across the seven still-unfed sections alone. What is
   missing is ONLY the adapter that constructs their inputs. Verified by search on
   2026-08-29: `observe_level`, `on_add`, `open_episode`, `open_runway`,
   `CandidateRecognition`, `observe_path` and `open_track` are each referenced by exactly
   one non-test file - **the module that defines them.** Zero callers from the traversal.
   Say "unfed", never "remaining". **Correction to the previous version of this file:** it said
   `LadderCalculator`, `RecurrenceCalculator` and `LineageCalculator` "expose no ingest
   method at all". That is wrong - they expose `observe`, `observe_sequence` and
   `observe_node` respectively, and a session spent adding ingest methods would be spent
   rebuilding what is there. The gap is UNIFORM across all eleven sections and is one level
   up: every ingest point takes a CONSTRUCTED DOMAIN OBJECT - a `LadderTransition`, a
   `Sequence[Occurrence]`, a `LineageNode` plus its `LineageGraph`, a `RunwayPressure` for
   `AbsorptionCalculator.score`, and likewise for `DipoleCalculator.observe_path` and
   `ExhaustionCalculator.enter_phase` - and **nothing anywhere turns raw MBO events into
   those objects.** **The contract specifies the CALCULATION, not the input event** - 4.10
   says "construct a complete causal runway for each candidate" without defining a
   candidate. Feeding these means deciding what counts as a runway, a dipole path, a lineage
   node and a ladder snapshot in raw MBO, which shapes what the benchmark reports and should
   not be invented quietly. `describe_structure` is the canonical precedent to build from.
   **THE UNIT IS DECIDED (2026-08-29, Greg - D53): the F_LAST GROUP, one unit across all
   sixteen sections.** A candidate IS one F_LAST group - the same unit `describe_structure`
   already hashes into `candidate_family_id`, and the unit the member-first run cut its
   4,758 families from. Chosen so reconciliation against the existing roster holds by
   construction rather than introducing a second traversal vocabulary, which is exactly the
   `_family_id` defect caught on 2026-08-29. **Recorded cost, not hidden:** 4.6 order
   survival and 4.9 ladder topology are not naturally group-shaped, and the adapters must
   report where that distorts rather than smoothing it over.

   **ADAPTER STATUS, CORRECTED 2026-08-29 - FOUR OF THE ELEVEN ARE BUILT, SEVEN ARE NOT.**
   This paragraph used to end "What remains is building the eleven adapters on that unit",
   and it was never updated when commit `8645c5d` landed the first tranche. That is the
   section-11 same-commit rule broken on this document itself, and it is what made the adapter work read
   as either finished or untouched depending on which line you landed on.
   **BUILT** (`native_group_adapters.py`, 314 lines, 22 tests): **4.14** recurrence
   (`occurrences`), **4.9** ladder (`ladder_transitions`), **4.8** absorption
   (`runway_pressure_fields`), **4.13** lineage (`lineage_additions`).
   **NOT BUILT: 4.6, 4.7, 4.10, 4.11, 4.12, 4.15, 4.16.**

   **T1 CLOSED 2026-08-30 - ALL FOUR BUILT ADAPTERS ARE NOW WIRED AND FED.** Count, so this
   queue shrinks when work lands: **4 of 4 built adapters wired; 7 of 11 adapters still
   unbuilt.** `NativeReplayDriver._feed_sections` calls all four on the D53 unit, from ONE
   `GroupContext` built off the canonical `candidate_family_id` - assembling the stratum per
   section is how two vocabularies for one quantity get born. Every return value is retained
   as a lifecycle row, because an average with no member beneath it is what section 6
   rejects. Package suite **653 -> 665**; wider suite unchanged at 7 pre-existing failures.

   **Three things the wiring settled that reading had not:**
   * **4.13 needed an owner for its graph.** `LineageCalculator.observe_node` takes the graph
     as an argument and the run holds none, so the driver holds it - and rebuilds it at every
     continuity boundary (`LINEAGE_SEGMENT_SCOPE = ONE_CONTINUITY_SEGMENT`). Lineage is the
     one fed section with cross-group state and no `close_continuity_segment` of its own, so
     without this it would have chained depth across the halt that censors every other
     section. The scope is emitted in the output, not left in prose.
   * **Nodes are observed at the BOUNDARY, not at creation.** `exited_recv_ns` is set by the
     arrival of a CHILD, so observing at creation would have reported every node `OPEN` with
     no stage duration - the section that exists to separate termination from censoring would
     have reported neither. Now `TERMINATED` vs `CENSORED_SEGMENT_END`/`CENSORED_STREAM_END`,
     pinned by a test.
   * **A defect only wiring could find.** `lineage_additions` took `actions[0]["order_id"]` as
     the initiator. Databento writes `order_id` 0 on rows that identify no resting order, so
     any group opening on one parented on `ord-0` - a node nobody adds - and
     `LineageGraph.add` raised. It would have killed the traversal on real tape at the first
     such group. Fixed by falling forward to the group's first NAMED order id; a group naming
     none contributes no lineage, which is recorded as an absence rather than filled.

   **Corrections to this section's own previous wording, both wrong when checked by
   execution:** it said `native_group_adapters` "is imported by exactly one file - its own
   test". It was also imported by `native_rt_book.py:80` (`PRICE_SENTINEL_ABS`). And it said
   NO non-test file imports `native_queue`, `native_replenishment`, `native_exhaustion`,
   `native_recognition`, `native_dipole`, `native_discovery` or `native_response` -
   `native_calculation_runner.py:24-36` imports **all thirteen** calculators. The intended
   claim was about ingest CALL SITES and was true; as written both were reached by grepping a
   name, which is the method this program has now been bitten by three times.
   `native_replay_driver.py` also carried a **dead** `AbsorptionCalculator` import, its only
   occurrence in the file, so an auditor grepping "is absorption wired" saw an import and
   stopped. It is now a live `RunwayPressure` import.

   **THE REMAINING SEVEN ARE NOT ONE JOB. THE CONTRACTS WERE EXTRACTED 2026-08-29 AND THEY
   SPLIT THREE WAYS.** Every ingest signature below was read out of the module and its tests,
   not inferred.

   * **4.15 discovery - DO NOT BUILD IT. It is not seven, it is six.** D5 closed clustering
     out of this run, and the code agrees: `native_calculation_runner.py:226` takes
     `discovery` as `None`-defaulted, `:281` enters section `4.15` in the layer map ONLY if
     it is not None, and `:466` is the sole gate that mentions it - with `discovery=None` the
     condition short-circuits and the gate passes. Building this adapter would not add a
     measurement, it would add an OBLIGATION: a live `DiscoveryCalculator` turns
     `_gate_determinism` from a free pass into a `freeze()`-before-`finalize()` requirement.
   * **BUILDABLE WITH NO INVENTION - 4.6 queue and 4.7 replenishment.** Both need a FIFO book,
     and **the book already exists**: `InstrumentBook` in
     `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` keeps `levels[side][price]` as
     an insertion-ordered `list[order_id]` plus `orders[order_id]` carrying size, and the
     driver already holds a `V4MboAdapter`. That supplies 4.6's mandatory `book_view`
     callback, and supplies 4.7's order-id novelty test (`NEW_ID_ADD` vs `SAME_ID_MODIFY`),
     level depth and touch price. One declared choice remains in 4.7: the tick neighbourhood
     that separates `SAME_PRICE` from `NEIGHBORING_PRICE`.
   * **BLOCKED ON A RULING - 4.10, 4.11, 4.12, 4.16. THE PROPOSALS ARE WRITTEN:**
     `research/kalshi/FRANKIE_A_ARM_ESTIMAND_PROPOSALS_20260829.md` carries one concrete
     definition per section with what it costs, what it makes unmeasurable, and how it would
     be falsified. Nothing is built against any of them. The 4.11 call predicate is flagged
     there as the weakest of the four and the one genuine invention.** Each needs a decision that SHAPES WHAT
     THE BENCHMARK REPORTS, which is the thing this document says must not be invented
     quietly. Named exactly, so each can be answered as itself:
     * **4.10 exhaustion** keys open runways on `candidate_id`. `GroupContext.candidate_id`
       is per-group, so using it makes **every runway exactly one group long** - phases can
       never advance and `PHASE_INDEX` never moves off its first entry. It needs a runway
       identity that spans groups, plus which raw pattern enters which phase.
     * **4.11 recognition** defines no predicate for what a "call" IS, no birth event, and no
       horizon separating MISSED from CENSORED. Worse, with `birth_recv_ns = ctx.recv_ns`
       the `PRIOR` outcome is **structurally unreachable** - every same-group call is `T0`
       and every later one `HORIZON` - so the prebirth half of the section, which is its
       point, would silently report nothing.
     * **4.12 dipole** requires `orientation` in `{SAME, FLIP}`, which is a MIRROR
       relationship defined nowhere in the tree and is explicitly NOT the bid/ask side; an
       `event_phase` string with no `GroupContext` source; and a counterpart's
       `mirror_signed_flow` that the calculator will never look up.
     * **4.16 response** requires the horizon set and `horizon_version`, a `values_for`
       callable saying WHAT response is measured, plus `starting_liquidity_regime` and
       `cluster_version`. Those four are not plumbing; they are the experiment.

   **THE CAUSALITY CONSTRAINT BELOW IS NOW CLOSED (2026-08-29): `native_rt_book.ReplayBook`
   is built, 24 tests, and the fork was decided by Greg - "We should see it like it would be
   seen in rt."** The book is advanced action by action, so `book_view` answers as a live feed
   would have at that action's own instant, and a property test asserts executably that the
   state after k rows is a function of `rows[:k]` and nothing later. It mirrors
   `InstrumentBook` on every mutation - a second book that disagreed with the first would
   reproduce the very defect it exists to prevent - and diverges only by refusing a negative
   size where `InstrumentBook` clamps it to zero. **4.6 is now unblocked; its adapter is the
   next build.** The constraint as originally recorded:

   **AND ONE CAUSALITY CONSTRAINT THAT BINDS 4.6 BEFORE ANY OF THAT.** `InstrumentBook.apply`
   mutates the book on EVERY record, while the group frame carrying `raw_actions` is returned
   only at F_LAST. So by the time `_on_group` sees a group, the book already reflects that
   group's own later actions. Reading `book_view` there would report a level as it stood
   AFTER the add it is meant to describe - an intra-group lookahead, present, typed and
   wrong. Feeding 4.6 therefore means either driving it per record inside `apply`, or holding
   a second FIFO book advanced action-by-action in tape order (the `FakeBook` precedent in
   `tests/test_native_queue.py`). This is a real fork and it is recorded rather than picked
   in passing.
   `on_invoke` is GONE, replaced by `stage_spawn`: at a cutoff the traversal writes a
   committed request via `native_staging.SpawnStager` and moves on. It calls nothing. The
   full loop is now closed and tested - stage at cutoff, agent session reads, artifact
   loaded back, runner ingests with attribution, gate rejects if absent.
2. ~~**Wire the checkpointer** into both launch workflows.~~ **DONE 2026-08-30 (T3).**
3. ~~**Wire the gate** into the launcher. An unreferenced gate is not a gate.~~
   **DONE 2026-08-30 (T2).**

   **T2, T3 and T5 were ONE missing thing, not three: a launch entrypoint.**
   `native_a_arm_launch.py` is it. The gate, the checkpointer and the driver were each built
   and each wired to nothing, because there was no module that ran them in order. It gates,
   traverses, checkpoints and finalizes, and it never calls a model - at a cutoff the
   traversal stages a committed request and moves on. **15 tests; package suite 665 -> 680.**

   The three pre-traversal gates run in order and fail closed:
   1. `validate_registry` - exact layer identities, policy counts, arm counts, sealed set.
   2. `validate_pre_call_receipt` - every registered layer enumerated with the status its own
      policy demands and a REAL evidence hash, computed over the declared source paths AND
      their bytes. A receipt cannot be produced for a file that is not there. Measured:
      **99 layers, 75 required for A-clean and 77 for A-memory** - the D2 asymmetry visible
      in the receipt - and the nine-layer answer wall SEALED.
   3. `validate_rt_surface_inventory` - the same registry in the execution gate's own
      vocabulary, **91 surfaces**, re-proving the Step-1 wall from a second object. Two
      objects over one registry on purpose: a field-level check cannot catch a
      wrong-but-well-formed input, and only a second source settles it.

   **Two defects the wiring found, both invisible while nothing dispatched the driver:** the
   checkpointer REFUSES an interval save before `seal_start` writes sequence 0, and
   `stage_spawn_request` REFUSES a request whose evidence carries no `result_hash`. Both are
   the modules failing closed exactly as designed; both could only surface on a path that
   runs.

   **The declared gap:** `native_records`, the DBN decode, is the one part of the launch path
   these tests do not cover. AWS credentials are GitHub-secret scoped, so no interactive
   session can read the roster; the tests drive the path with a supplied record iterable and
   the DBN read is covered by the workflow slice, not here. Stated rather than papered over.
4. ~~**Feed the D6 assignment into the traversal.**~~ **DONE.** Wired as a RECONCILIATION,
   not a hand-off: the traversal reports what it keyed on via
   `NativeCalculationRun.note_session_assignment`, `native_session.AssignmentLedger`
   recomputes both from the group's own `ts_event_ns`, and `denominators_strata_and_censoring`
   fails on any disagreement. A field-level check could never catch this - a constant phase
   is present, typed and plausible - which is the S108/S109 conclusion applied here. Both
   escape routes are closed: a wrong value mismatches, and writing member rows while
   reporting NO assignment fails the same gate. `session_strata` defaults to **True**, so
   forgetting leaves the check on; `make_run` in the runner tests opts out explicitly.
5. ~~**Wire an exchange holiday calendar.**~~ **DONE 2026-08-29** (Greg: *"we follow cme
   trading day schedule"*). `native_session.is_trading_day` reads the CME energy holiday
   class from `plant_calendar`, which generates it from RULES - necessary, because the
   roster year is 2021 and `flow_calendar.CME_HOLIDAYS` starts at 2025-09-01, so a table
   lookup would have answered "not a holiday" for every date in the source window. The
   rules reproduce all 16 committed entries with 0 mismatches. A `full_closure` is not a
   trade date and is skipped by the same loop that skips a Saturday; the Christmas-evening
   reopen carrying the NEXT trade date falls out of the existing reopen rule rather than a
   clause. A `partial_session` / `early_close` IS a trade date - `flow_calendar` calling a
   partial session "not a business day" is the SETTLEMENT-counting sense, and conflating it
   with the trading-day sense would move every expiry-adjacent segment by a day.
   **`phase_within` REFUSES on a shortened date** rather than answering from ordinary
   hours: the shortened close time is recorded nowhere in this repository, and a
   `partial_session` runs no settlement cycle at all, so there is no correct carried label
   to return. The roster contains no holiday, so this raises nowhere in the launch window
   and no value the run uses changed - verified by executing the traversal over the roster
   before and after. **The remaining declared gap is the shortened close TIME.**

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

**NOTHING IS DROPPED WITHOUT DISCUSSING IT FIRST (Greg, 2026-08-29 - D60, and he has said it
many times before this one).** *"we have all this data for a reason. do not drop any of it
without discussing with me first. make that a rule."* *"do not leave any of the book data out.
it may not seem relevant to you but it may to frankie."* *"i don't care about memory. restore
every piece... let him figure out what he uses but he has to see everything."* A row, field,
message or observable that reaches our code is **USED**, or **RETAINED and counted**, or
**REFUSED loudly**. Never silently ignored. **Memory is explicitly not a reason.** Relevance is
Frankie's to decide, not the ingest layer's. **The one exception is narrow:** *"if a row is
truly blank and is measuring nothing then you can leave it off"* - truly blank, shown from the
row itself.

**Why it is a standing constraint and not a preference, in Greg's words:** *"this is the
problem that i have been fighting the whole time that things are dropped for whatever reason
and not discussed and then we find out we have to rerun because it was important"* and *"we're
constantly having to go back and audit things over and over."* A dropped input does not fail -
it yields a number that is present, typed, in range and wrong - so it surfaces only after a
full run, and the rerun is the expensive part. **Two instances were found the day it was
written**, both now fixed: `native_rt_book.ReplayBook` silently ignoring four row classes
`InstrumentBook` acts on, and `native_replay_driver` discarding the adapter's legacy MBP-10
rows, which are the only source for a CAUSAL_STREAM_REQUIRED registry group. **A full-pipeline
drop audit is running across the ingest, traversal and output layers; findings and their
restorations belong here.**

**And the auditing is now the machine's job, because doing it by hand is what Greg is tired
of.** `tests/test_native_rt_book_differential.py` drives `ReplayBook` and `InstrumentBook` in
lockstep and compares full state after every record - 12,024 records, zero divergence - and its
governing assertion is design-independent: an anomalous row is refused loudly or mirrored
exactly, NEVER silently dropped. It also mutation-tests its own comparator, because a
differential that compares nothing passes forever. `RetentionTests` fails if any action stops
leaving a trace, and `LegacyRowRetentionTest` fails if retained ever falls short of seen.


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

~~**The A-arm launch workflows never reach the AWS box.**~~ **CLOSED 2026-08-30 (T4).**
The paragraph this replaces was true and is measured again below. Both workflows now carry
**12 references** each to `ssm` / `send-command` / `INSTANCE_ID` / the launcher module,
against **0** before, and they run in **two modes**:

* **`canary` (the default, and what a push runs).** A bounded slice of the REAL hash-bound
  roster through `native_a_arm_launch`, on the runner - no box, no SSM, no spend beyond
  runner minutes. This is prelaunch section 0 item 9: the dry run over a small slice with
  the eight section 6 gates passing, before anything touches the full roster. The launcher
  exits non-zero on any verdict but ACCEPTED, so the step cannot go green over a refused
  calculation, and a separate step writes the canary's verdict into the job summary **by
  reading `calculation_result.json`** rather than by restating it.
* **`full`.** The whole roster on the box over SSM, `AWS-RunShellScript`, dispatch and wait.
  **Reachable ONLY by an explicit `workflow_dispatch` with `mode=full`** - a push can never
  get there, and a test asserts BOTH limbs of that guard, because `inputs.mode == 'full'`
  alone is a condition that looks like a guard and is not one on a push where `inputs` is
  empty. Starting the box is a spend and D58 leaves the sizing with Greg.

**The D57 defect happened again while writing this, and `bash -n` caught it.** The canary
summary began as a heredoc nested inside the report step's `{ ... }` group, which put `PY`
at a non-zero column so bash never saw the terminator. It is now its own step. Both
workflows are verified by parsing the YAML, running `bash -n` on every `run:` block, and
`ast.parse` on every embedded Python heredoc - `tests/test_a_arm_launch_workflows.py`.

The original paragraph, kept because it is the measurement: neither file contained a single
reference to `ssm`, `ec2`, `send-command` or `INSTANCE_ID`; their steps were checkout,
verify branch, install the DBN reader, fetch and hash-bind the roster, seal the packet and
the pre-call checkpoint, push to S3, publish, report. **They staged and stopped.**

**The recorded box was STALE, and the predicted failure is exactly what happened**
(corrected 2026-08-29, Greg - D55). The paragraph this replaces said
`LIVE_TELEMETRY_S100.md` records `i-08cee7171c0a76a04` as a **t3.xlarge**, 4 vCPU / 16 GB,
and warned in writing: "if the instance was resized, the record was not updated, and the
record is what the next session will believe." It was resized and the record was not
updated.

Greg, verbatim: *"We switched to the larger box with 64g ram and 8 agents because of the big
computes and this might not be enough for this. We had 6 cpus running and 2 for the planes.
We also had a ram swap which was needed too."*

So the machine is **64 GB RAM / 8**, split **6 for work and 2 for the planes**, **with swap
that was required rather than incidental** - a run sized to fit in RAM alone would have been
sized against a configuration that never ran. `LIVE_TELEMETRY_S100.md` is wrong and should
be corrected at the source. `CLAUDE.md`'s 200 GB on the same instance is disk, not RAM, and
that part stands.

**VERIFIED LIVE 2026-08-29 - and Greg was right on every count while the record was wrong
on every count.** The probe ran (run 33242769879) and measured: instance **`r6i.2xlarge`**,
running, us-east-2b; **8 cores**; **61.8 GiB** memory (64 GB nominal, 60.7 GiB available on
an idle box); **32.0 GiB of swap, present** - the configuration Greg described as required
is actually in place; **128.2 GiB** free disk. `LIVE_TELEMETRY_S100.md`'s t3.xlarge is
wrong and has been corrected at the source, as have `PLANT_MAP.md`, the October sharded
handoff and the drop-in box. The S91-S93 handoffs are left untouched: a t3.xlarge was true
when they were written, and that is the audit trail, not an error.

**The one that mattered beyond the record:** the October sharded handoff sized its workers
at "three of four cores" on a machine that has eight. That is not cosmetic - it is a
capacity assumption wrong by a factor of two, and it was about to be inherited.

**SIZING IS STILL OPEN.** Knowing the box is 8 cores / 62 GiB / 32 GiB swap does not
establish that sixteen sections over 4.26M groups fit in it. Greg's *"this might not be
enough"* stands until a slice is actually measured, which is the dry run in section 0 item 9.

**How it was settled, since it is not obvious.** Greg (2026-08-29): *"aws credentials are in git secrets."* They are - which means
they are WORKFLOW-scoped, not session-scoped: an interactive session resolves nothing
(`NoCredentialsError`, verified). So no Claude session can settle this from a desk, and
`.github/workflows/frankie_box_sizing_probe_20260829.yml` is the path. It is strictly
read-only - `ec2 describe-instances` for the type, then `/proc` over SSM for cores, memory
and swap - writes nothing, starts no arm and touches no S3 object, and it is
**`workflow_dispatch` only** so it cannot fire on a push. It prints the observed values
against both claims side by side, including whether the swap Greg describes as REQUIRED is
actually in place. **Greg runs it; a Claude token cannot click Run workflow.**

**Sizing is NOT settled, and Greg flagged it himself:** *"this might not be enough for
this."* Sixteen sections over 4.26M groups against a member-first run that took 2,985s and
wrote 1.5 GB covering 5 of 16.

Why it matters: the member-first recalculation covering 5 of 16 sections took 2,985s and
produced a 1.5 GB exact-members file. Sixteen sections over 4.26M groups on 16 GB is at
least worth sizing before it is attempted, and `ubuntu-latest` - which is what the A-arm
workflows currently use - is smaller again.

~~**A likely explanation for the four helper lanes.**~~ **DEAD - the conjecture rested on
the stale record.** It read: a t3.xlarge has exactly 4 vCPUs and the registry carries
exactly 4 helper scouts, so the "four live helpers" may be a parallelism artifact of the
box. The box has **8**, so the coincidence it was built on does not exist. Recorded rather
than deleted because it is a clean example of the same defect twice over: a theory fitted to
a number that was itself unverified. Nothing depended on it - helpers are tools, not lanes
(D54).

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
- Run the A-arm suite first. If it is not 552 green, stop and find out why before building.
- Run the knowledge refresh with `--check`. It should report `CURRENT`. If it reports
  `UPDATED`, someone hand-edited a generated capsule and that needs understanding, not
  overwriting.
- If you change any decision in section 2 or 3, **update this file in the same commit.**
  The first version of this document went stale because that did not happen.
- **The same rule binds a BUILD, not only a decision** - added 2026-08-29 after this file
  went stale a second time. Commit `8645c5d` built four of the eleven adapters and changed no
  decision, so the rule as written did not bite, and section 8 went on saying "what remains is
  building the eleven adapters" while four of them sat in the tree. **If you land code that
  closes any part of section 8, close it in section 8 in the same commit, with a count.** A
  build queue that does not shrink when work lands is a build queue that will be re-proposed
  and re-argued every session - which is exactly what happened here.
