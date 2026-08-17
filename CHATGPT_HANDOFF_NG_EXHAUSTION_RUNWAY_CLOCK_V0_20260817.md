# ChatGPT Handoff — NG Exhaustion Runway Clock V0

Status: PROVEN ISOLATED V0. STOP BEFORE ANY PERMANENT FRANKIE MERGE.

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
Takeover base: `4954e9f178569f53623e9326be5dc3ac91caaca1`
Implementation proof head before this handoff: `d76c7ea0d21dc6c13fec6611fbec946550aac75f`

## What was built

The isolated deterministic NG exhaustion runway clock is implemented without modifying permanent Frankie.

Added implementation files:

- `research/ng_exhaustion_runway_clock.py`
- `research/ng_exhaustion_replay_proof.py`
- `research/render_ng_exhaustion_runway_clock.py`
- `tests/test_ng_exhaustion_runway_clock.py`
- `tests/test_ng_exhaustion_replay_proof.py`
- `research/NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`

The branch diff from the takeover base through the implementation proof head contains only those six added files. Existing permanent brain/schema/roles/plays/datapoints/spawn.py/workflow files were not edited.

## Frozen classifier contract

Classifier artifact:
`research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`

Required exact SHA-256:
`698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`

V0 behavior:

- Family A remains `A_STATE_PENDING` before +60 seconds.
- At/after +60 seconds, A uses the exact frozen 61-dimensional normalized roll-20 dipole classifier.
- Normalize the t=0..+60 values by the t=0 value.
- Use Euclidean nearest frozen centroid.
- Cluster 0 = `A-fast-collapse`.
- Cluster 1 = `A-persistent`.
- Any classifier checksum/schema/input drift fails closed.
- No partial-centroid/early classifier was invented.

## Frozen runway baselines

Operational reveal baselines remain unchanged:

- A-fast-collapse: 3t=358s, 5t=993s, 8t=1802s, 13t=4386s
- A-persistent: 3t=700s, 5t=1802s, 8t=3455s, 13t=6836s

V0 countdown:

`remaining_s = max(0, baseline_total_s - elapsed_since_t0_s)`

No hidden nonlinear duration weights were added.

B remains unresolved with only the specified low-confidence fallback durations. C remains a provisional low/moderate-confidence scale-transition fallback. Neither is promoted beyond the frozen handoff.

## Microstructure

Microstructure remains confidence-only. It never changes state identity or runway seconds.

V0 intentionally avoids invented numeric confidence probabilities. It reports qualitative modifiers only:

- same_side = stronger
- mixed = neutral
- opposite = weaker
- unavailable = degraded_unavailable

An unavailable event clock fails closed. Missing A-classifier data blocks the A state/runway. Missing microstructure forces `unavailable` rather than allowing stale confirmation.

## Two-sided blind proof

### Pre-reveal freeze gate

`research/ng_exhaustion_replay_proof.py` validates the committed blind freeze manifest without regenerating the blind predictions.

It verifies:

- frozen A classifier SHA;
- A-fast-collapse count = 831;
- A-persistent count = 785;
- Family A total = 1616;
- prediction total = 1711;
- causal t0 anchor was served;
- `future_price_served_to_model=false`;
- `outcome_accessed_before_freeze=false`;
- all four held-out shard days;
- all four frozen compressed shard SHA-256 values;
- shard record total = 1711;
- tampering fails closed.

### Post-reveal replay gate

`validate_committed_replay_metrics()` in `research/ng_exhaustion_runway_clock.py` validates the committed post-reveal metrics without retuning.

It verifies:

- the classifier was not refit after reveal;
- the 831 / 785 split remains unchanged;
- persistent > fast-collapse at 3t/5t/8t/13t on all four held-out days;
- frozen reveal baselines were preserved in the blind predictions rather than replaced with held-out medians;
- the frozen experiment reports no permanent Frankie brain/schema mutation.

The blind experiment was not redone.

## Test proof

Local deterministic proof suite:

`python -m unittest -v tests.test_ng_exhaustion_runway_clock tests.test_ng_exhaustion_replay_proof`

Result: 18/18 tests passed.

The suite covers:

- exact classifier SHA;
- checksum drift fail-closed;
- exact 61D normalization/distance;
- correct 121-field `[60:]` slice;
- no A state before +60s;
- exact frozen reveal baselines;
- monotonic/nonnegative countdown;
- confidence-only microstructure;
- fail-closed data gaps;
- B unresolved/C provisional boundaries;
- deterministic repeated output;
- pre-reveal freeze manifest/shard proof;
- post-reveal A counts/order/baseline proof.

No GitHub CI status checks are configured/reported for this branch, so the proof statement above is the local deterministic test result, not a claim about Actions CI.

## Render proof

Renderer:
`research/render_ng_exhaustion_runway_clock.py`

Validation fixture used:

- state: A-persistent
- elapsed: 300s
- microstructure: same_side

Expected remaining runway:

- 3t: 400s
- 5t: 1502s
- 8t: 3155s
- 13t: 6536s

The render explicitly reports `future_price_accessed=false` and keeps direction separate.

## Do not learn / do not do

- Do not import or reuse `research/ng_exhaustion_frankie_blind_predict_20260816.py` as a Frankie curve template.
- Do not learn its hand-authored curve coefficients or curve scores.
- Do not promote exact price-path prediction from this experiment.
- Do not promote B locality.
- Do not retune V0 duration baselines to held-out medians.
- Do not redo the blind experiment.
- Do not modify permanent Frankie from this branch without a separate explicit approval step.

## Current stop point

The isolated V0 clock is built and validated against the frozen pre-reveal and post-reveal experiment artifacts. It is not yet wired into permanent Frankie or a live ingestion/worker pool.

Before deciding whether multiple ordinary compute workers are needed, measure the deterministic engine over a larger historical/live batch. Parallel workers should be added only if throughput proves to be the bottleneck; do not create AI exhaustion agents for deterministic math.

Permanent Frankie remains untouched. The separately curated brain lesson proposal can be merged only in a deliberate later step after explicit approval; never bulk-merge the experiment.
