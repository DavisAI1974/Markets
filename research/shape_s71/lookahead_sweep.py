"""S77: per-coin LOOK-AHEAD sweep — does the book lead price on the small caps, and at what horizon?

The majors have a documented look-ahead (BTC book leads +1s; the tradeable signal lives at ~60s). This
sweeps `es.fit_direction_sign` horizon per coin on the Kraken book to locate each cell's look-ahead:
the forward horizon where a strong book lean best predicts the price move (max forward |bps| with a
reliable hit-rate). Honest OOS check: fit the sign on TRAIN (first 60%), confirm TEST (last 40%) picks
the SAME sign and stays positive — a look-ahead only counts if train/test agree. Live code only
(reuses book_swing_kraken.series_1s + es.fit_direction_sign; no reimplementation).

    python3 lookahead_sweep.py [coin ...]      # default: all 21
"""
import os, sys, json, types
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es
from book_swing_kraken import series_1s

HORIZONS = (1, 2, 5, 10, 15, 30, 60, 120, 300)   # grid steps == seconds (1s grid)
MINCONV = 0.5                                     # strong leans only (the tradeable book)
ALL = "btc eth sol xrp doge aave ada avax bch bnb hype link ltc near sui tao ton xlm xmr xpl zec".split()


def run(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"
    if not os.path.exists(path):
        print(f"{coin.upper():6} (no book)"); return
    imb, mid = series_1s(path)
    n = len(imb); cut = int(n * 0.6)
    imb_tr, mid_tr, imb_te, mid_te = imb[:cut], mid[:cut], imb[cut:], mid[cut:]
    print(f"=== {coin.upper()}  ({n/3600:.1f}h book, train {cut/3600:.1f}h / test {(n-cut)/3600:.1f}h) ===")
    print(f"  {'horizon':>8}{'tr_sign':>8}{'te_sign':>8}{'agree':>7}{'tr_hit':>8}{'te_hit':>8}{'te_bps':>9}{'te_n':>8}")
    best = None
    for h in HORIZONS:
        ftr = es.fit_direction_sign(imbalances=imb_tr.tolist(), mids=mid_tr.tolist(), horizon=h, min_conviction=MINCONV)
        fte = es.fit_direction_sign(imbalances=imb_te.tolist(), mids=mid_te.tolist(), horizon=h, min_conviction=MINCONV)
        agree = (ftr["sign"] == fte["sign"]) and ftr["n"] > 0 and fte["n"] > 0
        trh, teh = ftr["hit_rate"], fte["hit_rate"]
        teb, ten = fte["mean_signed_bps"], fte["n"]
        mark = ""
        # a real look-ahead: train/test agree on sign AND test forward-bps positive AND reliable hit
        if agree and teb == teb and teb > 0 and teh >= 0.52 and ten >= 30:
            mark = " *"
            if best is None or teb > best[1]:
                best = (h, teb, teh, ten)
        def f(x): return f"{x:.3f}" if x == x else "  nan"
        print(f"  {h:>8}{ftr['sign']:>+8}{fte['sign']:>+8}{str(agree):>7}{f(trh):>8}{f(teh):>8}{f(teb):>9}{ten:>8}{mark}")
    if best:
        print(f"  -> LOOK-AHEAD ~{best[0]}s : test fwd +{best[1]:.2f} bps @ hit {best[2]:.3f} (n={best[3]}) on strong leans")
    else:
        print(f"  -> NO robust look-ahead (no horizon with train/test sign-agree + positive OOS fwd-bps)")
    print()


if __name__ == "__main__":
    coins = sys.argv[1:] or ALL
    for c in coins:
        run(c)
