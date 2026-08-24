# Frankie Step-1 Structural Census Method V1

Date: 2026-08-24  
Status: **BINDING DIRECT KNOWLEDGE FOR BOTH REAL-TIME FRANKIE AND FORECASTER FRANKIE**  
Surface ID: `step1_structural_census_methodology`  
Result surface: `step1_revealed_retrospective_evidence` (separate identity and hashes)

## Purpose and collaboration rule

Step-1 constructs the exhaustion-structure population before a later system asks Frankie to predict it. It is a structural census, not a trade-edge, calibration, or promotion run.

Both Frankies receive this complete method directly. It is not target-answer material and must never be sealed, omitted, shortened into a misleading synopsis, or confused with Step-1 results. In the collaborative October retrospective, verified Step-1 results are exposed separately and explicitly as revealed comparison evidence. In a genuinely live prospective mode, future facts remain unavailable only until their lawful availability time; that is causal withholding, not dormancy.

Every negative, weak, losing, censored, unresolved, sparse, contradictory, unusual, unmatched, and novel case remains registered. The retention rule is `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

## Governing separation

Step-1 has two ordered layers:

1. **Phase 1 freezes structure.** It establishes event chronology, origins, descendants, incremental inherited-information depth, reset boundaries, causal availability, and immutable identities.
2. **Phase 2 characterizes the frozen structure.** It may group and name already-frozen structures using family, geometry, flow, book/FIFO, time, curve, roll, fundamentals, or other lawful characteristics. Those descriptors cannot retroactively create a chain or move a Phase-1 boundary.

The `D0` through `D5` labels describe realized inherited-information depth. They are not pre-exhaustion geometry families and are not assumed before the census calculates them.

## Canonical inputs and two census views

The native source is Databento `GLBX.MDP3` MBO for the exact approved continuous-symbol basis, with every object, raw contract resolution, instrument, publisher, channel, sequence, event clock, receive clock, mapping interval, adapter revision, and source hash preserved.

Step-1 produces two additive views from the same chronology:

- `LEGACY_CONTROL` reconstructs the trade/top-of-book compatibility surface required by the frozen detector and lineage doctrine. Revealed overlap weeks must satisfy the predeclared recall, precision, family, endpoint, depth, and gain-sign equivalence gates. Mismatches are retained and decomposed.
- `V4_NATIVE_FULL` uses the lawful native MBO-derived state. It is a new structural census, not a rewrite of the frozen legacy population. If richer causal state supports a different structure, it receives a new versioned identity instead of being forced into an old label.

The current five-year executable keeps the frozen event detector and inherited-information lineage machinery for both views, while recording native state and taxonomy on the V4 view. A future richer native structural engine must be additive and must not silently claim that the current coarse native annotation already performs that discovery.

## MBO reconstruction contract

Native DBN bytes remain canonical. Derived state is an auditable causal representation.

- `A`: add a resting order.
- `C`: remove the disseminated cancelled quantity; delete the order when exhausted.
- `M`: replace current state. A price change or size increase loses FIFO priority; a same-price nonincrease retains priority.
- `R`: clear the resting book for the instrument.
- `T`: aggressing trade record; it does not itself mutate the resting book.
- `F`: resting fill detail; the corresponding book reduction is represented separately, so this record does not itself mutate the book.
- `N`: no book-state mutation.

FIFO is reconstructed from message and snapshot order where supported; no native `PriorityID` is invented. Event groups are not sampled mid-update. A completed state is emitted only at `F_LAST`. Snapshot/bootstrap records initialize state but do not masquerade as live activity. Missing references, source gaps, sequence discontinuities, unsupported actions, and integrity counters remain explicit.

## Per-second causal signal

For each second, classify valid trades by price versus the concurrent best-bid/best-ask midpoint. Accumulate aggressor buy quantity `B` and sell quantity `S`. Midpoint trades and invalid/no-book cases are recorded but do not receive an invented side.

The frozen detector signal is trailing-20-second aggressor-volume imbalance:

```text
roll20(t) = (B20(t) - S20(t)) / (B20(t) + S20(t))
```

when the denominator is positive. Price and book state are causally forward-filled inside the already-bounded chronology. Each UTC source day has a threshold equal to the 85th percentile of finite `abs(roll20)` values. Day-native thresholding does not reset the continuous Sunday-to-Friday event chronology.

## Exhaustion-event construction

A candidate second `t0` must:

1. fall inside available history/aftermath and genuine weekly trade boundaries;
2. have finite `roll20(t0)` whose magnitude meets the UTC day’s 85th-percentile threshold;
3. be an absolute local maximum in the `t0-5..t0+5` window;
4. survive deterministic refractory selection: candidates are ordered by prominence then magnitude, and no selected pair may be closer than 45 seconds.

Prominence is `abs(roll20(t0))` minus the median absolute imbalance over `t0-30..t0-10`. Event polarity is `+1` for positive `roll20(t0)` and `-1` for negative. The `-60..+60` curve is oriented by multiplying by polarity and is causally filled only within that window.

The structural endpoint begins at the first post-`t0` second in a run of three causally forward-filled oriented `roll20 <= 0` observations. The third observation is the causal-confirmation time. If no such run exists before the true weekly boundary, the endpoint is censored rather than invented.

Events are ordered continuously from the first actual Sunday-reopen trade through the last actual trade before weekly close. UTC midnight, hour ending, file changes, holidays, and contract-roll file partitions do not reset the chain.

## Behavior vector used for lineage

After a causally confirmed endpoint, the frozen full-path behavior vector contains 22 dimensions:

- the next exhaustion’s same-versus-flip polarity encoded as `+1/-1`;
- signed price displacement at 5, 10, 20, 30, 60, 120, and 300 seconds;
- signed maximum favorable excursion at the same seven horizons;
- signed maximum adverse excursion at the same seven horizons.

Tick-valued dimensions receive an `asinh` transform. Standardization uses training weeks only. Censored or invalid vectors remain registered and are excluded only from a model cell that cannot lawfully score them.

## D-depth calculation

For a candidate descendant at depth `d`, compare two models on exactly the same eligible training and test events:

- the short model uses the latest `d-1` predecessor aftermath vectors;
- the long model adds exactly the predecessor `d` events back.

For each out-of-time event and model:

```text
incremental_gain(d) = loss(short d-1 history) - loss(long d history)
```

A positive value means the added older ancestor improved prediction. The frozen model families are multi-output Ridge, distance-weighted KNN, and ExtraTrees. Hyperparameters are selected only inside the training chronology. Long-history evaluation uses chronological expanding whole-week folds; no test-week tuning is allowed.

For each origin event, realized structural depth starts at zero and advances consecutively while all three model families have finite positive per-instance gain at the corresponding descendant:

- `D0`: no verified inherited link;
- `D1`: the immediate predecessor’s aftermath adds information about the next event;
- `D2`: the event two episodes back adds information beyond the latest one;
- `D3`, `D4`, and `D5`: the corresponding progressively older ancestor continues to add information beyond the shorter history.

The first failed, incomplete, or unscored depth stops the realized consecutive depth for that origin and records the exact uncertainty. It does not delete the origin. A deterministic chain ID hashes `census_view | week | origin_event_id`. The population row retains ordered members, ordered ancestry, reset event, elapsed seconds, per-model gains, causal-link availability, censorship, integrity reasons, and engine/ruleset/source hashes.

Aggregate depth and per-origin lineage are distinct. Population-level D2-D4 usefulness does not prove that one unchanged ancestor persists through every descendant. Cross-depth association tests and causal-link timing distinguish inherited fixed-origin chains from rolling memory or local re-origination.

## Causal-executable axis

Retrospective structural depth and causally executable depth are separate axes; neither overwrites the other.

At a descendant `t0`, a predecessor field is executable only when its endpoint was causally confirmed and the required aftermath horizon had completed by the descendant’s `t0`. Time is used as an availability gate, not as a Phase-1 characteristic. Structural information that was not yet available may remain a valid retrospective finding but is labeled not yet executable.

## Existing A/B/C pre-family annotation

`A`, `B`, and `C` are frozen pre-exhaustion geometry clusters. They are not D depths and cannot define Phase-1 chain membership.

For each event, orient the 61-sample `t0-60..t0` roll-20 curve by event polarity. Build the frozen 78-feature vector from:

- every other sample of the baseline/excursion-normalized build curve;
- every other sample of the peak-relative curve;
- baseline, log excursion, log prominence, threshold-crossing positions, rise duration, early/mid/late slopes, slope changes, roughness, and dispersion.

Apply the frozen RobustScaler with the 20th-to-80th-percentile range, calculate Euclidean distance to the frozen A/B/C centroids, and choose the nearest centroid with deterministic A/B/C tie order. The exact distance vector is retained. No outcome, post-`t0` price, or future data participates.

Family A’s later post-state classifier and the validated aftermath labels are annotations for later characterization. B/C subtype doctrine is not invented when support is insufficient.

## Grouping and naming D-structure families

New D-structure families are created only after Phase-1 IDs and boundaries freeze.

1. Build one characterization row per frozen structure without changing membership. Preserve raw and normalized values, explicit nulls, availability times, evidence pointers, and integrity state.
2. Characterize across all lawful dimensions: D depth; rolling-versus-inherited evidence; polarity sequence; A/B/C annotation and distances; aftermath-state sequence; pre/post curve geometry; endpoint timing; inter-event spacing; full MBO action mix; top-20 and full-depth FIFO/queue behavior; book pressure, absorption, depletion, replenishment, resilience and churn; synchronized curve/roll; session context; and relevant causal fundamentals.
3. Separate discovery and confirmation chronologically. Choose transformations and grouping on discovery data, then require recurrence, support, and characteristic stability on untouched time blocks. Record overlap, ambiguity, instability, and falsifiers.
4. Allow hierarchical, overlapping, rare, and novel groups when supported. Never force every structure into one family. Cases may remain `UNASSIGNED`, `AMBIGUOUS`, `NOVEL_CANDIDATE`, or `UNRESOLVED`.
5. Give every frozen family an immutable machine identity such as `D4-FAM-003-v1`. Store the versioned rule/centroid/medoid, member IDs, discovery and confirmation support, distance or membership scores, representative examples, closest falsifiers, and source hashes.
6. Add a human-readable alias only after the characteristics replicate, for example `D4 | same-same-flip-same | reload continuation`. The alias describes the evidence; it does not replace the machine identity. Rename by versioning the alias metadata, never by changing past membership silently.
7. Frankie may propose names collaboratively from the full evidence. Greg approves any promoted operational name or dormant feed decision. Known structures are minimum phenomena to investigate, not clues to conceal.

The current V4 census annotation `FLOW_POSITIVE/FLOW_NEGATIVE × DEPTH_BID_DOMINANT/DEPTH_ASK_DOMINANT/DEPTH_BALANCED/DEPTH_UNKNOWN × QUEUE_DENSE/QUEUE_SPARSE` is a coarse native state label. It is retained as evidence but is not, by itself, the final D-family taxonomy.

## Dual-view crosswalk

After both views freeze, construct an immutable crosswalk that preserves:

- one-to-one matches;
- legacy splits into multiple native structures;
- native merges supported by richer state;
- depth and reset agreement/disagreement;
- support changes and view-only cases;
- source, contract, roll, or integrity reasons for disagreement.

Neither view overwrites the other. Disagreement is a result.

## Required outputs and receipts

Every completed census must bind at least:

- view, origin, chain ID, ordered members, ancestry, successor, reset, depth, and elapsed time;
- inherited-information evidence and uncertainty for every attempted depth/model cell;
- causal/executable availability per link;
- family/native annotations without granting them boundary authority;
- censored/unresolved/negative/contradictory/novel status;
- exact dataset, schema, requested continuous symbol, resolved raw contract, instrument, publisher, channel, sequence, clocks, DBN key and SHA, mapping/roll interval, adapter, engine, ruleset, and source hashes;
- shard coverage, deterministic merge/reconciliation, population/index hashes, overlap equivalence, and fail-closed completion receipt.

Sharding is an execution partition only. It may not change semantics, thresholds, population membership, or naming. The merged union must reconcile exactly.

## Source precedence and exact references

This direct method pack is the compact operating explanation. The following exact sources are installed in the same uniform superset build and remain fully retrievable by both Frankies:

- `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json`
- `research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json`
- `research/NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json`
- `research/NG_EXHAUSTION_CHAIN_STEP1_ORIGINAL_FILE_MAP_20260820.md`
- `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.md`
- `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json`
- `research/ng_exhaustion_chain_canonical_table_20260817.py`
- `research/ng_exhaustion_chain_phase1_discovery_20260817.py`
- `research/ng_exhaustion_chain_phase1_structural_54w_20260817.py`
- `research/ng_exhaustion_chain_phase1_causal_54w_20260817.py`
- `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`
- `research/ng_exhaustion_mbo_5y_step1_census_20260822.py`
- `research/kalshi/ng_exhaustion_step1_completion_gate.py`

If this pack and an exact executable source disagree about what the current implementation does, report the discrepancy and follow the executable source for reproduction. If a later binding contract changes the intended method, version this pack and preserve the prior version and hashes.

## Build placement and activation

This file is a required static component of the uniform two-Frankie build. The role-context build receipt binds its full bytes, SHA-256, exact reference-source identities, role-profile hash, and uniform-build hash.

- Real-Time Frankie: `DIRECT`
- Forecaster Frankie: `DIRECT`
- Dormancy: forbidden by default; allowed only after Frankie requests the exact stable surface ID and Greg approves it
- Nova token optimization: disabled for this build

A build that cannot load or hash this method pack and all exact reference identities fails closed before any provider request.
