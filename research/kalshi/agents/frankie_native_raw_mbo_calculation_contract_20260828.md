# Frankie Native Raw-MBO Calculation Contract

## 1. Purpose and authority

This document fixes the reusable calculation layer for the corrected native-MBO
Frankie program. It supplements the controlling real-time mission; it does not
replace the mission, authorize another arm, open Step-1, or create a scientific
lock or freeze.

The calculation layer has an output goal: preserve the complete native causal
evidence, expose structures that aggregation hides, and add averaged views only
when they answer a distinct population-level question. Exact evidence is never
discarded or replaced by an average. The same versioned contract should be used
for each later authorized run so differences are attributable to the arm and its
lawful context rather than to changing arithmetic.

No family count, state count, chain depth, horizon grid, or previously observed
value is an eligibility gate. `P/O/S/X`, `SAME/FLIP`, known action families, and
`D0` through `D5` are discovery seeds. New structural states, transitions,
subfamilies, deeper chains, and unmatched members remain eligible and receive
deterministic content-derived identifiers.

## 2. Universal evidence and clock rules

The atomic observation is one F_LAST-closed native event group. Preserve its raw
action order and its full FIFO book immediately before and after the group. The
member record must bind:

- source, instrument, event-group index/hash, native-record interval, and
  continuity segment;
- exact action, side, price, size, order ID, sequence, channel, flags, event time,
  and receive time for every component;
- full bid/ask depth, order count, level count, spread, imbalance, touch, price
  ladder, queue identities, priority, volume ahead, and order age before/after;
- event time, first-component receive time, F_LAST availability time, and
  decision/as-of time as separate clocks; and
- all content-derived family, subfamily, cluster, mirror, pairing, transition,
  runway, and lineage IDs used downstream.

The first lawful knowledge time for a completed group is its F_LAST receive
time. A prebirth feature must exist and be available before the target birth and
is labeled `PRIOR` with exact lead time. Birth recognition is `T0`. The first
lawful later recognition is continuous `H+N`, where `N` is the observed elapsed
time on the named clock. A later, better-looking horizon may not replace an
earlier valid call. Fixed H+N response measurements may characterize causal
consequences, but they are never used to backdate a detection or cluster label.

Source resets, snapshots, gaps, session boundaries, and discontinuities start
new continuity segments. No calculation crosses them unless it explicitly
models the boundary as its own structure.

## 3. Parallel-view decision rule

For every focus below, emit the exact view first. Add an averaged companion only
when it supplies information that the member ledger does not state directly,
such as population scale, prevalence, expected conditional magnitude, or a
within-family response profile.

Every average must declare:

1. exact numerator and formula;
2. population and denominator;
3. source day and source role;
4. family, subfamily, and cluster version;
5. side or mirror orientation;
6. session, phase, and continuity segment policy;
7. causal clock and cutoff;
8. resolved, censored, or still-open status; and
9. missingness and inclusion rules.

Never average across distinct families, subfamilies, sides, mirror orientations,
sessions, phases, continuity segments, cluster identities, chain signatures, or
causal clocks. Pooling across source days is forbidden in the primary view. A
separately labeled cross-day synthesis is permitted only after every day-level
result remains present and the populations are demonstrably commensurate.

Counts, rates, empirical distributions, quantiles, survival curves, transition
probabilities, ratios of sums, and paired differences are not silently called
arithmetic means. Report their exact definitions. When both `mean(member ratio)`
and `ratio(aggregate sums)` are useful, retain both and label their difference
`COMPLEMENTARY_SCOPE_DIFFERENCE`.

## 4. Calculation matrix

### 4.0 Per-second flow and quote substrate

**Exact calculation.** For every completed second on the traversal's declared
binning clock (`ts_recv` unless declared otherwise; a second is complete once the
stream has moved past it, so its bins are final), emit one exact row carrying: the
second's own aggressor buy and sell volume and trade counts, classified by the
`legacy_per_second_roll20` midpoint rule and never by the tape's side field (mid =
0.5 * (bid_px_00 + ask_px_00) on rows with action `T`, price > 0, size > 0,
bid_px_00 > 0 and ask_px_00 >= bid_px_00; price above the mid is buy volume, below
is sell volume, exactly at the mid contributes to neither); the trades excluded at
the mid, without a usable quote, or with an unusable price or size; the touch the
last classifiable trade was judged against; and the trailing-window quantities
downstream consumed at that second - the roll20 value, the window signed flow and
its polarity. Every completed second receives exactly one own-second class - `BUY`,
`SELL`, `NO_DIRECTION` (no trades, or balanced classified volume), `EXCLUDED_AT_MID`,
`NO_QUOTE`, `UNUSABLE_PRICE_OR_SIZE` - and one trailing-window direction under
4.12's stage rule (`LONG`, `SHORT`, `NO_DIRECTION`; zero flow is no direction,
never a default). Missingness: a second that cannot be classified is a class, never
a gap; a second with no rows is a member; a second still open at a continuity or
stream boundary is `INCOMPLETE`, retained with its partial tallies and outside every
denominator. The section's per-second volumes must reconcile exactly with the
traversal's own binner, and a disagreement rejects rather than reports. Session
phase is the phase of the second's own instant, never the phase of the group that
closed after it. This section is upstream of the candidate detector and of 4.10
through 4.12 and 4.16, which are computed from it.

