"""portfolio_sim_kraken.py — the SHARED-POOL capital model replay (S67, the capital model).

⭐ ARCHITECTURE RULE (Greg S65, load-bearing): the DECISION PATH is the LIVE code —
`odcore.platform.run_kraken_cell` (per-coin legs) and `odcore.platform.run_portfolio` (the shared-pool
allocation). This sim ONLY adds pieces the live path doesn't own: (1) multi-coin Kraken TAPE loading
(`odcore.io.load_bins` + `align`), (2) building the per-coin capacity caps (`odcore.capacity`) and the
return-on-capacity weights + correlation clusters (`odcore.allocator`). It NEVER re-decides a trade or
re-implements the executor/fill/sizing/fees.

WHAT IT ANSWERS (the thing basket_sim's `aggregate (sum @ $5k each)` line cannot): given ONE shared
pool spread across the majors — capacity-capped per coin and correlation-aware — what does the POOL
earn per hour? (POOL RETURN, not sum-of-cells-@-$5k-each.)

DESIGN (Greg S67, locked): MAJORS-FIRST. Pool = $5k shared. Capacity granularity = PER-COIN position
cap (an explicit jump-off scaffold — the swappable `caps` dict migrates to per-LEG later without
touching the allocator). The cap is a SIZE scale, never an inclusion gate (a thin-cap coin gets small
size, never dropped). Fee frame = the $10M tier (majors 0bp; treated as real per Greg — carried as the
per-cell maker_fee parameter so a pre-$10M adjustment is a value change, not a rewrite).

DATA: Kraken 1s TAPE bins in realbins/<coin>_kraken_bins.json (BTC+ETH on box, 27.7d). No book depth
on tape, so capacity is the flow-bound proxy (S66) and fill is front-of-line (the deployed premise);
the DIRECTION/STRUCTURE is the deliverable, absolute $/hr is provisional (matches basket_sim's caveat).
Restore sol/xrp/doge tape (data/kraken-smallcap-tape or backfill_kraken_trades.py) + add the agent's
LARGE candidates (KRAKEN_MAJORS_SWEEP_S67.md) as ungraded seats to run the full roster.

Usage:
  python scripts/portfolio_sim_kraken.py                 # $5k shared pool, per-coin capacity caps
  python scripts/portfolio_sim_kraken.py --pool 10000    # resize the shared pool
  python scripts/portfolio_sim_kraken.py --canary        # prove pool=inf + cap=CAP == sum-of-cells
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.io import load_bins, align                                       # noqa: E402  (tape I/O)
from odcore.platform import KRAKEN, run_kraken_cell, run_portfolio           # noqa: E402  (LIVE path)
from odcore.capacity import cell_capacity_summary                            # noqa: E402
from odcore.allocator import pnl_correlation, cluster_by_corr                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REALBINS = os.path.join(ROOT, "realbins")
CAP = 5000.0            # basket_sim's flat per-cell slice (the canary reference)
BUCKET = 3600           # 1s grid -> hourly buckets
CORR_THRESH = 0.5       # PnL-correlation cluster threshold


def available_cells():
    """KRAKEN registry cells that have a realbins tape on box (majors-first; the roster grows as
    sol/xrp/doge tape + the agent's LARGE candidates are restored)."""
    out = []
    for cfg in KRAKEN:
        p = os.path.join(REALBINS, f"{cfg.coin}_kraken_bins.json")
        if os.path.exists(p):
            out.append((cfg, p))
    return out


def load_aligned(cells):
    """Load each coin's tape and clip ALL to one common overlap grid (so leg indices share a 0..n
    index space for the shared-pool replay). Returns (coins, arrays_by_coin, n, hours)."""
    series = {cfg.coin: load_bins(p) for cfg, p in cells}
    coins = [cfg.coin for cfg, _ in cells]
    # pairwise-align to the common window (align is 2-way; fold across coins)
    ref = series[coins[0]]
    lo = max(int(series[c].ts[0]) for c in coins)
    hi = min(int(series[c].ts[-1]) for c in coins)
    if hi <= lo:
        raise SystemExit("no common overlap window across the tapes")
    out = {}
    for c in coins:
        s = series[c]
        m = (s.ts >= lo) & (s.ts <= hi)
        out[c] = dict(mid=s.mid[m], buy=s.buy[m], sell=s.sell[m], spread=s.spread[m])
    n = hi - lo + 1
    return coins, out, n, n / float(BUCKET)


def legs_and_caps(cfg, arr):
    """Run the LIVE per-coin stack on this coin's aligned tape -> (legs, per-coin capacity summary).
    front-of-line fill needs no book sizes (pass zeros); capacity = the S66 deployed whole-hold +
    price-eligible flow-bound proxy on tape."""
    mid, buy, sell = arr["mid"], arr["buy"], arr["sell"]
    z = np.zeros(len(mid))
    hs = float(np.median((arr["spread"][mid > 0] / mid[mid > 0]) / 2.0) * 1e4) if np.any(mid > 0) else 0.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, z, z, hs)
    capsum = cell_capacity_summary(res.legs, mid, buy, sell, window=None, price_eligible=True)
    return res.legs, capsum


