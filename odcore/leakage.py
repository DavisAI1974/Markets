"""odcore/leakage.py — pre-entry leakage check: a signal computed AT t must be invariant to data AFTER t.

The Architect's mandatory discipline (S36b): every new signal gets this BEFORE it touches a backtest. The
algebraic-dipole 0.993 OOF / FN=0 is "exactly the shape leakage takes" — it does not enter the falsification
harness until it survives this. The test is model-agnostic: a leakage-free signal's value at index i cannot
change when you corrupt every data point AFTER i. If it does, the signal peeks at the future.
"""
from __future__ import annotations

import numpy as np


def _eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return a == b


def assert_no_leakage(signal_at, ts, p, bv, sv, idxs, reps=3, seed=0):
    """signal_at(i, ts, p, bv, sv) -> scalar/None 'as of i'. Corrupt all data AFTER i; require unchanged.

    Returns (passed: bool, fails: list of (i, v_clean, v_corrupt)). Empty fails = no look-ahead.
    """
    rng = np.random.default_rng(seed)
    fails = []
    for i in idxs:
        v0 = signal_at(i, ts, p, bv, sv)
        leaked = False
        for _ in range(reps):
            p2, bv2, sv2 = p.copy(), bv.copy(), sv.copy()
            j = i + 1
            if j < len(p):
                p2[j:] = rng.permutation(p2[j:])
                bv2[j:] = rng.permutation(bv2[j:])
                sv2[j:] = rng.permutation(sv2[j:])
            if not _eq(v0, signal_at(i, ts, p2, bv2, sv2)):
                fails.append((int(i), v0, signal_at(i, ts, p2, bv2, sv2))); leaked = True
                break
        if leaked:
            continue
    return (len(fails) == 0, fails)
