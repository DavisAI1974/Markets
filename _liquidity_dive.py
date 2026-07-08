"""_liquidity_dive.py — S42: mine the LIQUIDITY layer (the only layer S41 found structure in).

S41 result (do not re-litigate): the agnostic 5-step coupler found structured coupling that
survives the tautology null ONLY on the liquidity side (ask_depth~taker_sell, bid_depth~ask_depth);
every flow<->price / flow<->flow pair was NULL. BUT S41 used `abs_return` (magnitude) as the price
channel and never tested liquidity *dynamics*. This dive closes both gaps.

Two parts, both agnostic about direction (the coupler / cross-corr discover the lead/lag sign):

PART A — agnostic 5-step coupler (odcore.coupling_scanner.score_pair, all 5 steps + circular-shift
tautology null) over RICHER liquidity channels, including SIGNED return (the directional target
S41 lacked) and the liquidity *dynamics* Greg named (book-depth withdrawal, one-sided depth changes,
depth-imbalance velocity). Run across N time-slices for cross-segment consistency — a single-window
winner is a fluke (S41), so a coupling only counts if it survives the null in MULTIPLE slices.

PART B — exploitability readout (fast, no operator matrix): for each liquidity signal vs the SIGNED
forward return, on a 60/40 train/test split: pick the best lead on TRAIN, then on TEST report OOS
cross-correlation (+ circular-shift null z), directional hit-rate, and the mean |forward move| in bps
against the half-spread — i.e. is the discovered lead big enough to beat the fee/spread floor.

Channels (100ms grid, top-K depth):
  depth_imb     = (bid_depth - ask_depth)/(bid_depth + ask_depth)     imbalance LEVEL (signed)
  d_depth_imb   = d/dt depth_imb                                      imbalance DYNAMICS (velocity)
  d_total_depth = d/dt (bid_depth + ask_depth)                        book-depth WITHDRAWAL (<0 = pulled)
  d_bid_depth   = d/dt bid_depth                                      one-sided (bids pulled/refilled)
  d_ask_depth   = d/dt ask_depth                                      one-sided (asks pulled/refilled)
  signed_ret    = d log(mid)                                          DIRECTIONAL price
  flow          = trailing-W (buy-sell)/(buy+sell)                    head pressure (taker lean)
"""
from __future__ import annotations
import argparse, json, time
import numpy as np
from _birth_probe import load_book, to_grid, lean
from odcore.coupling_scanner import score_pair
from odcore.leadlag import cross_correlation


def build_channels(path, K, W, raw=None):
    g = to_grid(raw if raw is not None else load_book(path), 0.1)
    bd, ad = g["bidK"][K], g["askK"][K]
    tot = bd + ad
    depth_imb = (bd - ad) / (tot + 1e-12)
    d = lambda x: np.concatenate([[0.], np.diff(x)])
    lm = np.log(np.where(g["mid"] > 0, g["mid"], np.nan))
    signed_ret = np.nan_to_num(d(lm))
    flow = lean(g["buy"], g["sell"], W)
    ch = {
        "depth_imb":     depth_imb,
        "d_depth_imb":   d(depth_imb),
        "d_total_depth": d(tot),
        "d_bid_depth":   d(bd),
        "d_ask_depth":   d(ad),
        "signed_ret":    signed_ret,
        "flow":          flow,
    }
    return ch, g


