"""grade_coin_kraken.py — per-cell S54 gate for a NEW Kraken coin (S67, the candidate-seating harness).

Given a coin's Kraken TAPE (realbins/<coin>_kraken_bins.json), decide whether it deserves a cell and
with what config, using the SAME per-cell law the 5 majors were graded under (S54/S63/S65): the
DECISION runs through the LIVE path (odcore.flip_detector + odcore.platform.run_stream, front-of-line,
kr_mk0) — this script only ADDS the grading orchestration (forward-vs-reversed, a circular-shift null
FLOOR, per-window sign consistency, a REV sweep). It never re-implements the executor/fill/fees.

THE GATE (a coin SEATS only if all hold):
  1. forward $/hr > 0 and clearly beats reversed (direction premium is real, not a coin-flip).
  2. reversed <= ~0 (the wrong sign loses — the S54 reversed-below-floor control).
  3. forward > the CIRCULAR-SHIFT NULL floor (flow-lean flips must TIME the real price turns; random-
     timed flips of the same flow/price distributions should collapse to ~0 at kr_mk0 where there is no
     rebate volume-paycheck).
  4. per-window sign consistency (majority of sub-windows positive — not one lucky stretch).
Then a REV sweep picks the per-coin swing-floor that MAXIMISES $/hr (keep fine churn where net-positive,
coarsen where negative — the S65 revsweep rule). Output = a recommended CellConfig(side, rev) + verdict.

⚠ PROVISIONAL like every tape number (front-of-line fill, no book depth; capacity graded separately by
the capital model). This grades the SIGNAL (is the edge real + which way); capacity/fill is the pool's job.

Usage:
  python scripts/grade_coin_kraken.py                     # default: ada sui ltc avax
  python scripts/grade_coin_kraken.py ada ltc --nshift 25
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.io import load_bins                                          # noqa: E402
from odcore.flip_detector import lean_series, detect_flips              # noqa: E402
from odcore.platform import run_stream, WFLIP                           # noqa: E402  (live path)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REALBINS = os.path.join(ROOT, "realbins")
CAP = 5000.0
MAKER_FEE, TAKER_FEE = 0.0, 5.0          # kr_mk0
REV_GRID = [0.10, 0.13, 0.20, 0.30]
NWIN = 7                                  # sub-windows for the sign-consistency read


def load_coin(coin):
    p = os.path.join(REALBINS, f"{coin}_kraken_bins.json")
    if not os.path.exists(p):
        return None
    s = load_bins(p)
    mid = np.asarray(s.mid, float)
    hs = float(np.median((s.spread[mid > 0] / mid[mid > 0]) / 2.0) * 1e4) if np.any(mid > 0) else 0.0
    return dict(mid=mid, buy=np.asarray(s.buy, float), sell=np.asarray(s.sell, float),
                hs=hs, n=len(mid), hours=len(mid) / 3600.0)


def run_side(bk, side, rev):
    """LIVE stack, front-of-line, base flow-lean (no early-arm/bail — signal grade). Returns SwingResult."""
    flips, _ = detect_flips(lean_series(bk["buy"], bk["sell"], WFLIP), rev)
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    res, _ = run_stream(bk["mid"], bk["buy"], bk["sell"], flips, half_spread_bps=bk["hs"],
                        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, grace=300,
                        fill_model="front", close_improve_bps=0.5)
    return res


def dph(res, hours):
    return res.total_net_bps / 1e4 * CAP / hours if hours else 0.0


def shift_null(bk, side, rev, nshift):
    """Circular-shift the FLOW (buy/sell) vs price by random offsets -> flips fire at times uncorrelated
    with the real turns. If the edge is real timing, forward >> this null; at kr_mk0 the null ~ 0."""
    n = bk["n"]
    rng = np.random.default_rng(12345)
    out = []
    for _ in range(nshift):
        k = int(rng.integers(n // 10, n - n // 10))
        b2 = np.roll(bk["buy"], k); s2 = np.roll(bk["sell"], k)
        flips, _ = detect_flips(lean_series(b2, s2, WFLIP), rev)
        if side < 0:
            flips = [(c, p, -s) for (c, p, s) in flips]
        res, _ = run_stream(bk["mid"], b2, s2, flips, half_spread_bps=bk["hs"],
                            maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, grace=300,
                            fill_model="front", close_improve_bps=0.5)
        out.append(dph(res, bk["hours"]))
    return np.asarray(out)


def per_window(bk, side, rev, nwin=NWIN):
    """$/hr in each of nwin equal sub-windows (sign-consistency read)."""
    n = bk["n"]; edges = np.linspace(0, n, nwin + 1).astype(int)
    res = run_side(bk, side, rev)
    dphs = []
    for i in range(nwin):
        lo, hi = edges[i], edges[i + 1]
        pnl = sum(float(l.net_bps) for l in res.legs if lo <= int(l.close_idx) < hi)
        hrs = (hi - lo) / 3600.0
        dphs.append(pnl / 1e4 * CAP / hrs if hrs else 0.0)
    return np.asarray(dphs)


def grade(coin, nshift):
    bk = load_coin(coin)
    if bk is None:
        return dict(coin=coin, verdict="NO TAPE")
    # stage 1: side x rev sweep at base stack -> best (side, rev) by $/hr
    grid = {}
    for side in (+1, -1):
        for rev in REV_GRID:
            grid[(side, rev)] = dph(run_side(bk, side, rev), bk["hours"])
    (best_side, best_rev), best_dph = max(grid.items(), key=lambda kv: kv[1])
    rev_dph = max(grid[(-best_side, r)] for r in REV_GRID)          # best the WRONG side can do
    # stage 2: gate the winner
    nulld = shift_null(bk, best_side, best_rev, nshift)
    floor = float(nulld.mean() + 2 * nulld.std())
    wins = per_window(bk, best_side, best_rev)
    frac_pos = float(np.mean(wins > 0))
    seat = (best_dph > 0) and (best_dph > rev_dph) and (rev_dph <= max(0.5, 0.25 * best_dph)) \
        and (best_dph > floor) and (frac_pos >= 0.6)
    verdict = "SEAT" if seat else ("MARGINAL" if best_dph > 0 and best_dph > rev_dph else "REJECT")
    return dict(coin=coin, hours=bk["hours"], n=bk["n"], best_side=best_side, best_rev=best_rev,
                best_dph=best_dph, rev_dph=rev_dph, null_mean=float(nulld.mean()),
                null_floor=floor, frac_pos=frac_pos, wins=wins, grid=grid, verdict=verdict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coins", nargs="*", default=["ada", "sui", "ltc", "avax"])
    ap.add_argument("--nshift", type=int, default=20, help="circular-shift null replicas")
    args = ap.parse_args()
    coins = args.coins or ["ada", "sui", "ltc", "avax"]

    print("=== KRAKEN NEW-COIN GRADE (S54 gate, front-of-line, kr_mk0) — via LIVE run_stream ===")
    print(f"  {'coin':6}{'hrs':>6}{'side':>6}{'rev':>6}{'$/hr':>9}{'rev$/hr':>9}{'null':>8}{'floor':>8}"
          f"{'win-wins':>9}  verdict")
    rows = []
    for c in coins:
        r = grade(c, args.nshift)
        rows.append(r)
        if r["verdict"] == "NO TAPE":
            print(f"  {c:6}  (no realbins tape)"); continue
        sd = "FWD" if r["best_side"] > 0 else "REV"
        print(f"  {c:6}{r['hours']:>6.0f}{sd:>6}{r['best_rev']:>6.2f}{r['best_dph']:>+9.2f}"
              f"{r['rev_dph']:>+9.2f}{r['null_mean']:>+8.2f}{r['null_floor']:>+8.2f}"
              f"{100*r['frac_pos']:>7.0f}%   {r['verdict']}")
    print("\n  gate: $/hr>0, beats reversed, reversed<=~0, > shift-null floor, >=60% sub-windows positive.")
    print("  SEAT -> add as a candidate CellConfig(side, rev); MARGINAL -> hold; REJECT -> drop that coin.")
    # emit CellConfig lines for the SEATs
    seats = [r for r in rows if r["verdict"] == "SEAT"]
    if seats:
        print("\n  --- recommended candidate CellConfigs (seat these) ---")
        for r in seats:
            print(f'    CellConfig("{r["coin"]}", venue="kraken", side={r["best_side"]:+d}, '
                  f'rev={r["best_rev"]}, grace=300, improve=0.5),')
    return rows


if __name__ == "__main__":
    main()
