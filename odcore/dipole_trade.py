"""
odcore/dipole_trade.py — wire the algebraic (chem) dipole onto the current 5-step coupling
model, PER TRADE (S22, 2026-06-07).

Portable by design: this module takes each trade's aligned pre-entry channel arrays plus a
win/lose label as ARGUMENTS. It does NOT import the platform shell (executor / backend /
backtester); the runner that pulls labeled trades from the platform lives outside odcore
(scripts/, specced in the S22 handoff). This preserves odcore's portability (S21 decision).

Per-trade coefficient vector c_i = the 5-step coupling model's output on the trade's
pre-entry window (Greg-approved, S22):

    [mi_frac, chem_residual_frac, eq_entropy_frac, mi_slope, mi_slope_r2, mi_mean, mi_var,
     singular_gap, dipole_a, dipole_b, dipole_c, dipole_r2, leadlag, leadlag_cc, leadlag_z]

Deviation from the verbatim original (justified + documented): the original projected
homogeneous 128-dim operator_coefficients, so raw dot products were scale-balanced. Our c_i
is HETEROGENEOUS (fractions, slopes, lags, z-scores on different scales), so we STANDARDIZE
per feature on the TRAIN population before centroid projection -- otherwise the projection is
dominated by the large-scale features (e.g. leadlag in [-15, 15]) and the dipole degenerates.
This mirrors the per-feature z() in the v2 combined classifier (Markets CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .operators import windowed_operator_matrix
from .null_extract import analyze_coupling
from .leadlag import detect_leadlag
from .dipole_predictor import (
    algebraic_dipole_over_trades,
    build_centroids,
    dipole_direction,
    fit_algebraic_dipole,
    project,
    TradeDipoleFit,
)

FEATURE_NAMES: tuple[str, ...] = (
    "mi_frac", "chem_residual_frac", "eq_entropy_frac", "mi_slope", "mi_slope_r2",
    "mi_mean", "mi_var", "singular_gap", "dipole_a", "dipole_b", "dipole_c", "dipole_r2",
    "leadlag", "leadlag_cc", "leadlag_z",
)


def trade_coupling_vector(a, b, window: int = 40, stride: int = 10, max_lag: int = 15,
                          leadlag_nnull: int = 50, seed: int = 0):
    """Run the 5-step coupling model on one trade's aligned pre-entry channels -> c_i.

    a, b: 1-D arrays of the pair's two channels over [entry_ts - pre_entry, entry_ts],
    already materialized + conditioned (odcore.channels.materialize). Returns a
    (len(FEATURE_NAMES),) float vector, or None if the window is too short.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    M = windowed_operator_matrix(a, b, window=window, stride=stride, seed=seed)
    if M.shape[0] < 5:
        return None
    v = analyze_coupling(M)
    fit = fit_algebraic_dipole(M)
    try:
        ll = detect_leadlag(a, b, max_lag=max_lag, n_null=leadlag_nnull, seed=seed)
        lag, cc, z = float(ll.lag), float(ll.cc), float(ll.z)
    except Exception:
        lag, cc, z = 0.0, 0.0, 0.0
    return np.array([
        v.mi_frac, v.chem_residual_frac, v.eq_entropy_frac, v.mi_slope, v.mi_slope_r2,
        v.mi_mean, v.mi_var, v.singular_gap, fit.a, fit.b, fit.c, fit.r2,
        lag, cc, z,
    ], dtype=float)


@dataclass
class Standardizer:
    mean: np.ndarray
    std: np.ndarray

    def transform(self, C) -> np.ndarray:
        return (np.asarray(C, dtype=float) - self.mean) / self.std

    @classmethod
    def fit(cls, C) -> "Standardizer":
        C = np.asarray(C, dtype=float)
        mu = C.mean(axis=0)
        sd = C.std(axis=0)
        sd = np.where(sd < 1e-12, 1.0, sd)
        return cls(mean=mu, std=sd)


@dataclass
class TradeDipoleModel:
    fit: TradeDipoleFit
    standardizer: Standardizer
    c_win: np.ndarray
    c_lose: np.ndarray
    feature_names: tuple[str, ...]


def build_trade_vectors(trades, window: int = 40, stride: int = 10, max_lag: int = 15,
                        seed: int = 0):
    """trades: iterable of (a, b, label). Returns (C, labels), dropping too-short windows.
    label: >0 win, <=0 lose."""
    vecs: list[np.ndarray] = []
    labs: list[int] = []
    for a, b, lab in trades:
        c = trade_coupling_vector(a, b, window=window, stride=stride, max_lag=max_lag, seed=seed)
        if c is None:
            continue
        vecs.append(c)
        labs.append(1 if lab > 0 else -1)
    if not vecs:
        return np.empty((0, len(FEATURE_NAMES))), np.empty((0,))
    return np.vstack(vecs), np.asarray(labs)


def fit_trade_dipole(trades, window: int = 40, stride: int = 10, max_lag: int = 15,
                     seed: int = 0) -> TradeDipoleModel:
    """IN-SAMPLE fit (reproduces the original's report). Build c_i per trade, standardize,
    build centroids, fit the algebraic dipole. Returns a TradeDipoleModel.

    For an HONEST predictor use walk-forward centroids (fit standardizer + centroids on the
    train fold only, project the test fold) and validate via odcore/validation.py -- see the
    S22 runner spec. In-sample R^2 here is a STRUCTURAL check, not an edge.
    """
    C, labels = build_trade_vectors(trades, window=window, stride=stride, max_lag=max_lag, seed=seed)
    if C.shape[0] < 4:
        raise ValueError(f"need >=4 usable trades to fit the dipole, got {C.shape[0]}")
    std = Standardizer.fit(C)
    Cz = std.transform(C)
    fit = algebraic_dipole_over_trades(Cz, labels)
    c_win, c_lose = build_centroids(Cz, labels)
    return TradeDipoleModel(fit=fit, standardizer=std, c_win=c_win, c_lose=c_lose,
                            feature_names=FEATURE_NAMES)


def predict(model: TradeDipoleModel, a, b, window: int = 40, stride: int = 10,
            max_lag: int = 15, seed: int = 0) -> int:
    """Per-trade WIN(+1)/LOSE(-1) prediction from a fitted TradeDipoleModel (0 if unusable)."""
    c = trade_coupling_vector(a, b, window=window, stride=stride, max_lag=max_lag, seed=seed)
    if c is None:
        return 0
    cz = model.standardizer.transform(c.reshape(1, -1)).ravel()
    Ha, Hb = project(cz, model.c_win, model.c_lose)
    return dipole_direction(Ha, Hb)
