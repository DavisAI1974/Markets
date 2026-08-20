# NG Exhaustion V4 Clean-Source Deep-Dive Complete Findings — 2026-08-20

Status: **AUTHORITATIVE CLEAN-SOURCE V4 DATA/REPRESENTATION/PROVENANCE HANDOFF. FIVE DEEP DIVES COMPLETE. NO V4 LAUNCH. NO PERMANENT FRANKIE MUTATION.**

Branch: `chatgpt/ng-exhaustion-entry-timing-revival-20260818`

## Authority boundary

This record consolidates the completed clean-source deep dives:

1. V4 Gap Source Deep Dive;
2. V4 Trajectory Deep Dive;
3. V4 Geometry Deep Dive;
4. V4 History Deep Dive;
5. V4 Ledger Deep Dive.

These deep dives were explicitly forbidden from using V3 model/trade outputs as empirical evidence about exhaustion. Therefore this record does **not** use V3 scores, AUCs, exact PRIOR/T0/H timing results, continuation/depth/P/O/S/X predictive outcomes, directional economics, fixed-horizon trade results, nulls, or model-specific predictive claims to establish any fact about exhaustion behavior.

The evidence base for this record is limited to trustworthy sources:

- frozen detector/canonical evidence and their implementation semantics;
- finalized Phase-2 and frozen runway records;
- preserved lineage/ancestry and chronological support counts;
- raw causal price/trade/flow/dipole/book interfaces and archive schemas;
- timestamp, contract, source, revision, missingness and provenance code paths;
- current V4 contracts, state/graph design and execution-interface inspection.

V3 code may be referenced only where it reveals a research-system/interface defect. Such a defect is not evidence that any underlying V3 predictive signal was valid.

Every chain/case remains preserved. Sparse, negative, unresolved, missing-channel, disagreement, censored, losing or difficult cases are never dropped merely because they are inconvenient.

---

## Executive conclusion

The clean-source research reached one central conclusion:

> **Core V4 is not broadly blocked by missing market data. Most of the needed ancestry, temporal, price/path, signed-flow, dipole and aggregate-book state already exists or is causally derivable. The dominant gaps are causal clock semantics, provenance/coverage, missingness-safe representation, unresolved-lifecycle geometry, immutable state/ledger identity, and the prediction-to-execution handoff.**

A few narrower data/source gaps remain genuinely unresolved:

- whether the frozen detector exposes a separate continuous detector-native exhaustion-intensity stream;
- whether historical MBO/order-event coverage is complete enough to support literal queue survival/replenishment rather than aggregate MBP depth recovery;
- exact per-session historical book coverage across the V4 population;
- additional independent history for D3/D4/D5 support outside the frozen 55-week corpus.

Core ancestry/time/price/dipole geometry should **not** be delayed merely to acquire another generic market feed.

---

# 1. Master gap classification

The clean deep dives use these classifications:

- `ALREADY_EXISTS` — trustworthy source already stores the required object/field;
- `CAUSALLY_DERIVABLE` — lawful transformation can be computed using only information available by current cutoff;
- `NEEDS_NEW_REPRESENTATION` — source information exists, but V4 needs a new state/schema/graph/interface representation;
- `TIMESTAMP_OR_PROVENANCE_GAP` — value may exist but its lawful availability/source/revision identity is not yet sufficiently bound;
- `MISSING_RAW_DATA` — the needed measurement is genuinely absent from proven sources;
- `BLOCKED_BY_UNVERIFIED_SOURCE` — source capability exists, but actual historical coverage/identity is not certified;
- `INSUFFICIENT_HISTORY` — current chronology cannot support the intended population claim.

## High-level matrix

