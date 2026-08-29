# The four rulings the A-arm cannot make for itself

**Status: PROPOSALS. Nothing here is built. Greg accepts, redirects or rejects each one.**

Sections 4.10, 4.11, 4.12 and 4.16 are built and tested and cannot be fed, because feeding
each one requires a definition the contract does not contain. This is not plumbing. The
contract specifies the CALCULATION and never the input event - 4.10 says "construct a complete
causal runway for each candidate" without anywhere defining a candidate - so whatever is
chosen here decides what the benchmark reports. D53 settled the UNIT (the F_LAST group). It
did not settle these, and the prelaunch state doc says in terms that they "should not be
invented quietly."

Two sections are NOT here because they need no ruling. **4.6 and 4.7** are buildable from what
already exists (the FIFO book, order-id novelty, level depth, touch price) and are being built.
**4.15 must not be built at all**: D5 closed clustering out of this run, `discovery` is
`None`-defaulted, section 4.15 enters the layer map only when it is not None, and the one gate
that mentions it short-circuits - so an adapter would add a `freeze()`-before-`finalize()`
obligation and no measurement.

Each proposal below is structural and group-locally justifiable, keeps the open-world property,
and sites no threshold at a value. Where I could not honestly prefer one option I say so.

---

## 4.10 Exhaustion - what a runway IS

### What the module fixes, and is not up for decision
`open_runway` keys open runways on `candidate_id` and refuses a duplicate while one is open.
Phases must move strictly forward through `PHASE_INDEX` (SEARCHED, PRECURSOR, PREBIRTH,
FIRST_DEVIATION, BIRTH, TRANSITION, INFLECTION, PERSISTENCE, EXTENSION, COMPLETION, REVERSAL);
skips are allowed, repeats are refused, and a novel phase must be registered before use.
`completed_duration_ns` raises until the runway completes. `open_runway(seed_state=None,
observed_shape=())` raises - it needs a carried seed or an observed shape.

### The proposal
**A runway is one PRICE LEVEL ON ONE SIDE, identified by `(instrument_id, side, price_raw)`.**
It opens when a group first acts on that level and closes when the level is vacated - depth
reaches zero - or is censored at a continuity-segment boundary.

Phases come from the level's own liquidity trajectory, each derivable from the group's actions
plus the level's running depth, with no bar sited at a value:

| phase | entered when |
|---|---|
| `SEARCHED` | the level is resting and this group did not act on it |
| `BIRTH` | the first CONSUMING action against the level (fill, trade or cancel) |
| `TRANSITION` | consumption continues while the level is also being replenished |
| `PERSISTENCE` | the level has been consumed and its depth is no longer falling |
| `EXTENSION` | depth exceeds what it held at BIRTH |
| `COMPLETION` | the level is vacated |
| `REVERSAL` | the level is vacated and then re-established within the same segment |

`seed_state=None` with `observed_shape` = the ordered tuple of distinct actions the level has
seen so far, so the state id is open-world (`OW_<hash>`) and no carried seed is forced.

### Why this one
It is the only candidate identity I found that spans groups WITHOUT duplicating another
section. An order's life is 4.6. A group is one instant, and using `GroupContext.candidate_id`
makes every runway exactly one group long - phases can never advance, `max_depth` is 1 forever,
and the section reports an artifact of the unit rather than a measurement. A price level is
observable, persists across groups, is where liquidity actually exhausts, and the phase
vocabulary reads naturally against it.

### What it costs, and what it makes unmeasurable
A runway is then a LEVEL phenomenon, so exhaustion of a *participant* - one aggressor working
through the book - is not measurable by this section at all. It also produces many runways: one
per touched level per segment, which is a large open set. And `REVERSAL` as defined can only be
seen within a segment, so a level re-established across a boundary reads as two runways, not a
reversal. That is a real loss and I would rather declare it than hide it in a threshold.

