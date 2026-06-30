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

This module is a thin SEQUENCING layer over the validated S45 fill model: it reuses
`odcore.maker_book._first_fill_index` (the queue-position + opposing-taker-volume fill logic the autopsy
was built on) verbatim, and only adds the position state machine the swing strategy needs (a single
sequential pass that depends on the open leg, which the vectorized per-cell arm simulator cannot express).

Execution model (the S45 Architect reframe — "post ONLY the conviction side, re-quote it as price moves,
NEVER show the other side"; one maker fill at the turn closes the prior leg AND opens the next, since in
production you post 2x size so the climax aggressor flattens and re-establishes in one fill):
  - `flips` come from odcore.flip_detector.detect_flips (CAUSAL zigzag on the trailing flow lean). Each is
    (confirm_idx, pivot_idx, side); side +1 = valley -> go LONG (post BID), -1 = peak -> go SHORT (post ASK).
  - At flip k we post the ONE-SIDED conviction quote (offer for a short, bid for a long) and accept a MAKER
    fill ONLY within the CLIMAX WINDOW after the flip — `fill_window` is the climax-burst duration, NOT the
    whole leg. "The only fills we accept are the ones moving into our position favorably" (S45): the climax
    aggressor (S40 ~2x volume AT the turn) lifts our offer / hits our bid right at the extreme; a fill that
    only arrives long after the turn is the stale, adversely-selected fill we must REFUSE -> skip the turn.
  - A maker fill at flip k closes the prior (opposite) leg (the cover IS a maker fill — at the valley our bid
    is hit by capitulation sellers; "be the maker and have the best bid for people to hit", Greg S46) and
    opens the new leg. Both legs maker captures the two half-spreads.
  - No maker (climax) fill within the window: the cover instead "crosses as TAKER at the next turn" (Greg's
    fallback) — flatten any open leg by crossing the spread at the flip cell; do NOT open a new leg. Caps
    inventory to one swing and removes the falling-knife class (we NEVER rest the off-side during the slide).

Causal: every entry decision uses only the flip (data <= confirm_idx) and the post-cell book; fills/marks
use cells AFTER the post. Pure numpy; portable. Evaluate on a held-out slice.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np

from odcore.maker_book import _first_fill_index


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


def simulate_swing_maker(mid, best_bid_sz, best_ask_sz, buy_vol, sell_vol, flips, *,
                         half_spread_bps: float = 0.0, fill_window: int = 10,
                         queue_frac: float = 1.0, maker_fee_bps: float = 0.0,
                         taker_fee_bps: float = 0.0, taker_fallback: bool = True,
                         confirm=None, confirm_lookback: int = 0,
                         arm: str = "") -> SwingResult:
    """Run the one-sided maker-at-the-turn executor over a flip sequence. See module docstring.

    fees are PER LEG in bps (maker_fee NEGATIVE = rebate). The open leg always pays maker_fee; the close
    leg pays maker_fee when it is a maker fill at the opposite turn, taker_fee when it is a taker flatten.

    confirm: optional per-cell boolean array — the QuietFloor shock gate (the kickoff's "floor confirms the
    shock"). When supplied, a flip is only acted on if the floor fired at the confirm cell (or within the
    prior `confirm_lookback` cells — causal). A non-confirmed flip is skipped entirely (no open, no close):
    we don't trust it is a real turn, so we hold to the next confirmed turn. Default None = flips only.
    """
    mid = np.asarray(mid, float)
    bb = np.asarray(best_bid_sz, float); ba = np.asarray(best_ask_sz, float)
    bv = np.asarray(buy_vol, float); sv = np.asarray(sell_vol, float)
    n = len(mid)
    hs = half_spread_bps / 1e4
    conf = None if confirm is None else np.asarray(confirm).astype(bool)

    # Reuse the validated S45 fill model (maker_book): per cell, the first fill index for an ask (filled by
    # BUY flow clearing the best-ask queue) and for a bid (filled by SELL flow clearing the best-bid queue).
    # Floor the queue at EPS so queue_frac=0 ("have the BEST bid/offer" = front of queue, price improvement)
    # means "fill on the first REAL opposing trade", not the degenerate "fill next cell with zero volume".
    EPS = 1e-9
    fill_ask = _first_fill_index(np.maximum(ba * queue_frac, EPS), bv, fill_window)
    fill_bid = _first_fill_index(np.maximum(bb * queue_frac, EPS), sv, fill_window)

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
        # QuietFloor confirmation (causal): only act on a flip the floor flags as a real shock
        if conf is not None and not conf[max(0, ci - confirm_lookback):ci + 1].any():
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
