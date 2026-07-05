"""_s63_kraken_swingfloor.py — swing floor (coarser REV) on tape + maker-fill, and "exit too early?" test.

Greg: (1) run the swing floor — does firing only on BIGGER lean reversals (coarser REV) cut the tiny
fill-fragile churn and lift the FILL-realistic net? (2) are the winners exiting too early?

PART A  REV sweep on the 30d TAPE (ride-all): n trades, mean |swing|, net $/hr (0bp) — the signal-level
        effect of a coarser floor.
PART B  REV sweep on the real BOOK via the honest queue maker-fill (cover_grace=300): trades, fill%,
        taker%, honest net $/hr — does fewer/bigger swings help the fill economics?
PART C  EXIT-TOO-EARLY: for each WINNER, the favorable move in the 120s AFTER the flow-turn exit
        (side*(mid[nci+120]-mid[nci])). >0 = price kept going our way (exited early); <0 = reverted
        (good exit). Plus small-winner (exit<5bp) peak vs exit — tiny moves or big-peak-given-back?

Kraken, retime entries, SOL reversed.
Usage:  python scripts/_s63_kraken_swingfloor.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402
from odcore.swing_maker import simulate_swing_maker                   # noqa: E402
from _s63_kraken_makerfill import load_book_1s, MAKER_FEE, TAKER_FEE  # noqa: E402

CAP = 5000.0; WFLIP = 600
KTAPE = "/tmp/kraken_backfill"; KBOOK = "/tmp/kbook"
TAPE = [("eth", "ETHUSD", 10.0, 0), ("btc", "XBTUSD", 5.0, 0), ("sol", "SOLUSD", 10.0, 1)]
BOOK = [("eth", 0), ("btc", 0), ("sol", 1)]
REVS = [0.10, 0.15, 0.20, 0.30]


def main():
    print("=== PART A: swing floor on the 30d TAPE (ride-all, 0bp) ===")
    print(f"{'coin':5}{'REV':>6}{'trades':>8}{'mean|sw|':>10}{'net$/h':>8}")
    for coin, pair, eps, rev in TAPE:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        sgn = -1 if rev else 1
        for R in REVS:
            ent, _ = retime_flips(mid, buy, sell, WFLIP, R, eps)
            g = []; sw = []
            for k in range(len(ent) - 1):
                ci, _p, s = ent[k]; nci = ent[k + 1][0]; s *= sgn
                if mid[ci] > 0 and mid[nci] > 0 and nci > ci:
                    d = s * np.log(mid[nci] / mid[ci]) * 1e4; g.append(d); sw.append(abs(d))
            g = np.array(g)
            print(f"{coin:5}{R:>6.2f}{len(g):>8}{np.mean(sw):>10.1f}{g.sum()/1e4*CAP/720:>+8.2f}")

    print("\n=== PART B: swing floor on the real BOOK, honest maker fill (cover_grace=300) ===")
    print(f"{'coin':6}{'REV':>6}{'flips':>7}{'fill%':>7}{'takerCl%':>9}{'net$/h':>8}")
    for coin, rev in BOOK:
        p = f"{KBOOK}/{coin}_book.jsonl"
        if not os.path.exists(p):
            continue
        mid, bb, ba, buy, sell, hs, hrs = load_book_1s(p)
        lean = lean_series(buy, sell, WFLIP)
        for R in REVS:
            flips, _ = detect_flips(lean, R)
            if rev:
                flips = [(ci, pv, -s) for (ci, pv, s) in flips]
            res = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                       maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                                       fill_model="queue", queue_frac=1.0, cover_grace=300)
            tk = 100 * res.n_taker_closes / res.n_legs if res.n_legs else 0
            print(f"{coin+('*' if rev else ''):6}{R:>6.2f}{res.n_flips:>7}{100*res.fill_rate:>6.0f}%"
                  f"{tk:>8.0f}%{res.total_net_bps/1e4*CAP/hrs:>+8.2f}")

    print("\n=== PART C: are winners EXITING TOO EARLY? (favorable move 120s AFTER the flow-turn exit) ===")
    W = 120
    for coin, pair, eps, rev in TAPE:
        path = f"{KTAPE}/{pair}_30d_bins.json"
        if not os.path.exists(path):
            continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); lm = np.log(mid); n = len(mid)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float); sgn = -1 if rev else 1
        ent, _ = retime_flips(mid, buy, sell, WFLIP, 0.10, eps)
        post = []; smallpk = []; smallex = []
        for k in range(len(ent) - 1):
            ci, _p, s = ent[k]; nci = ent[k + 1][0]; s *= sgn
            if mid[ci] <= 0 or mid[nci] <= 0 or nci <= ci or nci + W >= n:
                continue
            r = s * (lm[ci:nci + 1] - lm[ci]) * 1e4; g = float(r[-1])
            if g > 0:
                post.append(s * (lm[nci + W] - lm[nci]) * 1e4)     # continuation our way after exit
                if g < 5:
                    smallpk.append(float(r.max())); smallex.append(g)
        post = np.array(post)
        print(f"[{coin}{'*' if rev else ''}]  post-exit 120s favorable move: mean={post.mean():+.2f}bp  "
              f"median={np.median(post):+.2f}  %kept-going={100*np.mean(post>0):.0f}%   "
              f"| small-winner(<5bp) mean peak={np.mean(smallpk):.1f} vs exit={np.mean(smallex):.1f}bp")
    print("  post-exit >0 = exited too early (kept going); <0 = reverted (good exit).")


if __name__ == "__main__":
    main()
