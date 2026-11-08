"""Run the imported fitters through the Markets leakage gate (odcore/leakage.py).

CLAUDE.md: the leakage gate is mandatory before ANY backtest. The review's
tests-remaining matrix lists "run imported fitters through
odcore.leakage.assert_no_leakage" as NOT-RUN. This module does two things:

1. `frame_permutation_gate`: the same test the Markets gate performs, applied
   natively to InfoFrame series: a signal computed "as of frame i" must be
   invariant when EVERY field of every frame after i is permuted.
2. `odcore_gate`: the literal Markets function, fed the three-array projection
   (p = target entropy, bv = donor entropy, sv = pair MI, ts = clocks) with the
   InfoFrames rebuilt from the arrays inside the signal, so the gate that the
   rest of Markets trusts is the one that judges these fitters too.

Signals offered: the directional operator row at i (same-clock and past-lag
donor), and the FULL library coefficients trained on intervals [lag, i-1). A
deliberately leaking signal is provided so a test can prove the gate bites.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Sequence

import numpy as np

from adaptive_locality.core import LocalityError
from adaptive_locality.information import InfoFrame
from adaptive_locality.coupling import (_operator_row, _series_rows, _qr_fit, FULL,
                                        chronological_partition)
from odcore.leakage import assert_no_leakage


def operator_row_signal(target: str, donor: str, lag: int = 0) -> Callable:
    def signal(frames: Sequence[InfoFrame], i: int):
        if i - lag < 0:
            return None
        return tuple(round(v, 12) for v in _operator_row(tuple(frames), i, target, donor, -lag))
    return signal


def training_coefficients_signal(target: str, donor: str) -> Callable:
    """Coefficients of the FULL fit using only frames[:i+1]; intervals [lag, i-1)."""
    def signal(frames: Sequence[InfoFrame], i: int):
        prefix = tuple(frames)[:i + 1]
        if len(prefix) < 2 * len(FULL) + 6:
            return None
        lag = chronological_partition(len(frames))[0]
        rows, y = _series_rows(prefix, target, donor, start_index=lag)
        if len(rows) < 2 * len(FULL):
            return None
        try:
            fit = _qr_fit(rows, y, FULL)
        except LocalityError as exc:
            return ("ABSTAIN", str(exc))
        return tuple(round(v, 10) for _, v in fit.coefficients)
    return signal


def leaking_signal(target: str) -> Callable:
    """Deliberately peeks at frame i+1; must FAIL both gates."""
    def signal(frames: Sequence[InfoFrame], i: int):
        frames = tuple(frames)
        if i + 1 >= len(frames):
            return None
        return round(dict(frames[i + 1].entropy)[target], 12)
    return signal


def frame_permutation_gate(frames: Sequence[InfoFrame], signal: Callable,
                           idxs: Sequence[int], *, reps: int = 3, seed: int = 0) -> tuple[bool, list]:
    """Permute whole frames after i (every field moves together); require signal unchanged."""
    frames = tuple(frames)
    rng = np.random.default_rng(seed)
    fails = []
    for i in idxs:
        clean = signal(frames, i)
        for _ in range(reps):
            tail = list(frames[i + 1:])
            if len(tail) > 1:
                order = rng.permutation(len(tail))
                tail = [tail[j] for j in order]
            # keep clocks monotone so the permuted series is still a legal series
            shuffled = frames[:i + 1] + tuple(replace(f, clock=frames[i + 1 + j].clock)
                                              for j, f in enumerate(tail))
            dirty = signal(shuffled, i)
            if dirty != clean:
                fails.append((int(i), clean, dirty))
                break
    return (len(fails) == 0, fails)


def odcore_gate(frames: Sequence[InfoFrame], target: str, donor: str, signal: Callable,
                idxs: Sequence[int], *, reps: int = 3, seed: int = 0) -> tuple[bool, list]:
    """The literal Markets gate on the (Ha, Hb, MI) projection of the series."""
    frames = tuple(frames)
    pair = tuple(sorted((target, donor)))
    ts = np.array([f.clock for f in frames], dtype=float)
    p = np.array([dict(f.entropy)[target] for f in frames], dtype=float)
    bv = np.array([dict(f.entropy)[donor] for f in frames], dtype=float)
    sv = np.array([{(a, b): v for a, b, v in f.mi}[pair] for f in frames], dtype=float)

    def rebuild(p2, bv2, sv2):
        out = []
        for f, ha, hb, mi in zip(frames, p2, bv2, sv2):
            entropy = tuple((n, float(ha) if n == target else float(hb) if n == donor else v)
                            for n, v in f.entropy)
            mutual = tuple((a, b, float(mi) if (a, b) == pair else v) for a, b, v in f.mi)
            out.append(replace(f, entropy=entropy, mi=mutual))
        return tuple(out)

    def signal_at(i, ts_, p2, bv2, sv2):
        return signal(rebuild(p2, bv2, sv2), int(i))

    return assert_no_leakage(signal_at, ts, p, bv, sv, list(idxs), reps=reps, seed=seed)
