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

## 4.16 Response - the event's own length IS the answer

**SUPERSEDED ON GREG'S RULING, 2026-08-29.** The first version of this section proposed fixed
wall-clock horizons of 1s / 10s / 60s / 300s. Greg: *"i'm not sure what the time intervals are
for but we want to get away from any of those and just make any time duration computational
from that event duration on its own. we want to observe the length and that's the answer not
random time intervals. that's why we have an event clock."* He is right, and the original
numbers were exactly the defect this tree keeps finding - a bar sited at a value, chosen
because it looked reasonable rather than because the data put it there. A 60-second horizon
asks "what had happened by an arbitrary moment"; the event asks "how long did I take", and only
the second question is answered by the tape rather than by us.

### What the module fixes, and the problem that creates
Horizons are `Sequence[int]` nanosecond offsets given ONCE to the constructor, and
`open_track` stamps that same grid onto every track: `native_response.py:245`,
`for horizon in self.horizons_ns: track.horizons[horizon] = HorizonObservation(horizon_ns=
horizon, due_recv_ns=first_lawful_recv_ns + horizon)`. **Verified: the grid is run-global and
per-track horizons are not expressible as the module stands.** Each horizon has its own
stratum, its own measure and its own at-risk denominator, and each is written exactly once.

**And there is a causality constraint that rules out the obvious fix.** A horizon scaled by an
event's own duration cannot be set when the track OPENS, because the duration is not known
until the event ends - that would be lookahead, which the whole traversal forbids.

### The proposal
**Two changes, and the first is the important one.**

**1. The duration is a first-class measurement, not a horizon.** The event's own length is
already the observable in the survival machinery - `time_to_exit` in 4.6, `time_to_restoration`
in 4.7, `completed_duration_ns` in 4.10 - each with proper censoring, so an event that outlives
its segment is censored rather than silently truncated. That is where "observe the length and
that's the answer" already lives, and it needs no new instrument. **The ruling that matters is
that this, not a wall-clock grid, is the primary output.**

**2. 4.16's horizons become EVENT-FRACTION milestones: 25%, 50%, 75% and 100% of the event's
own realized life.** They are shared LABELS, so the at-risk denominators stay meaningful - all
the 50%-of-life readings pool with each other and never with the 25% ones - while each track's
actual instants are computed from its OWN duration. No wall clock anywhere.

This is causally legal because of the flow, not despite it: `ResponseTrack.add_change_point`
already records the path AS IT HAPPENS, at instants that were lawfully observable when they
occurred. At completion the realized duration is known, the four milestone instants are
computed from it, and the values are READ OFF the path already recorded. Nothing is predicted
and nothing is read early - the emission is deferred to completion, which is the same deferral
`advance` already performs, moved from a clock to an event boundary.

**The one code change 4.16 needs:** maturity by event completion rather than by
`advance(recv_ns)` against a global grid. `add_change_point` and the at-risk table survive
unchanged; `horizons_ns` becomes the four fractions and `horizon_version` names them.

**Values, unchanged from the first version:** `mid_price_change_raw`, `touch_depth_change`,
`signed_flow` - exact book quantities, never ratios.
**Regime, unchanged:** `AT_TOUCH` / `BEHIND_TOUCH` / `OFF_BOOK`, the same vocabulary 4.7 needs
for `touch_state_at_open`, so the two sections agree by construction rather than by
coincidence.

### What it costs, stated plainly
An event censored at a segment boundary has no realized duration, so its milestones cannot be
computed at all - it contributes to the censored denominator and to nothing else. Under a
wall-clock grid such an event would still have produced its 1s and 10s readings. That is a real
loss of readings, and it is the correct one: those readings measured an arbitrary interval,
not the event.

Milestones are also not comparable in wall time - a 50% reading on a two-second event and on a
two-hour event are the same label over vastly different spans. That is the point rather than a
flaw, but it means the duration distribution must be read ALONGSIDE the milestone rows or the
labels mean nothing, which is why change 1 comes first.

### How it would be falsified
If the four milestone readings are indistinguishable from one another across every stratum,
the event's interior carries no shape and only its total duration is informative - in which
case 4.16 collapses into the survival measurements of change 1 and should say so rather than
report four columns of the same number.

## What I am building, and the one thing I actually need from you

**Greg, on reading the first draft: "i really don't know what you are wanting from me as far as
an answer for the other 3."** That is a fair complaint about this document, not about the
sections. Four open design questions is not a decision to make, it is homework. So this is
restated as what I will build unless told otherwise.

**And your 4.16 ruling already answered most of it.** *"observe the length and that's the
answer not random time intervals. that's why we have an event clock."* That is a principle, not
a note about 4.16: **do not impose a bar the data did not put there - let the thing measure
itself.** Applied to the other three, it decides them:

| section | what I build, applying your own rule | still yours |
|---|---|---|
| **4.10** | A runway is one price level on one side. BIRTH is its first consuming action, COMPLETION is the moment it is vacated - both structural, neither a bar I chose. The phases IN BETWEEN are **open-world**, registered from each runway's `observed_shape` via `register_discovered_phase`, instead of the fixed vocabulary I proposed first. My original TRANSITION / PERSISTENCE / EXTENSION table was exactly the thing you just struck down in 4.16: boundaries chosen because they sounded reasonable. | Only if a LEVEL is the wrong candidate and a runway should follow a participant instead. |
| **4.11** | Candidate at the level's first rest, birth at its first consumption. **Uses no horizon at all** - CENSORED is the segment ending before the level was ever consumed, MISSED is the level being consumed with no call made. The event's own life decides, exactly as you said. The call is the level's depth falling by CANCEL before any fill or trade has touched it - one-sided withdrawal, purely structural, no bar. | Nothing, unless the call predicate is wrong. |
| **4.12** | The mirror is the level the same number of ticks from the touch on the opposite side - the book's own reflection, not a bar. SAME / FLIP is whether a level and its mirror moved together over the stage. | Nothing, unless the counterpart is something other than the reflection. |
| **4.16** | The event's own LENGTH is the answer. Duration becomes the primary measurement, and the horizons become 25 / 50 / 75 / 100 percent of each event's realized life, read off the causally-recorded path at completion. No wall clock anywhere. | Confirm you are happy for 4.16 to mature on event completion rather than on a clock - that is a real change to a built section. |

**So the honest answer to your question is: nothing, for three of them.** I was asking you to
do design work I should have done by applying the rule you had already given me. Build proceeds
on the four rows above; say the word on any one and I change it.

**The one thing I do need**, because it changes built and tested code rather than adding to it:
**4.16 maturing on event completion instead of `advance` against a global grid.** Everything
else in this document is new code against an unchanged module.
