# HYPOTHESIS: 8 segments may push past 0.9999 target
#
# This is the ONLY file modified during autoresearch experiments.
# All tunable hyperparameters live here.

# =============================================================================
# Recovery Method Selection
# =============================================================================

# Which method to use: 'matrix_log', 'least_squares', or 'both' (try both, keep best)
recovery_method = "least_squares"

# =============================================================================
# Matrix Logarithm Method Knobs
# =============================================================================

# Time steps to try for propagator estimation (indices into trajectory)
ml_time_steps = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 80, 100]

# Maximum real eigenvalue allowed (reject unstable solutions)
ml_max_eigenvalue = 0.5

# Minimum number of samples needed per time step
ml_min_samples = 6

# Tikhonov regularization for pseudoinverse (0 = no regularization)
ml_regularization = 0.0

# Use error-weighted averaging of L estimates (vs simple mean)
ml_weighted_average = False

# =============================================================================
# Least Squares Method Knobs
# =============================================================================

# Fraction of trajectory edges to skip (reduces boundary artifacts)
ls_margin_frac = 0.01

# Finite difference order: 1 (forward) or 2 (central)
ls_diff_order = 2

# Tikhonov regularization strength (0 = no regularization)
ls_regularization = 0.0

# =============================================================================
# Piecewise Recovery Knobs
# =============================================================================

# Number of trajectory segments (1 = single L, 2+ = piecewise)
n_segments = 8

# Overlap between segments (in time points)
segment_overlap = 0

# =============================================================================
# Primary Knobs (OD Critical Path) — for future real OD engine
# =============================================================================

lambda_physics = 0.5
learning_rate = 0.01
lr_schedule = {"type": "constant"}
attention_sparsity = 0.1
spectral_fft_settings = {
    "window": "hann",
    "overlap": 0.5,
    "normalization": "ortho"
}
positional_encoding = {
    "type": "sinusoidal",
    "max_len": 2048,
    "d_model": 64
}
latent_dim = 32
n_modes = 16
residual_connections = {
    "enabled": True,
    "type": "pre_norm",
    "depth": 2
}
temperature = 1.0

# =============================================================================
# Secondary Knobs — for future real OD engine
# =============================================================================

batch_size = 64
n_epochs = 500
optimizer = {
    "type": "Adam",
    "betas": (0.9, 0.999),
    "eps": 1e-8
}
weight_decay = 1e-4
gradient_clip = 1.0
dropout = 0.1
activation = "gelu"
