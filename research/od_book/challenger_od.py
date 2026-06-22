"""
challenger_od.py — the OD challenger: operator recovery via exact-DMD.

OD's native mode is *recovering the governing operator* of a system's dynamics
from raw data (the piecewise Liouvillian on QD3SET-1, the blind Lindblad channel),
not classifying. Here we recover the operator A such that the book state evolves
z(t+h) ≈ A·z(t), via exact Dynamic Mode Decomposition with rank truncation. DMD
returns not just a one-step map but its SPECTRUM (eigenvalues = growth/decay +
oscillation of dynamic modes) and the modes themselves — the interpretable object
the spec asks for. If A collapses to the VAR coefficient matrix, that is itself the
informative result (OD found nothing the linear model didn't).

The fitted object is interface-compatible with champion.LinearForecaster (p=1,
intercept folded into the standardized mean), so champion.oos_r2/forecast_path
score both competitors identically. Eigenvalues are attached for the
spectrum-stability KILL-gate diagnostic.

Standardization (mu/sd) is fit on TRAIN ONLY.
"""

from __future__ import annotations

import numpy as np

from champion import LinearForecaster


def fit_dmd(X: np.ndarray, rank: int | None = None, h: int = 1,
            energy: float = 0.999) -> LinearForecaster:
    """Exact DMD of the h-step map on standardized states.

    rank: truncation rank; if None, choose smallest r capturing `energy` of the
    singular-value spectrum (capped at D).
    """
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd                  # (N, D)
    Xm = Z[:-h].T                       # (D, m) state at t
    Xp = Z[h:].T                        # (D, m) state at t+h
    D = Xm.shape[0]

    U, S, Vt = np.linalg.svd(Xm, full_matrices=False)
    if rank is None:
        cum = np.cumsum(S ** 2) / np.sum(S ** 2)
        rank = int(np.searchsorted(cum, energy) + 1)
    rank = max(1, min(rank, D, len(S)))
    Ur = U[:, :rank]
    Sr = S[:rank]
    Vr = Vt[:rank].T

    # reduced operator A_tilde = Ur* Xp Vr Sr^-1  (rank x rank)
    A_tilde = Ur.T @ Xp @ Vr @ np.diag(1.0 / Sr)
    eigs, W = np.linalg.eig(A_tilde)   # DMD spectrum + reduced eigenvectors

    # full-space one-step operator in the standardized basis
    A_r = (Ur @ A_tilde @ Ur.T).real   # (D, D)

    model = LinearForecaster(
        A=A_r, c=np.zeros(D), p=1, mu=mu, sd=sd, kind=f"dmd_r{rank}",
    )
    # attach DMD diagnostics
    model.eigs = eigs                  # type: ignore[attr-defined]
    model.rank = rank                  # type: ignore[attr-defined]
    model.sv = S                       # type: ignore[attr-defined]
    return model


def spectrum_summary(model) -> dict:
    """Compact summary of the DMD spectrum for the stability diagnostic."""
    eigs = getattr(model, "eigs", None)
    if eigs is None:
        return {}
    mod = np.abs(eigs)
    return {
        "rank": int(getattr(model, "rank", len(eigs))),
        "n_eigs": int(len(eigs)),
        "max_modulus": float(mod.max()),
        "n_unstable": int(np.sum(mod > 1.0 + 1e-9)),   # |lambda|>1 = growing mode
        "spectral_radius": float(mod.max()),
        "slowest_decay": float(np.sort(mod)[-min(3, len(mod)):].mean()),
    }
