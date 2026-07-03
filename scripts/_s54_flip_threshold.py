"""_s54_flip_threshold.py — find Greg's NUMBER: after a dipole flip, how much price movement
(x_profit_loss, vol-normalized) confirms a DIRECTION CHANGE vs chop?

Greg (S54): "for the bounce back you want the dipole flip + x_profit_loss ... figure out what
threshold change in price has to go after dipole flip before you are sure that it's a direction
change and not chop — I'm sure there's a number we can figure out."

Method (diagnostic only, no strategy code):
  - lean flips from the validated S40 causal detector (odcore.flip_detector, REV=0.25 mid).
  - volatility normalizer = trailing 4h hi-lo range (same as the adaptive big-line engine).
  - for each flip toward side s, sweep confirmation thresholds k: the flip is ACTED ON at the
    first t after confirm where s*(mid[t]-mid[c]) >= k * range_4h(c).
  - score each acted flip with a symmetric bracket theta = 0.25 * range_4h (the adaptive line
    scale): REAL = price runs +theta from the action point before giving back -theta.
    payoff/leg = realized bracket outcome net of taker round-trip.
  - report, per cell and per k: how many flips ever reach the threshold, P(real), mean net/leg,
    and total net $/hr at $5k — the number is where net $/hr peaks CONSISTENTLY across cells
    (never tuned per cell, per window).

Everything is causal bookkeeping on past data + a forward bracket for scoring; this is a
measurement, not a backtest — the bracket payoff ignores queue/fill detail on purpose.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                      # noqa: E402
from _liquidity_dive import build_channels              # noqa: E402
from _capacity_model import FLOW_W                      # noqa: E402
from _s54_bigline_probe import CELLS, DEC, LEAN_W_1S    # noqa: E402
from odcore.flip_detector import lean_series, detect_flips  # noqa: E402

REV = 0.25
K_GRID = [0.0, 0.02, 0.04, 0.06, 0.09, 0.12, 0.18, 0.25]
RANGE_W = 4 * 3600           # 4h, 1-sec cells
BRACKET_FRAC = 0.25          # theta = 0.25 x range (the adaptive line scale)
NOTIONAL = 5_000.0
# S54 finding at (W=60s, REV=0.25): 17-87 flips/hr, P(real) ~ 0.50 at every k, all cells bleed —
# the ripple-scale lean measures the CHOP, not the trend turns. The dive must be measured at the
# trend's scale (kickoff: "DIVW may need scale-up"). Sweep the detector scale:
SCALE_GRID = [(60, 0.25), (600, 0.25), (600, 0.5), (1800, 0.25), (1800, 0.5)]
K_GRID_COARSE = [0.0, 0.04, 0.09, 0.18, 0.25]


def rolling_range_bps(mid, W):
    """Trailing hi-lo range in bps at each t (causal), O(n) via deques."""
    from collections import deque
    n = len(mid)
    out = np.zeros(n)
    maxq, minq = deque(), deque()
    for t in range(n):
        m = mid[t]
        while maxq and mid[maxq[-1]] <= m:
            maxq.pop()
        maxq.append(t)
        while minq and mid[minq[-1]] >= m:
            minq.pop()
        minq.append(t)
        w0 = t - W
        while maxq[0] <= w0:
            maxq.popleft()
        while minq[0] <= w0:
            minq.popleft()
        out[t] = (mid[maxq[0]] - mid[minq[0]]) / m * 1e4
    return out


def bracket_outcome(mid, start, side, theta_bps):
    """From mid[start], first touch of +theta (with the flip) vs -theta (against). Returns
    (real: bool, pnl_bps, end_idx) where pnl is the touched side's move; None if data ends."""
    th = theta_bps / 1e4
    base = mid[start]
    up = base * (1 + th)
    dn = base * (1 - th)
    n = len(mid)
    for t in range(start + 1, n):
        m = mid[t]
        if m >= up:
            return (side > 0), (theta_bps if side > 0 else -theta_bps), t
        if m <= dn:
            return (side < 0), (theta_bps if side < 0 else -theta_bps), t
    return None


def run_cell(cell, path, K, tk):
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)[::DEC]
    buy0 = np.asarray(g["buy"], float)
    sell0 = np.asarray(g["sell"], float)
    n10 = (len(buy0) // DEC) * DEC
    buy1 = buy0[:n10].reshape(-1, DEC).sum(1)
    sell1 = sell0[:n10].reshape(-1, DEC).sum(1)
    L = min(len(mid), len(buy1))
    mid, buy1, sell1 = mid[:L], buy1[:L], sell1[:L]
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    rng4 = rolling_range_bps(mid, RANGE_W)
    rt = 2 * tk
    out = dict(cell=cell, hrs=hrs, scales={})

    for (W, rev) in SCALE_GRID:
        lean = lean_series(buy1, sell1, W)
        flips, _pos = detect_flips(lean, rev)
        flips = [(int(c), int(p), int(s)) for (c, p, s) in flips if c > RANGE_W // 4]
        srow = dict(n_flips=len(flips), flips_hr=len(flips) / hrs, k={})
        kg = K_GRID if (W, rev) == (60, 0.25) else K_GRID_COARSE
        for k in kg:
            acted = 0
            real = 0
            pnl = []
            lag = []
            for (c, p, s) in flips:
                rng = rng4[c]
                if rng <= 0:
                    continue
                xthr = k * rng / 1e4
                base = mid[c]
                # first t where the post-flip move reaches k x range (k=0 -> act at the flip)
                t_act = None
                horizon = min(len(mid), c + RANGE_W)      # give it up to 4h to confirm
                if k == 0.0:
                    t_act = c
                else:
                    for t in range(c + 1, horizon):
                        if s * (mid[t] - base) / base >= xthr:
                            t_act = t
                            break
                if t_act is None:
                    continue
                theta = BRACKET_FRAC * rng4[t_act]
                b = bracket_outcome(mid, t_act, s, theta)
                if b is None:
                    continue
                acted += 1
                real += int(b[0])
                pnl.append(b[1] - rt)
                lag.append(s * (mid[t_act] - base) / base * 1e4)
            srow["k"][f"{k:.2f}"] = dict(
                acted=acted, act_frac=acted / max(1, len(flips)),
                p_real=(real / acted) if acted else None,
                net_leg=float(np.mean(pnl)) if pnl else None,
                dhr=float(np.sum(pnl) / 1e4 * NOTIONAL / hrs) if pnl else 0.0,
                med_lag_bps=float(np.median(lag)) if lag else None)
        out["scales"][f"W{W}_r{rev:.2f}"] = srow
    return out


def main():
    results = []
    for (cell, path, K, tk) in CELLS:
        r = run_cell(cell, path, K, tk)
        if r is None:
            continue
        results.append(r)
        print(f"\n== {cell} ({r['hrs']:.1f}h) ==")
        for sname, srow in r["scales"].items():
            print(f"  {sname}: {srow['n_flips']} flips ({srow['flips_hr']:.1f}/hr)")
            print("    k(xrange)  acted  act%   P(real)  net/leg(tk)   $/hr")
            for k, row in srow["k"].items():
                pr = "  n/a" if row["p_real"] is None else f"{row['p_real']:.2f}"
                nl = "   n/a" if row["net_leg"] is None else f"{row['net_leg']:+.1f}"
                print(f"      {k}     {row['acted']:>5}  {row['act_frac']:>4.0%}    {pr}"
                      f"    {nl:>8}   {row['dhr']:>+7.2f}")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s54_flip_threshold_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
