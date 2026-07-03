"""_s55_bigline_platform_rerun.py — the BIG LINE rerun through THE ONE VERSION (S55 round 13).

Greg: "rerun the new big line complete version to see where we actually sit." The S54 bigline
verdicts were rendered by probe mechanics (taker-taker at mid, flat size, own fee math). This
rerun renders the SAME adaptive aligned big line (f0.25/w4h, ratcheting redraw — untouched in
odcore/swing_bigline.py) through odcore/platform.run_stream, i.e. the platform's own executor:

  - bigline legs -> a gated flip stream: entry events (gate TRUE, opens) + line-break events
    (gate FALSE -> the executor FLATTENS and does not reopen — exactly the bigline's flat state).
    This is the platform's generic structure-selects/executor-executes interface (two-scale shape).
  - Coinbase books: fill_mode="maker" (front-of-queue fills, mk0/tk5, cover-grace, half-spread
    earned) — the deploy-mechanics number the S54 probe could not produce. PLUS taker mode for
    apples-to-apples with S54.
  - Bybit 30d bins: fill_mode="taker" rt11 (no book depth) + REVERSED control (mandatory).
  - SIZED column via the platform's size_legs (same features as run_cell at the entry cell) —
    labeled PROVISIONAL at coarse scale (round 11: coarse axes not yet earned).

Usage: python scripts/_s55_bigline_platform_rerun.py [books|bins|all]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.platform import run_stream                    # noqa: E402
from odcore.flip_detector import lean_series              # noqa: E402
from odcore.swing_maker import size_legs                  # noqa: E402
from odcore.swing_bigline import run_bigline_adaptive     # noqa: E402
from _s54_bigline_probe import CELLS, DEC, FIXED_AD       # noqa: E402
from _s54_backfill_sweep import load_bins, COINS          # noqa: E402

CAP = 5000.0


def bigline_events(mid_1s, scale=1):
    """Adaptive big line -> (flips, exit_cells) on the target grid (scale = cells per 1s bin).
    Entry event: (entry_i, entry_i, side) plain flip (opens). Break event: (exit_i, exit_i,
    -side) with exit_gate True at that cell -> executor FLATTENS and opens nothing (the
    bigline's flat period). NOTE (S55 R13): entry_gate=False does NOT flatten — the executor
    HOLDS on non-actionable flips (S46 doc/code mismatch found by this adapter's first,
    invalid version); exit_gate is the correct structure-says-out input."""
    legs = run_bigline_adaptive(mid_1s, FIXED_AD[0], int(FIXED_AD[1] * 3600))
    flips, exit_cells = [], set()
    for l in legs:
        e, x = int(l.entry_i) * scale, int(l.exit_i) * scale
        if x <= e:
            continue
        flips.append((e, e, int(l.side)))
        flips.append((x, x, -int(l.side)))
        exit_cells.add(x)
    flips.sort(key=lambda f: f[0])
    return flips, exit_cells, legs


def _sized(res, mid, buy, sell, alpha=1.0, roll=200):
    """Platform sizing on the stream's legs (same features as platform.run_cell at the flip cell).
    PROVISIONAL at coarse scale — round 11: axes not yet earned; reported as a labeled column."""
    if not res.legs:
        return 0.0, 1.0
    vol = buy + sell
    cvol = np.concatenate([[0.0], np.cumsum(vol)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    lean = lean_series(buy, sell, 600)
    ret = np.concatenate([[0.0], np.diff(mid) / mid[:-1]])
    q, sx = [], []
    for l in res.legs:
        ci = int(l.flip_idx); lo = max(0, ci - 600)
        q.append(vm(ci, 60) / (vm(ci, 600) + 1e-12))
        v60 = vm(ci, 60); vlt = float(np.std(ret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4
        sx.append(v60 + vlt + rnp + abs(lean[ci]))
    for l in res.legs:
        l.size = 1.0
    tot = size_legs(res.legs, q, sx, alpha=alpha, roll=roll)
    return tot, float(np.mean([l.size for l in res.legs]))


def run_books():
    import importlib
    bp = importlib.import_module("_birth_probe"); ld = importlib.import_module("_liquidity_dive")
    print("=== BIG LINE via the platform — Coinbase/Bybit BOOK windows ===")
    print(f"{'cell':<14}{'legs':>5} | {'MAKER mk0/tk5':>14}{'$/hr':>7} | {'TAKER rt10':>11}{'$/hr':>7} | "
          f"{'sized(mk)':>10}{'msz':>5}")
    for (cell, path, K, tk) in CELLS:
        if not os.path.exists(path):
            continue
        raw = bp.load_book(path)
        ch, g = ld.build_channels(path, K, 20, raw=raw)
        mid = np.asarray(g["mid"], float)
        bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
        buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
        hs = ld.median_spread_bps(path, raw=raw) / 2.0
        hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
        mid_1s = mid[::DEC]
        flips, exit_cells, _legs = bigline_events(mid_1s, scale=DEC)
        xg = np.zeros(len(mid), bool)
        for c in exit_cells:
            if c < len(xg):
                xg[c] = True
        from odcore.swing_maker import simulate_swing_maker
        rm = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                  maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=300,
                                  exit_gate=xg, fill_mode="maker")
        rt = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                  maker_fee_bps=5.0, taker_fee_bps=5.0, cover_grace=0,
                                  exit_gate=xg, fill_mode="taker")
        dph = CAP / 1e4 / hrs
        sz_tot, msz = _sized(rm, mid, buy, sell)
        print(f"{cell:<14}{rm.n_legs:>5} | {rm.total_net_bps:>+13.0f}bp{rm.total_net_bps*dph:>+7.2f} | "
              f"{rt.total_net_bps:>+10.0f}bp{rt.total_net_bps*dph:>+7.2f} | "
              f"{sz_tot*dph:>+10.2f}{msz:>5.2f}")


def run_bins():
    from odcore.swing_maker import simulate_swing_maker
    print("\n=== BIG LINE via the platform — Bybit 30d x 5 bins (taker rt11) + REVERSED control ===")
    print(f"{'coin':<6}{'legs':>6}{'net/leg':>9}{'total':>9}{'$/hr':>8} | {'REV $/hr':>9} | "
          f"{'sized $/hr':>11}{'msz':>5}")
    tf = tr_ = ts = 0.0
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"{coin:<6} no bins — re-pull per kickoff")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        mid = np.asarray(mid, float)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        flips, exit_cells, _legs = bigline_events(mid, scale=1)
        xg = np.zeros(len(mid), bool)
        for c in exit_cells:
            if c < len(xg):
                xg[c] = True
        z = np.zeros(len(mid))
        res = simulate_swing_maker(mid, z, z, buy, sell, flips, half_spread_bps=0.0,
                                   maker_fee_bps=5.5, taker_fee_bps=5.5, cover_grace=0,
                                   exit_gate=xg, fill_mode="taker")
        rflips = [(c, p_, -s) for (c, p_, s) in flips]
        rres = simulate_swing_maker(mid, z, z, buy, sell, rflips, half_spread_bps=0.0,
                                    maker_fee_bps=5.5, taker_fee_bps=5.5, cover_grace=0,
                                    exit_gate=xg, fill_mode="taker")
        dph = CAP / 1e4 / hrs
        sz_tot, msz = _sized(res, mid, buy, sell)
        tf += res.total_net_bps * dph; tr_ += rres.total_net_bps * dph; ts += sz_tot * dph
        print(f"{coin:<6}{res.n_legs:>6}{res.net_per_leg_bps:>9.1f}{res.total_net_bps:>+9.0f}"
              f"{res.total_net_bps*dph:>+8.2f} | {rres.total_net_bps*dph:>+9.2f} | "
              f"{sz_tot*dph:>+11.2f}{msz:>5.2f}")
    print(f"{'TOTAL':<6}{'':>6}{'':>9}{'':>9}{tf:>+8.2f} | {tr_:>+9.2f} | {ts:>+11.2f}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "books"):
        run_books()
    if which in ("all", "bins"):
        run_bins()