| V4 need | Clean classification | Finding |
|---|---|---|
| root/predecessor order | `ALREADY_EXISTS` | frozen canonical/lineage preserves ordered ancestry and origin identity |
| predecessor causal confirmation/onset anchors | `ALREADY_EXISTS` retrospectively | usable live only after lawful availability/known-by semantics are attached |
| predecessor-to-predecessor gaps | `CAUSALLY_DERIVABLE` | differences of already-known causal anchors |
| predecessor-to-live age | `CAUSALLY_DERIVABLE` | current lawful cutoff minus already-known predecessor anchor |
| unresolved predecessor lifecycle | `NEEDS_NEW_REPRESENTATION` | build `UNRESOLVED/RESOLVED/CENSORED` state rather than reading future chain outcome |
| unresolved-overlap age | `CAUSALLY_DERIVABLE` + representation | age the unresolved predecessor continuously without future target clocks |
| price/path state | `CAUSALLY_DERIVABLE` | timestamped price/quotes support displacement, range, slopes and path-so-far |
| signed-flow persistence/reversal | `CAUSALLY_DERIVABLE` | requires frozen signing/transform revision and availability provenance |
| roll-20/dipole path | `ALREADY_EXISTS` as causal basis / derivable | current machinery already supports causal roll-20 history |
| dipole run/area/slope/curvature/crossing | `CAUSALLY_DERIVABLE` | backward-only transforms; persistence confirmation may not be backdated |
| aggregate MBP depth resilience | `CAUSALLY_DERIVABLE` where coverage verified | MBP-10 supports depth/imbalance/recovery paths |
| literal queue survival/replenishment | `BLOCKED_BY_UNVERIFIED_SOURCE` | requires provenance-complete MBO/order identity, not merely aggregate depth |
| continuous detector-native exhaustion intensity | `BLOCKED_BY_UNVERIFIED_SOURCE` / possible `MISSING_RAW_DATA` | not proven as a separate frozen per-second detector output |
| exhaustion slope/curvature as detector-native state | dependent | lawful only if native intensity is proven; otherwise use clearly named V4 proxy |
| ordered ancestry graph | `NEEDS_NEW_REPRESENTATION` | source order exists; V4 graph schema/edges are additive representation |
| cross-link timing/scale/path geometry | `CAUSALLY_DERIVABLE` + representation | source measurements mostly exist; ratios/distances are new V4 features |
| channel-specific encoders/fusion | `NEEDS_NEW_REPRESENTATION` | raw channels are separable; fusion architecture is not a data-acquisition issue |
| per-channel missing/stale/not-known mask | `NEEDS_NEW_REPRESENTATION` | hard requirement for causal movie |
| actual detector mark/known-by timestamp | `TIMESTAMP_OR_PROVENANCE_GAP` | canonical retrospective `t0` cannot substitute for live discovery time |
| per-channel `ts_event`/`ts_recv`/available-at | `TIMESTAMP_OR_PROVENANCE_GAP` | raw multi-clock data exists, but derived/current state is not fully field-addressable |
| exact contract/series/roll identity | `TIMESTAMP_OR_PROVENANCE_GAP` | must pin dataset/symbol/roll/instrument/definition per source interval |
| event-to-raw-message provenance | `TIMESTAMP_OR_PROVENANCE_GAP` | immutable instance→raw object/message-range mapping not yet proven |
| immutable V4 probability/lock ledger | `NEEDS_NEW_REPRESENTATION` | contract exists; end-to-end persisted implementation not verified |
| execution handoff identity | `NEEDS_NEW_INTERFACE` | execution must consume sealed signal identity and may not re-predict/re-time/re-fuse |
| D3 fine stratification | `INSUFFICIENT_HISTORY` | clean support becomes thin when subdivided |
| D4/D5 population calibration | `INSUFFICIENT_HISTORY` | preserve as case evidence only until chronology expands |

---

# 2. Critical clock finding: canonical `t0` is not live discovery time

The geometry/ledger deep dives found the most important pre-V4 clock distinction.

The frozen retrospective event detector/canonical builder identifies canonical exhaustion `t0` using retrospective event construction that includes a day-level magnitude threshold and a local-maximum neighborhood extending around the candidate. Therefore canonical `t0_idx` is a valid frozen retrospective event anchor, but **it is not proof that Frankie could know the exhaustion existed at that instant live**.

V4 must preserve distinct clocks:

1. `ts_event` — exchange/source market-event time;
2. `ts_recv` / `observed_at` — when the observation became available to the process;
3. `detector_marked_at` / `event_known_by` — when the upstream causal detector may lawfully declare the exhaustion event known;
4. `structural_onset_at` — when a candidate structural resolution begins;
5. `structural_confirmation_at` — when persistence makes that resolution causally confirmable;
6. `feature_available_at` — latest lawful availability time among all observations/transforms used in the feature;
7. `model_evaluated_at`;
8. `lock_decided_at` / `decision_available_at`.

No derived feature may be available earlier than the latest lawful availability of all contributing inputs. Persistence-confirmed state may not be backdated to the first observation in the persistence run.

