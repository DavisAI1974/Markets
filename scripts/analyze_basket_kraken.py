"""analyze_basket_kraken.py — WHERE IS THE (NEW) BLEED at front-of-line? (S65).

After the fill fix (front-of-line + enticing close), the forced-taker leak is largely gone, so this
re-locates the residual bleed. Runs each cell through the LIVE decision path (basket_sim_kraken.run_cell
-> platform.run_stream) at FRONT-OF-LINE + per-coin enticing, then splits every cell's legs:
  1. WIN/LOSS       — n, sum $, avg-W vs avg-L, W/L ratio.
  2. CLOSE-TYPE     — maker-close (the signal's own turn-exit) / deep-bail (intentional taker risk-control)
                      / residual FORCED-taker (fill still leaking?). Locates the bleed KIND.
  3. TAIL           — worst-10 leg $ as a share of total loss. Fat tail = a deeper/tighter bail caps it.
Verdict per cell: FILL-LEAK (residual forced-taker) / BAIL-COST (deep-bail crosses dominate) /
SIGNAL-LOSS (maker-close losers = wrong-direction swings, irreducible) / FAT-TAIL (cappable).

ARCHITECTURE: uses the live run_stream via basket_sim_kraken — NOT a reimplementation. PROVISIONAL:
one ~30h low-edge book window.

Usage:  python scripts/analyze_basket_kraken.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import CELLS, CAP, load_book, run_cell   # noqa: E402  (live decision path)


def d(bps):
    return bps / 1e4 * CAP


def anatomy(coin, side, r, hrs):
    legs = r.legs
    dd = np.array([d(l.net_bps) for l in legs])
    win = dd > 0; los = ~win
    maker = np.array([l.close_maker for l in legs])
    stop = np.array([bool(getattr(l, "stop_exit", False)) for l in legs])
    ftaker = (~maker) & (~stop)
    tot = dd.sum(); sum_w = dd[win].sum(); sum_l = dd[los].sum()
    tag = f"{coin}{'*' if side < 0 else ''}"
    print(f"\n[{tag}]  {len(legs)} legs, {hrs:.1f}h,  {tot/hrs:+.2f} $/hr   (win% {100*win.mean():.0f})")
    print(f"  WIN/LOSS: winners n={win.sum():>3} sum={sum_w:+8.1f}$ avg={dd[win].mean() if win.any() else 0:+5.2f}$"
          f"  |  losers n={los.sum():>3} sum={sum_l:+8.1f}$ avg={dd[los].mean() if los.any() else 0:+5.2f}$"
          f"  |  W/L={(dd[win].mean()/abs(dd[los].mean())) if los.any() and win.any() else 0:.2f}")
    for label, mask in [("maker-close  ", maker & ~stop), ("deep-bail    ", stop), ("FORCED-taker ", ftaker)]:
        if mask.any():
            dm = dd[mask]; loss = dm[dm < 0].sum()
            print(f"  {label}: n={mask.sum():>3}  net={dm.sum():+8.1f}$  win%={100*(dm>0).mean():>3.0f}  "
                  f"loss={loss:+8.1f}$ ({100*loss/sum_l if sum_l<0 else 0:>3.0f}% of all loss)")
    order = np.argsort(dd); worst10 = dd[order[:10]].sum()
    print(f"  TAIL: worst-10 = {worst10:+8.1f}$ ({100*worst10/sum_l if sum_l<0 else 0:.0f}% of all loss)")
    # verdict
    v = []
    ft_loss = dd[ftaker & los].sum(); bail_loss = dd[stop & los].sum(); mk_loss = dd[(maker & ~stop) & los].sum()
    if sum_l < 0:
        if ft_loss / sum_l > 0.4:
            v.append(f"FILL-LEAK (forced-taker still {100*ft_loss/sum_l:.0f}% of loss)")
        if bail_loss / sum_l > 0.4:
            v.append(f"BAIL-COST (deep-bail crosses {100*bail_loss/sum_l:.0f}% of loss — risk-control, expected)")
        if mk_loss / sum_l > 0.4:
            v.append(f"SIGNAL-LOSS (maker-close losers {100*mk_loss/sum_l:.0f}% — wrong-direction swings)")
        if worst10 / sum_l > 0.5:
            v.append("FAT-TAIL (worst-10 >50% of loss — cappable)")
    print(f"  => {' | '.join(v) if v else 'net positive / no material loss'}")


def main():
    print("=== KRAKEN BASKET — WHERE IS THE BLEED (front-of-line + enticing, LIVE run_stream) ===")
    books = {}
    for cell in CELLS:
        if cell["active"]:
            bk = load_book(cell["coin"])
            if bk is not None:
                books[cell["coin"]] = bk
            else:
                cell["active"] = False
    if not books:
        print("no books"); return
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1; ov_hrs = ov_sec / 3600.0
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = books[cell["coin"]]; s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        _, r = run_cell(cell, clip, "front")            # front-of-line + per-coin enticing (deployed premise)
        if r.legs:
            anatomy(cell["coin"], cell["side"], r, ov_hrs)
    print("\n  ⚠ one ~30h LOW-EDGE window — provisional. deep-bail loss is INTENTIONAL risk-control (a leg "
          "that reached the bail depth); SIGNAL-LOSS = the irreducible wrong-direction swings.")


if __name__ == "__main__":
    main()
