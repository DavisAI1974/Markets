# NG Exhaustion D0-D5 V4 Geometric State + Gated Self-Adaptation Contract — 2026-08-20

Status: **BINDING V4 RESEARCH ADDENDUM; ADDITIVE OVER V3; NO PERMANENT FRANKIE MUTATION, V4 LAUNCH, OR PLAY PROMOTION.**

Machine-readable companion:

`research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json`

## Authority and scope

This addendum applies the V4 Frankie architecture to every preserved exhaustion depth target:

- D0 terminality versus D1+ continuation;
- D1, D2 and D3 chain-stage birth;
- D4 and D5 preserved low-support chain-stage birth case studies;
- eventual final depth;
- P/O/S/X structural family/state as a separate head;
- SAME/FLIP or target polarity only as secondary context when causally knowable.

It extends, and does not replace:

1. the raw causal market surface;
2. the complete V3 live-state surface;
3. continuous per-instance V4 timing;
4. the frozen-versus-adaptive walk-forward comparison.

The V4 feature namespace must be distinct. No V4 field may rename, shadow, or silently substitute for a raw or V3 field.

## D-series target structure

Each task keeps its own label head and causal reveal rule.

| Head | Condition at instance start | Future target | Timing coordinate after scoring |
|---|---|---|---|
| D0 terminality | root exhaustion is causally represented | exact D0 versus D1+ continuation | root/candidate-relative; no descendant H fiction |
| D1 birth | root is causally represented | chain reaches D1 versus stops at D0 | PRIOR/T0/H for true D1; control-candidate-relative for stops |
| D2 birth | D1 predecessor set is causally represented | chain reaches D2 versus stops at D1 | same rule at the D2 boundary |
| D3 birth | D2 predecessor set is causally represented | chain reaches D3 versus stops at D2 | same rule at the D3 boundary |
| D4 birth | D3 predecessor set is causally represented | preserved D4 case versus D3 stop | case evidence only |
| D5 birth | D4 predecessor set is causally represented | preserved D5 case versus D4 stop | case evidence only |

The model scores every causal second in the natural opportunity window. Frozen target `t0`, PRIOR/H identity, seconds to birth, future depth, future target polarity, and future P/O/S/X state remain unavailable to the primary model. They may be attached only after the prediction ledger is frozen.

## Additive V4 geometric causal state

V4 adds a temporal attributed graph named `V4_GEOMETRIC_CAUSAL_STATE` on top of the raw and V3 surfaces.

### Nodes

At causal cutoff `c`, nodes may represent only facts available by `c`:

- the root exhaustion;
- each causally confirmed predecessor in chain order;
- the current live-market checkpoint;
- optional causally known session/contract context;
- book-side or price-path summary nodes only when their source observations are timestamped no later than `c`.

There is no target node before the target is causally represented. A placeholder node may not encode target existence, location, polarity, family, depth, or time-to-birth.

### Edges

Allowed typed edges are:

- `CHAIN_PREDECESSOR_OF` for already-known ancestry;
- `CONFIRMED_BEFORE` for known causal ordering;
- `LIVE_STATE_OF` from the current checkpoint to its represented predecessor/root context;
- `TEMPORAL_ADJACENT` for observations that were both available by `c`;
- `BOOK_INTERACTION` or `FLOW_INTERACTION` only when both endpoints are formed from causal observations.

No edge may be inserted because the future target later existed, shared a polarity, belonged to a family, or completed a depth.

### Node and edge attributes

The graph carries the existing rich causal market information rather than reducing it:

- complete V3 raw trade/mid direction and price-path state;
- displacement, range, MFE/MAE-so-far and dense causal lags;
- signed aggressor flow and roll-20/dipole state;
- MBP-10/book imbalance and book-path state;
- exhaustion/direction state already causally represented;
- relative causal ages and gaps between known predecessors;
- causal session/contract context;
- explicit missingness/provenance masks.

Price, flow, book, dipole, direction, and exhaustion information discoverable by cutoff `c` must be present. Future interpolation and target-relative anchoring remain prohibited.

## Geometric inductive-bias tests

The first V4 lane treats these as discovery-frozen ablations, not assumptions smuggled into the answer:

- **chain-node order:** preserve causal chain order; never impose permutation invariance on ordered ancestry;
- **set-like aggregation:** require permutation invariance only for genuinely unordered neighborhoods or book-level collections;
- **price translation:** test representations based on ticks/deltas so a harmless absolute price shift does not change the structural call;
- **relative time:** use causal ages/gaps rather than target-relative clocks or absolute frozen `t0`;
- **timing deformation:** test stability to small causal timestamp jitter/time warping without moving information earlier than it was available;
- **polarity/sign transformation:** test whether mirrored polarity should transform predictions consistently, but preserve asymmetry when the data rejects exact equivariance;
- **microstructure perturbation:** test stability to small lawful book/flow noise while preserving genuine discontinuities.

Every augmentation must be applied inside the discovery bank and frozen before OOT. An augmentation may never alter label chronology, reveal timing, or causal availability.

## Frozen and adaptive model topology

The preferred first topology is deliberately simple:

1. a shared causal graph encoder operating on the additive V4 graph;
2. separate task heads for D0 terminality, D1-D5 continuation, final depth, and P/O/S/X;
3. the existing discovery-frozen selective lock rule per model/head;
4. frozen and adaptive twins initialized from the identical discovery snapshot.

Start with the least complex graph aggregation that captures the predeclared structure. Convolutional/attention/message-passing variants remain independent ablations. Greater message-passing capacity is not assumed to be better.

Stage-local adaptation is the default. Cross-stage transfer requires a predeclared shared-encoder ablation and must report each stage separately so the large D0/D1 populations cannot hide D2/D3 damage or manufacture D4/D5 certainty.

