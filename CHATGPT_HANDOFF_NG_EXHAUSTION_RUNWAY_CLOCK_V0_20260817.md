# ChatGPT Handoff — NG Exhaustion Runway Clock V0

Status: PROVEN ISOLATED V0 + LARGE-BATCH PASS. STOP BEFORE ANY PERMANENT FRANKIE MERGE.

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
Takeover base: `4954e9f178569f53623e9326be5dc3ac91caaca1`
Implementation proof head before original handoff: `d76c7ea0d21dc6c13fec6611fbec946550aac75f`

## What was built

The isolated deterministic NG exhaustion runway clock is implemented without modifying permanent Frankie.

Added implementation/proof files:

- `research/ng_exhaustion_runway_clock.py`
- `research/ng_exhaustion_replay_proof.py`
- `research/render_ng_exhaustion_runway_clock.py`
- `tests/test_ng_exhaustion_runway_clock.py`
- `tests/test_ng_exhaustion_replay_proof.py`
- `research/NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`
- `research/ng_exhaustion_runway_batch_benchmark.py`
- `research/NG_EXHAUSTION_RUNWAY_CLOCK_LARGE_BATCH_RESULTS_20260817.json`
- `research/NG_EXHAUSTION_RUNWAY_CLOCK_LARGE_BATCH_20260817.md`

Existing permanent brain/schema/roles/plays/datapoints/spawn.py/workflow files were not edited.

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

Result: 18/18 tests passed after the large-batch work.

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

## Large-batch proof

The larger batch uses the exact original frozen blind-input GitHub Actions artifact, not a reconstructed sample:

- artifact ID: `9274443976`
- artifact SHA-256: `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`
- records: 1711
- Family A: 1616
- Family B: 35
- Family C: 60
- days: 20250717=420, 20250923=446, 20250930=428, 20251001=417
- `future_price_or_price_bearing_window_served=false`
- blind outcome-wall scan: PASS

Across all 1616 A records, the clock reproduces the pre-frozen assignment exactly:

- A-fast-collapse = 831
- A-persistent = 785
- invalid A windows = 0
- label mismatches = 0
- centroid-distance mismatches = 0

The batch contract sweep checks 8 elapsed checkpoints per record (`0, 30, 59.999, 60, 300, 900, 1802, 7200`):

- timeline outputs checked = 13,688
- pre-60 A gate failures = 0
- confirmed A mismatches = 0
- negative runway values = 0
- countdown monotonicity failures = 0
- future-price-access flags = 0
- all 1,616 A records fail closed when the legal +60 classifier window is removed
- 5,133 microstructure confidence variants produced 0 changes to runway seconds
- missing event clock fails closed

Timed sweeps deliberately use microstructure `unavailable`; no scratch support-to-confidence mapping was promoted into V0.

### Throughput result

Measured on the available Python 3.13.5 container (5 logical CPUs reported):

- blind records JSON size = 22,104,694 bytes
- parse manifest + records = ~411.4 ms
- one +60 checkpoint across all 1,711 records = ~20.62 ms median (~82,994 updates/s)
- eight-checkpoint / 13,688-update sweep = ~121.03 ms median (~113,095 updates/s)
- confirmed-A call latency = ~11.50 us median / 13.12 us p95 / 28.84 us p99
- 2 warm processes = ~220,620 updates/s
- 4 warm processes = ~231,607 updates/s

Parallel workers improve raw compute throughput, but the single deterministic process is already far faster than this batch requires. Parsing/transport costs materially more than the clock math.

### Worker decision

Do **not** add multiple exhaustion workers now. V0 should use one ordinary deterministic clock worker/service. The measured clock math is not the bottleneck.

If future live instrumentation shows actual queue backlog or demand approaching single-process capacity, a persistent 2-4 process pool is an available throughput optimization. Do not create AI exhaustion agents and do not retune the frozen classifier or runway durations to justify scaling.

## Do not learn / do not do

- Do not import or reuse `research/ng_exhaustion_frankie_blind_predict_20260816.py` as a Frankie curve template.
- Do not learn its hand-authored curve coefficients or curve scores.
- Do not promote exact price-path prediction from this experiment.
- Do not promote B locality.
- Do not retune V0 duration baselines to held-out medians.
- Do not redo the blind experiment.
- Do not modify permanent Frankie from this branch without a separate explicit approval step.

## Current stop point

The isolated V0 clock is built, proven against the frozen pre-reveal/post-reveal artifacts, and now stress-tested over the entire original 1,711-record blind input corpus. The worker question is resolved for V0: **one deterministic worker is sufficient**.

It is still not wired into permanent Frankie or a live ingestion path. The next deliberate decision is whether to wire the isolated clock into a live/near-live feed as an overlay, or separately approve the curated permanent-brain lesson merge. Neither has been done here.

Permanent Frankie remains untouched. The separately curated brain lesson proposal can be merged only in a deliberate later step after explicit approval; never bulk-merge the experiment.