"""_s63_kraken_makerfill.py — THE MAKER-FILL MODEL: does the ride's 0bp fill actually happen on Kraken?

The whole S63 Kraken edge assumes we get 0bp MAKER fills at the turns. This grades that on the real
Kraken L2 BOOK (data/*-kraken-book, ~18-23h/coin) via the honest queue-fill executor
`odcore.swing_maker.simulate_swing_maker(fill_model="queue")`: a maker post at the turn fills only when
cumulative opposing taker volume trades through the displayed best-level size ahead of us; else it
falls back to a TAKER cross. Compares, per coin:
  IDEAL (fill_model="front", any next opposing print fills us) — the paper assumption
  HONEST (fill_model="queue", must trade through the real best-level size) — reality
Reports fill_rate, taker-close %, net/leg, $/hr @ $5k. The gap = the real fill cost. SOL = reversed.

NB: the BOOK window (~18-23h, one regime) is NOT the 30d tape — the $/hr won't match the tape numbers;
what transfers is the FILL MECHANICS (do we get filled at maker, how often we bleed to taker).

Usage:  python scripts/_s63_kraken_makerfill.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.swing_maker import simulate_swing_maker                   # noqa: E402

CAP = 5000.0; WFLIP, REV = 600, 0.1
KBOOK = "/tmp/kbook"
CELLS = [("eth", 0), ("btc", 0), ("sol", 1)]        # (coin, reversed)
MAKER_FEE = 0.0        # kr_mk0
TAKER_FEE = 5.0        # Kraken taker fallback (representative)


def load_book_1s(path):
    """Parse the L2 book jsonl -> uniform 1-sec arrays: mid, best_bid_sz, best_ask_sz, buy, sell, hs_bps."""
    ts_l, mid_l, bb_l, ba_l, buy_l, sell_l, sp_l = [], [], [], [], [], [], []
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts_l.append(d["ts"]); mid_l.append(d["mid"]); sp_l.append(d.get("spread", 0.0))
            bb_l.append(d["bids"][0][1] if d.get("bids") else 0.0)
            ba_l.append(d["asks"][0][1] if d.get("asks") else 0.0)
            buy_l.append(d.get("buy", 0.0)); sell_l.append(d.get("sell", 0.0))
    ts = np.array(ts_l); sec = ts.astype(np.int64)
    t0, t1 = sec.min(), sec.max(); n = int(t1 - t0) + 1
    mid = np.zeros(n); bb = np.zeros(n); ba = np.zeros(n); buy = np.zeros(n); sell = np.zeros(n)
    sp = np.zeros(n); have = np.zeros(n, bool)
    mid_a = np.array(mid_l); bb_a = np.array(bb_l); ba_a = np.array(ba_l)
    buy_a = np.array(buy_l); sell_a = np.array(sell_l); sp_a = np.array(sp_l)
    idx = (sec - t0).astype(int)
    for i in range(len(idx)):
        j = idx[i]
        mid[j] = mid_a[i]; bb[j] = bb_a[i]; ba[j] = ba_a[i]; sp[j] = sp_a[i]  # last wins
        buy[j] += buy_a[i]; sell[j] += sell_a[i]; have[j] = True
    # forward-fill mid/book/spread over empty seconds
    fi = np.where(have, np.arange(n), 0); np.maximum.accumulate(fi, out=fi)
    first = int(np.argmax(have))
    for arr in (mid, bb, ba, sp):
        arr[:] = arr[fi]; arr[:first] = arr[first]
    hs_bps = np.median((sp[mid > 0] / mid[mid > 0]) / 2.0) * 1e4
    return mid, bb, ba, buy, sell, float(hs_bps), n / 3600.0


def run(mid, bb, ba, buy, sell, hs, hrs, rev, fill_model):
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    if rev:
        flips = [(ci, pv, -s) for (ci, pv, s) in flips]
    r = simulate_swing_maker(mid, bb, ba, buy, sell, flips,
                             half_spread_bps=hs, maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                             fill_model=fill_model, queue_frac=1.0)
    return r


def main():
    print("=== KRAKEN MAKER-FILL MODEL — does the 0bp maker fill actually happen? (real L2 book) ===")
    print(f"   maker_fee={MAKER_FEE} taker_fallback={TAKER_FEE}bp; $/hr @ $5k over the book window\n")
    print(f"{'coin':6}{'hrs':>6}{'hs_bp':>7}{'flips':>7} | "
          f"{'IDEAL$/h':>9}{'fill%':>7} || {'HONEST$/h':>10}{'fill%':>7}{'takerCl%':>9}{'net/leg':>9}")
    for coin, rev in CELLS:
        path = f"{KBOOK}/{coin}_book.jsonl"
        if not os.path.exists(path):
            print(f"{coin:6} (no book)"); continue
        mid, bb, ba, buy, sell, hs, hrs = load_book_1s(path)
        ideal = run(mid, bb, ba, buy, sell, hs, hrs, rev, "front")
        honest = run(mid, bb, ba, buy, sell, hs, hrs, rev, "queue")
        idph = ideal.total_net_bps / 1e4 * CAP / hrs
        hdph = honest.total_net_bps / 1e4 * CAP / hrs
        tk = 100 * honest.n_taker_closes / honest.n_legs if honest.n_legs else 0.0
        tag = f"{coin}{'*' if rev else ''}"
        print(f"{tag:6}{hrs:>6.1f}{hs:>7.2f}{ideal.n_flips:>7} | "
              f"{idph:>+9.2f}{100*ideal.fill_rate:>6.0f}% || {hdph:>+10.2f}{100*honest.fill_rate:>6.0f}%"
              f"{tk:>8.0f}%{honest.net_per_leg_bps:>+9.2f}")
    print("\n  IDEAL = any next opposing print fills us (paper). HONEST = must trade through the real")
    print("  best-level size (queue). fill% = flips that got a maker fill; takerCl% = closes forced to taker.")
    print("  * = SOL reversed. Book window ~18-23h (NOT the 30d tape) — read the FILL MECHANICS, not $/hr.")


if __name__ == "__main__":
    main()
