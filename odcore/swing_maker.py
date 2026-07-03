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
    size: float = 1.0    # conviction size multiplier (set by size_legs; 1.0 = flat/unsized)
    lean_exit: bool = False  # True = closed by the dipole lean-collapse exit (S55 R8), not a turn


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
                         cover_grace: int = 0, lean=None, lean_exit=None,
                         fill_mode: str = "maker", arm: str = "") -> SwingResult:
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

    fill_mode (S55 round 12 — ONE EXECUTOR, ANY SCALE; default "maker" = bit-identical): "taker"
    makes every open/close an immediate spread-crossing fill at the decision cell (open at
    mid*(1+hs) long / mid*(1-hs) short; both fee legs taker; queue/book-size arrays unused, pass
    zeros). This exists so RESEARCH threads (coarse zigzag/bigline on dump bins, which carry no
    book depth) run through THIS decision code — same leg accounting, sizing, lean_exit, gates,
    ledger schema — instead of re-implementing trade mechanics per probe (the "two versions"
    drift Greg flagged). The fill model becomes a labeled column, never a fork.

    lean + lean_exit (S55 round 8, THE INVERTED GRAPH — opt-in, default None = bit-identical): the
    dipole EXIT fine-tuner. `lean` = the causal flow-lean series (same array the flip detector runs
    on); `lean_exit` = (arm_hi, exit_lo). Per open leg, the with-ride lean side*lean[t] is walked
    between flips: once it reaches `arm_hi` (the flow is genuinely WITH the ride — prevents firing
    at entry, where with-ride lean starts negative by construction), the first collapse to
    `exit_lo` closes the leg via the SAME maker-preferred cover machinery (post the cover at the
    trigger cell, cover_grace applies, taker fallback at the cap). Measured basis (765 zz150 exits,
    30d x 5): flow climaxes AT the top and collapses through zero within ~60s at ~28bp giveback vs
    151bp for the theta-exit; the climax is also the maker-fillability peak (S45 "can't refuse").
    Legs closed this way carry SwingLeg.lean_exit=True. ADOPTION per cell via the forward ledger
    ONLY (controls mandatory) — this parameter existing does not mean it is on anywhere.

    cover_grace (cells, S48): the SMARTER LAST-OPTION. When the cover quote does not fill before the next
    turn (the forced-taker case — the doge cost sink, 36-47% of exits), DON'T cross the spread immediately.
    Keep the maker cover resting up to `cover_grace` cells past the turn and take the first opposing trade
    (still maker, EARNING the half-spread instead of crossing it); cross as taker only if it is still
    unfilled at the grace cap. Cover-ONLY — we do not open a late new leg (S47: late entries degrade), so
    inventory stays capped to one swing; intervening flips during the cover are skipped (no leg overlap).
    Default 0 == the prior immediate-taker behavior (bit-identical). On the S46/S47 window this drops the
    taker rate to ~0% and lifts net-of-fee on all 5 cells (doge flips -510 -> +1011), saturating ~G=300
    (30s); per-cell deploy (doge wants ~600). Faithful to the existing fill model (same `_next_positive`,
    fixed limit at the post cell) so it is an apples-to-apples execution improvement, not new optimism.
    """
    mid = np.asarray(mid, float)
    bb = np.asarray(best_bid_sz, float); ba = np.asarray(best_ask_sz, float)
    bv = np.asarray(buy_vol, float); sv = np.asarray(sell_vol, float)
    n = len(mid)
    hs = half_spread_bps / 1e4
    conf = None if confirm is None else np.asarray(confirm).astype(bool)
    egate = None if entry_gate is None else np.asarray(entry_gate).astype(bool)
    ln = None if (lean is None or lean_exit is None) else np.asarray(lean, float)
    arm_hi, exit_lo = (lean_exit if lean_exit is not None else (0.0, 0.0))
    taker_mode = fill_mode == "taker"

    # Front-of-queue fill, NO window: the offer (short) is lifted by the next BUY trade; the bid (long) is
    # hit by the next SELL trade. We have the best price, so the first real opposing trade fills us.
    fill_ask = _next_positive(bv)
    fill_bid = _next_positive(sv)

    legs: list[SwingLeg] = []
    pos = None            # open leg: dict(side, open_idx, open_px)
    n_fills = 0           # flips that produced a maker fill (opened a leg)
    hold_until = -1       # cells through which we are committed (a fill/cover in progress); skip flips <= it

    flips = list(flips)
    for k, (ci, _pivot, s) in enumerate(flips):
        ci = int(ci)
        if ci <= hold_until:   # a maker fill / grace cover is resolving past this flip — do not act yet
            continue
        if ci <= 0 or ci >= n - 1:
            continue
        # S55 R8 dipole lean-collapse EXIT: walk the with-ride lean over the cells since the last
        # look (leg segments can span skipped flips); arm at arm_hi, close at the collapse to exit_lo.
        if pos is not None and ln is not None:
            osd = pos["side"]
            te = -1
            for t in range(pos["scan_from"], min(ci, n)):
                sl = osd * ln[t]
                if not pos["lean_armed"]:
                    if sl >= arm_hi:
                        pos["lean_armed"] = True
                elif sl <= exit_lo:
                    te = t
                    break
            if te < 0:
                pos["scan_from"] = ci
            else:
                # close via the SAME maker-preferred cover machinery, anchored at the trigger cell:
                # the cover rests INTO the dying climax (max fillability); grace cap, taker fallback.
                # (taker fill_mode: immediate spread-crossing close at the trigger cell.)
                fl = pos["flip_idx"]; op = pos["open_px"]; oi = pos["open_idx"]
                fo = pos.get("fee_open", maker_fee_bps)
                cf = -1 if taker_mode else (int(fill_ask[te]) if osd > 0 else int(fill_bid[te]))
                cap = min(n - 1, te + max(cover_grace, 0))
                if not taker_mode and cf <= cap:
                    cpx = mid[te] * (1.0 + hs) if osd > 0 else mid[te] * (1.0 - hs)
                    gross = osd * (cpx - op) / op * 1e4
                    net = gross - fo - maker_fee_bps
                    swing = abs(mid[cf] - mid[fl]) / mid[fl] * 1e4
                    legs.append(SwingLeg(osd, fl, oi, op, int(cf), float(cpx), True, gross, net,
                                         swing, lean_exit=True))
                    hold_until = int(cf)
                else:
                    xc = te if taker_mode else cap
                    cpx = mid[xc] * (1.0 - hs) if osd > 0 else mid[xc] * (1.0 + hs)
                    gross = osd * (cpx - op) / op * 1e4
                    net = gross - fo - taker_fee_bps
                    swing = abs(mid[xc] - mid[fl]) / mid[fl] * 1e4
                    legs.append(SwingLeg(osd, fl, oi, op, int(xc), float(cpx), False, gross, net,
                                         swing, lean_exit=True))
                    hold_until = int(xc)
                pos = None
                if ci <= hold_until:   # the cover resolution runs past this flip — do not act on it
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
        # taker fill_mode: immediate cross at the decision cell (long buys the ask, short sells the bid);
        # the close of the prior opposite leg crosses the SAME side of the book at the same cell.
        if taker_mode:
            limit = mid[ci] * (1.0 - hs) if s < 0 else mid[ci] * (1.0 + hs)
            fi = ci
        elif s < 0:
            limit = mid[ci] * (1.0 + hs); fi = int(fill_ask[ci])
        else:
            limit = mid[ci] * (1.0 - hs); fi = int(fill_bid[ci])
        if fi >= next_ci:    # didn't fill before the next turn superseded the quote
            fi = -1

        if fi >= 0:
            n_fills += 1
            fee_leg = taker_fee_bps if taker_mode else maker_fee_bps
            # close prior opposite leg at this fill (maker/maker, or taker/taker in taker mode)
            if pos is not None and pos["side"] == -s:
                fl = pos["flip_idx"]; op = pos["open_px"]; oi = pos["open_idx"]; osd = pos["side"]
                gross = osd * (limit - op) / op * 1e4
                net = gross - pos.get("fee_open", maker_fee_bps) - fee_leg
                # swing = the price move the leg spanned, anchored on the POST (decision) cell, not the fill
                swing = abs(mid[fi] - mid[fl]) / mid[fl] * 1e4
                legs.append(SwingLeg(osd, fl, oi, op, fi, limit, not taker_mode, gross, net, swing))
            # open the new leg at the fill
            pos = dict(side=int(s), flip_idx=int(ci), open_idx=int(fi), open_px=float(limit),
                       scan_from=int(fi) + 1, lean_armed=False, fee_open=fee_leg)
            hold_until = int(fi)                  # no-op at cover_grace=0 (fi < next_ci <= the next flip)
        else:
            # no climax volume to fill the passive quote -> skip the turn; flatten any open leg.
            # a taker flatten CROSSES the spread: closing a long sells into the bid (mid*(1-hs)), closing a
            # short buys the ask (mid*(1+hs)) — so the half-spread is a real cost on the exit, not free at mid.
            if pos is not None and taker_fallback:
                fl = pos["flip_idx"]; op = pos["open_px"]; oi = pos["open_idx"]; osd = pos["side"]
                fo = pos.get("fee_open", maker_fee_bps)
                # SMARTER LAST-OPTION (S48): rest the maker cover up to `cover_grace` cells; take the first
                # opposing trade as a MAKER (earn the half-spread) before resorting to a taker cross.
                # cover side osd: long(+1)->post ASK lifted by next BUY; short(-1)->post BID hit by next SELL.
                cf = int(fill_ask[ci]) if osd > 0 else int(fill_bid[ci])
                cap = min(n - 1, ci + cover_grace)
                if cover_grace > 0 and cf <= cap:
                    # maker cover fills within grace: fixed limit at the turn (mid[ci] +/- hs), close idx = cf
                    cpx = mid[ci] * (1.0 + hs) if osd > 0 else mid[ci] * (1.0 - hs)
                    gross = osd * (cpx - op) / op * 1e4
                    net = gross - fo - maker_fee_bps                      # open fee as opened + maker close
                    swing = abs(mid[cf] - mid[fl]) / mid[fl] * 1e4
                    legs.append(SwingLeg(osd, fl, oi, op, int(cf), float(cpx), True, gross, net, swing))
                    hold_until = int(cf)
                else:
                    # unfilled within grace (or grace off) -> taker cross. With grace we crossed at the cap
                    # cell (held then crossed, the realistic downside); without grace, at this turn cell.
                    xc = cap if cover_grace > 0 else ci
                    cpx = mid[xc] * (1.0 - hs) if osd > 0 else mid[xc] * (1.0 + hs)
                    gross = osd * (cpx - op) / op * 1e4
                    net = gross - fo - taker_fee_bps                     # open fee as opened + taker close
                    swing = abs(mid[xc] - mid[fl]) / mid[fl] * 1e4
                    legs.append(SwingLeg(osd, fl, oi, op, int(xc), float(cpx), False, gross, net, swing))
                    hold_until = int(xc)
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


def size_legs(legs, quality, size_axis, *, alpha: float = 1.0, roll: int = 200,
              lo_clip: float = 0.25, hi_clip: float = 4.0, warmup: int = 20) -> float:
    """Two-factor conviction SIZING (S47, validated OOS S49) — set leg.size in place, return the sized total.

    The edge is sizing, NOT gating (S47/Greg): keep EVERY leg, concentrate capital on the high-conviction
    turns. `E[net] = P(reversal) x E[|move|]`, so conviction = rank(QUALITY axis) x rank(SIZE axis):
      - QUALITY axis (predicts win/lose): clmx_60 = vm(60)/vm(600) — the only sign-consistent net lever.
      - SIZE axis (predicts |move|): z(vol_60)+z(volat_120)+z(runup)+z(dive_depth) — sign-consistent on all 5.
    Both are CAUSAL features at the leg's flip (decision) cell; `quality[i]`/`size_axis[i]` are one value per
    leg, in chronological order. Normalization is CAUSAL ROLLING (trailing `roll` PRIOR legs only) so it is
    leakage-free by construction (verified by assert_no_leakage on the underlying features, S49).

    pass 1: conviction[i] = frac(prior quality < quality[i]) * frac(prior size_axis < size_axis[i])  (0..1)
    pass 2: leg.size = clip(1 + alpha * z(conviction over trailing roll), lo_clip, hi_clip), centered on 1
            (matched-capital: mean size ~ 1). Warmup (< `warmup` priors) -> flat size 1.0.

    Bit-identical to the inline pass that paper_trade.py used before this was extracted. Deploy per cell
    (S49: lift positive OOS on all 5; biggest on doge +0.82/leg). Returns sum(leg.net_bps * leg.size).
    """
    q = np.asarray(quality, float); sa = np.asarray(size_axis, float)
    m = len(legs)
    if m == 0:
        return 0.0
    conv = np.full(m, lo_clip)
    for i in range(m):
        lo = max(0, i - roll)
        if i - lo >= warmup:
            pr = slice(lo, i)
            rq = float((q[pr] < q[i]).mean())
            rs = float((sa[pr] < sa[i]).mean())
            conv[i] = rq * rs
    total = 0.0
    for i, l in enumerate(legs):
        lo = max(0, i - roll)
        if i - lo >= warmup:
            pri = conv[lo:i]; sd = pri.std()
            zc = (conv[i] - pri.mean()) / (sd + 1e-9)
            l.size = float(np.clip(1.0 + alpha * zc, lo_clip, hi_clip))
        else:
            l.size = 1.0
        total += l.net_bps * l.size
    return total