**Average decision: limited yes, census only.** Two classification censuses, each
as per-class shares whose denominator is the count of completed seconds in the
stratum (source day, role, continuity segment, session phase): the own-second class
shares, and the trailing-window direction shares 4.12 consumes. These are population
scale the member rows do not state directly. Nothing else in this section is
averaged: volumes, counts and window values are member facts on the exact rows.
### 4.0b Detector coverage and rejection accounting

**Exact calculation.** The candidate population that 4.10, 4.11, 4.12 and 4.16
report on is created by a selection function, and that function is governed here.
For every continuity segment, and stratified by source day, source role, segment,
and session phase, record: seconds observed by the causal candidate detector;
seconds whose local window completed and were judged; seconds held in warm-up;
seconds searched with a live bar; seconds with no finite flow reading; second-events
considered; candidates promoted; and candidates rejected by NAMED reason, using the
detector's own reason vocabulary verbatim - zero magnitude, below the trailing
threshold, not a local maximum, inside the refractory at judgement, inside the
winner's refractory at window release, and suppressed by prominence. Every judged
second ends in exactly one named outcome or the pending gauge; a residual rejects
the calculation rather than becoming an unnamed bin. Emit every detector parameter
as a declared field on the row - peak quantile, minimum threshold observations,
warm-up seconds, refractory seconds, local radius, threshold-observation cap,
selection rule, threshold rule, baseline lookback, prominence rule, and the
zero-flow guard - so that two runs under different parameters are two populations.
Retain one exact reconciliation row per segment close carrying the detector's own
counters beside the section's totals.

**Average decision: no.** These are counts, ratios of counts, and declared constants.
A rate here - the promotion rate, the searched share, the share rejected for each
reason - is a ratio of two exact counts with its numerator and denominator on the
same row, never an arithmetic mean. The summary gives every downstream exhaustion
rate its true denominator: `promoted` is the population 4.10 through 4.16 report on,
and `considered` with `rejected_by_reason` is what it was selected from.

### 4.1 Identity, integrity, and exact member surface

**Exact calculation.** Verify ledger/source hashes, exact-once native record and
group counts, F_LAST closure, cursor continuity, source identity, reconstruction
agreement, and raw-action tuple preservation. Emit one immutable member row per
group and a content-derived candidate-family ID. Preserve unmatched and singleton
members.

**Average decision: no.** Identity and integrity are boolean/count/hash facts;
averaging would weaken them. Descriptive counts and prevalence by exact stratum
are allowed but are not substitutes for member evidence.

### 4.2 Daily book regime companion

**Exact calculation.** Preserve the first and last full-book snapshot and every
intermediate member snapshot for each source day.

**Average decision: yes.** Retain the established per-day `first`, `last`, `min`,
`max`, and arithmetic `mean` for spread, full-depth imbalance, bid/ask depth,
bid/ask order count, and bid/ask level count. Keep action/side totals, group count,
and maximum actions per group beside them. The denominator is F_LAST-closed
groups in that source day. These are regime/scale facts, not causal family facts.

### 4.3 Open-world event families and exact members

**Exact calculation.** Describe each group by literal action/side sequence,
component order, fill disposition, order-ID graph, price multiplicity, size path,
terminal disposition, before/after book delta, and clocks. Create deterministic
IDs from the complete versioned descriptor. Carried families are a crosswalk,
never an allowlist.

**Average decision: conditionally yes.** Frequency, share, formation latency,
book impact, and response magnitude may be summarized only within one exact
family/subfamily, side orientation, day, session/phase, and clock. Do not average
action strings, order identities, topology, or distinct candidate families.

### 4.4 Mirrored members and matched pairings

**Exact calculation.** Preserve each member and its mechanically defined mirror
key. Form pairs only under a declared deterministic matching rule using lawful
pre-event covariates; retain pair IDs, unmatched members, exact differences, and
matching distance. Never use a future response to form a pair.

**Average decision: yes when matched support exists.** Report the arithmetic mean
of exact within-pair differences, denominator in pairs, and orientation. Keep the
member-pair ledger coequal. Unpaired orientation means may be reported as a
different estimand but may not replace paired differences.

