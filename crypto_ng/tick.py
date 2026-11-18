"""Crypto and ng AT THE TICK: the July rules read on the clock, every trade at its own nanosecond.

Greg, 2026-11-18: "Definitely run it on nano ticks. .1 is losing too much data"; "We don't keep wrong data".

The July program (`crypto_ng/program/`, byte for byte) walks a grid of tenths of a second. That grid is not allowed
on our tape. Here every rule and every number of the July calculation is kept and only the grid is gone:

  July, on cells                                   here, on the clock
  ------------------------------------------------ ------------------------------------------------------------
  the 20-second line: the last 200 cells           the trades received in the last 20 seconds, to the nanosecond
  the turn finder's lean: the last 600 cells       the trades received in the last 60 seconds
  0 where nothing traded                           the same 0 inside the turn finder (the stored line is empty)
  the turn finder (`detect_flips`), turn 0.10      THE SAME FUNCTION, untouched, walked over every moment the
                                                   60-second lean changes instead of over every cell
  in at the next trade on the other side           the same: the first such trade strictly after the turn
  ... only if before the next turn                 the same
  the wait of 300 cells                            30 seconds on the clock
  45 s before, 60 s after as the least a picture   the same two numbers
  shows

A line is READ: after every trade with a side is received (one read per trade, in tape order, also when several
share one nanosecond), and at every moment trades leave the span (one read per moment; trades that leave at the
very nanosecond a trade is received leave first and are read with that trade). The same convention as the stored
20-second flow of piece 1 (`root/calcs/flow_peak.py`).

Said plainly: this is no longer the July code run byte for byte. It is the July rules on our clock. The trades it
makes will not equal the trades of a grid run even with every number unchanged, because a grid nets everything
inside a tenth of a second into one reading and the clock does not.

Observation and verification only. Nothing here may be imported by a calculation, a strategy or the Kalshi work.
"""
from __future__ import annotations

import numpy as np

from crypto_ng import ng
from crypto_ng.program.flip_detector import detect_flips

NS = 10 ** 9
LINE_NS = ng.SMOOTH_SEC * NS                           # the 20-second line (July: SMOOTH_SEC = 20)
LEAN_NS = ng.WFLIP // ng.CPS * NS                      # the turn finder's lean: 600 cells of a tenth = 60 seconds
WAIT_NS = ng.NG.grace // ng.CPS * NS                   # the wait: 300 cells of a tenth = 30 seconds
PRE_NS, POST_NS = ng.PRE_SEC * NS, ng.POST_SEC * NS    # 45 seconds before, 60 after
BPS = 1e4
NONE = -1                                              # "no trade here" in a column of trade numbers

# how a trade of the program ended (the branches of the July trade maker, in its order)
END_NEXT_TURN = 'the next turn was filled: that fill ended this trade and started the next'
END_IN_WAIT = 'the next turn was not filled; a trade on the other side came within the 30-second wait'
END_BEFORE_TURN = 'the next turn was not filled; a trade on the other side came after the wait, before the turn after'
END_WAIT_OUT = 'the next turn was not filled and the wait ran out: 30 seconds after the turn, at no tick'
END_OPEN = 'still open at the last tick of the trade day (the July program wrote no line for such a trade)'

# what became of a turn
TURN_FILLED = 'filled: a trade of the program started'
TURN_HELD = 'not acted on: a fill or a wait before it was still resolving'
TURN_SAME_SIDE = 'not acted on: the program already held this side'
TURN_UNFILLED = 'not filled before the next turn'


