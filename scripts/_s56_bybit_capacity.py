"""_s56_bybit_capacity.py — QUEUE-HONEST capacity of the S56 sandbox cells (sol/eth bybit @MM3).

The number that turns the bins ceiling (+$112/hr/coin, 90%-maker blend assumption) into an honest
figure: the deployed executor on the REAL bybit books (true spread/depth/fills), with the S52
price-eligible flow-bounded fill cap — v1 front-of-queue vs v2 back-of-queue (S51 truth bracket).
Fees = MM3 (−1.25 maker / 5.5 taker), grace 300; std (+2.0) column for the no-program reference.

Usage: python scripts/_s56_bybit_capacity.py   (books in /tmp/<coin>_bybit_book.jsonl.gz)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                  # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps       # noqa: E402
from _capacity_model import _leg_caps, _leg_features, _dollars, FLOW_W, WFLIP, REV  # noqa: E402
from odcore.flip_detector import lean_series, detect_flips          # noqa: E402
from odcore.swing_maker import simulate_swing_maker, size_legs      # noqa: E402

REP_S = 5000.0
TIERS = (("mm3", -1.25, 5.5), ("std", 2.0, 5.5))


def cell(coin):
    path = f"/tmp/{coin}_bybit_book.jsonl.gz"
    if not os.path.exists(path):
        print(f"[{coin}] no book"); return
    raw = load_book(path)
    ch, g = build_channels(path, 1, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    caps = caps2 = None
    print(f"\n[{coin}_bybit] {hrs:.2f}h  half-spread {hs:.3f}bp")
    for label, mk, tk in TIERS:
        res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                   maker_fee_bps=mk, taker_fee_bps=tk, cover_grace=300)
        legs = res.legs
        if caps is None:
            caps, caps2 = _leg_caps(legs, mid, buy, sell, bb, ba)
            feats = _leg_features(legs, mid, sret, buy, sell, lean, piv)
        nets = np.asarray([float(l.net_bps) for l in legs])
        size_legs(legs, feats[0], feats[1], alpha=1.0, roll=200)
        sizes = np.asarray([float(l.size) for l in legs])
        ones = np.ones_like(sizes)
        tkpct = res.n_taker_closes / max(1, res.n_legs) * 100
        print(f"  {label:>4} (mk{mk:+.2f}): {res.n_legs} legs ({res.n_legs/hrs:.0f}/hr) "
              f"net/leg {res.net_per_leg_bps:+.2f}bp taker {tkpct:.1f}%")
        print(f"        v1 front-of-queue: flat ${_dollars(nets, ones, caps, hrs, REP_S):+.2f}/hr"
              f"  sized ${_dollars(nets, sizes, caps, hrs, REP_S):+.2f}/hr"
              f"  ceil ${_dollars(nets, ones, caps, hrs, 1e12):+.2f}/hr")
        print(f"        v2 QUEUE-HONEST  : flat ${_dollars(nets, ones, caps2, hrs, REP_S):+.2f}/hr"
              f"  sized ${_dollars(nets, sizes, caps2, hrs, REP_S):+.2f}/hr"
              f"  ceil ${_dollars(nets, ones, caps2, hrs, 1e12):+.2f}/hr")
    print(f"        med cap/leg v1 ${np.median(caps):,.0f} | v2 ${np.median(caps2):,.0f} | "
          f"v2 fillable {np.mean(caps2 > 0)*100:.0f}% of legs")


if __name__ == "__main__":
    for c in ("sol", "eth"):
        cell(c)
