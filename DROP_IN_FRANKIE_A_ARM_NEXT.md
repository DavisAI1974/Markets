# DROP-IN BOX - FRANKIE A-ARM

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies month-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

**BRANCH:** `chatgpt/frankie-raw-mbo-benchmark-20260828` **TIP:** `88eb1e9` or later.
**STATUS: T1-T4 DONE AND PUSHED. THE LAUNCH PATH EXISTS AND RUNS.** The roll20 substrate is
BUILT, FED and RECONCILED. **688 tests** in the package (was 653); `research/kalshi/tests/`
still has the same 7 PRE-EXISTING failures - not regressions, they fail at `d5b7b51` too.

**WHAT CHANGED 2026-08-30, and it is the whole critical path:**

| T | Was | Now |
|---|---|---|
| T1 | 4 built group adapters called by nothing | **WIRED.** 4.8, 4.9, 4.13, 4.14 fed; `sections_fed` emitted so an empty ingest is visible, not inferred |
| T2 | execution gate referenced only by its own test | **ON THE LAUNCH PATH.** 3 gates in order, real evidence hashes, fail closed |
| T3 | checkpointer imported by a driver nothing dispatched | **ON THE LAUNCH PATH.** save points written during a slice |
| T4 | both workflows staged and stopped, 0 compute refs | **DISPATCHING.** 12 refs each; canary on the runner, full roster on the box over SSM |
| T5 | never run | **canary green locally; first real-data run 33300298768 correctly REJECTED - see 5b** |
| D59 | half open | **CLOSED (D64).** Four helpers out of every model-visible surface |
| D62 | open, needed Greg | **CLOSED as D66.** Both unit levels, RT-causal |
| box | resize armed at 128 GiB | **D65: no resize needed.** 128 GiB was undersized; streaming makes 61.8 GiB ample |

**704 tests** in the package. **Registry is 99 layers, not 105** - D64 removed six.

**`research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py` is the entrypoint.** T2,
T3 and T5 were never three problems - they were one missing module that ran the built pieces
in order. It gates, traverses, checkpoints, finalizes, and **calls no model**: at a cutoff it
stages a committed request and moves on. Zero HTTP or provider imports on the whole path.

**THE ONE THING THAT STILL NEEDS GREG: `mode=full`.** A push runs the bounded canary on the
runner only. The full roster on the box (`i-08cee7171c0a76a04`, SSM) is reachable ONLY by an
explicit `workflow_dispatch` with `mode=full`, and a test asserts BOTH limbs of that guard.
Starting the box is a spend and D58 leaves the sizing decision with Greg.

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

**AND THE REGISTRY CHANGE IS NOW MADE (D64, Greg 2026-08-30):** *"get any mention of the 4
helpers out. He can call with different persona options as part of his tools. We've covered
this more than once."* Six layer identities removed - the carryforward helper-architecture
layer, the whole `helper_role_configuration` group of four scouts, and
`output_helper_evidence_movie`. Union **105 -> 99**, arms **102/104 -> 96/98**,
`STATIC_REQUIRED_INPUT` **24 -> 19**, `APPEND_ONLY_OUTPUT` **11 -> 10**, concrete layers
**97 -> 91** against a floor of 90, new `EXPECTED_LAYER_ID_SET_SHA256` and `registry_sha256`,
six surfaces out of the execution gate.

**NOTHING SOURCE-LEVEL WAS DROPPED, which is what makes it D60-clean.** The removed layer
named exactly the same three V3 files as `extra_agent_corrected_information_and_gap_diagnoses`,
which stays required and model-visible, and **those files contain no helper text at all** -
measured, zero matches. The architecture lived in a layer DESCRIPTION and in feed-inventory
section 10, never in the evidence. What was removed is the INSTRUCTION to read those files as
a helper architecture. Feed inventory section 10 is retired in place (number kept, so every
cross-reference still resolves) and the canonical procedure is at **version 2**.

**D59's other half is untouched and still open:** whether
`extra_agent_corrected_information_and_gap_diagnoses` itself stays a required, model-visible
input is a different question and was not asked.

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
git log --oneline -1                                                  # 4266a32 or later
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

## 4. THE CRITICAL PATH - T1 THROUGH T5, ALL DONE 2026-08-30

Greg: *"We have to get all 5 t's done. This isn't a min build to get this running. We have to
get the complete thing done for the a's."* Every one is verified by EXECUTION, not by reading.