## Immutable active-instance lifecycle

Every D-series instance follows:

`snapshot -> causal graph movie -> probability movie -> frozen lock/ledger -> conservative reveal -> candidate self-edit -> sandbox evaluation -> accept/reject for later research snapshots`

Rules:

1. Assign `frankie_snapshot_id` and model/head versions before the instance starts.
2. Keep that exact snapshot for the instance's full natural causal trajectory.
3. Never inject an update into an already-active overlapping instance.
4. Never revise, backdate, relabel, or delete its prediction after reveal.
5. Use the target only to score the frozen ledger and compute the posthoc timing coordinate.
6. Make any accepted research update available only to later instances whose start follows the update's causal acceptance time.

## Post-reveal self-edit packet

After conservative truth reveal, the adaptive research lane may generate a structured `self_edit_packet`. This is a proposal artifact, not permission to edit permanent Frankie, production code, frozen evidence, or an active model in place.

The packet must contain:

- source instance and stage/head identity;
- source `frankie_snapshot_id` and graph-schema version;
- source truth-reveal timestamp and causal-evidence cutoff;
- immutable prediction-ledger hash;
- error/calibration/latency diagnosis;
- causally reconstructed training examples and counterfactuals;
- proposed update scope: stage-local head, shared graph encoder, calibration, or abstention behavior;
- explicit forbidden-field audit;
- candidate adapter/update identifier;
- retention-suite hash and proposed evaluation budget;
- provenance for every synthetic or transformed example.

The self-edit generator may suggest examples, update directives, adapter settings, or loss weights. It may not directly patch live code, overwrite base weights, alter the lock ledger, choose a favorable OOT subset, or declare its own proposal accepted.

Packets become stale when their source snapshot is no longer the current evaluation parent. A stale packet must be regenerated or explicitly evaluated as a branched candidate; its prior reward cannot be reused.

## Candidate-update sandbox

Candidate updates run only in an isolated research twin and receive a new `candidate_adapter_id`. Prefer reversible adapters or similarly isolated parameter deltas for the first V4 implementation so every accepted research update has an exact rollback pointer.

The candidate is evaluated against:

- chronological later-instance replay unavailable to the packet generator during proposal construction;
- a frozen retention suite covering D0-D3 heads, class-specific errors, P/O/S/X, no-locks, wrong locks, and latency;
- preserved D4/D5 case checks without treating them as population validation;
- leakage and causal-availability tests;
- geometric robustness ablations frozen on discovery;
- calibration and selective-lock behavior;
- compute, latency, and turnover costs.

The evaluation uses the current parent snapshot. Candidate-vs-parent comparison must use identical eligible rows, timestamps, reveal rules, and scoring code.

## Acceptance and rollback gates

A candidate may enter only the adaptive **research** lineage when all mandatory gates pass:

- no leakage or forbidden-field failure;
- positive predeclared chronological predictive reward versus its exact parent;
- no protected regression beyond frozen tolerance;
- no unsupported stage/class collapse hidden by aggregate score;
- calibration and lock behavior remain within frozen tolerances;
- latency/compute cost stays inside the declared budget;
- all calls made before the candidate existed remain immutable;
- full provenance, parent, candidate, retention-suite and rollback hashes exist.

The reward is a vector, not a single self-reported score. Preserve at least log-loss, Brier score, calibration, discrimination, selective coverage, wrong-lock rate, no-lock rate, decision latency, class/stage stability, compute cost, and maximum protected regression.

Rejected candidates remain durable evidence with the rejection reason. `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` applies to rejected updates as well as difficult instances.

Research-line acceptance is not permanent Frankie promotion. Promotion remains a later deliberate adjudication requiring fresh prospective/OOT evidence.

## Sparse-stage protections

- D4 and D5 remain preserved case studies until support changes materially.
- A D4/D5 outcome may generate a diagnostic self-edit packet, but it may not by itself authorize a shared-encoder or general D-series update.
- Candidate changes motivated by D4/D5 must first pass the full D0-D3 retention and chronological evaluation suite.
- No unsupported universal timing, geometry, family, or trade law may be inferred from sparse stages.

## Required durable records

For every stage/head/instance/model lane preserve:

- raw and V3 feature revision identifiers;
- `v4_graph_schema_version`;
- `frankie_snapshot_id` and parent snapshot;
- exact causal graph/movie provenance;
- immutable probability and decision ledger hash;
- lock rule and task-head version;
- truth-reveal rule and reveal timestamp;
- posthoc PRIOR/T0/H or candidate-relative coordinate;
- `self_edit_packet_id`, when generated;
- `candidate_adapter_id`, when trained;
- retention-suite hash and reward vector;
- accept/reject decision, reason and causal acceptance time;
- rollback pointer;
- all censored, no-lock, wrong-lock, losing, low-support, model-disagreement and rejected-update cases.

## Compute policy

The first V4 experiment may batch self-edit proposals and candidate training after several reveals to control cost. Batching is a compute decision only. It may not change what information was available to an instance, reorder chronology, or inject later outcomes into earlier snapshots.

## Protected boundaries and launch state

Do not modify:

- frozen detector;
- canonical rows/evidence;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings;
- frozen runway clock;
- permanent Frankie or Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play;
- any frozen V3 benchmark output.

This contract authorizes D0-D5 V4 **design and implementation work only**. It does not authorize launching V4, reading protected result artifacts, committing, pushing, merging, changing permanent Frankie, or promoting a play.

## Design sources

- Self-Adapting Language Models (SEAL): <https://arxiv.org/pdf/2506.10943>
- Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and Gauges: <https://arxiv.org/pdf/2104.13478>

These sources motivate the proposal-generation/evaluation loop and the structural inductive biases. They are not empirical evidence that the resulting D-series market model will improve.
