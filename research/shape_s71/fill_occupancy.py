"""S77: realistic per-trade FILL + OCCUPANCY per small cap — of the $5k, how much actually trades / is
consistently deployed? The $/hr table assumed the full $5k fills every trade; a front-of-line maker on a
thin book only fills what trades against it. Per coin (using its train-picked config from r2_<coin>.txt),
replay the swing on the TEST slice and measure, per trade:
  fill$   : min($5k, opposing-side $ traded during the hold)   (a maker fills only the flow that hits it)
  hold_s  : position duration
Then per cell:
  occ%        : fraction of test time in a position
  med_fill$   : median per-trade fill
  avg_depl$   : time-avg capital deployed = sum(fill_i * hold_i) / test_seconds   (<= $5k)
The bank's "consistently in small caps" = sum of avg_depl$ across cells, capped at $5k (shared bank).

    python3 fill_occupancy.py
"""
import os, sys, json, types, re
import numpy as np
from collections import deque
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es
from book_swing_kraken import zscores, CAP, STRIDE, MINCONV

SMALL = "aave ada avax bch bnb hype link ltc near sui tao ton xlm xmr xpl zec".split()


def series_vol(path, k=es.DEFAULT_K, stride=STRIDE):
    """Like series_1s but also aggregate buy/sell traded volume ($) per strided bar."""
    imb, mid, opp_buy, opp_sell = [], [], [], []
    ab = asl = 0.0
    with open(path) as f:
        for i, line in enumerate(f):
            r = json.loads(line); m = float(r["mid"])
            ab += float(r.get("buy", 0.0)) * m; asl += float(r.get("sell", 0.0)) * m
            if i % stride:
                continue
            bids = [[m + float(o), float(s)] for o, s in r["bids"][:k]]
            asks = [[m + float(o), float(s)] for o, s in r["asks"][:k]]
            bk = es.book_imbalance(bids, asks, k, m)
            imb.append(bk["imb"] if bk["ok"] else 0.0); mid.append(m)
            opp_buy.append(ab); opp_sell.append(asl); ab = asl = 0.0
    return np.array(imb), np.array(mid), np.array(opp_buy), np.array(opp_sell)


def picked(coin):
    t = open(f"/tmp/kbook/r2_{coin}.txt").read()
    m = re.search(r"horizon=(\d+)s sign=([+-]\d) enter_z=([\d.]+) minconv=([\d.]+) trail=(\d+) hold=(\d+)", t)
    if not m: return None
    return dict(hz=int(m[1]), ds=int(m[2]), ez=float(m[3]), mc=float(m[4]), trail=float(m[5]), mh=int(m[6]))


def replay(imb, mid, buy, sell, z, cfg):
    """Replay the swing; per trade record (fill$, hold). fill = opposing-side $ over the hold, capped CAP.
    long (d=+1): filled by SELL flow; short (d=-1): filled by BUY flow."""
    n = len(imb); pos = None; trades = []
    for i in range(n):
        if pos is None:
            if abs(z[i]) >= cfg["ez"] and abs(imb[i]) >= cfg["mc"]:
                d = cfg["ds"] if z[i] > 0 else -cfg["ds"]
                pos = {"d": d, "entry": mid[i], "best": 0.0, "t": 0, "opp": 0.0}
        else:
            pos["t"] += 1
            pos["opp"] += sell[i] if pos["d"] > 0 else buy[i]     # flow that fills our resting maker
            fav = pos["d"] * (mid[i] - pos["entry"]) / pos["entry"] * 1e4
            pos["best"] = max(pos["best"], fav)
            if (pos["best"] - fav) >= cfg["trail"] or pos["t"] >= cfg["mh"]:
                trades.append((min(CAP, pos["opp"]), pos["t"])); pos = None
    return trades


def main():
    rows = []
    for c in SMALL:
        cfg = picked(c)
        if not cfg:
            continue
        imb, mid, buy, sell = series_vol(f"/tmp/kbook/{c}_book.jsonl")
        n = len(imb); cut = int(n * 0.6)
        te = slice(cut, n); T = n - cut
        z_te = zscores(imb[te])
        tr = replay(imb[te], mid[te], buy[te], sell[te], z_te, cfg)
        if not tr:
            continue
        fills = np.array([f for f, _ in tr]); holds = np.array([h for _, h in tr])
        occ = holds.sum() / T
        avg_depl = (fills * holds).sum() / T
        rows.append((c, occ, float(np.median(fills)), float(fills.mean()), avg_depl, len(tr)))
    rows.sort(key=lambda r: -r[4])
    print(f"{'coin':>6}{'occ%':>7}{'med_fill$':>11}{'mean_fill$':>11}{'avg_depl$':>11}{'trades':>7}")
    tot = 0.0
    for c, occ, mf, af, ad, nt in rows:
        print(f"{c.upper():>6}{occ*100:>7.1f}{mf:>11,.0f}{af:>11,.0f}{ad:>11,.0f}{nt:>7}")
        tot += ad
    print(f"\n  raw sum avg-deployed across small caps: ${tot:,.0f}  (shared bank caps at ${CAP:,.0f})")
    print(f"  => consistently in small caps: ${min(tot, CAP):,.0f} of ${CAP:,.0f}")


if __name__ == "__main__":
    main()
