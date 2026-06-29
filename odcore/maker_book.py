"""
maker_book.py — portable maker-fill / queue simulator for the book-imbalance signal.

NEXT #3 (S42/S43): turn the depth-imbalance next-move predictor (63% next-cell, OOS,
S42) into a NET-OF-REBATE quoting edge. A sub-bp taker signal cannot clear the ~50-80
bps Coinbase taker floor (S43 OD-BOOK leg-2 post-mortem: the edge is ~140x below the
taker fee). The only realistic monetization is as a MAKER: post passively, earn the
rebate + half-spread, and use the signal to choose WHICH SIDE to post so fills are not
adversely selected.

This module is honest about the two things that kill naive maker backtests:
  1. QUEUE POSITION — you do not get filled just because price touches your level; the
     resting size AHEAD of you must trade through first. We model: join the back of the
     best level (queue_ahead = queue_frac * best_level_size at post time), and fill only
     once the cumulative OPPOSING taker volume within a fill window exceeds that queue.
  2. ADVERSE SELECTION — a passive bid gets filled exactly when sellers are aggressive,
     i.e. right as the mid is dropping. Because the limit price is fixed at post time and
     the position is marked to the FUTURE mid, this adverse drift is captured naturally:
     unconditional making on a 1-tick book is net-negative before rebate. The signal has
     to make conditional fills *less* adversely selected to earn its keep.

Pure numpy; no platform deps. Causal: the quote decision at cell t uses only info known
at t; fills and marks use t+1.. only. Evaluate on a held-out slice.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class MakerResult:
    arm: str
    n_quotes: int            # cells where we posted
    n_fills: int
    fill_rate: float
    gross_per_fill_bps: float    # mean PnL per fill BEFORE fee/rebate (spread + drift)
    net_per_fill_bps: float      # mean PnL per fill at the supplied fee_bps (rebate = negative fee)
    net_per_quote_bps: float     # net per posted quote (no-fills count as 0)
    breakeven_fee_bps: float     # the per-leg fee that drives net_per_fill to 0 (negative => needs a rebate)
    adverse_drift_bps: float     # mean signed mid drift entry->exit on fills (the adverse-selection term)
    half_spread_bps: float
    total_net_bps: float         # n_fills * net_per_fill (book-total at this fee)

    def as_dict(self):
        return asdict(self)


def _first_fill_index(queue_ahead: np.ndarray, opp_vol: np.ndarray,
                      fill_window: int) -> np.ndarray:
    """For each post cell t, the index of the first cell in (t, t+fill_window] at which
    cumulative opposing taker volume >= queue_ahead[t]. -1 if never filled in the window.
    Vectorized over t (O(fill_window) passes)."""
    n = len(opp_vol)
    cum = np.zeros(n)
    filled_at = np.full(n, -1, dtype=int)
    idx = np.arange(n)
    for w in range(1, fill_window + 1):
        # opposing volume arriving w cells after the post
        shifted = np.concatenate([opp_vol[w:], np.zeros(w)])
        cum += shifted
        reachable = (idx + w) < n
        newly = (filled_at < 0) & reachable & (cum >= queue_ahead)
        filled_at[newly] = idx[newly] + w
    return filled_at


def simulate_arm(side: np.ndarray, mid: np.ndarray, best_bid_sz: np.ndarray,
                 best_ask_sz: np.ndarray, buy_vol: np.ndarray, sell_vol: np.ndarray,
                 *, fill_window: int = 10, hold: int = 10, queue_frac: float = 1.0,
                 half_spread_bps: float = 0.0, fee_bps: float = 0.0,
                 arm: str = "") -> MakerResult:
    """Simulate one quoting policy. `side[t]` in {+1 post bid (buy), -1 post ask (sell),
    0 no quote}. fee_bps is the per-leg maker fee (NEGATIVE = rebate). Exit is mark-to-mid
    at fill+hold (a single passive leg is charged fee_bps; the exit is frictionless mid —
    a conservative, clearly-stated assumption; doubling fee_bps models a passive exit too).
    """
    n = len(mid)
    mid = np.asarray(mid, float)
    hs = (half_spread_bps / 1e4) * mid           # half-spread in price units, per cell

    post = side != 0
    # queue ahead at the posted level
    qa = np.where(side > 0, best_bid_sz, best_ask_sz) * queue_frac
    # opposing taker volume that fills us: a bid is filled by SELL flow; an ask by BUY flow
    # (run both fill scans, pick per-cell by side)
    fill_bid = _first_fill_index(qa, np.asarray(sell_vol, float), fill_window)
    fill_ask = _first_fill_index(qa, np.asarray(buy_vol, float), fill_window)
    filled_at = np.where(side > 0, fill_bid, np.where(side < 0, fill_ask, -1))

    filled = post & (filled_at >= 0)
    fi = filled_at.copy()
    exit_i = np.clip(np.where(filled, fi, 0) + hold, 0, n - 1)
    valid = filled & ((fi + hold) <= (n - 1))

    t = np.arange(n)
    entry = np.where(side > 0, mid[t] - hs, mid[t] + hs)   # passive limit price at post
    exit_mid = mid[exit_i]
    # PnL per fill in bps of mid[t], side-aware (long for bid, short for ask)
    pnl_gross = np.where(side > 0,
                         (exit_mid - entry) / mid[t] * 1e4,
                         (entry - exit_mid) / mid[t] * 1e4)
    # signed mid drift entry->exit (the adverse-selection diagnostic, sign = our direction)
    drift = np.where(side > 0,
                     (exit_mid - mid[t]) / mid[t] * 1e4,
                     (mid[t] - exit_mid) / mid[t] * 1e4)

    f = valid
    nq = int(post.sum())
    nf = int(f.sum())
    if nf == 0:
        return MakerResult(arm, nq, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           float(half_spread_bps), 0.0)
    g = float(pnl_gross[f].mean())            # gross per fill (spread + drift)
    net_pf = g - fee_bps                      # net per fill at supplied fee (rebate<0)
    return MakerResult(
        arm=arm, n_quotes=nq, n_fills=nf, fill_rate=nf / nq if nq else 0.0,
        gross_per_fill_bps=g, net_per_fill_bps=net_pf,
        net_per_quote_bps=net_pf * nf / nq if nq else 0.0,
        breakeven_fee_bps=g,                  # fee that makes net per fill = 0 (>0 ok, <0 needs rebate)
        adverse_drift_bps=float(drift[f].mean()),
        half_spread_bps=float(half_spread_bps),
        total_net_bps=net_pf * nf,
    )