### How it would be falsified
If the phase distribution collapses - the overwhelming majority of runways going BIRTH straight
to COMPLETION with nothing between - then the intermediate phases carry no information as
sited, and the definition is degenerate in the S114 sense. Measurable on a small slice before
the roster: run it, read the phase histogram, and if fewer than a meaningful fraction of
runways ever reach TRANSITION or beyond, re-site the phases rather than keep the mechanism.

---

## 4.11 Recognition - what a birth and a call ARE

### What the module fixes
`record_call` classifies purely by the sign of `birth_recv_ns - recv_ns`: earlier is `PRIOR`,
equal is `T0`, later is `HORIZON`. The first call wins; later ones are counted as
`superseded_attempts` and discarded. `record` refuses a candidate with no outcome, so every
candidate must be marked missed or censored if it was never called. The module defines no
predicate for a call, no birth event and no horizon.

### The proposal
**The candidate is the same price-level runway as 4.10, constructed when the level is FIRST
OBSERVED RESTING - before anything happens to it. BIRTH is the instant of its `BIRTH` phase,
the first consuming action.** A CALL is the first group in which the level shows a declared
precursor: its depth falls while the mirror level on the opposite side is not falling, i.e.
one-sided withdrawal. MISSED versus CENSORED: **CENSORED** when the continuity segment ended
before the level was ever consumed - the window closed and the question was never answerable -
and **MISSED** when the level was consumed and no call had been made.

### Why this one
This is the only arrangement I found in which `PRIOR` is reachable at all. The section exists
to measure prebirth recognition; with `birth_recv_ns` set to the candidate's own group, every
same-group call is `T0` and every later one `HORIZON`, `PRIOR` is structurally unreachable, and
the section would report cleanly while measuring nothing - the worst available outcome, because
it looks like a result. Constructing the candidate at first REST and birthing it at first
CONSUMPTION puts a real interval between the two, which is the interval the section measures.

### What it costs
It requires a pending-precursor buffer: calls and failed states observed before a birth exists
must be held and replayed into the record at construction, because `birth_recv_ns` is a
required constructor argument. It also means the candidate population is every resting level,
which is large, and the denominator is correspondingly large - so the detection SHARE will look
small. That is honest rather than flattering, and `population_report` already carries the
missed and censored counts that give the figure meaning.

### How it would be falsified
If `PRIOR` remains empty in practice, the precursor predicate carries no lead and should be
replaced rather than kept. If `CENSORED` dominates, the segment is short relative to the level
lifetime and the horizon is mis-sited.

**This is the proposal I am least confident in**, because the call predicate is the one genuine
invention in this document. The alternative is to define a call as any group in which the
level's own depth falls at all, which is nearly always true and would make the section
degenerate in the other direction. I would rather ship the one-sided-withdrawal version with
the falsifier above than pick the trivially satisfiable one.

---

## 4.12 Dipole - what SAME and FLIP mean

### What the module fixes
`orientation` must be `SAME` or `FLIP` and lands in `StratumKey.side_orientation`, so the two
never pool; a path holds exactly one orientation. Direction comes from the sign of
`signed_flow` and nothing else - never from magnitude, never clamped, and a genuinely balanced
group must produce exactly `0`. `stage_index` must be strictly increasing within a path and is
embedded in `subfamily_id`, so stage 0 pools only with other stage 0. `mirror_signed_flow` is
never looked up by the calculator.

### The proposal
**The MIRROR of a level is the level the same number of ticks from the touch on the OPPOSITE
side** - the reflected level. `mirror_signed_flow` is that level's signed flow over the same
stage. **Orientation is `SAME` when this level and its mirror moved in the same direction over
the stage, and `FLIP` when they moved in opposite directions.** `event_phase` is the 4.10
runway phase the level was in at that stage. `stage_index` is the ordinal of the group within
the runway, starting at 0.

### Why this one
It makes orientation a genuine mirror relationship rather than a relabelled side or a second
copy of direction. Deriving orientation from `signed_flow`'s sign would collapse orientation
and direction into one variable and destroy the estimand; using bid/ask would make
`side_orientation` mean the same thing it means everywhere else and waste the dimension.
Reflecting about the touch is the natural symmetry of a book, and it is computable group-locally
from the RT book we now have.

