"""
odcore/operators.py — the windowed Operator-Discovery basis.

RECONSTRUCTED-FROM-CLAUDE.md. Parts list cites (CLAUDE (5).md):
  - Basis [H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI], window=40 (INFO-012 l.597; basis l.265).
  - Estimator robustness: Vasicek / KDE / kNN(KSG) families all agree on the structural
    core (INFO-022 l.609; INFO-034 KSG holds l.1972). We use Vasicek m-spacing for the
    marginal differential entropies and KSG-1 (k=4) for mutual information.
  - MI is the only scale-invariant (physical) quantity in the basis; marginal-entropy
    asymmetry is a units choice (INFO-051 l.1051) -> we center, never z-score (null_extract).
  - anti_frac ~ 1/N_eff flags finite-effective-sample noise / data sufficiency (INFO-017 l.581).

Numerical-stability notes baked in:
  - jitter near-constant channels and break ties (KSG degenerates on repeated values;
    order-flow channels are full of zeros).
  - clamp MI >= 0 (KSG can return small negatives).
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.special import digamma


# ---------------------------------------------------------------------------
# Marginal differential entropy — Vasicek (1976) m-spacing estimator
# ---------------------------------------------------------------------------

def vasicek_entropy(x: np.ndarray, m: int | None = None) -> float:
    """Differential entropy of a 1-D sample via the Vasicek m-spacing estimator.

    H_hat = (1/n) * sum_i log( (n / (2m)) * (x_{(i+m)} - x_{(i-m)}) )

    with edge spacings clamped to the sample extremes. m defaults to round(sqrt(n)),
    the standard choice. Robust, fast, and the OD default for windowed marginal H.
    """
    x = np.asarray(x, dtype=float).ravel()
    n = x.size
    if n < 4:
        return 0.0
    if m is None:
        m = max(1, int(round(np.sqrt(n))))
    m = min(m, (n - 1) // 2)
    xs = np.sort(x)
    # indices i+m and i-m, clamped to [0, n-1]
    hi = np.clip(np.arange(n) + m, 0, n - 1)
    lo = np.clip(np.arange(n) - m, 0, n - 1)
    diffs = xs[hi] - xs[lo]
    # guard zero spacings (ties / near-constant windows)
    scale = np.std(xs)
    floor = 1e-12 if scale == 0 else 1e-9 * scale
    diffs = np.maximum(diffs, floor)
    return float(np.mean(np.log((n / (2.0 * m)) * diffs)))


# ---------------------------------------------------------------------------
# Mutual information — Kraskov-Stoegbauer-Grassberger (KSG-1), Chebyshev metric
# ---------------------------------------------------------------------------

def ksg_mi(a: np.ndarray, b: np.ndarray, k: int = 4, base: float = np.e,
           rng: np.random.Generator | None = None) -> float:
    """KSG-1 mutual information estimator for two 1-D continuous variables.

    MI = psi(k) + psi(N) - <psi(n_a+1) + psi(n_b+1)>

    using the Chebyshev (L-inf) metric in the joint space. Tiny noise is added to
    break ties (standard KSG practice; required because order-flow channels repeat
    zeros). Clamped at 0.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    if n <= k + 1:
        return 0.0
    if rng is None:
        rng = np.random.default_rng(0)
    # break ties with negligible jitter scaled to each channel
    sa = np.std(a) or 1.0
    sb = np.std(b) or 1.0
    a = a + 1e-10 * sa * rng.standard_normal(n)
    b = b + 1e-10 * sb * rng.standard_normal(n)

    joint = np.column_stack([a, b])
    jtree = cKDTree(joint)
    # distance to the k-th neighbour (query returns self as the first neighbour)
    dists, _ = jtree.query(joint, k=k + 1, p=np.inf)
    eps = dists[:, -1]  # Chebyshev radius to k-th neighbour

    atree = cKDTree(a[:, None])
    btree = cKDTree(b[:, None])
    # count neighbours strictly within eps in each marginal (exclude self -> -1)
    na = np.array([len(atree.query_ball_point([a[i]], eps[i] - 1e-15, p=np.inf)) - 1
                   for i in range(n)])
    nb = np.array([len(btree.query_ball_point([b[i]], eps[i] - 1e-15, p=np.inf)) - 1
                   for i in range(n)])
    na = np.maximum(na, 0)
    nb = np.maximum(nb, 0)

    mi = digamma(k) + digamma(n) - np.mean(digamma(na + 1) + digamma(nb + 1))
    mi = max(0.0, float(mi))
    if base != np.e:
        mi /= np.log(base)
    return mi


# ---------------------------------------------------------------------------
# Windowed operator matrix
# ---------------------------------------------------------------------------

# Canonical column order for the 6-operator basis.
BASIS_COLUMNS = ("H_a", "H_b", "H_a^2", "H_b^2", "H_a*H_b", "MI")
COL = {name: i for i, name in enumerate(BASIS_COLUMNS)}


def operator_row(a_win: np.ndarray, b_win: np.ndarray, k: int = 4,
                 rng: np.random.Generator | None = None) -> np.ndarray:
    """The 6-operator row for one aligned window of two channels."""
    Ha = vasicek_entropy(a_win)
    Hb = vasicek_entropy(b_win)
    mi = ksg_mi(a_win, b_win, k=k, rng=rng)
    return np.array([Ha, Hb, Ha * Ha, Hb * Hb, Ha * Hb, mi], dtype=float)


def windowed_operator_matrix(a: np.ndarray, b: np.ndarray, window: int = 40,
                             stride: int = 10, k: int = 4, seed: int = 0) -> np.ndarray:
    """Slide a window over two aligned channels and stack the 6-operator rows.

    Returns an (n_windows, 6) matrix with columns BASIS_COLUMNS. window=40,
    stride=10 are the OD defaults (INFO-012). Independent of the PELT chunker.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    if n < window:
        return np.empty((0, 6), dtype=float)
    rng = np.random.default_rng(seed)
    starts = range(0, n - window + 1, stride)
    rows = [operator_row(a[s:s + window], b[s:s + window], k=k, rng=rng) for s in starts]
    return np.vstack(rows) if rows else np.empty((0, 6), dtype=float)


def anti_frac(a: np.ndarray, b: np.ndarray, window: int) -> float:
    """Antisymmetric-energy / data-sufficiency proxy ~ 1/N_eff (INFO-017 l.581).

    N_eff = window / tau_correlation; small N_eff => the windowed extraction is
    noise-limited. We return 1/N_eff using a lag-1-autocorrelation estimate of tau
    on the concatenated channels; callers can refuse extraction above a threshold.
    """
    def tau(x: np.ndarray) -> float:
        x = np.asarray(x, dtype=float).ravel()
        x = x - x.mean()
        denom = np.dot(x, x)
        if denom <= 1e-12:
            return 1.0
        r1 = np.dot(x[:-1], x[1:]) / denom
        r1 = min(max(r1, 0.0), 0.999)
        # tau ~ -1/ln(r1) for an AR(1) process; r1<=0 -> tau ~ 1
        return 1.0 if r1 <= 0 else -1.0 / np.log(r1)
    tau_eff = 0.5 * (tau(a) + tau(b))
    n_eff = max(1e-6, window / max(tau_eff, 1e-6))
    return float(1.0 / n_eff)