def reads(received: np.ndarray, is_buy: np.ndarray, size: np.ndarray, span_ns: int, until_ns: int) -> dict:
    """Every read of one line, in order. `received`, `is_buy`, `size`: the trades WITH A SIDE, in tape order.
    Gives, per read: its moment; the trade received at it (its place among the sided trades, NONE when the read is
    a moment trades left); how many trades left at it; the size bought and sold inside the span after it."""
    n = len(received)
    moment, trade, left, bought, sold = [], [], [], [], []
    b = s = 0
    i = j = 0                                          # the next trade to arrive; the next trade to leave
    while True:
        arrives = int(received[i]) if i < n else None
        leaves = int(received[j]) + span_ns if j < i else None
        if leaves is not None and leaves >= until_ns:  # the trade day is over: nothing is read past its end
            leaves = None
        if arrives is None and leaves is None:
            break
        gone = 0
        if leaves is not None and (arrives is None or leaves <= arrives):
            while j < i and int(received[j]) + span_ns == leaves:
                if is_buy[j]:
                    b -= int(size[j])
                else:
                    s -= int(size[j])
                j += 1
                gone += 1
            if arrives is None or leaves < arrives:    # a moment with no trade: the read of the trades leaving
                moment.append(leaves); trade.append(NONE); left.append(gone); bought.append(b); sold.append(s)
                continue
        if is_buy[i]:                                  # a trade is received (those leaving at this nanosecond
            b += int(size[i])                          # have left first)
        else:
            s += int(size[i])
        moment.append(arrives); trade.append(i); left.append(gone); bought.append(b); sold.append(s)
        i += 1
    as_ints = lambda x: np.array(x, np.int64)
    return dict(moment=as_ints(moment), trade=as_ints(trade), left=as_ints(left), bought=as_ints(bought),
                sold=as_ints(sold))


def line(bought: np.ndarray, sold: np.ndarray) -> tuple:
    """The July formula (`rolling_imb`, `lean_series`): bought minus sold over bought plus sold; 0 where nothing
    traded. Also gives where nothing traded, so the 0 is never stored as a reading."""
    total = bought + sold
    out = np.zeros(len(total))
    some = total > 0
    out[some] = (bought[some] - sold[some]) / total[some]
    return out, ~some


def recount(received: np.ndarray, is_buy: np.ndarray, size: np.ndarray, span_ns: int, r: dict) -> tuple:
    """The second method: bought and sold at every read, from running totals and two look-ups on the clock. At a
    trade's read: every sided trade up to and including it, less every one received 20 (or 60) seconds or more
    before. At a read of trades leaving: every sided trade received up to that moment, less the same."""
    cb = np.concatenate([[0], np.cumsum(np.where(is_buy, size, 0))])
    cs = np.concatenate([[0], np.cumsum(np.where(is_buy, 0, size))])
    through = np.where(r['trade'] != NONE, r['trade'] + 1, np.searchsorted(received, r['moment'], 'right'))
    gone = np.searchsorted(received, r['moment'] - span_ns, 'right')
    return cb[through] - cb[gone], cs[through] - cs[gone]


def turns(lean: np.ndarray) -> list:
    """The July turn finder itself (`detect_flips`, untouched), walked over the reads of the 60-second lean. The
    walk starts at the open of the trade day, where nothing has traded and the July rule reads 0. Gives
    (the read the turn was marked at, the read the lean stood furthest at or NONE for the open, the side)."""
    flips, _ = detect_flips(np.concatenate([[0.0], lean]), ng.NG.rev)
    return [(int(c) - 1, int(p) - 1, int(s)) for c, p, s in flips]


