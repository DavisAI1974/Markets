"""
odcore/synthetic.py — synthetic systems with KNOWN coupling, for tests + the PySR anchor.

These reproduce the controls the research log uses to validate the operator machinery:
  - symmetric independent channels -> equal-entropy attractor (-1,-1,+2)/sqrt6 (INFO-012).
  - native structured coupling -> MI a tight function of H_a, slope rises with knob g (INFO-040).
  - diffusive correlation -> high correlation but MI high-variance, stays OUT of the null
    (the INFO-041 control that separates structure from mere correlation).
  - Brusselator (chemistry) -> the algebraic-dipole anchor a=0.007,b=-0.093,c=1.309 (INFO-044/D).
  - lagged pair -> known lead-lag for the raw-cross-cov detector (INFO-066/E).

Each `ensemble_*` returns a (n_windows, 6) operator matrix built from independent windows
(the ensemble construction; faithful to the log's ensemble-H approach).
"""

from __future__ import annotations

import numpy as np

from .operators import operator_row


def _ar1(n: int, phi: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + sigma * rng.standard_normal()
    return x


def ou_series(n: int, theta: float = 0.5, sigma: float = 1.0, seed: int = 0) -> np.ndarray:
    """Ornstein-Uhlenbeck (mean-reverting) trajectory."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = x[t - 1] - theta * x[t - 1] + sigma * rng.standard_normal()
    return x


# ---------------------------------------------------------------------------
# Operator-ensemble generators (one independent window per row)
# ---------------------------------------------------------------------------

def ensemble_independent(n_windows: int = 80, win: int = 40, seed: int = 0) -> np.ndarray:
    """Symmetric, independent channels with per-window amplitude. H_a~=H_b within a
    window (equal-entropy), varying across windows -> recovers the attractor; MI ~ 0."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_windows):
        s = rng.uniform(0.3, 3.0)             # per-window amplitude
        a = s * rng.standard_normal(win)
        b = s * rng.standard_normal(win)      # same amplitude, independent draw
        rows.append(operator_row(a, b, rng=rng))
    return np.vstack(rows)


def ensemble_native_coupled(n_windows: int = 80, win: int = 40, g: float = 1.0,
                            seed: int = 0) -> np.ndarray:
    """Structured nonlinear coupling: b = tanh(g*a) + small noise. MI is a tight
    function of the window's spread (hence H_a); slope rises with g (INFO-040)."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_windows):
        s = rng.uniform(0.3, 3.0)
        a = s * rng.standard_normal(win)
        b = np.tanh(g * a) + 0.05 * rng.standard_normal(win)
        rows.append(operator_row(a, b, rng=rng))
    return np.vstack(rows)


def ensemble_biology_coupled(n_windows: int = 80, win: int = 40, g: float = 0.5,
                             seed: int = 0) -> np.ndarray:
    """Biology-type structured coupling: MI is a tight LINEAR function of H_a, with
    ASYMMETRIC channels (H_b ~ const) so the equal-entropy identity does NOT dominate.

    Per window: pick t ~ U(0.2, 2.0); amplitude s=exp(t) so H_a ~ t + const; choose the
    Gaussian correlation rho with -0.5*ln(1-rho^2) = g*t, so MI(a,b) ~ g*t ~ g*H_a. Channel
    b has fixed unit amplitude (H_b ~ const). => MI enters the null as MI ~ g*H_a (INFO-040),
    and the slope rises with g.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_windows):
        t = rng.uniform(0.2, 2.0)
        s = np.exp(t)
        rho = np.sqrt(max(0.0, 1.0 - np.exp(-2.0 * g * t)))
        rho = min(rho, 0.999)
        z1 = rng.standard_normal(win)
        z2 = rng.standard_normal(win)
        a = s * z1                                           # H_a ~ t + const
        b = rho * z1 + np.sqrt(1 - rho * rho) * z2           # unit amplitude, H_b ~ const
        rows.append(operator_row(a, b, rng=rng))
    return np.vstack(rows)


def ensemble_diffusive(n_windows: int = 80, win: int = 40, seed: int = 0) -> np.ndarray:
    """Diffusive correlation: per-window correlation rho_w drawn INDEPENDENTLY of the
    per-window amplitude. MI(~ -0.5 ln(1-rho^2)) is high-variance and uncorrelated with
    H_a, so it stays out of the low-variance null (the INFO-041 control)."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_windows):
        s = rng.uniform(0.3, 3.0)
        rho = rng.uniform(0.3, 0.95)
        z1 = rng.standard_normal(win)
        z2 = rng.standard_normal(win)
        a = s * z1
        b = s * (rho * z1 + np.sqrt(1 - rho * rho) * z2)
        rows.append(operator_row(a, b, rng=rng))
    return np.vstack(rows)


# ---------------------------------------------------------------------------
# Brusselator (chemistry) — the algebraic-dipole anchor
# ---------------------------------------------------------------------------

def brusselator(n: int, A: float = 1.0, B: float = 3.0, dt: float = 0.05,
                seed: int = 0, noise: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Two-species Brusselator (x, y). B>1+A^2 (here 2) => oscillatory regime."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    y = np.zeros(n)
    x[0], y[0] = A + 0.1, B / A
    for t in range(1, n):
        dx = A + x[t - 1] ** 2 * y[t - 1] - (B + 1) * x[t - 1]
        dy = B * x[t - 1] - x[t - 1] ** 2 * y[t - 1]
        x[t] = x[t - 1] + dt * dx + noise * rng.standard_normal()
        y[t] = y[t - 1] + dt * dy + noise * rng.standard_normal()
    return x, y


def ensemble_brusselator(n_windows: int = 120, win: int = 40, B: float = 3.0,
                         seed: int = 0) -> np.ndarray:
    """Operator ensemble from independent Brusselator runs (varied initial phase)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_windows):
        x, y = brusselator(win + 50, B=B, seed=int(rng.integers(0, 1 << 31)))
        rows.append(operator_row(x[-win:], y[-win:], rng=rng))
    return np.vstack(rows)


# ---------------------------------------------------------------------------
# Lead-lag pair — known lag for the raw-cross-cov detector
# ---------------------------------------------------------------------------

def lagged_pair(n: int, lag: int, sigma: float = 1.0, noise: float = 0.2,
                seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """b lags a by `lag` samples: b[t] = a[t-lag] + noise. (a leads.)"""
    rng = np.random.default_rng(seed)
    a = _ar1(n + lag, phi=0.9, sigma=sigma, rng=rng)
    b = np.empty(n)
    b[:] = a[:n]  # placeholder
    a_full = a
    a = a_full[lag:lag + n]
    b = a_full[0:n] + noise * rng.standard_normal(n)  # b = a shifted later in time
    return a, b