This is distinct from the retrospective-target clock problem. A system can be chronological in `ts_event` and still leak by using information whose `ts_recv`/availability time was later.

### Required rule

**Align the causal V4 graph on when Frankie could actually know the information, while preserving source event time separately for market geometry.**

---

# 3. Unresolved predecessor / survival-resolution state

The clean trajectory dive determined that the proposed survival/resolution idea is mostly a **state-construction problem, not a missing-data problem**.

## Buildable causal lifecycle

For each causally known predecessor, V4 can maintain:

- predecessor identity and chain order;
- predecessor `known_by` timestamp;
- structural onset when it becomes observable;
- structural confirmation when it becomes lawfully confirmed;
- `UNRESOLVED` state until confirmation;
- elapsed unresolved age;
- right-censored state if the observation period ends while unresolved;
- current causal price/path evolution;
- current signed-flow path;
- current roll-20/dipole path;
- current aggregate book/depth recovery where source coverage exists;
- known ancestry and relative timing/scale context;
- per-channel missing/stale/not-known masks.

The live state must **not** consume retrospective fields that encode the eventual next event, future chain membership, future depth, future target family/polarity or future target time.

Historical overlap labels remain valid posthoc scoring/reveal metadata. They are not lawful live features.

## Survival/hazard output

The state needed to *test* a transition/termination hazard is buildable, but the deep dives did not fit or validate such a model. A hazard/resolution probability is therefore a **V4 model/output hypothesis**, not a current empirical law.

---

# 4. Trajectory fields that are build-ready

## Price/path

Causal timestamped price/quote observations support:

- current price and mid;
- tick-normalized displacement;
- range-so-far;
- MFE-so-far / MAE-so-far;
- backward-looking slope and curvature;
- path-shape descriptors;
- causal path distance/similarity to already-known predecessor paths;
- current/predecessor scale ratios.

Never use eventual full-window extrema or future endpoint geometry.

## Signed flow

Existing raw trade and quote information is sufficient to derive signed aggressor flow causally, subject to a frozen and versioned signing rule. V4 can derive:

- cumulative signed-flow persistence;
- trailing multiscale flow summaries;
- reversal magnitude;
- sign-run state;
- current/predecessor relative flow scales.

The signing/classification transform itself must carry revision/hash and source watermark provenance.

## Dipole / roll-20

The frozen runway/live machinery provides a causal roll-20/dipole basis. V4 can derive, using only past/current observations:

- sign-run length;
- area/integral over frozen window or current sign run;
- slope;
- change-of-slope;
- curvature;
- observed zero crossing;
- persistence-confirmed crossing;
- reversal impulse under a predeclared formula;
- cross-link dipole magnitude/shape ratios.

No centered/future smoothing is allowed.

### Important redundancy note

Roll-20/dipole is derived from signed flow. Therefore flow persistence, dipole area, dipole slope and any exhaustion proxy based on oriented roll-20 are related coordinate systems, not independent raw sensors. V4 should keep them identifiable for ablations without pretending each is separate raw information.

## Book/depth

Where historical MBP-10 coverage is verified, V4 can construct aggregate book geometry and resilience from:

- ordered bid/ask levels;
- level sizes/counts where available;
- spread;
- imbalance;
- depth depletion/recovery;
- state age/staleness;
- post-shock aggregate replenishment/resilience trajectories.

Literal order survival, add/cancel lineage or queue replenishment requires a proven MBO/order-event source for the relevant instance. Aggregate MBP recovery must not be mislabeled as literal queue survival.

---

# 5. Detector-native exhaustion intensity remains unresolved

The clean-source dives verified event-level exhaustion structure and causal roll-20/dipole state, but did **not** prove that the frozen detector exposes a separate timestamped continuous detector-native exhaustion-intensity scalar.

Therefore V4 must choose one of two lawful paths:

1. prove that the frozen detector can causally emit/replay a continuous native intensity series, with exact revision and availability timestamps; or
2. omit that native field and define a separate V4 proxy namespace, for example polarity-oriented roll-20 trajectory, without calling the proxy detector-native intensity.

Do **not** reconstruct a supposed continuous detector intensity from retrospective endpoint milestones or future information.

Any detector-intensity slope/curvature claim depends on first resolving this source question.

---

# 6. Ordered ancestry and geometric state

