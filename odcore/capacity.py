"""odcore/capacity.py — per-leg DOLLAR fill-capacity (S66 architect read: THE missing live mechanic).

WHY THIS EXISTS: the executor books maker fills capped by NOTHING (`swing_maker` fill models fill the
next opposing print of any size, or the best-level queue then still book a full fill). On thin books a
$5k leg is hours of the entire daily volume, so every thin-book $/hr today is FICTION. This module bounds
a leg's realized fill by the REAL opposing taker $ that trades through our fixed limit — the cap the
allocator/capacity work needs. Deployable capital is then Σ per-cell caps over simultaneously-live cells;
you scale by adding CELLS, not $/cell.

MODEL (a resting maker leg of desired notional D, side +1 long/bid <- SELL flow, -1 short/ask <- BUY flow):
  flow-bound (v1):   cap = Σ opposing coin-volume over the entry window at PRICE-ELIGIBLE cells · px
  queue-honest (v2): cap = max(0, opposing_vol − best_level_size_ahead·queue_frac) · px   (needs BOOK depth)
  realized fill = min(D, cap);  leg PnL scales by realized/D (same net_bps on the filled portion).
On TAPE (mid/buy/sell, no book depth) only the flow-bound is available; pass best_ahead when a book is
present for the queue-honest haircut. Exit side left un-marked (turns are ~2x-volume climaxes, S40) — the
entry side is the tighter constraint, so leg capacity is bounded by entry-window opposing flow (conservative).

Venue-agnostic; meant to be consumed by run_stream/run_cell (live) and the sims UNIFORMLY (sim = live code).
PROVENANCE — a faithful promotion of scripts/_capacity_model.py::_leg_caps:
  S50  FILL_W entry-window bound (Greg: whole-hold accumulation was the "coding issue" that made caps wrong)
  S51  rebate/spread frame (leg indices are fee/spread-independent, so caps are computed once per cell)
  S52  price-eligibility fix (a fixed limit only fills where the venue best is at-or-through it; summing ALL
       window flow overstated mk0 $/hr on every cell — eligibility is the default).
Canary: scripts/_s66_canary_capacity.py proves caps_for_legs reproduces _leg_caps v1/v2 bit-for-bit.
"""
from __future__ import annotations

import numpy as np

# cells the resting order stays working after the fill cell (a TIF / cancel-remainder window). A fixed
# per-turn position fills NEAR the turn (S40 climax volume); it does NOT keep scaling into the whole adverse
# leg. Bounding to this window (not the whole hold) removes the S50 whole-hold-accumulation artifact.
# Units are BINS: ~1.0s at 100ms book bins, ~10s at 1s tape bins. None = rest until the leg close.
FILL_W = 10


# ⚠ S66 CAUSALITY LESSON (Greg's code-fix instinct + the adversarial Kraken agent): it is TEMPTING to say a
# maker-at-the-turn fills from the capitulation CLIMAX at the pivot, and to count flow in a window [flip-W, flip+W].
# That is LOOK-AHEAD for the DEPLOYED one-sided strategy: you post the bid only AFTER the flip CONFIRMS (WFLIP=600
# lag), so any pre-flip climax already traded before your order existed — you cannot fill from it. Counting it
# spuriously made WINNERS look fillable (winCap $15->$206) and flipped BTC/ETH capacity-capped $/hr fake-positive.
# CAUSAL windows only: "open" = forward from the actual fill cell open_idx (S50/_leg_caps, the honest default);
# "pivot" here = forward from the CONFIRM flip_idx (a hair more generous than open, still causal). Both give
# winCap ~$15-41 and NEGATIVE capacity-capped $/hr on every major = the S45/S56 winners-invisible / fill-is-the-wall
# law. A TWO-SIDED always-quoting MM (a different strategy) could capture the pre-turn climax; the one-sided cannot.
PIVOT_W = None   # forward from flip to close by default (causal); an int caps the forward window in cells