### What it costs
A level with no mirror - one side thinner than the other, so the reflected level does not exist
- has no `mirror_signed_flow`, and must pass `None`, which the calculator counts as an
exclusion rather than an observation. Passing `0` there would be a lie, so those stages are
legitimately excluded and the exclusion count must be read alongside the result. Orientation
must also hold constant along a path, so a level whose relationship to its mirror inverts ends
one path and starts another; long paths will therefore be rarer than they intuitively should
be.

### How it would be falsified
If SAME and FLIP produce indistinguishable distributions across every stratum, the mirror
relationship carries nothing and the dimension is spending a stratum key for no information.

---

## 4.16 Response - what is being measured, and over what horizons

### What the module fixes
Horizons are a fixed set of nanosecond offsets given once, with a `horizon_version` label that
enters every stratum key. Each horizon has its OWN measure, its own stratum and its own at-risk
denominator, and each is written exactly once - a later, cleaner value cannot replace it.
Maturity is in stream time, and the recorded timestamp is the DUE time, not the time `advance`
happened, so a coarse cadence delays emission without corrupting the causal stamp.

### The proposal
**Horizons: 1s, 10s, 60s, 300s** (`1_000_000_000`, `10_000_000_000`, `60_000_000_000`,
`300_000_000_000` ns), `horizon_version = "H4_S115_V1"`.
**`value_names`: `mid_price_change_raw`, `touch_depth_change`, `signed_flow`** - the three
things a level's future can do that the book can state exactly.
**`values_for(track, horizon)`** reads the driver's current RT book state for the track's level
and returns those three as differences from the values held at `open_track`.
**`starting_liquidity_regime`**: `AT_TOUCH` when the level was the best price on its side at
open, `BEHIND_TOUCH` when it was resting but not best, `OFF_BOOK` when it was not resting at
all. Three structural states, no fitted bar.

### Why this one
The horizons span the range the rolling activity windows already use, so the response is
measured on the same time scale the rest of the adapter observes, and 300s is the outer bound
of the activity window - beyond it there is no corroborating context. The three value names are
exact book quantities rather than derived ratios, which keeps the no-averaging rule intact at
the point of measurement. The regime vocabulary is the same AT_TOUCH / DEEP distinction 4.7
needs for `touch_state_at_open`, so the two sections agree by construction rather than by
coincidence - which is the `_family_id` lesson.

### What it costs
Four horizons over a large open track set makes `advance` O(open_tracks x horizons) on every
call with no early exit, which is the one place in this design where cost is real. Batching the
advance is safe - the stamp is the due time - but it delays emission. And a 300s horizon at the
end of a segment is censored far more often than a 1s one, so the four horizons will have very
different denominators. That is exactly what the per-horizon at-risk table exists to show, and
it must be read, not summarized.

### How it would be falsified
If the 1s and 300s responses are indistinguishable, the horizon set is not spanning anything
and one horizon would do. If every horizon censors at the boundary, the segments are too short
for the set and the horizons are mis-sited.

---

## The four rulings, in one table

| section | proposal in one line | what Greg decides |
|---|---|---|
| 4.10 exhaustion | A runway is one price level on one side, phased by its own liquidity trajectory | Is a LEVEL the right candidate, or should a runway follow a participant? |
| 4.11 recognition | Candidate at first rest, birth at first consumption, call on one-sided withdrawal | Accept the call predicate, or name a different one - this is the weakest of the four |
| 4.12 dipole | The mirror is the reflected level across the touch; SAME/FLIP is whether the two moved together | Is the reflection the right mirror, or is the counterpart something else? |
| 4.16 response | 1s/10s/60s/300s over mid change, touch depth change and signed flow, keyed by AT_TOUCH / BEHIND_TOUCH / OFF_BOOK | Are those the horizons and the quantities worth measuring? |

**Nothing is built against any of these.** Say the word on each and I build it; redirect any of
them and I build what you say instead.
