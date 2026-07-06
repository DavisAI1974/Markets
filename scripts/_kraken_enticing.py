"""_kraken_enticing.py — front-of-line vs enticing-quote maker close (S65, Greg).

Two questions:
  #2 ARE WE FRONT-OF-LINE?  The basket-sim "honest" number used fill_model="queue" queue_frac=1.0 =
     BACK of the displayed best-level queue (pessimistic). The deployed run_cell uses fill_model="front"
     = front-of-line (the S46 premise). PART A sweeps queue_frac 1.0(back)->0.0(front) to bracket it.
  #1 ENTICING CLOSE.  To actually EARN front-of-line you post a price-IMPROVED quote: concede a little
     half-spread to jump the queue and get a MAKER close instead of crossing to taker. PART B sweeps
     close_improve_bps (the new opt-in swing_maker mechanic) at the pessimistic back-of-line base and
     shows it converting forced-taker closes -> maker.

Per-cell deployed config (kr_mk0). PROVISIONAL: one ~30h low-edge book window.

Usage:  python scripts/_kraken_enticing.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips             # noqa: E402
from odcore.swing_maker import simulate_swing_maker                    # noqa: E402
from basket_sim_kraken import CAP, load_book, MAKER_FEE, TAKER_FEE, WFLIP, REV  # noqa: E402

# coin, side, deep-bail, grace
CELLS = [("eth", +1, 100.0, 300), ("btc", +1, 80.0, 300),
         ("sol", -1, None, 300), ("xrp", +1, None, 300)]
QFRAC = [1.0, 0.5, 0.25, 0.0]              # back-of-line -> front-of-line
IMPROVE = [0.0, 0.5, 1.0, 2.0, 3.0]        # enticing concession bps


def run(bk, side, bail, grace, qfrac, improve):
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    xs = {"kind": "price_stop", "x_bp": float(bail), "action": "flat", "side": 0} if bail else None
    return simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE, cover_grace=grace,
                                exit_spec=xs, fill_model="queue", queue_frac=qfrac,
                                close_improve_bps=improve)


def dph(r, hrs):
    return r.total_net_bps / 1e4 * CAP / hrs


def main():
    print("=== KRAKEN front-of-line vs ENTICING maker close (S65) — honest queue fill ===")
    books = {c: load_book(c) for c, *_ in CELLS}
    for coin, side, bail, grace in CELLS:
        bk = books[coin]
        if bk is None:
            print(f"[{coin}] no book"); continue
        hrs = bk["n"] / 3600.0
        tag = f"{coin}{'*' if side < 0 else ''}"
        print(f"\n[{tag}]  bail={bail} grace={grace}  ({hrs:.1f}h)  hs={bk['hs']:.2f}bp")
        # PART A: queue position (back -> front), no enticing
        print("  A) queue position (no enticing):   " +
              "  ".join(f"qf{q:<4}={dph(run(bk, side, bail, grace, q, 0.0), hrs):+6.1f}" for q in QFRAC)
              + "   [$/hr; qf1.0=back, qf0.0=front-of-line]")
        rback = run(bk, side, bail, grace, 1.0, 0.0)
        rfront = run(bk, side, bail, grace, 0.0, 0.0)
        print(f"     fill%: back={100*rback.fill_rate:.0f} front={100*rfront.fill_rate:.0f}   "
              f"forced-taker%: back={100*rback.n_taker_closes/max(rback.n_legs,1):.0f} "
              f"front={100*rfront.n_taker_closes/max(rfront.n_legs,1):.0f}")
        # PART B: enticing concession at the pessimistic back-of-line base (qf=1.0)
        print("  B) enticing close @ back-of-line (qf1.0):")
        print(f"     {'improve_bp':>11}{'$/hr':>8}{'fill%':>7}{'tkCl%':>7}{'makerCl%':>9}{'win%':>6}")
        for imp in IMPROVE:
            r = run(bk, side, bail, grace, 1.0, imp)
            tk = 100 * r.n_taker_closes / max(r.n_legs, 1)
            mk = 100 - tk
            print(f"     {imp:>11.1f}{dph(r, hrs):>+8.1f}{100*r.fill_rate:>6.0f}%{tk:>6.0f}%"
                  f"{mk:>8.0f}%{100*r.win_frac:>5.0f}%")
    print("\n  A answers 'are we front-of-line': deployed run_cell uses fill_model=front (front-of-line);")
    print("  the basket-sim honest number used queue_frac=1.0 (back-of-line) = the pessimistic bound.")
    print("  B: enticing concedes improve_bp to jump to front -> converts forced-taker closes to MAKER.")
    print("  ⚠ one ~30h LOW-EDGE window — the MECHANISM transfers, the $/hr won't; re-grade on Tardis.")


if __name__ == "__main__":
    main()
