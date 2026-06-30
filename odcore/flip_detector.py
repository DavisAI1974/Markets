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


# ---------------------------------------------------------------------------------------------------------
# S47 job #2 — ENTRY TIMING: the S36b two-tool split (the kickoff's "biggest remaining edge").
#
# PROBLEM: detect_flips confirms a flip only after the lean RETRACES `reversal` past its extremum, and the
# executor posts the entry at that LATE confirm cell -> entries sit 6-10 bps off the true price extreme
# (the "money left on the table"). The lean is doing BOTH the FILTER (which turns are real + direction) AND
# the TIMING, so the timing lags.
#
# FIX (S36b): keep the lean as the FILTER (regime/direction); add a fast CAUSAL PRICE-REVERSAL as the
# TIMING. Within each lean regime we ARM for the side it is hunting (d==1 buying-climax -> hunt a peak/SHORT;
# d==-1 selling-climax -> hunt a valley/LONG) and FIRE the entry at the first price reversal -- price
# retraces `eps_bps` from the regime's running price extremum -> lands near the true turn, EARLIER than the
# lean's confirm (early-arm). If no price reversal fires before the lean confirms, we FALL BACK to entering
# at confirm (== the S46 baseline timing), so eps_bps -> inf recovers detect_flips exactly. The lean confirm
# still bounds the regime (lean-confirms / flips the hunted side). One entry per regime.
# CAUSAL by construction (every decision uses data <= t) -> passes odcore.leakage.assert_no_leakage.
# ---------------------------------------------------------------------------------------------------------
def retime_flips(mid: np.ndarray, bv: np.ndarray, sv: np.ndarray, W: int, reversal: float, eps_bps: float):
    """Early-arm + price-reversal entry timing. Returns (entries, pos):
       entries = list of (entry_idx, pivot_idx, side)  side +1 long / -1 short  (drop-in for the executor's
                 flip list -- entry_idx replaces confirm_idx so the executor posts EARLIER/nearer the extreme)
       pos     = held side per cell (for odcore.leakage)."""
    mid = np.asarray(mid, float)
    lean = lean_series(np.asarray(bv, float), np.asarray(sv, float), W)
    n = len(lean)
    pos = np.zeros(n, dtype=np.int8)
    entries: list = []
    if n < 2:
        return entries, pos
    d = 1; lean_ext = lean[0]; lean_exti = 0      # lean zigzag (== detect_flips) = the FILTER
    px_ext = mid[0]; fired = False; cur = 0       # regime price extremum + one-fire-per-regime guard
    eps = eps_bps / 1e4
    for t in range(1, n):
        x = lean[t]
        hunt = -1 if d == 1 else 1                # side this regime is hunting (peak->short / valley->long)
        # track the regime's running price extremum and test the price reversal for the hunted side
        if hunt < 0:
            if mid[t] > px_ext: px_ext = mid[t]
            reversed_ = px_ext > 0 and mid[t] <= px_ext * (1.0 - eps)
        else:
            if mid[t] < px_ext and mid[t] > 0: px_ext = mid[t]
            reversed_ = px_ext > 0 and mid[t] >= px_ext * (1.0 + eps)
        if (not fired) and reversed_:             # FIRE: early entry at the price reversal (near the extreme)
            entries.append((t, lean_exti, hunt)); fired = True; cur = hunt
        # lean zigzag + confirm (the FILTER; also the fallback entry timing when no reversal fired)
        confirmed = False; conf_side = 0
        if d == 1:
            if x > lean_ext: lean_ext = x; lean_exti = t
            elif x <= lean_ext - reversal: confirmed = True; conf_side = -1
        else:
            if x < lean_ext: lean_ext = x; lean_exti = t
            elif x >= lean_ext + reversal: confirmed = True; conf_side = 1
        if confirmed:
            if not fired:                         # no price reversal this regime -> baseline (confirm) timing
                entries.append((t, lean_exti, conf_side)); cur = conf_side
            d = conf_side; lean_ext = x; lean_exti = t
            px_ext = mid[t]; fired = False        # reset the regime for the new hunted side
        pos[t] = cur
    return entries, pos


def make_retimed_signal(W: int, reversal: float, eps_bps: float):
    """signal_at(i, ts, p, bv, sv) -> retimed side as of i (for odcore.leakage; recomputes causally).
    p is the price/mid series; bv/sv the taker buy/sell volumes."""
    def signal_at(i, ts, p, bv, sv):
        i = int(i)
        if i < W:
            return 0
        _, pos = retime_flips(np.asarray(p[:i + 1], float), np.asarray(bv[:i + 1], float),
                              np.asarray(sv[:i + 1], float), W, reversal, eps_bps)
        return int(pos[-1])
    return signal_at