The clean geometry dive found that the ancestry skeleton is already available.

## Existing/derivable basis

V4 can construct from clean sources:

- root/predecessor order;
- known ancestry origin;
- predecessor confirmation/onset anchors once lawfully available;
- predecessor-to-predecessor temporal gaps;
- predecessor-to-live age;
- known hop count/path length;
- inter-link gap ratios;
- tick-normalized price displacement/range ratios;
- flow/dipole/book relative scales where channels exist;
- path-shape distances;
- session/contract context;
- causal missingness/provenance state.

## New representation

The binding V4 graph should materialize only causally known state, such as:

- known exhaustion/predecessor nodes;
- live-state node at current cutoff;
- optional session/contract context node;
- `CHAIN_PREDECESSOR_OF` edges;
- `CONFIRMED_BEFORE` edges;
- `LIVE_STATE_OF` edges;
- causal temporal adjacency;
- book/flow interaction edges only when both endpoint states are causally available.

No target node may be inserted before the target itself is causally represented. No placeholder may encode future existence, location, time, polarity, family or final depth.

## Geometry invariance/equivariance rules

- preserve causal chain order; do not impose permutation invariance on ancestry;
- preserve book depth/rank order; do not make level rank unordered;
- test price translation using ticks/deltas rather than absolute price where lawful;
- use causal ages/gaps, not target-relative clocks;
- any timing deformation/jitter test must never move information earlier than lawful availability;
- polarity/sign transformation remains an ablation, not an assumption;
- missing channels remain explicit rather than causing case deletion.

---

# 7. Missingness and staleness are first-class V4 state

A major representation gap is that V4 needs richer state than numeric fill/default behavior.

At every cutoff/channel, distinguish at minimum:

- `OBSERVED`;
- `PAST_CARRY`;
- `STALE`;
- `MISSING`;
- `STRUCTURALLY_NOT_YET_KNOWN`;
- `NOT_APPLICABLE`;
- true numerical zero.

A later observation may not be backward-filled into an earlier V4 movie state and then represented as if it had been known earlier. Retrospective completed-window utilities may legitimately summarize an as-of-cutoff window, but V4's immutable per-second movie is stronger: **old frozen states cannot later be rewritten by a newly arrived observation.**

Every carried value must preserve its source timestamp/age.

---

# 8. Raw-source and contract provenance gates

The raw ingestion interfaces are capable of preserving rich identity, including event/receive timestamps, instrument identity and level data. However source capability is not proof of population-wide historical coverage.

## Required source identity per instance/channel

V4 must pin:

- dataset/publisher;
- schema/message type;
- requested continuous symbol where applicable;
- resolved `raw_symbol`;
- `instrument_id`;
- point-in-time definition period;
- tick size / unit / tick value where needed;
- continuous-series roll rule/method;
- source object/file identity;
- message or row range/watermark;
- source content hash;
- transform/builder revision/hash.

## Continuous-series trap

Repository backfill code explicitly documents a basis mismatch risk between `NG.v.0` and `NG.n.0`. Therefore V4 must never treat continuous NG as one identity-free series. Exact roll basis and point-in-time constituent identity are fail-closed provenance requirements.

## Historical book coverage

Earlier repository audit/backfill code documents incomplete L1 coverage in an audited subset and adds machinery to repair it, but implementation of a repair path is not proof that every required historical session was subsequently filled.

Before V4 claims book features are available for the full population, produce an exact per-session/channel coverage manifest for MBP/MBO/L1 as applicable.

Missing book/MBO for an instance does **not** justify dropping the instance. The channel remains explicitly missing.

---

# 9. Clean historical support findings

The history deep dive used the frozen characterization corpus/lineage rather than V3 predictive outputs.

## Authoritative historical scope

The frozen exhaustion campaign covers **55 complete NG trading weeks**, based on **329 unique raw dates**, spanning approximately **2025-06-29 through 2026-07-17** under the protected characterization campaign.

There is no verified pool of complete, provenance-certified but unused weeks inside that frozen corpus. The first 18 weeks already served discovery/training roles and cannot later be relabeled as fresh OOT evidence.

The preserved chronological evaluation/confirmation lineage population spans 37 weeks and contains approximately:

- D0: 135,860 cases;
- D1: 18,837 cases;
- D2: 1,592 cases;
- D3: 124 cases;
- D4: 8 cases;
- D5: 1 case.

