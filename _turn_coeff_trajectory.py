"""_turn_coeff_trajectory.py — does the OD coeff FLIP through the turn? (second-by-second around the 33)

Greg: get second-by-second coeffs for the minute before the turn, through it, and the minute after — there's
a distinct pattern. Instead of one coeff per 30-min window, slide the cs100_v2 pipeline second-by-second
around the located turn and project each rolling coeff onto the BUY/SELL axis (the mirror direction). If the
operator flips through the turn, the projection (sign-aligned to the winning side) should rise from negative
(old/against) through ~0 at the turn to positive (new/with).

Everything stays PRE-ENTRY: we only use turns that sit >= T_HALF before the trade's decision second.
Runs on local bins (covered winners). Usage: python _turn_coeff_trajectory.py
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from odcore.io import load_bins
from odcore.fingerprint_predictor import assemble, global_mean_coeff, _l2
from _run_alt_coeffs import coef_for_window

LB = 1800          # 30-min pre-entry window to locate the turn
WIN = 300          # trailing window (sec) per rolling coeff (>=192 chunker req)
T_HALF = 120       # +/- seconds around the turn to trace
STEP = 5           # sample every STEP seconds
CAP = 120          # winners per cell (speed)


def main():
    per = assemble("_alt_labels/coeffs/alt_coeff_index.json.gz", "_alt_labels")
    g = global_mean_coeff(per)
    buy = np.vstack([np.array([r["coeff"] for r in per[c]]) for c in per if c.endswith("_buy")])
    sell = np.vstack([np.array([r["coeff"] for r in per[c]]) for c in per if c.endswith("_sell")])
    axis = _l2(_l2((buy - g).mean(0)) - _l2((sell - g).mean(0)))   # buy<->sell discriminant (residual)

    offs = list(range(-T_HALF, T_HALF + 1, STEP))
    acc = {o: [] for o in offs}
    n_used = 0
    for cv in ("btc_bybit_perp", "eth_bybit_perp"):
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        bs = load_bins(f"realbins/{cv}_bins.json"); ts, mid = bs.ts, bs.mid
        t0, t1 = ts[0], ts[-1]
        for side in ("buy", "sell"):
            fp = Path(f"_alt_labels/{cv}_{side}_winner_onsets.json")
            if not fp.exists():
                continue
            sgn = 1.0 if side == "buy" else -1.0
            cnt = 0
            for r in json.load(open(fp)):
                if cnt >= CAP:
                    break
                dts = float(r["decision_ts_utc"])
                if not (t0 + LB <= dts <= t1):
                    continue
                i = int(np.searchsorted(ts, dts, side="right")) - 1
                w = mid[i - LB:i + 1]
                if (w <= 0).any():
                    continue
                E = i - LB + (int(np.argmin(w)) if side == "buy" else int(np.argmax(w)))  # turn idx
                if (i - E) < T_HALF or (E - T_HALF - WIN) < 0:     # keep whole trace pre-entry + in-range
                    continue
                traj = {}
                ok = True
                for o in offs:
                    t = E + o
                    m = mid[t - WIN:t]
                    if (m <= 0).any():
                        ok = False; break
                    c = coef_for_window(np.diff(np.log(m)).tolist())
                    if c is None:
                        ok = False; break
                    traj[o] = sgn * float(_l2(np.asarray(c[0]) - g) @ axis)   # signed toward winside
                if ok:
                    for o in offs:
                        acc[o].append(traj[o]);
                    cnt += 1; n_used += 1
    print(f"n={n_used} winners traced (rolling coeff every {STEP}s, +/-{T_HALF}s around the turn)\n")
    print("offset(s)   coeff->winside (mean)    [sign flip = the operator turning]")
    prev = None
    for o in offs:
        m = float(np.mean(acc[o])) if acc[o] else float("nan")
        mark = ""
        if prev is not None and prev < 0 <= m:
            mark = "  <== crosses 0 (flip)"
        prev = m
        print(f"  {o:+5d}      {m:+.4f}{mark}")
    vals = np.array([np.mean(acc[o]) for o in offs])
    print(f"\nedge(-{T_HALF}s)={vals[0]:+.4f}  turn(0s)={vals[len(offs)//2]:+.4f}  edge(+{T_HALF}s)={vals[-1]:+.4f}")
    print("READ: a clean rise from - to + through 0 near the turn = the OD coeff itself flips with the swing -> "
          "a second-by-second operator signature of the turn (the distinct pattern).")


if __name__ == "__main__":
    main()
