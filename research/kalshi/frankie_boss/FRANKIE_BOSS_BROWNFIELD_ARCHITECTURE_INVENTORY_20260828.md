# Frankie BOSS brownfield architecture inventory

Date: 2026-08-28

Repository: `DavisAI1974/Markets`

Branch at start of inventory: `codex/frankie-boss-sol-replacement-20260824`

Pre-inventory HEAD: `0c25821f407bf0d528fe9bedacf892d5187430d7`

Lifecycle: `addyosmani/agent-skills` release `0.6.7`, `using-agent-skills` -> brownfield `context-engineering` first. This document is read-only architecture characterization. It does not authorize serializer code, recurrent reasoning code, Granite integration, training, Step-1 work, Frankie/provider calls, or production launch.

## Purpose

Record the current executable BOSS architecture and distinguish:

- implemented contract,
- preserved baseline behavior,
- explicit non-features,
- experimental seams,
- unresolved questions that must be specified before new behavior is added.

The central brownfield rule is to characterize before changing. Existing oddities are not treated as defects merely because a new design might prefer something else.

## Authority inspected in this pass

Primary executable/current sources:

- `research/kalshi/frankie_boss/causal_packet.py`
- `research/kalshi/frankie_boss/databento_adapter.py`
- `research/kalshi/frankie_boss/trunk.py`
- `research/kalshi/frankie_boss/teacher.py`
- `research/kalshi/frankie_boss/decision_contract.py`
- `research/kalshi/frankie_boss/frankie_contract.py`
- `research/kalshi/frankie_boss/tests/test_causal_packet.py`
- `research/kalshi/frankie_boss/tests/test_trunk.py`
- `research/kalshi/frankie_boss/tests/test_seam.py`

Preserved supplied-source authority:

- `research/kalshi/frankie_boss/provenance/supplied_checkpoint/trunk(1).py`
- `research/kalshi/frankie_boss/provenance/supplied_checkpoint/trunk(2).py`
- preserved supplied tests and source variants listed by the provenance bundle

Governing context:

- `research/kalshi/FRANKIE_BOSS_SOL_REPLACEMENT_HANDOFF_20260824.md`
- `research/kalshi/frankie_boss/README.md`
- `research/kalshi/frankie_boss/FRANKIE_BOSS_PREUSE_PROVENANCE_20260828.md`
- `research/refrag/README.md`
- `tasks/plan.md`
- `tasks/todo.md`

## Current data and audit boundary

### CausalPacket is the audit object

`CausalPacket` is deterministic and point-in-time. The packet contains:

- `entity`,
- `as_of`,
- versioned derived `features`,
- source `watermarks`,
- touched-source `provenance`,
- `record_counts`,
- degradation/defect state,
- a full stamp including code, feature-spec, model, calibrator, schema, and float-canonicalization versions.

Packet bytes are canonicalized before SHA-256 hashing. Float canonicalization is part of the packet contract. Same immutable ledger state + same `as_of` is intended to yield byte-identical packet identity.

### Causal clock

The Databento adapter declares `ts_recv_ns` as the sole causal availability clock. `ts_event_ns` is exchange event time. `ts_in_delta_ns` is provenance/latency evidence only. Future receive-time rows are excluded; clock inversions are quarantined and surfaced rather than silently admitted.

### Important boundary finding for future Granite work

The existing packet is an audit/provenance object, not yet a declared Granite text schema and not itself the full typed tensor sequence consumed by `Trunk`. A future Granite serializer must not be assumed to attach merely because `CausalPacket` is deterministic. The exact semantic bridge from packet/features and typed model inputs to Granite-visible state remains a new interface that must be specified and tested separately.

This distinction is required to avoid conflating serializer failure with reasoning-transfer failure.

## Current BOSS trunk

### Inputs

The trunk accepts explicit typed streams:

- numeric tensor `(B,T,n_numeric)`,
- categorical tensor `(B,T,n_cat)`,
- venue ids `(B,T)`,
- instrument ids `(B,T)`,
- parent ancestry indices `(B,T)`,
- optional named-registry QSV tensor `(B,T,qsv_dim)`,
- optional QSV availability mask.

QSV remains a separate stream rather than being folded into generic numerics. `qsv_dim` is governed by `len(QSV_FEATURE_REGISTRY)`. QSV is dormant by default and exactly ablatable when enabled.

### One shared temporal graph branch

There is exactly one `TemporalGraphBranch` instance. It adds venue and instrument embeddings and one parent-message path. It exists to preserve order ancestry/structure that the sequence view loses; it is not a second or third independent graph model.

The graph path can carry information from outside the local attention window through ancestry. Therefore `window` bounds only the attention path, not the full model receptive field.

### Fixed-depth sequence stack

