"""odcore/flip_detector.py — causal swing FLIP detector on the directional flow lean (S40).

What we learned reverse-engineering the turn (S40):
  - the edge is the FLOW's directional asymmetry, NOT price (price near a turn is ~99.6% symmetric).
  - the turn = where the trailing-W flow LEAN reverses (its vertex); price is just the timing scaffold.
  - the chop near the turn is the losing side fighting to restart momentum (Greg) — so the reversal
    threshold is a "did the defense fail" gate, not a noise filter.

Detector (CAUSAL by construction -> passes odcore.leakage):
  lean[t] = trailing-W taker (buy-sell)/(buy+sell), using only data <= t.
  ZigZag on the lean: hold a direction, track the running extremum; when the lean RETRACES past `reversal`
  from that extremum, the prior extremum was a pivot -> FLIP to the new side, entering at the confirmation
  second (which is `reversal`-worth past the true pivot = the realistic timing lag).
"""
from __future__ import annotations
import numpy as np


def lean_series(bv: np.ndarray, sv: np.ndarray, W: int) -> np.ndarray:
    """Trailing-W net taker flow imbalance at each second (causal). +buying / -selling."""
    cb = np.concatenate([[0.0], np.cumsum(bv)]); cs = np.concatenate([[0.0], np.cumsum(sv)])
    n = len(bv); ix = np.arange(n)
    lo = np.maximum(ix + 1 - W, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    out = np.zeros(n)
    nz = tot > 0
    out[nz] = (B[nz] - S[nz]) / tot[nz]
    return out


def detect_flips(lean: np.ndarray, reversal: float):
    """Causal ZigZag on the lean. Returns (flips, pos):
       flips = list of (confirm_idx, pivot_idx, side)  side +1 long / -1 short
       pos   = side held at each t (0 before the first flip)."""
    n = len(lean)
    pos = np.zeros(n, dtype=np.int8)
    flips = []
    d = 1; ext = lean[0]; exti = 0; cur = 0
    for t in range(1, n):
        x = lean[t]
        if d == 1:                                  # seeking a HIGH in the lean (buying climax -> short turn)
            if x > ext:
                ext = x; exti = t
            elif x <= ext - reversal:               # lean rolled over -> price peak -> SHORT
                flips.append((t, exti, -1)); cur = -1; d = -1; ext = x; exti = t
        else:                                       # seeking a LOW (selling climax -> long turn)
            if x < ext:
                ext = x; exti = t
            elif x >= ext + reversal:               # lean turned up -> price valley -> LONG
                flips.append((t, exti, 1)); cur = 1; d = 1; ext = x; exti = t
        pos[t] = cur
    return flips, pos


def backtest_swings(mid: np.ndarray, flips, fee_bps: float):
    """Flip-at-each-turn swing P&L, net of a per-swing round-trip fee. Returns dict of stats."""
    if len(flips) < 2:
        return dict(n=0, net=0.0, mean=0.0, pos_frac=0.0, lag_bps=0.0, gross=0.0)
    pnl = []; lag = []
    for k in range(len(flips) - 1):
        ci, pv, side = flips[k]; nci = flips[k + 1][0]
        if mid[ci] <= 0 or mid[nci] <= 0:
            continue
        gross = side * np.log(mid[nci] / mid[ci]) * 1e4      # ride to the next opposite turn
        pnl.append(gross - fee_bps)
        if mid[pv] > 0:
            lag.append(abs(np.log(mid[ci] / mid[pv]) * 1e4))  # bps entered PAST the true pivot
    pnl = np.array(pnl)
    return dict(n=len(pnl), net=float(pnl.sum()), mean=float(pnl.mean()) if len(pnl) else 0.0,
                pos_frac=float((pnl > 0).mean()) if len(pnl) else 0.0,
                lag_bps=float(np.mean(lag)) if lag else 0.0,
                gross=float((pnl + fee_bps).mean()) if len(pnl) else 0.0)


def make_signal_at(W: int, reversal: float):
    """signal_at(i, ts, p, bv, sv) -> current side as of i (for odcore.leakage; recomputes causally)."""
    def signal_at(i, ts, p, bv, sv):
        i = int(i)
        if i < W:
            return 0
        ln = lean_series(np.asarray(bv[:i + 1], float), np.asarray(sv[:i + 1], float), W)
        _, pos = detect_flips(ln, reversal)
        return int(pos[-1])
    return signal_at