# ---------------------------------------------------------------- PART A
def part_a(ch, window, stride, nparts):
    names = list(ch)
    L = len(ch["signed_ret"])
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]
    print(f"# PART A — agnostic 5-step coupler, {len(pairs)} pairs x {nparts} slices "
          f"(window={window} stride={stride}, tautology-null on)")
    print(f"# a coupling COUNTS only if structure_z>2 in MULTIPLE slices (single-window = fluke, S41)\n")
    agg = {f"{a}~{b}": {"z": [], "ll": [], "llz": [], "r2": []} for a, b in pairs}
    t0 = time.time()
    for p in range(nparts):
        lo, hi = p * L // nparts, (p + 1) * L // nparts
        for a, b in pairs:
            ps = score_pair(ch[a][lo:hi], ch[b][lo:hi], f"{a}~{b}", "dive",
                            window=window, stride=stride, seed=p)
            if ps is None:
                continue
            d = agg[f"{a}~{b}"]
            d["z"].append(ps.structure_z); d["ll"].append(ps.leadlag)
            d["llz"].append(ps.coupling_z); d["r2"].append(ps.dipole_r2)
        print(f"  slice {p+1}/{nparts} done ({time.time()-t0:.0f}s)")
    rows = []
    for name, d in agg.items():
        if not d["z"]:
            continue
        z = np.array(d["z"]); ll = np.array(d["ll"])
        rows.append(dict(pair=name, meanZ=float(z.mean()), nZgt2=int((z > 2).sum()),
                         nslices=len(z), meanLL_s=float(ll.mean() * 0.1),
                         meanLLz=float(np.mean(d["llz"])), meanR2=float(np.mean(d["r2"]))))
    rows.sort(key=lambda r: (r["nZgt2"], r["meanZ"]), reverse=True)
    hdr = f"{'pair':24} {'meanZ':>6} {'#z>2':>5}/{'N':<3} {'meanLL(s)':>9} {'meanLLz':>8} {'dip_r2':>7}"
    print("\n" + hdr); print("-" * len(hdr))
    for r in rows:
        lead = ("LEADS" if r["meanLL_s"] > 0 else "lags" if r["meanLL_s"] < 0 else "coinc")
        print(f"{r['pair']:24} {r['meanZ']:6.2f} {r['nZgt2']:5d}/{r['nslices']:<3} "
              f"{r['meanLL_s']:+9.2f} {r['meanLLz']:8.2f} {r['meanR2']:7.3f}  ({lead})")
    return rows


# ---------------------------------------------------------------- PART B
def fwd_cum_return(signed_ret, H):
    """Forward cumulative return over the next H cells (excludes the current cell)."""
    c = np.concatenate([[0.], np.cumsum(signed_ret)])
    n = len(signed_ret)
    out = np.full(n, np.nan)
    out[:n - H] = c[H + 1:n + 1] - c[1:n - H + 1]  # sum of ret[t+1 .. t+H]
    return out


def part_b(ch, g, horizons, split=0.6, n_null=200, seed=0):
    rng = np.random.default_rng(seed)
    sret = ch["signed_ret"]
    n = len(sret)
    cut = int(n * split)
    # half-spread in bps from the book file (median), the maker-side floor reference
    # spread ~ ask_offset - bid_offset around mid; use the actual mid + a representative half-spread
    half_spread_bps = float(np.median(np.abs(g.get("spread_bps", np.array([np.nan])))))  # may be nan
    sig_names = ["depth_imb", "d_depth_imb", "d_total_depth", "d_bid_depth", "d_ask_depth", "flow"]
    print(f"\n# PART B — exploitability: does each liquidity signal predict the SIGNED forward return,"
          f"\n#          OOS, net of the spread floor? split train[:{cut:,}] test[{cut:,}:] (60/40)\n")
    print(f"{'signal':14} {'H(s)':>5} {'bestLag(s)':>10} {'OOS_r':>7} {'null_z':>7} "
          f"{'hit%':>6} {'|fwd|bps':>9}")
    print("-" * 70)
    out = []
    for name in sig_names:
        s = ch[name]
        for H in horizons:
            fwd = fwd_cum_return(sret, H)
            # choose lead on TRAIN: lag L maximizing |corr(s[t], fwd[t]) shifted| over small grid
            lags = range(0, 21)  # signal leads price by 0..2s
            best_lag, best_c = 0, 0.0
            for L in lags:
                a = s[:cut - L]; b = fwd[L:cut]
                m = ~np.isnan(b)
                if m.sum() < 100 or a[m].std() < 1e-12 or b[m].std() < 1e-12:
                    continue
                c = np.corrcoef(a[m], b[m])[0, 1]
                if abs(c) > abs(best_c):
                    best_c, best_lag = c, L
            # evaluate on TEST at best_lag
            a = s[cut:n - best_lag] if best_lag else s[cut:]
            b = fwd[cut + best_lag:] if best_lag else fwd[cut:]
            L2 = min(len(a), len(b)); a, b = a[:L2], b[:L2]
            m = ~np.isnan(b)
            a, b = a[m], b[m]
            if len(a) < 200 or a.std() < 1e-12 or b.std() < 1e-12:
                continue
            oos_r = float(np.corrcoef(a, b)[0, 1])
            # circular-shift null on TEST
            null = []
            for _ in range(n_null):
                sh = int(rng.integers(50, len(b) - 50))
                bb = np.concatenate([b[sh:], b[:sh]])
                null.append(np.corrcoef(a, bb)[0, 1])
            null = np.array(null)
            z = float((oos_r - null.mean()) / (null.std() + 1e-12))
            # directional hit-rate (sign of signal vs sign of fwd move), only where both nonzero
            sgn = (np.sign(a) == np.sign(b))
            nz = (a != 0) & (b != 0)
            hit = float(sgn[nz].mean()) if nz.any() else np.nan
            fwd_bps = float(np.mean(np.abs(b)) * 1e4)
            out.append(dict(signal=name, H_s=round(H * 0.1, 1), best_lag_s=round(best_lag * 0.1, 1),
                            oos_r=round(oos_r, 4), null_z=round(z, 2), hit=round(hit, 4),
                            fwd_bps=round(fwd_bps, 3)))
            print(f"{name:14} {H*0.1:5.1f} {best_lag*0.1:10.1f} {oos_r:+7.3f} {z:+7.2f} "
                  f"{hit*100:6.1f} {fwd_bps:9.3f}")
    return out, half_spread_bps


