"""_s66_dynamic_fill_kraken.py — the DYNAMIC front-of-line FOLLOWING-maker fill model (Greg S66).

The S66 static capacity cap (odcore.capacity, opposing flow at a FIXED limit) is too pessimistic: a real
front-of-line maker RE-QUOTES to follow the price ("move that number with the direction") and accumulates
its full size, or steps out ("go out of front of line"). This models that honestly: accumulate opposing
flow over the entry window at the MOVING best price, track the VWAP entry (following costs a worse avg
price), causal adverse-pull if the excursion from VWAP exceeds a stop. Recompute net at the VWAP entry.
Exit assumed at the executor's close_px (entry is the tighter side). CAUSAL — no pre-post flow.

Result (Kraken 30d tape, D=$5k): fills ~100% (not the static cap's $15) but VWAP-diluted -> ETH +0.45,
BTC +1.35 positive; SOL/XRP/DOGE ~0/negative. Bracketed: static-cap (too pessimistic) < THIS < uncapped
(too optimistic). Assumptions to pin on the BOOK: instant re-quote (no latency), climax concentration at
the turn, exit fill. The 'go out of losers' asymmetry needs early direction (dead) -> a causal stop barely helps.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                    # noqa: E402
from odcore.platform import KRAKEN, run_kraken_cell          # noqa: E402

PAIR = {"eth": "ETHUSD", "btc": "XBTUSD", "sol": "SOLUSD", "xrp": "XRPUSD", "doge": "XDGUSD"}
BINS = "/tmp/ktape"


def dynamic_fill(legs, m, b, s, desired, stop_bps):
    pnl, ff = [], []
    for l in legs:
        o, c, side = int(l.open_idx), int(l.close_idx), int(l.side)
        opp = (s if side > 0 else b)
        cost = 0.0; coin = 0.0; rem = desired
        for t in range(o, min(c + 1, len(m))):
            px = float(m[t])
            if coin > 0:
                vwap = cost / coin
                if side * (px - vwap) / vwap * 1e4 < -stop_bps:   # adverse -> pull (causal)
                    break
            take = min(rem, float(opp[t]) * px)
            if take > 0:
                cost += take; coin += take / px; rem -= take
            if rem <= 0:
                break
        if coin <= 0:
            pnl.append(0.0); ff.append(0.0); continue
        vwap = cost / coin
        nb = side * (float(l.close_px) - vwap) / vwap * 1e4
        pnl.append(nb / 1e4 * cost); ff.append(cost / desired)
    return np.array(pnl), np.array(ff)


def main():
    D = 5000.0
    print(f"DYNAMIC following-maker (VWAP entry + causal adverse-pull), D=${int(D)}, Kraken 30d tape:")
    print(f"{'coin':5}{'uncap $/hr':>12}   " + "   ".join(f"stop{st}: $/hr(fill%)" for st in (40, 80, 150)))
    for cfg in KRAKEN:
        p = f"{BINS}/{PAIR[cfg.coin]}_30d_bins.json"
        if not os.path.exists(p):
            continue
        m, b, s, cov, hrs = load_bins(p)
        m = np.asarray(m, float); b = np.asarray(b, float); s = np.asarray(s, float); n = len(m)
        z = np.zeros(n)
        res, _ = run_kraken_cell(cfg, m, b, s, z, z, 0.0)
        legs = res.legs; H = n / 3600.0
        uncap = float(np.sum(np.array([l.net_bps for l in legs]) / 1e4 * D)) / H
        row = f"{cfg.coin:5}{uncap:>+12.2f}   "
        for st in (40, 80, 150):
            pnl, ff = dynamic_fill(legs, m, b, s, D, st)
            row += f"   {pnl.sum() / H:+7.2f} ({np.median(ff) * 100:3.0f}%)"
        print(row)


if __name__ == "__main__":
    main()
