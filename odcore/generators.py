"""
odcore/generators.py — OD signal functions (real-bin -> per-bar signal).

Signals are computed from REAL BinSeries (no synthetic). Each returns a per-bar array in
{-1, 0, +1} aligned to the bars (signal[t] is acted on returns[t+1]).
"""

from __future__ import annotations

import numpy as np

from .io import BinSeries
from .operators import vasicek_entropy


def _sign(x, thresh=0.0):
    s = np.zeros_like(x, dtype=float)
    s[x > thresh] = 1.0
    s[x < -thresh] = -1.0
    return s


def ofi_signal(s: BinSeries, thresh: float = 0.05) -> np.ndarray:
    """Order-flow imbalance (buy-sell)/(buy+sell) momentum: follow the aggressor side."""
    tot = s.buy + s.sell
    ofi = np.where(tot > 0, (s.buy - s.sell) / (tot + 1e-12), 0.0)
    return _sign(ofi, thresh)


def ofi_fade(s: BinSeries, thresh: float = 0.05) -> np.ndarray:
    """Fade order-flow imbalance (mean-reversion of microstructure aggression)."""
    return -ofi_signal(s, thresh)


def momentum(s: BinSeries, k: int = 5) -> np.ndarray:
    """Sign of the trailing k-bar return."""
    r = s.log_return()
    mom = np.convolve(r, np.ones(k), mode="full")[:r.size]
    return _sign(mom)


def dipole_direction(s: BinSeries, window: int = 40) -> np.ndarray:
    """OD directional rule: rolling entropy of buy-volume (H_a) vs sell-volume (H_b);
    +1 when H_a > H_b (buy side carries more information), else -1 (INFO-044 / line 244)."""
    n = len(s)
    sig = np.zeros(n)
    for t in range(window, n):
        Ha = vasicek_entropy(s.buy[t - window:t])
        Hb = vasicek_entropy(s.sell[t - window:t])
        sig[t] = 1.0 if Ha > Hb else -1.0
    return sig


# Registry of standalone signals for the honest backtest harness
SIGNALS = {
    "ofi_momentum": ofi_signal,
    "ofi_fade": ofi_fade,
    "momentum5": lambda s: momentum(s, 5),
    "dipole_direction": dipole_direction,
}
