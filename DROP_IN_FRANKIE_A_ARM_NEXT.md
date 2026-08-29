# DROP-IN BOX - FRANKIE A-ARM, NEXT SESSION

BRANCH: `chatgpt/frankie-raw-mbo-benchmark-20260828`
TIP AT HANDOFF: `bca3a53` or later - run `git log --oneline -1` and confirm it's that or later.
STATUS: NOTHING LAUNCHED. Calculation layer built. **D6 and D5 closed. The driver RUNS.
The runner can no longer stand in for Frankie, and the spawn contract that calls him
exists.** Sections 4.6-4.16 still unfed. 522 tests green.

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
the recorded box is a t3.xlarge, 4 vCPU / 16 GB, unverified - this session had no AWS
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