The exact deep-tail counts are preserved as support evidence, not predictive outcomes.

## Support disposition

- D0/D1: large historical populations;
- D2: meaningful population characterization support;
- D3: limited support, especially after stratification by ancestry/geometry/regime;
- D4/D5: preserved case studies only; no population calibration/general law.

Additional independent history is most valuable if it contributes new D3/D4/D5 or otherwise rare chronology, not merely more abundant shallow cases.

## Expansion policy

For history outside the frozen 55-week span:

1. certify complete-week boundaries and raw-source provenance first;
2. pin object hashes, dataset/schema, symbol/instrument/definition/roll identity and channel coverage;
3. run qualifying weeks through the **unchanged frozen detector/canonical rules** into an additive expansion corpus;
4. never rewrite the original 55-week evidence;
5. measure what new deep/tail cases the added chronology contributes;
6. preserve every resulting case regardless of outcome.

No clean-source finding requires delaying core V4 merely to accumulate more D0/D1 rows.

---

# 10. Channel encoding/fusion: data exists, representation does not

The clean dives found separable source channels for:

- structural/ancestry state;
- price/path;
- trade/signed flow;
- dipole/roll state;
- book/depth where covered;
- session/contract context.

V4 should preserve identifiable channel namespaces and explicit channel masks. Separate encoders, flat concatenation, gated fusion and late fusion are **V4 architecture ablations**. No clean-source evidence establishes a winner in advance.

Do not let a combined representation erase source identity, missingness, availability time or the ability to inspect an individual channel.

---

# 11. Immutable probability movie and signal ledger

The ledger deep dive concluded that the V4 contract specifies the right lifecycle but an end-to-end sealed runtime implementation was not yet verified.

V4 needs one immutable probability record per:

`instance × model/snapshot × head × causal evaluation`

followed by a separate append-only first-lock/no-lock record.

## Minimum probability-record identity

At minimum bind:

### Identity

- `ledger_schema_version`;
- `ledger_id` / `signal_lane_id`;
- `instance_id`;
- stage;
- head;
- model ID/version/artifact hash;
- `frankie_snapshot_id`;
- parent snapshot ID;
- task-head version;
- `v4_graph_schema_version`.

### Causal clocks

- market cutoff `ts_event`;
- source maximum `ts_recv` / observed-at;
- `feature_available_at`;
- `model_evaluated_at`;
- `decision_available_at`;
- explicit clock-domain semantics.

### View/source state

- causal view/channel identity;
- ordered channel manifest;
- per-channel availability/missing/stale states;
- ancestry/lineage revision;
- session/contract identity;
- dataset/schema;
- continuous and raw symbol identity;
- instrument/definition/roll revision.

### Provenance

- source-manifest hash;
- raw object/message watermark/range where available;
- feature-builder hash;
- transform-config hash;
- graph/state canonical hash;
- feature payload hash;
- code revision.

### Prediction

- exact head probability/state vector;
- calibration artifact ID/hash;
- support-group ID/revision;
- eligibility state;
- abstention/no-lock reason.

## First-lock record

The first-lock record must reference the exact probability-entry hash and bind:

- lock-rule ID/hash;
- threshold/margin/persistence configuration;
- persistence-evidence interval;
- actual `lock_decided_at`;
- `decision_available_at`;
- exact frozen causal-view identity.

Persistence-confirmed locks are recorded at the moment persistence becomes lawfully known, not at the first second of the run.

---

# 12. Prediction-to-execution handoff is a hard seam

Execution must consume one sealed predictive object. It may not independently recreate the predictive question.

## Minimum interface rule

Execution receives an immutable:

- `signal_id`;
- `execution_handoff_id`;
- frozen head;
- frozen model/snapshot;
- frozen causal view/channel manifest;
- frozen probability/state;
- frozen lock time/availability time;
- source/feature/graph/provenance hashes;
- eligibility/abstention state.

Execution **must not** accept override inputs that silently substitute:

- a different model;
- a different head;
- a different causal view;
- a different checkpoint/lock time;
- a different source/channel set;
- a newly rebuilt feature vector;
- a re-run prediction.

If required provenance is missing, fail closed/abstain rather than reconstructing a nearby signal.

Execution may add new post-lock execution observations and test downstream entry/orientation/management, but it may never mutate the predictive record.

This makes prediction→execution routing a mechanical invariant rather than a research convention.

