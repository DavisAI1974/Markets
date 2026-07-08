"""S76: the paper's RIDE-TO-REVERSAL directional swing, driving Greg's ACTUAL early_signal.EarlySignalTracker
(his tested code — not a reimplementation) on our Kraken books (BTC/ETH).

Feed each 1s book snapshot to the tracker; when it says ENTER, open a position in sig.direction; ride the
~60s move; EXIT on the documented wide trailing stop (TRAIL_BPS_DEFAULT=30) or the max hold
(MAX_HOLD_S_DEFAULT=600). Mid-price directional P&L at 0% maker and at a taker cost. One position at a time.
The book's directional edge is a SEPARATE strategy from the maker zigzag (it's a coin-flip on the maker legs).

    python3 book_swing_kraken.py <btc|eth>
"""
import os, sys, json, types
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es                         # Greg's file — use it as-is

CAP = 5000.0
STRIDE = 10                                       # 100ms book -> 1s grid
DIR_SIGN = {"btc": +1, "eth": +1, "xrp": +1, "sol": +1, "doge": -1}
TRAIL = es.TRAIL_BPS_DEFAULT                       # 30 bps (documented ride-to-reversal stop)
MAXHOLD = es.MAX_HOLD_S_DEFAULT                    # 600 s


def run(coin, enter_z, min_conv, fee):
    """Drive es.EarlySignalTracker over the book; ride-to-reversal exit. Returns (pnl bps array, hours)."""
    path = f"/tmp/kbook/{coin}_book.jsonl"
    ds = DIR_SIGN.get(coin, +1)
    trk = es.EarlySignalTracker(k=es.DEFAULT_K, roll=es.DEFAULT_ROLL, enter_z=enter_z,
                                direction_sign=ds, min_conviction=min_conv)
    pos = None; pnl = []; nsnap = 0
    with open(path) as f:
        for i, line in enumerate(f):
            if i % STRIDE:
                continue
            r = json.loads(line); m = float(r["mid"])
            bids = [[m + float(o), float(s)] for o, s in r["bids"]]     # tracker takes the top-k itself
            asks = [[m + float(o), float(s)] for o, s in r["asks"]]
            sig = trk.update(bids, asks, mid=m)
            nsnap += 1
            if pos is None:
                if sig.enter and sig.direction != 0:
                    pos = {"d": sig.direction, "entry": m, "best": 0.0, "t": 0}
            else:
                pos["t"] += 1
                fav = pos["d"] * (m - pos["entry"]) / pos["entry"] * 1e4
                pos["best"] = max(pos["best"], fav)
                if (pos["best"] - fav) >= TRAIL or pos["t"] >= MAXHOLD:
                    pnl.append(fav - fee); pos = None
    return np.array(pnl), nsnap / 3600.0


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "btc"
    print(f"=== {coin.upper()} — es.EarlySignalTracker ride-to-reversal (trail {TRAIL:.0f} / hold {MAXHOLD}s) ===", flush=True)
    print(f"  {'enter_z':>7}{'minconv':>8}{'fee':>5}{'trades':>7}{'/hr':>6}{'win%':>7}{'bps/trd':>9}{'$/hr':>9}", flush=True)
    for ez in (2.0, 3.0, 4.0):
        for mc in (0.5,):
            for fee in (0.0, 5.0):
                p, hours = run(coin, ez, mc, fee)
                if len(p) < 3:
                    print(f"  {ez:>7.1f}{mc:>8.1f}{fee:>5.0f}{len(p):>7}   (too few)", flush=True); continue
                print(f"  {ez:>7.1f}{mc:>8.1f}{fee:>5.0f}{len(p):>7}{len(p)/hours:>6.1f}"
                      f"{(p>0).mean()*100:>7.1f}{p.mean():>9.3f}{p.sum()/1e4*CAP/hours:>9.3f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
