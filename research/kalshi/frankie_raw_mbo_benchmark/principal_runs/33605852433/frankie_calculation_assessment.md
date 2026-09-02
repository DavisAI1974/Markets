# Calculation-surface assessment: which of the sixteen sections earn their place

REAL_TIME_FRANKIE, arm A_CLEAN, run `frankie-a-clean-rt-33605852433-1`
Source: `glbx-mdp3-20211003.mbo.dbn.zst`, instrument_id 111313, 57,027 native MBO records,
43,569 F_LAST-closed groups, one continuity segment (18904), causal clock `ts_recv_ns`.
Calculation contract sha256 `6c46073...`, result hash `cb685e0e...`.

**Scope warning that governs every verdict below.** 43,366 of 43,569 groups (99.53%) are
PRE_SETTLEMENT and 203 (0.47%) are PRE_OPEN. One day, one instrument, one continuity segment,
a Sunday reopen. All 19 lawful invocation cutoffs fall in PRE_SETTLEMENT. Wherever a verdict
turns on that, it is said in the section.

**Retention is not the question and this document does not re-open it.** The byte attribution
settles it: of the run's 10,838,754,711 bytes, the exact member ledger is 97.95% and its
`book_full` field alone is 10,131,179,453 bytes (93.47% of everything, 95.43% of the member
ledger). All sixteen calculations together — the entire lifecycle-and-runway ledger — are
192,510,728 bytes, **1.78%**. The whole exhaustion programme (4.10, 4.11, 4.12, 4.16 plus the
candidate ledger) is 1,813,721 bytes, **0.0167%**. No calculation can be argued away on cost.
The question this document answers is what each one *tells* you, and where it is currently
telling you nothing, the smallest change that would make it informative.

---

## Summary table

| § | Section | Verdict | One-line reason |
|---|---------|---------|-----------------|
| 4.1 | Identity, integrity, exact member surface | **EARNS_ITS_PLACE** | 0 cursor discontinuities / 0 duplicate groups / 0 FIFO failures over 43,569 groups, with the phase histogram that scopes every other claim |
| 4.2 | Daily book regime companion | **NO_VALUE_AS_COMPUTED** | It did not run at all — zero rows, zero summary, no key anywhere in the result — while `book_full` at 93.5% of all bytes is the input it needed |
| 4.3 | Open-world event families | **EARNS_ITS_PLACE** | 205 exact strata, 123 singletons retained, and the cascade grammar no carried vocabulary contained; but family_id = the literal action string, which degenerates every section that strata on it |
| 4.4 | Mirrored members and matched pairings | **NO_VALUE_AS_COMPUTED** | 0 pairs formed out of 3,454 stages, and no matching-distance or unmatched-reason record, so the matcher's failure cannot even be diagnosed |
| 4.5 | Formation, serialization, observation clocks | **EARNS_ITS_PLACE** | The only measure in the artifact with zero degenerate strata: 57 large strata, 57 distinct medians spanning 106 us to 300 ms; delivered the adverse-selection gradient. One channel (decision clock) is empty |
| 4.6 | Queue position, priority, order survival | **EARNS_ITS_PLACE** | Kaplan-Meier with at-risk counts found a two-population survival curve and an 84x-237x PRE_OPEN vs PRE_SETTLEMENT median split that a mean would have erased |
| 4.7 | Replenishment and liquidity resilience | **EARNS_IT_BUT_MISCOMPUTED** | Survival and quantity channels are the run's cleanest causal contrast (touch defended 379-405x faster than behind it); the headline `restoration_ratio` is an arrival-density measure, not a replacement ratio |
| 4.8 | Absorption, withdrawal, delivered pressure | **EARNS_IT_BUT_MISCOMPUTED** | The disposition census is real and useful (withdrawal beats delivery 99:1); but `same_side_replacement_ratio` has a zero numerator in all 205 strata, and absorption + withdrawal is identically 1 in all 192 |
| 4.9 | Price-ladder topology | **NO_VALUE_AS_COMPUTED** | It is computed on a one-level, one-sided book: occupied levels are 0 or 1 on 40,269 of 40,272 transitions, and 152 of 154 imbalance readings are exactly +/-1.0, while 4.12's identical formula reads [0.0116, 0.1109] |
| 4.10 | Exhaustion state, birth, persistence, completion | **EARNS_IT_BUT_MISCOMPUTED** | The runway skeleton is right and lawfully censored; but two of six measures are structurally zero, a third is a censoring artifact, and a fourth (SEARCHED) has zero duration everywhere |
| 4.11 | Prebirth prediction and H+N recognition | **CANNOT_JUDGE_YET** | PRIOR is unreachable by the unit's own construction, detection_share = 1.0 is a tautology over the detector's own output, and the first-call rule was never exercised (0 failed states) |
| 4.12 | Dipole and opposing-pressure runway | **EARNS_IT_BUT_MISCOMPUTED** | It produced the run's one genuine decoupling result (imbalance flat while flow swings), but 1,692 strata over 3,454 observations means the modal "average" is n=1, and the mirror channel is empty |
| 4.13 | Chain families and D-depth lineages | **EARNS_IT_BUT_MISCOMPUTED** | The A-vs-TRADE interstage bimodality is real; but the censored-age channel is empty while 21,603 of 21,651 nodes are censored, and the section's own root count does not reconcile with itself |
| 4.14 | Recurrence, bursts, transition graphs | **EARNS_IT_BUT_MISCOMPUTED** | The transition-edge index is the best open-world artifact in the run; the three averaged measures are not recurrence — `interarrival_gap_ns` is byte-identical to 4.5's within-group receive gap |
| 4.15 | Open-world cluster and new-structure discovery | **CANNOT_JUDGE_YET** | Declared not-run (`NO_CLUSTERING_D5`) under D5, so nothing is licensed; separately, 99.5% of averaged rows carry a blank cluster_version rather than that declaration |
| 4.16 | Fixed causal future-response table | **EARNS_IT_BUT_MISCOMPUTED** | Correct at-risk discipline per horizon, but it emits 1 of the 7 response channels the contract names, and its conditioning key `starting_liquidity_regime` takes one value on all 84 rows |

Counts: EARNS_ITS_PLACE 4, EARNS_IT_BUT_MISCOMPUTED 7, CANNOT_JUDGE_YET 2, NO_VALUE_AS_COMPUTED 3.
Every NO_VALUE_AS_COMPUTED here is a **fix instruction**, not a deletion: 4.2 never ran, 4.4's
matcher produced nothing, and 4.9 is reading the wrong book. All three have a small, named fix.

---

## Defect register

Four were already reported in my 44 findings; thirteen are new here; one is a correction to my
own earlier claim. Every one is a number that is present, typed, in range, and measuring
something other than what its name implies — the failure class this programme exists to catch.

### Carried forward

**D-1. The decision clock is empty (4.5).** `f_last_to_decision_delay_ns` has n=0 in all 205
strata with `excluded_missing_members` summing to exactly 43,569 — every member. The declared
missingness rule is "members with no decision time are excluded and counted", so the measure
ran and found no decision times. Consequence: nothing in this artifact can separate *lawfully
knowable* from *acted upon*. Three of the mission's four clocks are populated; the one that
makes the other three actionable is not.

**D-2. 4.10 depletion and refill are identically zero.** `phase_depletion` and `phase_refill`
are 0.0 at mean, p10, p50, p90, p99, min and max in **all 109** state x phase x family x side
strata, over 344 observations, with **zero exclusions** and a declared missingness rule of "no
exclusions". A measure that ran and was handed zeros. It is why no runway can be described in
terms of liquidity consumption.

**D-3. 4.7's `restoration_ratio` is an arrival-density measure.** The runner attributes each
refill to *every* pending episode in the neighbourhood: 441,404 refills attributed across
24,283 episodes = **18.18 attributions per episode**. Aggregate numerator 748,271 over
denominator 52,541 gives 14.24. That is how much liquidity lands within one tick and 60 s of a
removal — not how much came back for what left. Median removed quantity is 1-2 lots.