---

# 13. Active-instance immutability

The V4 lifecycle remains:

`snapshot -> causal state/graph movie -> probability movie -> frozen first-lock/no-lock ledger -> conservative reveal -> later learning/update candidate`

Rules:

- assign snapshot/model/head/schema identities before an instance begins;
- active overlapping instances retain their original snapshot;
- accepted later research updates apply only to later eligible instances;
- reveal may score a frozen call but cannot rewrite it;
- no backdated lock, probability, source state or graph edge;
- every rejected update and difficult instance remains durable evidence.

---

# 14. Hard pre-V4 launch gates from clean-source research

The five deep dives converge on these launch gates.

## Gate 1 — causal exhaustion discovery clock

Prove and persist actual `detector_marked_at` / `event_known_by`. Do not substitute retrospective canonical `t0`.

## Gate 2 — field/channel multi-clock provenance

Preserve `ts_event`, `ts_recv/observed_at`, feature `available_at`, model-evaluation time and decision time. Derived feature availability is the maximum lawful availability of all contributing inputs.

## Gate 3 — exact raw source / contract / roll provenance and coverage

Bind dataset/schema, series, roll method, raw symbol, instrument, definitions, source objects/message ranges/hashes and actual per-session channel coverage.

## Gate 4 — missingness-safe immutable causal state/movie

Create per-second model-independent state with explicit `OBSERVED/PAST_CARRY/STALE/MISSING/NOT_YET_KNOWN` semantics and no future back-fill.

## Gate 5 — unresolved predecessor lifecycle / survival representation

Build lawful `UNRESOLVED/RESOLVED/CENSORED` state, ages, known ancestry and causal trajectory without future target-relative information.

## Gate 6 — detector-intensity semantic resolution

Prove detector-native continuous intensity or omit it/use a clearly named proxy. Never silently rename roll-20.

## Gate 7 — immutable probability/first-lock ledger

Persist deterministic, hashed, versioned probability movie and first-lock/no-lock records.

## Gate 8 — sealed prediction→execution handoff

Execution consumes exact sealed signal identity and is structurally unable to re-predict, re-time or re-fuse the call.

## Gate 9 — sparse-stage scope

D4/D5 remain preserved case evidence until additional independent chronology changes support. Do not block D0–D3 core research solely because D4/D5 are sparse.

---

# 15. What can proceed immediately

Subject to user authorization for implementation, the clean research supports building the following without waiting for another broad market-data campaign:

- model-independent causal state assembler;
- explicit multi-clock provenance fields;
- unresolved predecessor lifecycle;
- causal ages/gaps;
- ordered ancestry graph;
- tick-normalized price/path geometry;
- signed-flow trajectory and frozen transform identity;
- roll-20/dipole geometry;
- aggregate MBP depth resilience where coverage verifies;
- explicit channel masks/missingness/staleness;
- source/contract/roll manifest binding;
- deterministic state/feature/graph hashing;
- immutable probability/lock ledger;
- sealed execution handoff.

The following remain conditional/gated:

- detector-native continuous exhaustion intensity;
- literal queue survival/replenishment unless MBO coverage is proven;
- book-dependent features on sessions without certified book coverage;
- D4/D5 population calibration;
- any learned survival/termination hazard;
- any trade edge, orientation, exit or profitability claim.

---

# 16. Clean-source V4 readiness answer

**GO for V4 implementation design/build work once separately authorized. NO-GO for a trusted V4 empirical launch until the causal clock, provenance, missingness-safe state, ledger and execution-handoff gates are mechanically closed and tested.**

There is no clean-source reason to postpone the core V4 representation simply to acquire more generic market data. History expansion can proceed additively in parallel, targeted at deep/tail support and source-coverage holes.

Nothing in this record validates a predictive edge, validates a trade, promotes a play, mutates permanent Frankie, changes the frozen detector/canonical evidence/runway, launches V4, or drops a chain/case.

---

## Companion records

Machine-readable matrix:

`research/NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_GAP_MATRIX_20260820.json`

Pre-launch checklist:

`research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`

Existing binding/context records to read with this file:

- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`
- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json`
- `research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md`
- `research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md`
- `research/NG_EXHAUSTION_V4_RESEARCH_THREAD_FINAL_20260820.md`
- `research/kalshi/FRANKIE_NEXT_CHAT_HANDOFF_20260820.md`
