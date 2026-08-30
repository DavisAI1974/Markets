# Scoping the roll20 substrate before building it

> # STOP - CORRECTED AGAIN, AND THIS ONE REVERSES THE RECOMMENDATION
>
> **This document recommended reading the October Step-1 seconds artifact. The binding
> mission FORBIDS it, and the feed inventory seals it as the ANSWER.**
>
> `research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md:31-34`,
> verbatim: *"Use only F_LAST-closed native event groups. **Never use reduced seconds rows,
> `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`, MBP/top-10, Step-1-derived input**, another
> benchmark arm's output, post-cutoff information, or old reduced market rows. **Keep Step-1
> and the answer/reveal wall sealed.**"*
>
> And `NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` section 14, "Sealed October
> answer feed", lists **"Existing October Step-1 seconds"** under authority
> `SEALED_TARGET_ANSWER`, *"mechanically inaccessible until all primary discoveries, helper
> evidence, probability movies, and first-lock/no-lock ledgers are immutable."*
>
> **Narrowed 2026-08-30, because the first version of this banner over-corrected.** What is
> sealed is the October Step-1 SECONDS FILE. Reading it would void the run. That is not the
> same as a ban on the legacy SURFACE: inventory section 8 positively REQUIRES the causal
> replay to recreate per-second `roll20` and the other legacy observables, and
> `_legacy_control_row` in the V4 adapter already *projects* those rows - `bid_px_00`,
> `ask_px_00`, the ten depth levels - from the native MBO stream, with
> `native_replay_driver.py:279-293` retaining every one under D60. Recomputing from native is
> lawful and mandated; reading the Step-1 output is neither. The first banner conflated the
> file with the quantity and would have forbidden the required work.
>
> **What the directive actually requires** is inventory section 8, the *Legacy-observable
> compatibility feed*: *"The same causal replay must recreate the exact lawful surface on
> which the 54/55-week structures were learned"* - including *"Per-second `roll20`"* - and
> *"Every legacy field requires an explicit crosswalk to its V4-native source fields,
> calculation, availability time, and state hash. The crosswalk must not contain October
> target identities."*
>
> So roll20 IS computed inside the benchmark, from the native F_LAST stream, and crosswalked.
> **The drop-in box was right and I was wrong.** What survives from this document is section
> 1's recipe, section 2's measured 1.5s cost, and the observation that the frozen detector and
> `AggressorRoll20Feed` are reusable arithmetic. What does not survive is every suggestion to
> read a Step-1 output.


**Why this document exists.** Greg: *"Don't we already have an exhaustion calc? We've
measured it on other runs"* - and then, given the choice, *stop and scope it with you
first*. So nothing here is built. This is the three things the ruling needs: what the
frozen roll20 actually requires from the MBO stream, what it costs, and what it would
reproduce against the frozen 3,429.

**CORRECTED 2026-08-30, same session, by Greg:** *"We have actually done step 1 work for
the less than mbo data for these 2 days. I don't understand what is still missing."* He was
right and the first version of this document was wrong where it mattered most. **The
per-second substrate for October 2021 already exists.** Step 1 built it, hash-pinned it, and
a prior-surface Frankie run already consumed it row by row. The correction is section 5, and
it is the section to read; sections 1 and 2 survive intact, section 3 does not.

**The short version, corrected: the substrate is not missing, the compute is free, and what
is actually left is a READER plus one column ruling.** And the column ruling matters more
than the reader, because step 1 built the series TWICE under two different rules and the two
disagree.

---

## 0. The premise, verified rather than assumed

Yes, there is already an exhaustion calc, and it was measured.

* ~40 Python modules under `research/`, 266 exhaustion artifacts.
* Frozen population **3,429 events**, blind 1,711 / reveal 1,718
  (`FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json`).
* Families **A=3,235 / B=72 / C=122**, classifier SHA `698b956f...`,
  `recovered_assignment_check: {"mismatches": 0, "records": 3429}`, `"no refit"`.
* `NG_EXHAUSTION_POX_FOCUSED_LAUNCH_20260819.json:6`: `FIXED_3429_DO_NOT_REOPEN`.

And the benchmark's own exhaustion calculator is **not** that one. Grepped every caller:
`ExhaustionCalculator` is constructed once at `native_calculation_runner.py:258` and no
`open_runway` / `mark_landmark` / `complete` call exists anywhere outside its own tests. It
has never seen a market record. So the repo holds one exhaustion calc that measured things
and one that has measured nothing.

---

## 1. What roll20 needs from the MBO stream

Smaller than expected. The detector's ONLY input is two per-second arrays, `buy_vol` and
`sell_vol` (`ng_dipole_native_shape_audit.flow_series`). Everything downstream - roll20,
peak detection, the A/B/C geometry, the endpoint - is pure arithmetic on those two arrays.

