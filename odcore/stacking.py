"""
odcore/stacking.py — compose multiple OD operators into one stacked signal.

RECONSTRUCTED-FROM-CLAUDE.md (would-be port of _markets_dipole_chunker_stack.py). The log's
"they never stacked" rule (l.124): the edge is in COMBINING pieces others used singly. Here a
stack composes per-bar signal arrays (from generators.py) into one signal, optionally GATED by
the coupling structure (only fire the directional dipole when the channels are currently coupled).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class OperatorSpec:
    name: str
    signal: np.ndarray            # per-bar signal in {-1,0,+1}
    weight: float = 1.0
    gate: np.ndarray | None = None  # optional per-bar boolean gate (trade only where True)


def _aligned(specs: list[OperatorSpec]) -> int:
    return min(len(s.signal) for s in specs)


def stack(specs: list[OperatorSpec], combine: str = "weighted_sign") -> np.ndarray:
    """Combine operator signals into one per-bar signal in {-1,0,+1}.

    combine:
      - "weighted_sign":  sign of the weighted sum of the (gated) signals.
      - "majority_vote":  sign of the count of agreeing (gated) signals.
      - "unanimous":      fire only when all non-zero (gated) signals agree.
    """
    n = _aligned(specs)
    mat = np.zeros((len(specs), n))
    for i, s in enumerate(specs):
        sig = np.asarray(s.signal[:n], dtype=float)
        if s.gate is not None:
            sig = np.where(np.asarray(s.gate[:n], dtype=bool), sig, 0.0)
        mat[i] = sig * (s.weight if combine == "weighted_sign" else 1.0)

    if combine == "weighted_sign":
        agg = mat.sum(axis=0)
        return np.sign(agg)
    if combine == "majority_vote":
        agg = np.sign(mat).sum(axis=0)
        return np.sign(agg)
    if combine == "unanimous":
        signs = np.sign(mat)
        nonzero = signs != 0
        out = np.zeros(n)
        for t in range(n):
            nz = signs[nonzero[:, t], t]
            if nz.size and np.all(nz == nz[0]):
                out[t] = nz[0]
        return out
    raise ValueError(combine)


def coupling_gate(coupling_series: np.ndarray, threshold: float, bars: int,
                  step: int) -> np.ndarray:
    """Expand a rolling-coupling series (one value per `step` bars) to a per-bar boolean
    gate that is True where coupling >= threshold (only trade when structurally coupled)."""
    n = bars
    gate = np.zeros(n, dtype=bool)
    for i, c in enumerate(coupling_series):
        lo = i * step
        hi = min(n, lo + step)
        gate[lo:hi] = c >= threshold
    return gate
