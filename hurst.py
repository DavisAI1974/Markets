"""
hurst.py — per-chunk Hurst exponent via Detrended Fluctuation Analysis.

DFA produces an orthogonal trending-vs-reverting label that layers on
top of the regime classifier:

  H > 0.5  : long-range positive correlation (trending / momentum)
  H = 0.5  : uncorrelated random walk (no edge from this axis)
  H < 0.5  : negative correlation / mean-reverting

Why DFA and not R/S: DFA is more robust on short, non-stationary series
(both true of our chunk-level log returns at ~10-30 bars per chunk).

Returned at the chunk level, not the bin level. For very small chunks
(n_returns < 8) the estimator returns (0.5, 0) — the consumer should
treat that as "no signal" rather than "true random walk".
"""

from __future__ import annotations

import numpy as np


# Minimum number of log returns the DFA estimator considers reliable.
# Below this, hurst_dfa returns (0.5, 0) so the consumer can filter.
HURST_MIN_RETURNS = 8


def hurst_dfa(returns: np.ndarray, min_window: int = 4) -> tuple[float, int]:
    """Estimate the Hurst exponent of `returns` via DFA-1.

    Returns (H, n_returns_used). H ∈ (~0, ~1.5) in theory; in practice
    well-behaved series fall in [0.2, 0.8]. (0.5, 0) signals "no
    signal" — too few samples for a reliable fit.
    """
    if returns is None:
        return 0.5, 0
    r = np.asarray(returns, dtype=float)
    n = r.size
    if n < HURST_MIN_RETURNS:
        return 0.5, 0
    max_window = n // 2
    if max_window < min_window:
        return 0.5, 0

    # Cumulative deviation from the mean ("profile" in DFA terminology)
    profile = np.cumsum(r - np.mean(r))

    # Geometric spread of window scales between min_window and max_window.
    # 5 scales is the sweet spot for n in [10, 50] — fewer is unstable,
    # more correlates the points and biases the slope estimate.
    n_scales = 5
    scales = np.unique(np.round(
        np.geomspace(min_window, max_window, n_scales)
    ).astype(int))
    if scales.size < 2:
        return 0.5, n

    Fs: list[float] = []
    valid_scales: list[int] = []
    for s in scales:
        n_windows = n // int(s)
        if n_windows < 1:
            continue
        s_int = int(s)
        x = np.arange(s_int, dtype=float)
        A = np.vstack([x, np.ones(s_int)]).T
        residual_sq_means: list[float] = []
        for w in range(n_windows):
            seg = profile[w * s_int : (w + 1) * s_int]
            coef, *_ = np.linalg.lstsq(A, seg, rcond=None)
            trend = A @ coef
            res = seg - trend
            residual_sq_means.append(float(np.mean(res ** 2)))
        if not residual_sq_means:
            continue
        F = float(np.sqrt(np.mean(residual_sq_means)))
        if F > 0.0:
            Fs.append(F)
            valid_scales.append(s_int)

    if len(Fs) < 2:
        return 0.5, n

    log_F = np.log(np.asarray(Fs))
    log_s = np.log(np.asarray(valid_scales, dtype=float))
    slope, _intercept = np.polyfit(log_s, log_F, 1)
    return float(slope), n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30, help="series length")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)

    # Random walk: H ≈ 0.5
    rw = rng.normal(size=args.n)
    print(f"random walk     n={args.n}  H={hurst_dfa(rw)[0]:.3f}  (expect ≈0.5)")

    # Trending: cumulative random walk integrated again => H > 0.5
    trend = np.cumsum(rng.normal(size=args.n)) * 0.01
    print(f"trending        n={args.n}  H={hurst_dfa(trend)[0]:.3f}  (expect >0.5)")

    # Mean-reverting: AR(1) with negative coefficient
    mr = np.zeros(args.n)
    for i in range(1, args.n):
        mr[i] = -0.7 * mr[i - 1] + rng.normal(scale=0.1)
    print(f"mean-reverting  n={args.n}  H={hurst_dfa(mr)[0]:.3f}  (expect <0.5)")


if __name__ == "__main__":
    main()