def hourly_pnl_at_cap(legs, cap, n):
    """Per-hour $ PnL of a cell run at a FLAT `cap` (for correlation/clustering — matches basket_sim's
    bucket_pnl on the un-pooled stream)."""
    nb = max(1, n // BUCKET)
    pnl = np.zeros(nb)
    for l in legs:
        b = min(int(l.close_idx) // BUCKET, nb - 1)
        pnl[b] += float(l.net_bps) / 1e4 * cap
    return pnl


def sh(x):
    return float(x.mean() / (x.std() + 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=float, default=CAP, help="shared pool $ (default 5000)")
    ap.add_argument("--cap-pct", type=int, default=50,
                    help="per-coin position cap = this percentile of the coin's per-leg capacity (default median)")
    ap.add_argument("--corr-thresh", type=float, default=CORR_THRESH)
    ap.add_argument("--canary", action="store_true",
                    help="prove pool=inf + per-coin cap=CAP reproduces basket_sim's sum-of-cells")
    args = ap.parse_args()

    cells = available_cells()
    if not cells:
        raise SystemExit("no realbins/<coin>_kraken_bins.json on box — restore the Kraken tape first")
    coins, arr, n, hours = load_aligned(cells)
    cfg_of = {cfg.coin: cfg for cfg, _ in cells}

    print("=== KRAKEN SHARED-POOL CAPITAL MODEL (S67) — via LIVE run_kraken_cell + run_portfolio ===")
    print(f"   majors-first roster: {coins}   common window: {n}s = {hours:.1f}h   fee=$10M tier (majors 0bp)\n")

    cell_legs = {}
    capsum = {}
    for cfg, _ in cells:
        legs, cs = legs_and_caps(cfg, arr[cfg.coin])
        cell_legs[cfg.coin] = legs
        capsum[cfg.coin] = cs

    # ---- CANARY: pool=inf + per-coin cap=CAP must reproduce the sum-of-cells @ $CAP each ----
    if args.canary:
        indep = {c: sum(float(l.net_bps) / 1e4 * CAP for l in cell_legs[c]) for c in coins}
        indep_total = sum(indep.values())
        pr = run_portfolio(cell_legs, pool=float("inf"),
                           caps={c: CAP for c in coins}, desired={c: CAP for c in coins},
                           n=n, bucket_cells=BUCKET)
        print("  --- CANARY: run_portfolio(pool=inf, cap=$5k/coin) vs basket_sim sum-of-cells ---")
        for c in coins:
            print(f"    {c:5} independent ${indep[c]:+10.2f}   portfolio ${pr.per_coin[c]['realized_pnl_usd']:+10.2f}")
        diff = abs(pr.total_pnl_usd - indep_total)
        print(f"    TOTAL independent ${indep_total:+.4f}   portfolio ${pr.total_pnl_usd:+.4f}   |diff|={diff:.2e}")
        assert diff < 1e-6, f"CANARY FAIL: portfolio != sum-of-cells (diff {diff})"
        # every coin fully funded (uncapped vs an infinite pool)
        assert all(pr.per_coin[c]["fill_share"] == 1.0 for c in coins), "CANARY FAIL: not all legs funded"
        print("  CANARY PASS — the capital model sits ON the proven per-cell path (allocator 'off' == today's numbers).\n")

    # ---- per-coin capacity caps (the swappable scaffold: per-COIN position cap = a percentile of
    #      the coin's per-leg capacity distribution). A low cap => small size, never exclusion. ----
    pct = args.cap_pct
    caps = {c: float(capsum[c][f"p{pct}_cap_usd"] if pct in (75, 90) else capsum[c]["median_cap_usd"])
            for c in coins}

    # ---- return-on-capacity weights: the coin's net-bps-per-hour rate (edge per $). Shift so all are
    #      positive (never fully starve a coin; magnitude still prioritizes). ----
    raw_edge = {c: sum(float(l.net_bps) for l in cell_legs[c]) / 1e4 / hours for c in coins}
    lo_edge = min(raw_edge.values())
    shift = (-lo_edge + 1e-6) if lo_edge <= 0 else 0.0
    weights = {c: raw_edge[c] + shift for c in coins}

    # ---- correlation clusters from the per-coin hourly PnL streams (at each coin's own cap) ----
    streams = {c: hourly_pnl_at_cap(cell_legs[c], caps[c], n) for c in coins}
    ccoins, corr = pnl_correlation(streams)
    clusters = cluster_by_corr(ccoins, corr, thresh=args.corr_thresh) if corr is not None else {c: i for i, c in enumerate(coins)}
    for c in coins:
        clusters.setdefault(c, max(clusters.values(), default=-1) + 1)
    # cluster cap: no CORRELATED GROUP (>=2 coins) may draw more than this fraction of the pool in a
    # flush. A singleton is not a group -> uncapped by cluster (its own capacity cap governs).
    CLUSTER_FRAC = 0.7
    from collections import Counter
    csize = Counter(clusters.values())
    cluster_caps = {cid: (args.pool * CLUSTER_FRAC if csize[cid] >= 2 else float("inf"))
                    for cid in csize}

    print("  --- per-coin inputs ---")
    print(f"  {'coin':5}{'legs':>6}{'cap$(p'+str(pct)+')':>12}{'edge$/hr/$':>12}{'weight':>9}{'cluster':>8}")
    for c in coins:
        print(f"  {c:5}{len(cell_legs[c]):>6}{caps[c]:>12.0f}{raw_edge[c]:>12.4f}{weights[c]:>9.3f}{clusters[c]:>8}")

    if corr is not None:
        print("\n  PnL correlation:  " + "".join(f"{c:>7}" for c in ccoins))
        for i, c in enumerate(ccoins):
            print(f"    {c:>6}    " + "".join(f"{corr[i, j]:>7.2f}" for j in range(len(ccoins))))

    # ---- THE SHARED-POOL REPLAY ----
    pr = run_portfolio(cell_legs, pool=args.pool, caps=caps, desired=caps, weights=weights,
                       clusters=clusters, cluster_caps=cluster_caps, n=n, bucket_cells=BUCKET)

    print(f"\n  --- SHARED POOL = ${args.pool:.0f} (capacity-capped, {int(CLUSTER_FRAC*100)}% cluster cap, "
          f"return-on-capacity weighted) ---")
    print(f"  {'coin':5}{'legs':>6}{'funded%':>9}{'meanAlloc$':>12}{'realized$':>12}{'$/hr':>9}")
    for c in coins:
        pc = pr.per_coin[c]
        print(f"  {c:5}{pc['n_legs']:>6}{100*pc['fill_share']:>8.0f}%{pc['mean_alloc_usd']:>12.0f}"
              f"{pc['realized_pnl_usd']:>+12.2f}{pc['realized_pnl_usd']/hours:>+9.2f}")

    port = pr.pool_pnl_bucketed
    print(f"\n  POOL RETURN = ${pr.total_pnl_usd:+.2f} over {hours:.1f}h = {pr.pool_return_per_hr:+.3f} $/hr "
          f"on ${args.pool:.0f}  ({100*pr.pool_return_per_hr/args.pool:+.4f}%/hr)")
    print(f"  pool utilization: mean {100*pr.mean_util:.1f}%  peak {100*pr.max_util:.1f}%  idle {100*pr.idle_frac:.1f}% of live steps")
    print(f"  pool Sharpe/bucket = {sh(port):+.3f}")
    # contrast: the WRONG framing basket_sim flags (sum of independent @ $CAP each)
    indep_total = sum(sum(float(l.net_bps) / 1e4 * CAP for l in cell_legs[c]) for c in coins)
    print(f"\n  (contrast — the acknowledged-WRONG framing: sum-of-cells @ ${CAP:.0f} each = "
          f"${indep_total:+.2f} over {hours:.1f}h on ${CAP*len(coins):.0f} of capital. The pool number above is "
          f"what ONE ${args.pool:.0f} pool actually earns spread + capacity-capped.)")
    print("\n  ⚠ PROVISIONAL: 2-coin (BTC/ETH) tape-proxy capacity + front-of-line fill. Restore sol/xrp/doge "
          "tape + add the KRAKEN_MAJORS_SWEEP_S67 LARGE candidates as ungraded seats for the full roster.")


if __name__ == "__main__":
    main()
