> # SUPERSEDED 2026-08-30 by `DROP_IN_FRANKIE_A_ARM_NEXT.md`. KEPT AS THE RECORD, NOT DELETED.
>
> Retained because a superseded value is a deliberate record, and because four of its factual
> claims were acted on and turned out to be wrong - that is the evidence for why the read
> order changed. Specifically: section 4's instruction to delete `PHASE_ORDER`/`PHASE_INDEX`
> and the 4.12 `SAME`/`FLIP` definition was WRONG - the calculation contract lists both
> verbatim at 4.10 and 4.12 - and section 2's "no code computes roll20 or any dipole" was
> true of this package only, while three implementations existed elsewhere.
>
> Do not build from this file.

# DROP-IN BOX - FRANKIE A-ARM, NEXT SESSION

**BRANCH:** `chatgpt/frankie-raw-mbo-benchmark-20260828`
**TIP AT HANDOFF:** run `git log --oneline -1` and confirm it is `1eb116a` or later.
**STATUS: NOTHING LAUNCHED, AND THE BUILD PLAN CHANGED.** 613 tests green (was 552).
**START A FRESH SESSION. Do not carry the previous one's proposals forward - they are withdrawn.**

## 0. READ THIS FIRST, BEFORE ANY BUILD

`research/kalshi/FRANKIE_A_ARM_PRIOR_WORK_RECOVERY_20260829.md`.

The previous session wrote four estimand proposals for sections 4.10, 4.11, 4.12 and 4.16 on
the premise that the calculation contract "specifies the CALCULATION and never the input
event". Greg asked *"this should have already been built in some capacity for the exhaustion
prediction part. is this related?"* **It is the same work.** Roughly 200 files, built
2026-08-16 to 2026-08-25, in places frozen and hash-bound. The proposals were building a second
vocabulary over facts this project already has one for - the `_family_id` defect at project
scale, which does not fail, it disagrees.

**All four proposals are WITHDRAWN.** Read the recovery document instead.

## 1. FIRST COMMANDS

```
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q     # expect 613
python3 -m pytest research/kalshi/tests/ -q                                # expect 7 PRE-EXISTING failures
```

## 2. THE FINDING THAT CHANGES THE BUILD PLAN

**Do not build the six adapters the previous drop-in box asked for.** The missing layer is not
an adapter on the F_LAST group. It is the **per-second roll20 / dipole substrate**.

The built exhaustion candidate is a **1-second flow event** - a spike in the trailing-20s signed
aggressor-volume imbalance, detected by an 85th-percentile adaptive bar with a +/-5s local max,
prominence ranking and a 45s refractory, and closed by three consecutive causal oriented
`roll20 <= 0`. The A-arm's unit (D53) is the **nanosecond F_LAST group**. These are three to
four orders of magnitude apart: **3,429 frozen events against 4.26M groups.**

The registry REQUIRES the bridge - `derived_roll20_and_dipole_state`,
`legacy_per_second_roll20`, `derived_open_world_predecessor_state`, all
`CAUSAL_STREAM_REQUIRED` - and **no code in `frankie_raw_mbo_benchmark/` computes roll20 or any
dipole from the MBO stream.** The benchmark does not import one line of the built exhaustion
stack. **That is why 4.10, 4.11 and 4.12 have nothing to feed them, and no F_LAST-group adapter
fixes it.**

## 3. THE OPEN QUESTION FOR GREG - IT IS A UNIT QUESTION, NOT A PHASE QUESTION

**Is an F_LAST-group-local candidate admissible at all, when every prior exhaustion result is
per-second?** If no, sections 4.10/4.11/4.12 need a second clock and the roll20 substrate, not
new definitions. Everything else follows from this. Do not re-ask the four proposal questions -
they were the symptom.

## 4. WHAT TO DELETE ON SIGHT

* **`native_exhaustion.PHASE_ORDER` / `PHASE_INDEX`** (`native_exhaustion.py:33-60`). Eleven
  names, **0 match the built corpus as phases**, and FOUR collide semantically - BIRTH is an
  instant, TRANSITION is a chain edge BETWEEN events, EXTENSION is the chain reaching depth D+1,
  REVERSAL is a price-outcome class after the endpoint. `FIRST_DEVIATION` and `INFLECTION` occur
  nowhere in the frozen corpus. Provenance is one prose line in the 2026-08-28 mission doc.
  **Already superseded by commit `465a2e1`, but the code still carries it** - the S114 failure
  exactly: a decision recorded where nothing enforces it.
