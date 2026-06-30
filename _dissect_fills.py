"""_dissect_fills.py — per-fill autopsy of the maker gate arm (S45).

The deploy map reports one number per cell (gross/fill). This opens the hood: it reproduces the
EXACT gate-arm fills the deploy map simulates for one cell, and for each fill decomposes the PnL into
the only two things that move it (maker_book.py:99-108):

    gross_bps = half_spread_bps + drift_bps
    drift_bps = signed(mid[exit] - mid[post]) / mid[post] * 1e4         # in OUR direction (+ = good)

and splits drift into the two legs that produce it:
    d_wait = signed(mid[fill] - mid[post])     # adverse selection WHILE QUEUED (post -> fill)
    d_hold = signed(mid[exit] - mid[fill])     # move during the hold (fill -> fill+hold)

A maker earns the half-spread but is filled exactly when flow is against the quote, so d_wait is
systematically negative and usually swamps the half-spread. This prints ~10 fills sampled across the
gross distribution (so they are representative, not cherry-picked) + the aggregate that the deploy map
verdict is built from.

Run:  python _dissect_fills.py <coin> [K] [kgate]    e.g.  python _dissect_fills.py sol 1 1.5
"""
from __future__ import annotations

import sys

import numpy as np

from _liquidity_dive import build_channels, median_spread_bps
from odcore import quiet_floor
from odcore.maker_book import _first_fill_index

FLOW_W = 20
TRAIN_FRAC = 0.6
FILL_WINDOW = 10
HOLD = 1
QUEUE_FRAC = 1.0


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    kgate = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"

    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)  # top-of-book queue size
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid)
    cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0

    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    gated = qf.gated_signal(imb, k=kgate)                 # +1/-1 when gate open, else 0

    # restrict to the held-out test slice exactly as the deploy map does (te = [cut, n))
    side = np.zeros(n)
    side[cut:] = gated[cut:]

    qa = np.where(side > 0, bb, ba) * QUEUE_FRAC
    fill_bid = _first_fill_index(qa, sell, FILL_WINDOW)   # a bid is filled by SELL flow
    fill_ask = _first_fill_index(qa, buy, FILL_WINDOW)    # an ask is filled by BUY flow
    filled_at = np.where(side > 0, fill_bid, np.where(side < 0, fill_ask, -1))

    post = side != 0
    filled = post & (filled_at >= 0) & ((filled_at + HOLD) <= (n - 1))
    idx = np.where(filled)[0]

    hs_price = (hs_bps / 1e4) * mid
    entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    fi = filled_at
    ei = np.clip(fi + HOLD, 0, n - 1)

    sgn = side[idx]
    mp, mf, me = mid[idx], mid[fi[idx]], mid[ei[idx]]
    en = entry[idx]
    d_wait = sgn * (mf - mp) / mp * 1e4
    d_hold = sgn * (me - mf) / mp * 1e4
    drift = sgn * (me - mp) / mp * 1e4
    gross = sgn * (me - en) / mp * 1e4                     # == hs_bps + drift (per maker_book)
    wait_cells = fi[idx] - idx

    nf = len(idx)
    print(f"\n# FILL AUTOPSY — {coin}_coinbase  K={K} (top-of-book imbalance)  gate k={kgate}  "
          f"hold={HOLD} cell (100ms)  fill_window={FILL_WINDOW} (1s)")
    print(f"# half_spread = {hs_bps:.4f} bps   test fills = {nf}   "
          f"(gross = half_spread + drift; drift = d_wait + d_hold, signed in our direction)\n")

    # 10 fills sampled evenly across the gross distribution -> representative of the spread
    order = np.argsort(gross)
    picks = order[np.linspace(0, nf - 1, 10).round().astype(int)]
    hdr = (f"{'#':>3} {'side':>4} {'wait':>4} {'mid_post':>11} {'mid_fill':>11} {'mid_exit':>11} "
           f"{'half_sp':>8} {'d_wait':>8} {'d_hold':>8} {'drift':>8} {'GROSS':>8}")
    print(hdr)
    for r, k in enumerate(picks):
        sd = "bid" if sgn[k] > 0 else "ask"
        print(f"{r+1:>3} {sd:>4} {wait_cells[k]:>4} {mp[k]:>11.5f} {mf[k]:>11.5f} {me[k]:>11.5f} "
              f"{hs_bps:>8.4f} {d_wait[k]:>8.4f} {d_hold[k]:>8.4f} {drift[k]:>8.4f} {gross[k]:>8.4f}")

    print(f"\n# AGGREGATE over all {nf} test fills (this is what the deploy-map verdict averages):")
    print(f"#   mean half_spread = {hs_bps:>8.4f} bps   (what you earn if the mid never moves)")
    print(f"#   mean d_wait      = {d_wait.mean():>8.4f} bps   (adverse selection while queued, post->fill)")
    print(f"#   mean d_hold      = {d_hold.mean():>8.4f} bps   (move during the {HOLD}-cell hold)")
    print(f"#   mean drift       = {drift.mean():>8.4f} bps   (= d_wait + d_hold; the adverse-selection term)")
    print(f"#   mean GROSS/fill  = {gross.mean():>8.4f} bps   (= half_spread + drift)")
    print(f"#   fills with gross<0: {100*(gross<0).mean():.1f}%   median wait = {int(np.median(wait_cells))} cells "
          f"({100*np.median(wait_cells):.0f}ms)")
    fav = drift > 0
    print(f"#   when filled: mid moved AGAINST us {100*(drift<0).mean():.1f}% of the time "
          f"(that is the adverse selection).")


if __name__ == "__main__":
    main()
