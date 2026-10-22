# NG Exhaustion V4 Clean-Source Prelaunch Gates — 2026-08-20

Status: **BINDING IMPLEMENTATION-READINESS CHECKLIST FROM COMPLETED CLEAN-SOURCE DEEP DIVES. NO V4 LAUNCH.**

This checklist is distilled from:

- `NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_COMPLETE_FINDINGS_20260820.md`
- `NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_GAP_MATRIX_20260820.json`

It inherits the authority boundary that V3 model/trade outputs are non-authoritative for empirical exhaustion truth.

## Gate 1 — causal exhaustion discovery clock

Required before trusted V4 use of event-relative state:

- persist actual `detector_marked_at` / `event_known_by` from the causal detector path;
- preserve retrospective canonical `t0` separately;
- prove that no live feature, graph node, model opportunity window or lock is backdated to canonical retrospective `t0` merely because the event was later reconstructed there;
- keep event mark, structural onset and structural confirmation as distinct clocks.

**Pass condition:** every active event has an explicit causal known-by timestamp with frozen semantics and tests preventing substitution with retrospective `t0`.

## Gate 2 — multi-clock field/channel provenance

Required fields/semantics:

- `ts_event`;
- `ts_recv` / `observed_at`;
- per-channel/source `known_by` where needed;
- `feature_available_at`;
- `model_evaluated_at`;
- `decision_available_at` / `lock_decided_at`.

Derived state is available no earlier than the latest lawful availability of all contributing inputs and any persistence confirmation.

**Pass condition:** deterministic tests prove no field or feature can be consumed before its lawful availability time and no persistence-confirmed state is backdated.

## Gate 3 — exact source / contract / roll / coverage provenance

For every instance/channel bind:

- dataset/publisher/schema;
- requested continuous symbol;
- roll rule/method;
- resolved raw symbol;
- instrument ID;
- point-in-time definition period;
- tick size / unit / tick value where relevant;
- source object/file identity;
- source message/range/watermark;
- content hash;
- transform/builder revision/hash.

`NG.v.0` and `NG.n.0` or any other continuous-series basis may never be silently substituted.

**Pass condition:** every V4 state movie is reproducibly tied to exact source/series/definition identities and book/MBO channels are enabled only for sessions with verified coverage.

## Gate 4 — missingness-safe immutable causal state movie

At each cutoff/channel distinguish at minimum:

- `OBSERVED`;
- `PAST_CARRY`;
- `STALE`;
- `MISSING`;
- `STRUCTURALLY_NOT_YET_KNOWN`;
- `NOT_APPLICABLE`;
- true numerical zero.

Rules:

- no future/backward fill into an earlier frozen V4 state;
- every carried value retains source timestamp/age;
- missing channel never causes the case to be dropped;
- old frozen states are immutable when later observations arrive.

**Pass condition:** replay tests prove per-second state immutability and explicit missing/stale semantics.

## Gate 5 — unresolved predecessor lifecycle / survival representation

Build prospectively from causal state only:

- known predecessor identity/order;
- predecessor known-by time;
- unresolved age;
- `UNRESOLVED` / `RESOLVED` / `CENSORED` lifecycle;
- structural onset/confirmation only when lawfully available;
- known ancestry;
- causal price/flow/dipole/book trajectory and masks.

Forbidden live inputs include posthoc future-successor overlap labels, future chain membership, future depth, future target family/polarity and future target time.

**Pass condition:** unit/replay tests show the live lifecycle can be reproduced without any future descendant fields.

## Gate 6 — detector-intensity semantic resolution

Before using a field named detector/native exhaustion intensity:

- locate and prove a frozen causal per-second detector-native intensity stream with revision and availability timestamps; **or**
- omit the native field and use an explicitly different V4 proxy namespace such as polarity-oriented roll-20 trajectory.

Do not infer a continuous native intensity from retrospective endpoint milestones.

**Pass condition:** source semantics are explicit and impossible to confuse with a proxy.

## Gate 7 — immutable probability movie and first-lock ledger

Persist one immutable record per:

`instance × model/snapshot × head × causal evaluation`

Minimum identity/provenance:

- ledger/signal lane ID;
- instance/stage/head;
- model artifact/version;
- `frankie_snapshot_id` and parent;
- task-head version;
- `v4_graph_schema_version`;
- causal view/channel manifest;
- causal clocks;
- source-manifest hash;
- feature/transform/graph/code hashes;
- calibration/support revision;
- eligibility/abstention state;
- probability/state vector;
- missingness/staleness manifest.

First-lock/no-lock record must reference the exact probability-entry hash and bind lock rule, thresholds/margins/persistence, evidence interval, `lock_decided_at` and `decision_available_at`.

**Pass condition:** deterministic replay produces identical ledger hashes and first-lock identity; reveal cannot mutate/backdate any call.

## Gate 8 — sealed prediction-to-execution handoff

Execution receives one sealed predictive object referenced by:

- `signal_id`;
- `execution_handoff_id`;
- frozen head/model/snapshot;
- frozen causal view/channel manifest;
- frozen probability/state;
- frozen lock/availability timestamps;
- provenance hashes;
- eligibility/abstention state.

Execution may not override/recreate:

- model;
- head;
- view;
- channel set;
- checkpoint/lock time;
- feature vector;
- prediction.

If required provenance is missing, fail closed/abstain.

**Pass condition:** tests prove execution cannot invoke/rebuild predictor/features or substitute another view/head/time.

## Gate 9 — sparse-stage scope

Clean historical support remains materially thinner at deep stages.

- preserve every D4/D5 case;
- D4/D5 remain case evidence until additional independent chronology changes support;
- no universal D4/D5 timing, calibration, geometry or trade law;
- do not block D0–D3 implementation solely because D4/D5 remain sparse;
- additional history must be additive, provenance-certified and processed under unchanged frozen detector/canonical rules.

**Pass condition:** reporting and acceptance logic cannot hide sparse-stage uncertainty behind aggregate scores or delete rare cases.

## Build-ready areas once implementation is authorized

The clean-source deep dives support immediate implementation work on:

- causal state assembler;
- multi-clock provenance;
- unresolved predecessor lifecycle;
- causal ages/gaps;
- ordered ancestry graph;
- tick-normalized price/path geometry;
- signed-flow trajectory with frozen transform identity;
- roll-20/dipole geometry;
- aggregate MBP depth resilience where coverage verifies;
- channel availability/missingness/staleness masks;
- source/contract/roll manifests;
- deterministic state/feature/graph hashing;
- immutable probability/lock ledger;
- sealed execution handoff.

Conditional/gated areas:

- detector-native continuous intensity;
- literal queue survival/replenishment without proven MBO coverage;
- book-dependent features on uncovered sessions;
- D4/D5 population calibration;
- any learned survival/termination hazard;
- any trade edge/orientation/exit/profitability claim.

## Launch decision

**Implementation design/build may proceed only when separately authorized. Trusted empirical V4 launch remains NO-GO until Gates 1–9 are mechanically closed and tested.**
