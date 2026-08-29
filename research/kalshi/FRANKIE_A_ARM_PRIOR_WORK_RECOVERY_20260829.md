# The prior exhaustion work already defines what I proposed inventing

**Why this document exists.** I wrote four estimand proposals for sections 4.10, 4.11, 4.12 and
4.16 on the premise that the calculation contract "specifies the CALCULATION and never the
input event". Greg: *"this should have already been built in some capacity for the exhaustion
prediction part. is this related?"* It is. It is not merely related - **it is the same work**,
built across roughly two hundred files between 2026-08-16 and 2026-08-25, and in places
FROZEN. My proposals were building a second vocabulary over facts this project already has one
for, which is the `_family_id` defect at project scale: two vocabularies do not fail, they
disagree, and the disagreement surfaces only after a run.

**This document records what already exists, so the proposals can be deleted rather than
reconciled.** Everything below is quoted from the built code with file and line. Where the
built work and the NEW benchmark modules CONTRADICT each other, that is called out as such -
those are the findings that matter most, because nothing would fail.

---

## B. Recognition (section 4.11) - RECOVERED

### t0 is a DIPOLE SPIKE IN FLOW. Price never selects or orients it.

`research/ng_dipole_native_shape_audit.py:97-134`, `detect_dipole_peaks`. The series is a
**causal trailing signed aggressor-volume imbalance** `(buy-sell)/(buy+sell)` over a 20s roll at
1s resolution. A candidate must be a local `|flow|` maximum over +/-5s AND exceed the day's
85th percentile of `|flow|`; candidates rank by a **pre-only prominence** (`|flow[t0]|` minus
the median `|flow|` over `t0-30..t0-10`, so left-of-t0 information only); greedy selection with
a 45s refractory. The module states it at `:11-18`: *"t=0 is detected from the DIPOLE ONLY.
Price is never used to find or orient the dipole event... Price legs are attached only AFTER
dipole events are frozen, as external structural labels."*

**My proposal made t0 a price-level event.** That is not a variation on the built definition,
it is a different object. The built t0 is a flow spike; the price path is a LABEL attached
afterwards.

### PRIOR / T0 / H+N already exists, by that name, and the classes are ORDERED

`research/ng_exhaustion_chain_recovery_features_v3_20260819.py:13`:
`TIMING_LADDER = ("PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5")`.
The boundary rule, same file `:20-37`: *"PRIOR remains strictly before target t0. BIRTH_T0 is
the target's frozen birth second itself and is deliberately not called H=0. POST_BIRTH H begins
only at +1 second after t0."* And as policy,
`research/ng_exhaustion_d0_d3_model_specific_trade_v3_t0_20260820.py:83-84`:
`ALL_ELIGIBLE_PRIOR_OUTRANKS_T0; T0_OUTRANKS_H; H_BEGINS_AT_PLUS_1_ONLY`, with
`primary_success_definition: PRIOR_BIRTH_PREDICTION_ONLY`
(`ng_exhaustion_d1_d5_chain_birth_agents_20260819.py:283`).

"Early" is measured by **information-set closure**, not by comparing timestamps after the fact:
every predecessor's window `[confirm, confirm+h]` must close at or before the target's t0, and
`lead = t0_idx - max(confirm+h)` (`chain_birth_agents:110-119`).

### A CALL is a persistence run on signed flow, and it has TWO timestamps

`research/ng_exhaustion_chain_canonical_table_20260817.py:255-267`, with `PERSIST = 3`:
`structural_onset_idx` is the first second of three consecutive seconds of oriented flow `<= 0`
- when the thing began - and `causal_confirmation_idx` is the third - the earliest lawful
assertion. Policy verbatim at `research/ng_exhaustion_aftermath_validate_v2_20260817.py:340`.
Confirmation may be used as a CLOCK and never as evidence: `confirmation_lag_as_feature` is on
the prohibited list (`chain_birth_agents:283`).

