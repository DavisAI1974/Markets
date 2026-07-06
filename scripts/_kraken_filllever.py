"""_kraken_filllever.py — can we LIFT the bleeders by fixing the FILL? (S65)

The winner/loser anatomy (analyze_basket_kraken.py) showed eth/btc/sol bleed entirely through
FORCED-TAKER closes (maker-closed legs are net positive/breakeven; the ~30-43% that can't get a
maker fill cross to taker and win only 11-32%). The fix is the FILL, two levers:
  cover_grace  — rest the maker cover further past the turn (catch a maker fill before crossing)
  swing-floor  — coarser REV -> fewer, BIGGER swings, each easier to fill (fill-vs-edge knob)

Sweeps both on the honest queue-fill for the three bleeders, holding each cell's deployed direction
+ deep-bail. Reports honest $/hr, fill%, forced-taker%, legs — does a fill config recover the
+10..+17 $/hr the fill is currently giving up? PROVISIONAL: one ~30h low-edge book window.

Usage:  python scripts/_kraken_filllever.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips             # noqa: E402
from odcore.swing_maker import simulate_swing_maker                    # noqa: E402
from basket_sim_kraken import CAP, load_book, MAKER_FEE, TAKER_FEE, WFLIP  # noqa: E402

# deployed per-cell: side, deep-bail (the bleeders only)
CELLS = [("eth", +1, 100.0), ("btc", +1, 80.0), ("sol", -1, None)]
GRACE = [300, 600, 1200]
REVS = [0.10, 0.15, 0.20, 0.30]


def run(bk, side, bail, rev, grace):
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, rev)
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    xs = {"kind": "price_stop", "x_bp": float(bail), "action": "flat", "side": 0} if bail else None
    r = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                             maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                             cover_grace=grace, exit_spec=xs, fill_model="queue", queue_frac=1.0)
    return r


def main():
    print("=== KRAKEN FILL-LEVER SWEEP — lift the bleeders via cover_grace x swing-floor (honest fill) ===")
    books = {c: load_book(c) for c, _, _ in CELLS}
    hrs = None
    for coin, side, bail in CELLS:
        bk = books[coin]
        if bk is None:
            print(f"[{coin}] no book"); continue
        hrs = bk["n"] / 3600.0
        print(f"\n[{coin}{'*' if side < 0 else ''}]  bail={bail}  ({hrs:.1f}h)   honest $/hr @ ${CAP:.0f}")
        hdr = "REV/grace"
        print(f"   {hdr:>10}" + "".join(f"{g:>10}" for g in GRACE))
        for rev in REVS:
            row = [f"{rev:>10.2f}"]
            for g in GRACE:
                r = run(bk, side, bail, rev, g)
                dph = r.total_net_bps / 1e4 * CAP / hrs
                ft = 100 * r.n_taker_closes / r.n_legs if r.n_legs else 0
                row.append(f"{dph:>+6.1f}/{100*r.fill_rate:>2.0f}")
            print("".join(f"{x:>10}" for x in row))
        # a fill-detail line at the best-looking config (grace1200, rev0.2)
        r = run(bk, side, bail, 0.20, 1200)
        ft = 100 * r.n_taker_closes / r.n_legs if r.n_legs else 0
        print(f"   @ rev0.20/grace1200: legs={r.n_legs} fill%={100*r.fill_rate:.0f} forced-taker%={ft:.0f} "
              f"win%={100*r.win_frac:.0f} net/leg={r.net_per_leg_bps:+.2f}bp")
    print("\n  cells: $/hr / fill%.  Deployed baseline = rev0.10/grace300. * = SOL reversed.")
    print("  ⚠ one ~30h LOW-EDGE book window — provisional; the LIFT MECHANISM (fill) transfers, the $/hr won't.")


if __name__ == "__main__":
    main()
