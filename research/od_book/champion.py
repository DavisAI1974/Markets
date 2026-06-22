"""
champion.py — the strong classical baseline for OD-BOOK.

VAR(p) and ridge one-step linear predictors on x(t). Hand-rolled in numpy (no
statsmodels dep) so the estimated operator is directly comparable to the DMD
challenger: VAR(1) least-squares IS the regression operator x(t+1) ~ A x(t) + c,
and exact-DMD recovers the same map through a different (spectral, rank-truncated)
lens. The experiment is precisely whether the spectral/operator framing buys
anything over this.

Standardization is fit on TRAIN ONLY (means/stds), then applied to val/test — no
leakage. Forecast skill is reported as OUT-OF-SAMPLE R² per component, where the
naive baseline for R² is "persistence" (x(t+Δ) = x(t)) — i.e. R²>0 means beating
the last-observed value, the honest bar for a short-horizon forecaster.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LinearForecaster:
    """x(t+1) ~ A·[lags] + c, fit by (ridge) least squares. Multi-step by
    iterating the one-step operator (VAR(1)) or by direct h-step regression."""
    A: np.ndarray            # (D, D*p) coefficient blocks
    c: np.ndarray            # (D,) intercept
    p: int                   # lag order
    mu: np.ndarray           # (D,) train mean (standardization)
    sd: np.ndarray           # (D,) train std
    kind: str = "var"

    def _z(self, X):
        return (X - self.mu) / self.sd

    def _unz(self, Z):
        return Z * self.sd + self.mu


def _design(Z: np.ndarray, p: int):
    """Build lagged design: returns (Phi, Y) where row t predicts Z[t] from the p
    previous rows. Phi has columns [Z[t-1] ... Z[t-p]]."""
    n, d = Z.shape
    rows_X, rows_Y = [], []
    for t in range(p, n):
        lags = np.concatenate([Z[t - k] for k in range(1, p + 1)])
        rows_X.append(lags)
        rows_Y.append(Z[t])
    return np.asarray(rows_X), np.asarray(rows_Y)


def fit_var(X: np.ndarray, p: int = 1, alpha: float = 0.0) -> LinearForecaster:
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    Phi, Y = _design(Z, p)
    # ridge least squares: W = (Phi'Phi + alpha I)^-1 Phi'Y  (with intercept col)
    Phi1 = np.hstack([Phi, np.ones((Phi.shape[0], 1))])
    G = Phi1.T @ Phi1
    reg = alpha * np.eye(G.shape[0])
    reg[-1, -1] = 0.0  # don't penalize intercept
    W = np.linalg.solve(G + reg, Phi1.T @ Y)   # (D*p+1, D)
    A = W[:-1].T                                 # (D, D*p)
    c = W[-1]                                    # (D,)
    return LinearForecaster(A=A, c=c, p=p, mu=mu, sd=sd, kind=f"var{p}")


def forecast_path(model: LinearForecaster, hist: np.ndarray, horizon: int) -> np.ndarray:
    """Iterate the one-step operator `horizon` steps. `hist` is the last p raw
    states (>= p rows). Returns the raw-space predicted state at t+horizon."""
    Z = model._z(hist)
    buf = [Z[-k] for k in range(1, model.p + 1)]  # most-recent-first
    pred_z = None
    for _ in range(horizon):
        lags = np.concatenate(buf)
        pred_z = model.A @ lags + model.c
        buf = [pred_z] + buf[:-1]
    return model._unz(pred_z)


def oos_r2(model: LinearForecaster, X: np.ndarray, horizon: int,
           cols: list[str]) -> dict:
    """Walk the test block, predict x(t+horizon) from states up to t, score R² per
    component vs persistence (x(t+h)=x(t))."""
    n = X.shape[0]
    preds, truth, persist = [], [], []
    for t in range(model.p - 1, n - horizon):
        hist = X[max(0, t - model.p + 1): t + 1]
        if hist.shape[0] < model.p:
            continue
        preds.append(forecast_path(model, hist, horizon))
        truth.append(X[t + horizon])
        persist.append(X[t])
    if not preds:
        return {}
    P = np.asarray(preds); T = np.asarray(truth); B = np.asarray(persist)
    out = {}
    for j, name in enumerate(cols):
        ss_res = np.sum((T[:, j] - P[:, j]) ** 2)
        ss_base = np.sum((T[:, j] - B[:, j]) ** 2)  # persistence baseline
        out[name] = float("nan") if ss_base == 0 else 1.0 - ss_res / ss_base
    out["_n"] = len(preds)
    return out
