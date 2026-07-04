"""_s62_3piece_harness.py — S62 rebuild of Greg's 3-PIECE strategy rig (R11).

The 3-piece rule at the FIRST-UNDERWATER moment (leg reaches -X bp):
  (A) winner-dipping        -> HOLD   (ride the leg to its natural exit)
  (B) loser + weak move     -> FLATTEN small (exit now at -X)
  (C) loser + strong move   -> FLIP and ride (reverse at -X, ride to the leg's exit)

This rig reconstructs the exact leg population of the promoted mid-band machine
(odcore.entry_coinbase.armed_midband_flips, naive k0) on the 30d Binance-spot bins tape
(the same `entry_idx`-indexed series the S60 leg dumps used), walks each leg's path to the
-X decision cell, and grades the three actions per leg.

Grading (Greg's scoreboard): net $/hr @ $5k (CAP), leads; per-leg bp = diagnostics.
Baseline = HOLD-all (the machine's own P&L). ORACLE = best action per leg (the ceiling).
Winner-preservation = of the winners, how many the policy leaves as HOLD.

Milestone 1 (this file, first pass): reproduce the SOL anchors — baseline +1.77 $/hr,
ORACLE +26.09 $/hr, 508/508 winners kept. Convention-locking pass; the causal classifier
(trend-efficiency driver, R11's +1.89) is added next once these anchors land.

Fee frame = Coinbase; Greg handles the fee tier -> default grade at fee=0 (R11). The FLIP is
a taker cross; `--flip-cost` parametrizes it (0 for the fee=0 reproduction).

Usage:
    python scripts/_s62_3piece_harness.py --coin sol --theta 100 --x 20
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS                       # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

CAP = 5000.0            # capital clip ($) — matches _s58_piece1_entry.net_dollars_hr
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
SYM = dict(COINS)       # coin -> SYMBOL


def build_legs(mid, theta, c=0.5):
    """Regenerate the machine's legs. Returns list of (ci, xi, side)."""
    flips = armed_midband_flips(mid, theta, c)
    legs = []
    for k in range(len(flips) - 1):        # last flip has no exit (score uses ci[:-1])
        ci, _pivot, side = flips[k]
        xi = flips[k + 1][0]
        if xi > ci:
            legs.append((int(ci), int(xi), int(side)))
    return legs


def leg_actions(mid, ci, xi, side, x_bp, flip_cost):
    """Per-leg outcomes (bp) for HOLD/FLATTEN/FLIP + the decision-cell offset.

    HOLD    = gross to the natural exit.
    FLATTEN = exit at the first -x_bp cell (its realized signed excursion).
    FLIP    = reverse at the decision cell, ride to xi = -(gross - r_dec) - flip_cost.
    Legs that never reach -x_bp: only HOLD (no decision cell -> t_dec = None).
    """
    ep = mid[ci]
    seg = mid[ci:xi + 1]
    r = side * (np.log(seg / ep)) * 1e4          # signed excursion path, bp
    gross = float(r[-1])
    # first underwater crossing of -x_bp
    under = np.where(r <= -x_bp)[0]
    if len(under) == 0:
        return dict(gross=gross, t_dec=None, hold=gross, flatten=None, flip=None,
                    winner=gross > 0.0)
    t_dec = int(under[0])
    r_dec = float(r[t_dec])
    hold = gross
    flatten = r_dec
    flip = -(gross - r_dec) - flip_cost
    return dict(gross=gross, t_dec=t_dec, hold=hold, flatten=flatten, flip=flip,
                winner=gross > 0.0)


def grade(legs, acts, hrs, policy, fee_bp=0.0):
    """policy(a) -> 'hold'|'flatten'|'flip' per leg action-dict. Returns $/hr + stats."""
    dollars = 0.0
    winners = winners_kept = 0
    n_flip = n_flat = n_hold = 0
    for a in acts:
        choice = policy(a)
        pnl = a[choice]
        if pnl is None:               # action unavailable (no decision cell) -> HOLD
            choice, pnl = "hold", a["hold"]
        # FLIP pays the taker fee on both the flip open and its close; HOLD/FLATTEN one leg
        fee = (2.0 * fee_bp) if choice == "flip" else (2.0 * fee_bp)
        dollars += CAP * (pnl - fee) / 1e4
        n_flip += choice == "flip"; n_flat += choice == "flatten"; n_hold += choice == "hold"
        if a["winner"]:
            winners += 1
            winners_kept += choice == "hold"
    return dict(dph=dollars / hrs, winners=winners, winners_kept=winners_kept,
                n_flip=n_flip, n_flat=n_flat, n_hold=n_hold)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="sol")
    ap.add_argument("--theta", type=float, default=100.0)
    ap.add_argument("--x", type=float, default=20.0, help="first-underwater trigger (bp)")
    ap.add_argument("--flip-cost", type=float, default=22.0,
                    help="taker cost of a flip (bp); 22 = R11-calibrated SOL taker cross "
                         "(reproduces oracle +26.09 / flatten-only +13.9); 0 = frictionless ceiling")
    ap.add_argument("--fee-bp", type=float, default=0.0)
    args = ap.parse_args()

    sym = SYM[args.coin]
    path = os.path.join(BINS_DIR, f"{sym}_30d_bins.json")
    if not os.path.exists(path):
        sys.exit(f"[{args.coin}] bins missing at {path}")
    mid, buy, sell, cover, hrs = load_bins(path)
    mid = np.asarray(mid, float)
    print(f"[{args.coin}] {sym}  cells={len(mid)}  hrs={hrs:.1f}  cover={cover:.3f}")

    legs = build_legs(mid, args.theta)
    acts = [leg_actions(mid, ci, xi, side, args.x, args.flip_cost) for ci, xi, side in legs]
    n = len(acts)
    reach = sum(1 for a in acts if a["t_dec"] is not None)
    winners = sum(1 for a in acts if a["winner"])
    print(f"  legs={n}  reach -{args.x:.0f}bp={reach}  winners={winners}  "
          f"losers={n - winners}")

    base = grade(legs, acts, hrs, lambda a: "hold", args.fee_bp)
    oracle = grade(legs, acts, hrs,
                   lambda a: max(("hold", "flatten", "flip"),
                                 key=lambda k: (a[k] if a[k] is not None else -1e18)),
                   args.fee_bp)
    print(f"\n  BASELINE (hold-all):   {base['dph']:+.2f} $/hr")
    print(f"  ORACLE (best/leg):     {oracle['dph']:+.2f} $/hr  "
          f"winners_kept={oracle['winners_kept']}/{oracle['winners']}  "
          f"(flip={oracle['n_flip']} flat={oracle['n_flat']} hold={oracle['n_hold']})")


if __name__ == "__main__":
    main()
