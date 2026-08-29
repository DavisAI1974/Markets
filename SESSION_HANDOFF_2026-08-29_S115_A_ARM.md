# SESSION HANDOFF - 2026-08-29 - S115 A-ARM (Frankie raw-MBO benchmark)

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Started at: `83d82a8`. Ended at: see `git log --oneline -1`.
Tests: **552 pass** in `research/kalshi/frankie_raw_mbo_benchmark/tests/` (was 522).
The wider `research/kalshi/tests/` suite still has its **7 pre-existing failures** - verified
unchanged, not caused here, not fixed here.

**NOTHING LAUNCHED.** No arm started, no calculation dispatched, no model invoked.

> Session-number note: `KALSHI_TRADING.md` already carried an "S115" section for a different
> line of work (the pre-paper-trade platform audit / brain one-doc fix). This handoff is the
> **A-ARM** S115 and is deliberately named so the two are never conflated.

---

## 1. THE FINDING THAT MATTERS MOST - THE GATE ENFORCED THE ARCHITECTURE GREG KEPT CORRECTING

Greg, mid-session: *"we're not using the openai api!!! we are running 5.6sol like you ran the
blind/refine groups. i have said this every session."*

He has. The reason it kept needing saying is not that the record was missing - section 1 of the
prelaunch state doc says it plainly, and D5 recorded it. **The reason is that the execution gate
still ENFORCED the API architecture.** `validate_principal_execution` required `provider`,
`requested_model`, `served_model`, `principal_invocation_id`, and reconciling token `usage` with
a `provider_usage_receipt_sha256`.

**None of those exist in an agent-session run.** So the gate would have **rejected a correct Sol
run and accepted only an API one.** The correction lived in prose while the check demanded the
opposite - which is exactly the S114 lesson about the do/dont rule that "silently expired"
because it was never made a schema rule. A decision recorded where nothing enforces it is a
decision that has not landed.

**Fixed.** The gate is now file-based, matching what `native_staging.py` already implements and
what actually proved a specialist ran for twenty-four group cycles: a committed staged request at
a known path and a committed artifact at a known path in the expected schema, both hash-bound.
A request and its artifact hashing identically is refused - a run that returned its own input
produced no findings. The lock and freeze gates moved with it (`principal_response_id` ->
`principal_artifact_path`, `principal_output_sha256` -> `principal_findings_sha256`).

**The old token-usage test was REPLACED, not deleted**, and a new test pins that a
provider-shaped record is now REFUSED outright, so the API shape cannot quietly return.

**Audited for the rest of the surface.** The four model-visible papers carry no provider
acceptance language. Two items are deliberately untouched: the registry surface id
`output_provider_invocation_response_receipts`, because renaming it changes
`surface_inventory_hash` and the manifest and that is Greg's call; and the `provider` mention in
`FRANKIE_KNOWLEDGE_USE_AND_NONFORGETTING_REVIEW_20260828.md`, which is a record.

---

## 2. DECISIONS TAKEN - D52 THROUGH D57 (root `DECISIONS.md`)

**D52 - the CME trading-day schedule is the holiday authority.** Greg: *"we follow cms [CME]
trading day schedule."* D51 applied to holidays. Built into `native_session.py`:

- Classes come from `plant_calendar`'s **RULES**, not a date table. This was necessary rather
  than stylistic: the roster year is **2021** and `flow_calendar.CME_HOLIDAYS` begins
  **2025-09-01**, so a table lookup would have answered "not a holiday" for every date in the
  source window - present, boolean and wrong, the S112 expiring-table finding. The rules
  reproduce all 16 committed entries with **0 mismatches**.
- A `full_closure` is not a trade date and is skipped by the same loop that skips a Saturday, so
  the Christmas-evening reopen carrying the NEXT trade date falls out of the existing reopen rule
  instead of a special case.
- A `partial_session` / `early_close` **IS** a trade date, because the book opens. `flow_calendar`
  calling a partial session "not a business day" is the **settlement-counting** sense; conflating
  it with the trading-day sense would move every expiry-adjacent segment by a day.
- **`phase_within` REFUSES on a shortened date** rather than answering from the ordinary 16:00 CT
  / 14:28 ET boundaries. Two facts are missing and either alone makes the answer wrong: no source
  in this repository records the shortened close time, and a `partial_session` runs **no
  settlement cycle at all**, so the settlement-derived phases do not shift, they do not exist.
- The roster spans no holiday, so nothing raises in the launch window. **Verified by executing
  the traversal over the roster before and after, not by inspection.**