### 4.5 Formation, serialization, and observation clocks

**Exact calculation.** For each member compute event-to-receive latency per
component, first-component-to-F_LAST formation latency, within-group receive gaps,
F_LAST-to-decision delay, sequence/channel relationships, and the first lawful
availability of every derived feature.

**Average decision: yes.** Means add feed/venue timing scale when stratified by
source, channel, session/phase, exact family, side orientation, component count,
and clock. Always retain empirical quantiles and maxima because a mean alone
cannot expose a heavy tail. Economic interpretation remains separate from a
serialization/feed explanation.

### 4.6 Queue position, priority, and order survival

**Exact calculation.** At each relevant action and runway stage preserve order
birth, age, initial and current volume/orders ahead, fills ahead, own fills,
cancels ahead, modifies, priority retention/loss, queue movement, and terminal
fill/cancel/modify/open status. Link same-order lifecycles across groups without
crossing a continuity boundary.

**Average decision: limited yes.** Arithmetic means of age, volume ahead, queue
movement, and resolved lifetime are useful within exact family/side/session/phase
strata. Censored or still-open orders remain separate. Time-to-exit with censoring
uses a declared survival/hazard estimator rather than an arithmetic mean, with
at-risk counts at every time.

### 4.7 Replenishment and liquidity resilience

**Exact calculation.** Following an identified removal/contact, measure depth and
order removal, new-ID adds, same-ID modifies, refills at the same price, refills
at neighboring prices, touch restoration, overshoot, persistence, and first
lawful restoration time. Distinguish new liquidity from reshaped residual orders.

**Average decision: yes.** Within one initiating family, side, price/touch state,
session/phase, and day, report mean removed quantity, neighbourhood arrival quantity
(the arrival-credited numerator, not a replacement), the neighbourhood arrival ratio,
and fixed-H+N response curves. Resolved, censored, and never-restored paths are
separate. Exact paths and time-to-restoration distributions remain present.

### 4.8 Absorption, withdrawal, and delivered pressure

**Exact calculation.** Measure traded quantity, displayed depletion, same-side
replacement, opposite-side retreat, surviving depth, price response, and order-ID
turnover over each causal runway. Preserve whether pressure is absorbed without
price movement, delivered through price, or accompanied by withdrawal.

**Average decision: yes.** Within exact structural and causal strata report both
the mean of member-level absorption/withdrawal ratios and the ratio of aggregate
sums when denominators are nonzero. They answer different questions and are
coequal. Zero-denominator, sparse, and indeterminate members remain explicit.

### 4.9 Price-ladder topology

**Exact calculation.** Preserve best-price transitions, level births/deaths,
gaps, occupied-level geometry, depth migration, touch compression/expansion, and
the exact orders causing each change. Separate absolute liquidity from relative
imbalance.

**Average decision: yes.** Mean gap, occupied levels, depth concentration,
birth/death rate, and touch-migration magnitude add regime scale within one
family/side/session/phase/day. Exact topology and rare discontinuities cannot be
represented by an average and remain coequal.

### 4.10 Exhaustion state, birth, persistence, and completion

**Exact calculation.** Construct a complete causal runway for each candidate:
searched coverage, precursor, prebirth state, first deviation, birth/T0,
transitions, inflection, persistence, recurrence, extension, completion/reversal,
and censored/open status. `P/O/S/X` are seed annotations; any unmatched state gets
a deterministic open-world ID. Preserve falsifiers and alternative hypotheses.

**Average decision: yes after state identity is fixed.** Duration, causal age,
depletion, refill, absorption, response, and recurrence may be averaged within
one exact state/substate, side, session/phase, day, and resolved-status stratum.
Never average across phases of the same event or use completed duration at an
earlier causal cutoff.

### 4.11 Prebirth prediction and continuous H+N recognition

**Exact calculation.** For every candidate record the earliest durable lawful
precursor, exact PRIOR lead if prebirth, T0 if first known at birth, or exact H+N
recognition if first known later. Preserve all earlier failed/ambiguous causal
states and the first-call rule. Members without a lawful early call remain in the
population.

**Average decision: yes, with strict separation.** Mean/median lead or delay,
recognition share, and empirical distributions are useful within one candidate
family/side/session/phase/day and separately for PRIOR, T0, H+N, missed, and
censored cases. A mean over only successful detections must never be presented as
the population detection time.

### 4.12 Dipole and opposing-pressure runway

**Exact calculation.** At every runway stage preserve signed flow, side-specific
depth/order/level composition, normalized imbalance, magnitude, sign, persistence,
reversal, coupling to price, and all clocks. Direction comes from signed flow and
causal mechanics, not unsigned dipole magnitude.