def leg_capacity_usd(side, open_idx, close_idx, flip_idx, mid, buy, sell,
                     *, window=FILL_W, price_eligible=True, best_ahead=None, queue_frac=1.0,
                     anchor="open", pivot_w=PIVOT_W):
    """$ fill-capacity for ONE maker leg, bounded by real opposing flow (CAUSAL only — see the CAUSALITY LESSON above).

    side: +1 long (bid, filled by SELL flow) / -1 short (ask, filled by BUY flow).
    open_idx/close_idx/flip_idx: leg cell indices (flip = the confirm / the price-eligibility ref).
    mid/buy/sell: 1-cell-uniform arrays (mid price, taker BUY $-vol proxy, taker SELL $-vol proxy) in COIN units.
    anchor: "open" = forward from the actual fill cell open_idx over `window` cells (S50/_leg_caps); "pivot" =
            forward from the CONFIRM flip_idx to close (or +pivot_w cells) — causal, slightly more generous than open.
    window: cells the order stays working after open (FILL_W), open-anchor only; None = until close.
    price_eligible: only count flow in cells where the venue best is at-or-through our post price (S52).
    best_ahead: best-level resting size AHEAD of us (coin units) -> queue-honest haircut; None = flow-bound.
    Returns capacity in QUOTE ($) units.
    """
    o, c, ci = int(open_idx), int(close_idx), int(flip_idx)
    if c <= o:
        return 0.0
    if anchor == "pivot":
        lo = ci                                                    # CAUSAL: from the confirm forward (never pre-flip)
        hi = c if pivot_w is None else min(c, ci + int(pivot_w))
        seg = slice(lo, hi + 1)
        px_i = ci
    else:
        end = c if window is None else min(c, o + window)
        seg = slice(o, end + 1)
        px_i = o
    opp_arr = (sell if side > 0 else buy)[seg]
    if price_eligible:
        m = mid[seg]
        ok = (m <= mid[ci]) if side > 0 else (m >= mid[ci])
        opp = float(np.sum(opp_arr[ok]))
    else:
        opp = float(np.sum(opp_arr))
    if best_ahead is not None:
        opp = max(0.0, opp - float(best_ahead) * queue_frac)
    return opp * float(mid[px_i])


def caps_for_legs(legs, mid, buy, sell, *, window=FILL_W, price_eligible=True,
                  bb=None, ba=None, queue_frac=1.0, anchor="open", pivot_w=PIVOT_W):
    """Per-leg $ caps for a list of SwingLeg (needs .side/.open_idx/.close_idx/.flip_idx).
    anchor: "open" (S50/_leg_caps) or "pivot" (maker-at-the-turn climax fill, S66 — winner-fill fix).
    bb/ba: best bid/ask resting sizes per cell (BOOK) -> queue-honest; None on both = flow-bound (tape)."""
    out = np.empty(len(legs), dtype=float)
    for k, l in enumerate(legs):
        ahead = None
        if bb is not None and ba is not None:
            aidx = int(l.flip_idx) if anchor == "pivot" else int(l.open_idx)
            ahead = (bb if l.side > 0 else ba)[aidx]
        out[k] = leg_capacity_usd(l.side, l.open_idx, l.close_idx, l.flip_idx, mid, buy, sell,
                                  window=window, price_eligible=price_eligible,
                                  best_ahead=ahead, queue_frac=queue_frac,
                                  anchor=anchor, pivot_w=pivot_w)
    return out


def realized_fill_usd(desired_usd, cap_usd):
    """Realized maker fill = min(desired notional, capacity). Both scalar or array. PnL scales by realized/desired."""
    return np.minimum(np.asarray(desired_usd, dtype=float), np.asarray(cap_usd, dtype=float))


def cell_capacity_summary(legs, mid, buy, sell, *, window=FILL_W, price_eligible=True,
                          bb=None, ba=None, queue_frac=1.0, pct=(50, 75, 90)):
    """Diagnostic: per-cell fillable-$ distribution across legs (the deployable per-leg size for this cell).
    Returns dict(n_legs, median_cap, mean_cap, pXX...). The allocator caps each leg at ~a low percentile."""
    caps = caps_for_legs(legs, mid, buy, sell, window=window, price_eligible=price_eligible,
                         bb=bb, ba=ba, queue_frac=queue_frac)
    out = {"n_legs": int(len(caps)), "mean_cap_usd": float(np.mean(caps)) if len(caps) else 0.0,
           "median_cap_usd": float(np.median(caps)) if len(caps) else 0.0}
    for p in pct:
        out[f"p{p}_cap_usd"] = float(np.percentile(caps, p)) if len(caps) else 0.0
    return out
