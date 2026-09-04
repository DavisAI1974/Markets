# Dipole teacher test and promotion plan

Date: 2026-09-04

Status: Brownfield characterization and required test plan. The current harness is not yet a production teacher.

## What the dipole teacher actually is

`research/kalshi/frankie_boss/teacher.py` implements an auxiliary representation-learning experiment.

The BOSS produces hidden states. A `TeacherHead` projects those hidden states into a target space. During training, the task loss is combined with an auxiliary mean-squared-error loss against one of five target/control arms:

- `none`;
- `plain_aux`;
- `shuffled`;
- `random`;
- `dipole`.

The intended scientific claim is narrow: OD/dipole geometry might provide useful intermediate supervision beyond the primary label. It is not an inference-time teacher model, not a market-data feed, not Granite, and not execution logic.

The current verdict function deliberately returns KILL unless the dipole arm beats every control and its gain exceeds the spread among controls. That falsification posture is correct and should be preserved.

## What is already functional

REPO FACTS:

- `TeacherHead` is executable PyTorch code.
- The harness refuses an arm list missing any of the five named controls.
- Multiple seeds are supported and default to three.
- Task and auxiliary losses are recorded per arm and seed.
- A verdict cannot render without at least one result from every arm.
- Tests cover missing-arm rejection, verdict behavior, and a synthetic end-to-end smoke run.
- ReFRAG supplies a named QSV registry and the trunk can enable, mask, or exactly ablate its QSV projection.

That is enough to call the harness built. It is not enough to call the market experiment tested.

## Blocking findings from brownfield inspection

### P0: no governed production dipole target schema

The synthetic test uses a four-wide random tensor named `dipole`. The production target dimension, field names, units, ordering, time alignment, normalization, presence mask, source identity, and version are not governed by a typed contract.

Until a `DIPOLE_TEACHER_SCHEMA_V1` exists, two runs can use different meanings behind the same tensor shape.

### P0: `plain_aux` implementation does not match its description

The file describes `plain_aux` as a random-but-fixed projection of inputs. The implementation computes a random matrix product and then multiplies it by `0.0`, leaving the time-mean of the dipole target expanded over the sequence.

This means the named control is neither the documented fixed random input projection nor independent of the real dipole target. The mismatch must be characterized with a failing test and corrected before a result-bearing run. Historical smoke tests do not catch it.

### P0: the real raw-MBO-to-training-batch seam is missing

There is no accepted builder that proves the numeric, categorical, venue, instrument, parent, QSV, label, and dipole tensors are all derived from the same hash-bound causal prefix.

Hand-building a JSON or tensor batch is not acceptable. It would break the answer wall and provenance chain.

### P0: QSV presence is not passed through the training harness

The trunk supports `qsv_mask`, but `run_experiment()` passes only `b.get("qsv")` into `represent()`. A result-bearing training path must carry the QSV presence mask and preserve the distinction among present zero, missing, and ablated.

### P0: the primary task is too narrow for promotion

The harness trains and validates only binary `p_up` cross-entropy. Frankie's public contract includes net move, overnight gap, path curve, confidence, and disposition. A dipole result cannot be promoted to the full BLD-1 system solely because one binary validation loss moved.

### P1: shuffled control can be ineffective

`torch.randperm` can return the identity permutation, and a batch of size one cannot be shuffled. A control advertised as correspondence-destroying must verify that correspondence was actually destroyed, or shuffle across a larger frozen example index rather than only within a small batch.

### P1: device-specific random generation needs proof

The harness creates a CPU generator and passes it to target construction on the dipole tensor's device. Real GPU execution needs a device-compatible deterministic RNG contract and a test, not an assumption based on CPU smoke tests.

### P1: statistical verdict is descriptive, not inferential

Mean loss and control spread across whatever results exist do not provide a confidence interval, paired-seed uncertainty, regime stability, or a minimum practically important effect. The current verdict can remain an early safety check but cannot be the only promotion criterion.

### P1: lifecycle and recovery are incomplete

The teacher harness does not by itself freeze data splits, checkpoint optimizer/model state, resume exactly, bind environment identities, or write an immutable final lock. Those responsibilities must use the existing benchmark checkpoint and raw-MBO manifest contracts.

## Required dipole target contract

Before training, define and test a closed target object with at least:

| Field | Requirement |
|---|---|
| `schema_version` | Exact version string |
| `source_manifest_hash` | Binds raw DBN roster |
| `source_prefix_hash` | Binds causal event-group prefix |
| `as_of_ts_recv_ns` | Sole availability cutoff |
| `registry_id` | Exact OD/ReFRAG operator registry identity |
| `target_names` | Ordered semantic names, never width-only |
| `target_units` | Unit for every target |
| `target_values` | Finite values only when present |
| `target_states` | Present, missing, invalid, or ablated |
| `target_mask` | Must agree exactly with states |
| `normalizer_id` | Fit only on allowed training data |
| `builder_code_sha` | Exact implementation identity |
| `target_hash` | Canonical hash over all deterministic content |

The target must be derivable at or before `as_of_ts_recv_ns`. It cannot use a future order action, realized daily outcome, future Step-1 finding, or another arm's prediction.

## Two different experiment matrices

Do not conflate the system-level BOSS matrix with the dipole auxiliary controls.

### System-level eight locks

The accepted raw-MBO benchmark requires:

