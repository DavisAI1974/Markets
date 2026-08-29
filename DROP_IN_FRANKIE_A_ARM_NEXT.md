# DROP-IN BOX - FRANKIE A-ARM, NEXT SESSION

BRANCH: `chatgpt/frankie-raw-mbo-benchmark-20260828`
TIP AT HANDOFF: `e8e628e` or later - run `git log --oneline -1` and confirm.
STATUS: **NOTHING LAUNCHED.** 552 tests green (was 522). Wider `research/kalshi/tests/`
still has its **7 pre-existing failures - not yours**.

## S115 - WHAT CHANGED, AND THE ONE THING TO READ FIRST

**Read `research/kalshi/FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md` end to end.** It is
current as of this tip. Decisions D52-D57 are in the root `DECISIONS.md`.

**THE FINDING THAT MATTERS MOST.** Greg has corrected "we are not using the OpenAI API"
every session, and the reason it kept needing saying is that **the execution gate ENFORCED
the API architecture**: `validate_principal_execution` demanded `provider`,
`requested_model`, `served_model`, `principal_invocation_id` and reconciling token `usage`.
None of those exist in an agent-session run, so **the gate would have rejected a correct
Sol run and accepted only an API one.** Now file-based, matching `native_staging.py`. A
decision recorded in prose while the check demands the opposite is a decision that has not
landed - the S114 do/dont lesson, again.

**CLOSED THIS SESSION.** D52 the CME trading-day calendar is wired into `native_session`
(rule-sourced, not a table - the roster year is 2021 and the committed table starts 2025;
a shortened session REFUSES rather than answering from ordinary hours). D53 the input unit
is the **F_LAST group** - the adapter layer exists as `native_group_adapters.py` covering
4.8, 4.9, 4.13, 4.14, each verified against the real calculator. D54 no helper lanes, no
specialists. D55 **the box was live-probed**: `r6i.2xlarge`, 8 cores, 61.8 GiB, 32 GiB
swap - the recorded `t3.xlarge` was wrong and is corrected at source in four live records.

**SAY "UNFED", NEVER "REMAINING".** All sixteen sections ARE built and tested. What is
missing for 4.6, 4.7, 4.10-4.12, 4.15 and 4.16 is only the ADAPTER that constructs their
inputs - verified by search: their entry points are each referenced by exactly one non-test
file, the module that defines them. This wording already misled once.

## WHAT IS WAITING FOR GREG

1. **Fire the resize, or pick a smaller target.** `frankie_box_resize_20260829.yml` is
   built, validated and **armed but NOT fired**. Target `r6i.8xlarge` (32 vCPU / 256 GiB)
   because 5 of 16 sections nearly exhausted 62 GiB, so 16 sections needs ~200 GiB and 128
   is still short. It is roughly 4x the current hourly rate, which is why it waits. Bump
   its RUN MARKER to fire. Guards: refuses on non-EBS root, refuses if the box is busy,
   full rollback on every failure path.
2. **The memory monitor is LIVE on the box** (`frankie_box_monitor_20260829.yml`), sampling
   every 30s to a self-trimming capped log. Bump its marker for a reading. It reports
   MIN_MEM_AVAILABLE and PEAK_SWAP_USED - low/high-water marks, never a mean.
   **NOTE: a resize reboots the box and the sampler will not survive it** - re-fire the
   monitor after resizing. The resize's verify step says so too.
3. **`extra_agent_corrected_information_and_gap_diagnoses`** - still no ruling on its
   `PROVISIONAL_SHADOW`. The four-helper layer is settled by D54: stays shadow.
4. **`output_provider_invocation_response_receipts`** - a registry surface id still carrying
   API vocabulary. Renaming changes `surface_inventory_hash` and the manifest, so it needs
   Greg rather than a unilateral edit.

## THE BUILD QUEUE

1. **Adapters for the seven unfed sections**, on the F_LAST unit per D53. Build from
   `native_group_adapters.py`, which establishes the pattern and declares its scope limits
   on the value (`LADDER_SCOPE`) rather than only in prose.
2. **Wire the adapters into `native_replay_driver`** - they are built and tested but the
   driver does not call them yet.
3. **Wire the checkpointer and the execution gate into the launch workflows.**
4. **A dry run over a small slice**, eight gates passing, before anything touches the
   roster.

## A WORKFLOW RULE THIS SESSION LEARNED TWICE

A heredoc inside a YAML `run:` block must never dedent below the block's indentation. Two
step1 workflows were failing on EVERY push to EVERY branch for exactly this - GitHub emits
a jobless startup-failure run to report a broken workflow, ignoring branch and paths
filters. **Those runs had zero jobs, so no step1 data was ever exposed.** Both removed; 0
of 186 workflows now fail to parse. Then I made the identical mistake in the resize
workflow an hour later. **Verify a new workflow by parsing the YAML, running `bash -n` on
every step, and RENDERING the remote script - not by reading it.** Also: `workflow_dispatch`
404s unless the workflow is on the default branch, and a branch's first push changes no
file, so the paths filter matches nothing - bump a RUN MARKER to fire.

## 0. STOP BEFORE LAUNCH

Do not dispatch a workflow or start either arm. The decision blockers are gone, but three
build items and the compute question remain, and a launch from here still produces artifacts
that look complete and are not. Section 0 of the state doc has the item-by-item list.

## 1. FIRST THREE COMMANDS

```
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1
```

Then read `research/kalshi/FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md` end to end.

## 2. TWO SANITY CHECKS BEFORE BUILDING

```
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q
python3 research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \
  --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \
  --repo-root . --check
```

