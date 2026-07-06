"""_kraken_legbleed.py — WHERE DO THE NEW LEGS BLEED? (S65, Greg).

The front-of-line leg explosion is churn (money is in the big swings). This dissects the LOSING legs to
locate the bleed: by HOLD DURATION (short = quick whipsaw churn), by |swing| size, and by whether the leg
is a QUICK-REVERSAL (opened soon after the prior leg closed = the zigzag flipping on noise). If the bleed
is short-hold small-swing whipsaws, a coarser REV / min-hold kills it; if it's long-hold big-swing legs,
it's trend-fighting (direction).

Per cell (front-of-line, live run_stream): loss $/hr by hold bucket, by swing bucket, and the quick-
reversal share of the loss. PROVISIONAL: one 30h window.

Usage:  python scripts/_kraken_legbleed.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import CELLS, CAP, load_book, run_cell   # noqa: E402  (live path)

HOLD = [0, 10, 30, 60, 120, 300, 1e9]        # hold-duration buckets (seconds)
SW = [0, 2, 5, 10, 20, 1e9]                    # |swing| buckets (bps)


def main():
    print("=== KRAKEN — WHERE DO THE NEW LEGS BLEED? (front-of-line losers) ===")
    books = {}
    for cell in CELLS:
        if cell["active"]:
            bk = load_book(cell["coin"])
            if bk is not None:
                books[cell["coin"]] = bk
            else:
                cell["active"] = False
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1; hrs = ov_sec / 3600.0
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = books[cell["coin"]]; s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        _, r = run_cell(cell, clip, "front")
        legs = sorted(r.legs, key=lambda l: int(l.open_idx))
        net = np.array([l.net_bps for l in legs]); d0 = net / 1e4 * CAP
        hold = np.array([int(l.close_idx) - int(l.open_idx) for l in legs])
        sw = np.array([abs(l.swing_bps) for l in legs])
        # quick-reversal: opened within 30s of the prior leg's close
        prev_close = np.array([int(legs[i - 1].close_idx) if i > 0 else -10 ** 9 for i in range(len(legs))])
        gap = np.array([int(legs[i].open_idx) for i in range(len(legs))]) - prev_close
        quick = gap <= 30
        los = d0 < 0
        tag = f"{cell['coin']}{'*' if cell['side'] < 0 else ''}"
        tot_loss = d0[los].sum()
        print(f"\n[{tag}]  {len(legs)} legs  net {d0.sum()/hrs:+.2f}$/hr  |  losers {los.sum()} "
              f"lose {tot_loss/hrs:+.2f}$/hr  median-hold {int(np.median(hold))}s")
        # loss by hold bucket
        print("   loss by HOLD:   " + "  ".join(
            f"{HOLD[i]:g}-{HOLD[i+1]:g}s:{d0[los & (hold>=HOLD[i]) & (hold<HOLD[i+1])].sum()/hrs:+.1f}"
            f"/{int((los & (hold>=HOLD[i]) & (hold<HOLD[i+1])).sum())}" for i in range(len(HOLD)-1)))
        # loss by swing bucket
        print("   loss by |SWING|:" + "  ".join(
            f"{SW[i]:g}-{SW[i+1]:g}:{d0[los & (sw>=SW[i]) & (sw<SW[i+1])].sum()/hrs:+.1f}"
            f"/{int((los & (sw>=SW[i]) & (sw<SW[i+1])).sum())}" for i in range(len(SW)-1)))
        # quick-reversal share of loss
        qloss = d0[los & quick].sum(); qn = int((los & quick).sum())
        print(f"   QUICK-REVERSAL (open<=30s after prior close): {qn} losers, {qloss/hrs:+.2f}$/hr "
              f"= {100*qloss/tot_loss if tot_loss<0 else 0:.0f}% of all loss  "
              f"(these legs whipsaw on noise)")
    print("\n  [$/hr / n] per bucket. If loss concentrates in short-hold / small-swing / quick-reversal legs,")
    print("  the bleed is whipsaw churn -> coarser REV + a min-hold kills it. ⚠ one 30h window.")


if __name__ == "__main__":
    main()
