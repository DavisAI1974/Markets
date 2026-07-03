"""_s52_tif_sweep.py — S52: the entry TIME-IN-FORCE (cancel-remainder) sweep the fill-window audit exposed.

`_s52_fill_window_audit.py` showed FILL_W=10 is not a neutral modeling constant — it is an EXECUTION POLICY
(post size S at the turn limit, cancel the unfilled remainder after W seconds), and it out-earns honest
rest-until-turn fills (capP) because a short TIF truncates the ADVERSE fills (losers keep filling the whole
slide-through; winners fill at the climax then price leaves). This sweeps W over {5,10,20,30,60,120,rest}
per cell at mk0 and −1bp, flat + sized, $1k/leg and best-S, to see where the policy peaks and how sharp it is.

NOT a tuning exercise for deploy (standing rule: never tune off one window) — the output is the SHAPE
(does $/hr decay monotonically in W past the climax?) + the honest statement of which matrix cells
correspond to which policy. Green-add / winner-fill re-measurement lives in _s52_green_state_flow.py.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker, size_legs
from _capacity_model import (_leg_features, _dollars, CELLS, GRACE, FLOW_W, WFLIP, REV, REP_S, SIZES)

WS = [5, 10, 20, 30, 60, 120]


def _caps_tif(legs, mid, buy, sell, W):
    """v1-style cap with window W cells after the fill cell, still bounded by the leg close AND by price
    eligibility (a fixed limit cannot fill once price has left it — the honest part of capP kept)."""
    caps = []
    for l in legs:
        o, c, ci = int(l.open_idx), int(l.close_idx), int(l.flip_idx)
        if c <= o:
            caps.append(0.0); continue
        end = min(c, o + W)
        seg = slice(o, end + 1)
        m = mid[seg]
        ok = (m <= mid[ci]) if l.side > 0 else (m >= mid[ci])
        opp = (sell if l.side > 0 else buy)[seg]
        caps.append(float(np.sum(opp[ok])) * float(mid[o]))
    return np.asarray(caps)


def cell(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    out = dict(coin=coin, hrs=hrs, rows=[])
    for mk in (0.0, -1.0):
        res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                   maker_fee_bps=mk, taker_fee_bps=5.0, cover_grace=grace)
        legs = res.legs
        nets = np.asarray([float(l.net_bps) for l in legs])
        q, sa = _leg_features(legs, mid, sret, buy, sell, lean, piv)
        size_legs(legs, q, sa, alpha=1.0, roll=200)
        sizes = np.asarray([float(l.size) for l in legs])
        ones = np.ones_like(sizes)
        for W in WS + ["rest"]:
            caps = _caps_tif(legs, mid, buy, sell, 10**9 if W == "rest" else W)
            grid = {S: _dollars(nets, sizes, caps, hrs, S) for S in SIZES[:-1]}
            bS = max(grid, key=grid.get)
            out["rows"].append(dict(mk=mk, W=W,
                                    flat_1k=_dollars(nets, ones, caps, hrs, REP_S),
                                    sized_1k=_dollars(nets, sizes, caps, hrs, REP_S),
                                    best_S=bS, best_sized=grid[bS]))
    return out


print("=== S52 TIF sweep — $/hr vs entry cancel-remainder window W (price-eligible flow within W) ===\n")
allout = []
for coin, K in CELLS:
    r = cell(coin, K, GRACE[coin])
    if r is None:
        print(f"[{coin}] no book\n"); continue
    allout.append(r)
    print(f"[{r['coin'].upper()}]  {r['hrs']:.1f}h")
    for mk in (0.0, -1.0):
        rows = [x for x in r["rows"] if x["mk"] == mk]
        lab = "mk0 " if mk == 0 else "mk-1"
        line = "  ".join(f"W={x['W']}: {x['sized_1k']:+.1f}" for x in rows)
        best = max(rows, key=lambda x: x["best_sized"])
        print(f"    [{lab}] sized $/hr @$1k:  {line}")
        print(f"           best cell of sweep: W={best['W']} S=${best['best_S']:,.0f} -> {best['best_sized']:+.1f} $/hr")
    print()
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s52_tif_sweep_results.json"), "w") as f:
    json.dump(allout, f, indent=2, default=float)
