"""
odcore/generators.py — OD signal functions (real-bin -> per-bar signal) + a bridge to the
existing adaptive_backtester.SignalGenerator interface.

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


def dipole_gated(s: BinSeries, train_frac: float = 0.6, k: float = 1.5) -> np.ndarray:
    """The order-flow dipole with the QuietFloor gate wired in (S43 NEXT #4).

    DIRECTION lives in the order-flow imbalance LEVEL (sign of ofi = (buy-sell)/(buy+sell)); the
    QuietFloor decides WHEN to fire so the dipole stops churning through a trend. In a trend the ofi
    level stays elevated and slowly relaxes (the quiet AR(1) floor absorbs it → small innovation →
    gate shut); only a shock that breaks the relaxation opens the gate.

    Leakage-safe: the QuietFloor is fit on the TRAINING slice's quiet cells only (`quiet_floor.fit`,
    same train_frac), and the gate is causal (innovation at t uses imb[t-1]). Returns sign(ofi) where
    the gate is open, else 0 (stand aside)."""
    from .quiet_floor import fit as fit_quiet
    tot = s.buy + s.sell
    imb = np.where(tot > 0, (s.buy - s.sell) / (tot + 1e-12), 0.0)
    quiet = tot <= 0.0                      # 'still' cells: no taker volume
    floor = fit_quiet(imb, quiet, train_frac=train_frac)
    return floor.gated_signal(imb, k=k)     # sign(level) where the gate opens, else 0


# Registry of standalone signals for the honest backtest harness
SIGNALS = {
    "ofi_momentum": ofi_signal,
    "ofi_fade": ofi_fade,
    "momentum5": lambda s: momentum(s, 5),
    "dipole_direction": dipole_direction,
    "dipole_gated": dipole_gated,
}


# ---------------------------------------------------------------------------
# Bridge to adaptive_backtester.SignalGenerator (MarketFeatures-based)
# ---------------------------------------------------------------------------

def make_od_generators():
    """Return SignalGenerators that plug into the existing AdaptiveSelector pool.

    Uses MarketFeatures fields already produced by the encoder (mean_dipole etc.) so the
    OD operators compete in the same rolling-Sharpe selection as pure_dipole_fade /
    dipole_x_volz. The richer entropy-based dipole runs in the odcore harness; this bridge
    keeps the live path working without disturbing the 64-dim encoder layout.
    """
    try:
        from adaptive_backtester import SignalGenerator
    except Exception:
        return []
    return [
        SignalGenerator(
            name="od_dipole_fade",
            predict_fn=lambda f: -f.mean_dipole,
            threshold=0.15,
            description="OD: fade order-flow dipole (entropy-dipole bridge)"),
        SignalGenerator(
            name="od_dipole_sustained",
            predict_fn=lambda f: f.mean_dipole * (1.0 + abs(f.dipole_autocorr_lag1)),
            threshold=0.2,
            description="OD: sustained one-side pressure (dipole x its persistence)"),
    ]
