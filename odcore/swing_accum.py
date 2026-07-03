"""odcore/swing_accum.py — Greg's ACCUMULATE-AT-THE-TURN executor (S52). Sibling of swing_maker (NOT a fork).

The strategy, in Greg's terms (S52 dissection session):
  - The dipole picks the REAL turns — no hit-lift churn over 2–4 bps noise (entry gating lives in the
    harness: the flip list passed in is pre-filtered; EXITS are never gated — the next opposite detected
    flip always ends the leg, same as the validated one-shot).
  - At a selected valley: STARTER fill at the turn price (small — cheap to dump if wrong). Incremental
    while unsure. "If we need to be incremental because we are unsure that's fine."
  - On CONFIRMATION ("if we acknowledge a winner"): go ALL IN on the remainder as quickly as possible —
    aggressive maker peg + fee-aware TAKER completion. As much of the trading done as early as possible
    on confirmed winners, so the full position rides the confirmed move to the flip.
  - At the next turn: unload for the HIGHEST DOLLAR amount, fees included — best offer at the top for the
    full inventory, stay best offer down the slide, cross as taker when waiting has provably cost more
    than crossing would have (slide > spread + taker fee).
  - Failed call (red beyond the dump band BEFORE confirmation): dump the whole (small) remainder taker
    immediately. "You don't go all in on a loser and you can dump it quickly in a worst case."
  - Fully symmetric short legs.

Fill honesty (the S52 corrections, both directions):
  - PRICE ELIGIBILITY: a resting quote only fills in cells where the venue's best is at-or-through it
    (long entry at the turn: mid[t] <= turn mid; peak unload: mid[t] >= peak mid).
  - QUEUE (v2, odcore/maker_book discipline): we join the BACK of the best level, so the size resting
    ahead (best-level size at the post cell) must trade through before our first unit fills.
  - Phase-2 maker completion pegs to the CURRENT best bid each cell (trailing peg): fills are priced at
    that cell's bid (mid[t]·(1−hs)) — no free bottom-tick on chased size — and queue-marked per cell.
  - Taker fills cross the spread (±hs) and pay the taker fee. Maker fills pay maker_fee (negative =
    rebate). No mark-to-close fiction: every unit's exit is an explicit fill (maker at the turn price,
    or taker at the slide-cross price).

Aggregate P&L per leg = sell proceeds − buy cost − fees (identical to LIFO-matched total; per-lot LIFO
attribution is reporting, not P&L). Causal by construction: every decision at cell t uses data <= t.
Pure numpy, per-leg vectorized (no cell loop).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np


@dataclass
class AccumLeg:
    side: int                # +1 long / -1 short
    flip_idx: int            # decision cell (gated flip)
    close_flip_idx: int      # the opposite flip that ended the leg (or dump cell)
    bought_usd: float        # total entry notional filled (both phases)
    starter_usd: float
    phase2_maker_usd: float
    phase2_taker_usd: float
    confirmed: bool
    confirm_idx: int         # cell where confirmation fired (-1 = never)
    dumped: bool             # quick-dump before confirmation
    unload_maker_usd: float  # exit notional filled maker at the turn price
    unload_taker_usd: float  # exit notional crossed on the slide
    net_usd: float           # sell proceeds − buy cost − all fees (signed, both leg directions)
    fees_usd: float          # total fees paid (negative = net rebate earned)
    add_height_bps: float    # VW entry height above/below the turn price (the S40 headwind number)
    maker_usd: float         # total maker-filled notional both sides (for maker-share accounting)
    taker_usd: float


@dataclass
class AccumResult:
    arm: str
    n_flips: int
    n_legs: int
    n_confirmed: int
    n_dumped: int
    net_usd: float
    fees_usd: float
    win_frac: float
    med_win_notional: float
    med_loss_notional: float
    maker_usd: float
    taker_usd: float
    legs: list = field(default_factory=list, repr=False)

    def as_dict(self, with_legs=False):
        d = asdict(self)
        if not with_legs:
            d.pop("legs", None)
        return d


def _eligible_fill(mid, opp, best_ahead, lo, hi, ref_px, side, hs, budget_usd=None,
                   budget_coins=None, peg=False):
    """Queue+price-honest maker fill between cells [lo, hi], capped by USD and/or COIN budget.

    side +1 = we BID (filled by sell flow), −1 = we OFFER (filled by buy flow).
    peg=False: fixed limit at ref_px·(1∓hs); eligible cells are mid <= / >= ref_px; all fills at the limit.
    peg=True: TRAILING peg to the current best each cell (Greg: "still be the best offer on the way
    down"); every cell eligible; fill price = mid[t]·(1∓hs) — no free top-tick on trailed fills.
    best_ahead: the best-level size (coin) that must trade through first (charged once, at the front).
    Returns (filled_usd, filled_coins, last_fill_cell); fees NOT included."""
    if hi < lo or (budget_usd is not None and budget_usd <= 0) or \
       (budget_coins is not None and budget_coins <= 0):
        return 0.0, 0.0, -1
    seg = slice(lo, hi + 1)
    m = mid[seg]
    o = opp[seg].astype(float).copy()
    if not peg:
        ok = (m <= ref_px) if side > 0 else (m >= ref_px)
        o[~ok] = 0.0
    # queue ahead: first `best_ahead` coins of eligible flow belong to the level ahead of us
    cum = np.cumsum(o)
    avail = np.maximum(0.0, cum - max(0.0, best_ahead))          # coins available to US, cumulative
    if peg:
        pxs = m * (1.0 - hs) if side > 0 else m * (1.0 + hs)     # trailing peg fill price per cell
    else:
        px_limit = ref_px * (1.0 - hs) if side > 0 else ref_px * (1.0 + hs)
        pxs = np.full(len(m), px_limit)
    inc = np.diff(np.concatenate([[0.0], avail]))                 # coins newly available per cell
    if budget_coins is not None:
        cumc = np.cumsum(inc)
        inc = np.minimum(inc, np.maximum(0.0, budget_coins - (cumc - inc)))
    usd_inc = inc * pxs
    if budget_usd is not None:
        cumu = np.cumsum(usd_inc)
        usd_take = np.minimum(usd_inc, np.maximum(0.0, budget_usd - (cumu - usd_inc)))
    else:
        usd_take = usd_inc
    coin_take = np.where(pxs > 0, usd_take / pxs, 0.0)
    filled = float(usd_take.sum())
    if filled <= 0:
        return 0.0, 0.0, -1
    nz = np.nonzero(usd_take > 0)[0]
    return filled, float(coin_take.sum()), int(lo + nz[-1])


def simulate_swing_accum(mid, best_bid_sz, best_ask_sz, buy_vol, sell_vol, flips, *,
                         half_spread_bps: float, maker_fee_bps: float, taker_fee_bps: float,
                         S_max: float = 5_000.0, starter_frac: float = 0.25,
                         starter_window: int = 100, complete_window: int = 50,
                         confirm_mode: str = "price", confirm_k: float = 0.25,
                         swing_roll: int = 100, unload_grace: int = 300, queue_frac: float = 1.0,
                         lean=None, entry_ok=None, arm: str = "") -> AccumResult:
    """Run the accumulate executor over a (pre-gated) flip list. See module docstring.

    confirm_mode: 'price' — leg green by conf_bps = max(dump floor, confirm_k × rolling-median swing);
                  'lean'  — trailing flow lean holds on our side (requires `lean` array);
                  'price+lean' — both.
    entry_ok: optional boolean array aligned to `flips` — the TURN-SELECTION gate (dipole / fee-floor /
    controls, computed causally in the harness). Gates ENTRIES ONLY: exits always fire at the next
    opposite detected flip regardless of the gate (a gated-out exit would ride a position forever).
    The dump band mirrors the confirm band (symmetric, fee-floor floored). Thresholds derive from the
    fee/spread arithmetic + a causal rolling swing stat — fixed k across all cells, never per-window tuned.
    """
    mid = np.asarray(mid, float)
    bb = np.asarray(best_bid_sz, float); ba = np.asarray(best_ask_sz, float)
    bv = np.asarray(buy_vol, float); sv = np.asarray(sell_vol, float)
    n = len(mid)
    hs = half_spread_bps / 1e4
    fee_floor_bps = half_spread_bps + taker_fee_bps          # cost of a taker dump from mid
    flips = [(int(c), int(p), int(s)) for (c, p, s) in flips]

    # causal rolling median of realized flip-to-flip swings (bps) — the expected-swing stat
    swings = []
    med_swing = np.full(len(flips), np.nan)
    for k in range(1, len(flips)):
        a, b = flips[k - 1][0], flips[k][0]
        if 0 < a < b < n:
            swings.append(abs(mid[b] - mid[a]) / mid[a] * 1e4)
            lo = max(0, len(swings) - swing_roll)
            med_swing[k] = float(np.median(swings[lo:]))

    legs: list[AccumLeg] = []
    pos = None   # dict(side, flip_idx, qty_coins, cost_usd, starter, p2m, p2t, confirmed, cidx, heights)

    def _close(exit_maker_usd, exit_taker_usd, proceeds_usd, fees, close_idx):
        p = pos
        buy_cost = p["cost_usd"]
        net = (proceeds_usd - buy_cost) if p["side"] > 0 else (buy_cost - proceeds_usd)
        # short legs: "cost_usd" is the SELL proceeds of the entry, proceeds_usd is the buy-back cost
        net -= fees
        vw = p["vw_height"] / p["bought"] if p["bought"] > 0 else 0.0
        legs.append(AccumLeg(p["side"], p["flip_idx"], close_idx, p["bought"], p["starter"],
                             p["p2m"], p["p2t"], p["confirmed"], p["cidx"], p["dumped"],
                             exit_maker_usd, exit_taker_usd, float(net), float(fees + p["fees"]),
                             float(vw), p["maker"] + exit_maker_usd, p["taker"] + exit_taker_usd))

    for k, (ci, _pv, s) in enumerate(flips):
        if ci <= 0 or ci >= n - 2:
            continue
        nxt = flips[k + 1][0] if k + 1 < len(flips) else n - 1
        nxt = min(nxt, n - 1)

        # ---- 1. unload any opposite inventory at this turn (exits are NEVER gated) ----
        if pos is not None and pos["side"] == -s and not pos["dumped"]:
            osd = pos["side"]
            ref = mid[ci]
            gr = min(nxt - ci, unload_grace)
            # fee-aware slide-cross cell FIRST: past X = spread + taker fee of adverse slide, waiting has
            # provably cost more than crossing at the turn would have -> taker the remainder there.
            X = (2 * half_spread_bps + taker_fee_bps) / 1e4
            seg = mid[ci:ci + gr + 1]
            crossed = np.nonzero(seg < ref * (1 - X))[0] if osd > 0 else np.nonzero(seg > ref * (1 + X))[0]
            xcell = ci + int(crossed[0]) if len(crossed) else min(ci + gr, n - 1)
            # maker unload: TRAILING best offer (long) / bid (short) down the slide, up to the cross cell
            opp = bv if osd > 0 else sv                       # closing a long = we OFFER, buys lift us
            ahead = ba[ci] if osd > 0 else bb[ci]
            mk_usd, mk_coins, _ = _eligible_fill(mid, opp, ahead * queue_frac, ci, xcell, ref, -osd,
                                                 hs, budget_coins=pos["qty"], peg=True)
            mk_coins = min(mk_coins, pos["qty"])
            rem_coins = pos["qty"] - mk_coins
            tk_usd = tk_fee = 0.0
            if rem_coins * ref > 1e-9:
                tk_px = mid[xcell] * (1.0 - hs) if osd > 0 else mid[xcell] * (1.0 + hs)
                tk_usd = rem_coins * tk_px
                tk_fee = tk_usd * taker_fee_bps / 1e4
            mk_fee = mk_usd * maker_fee_bps / 1e4
            proceeds = mk_usd + tk_usd
            _close(mk_usd, tk_usd, proceeds, mk_fee + tk_fee, ci)
            pos = None
        elif pos is not None and pos["dumped"]:
            pos = None

        # ---- 2. open a new leg at this flip (ENTRY gate applies here only) ----
        if pos is not None:
            continue                                          # still holding same-side inventory: hold
        if entry_ok is not None and not bool(entry_ok[k]):
            continue                                          # turn not selected: stay flat
        ref = mid[ci]
        ms = med_swing[k]
        conf_bps = max(fee_floor_bps, confirm_k * ms) if np.isfinite(ms) else fee_floor_bps
        dump_bps = conf_bps
        # starter: fixed limit at the turn price, price-eligible + queue-honest
        opp_in = sv if s > 0 else bv
        ahead_in = bb[ci] if s > 0 else ba[ci]
        w0 = min(nxt - ci, starter_window)
        st_usd, st_coins, st_cell = _eligible_fill(mid, opp_in, ahead_in * queue_frac, ci, ci + w0,
                                                   ref, s, hs, budget_usd=starter_frac * S_max, peg=False)
        if st_usd <= 0:
            continue                                          # no starter fill before the next turn: skip
        st_fee = st_usd * maker_fee_bps / 1e4
        qty = st_coins
        pos = dict(side=s, flip_idx=ci, qty=qty, cost_usd=st_usd, bought=st_usd, starter=st_usd,
                   p2m=0.0, p2t=0.0, confirmed=False, cidx=-1, dumped=False, fees=st_fee,
                   vw_height=0.0, maker=st_usd, taker=0.0)

        # ---- 3. confirmation vs dump scan on [ci+1, nxt−1] ----
        seg = slice(ci + 1, nxt)
        m = mid[seg]
        if len(m) == 0:
            continue
        green = (m >= ref * (1 + conf_bps / 1e4)) if s > 0 else (m <= ref * (1 - conf_bps / 1e4))
        red = (m <= ref * (1 - dump_bps / 1e4)) if s > 0 else (m >= ref * (1 + dump_bps / 1e4))
        if confirm_mode in ("lean", "price+lean") and lean is not None:
            lseg = np.sign(np.asarray(lean, float)[seg]) == np.sign(s)
            green = (green & lseg) if confirm_mode == "price+lean" else lseg
        gi = np.nonzero(green)[0]
        ri = np.nonzero(red)[0]
        tg = ci + 1 + int(gi[0]) if len(gi) else -1
        tr = ci + 1 + int(ri[0]) if len(ri) else -1

        if tr >= 0 and (tg < 0 or tr < tg):
            # ---- quick dump: red before confirmation, position is only the starter ----
            dump_px = mid[tr] * (1.0 - hs) if s > 0 else mid[tr] * (1.0 + hs)
            d_usd = qty * dump_px
            d_fee = d_usd * taker_fee_bps / 1e4
            pos["dumped"] = True
            _close(0.0, d_usd, d_usd, d_fee, tr)
            pos["dumped"] = True   # marker so the next flip doesn't try to unload again
            continue

        if tg >= 0:
            # ---- confirmed: ALL IN on the remainder as fast as fills allow ----
            pos["confirmed"] = True; pos["cidx"] = tg
            R = S_max - pos["bought"]
            if R > 0:
                cw = min(nxt - 1 - tg, complete_window)
                opp2 = sv if s > 0 else bv
                ahead2 = bb[tg] if s > 0 else ba[tg]
                mk2, q2, _ = _eligible_fill(mid, opp2, ahead2 * queue_frac, tg, tg + cw, mid[tg], s,
                                            hs, budget_usd=R, peg=True)
                px2 = mid[tg] * (1.0 - hs) if s > 0 else mid[tg] * (1.0 + hs)   # height metric only
                fee2 = mk2 * maker_fee_bps / 1e4
                R2 = R - mk2
                tk2 = q3 = fee3 = 0.0
                # fee-aware taker completion: only if the expected remaining move pays the crossing cost
                height = abs(mid[min(tg + cw, n - 1)] - ref) / ref * 1e4
                if R2 > 1.0 and np.isfinite(ms) and (ms - height) > (taker_fee_bps + half_spread_bps):
                    t3 = min(tg + cw, n - 1)
                    px3 = mid[t3] * (1.0 + hs) if s > 0 else mid[t3] * (1.0 - hs)
                    tk2 = R2
                    q3 = tk2 / px3
                    fee3 = tk2 * taker_fee_bps / 1e4
                    pos["taker"] += tk2
                pos["qty"] += q2 + q3
                pos["cost_usd"] += mk2 + tk2
                pos["bought"] += mk2 + tk2
                pos["p2m"] += mk2; pos["p2t"] += tk2
                pos["fees"] += fee2 + fee3
                pos["maker"] += mk2
                add_px = (mk2 * px2 + (tk2 and tk2 * (mid[min(tg + cw, n-1)]))) / max(mk2 + tk2, 1e-9)
                pos["vw_height"] += (mk2 + tk2) * abs(add_px - ref) / ref * 1e4
        # unconfirmed & never red: ride the starter to the next turn (handled at the next flip)

    if pos is not None and not pos["dumped"] and len(flips):
        # flatten any open inventory at the last flip cell price (taker, end-of-window honesty)
        last = min(flips[-1][0], n - 1)
        px = mid[last] * (1.0 - hs) if pos["side"] > 0 else mid[last] * (1.0 + hs)
        v = pos["qty"] * px
        _close(0.0, v, v, v * taker_fee_bps / 1e4, last)

    if not legs:
        return AccumResult(arm, len(flips), 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, legs)
    nets = np.asarray([l.net_usd for l in legs])
    notion = np.asarray([l.bought_usd for l in legs])
    w = nets > 0
    return AccumResult(
        arm=arm, n_flips=len(flips), n_legs=len(legs),
        n_confirmed=int(sum(1 for l in legs if l.confirmed)),
        n_dumped=int(sum(1 for l in legs if l.dumped)),
        net_usd=float(nets.sum()), fees_usd=float(sum(l.fees_usd for l in legs)),
        win_frac=float(w.mean()),
        med_win_notional=float(np.median(notion[w])) if w.any() else 0.0,
        med_loss_notional=float(np.median(notion[~w])) if (~w).any() else 0.0,
        maker_usd=float(sum(l.maker_usd for l in legs)),
        taker_usd=float(sum(l.taker_usd for l in legs)), legs=legs)
