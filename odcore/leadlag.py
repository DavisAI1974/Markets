"""
odcore/leadlag.py — raw cross-covariance-over-lag lead-lag detector (the S19 right tool).

RECONSTRUCTED-FROM-CLAUDE.md. Cites (CLAUDE (5).md):
  - S19 (INFO-065/066 l.890-945): the entropy/flow dipole is BLIND to lag/coupling because
    windowed marginal entropies are lag-independent; the RAW cross-covariance over lag is
    where the coupling/time information lives. It recovered the 7.32 ms inter-detector
    light-travel lag (LIGO) and lag-0 |cc|~0.99 z=37 (GPS).
  - In crypto this is a CROSS-VENUE / CROSS-ASSET lead-lag detector: who moves first, by how
    many bars, and how reliably (z vs a time-slide null).
  - The tautology-killing circular-shift null (INFO-066 l.913) is the rigorous control;
    here we use a time-slide null for the z and expose the circular-shift control in validation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    s = x.std()
    return x / s if s > 1e-12 else x


def cross_correlation(a: np.ndarray, b: np.ndarray, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Pearson cross-correlation of (a, b) over integer lags in [-max_lag, +max_lag].

    Convention: cc[lag] = corr(a[t], b[t+lag]). A POSITIVE peak lag means b follows a, i.e.
    a LEADS b by `lag` bars.
    """
    a = _norm(a); b = _norm(b)
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    lags = np.arange(-max_lag, max_lag + 1)
    cc = np.empty(lags.size, dtype=float)
    for i, lag in enumerate(lags):
        if lag >= 0:
            x, y = a[:n - lag], b[lag:]
        else:
            x, y = a[-lag:], b[:n + lag]
        if x.size < 3:
            cc[i] = 0.0
        else:
            cc[i] = float(np.mean(x * y))  # both already unit-variance, zero-mean
    return lags, cc


@dataclass
class LeadLagResult:
    lag: int          # peak lag in bars; >0 => channel a LEADS channel b
    cc: float         # cross-correlation at the peak lag
    z: float          # z of the peak vs a time-slide null
    leader: str       # "a", "b", or "synchronous"
    max_lag: int


def detect_leadlag(a: np.ndarray, b: np.ndarray, max_lag: int = 30,
                   n_null: int = 200, seed: int = 0) -> LeadLagResult:
    """Find the lead-lag between two channels and its significance.

    z is computed against a time-slide null: random circular shifts of b destroy the genuine
    temporal pairing while preserving each channel's autocorrelation (the INFO-066 idea).
    """
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    lags, cc = cross_correlation(a, b, max_lag)
    k = int(np.argmax(np.abs(cc)))
    peak_lag, peak_cc = int(lags[k]), float(cc[k])

    rng = np.random.default_rng(seed)
    n = min(a.size, b.size)
    null_peaks = np.empty(n_null)
    for i in range(n_null):
        shift = int(rng.integers(max_lag + 1, n - max_lag - 1))
        b_shift = np.roll(b[:n], shift)
        _, cc_null = cross_correlation(a[:n], b_shift, max_lag)
        null_peaks[i] = np.max(np.abs(cc_null))
    mu, sd = float(null_peaks.mean()), float(null_peaks.std())
    z = (abs(peak_cc) - mu) / sd if sd > 1e-12 else 0.0

    if abs(peak_lag) == 0:
        leader = "synchronous"
    elif peak_lag > 0:
        leader = "a"   # a leads b
    else:
        leader = "b"
    return LeadLagResult(lag=peak_lag, cc=peak_cc, z=z, leader=leader, max_lag=max_lag)