The construction is recovered verbatim from
`ng_exhaustion_pox_standalone_analysis_20260819.py:301-320`:

```
maintain the book; for each row with action == "T":   # projected from native, never read from Step-1
    price, size = row.price, row.size
    if the book has BOTH a bid and an ask (valid_quote):
        midpoint = 0.5 * (bid + ask)
        if price > midpoint:  buy_vol[second]  += size
        elif price < midpoint: sell_vol[second] += size
        # price == midpoint contributes to NEITHER
```

Four properties of that recipe that a reimplementation has to carry, or it is a different
measurement wearing the same name:

1. **It is a mid-comparison, not the MBO `side` field.** Aggressor side is inferred from
   trade price against the prevailing mid. The tape's own side is not consulted.
2. **A trade exactly AT the mid is dropped from both sides.** There is no tick-rule
   fallback. It is not counted as buy, sell, or unsided - it simply does not enter.
3. **A trade with no two-sided book is dropped entirely.** `valid_quote` gates the whole
   branch, so trades before both sides exist contribute nothing.
4. **It keys on `action == "T"` only** - not `F`.

Then, from `flow_series` and `detect_dipole_peaks`, with the constants read out of the
module: `roll = 20`s trailing, `PEAK_Q = 0.85`, `LOCAL_RADIUS = 5`, `REFRACTORY = 45`,
`PRE = POST = 60`. Prominence is pre-only: `|flow[t0]|` minus the median `|flow|` over
`t0-30 .. t0-10`. Selection is greedy on prominence, then re-sorted chronologically.

Two spec details that are easy to lose:

* **The threshold is day-native, the candidate window is week-continuous.**
  `CHAIN_STUDY_CONTRACT.event_detection.threshold` is *"85th percentile of absolute roll20
  within each UTC source date"*, while `week_continuity_extension` says candidate windows,
  prominence history, roll20 and refractory selection *may* cross UTC-date boundaries and a
  date change does not create a reset. Those are two different clocks in one detector.
* **The week's origin is the tape, not the calendar** - *"first actual NG trade after the
  Sunday weekly reopen"*, and holidays *"follow actual trade stream, never assumed clock
  time"*.

### What we already have for this

The book half is built and does not need rebuilding. `native_rt_book.ReplayBook` mirrors
`InstrumentBook` on every mutation, was differential-tested over 12,024 records with zero
divergence, and exposes `touch_price(side)` - which is exactly the bid and ask the
`valid_quote` mid needs.

**And per section 5, the per-second accumulator is built too, and has already run on these
days.** So the only piece with no implementation anywhere is the detector wiring - and the
detector itself is 60 lines of committed, frozen Python that runs today.

One format gap: the frozen loader reads `NG_*.jsonl.gz` raw causal days
(`load_raw_causal_days`), while step 1's output is `*.seconds.jsonl.gz`. That is a reader
difference, not a semantic one.

---

## 2. What it costs

**The derived layer is free, and this is measured rather than argued.** Running the frozen
`flow_series` and `detect_dipole_peaks` unmodified, on per-second arrays of the real length
(a 23-hour CME NG session = 82,800 seconds):

| span | seconds | roll20 | detect | total |
|---|---|---|---|---|
| 1 day | 82,800 | 0.027s | 0.120s | **0.147s** |
| 4 days (the whole A-arm roster) | 331,200 | 0.104s | 1.417s | **1.521s** |

One and a half seconds for the entire A-arm. Pure Python, no numpy, no tuning. The
per-second arrays are ~331k floats - not a memory consideration at any instance size. **The
armed `r6i.4xlarge` / 128 GiB resize is not needed for this layer.**

**What is NOT measured here, and I am not going to pretend otherwise:** the single pass over
the **5,667,689** raw MBO records (`raw_mbo_source_manifest`, `total_mbo_records`, hash-bound)
that maintains the book and bins trades into seconds. No raw data is staged in this
container and there are no AWS credentials, so I could not run it. Two things bound it
honestly:

* That pass is **the pass the replay driver already performs**. The accumulator adds one
  comparison and one addition per `T` row to a walk that already happens; it does not add a
  traversal.
* The 4.26M figure in the drop-in box is `EXPECTED_A_MEMORY_GROUPS = 4,256,603` - the
  F_LAST *group* count over the same 5.67M records. Grouping does not change the pass.

So the honest cost statement is: **the substrate adds a near-constant overhead to an
existing pass, plus 1.5 measured seconds.** If that estimate is wrong it is wrong in the
MBO-reader constant, and the way to settle it is to run one October day, not to argue.

---

## 3. What it would reproduce against the 3,429

