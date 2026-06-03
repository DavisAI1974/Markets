"""
odcore/dipole_predictor.py — the PRIMARY signal: the static algebraic (chem) dipole.

RECONSTRUCTED-FROM-CLAUDE.md (would-be port of _markets_algebraic_dipole.py). Cites:
  - Algebraic dipole H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2; chemistry-preserved
    coeffs a=0.007, b=-0.093, c=1.309, R^2 0.943 (D / INFO-044 l.287).
  - Directional rule H_a > H_b (l.244).
  - PySR (symbolic.py) DISCOVERS this form from raw data; this module fits the
    coefficients once the form is chosen, and exposes the directional predictor.
  - S19 (INFO-065/066): the static algebraic dipole is the carrier; the entropy/flow
    dipole is blind. So this is the primary, not a fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .operators import COL


@dataclass
class DipoleFit:
    a: float
    b: float
    c: float
    r2: float
    n: int


def fit_algebraic_dipole(M: np.ndarray) -> DipoleFit:
    """Least-squares fit of H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2 over the window ensemble."""
    M = np.asarray(M, dtype=float)
    y = M[:, COL["H_a^2"]]
    p = M[:, COL["H_a*H_b"]]
    X = np.column_stack([np.ones_like(p), p, p * p])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return DipoleFit(a=float(coef[0]), b=float(coef[1]), c=float(coef[2]), r2=r2, n=M.shape[0])


def dipole_direction(H_a: float, H_b: float) -> int:
    """Directional rule: H_a > H_b => +1 (buy-side carries more info), else -1."""
    return 1 if H_a > H_b else -1
