"""_kraken_newlegs.py — LOOK AT THE NEW LEGS (S65, Greg): 2.5x more trades but only ~a couple $/hr.

Front-of-line fires ~2.5x more legs than back-of-line, but $/hr is small (~0.9 bp/leg). Greg: "it doesn't
make sense that we have 2.5x more trades and they're only adding a couple bucks/hr." This dissects the
front-of-line legs by SIZE to answer: is the money in a few real legs, or spread across tiny sub-bp CHURN
round-trips (the S56 "rebate-only economics" pattern) that an optimistic front-of-line fill flatters?

Per cell (front-of-line, live run_stream):
  1. size buckets by |swing_bps| — count, $/hr contribution, win%, net/leg. Where does the money live?
  2. swing-FLOOR sweep — keep only legs with swing >= X: how $/hr and leg-count move. If dropping the
     tiny legs barely dents $/hr, they are churn (trade fewer/bigger via coarser REV).

ARCHITECTURE: uses the live path via basket_sim_kraken (no reimplementation). PROVISIONAL: one 30h window.

Usage:  python scripts/_kraken_newlegs.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import CELLS, CAP, load_book, run_cell   # noqa: E402  (live path)

EDGES = [0, 1, 2, 5, 10, 20, 1e9]                    # |swing_bps| bucket edges
FLOORS = [0, 1, 2, 3, 5, 8]                           # swing-floor thresholds (bps)


def main():
    print("=== KRAKEN — LOOK AT THE NEW LEGS (front-of-line): are they real or sub-bp churn? ===")
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
        legs = r.legs
        net = np.array([l.net_bps for l in legs])
        sw = np.array([abs(l.swing_bps) for l in legs])
        dollars = net / 1e4 * CAP
        tag = f"{cell['coin']}{'*' if cell['side'] < 0 else ''}"
        print(f"\n[{tag}]  {len(legs)} legs  {dollars.sum()/hrs:+.2f} $/hr  "
              f"net/leg={net.mean():+.2f}bp  median|swing|={np.median(sw):.2f}bp  "
              f"p90|swing|={np.percentile(sw,90):.1f}bp")
        # size buckets
        print(f"   {'|swing| bp':>12}{'n':>6}{'%legs':>7}{'$/hr':>8}{'%$/hr':>7}{'net/leg':>9}{'win%':>6}")
        totd = dollars.sum()
        for i in range(len(EDGES) - 1):
            lo, hi = EDGES[i], EDGES[i + 1]
            m = (sw >= lo) & (sw < hi)
            if not m.any():
                continue
            dm = dollars[m]
            lab = f"[{lo},{hi})" if hi < 1e8 else f">= {lo}"
            print(f"   {lab:>12}{m.sum():>6}{100*m.mean():>6.0f}%{dm.sum()/hrs:>+8.2f}"
                  f"{100*dm.sum()/totd if totd else 0:>6.0f}%{net[m].mean():>+8.2f}{100*(dm>0).mean():>5.0f}%")
        # swing-floor sweep (keep legs with |swing| >= floor)
        print(f"   swing-floor:  " + "  ".join(
            f">={f}bp: {dollars[sw>=f].sum()/hrs:+.1f}/{int((sw>=f).sum())}" for f in FLOORS)
            + "   [$/hr / legs kept]")
    print("\n  If most legs sit in [0,1)bp and contribute little $, the 2.5x trade count is CHURN — the real")
    print("  edge is a smaller number of bigger swings (use a coarser REV swing-floor). ⚠ one 30h window,")
    print("  front-of-line is OPTIMISTIC on sub-bp legs (tiny maker wins wouldn't survive real slippage).")


if __name__ == "__main__":
    main()
