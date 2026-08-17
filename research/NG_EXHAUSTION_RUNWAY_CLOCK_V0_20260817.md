# NG Exhaustion Runway Clock V0

Status: isolated deterministic implementation. Permanent Frankie is intentionally untouched.

## Boundary

This module estimates structural lifespan/runway. It does not forecast direction and does not forecast an exact future price path. The intended later architecture is:

`Frankie direction/magnitude + exhaustion runway clock -> hold-length / continuation / failure overlay`

V0 does not require or access future price.

## Frozen Family A contract

The clock loads `FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json` only if its exact SHA-256 is:

`698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`

Classifier behavior is frozen:

- input: 61 roll-20 dipole samples for t=0..+60 seconds;
- normalization: divide all 61 values by the t=0 value;
- distance: Euclidean to the two frozen centroids;
- raw cluster 0 = `A-fast-collapse`;
- raw cluster 1 = `A-persistent`;
- no refit, extra scaling, custom threshold, or alternate tie rule.

Before +60s, A state is `A_STATE_PENDING` and no A runway seconds are emitted. At/after +60s, an invalid or unavailable classifier window fails closed as `A_STATE_UNAVAILABLE` with unavailable confidence and no runway seconds.

## Frozen reveal runway baselines

Operational baselines remain reveal values, not held-out medians:

| state | 3t | 5t | 8t | 13t |
|---|---:|---:|---:|---:|
| A-fast-collapse | 358s | 993s | 1802s | 4386s |
| A-persistent | 700s | 1802s | 3455s | 6836s |

V0 rule for every scale:

`remaining_s = max(0, baseline_total_s - elapsed_since_t0_s)`

There are no nonlinear duration weights in V0.

## Microstructure

Microstructure is confidence-only and can never change family/state identity or runway seconds. V0 deliberately uses qualitative confidence because the experiment did not freeze calibrated numeric confidence weights:

- same_side: `stronger`;
- mixed: `neutral`;
- opposite: `weaker`;
- unavailable: `degraded_unavailable`.

Family A base confidence is `validated`, B is `low`, and C is `low_to_moderate`. No numeric probability or learned seconds mapping is invented in V0.

Data-availability flags are authoritative: an unavailable event clock fails closed, an unavailable A classifier window blocks A state/runway, and an unavailable microstructure feed forces the microstructure state to `unavailable` rather than accepting a stale confirmation badge.

## B and C

B remains `B_UNRESOLVED` with a low-confidence fallback duration set (353 / 995 / 1615 / 4543 seconds). The failed B-locality hypothesis is not promoted.

C remains `C_SCALE_TRANSITION_PROVISIONAL` with a low/moderate-confidence fallback duration set (377 / 1159 / 1713 / 4320 seconds). V0 does not invent a scalar C transition threshold.

## Replay proof

V0 validates both immutable sides of the finished blind experiment without regenerating predictions or retuning anything.

`validate_blind_freeze_manifest()` validates the pre-reveal freeze manifest and fails if any of these facts drift:

- exact classifier SHA;
- A state counts 831 fast-collapse / 785 persistent;
- Family A total 1616 and prediction total 1711;
- causal t0 anchor was served;
- future price was not served to the model;
- outcome was not accessed before freeze;
- the four frozen prediction-shard days, record total, or compressed SHA-256 values drift.

`validate_committed_replay_metrics()` independently validates the post-reveal metrics and fails if any of these facts drift:

- classifier SHA or post-reveal refit status;
- the same 831 / 785 A counts;
- persistent > fast-collapse at 3t/5t/8t/13t on every one of the four held-out days;
- blind predictions retained the frozen reveal duration baselines;
- frozen artifact reports no permanent Frankie brain/schema mutation.

The pre-reveal freeze manifest and four frozen prediction shards are committed in the repository. V0 validates their immutable manifest metadata/hashes plus the post-reveal metrics; it does not redo the blind experiment.

## Do-not-learn boundary

The finished blind scratch curve generator is not imported or reused. Its hand-authored curve shape and curve scores are not part of the clock. V0 promotes lifespan/runway only.

## Tests

`tests/test_ng_exhaustion_runway_clock.py` covers checksum drift, 61D normalization/distance, the +60s legal gate, monotonic/nonnegative countdown, fail-closed data availability, microstructure confidence-only behavior, B/C boundaries, deterministic output, and post-reveal replay facts.

`tests/test_ng_exhaustion_replay_proof.py` separately validates the immutable pre-reveal freeze manifest, all four shard hashes/record totals, and fail-closed tamper detection.

## Permanent Frankie protection

This V0 adds isolated modules, renderer, tests, and documentation only. It does not modify permanent brain/schema/roles/plays/datapoints/spawn.py/workflow. A later deliberate brain-update step may merge only the separately curated validated lessons.