**Superseded in its consequence by section 5. What survives is narrower than what I wrote:
the frozen 3,429 EVENT roster does not cover October 2021, so that particular
roster-to-roster reconciliation is unavailable. What does NOT survive is the conclusion I
drew from it - that validation therefore needs a data pull. It does not; see section 5.**

There is not one day in common between the frozen event roster and the A-arm's roster.

| | days |
|---|---|
| Frozen pilot roster behind the 3,429 | weeks of **2025-07-13, 2025-09-21, 2025-09-28** (`CHAIN_STUDY_CONTRACT.validation.initial_weeks`) |
| Frozen 54-week base | **2025-06-29 through 2026-07-12**, plus repair week `20260329` held aside (`CHAIN_PHASE1_54W_BASE_FREEZE`) |
| The A-arm's entire raw roster | **2021-10-01, 2021-10-03, 2021-10-04, 2021-10-05** (`raw_mbo_source_manifest.EXPECTED_ROSTER`) |

The A-arm is on **October 2021**. The frozen exhaustion program is on **mid-2025 to
mid-2026**. They are almost four years apart and share zero sessions.

The consequence is precise: `target_day_equivalence` - *"compare continuous-week detected
target-day events against the frozen 3429-event reveal+holdout roster and fail closed on
unexplained interior mismatches"* - **cannot be executed on the A-arm's data at all.** There
is no roster for October 2021 to fail closed against.

That is not a reason to skip validation. It changes what validation is available, into three
distinct options with very different costs:

**(a) Reconcile properly.** Pull NG MBO for the three pilot weeks (~15 sessions) and run the
reimplementation against the frozen 3,429 roster. This is the only option that produces a
true reconciliation, and it is the one the frozen contract was written for. Cost is a
Databento pull plus the reader work.

**(b) Differential-test the arithmetic.** Run the reimplementation and the frozen
`ng_dipole_native_shape_audit` functions on identical per-second inputs and require exact
agreement. Free, runnable today, and it is the same technique that validated `ReplayBook`
over 12,024 records with zero divergence. **It proves the detector is the same detector. It
proves nothing about the MBO -> per-second bridge**, which is where the four subtle rules in
section 1 live and where a reimplementation would actually go wrong.

**(c) Construct on October 2021 and validate nothing.** Produces numbers with no external
check. Given what the `_family_id` defect cost, this is the option that manufactures a
second population.

**My read at the time was that (a) was the only real reconciliation and needed a data pull.
That was wrong, and section 5 says why: the bridge I called "the risky half" was already
built and already run on these days, so it can be checked against its own output rather than
re-derived. (b) remains unconditionally worth doing.**

### A density check, so the expectation is on the record before anything runs

3,429 events over 3 pilot weeks is roughly **15 sessions, ~229 events per session**. The
45-second refractory caps a 23-hour session at ~1,840. So a plausible expectation for the
four October 2021 days is **order 900 events**, if 2021 tape density resembles 2025's -
which is itself an assumption worth stating, since the whole point of a four-year gap is
that it may not. Writing the expectation down first is what makes a surprise legible.

---

## 4. What this leaves for the ruling

Rewritten after the correction. The question is no longer whether to build a substrate.

1. **Which column feeds roll20?** `legacy_*` or `native_*`. Section 5 argues this is
   determined rather than open, but it is a ruling and it should be made explicitly, once,
   in writing, because both columns are present, numeric, in range and plausible.
2. **Is the benchmark's `ExhaustionCalculator` a carrier or a competitor?** It has measured
   nothing. It can be the vessel the frozen definitions flow through, or it can be dropped
   in favour of consuming the built stack's output. It should not stay as it is - a parallel
   apparatus with its own vocabulary and no data.
3. **Only then, the unit.** Whether a nanosecond F_LAST group may carry a candidate at all,
   given the frozen unit is a 1-second flow event - 3,429 events against 4,256,603 groups.
   Note that a per-second series for these days now demonstrably exists, so the two clocks
   can be held side by side rather than one being hypothetical.

---

## 5. THE CORRECTION: the substrate exists, and it exists TWICE

Greg: *"We have actually done step 1 work for the less than mbo data for these 2 days."*

He is right, and every part of it checks out.

### It was built

`ng_exhaustion_mbo_5y_step1_census_20260822.py:244-271` defines a per-second row keyed on
`epoch_second` carrying, among other fields:

```
legacy_rows, legacy_buy_qty, legacy_sell_qty,
native_buy_qty, native_sell_qty,
trade_count, last_trade_price,
book_imbalance_sum, book_imbalance_n, native_state{...}
```

A per-second buy and sell aggressor volume. **That is `buy_vol` and `sell_vol` - the entire
and only input `flow_series` takes.**

