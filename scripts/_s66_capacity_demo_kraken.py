"""_s66_capacity_demo_kraken.py — DEMONSTRATE odcore.capacity on real Kraken tape (S66).

Runs the LIVE KRAKEN cell (run_kraken_cell) to get legs, then bounds each leg's fill by real opposing
flow (odcore.capacity, flow-bound tape mode) to show the gap between the UNCAPPED $/hr the basket sim
reports (fills the full desired size — the "fiction") and the CAPACITY-CAPPED $/hr (fills only what real
flow allows). On liquid majors the gap should be small (they are NOT capacity-bound); the same lens on the
thin-cap sleeve is where it will bite. Tape = flow-bound only (no book depth for queue-honest).

Usage: python scripts/_s66_capacity_demo_kraken.py            # majors from /tmp/ktape
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                    # noqa: E402
from odcore.platform import KRAKEN, run_kraken_cell          # noqa: E402
from odcore.capacity import caps_for_legs                    # noqa: E402

BINS = "/tmp/ktape"
PAIR = {"eth": "ETHUSD", "btc": "XBTUSD", "sol": "SOLUSD", "xrp": "XRPUSD", "doge": "XDGUSD"}
DESIRED = [500.0, 1000.0, 5000.0]


def main():
    print("=== CAPACITY on Kraken tape: UNCAPPED (fiction) vs FLOW-CAPPED $/hr @ desired size ===")
    print(f"{'coin':5}{'legs':>6}{'hrs':>6}{'medCap$':>10}{'p25':>9}{'p75':>9}   " +
          "  ".join(f"D=${int(d)}: uncap/cap $/hr (fill%)" for d in DESIRED))
    for cfg in KRAKEN:
        coin = cfg.coin
        path = f"{BINS}/{PAIR[coin]}_30d_bins.json"
        if not os.path.exists(path):
            print(f"{coin:5}  (tape missing: {path})")
            continue
        m, b, s, cov, hrs = load_bins(path)
        m = np.asarray(m, float); b = np.asarray(b, float); s = np.asarray(s, float)
        n = len(m)
        z = np.zeros(n)
        res, _ = run_kraken_cell(cfg, m, b, s, z, z, 0.0)     # LIVE decision; front-of-line, no book
        legs = res.legs
        if not legs:
            print(f"{coin:5}{0:>6}"); continue
        # ⚠ WINDOW IS LOAD-BEARING: the deployed executor RESTS the maker quote the whole leg (median ~155s),
        # so capacity = price-eligible opposing flow over [open, close] (window=None). The FILL_W=10 default is
        # a 100ms-BOOK param (=1s); on 1s TAPE it is a 10s window that understates by ~100x (bursty tape,
        # median $0/s). price_eligible already excludes flow after price left our limit (the S50 concern).
        caps = caps_for_legs(legs, m, b, s, window=None, price_eligible=True)   # deployed whole-leg rest
        net = np.array([l.net_bps for l in legs]) / 1e4
        sz = np.array([l.size for l in legs])
        H = n / 3600.0
        row = f"{coin:5}{len(legs):>6}{H:>6.1f}{np.median(caps):>10.0f}" \
              f"{np.percentile(caps,25):>9.0f}{np.percentile(caps,75):>9.0f}   "
        for d in DESIRED:
            desired = d * sz
            uncap = float(np.sum(net * desired)) / H
            filled = np.minimum(desired, caps)
            cap = float(np.sum(net * filled)) / H
            fillpct = 100.0 * float(np.sum(filled)) / float(np.sum(desired))
            row += f"  {uncap:+6.2f}/{cap:+6.2f} ({fillpct:4.0f}%)"
        print(row)
    print("\nRead: medCap$ = median per-leg fillable $. If medCap >> desired, cell is NOT capacity-bound "
          "(majors); fill% -> 100 and uncap≈cap. Thin cells will show medCap << $5k -> the fiction gap.")


if __name__ == "__main__":
    main()
