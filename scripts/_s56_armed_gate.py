"""_s56_armed_gate.py — S56 JOB 1: the FULL GATE on the S55 arming rule (armed_fine_zigzag).

Round 1 (--grid): widen the leg count. ARM x FINE grid on 30d x 5 Bybit bins, flat $5k taker
rt11 through the platform executor (identical mechanics to the S55 first pass), REVERSED column
per cell. Purpose: find where n is thick enough for per-week z-stats; check the S55 20/20
positivity on a finer grid. Report the grid, not the best cell (never tune off one window).

Round 2 (--gate): S54-style full gate on the grid — shuffle (permuted log-returns re-run through
the whole pipeline; flow irrelevant under fill_mode="taker") + per-week splits + z-stats.

Usage:
  python scripts/_s56_armed_gate.py --grid
  python scripts/_s56_armed_gate.py --gate
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS            # noqa: E402
from _s55_armed_zigzag_probe import armed_fine_zigzag        # noqa: E402
from odcore.swing_maker import simulate_swing_maker          # noqa: E402

RT = 11.0
CAP = 5000.0
ARMS = (40.0, 50.0, 60.0, 75.0, 100.0, 125.0, 150.0)
FINES = (15.0, 25.0, 35.0)
N_SHUF = 5
WEEK_S = 7 * 24 * 3600
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_s56_armed_gate_results.json")


def run_armed(mid, buy, sell, arm, fine, reverse=False):
    """Flips + platform executor at S55 first-pass mechanics (flat taker rt11)."""
    fl = armed_fine_zigzag(mid, arm, fine)
    if reverse:
        fl = [(c, p, -s) for (c, p, s) in fl]
    z = np.zeros(len(mid))
    res = simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                               maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
    return res


def load_all():
    data = {}
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] MISSING bins at {p}")
            continue
        mid, buy, sell, cov, hrs = load_bins(p)
        data[coin] = (np.asarray(mid, float), np.asarray(buy, float),
                      np.asarray(sell, float), hrs)
        print(f"[{coin}] {len(mid)} s ({hrs:.1f}h) coverage {cov:.3f}")
    return data


def grid(data):
    print("\nROUND 1 GRID — armed_fine_zigzag, 30d x 5, flat $5k taker rt11, platform executor")
    print("per cell: n legs | net/leg bp | $/hr  (REV = reversed $/hr)")
    rows = {}
    for fine in FINES:
        print(f"\n== FINE {fine:.0f}bp ==")
        hdr = f"{'ARM':>5} | " + "".join(f"{c:>26}" for c in data) + f" | {'TOT$/h':>8}{'REV$/h':>8}"
        print(hdr)
        for arm in ARMS:
            row = f"{arm:>5.0f} | "
            tot = rtot = 0.0
            cells = {}
            for coin, (mid, buy, sell, hrs) in data.items():
                res = run_armed(mid, buy, sell, arm, fine)
                rres = run_armed(mid, buy, sell, arm, fine, reverse=True)
                dhr = res.total_net_bps * CAP / 1e4 / hrs
                rdhr = rres.total_net_bps * CAP / 1e4 / hrs
                tot += dhr; rtot += rdhr
                row += f"{res.n_legs:>6}n {res.net_per_leg_bps:>+7.1f} {dhr:>+8.2f}"
                cells[coin] = dict(n=int(res.n_legs), net_leg=float(res.net_per_leg_bps),
                                   dhr=float(dhr), dhr_rev=float(rdhr),
                                   legs_day=float(res.n_legs / hrs * 24.0))
            print(row + f" | {tot:>+8.2f}{rtot:>+8.2f}")
            rows[f"a{arm:.0f}_f{fine:.0f}"] = cells
    with open(OUT, "w") as f:
        json.dump({"grid": rows}, f, indent=1)
    print(f"\nsaved -> {OUT}")


def shuffle_mid(mid, seed):
    rng = np.random.default_rng(2000 + seed)
    r = np.diff(np.log(mid))
    return float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(rng.permutation(r))]))


def gate(data, arms, fines):
    """Round 2: shuffle + per-week + z per cell on the (given) grid subset."""
    print("\nROUND 2 GATE — shuffle x%d + per-week splits + z" % N_SHUF)
    res_all = {}
    for fine in fines:
        for arm in arms:
            print(f"\n== ARM {arm:.0f} / FINE {fine:.0f} ==")
            print(f"{'coin':>6} {'n':>5} {'$/hr':>8} {'rev':>8} {'shuf_mu':>8} {'shuf_sd':>7} "
                  f"{'z':>6}  weeks $/hr")
            for coin, (mid, buy, sell, hrs) in data.items():
                res = run_armed(mid, buy, sell, arm, fine)
                dhr = res.total_net_bps * CAP / 1e4 / hrs
                rres = run_armed(mid, buy, sell, arm, fine, reverse=True)
                rdhr = rres.total_net_bps * CAP / 1e4 / hrs
                svals = []
                for s in range(N_SHUF):
                    m2 = shuffle_mid(mid, s)
                    sres = run_armed(m2, buy, sell, arm, fine)
                    svals.append(sres.total_net_bps * CAP / 1e4 / hrs)
                smu, ssd = float(np.mean(svals)), float(np.std(svals))
                zz = (dhr - smu) / ssd if ssd > 1e-9 else float("nan")
                wk = []
                nW = max(1, int(len(mid) // WEEK_S))
                for w in range(nW):
                    sl = slice(w * WEEK_S, min(len(mid), (w + 1) * WEEK_S))
                    m_w = mid[sl]
                    if len(m_w) < 12 * 3600:
                        continue
                    h_w = len(m_w) / 3600.0
                    wres = run_armed(m_w, buy[sl], sell[sl], arm, fine)
                    wk.append(float(wres.total_net_bps * CAP / 1e4 / h_w))
                print(f"{coin:>6} {res.n_legs:>5} {dhr:>+8.2f} {rdhr:>+8.2f} {smu:>+8.2f} "
                      f"{ssd:>7.2f} {zz:>6.2f}  " + " ".join(f"{v:+.2f}" for v in wk))
                res_all[f"{coin}_a{arm:.0f}_f{fine:.0f}"] = dict(
                    n=int(res.n_legs), dhr=float(dhr), dhr_rev=float(rdhr),
                    shuf_mu=smu, shuf_sd=ssd, z=float(zz), weeks=wk)
    key = "gate"
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    prev[key] = res_all
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    d = load_all()
    if "--gate" in sys.argv:
        import argparse
        pa = argparse.ArgumentParser()
        pa.add_argument("--gate", action="store_true")
        pa.add_argument("--arms", default="50,75,100,150")
        pa.add_argument("--fines", default="25")
        a = pa.parse_args()
        gate(d, [float(x) for x in a.arms.split(",")],
             [float(x) for x in a.fines.split(",")])
    else:
        grid(d)