**My proposed call predicate - "the level's depth falls by cancel before any fill or trade
touches it" - has no counterpart anywhere in the built work.** Every built predicate is a
persistence run on signed aggressor flow. This was the part of my proposal I flagged as
weakest, and it was weakest because it was inventing over a settled mechanism.

### CENSORED exists in three built forms; MISSED does not exist at all

`ENDPOINT_CONFIRMATION_CENSORED` when the qualifying run never completes before the tape ends
(`ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py:559-562, 604`); per-horizon censoring when
`end + h > last_trade_idx` (`chain_canonical_table:284-287`), so one candidate can resolve at
5s and censor at 300s; and `FROZEN_WEEK_END_OR_CANONICAL_TARGET_UNAVAILABLE` for a target that
does not exist, carried out as a separate list and reported as `censored_n`, never labelled
`y=0` (`chain_birth_agents:96-97`).

**MISSED is genuinely new and genuinely needed.** Nothing in the built corpus separates "a
birth occurred and our detector said nothing" from "no birth occurred", because a non-birth is
a LABEL (`y = 1 if q >= stage else 0`, `chain_birth_agents:98`) evaluated by Brier/AUC, not a
detection failure.

### FOUR COLLISIONS WITH `native_recognition.py`, one of them structural

1. **The T0/HORIZON boundary AGREES.** `native_recognition.py:93-98` is a faithful
   re-implementation of `T0_semantics: FROZEN_TARGET_BIRTH_SECOND_ITSELF_NOT_H_ZERO` and
   `H_BEGINS_AT_PLUS_1_ONLY`. No conflict.
2. **The three detected classes are NOT equal, and the module treats them as equal.**
   `native_recognition.py:38` `DETECTED_OUTCOMES = frozenset({PRIOR, T0, HORIZON})` and a
   single `detection_share` over all three. The built work ranks them strictly and stops the
   search at the earliest validated class. **A `detection_share` scoring an H+3-only system
   identically to a PRIOR system reports the opposite of what the built work concluded.**
3. **Birth is ONE timestamp in the module and TWO in the built detector.** The built PRIOR/T0
   boundary is the target's ONSET (`t0_idx`), while observation starts from a predecessor's
   CONFIRMATION - separated by `PERSIST-1 = 2s`. Populate `birth_recv_ns` from a confirmation
   and every class boundary shifts later, turning built-T0 and built-H+1 calls into PRIOR.
   **If 4.11 keeps a single landmark it must be the ONSET, and the module must say so.**
4. **THE ONE THAT MATTERS: the built prebirth measurement has a large NEGATIVE class and
   `native_recognition` cannot represent one.** At D0 the split is 135,823 positive / 20,562
   negative (`ng_exhaustion_prior_early_model_agent_20260819.py:36-37`). A negative case has a
   boundary but NO BIRTH, and `CandidateRecognition.birth_recv_ns` is a required constructor
   argument - so it cannot be constructed at all. Consequently the module has no null baseline,
   and therefore none of `roc_auc`, `brier_gain_vs_null` or `log_loss_gain_vs_null` - **the
   four things the built gate `model_pass` actually tests**
   (`chain_birth_agents:229-239`). `detection_share` is not a weaker version of those. It is a
   different quantity with nothing to beat.

### And the scoring that survived is NOT the curve

`FRANKIE_NG_EXHAUSTION_REVEAL_BLIND_FINDINGS_FROZEN_20260817.md`, "Do NOT learn": the blind
predictor *"is a deterministic rule-engine... its full-curve RMSE/correlation scores are NOT a
valid measure of Frankie's model forecasting ability"*, and **"The validated finding is
runway/lifespan, not exact future price shape."**

**`3t/5t/8t/13t` are ZigZag PIVOT THRESHOLDS IN TICKS, not time units.** They are the duration
of the retrospective ZigZag leg containing t0, at pivot thresholds of 3, 5, 8 and 13 ticks
(`research/ng_dipole_runway_audit.py:157-197`). I read them as event-relative time landmarks
and proposed a percentage grid; they are a PRICE-EXCURSION scale. The scoring that reproduced
out of sample is an ORDERING - median duration of `A-persistent` exceeds `A-fast-collapse`,
pooled AND per day, holding on all four held-out days at all four thresholds
(`ng_exhaustion_frankie_blind_reveal_score_20260816.py:142-157`).