**D-4. 4.2 is absent entirely.** A full-text walk of the result for `4.2`, `book_regime`,
`daily_book`, `first_book`, `last_book`, `spread` returns four hits, none of them a 4.2 output:
one gate surface id, two byte-accounting entries for `book_full`, and one `frame_keys_carried`
entry. No first/last snapshot pair, no per-day min/max/mean for spread, depth, order count or
level count, no group count or max-actions-per-group companion.

### New in this pass

**D-5 (the largest). 4.9 is computed on a one-level, one-sided book, and 4.12 proves it.**
- `occupied_level_count` over 40,272 ladder transitions: **20,266 observations exactly 0,
  20,003 exactly 1**, and precisely three above 1 in the entire day (121, 76 and 2 — the first
  two being the PRE_OPEN reopen snapshot). So 40,269 of 40,272 transitions (99.99%) see at most
  one occupied price per side.
- `relative_imbalance`, declared as `(bid - ask)/(bid + ask)`, **book-level**: n=154 with 40,118
  excluded, and **152 of those 154 are exactly +1.0 (90) or -1.0 (62)**. Only two observations
  in the whole day had both sides simultaneously non-empty.
- 4.12's `normalized_imbalance` is the **identical formula** on the same day and instrument:
  n=3,454, zero exclusions, range **[0.0116, 0.1109]**, grand mean 0.0538, never once at +/-1.

Two sections computing one estimand cannot both be right. A book that yields +/-1 on 152 of 154
readings has one empty side; a book that yields 0.0116-0.1109 on 3,454 readings has two. 4.9 is
reading a side-local, top-of-book view — not the reconstructed full book that the member ledger
stores at 10.13 GB. Every one of 4.9's eight measures (2,840 averaged rows, 24.5 MB of ledger)
inherits this, which is why `level_birth_count`, `level_death_count`, `occupied_level_count` and
`absolute_total_depth` are degenerate (min = max) in **all 355 strata across all 40,272
observations**. All eight section-6 gates passed with this in place, because nothing in the
contract compares one section's estimand against another's.