**T1 - the four built adapters are WIRED.** `NativeReplayDriver._feed_sections` calls all four
on the D53 unit from ONE `GroupContext` built off the canonical `candidate_family_id`. Every
return value is retained as a lifecycle row - an average with no member beneath it is what
section 6 rejects. `sections_fed` is emitted beside the measures so an empty ingest is VISIBLE
rather than inferred from zero strata.
*Three things wiring settled that reading had not:* 4.13's graph needed an owner (the driver
holds it and rebuilds it at every continuity boundary, or depth would chain across the halt
that censors every other section); nodes are observed at the BOUNDARY with a terminal status,
not at creation, because `exited_recv_ns` is set by a CHILD arriving and observing early would
report every node `OPEN` with no duration; and `lineage_additions` parented on `ord-0` for any
group opening on a row with no order id - **it would have killed the traversal on real tape at
the first such group.**

**T2 + T3 + T5 were ONE missing thing: a launch entrypoint.**
**`research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py`.** The gate, the
checkpointer and the driver were each built and each wired to nothing because no module ran
them in order. Three gates, in order, failing closed:
1. `validate_registry` - layer identities, policy counts, arm counts, sealed set.
2. `validate_pre_call_receipt` - every layer with the status its policy demands and a REAL
   evidence hash over the declared paths AND their bytes. **99 layers, 75 required for A-clean
   and 77 for A-memory** (the D2 asymmetry, visible in the receipt), nine-layer wall SEALED.
3. `validate_rt_surface_inventory` - the same registry in the gate's own vocabulary, **91
   surfaces**, re-proving the wall from a SECOND object. Two objects over one registry on
   purpose: a field-level check cannot catch a wrong-but-well-formed input.

**It calls no model.** At a cutoff it stages a committed request and moves on. **Zero HTTP or
provider imports on the whole path** - `SpawnStager` writes a JSON file, it is not an API
client, and a test pins that staging happens and nothing is invoked.

**T4 - both workflows DISPATCH COMPUTE.** Measured: 0 references to `ssm`/`send-command`/
`INSTANCE_ID`/the launcher before, **12 each** now.
* **`canary`, the default and what a push runs:** a bounded slice of the real hash-bound
  roster on the runner. Default **50,000 records** - deliberately small, because D60 retains
  every legacy, member and lifecycle row IN MEMORY and nobody has measured what sixteen fed
  sections cost per record. Raise it once there is a curve.
* **`full`:** the whole roster on the box over SSM. **Explicit `workflow_dispatch` with
  `mode=full` ONLY** - a push can never reach it, and the test asserts BOTH limbs, because
  `inputs.mode == 'full'` alone is true on a push where `inputs` is empty. **This is the one
  remaining Greg decision: it is a spend, and D58 leaves sizing with him.**

**T5 - the dry run.** Green locally over a supplied record stream: ACCEPTED, no failed gates,
save points written, spawn requests staged, `completion_status: EVIDENCE_ONLY`. First
real-data canary: run **33300298768**.

**THE DECLARED GAP:** `native_records`, the DBN decode, is the one part of the launch path the
package tests do not cover - AWS credentials are GitHub-secret scoped so no interactive session
can read the roster. It is covered by the workflow canary and by nothing here. Stated rather
than papered over.

**D57 HAPPENED AGAIN AND `bash -n` CAUGHT IT.** The canary summary began as a heredoc nested
inside the report step's brace group, putting `PY` at a non-zero column where bash never sees
it. Now its own step. Both workflows are verified by parsing the YAML, `bash -n` on every
`run:` block, and `ast.parse` on every embedded Python heredoc.

## 5. THE RULINGS ARE MADE - D62 IS CLOSED AS D66, AND THE BOX IS SETTLED AS D65

**D66 (Greg, ruling D62): BOTH UNIT LEVELS, AND FRANKIE SEES IT AS WE WOULD IN RT.** Verbatim:
*"I don't want to limit that just on our wrong coding or assumptions. It should see that as we
would in rt."*

* **Groups are the MEMBER unit** - 4.1-4.9, 4.13-4.15. The four fed in T1 (4.8, 4.9, 4.13,
  4.14) are exactly the group-shaped ones.
* **Dipole flow events are the CANDIDATE unit** - 4.10, 4.11, 4.12, 4.16, exactly the four
  recorded as blocked. **That split was never designed; it fell out of which sections need an
  event with a before and an after**, which is the evidence for the ruling.