### What to delete from the proposals, and what genuinely remains
**DELETE:** the PRIOR/T0/HORIZON classification and its boundary rule (settled 2026-08-19/20);
any new candidate or birth definition (4.10 already has one, with a `PREBIRTH` phase and a
`birth_recv_ns`); CENSORED (three built forms); and the claim that 4.11 "uses no horizon at
all" - the built work scans an explicit H grid in order, and dropping it discards the mechanism
that makes "earliest" measurable.
**KEEP, because it does not exist:** MISSED; a negative class inside 4.11; a ruling on whether
`birth_recv_ns` carries the onset or the confirmation; and a call predicate - but shaped as the
built work shapes it, as *the earliest instant at which a declared persistence criterion is
satisfied by causally available evidence, with onset and confirmation recorded separately*.

**Also confirmed: 4.11 is constructed, registered and fed by nothing**
(`native_calculation_runner.py:259, 297`; `RecognitionCalculator.record` is called nowhere), so
none of the above has been exercised on real data.

---

## A. Exhaustion (4.10) - RECOVERED

**A chain is an ordered sequence of detected exhaustion EVENTS inside one trading week**, and
membership is defined by surviving inherited predictive information, not by structure.
`NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json:104, 37, 40`. The stream is the WEEK: a date
change, midnight, HE24->HE1 or a file boundary *"can never create a reset by itself"*
(`AFTERMATH_CAUSAL_VALIDATION_FREEZE_20260817.json:57`).

**The unit is a DIPOLE EVENT - a flow spike - not a price level, an order or a participant.**
Detector: local `|roll20|` max over +/-5s, above the day's 85th percentile, 45s refractory,
ranked by pre-only prominence (`CHAIN_STUDY_CONTRACT:18-23`;
`ng_dipole_native_shape_audit.py:97`). **My proposal made the runway a price level. That is a
different object at a different scale** - roughly 3,429 events in the frozen ledger against
3,094,296 F_LAST groups on two October days.

**The runway is `t0 -> dynamic endpoint`, and the endpoint is the frozen COMPLETION rule:**
*"first three consecutive causal seconds after t0 with oriented roll20 <= 0"*, with
`maximum_duration_seconds: null`, `hardcoded_end_time: false`, and *"If termination never
occurs before available raw data ends, mark endpoint censored. **Never manufacture an
endpoint.**"* (`AFTERMATH_FREEZE:15-22`). It records **structural onset AND causal
confirmation** separately - exactly the two-timestamp structure `RunwayPhase` needs, and it is
threshold-free in the way that matters: no duration cap, no clock.

**BIRTH = a chain reaching depth D, and "extension" is its synonym** (`CHAIN_BIRTH_V2:17-19`),
not a later phase. **PREBIRTH is a timing REGION, never a phase**, with its own registry group.

**A/B/C families and A-fast-collapse / A-persistent are FROZEN AND HASH-BOUND** - a 78-feature
vector over the oriented `t-60..0` curve, counts A=3235 / B=72 / C=122, classifier SHA
`698b956f...`, `no refit`. **B's locality rule was REFUTED on holdout** (alignment ~51/49/51/55%)
and must not be carried forward. **P/O/S/X are AFTERMATH states**, explicitly *"benchmark/
post-hoc interpretation only; never a phase-1 chain cell or boundary rule"*
(`CHAIN_STUDY_CONTRACT:76-84`).

## C. Dipole (4.12) - RECOVERED

