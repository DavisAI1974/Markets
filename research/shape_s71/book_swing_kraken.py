"""S76: the paper's RIDE-TO-REVERSAL directional swing on the book early-signal (BTC/ETH Kraken).

The book's directional edge (Kraken 60s hit BTC 71% / ETH 55%) is a SEPARATE signal from the maker zigzag
(it's a coin-flip on the maker legs' spread-driven win/lose). Monetize it the paper's way: ENTER on a strong
book lean (rolling z), RIDE the ~60s move, EXIT on a wide trailing-stop reversal or a max hold. Mid-price
directional P&L (the book predicts mid direction), at 0% maker and at a taker cost. One position at a time.

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
from arc_gate import KRAKEN  # noqa (just to confirm shared import path)

CAP = 5000.0
K = 10
STRIDE = 10                          # 100ms book -> 1s grid
DIR_SIGN = {"btc": +1, "eth": +1, "xrp": +1, "sol": +1, "doge": -1}
SD_FLOOR = 0.02


def series_1s(path, k=K, stride=STRIDE):
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


def swing(imb, mid, ds, enter_z, trail_bps, max_hold_s, roll, fee_bps):
    """Ride-to-reversal. One position at a time. Returns per-trade net bps (mid-price directional)."""
    n = len(imb); hist = deque(maxlen=roll); pos = None; pnl = []
    for i in range(n):
        z = 0.0
        if len(hist) >= 5:
            m = sum(hist) / len(hist)
            sd = max((sum((v - m) ** 2 for v in hist) / len(hist)) ** 0.5, SD_FLOOR)
            z = (imb[i] - m) / sd
        hist.append(imb[i])
        if pos is None:
            if abs(z) >= enter_z:
                d = ds if z > 0 else -ds                       # book lean -> direction (sign * dir_sign)
                pos = {"d": d, "entry": mid[i], "best": 0.0, "t0": i}
        else:
            fav = pos["d"] * (mid[i] - pos["entry"]) / pos["entry"] * 1e4
            pos["best"] = max(pos["best"], fav)
            if (pos["best"] - fav) >= trail_bps or (i - pos["t0"]) >= max_hold_s:
                pnl.append(fav - fee_bps); pos = None
    return np.array(pnl)


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "btc"
    path = f"/tmp/kbook/{coin}_book.jsonl"
    imb, mid = series_1s(path); ds = DIR_SIGN.get(coin, +1)
    hours = len(imb) / 3600.0
    print(f"=== {coin.upper()} BOOK RIDE-TO-REVERSAL swing — {len(imb)} snaps @1s ({hours:.1f}h), dir_sign={ds:+d} ===", flush=True)
    print(f"  {'enter_z':>7}{'trail':>7}{'maxhold':>8}{'fee':>5}{'trades':>7}{'win%':>7}{'bps/trd':>9}{'$/hr':>9}", flush=True)
    for ez in (1.0, 1.5, 2.0):
        for trail in (30.0, 50.0):
            for mh in (600, 60):
                for fee in (0.0, 5.0):
                    p = swing(imb, mid, ds, ez, trail, mh, 120, fee)
                    if len(p) < 5:
                        continue
                    dph = p.sum() / 1e4 * CAP / hours
                    print(f"  {ez:>7.1f}{trail:>7.0f}{mh:>8}{fee:>5.0f}{len(p):>7}"
                          f"{(p>0).mean()*100:>7.1f}{p.mean():>9.3f}{dph:>9.3f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
