"""
_maker_fill_model.py — NEXT #3: net-of-rebate maker edge from the depth-imbalance signal.

Builds the S42 signal (depth_imb K=5) + the QuietFloor gate, then runs the portable
maker/queue simulator (odcore.maker_book) on a HELD-OUT slice with honest queue position
and adverse selection. Question: can the 63%-next-cell directional signal be monetized as
a MAKER (post the favorable side, earn rebate + half-spread) once the taker fee floor is
removed?

Arms (all on the held-out test slice; QuietFloor fit on the train slice's quiet cells):
  base_bid / base_ask  : unconditional maker, post that side every cell (adverse-selection
                         benchmark — what making costs with NO signal).
  signal_fav           : post only the side depth_imb favors (sign of level), every cell.
  signal_anti          : post the side depth_imb DISfavors (internal control — if the signal
                         is a real adverse-selection filter, fav per-fill >> anti per-fill).
  gate1.5 / gate2.0    : post the favorable side ONLY when the quiet-floor gate is open
                         (a shock breaks the floor); stand aside otherwise (the deploy form).

Reported per arm: fill rate, gross per fill (bps; = half-spread + signed drift), the adverse
drift term, the breakeven per-leg fee (>0 = tolerates a fee; <0 = needs a rebate), and net at
a sweep of realistic maker fees/rebates.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import to_grid, load_book  # noqa: F401  (build_channels uses them)
from odcore import quiet_floor
from odcore.maker_book import simulate_arm

K = 5
FLOW_W = 20
TRAIN_FRAC = 0.6
FILL_WINDOW = 10            # 1.0 s to get filled through the queue
HOLDS = [1, 5, 10, 20]     # cells held after fill (0.1 s .. 2.0 s)
QUEUE_FRAC = 1.0           # join the BACK of the displayed best-level queue (conservative)
FEE_GRID = [40.0, 10.0, 2.5, 0.0, -1.0, -2.5]   # per-leg maker fee bps (negative = rebate)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/od_book.jsonl.gz"
    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]
    mid = g["mid"]
    bb = g["bidK"][1]                # best-bid size (queue ahead for a bid)
    ba = g["askK"][1]                # best-ask size (queue ahead for an ask)
    buy, sell = g["buy"], g["sell"]
    n = len(mid)
    hs_bps = median_spread_bps(path) / 2.0     # half the median top-of-book spread
    quiet = (buy + sell) <= 0

    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    print(f"# book: {n:,} cells; half-spread={hs_bps:.4f} bps; "
          f"QuietFloor phi={qf.phi:.3f} sigma={qf.sigma:.4f} r2_quiet={qf.r2_quiet:.3f}")

    cut = int(n * TRAIN_FRAC)
    te = slice(cut, n)                # held-out test slice (causal: signal at t uses imb[t])
    sign = np.sign(imb)
    g15 = qf.gated_signal(imb, k=1.5)
    g20 = qf.gated_signal(imb, k=2.0)

    def sub(a):
        return np.asarray(a)[te]

    mid_t, bb_t, ba_t, buy_t, sell_t = sub(mid), sub(bb), sub(ba), sub(buy), sub(sell)
    base_bid = np.ones_like(mid_t)
    base_ask = -np.ones_like(mid_t)
    fav = sub(sign)
    anti = -sub(sign)
    gate15 = sub(g15)
    gate20 = sub(g20)

    arms = {"base_bid": base_bid, "base_ask": base_ask, "signal_fav": fav,
            "signal_anti": anti, "gate1.5": gate15, "gate2.0": gate20}

    out = {"path": path, "n": int(n), "K": K, "half_spread_bps": hs_bps,
           "fill_window": FILL_WINDOW, "queue_frac": QUEUE_FRAC,
           "quietfloor": {"phi": qf.phi, "sigma": qf.sigma, "r2_quiet": qf.r2_quiet},
           "by_hold": {}}

    for hold in HOLDS:
        rows = {}
        for name, side in arms.items():
            r = simulate_arm(side, mid_t, bb_t, ba_t, buy_t, sell_t,
                             fill_window=FILL_WINDOW, hold=hold, queue_frac=QUEUE_FRAC,
                             half_spread_bps=hs_bps, fee_bps=0.0, arm=name)
            d = r.as_dict()
            d["net_at_fee"] = {f: r.gross_per_fill_bps - f for f in FEE_GRID}
            rows[name] = d
        out["by_hold"][hold] = rows
        print(f"\n=== hold={hold} cells ({hold*0.1:.1f}s), fill_window={FILL_WINDOW} "
              f"({FILL_WINDOW*0.1:.1f}s) ===")
        print(f"  {'arm':<12}{'quotes':>9}{'fills':>9}{'fillrate':>9}"
              f"{'gross/fill':>11}{'drift':>9}{'breakeven_fee':>14}")
        for name in arms:
            d = rows[name]
            print(f"  {name:<12}{d['n_quotes']:>9}{d['n_fills']:>9}{d['fill_rate']:>9.3f}"
                  f"{d['gross_per_fill_bps']:>11.4f}{d['adverse_drift_bps']:>9.4f}"
                  f"{d['breakeven_fee_bps']:>14.4f}")

    json.dump(json.loads(json.dumps(out, default=float)),
              open("_maker_fill_model_results.json", "w"), indent=2)
    print("\n# wrote _maker_fill_model_results.json")
    # headline reading
    h = 5 if 5 in out["by_hold"] else HOLDS[0]
    rb = out["by_hold"][h]
    fav_g = rb["signal_fav"]["gross_per_fill_bps"]
    anti_g = rb["signal_anti"]["gross_per_fill_bps"]
    base_g = (rb["base_bid"]["gross_per_fill_bps"] + rb["base_ask"]["gross_per_fill_bps"]) / 2
    print(f"\n# READ (hold={h}): gross/fill  fav={fav_g:+.4f}  anti={anti_g:+.4f}  "
          f"base={base_g:+.4f} bps  -> signal lift over base = {fav_g-base_g:+.4f} bps/fill; "
          f"fav-vs-anti = {fav_g-anti_g:+.4f} bps/fill")


if __name__ == "__main__":
    main()
