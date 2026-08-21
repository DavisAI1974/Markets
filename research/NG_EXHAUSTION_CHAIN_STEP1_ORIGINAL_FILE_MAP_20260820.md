# NG Exhaustion Step-1 — Original Chain Census File Map — 2026-08-20

Status: **AUTHORITATIVE FILE-MAP CLARIFICATION. PROVENANCE ONLY FOR FROZEN 2026-08-17/18 RESULTS; NO EMPIRICAL RUN AUTHORIZED.**

This file exists because the initial chain-population census was being confused with the later V3 birth/depth/type prediction work and with the new per-D V4 prediction protocol.

## What Step 1 originally did

The original Step-1 job was to establish the chain population before asking Frankie to predict it:

`raw chronology -> canonical exhaustion events -> sequential behavioral lineage -> inherited-information survival/reset -> frozen realized chain depth/boundary -> post-freeze characterization`

The governing frozen contract is:

- `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json`

Its key rule is that Phase 1 discovers chain origin/descendants/depth/reset first. Family A/B/C, aftermath state, geometry, flow, book, time/session and similar characteristics are Phase-2/post-hoc descriptors and may not retroactively create or move a frozen Phase-1 chain boundary.

## Original three-week pilot machinery

These files established the original method but are **not** the files to run directly on five years:

1. `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json`
   - frozen doctrine for chain discovery versus later characterization;
   - chain membership/reset based on incremental out-of-sample inherited information;
   - no predefined family/time/shape segmentation in Phase 1.

2. `research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json`
   - three-week preregistration;
   - behavior-only full/sparse vectors;
   - ridge, distance-weighted KNN, extra trees;
   - lag-depth semantics and replication rules.

3. `research/ng_exhaustion_chain_canonical_table_20260817.py`
   - canonical event-table builder;
   - continuous Sunday-Friday trading-week stream;
   - frozen exhaustion detector convention;
   - dynamic endpoint, event chronology, sequential links and annotations;
   - frozen reveal/holdout equivalence check.

4. `research/ng_exhaustion_chain_phase1_discovery_20260817.py`
   - original structural lineage engine;
   - tests whether progressively older predecessor aftermaths add out-of-sample predictive information;
   - writes per-origin incremental gains and consecutive positive depth candidates.

5. `research/ng_exhaustion_chain_phase1_causal_20260817.py`
   - original causal/executable counterpart used by the later long-history adapter.

The original discovery script contains pilot-only exact assertions for the three weeks and 12,991 events. Those assertions are not chain doctrine and must not simply be date-edited in place.

## The correct long-history precedent: 54/55-week expansion layer

The repo already solved the first expansion correctly by wrapping/reusing the frozen machinery instead of overwriting it:

1. `research/NG_EXHAUSTION_CHAIN_PHASE1_54W_EXECUTION_PROTOCOL_20260817.json`
   - explicitly says to reuse the prior detector, endpoint, behavioral-vector and lineage semantics;
   - removes pilot-only week/event-count assumptions through an execution adapter;
   - replaces the tiny three-week validation schedule with temporally honest whole-week/out-of-time folds.

2. `research/ng_exhaustion_chain_canonical_54w_shard_20260817.py`
   - sharded week-by-week canonical construction using the frozen canonical builder;
   - exact Sunday-Friday coverage checks;
   - deterministic hashes and durable shard summaries.

3. `research/ng_exhaustion_chain_canonical_54w_merge_20260817.py`
   - merges the sharded population;
   - proves complete week coverage, ordering and schema consistency;
   - recovers all 3,429 original frozen reveal+holdout events as a regression/equivalence wall.

4. `research/ng_exhaustion_chain_phase1_structural_54w_20260817.py`
   - long-history structural lineage engine;
   - chronological expanding-era folds;
   - depths beyond the original pilot;
   - same ridge / extra-trees / KNN model families and behavior-only lineage semantics.

5. `research/ng_exhaustion_chain_phase1_causal_54w_20260817.py`
   - long-history causal/executable structural counterpart;
   - whole-week temporal folds and causal information horizons.

6. `research/ng_exhaustion_chain_phase1_reconcile_55w_20260817.py`
   - reconciles the held insert week into the frozen long-history population;
   - produces the realized survival-depth histogram, per-origin consensus depth and elapsed-time summaries without discarding awkward cases.

**This 54/55-week wrapper architecture is the implementation precedent for the new five-year Step-1 census.**

## Files that are NOT the Step-1 grouping engine

Do not use these as substitutes for the initial census:

- `research/ng_exhaustion_chain_birth_depth_type_recovery_v2_20260819.py`
- `research/ng_exhaustion_chain_birth_depth_type_recovery_v3_20260819.py`
- `research/ng_exhaustion_chain_recovery_features_v2_20260819.py`
- `research/ng_exhaustion_chain_recovery_features_v3_20260819.py`
- corresponding recovery model files.

Those files ask later predictive questions about continuation, eventual depth, chain-type state and timing. They consume a chain population; they do not define the original Step-1 structural population.

## Five-year update rule

Do **not** edit frozen 2026-08-17 files in place.

The five-year work gets new dated files and two explicitly separate structural views:

### View A — LEGACY_CONTROL

Purpose: preserve comparability with the frozen Step-1 experiment.

- reconstruct a MBP/trade-shaped compatibility surface from the true MBO stream;
- run the frozen canonical detector/endpoint/behavioral-lineage doctrine through a generalized long-history wrapper;
- require overlap/equivalence receipts before trusting the projection;
- never overwrite the frozen 55-week population or its findings.

### View B — V4_NATIVE_FULL

Purpose: discover the structure Frankie can see with the information he will actually receive.

- true MBO is first-class causal input, not archival decoration;
- preserve raw MBO actions and order identity plus causal book reconstruction;
- expose price/path, direct trade aggressor side, signed flow, dipole/roll-20, aggregate book, order/queue state, source/contract/roll provenance, clocks, missingness/staleness and other lawful V4 channels;
- allow richer information to reveal different/better structural organization;
- freeze that result as a **new V4-native census**, never as a rewrite of frozen Phase 1.

Disagreement between `LEGACY_CONTROL` and `V4_NATIVE_FULL` is itself a finding and must be retained.

## Correct sequence after the update

`five-year source/coverage verification`
`-> tiny MBO adapter/equivalence verification`
`-> LEGACY_CONTROL structural census`
`-> V4_NATIVE_FULL structural census`
`-> immutable crosswalk + frozen new population registry`
`-> support/family/depth characterization`
`-> later small blind V4 predictive pilots`
`-> later D/year predictive runs`
`-> full empirical validation last`

The per-D/per-year pilot protocol governs the **later prediction/testing stage**. It does not require D membership to be known before the Step-1 structural census that discovers/finalizes that membership.
