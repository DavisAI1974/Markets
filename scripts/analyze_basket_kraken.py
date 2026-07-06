"""analyze_basket_kraken.py — WINNER/LOSER anatomy of the Kraken basket run (S65).

Greg: "split winners from losers and let's see if there's a bunch of bleed or if we can lift winners."

Runs the SAME honest-fill basket (basket_sim_kraken) per cell on the common overlap window, then
dissects each cell's legs three ways to locate WHERE the money is:
  1. WINNER/LOSER split      — n, sum $, mean bps, avg-W vs avg-L, W/L ratio. Is loss SIZE the problem?
  2. CLOSE-TYPE split        — maker-close vs FORCED-TAKER-close vs deep-bail(stop). The S63 thesis:
                               the bleed is forced-taker closes (the FILL leak), not the signal.
  3. TAIL concentration      — worst-10 / best-10 leg $ as a share of total loss / total win. A FAT
                               tail = cappable bleed; a thin even spread = systematic thin edge.
  + IDEAL-vs-HONEST winners  — how many winners the honest fill LOSES to forced-taker (the liftable $).
  + FILL CEILING             — $/hr if every forced-taker close were a maker close (signal-only ceiling).

Verdict per cell: BLEED-FAT-TAIL (cap it) / BLEED-FORCED-TAKER (fix the fill) / THIN-EDGE (signal weak)
/ LIFTABLE (winners given back to fill).  All PROVISIONAL — one ~30h low-edge book window.

Usage:  python scripts/analyze_basket_kraken.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import CELLS, CAP, load_book, run_cell   # noqa: E402


def dollars(bps):
    return bps / 1e4 * CAP


def anatomy(coin, cell, honest, ideal, hrs):
    legs = honest.legs
    net = np.array([l.net_bps for l in legs])
    d = dollars(net)
    win = d > 0
    los = ~win
    maker = np.array([l.close_maker for l in legs])
    stop = np.array([bool(getattr(l, "stop_exit", False)) for l in legs])
    forced_taker = (~maker) & (~stop)          # taker close that is NOT an intentional deep-bail

    tot = d.sum()
    sum_w, sum_l = d[win].sum(), d[los].sum()
    print(f"\n[{coin}]  {len(legs)} legs, {hrs:.1f}h,  honest net {tot/hrs:+.2f} $/hr  (ideal {dollars(ideal.total_net_bps)/hrs:+.2f})")
    print(f"  WIN/LOSS:  win% {100*win.mean():.0f}  |  winners n={win.sum():>3} sum={sum_w:+8.1f}$ avg={d[win].mean() if win.any() else 0:+6.2f}$"
          f"  |  losers n={los.sum():>3} sum={sum_l:+8.1f}$ avg={d[los].mean() if los.any() else 0:+6.2f}$"
          f"  |  W/L(avg)={(d[win].mean()/abs(d[los].mean())) if los.any() and win.any() else 0:.2f}")

    # close-type split
    for label, mask in [("maker-close ", maker & ~stop), ("FORCED-taker", forced_taker), ("deep-bail   ", stop)]:
        if mask.any():
            dm = d[mask]
            print(f"  {label}: n={mask.sum():>3}  net={dm.sum():+8.1f}$  win%={100*(dm>0).mean():>3.0f}  "
                  f"avg={dm.mean():+6.2f}$  (share of |loss| {100*dm[dm<0].sum()/sum_l if sum_l<0 else 0:>4.0f}%)")

    # tail concentration
    order = np.argsort(d)
    worst10 = d[order[:10]].sum(); best10 = d[order[::-1][:10]].sum()
    print(f"  TAIL: worst-10 legs = {worst10:+8.1f}$ ({100*worst10/sum_l if sum_l<0 else 0:.0f}% of all loss)   "
          f"best-10 = {best10:+8.1f}$ ({100*best10/sum_w if sum_w>0 else 0:.0f}% of all win)")

    # fill ceiling: if every forced-taker close earned the maker half-spread instead of crossing.
    # approximate the give-up as the taker-vs-maker fee delta + the crossed half-spread already in the leg;
    # cleanest proxy = compare to the IDEAL (front-fill) run, which fills the same turns as maker.
    lost_to_fill = dollars(ideal.total_net_bps - honest.total_net_bps)
    print(f"  FILL COST (ideal - honest): {lost_to_fill:+.1f}$ total = {lost_to_fill/hrs:+.2f} $/hr given to the fill")

    # verdict
    frac_tail = worst10 / sum_l if sum_l < 0 else 0
    ft_loss = d[forced_taker & los].sum()
    frac_ft = ft_loss / sum_l if sum_l < 0 else 0
    verdict = []
    if frac_tail > 0.5:
        verdict.append("BLEED-FAT-TAIL (worst-10 carry >50% of loss -> a deeper/tighter bail caps it)")
    if frac_ft > 0.5:
        verdict.append("BLEED-FORCED-TAKER (>50% of loss is forced-taker closes -> FILL fix: cover_grace/swing-floor)")
    if lost_to_fill / max(abs(tot), 1) > 1.0 and ideal.total_net_bps > 0:
        verdict.append("LIFTABLE (ideal is positive; the honest loss is the fill giving winners back)")
    if not verdict:
        verdict.append("THIN-EDGE (loss spread evenly, ideal weak -> signal itself thin on this window)")
    print(f"  => {' | '.join(verdict)}")


def main():
    print("=== KRAKEN BASKET — WINNER/LOSER ANATOMY (S65) — honest fill, per cell, common window ===")
    books = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = load_book(cell["coin"])
        if bk is not None:
            books[cell["coin"]] = bk
        else:
            cell["active"] = False
    if not books:
        print("no books; materialize /tmp/kbook/*_book.jsonl first"); return
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1; ov_hrs = ov_sec / 3600.0
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = books[cell["coin"]]; s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        _, honest = run_cell(cell, clip, "queue")
        _, ideal = run_cell(cell, clip, "front")
        if honest.legs:
            anatomy(cell["coin"], cell, honest, ideal, ov_hrs)
    print("\n  ⚠ one ~30h LOW-EDGE book window — provisional. 'FILL COST' uses ideal(front) as the "
          "perfect-maker-fill reference; the gap is what the real queue fill gives up.")


if __name__ == "__main__":
    main()
