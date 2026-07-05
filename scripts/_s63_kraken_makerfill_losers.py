"""_s63_kraken_makerfill_losers.py — post-fill win/loss split + 10 worst losers (Greg: squeeze).

Runs the HONEST queue-fill maker model on the Kraken book, splits the realized legs into wins/losses,
and renders the 10 worst legs so we can see what (if anything) is left to squeeze after real fills.
Each loser panel: the leg's mid path open->close, the OPEN fill (^) and CLOSE (v, red=taker/green=maker),
net_bps in the title. The maker gate (S63 §17) showed ~40% fill / 55-67% taker → this shows WHERE the
damage is (forced-taker closes vs adverse legs).

Usage:  python scripts/_s63_kraken_makerfill_losers.py [coin]   (default eth)
"""
from __future__ import annotations

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.swing_maker import simulate_swing_maker                   # noqa: E402
from _s63_kraken_makerfill import load_book_1s, WFLIP, REV, MAKER_FEE, TAKER_FEE  # noqa: E402

CAP = 5000.0
KBOOK = "/tmp/kbook"
REVERSED = {"sol"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s63")


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "eth"
    path = f"{KBOOK}/{coin}_book.jsonl"
    mid, bb, ba, buy, sell, hs, hrs = load_book_1s(path)
    lean = lean_series(buy, sell, WFLIP); flips, _ = detect_flips(lean, REV)
    if coin in REVERSED:
        flips = [(ci, pv, -s) for (ci, pv, s) in flips]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                               maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                               fill_model="queue", queue_frac=1.0)
    legs = res.legs
    net = np.array([l.net_bps for l in legs])
    w = net[net > 0]; l_ = net[net < 0]
    tk = [lg for lg in legs if not lg.close_maker]
    print(f"[{coin}{'*' if coin in REVERSED else ''}]  book {hrs:.1f}h  legs={len(legs)}  "
          f"fill_rate={100*res.fill_rate:.0f}%  taker_closes={res.n_taker_closes}/{len(legs)}")
    print(f"   WIN/LOSS: win%={100*len(w)/max(len(net),1):.0f}  avgW={w.mean() if len(w) else 0:+.2f}  "
          f"avgL={l_.mean() if len(l_) else 0:+.2f}  net/leg={net.mean():+.2f}bp  "
          f"total {net.sum()/1e4*CAP/hrs:+.2f} $/hr")
    print(f"   of the LOSSES, how many were forced-taker closes: "
          f"{sum(1 for lg in legs if lg.net_bps < 0 and not lg.close_maker)}/{len(l_)}")

    order = sorted(range(len(legs)), key=lambda i: legs[i].net_bps)[:10]
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle(f"{coin.upper()}{' REV' if coin in REVERSED else ''} — 10 worst legs, HONEST maker fill "
                 f"(kr book {hrs:.0f}h, fill {100*res.fill_rate:.0f}%)  |  mid path open→close; "
                 f"^=open v=close (red=taker)", fontsize=12)
    for ax, i in zip(axes.flat, order):
        lg = legs[i]; a, b = lg.open_idx, lg.close_idx
        seg = mid[a:b + 1]
        r = lg.side * (np.log(seg / mid[a])) * 1e4
        t = np.arange(len(r))
        ax.axhline(0, color="#888", lw=0.8)
        ax.plot(t, r, color="#1a9850", lw=1.2)
        ax.plot(0, 0, "^", color="#1a9850", ms=8)
        ax.plot(len(r) - 1, r[-1], "v", color=("#d73027" if not lg.close_maker else "#1a9850"), ms=8)
        ax.set_title(f"net {lg.net_bps:+.0f}bp  {'LONG' if lg.side>0 else 'SHORT'}  {b-a}s  "
                     f"{'TAKER' if not lg.close_maker else 'maker'}", fontsize=9)
        ax.set_xlabel("s", fontsize=8); ax.set_ylabel("bps", fontsize=8); ax.tick_params(labelsize=7)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fp = os.path.join(OUT, f"makerfill_losers_{coin}.png")
    plt.savefig(fp, dpi=110); plt.close()
    print(f"   rendered -> {fp}")


if __name__ == "__main__":
    main()
