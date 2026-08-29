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

## A. Exhaustion (4.10), C. Dipole (4.12), D. Duration (4.16)

Recovery in flight. Sections to be appended as they land.
