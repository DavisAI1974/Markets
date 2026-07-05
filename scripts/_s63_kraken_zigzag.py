"""_s63_kraken_zigzag.py — S63 Kraken pivot: plain ZIGZAG (Greg — no fee floor at kr_mk0).

At kr_mk0 (0bp maker) the fee floor that killed sub-fee swings is gone, so a plain causal zigzag
(always in the market, flip at every confirmed turn) becomes viable. This ignores the entry machine
entirely — it just oscillates on Kraken's own price:

  causal zigzag with reversal threshold theta (bps):
    hold LONG until price retraces theta from the running peak -> flip SHORT at that price
    hold SHORT until price rises   theta from the running trough -> flip LONG  at that price
  realized per leg = signed move from the last flip to this flip (includes the theta giveback);
  a flip pays `fee_bp` (kr_mk0 = 0).

Grade: net $/hr @ $5k over the tape hours, swept over theta, at kr_mk0 (0bp) with kr_mk2 (2bp/flip)
and taker (11bp/flip) sensitivities. per-week robustness. This is a real, causal, no-look-ahead
strategy (NOT the perfect-hindsight oracle). Data = Kraken's own tape (BTC/ETH realbins ~26.7d;
SOL/DOGE/XRP from the REST pull as it lands).

Usage:  python scripts/_s63_kraken_zigzag.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402

CAP = 5000.0; WK = 7 * 24 * 3600
REALBINS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realbins")
KTAPE = "/tmp/kraken_backfill"
CELLS = [
    ("btc", f"{REALBINS}/btc_kraken_bins.json"),
    ("eth", f"{REALBINS}/eth_kraken_bins.json"),
    ("sol", f"{KTAPE}/SOLUSD_30d_bins.json"),
    ("doge", f"{KTAPE}/XDGUSD_30d_bins.json"),
    ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json"),
]
THETAS = [10, 20, 30, 50, 80, 120]      # reversal threshold (bps)
FEES = [("kr_mk0", 0.0), ("kr_mk2", 2.0), ("taker", 11.0)]


def zigzag(mid, theta_bp, fee_bp):
    """Causal zigzag. Returns (realized_bps_array, flip_index_array). Always in market from t0."""
    n = len(mid)
    pos = 1                     # start long (arbitrary; first leg tiny effect over long tape)
    entry = mid[0]; ext = mid[0]
    realized = []; fidx = []
    for t in range(1, n):
        p = mid[t]
        if pos == 1:
            if p > ext:
                ext = p
            elif (ext - p) / ext * 1e4 >= theta_bp:            # retrace theta from peak -> flip short
                realized.append((p - entry) / entry * 1e4 - fee_bp)
                fidx.append(t); pos = -1; entry = p; ext = p
        else:
            if p < ext:
                ext = p
            elif (p - ext) / ext * 1e4 >= theta_bp:            # rise theta from trough -> flip long
                realized.append((entry - p) / entry * 1e4 - fee_bp)
                fidx.append(t); pos = 1; entry = p; ext = p
    return np.array(realized), np.array(fidx)


def main():
    print("=== S63 KRAKEN plain causal ZIGZAG (no look-ahead), net $/hr @ $5k ===")
    for coin, path in CELLS:
        if not os.path.exists(path):
            print(f"\n[{coin}] bins not present yet: {os.path.basename(path)}"); continue
        mid, buy, sell, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); n = len(mid)
        span_d = n / 86400.0
        print(f"\n[{coin}]  {os.path.basename(path)}  span={span_d:.1f}d  cover={cover*100:.0f}%  hrs={hrs:.0f}")
        print(f"   {'theta':>6}{'flips':>7}{'flip/h':>7}" + "".join(f"{lbl:>9}" for lbl, _ in FEES)
              + "   per-week (kr_mk0)")
        for th in THETAS:
            r0, fidx = zigzag(mid, th, 0.0)
            if len(r0) < 2:
                print(f"   {th:>5}b{len(r0):>7}  (too few flips)"); continue
            fph = len(r0) / hrs
            row = f"   {th:>5}b{len(r0):>7}{fph:>7.2f}"
            # net $/hr at each fee tier
            for lbl, fee in FEES:
                net = np.sum((r0 - fee)) * CAP / 1e4 / hrs
                row += f"{net:>+9.1f}"
            # per-week at kr_mk0
            wk = (fidx // WK).astype(int)
            pw = []
            for w in sorted(set(wk)):
                mk = wk == w
                if mk.sum() < 2:
                    continue
                hh = (np.ptp(fidx[mk]) + 1) / 3600.0
                pw.append(np.sum(r0[mk]) * CAP / 1e4 / hh)
            row += "   " + " ".join(f"{v:+.0f}" for v in pw)
            print(row)


if __name__ == "__main__":
    main()
