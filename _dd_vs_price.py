"""_dd_vs_price.py — does a HARDER dipole dive predict a BIGGER price swing? (the swing-size gate test)

Per turn: measure the dipole DIVE into the turn (depth + steepness) and the PRICE SWING that follows
(favorable excursion over the next POST seconds). If harder dive -> bigger swing, dive magnitude IS the gate.
Covered BTC/ETH bybit winners, turn-aligned."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from odcore.io import load_bins

LB = 1800; H = 60; W = 60; POST = 600; CAP = 500


def main():
    offs = np.arange(-H, 1).astype(int)         # pre-turn .. turn
    depth, steep, swing = [], [], []
    for cv in ("btc_bybit_perp", "eth_bybit_perp"):
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        bs = load_bins(f"realbins/{cv}_bins.json"); ts, mid, bvol, svol = bs.ts, bs.mid, bs.buy, bs.sell
        cb = np.concatenate([[0.0], np.cumsum(bvol)]); cs = np.concatenate([[0.0], np.cumsum(svol)])
        t0, t1 = ts[0], ts[-1]
        for side in ("buy", "sell"):
            fp = Path(f"_alt_labels/{cv}_{side}_winner_onsets.json")
            if not fp.exists():
                continue
            sgn = 1.0 if side == "buy" else -1.0; cnt = 0
            for r in json.load(open(fp)):
                if cnt >= CAP:
                    break
                dts = float(r["decision_ts_utc"])
                if not (t0 + LB <= dts <= t1):
                    continue
                i = int(np.searchsorted(ts, dts, "right")) - 1
                w = mid[i - LB:i + 1]
                if (w <= 0).any():
                    continue
                E = i - LB + (int(np.argmin(w)) if side == "buy" else int(np.argmax(w)))
                if (i - E) < H or (E - H - W) < 0 or (E + POST + 1) > len(ts):
                    continue
                lean = np.empty(len(offs))
                for k, o in enumerate(offs):
                    end = int(E + o)
                    B = cb[end + 1] - cb[end - W + 1]; Sv = cs[end + 1] - cs[end - W + 1]; tot = B + Sv
                    lean[k] = sgn * (B - Sv) / tot if tot > 0 else 0.0
                # DIVE (sign-agnostic magnitudes -> real-time gate-able):
                dd_depth = float(-lean[-1])                       # how deep the against-side flow got at the turn
                dd_steep = float(-np.min(np.diff(lean)))          # steepest 1s drop approaching the turn
                # PRICE SWING after the turn (favorable excursion in the new direction):
                fwd = mid[E + 1:E + POST + 1]
                sw = float(np.max(sgn * np.log(fwd / mid[E]) * 1e4)) if (fwd > 0).all() else 0.0
                depth.append(dd_depth); steep.append(dd_steep); swing.append(sw); cnt += 1
    depth = np.array(depth); steep = np.array(steep); swing = np.array(swing); n = len(swing)
    print(f"n={n}   POST={POST}s favorable excursion = the swing")
    print(f"corr(dive DEPTH, swing)     = {np.corrcoef(depth, swing)[0,1]:+.3f}")
    print(f"corr(dive STEEPNESS, swing) = {np.corrcoef(steep, swing)[0,1]:+.3f}")
    for name, v in [("DEPTH", depth), ("STEEPNESS", steep)]:
        q = np.quantile(v, [0, .25, .5, .75, 1.0])
        print(f"\nmean swing (bps) by dive-{name} quartile:")
        for lo, hi, lab in zip(q[:-1], q[1:], ["Q1 soft", "Q2", "Q3", "Q4 HARD"]):
            m = (v >= lo) & (v <= hi)
            print(f"  {lab:8s} {name.lower()}[{lo:.3f},{hi:.3f}]  swing={swing[m].mean():6.1f}  (n={m.sum()})")
    # fee-floor framing: of the HARD-dive turns, what frac clears the maker (>4) / taker (>22) floor?
    hard = steep >= np.quantile(steep, 0.75)
    print(f"\nhard-dive (top-quartile steepness) turns clearing fee floor:")
    print(f"  > 4 bps (maker): {(swing[hard] > 4).mean():.1%}   vs all turns {(swing > 4).mean():.1%}")
    print(f"  >22 bps (taker): {(swing[hard] > 22).mean():.1%}   vs all turns {(swing > 22).mean():.1%}")


if __name__ == "__main__":
    main()