### It exists for these exact days

`NG_EXHAUSTION_OCTOBER_STEP1_RESULT_INVENTORY_20260824.txt`:

```
WORKER_CHILD_RECEIPT_FILE = 20211001_20211101.receipt.json | 20604 bytes
WORKER_OCTOBER_SECONDS_BYTES  = 112,852,940
WORKER_OCTOBER_SECONDS_SHA256 = 93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90
```

A 112.8 MB hash-pinned seconds artifact covering `20211001` to `20211101` - which contains
all four A-arm days, not just two.

### And it has already been READ

`ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.py` pins the whole schema as
`PRIOR_ROW_FIELDS` (`:85-110`) and `build_day_context` (`:472-495`) serves
`legacy_buy_qty`, `legacy_sell_qty`, `native_buy_qty`, `native_sell_qty` and the book state
as per-day distributions over two target days. The reduced-surface Frankie run consumed this
series. It is not a dormant artifact.

So the drop-in box's sentence - *"no code in `frankie_raw_mbo_benchmark/` computes roll20 or
any dipole from the MBO stream"* - is literally true and led to the wrong conclusion, mine
included. **The benchmark does not compute it because it does not need to compute it. It
needs to READ it.**

### THE PART THAT MATTERS: the two columns are different quantities

Step 1 builds the series twice, from two different rules, in the same loop
(`ng_exhaustion_mbo_5y_step1_census_20260822.py:303-334`):

**`legacy_buy_qty` / `legacy_sell_qty`** - from the legacy mbp-10 rows, gated on
`price>0 and size>0 and bid>0 and ask>=bid`:

```
mid = 0.5 * (bid_px_00 + ask_px_00)
price > mid  ->  legacy_buy_qty  += size
price < mid  ->  legacy_sell_qty += size
```

**`native_buy_qty` / `native_sell_qty`** - from the native raw actions:

```
raw.side == "B"  ->  native_buy_qty  += size
raw.side == "A"  ->  native_sell_qty += size
```

**The first is the frozen recipe, character for character. The second is the tape's own side
field, which the frozen program deliberately does not use.** Compare section 1: aggressor
side is inferred from trade price against the prevailing mid, and the tape's side is not
consulted.

They will not agree, and they are not supposed to. A mid-priced trade enters neither
`legacy_*` column and enters one `native_*` column. A trade with no two-sided book is
excluded from `legacy_*` entirely and is included in `native_*`. And `native_*` inherits
whatever aggressor convention the venue encodes, which is a different question from where
the trade printed relative to the mid.

**So the ruling is: `legacy_*` is the frozen-compatible column, and roll20 must be built on
it.** The trap is that `native_*` is the one whose name sounds authoritative and whose
lineage is the newer, richer surface - and feeding it into a section named for the frozen
dipole would be "present, typed, in range, and wrong", producing a number that never fails
and simply is not the quantity the 3,429 were detected from. That is the `_family_id` defect
one more time, and this time it is not in a proposal - it is in committed code that already
ran.

That `DUAL_CENSUS_CROSSWALK` exists at all says the prior work knew the two censuses had to
be reconciled rather than assumed equal.

### What this changes about validation

Section 3 said reconciliation needed a data pull. It does not.

* The frozen 3,429 EVENT roster still does not cover October 2021 - that stands.
* But the detector can now be run on the `legacy_*` series for these days and its output
  compared against the reduced-surface work already done on the same days, which is a
  reconciliation on shared data rather than a construction in the dark.
* And the differential test (option (b)) becomes sharper than I described: run the frozen
  `flow_series` / `detect_dipole_peaks` on the `legacy_*` column, and on the `native_*`
  column, and MEASURE how far apart the two event sets are. That is a free experiment on
  data that already exists, and its answer is directly useful: it sizes exactly what the
  column choice is worth.

### The honest note on availability

`S3_RESULT_OBJECT_COUNT=0` in the same inventory. The seconds artifact is recorded with a
worker-local byte count and SHA, not as an S3 object, so **where it currently lives needs
confirming before anything reads it**. No credentials are resolvable in this container, so I
could not check. That is a retrieval question, not a build question, and it is the one thing
between here and running the experiment above.

---

## 6. What was actually wrong in my first pass, recorded because the pattern is the point

I searched the frozen EVENT corpus and the raw MBO manifest, found no shared day, and
stopped. I did not search for the STEP 1 outputs on the A-arm's own days - so I concluded a
substrate was missing when it existed, was hash-pinned, and had already been served to a
Frankie.

The standing rule from D62 is *search the prior corpus before proposing a definition.* I
searched it for the definition and not for the DATA. Same rule, and the half I skipped is
the half that had the answer.
