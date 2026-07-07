"""pool_capacity_honest.py — the HONEST capacity test (Greg's correction, S71).

The prior 'concentration optimal, spreading dilutes +14.5->+6.4' was an ARTIFACT: it capped XRP BELOW
$5k (shallow depth) so forcing a spread pulled REAL dollars OUT of XRP. That is not the honest question.

The honest question: cap each coin at its REAL reachable per-leg capacity. Once XRP's capacity BINDS
(<$5k), the leftover CANNOT go into XRP — its only alternatives are IDLE ($0/hr) or a BACKUP coin
($x/hr>=0). So leftover deployed is ADDITIVE to XRP, never dilutive. This measures that.

REAL reachable per-leg capacity of a FRONT-OF-LINE maker resting over a leg = min of TWO bounds ($=size*mid):
  (a) near-touch RESTING DEPTH reachable at front-of-line (counter-side top-1..top-3 levels) — what's there.
  (b) TAKER FLOW that crosses to our resting order during the leg (counter-side per-bin taker volume over
      the leg window) — what realistically FILLS us. LONG (rest bid) is filled by taker SELLS; SHORT
      (rest ask) by taker BUYS.
  real_cap = min(a, b).

Three worlds, POOL $/hr, on IDENTICAL live legs (run_cell -> run_kraken_cell -> swing_maker; firing LOCKED):
  A) best-coin (XRP) at real cap, leftover IDLE           -> concentration, no backup.
  B) best-coin at real cap + leftover cascades to backups -> Greg's additive design (leg_caps=real caps).
  B+preempt) reactive preemption when the pool binds (built into run_portfolio, opt-in, leakage-safe).
Decompose B = XRP $/hr + leftover-coins' $/hr; show the leftover's additive contribution.

SIM=LIVE, BOOK not tape, strictly pre-entry (capacity uses only the leg's own window; no future beyond it
for sizing). Additive; nothing committed. CAVEAT: ONE 42h low-edge Kraken window = current conditions.

Run: python scripts/pool_capacity_honest.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import load_book, run_cell, CELLS, CAP
from odcore.platform import run_portfolio

POOL = CAP  # $5000
BUCKET = 3600
BEST = "xrp"   # the highest edge-per-$ coin on this window (baseline weight leader) = the "primary"


def load_clipped():
    books = {}
    for cell in CELLS:
        if cell["active"]:
            bk = load_book(cell["coin"])
            if bk is not None:
                books[cell["coin"]] = bk
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1
    clips = {}
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in books:
            continue
        c = cell["coin"]; bk = books[c]; s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        clip["bid_depth"] = {N: bk["bid_depth"][N][s:e] for N in bk["bid_depth"]}
        clip["ask_depth"] = {N: bk["ask_depth"][N][s:e] for N in bk["ask_depth"]}
        clip["hs"] = bk["hs"]
        clips[c] = clip
    return clips, ov_sec


def leg_capacity(coin, clip, legs):
    """Per-leg (a) near-touch resting depth top-1/top-3, (b) taker flow crossing during the leg, and
    real_cap = min(top-3 resting depth, flow). LONG rests bid -> filled by SELL flow / ask-side depth;
    SHORT rests ask -> filled by BUY flow / bid-side depth. All in $ (size*mid)."""
    mid = clip["mid"]; buy = clip["buy"]; sell = clip["sell"]
    a1 = clip["ask_depth"][1]; a3 = clip["ask_depth"][3]
    b1 = clip["bid_depth"][1]; b3 = clip["bid_depth"][3]
    csum_buy = np.concatenate([[0.0], np.cumsum(buy)])
    csum_sell = np.concatenate([[0.0], np.cumsum(sell)])
    rows = []
    for l in legs:
        o = int(l.open_idx); x = int(min(l.close_idx, len(mid) - 1))
        if x < o:
            continue
        long = int(l.side) > 0
        near1 = float((a1 if long else b1)[o]); near3 = float((a3 if long else b3)[o])
        # taker flow crossing our rest over the leg window (counter-side taker volume) x mid
        if long:      # rest bid -> filled by taker SELLS
            vol = csum_sell[x + 1] - csum_sell[o]
        else:         # rest ask -> filled by taker BUYS
            vol = csum_buy[x + 1] - csum_buy[o]
        flow = float(vol) * float(mid[o])
        real = min(near3, flow)
        rows.append((near1, near3, flow, real))
    arr = np.array(rows) if rows else np.zeros((0, 4))
    return arr  # columns: near1, near3, flow, real=min(near3,flow)


def dist(x):
    if len(x) == 0:
        return dict(n=0)
    return dict(n=int(len(x)), med=round(float(np.median(x))), p10=round(float(np.percentile(x, 10))),
                p90=round(float(np.percentile(x, 90))), pct_lt5k=round(100 * float((x < 5000).mean()), 0))


def main():
    print("=" * 100)
    print("HONEST CAPACITY TEST — real per-leg reachable cap, then A (concentrate) vs B (additive leftover)")
    print("=" * 100)
    clips, ov_sec = load_clipped()
    hours = ov_sec / 3600.0
    coins = [c["coin"] for c in CELLS if c["active"] and c["coin"] in clips]
    print(f"window {ov_sec}s = {hours:.1f}h, {len(coins)} coins, pool=${POOL:.0f}, front-of-line kr_mk0\n")

    # live legs + edge weights (same as baseline)
    cell_legs = {}; edge = {}; caparr = {}
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in clips:
            continue
        c = cell["coin"]; clip = clips[c]
        _, r = run_cell(cell, clip, fill_model="front")
        cell_legs[c] = r.legs
        edge[c] = sum(float(l.net_bps) for l in r.legs) / 1e4 * POOL / hours
        caparr[c] = leg_capacity(c, clip, r.legs)
    lo = min(edge.values()); shift = (-lo + 1e-6) if lo <= 0 else 0.0
    weights = {c: edge[c] + shift for c in coins}

    # ---- (1) per-coin REAL capacity distributions ----
    print("--- (1) REAL per-leg reachable capacity ($ = size*mid), per coin ---")
    print(f"  {'coin':6}{'edge$/hr':>9} | {'near-touch top1 (med/p10/p90)':>34} | "
          f"{'taker-flow/leg (med/p10/p90)':>32} | {'REAL=min (med)  %<$5k':>22}")
    cap_table = {}
    real_caps = {}
    for c in coins:
        A = caparr[c]
        d1 = dist(A[:, 0]); d3 = dist(A[:, 1]); df = dist(A[:, 2]); dr = dist(A[:, 3])
        cap_table[c] = {"near_top1": d1, "near_top3": d3, "flow": df, "real_min": dr}
        real_caps[c] = list(A[:, 3])
        print(f"  {c:6}{edge[c]:>+9.2f} | {d1['med']:>10,.0f}/{d1['p10']:>7,.0f}/{d1['p90']:>8,.0f}   | "
              f"{df['med']:>9,.0f}/{df['p10']:>6,.0f}/{df['p90']:>8,.0f}  | "
              f"{dr['med']:>9,.0f}   {dr['pct_lt5k']:>4.0f}%")
    print(f"\n  (near-touch shown top-1; top-3 median in JSON. REAL cap = min(top-3 resting depth, taker "
          f"flow over the leg). %<$5k = how often capacity BINDS below the pool.)")

    # ---- (2) A vs B worlds on REAL caps ----
    print("\n--- (2) A (concentrate) vs B_naive vs B_reserve vs B_preempt — POOL $/hr on REAL caps ---")
    mids = {c: clips[c]["mid"] for c in coins}
    xrp_reserve = float(np.median(real_caps[BEST]))   # reserve-per-rest v1: reserve the primary's typical cap
    backups = [c for c in coins if c != BEST]

    # World A: BEST coin only, at real cap, everything else idle (leftover -> $0/hr).
    prA = run_portfolio({BEST: cell_legs[BEST]}, pool=POOL, weights={BEST: weights[BEST]}, mode="greedy",
                        n=ov_sec, bucket_cells=BUCKET, leg_caps={BEST: real_caps[BEST]})
    poolA = prA.pool_return_per_hr
    xrpA = prA.per_coin[BEST]["realized_pnl_usd"] / hours

    # World B_naive: all coins, real caps, naive greedy cascade (NO reservation) — the starvation hazard.
    prB = run_portfolio(cell_legs, pool=POOL, weights=weights, mode="greedy",
                        n=ov_sec, bucket_cells=BUCKET, leg_caps=real_caps)
    poolB = prB.pool_return_per_hr
    per_hr_B = {c: prB.per_coin[c]["realized_pnl_usd"] / hours for c in coins}

    # World B_reserve: reserve-per-rest v1 — backups CLUSTER-CAPPED at pool - xrp_reserve so the primary
    # is never starved of its reserve; the leftover slice funds backups (no preemption, causal, clean).
    clusters = {c: "bk" for c in backups}
    prR = run_portfolio(cell_legs, pool=POOL, weights=weights, mode="greedy",
                        n=ov_sec, bucket_cells=BUCKET, leg_caps=real_caps,
                        clusters=clusters, cluster_caps={"bk": max(0.0, POOL - xrp_reserve)})
    poolR = prR.pool_return_per_hr
    per_hr_R = {c: prR.per_coin[c]["realized_pnl_usd"] / hours for c in coins}
    xrpR = per_hr_R[BEST]

    # World B_preempt: naive cascade + reactive preemption with HONEST book-mid MTM on the cut leg.
    prBp = run_portfolio(cell_legs, pool=POOL, weights=weights, mode="greedy",
                         n=ov_sec, bucket_cells=BUCKET, leg_caps=real_caps, preempt=True, mtm_prices=mids)
    poolBp = prBp.pool_return_per_hr
    per_hr_Bp = {c: prBp.per_coin[c]["realized_pnl_usd"] / hours for c in coins}
    xrpBp = per_hr_Bp[BEST]
    binds = getattr(prBp, "preempt_events", 0)

    print(f"  A)  {BEST}-only @ real cap, leftover IDLE          : POOL $/hr = {poolA:+6.2f}   "
          f"deploy {100*prA.time_util:>3.0f}%   ({BEST}={xrpA:+.2f}, backups=idle)")
    print(f"  B_naive)  real-cap cascade, NO reservation        : POOL $/hr = {poolB:+6.2f}   "
          f"deploy {100*prB.time_util:>3.0f}%   ({BEST}={per_hr_B[BEST]:+.2f}  <- STARVED by squatting backups)")
    print(f"  B_reserve) reserve-per-rest (reserve ${xrp_reserve:,.0f}): POOL $/hr = {poolR:+6.2f}   "
          f"deploy {100*prR.time_util:>3.0f}%   ({BEST}={xrpR:+.2f} protected + backups {poolR-xrpR:+.2f})")
    print(f"  B_preempt) cascade + reactive preempt (book-MTM)  : POOL $/hr = {poolBp:+6.2f}   "
          f"deploy {100*prBp.time_util:>3.0f}%   ({BEST}={xrpBp:+.2f} + backups {poolBp-xrpBp:+.2f}, {binds} preempts)")

    print(f"\n  B_reserve decomposition (per-coin $/hr; primary reserved, backups on the ${POOL-xrp_reserve:,.0f} leftover):")
    for c in sorted(coins, key=lambda c: -per_hr_R[c]):
        tag = "  <- PRIMARY (reserved)" if c == BEST else "  (backup on leftover)"
        print(f"     {c:6} {per_hr_R[c]:>+7.2f} $/hr   funded {prR.per_coin[c]['n_funded']:>4d}/"
              f"{prR.per_coin[c]['n_legs']:<4d}  meanAlloc ${prR.per_coin[c]['mean_alloc_usd']:>5.0f}{tag}")

    best_world = max([("A", poolA), ("B_naive", poolB), ("B_reserve", poolR), ("B_preempt", poolBp)],
                     key=lambda t: t[1])
    print(f"\n  ADDITIVE-LEFTOVER READ:")
    print(f"    primary {BEST} standalone (A)          = {poolA:+.2f} $/hr")
    print(f"    B_reserve leftover contribution        = {poolR - xrpR:+.2f} $/hr  (backups on genuine leftover)")
    print(f"    B_reserve vs A                         = {poolR - poolA:+.2f}  "
          f"({'ADDITIVE — Gregs thesis holds under reservation' if poolR >= poolA - 1e-6 else 'still < A'})")
    print(f"    B_naive vs A                           = {poolB - poolA:+.2f}  "
          f"(naive cascade STARVES the primary -> not additive)")
    print(f"    B_preempt vs A                         = {poolBp - poolA:+.2f}  ({binds} reactive preempts, book-MTM cut)")
    print(f"    => best world on this window: {best_world[0]} ({best_world[1]:+.2f} $/hr)")

    # ---- persist ----
    out = {
        "window": {"seconds": ov_sec, "hours": round(hours, 2), "coins": coins, "pool": POOL, "primary": BEST},
        "capacity_table": cap_table,
        "xrp_reserve": round(xrp_reserve),
        "worlds": {
            "A_concentrate_idle": {"pool_per_hr": round(poolA, 2), "time_util": round(prA.time_util, 3),
                                   "primary_per_hr": round(xrpA, 2)},
            "B_naive_cascade": {"pool_per_hr": round(poolB, 2), "time_util": round(prB.time_util, 3),
                                "per_coin_per_hr": {c: round(per_hr_B[c], 2) for c in coins},
                                "primary_per_hr": round(per_hr_B[BEST], 2)},
            "B_reserve_per_rest": {"pool_per_hr": round(poolR, 2), "time_util": round(prR.time_util, 3),
                                   "per_coin_per_hr": {c: round(per_hr_R[c], 2) for c in coins},
                                   "primary_per_hr": round(xrpR, 2), "leftover_per_hr": round(poolR - xrpR, 2)},
            "B_preempt": {"pool_per_hr": round(poolBp, 2), "lift_over_B_naive": round(poolBp - poolB, 2),
                          "preempt_events": binds, "time_util": round(prBp.time_util, 3),
                          "primary_per_hr": round(xrpBp, 2), "leftover_per_hr": round(poolBp - xrpBp, 2)},
        },
        "B_reserve_minus_A": round(poolR - poolA, 2),
        "B_naive_minus_A": round(poolB - poolA, 2),
        "caveat": "ONE 42h low-edge Kraken window; real cap = min(top-3 resting depth, taker flow/leg); "
                  "reserve-per-rest v1 (no optimistic-over-resting yet).",
    }
    with open("_pool_capacity_honest_results.json", "w") as f:
        json.dump(out, f, indent=2, default=lambda o: None)
    print("\nwrote _pool_capacity_honest_results.json")


if __name__ == "__main__":
    main()
