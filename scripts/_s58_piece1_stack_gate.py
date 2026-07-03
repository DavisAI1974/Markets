"""_s58_piece1_stack_gate.py — S58 PIECE 1, ROUND 3 CONTROLS (mandatory before any next step).

Two jobs, both pure measurement of the round-3 machine (no new mechanics):

(1) GATE on the stack lift (bins, k>=3 cells at th80/th100 c0.5): shuffle floor (x3 full-
    pipeline re-runs on return-permuted mid), per-week net-$ buckets (pos weeks + z), and the
    truncation-invariance leakage check on the stack machine itself.

(2) WINDOW-MATCH cross-check for the SOL books INVERSION (round-3 books: k>=3 destroys what
    k<=2 keeps; member signs flip vs bins). Confound to split: VENUE vs REGIME — books are one
    ~4-day window, bins are 30d. Test: re-run the stack curve on ONLY the LAST hrs_books hours
    of each coin's bins tape (regime-matched suffix). If the bins suffix ALSO inverts at k>=3,
    the inversion is REGIME (recent window), not venue microstructure.

Usage: python scripts/_s58_piece1_stack_gate.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import CAP, CB_REAL, load_venue, score, shuffle_mid  # noqa: E402
from _s58_piece1_stack import StackReads, armed_stack_zigzag                # noqa: E402

CELLS = ((80.0, 0.5), (100.0, 0.5))
K = 3
N_SHUF = 3
WEEK_S = 7 * 24 * 3600
BOOK_HRS = {"sol": 99.3, "eth": 64.3, "btc": 196.3, "doge": 196.0, "xrp": 196.0}


def net_real(res, hrs):
    return float(np.sum(CAP * (res["gross"] - 2 * CB_REAL) / 1e4)) / hrs


def main():
    print("== (1) GATE: stack k>=3, bins, shuffle + per-week + leakage ==")
    tapes = {}
    for coin, mid, buy, sell, hrs, _b in load_venue("bins"):
        tapes[coin] = (mid, buy, sell, hrs)
        sr = StackReads(mid, buy, sell)
        for theta, c in CELLS:
            fl = armed_stack_zigzag(mid, sr, theta, c * theta, k=K)
            res = score(mid, fl, hrs)
            if res is None:
                print(f"[{coin} th{theta:.0f}] no legs"); continue
            fwd = net_real(res, hrs)
            # per-week buckets by entry index
            dollars = CAP * (res["gross"] - 2 * CB_REAL) / 1e4
            b = (res["ei"] // WEEK_S).astype(int)
            sums = np.bincount(b, weights=dollars)
            wk = sums[np.bincount(b) > 0]
            zw = float(np.mean(wk) / (np.std(wk, ddof=1) / np.sqrt(len(wk)))) if len(wk) > 1 else 0.0
            # shuffle floor: permuted log-returns, full pipeline (stack reads recomputed on
            # the shuffled mid; flow arrays unchanged — price structure destroyed)
            sh = []
            for si in range(N_SHUF):
                smid = shuffle_mid(mid, np.random.default_rng(2000 + si))
                ssr = StackReads(smid, buy, sell)
                sfl = armed_stack_zigzag(smid, ssr, theta, c * theta, k=K)
                sres = score(smid, sfl, hrs)
                sh.append(net_real(sres, hrs) if sres else 0.0)
            sh = np.asarray(sh)
            # truncation-invariance leakage on the stack machine
            n = len(mid)
            leak = "PASS"
            for cut in (n // 2, (3 * n) // 4):
                pre = armed_stack_zigzag(mid[:cut], StackReads(mid[:cut], buy[:cut], sell[:cut]),
                                         theta, c * theta, k=K)
                want = [f for f in fl if f[0] < cut]
                if pre[:len(want)] != want:
                    leak = "FAIL"; break
            print(f"[{coin} th{theta:.0f}c{c}] fwd {fwd:+.2f}/hr ({res['n']} legs) | "
                  f"shuffle {np.mean(sh):+.2f}±{np.std(sh):.2f} | weeks {np.sum(wk > 0)}/"
                  f"{len(wk)} pos z={zw:+.1f} | leakage {leak}")

    print("\n== (2) WINDOW-MATCH: bins SUFFIX (last hrs_books) stack curve k=0 vs k>=3 ==")
    for coin, (mid, buy, sell, hrs) in tapes.items():
        cut_h = BOOK_HRS.get(coin, 99.0)
        n_suf = int(cut_h * 3600)
        mid_s, buy_s, sell_s = mid[-n_suf:], buy[-n_suf:], sell[-n_suf:]
        sr = StackReads(mid_s, buy_s, sell_s)
        for theta, c in ((100.0, 0.5),):
            r0 = score(mid_s, armed_stack_zigzag(mid_s, sr, theta, c * theta, k=0), cut_h)
            r3 = score(mid_s, armed_stack_zigzag(mid_s, sr, theta, c * theta, k=K), cut_h)
            g0 = np.mean(r0["gross"]) if r0 else float("nan")
            g3 = np.mean(r3["gross"]) if r3 else float("nan")
            n0 = r0["n"] if r0 else 0
            n3 = r3["n"] if r3 else 0
            print(f"[{coin} suffix {cut_h:.0f}h th{theta:.0f}c{c}] k0 {g0:+.2f}bp/leg ({n0}) "
                  f"-> k>=3 {g3:+.2f}bp/leg ({n3})  {'INVERTS' if g3 < g0 else 'holds'}")


if __name__ == "__main__":
    main()
