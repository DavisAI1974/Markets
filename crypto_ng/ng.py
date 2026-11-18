"""Crypto and ng: the natural gas row, and the lines of the July scripts that sit around the program.

Everything here is the July calculation as its scripts have it (see `PROVENANCE.md`); nothing is improved, swapped
or added. The trades come from `crypto_ng.program.platform.run_kraken_cell`, untouched.
"""
from __future__ import annotations

import numpy as np

from crypto_ng.program.platform import CellConfig, WFLIP, kraken_flips, run_kraken_cell
from crypto_ng.program.flip_detector import lean_series

# The natural gas row: sol's row of the July registry with the name changed.
#   July: CellConfig("sol", venue="kraken", side=+1, rev=0.10, eps=None, bail=None,  grace=300, improve=0.5)
NG = CellConfig("ng", venue="nymex", side=+1, rev=0.10, eps=None, bail=None, grace=300, improve=0.5)

# research/shape_s71/regroup2.py, line 10, unchanged
CPS = 10; PRE_SEC, POST_SEC, SMOOTH_SEC = 45, 60, 20
PRE, POST = PRE_SEC*CPS, POST_SEC*CPS
EVERY = 50                                             # _liquidity_dive.median_spread_bps reads every 50th record


# research/shape_s71/arc_gate.py, lines 39 to 44, unchanged
def rolling_imb(buy, sell, w_sec):
    w=int(w_sec*CPS); cb=np.concatenate([[0.],np.cumsum(buy)]); cs=np.concatenate([[0.],np.cumsum(sell)])
    ix=np.arange(len(buy)); lo=np.maximum(ix+1-w,0)
    B=cb[ix+1]-cb[lo]; S=cs[ix+1]-cs[lo]; tot=B+S
    out=np.zeros(len(buy)); nz=tot>0; out[nz]=(B[nz]-S[nz])/tot[nz]
    return out


def last_in(n, cell, x):
    """_birth_probe.to_grid's `last_in`, unchanged but for taking n and cell as arguments: a book figure takes the
    last value in each cell and is carried forward (the cells before the first value take the first value)."""
    out = np.full(n, np.nan); out[cell] = x
    # forward fill
    idx = np.where(~np.isnan(out))[0]
    out[:idx[0]] = out[idx[0]]
    last = np.maximum.accumulate(np.where(~np.isnan(out), np.arange(n), 0))
    return out[last]


def half_spread_bps(mid, spread):
    """_liquidity_dive.median_spread_bps (its branch for records already read), halved as regroup2 halves it."""
    m_ = mid[::EVERY]; sp = spread[::EVERY]
    m = (m_ > 0) & ~np.isnan(sp)
    sb = (sp[m] / m_[m] * 1e4)
    return (float(np.median(sb)) if sb.size else float("nan")) / 2.0


def run(mid, buy, sell, best_bid_size, best_ask_size, hs):
    """The July lines of regroup2.quad_means up to the trades: the program's trades, what it writes beside each,
    the turns it found, the 20-second line and the turn finder's own 60-second lean."""
    res, desc = run_kraken_cell(NG, mid, buy, sell, best_bid_size, best_ask_size, hs)
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    return res, desc, kraken_flips(NG, mid, buy, sell), imb, lean_series(buy, sell, WFLIP)


def arc(imb, leg, n):
    """One trade's arc, as regroup2 cuts it: the 20-second line from PRE cells before the onset to POST after,
    turned to the trade's side. None when it does not fit inside the data or the end is not after the onset."""
    o=int(leg.open_idx); c=int(leg.close_idx)
    if o-PRE<0 or o+POST>=n or c<=o: return None
    return imb[o-PRE:o+POST+1]*int(leg.side)