Expect **522 passed** and `"status": "CURRENT"`. Seven failures in the wider
`research/kalshi/tests/` suite are PRE-EXISTING, verified at `d5b7b51`. Not yours to fix.

## 2b. THE PROCEDURAL CORRECTION - THE MOST IMPORTANT THING IN THIS BOX

**On the first run Frankie was never called and the runner stood in for it** (Greg). Two
things allowed it: `add_finding` let the traversal author the findings report, and
`_gate_not_a_model_run` **always returned True** - it asserted the distinction instead of
checking it. A label is not a check.

Now enforced: the calculation layer produces EVIDENCE, Frankie produces FINDINGS.
`add_finding` raises. `attach_principal_findings` is the only route in and needs a named
principal, an artifact path and its hash. `controller_only` work is refused. The gate REJECTS
findings with no principal. Every result states `completion_status`.

**`native_staging.py` is how Frankie gets called** - the walk's mechanism, no API call. The
driver's `on_invoke` is gone; `stage_spawn` writes a committed request at the cutoff and
moves on. `load_principal_artifact` hard-fails on missing, malformed, wrong-evidence,
controller-only or EMPTY. **A missing artifact is never zero findings.**

## 3. WHAT CLOSED THIS SESSION

**D6a session boundary and D6b session phase - both taken from the EXCHANGE, not our tape.**
Greg's rule, now D51 in the root `DECISIONS.md`: *"we should follow what the market does and
not what our data says. we might be looking at it wrong."* A tape agrees with a wrong rule as
readily as a right one, because it cannot falsify what it was used to derive.

- CME Globex energy: Sun-Fri 17:00-16:00 CT, 60-minute halt at 16:00 CT **Mon-Fri only**.
- CME **trade date** begins 17:00 CT on the previous calendar day. This makes the S104 Sunday
  fold fall out of the definition instead of being hand-coded.
- NG settlement window is **14:28:00-14:30:00 Eastern** (NYMEX Energy Futures Daily Settlement
  Procedure), giving PRE_OPEN / PRE_SETTLEMENT / SETTLEMENT / POST_SETTLEMENT / POST_CLOSE.
- Written in exchange LOCAL time. A literal 21:00 UTC constant reproduces this roster and is
  silently one hour wrong from 2021-11-07.
- Friday's close is a ~49h weekly gap, not a 1h daily one. Different censoring event.

**D5:** no clustering in this run.

**`on_invoke` (Greg):** Sol runs as an agent session over committed files exactly as the
blind/refine group runs did - **no API call**. Decided AND built: `on_invoke` is gone,
replaced by `stage_spawn`. See section 2b.

**The driver RUNS** - a pass executes end to end and finalizes ACCEPTED, which it had never
done. 13 tests where it had none.

**The D6 assignment is wired as a RECONCILIATION, not a hand-off.** The traversal reports what
it keyed on, `AssignmentLedger` recomputes from the group's own `ts_event_ns`, and
`denominators_strata_and_censoring` fails on disagreement. A field-level check cannot catch a
constant phase - it is present, typed and plausible.

## 4. THREE DEFECTS FOUND AND FIXED, RECORDED BECAUSE THE PATTERN MATTERS

1. **`SessionRule.classify` offered only `recv_ns`** - would have keyed session membership on
   the feed's serialization rather than on the market. Now takes both clocks, decides on
   `event_ns`.
2. **`in_halt_window` contradicted `session_phase`** - read True at 16:30 CT on a Saturday.
   Two fields in one dict disagreeing about the same fact: the S109 `session_b_share` shape.
   Removed, not reconciled.
3. **The driver held a second family vocabulary** - `_family_id` was the bare action string
   while the member-first roster run keys on `candidate_family_id`. Nothing would have failed;
   the strata would just have been cut differently from the run it must reconcile against.

## 5. OPEN

**Build:**
- **Sections 4.6-4.16 are unfed** and this is **NOT mechanical**. `LadderCalculator`,
  `RecurrenceCalculator` and `LineageCalculator` expose no ingest method; `Absorption.score`,
  `Dipole.observe_path` and `Exhaustion.enter_phase` take constructed domain objects. The
  contract specifies the CALCULATION, not the input event - 4.10 says "construct a runway for
  each candidate" without defining a candidate. **These are research design decisions. Take
  them to Greg; build from `describe_structure` as the precedent.**
- Wire the checkpointer and the execution gate into the launch workflows.
- Wire an exchange holiday calendar - `native_session` consults none. The roster spans none,
  so this is a declared gap, not a live bug.

**Compute - unresolved:** the A-arm workflows dispatch nothing (zero `ssm`/`ec2`/`INSTANCE_ID`);
the recorded box was a t3.xlarge, 4 vCPU / 16 GB, unverified - that session had no AWS
credentials. 5 of 16 sections previously took 2,985s and made a 1.5 GB file.

**Needs Greg - two `provisional` labels NOT changed** (the findings status WAS dropped):
- `PROVISIONAL_SHADOW`, a routing policy on 2 registry layers, both `model_visible: False`.
  Making them permanent lets Frankie SEE them and changes the manifest and surface hash.
- "provisional strategy hypotheses" in the RT mission and discovery addendum - `ALWAYS_LOAD`
  instructions about what Frankie PRODUCES; editing them changes Frankie's job.

**Parked:** D3/`ALLOWED_BOSSES`, native-build proof modes.

## 6. DO NOT TIDY

Superseded values in the review findings, historical handoffs and A-memory prior-run reports
are deliberate records. The warmup-scoped capsule proposal stays unregistered.

## 7. THE RULE THAT MATTERS MOST

Change a decision -> update `FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md` in the same commit.