**A dipole is a FLOW object, not book geometry**: the trailing-20-second signed aggressor-volume
imbalance at 1s resolution, `(buy-sell)/(buy+sell)`, trade side inferred Lee-Ready off the
concurrent top-of-book mid (`ng_dipole_native_shape_audit.py:73-89`). Its two poles are BUY vs
SELL aggressor volume. The book is a **separate companion channel, never the dipole itself**
(`ng_dipole_runway_audit.py:313`).

**"Geometry" is a term of art: the SHAPE OF THE PRE-EVENT CURVE IN TIME** - a 61-sample oriented
window reduced to 78 features. There is **no spatial or price-ladder axis in it at all**.

**SAME / FLIP already exists and means something else entirely:** *"`SAME` / `FLIP` refers to
current exhaustion polarity relative to the latest predecessor"*
(`CHAIN_PHASE2_MODULE_NOVELTY_FINDINGS_20260818.md:14`). It is a chain-lineage TEMPORAL relation,
frozen with committed counts - **1,546 FLIP / 1,883 SAME of 3,429** - asserted as a hard gate in
four separate files. **The words are taken and the existing meaning has published results.**

**The mirror is ALREADY BUILT, and it is the side-swapped side string**, not a price reflection:
`mirror_identity()` in `a_memory_member_first_recalculation_20260828.py:92-102`, emitting
`mirror_pair_key` and `orientation in {CANONICAL, MIRROR}`, already computed for every open-world
member with 966 mirror-ready keys, and already nominated as the basis for this very section:
*"`ABBN`/`BAAN` ... form a native side-resolved basis for opposing-pressure, direction-change,
and signed-dipole research"*. **That is what `mirror_signed_flow` should be.** My price-ladder
reflection occurs in exactly one file in the repo - my own proposal.

**And `WITH_CURRENT` / `AGAINST_CURRENT` already occupies the "orientation" role**
(`MODULE_NOVELTY_FINDINGS:16-17`).

## D. Duration (4.16) - RECOVERED, AND THIS IS THE BIGGEST CORRECTION

**`t` IS A PRICE TICK, NOT A TIME UNIT.** `TICK = 0.001`; `3t/5t/8t/13t` are **ZigZag reversal
thresholds in ticks**, and 358s / 993s / 1802s / 4386s are the MEDIAN DURATIONS of the legs
those thresholds produce (`ng_dipole_runway_audit.py:22-23, 157-158`). So `A-persistent 8t =
3455s` reads: for A-persistent events, the median duration of the attached ZigZag leg built on
an 8-tick reversal threshold is 3,455 seconds. **It is a SCALE ladder, not a horizon grid.** I
read it as time landmarks and proposed a percentage grid against it.

**Greg's ruling restates a correction frozen on 2026-08-18.**
`NG_EXHAUSTION_DURATION_TARGET_CORRECTION_20260818.md:5`: *"**Exhaustion is being studied as a
duration / remaining-runway signal, not as a direction predictor.**"* The reusable object is
`remaining_s = max(0, baseline_total_s - elapsed_since_t0_s)` against the dynamic endpoint, with
censoring (`RUNWAY_CLOCK_V0_20260817.md`).

**Do NOT reuse the curve.** *"Its full-curve RMSE/correlation scores are NOT a valid measure...
The validated finding is runway/lifespan, not exact future price shape."*

**AND THE FROZEN PROGRAM SOLVES THE CLOCK PROBLEM BETTER THAN MY PROPOSAL DID.** It *does* use
absolute-second horizons - `5, 10, 20, 30, 60, 120, 300` - but anchored on the **dynamic
episode endpoint, "never t0+60 by fiat"** (`AFTERMATH_FREEZE:38-46`). **The fix was never to
abolish horizons; it was to move the ANCHOR to a structural endpoint.** That keeps horizons
comparable across events, which my 25/50/75/100% milestones deliberately gave up. It also has
`first_hit_times` - first +/-3t, +/-5t after the endpoint, *"scanned without an arbitrary
duration cap; censor only when the available continuous market stream ends"* - a first-passage
measure that is the natural companion to duration.

---

## A-BIS. Corrections to my own claims, and the answer on the event clock

