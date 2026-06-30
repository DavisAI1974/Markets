"""odcore/swing_maker.py — one-sided MAKER-AT-THE-TURN swing executor (S46).

The strategy (STRATEGY_maker_at_the_turn_S45.md, Greg): a symmetric two-sided passive maker is at the
counterparty's mercy — mid-trend it only fills when flow is RIGHT and against you (the adversely-selected
victim, every red fill in the S45 autopsy). The fix is to be a maker ONLY at the turns, ONE-SIDED, on the
side where the aggressor is WRONG:

  - PEAK   (flip = top, side -1):  show the OFFER (post ASK), pull the bid. Euphoric BUYERS lift the offer
                                   (buying the high — adversely selected) -> we are filled SHORT, as a maker.
  - VALLEY (flip = bottom, side +1): show the BID (post), pull the offer. Capitulation SELLERS hit the bid
                                   (dumping the low) -> we cover/go LONG, as a maker.

Both legs are MAKER; we earn the spread on both turns and never cross it. Taker is only a FALLBACK to
flatten if a turn does not bring enough opposing (climax) volume to fill the passive quote.

This module is a thin SEQUENCING layer adding the position state machine the swing strategy needs (a
single sequential pass that depends on the open leg, which a vectorized per-cell simulator cannot express).

Execution model (the S45 Architect reframe + Greg S46 — "post ONLY the conviction side, re-quote it as
price moves, NEVER show the other side"; one maker fill at the turn closes the prior leg AND opens the
next, since in production you post 2x size so the turn aggressor flattens and re-establishes in one fill):
  - `flips` come from odcore.flip_detector.detect_flips (CAUSAL zigzag on the trailing flow lean). Each is
    (confirm_idx, pivot_idx, side); side +1 = valley -> go LONG (post BID), -1 = peak -> go SHORT (post ASK).
  - best BID on the valley + all the way UP (be long, sellers hit us as price rises); best OFFER at the peak
    + all the way DOWN (be short, buyers lift us as price falls). Flip the shown side at each turn.
  - We HAVE THE BEST price (front of queue), so the fill is simply the next REAL opposing trade after the
    turn — NO time/climax window (Greg S46: "the time windows are irrelevant"). The quote rests at the best
    price the whole leg, re-quoted as price moves; it is capped only at the next turn.
  - A maker fill at flip k closes the prior (opposite) leg (the cover IS a maker fill — at the valley our bid
    is hit by capitulation sellers; "be the maker and have the best bid for people to hit", Greg S46) and
    opens the new leg. Both legs maker captures the two half-spreads.
  - No opposing trade before the next turn: the cover "crosses as TAKER at the next turn" (Greg: "only do
    taker as last option") — flatten the open leg by crossing the spread; do NOT open a new leg. Caps
    inventory to one swing and removes the falling-knife class (we NEVER rest the off-side during the slide).

Causal: every entry decision uses only the flip (data <= confirm_idx) and the post-cell book; fills/marks
use cells AFTER the post. Pure numpy; portable. Evaluate on a held-out slice.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np


@dataclass
class SwingLeg:
    side: int            # +1 long (bid) / -1 short (ask)
    flip_idx: int        # confirm cell of the flip that opened this leg (where we DECIDED the side)
    open_idx: int        # cell where the maker fill actually opened this leg (>= flip_idx, the fill lag)
    open_px: float       # maker entry price (mid +/- half-spread)
    close_idx: int       # cell where the leg closed
    close_px: float      # close price (maker fill, or taker mid if flattened)
    close_maker: bool    # True = closed by a maker fill at the opposite turn; False = taker fallback
    gross_bps: float     # side * (close - open)/open * 1e4  (both half-spreads already in open/close px)
    net_bps: float       # gross - fees (maker on the open leg; maker or taker on the close leg)
    swing_bps: float     # |mid move| open->close (the raw swing size, for the fee-floor gate)


@dataclass
class SwingResult:
    arm: str
    n_flips: int
    n_legs: int          # closed swings
    n_taker_closes: int
    gross_per_leg_bps: float
    net_per_leg_bps: float
    total_net_bps: float
    win_frac: float
    mean_swing_bps: float
    fill_rate: float     # fraction of flips that got a maker fill (opened a leg)
    legs: list = field(default_factory=list, repr=False)

    def as_dict(self, with_legs=False):
        d = asdict(self)
        if not with_legs:
            d.pop("legs", None)
        return d


def _next_positive(vol: np.ndarray) -> np.ndarray:
    """For each cell t, the first index j > t with vol[j] > 0 (else n). O(n). This is the front-of-queue
    fill: posting the BEST price, we are first in line, so the next REAL opposing trade lifts/hits us."""
    n = len(vol)
    nxt = np.full(n, n, dtype=int)
    last = n
    for t in range(n - 1, -1, -1):
        nxt[t] = last
        if vol[t] > 0:
            last = t
    return nxt


def simulate_swing_maker(mid, best_bid_sz, best_ask_sz, buy_vol, sell_vol, flips, *,
                         half_spread_bps: float = 0.0, maker_fee_bps: float = 0.0,
                         taker_fee_bps: float = 0.0, taker_fallback: bool = True,
                         confirm=None, confirm_lookback: int = 0, entry_gate=None,
                         arm: str = "") -> SwingResult:
    """Run the one-sided maker-at-the-turn executor over a flip sequence. See module docstring.

    NO time/fill window (Greg S46: "take the time windows out, they are irrelevant"). The conviction quote
    rests at the BEST price the WHOLE leg (turn to turn), re-quoted as price moves; the fill is simply the
    first REAL opposing trade after the turn (front of queue), capped at the next turn. best bid on the
    valley/up-leg (long), best offer on the peak/down-leg (short).

    fees are PER LEG in bps (maker_fee NEGATIVE = rebate). The open leg always pays maker_fee; the close
    leg pays maker_fee when it is a maker fill at the opposite turn, taker_fee when it is a taker flatten.

    confirm: optional per-cell boolean array — the QuietFloor shock gate (the kickoff's "floor confirms the
    shock"). entry_gate: optional per-cell boolean array — the EXHAUSTION/reversal confirmation (e.g.
    info_dipole.divergence: order flow opposes price + the dipole collapsing toward 0.5). A flip is
    ACTIONABLE only if BOTH gates pass at the confirm cell. A non-actionable flip is NOT trusted as a real
    turn: we FLATTEN any open position (taker, last resort — caps the wrong-tail/inventory) and do NOT open
    a new one, waiting for the next confirmed+exhausted turn. Both default None = flips only.
    """
    mid = np.asarray(mid, float)
    bb = np.asarray(best_bid_sz, float); ba = np.asarray(best_ask_sz, float)
    bv = np.asarray(buy_vol, float); sv = np.asarray(sell_vol, float)
    n = len(mid)
    hs = half_spread_bps / 1e4
    conf = None if confirm is None else np.asarray(confirm).astype(bool)
    egate = None if entry_gate is None else np.asarray(entry_gate).astype(bool)

    # Front-of-queue fill, NO window: the offer (short) is lifted by the next BUY trade; the bid (long) is
    # hit by the next SELL trade. We have the best price, so the first real opposing trade fills us.
    fill_ask = _next_positive(bv)
    fill_bid = _next_positive(sv)

    legs: list[SwingLeg] = []
    pos = None            # open leg: dict(side, open_idx, open_px)
    n_fills = 0           # flips that produced a maker fill (opened a leg)

    flips = list(flips)
    for k, (ci, _pivot, s) in enumerate(flips):
        ci = int(ci)
        if ci <= 0 or ci >= n - 1:
            continue
        # the quote RESTS until the next flip (the strategy "rides it down keeping the best offer" until the
        # next turn); the fill search is therefore capped at the next flip's confirm cell, not a fixed window.
        next_ci = int(flips[k + 1][0]) if k + 1 < len(flips) else n
        # ACTIONABLE = the floor confirms the shock AND the exhaustion gate confirms the reversal (causal).
        floor_ok = conf is None or conf[max(0, ci - confirm_lookback):ci + 1].any()
        exh_ok = egate is None or bool(egate[ci])
        if not (floor_ok and exh_ok):
            continue                       # turn not trusted -> HOLD the prior position (ride the trend)
        # if we already hold the conviction side (a flip was skipped), HOLD -- do not re-open/overwrite it
        if pos is not None and pos["side"] == s:
            continue
        # one-sided quote for side s: short(-1)->post ASK (filled by BUY); long(+1)->post BID (filled by SELL)
        if s < 0:
            limit = mid[ci] * (1.0 + hs); fi = int(fill_ask[ci])
        else:
            limit = mid[ci] * (1.0 - hs); fi = int(fill_bid[ci])
        if fi >= next_ci:    # didn't fill before the next turn superseded the quote
            fi = -1

        if fi >= 0:
            n_fills += 1
            # close prior opposite leg at this maker fill (both legs maker)
            if pos is not None and pos["side"] == -s:
                fl = pos["flip_idx"]; op = pos["open_px"]; oi = pos["open_idx"]; osd = pos["side"]
                gross = osd * (limit - op) / op * 1e4
                net = gross - maker_fee_bps - maker_fee_bps     # maker open + maker close
                # swing = the price move the leg spanned, anchored on the POST (decision) cell, not the fill
                swing = abs(mid[fi] - mid[fl]) / mid[fl] * 1e4
                legs.append(SwingLeg(osd, fl, oi, op, fi, limit, True, gross, net, swing))
            # open the new leg at the maker fill
            pos = dict(side=int(s), flip_idx=int(ci), open_idx=int(fi), open_px=float(limit))
        else:
            # no climax volume to fill the passive quote -> skip the turn; flatten any open leg as taker.
            # a taker flatten CROSSES the spread: closing a long sells into the bid (mid*(1-hs)), closing a
            # short buys the ask (mid*(1+hs)) — so the half-spread is a real cost on the exit, not free at mid.
            if pos is not None and taker_fallback:
                fl = pos["flip_idx"]; op = pos["open_px"]; oi = pos["open_idx"]; osd = pos["side"]
                cpx = mid[ci] * (1.0 - hs) if osd > 0 else mid[ci] * (1.0 + hs)
                gross = osd * (cpx - op) / op * 1e4
                net = gross - maker_fee_bps - taker_fee_bps      # maker open + taker close (+ spread crossed in cpx)
                swing = abs(mid[ci] - mid[fl]) / mid[fl] * 1e4    # anchored on the POST (decision) cell
                legs.append(SwingLeg(osd, fl, oi, op, ci, float(cpx), False, gross, net, swing))
                pos = None

    nlegs = len(legs)
    if nlegs == 0:
        return SwingResult(arm, len(flips), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           n_fills / max(1, len(flips)), legs)
    return SwingResult(
        arm=arm, n_flips=len(flips), n_legs=nlegs,
        n_taker_closes=int(sum(1 for l in legs if not l.close_maker)),
        gross_per_leg_bps=float(np.mean([l.gross_bps for l in legs])),
        net_per_leg_bps=float(np.mean([l.net_bps for l in legs])),
        total_net_bps=float(np.sum([l.net_bps for l in legs])),
        win_frac=float(np.mean([l.net_bps > 0 for l in legs])),
        mean_swing_bps=float(np.mean([l.swing_bps for l in legs])),
        fill_rate=n_fills / max(1, len(flips)), legs=legs,
    )
