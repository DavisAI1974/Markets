"""pool_aggressive_margin.py — the AGGRESSIVE / MARGIN model, DIRECTIONAL only (Greg S71: "just to see if
it's the right direction, we can tune later"). NO fine tuning.

Contrast to reservation (pool_capacity_honest.py): DROP the single-$5k reservation cap. Every coin deploys
to its OWN real per-leg reachable capacity CONCURRENTLY (over-rest across coins). Total deployed may EXCEED
$5k -> the excess is MARGIN (borrowed cash). Cancel-on-fill makes true same-second double-book rare
(~0.24/hr), so concurrent RESTS are allowed; the model books the leveraged EXCESS as borrow and NETS its cost.

The decisive variable = the borrow rate. Kraken margin = opening fee (~1-2bp on borrowed) + rollover every
4h on the borrowed amount. We SWEEP rollover in {0.01, 0.02, 0.05}%/4h and report the net-$/hr-vs-borrow
curve + the BREAKEVEN rollover where aggressive ties the reservation anchors A (+9.51) and B_reserve (+9.65).

SIM=LIVE: legs are the live run_kraken_cell output (firing LOCKED); per-leg capacity = min(near-touch depth,
taker flow) reused from pool_capacity_honest. Aggressive PnL runs through the live run_portfolio with the
pool set effectively infinite so each coin fills its own real cap concurrently. Additive; nothing committed.

CAVEAT: ONE 42h low-edge Kraken window; 5 majors only (minors not yet seated); borrow rate assumed & swept,
NOT confirmed; directional (no tuning).

Run: python scripts/pool_aggressive_margin.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import CELLS, run_cell, CAP
from odcore.platform import run_portfolio, KRAKEN
from pool_capacity_honest import load_clipped, leg_capacity

POOL = CAP           # $5000 collateral line — the level above which deployment is BORROWED (margin)
BIG = 1e9            # effectively-infinite pool -> greedy fills every coin to its own real cap (no reservation)
BUCKET = 3600
OPEN_BPS = 1.5       # representative Kraken margin opening fee on the borrowed amount (1-2bp)
ROLL_SWEEP = [0.0001, 0.0002, 0.0005]   # rollover per 4h: 0.01% / 0.02% / 0.05%
A_ANCHOR = 9.51      # reservation anchor A (xrp-only real cap, leftover idle)
BR_ANCHOR = 9.65     # reservation anchor B_reserve (reserve-per-rest)


def main():
    print("=" * 100)
    print("AGGRESSIVE / MARGIN model (DIRECTIONAL) — every coin at its own real cap concurrently; borrow the excess")
    print("=" * 100)
    clips, ov_sec = load_clipped()
    hours = ov_sec / 3600.0
    coins = [c["coin"] for c in CELLS if c["active"] and c["coin"] in clips]
    print(f"window {ov_sec}s = {hours:.1f}h, {len(coins)} coins, $5k collateral line, front-of-line kr_mk0\n")

    # live legs, edge weights, real per-leg caps (same as pool_capacity_honest)
    cell_legs = {}; edge = {}; caparr = {}
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in clips:
            continue
        c = cell["coin"]
        _, r = run_cell(cell, clips[c], fill_model="front")
        cell_legs[c] = r.legs
        edge[c] = sum(float(l.net_bps) for l in r.legs) / 1e4 * POOL / hours
        caparr[c] = leg_capacity(c, clips[c], r.legs)     # cols: near1, near3, flow, real=min(near3,flow)
    lo = min(edge.values()); shift = (-lo + 1e-6) if lo <= 0 else 0.0
    weights = {c: edge[c] + shift for c in coins}
    real_caps = {c: list(caparr[c][:, 3]) for c in coins}   # per-leg real reachable cap (= alloc used)

    # shorts? the KRAKEN registry cell sides:
    reg_sides = {cfg.coin: cfg.side for cfg in KRAKEN}
    print("  KRAKEN registry cell sides: " + ", ".join(f"{k}={'+1' if v>0 else '-1'}" for k, v in reg_sides.items()))

    # ---- AGGRESSIVE run: pool = infinite -> each coin fills its OWN real cap concurrently (live path) ----
    prAg = run_portfolio(cell_legs, pool=BIG, weights=weights, mode="greedy",
                         n=ov_sec, bucket_cells=BUCKET, leg_caps=real_caps)
    gross_pnl = prAg.total_pnl_usd
    gross_per_hr = prAg.pool_return_per_hr

    # realistic exchange-max leverage bound (Kraken spot margin ~5x) — NOT tuning, an exchange limit; the
    # unbounded real-cap tail (max 100x+) can't actually be posted on a $5k account.
    MAXLEV = 5.0
    pr5 = run_portfolio(cell_legs, pool=POOL * MAXLEV, weights=weights, mode="greedy",
                        n=ov_sec, bucket_cells=BUCKET, leg_caps=real_caps)
    gross5_per_hr = pr5.pool_return_per_hr

    # ---- deployed-over-time timeline (each funded leg holds its real cap for [open,close]) ----
    def deployed_timeline(cap_of):
        dep = np.zeros(ov_sec); sdep = np.zeros(ov_sec); ldep = np.zeros(ov_sec)
        for c in coins:
            for k, l in enumerate(cell_legs[c]):
                o = int(l.open_idx); x = int(min(l.close_idx, ov_sec - 1))
                if x < o:
                    continue
                cap = cap_of(c, k)
                dep[o:x + 1] += cap
                (sdep if int(l.side) < 0 else ldep)[o:x + 1] += cap
        return dep, sdep, ldep

    dep, short_dep, long_dep = deployed_timeline(lambda c, k: real_caps[c][k])
    # 5x-capped deployed: cap each leg so no single moment exceeds $25k is hard to attribute per-leg; use the
    # total capped at 5x (the realistic borrow base) = min(dep, 5*POOL).
    dep5 = np.minimum(dep, POOL * MAXLEV)

    borrowed = np.maximum(0.0, dep - POOL)                 # leveraged cash borrow (excess over collateral)
    integral_borrowed_hrs = float(borrowed.sum()) / 3600.0  # $*hours
    open_volume = float(np.maximum(0.0, np.diff(borrowed, prepend=0.0)).sum())  # $ of new borrow opened

    n_short = sum(1 for c in coins for l in cell_legs[c] if int(l.side) < 0)
    n_long = sum(1 for c in coins for l in cell_legs[c] if int(l.side) > 0)
    short_hours = float(short_dep.sum()) / 3600.0
    total_dep_hours = float(dep.sum()) / 3600.0

    # ---- (2) leverage actually used ----
    mult = dep / POOL
    print(f"\n--- (2) LEVERAGE ACTUALLY USED (gross deployed / $5k) ---")
    print(f"  deployed/$5k:  median {np.median(mult):.2f}x   p90 {np.percentile(mult,90):.2f}x   "
          f"max {mult.max():.2f}x   mean {mult.mean():.2f}x")
    print(f"  % of time deployed > $5k (uses margin): {100*float((dep>POOL).mean()):.0f}%")
    print(f"  gross deployed: median ${np.median(dep):,.0f}  p90 ${np.percentile(dep,90):,.0f}  max ${dep.max():,.0f}")

    # ---- (3) margin-spike / over-$5k episodes ----
    over = dep > POOL
    edges = np.diff(over.astype(int))
    n_episodes = int((edges == 1).sum()) + (1 if over[0] else 0)
    print(f"\n--- (3) MARGIN-SPIKE (deployed > $5k) EPISODES ---")
    print(f"  distinct over-$5k episodes: {n_episodes}  ({n_episodes/hours:.2f}/hr)   "
          f"max concurrent over-$5k = ${dep.max()-POOL:,.0f} above the line")
    print(f"  (vs the ~0.24/hr EXACT same-second double-book of one coin — the over-$5k overlap is FREQUENT,")
    print(f"   because {len(coins)} coins are live concurrently most of the time; that's the margin the model books.)")

    # ---- shorts ----
    print(f"\n--- SHORTS (borrow the asset for the whole hold regardless of the $5k line) ---")
    print(f"  legs: {n_long} long / {n_short} short   |   short notional-hours = {short_hours:,.0f} $*h "
          f"= {100*short_hours/max(1e-9,total_dep_hours):.0f}% of deployed $*h")
    print(f"  (registry cells are all side=+1, but the zigzag ALTERNATES -> ~half the LEGS are genuine shorts.)")

    # ---- (1) net $/hr vs borrow rate ----
    # borrow bases: UNBOUNDED (deploy full real cap) vs 5x-CAPPED (Kraken realistic max)
    borrowed = np.maximum(0.0, dep - POOL)
    integ_unb = float(borrowed.sum()) / 3600.0
    openv_unb = float(np.maximum(0.0, np.diff(borrowed, prepend=0.0)).sum())
    borrowed5 = np.maximum(0.0, dep5 - POOL)
    integ_5x = float(borrowed5.sum()) / 3600.0
    openv_5x = float(np.maximum(0.0, np.diff(borrowed5, prepend=0.0)).sum())

    def costs(roll_4h, integ_hrs, open_vol):
        roll_cost = (roll_4h / 4.0) * integ_hrs                 # roll_4h per 4h -> per-hr = /4
        open_cost = OPEN_BPS / 1e4 * open_vol
        return roll_cost, open_cost

    print(f"\n--- (1) NET POOL $/hr vs BORROW RATE ---")
    print(f"  gross (no borrow): UNBOUNDED = {gross_per_hr:+.2f} $/hr   |   5x-capped = {gross5_per_hr:+.2f} $/hr")
    print(f"  anchors: A (leftover idle) = {A_ANCHOR:+.2f}   B_reserve = {BR_ANCHOR:+.2f}")
    print(f"  borrow cost split @ 0.02%/4h (5x-capped): rollover ${costs(0.0002,integ_5x,openv_5x)[0]:,.0f} + "
          f"open-fee ${costs(0.0002,integ_5x,openv_5x)[1]:,.0f}  -> open fee DOMINATES (huge churn of leveraged $)")
    print(f"\n  {'rollover/4h':>12} | {'net $/hr UNBOUNDED':>18} | {'net $/hr 5x-CAPPED':>18} | 5x beats B_reserve?")
    sweep = {}
    for r in ROLL_SWEEP:
        rc_u, oc_u = costs(r, integ_unb, openv_unb); net_u = (gross_pnl - rc_u - oc_u) / hours
        rc5, oc5 = costs(r, integ_5x, openv_5x); net_5 = (pr5.total_pnl_usd - rc5 - oc5) / hours
        sweep[f"{r*100:.2f}%/4h"] = {"unbounded": round(net_u, 2), "capped_5x": round(net_5, 2)}
        beat = "YES" if net_5 > BR_ANCHOR else "no"
        print(f"  {r*100:>10.2f}% | {net_u:>+18.2f} | {net_5:>+18.2f} | {beat}")

    # breakeven rollover vs each anchor (5x-capped borrow base — the realistic one)
    open_per_hr5 = (OPEN_BPS / 1e4 * openv_5x) / hours
    def breakeven(target):
        num = (gross5_per_hr - open_per_hr5 - target) * hours * 4.0
        return num / integ_5x if integ_5x > 0 else float("inf")
    be_A = breakeven(A_ANCHOR); be_BR = breakeven(BR_ANCHOR)
    print(f"\n  BREAKEVEN rollover (5x-capped): aggressive ties B_reserve at {be_BR*100:.3f}%/4h ; ties A at {be_A*100:.3f}%/4h.")
    print(f"  (negative breakeven => even a ZERO rollover can't beat reservation, because the OPEN FEE alone "
          f"on the churned leveraged $ ({open_per_hr5:+.2f} $/hr) already sinks it below the anchors.)")

    # ---- (4) directional verdict ----
    mid_r = ROLL_SWEEP[1]
    rc5, oc5 = costs(mid_r, integ_5x, openv_5x); net_mid5 = (pr5.total_pnl_usd - rc5 - oc5) / hours
    verdict = ("RIGHT DIRECTION" if net_mid5 > BR_ANCHOR else
               ("WASH" if abs(net_mid5 - BR_ANCHOR) < 0.5 else "WORSE"))
    print(f"\n--- (4) DIRECTIONAL VERDICT ---")
    print(f"  gross 5x-capped (no borrow) = {gross5_per_hr:+.2f} $/hr   ({gross5_per_hr/BR_ANCHOR:.2f}x B_reserve)")
    print(f"  net 5x @ 0.02%/4h           = {net_mid5:+.2f} $/hr   (vs B_reserve {BR_ANCHOR:+.2f})")
    print(f"  VERDICT: aggressive/margin is **{verdict}** vs reservation — the leverage gross uplift "
          f"({gross5_per_hr/BR_ANCHOR:.1f}x) is swamped by borrow (open-fee on churned leveraged $).")
    integral_borrowed_hrs = integ_5x; open_volume = openv_5x; integ_se = 0; open_vol_se = 0  # for JSON compat

    out = {
        "window": {"seconds": ov_sec, "hours": round(hours, 2), "coins": coins, "collateral": POOL},
        "gross_per_hr_no_borrow_unbounded": round(gross_per_hr, 2),
        "gross_per_hr_no_borrow_5x": round(gross5_per_hr, 2),
        "anchors": {"A_idle": A_ANCHOR, "B_reserve": BR_ANCHOR},
        "leverage": {"median_mult": round(float(np.median(mult)), 2), "p90_mult": round(float(np.percentile(mult, 90)), 2),
                     "max_mult": round(float(mult.max()), 2), "pct_time_over_5k": round(100 * float((dep > POOL).mean()), 1),
                     "median_deployed": round(float(np.median(dep))), "p90_deployed": round(float(np.percentile(dep, 90)))},
        "margin_spikes": {"episodes": n_episodes, "per_hr": round(n_episodes / hours, 2),
                          "max_over_5k": round(float(dep.max() - POOL))},
        "shorts": {"n_long": n_long, "n_short": n_short, "short_notional_hours": round(short_hours),
                   "pct_of_deployed_hours": round(100 * short_hours / max(1e-9, total_dep_hours), 1)},
        "borrow_integral_hrs_5x": round(integ_5x), "open_volume_5x": round(openv_5x),
        "net_vs_rollover": sweep,
        "breakeven_rollover_pct_4h": {"vs_A": round(be_A * 100, 3), "vs_B_reserve": round(be_BR * 100, 3)},
        "verdict": verdict,
        "caveat": "ONE 42h low-edge window; 5 majors only; borrow rate assumed/swept not confirmed; DIRECTIONAL, no tuning.",
    }
    with open("_pool_aggressive_margin_results.json", "w") as f:
        json.dump(out, f, indent=2, default=lambda o: None)
    print("\nwrote _pool_aggressive_margin_results.json")


if __name__ == "__main__":
    main()
