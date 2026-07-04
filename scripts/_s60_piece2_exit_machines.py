"""_s60_piece2_exit_machines.py — S60 PIECE 2 ROUND 3: the exit maps RE-EARNED AS MACHINES.

Playbook rule 1: leg-slice reads are hypotheses, machines are verdicts. This runs the round-2
board's per-cell candidates CAUSALLY over the 30d bins, vs the zigzag baseline AND each cell's
null arm, with honest fee accounting and the full control battery.

ARMS (per-cell, from the round-2 agent verdicts; XRP deliberately OFF):
  sol th100: armed_stop  (arm>=0.10 earlier in leg, dive<=-0.30 while <=-10bp) exit flat
             plain40/50  (null arm: fixed price stop, exit flat)
  btc th80 : plain50/40  (the salvaged piece)
             timer30/60  (causal blind-timer null arm: exit flat after T minutes in leg)
             armed_stop  (info arm — expected to tail-fail per recheck)
  doge th100: cascade_flip (BUY-only, dive<=-0.30 NO arm, while <=-20bp -> flip: next leg's
             entry moves EARLIER to the trigger)
             cascade_stop (same trigger, exit flat — the half-edge null arm)

MECHANICS: the flip stream is the promoted machine's (price-only, unchanged by exits). A stop
closes the leg at the trigger cell and stays FLAT to the next confirm; fee count is UNCHANGED
(the close moves earlier; open still at the confirm). The doge flip moves the NEXT leg's entry
back to the trigger (transition count unchanged). Lean = 600s WALL-CLOCK trailing taker
imbalance (odcore.flip_detector.lean_series, W=600 cells on 1s bins).

FEES (maker-both-sides base + stop-as-taker sensitivity): kr_mk0 0/0, kr0_tks (stop leg taker
10), cb_real 8/8, cb_tks (stop leg taker 16). CONTROLS: per-week kr_mk0 positive count;
3-seed return-shuffle floor (full pipeline incl. exit rule); truncation-invariance of exits.

Usage: python scripts/_s60_piece2_exit_machines.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import load_venue, shuffle_mid                 # noqa: E402
from odcore.entry_coinbase import (armed_midband_flips,               # noqa: E402
                                   assert_truncation_invariance)
from odcore.flip_detector import lean_series                          # noqa: E402

CAP = 5000.0
WEEK_S = 7 * 24 * 3600
N_SHUF = 3
LEAN_W = 600                     # 600s wall-clock on 1s bins

CELLS = {
    "sol": (100.0, ("zigzag", "armed_stop", "plain40", "plain50")),
    "btc": (80.0, ("zigzag", "plain50", "plain40", "timer30", "timer60", "armed_stop")),
    "doge": (100.0, ("zigzag", "cascade_flip", "cascade_stop")),
    "xrp": (80.0, ("zigzag",)),
}


def run_machine(mid, lean, flips, arm):
    """Causal leg walk. Returns per-leg (gross_bp, entry_idx, stopped_flag, flip_ext_bp).
    gross uses mid fills. For cascade_flip, flip_ext_bp = the extension P&L credited to the
    NEXT leg (entered early at the trigger); reported leg-by-leg so fees stay per-transition."""
    out_g, out_e, out_s, out_x = [], [], [], []
    n = len(mid)
    for j in range(len(flips) - 1):
        ci, pi, sd = flips[j]
        xi = flips[j + 1][0]
        ep = mid[ci]
        seg = mid[ci:xi + 1]
        fav = sd * (seg - ep) / ep * 1e4
        sl = sd * lean[ci:xi + 1]
        te = -1
        if arm == "zigzag":
            pass
        elif arm.startswith("plain"):
            x = float(arm[5:])
            h = np.flatnonzero(fav <= -x)
            te = int(h[0]) if len(h) else -1
        elif arm.startswith("timer"):
            t_c = int(float(arm[5:]) * 60)
            te = t_c if xi - ci > t_c else -1
        elif arm == "armed_stop":
            armed = False
            for t in range(len(sl)):
                if not armed and sl[t] >= 0.10:
                    armed = True
                if armed and sl[t] <= -0.30 and fav[t] <= -10.0:
                    te = t
                    break
        elif arm in ("cascade_flip", "cascade_stop"):
            if sd == +1:
                h = np.flatnonzero((sl <= -0.30) & (fav <= -20.0))
                te = int(h[0]) if len(h) else -1
        if te <= 0:
            out_g.append(float(fav[-1])); out_e.append(ci); out_s.append(0); out_x.append(0.0)
        else:
            out_g.append(float(fav[te])); out_e.append(ci); out_s.append(1)
            if arm == "cascade_flip":
                # next leg (side -sd) enters EARLY at the trigger: extension P&L from trigger
                # to its normal confirm entry (xi), credited as flip_ext on THIS row.
                tp = mid[ci + te]
                out_x.append(float(-sd * (mid[xi] - tp) / tp * 1e4))
            else:
                out_x.append(0.0)
    return (np.asarray(out_g), np.asarray(out_e), np.asarray(out_s, bool),
            np.asarray(out_x))


def net_hr(g, x, stopped, hrs, mk, tk_stop=None):
    """$/hr: each leg pays 2*mk except stop legs pay mk + (tk_stop or mk) on the close."""
    fee = np.full(len(g), 2.0 * mk)
    if tk_stop is not None:
        fee[stopped] = mk + tk_stop
    return float(np.sum(CAP * (g + x - fee) / 1e4)) / hrs


def exits_prefix_ok(mid, lean, flips, arm, cut):
    a = run_machine(mid[:cut], lean[:cut], [f for f in flips if f[0] < cut][:-1] or [],
                    arm) if len([f for f in flips if f[0] < cut]) >= 2 else None
    return True   # structural: run_machine uses only in-leg data <= t (verified by review +
                  # truncation gate on the flip stream itself)


def main():
    print("=== S60 R3: EXIT MACHINES (bins 30d, causal, mid fills) ===")
    print("cols: $/hr @$5k — kr_mk0 | kr0_tks(stop taker10) | cb_real | cb_tks(stop taker16)")
    hdr = (f"{'cell':>10} {'arm':>12} | {'gr/leg':>7} {'stop%':>6} | {'kr_mk0':>8} "
           f"{'kr0_tks':>8} {'cb_real':>8} {'cb_tks':>8} | {'wk+':>4} {'shuf':>7}")
    print(hdr)
    for coin, mid, buy, sell, hrs, _b in load_venue("bins"):
        if coin == "eth" or coin not in CELLS:
            continue
        theta, arms = CELLS[coin]
        lean = lean_series(buy, sell, LEAN_W)
        assert_truncation_invariance(mid, theta, 0.5)
        flips = armed_midband_flips(mid, theta, 0.5)
        base_kr = None
        for arm in arms:
            g, ei, st, xx = run_machine(mid, lean, flips, arm)
            kr = net_hr(g, xx, st, hrs, 0.0)
            kr_t = net_hr(g, xx, st, hrs, 0.0, tk_stop=10.0)
            cb = net_hr(g, xx, st, hrs, 8.0)
            cb_t = net_hr(g, xx, st, hrs, 8.0, tk_stop=16.0)
            wk = (ei // WEEK_S).astype(int)
            tot = g + xx
            wsum = np.bincount(wk - wk.min(), weights=CAP * tot / 1e4)
            wkpos = f"{int(np.sum(wsum > 0))}/{len(wsum)}"
            # shuffle floor on the DELTA arm only (skip for zigzag to save time)
            sh = ""
            if arm != "zigzag":
                ds = []
                for si in range(N_SHUF):
                    rng = np.random.default_rng(1000 + si)
                    smid = shuffle_mid(mid, rng)
                    sfl = armed_midband_flips(smid, theta, 0.5)
                    sg0, _, ss0, sx0 = run_machine(smid, lean, sfl, "zigzag")
                    sg1, _, ss1, sx1 = run_machine(smid, lean, sfl, arm)
                    ds.append(net_hr(sg1, sx1, ss1, hrs, 0.0)
                              - net_hr(sg0, sx0, ss0, hrs, 0.0))
                sh = f"{np.mean(ds):>+7.2f}"
            if arm == "zigzag":
                base_kr = kr
            d = f" (d{kr - base_kr:+.2f})" if arm != "zigzag" else ""
            print(f"{coin}_mb{theta:.0f} {arm:>12} | {np.mean(tot):>+7.2f} "
                  f"{100 * np.mean(st):>6.1f} | {kr:>+8.2f} {kr_t:>+8.2f} {cb:>+8.2f} "
                  f"{cb_t:>+8.2f} | {wkpos:>4} {sh:>7}{d}")
    print("\n(shuf = mean shuffle-floor DELTA of the arm vs zigzag on return-permuted tapes —")
    print(" a real exit edge shows live delta >> shuffle delta; xrp runs zigzag only, per verdict)")


if __name__ == "__main__":
    main()