**I WAS WRONG ABOUT `ng_exhaustion_v4_exact_candidate_freeze.py`.** I told Greg it was "a frozen
candidate definition" and that it proved the contract's "never defines a candidate" line false.
It is nothing of the kind: `ExactFreezeIdentity` carries a 40-char `candidate_commit_sha` plus
workflow, ruleset, engine, adapter, reconciler and model hashes, and its eight `REQUIRED_CHECKS`
are release-engineering checks. **"Candidate" there means a candidate BUILD. Nothing in it
touches the market.** It also lives in `research/kalshi/`, not `research/`. The real candidate
definition is `ng_exhaustion_chain_canonical_table_20260817.py:220-267`, which is a better
answer anyway.

**THE EVENT CLOCK DOES NOT EXIST IN THE BUILT WORK.** This is the honest answer to Greg's rule.
The only thing named `event_clock` anywhere is a **boolean data-availability flag**:
`ng_exhaustion_runway_clock.py:249-250` raises if it is False, and the live adapter sets it True.
It gates whether a countdown may run; it is not a unit of duration. Every duration in the built
work is SECONDS (`horizons (5,10,20,30,60,120,300)`, the birth ladder `H = 1..3600`,
`PRIOR_LEAD_SECONDS`), and every duration in the new benchmark is NANOSECONDS. **On Greg's rule
the built work and the new modules are equally guilty - one in seconds, one in nanoseconds.**
The only raw material for a real event clock in the repo is `native_clocks.py:174-177`
(`sequence_first/last/span/contiguous` off MBO sequence numbers), and 4.10 does not use it.

**FIBONACCI IS COINCIDENTAL.** Zero occurrences of "fibonacci" or "fib" in `research/`. The set
is a hardcoded `THRESH_TICKS = (2, 3, 5, 8, 13)` whose stated intent is coverage - *"we sweep
several NG-native reversal tolerances so no conclusion depends on one imported crypto
threshold"*. **Decisive: 3 is not the start of anything - 2t was dropped after the sweep** and
its data survives in the record (`C_alignment_reveal_rates` carries a `2t` entry). The four
scales are a truncation of a five-point log-spaced sweep. Do not build on the sequence.

**PHASE_INDEX SCORES 0 OF 11.** Not one of its names is a phase in the built corpus, and **four
are reused with a different referent** - BIRTH is an INSTANT (`t0`), TRANSITION is a chain-level
edge BETWEEN events, EXTENSION is the chain reaching depth D+1, REVERSAL is a price-outcome
class computed AFTER the endpoint. That is worse than absence: it reads as continuity to anyone
who does not open both files. Its whole provenance is one prose line in the 2026-08-28 mission
doc - *"Precursor through completion or reversal"* - from which three names were taken and
eight invented.

**TWO THINGS IN THE NEW MODULES ARE GENUINELY RIGHT AND MUST STAY.**
`native_exhaustion.SEED_STATES` already carries P/O/S/X correctly, and
`native_clocks.RecognitionLabel` already uses PRIOR / T0 / H+N correctly. **Those are the model
for how to reuse the frozen vocabulary** - the rest of 4.10 should look like them.

**AND PREBIRTH SKILL IS NOT ESTABLISHED.** Median positive leads exist (43-47s at H=1 for
D1-D3) but *"These counts do not establish predictive skill"* and *"there is currently no
authorized claim that D1, D2, or D3 validates at any specific PRIOR H"*. The one clue tested
FAILED the 2-of-3 model gate. **Do not build 4.11 on an assumption that prebirth validated.**
There is also a hard CHARACTERISTICS WALL on any prebirth model: it may not use the unborn
target's identity, polarity, family, state or path, nor realized depth or duration, nor time of
day or session position - *"timing is used only for causal availability and actual lead
reporting."*

**MINOR BUT REAL: "runway" now means three different things in this repo** - the ZigZag price
leg, `native_exhaustion.ExhaustionRunway`, and `native_absorption.RunwayPressure`. Whatever
4.10 settles on, that word needs disambiguating.

