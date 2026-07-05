"""_s63_kraken_covergrace.py — THE SQUEEZE: cover_grace vs the forced-taker leak (honest Kraken fill).

The maker-fill losers were dominated by FORCED-TAKER closes (~40% fill -> 60% cross to taker = the loss).
cover_grace (S48) rests the cover up to G cells PAST the turn to catch a maker fill before crossing.
Sweeps G on the honest queue-fill model per coin: taker-close %, fill_rate, net $/hr — does the grace
convert the forced-taker losses back to maker fills and recover the edge? SOL reversed.

Usage:  python scripts/_s63_kraken_covergrace.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.swing_maker import simulate_swing_maker                   # noqa: E402
from _s63_kraken_makerfill import load_book_1s, WFLIP, REV, MAKER_FEE, TAKER_FEE  # noqa: E402

CAP = 5000.0
KBOOK = "/tmp/kbook"
CELLS = [("eth", 0), ("btc", 0), ("sol", 1)]
GRACES = [0, 60, 120, 300, 600]


def main():
    print("=== SQUEEZE: cover_grace on the honest Kraken maker fill (convert forced-taker -> maker) ===")
    print(f"   maker_fee={MAKER_FEE} taker={TAKER_FEE}bp; $/hr @ $5k over the book window\n")
    for coin, rev in CELLS:
        path = f"{KBOOK}/{coin}_book.jsonl"
        if not os.path.exists(path):
            print(f"[{coin}] no book"); continue
        mid, bb, ba, buy, sell, hs, hrs = load_book_1s(path)
        lean = lean_series(buy, sell, WFLIP); flips, _ = detect_flips(lean, REV)
        if rev:
            flips = [(ci, pv, -s) for (ci, pv, s) in flips]
        print(f"[{coin}{'*' if rev else ''}]  book {hrs:.1f}h  hs={hs:.2f}bp")
        print(f"   {'grace':>6}{'fill%':>7}{'takerCl%':>9}{'win%':>6}{'net/leg':>9}{'$/hr':>8}")
        for g in GRACES:
            r = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                     maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                                     fill_model="queue", queue_frac=1.0, cover_grace=g)
            net = np.array([lg.net_bps for lg in r.legs])
            win = 100 * np.mean(net > 0) if len(net) else 0
            tk = 100 * r.n_taker_closes / r.n_legs if r.n_legs else 0
            dph = r.total_net_bps / 1e4 * CAP / hrs
            print(f"   {g:>6}{100*r.fill_rate:>6.0f}%{tk:>8.0f}%{win:>6.0f}{r.net_per_leg_bps:>+9.2f}{dph:>+8.2f}")
        print()


if __name__ == "__main__":
    main()