**Average decision: yes.** Stage-relative mean paths and paired mirror differences
are valuable within one dipole family, orientation, event phase, session/day, and
clock. `SAME` and `FLIP` orientations never pool. Exact sign reversals, inflection
times, and rare paths remain visible.

### 4.13 Chain families and D-depth lineages

**Exact calculation.** Build deterministic lineage graphs from qualifying causal
successors. `D0` is a root with no qualifying successor; `D1`, `D2`, and deeper
values are successive stages. Preserve exact parent/child IDs, transition type,
interstage delay, stage duration, side/orientation, termination, censoring, and
open lineage status. No maximum depth is imposed.

**Average decision: yes.** Within one exact lineage signature, depth, transition,
orientation, session/phase/day, and resolved-status stratum, report mean
interstage delay, stage duration, queue change, and response. Never average depth
labels or mix roots, descendants, terminated, censored, and still-open chains.

### 4.14 Recurrence, bursts, and transition graphs

**Exact calculation.** Preserve consecutive homogeneous runs, interarrival gaps,
recurrences, alternating sequences, transition edges, source-boundary restart
chains, and same-order paths. Threshold-free exact gaps are canonical; any burst
threshold is a versioned descriptive view, not a membership gate.

**Average decision: yes.** Mean run length, interarrival time, recurrence delay,
and edge-conditioned response add population structure within one exact node/edge,
orientation, session/phase/day, and clock. Transition counts and conditional
probabilities must be reported as such, with denominators, rather than mislabeled
as averages.

### 4.15 Open-world cluster and new-structure discovery

**Exact calculation.** Discovery begins from exact member/runway features and
must allow unmatched observations, singletons, splits, merges, and additional
states. The feature schema, scaling, distance/model, seed, training population,
and version are hash-bound. Every assignment includes distance/support and every
unassigned member remains preserved. Outcomes, Step-1, reveal, scoring, and later
causal responses are excluded from discovery features.

**Average decision: only after discovery is frozen.** A cluster may receive a
within-cluster descriptive centroid/mean and prevalence after its membership and
version are fixed. An average may describe a discovered cluster; it may not erase
members, force assignment, determine the allowed number of clusters, or serve as
the sole discovery surface. Exact exemplars, boundary members, and distributions
remain coequal.

### 4.16 Fixed causal future-response table

**Exact calculation.** From each structure's first lawful availability, emit
native price, flow, full-book, queue, survival, transition, and completion changes
at every available event-driven change point and at versioned fixed H+N reporting
horizons. Preserve the earliest observation and do not substitute a later horizon.
Stop or mark censored at source/session/continuity boundaries.

**Average decision: yes.** Conditional mean response curves are useful only within
one exact structure/cluster version, side/orientation, session/phase/day, starting
liquidity regime, horizon, and clock. Every horizon has its own at-risk denominator.
Exact trajectories remain the causal evidence; averaged curves supply conditional
population scale.

## 5. Required artifact layers

Each authorized run produces hash-bound layers rather than one mixed report:

1. **identity receipt:** inputs, source roster, hashes, counts, calculation-
   contract version, clock policy, and fail-closed checks;
2. **exact member ledger:** every closed event group and raw/native state;
3. **exact lifecycle and runway ledger:** orders, pairs, episodes, transitions,
   lineages, event-driven consequences, and censoring;
4. **open-world indexes:** family, cluster, mirror, adjacency, recurrence, and
   chain indexes with deterministic IDs;
5. **averaged companions:** only the useful views authorized above, each with its
   complete stratum and denominator;
6. **reconciliation receipt:** exact-to-index-to-average recomputation, with valid
   granularity differences labeled `COMPLEMENTARY_SCOPE_DIFFERENCE`; and
7. **positive findings report:** mechanically supported discoveries, hypotheses,
   exact exemplars, averaged companions when useful, and falsifiers.

The calculation artifacts are evidence, not a principal Frankie invocation,
first lock, freeze, one-way handoff, Forecaster authorization, reconciliation,
or score.

## 6. Fail-closed acceptance gates

Reject the calculation rather than partially promote it if any of the following
cannot be verified:

- mission, knowledge profile, source roster, native ledger, or calculation-
  contract identity;
- exact-once record/group coverage, F_LAST closure, cursor continuity, or full
  FIFO reconstruction;
- arm isolation, Step-1/reveal sealing, and absence of later/rerun-only evidence;
- lawful clock order or first-availability semantics;
- deterministic family/cluster/pair/lineage identity and open-world retention;
- exact denominators, strata, censoring, or recomputation of an averaged view;
- preservation of exact members beneath every summary; or
- distinction between calculation evidence and actual principal-model execution.

Passing this contract means the calculation layer is reusable. It does not by
itself validate a forecast, strategy, scientific model call, lock, or freeze.
