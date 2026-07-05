"""dipole_trend_gate.py — arm-point TREND/MOMENTUM read for the mid-band machine (S62 research).

At a leg's ARM point (leg gone -Xarm underwater), decide whether the adverse move is a
CONTINUING trend (-> FLIP, follow it, the leg would DIE) or an EXHAUSTING/choppy move
(-> FLATTEN/HOLD, the leg would RECOVER). Depth/price/coeff are ~chance here; this module
asks whether the DIPOLE FLOW read separates DEATH from RECOVERY.

Strictly causal: every read uses only cells <= the arm cell aj, over the in-leg window [ci, aj]
(or a trailing sub-window). price_drift is the RAW price change over the read window; the info
dipole's aligned_flow = imb_level * sign(price_drift) then reads > 0 = flow CONFIRMS the move
(continuation/DEATH) and < 0 = flow OPPOSES (reversal/RECOVERY).

Pure numpy + odcore.info_dipole/quiet_floor. The caller passes the leg's own buy/sell arrays.
"""
from __future__ import annotations

import sys
import numpy as np

sys.path.insert(0, '/home/user/Markets')
from odcore.info_dipole import divergence, signed_flow_features, _imbalance  # noqa: E402


def _er(x: np.ndarray) -> float:
    """Kaufman efficiency ratio: |net displacement| / path length. 1 = smooth trend, 0 = chop."""
    x = np.asarray(x, float)
    if x.size < 2:
        return 0.0
    path = np.abs(np.diff(x)).sum()
    return abs(x[-1] - x[0]) / path if path > 0 else 0.0


def arm_trend_reads(mid, buy, sell, ci, aj, side, trail=(0, 60, 120)):
    """All arm-point trend reads for one leg. Returns a flat dict of scalar features.

    mid/buy/sell : full 1-sec arrays. ci = entry idx, aj = arm idx, side = +1/-1 position.
    trail : trailing window lengths in seconds; 0 = the whole [ci, aj] leg window.

    Every feature is oriented so that HIGHER == more CONTINUATION (more likely DEATH). The
    info-dipole aligned_flow already has that polarity (flow confirming the adverse move).
    """
    out = {}
    pricewin = mid[ci:aj + 1]
    # raw price change over the whole leg window (the ADVERSE move; sign = -side by construction)
    pdrift_full = float(np.log(mid[aj] + 1e-12) - np.log(mid[ci] + 1e-12))
    price_dir = 1.0 if pdrift_full > 0 else -1.0        # direction of the adverse move

    for w in trail:
        if w <= 0:
            s = ci
        else:
            s = max(ci, aj - w)
        b = buy[s:aj + 1]
        sv = sell[s:aj + 1]
        pw = mid[s:aj + 1]
        pdrift = float(np.log(mid[aj] + 1e-12) - np.log(mid[s] + 1e-12))
        tag = 'full' if w <= 0 else f't{w}'

        d = divergence(b, sv, pdrift if pdrift != 0 else pdrift_full)
        if d is not None:
            # aligned_flow: >0 flow confirms move (continuation), <0 opposes (reversal)
            out[f'aligned_{tag}'] = d['aligned_flow']
            out[f'revconv_{tag}'] = d['reversal_conviction']   # high = reversal expected
            out[f'exhaust_{tag}'] = 1.0 if d['exhausting'] else 0.0
            out[f'opposing_{tag}'] = 1.0 if d['opposing'] else 0.0
        else:
            out[f'aligned_{tag}'] = 0.0
            out[f'revconv_{tag}'] = 0.0
            out[f'exhaust_{tag}'] = 0.0
            out[f'opposing_{tag}'] = 0.0

        # raw taker lean of the window, oriented to the adverse-move direction
        lean = _imbalance(b, sv)                 # buy-pressure imbalance (signed)
        out[f'lean_{tag}'] = lean * price_dir    # >0 = flow pushing the adverse move (continuation)

        # early-vs-late imbalance flow (acceleration of the lean), oriented to the move
        f = signed_flow_features(b, sv)
        if f is not None:
            out[f'imbflow_{tag}'] = f['imb_flow'] * price_dir   # >0 = lean strengthening w/ the move
            out[f'miflow_{tag}'] = f['mi_flow'] * price_dir
        else:
            out[f'imbflow_{tag}'] = 0.0
            out[f'miflow_{tag}'] = 0.0

        # price efficiency of the window (smooth trend vs chop) — a PRICE trend read, comparison
        out[f'er_{tag}'] = _er(pw)

        # RAW net one-sided taker volume in the adverse/trend direction (magnitude, not normalized).
        # A steady strong trend sustains large absolute one-sided pressure -> best single read.
        out[f'netmag_{tag}'] = float((b.sum() - sv.sum()) * price_dir)
        # persistence: fraction of 10s chunks whose lean points with the adverse move
        Wc = 10
        nch = max(1, (aj - s) // Wc)
        pc = 0
        for j in range(nch):
            cb = b[j * Wc:(j + 1) * Wc].sum(); cs = sv[j * Wc:(j + 1) * Wc].sum()
            if (cb - cs) * price_dir > 0:
                pc += 1
        out[f'persist_{tag}'] = pc / nch

    return out


def continuation_score(reads: dict, feature: str = 'lean_t120') -> float:
    """The single arm-point continuation score to gate on (higher = FLIP/follow the trend)."""
    return float(reads.get(feature, 0.0))
