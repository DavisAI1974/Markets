"""odcore/quiet_floor.py — the QUIET relaxation floor (portable, numpy-only). S42.

Chat's OD book run (research/od_book/chat_runs/OD_book_run_1.docx) found the book-depth imbalance
obeys a clean AR(1) RELAXATION that is QUIET AND STILL between trades:
    imb(t+1) = phi*imb(t) + c        quiet (n_trades=0): phi~0.94, the smooth decay toward the mean.

Greg (S42): use that quiet/still operator as a FLOOR to smooth the bumps out between trades, so the
directional dipole does not keep FIRING while it is merely trend-following (the imbalance LEVEL stays
elevated and slowly relaxes through a whole trend -> a raw-level trigger holds continuously / churns).

MECHANISM (validated on btc_coinbase, 11.67h, _quiet_floor.py):
  - DIRECTION lives in the imbalance LEVEL (next-cell hit ~62%). Do NOT replace it.
  - The FLOOR is the quiet AR(1) expectation  floor_hat(t) = phi_q*imb(t-1) + c_q.
  - The INNOVATION  innov(t) = imb(t) - floor_hat(t)  is small between trades (the floor absorbs the
    smooth relaxation: std ~0.15 quiet vs ~0.22 on trades) and spikes only when a real shock breaks
    the relaxation.
  - GATE the dipole on |innov| > k*sigma: it fires ~2.3x more on trade/shock cells than quiet cells,
    stays silent between trades, and the gated direction (sign of the LEVEL) keeps the ~62% edge
    (slightly sharper at k=2). Churn through trends is cut without losing direction.

LEAKAGE DISCIPLINE: fit() uses only the training slice (and only its quiet cells); sigma for the gate
is the innovation std on training. apply() is causal (floor_hat(t) uses imb(t-1)). Per-cell: fit one
QuietFloor per asset x venue x side (`deploy-signal-per-cell-not-universal`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EPS = 1e-12


@dataclass
class QuietFloor:
    phi: float          # quiet AR(1) relaxation coefficient
    c: float            # quiet AR(1) intercept
    sigma: float        # std of the innovation on the (quiet) training slice -> the gate scale
    r2_quiet: float     # OOS-style fit quality on quiet cells (diagnostic)
    n_quiet: int

    # -- apply (causal) --
    def floor_hat(self, imb: np.ndarray) -> np.ndarray:
        """The quiet relaxation expectation; floor_hat(t) = phi*imb(t-1)+c (causal, t=0 -> imb[0])."""
        out = np.empty_like(imb, dtype=float)
        out[0] = imb[0]
        out[1:] = self.phi * imb[:-1] + self.c
        return out

    def innovation(self, imb: np.ndarray) -> np.ndarray:
        """imb minus the quiet floor: ~0 between trades, spikes on shocks."""
        return imb - self.floor_hat(imb)

    def gate(self, imb: np.ndarray, k: float = 1.5) -> np.ndarray:
        """Boolean fire-gate: True only when the imbalance breaks the quiet floor by > k*sigma."""
        return np.abs(self.innovation(imb)) > k * (self.sigma + EPS)

    def gated_signal(self, imb: np.ndarray, k: float = 1.5) -> np.ndarray:
        """The deploy form: sign(level) for DIRECTION, but only where the gate is open; else 0 (stand
        aside). Smooths the between-trade bumps so the dipole stops firing while trend-following."""
        g = self.gate(imb, k)
        return np.where(g, np.sign(imb), 0.0)


def fit(imb: np.ndarray, quiet: np.ndarray, train_frac: float = 0.6) -> QuietFloor:
    """Fit the quiet relaxation floor on the TRAINING slice's quiet cells only (no look-ahead).

    imb   : depth-imbalance series (signed), one cell per snapshot.
    quiet : boolean mask, True where the cell had no taker volume / no trade (the 'still' cells).
    """
    imb = np.asarray(imb, float)
    quiet = np.asarray(quiet, bool)
    n = len(imb)
    cut = int(n * train_frac)
    t = np.arange(n - 1)
    # condition on the t+1 cell being quiet (we are modelling the quiet relaxation step)
    qnext = quiet[1:]
    tr = (t < cut) & qnext
    x0, x1 = imb[t][tr], imb[1:][tr]
    if x0.size < 50 or x0.std() < EPS:
        return QuietFloor(phi=0.0, c=float(imb.mean()), sigma=float(imb.std() + EPS),
                          r2_quiet=0.0, n_quiet=int(x0.size))
    A = np.vstack([x0, np.ones_like(x0)]).T
    (phi, c), *_ = np.linalg.lstsq(A, x1, rcond=None)
    # OOS-style R2 on held quiet cells
    te = (t >= cut) & qnext
    y0, y1 = imb[t][te], imb[1:][te]
    if y0.size > 10:
        pred = phi * y0 + c
        ss = np.sum((y1 - pred) ** 2); tot = np.sum((y1 - y1.mean()) ** 2) + EPS
        r2 = float(1 - ss / tot)
    else:
        r2 = 0.0
    # gate scale = innovation std on the training quiet cells
    floor = phi * imb[:cut][:-1] + c
    innov_tr = imb[:cut][1:] - floor
    sigma = float(innov_tr.std() + EPS)
    return QuietFloor(phi=float(phi), c=float(c), sigma=sigma, r2_quiet=r2, n_quiet=int(x0.size))
