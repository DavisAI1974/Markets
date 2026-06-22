"""_flip_gate_test.py — does the dipole-dive tracking SELECT better swings on the FULL flip population?

The dive->swing relationship was measured on winners (survivorship). The real test: on ALL detected flips
(duds included, the over-trading set), does dive magnitude track the realized swing? If gentle-dive flips
realize bigger gross swings than violent ones, the (inverse) tracking is real + usable as a gate. Sign is
irrelevant; tracking + effect size is everything."""
from __future__ import annotations
import numpy as np
from pathlib import Path
from odcore.io import load_bins
from odcore.flip_detector import lean_series, detect_flips

W, REV, DIVEWIN = 60, 0.10, 30
TAKER, MAKER = 10.0, 4.0


def main():
    for cv in ("btc_bybit_perp", "eth_bybit_perp"):
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        bs = load_bins(f"realbins/{cv}_bins.json"); mid = bs.mid
        lean = lean_series(bs.buy, bs.sell, W)
        flips, _ = detect_flips(lean, REV)
        steep, gross = [], []
        for k in range(len(flips) - 1):
            ci, pv, side = flips[k]; nci = flips[k + 1][0]
            if mid[ci] <= 0 or mid[nci] <= 0 or pv - DIVEWIN < 0:
                continue
            d = np.diff(lean[pv - DIVEWIN:pv + 1])
            steep.append(float(-np.min(d)) if len(d) else 0.0)    # steepest drop into the pivot (violence)
            gross.append(float(side * np.log(mid[nci] / mid[ci]) * 1e4))
        steep = np.array(steep); gross = np.array(gross); n = len(gross)
        cc = np.corrcoef(steep, gross)[0, 1]
        print(f"\n=== {cv}  ({n} flips, FULL population incl. duds) ===")
        print(f"corr(dive steepness, realized gross swing) = {cc:+.3f}")
        q = np.quantile(steep, [0, .25, .5, .75, 1.0])
        print(f"{'dive bin':10} {'gross/sw':>9} {'net@maker':>10} {'net@taker':>10} {'n':>6}")
        for lo, hi, lab in zip(q[:-1], q[1:], ["Q1 gentle", "Q2", "Q3", "Q4 violent"]):
            m = (steep >= lo) & (steep <= hi)
            g = gross[m].mean()
            print(f"{lab:10} {g:>9.2f} {g - MAKER:>10.2f} {g - TAKER:>10.2f} {m.sum():>6}")
        # if gentle flips clear maker while violent don't, that's a usable gate
        gentle = steep <= q[1]; viol = steep >= q[3]
        print(f"gentle-only net@maker={gross[gentle].mean()-MAKER:+.2f}  "
              f"violent-only net@maker={gross[viol].mean()-MAKER:+.2f}")


if __name__ == "__main__":
    main()
