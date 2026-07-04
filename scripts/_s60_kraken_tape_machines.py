"""_s60_kraken_tape_machines.py — S60 JOB 1: THE KRAKEN TAPE VERDICT (kickoff #1).

Question (one defined test): does the mid-band gross exist on KRAKEN'S OWN PRICES?
The kr_mk0 re-price (S59) was Binance-instrument gross at Kraken fees; this runs the SAME
promoted entry machine (odcore.entry_coinbase.armed_midband_flips, naive k0, c=0.5) on the
30d Kraken trade-history bins (backfill_kraken_trades.py output, same schema as Binance).

ALL 5 COINS x both thetas (per-cell law: ETH/BTC Kraken cells are their own cells — ETH's
Coinbase drop does not pre-judge eth_kraken). Fee columns: kr_mk0 0bp maker (net==gross),
kr_mk2/4/6 tier ladder, cb_real 8 for cross-reference. Flow maps NOT ported (venue law) —
naive k0 only. Controls: leakage truncation-invariance per tape; REVERSED sanity; per-week
buckets at kr_mk0. Tape-coverage honesty: report gap fraction (Kraken volume is 35-42% of
Coinbase; thin-tape cells are flagged, DOGE especially).

Usage: python scripts/_s60_kraken_tape_machines.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                             # noqa: E402
from odcore.entry_coinbase import (armed_midband_flips,               # noqa: E402
                                   assert_truncation_invariance)

PAIRS = [("sol", "SOLUSD"), ("btc", "XBTUSD"), ("doge", "XDGUSD"),
         ("xrp", "XRPUSD"), ("eth", "ETHUSD")]
REGISTRY_TH = {"sol": 100.0, "xrp": 80.0, "doge": 100.0, "btc": 80.0, "eth": None}
THETAS = (80.0, 100.0)
C = 0.5
CAP = 5000.0
FEES = (("kr_mk0", 0.0), ("kr_mk2", 2.0), ("kr_mk4", 4.0), ("cb_real", 8.0))
WEEK_S = 7 * 24 * 3600
BINS_DIR = "/tmp/kraken_backfill"


def score(mid, flips, hrs):
    if len(flips) < 2:
        return None
    ci = np.asarray([c for (c, p, s) in flips])
    sd = np.asarray([s for (c, p, s) in flips])
    ep, xp = mid[ci[:-1]], mid[ci[1:]]
    gross = sd[:-1] * (xp - ep) / ep * 1e4
    return {"gross": gross, "ei": ci[:-1], "lph": len(gross) / hrs, "hrs": hrs}


def main():
    print("=== S60 JOB 1: promoted mid-band machine (naive k0) on the 30d KRAKEN tape ===")
    print("(net $/hr @$5k flat, maker both sides; REG marks the registry theta; wk+ = positive")
    print(" weeks at kr_mk0; REV = reversed net at kr_mk0 — real edge shows fwd >> REV)")
    hdr = (f"{'cell':>16} {'hrs':>6} {'gap%':>5} | {'legs/h':>6} {'gr/leg':>7} {'win%':>5} |"
           + "".join(f"{lbl:>8}" for lbl, _ in FEES) + f" | {'wk+':>4} {'REV':>7}")
    print(hdr)
    for coin, pair in PAIRS:
        p = f"{BINS_DIR}/{pair}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] missing {p}")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        mid = np.asarray(mid, float)
        gap = 100.0 * (1.0 - float(cover)) if np.isscalar(cover) else \
            100.0 * (1.0 - float(np.mean(cover)))
        for theta in THETAS:
            assert_truncation_invariance(mid, theta, C)
            flips = armed_midband_flips(mid, theta, C)
            res = score(mid, flips, hrs)
            reg = "REG" if REGISTRY_TH[coin] == theta else "   "
            if res is None:
                print(f"{coin}_kraken_mb{theta:.0f} {reg} | (no legs)")
                continue
            g = res["gross"]
            cols = "".join(
                f"{float(np.sum(CAP * (g - 2 * mk) / 1e4)) / hrs:>+8.2f}" for _, mk in FEES)
            wk = (res["ei"] // WEEK_S).astype(int)
            wsum = np.bincount(wk - wk.min(), weights=CAP * g / 1e4)
            wk_pos = int(np.sum(wsum > 0))
            rev = float(np.sum(CAP * (-g) / 1e4)) / hrs
            print(f"{coin}_kraken_mb{theta:.0f}{reg[:1]:>2} {hrs:>6.1f} {gap:>5.1f} | "
                  f"{res['lph']:>6.2f} {np.mean(g):>+7.2f} {100 * np.mean(g > 0):>5.0f} |"
                  f"{cols} | {wk_pos}/{len(wsum)} {rev:>+7.2f}")


if __name__ == "__main__":
    main()