---

# THE SIX COLLISIONS BETWEEN THE FROZEN LEARNING AND THE BUILT SECTIONS

These are the findings that matter, because none of them would fail - the numbers would just be
a different quantity than the name says.

**F1. `native_dipole`'s SAME/FLIP is a different variable from the frozen one, and cannot hold
it.** The module says the two ways a mirrored structure relates to its counterpart
(cross-sectional); frozen says polarity versus the latest predecessor (temporal). Worse,
`DipolePath.__post_init__` refuses a path holding more than one orientation - and the frozen
motifs (`OOSS->FLIP`, `SOOS->SAME`) are **sequences whose whole point is that orientation
alternates**. A frozen chain motif cannot be expressed as a `DipolePath` at all.

**F2. THREE mirror vocabularies now exist over one set of facts** - `mirror_identity()`'s
side-swap (built and ran), `native_dipole.orientation`, and my proposal. Contract 4.4 mandates
exactly one mechanically defined mirror key. **This is the `_family_id` defect at project scale
and it is already live in committed code, not just in a proposal.**

**F3. 4.16's horizon grid is a wall clock the frozen program forbids** - *"Timing is an output,
not a predeclared input grid"* - but the frozen fix is a better one than mine: same absolute
horizons, anchored on the structural endpoint.

**F4. `PHASE_INDEX` is a 2026-08-28 CONTRACT INVENTION, not recovered learning.**
`FIRST_DEVIATION` and `INFLECTION` occur NOWHERE in the frozen corpus. And two of its phases
collide with frozen terms: `EXTENSION` is intra-runway here but IS CHAIN BIRTH there;
`REVERSAL` is a terminal phase here but is `O`, one of four aftermath states, there. So a
`RunwayPhase` sequence and a P/O/S/X motif describe one object in two vocabularies - and
`native_exhaustion.SEED_STATES` already carries P/O/S/X in the state slot, so both live inside
one dataclass with no declared relation.

**F5. THE REASON THE SECTIONS WERE NEVER FED.** The frozen candidate is a 1-second flow event
needing a per-second roll20 series over a day; the built candidate is a nanosecond F_LAST group.
The registry REQUIRES the bridge - `derived_roll20_and_dipole_state`, `legacy_per_second_roll20`,
`derived_open_world_predecessor_state`, all CAUSAL_STREAM_REQUIRED - and **no code in
`frankie_raw_mbo_benchmark/` computes roll20 or any dipole from the MBO stream.** The only
`roll20` references are layer-name strings in the gate. **The frozen substrate is specified as
required input and was never built. That is why 4.10, 4.11 and 4.12 had nothing to feed them,
and no adapter on the F_LAST unit fixes it.**

**F6. `DipoleStage` types the dipole as a book object** - `bid_depth`, `ask_depth`,
`normalized_imbalance` from DEPTH - while the frozen dipole is a trade-flow ratio in [-1,+1].
Feeding depth-derived orientation into a section named for the frozen dipole is the
"present, typed, in range and wrong" failure exactly.

---

# WHAT THIS MEANS FOR THE NEXT SESSION

**Do not build the six adapters as specified.** F5 says the missing layer is not an adapter on
the F_LAST group - it is the **per-second roll20 / dipole substrate**, which the registry
requires and which does not exist. Building F_LAST-group adapters for 4.10/4.11/4.12 would
produce a second vocabulary at the wrong scale and it would not fail.

**The four proposals are withdrawn.** Every definition in them is either already frozen (and
mine differs), or occupies a name that is taken. The honest remainder is small: MISSED (which
does not exist), a negative class inside 4.11, and a ruling on whether `birth_recv_ns` carries
the onset or the confirmation.

**The one genuinely open design question for Greg** is whether an F_LAST-group-local dipole is
admissible at all, given that every prior dipole result is per-second. If the answer is no,
4.12 needs a second clock, not a definition.
