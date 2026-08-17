# ChatGPT Kickoff — NG Exhaustion Runway Clock

Status: BUILD NEXT. Current repo state plus this handoff are truth.
Repository: `DavisAI1974/Markets`
Working branch: `chatgpt/ng-exhaustion-runway-clock-20260817`

## Read first
1. `research/FRANKIE_NG_EXHAUSTION_REVEAL_BLIND_FINDINGS_FROZEN_20260817.md`
2. `research/FRANKIE_NG_EXHAUSTION_BRAIN_LESSON_PROPOSAL_20260817.md`
3. `research/FRANKIE_NG_EXHAUSTION_REVEAL_MEMO_20260816.md`
4. `research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`
5. `research/blind_reveal/ng_exhaustion_20260816/FRANKIE_NG_EXHAUSTION_POSTREVEAL_METRICS_20260816.json`
6. `research/FRANKIE_NG_DIPOLE_PREBLIND_REFLECTION_20260816.md`
7. `research/FRANKIE_NG_DIPOLE_BRAIN_CROSSWALK_20260816.md`
8. `research/kalshi/S136_PERMANENT_WORKFLOW_HANDOFF.md` only for permanent-runtime/protection truth.

Do not redo the finished blind experiment.

## Mission
Build an isolated deterministic NG **exhaustion runway clock**. Its job is to estimate how much structural life/runway remains at 3t, 5t, 8t, and optionally 13t. It is not a direction model and not a full price-curve model.

Architecture target:
`Frankie direction/magnitude` + `exhaustion runway clock` -> `hold-length / continuation / failure overlay`.

Do not wire into permanent Frankie until the isolated clock is proven.

## Validated core
Exact A classifier SHA256:
`698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`

Classifier contract:
- normalized roll-20 dipole values, t=0..+60s inclusive, 61 dimensions
- divide all 61 values by t=0 value
- Euclidean nearest frozen centroid
- cluster 0 = A-fast-collapse
- cluster 1 = A-persistent
- no refit, no extra scaling, no custom threshold/tie rule.

Frozen operational duration baselines from reveal:
- A-fast-collapse: 3t=358s, 5t=993s, 8t=1802s, 13t=4386s
- A-persistent: 3t=700s, 5t=1802s, 8t=3455s, 13t=6836s

Held-out validation reproduced persistent > fast-collapse on all 4 days at 3t/5t/8t/13t. Do not retune v0 baselines to held-out medians.

Microstructure confirmation survived as confidence only:
- same-side support -> stronger alignment
- opposite-side support -> weaker alignment
Do not convert support into seconds in v0.

C: keep low/moderate-confidence scale-transition note.
B: unresolved; do not teach the failed locality hypothesis.

## V0 implementation
Suggested module: `research/ng_exhaustion_runway_clock.py`

Inputs:
- event/session ID
- t0
- family
- elapsed seconds since t0
- exact A classifier inputs when available
- legal post-event aggressor/book/MBO confirmation
- data-availability flags

State rule:
- before +60s: A state is `A_STATE_PENDING` unless a separately frozen earlier classifier exists
- at/after +60s: apply exact frozen A classifier
- do not invent a partial-centroid classifier.

Outputs per update should include:
- family
- confirmed/pending post-state
- elapsed time
- for each 3t/5t/8t/13t: baseline total runway, remaining runway, confidence, basis
- microstructure confirmation: same_side / mixed / opposite / unavailable
- confidence modifier
- falsifier/data-gap status
- explicit `future_price_accessed=false`.

V0 remaining time rule:
`remaining_s = max(0, baseline_total_s - elapsed_since_t0_s)`

No hidden nonlinear weights in v0.

B/C fallback duration baselines if needed:
- B: 353 / 995 / 1615 / 4543s, low confidence
- C: 377 / 1159 / 1713 / 4320s, low confidence

## Tests
Must cover:
- classifier SHA drift fails closed
- exact 61D normalization/distance
- no A state before +60s
- countdown monotonicity
- remaining time never negative
- data gaps fail closed or clearly degrade confidence
- microstructure never changes seconds in v0
- B stays unresolved
- replay reproduces held-out A counts 831 fast / 785 persistent and persistent>fast ordering on all four days.

## Render
Produce a PNG with two panels:
1. normalized exhaustion curve + current as-of marker + confirmed/pending A state
2. four runway clocks/bars for 3t/5t/8t/13t showing baseline, elapsed, remaining, confidence, and microstructure badge.

Replay may show actual realized endpoint markers only for validation. Live clock must not require future price.

## Do not learn / do not reuse
- Do not use `research/ng_exhaustion_frankie_blind_predict_20260816.py` as a Frankie curve template. It was a scratch deterministic rule-engine.
- Do not treat its full-curve RMSE/correlation as Frankie model performance.
- Do not promote exact path prediction from this experiment.
- Do not promote B locality.

## Permanent Frankie protection
Do not modify permanent brain/schema/roles/plays/datapoints/spawn.py/workflow during the isolated clock build.

A separate deliberate brain-update step can later merge the validated lesson proposal. If that happens, merge only validated positive lessons plus explicit negative lessons; never bulk-merge all experiment artifacts.

## Acceptance
V0 is done only when:
- exact classifier is reused with SHA verification
- frozen reveal baselines are used
- state availability timing is legal
- no future price required
- tests pass
- replay validation matches committed facts
- PNG render is shown in chat
- permanent Frankie remains untouched.

Central product hypothesis:
**Exhaustion is a runway/lifespan signal. Build the clock around that and keep direction separate.**