def trades(r: dict, lean: np.ndarray, found: list, received: np.ndarray, is_buy: np.ndarray, mid_at_read,
           mid_at_trade, mid_at_moment, hs_bps: float, last_ns: int) -> tuple:
    """The July trade maker (`simulate_swing_maker` as `run_kraken_cell` calls it for the natural gas row: first
    in line, the 30-second wait, the close improved by 0.5, no gate, no stop), branch for branch, on the clock.
    `r`, `lean`: the reads of the 60-second lean. `found`: its turns. Gives (the program's trades, what became of
    every turn)."""
    n = len(received)
    cfg = ng.NG
    hs, imp = hs_bps / BPS, cfg.improve / BPS
    after = np.where(r['trade'] != NONE, r['trade'] + 1, np.searchsorted(received, r['moment'], 'right'))
    read_of = np.full(n, NONE, np.int64)
    at_trade = r['trade'] != NONE
    read_of[r['trade'][at_trade]] = np.flatnonzero(at_trade)
    next_buy, next_sell = np.full(n + 1, n, np.int64), np.full(n + 1, n, np.int64)
    for k in range(n - 1, -1, -1):                     # the first buy, the first sell, at or after each trade
        next_buy[k] = k if is_buy[k] else next_buy[k + 1]
        next_sell[k] = next_sell[k + 1] if is_buy[k] else k
    out, fate = [], []
    pos = None                                         # the trade under way (a line of `out`)
    hold = NONE                                        # reads up to here are a fill or a wait still resolving

    def close(leg, how, trade, at_ns, px, maker, swing_from):
        gross = leg['side'] * (px - leg['open_px']) / leg['open_px'] * BPS
        fee = cfg.maker_fee if maker else cfg.taker_fee
        leg.update(ended=how, end_trade=trade, end_ns=int(at_ns), close_px=float(px), close_maker=bool(maker),
                   gross_bps=float(gross), net_bps=float(gross - cfg.maker_fee - fee),
                   swing_bps=float(abs(swing_from - leg['turn_mid']) / leg['turn_mid'] * BPS))

    for k, (c, p, s) in enumerate(found):
        if c <= hold:
            fate.append(TURN_HELD)
            continue
        next_c = found[k + 1][0] if k + 1 < len(found) else None
        if pos is not None and pos['side'] == s:
            fate.append(TURN_SAME_SIDE)
            continue
        turn_mid = mid_at_read(c)
        # long (+1): its bid is hit by the next SELL; short (-1): its offer is lifted by the next BUY
        j = int(next_sell[after[c]] if s > 0 else next_buy[after[c]])
        limit = turn_mid * (1.0 - hs) if s > 0 else turn_mid * (1.0 + hs)
        if j < n and (next_c is None or read_of[j] < next_c):
            if pos is not None:                        # the fill ends the trade under way (it is the other side)
                close(pos, END_NEXT_TURN, j, received[j], limit, True, mid_at_trade(j))
            pos = dict(side=s, turn=k, turn_read=c, furthest_read=p, onset_trade=j, onset_ns=int(received[j]),
                       open_px=float(limit), turn_mid=float(turn_mid), ended=END_OPEN, end_trade=NONE, end_ns=None,
                       close_px=None, close_maker=None, gross_bps=None, net_bps=None, swing_bps=None)
            out.append(pos)
            hold = int(read_of[j])
            fate.append(TURN_FILLED)
            continue
        fate.append(TURN_UNFILLED)
        if pos is None:
            continue
        osd = pos['side']                              # the trade under way is closed: long by the next BUY,
        cj = int(next_buy[after[c]] if osd > 0 else next_sell[after[c]])   # short by the next SELL
        cap_ns = min(int(r['moment'][c]) + WAIT_NS, last_ns)
        if cj < n and int(received[cj]) <= cap_ns:
            close(pos, END_IN_WAIT, cj, received[cj], turn_mid * (1.0 + hs) if osd > 0 else turn_mid * (1.0 - hs),
                  True, mid_at_trade(cj))
            hold = int(read_of[cj])
        elif cj < n and (next_c is None or read_of[cj] < next_c):
            m = mid_at_trade(cj)
            close(pos, END_BEFORE_TURN, cj, received[cj], m * (1.0 + (hs - imp)) if osd > 0 else m * (1.0 - (hs - imp)),
                  True, m)
            hold = int(read_of[cj])
        else:
            m = mid_at_moment(cap_ns)
            close(pos, END_WAIT_OUT, NONE, cap_ns, m * (1.0 - hs) if osd > 0 else m * (1.0 + hs), False, m)
            hold = int(np.searchsorted(r['moment'], cap_ns, 'right')) - 1
        pos = None

    for leg in out:                                    # what the program writes beside each trade (its lean reads)
        f, c = leg['furthest_read'], leg['turn_read']
        leg['dive_depth'] = round(float(abs(lean[f])) if f != NONE else 0.0, 4)
        leg['lean_flip'] = round(float(lean[c]) * -leg['side'], 4)
        if leg['end_ns'] is None:
            leg['lean_close'] = None
        else:
            e = read_of[leg['end_trade']] if leg['end_trade'] != NONE else \
                int(np.searchsorted(r['moment'], leg['end_ns'], 'right')) - 1
            leg['lean_close'] = round(float(lean[e]) * leg['side'], 4)
    return out, fate