- A-clean;
- A-memory;
- B0-clean;
- B0-memory;
- B1-clean;
- B1-memory;
- B2-clean;
- B2-memory.

These answer controller, native recurrence, Granite, and memory questions.

### Dipole auxiliary matrix inside a native training comparison

The five current teacher arms answer whether aligned dipole targets provide more than generic auxiliary regularization. To isolate QSV and dipole effects, add a predeclared factor comparison rather than assuming QSV is constant:

| Arm | QSV | Auxiliary target | Purpose |
|---|---|---|---|
| D0 | Off or exactly ablated | None | Clean native floor |
| D1 | On | None | QSV contribution without auxiliary loss |
| D2 | On | Corrected fixed plain auxiliary | Extra learnable-gradient control |
| D3 | On | Shuffled real dipole | Marginal-preserving correspondence control |
| D4 | On | Random | Dense-noise control |
| D5 | On | Aligned dipole | Hypothesis arm |

If B1 recurrence is in scope, D0-D5 must all use the same B1 architecture. If Granite is in scope, it belongs in a separate factor or later teacher experiment. Do not change recurrence, Granite supervision, and dipole supervision in one comparison.

## Initial four-date plan

### Stage 0: code and contract tests, no market claim

- Add characterization tests for current control construction.
- Add a failing test proving `plain_aux` does not implement its documented behavior.
- Specify and test the dipole target schema.
- Build the raw-MBO causal batch adapter behind a closed allowlist.
- Prove continuous replay equals checkpoint/restore replay.
- Prove QSV masks and dipole masks reach the model.
- Prove every arm uses identical initialization, batches, optimizer settings, and example order for a paired seed.

### October 1: development and fitting only

- Reconstruct native raw MBO event by event in `ts_recv_ns` order.
- Validate packet to typed state to dipole target identity.
- Fit normalization only on the declared October 1 training partition.
- Run small capacity and learning-rate checks if predeclared.
- Verify every control actually differs as intended.
- Exercise checkpoint/resume.

October 1 is not part of the headline score.

### October 3: warmup validation only

- Freeze hyperparameters before reading its validation metrics.
- Validate out-of-day causal behavior and target coverage.
- Run the full D0-D5 matrix across at least five paired seeds for stability estimation.
- Measure calibration, BLD-relevant heads, latency, memory, and defects.
- Do not rewrite or re-run the frozen Sunday A-memory principal artifact.

October 3 is not part of the headline score after use for development.

### October 4 and October 5: paired blind evaluation

- Freeze code, data hashes, target schema, normalizer, model architecture, seeds, thresholds, and all arm identities first.
- Run every required lock independently.
- Prevent any arm from seeing another current arm's output.
- Preserve negative, null, KILL, abstain, malformed, and disagreement results.
- Freeze and hash all outputs before the single reveal.
- Score both days together and separately so one day cannot hide the other.

These two days are enough for interface failure detection and an initial paired comparison. They are not enough for a stable production promotion.

## Metrics

Primary metric must be predeclared and reflect the actual BLD objective. Recommended hierarchy:

1. proper scoring rule for the exact prediction target, such as Brier or log loss where probabilistic;
2. calibration error and reliability by confidence band;
3. absolute/quantile loss for net, gap, and path outputs;
4. selective risk versus coverage for abstention;
5. contradiction/evidence-consistency accuracy on objectively labeled probes;
6. latency, peak memory, and failure rate;
7. economic simulation net of commissions, exchange fees, spread, and slippage as a secondary metric, never the sole training selector.

Report:

- every seed;
- paired seed differences;
- mean, median, and distribution;
- confidence interval or a justified resampling interval at the event/day level;
- separate results per date and regime;
- control identities and sample counts;
- missing/invalid target rates;
- compute and wall-time receipts.

## Promotion rule

The dipole hypothesis advances beyond research only if all are true:

1. D5 beats D0 and D1, proving value beyond no-QSV/no-aux and QSV-only baselines.
2. D5 beats D2, D3, and D4 on the predeclared primary metric.
3. The paired improvement exceeds the predeclared practical margin and its uncertainty interval excludes no improvement.
4. The direction of improvement is consistent across October 4 and October 5 rather than entirely caused by one day.
5. Calibration and critical BLD heads do not materially degrade.
6. The benefit survives a market-field ablation that should remove relevant information.
7. The exact result reproduces from checkpoint/resume.
8. No causal, answer-wall, schema, or provenance defect occurs.
9. A later time-disjoint forward-live shadow test reproduces the effect.

If any required control performs as well as D5, record KILL for the claim that aligned dipole geometry supplied unique structure. The dipole data may still be useful for another purpose, but this experiment would not have proven it.

## Minimum functional deliverables

To call the dipole teacher tested and functional, the later code tranche must deliver:

- `DIPOLE_TEACHER_SCHEMA_V1` and parser/validator;
- causal raw-MBO target builder;
- exact target and QSV mask propagation;
- corrected and tested control construction;
- time-disjoint dataset manifest;
- restart-safe trainer state;
- closed metrics and result schema;
- D0-D5 runner;
- immutable per-arm locks and hashes;
- single-reveal scorer;
- forward-live shadow plan;
- documentation of every null, negative, and failure.

Until those exist, `teacher.py` is a serious experimental scaffold, not a production capability.
