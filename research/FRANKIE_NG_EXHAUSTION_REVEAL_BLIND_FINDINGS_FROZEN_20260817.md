# Frankie NG Exhaustion — Frozen Reveal + Blind Findings

Status: FROZEN FINDINGS. This file records what survived the completed reveal/blind experiment and what must NOT be learned as doctrine.

## Proven / promote as candidate brain lessons

### 1. Exhaustion is a runway/lifespan signal
The strongest validated result is not exact price-path prediction. It is move lifespan / remaining runway.

### 2. Family A has a validated two-state runway split
Exact frozen classifier: 61D normalized roll-20 dipole, t=0..+60s, Euclidean nearest-centroid.
Classifier SHA256: `698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`.
Do not refit.

Frozen reveal baselines:
- A-fast-collapse: 3t=358s, 5t=993s, 8t=1802s, 13t=4386s
- A-persistent: 3t=700s, 5t=1802s, 8t=3455s, 13t=6836s

Held-out validation:
- A-fast-collapse actual medians: 3t=344s, 5t=992.5s, 8t=1576s, 13t=3786s
- A-persistent actual medians: 3t=706s, 5t=1898s, 8t=3455s, 13t=7474s
- persistent > fast-collapse reproduced on all four held-out days at 3t, 5t, 8t, and 13t.

Operational lesson: confirmed A-persistent means materially longer runway than A-fast-collapse. Use reveal baselines operationally; do not retune to holdout medians.

### 3. Microstructure is a confidence modifier
Held-out 8t actual alignment with dipole polarity:
- same-side support: ~60.6%
- mixed/sparse: ~54.1%
- opposite-side: ~42.2%

Lesson: same-side post-event recruitment raises confidence that the exhaustion state retains directional authority; opposite-side flow lowers confidence. Do not convert this into seconds without a separately frozen/tested mapping.

### 4. C remains a scale-transition hypothesis
Held-out C alignment improved with scale:
- 3t 50.0%
- 5t 54.2%
- 8t 56.9%
- 13t 58.2%

Lesson: C can be ambiguous locally while becoming more useful at broader scales. Keep confidence modest.

## Do NOT learn / demote

### B locality rule did not reproduce
Held-out B alignment was approximately 51.4%, 48.6%, 51.4%, 54.5% at 3t/5t/8t/13t. Do not teach Frankie that B is reliably local then loses authority. B remains unresolved / low confidence.

### Do not learn the scratch curve generator
`research/ng_exhaustion_frankie_blind_predict_20260816.py` is a deterministic rule-engine used for the finished blind implementation. Its hand-authored price-path coefficients are NOT Frankie doctrine and its full-curve RMSE/correlation scores are NOT a valid measure of Frankie's model forecasting ability.

### Do not promote exact path prediction from this experiment
The validated finding is runway/lifespan, not exact future price shape.

## Integration recommendation
Do not bulk-merge this file into the permanent brain. Convert the proven items above into explicit, provenance-tagged lesson proposals with confidence and negative constraints. Preserve the rejected B rule and scratch-curve warning as negative lessons so they cannot be accidentally rediscovered from this experiment.

Permanent Frankie remains unchanged until a deliberate brain-update step is approved separately.