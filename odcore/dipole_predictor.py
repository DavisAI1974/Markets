"""
odcore/dipole_predictor.py — the PRIMARY signal: the static algebraic (chem) dipole.

PORT NOTE (S22, 2026-06-07): the previous version computed H_a/H_b as windowed Vasicek
entropies of buy/sell volume. That was a RECONSTRUCTION guess and it is WRONG -- it is the
whole reason the quadratic coefficient collapsed to c~=0 (buy/sell window entropies are
near-symmetric -> H_a ~= H_b -> the regressor H_a*H_b is collinear with the response H_a^2,
so gamma is unidentified). Epistemic rule #4 (S19): a uniform-low result is as much evidence
the TOOL is wrong as that structure is absent.

The verbatim original (_markets_algebraic_dipole.py, recovered from E:\\Markets) defines:

    H_a_i = <c_i, c_win_centroid> / ||c_win_centroid||     # alignment with winners
    H_b_i = <c_i, c_lose_centroid> / ||c_lose_centroid||   # alignment with losers
    fit   H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2          # per pair + pooled

where c_i is a PER-TRADE operator-coefficient vector and the centroids are built from
labeled win/lose trades. This module now carries that construction (build_centroids /
project / algebraic_dipole_over_trades) -- verbatim in the math. The per-trade c_i for the
current platform is assembled in dipole_trade.py from the 5-step coupling model.

The legacy window-based fit_algebraic_dipole(M) is KEPT (coupling_scanner imports it) as a
descriptive operator-matrix fit; it is NOT the predictor.

Reference coeffs the construction should reproduce: a=0.007, b=-0.093, c=1.309, R^2 0.943
(chemistry-tier; INFO-044). RESULT DISCIPLINE: a high algebraic R^2 is a STRUCTURAL property
of projecting onto in-sample centroids, NOT a net-of-cost edge. The directional / combined
predictor must clear odcore/validation.py (net>0 after fees+slip, walk-forward, tautology z)
before any promotion. S20/S21: the predictor loses net-of-cost on the unblocked pieces.
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


def _polyfit_r2(x: np.ndarray, y: np.ndarray, degree: int) -> tuple[np.ndarray, float]:
    """Least-squares y = sum_k coef[k] * x^k (coef ascending). Returns (coef, R^2)."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = x.size
    if n == 0:
        return np.zeros(degree + 1), 0.0
    X = np.vander(x, degree + 1, increasing=True)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return coef, r2


def fit_algebraic_dipole(M: np.ndarray) -> DipoleFit:
    """LEGACY (descriptive): fit H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2 over the WINDOW
    ensemble from the 6-col operator matrix. Kept for coupling_scanner; not the predictor."""
    M = np.asarray(M, dtype=float)
    y = M[:, COL["H_a^2"]]
    p = M[:, COL["H_a*H_b"]]
    coef, r2 = _polyfit_r2(p, y, 2)
    return DipoleFit(a=float(coef[0]), b=float(coef[1]), c=float(coef[2]), r2=r2, n=int(M.shape[0]))


def dipole_direction(H_a: float, H_b: float) -> int:
    """Directional rule: H_a > H_b => +1 (winner-aligned), else -1."""
    return 1 if H_a > H_b else -1


# --------------------------------------------------------------------------- #
# The REAL construction: per-trade centroid-projection algebraic dipole
# (verbatim port of _markets_algebraic_dipole.py)
# --------------------------------------------------------------------------- #

@dataclass
class TradeDipoleFit:
    a: float
    b: float
    c: float
    r2_lin: float
    r2_quad: float
    n_win: int
    n_lose: int


def build_centroids(C: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean winner / loser coefficient vectors. labels: >0 win, <=0 lose."""
    C = np.asarray(C, dtype=float)
    labels = np.asarray(labels)
    win = C[labels > 0]
    lose = C[labels <= 0]
    d = C.shape[1] if C.ndim == 2 and C.shape[1] else 1
    c_win = win.mean(axis=0) if win.shape[0] else np.zeros(d)
    c_lose = lose.mean(axis=0) if lose.shape[0] else np.zeros(d)
    return c_win, c_lose


def project(c: np.ndarray, c_win: np.ndarray, c_lose: np.ndarray) -> tuple[float, float]:
    """H_a = <c, c_win>/||c_win||, H_b = <c, c_lose>/||c_lose||  (verbatim original)."""
    nw = float(np.linalg.norm(c_win)) or 1.0
    nl = float(np.linalg.norm(c_lose)) or 1.0
    Ha = float(np.dot(c, c_win) / nw)
    Hb = float(np.dot(c, c_lose) / nl)
    return Ha, Hb


def algebraic_dipole_over_trades(C: np.ndarray, labels: np.ndarray) -> TradeDipoleFit:
    """Verbatim _markets_algebraic_dipole.py: build in-sample win/lose centroids, project
    every trade to (H_a, H_b), fit H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2 (linear + quad).

    C: (n_trades, d) per-trade coefficient vectors. labels: >0 win, <=0 lose.
    NOTE: in-sample centroids reproduce the ORIGINAL's report. For an honest predictor use
    walk-forward centroids (fit on the train fold only; project the test fold) and validate
    via odcore/validation.py. In-sample R^2 here is a STRUCTURAL check, not an edge.
    """
    C = np.asarray(C, dtype=float)
    labels = np.asarray(labels)
    c_win, c_lose = build_centroids(C, labels)
    xs = np.empty(C.shape[0])
    ys = np.empty(C.shape[0])
    for i in range(C.shape[0]):
        Ha, Hb = project(C[i], c_win, c_lose)
        xs[i] = Ha * Hb
        ys[i] = Ha * Ha
    _, r2_lin = _polyfit_r2(xs, ys, 1)
    coef_q, r2_quad = _polyfit_r2(xs, ys, 2)
    return TradeDipoleFit(a=float(coef_q[0]), b=float(coef_q[1]), c=float(coef_q[2]),
                          r2_lin=r2_lin, r2_quad=r2_quad,
                          n_win=int((labels > 0).sum()), n_lose=int((labels <= 0).sum()))


def predict_direction(c: np.ndarray, c_win: np.ndarray, c_lose: np.ndarray) -> int:
    """Per-trade WIN(+1)/LOSE(-1) call via the directional rule on projected H_a/H_b."""
    Ha, Hb = project(c, c_win, c_lose)
    return dipole_direction(Ha, Hb)


if __name__ == "__main__":
    # NUMERICAL METHOD CHECK (not market data): the poly fit recovers known coefficients,
    # and a winner-aligned vector projects to H_a > H_b. Pure linear-algebra correctness.
    x = np.linspace(-2.0, 2.0, 200)
    y = 0.007 - 0.093 * x + 1.309 * x * x
    coef, r2 = _polyfit_r2(x, y, 2)
    assert abs(coef[0] - 0.007) < 1e-6 and abs(coef[1] + 0.093) < 1e-6 and abs(coef[2] - 1.309) < 1e-6
    assert r2 > 0.999999
    C = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])
    labels = np.array([1, 1, -1, -1])
    cw, cl = build_centroids(C, labels)
    Ha, Hb = project(np.array([1.0, 0.0]), cw, cl)
    assert Ha > Hb
    fit = algebraic_dipole_over_trades(C, labels)
    print(f"dipole_predictor self-check OK: poly recovery exact (R2={r2:.6f}); "
          f"projection direction correct; trade-fit c={fit.c:+.3f} r2_quad={fit.r2_quad:.3f}")
