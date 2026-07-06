"""_kraken_revsweep.py — per-coin REV (swing-floor) sweep (S65, Greg).

The front-of-line churn finding says REV=0.1 is too fine. But Greg: "don't cut churn if it's POSITIVE,
only if it's NEGATIVE." So the right knob is the per-coin REV that MAXIMISES $/hr — that inherently KEEPS
a coin's fine legs when they're net-positive (max stays at fine REV) and only coarsens where the cut legs
were net-negative (coarsening lifts $/hr). Sweeps REV per coin at front-of-line through the LIVE path with
each cell's employed stack (direction, early-arm, deep-bail, enticing), and marks the max-$/hr REV.

PROVISIONAL: one 30h book window — the REV pick needs a 30d-tape/Tardis confirm before it goes live.

Usage:  python scripts/_kraken_revsweep.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402
from odcore.platform import run_stream                                    # noqa: E402  (live path)
from basket_sim_kraken import CELLS, CAP, load_book, MAKER_FEE, TAKER_FEE, WFLIP  # noqa: E402

REVS = [0.05, 0.08, 0.10, 0.13, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]


def run(cell, bk, rev):
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    if cell["eps"] is not None:
        flips, _ = retime_flips(mid, buy, sell, WFLIP, rev, cell["eps"])
    else:
        flips, _ = detect_flips(lean_series(buy, sell, WFLIP), rev)
    if cell["side"] < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    xs = {"kind": "price_stop", "x_bp": float(cell["bail"]), "action": "flat", "side": 0} \
        if cell["bail"] is not None else None
    res, _ = run_stream(mid, buy, sell, flips, best_bid_sz=bb, best_ask_sz=ba,
                        half_spread_bps=hs, maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
                        grace=cell["grace"], exit_spec=xs, fill_model="front",
                        close_improve_bps=cell["improve"])
    return res


def main():
    print("=== KRAKEN per-coin REV (swing-floor) sweep — pick max-$/hr REV (keep positive churn, cut negative) ===")
    best = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        coin = cell["coin"]; bk = load_book(coin)
        if bk is None:
            print(f"\n[{coin}] no book"); continue
        hrs = bk["n"] / 3600.0
        rows = []
        for rev in REVS:
            r = run(cell, bk, rev)
            dph = r.total_net_bps / 1e4 * CAP / hrs
            rows.append((rev, dph, r.n_legs, r.net_per_leg_bps))
        bi = int(np.argmax([x[1] for x in rows]))
        best[coin] = rows[bi][0]
        tag = f"{coin}{'*' if cell['side'] < 0 else ''}"
        print(f"\n[{tag}]  (deployed REV=0.10)   best REV = {rows[bi][0]} @ {rows[bi][1]:+.2f} $/hr")
        print(f"   {'REV':>6}{'$/hr':>9}{'legs':>7}{'net/leg':>9}")
        for rev, dph, n, npl in rows:
            mark = "  <== max" if rev == rows[bi][0] else ("   (deployed)" if rev == 0.10 else "")
            print(f"   {rev:>6.2f}{dph:>+9.2f}{n:>7}{npl:>+9.2f}{mark}")
    print("\n  best REV per coin: " + "  ".join(f"{c}={best[c]}" for c in best))
    print("  max-$/hr REV keeps positive churn (max at fine REV) and cuts negative churn (max at coarse REV).")
    print("  ⚠ ONE 30h book window — confirm on a 30d tape / Tardis before this REV goes live.")


if __name__ == "__main__":
    main()
