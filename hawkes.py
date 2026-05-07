"""
hawkes.py — fit a univariate exponential-kernel Hawkes process per
chunk and report the branching ratio η = α/β as a clustered-vs-Poisson
discriminator.

The intensity is

    λ(t) = μ + α · Σ_{tᵢ < t} exp(-β · (t − tᵢ))

with η = α / β bounded in [0, 1) for stationarity. η ≈ 0 means trade
arrivals look like an inhomogeneous Poisson stream; η near 1 means
heavy self-excitation, i.e. each trade triggers ~η descendants on
average. The literature (2025–2026 crypto LOB papers) consistently
finds high η during informed-flow / cascade regimes and low η during
quiet two-sided regimes, so it should be a sharper separator for
NASCENT-vs-WHALE than VPIN alone.

Design notes:
  - Bar-binned data only gives us bar timestamps + n_trades, not real
    trade times. We jitter n_trades synthetic events uniformly within
    each bar's 60s span to approximate the event sequence; this
    preserves arrival counts and inter-arrival distributions to within
    one bar's resolution. Good enough for relative ordering of η
    across chunks; not adequate for reporting the absolute η level.
  - We cap synthetic events at MAX_EVENTS_PER_CHUNK (default 1500) to
    keep the fit fast for large chunks; downsample uniformly if
    exceeded. The cap is well above typical chunk sizes.
  - Optimization uses scipy.optimize.minimize with L-BFGS-B and a
    coarse multi-start over β. The Hawkes log-lik can have shallow
    plateaus when η is small, so multi-start is cheap insurance.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


MIN_EVENTS_FOR_FIT = 8
MAX_EVENTS_PER_CHUNK = 1500
DEFAULT_BAR_DURATION_S = 60.0


def _neg_log_lik_exp_hawkes(params: np.ndarray, et: np.ndarray, T: float) -> float:
    """Negative log-likelihood of the exponential-kernel univariate
    Hawkes process on event times et ⊂ [0, T]."""
    mu, alpha, beta = params
    if mu <= 1e-12 or alpha < 0.0 or beta <= 1e-6:
        return 1e18
    if alpha / beta >= 0.999:
        return 1e18
    n = len(et)
    A = 0.0
    log_lambda_sum = 0.0
    for i in range(n):
        if i > 0:
            A = math.exp(-beta * (et[i] - et[i - 1])) * (A + 1.0)
        lam = mu + alpha * A
        if lam <= 0.0:
            return 1e18
        log_lambda_sum += math.log(lam)
    integral = mu * T + (alpha / beta) * float(np.sum(1.0 - np.exp(-beta * (T - et))))
    return -(log_lambda_sum - integral)


def fit_exponential_hawkes(event_times: np.ndarray, T: Optional[float] = None
                              ) -> dict:
    """Fit μ, α, β for λ(t) = μ + α Σ_{tᵢ<t} exp(-β·(t-tᵢ)) on event
    times in [0, T]. Returns a dict with eta=α/β, mu, alpha, beta,
    log_lik, n_events. Returns eta=0.0 (Poisson-like) and a None
    log_lik when there isn't enough data to fit."""
    et = np.asarray(event_times, dtype=float)
    et = np.sort(et[~np.isnan(et)])
    if T is None:
        T = float(et[-1] + 1e-3) if len(et) else 0.0
    if len(et) < MIN_EVENTS_FOR_FIT or T <= 0:
        return {"eta": 0.0, "mu": 0.0, "alpha": 0.0, "beta": 0.0,
                "log_lik": None, "n_events": int(len(et))}
    et = et - et[0]   # shift to start at 0; T already sized accordingly
    T = float(et[-1] + 1e-3)

    if len(et) > MAX_EVENTS_PER_CHUNK:
        idx = np.linspace(0, len(et) - 1, MAX_EVENTS_PER_CHUNK).astype(int)
        et = et[idx]
        T = float(et[-1] + 1e-3)

    n = len(et)
    avg_rate = n / T if T > 0 else 0.0
    avg_gap = T / max(n, 1)

    # Multi-start over β: faster decay (small β) ↔ shorter cluster
    # half-life. Pick the best ML fit.
    best = None
    try:
        from scipy.optimize import minimize
    except ImportError:
        # No scipy => degrade gracefully to Poisson estimate.
        return {"eta": 0.0, "mu": float(avg_rate), "alpha": 0.0, "beta": 0.0,
                "log_lik": None, "n_events": n}

    bounds = [(1e-9, None), (0.0, None), (1e-6, None)]
    for beta_init in (0.5 / avg_gap, 1.0 / avg_gap, 5.0 / avg_gap):
        x0 = np.array([avg_rate * 0.5, 0.5 * beta_init, beta_init])
        try:
            res = minimize(_neg_log_lik_exp_hawkes, x0, args=(et, T),
                            method="L-BFGS-B", bounds=bounds,
                            options={"maxiter": 200, "ftol": 1e-7})
        except Exception:
            continue
        if not np.isfinite(res.fun):
            continue
        if best is None or res.fun < best.fun:
            best = res

    if best is None:
        return {"eta": 0.0, "mu": float(avg_rate), "alpha": 0.0, "beta": 0.0,
                "log_lik": None, "n_events": n}

    mu, alpha, beta = best.x
    eta = float(alpha / beta) if beta > 0 else 0.0
    eta = max(0.0, min(eta, 0.999))
    return {"eta": eta, "mu": float(mu), "alpha": float(alpha),
            "beta": float(beta), "log_lik": float(-best.fun),
            "n_events": n}


def synth_event_times_from_bars(bars, bar_duration_s: float = DEFAULT_BAR_DURATION_S
                                  ) -> np.ndarray:
    """Reconstruct synthetic per-trade event times from bar-level data.
    For each bar with n_trades > 0, place n_trades event times
    uniformly in [bar.ts, bar.ts + bar_duration_s).

    Returns a sorted np.ndarray. Empty if no bars have trade activity."""
    rng = np.random.default_rng(0)
    out: list[float] = []
    for b in bars:
        n = int(getattr(b, "n_trades", 0) or 0)
        if n <= 0:
            continue
        ts0 = float(getattr(b, "ts", 0.0))
        if ts0 <= 0:
            continue
        offsets = rng.uniform(0.0, bar_duration_s, size=n)
        out.extend((ts0 + offsets).tolist())
    if not out:
        return np.empty(0, dtype=float)
    arr = np.asarray(out, dtype=float)
    arr.sort()
    return arr


def hawkes_eta_for_bars(bars) -> tuple[float, int]:
    """Convenience: return (eta, n_events) for the given bars sequence,
    using bar_duration_s = 60 (one-minute bins). Caller can store both
    on MarketFeatures."""
    et = synth_event_times_from_bars(bars)
    if len(et) < MIN_EVENTS_FOR_FIT:
        return 0.0, int(len(et))
    fit = fit_exponential_hawkes(et)
    return float(fit["eta"]), int(fit["n_events"])