**D53 - the A-arm input unit is the F_LAST group, one unit across all sixteen sections.** Sections
4.6-4.16 were closed at their boundaries and fed by nothing because the contract specifies the
CALCULATION and never the input event (4.10 says "construct a complete causal runway for each
candidate" and never defines a candidate). A candidate IS one F_LAST group - the unit
`describe_structure` already hashes into `candidate_family_id`, and the unit the member-first run
cut its 4,758 families from. Chosen so reconciliation against the roster holds **by construction**
rather than by agreement between two vocabularies, which is the `_family_id` defect of 2026-08-29.
**Recorded cost, not hidden:** 4.6 order survival and 4.9 ladder topology are not naturally
group-shaped.

**D54 - no helper lanes and no specialists on the A arms.** Greg: *"we aren't doing the helpers or
the specialists anymore. Rt and forecaster can call one as part of their tools and there's options
as to the role."* So `extra_agent_four_helper_architecture_roles` documents a **superseded**
architecture and stays shadow - showing Frankie a dead architecture is worse than showing nothing.

**D55 - the box record was stale, and the failure is the one section 10a predicted in writing.**
It said: *"if the instance was resized, the record was not updated, and the record is what the
next session will believe."* It was, and it wasn't. **Settled by live probe** (see section 4).

**D56 - size the box up before the run, then watch it grow.** See section 4.

**D57 - the two always-failing workflows never touched step1 data.** See section 5.

---

## 3. BUILT

### `native_group_adapters.py` (NEW) - the missing layer under sections 4.6-4.16

Every ingest point in the tree takes a **constructed domain object** - a `LadderTransition`, a
`Sequence[Occurrence]`, a `LineageNode`, a `RunwayPressure` - and **nothing built those from raw
MBO**. This module is that layer, on the D53 unit. Covered in this tranche, each verified against
the **real calculator** rather than in isolation: **4.14** recurrence, **4.9** ladder, **4.8**
absorption, **4.13** lineage. 20 tests.

Two construction choices are declared rather than assumed, both costs Greg took knowingly:

- **4.9 is a group-local ladder DELTA, not a book snapshot** - a group cannot see liquidity it
  never touched, so `before` is the depth it consumed and `after` the depth it left. The scope
  travels **on the value** as `LADDER_SCOPE`, not only in a docstring, because a caveat that lives
  only in prose expires (S114).
- **Lineage depth accumulates ACROSS groups.** Inside a single fill cascade the observable causal
  structure is one level deep, so a within-group lineage would report `max_depth` 1 forever and
  read as a measurement rather than an artifact of the unit.

`lineage_additions` returns argument sets, never nodes carrying their own depth: `LineageGraph`
derives depth from the parent it holds, and a second computation of one fact does not fail, it
just disagrees.

A negative size **raises** rather than clamping to zero; the undefined-price sentinel is dropped
rather than treated as a level.

### Corrections to the state doc

- **The claim that `LadderCalculator`, `RecurrenceCalculator` and `LineageCalculator` "expose no
  ingest method at all" was WRONG.** They expose `observe`, `observe_sequence` and `observe_node`.
  A session spent adding ingest methods would have been spent rebuilding what is there.
- **Say "unfed", never "remaining".** All sixteen sections ARE built and tested - 156 tests across
  the seven still-unfed ones alone. Verified by search: `observe_level`, `on_add`, `open_episode`,
  `open_runway`, `CandidateRecognition`, `observe_path` and `open_track` are each referenced by
  **exactly one non-test file, the module that defines them.** This wording misled Greg once.

---

## 4. THE BOX - PROBED LIVE, AND GREG WAS RIGHT ON EVERY COUNT

Greg: *"aws credentials are in git secrets."* They are - which makes them **workflow-scoped, not
session-scoped**. An interactive session resolves none at all (`NoCredentialsError`, verified), so
no Claude session can settle this from a desk. A workflow is the only path.

`.github/workflows/frankie_box_sizing_probe_20260829.yml`, run **33242769879**, succeeded:

| | recorded | Greg said | **MEASURED** |
|---|---|---|---|
| type | t3.xlarge | (larger box) | **r6i.2xlarge** |
| cores | 4 | 8 | **8** |
| memory | 16 GB | 64 GB | **61.8 GiB** |
| swap | - | required | **32.0 GiB, present** |

Also 128.2 GiB free disk, running, us-east-2b.

**Corrected at source in every LIVE record a future session would believe** -
`LIVE_TELEMETRY_S100.md`, `PLANT_MAP.md`, `NG_EXHAUSTION_OCTOBER_SHARDED_HANDOFF_20260824.md`, and
the drop-in - each as a dated correction beside the original rather than a rewrite. **The S91-S93
handoffs are deliberately untouched:** a t3.xlarge was true when they were written, and that is
the audit trail, not an error.

**One correction mattered beyond bookkeeping.** The October sharded handoff sized its workers at
*"three of four cores"* on a machine that has **eight** - a capacity assumption wrong by a factor
of two, about to be inherited.

### D56 - size up before the run, then watch

Greg: *"start with a bigger box than the 64g's. the less rich data run almost used the 64 g up so
logic says that it def won't be enough for this."* The member-first run covered **5 of 16
sections** over 4.26M groups and nearly exhausted 61.8 GiB. Sixteen sections is 3.2x that count
and the dominant term scales with it, so **~200 GiB**: `r6i.4xlarge` at 128 GiB is only 2x and
still short. **Target `r6i.8xlarge`** (32 vCPU / 256 GiB), same family so no architecture or AMI
surprise.

**Correction to something said in passing:** an EC2 instance type **cannot** be changed on the fly.
There is no live resize; the instance must stop. So the monitor is the **watch during the run**,
not the sizing decision, and "stop at a checkpoint and up it" is the fallback
`periodic_checkpointer` exists to make cheap.

**Two workflows, both built and validated:**

- `frankie_box_monitor_20260829.yml` - **LIVE, sampler installed and running.** Samples /proc every
  30s to a **capped, self-trimming** log so the monitor cannot grow into the disk it watches.
  Reports **MIN_MEM_AVAILABLE** and **PEAK_SWAP_USED** - low and high-water marks, never a mean,
  because a mean hides the moment that decides a resize. Bump its RUN MARKER for a reading.
  **A resize reboots the box and the sampler will not survive it - re-fire the monitor after.**
- `frankie_box_resize_20260829.yml` - **ARMED, NOT FIRED.** Greg authorised a bigger box; the
  specific size is an inference and 8xlarge is ~4x the current hourly rate, so it waits on his
  word. Three guards, because the stop is the destructive step: refuses on a non-EBS root (a stop
  would destroy local disks), refuses if the box is busy (verified idle, but the guard belongs in
  the workflow rather than in a session's memory of a reading), and full rollback on every failure
  path, taken from the resize that already succeeded.

---

## 5. D57 - THE STEP1 EXPOSURE QUESTION, AND THE REUSABLE LESSON

Greg: *"we def don't want step1 data exposed now."*

Measured before acting. `ng_exhaustion_step1_receipt_count_20260823` and
`ng_exhaustion_step1_oom_continue_v2_20260827` produced a run on **every push to any branch** and
failed every time (runs 100-107), despite branch filters excluding those branches.

**Cause: both files have INVALID YAML** - an embedded heredoc dedents to column 0 and breaks its
enclosing block scalar - and **GitHub creates a jobless startup-failure run to REPORT a broken
workflow, ignoring branch and paths filters.**

**So the exposure answer is reassuring and worth stating plainly: those runs had ZERO jobs.
Nothing started, nothing authenticated, no step1 data was fetched, printed or written.** The red
was a config error surfacing, not a run touching data.

Both removed from this branch (each duplicated on its home branch, which carries all 49). **The
other 47 step1 workflows were deliberately KEPT**: valid YAML, branch-filtered, and empirically
zero runs across eight pushes - deleting them would be scope-widening with test risk and no
exposure benefit. **0 of 186 workflows on this branch now fail to parse.**

**Then I made the identical mistake an hour later** in the resize workflow, caught by `bash -n`
before it ever landed. The rule, now in the drop-in: **verify a workflow by parsing the YAML,
running `bash -n` on every step, and RENDERING the remote script - not by reading it.** That same
render check caught a second real bug: a doubled backslash in a raw Python string emitted a
write-time expansion into a heredoc, so every monitor sample would have baked in one frozen
timestamp.

**Two GitHub Actions facts worth keeping:** `workflow_dispatch` returns 404 for a workflow not on
the **default** branch; and a branch's **first** push changes no file relative to its branch point,
so a paths filter matches nothing. Both are why the house pattern is a dedicated branch plus a
bumpable RUN MARKER.

---

## 6. OPEN AT CLOSE

**Waiting on Greg:**

1. **Fire the resize or pick a smaller target.** Armed, not fired. ~4x hourly rate.
2. **`extra_agent_corrected_information_and_gap_diagnoses`** - no ruling on its
   `PROVISIONAL_SHADOW`. (The four-helper layer is settled by D54: stays shadow.)
3. **`output_provider_invocation_response_receipts`** - a surface id still carrying API
   vocabulary; renaming changes `surface_inventory_hash` and the manifest.

**Build queue:**

1. **Adapters for the seven unfed sections** (4.6, 4.7, 4.10-4.12, 4.15, 4.16) on the F_LAST unit,
   building from `native_group_adapters.py` and its declared-scope pattern.
2. **Wire the adapters into `native_replay_driver`** - built and tested, but the driver does not
   call them yet.
3. **Wire the checkpointer and the execution gate into the launch workflows.**
4. **A dry run over a small slice**, eight gates passing, before anything touches the roster.
5. The shortened-session close time (the one declared gap left in `native_session`), and an
   exchange holiday calendar note for any window wider than the roster.
