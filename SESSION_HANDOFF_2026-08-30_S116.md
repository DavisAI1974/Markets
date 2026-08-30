# SESSION HANDOFF - S116, 2026-08-30 - THE WORK WAS ALREADY BUILT

**Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. 552 -> 613 tests green. NOTHING
LAUNCHED. Decisions 57 -> 61.** No group run, no merge, no launch.

## The session in one paragraph

Two things happened. First, a full **data-drop audit and restoration** across the ingest,
traversal and output layers, forced by Greg saying the same thing for what he estimated was the
thirtieth time: *"we have all this data for a reason. do not drop any of it without discussing
with me first. make that a rule."* Fifty-five confirmed drops found, every one restored. Second,
and larger: Greg asked *"this should have already been built in some capacity for the exhaustion
prediction part. is this related?"* **It was.** Four estimand proposals written earlier in the
session were reinventing a frozen, hash-bound vocabulary built between 2026-08-16 and
2026-08-25. All four are withdrawn, and the build plan for the next session changed as a result.

## 1. D60 - NOTHING IS DROPPED WITHOUT DISCUSSING IT FIRST

Greg, on why it is a rule and not a preference: *"this is the problem that i have been fighting
the whole time that things are dropped for whatever reason and not discussed and then we find
out we have to rerun because it was important"*, and *"we're constantly having to go back and
audit things over and over."* Then, decisively: *"i don't care about memory. restore every
piece... let him figure out what he uses but he has to see everything."*

**A row, field, message or observable that reaches our code is USED, or RETAINED and counted, or
REFUSED loudly. Never silently ignored. Memory is explicitly not a reason.** The one exception is
narrow: *"if a row is truly blank and is measuring nothing then you can leave it off."*

**The instances, all found the day the rule was written and all now closed:**

* **`native_rt_book.ReplayBook` silently ignored four row classes `InstrumentBook` acts on** - a
  sentinel or absent price on an A/M, the `F_TOB` side wipe, `order_id == 0`, a modify on side
  `N` - and kept no anomaly counters at all. A code review with a differential harness proved
  each one silently moved a `view` number. The book now MIRRORS even where mirroring looks
  wrong, and counts what it cannot act on.
* **The driver discarded the adapter's legacy MBP-10 rows** (`frame, _legacy = ...`), which carry
  the projected ten-level depth and are the only source for a `CAUSAL_STREAM_REQUIRED` registry
  group. **My first fix merely COUNTED them, reasoning that ~70 fields across 4.26M groups was a
  memory decision for Greg. That reasoning was itself the defect.** Now retained verbatim.
* **The two exact-evidence layers of section 5 emitted COUNTS, not rows** - and the gate that
  exists to guarantee exact members beneath every summary was satisfied by an integer being
  greater than zero. Nine call sites discarded returned lifecycle rows, the only emission point a
  censored lifecycle ever had.
* **`describe_structure` computes ~18 fields and the driver kept one truncated hash**, including
  `discovery_status`, the open-world novelty signal. A 20-hex hash cannot be inverted.
* **`AssignmentLedger` used one capped list as both sample and count**, so twenty mismatches and
  twenty million both reported 20 - and the denominators gate printed that number.
* **`summarized_observations` read only `"n"`**, which ratio and survival measures do not carry,
  so every one of them counted as zero in the receipt that is gate 7's evidence.
* Plus: `sum_of_squares` accumulated and never emitted; `at_risk_table` computed inside a gate
  and discarded; `population_report` never called; `ladder_scope` documented as travelling on the
  value and attached to nothing; `native_staging` canonicalizing with `default=str`.

**D61 - restore by WRAPPING, never by editing.** The V4 MBO adapter is hash-locked. Restoring its
drops in place **broke six supply-chain locks in one commit**. Reverted; `FullCaptureAdapter`
subclasses it and keeps what it discards while the locked file stays byte-identical. It restores
the per-record `ApplyEffect` (bound to `_`, so no per-record book effect reached the traversal at
all - `top_before_price_raw` and `removed` had **zero readers anywhere**), the reconstructed FIFO
queue, the book below level ten, per-side event counts, touch quantity for T/F/M, and every
anomaly magnitude. The resume path is closed too, where a fallback would have been invisible.