After encoding and the single graph pass, `Trunk.represent` executes `n_layers` fixed layers. Per layer:

1. causal sliding-window attention,
2. optional `GatedDeltaCell`,
3. residual feed-forward update `h = h + ff[i](h)`.

This layer count is configuration-controlled fixed depth. There is no data-dependent whole-model reasoning-depth loop in the current executable trunk.

### GatedDeltaCell recurrence is temporal memory, not reasoning-depth recurrence

`GatedDeltaCell` contains an explicit recurrent state `S` updated across sequence time steps. It is causal temporal memory over the input sequence.

This must not be mislabeled as the missing BOSS reasoning loop. The preserved trunk source explicitly distinguishes it from `recurrent-depth reasoning` and says shared-weight recurrent reasoning comes only after the fixed-depth baseline proves itself.

### Explicitly absent from the fixed-depth baseline

The preserved supplied trunk variants state that the following are not part of the baseline:

- recurrent-depth reasoning,
- Mamba-3 complex-state,
- reservoir ensemble.

The same source says the baseline must remain clean because a baseline that already contains the experiment cannot prove the experiment.

## Existing state-update and residual authority

Implemented residual/state behavior is currently local to the fixed-depth architecture:

- field streams are summed then layer-normalized,
- graph returns a normalized residual against its input,
- sliding attention returns `norm(x + out(attention))`,
- gated delta memory returns `norm(x + out(memory_read))`,
- feed-forward update is an explicit outer residual `h = h + ff[i](h)`.

No separate recurrent-reasoning state object, scratch state, ponder state, loop counter state, or recurrence-carried graph state currently exists.

## Masking authority

### Attention mask

Sliding attention is strictly causal and window-limited on its own path.

### QSV mask

QSV can be unavailable per time step. Masked/unavailable values are intended to contribute exactly zero; present non-finite values fail closed; complete QSV ablation makes the stream inert.

### No reasoning-depth mask yet

There is no implemented per-example active-loop mask, halted-example mask, variable-depth batch mask, or recurrent-reasoning attention mask because recurrent-depth reasoning does not yet exist.

## Training versus inference

### Inference/eval

The fixed-depth trunk is deterministic in `eval()` by construction: no dropout, no sampling, no data-dependent control flow. Existing tests require identical repeated eval outputs and no future leakage.

### Current teacher training harness

`teacher.py` trains the fixed-depth trunk plus an auxiliary `TeacherHead` under mandatory controlled arms:

- `none`,
- `plain_aux`,
- `shuffled`,
- `random`,
- `dipole`.

The harness refuses partial control sets. Multiple seeds are expected by default. The dipole hypothesis passes only if it beats every control and exceeds control spread; otherwise the result is a KILL/clean negative to preserve.

### No train/inference recurrence contract yet

There is currently no contract for:

- teacher-forced versus free recurrent steps,
- recurrence unrolling during training,
- truncated/backprop-through-reasoning depth,
- loop-state detachment,
- variable depth in a batch,
- inference-only additional depth,
- recurrence regularization,
- learned stopping loss.

Those are missing specification, not implicit defaults.

## Stopping/halting authority

### Existing decision abstention is not reasoning halting

`decision_contract.py` and `frankie_contract.py` contain deterministic decision/abstention behavior after head outputs exist. They validate contracts, packet defects, evidence pointers, contradiction/confidence rules in the generic decision layer, and the BLD-1 projection.

That is output disposition. It is not an internal recurrent-compute halt controller.

### BLD-1 reasoning text is not a loop state

The BLD-1 `reasoning` field is explicitly free text and excluded from the deterministic payload digest. A changed wording can change `reasoning_digest` without changing deterministic forecast identity.

Therefore the current free-text `reasoning` field cannot be treated as authoritative hidden reasoning state or recurrence state.

### Missing reasoning-halting contract

No current BOSS executable authority defines:

- maximum reasoning depth,
- minimum reasoning depth,
- fixed versus adaptive recurrence,
- ACT/Ponder-style probability,
- confidence exit,
- representation-convergence exit,
- contradiction exit,
- compute penalty,
- no-halt safety fallback,
- training target for halt,
- whether abstention and compute halting are coupled or independent.

These must be decided by a future spec/experiment rather than inferred.

## Head and public-contract boundary

The trunk currently exposes internal typed heads including:

- `p_up`,
- `size`,
- `regime_logits`,
- `contradiction`,
- `sigma`,
- `evidence_scores`.

These are not the public Frankie contract.

The BLD-1 seam deliberately allows only four learned quantities to cross after semantic mapping:

- `session_net_usd` -> `guessed_net_usd`,
- `overnight_gap_usd` -> `overnight_gap_usd`,
- `session_path_p50_curve` -> `path_p50_curve`,
- `confidence_label` -> `confidence`.

