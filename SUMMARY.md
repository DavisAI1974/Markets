# OD Autoresearch Summary — apr5 (Real OD Run)

**Branch:** `od-autoresearch/apr5`
**Date:** 2026-04-05
**Stop condition:** Target reached (R² = 0.999997 >= 0.9999)

---

## Results Overview

| Metric | Value |
|---|---|
| Total experiments | 14 |
| Kept | 7 |
| Discarded | 7 |
| Crashed | 0 |
| Best R² | **0.999997** |
| Best R² holdout | **1.000000** |
| Best runtime | 0.117s |
| Best memory | 0.1 MB |
| Dataset | QD3SET-1 spin-boson (401 points, complex density matrix) |

---

## Best Configuration

**Three key changes from baseline:**

1. `recovery_method = "least_squares"` (not "both") — LS alone is 10x faster, same quality
2. `ls_margin_frac = 0.01` (was 0.05) — using more data points dramatically improved R²
3. `n_segments = 8` (was 1) — piecewise Liouvillian captures non-Markovian dynamics

**Full od_config.py (best):**
```python
recovery_method = "least_squares"
ml_time_steps = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 80, 100]
ml_max_eigenvalue = 0.5
ml_min_samples = 6
ml_regularization = 0.0
ml_weighted_average = False
ls_margin_frac = 0.01
ls_diff_order = 2
ls_regularization = 0.0
n_segments = 8
segment_overlap = 0
```

**Final metrics:**
```
r_squared:         0.999997
r_squared_holdout: 1.000000
residual_mean:     0.000291
residual_max:      0.002006
runtime_seconds:   0.109
peak_memory_mb:    0.1
```

---

## Top 5 Most Impactful Changes (ranked by R² improvement)

| Rank | Change | R² Before | R² After | Delta |
|---|---|---|---|---|
| 1 | n_segments=8 | 0.999790 | 0.999997 | +0.000207 |
| 2 | n_segments=4 | 0.999398 | 0.999790 | +0.000392 |
| 3 | n_segments=2 | 0.999242 | 0.999398 | +0.000156 |
| 4 | ls_margin_frac 0.02->0.01 | 0.999032 | 0.999242 | +0.000210 |
| 5 | ls_margin_frac 0.05->0.02 | 0.996956 | 0.999032 | +0.002076 |

The single biggest improvement was reducing ls_margin_frac from 0.05 to 0.02 (+0.0021). The cumulative piecewise segmentation added +0.000755 total.

---

## Top 3 Changes That Surprisingly Didn't Help

1. **Matrix log method** — R² dropped to 0.879 when used alone. The multi-timestep averaging with matrix logarithm is fundamentally less stable than least-squares for this data. The original twobath_operator_discovery.py defaults to ML, but LS is clearly better for QD3SET-1 data.

2. **Tikhonov regularization** (1e-4 and 1e-6) — Zero effect. The pseudoinverse is already well-conditioned for 4x4 systems with 400 data points. Regularization would help for larger, ill-conditioned systems.

3. **Forward differences** (vs central) — R² dropped from 0.999242 to 0.994648. Central differences are 2nd-order accurate vs 1st-order for forward, and the extra accuracy matters for computing dv/dt cleanly.

---

## Analysis

The R² trajectory tells a clear story:

- **Phase 1 (baseline tuning):** Method selection and margin optimization took R² from 0.9970 to 0.9992. The biggest single lever was ls_margin_frac — the original 5% margin discards too much valuable data for a 401-point trajectory.

- **Phase 2 (structural improvement):** Piecewise Liouvillian recovery was the breakthrough. A time-independent L cannot capture the non-Markovian dynamics of a spin-boson system coupled to a thermal bath. By fitting separate L matrices to trajectory segments, the piecewise approach captures time-dependent dissipation rates. The L-norms confirm this: the first segment's L has norm 4.24 (strong initial dynamics) while later segments converge to ~3.27 (equilibrium dissipation).

- **Noise floor:** R²=0.999997 means the population residuals are ~0.03%. This is approaching numerical precision for the matrix exponential reconstruction. Further improvement would require higher-order integration or Krylov subspace methods.

---

## Recommended Next Steps

1. **Test across multiple spin-boson files** — The current result is on a single dataset (lambda=0.1, gamma=1.0, beta=0.5). Run the best config across all 1000 QD3SET-1 files to measure generalization.

2. **Optimize n_segments dynamically** — Instead of fixed 8 segments, use adaptive segmentation based on local trajectory curvature. More segments where dynamics change rapidly, fewer where steady-state.

3. **Add segment overlap** — The `segment_overlap` knob exists but wasn't tested. Overlapping segments with blending could smooth boundary artifacts between segments.

4. **Benchmark harder parameter regimes** — High lambda (strong coupling) and low beta (high temperature) files will be harder to recover. These test the physical limits of the Liouvillian model.

5. **Swap in SpectralNeuralODE** — The spectral_neuralode.py module in E:\operator_discovery\modules\ can learn adaptive basis functions for the dynamics. This would replace the piecewise approach with a continuous time-dependent model.

6. **Run on twobath data** — The two-bath spin-boson files at E:\operator_discovery\twobath_data\ have a different format and physics. Test the engine's generalization.