* D53's group unit stays correct for what it was chosen for. Nothing built is discarded.

**THE RT CONSTRAINT DISQUALIFIES PART OF THE FROZEN DETECTOR, MEASURED - do not port it
verbatim:**
* `ng_exhaustion_chain_canonical_table_20260817.py:194-198` sets `day_thresholds[d] =
  quantile(|roll20| over the WHOLE DAY, PEAK_Q)`. **The bar for 09:00 is set using 15:00's
  data. That is hindsight and it is not RT-legal.** The A-arm detector needs a trailing causal
  threshold.
* `LOCAL_RADIUS = 5`: a spike at `t` is only KNOWABLE at `t+5`. A lawful availability delay,
  not a violation - but stamp it at `t+5` or 4.11's PRIOR/T0/H+N arithmetic is wrong at the root.
* `endpoint()` walks FORWARD. An outcome, never available at the decision point.

**DECLARED NOW RATHER THAN DISCOVERED LATER: the A-arm event set will NOT equal the frozen
3,429.** A causal bar finds a different set than a hindsight bar. Correct behaviour to declare,
not to reconcile away.

**The substrate already exists:** `native_roll20.SecondBinner.series()` yields the per-second
buy/sell arrays and `roll20()` builds the rolling series - precisely `detect_week_events`'
input. This is porting a frozen detector onto a substrate we have, not a rewrite.

**D65: THE BOX IS SETTLED AND NEEDS NO RESIZE.** Peak RSS (`VmHWM`, isolated processes):

| | MiB per 1k groups | full roster | rec/s |
|---|---|---|---|
| in-RAM 20k / 60k | 33.95 / 33.00 | **137-141 GiB** | 1,752 / 1,486 |
| streamed 20k / 60k | 2.49 / 1.59 | **6.6-10.3 GiB** | 1,777 / 1,772 |

**D56/D58 are superseded: `r6i.4xlarge` at 128 GiB was UNDERSIZED, not merely unfired** - the
in-RAM path needs ~137 GiB. Streaming makes the current `r6i.2xlarge` (61.8 GiB) roughly six
times oversized, and throughput is unchanged or better. **Do not fire the resize.**

## 5b. WHAT IS LEFT TO BUILD - SIX ADAPTERS, AND WE ARE NOT DONE

Greg: *"Sounds like we aren't done building."* Correct. **The T-list wired what EXISTED; it did
not build what is missing.** Say it that way.

| section | state |
|---|---|
| 4.6 queue | **not built.** No invention needed - `native_rt_book.ReplayBook` supplies the mandatory `book_view`, advanced action by action |
| 4.7 replenishment | **half built.** Horizon maturation is fed; the OBSERVATION half is missing. One declared choice: the tick neighbourhood separating `SAME_PRICE` from `NEIGHBORING_PRICE` |
| 4.10 / 4.11 / 4.12 / 4.16 | **not built.** Were blocked on the unit ruling; **D66 unblocks all four** |
| 4.15 discovery | **out of this run by D5 (Greg).** Not skipped - building it would add an OBLIGATION, turning `_gate_determinism` from a free pass into a `freeze()`-before-`finalize()` requirement |

**Order:** the causal detector first (it is the unit the other four hang off), then
4.10/4.11/4.12/4.16 on it, then 4.6 and 4.7 which need nothing from anyone, then the
slice-boundary bug, then ONE canary.

**THE OPEN BUG, and it is why the first real canary was correctly REJECTED.** Run 33300298768:
50,000 records, 40,241 groups, all four fed sections reporting real data, 2 save points,
`EVIDENCE_ONLY` - and `failed_gates: ["exact_once_coverage"]`. `_gate_coverage` requires
`coverage.records_seen == identity.total_mbo_records`; `coverage.records_seen` counts records
assigned to CLOSED groups while the identity carried the raw records FED. **A bounded slice
that cuts mid-group can never satisfy that equality.** The gate is right; the launcher is
wrong. Fix: end the slice on a group boundary and declare the records actually closed.

**AND A BUG IN THE T4 DISPATCH THAT HAS NEVER FIRED.** Real data ran at **200 rec/s** on the
runner, so the full roster is ~7.9h there and ~4-5h on the box. The SSM step sends
`--timeout-seconds 3600` and waits 2,400 x 5s = 200 minutes. **Both are shorter than the run.**
`mode=full` must become fire-and-return with the monitor watching, not dispatch-and-wait,
before it is ever used.

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