* **The 4.12 SAME/FLIP definition.** Those words are TAKEN: *"current exhaustion polarity
  relative to the latest predecessor"*, frozen with committed counts of 1,546 FLIP / 1,883 SAME
  of 3,429, gated in four files. And `DipolePath` refuses a path with mixed orientation, so a
  frozen chain motif (`OOSS->FLIP`) cannot be expressed as a `DipolePath` at all.
* **Any new mirror definition.** `mirror_identity()` is built, ran, and emitted a
  `mirror-pair-index.json`: the mirror is the **side-swapped side string**, `CANONICAL|MIRROR`.
  There are currently THREE mirror vocabularies live in committed code; contract 4.4 mandates one.

## 5. WHAT IS ALREADY RIGHT AND MUST NOT BE "FIXED"

`native_exhaustion.SEED_STATES` carries P/O/S/X correctly. `native_clocks.RecognitionLabel`
carries PRIOR / T0 / H+N correctly. **These two are the model for how the rest should reuse the
frozen vocabulary.**

## 6. FACTS THAT ARE EASY TO GET WRONG

* **`t` IS A PRICE TICK** (`TICK = 0.001`). `3t/5t/8t/13t` are ZigZag reversal thresholds; the
  358/993/1802/4386 figures are the median DURATIONS IN SECONDS of the legs they produce. It is
  a SCALE ladder, not a horizon grid.
* **Fibonacci is coincidental** - 2t was dropped after a five-point sweep; zero occurrences of
  "fibonacci" in the repo.
* **There is NO event clock in the built work.** The only `event_clock` is a boolean
  data-availability flag. Built durations are seconds, the new modules' are nanoseconds - on
  Greg's rule both are guilty. The only raw material is `native_clocks.sequence_span`.
* **The frozen program's horizon fix was the ANCHOR, not abolition:** absolute seconds
  `5,10,20,30,60,120,300` anchored on the **dynamic episode endpoint, "never t0+60 by fiat"**.
  That keeps horizons comparable across events. Plus `first_hit_times` - first +/-3t, +/-5t
  after the endpoint, no duration cap, censor when the stream ends.
* **Prebirth skill is NOT established.** *"No authorized claim that D1, D2, or D3 validates at
  any specific PRIOR H."* The one clue tested FAILED the 2-of-3 gate. There is also a hard
  characteristics wall on prebirth models.
* **B's locality rule was REFUTED on holdout.** Do not carry it forward.
* **`ng_exhaustion_v4_exact_candidate_freeze.py` is a CI release freeze**, not a market
  candidate definition. The previous session claimed otherwise. The real one is
  `ng_exhaustion_chain_canonical_table_20260817.py:220-267`.
* **"runway" means three different things** in this repo now. Disambiguate before using it.

## 7. WHAT IS GENUINELY DONE AND SHOULD NOT BE REBUILT

* **`native_rt_book.ReplayBook`** - the RT view, advanced action by action, on Greg's ruling
  *"we should see it like it would be seen in rt"*. Mirrors `InstrumentBook` on every mutation;
  differential-tested over 12,024 records with zero divergence.
* **`native_full_capture_adapter.FullCaptureAdapter`** - restores everything the hash-locked V4
  adapter discarded. **Never edit that adapter; it is hash-locked and editing it broke six
  supply-chain locks in one commit (D61).**
* **The whole D60 restoration sweep** - legacy rows, exact member and lifecycle rows,
  `describe_structure`'s full output, the at-risk table, the population report, sum_of_squares,
  ladder_scope on the value, the de-saturated assignment ledger.
* The CME trading-day calendar; the file-based execution gate.

## 8. STANDING RULES THAT WERE EARNED THE HARD WAY

* **D60 - nothing is dropped without discussing it first.** Memory is explicitly not a reason.
  The one exception is a row that is TRULY BLANK and measuring nothing.
* **D61 - restore what the MBO adapter drops by WRAPPING it, never by editing it.**
* **Verify by EXECUTION, not by the presence of a file.** Four adapters were built and called by
  nothing; the checkpointer sits on a driver no workflow dispatches; ten of thirteen sections
  receive zero data today. Components existing is not wiring existing.
* **Search the prior corpus BEFORE proposing a definition.** This session cost hours to that.

## 9. LAUNCH READINESS - MEASURED, NOT ASSUMED

Sections fed by the driver: **clocks, coverage, and a replenishment clock advance. That is all.**
Adapters wired: **0**. Execution gate referenced by any non-test file: **0**. Workflows that
dispatch the driver: **0**. Resize armed at `r6i.4xlarge` / 128 GiB, **not fired**.