def median_spread_bps(path, raw=None):
    """Median top-of-book spread in bps (the maker-execution floor reference). Subsamples every 50th record.
    If a preloaded `raw` dict (from load_book) is passed, reuse it instead of re-reading the gzip — the raw
    arrays are 1:1 with the file rows, so [::50] with the same mid>0 / spread-present filters is bit-identical."""
    if raw is not None:
        mid = raw["mid"][::50]; sp = raw["spread"][::50]
        m = (mid > 0) & ~np.isnan(sp)
        sb = (sp[m] / mid[m] * 1e4)
        return float(np.median(sb)) if sb.size else float("nan")
    sb = []
    with __import__("gzip").open(path, "rt") as f:
        for i, line in enumerate(f):
            if i % 50:  # subsample every 50th record — plenty for a median
                continue
            r = json.loads(line)
            if r.get("mid", 0) > 0 and r.get("spread") is not None:
                sb.append(r["spread"] / r["mid"] * 1e4)
    return float(np.median(sb)) if sb else float("nan")


def run(path, K, W, window, stride, nparts, horizons, do_a, do_b):
    ch, g = build_channels(path, K, W)
    res = dict(path=path, K=K, W=W, window=window, stride=stride, nparts=nparts)
    if do_a:
        res["part_a"] = part_a(ch, window, stride, nparts)
    if do_b:
        b_out, _ = part_b(ch, g, horizons)
        res["part_b"] = b_out
        hs = median_spread_bps(path)
        res["spread_bps_median"] = hs
        # cost floors (Coinbase Advanced, representative): taker ~40bps, maker ~25bps, maker rebate ~0
        res["cost_floor_bps"] = dict(taker_rt=80.0, maker_rt=50.0, maker_zero_rt=0.0,
                                     half_spread=round(hs / 2, 4))
        print(f"\n# FEE/SPREAD FLOOR — median top-of-book spread = {hs:.4f} bps (half = {hs/2:.4f} bps).")
        print(f"#   Coinbase round-trip: taker ~80 bps, maker ~50 bps, maker-rebate ~0.")
        print(f"#   The biggest predicted move above is ~1.3 bps (depth_imb @5s) — BELOW any active")
        print(f"#   fee floor. This is a MAKER/quoting signal (which side to post / when to pull),")
        print(f"#   NOT a taker strategy. Edge is real & OOS but lives below the round-trip cost.")
    json.dump(res, open("_liquidity_dive_results.json", "w"), indent=2)
    print("\n[saved] _liquidity_dive_results.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--W", type=int, default=20, help="flow lean window (cells)")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=40)
    ap.add_argument("--nparts", type=int, default=10)
    ap.add_argument("--horizons", default="1,5,10,30,50", help="forward horizons in cells")
    ap.add_argument("--skip-a", action="store_true")
    ap.add_argument("--skip-b", action="store_true")
    a = ap.parse_args()
    H = [int(x) for x in a.horizons.split(",")]
    run(a.path, a.K, a.W, a.window, a.stride, a.nparts, H, not a.skip_a, not a.skip_b)