**D-6. 4.14's `interarrival_gap_ns` is 4.5's `within_group_receive_gap_ns`, exactly.** Both have
n = **13,458**; both sum to **10,437,153,281,209 ns**; both have maximum
**10,436,764,315,270 ns** (the reopen snapshot's formation gap). The two are the same
observations re-stratified — 4.5 by family x channel x component count, 4.14 by transition node.
So the section charged with "this structure happened again" is measuring the spacing of
components *inside* one group, which is serialization, not recurrence. Meanwhile 4.14's own
summary reports **19,625 multi-occurrence order paths** and **21,651 same-order paths**: the
actual recurrence population exists in the traversal and receives no averaged companion at all.

**D-7. 4.8's `absorption_ratio` and `withdrawal_ratio` are algebraically complementary.** In
**all 192** nonempty strata, `absorption_numerator + withdrawal_numerator == depletion
denominator` exactly (aggregate 6,546 + 38,164 = 44,710), and `mean_of_member_ratios` for the
two sums to exactly 1.0 in all 192. They carry one degree of freedom, not two. 410 averaged rows
and the full coequal-ratio apparatus are spent on an identity. Nothing is *wrong* in the
arithmetic; the label "coequal views answering different questions" is wrong.

**D-8. 4.8's `same_side_replacement_ratio` never fires.** `numerator_total` is **0.0 in all 205
strata** against a denominator total of 44,710 and 18,952 member observations. Either same-side
replacement is not being attributed to the runway, or the numerator is not wired. The contract
names same-side replacement as one of seven exact 4.8 quantities, and it is the one that would
distinguish a maker retreating from a maker being run over.

**D-9. 4.13's censored-age channel excludes the censored.** `censored_stage_age_ns` has n=0
across all 17 strata with **21,651 excluded** — while the section's own status counts are
`CENSORED_STREAM_END: 21,603`, `TERMINATED: 48`, `OPEN: 0`. A measure whose declared population
is censored stages excluded 100% of them, including the 21,603 that are censored. 4.6's
equivalent (`censored_age_ns`) works correctly with n=597 against 597 declared censorings, so
this is a 4.13-local defect, not a shared convention.

**D-10. 4.16 emits 1 of 7 response channels, and its conditioning key never varies.**
`value_names` is `["price_response"]`. The contract requires "native price, flow, full-book,
queue, survival, transition, and completion changes"; flow, full-book, queue, survival,
transition and completion are absent. It also requires emission "at every available event-driven
change point *and* at versioned fixed H+N horizons" — only the three fixed horizons
(1 s / 10 s / 60 s) were emitted. Separately, `starting_liquidity_regime` is
**`DEPTH_SKEW_BID` on all 84 at-risk rows**, so the stratum dimension the contract requires
for conditioning does no conditioning. Given D-5 I read that as downstream of the same
one-sided book, but I cannot prove the derivation from this artifact and do not claim it.

**D-11. Two more 4.10 channels are structurally zero.** `phase_duration_ns` for the **SEARCHED**
phase is min = max = **0.0** for all 91 candidates — the phase the contract names first
("searched coverage") has no duration anywhere. `recurrence_count` is min = max = **0.0** in all
28 strata over 91 candidates. Neither has a single exclusion. Combined with D-2, four of 4.10's
six measures carry no information.

**D-12. 4.12 is stratified past the point where an average exists.** 1,692 strata for **3,454
observations**: 848 strata (50.1%) have n=1, 1,307 (77.2%) have n<=2, and **not one stratum
reaches n=30**. The averaged-companion layer for 4.12 is 6,768 rows — 41.5% of the entire
16,293-row averaged layer — describing a population where the modal "average" is a single
member restating itself. The stratum key includes `stage=k`, a *within-path index*, so honouring
"never average across event phase" to the letter shattered the population. Also: 4.12's stages
are only `BIRTH` (220) and `PERSISTENCE` (3,234). **There are no REVERSAL stages**, though 4.10
records 90 of 91 runways as reversed.

**D-13. 4.6 declares one population for two different units.** `initial_volume_ahead` has
n = 20,005 (one per tracked order birth); `queue_movement` has n = **24,645**. Both carry the
identical declared population, "resting orders within the stratum and continuity segment". The
difference, 4,640, sits against 4,625 `modify_reprice` events, so `queue_movement` is plainly
per queue *episode* while `initial_volume_ahead` is per order. Fifteen observations are
unaccounted for on that reading.

**D-14. 99.5% of averaged rows carry a blank cluster version.** Contract section 3 requires every
average to declare "family, subfamily, and cluster version". `cluster_version` is the empty
string on **16,209 of 16,293** rows; only the 84 4.16 rows declare `NO_CLUSTERING_D5`. An empty
string is not a declaration that clustering did not run.

**D-15. 4.13's root count does not reconcile with itself.** `d0_roots: 21,296` against
`role_counts.ROOT: 21,344` and `depth_distribution` D0 count 21,344 — a difference of exactly
**48**, which is exactly the `TERMINATED` count. With 307 descendants and observed max depth 1,
neither 21,344 - 307 = 21,037 nor 21,296 is obviously the "roots with no qualifying successor"
the contract defines. I state the arithmetic and do not guess the intent.

**D-16. 4.4 records no matching distance and no unmatched reason.** Contract 4.4 requires
retaining "pair IDs, unmatched members, exact differences, and matching distance". The artifact
has zero pairs, 3,454 unmatched stages, and neither a distance distribution nor a per-reason
unmatched counter. So the matcher's total failure is visible but undiagnosable from the
delivered evidence.

### Correction to my own prior finding

**F-32 overstated.** I wrote that `depth_concentration_at_touch` is "exactly 1.0 in all 20,006
observations where a side was non-empty". It is 1.0 in **20,003** of 20,006; three observations
are not (0.0025189, 0.0107527, 0.5) and they are the reopen-snapshot rows. The direction of the
finding is unchanged; the count was wrong and is corrected here.

---

## Per-section detail

### 4.1 Identity, integrity, and exact member surface — EARNS_ITS_PLACE

**What it gave.** 57,027 native records closing into 43,569 F_LAST groups, **all 43,569 closed**;
`cursor_discontinuities` 0, `duplicate_group_indices` 0, `fifo_reconstruction_failures` 0;
one instrument (111313), one continuity segment (18904), `segments_opened` 1. Session assignment
independently recomputed from `ts_event_ns` via the CME rule: **0 phase mismatches and 0 segment
mismatches over 43,569 assignments**. Phase histogram PRE_SETTLEMENT 43,366 / PRE_OPEN 203.
Reconciliation: 43,569 exact member rows and 243,270 exact lifecycle rows beneath 16,293 averaged
rows summarizing 845,120 observations, with `exact_members_present_beneath_summaries` true.

**Why it earns.** It is the only section that licenses the rest. The 99.53% PRE_SETTLEMENT
figure is what forces every other verdict in this document to be scoped, and it came from here.
Cheap by construction (boolean/count/hash, no averaged rows, contract-correct).

**Change.** One addition: the phase histogram should be emitted *beside every section's stratum
counts*, not only in the reconciliation receipt, so a reader of one section cannot miss that the
day is single-phase.

### 4.2 Daily book regime companion — NO_VALUE_AS_COMPUTED (it did not run)

**What it gave.** Nothing. Zero averaged rows (4.2 is absent from `layers.averaged_companions`),
no section summary, no first/last snapshot pair, no key matching any 4.2 term anywhere in the
34 MB result.

**Why this is the sharpest waste in the run.** The input is not missing — it is the single
largest thing in the run. `book_full` is 10,131,179,453 bytes, 232,530 bytes per group, 93.47%
of every byte the run produced, and it is in `traversal.frame_keys_carried`. The full book was
captured, streamed, hashed and retained for all 43,569 groups, and no per-day regime summary was
computed from it. The contract's 4.2 average decision is an unambiguous **yes** with a named
field list.

**Bar to be worth keeping (it is already met in principle).** Emit first / last / min / max /
arithmetic mean for spread, full-depth imbalance, bid and ask depth, bid and ask order count,
bid and ask level count, denominator = F_LAST-closed groups in the day, beside action/side
totals, group count and max actions per group. On this day I would expect it to show a spread
and depth profile that changes across the PRE_OPEN to PRE_SETTLEMENT boundary and a level count
that immediately contradicts 4.9's one-level view — which is why it is also a diagnostic.

**Change.** Compute it, and make it the source of 4.16's `starting_liquidity_regime` (D-10),
which currently takes one value on all 84 rows.

### 4.3 Open-world event families and exact members — EARNS_ITS_PLACE

**What it gave.** 205 exact family x subfamily x side x phase strata over 43,569 members. The
four largest strata are 71.5% of members, the top eleven 95.5%; **123 strata (60%) hold exactly
one member** and were retained with their own deterministic IDs rather than folded. 80.9% of
groups carry a single action; the largest carries 245. The carried seed vocabulary crosswalks
cleanly: elementary A 16,199 / C 15,136 / M 3,896, AN 3,727, CN 2,182, MN 794, and the
trade-bearing seeds two orders of magnitude rarer (TFCN 812, TFC 162, TFM 139, TFFCCN 32). It
also preserved a cascade grammar no carried vocabulary contained: every group of 25+ components
is an alternating trade/fill run against one resting side terminated by an uninterrupted
same-side mass cancel, up to 28 fills then 21+6 cancels in one group.

**Why it earns.** Open-world retention worked. Nothing was rounded to a nearest carried label,
and the one structure that mattered most (the cascade) is one that no allowlist would have kept.

**Defect that belongs to 4.3 but is charged to its consumers.** `family_id` is derived from the
literal action/side string. That makes it a near-perfect predictor of any measure that is a
function of the action string, which is why 4.9 is 100% degenerate within stratum and 4.8 is
97.6% (18,506 of 18,952 observations sit in strata where the member ratio's min equals its max).
The informative variation in those sections is *between* families, and the within-stratum
distribution is a point mass carrying no information.

**Change.** Emit a second, coarser family axis alongside the exact one — for example
(component count band) x (contains trade) x (terminal disposition) — so that consumers can
stratify on something that is not a restatement of the measure. Keep the exact ID as canonical.

### 4.4 Mirrored members and matched pairings — NO_VALUE_AS_COMPUTED

**What it gave.** `paired_mirror_difference`: n = 0 in **all 1,692 strata**, with
`excluded_missing_members` totalling **3,454** — every stage unpaired. Section 4.4 contributed
no averaged rows of its own. So the mission's third seed hypothesis (that mirrored side
sequences organize opposing-pressure state) is **untested**, not refuted. Absence of matched
support and matched support showing no difference are different results and only the first
happened.

**Bar to be worth keeping.** One number: a nonzero pair count with a matching-distance
distribution. Specifically, over the 91 candidates (45 side A, 39 side B in the 4.16 strata),
a declared deterministic rule on lawful pre-event covariates should form some pairs or state
why none qualify. If after that the pair count is still zero on a two-sided weekday tape, the
mirror estimand should be re-specified rather than re-run.

**Defect.** D-16: no matching distance, no unmatched-reason counter. Zero pairs with no
diagnostic is the least informative possible outcome — one counter would have told us whether
the rule found no candidates, found candidates outside the distance bound, or was never invoked.

**Change.** (1) Emit `matching_distance` distribution and unmatched-reason counts even when the
pair count is zero. (2) State the matching rule in the declaration block the way every other
measure states its numerator formula — 4.4's is the only estimand in the artifact whose
definition cannot be read off the output.

### 4.5 Formation, serialization, and observation clocks — EARNS_ITS_PLACE (top three)

**What it gave.** The most discriminating output in the artifact. `event_to_receive_latency_ns`:
57,027 observations over 205 strata, **zero degenerate strata**, 57 strata at n>=30 carrying
**57 distinct medians** spanning **106,442 ns to 300,329,573 ns — a 2,822x range**. Median
event-to-receive latency rises monotonically with component count: 106-192 us at 1 component
(35,231 groups), 181-662 us at 2, 354 us to 5.1 ms at 3, ~1.0 ms at 17, then 118.3 ms at 24,
**300.3 ms at 59** (the mass-fill cascade) and 253.8 ms at 245 (the reopen snapshot).
`formation_latency_ns` is identically 0 for the 35,231 single-component groups by construction
and p50 20.1-22.7 us for two-component families, 47.9 us at four. `within_group_receive_gap_ns`
n=13,458 with 35,231 correctly excluded as single-component. `noncontiguous_sequence_members`
6,287; `multi_channel_members` 0.

**Why it earns.** It produced the run's one operationally actionable structural fact: **the
largest and most informative liquidity events are the last to become lawfully observable**. By
the time the 59-component cascade is readable, ~300 ms of event time has passed against a
106-192 us median for the 80.9% of the tape that is single-action. That is an adverse-selection
gradient built into the transport, and it is not derivable from any other section. It is also
correctly fenced: the section stamps `interpretation_domain: SERIALIZATION_FEED` and states that
an economic reading is a separate claim.

**Defect.** D-1, the decision clock — 43,569 of 43,569 excluded.

**Change.** Populate `decision.ts_recv_ns` even when it equals F_LAST availability, and stamp a
basis field saying which (`DECISION_EQUALS_F_LAST` vs an actual downstream decision point). An
identically-zero delay that is *declared* identical is evidence; an empty channel is not.

### 4.6 Queue position, priority, and order survival — EARNS_ITS_PLACE (top three)

**What it gave.** 20,005 completed lifecycles, 19,408 resolved, 597 censored, `fifo_identity_
violations` 0. Kaplan-Meier with at-risk counts at every time (8,528 curve points in the largest
stratum) rather than an arithmetic mean, and `arithmetic_mean_forbidden` on the estimator.
Result: survival is **two-population, not one distribution with a tail**. In the dominant bid-add
birth stratum (`ow-3a12d9bd4a731b597f0d`, side B, PRE_SETTLEMENT, 8,534 orders, 8,260 events,
274 censored) 10% of orders are gone by **1.19 ms**, the median lives **3.19 s**, a quarter
survive past 17.0 s, a tenth past 105.9 s, and **2.74% are still resting at 7,196 s**. The ask
mirror (`ow-f6ba7eaa9e45ef1b68cf`, 7,527 orders, 7,265 events, 262 censored) is the same shape
with a shorter median. And the phase split is enormous: ask-side PRE_OPEN births (73 orders,
53 events, 20 censored) have a median time-to-exit of **217.4 s** and 27.4% still resting at
9,653 s; bid-side PRE_OPEN births (65 orders, 38 events, 27 censored) a median of **755.2 s**
and 41.5% still resting at 9,892 s — **84x and 237x** the same families' PRE_SETTLEMENT medians
of 2.60 s and 3.19 s. Queue position: median volume ahead at birth is 1 in both dominant strata
(side B mean 1.396, p90 3, p99 11, max 30; side A mean 1.570, p90 4, p99 17, max 42), and 0 in
the add-with-neutral-close strata. `resolved_lifetime_ns` shows 6 large strata with 6 distinct
medians spanning 1.9 ms to 145.6 s.

**Why it earns.** It is the only section whose estimator is chosen to refuse the wrong answer,
and it is the section that found the day's clearest population split. On a 0.47% PRE_OPEN slice
it still resolved a difference of two orders of magnitude, with at-risk counts attached.

**Defects.** (a) `BIRTH_GROUP_STRATUM`, declared by the runner: **19,462 of 20,005 lifecycles
(97.3%) outlive their birth group** and 64 are alive in a different session phase, yet family,
side and phase are stamped at birth and never restamped. Birth is a lawful causal label, so the
curves stand, but a stratum describes *where an order was born*, not the conditions it lived
through. (b) D-13, the unit mismatch (20,005 vs 24,645 under one declared population).

**Change.** (1) Emit a second, time-varying stratum stamped at *exit* alongside the birth stamp,
so "orders that died during a cascade" becomes askable — currently it is not. (2) Split
`queue_movement`'s declaration to say "queue episodes", and reconcile the 15 unexplained.
(3) Join key to 4.7: a 4.7 removal episode is a 4.6 terminal, and there is no field connecting
them (see Missing joins).

### 4.7 Replenishment and liquidity resilience — EARNS_IT_BUT_MISCOMPUTED

**What it gave.** 24,283 episodes opened, 24,232 resolved, **1,903 never restored**, 51
censored at the 60 s horizon, 22,369 restoration events. The cleanest controlled contrast in the
run, because it changes exactly one thing: **the touch is defended two to three orders of
magnitude faster than the level behind it.** Within `ow-40540069fe5aeddc127b` side B, KM median
time-to-restoration is **1.775 ms AT_TOUCH (n=556) against 673.1 ms BEHIND_TOUCH (n=7,636)** — a
factor of 379. Within `ow-59ace24da4a485c605b6` side A: **1.379 ms (n=400) against 558.8 ms
(n=6,501)** — a factor of 405. Same family, same side, same phase, same day; only `touch=`
changes. The coequal ratio views then do real work: behind the touch,
mean-of-member-ratios far exceeds ratio-of-aggregate-sums (14.86 vs 9.65 over n=7,622;
24.34 vs 14.73 over n=6,475), meaning small removals get proportionally far more back; at the
touch the two views nearly coincide (44.01 vs 42.63; 39.37 vs 39.20; 34.06 vs 33.60). Behind the
touch replenishment is size-dependent; at the touch it is size-invariant.

**Why the miscomputation matters.** D-3. The ratio's magnitude (aggregate 14.24, strata 9 to 44)
is an arrival density, because every refill is attributed to every pending episode within one
tick — 441,404 attributions over 24,283 episodes. The *contrast* between AT_TOUCH and
BEHIND_TOUCH survives it (both arms carry the same attribution rule), and so does the
mean-vs-aggregate divergence. The *level* does not, and "nine to forty lots come back for every
lot removed" is not a statement this measure supports.

**Change.** Emit a second, disjoint attribution: each refill credited to exactly one episode
(nearest pending by price then by time), retained beside the current many-to-many view and
labelled as a different estimand. Keep both; the density view is genuinely informative about
neighbourhood liquidity arrival, it is just not a replacement ratio. Also emit
`attributions_per_episode` per stratum so the density is visible in the row rather than only in
the traversal counters.

### 4.8 Absorption, withdrawal, and delivered pressure — EARNS_IT_BUT_MISCOMPUTED

**What it gave.** Over all 43,569 group-scoped runways: INDETERMINATE **24,617 (56.5%)**,
ACCOMPANIED_BY_WITHDRAWAL **17,327 (39.8%)**, ABSORBED_WITHOUT_PRICE_MOVE **1,450 (3.3%)**,
DELIVERED_THROUGH_PRICE **175 (0.40%)**, SPARSE 0. **Withdrawal outnumbers delivery through
price 99 to 1.** Aggregate absorption 6,546/44,710 = 0.146, withdrawal 38,164/44,710 = 0.854,
depth survival 39,151/44,710 = 0.876. `discovered_disposition_counts` is empty — the carried
three-label vocabulary was sufficient, nothing new was discovered.

**Why it earns anyway.** The disposition census is a real market statement about this tape and
it is honest about its own hole: the INDETERMINATE 56.5% is the single-action groups, which
carry no trade and no measurable depletion and contribute n=0 to every ratio. 56.5% of the day
supplies no absorption evidence, and that is reported rather than absorbed into a denominator.

**Defects.** D-8 (`same_side_replacement_ratio` numerator 0 in all 205 strata), D-7 (absorption +
withdrawal identically 1 in all 192 nonempty strata, in both coequal views), and the family
degeneracy inherited from 4.3: **181 of 192 nonempty strata have min = max on the member ratio,
covering 18,506 of 18,952 observations (97.6%)**. `ow-3a98bbe15cb2bf0c14ba` (n=404) reads
absorption exactly 0.6667 at mean, p50, p90 *and* max; `ow-b13ef7b8d0191e4e0d42` (n=70) reads
exactly 1.0 throughout. `depth_survival_ratio` additionally has **24,617 zero-denominator
members** — exactly the INDETERMINATE count. `price_response_raw` is 0 at min and max in 85
strata covering 43,393 of 43,569 observations.

**Change.** (1) Fix or refuse `same_side_replacement_ratio` — a channel with a structurally zero
numerator across a whole day should hard-declare, not report 0.0 as a value. (2) Replace one of
absorption/withdrawal with a genuinely independent second quantity: **traded quantity over
opposite-side retreat**, which the contract names ("opposite-side retreat") and which is not
currently emitted. (3) Stratify the 43.5% that carry a ratio by *trade presence* rather than by
family, so within-stratum variation exists.

### 4.9 Price-ladder topology — NO_VALUE_AS_COMPUTED (wrong substrate; fix, do not remove)

**What it gave, and why none of it is usable as a market statement.** 40,272 ladder transitions:
touch_state UNCHANGED **40,264**, COMPRESSION 4, EXPANSION 4. `depth_concentration_at_touch`
is exactly 1.0 in 20,003 of 20,006 non-empty-side observations. `price_gap_raw` is observable in
**196 of 40,272** transitions, 195 of them inside the single PRE_OPEN reopen group (side B: 120
gaps, p10 1 tick, p50 8, p90 46, max 978; side A: 75 gaps, p10 3, p50 14, p90 66, max 1,380) and
exactly one elsewhere. `touch_migration_raw` yields 69 observations, 61 of them zero.
`occupied_level_count` is 0 (20,266) or 1 (20,003) with three exceptions. All 355 strata are
degenerate (min = max) on `absolute_total_depth`, `level_birth_count`, `level_death_count` and
`occupied_level_count`.

Taken at face value that says the instrument is a one-tick, one-level, mostly one-sided market
whose touch never moves. It is not: D-5 shows 4.12 reading a two-sided book with imbalance
0.0116-0.1109 on 3,454 stages, and 4.6 tracking 20,005 orders with queue depth ahead of them.
4.9 is reading a different, thinner object than the book the run captured.

**Bar to be worth keeping.** After binding 4.9 to `book_full`: `relative_imbalance` should have
an observation count of the same order as `absolute_total_depth` (tens of thousands, not 154)
and a distribution that is not concentrated at +/-1; `occupied_level_count` should exceed 1 on a
material share of transitions; and its imbalance readings should agree with 4.12's to within
sampling on the stages where both exist. If after that fix the ladder is still one level per
side, then it is a market fact about a Sunday reopen and 4.9 becomes CANNOT_JUDGE_YET pending a
weekday.

**Change.** Bind every book-derived measure in 4.9 to the same reconstructed full book stored in
the member ledger, and add a cross-section agreement check on `relative_imbalance` vs
`normalized_imbalance` (see the single highest-value change).

### 4.10 Exhaustion state, birth, persistence, and completion — EARNS_IT_BUT_MISCOMPUTED

**What it gave.** 91 runways opened, **0 completed, 0 still open, 91 censored**; 90 recorded as
reversed, 1 censored before reversal. Two open-world structural states discovered
(`OW_1b406d5ef0b2d32d` n=178, `OW_fa0c9c97f63e8551` n=166) and they are **perfectly side-locked**
— the first appears in 59 side-A strata and never on B, the second in 50 side-B strata and never
on A — so the discovered state is a re-encoding of side, not an independent axis.
`discovered_named_states` empty, `discovered_phases` empty. Four of eleven carried phases
observed: SEARCHED (91), BIRTH (91), PERSISTENCE (71), REVERSAL (91). BIRTH durations run
7-53 s; PERSISTENCE 3-190 s.

**Defects.** D-2 (depletion and refill identically 0.0, 344 observations, zero exclusions),
D-11 (SEARCHED duration identically 0.0; recurrence_count identically 0.0), and the censoring
artifact: **every REVERSAL duration and every `censored_runway_age` shares the identical
nanosecond remainder 372,071,705**, meaning they all end at one common wall-clock instant — the
end of the observation window — while BIRTH and PERSISTENCE durations are exact multiples of
1e9 ns because the underlying substrate is per-second. So the apparent "median reversal of
1,717 s to 5,615 s" is remaining observation window, not reversal persistence. That is not a
defect in the arithmetic; it is a defect in anyone reading the field by its name, and it should
be renamed.

**Starved or broken?** Both, separably. The **skeleton is sound and starved**: 91 candidates on
one day, all censored, is what a one-day window produces and nothing about it is wrong.
The **depletion, refill, SEARCHED and recurrence channels are broken regardless of tape** — more
days will produce more zeros.

**Bar.** After wiring depletion/refill from the replenishment and absorption substrates:
`phase_depletion` must be nonzero on at least the runways that overlap a trade-bearing group
(2,028 trades exist on this day), and the depletion measured on a runway must reconcile against
4.8's displayed depletion for the same interval to within the attribution rule.

**Change.** (1) Feed `phase_depletion` and `phase_refill` from 4.7's episode quantities and 4.8's
displayed depletion, joined on time-and-price within the runway — this is the missing join that
blocks the entire exhaustion programme. (2) Rename the reversal duration to
`reversal_onset_to_window_end_ns` while it is censored, or emit it only with an explicit
`CENSORED_AT_WINDOW_END` status. (3) Separate the discovered state from side: the current two
states carry no information beyond a field 4.1 already stamps.

### 4.11 Prebirth prediction and continuous H+N recognition — CANNOT_JUDGE_YET

**What it gave.** All 91 candidates are H+N; **PRIOR 0, T0 0, MISSED 0, CENSORED 0**, and
`detection_share = 1.0` in all 28 strata. Recognition delay is second-quantized: 6 s to exactly
50 s, nothing beyond; **24 members sit at the 50 s ceiling**, the ceiling is the modal value in
11 of 28 strata, and the population mean is 42.60 s pulled toward the cap by construction.
`failed_state_count` is 0 for every candidate and `superseded_call_attempts` is 0.

**Why CANNOT_JUDGE_YET is the honest verdict, not a hedge.** Three distinct reasons, none of
which is a fault in 4.11's arithmetic. (a) PRIOR is **unreachable by the unit's construction**:
the candidate is a dipole flow spike whose birth *is* its own detection, and the runner correctly
refuses to backdate. (b) `detection_share = 1.0` is a **tautology over the detector's own
output** — the denominator is the set of events the detector defined, so it says nothing about
what was missed; the missed population is the 4,371 rejected second-events
(2,053 prominence-suppressed, 1,672 below threshold, 338 zero-magnitude, 294 refractory,
14 not-local-max) plus the 11,399 warm-up seconds, none of which 4.11 can see. (c) The
**first-call rule was never exercised**: 0 failed states means the protection exists and was
untested. Censored is not negative.

**Bar.** 4.11 becomes judgeable the moment the candidate population contains at least one
structure whose precursor is separable from its detection — i.e. a candidate unit with a
pre-birth observable. Until then, no amount of tape helps: the recognition share will be 1.0 on
every day, on every instrument.

**Change.** (1) Bring the detector's rejection ledger *inside* the contract (see "what should be
in the contract"). Without it, 4.11 reports a rate whose denominator is defined outside anything
the contract governs. (2) Emit the 50 s recognition ceiling as a declared parameter in the
stratum, so a reader cannot mistake a censored delay for an observed one — 24 of 91 members are
at it.

### 4.12 Dipole and opposing-pressure runway — EARNS_IT_BUT_MISCOMPUTED, and starved

**What it gave, and one result is genuinely valuable.** 3,454 stages over 90 paths, 59 sign
reversals. Direction: **NO_DIRECTION 1,782 (51.6%)**, SHORT 896 (25.9%), LONG 776 (22.5%) — a
zero-flow stage is reported as having no direction rather than defaulted to the prevailing side,
which is the right choice. Orientation: FLIP 1,881 stages / SAME 1,573; 46 FLIP episodes,
44 SAME, 1 NO_PREDECESSOR. The positive finding: **normalized book imbalance and signed flow are
decoupled**. Imbalance sits in a narrow band — stratum means 0.0337 to 0.0848, whole-population
range [0.0116, 0.1109], grand mean 0.0538, and within a single path it moves by at most ~0.01
from BIRTH stage 0 through PERSISTENCE stage 15 — while signed flow in the same strata swings
from +1.29 to -10.60 with individual members reaching -53. The book stays bid-tilted by the same
small relative amount whatever the flow does. That is a positive result, not a null, and it
directly refutes reading direction off the imbalance. SAME/FLIP differ in **dispersion, not
location**: in the largest family, FLIP births (n=14) range [-52, +9] with median 0.0 and
magnitude mean 8.21 while SAME births (n=7) range [-1, +4] with median +1.0 and magnitude mean
1.86 — nearly the same medians, very different tails.

**Starvation, quantified and separable from the defects.** The per-second substrate classified
**474 buy seconds and 488 sell seconds** (plus 8 excluded at mid, 1 with no quote) out of
**17,991 observed seconds** — flow is classifiable on **5.4%** of seconds, because the day
carries only **2,028 trades**, 0.11 per second. That is the whole explanation for the 51.6%
NO_DIRECTION share. It is a Sunday, not a broken measure.

**Defects.** D-12 (1,692 strata over 3,454 observations; 848 at n=1; none at n>=30; 6,768
averaged rows = 41.5% of the whole averaged layer), the absent REVERSAL stages (BIRTH 220 and
PERSISTENCE 3,234 only, against 90 reversed runways in 4.10), and D-16/4.4's empty mirror
channel, which lives in 4.12's strata.

**Change.** (1) Stop stratifying on the raw `stage=k` index; bin it (BIRTH / early PERSISTENCE /
late PERSISTENCE / REVERSAL) so a stratum can hold a population. Keep exact stage on the member
row. (2) Emit REVERSAL stages so 4.10 and 4.12 describe the same runway. (3) Report the
classifiable-seconds share **in the stratum**, so the 51.6% NO_DIRECTION is read as sparsity
rather than as balance.

### 4.13 Chain families and D-depth lineages — EARNS_IT_BUT_MISCOMPUTED, and starved on depth

**What it gave.** 21,651 lineage nodes: **21,344 D0 roots (98.58%) and 307 D1 descendants
(1.42%)**, observed maximum depth 1, no maximum depth imposed. Status: TERMINATED 48,
CENSORED_STREAM_END 21,603, OPEN 0, CENSORED_SEGMENT_END 0. The one real result is a **strict
bimodality by transition type**: descendants reached by an ADD transition are overwhelmingly
instantaneous — **243 of 249 A-transition descendants have interstage delay exactly 0 ns**
(153 side B, 90 side A), the child entering in the same event group as the parent — while
descendants reached by a TRADE transition are separated by real time (side A n=27: p50 14.7 us,
p90 4.08 s, max 15.60 s; side B n=26: p50 21.5 us, p90 682 us, max 351.4 s). An order-ID lineage
step that is an add is a bookkeeping successor; one that is a trade is a market event.

**Starved, honestly.** D2 and deeper are **absent, not suppressed**. The mission's D0-D5 anchor
range is exercised only at its first rung, and nothing about deep-chain grammar is answerable on
one day of one instrument.

**Defects.** D-9 (censored-age channel excludes all 21,603 censored nodes) and D-15
(21,296 vs 21,344 root counts, differing by exactly the 48 terminated).

**Change.** (1) Fix the censored-age channel — with 99.8% of nodes censored, it is the only
channel that could describe the population. (2) Reconcile the two root counts or rename one.
(3) 4.13 and 4.14 are built on the same order-ID graph (`same_order_paths` 21,651 equals the
lineage node count exactly) and never cross-reference each other; give them a shared path ID.

### 4.14 Recurrence, bursts, and transition graphs — EARNS_IT_BUT_MISCOMPUTED

**What the exact index gave, and it is excellent.** 57 transition edges, each carrying its own
count, outgoing denominator and a `CONDITIONAL_PROBABILITY` label, explicitly kept out of the
averages. From it, two of the strongest market-mechanics results of the whole run:
- **Post-fill disposition is CANCEL, not MODIFY, by roughly seven to one.** F|A -> C|A is
  550/1,090 = 0.505 against F|A -> M|A 80/1,090 = 0.073 (6.9:1); F|B -> C|B is 635/1,085 = 0.585
  against F|B -> M|B 73/1,085 = 0.067 (8.7:1). Corroborated independently by the family census:
  cancel-terminal trade families (TFCN 812 + TFC 162 = 974 groups) against modify-terminal
  (TFM 139) is 7.0:1.
- **Trades almost never sweep.** 2,028 trade actions produced 2,411 fills — **1.19 fills per
  trade**. The aggressor/passive pairing is near-deterministic: T|A -> F|B occurs 823 of 917
  (0.897), T|B -> F|A 835 of 930 (0.898). Aggression is almost perfectly two-sided (917 ask-tagged
  against 930 bid-tagged), corroborated by the per-second substrate's 474 buy / 488 sell seconds
  classified by midpoint without consulting the tape's side field.

**What the averaged companions gave: nothing.** `run_length` maximal run is exactly 1 in every
high-count PRE_SETTLEMENT stratum (777 of 865 strata degenerate, 55,223 of 55,638 observations);
`run_duration_ns` is **0 for 55,597 of 55,638 observations (99.93%)** across 858 all-zero strata;
and `interarrival_gap_ns` is D-6 — byte-identical to 4.5's within-group receive gap.

**The recurrence population that exists and is unmeasured.** The section's own summary reports
`multi_occurrence_order_paths: 19,625` and `same_order_paths: 21,651` against
`occurrences_seen: 57,027` and `boundary_restarts: 0`. Nineteen thousand six hundred
twenty-five order IDs recur, and not one averaged companion describes the time between their
occurrences.

**Change (this is the smallest change with the largest payoff in the section).** Redefine
`interarrival_gap_ns` as the gap between consecutive occurrences **of the same order path**, not
of consecutive components within a group. The data is already retained. That single redefinition
turns 4.14 from a duplicate of 4.5 into the only cross-group recurrence measure in the contract,
with a population of 19,625.

### 4.15 Open-world cluster and new-structure discovery — CANNOT_JUDGE_YET

**What it gave.** Nothing, declared: `cluster_version` reads `NO_CLUSTERING_D5` in every 4.16
stratum, so open-world clustering did not run under D5 and no cluster description is licensed.
That is contract-correct behaviour, not a failure. Corroborating: 4.8's
`discovered_disposition_counts` is empty and 4.10's `discovered_named_states` is empty, so
nothing anywhere in the run discovered a new named entity except the two 4.10 open-world state
IDs, which are a re-encoding of side.

**Defect.** D-14: 16,209 of 16,293 averaged rows carry a blank `cluster_version` instead of the
`NO_CLUSTERING_D5` declaration that the 84 4.16 rows carry, against contract section 3's
requirement that every average declare its cluster version.

**Bar.** 4.15 is judgeable only once discovery is authorized and frozen. When it is, the first
thing to check is whether the discovered clusters are separable from `family_id` — because 4.10's
two "discovered" states turned out to be side, and 4.3's family ID is the literal action string,
so a clusterer fed those features will rediscover them.

**Change.** Stamp `NO_CLUSTERING_D5` on every averaged row, not only 4.16's.

### 4.16 Fixed causal future-response table — EARNS_IT_BUT_MISCOMPUTED

**What it gave.** 91 tracks opened, 91 closed, 0 open. At-risk discipline is exactly right and
per-horizon: entered 91 at every horizon, observed 90 / 90 / 89, censored before horizon
1 / 1 / 2, `denominator_is_horizon_specific` true, with an explicit refusal to reuse one
denominator across horizons. The result: **price response is zero at the median at one second
and only develops dispersion, not direction, by sixty.** At H+1s the median is exactly 0 in all
28 strata (20 strata are all-zero, covering 52 of 90 observations). At H+10s dispersion opens —
largest stratum (`ow-3a12d9bd4a731b597f0d`, side B, n=10): p10 -3.0 ticks, p50 0, p90 +1.0,
max +7.5. At H+60s it widens: p10 -6.5, p50 0, p90 +2.0, min -6.5, max +7.5, with day extremes
at -11.5 and +9.0 ticks.

**Why it earns despite the defects.** That null is a real, falsifiable, negative result and it
is the basis of my SH-2 (do not build a directional trigger on this candidate unit). A section
that produces a well-denominated zero has earned its place.

**Defects.** D-10: one of seven required response channels, fixed horizons only with no
event-driven change points, and `starting_liquidity_regime` = `DEPTH_SKEW_BID` on **all 84** at-
risk rows, so the contract's required conditioning on starting liquidity regime conditions on a
constant. Also n=89-90 across 28 strata means 13 strata hold exactly one member.

**Bar.** Emit the flow, queue and full-book response channels. Price response being null at all
three horizons while, say, queue-depth response is not would be a genuine finding; with one
channel emitted, a null is uninformative about whether the *structure* had any consequence at
all.

**Change.** (1) Add at minimum the flow and queue response channels — the substrates for both
already exist (4.12's signed flow, 4.6's volume ahead). (2) Source `starting_liquidity_regime`
from 4.2 once 4.2 exists. (3) Add one horizon below 1 s: the mechanics this run measures live at
1-5 ms (4.7's touch restoration) and 20-30 us (4.5's within-group spacing), so the shortest
response horizon is three orders of magnitude coarser than the fastest thing the run can see.

---

## Direct answers

### Which three sections gave you the most, and why

**1. 4.6 (queue position, priority, order survival).** It is the only section whose estimator is
chosen so that the wrong answer cannot be produced — `arithmetic_mean_forbidden`, Kaplan-Meier
with at-risk counts at every time. It repaid that immediately: resting-order survival is
two-population, not one distribution with a tail (10% gone by 1.19 ms, median 3.19 s, 2.74% still
resting at 7,196 s in one stratum of 8,534 orders), and orders born at the Sunday reopen are a
*different population* from orders born in session — medians of 217.4 s and 755.2 s against 2.60 s
and 3.19 s, an 84x and 237x split, resolved from only 138 PRE_OPEN births. A mean would have shown
one number and hidden both facts.

**2. 4.7 (replenishment).** It is the run's one clean controlled contrast: same family, same side,
same phase, same day, one variable changed. AT_TOUCH restoration median 1.775 ms against
BEHIND_TOUCH 673.1 ms (379x) and 1.379 ms against 558.8 ms (405x). And its coequal ratio pair
earned its keep exactly once in the whole artifact, detecting that replenishment is size-dependent
behind the touch (mean-of-ratios 14.86 vs ratio-of-sums 9.65) and size-invariant at it
(44.01 vs 42.63) — a structural difference that neither view alone would show.

**3. 4.5 (formation, serialization, observation clocks).** The only measure in the artifact with
**zero degenerate strata**: 57 large strata carrying 57 distinct medians over a 2,822x range. It
produced the one fact from this run that changes how a real-time system should be built — the
largest structural events are the *last* to become lawfully observable (300.3 ms for the
59-component cascade against 106-192 us for the 80.9% of the tape that is single-action), so the
transport itself imposes an adverse-selection gradient. And it fences its own interpretation
(`interpretation_domain: SERIALIZATION_FEED`).

Honourable mention: **4.14's transition-edge index**, which produced the two best market-mechanics
results in the run (post-fill cancel:modify at 6.9-8.7:1, and 1.19 fills per trade). It is not in
the top three only because its three *averaged* measures are the weakest in the artifact.

### Which sections are currently telling you nothing, and the smallest change that would fix each

| Section | What it currently tells you | Smallest change that makes it informative |
|---|---|---|
| **4.2** | Nothing — it did not run | Compute the per-day companion from the `book_full` already stored on all 43,569 member rows. No new capture, no new field, no new pass |
| **4.9** | A one-level, one-sided market that does not exist | Point the ladder measures at the same reconstructed book 4.12 reads. One substrate binding |
| **4.4** | Zero pairs, undiagnosable | Emit `matching_distance` and unmatched-reason counters even at zero pairs, and state the matching rule in the declaration |
| **4.10** depletion/refill | 0.0 with zero exclusions | Feed them from 4.7's episode quantities and 4.8's displayed depletion, joined on time-and-price inside the runway |
| **4.10** SEARCHED / recurrence_count | 0.0 everywhere | SEARCHED needs a start time distinct from the candidate's own birth; recurrence_count needs 4.14's same-order path population, which exists |
| **4.10** REVERSAL duration | A censoring artifact readable as persistence | Rename to `reversal_onset_to_window_end_ns` while censored, or emit only with `CENSORED_AT_WINDOW_END` |
| **4.14** interarrival gap | 4.5's within-group receive gap, restated | Redefine as the gap between consecutive occurrences of the **same order path** — 19,625 such paths already exist in the traversal |
| **4.14** run_length / run_duration | 1 and 0 on 99.9% of observations | Define runs across groups within an order path, not within a group |
| **4.13** censored_stage_age | Empty while 21,603 of 21,651 nodes are censored | Fix the exclusion predicate; 4.6's equivalent is correct and can be copied |
| **4.8** same_side_replacement | 0.0 on a zero numerator, all 205 strata | Wire the numerator, or refuse loudly. Then replace withdrawal_ratio (which is 1 - absorption) with **traded quantity over opposite-side retreat**, which the contract already names |
| **4.16** | One response channel, and a conditioning key with one value | Emit flow and queue responses from substrates that already exist; source the regime from 4.2; add a sub-second horizon |
| **4.5** decision clock | Empty, 43,569 of 43,569 excluded | Populate it even when it equals F_LAST, with a basis field saying so |
| **4.12** | Averages over n=1 in half its strata | Bin the stage index instead of stratifying on it raw |
| **4.15** | Declared not-run (correct); blank cluster_version on 99.5% of rows | Stamp `NO_CLUSTERING_D5` on every averaged row |

### Which sections are structurally sound but starved by this slice rather than by their design

**Starved, not broken — wait for more tape:**
- **4.10's runway skeleton.** 91 opened, 0 completed, 91 censored is what a one-day window
  produces. Completion is only observable in a window longer than the runway.
- **4.11 entirely.** PRIOR is unreachable because of the *unit*, not the day; but the recognition
  distribution, the 50 s ceiling behaviour and the untested first-call rule all need a population
  with pre-birth observables before anything can be judged.
- **4.12's direction channel.** 2,028 trades over 17,991 seconds means flow is classifiable on
  5.4% of seconds. On a weekday tape the 51.6% NO_DIRECTION share should fall sharply. The
  *measurement* is fine; the day is empty.
- **4.13's depth axis.** Max depth 1 with 21,603 of 21,651 censored at stream end. D2+ needs a
  longer window, not different code.
- **4.16's power.** n=89-90 across 28 strata, 13 of them holding one member. The at-risk
  discipline is right; the population is tiny.
- **4.15.** Not run by declaration (D5), so nothing to judge.
- **4.9's `price_gap_raw`** *would* be starvation (195 of 196 gaps inside the one reopen group) —
  except that D-5 means we cannot tell starvation from substrate failure here. That is exactly why
  D-5 must be fixed before any 4.9 verdict can be trusted.

**Broken regardless of how much tape you give them — fix the code:**
4.2 (never ran), 4.9's book binding, 4.5's decision clock, 4.7's restoration attribution, 4.8's
same-side replacement and the absorption/withdrawal identity, 4.10's depletion / refill /
SEARCHED / recurrence, 4.13's censored-age channel, 4.14's interarrival definition, 4.16's channel
count and regime key, 4.4's matcher, 4.12's stratification.

**The trap in between, and it is the reason this distinction matters.** More tape will make
several of the broken ones *look better while still being wrong*. On a weekday, 4.9's
`price_gap_raw` will collect thousands of observations at each session reopen and still be reading
a one-sided book; 4.12's NO_DIRECTION share will fall and its strata will still be n=1;
4.14's `interarrival_gap_ns` will grow and still be measuring serialization. A defect that gets
more populated does not get more correct, and a populated wrong number is harder to catch than
an empty one.

### Missing joins — where two sections should be connectable and are not

1. **4.10 <- 4.7 and 4.8 (the blocking one).** `phase_depletion` and `phase_refill` are the
   fields where a runway becomes a liquidity statement. 4.7 measured 24,283 removal episodes with
   quantities and restoration times; 4.8 measured displayed depletion on 43,569 runways. Neither
   reaches 4.10, which reports 0.0 on 344 observations. Until this join exists the exhaustion
   programme cannot say anything about liquidity, which is the only thing exhaustion is about.
2. **4.9 <- the member ledger's `book_full`.** 10,131,179,453 bytes of full book, captured and
   retained, and the section whose job is ladder topology is not reading it (D-5).
3. **4.16 <- 4.2.** `starting_liquidity_regime` is constant because there is no book regime
   companion to source it from. Two absent things producing one uninformative field.
4. **4.10 <-> 4.12.** The same 91 runways are phase-labelled differently: 4.10 has SEARCHED /
   BIRTH / PERSISTENCE / REVERSAL and records 90 reversals; 4.12 has BIRTH and PERSISTENCE only
   and emits no reversal stages. The reversal — the part anyone would want — has a duration in
   4.10 that is a censoring artifact and no dipole stages at all in 4.12.
5. **4.6 <-> 4.7.** A 4.7 removal episode *is* a 4.6 lifecycle terminal. There is no key joining
   them, so "did the removed order's queue position predict whether the level was restored" is
   unanswerable, even though both halves were computed on the same day from the same book.
6. **4.13 <-> 4.14.** Both are built on the order-ID graph — 4.14's `same_order_paths` is 21,651,
   exactly 4.13's lineage node count — and neither references the other. 4.14's 19,625
   multi-occurrence paths are the recurrence 4.13 would need to distinguish a chain from a
   coincidence.
7. **4.11 <- the candidate detector's rejection ledger.** The denominator of every 4.11 rate lives
   in `traversal.candidate_detection` (11,399 warm-up seconds, 4,462 considered, 91 promoted,
   4,371 rejected across five named reasons) — outside every section the contract governs.
8. **4.5 <-> everything.** 4.5 measures when each group became lawfully observable. No other
   section carries that observation delay into its own stratum, so no section can ask whether the
   structures that arrive late behave differently — and 4.5's own strongest finding says the
   biggest ones do arrive latest.

### Is there a calculation not in the contract that should be?

**Yes, three, in order of value.**

**(a) A per-second (or per-interval) flow and quote substrate section.** The run already computes
one — `traversal.legacy_per_second_roll20`: 22,380 legacy observable rows (29,329,182 bytes,
0.27% of the run), 2,028 trades, 474 buy / 488 sell seconds classified by midpoint with the
tape's side field never consulted, 8 excluded at mid, 1 with no quote, its own
`crosswalk_state_hash`. **It is the substrate on which the candidate detector and all of 4.12
run, and it is not one of the sixteen sections.** It has no averaged companion, no declaration
block, no stratum, and no acceptance gate. That is why the 51.6% NO_DIRECTION share in 4.12 had
to be explained from traversal counters rather than from a section, and why nobody can check
whether the classification rule is right. Making it section 4.0 (it is upstream of everything)
with a declared numerator, denominator and missingness rule would put the foundation of the
exhaustion programme under the same discipline as its consequences.

**(b) A detector-coverage and rejection-accounting section.** The population that defines
4.10, 4.11, 4.12 and 4.16 is created by a selection function the contract never mentions:
trailing causal quantile 0.85, 600 minimum threshold observations, 900 s warm-up, 45 s refractory,
5 s local radius, causal windowed prominence. It searched 6,592 of 17,991 seconds (36.6%),
considered 4,462 second-events, and promoted **91 — 2.04%**. Every exhaustion rate in this
artifact has that as its denominator, and 4.11's `detection_share = 1.0` is unfalsifiable
precisely because the rejected 4,371 are outside the contract. **The selection function that
creates a population belongs in the contract that governs the population.**

**(c) A cross-section estimand-agreement check.** Two sections computed
`(bid - ask)/(bid + ask)` on the same day, on the same instrument, and got +/-1.0 on 152 of 154
readings in one and [0.0116, 0.1109] on 3,454 readings in the other — and the result was
**ACCEPTED with all eight section-6 gates passing**. The reconciliation receipt (contract 5.6)
reconciles *vertically*, exact to index to average. Nothing reconciles *horizontally*: the same
estimand computed in two places. That is the exact gap D-5 fell through.

A fourth, smaller one: **there is no section that owns executions.** Trades appear only as
by-products — 4.14's transition edges, 4.8's traded quantity, the traversal's counters. The two
strongest market-mechanics results of this run (post-fill cancel:modify 6.9-8.7:1, and 1.19 fills
per trade with 0.897/0.898 aggressor pairing) had to be assembled across three layers. On a tape
with 2,028 trades that is survivable; on a weekday it will not be.

### The single highest-value change to the calculation surface before the next run

**Bind every book-derived measure to the one reconstructed full book the run already stores, and
add a cross-section agreement gate on estimands that more than one section computes.**

Why this and not the others:

- **It is the defect with the widest blast radius.** It fully accounts for 4.9 (2,840 averaged
  rows, 24.5 MB of ledger, eight measures, 100% degenerate strata, verdict NO_VALUE_AS_COMPUTED);
  it is the most likely explanation for 4.16's `starting_liquidity_regime` being constant on all
  84 rows; and it is a live suspect for 4.10's zero depletion and refill, since a book that
  reports one occupied level and one side cannot show depletion behind the touch.
- **It is the defect the acceptance gates cannot currently see.** Every one of the eight
  section-6 gates passed. A one-sided book is present, typed, in range, self-consistent, and
  reconciles perfectly against itself. Only comparison against an independent computation of the
  same quantity settles it — and 4.12 was already computing exactly that, in the same artifact,
  and nothing compared them.
- **It costs nothing to fix and nothing to store.** The book is already captured:
  10,131,179,453 bytes, 93.47% of the run, on every one of the 43,569 member rows. We are paying
  for the full book and computing the ladder off something else. This is not a retention
  question; the retention decision was already made correctly.
- **It unblocks 4.2 in the same motion.** The daily book regime companion needs precisely the
  same binding, and 4.2 is currently the only section that produced literally nothing.

Concretely, before the next run: (1) make the ladder, absorption and response sections read the
same book object 4.12 reads; (2) add to section 6 a gate that fails the calculation when two
sections' computations of a shared estimand disagree beyond a declared tolerance on the
overlapping population; (3) emit 4.2 from that book.

If only one of those three ships, ship the gate. The binding fixes one defect; the gate is what
would have caught it, and it is the class of defect — present, typed, in range, and measuring
something other than what its name implies — that this programme exists to catch.

---

## What this slice still cannot answer

Recorded so a reader can size the remaining gap, unchanged from my prior pass and reconfirmed
here: the cross-day stream-position gradient (this run holds only 20211003); whether any
exhaustion runway ever completes (91 of 91 censored); chain grammar beyond D1 (no D2+ node
exists); cross-group recurrence (the measure is within-group, D-6); anything about a two-sided
weekday book (99.53% PRE_SETTLEMENT on a Sunday, one instrument, one continuity segment); and
anything separating lawfully knowable from acted upon (D-1, the decision clock).

And what I did not read: the exact member ledger is 10,616,914,801 bytes over 43,569 rows,
streamed to `/opt/frankie-a-arm-run/ledgers/exact_member_rows.jsonl`, sha256 `153cc761...`; the
exact lifecycle and runway ledger 192,510,728 bytes over 243,270 rows, sha256 `4ebc5b71...`; the
legacy observable rows 29,329,182 bytes over 22,380 rows, sha256 `3c75f8b4...`. None are in the
34 MB result I received. Every exact-member claim above rests on the runner's counters, receipts
and per-stratum summaries, which reconcile internally (`rows_read_back_from_disk` equals
`row_count` on all three ledgers) but which I have not independently verified against the rows.
