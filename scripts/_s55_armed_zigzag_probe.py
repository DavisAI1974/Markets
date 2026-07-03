"""_s55_armed_zigzag_probe.py — the ARMING RULE v1 (S55 round 15): armed fine-confirm zigzag.

Greg: "I thought we wired in the part that shortened the lag?" — the executor capability was
wired (R10/R12/R13); this is the AIMER: a two-stage confirm zigzag. The leg must EXTEND >= arm_bp
from the last flip pivot (the scale filter — paid DURING the ride, costless at the turn), then
the first fine_bp reversal off the running extreme confirms the flip (paid AT the turn: ~fine_bp
instead of theta). Bounded loss by construction (a fakeout re-arms opposite at ~arm+fine).

FIRST-PASS RESULT (30d x 5 Bybit bins, taker rt11, $5k flat, via the platform executor):
positive on ALL 5 coins at ALL ARM levels {50,75,100,150} (20/20 cells), REVERSED negative on
every row; net/leg tracks the R14 lag projection (ARM150: +100..+121bp/leg). CAVEATS (why this
is NOT adopted): n tiny on 4 coins (eth 2 legs); entries fire on the FIRST post-arm dip (often
mid-leg, not the true turn — the dipole gate is the natural fix); S54 full gate (shuffle +
per-week x 5 coins) NOT yet run. Sandbox-first: promote armed_fine_zigzag into odcore only
after the gate passes.

Usage: python scripts/_s55_armed_zigzag_probe.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS      # noqa: E402
from odcore.swing_maker import simulate_swing_maker   # noqa: E402

RT = 11.0
CAP = 5000.0
FINE = 25.0


def armed_fine_zigzag(mid, arm_bp, fine_bp):
    """Two-stage confirm zigzag (causal). Returns (confirm_idx, pivot_idx, side) like
    detect_flips, so it feeds the platform executor directly."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    last_px = mid[0]
    mode = 0   # +1 riding up (watch for the peak), -1 down, 0 undetermined
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed = mid[hi_i] >= last_px * (1 + a)
            if armed and m <= mid[hi_i] * (1 - f):        # fine reversal off the peak
                flips.append((t, hi_i, -1)); mode = -1; last_px = mid[hi_i]; lo_i = t
                continue
        if mode <= 0:
            armed = mid[lo_i] <= last_px * (1 - a)
            if armed and m >= mid[lo_i] * (1 + f):        # fine reversal off the valley
                flips.append((t, lo_i, +1)); mode = +1; last_px = mid[lo_i]; hi_i = t
    return flips


def main():
    data = {}
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] no bins — re-pull per kickoff")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        data[coin] = (np.asarray(mid, float), np.asarray(buy, float),
                      np.asarray(sell, float), hrs)
    print("ARMED FINE-CONFIRM ZIGZAG v1 — 30d x 5, taker rt11, $5k flat, platform executor")
    print(f"{'ARM':>5} | " + "".join(f"{c:>9}" for c in data) + f"{'TOTAL':>9}{'REV':>9}")
    for ARM in (50.0, 75.0, 100.0, 150.0):
        row = f"{ARM:>5.0f} | "
        tot = rtot = 0.0
        detail = []
        for coin, (mid, buy, sell, hrs) in data.items():
            fl = armed_fine_zigzag(mid, ARM, FINE)
            z = np.zeros(len(mid))
            res = simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                                       maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
            rfl = [(c, p, -s) for (c, p, s) in fl]
            rres = simulate_swing_maker(mid, z, z, buy, sell, rfl, half_spread_bps=0.0,
                                        maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
            v = res.total_net_bps * CAP / 1e4 / hrs
            tot += v; rtot += rres.total_net_bps * CAP / 1e4 / hrs
            row += f"{v:>+9.2f}"
            detail.append(f"{coin}:{res.n_legs}n/{res.net_per_leg_bps:+.1f}bp")
        print(row + f"{tot:>+9.2f}{rtot:>+9.2f}   " + " ".join(detail))


if __name__ == "__main__":
    main()
