"""_flip_gate_split.py — does the dive->swing tracking live INSIDE cells (Simpson's)? Split, don't pool.
Per cell (coin x venue) x side (detector long/short): corr(dive steepness, realized gross swing)."""
from __future__ import annotations
import numpy as np
from pathlib import Path
from odcore.io import load_bins
from odcore.flip_detector import lean_series, detect_flips

W, REV, DIVEWIN = 60, 0.10, 30
CELLS = ["btc_bybit_perp", "eth_bybit_perp", "btc_kraken", "eth_kraken", "btc_coinbase", "eth_coinbase"]


def flip_feats(cv):
    bs = load_bins(f"realbins/{cv}_bins.json"); mid = bs.mid
    lean = lean_series(bs.buy, bs.sell, W)
    flips, _ = detect_flips(lean, REV)
    rows = []
    for k in range(len(flips) - 1):
        ci, pv, side = flips[k]; nci = flips[k + 1][0]
        if mid[ci] <= 0 or mid[nci] <= 0 or pv - DIVEWIN < 0:
            continue
        d = np.diff(lean[pv - DIVEWIN:pv + 1])
        steep = float(-np.min(d)) if len(d) else 0.0
        gross = float(side * np.log(mid[nci] / mid[ci]) * 1e4)
        rows.append((side, steep, gross))
    return rows


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 5 and np.std(a) > 0 and np.std(b) > 0 else float("nan")


def main():
    print(f"{'cell':16} {'side':5} {'n':>6} {'corr(dive,swing)':>17} {'gentleGross':>12} {'violentGross':>13}")
    for cv in CELLS:
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        rows = flip_feats(cv)
        for sd, lab in [(1, "long"), (-1, "short"), (None, "BOTH")]:
            sub = [r for r in rows if (sd is None or r[0] == sd)]
            if len(sub) < 20:
                continue
            st = np.array([r[1] for r in sub]); gr = np.array([r[2] for r in sub])
            q1, q3 = np.quantile(st, .25), np.quantile(st, .75)
            gentle = gr[st <= q1].mean(); viol = gr[st >= q3].mean()
            print(f"{cv:16} {lab:5} {len(sub):>6} {corr(st, gr):>17.3f} {gentle:>12.2f} {viol:>13.2f}")
        print()


if __name__ == "__main__":
    main()
