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

## Microstructure and confidence

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

`validate_committed_replay_metrics()` validates the already-frozen post-reveal metrics without rerunning the blind experiment. It fails if any of these committed facts drift:

- classifier SHA;
- A count 831 fast-collapse / 785 persistent;
- four held-out days are present;
- persistent > fast-collapse at 3t/5t/8t/13t on every held-out day;
- blind predictions retained the frozen reveal duration baselines;
- classifier was not refit after reveal;
- frozen artifact reports no permanent Frankie brain/schema mutation.

The raw held-out prediction packet is not committed on this branch, so V0 does not fabricate a second blind run. The committed blind metrics are the replay-validation boundary.

## Do-not-learn boundary

The finished blind scratch curve generator is not imported or reused. Its hand-authored curve shape and curve scores are not part of the clock. V0 promotes lifespan/runway only.

## Tests

`tests/test_ng_exhaustion_runway_clock.py` covers checksum drift, 61D normalization/distance, the +60s legal gate, monotonic/nonnegative countdown, fail-closed data availability, microstructure confidence-only behavior, B/C boundaries, deterministic output, and frozen replay facts.

## Permanent Frankie protection

This V0 adds an isolated module, renderer, tests, and documentation only. It does not modify permanent brain/schema/roles/plays/datapoints/spawn.py/workflow. A later deliberate brain-update step may merge only the separately curated validated lessons.
