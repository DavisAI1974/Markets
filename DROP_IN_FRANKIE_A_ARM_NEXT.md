# DROP-IN BOX - FRANKIE A-ARM

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies month-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

**BRANCH:** `chatgpt/frankie-raw-mbo-benchmark-20260828` **TIP:** `d3b6744` or later.
**STATUS: NOTHING LAUNCHED. The roll20 substrate is BUILT, FED and RECONCILED.**
653 tests in the package; `research/kalshi/tests/` has 7 PRE-EXISTING failures - not regressions.

---

## RESOLVED BY GREG, 2026-08-30: NO HELPERS OR SPECIALISTS

The canonical procedure mandates the **four-helper paired-lane architecture** (recurrence=CPU0,
extension=CPU1, timing=CPU2, context=CPU3; *"Frankie is call five and starts only after all four
helpers finish"*, step 11, plus the role-to-CPU mapping in the permanent invariants). It was adopted
2026-08-24. **D54 (S115) retires it, and Greg reaffirmed it directly when this handoff raised the
conflict: "No helpers or specialists."**

**The ruling, applied:**

* **Two roles only** - `REAL_TIME_FRANKIE` and `FORECASTER_FRANKIE`. A helper is a **tool invocation
  inside a role**, never a parallel lane with its own knowledge profile or its own output, and the role
  a helper is called under is selectable (D54, verbatim: *"we aren't doing the helpers or the
  specialists anymore. Rt and forecaster can call one as part of their tools and there's options as to
  the role."*).
* **The procedure's step 11 four-helper concurrency and its role-to-CPU mapping DO NOT APPLY to the A
  arms.** This is the "explicitly approved exception" the procedure's header contemplates - raised, not
  silently forked, and now ruled.
* **The five walk specialists (`mbo_specialist_{A..E}.md`) are not used by the A arms.**

**Consequence that is now unblocked, and it is still a registry change rather than a code edit:** D59
records that both `extra_agent_*` layers are `STATIC_REQUIRED_INPUT` and model-visible, so Frankie
would READ the dead four-helper architecture as a required input on every run - *"showing Frankie a
dead architecture is worse than showing nothing."* Moving either layer changes
`EXPECTED_POLICY_COUNTS`, `EXPECTED_ARM_LAYER_COUNTS`, `EXPECTED_LAYER_ID_SET_SHA256`, the surface
inventory hash and the manifest. **Greg's ruling settles the architecture question; whether to spend
those hash changes now, and on which layer, is the remaining half of D59.**

---

## 0. READ ORDER - THIS IS THE FIX FOR WHAT WENT WRONG LAST SESSION

Three sessions ran without opening the two documents that actually govern this work, and the cost was
real: committed code was deleted against the contract's own wording. **Read these before any build.**

| # | File | Why |
|---|---|---|
| 1 | `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md` | `BINDING_CURRENT_MISSION`, `ALWAYS_LOAD`, sha256-pinned in the knowledge manifest. Fixes the evidence surface and the sealed wall. |
| 2 | `research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md` | `BINDING_CURRENT_CALCULATION_CONTRACT`. Sections 4.1-4.16 ARE the vocabulary. |
| 3 | `research/kalshi/NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` | 193 lines. **93 of the registry's 105 layers name it as their source.** It says which feeds exist. |
| 4 | `research/kalshi/FRANKIE_A_ARM_PRELAUNCH_STATE_20260829.md` | State record and file map. Opens with STOP BEFORE LAUNCH. |
| 5 | `DECISIONS.md` D50-D62 | The A-arm decisions. |
| 6 | `research/kalshi/FRANKIE_A_ARM_ALREADY_BUILT_AUDIT_20260830.md` | What was claimed missing and actually exists. |

**THE METHOD RULE, learned three times at cost: absence of a string is not absence of a capability.**
Search for what a capability must CONSUME AND PRODUCE, never for its name. `roll20` was declared
missing while three implementations existed; the event clock was declared missing while four modules
existed, because both searches were for the name.

## 1. FIRST COMMANDS

```
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1                                                  # 990d15f or later
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q  # expect 653
python3 -m pytest research/kalshi/tests/ -q                            # expect 7 PRE-EXISTING failures
```

## 2. CORRECTIONS TO THE PREVIOUS BOX - all five were acted on, all five were wrong

* **`PHASE_ORDER` / `PHASE_INDEX` are CONTRACT VOCABULARY. Do not delete them.** Contract 4.10 reads
  *"searched coverage, precursor, prebirth state, first deviation, birth/T0, transitions, inflection,
  persistence, recurrence, extension, completion/reversal, and censored/open status."* The old box said
  their provenance was one prose line. It is section 4.10 of an `ALWAYS_LOAD` document.
* **4.12's `SAME`/`FLIP` is CONTRACT VOCABULARY.** 4.12: *"`SAME` and `FLIP` orientations never pool."*
* **The exhaustion program exists and was measured.** 3,429 frozen events, families A=3,235/B=72/C=122,
  classifier SHA `698b956f...`, `mismatches 0 of 3429`, `FIXED_3429_DO_NOT_REOPEN`.
* **The event clock exists.** `research/kalshi/ng_exhaustion_v4_causal_clock.py` is a causal
  discovery-clock contract that fails closed when retrospective `t0` is substituted for a causal mark,
  plus a runway clock, a live clock and a batch proof.
* **`roll20` existed three ways before this session** - the step1 census columns, the frozen
  `flow_series`/`detect_dipole_peaks`, and a live streaming `AggressorRoll20Feed`.

## 3. WHAT LANDED THIS SESSION

* **`native_roll20.py`** - the feed inventory section 8 recreation of legacy per-second `roll20` from
  the native stream. Opens no file; a structural test asserts the source text contains no file access.
* **Reconciled two ways.** Bit-exact against the frozen `flow_series` over 400 seconds, and - the one
  that matters - against **the frozen `SecondAggregator` itself** on identical legacy rows, across the
  edge cases and a randomised 60-second stream. The harness is mutation-tested: three deliberate wrong
  rules each produce a named exact disagreement.
* **Fed by the traversal** at group close, from rows already retained under D60, **at the group's
  second** - the frozen census assigns every legacy row in a group to that group's second, and per-row
  binning splits a boundary-straddling group.
* **The clock is declared, never defaulted.** `SecondBinner` refuses construction without a named
  clock; the crosswalk hash changes with it.

## 4. THE CRITICAL PATH TO A RUN - do these in order

Each is small, each leaves the tree green, each is verified by EXECUTION.

**T1 - Wire the four built adapters.** `native_group_adapters` is imported by nothing but its own test.
Four call sites in `native_replay_driver._on_group`, beside the existing `clocks.observe(row)`:
`occurrences` -> `native_recurrence.observe_sequence`; `ladder_transitions` -> `native_ladder.observe`;
`runway_pressure_fields` -> `native_absorption`'s `RunwayPressure`; `lineage_additions` ->
`native_lineage.observe_node`. All four are group-local and D53-consistent.
*Accept:* 4.8, 4.9, 4.13 and 4.14 report non-zero strata after a driver pass. *Verify:* a driver test
asserting counts that can only appear if rows arrived. *Scope:* S. *Depends:* none.

**T2 - Wire the execution gate into the launcher.** `corrected_a_arm_execution_gate_20260828` is
referenced by itself and its test and nothing else. An unreferenced gate is not a gate.
*Accept:* a non-test file references it and it runs in the dry run. *Scope:* S. *Depends:* none.

**T3 - Put the checkpointer on the launch path.** It is imported by the driver, and no workflow
dispatches the driver. D58 makes this a **precondition of the resize**, not an independent item.
*Accept:* a save point is written during a slice run. *Scope:* S. *Depends:* T2.

**T4 - Make a launch workflow actually dispatch compute. NEEDS GREG (spend).** Measured: both
`frankie_a_clean_rt_native_launch_20260828.yml` and its A-memory twin contain **zero** references to
`ssm`, `ec2`, `send-command` or `INSTANCE_ID`. They stage and stop. *Scope:* M. *Depends:* T3.

**T5 - Dry run over a small slice; the contract's eight section 6 gates pass.** Prelaunch section 0
item 9 requires this before anything touches the full roster. *Scope:* M. *Depends:* T4.

**CHECKPOINT after T1-T3:** package suite green, wider suite still exactly 7 pre-existing failures, and
every section T1 touched reports data. Then stop and show Greg before T4.

## 5. THE TWO OPEN RULINGS - parallel, they block only 4.10/4.11/4.12

* **`SAME`/`FLIP` carries three readings.** Contract 4.12 (a stratum axis); the frozen corpus (polarity
  vs the latest predecessor, 1,546 FLIP / 1,883 SAME of 3,429, gated in four files); and
  `FRANKIE_A_ARM_PRELAUNCH_STATE:464-467` (*"a MIRROR relationship defined nowhere in the tree"*).
  Contract section 3 lists the stratifier as *"side or mirror orientation"* (:65) and forbids averaging
  across *"mirror orientations"* (:71), so one-axis and two-axis both read defensibly. **Nothing is
  pinned; `native_mirror` deliberately makes no claim.** Moot until something feeds
  `DipoleStage.orientation`, which has no producer.
* **4.10's runway identity is per-group.** `GroupContext.candidate_id` is per-group by D53, so every
  runway is one group long and phases can never advance. **This is the real blocker on 4.10 and
  redefining it answers D62's open unit question**, which is Greg's. Do not decide it in code.

## 6. DO NOT

* **Never read the October Step-1 seconds.** The mission: *"Never use reduced seconds rows,
  `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`, MBP/top-10, Step-1-derived input... Keep Step-1 and the
  answer/reveal wall sealed."* Feed inventory section 14 seals them as `SEALED_TARGET_ANSWER`.
  Recreating the surface from native is REQUIRED (section 8); reading that file voids the run.
* **Never edit `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`** - hash-locked; editing it
  broke six supply-chain locks in one commit (D61). Restore by wrapping.
* **D60: nothing dropped without discussing first.** Memory is explicitly not a reason. The one
  exception is a row shown from itself to be truly blank.
* **Do not launch, dispatch a workflow, or invoke a model** without walking prelaunch section 0 with
  Greg first.
* **Do not treat the 7 wider-suite failures as regressions.** They fail at `d5b7b51` too.
* **Do not apply `RUN_SOP.md`, `PLANT_MAP.md`, `QC_CHECKLIST.md` or `plant_status.py` here.** Greg,
  2026-08-30: *"The sop and plant map are something different... It should have no bearing on this
  stuff."* They govern the group-walk program.
* **Do not touch `tasks/plan.md` or `tasks/todo.md`** - different work, 54 unchecked tasks.

## 7. HANDOFF COMPLETION CHECKLIST - supplied and missing, stated honestly

**Supplied:** target branch and tip; focused test nodes and expected counts; raw-manifest identity
(`raw_mbo_source_manifest`, 5,667,689 records over 2021-10-01/03/04/05, manifest SHA
`a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`); the sealed-wall declaration; the
declared exception in the conflict notice above.

**MISSING, and a run cannot be authorized without them:** the month descriptor path and hash, the
prior-learning declaration and receipt hashes, the expected implementation/marker ancestry, the
artifact namespace, the canary size, the progress source, and the isolated stop command. The canonical
procedure requires every one. **This is a build-and-wire handoff, not a launch authorization.**
