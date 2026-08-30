# Scoping the roll20 substrate before building it

**Why this document exists.** Greg: *"Don't we already have an exhaustion calc? We've
measured it on other runs"* - and then, given the choice, *stop and scope it with you
first*. So nothing here is built. This is the three things the ruling needs: what the
frozen roll20 actually requires from the MBO stream, what it costs, and what it would
reproduce against the frozen 3,429.

**The short version: the compute is free, the recipe is small and fully recovered, and the
reconciliation is impossible on the days the A-arm holds.** The third finding is the one
that decides the build.

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
maintain the book; for each row with action == "T":
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
`valid_quote` mid needs. **The missing piece is only the per-second accumulator and the
detector**, not the book.

One format gap: the frozen loader reads `NG_*.jsonl.gz` raw causal days
(`load_raw_causal_days`), while the A-arm's sources are native DBN MBO. That is a reader
difference, not a semantic one, but it is real work.

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

## 3. What it would reproduce against the 3,429 - and this is the finding

**Nothing. There is not one day in common.**

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

**My read:** (b) is cheap enough to be unconditional - do it whatever else is decided,
because it costs nothing and it pins the half of the work that can be pinned. But (b) alone
would leave the bridge unchecked, and the bridge is the risky half. **(a) is the only thing
that reconciles**, and it needs a data pull the A-arm has not budgeted.

### A density check, so the expectation is on the record before anything runs

3,429 events over 3 pilot weeks is roughly **15 sessions, ~229 events per session**. The
45-second refractory caps a 23-hour session at ~1,840. So a plausible expectation for the
four October 2021 days is **order 900 events**, if 2021 tape density resembles 2025's -
which is itself an assumption worth stating, since the whole point of a four-year gap is
that it may not. Writing the expectation down first is what makes a surprise legible.

---

## 4. What this leaves for the ruling

The unit question the last drop-in box posed - is an F_LAST-group-local candidate admissible
when every prior result is per-second - turns out to be downstream of a data question:

1. **Which days?** October 2021 (what we hold) or the pilot weeks (what the frozen roster
   covers)? Nothing reconciles until this is answered, and it is a procurement question, not
   a design one.
2. **Is the benchmark's `ExhaustionCalculator` a carrier or a competitor?** It has measured
   nothing. It can become the vessel the frozen definitions flow through, or it can be
   dropped in favour of consuming the built stack's output. It should not stay as it is -
   a parallel apparatus with its own vocabulary and no data.
3. **Only then, the unit.** Whether a nanosecond F_LAST group may carry a candidate at all,
   given the frozen unit is a 1-second flow event - 3,429 events against 4,256,603 groups.

**Nothing in this document was built.** The one thing done this session was deletion: the
eleven invented phase names, the misappropriated `SAME`/`FLIP`, and two of the three mirror
vocabularies (commit `c0b6216`).
