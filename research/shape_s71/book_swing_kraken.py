"""S76: the paper's RIDE-TO-REVERSAL book swing, with the 60/40 WALK-FORWARD (Greg: tune on the first 60%,
validate on the held-out 40%). Uses Greg's early_signal.py: fit_direction_sign() to fit the sign on TRAIN,
and the swing entry logic (verified bit-equivalent to es.EarlySignalTracker) so we can slice train/test.

TRAIN (first 60%): fit direction_sign + pick the enter_z with the best train $/hr @0% maker.
TEST  (last 40%):  run frozen (sign, enter_z), report OOS bps/trade, win%, $/hr @0% maker and @taker.

    python3 book_swing_kraken.py <btc|eth>
"""
import os, sys, json, types
import numpy as np
from collections import deque
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es

CAP = 5000.0
STRIDE = 10
DIR_SIGN0 = {"btc": +1, "eth": +1, "xrp": +1, "sol": +1, "doge": -1}
TRAIL = es.TRAIL_BPS_DEFAULT          # 30
MAXHOLD = es.MAX_HOLD_S_DEFAULT       # 600
ROLL = es.DEFAULT_ROLL               # 120
SD_FLOOR = es.EarlySignalTracker.SD_FLOOR
MINCONV = 0.5
Z_GRID = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)


def series_1s(path, k=es.DEFAULT_K, stride=STRIDE):
    imb, mid = [], []
    with open(path) as f:
        for i, line in enumerate(f):
            if i % stride:
                continue
            r = json.loads(line); m = float(r["mid"])
            bids = [[m + float(o), float(s)] for o, s in r["bids"][:k]]
            asks = [[m + float(o), float(s)] for o, s in r["asks"][:k]]
            bk = es.book_imbalance(bids, asks, k, m)
            imb.append(bk["imb"] if bk["ok"] else 0.0); mid.append(m)
    return np.array(imb), np.array(mid)


def swing(imb, mid, ds, enter_z, fee, trail=TRAIL, maxhold=MAXHOLD, min_conv=MINCONV):
    """Ride-to-reversal on a precomputed imb/mid slice. Entry = es.EarlySignalTracker logic (|z|>=enter_z
    AND |imb|>=min_conv), verified identical to the tracker. trail/maxhold tune the exit. Returns net bps."""
    n = len(imb); hist = deque(maxlen=ROLL); pos = None; pnl = []
    for i in range(n):
        z = 0.0
        if len(hist) >= 5:
            m = sum(hist) / len(hist)
            sd = max((sum((v - m) ** 2 for v in hist) / len(hist)) ** 0.5, SD_FLOOR)
            z = (imb[i] - m) / sd
        hist.append(imb[i])
        if pos is None:
            if abs(z) >= enter_z and abs(imb[i]) >= min_conv:
                pos = {"d": (ds if z > 0 else -ds), "entry": mid[i], "best": 0.0, "t": 0}
        else:
            pos["t"] += 1
            fav = pos["d"] * (mid[i] - pos["entry"]) / pos["entry"] * 1e4
            pos["best"] = max(pos["best"], fav)
            if (pos["best"] - fav) >= trail or pos["t"] >= maxhold:
                pnl.append(fav - fee); pos = None
    return np.array(pnl)


def dph(p, hours):
    return p.sum() / 1e4 * CAP / hours if len(p) else 0.0


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "btc"
    imb, mid = series_1s(f"/tmp/kbook/{coin}_book.jsonl")
    n = len(imb); cut = int(n * 0.6)
    tr_h, te_h = cut / 3600.0, (n - cut) / 3600.0
    imb_tr, mid_tr, imb_te, mid_te = imb[:cut], mid[:cut], imb[cut:], mid[cut:]

    print(f"=== {coin.upper()} WALK-FORWARD 60/40 — train {tr_h:.1f}h / test {te_h:.1f}h ===", flush=True)
    # TRAIN: joint grid over (sign-fit HORIZON, min_conv, enter_z, trail, maxhold); pick MAX train $/hr @0%
    # maker (>=10 trades). The sign-fit horizon is PER-CELL (Greg S77: small caps lead price at their own
    # look-ahead, mostly 120-300s vs majors' 60s) — each coin auto-picks it on TRAIN. 60 stays a candidate so
    # majors don't regress. min_conv swept so flat-book coins still enter. OBJECTIVE = MAX $/hr, count irrelevant.
    hfits = {}
    for hz in (30, 60, 120, 300):
        f = es.fit_direction_sign(imbalances=imb_tr.tolist(), mids=mid_tr.tolist(), horizon=hz, min_conviction=MINCONV)
        hfits[hz] = f["sign"]
    best = None
    for hz, ds in hfits.items():
        for mc in (0.0, 0.2, 0.3, 0.5):
            for ez in (1.0, 1.5, 2.0):
                for trail in (10.0, 15.0, 20.0, 30.0):
                    for mh in (60, 300, 600):
                        p = swing(imb_tr, mid_tr, ds, ez, 0.0, trail, mh, min_conv=mc)
                        d = dph(p, tr_h)
                        if len(p) >= 10 and (best is None or d > best[0]):
                            best = (d, hz, ds, ez, trail, mh, mc)
    if best is None:
        print("  -> insufficient signal on train (book too flat; no config with >=10 trades)\nDONE", flush=True)
        return
    _, hz, ds, ez, trail, mh, mc = best
    print(f"  -> TRAIN picks horizon={hz}s sign={ds:+d} enter_z={ez:.1f} minconv={mc:.1f} trail={trail:.0f} "
          f"maxhold={mh}s (train $/hr@0={best[0]:.2f})\n", flush=True)

    # TEST: frozen (hz, ds, ez, trail, mh, mc), report OOS
    print(f"  TEST (OOS, frozen horizon={hz}s sign={ds:+d} enter_z={ez:.1f} minconv={mc:.1f} trail={trail:.0f} hold={mh}s):", flush=True)
    print(f"  {'fee':>5}{'trades':>7}{'/hr':>6}{'win%':>7}{'bps/trd':>9}{'$/hr':>9}", flush=True)
    for fee in (0.0, 5.0):
        p = swing(imb_te, mid_te, ds, ez, fee, trail, mh, min_conv=mc)
        if len(p) < 3:
            print(f"  {fee:>5.0f}{len(p):>7}   (too few)", flush=True); continue
        print(f"  {fee:>5.0f}{len(p):>7}{len(p)/te_h:>6.1f}{(p>0).mean()*100:>7.1f}{p.mean():>9.3f}{dph(p, te_h):>9.3f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
