"""S76: does the BOOK direction (early_signal) call the WINNING side at each leg's entry on BTC/ETH?

The book is HIGH on BTC/ETH (Kraken 60s hit 71% / 55%) and FLAT on SOL — so this is the direction lever
SOL never had. Run legs through the LIVE run_kraken_cell, read the proximity-weighted book imbalance at
each leg's entry (early_signal.book_imbalance verbatim), sign it by the fitted direction_sign, and test:
  (a) book-direction vs the leg's WINNING direction (accuracy),
  (b) FLIP the legs where the book OPPOSES the taken side (opposite trade ~= -gross) -> win%/$/hr,
  (c) trade ONLY when the book AGREES with the taken side (skip opposers).
Live-code only; book = fills/direction. Mid-price caveat on the flip P&L (uses -gross). Per coin:
  python3 book_direction_kraken.py <btc|eth>
"""
import os, sys, json, types
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:                     # arc_gate imports it at load; we never draw
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es
from arc_gate import load_raw, build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN

CAP = 5000.0
K = 10
STRIDE = 10                       # 100ms book -> 1s grid (the signal lives at ~60s)
DIR_SIGN = {"btc": +1, "eth": +1, "xrp": +1, "sol": +1, "doge": -1}   # fitted on Kraken (S75)


def book_imb_1s(path, k=K, stride=STRIDE):
    """Proximity-weighted top-K book imbalance on a 1s grid (index = second)."""
    imb = []
    with open(path) as f:
        for i, line in enumerate(f):
            if i % stride:
                continue
            r = json.loads(line); mid = float(r["mid"])
            bids = [[mid + float(o), float(s)] for o, s in r["bids"][:k]]
            asks = [[mid + float(o), float(s)] for o, s in r["asks"][:k]]
            bk = es.book_imbalance(bids, asks, k, mid)
            imb.append(bk["imb"] if bk["ok"] else 0.0)
    return np.array(imb)


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "btc"
    path = f"/tmp/kbook/{coin}_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; hours = len(mid) * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    imb = book_imb_1s(path); ds = DIR_SIGN.get(coin, +1)

    legs = res.legs
    net = np.array([float(l.net_bps) for l in legs]); gross = np.array([float(l.gross_bps) for l in legs])
    side = np.array([int(l.side) for l in legs])
    bidx = np.clip(np.array([int(l.open_idx) // STRIDE for l in legs]), 0, len(imb) - 1)
    book_dir = np.sign(imb[bidx]) * ds                       # +1 long / -1 short (the book's call at entry)
    win = net > 0; winning = np.where(win, side, -side)       # the side that WOULD have won
    dph = lambda v: v.sum() / 1e4 * CAP / hours

    print(f"=== {coin.upper()} BOOK-DIRECTION at entry — {len(legs)} legs, {hours:.1f}h (dir_sign={ds:+d}) ===", flush=True)
    print(f"  UNGATED: win%={win.mean()*100:.1f}  $/hr={dph(net):.3f}", flush=True)
    ok = book_dir != 0
    acc = (book_dir[ok] == winning[ok]).mean() * 100
    agree_taken = (book_dir == side)                          # book agrees with the side we actually took
    print(f"  book-dir vs WINNING side: {acc:.1f}% correct (n={ok.sum()})  |  "
          f"book agrees with taken side on {agree_taken.mean()*100:.0f}% of legs", flush=True)

    # (b) FLIP legs where the book OPPOSES the taken side
    opp = ok & (book_dir != side)
    v = net.copy(); v[opp] = -gross[opp]
    conv = (net[opp] < 0) & (-gross[opp] > 0)
    print(f"\n  (b) FLIP where book opposes taken side: flipped {opp.sum()}  "
          f"win%={ (v>0).mean()*100:.1f}  $/hr={dph(v):.3f}  (losers->winners {int(conv.sum())})", flush=True)

    # (c) trade ONLY when book agrees (skip opposers)
    keep = ~opp
    print(f"  (c) trade only when book AGREES: kept {keep.sum()}/{len(legs)}  "
          f"win%={ (net[keep]>0).mean()*100:.1f}  $/hr={dph(net[keep]):.3f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