Other learned values remain internal until their destination, chronology, units, and semantics are explicitly specified and tested.

A valid forecast-backed `ABSTAIN` may preserve forecast values; complete zero safety abstention is for malformed/unavailable forecast state. No numeric confidence threshold is invented at the BLD-1 seam.

## Current ablation/control authority

Existing controlled mechanisms include:

- QSV dormant-by-default switch,
- exact QSV ablation,
- optional gated-delta-memory switch,
- mandatory teacher controls (`none`, `plain_aux`, `shuffled`, `random`, `dipole`),
- fixed-depth trunk as the baseline against any later recurrent-depth experiment.

No Granite arm exists. No adaptive-depth arm exists. No recurrent-depth arm exists.

## Granite 4.2 candidate status

Granite 4.2 is **not adopted** by this inventory. It remains a research candidate.

The current hypothesis is narrower than replacing BOSS or Step-1: Granite 4.2 8B may later be tested as a frozen reasoning teacher/control to improve sample efficiency when only a bounded amount of expensive full-MBO training data is available.

Required preconditions identified before any Granite distillation plan:

1. The BOSS-to-Granite serialization/interface must be a separately tested experiment.
2. A Granite null must be distinguishable from serializer information loss.
3. Granite process labels must be validated before distillation.
4. Contradiction/evidence-conflict targets should be tested before market halting/abstention targets.
5. A native adaptive-depth BOSS control must exist so adaptive computation is not confounded with Granite supervision.
6. Shuffled Granite labels must be a control.
7. A market-specific-field-ablated teacher-input control must preserve serializer shape while removing market information.
8. The primary learning-runway metric should be horizontal sample-efficiency shift: amount of expensive MBO training data needed to reach a predeclared held-out performance level, with uncertainty across seeds and time-disjoint holdout.

No item above is an implementation directive yet.

## Step-1 dependency status

No new Step-1 run is required to finish Brownfield Phase 1 or to test a future serializer's mechanical properties with synthetic/fixture typed states.

Real Step-1 information becomes necessary later for market-semantic validation. At that stage, begin with the smallest frozen representative sample sufficient to validate the interface and teacher labels. Do not use the Granite investigation as justification for another large MBO census.

## Brownfield findings: implemented versus missing

| Concern | Current authority | Status |
|---|---|---|
| causal availability | receive-time packet/adapter contract | implemented/frozen |
| packet identity/provenance | canonical `CausalPacket` + hash/stamp | implemented |
| typed tensor inputs | `Trunk.represent` signature/config | implemented |
| QSV ownership/mask/ablation | ReFRAG registry + `FieldEncoder` | implemented/frozen |
| temporal graph | one `TemporalGraphBranch` | implemented/frozen |
| temporal memory | `GatedDeltaCell` state across T | implemented |
| fixed representation depth | `n_layers` | implemented baseline |
| whole-representation recurrence | none | explicitly deferred |
| recurrent loop state | none | missing spec |
| adaptive/fixed reasoning depth | none | missing spec |
| compute halting | none | missing spec |
| recurrence batch mask | none | missing spec |
| recurrence train/inference difference | none | missing spec |
| recurrent graph interaction | none | missing spec |
| recurrent ablation/control | fixed-depth baseline only | missing experiment contract |
| output abstention | decision/BLD contracts | implemented, distinct from compute halting |
| Granite serialization | none | new interface candidate |
| Granite teacher validity | none | new experiment candidate |

## Boundaries for the next phase

Before any serializer or recurrent-reasoning code:

- do not modify the existing trunk merely to make a future design convenient,
- do not reinterpret temporal `GatedDeltaCell` memory as reasoning-depth recurrence,
- do not couple BLD-1 abstention to a future compute-halt decision without a separate contract,
- do not feed Granite undocumented ad-hoc prose and call the result a BOSS-state experiment,
- do not alter the single temporal graph branch,
- do not leak additional learned heads through BLD-1,
- do not require full-history Step-1 data for interface tests,
- do not change Frankie/provider/core seams.

## Remaining Brownfield Phase-1 work before specification

1. Inspect the preserved chronological architecture screenshots/source notes for any intended recurrent-loop contract that is not represented in executable files.
2. Perform a doubt-driven adversarial review of this inventory's non-trivial claims, especially:
   - `GatedDeltaCell` recurrence is temporal rather than reasoning-depth recurrence;
   - output abstention is distinct from compute halting;
   - no current executable loop/halting authority exists;
   - the packet is not automatically a sufficient Granite state serialization.
3. Reconcile any findings and record corrections additively.
4. Only then enter the new-feature spec phase for the smallest bounded next capability.
