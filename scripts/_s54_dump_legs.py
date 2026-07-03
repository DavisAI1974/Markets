"""_s54_dump_legs.py — dump PER-LEG trade tables from the S54 runs for Greg's walkthrough (S55).

Three tables, CSV (one row per leg, ISO UTC timestamps):
  _s54_legs_bigline_coinbase.csv   adaptive big line f0.25/w4h on the 5 Coinbase book windows
                                   (the one-window +$1-4/hr result)
  _s54_legs_bigline_bybit30d.csv   same engine on the 30d x 5-coin Bybit dump bins (the failed gate)
  _s54_legs_zigzag_bybit30d.csv    scaled-up causal zigzag flip at theta 100/150 on the same bins
                                   (the S55 two-scale baseline)
Columns: cell, engine, side, entry_utc, exit_utc, hold_h, entry_px, exit_px, gross_bps,
net_bps_taker, redraws, forced. Fees: Coinbase taker 5bp/side (rt10), Bybit 5.5 (rt11).
Needs books in /tmp/<coin>_..._book.jsonl.gz and bins in /tmp/backfill/ (see S55 kickoff to re-pull).
"""
import csv
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                      # noqa: E402
from _liquidity_dive import build_channels              # noqa: E402
from _capacity_model import FLOW_W                      # noqa: E402
from _s52_accum_vs_oneshot import _price_zigzag         # noqa: E402
from _s54_bigline_probe import CELLS, DEC, FIXED_AD     # noqa: E402
from _s54_backfill_sweep import load_bins, COINS        # noqa: E402
from odcore.swing_bigline import run_bigline_adaptive   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _iso(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "engine", "side", "entry_utc", "exit_utc", "hold_h",
                    "entry_px", "exit_px", "gross_bps", "net_bps_taker", "redraws", "forced"])
        w.writerows(rows)
    print(f"-> {path} ({len(rows)} legs)")


def bigline_rows(cell, engine, mid, t0, cell_s, rt, legs):
    out = []
    for l in legs:
        out.append([cell, engine, "LONG" if l.side > 0 else "SHORT",
                    _iso(t0 + l.entry_i * cell_s), _iso(t0 + l.exit_i * cell_s),
                    round(l.hold_cells * cell_s / 3600.0, 2),
                    round(l.entry_px, 6), round(l.exit_px, 6),
                    round(l.gross_bps, 1), round(l.gross_bps - rt, 1),
                    l.n_redraws, int(l.forced)])
    return out


def main():
    # 1. Coinbase books, adaptive big line
    rows = []
    for (cell, path, K, tk) in CELLS:
        if not os.path.exists(path):
            continue
        raw = load_book(path)
        ch, g = build_channels(path, K, FLOW_W, raw=raw)
        mid = np.asarray(g["mid"], float)[::DEC]
        t0 = float(raw["ts"][0])
        legs = run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        rows += bigline_rows(cell, "bigline_ad", mid, t0, 1.0, 2 * tk, legs)
    _write(os.path.join(ROOT, "_s54_legs_bigline_coinbase.csv"), rows)

    # 2 + 3. Bybit 30d bins: adaptive big line + zigzag flip
    bl_rows, zz_rows = [], []
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] no bins — skipped (re-pull per kickoff)")
            continue
        mid, buy, sell, cover, hrs = load_bins(p)
        import json
        with open(p) as f:
            t0 = min(float(k) for k in json.load(f).keys())
        cellname = f"{coin}_bybit_perp"
        legs = run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        bl_rows += bigline_rows(cellname, "bigline_ad", mid, t0, 1.0, 11.0, legs)
        for th in (100.0, 150.0):
            fl = _price_zigzag(mid, th)
            for a, b in zip(fl[:-1], fl[1:]):
                ci, s, cj = int(a[0]), int(a[2]), int(b[0])
                gross = s * (mid[cj] - mid[ci]) / mid[ci] * 1e4
                zz_rows.append([cellname, f"zz{th:.0f}", "LONG" if s > 0 else "SHORT",
                                _iso(t0 + ci), _iso(t0 + cj), round((cj - ci) / 3600.0, 2),
                                round(mid[ci], 6), round(mid[cj], 6),
                                round(gross, 1), round(gross - 11.0, 1), "", ""])
    _write(os.path.join(ROOT, "_s54_legs_bigline_bybit30d.csv"), bl_rows)
    _write(os.path.join(ROOT, "_s54_legs_zigzag_bybit30d.csv"), zz_rows)


if __name__ == "__main__":
    main()
