"""_s59_kraken_tape_run.py — THE KRAKEN TAPE VERDICT (S59/S60 job 1; one defined test).

Question: does the mid-band entry machine's gross EXIST on Kraken's own prices? The kr_mk0
re-price rode Binance-instrument gross; venue law demands the machine re-earn it on the
deploy venue's tape. This runs the PROMOTED machine (odcore.entry_coinbase, naive k0 — the
only venue-portable shape; flow maps are NOT ported, per the master law) on the 30d Kraken
trade-history bins (backfill_kraken_trades.py) at the REAL Kraken fee ladder:

  kr_mk0  0bp maker/side  (the $10M/30d tier — the destination)
  kr_mk2  2bp maker/side  (the $5M tier — late climb)
  kr_mk6  6bp maker/side  (the $1M tier — early climb)

Both thetas printed per coin (Kraken is a NEW venue; the Coinbase registry theta is not
assumed) — but per discipline no theta is PICKED here; the read is whether positive-gross
cells exist at all, their weekly stability, and how the climb tiers bleed. Fill/queue
reality (maker fills at 35-42% of Coinbase volume) is NOT answered here — that waits on
the live Kraken book collector. Leakage: the promoted machine's truncation-invariance gate
is asserted per tape.

Usage: python scripts/_s59_kraken_tape_run.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import (armed_midband_flips,                # noqa: E402
                                   assert_truncation_invariance)

PAIRS = [("sol", "SOLUSD"), ("btc", "XBTUSD"), ("doge", "XDGUSD"),
         ("xrp", "XRPUSD"), ("eth", "ETHUSD")]
THETAS = (80.0, 100.0)
C = 0.5
CAP = 5000.0
TIERS = (("$kr0", 0.0), ("$kr2", 2.0), ("$kr6", 6.0))
WEEK_S = 7 * 24 * 3600


def main():
    print("KRAKEN TAPE VERDICT — promoted k0 machine on 30d Kraken trade-history bins "
          "(@$5k flat, maker both sides; fills NOT modeled — books accruing)")
    for coin, pair in PAIRS:
        p = f"/tmp/kraken_backfill/{pair}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] kraken bins missing — re-pull per kickoff"); continue
        mid, buy, sell, cover, hrs = load_bins(p)
        mid = np.asarray(mid, float)
        try:
            assert_truncation_invariance(mid, 100.0, C)
            leak = "PASS"
        except AssertionError:
            leak = "FAIL"
        print(f"\n=== {coin} kraken_bins ({hrs:.1f}h, bin coverage {100*cover:.0f}%) — "
              f"leakage {leak} ===")
        print(f"  {'config':>8} {'th':>4} | {'legs/h':>6} {'win%':>4} {'gr/leg':>7} |"
              + "".join(f"{lbl:>8}" for lbl, _ in TIERS) + f" | {'wk+':>4} {'zw':>5}")
        if leak != "PASS":
            continue
        for theta in THETAS:
            fl = armed_midband_flips(mid, theta, C)
            if len(fl) < 2:
                print(f"  {'k0':>8} {theta:>4.0f} | (no legs)"); continue
            ci = np.asarray([int(c) for (c, pv, s) in fl])
            sd = np.asarray([int(s) for (c, pv, s) in fl])
            gross = sd[:-1] * (mid[ci[1:]] - mid[ci[:-1]]) / mid[ci[:-1]] * 1e4
            lph = len(gross) / hrs
            cols = ""
            for _, mk in TIERS:
                dollars = CAP * (gross - 2 * mk) / 1e4
                cols += f"{float(np.sum(dollars)) / hrs:>+8.2f}"
            d0 = CAP * gross / 1e4
            bkt = (ci[:-1] // WEEK_S).astype(int)
            sums = np.bincount(bkt, weights=d0)
            wk = sums[np.bincount(bkt) > 0]
            zw = float(np.mean(wk) / (np.std(wk, ddof=1) / np.sqrt(len(wk)))) \
                if len(wk) > 1 else 0.0
            print(f"  {'k0':>8} {theta:>4.0f} | {lph:>6.2f} "
                  f"{100 * np.mean(gross > 0):>4.0f} {np.mean(gross):>+7.2f} |{cols} | "
                  f"{np.sum(wk > 0):>2d}/{len(wk):<2d} {zw:>+5.1f}")


if __name__ == "__main__":
    main()