## 2. THE PRIOR WORK - AND WHY THE BUILD PLAN CHANGED

Read `research/kalshi/FRANKIE_A_ARM_PRIOR_WORK_RECOVERY_20260829.md` in full.

**The frozen program already defines almost everything the proposals invented.** t0 is a
**dipole flow spike**, not a price-level event, and price never selects or orients it. PRIOR /
T0 / H+N exists by name as `TIMING_LADDER`, settled 2026-08-19/20, with the classes strictly
ORDERED. A call is a **persistence run on signed flow** with two timestamps, structural onset and
causal confirmation. SAME/FLIP means **polarity versus the latest predecessor**, frozen with
committed counts of 1,546 FLIP / 1,883 SAME of 3,429. The mirror is the **side-swapped side
string**, already computed for every member.

**`t` IS A PRICE TICK.** `3t/5t/8t/13t` are ZigZag reversal thresholds; 358/993/1802/4386 are the
median leg durations in SECONDS they produce. A scale ladder, not a horizon grid. Fibonacci is
coincidental - 2t was dropped after a five-point sweep.

**Greg's duration ruling restates a correction frozen on 2026-08-18**: *"Exhaustion is being
studied as a duration / remaining-runway signal, not as a direction predictor."* And the frozen
program solves the clock problem better than my revision did - it keeps absolute-second horizons
but anchors them on the **dynamic episode endpoint, "never t0+60 by fiat"**, which keeps them
comparable across events. The fix was the ANCHOR, not abolition.

**THE FINDING THAT CHANGES THE PLAN.** The built candidate is a 1-second flow event; the A-arm's
unit is the nanosecond F_LAST group - **3,429 frozen events against 4.26M groups.** The registry
requires the bridge (`derived_roll20_and_dipole_state`, `legacy_per_second_roll20`) as
`CAUSAL_STREAM_REQUIRED`, and **no code in the benchmark computes roll20 or any dipole from the
MBO stream.** That is why 4.10, 4.11 and 4.12 have nothing to feed them. **The missing layer is
the substrate, not six adapters.**

**Corrections to my own claims, recorded because they were stated confidently:**
`ng_exhaustion_v4_exact_candidate_freeze.py` is a **CI release freeze** carrying git SHAs, not a
market candidate definition. And **there is no event clock in the built work** - the only
`event_clock` is a boolean availability flag; built durations are seconds, the new modules' are
nanoseconds, so on Greg's rule both are guilty.

**`PHASE_INDEX` scores 0 of 11** against the built corpus and four of its names are reused with a
different referent, which is worse than absence. Its provenance is one prose line in the
2026-08-28 mission doc. **Two things ARE right and must stay:** `SEED_STATES` carries P/O/S/X
correctly and `RecognitionLabel` carries PRIOR/T0/H+N correctly.

## 3. BUILT AND KEPT

* **`native_rt_book.ReplayBook`** - the RT view on Greg's ruling *"we should see it like it would
  be seen in rt"*. Advanced action by action; a differential suite drives it against
  `InstrumentBook` in lockstep over 12,024 records with zero divergence, and mutation-tests its
  own comparator so a harness that compares nothing cannot pass.
* **`native_full_capture_adapter.FullCaptureAdapter`** - D61.
* The whole D60 restoration across ingest, traversal and output.

## 4. LAUNCH READINESS - MEASURED

Sections fed by the driver: **clocks, coverage, and a replenishment clock advance.** Ten receive
zero. Adapters wired: **0**. Execution gate referenced by any non-test file: **0**. Workflows
dispatching the driver: **0**. Resize armed at `r6i.4xlarge` / 128 GiB, not fired.

## 5. THE LESSON THAT COST THE MOST

**I assumed wiring existed because components did, and assumed nothing existed because the
contract did not define it. Both are the same error.** Verify by EXECUTION, and search the prior
corpus BEFORE proposing a definition.
