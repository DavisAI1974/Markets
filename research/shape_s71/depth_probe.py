"""S77: book DEPTH + trade TURNOVER per coin (Kraken) — is a small-cap's look-ahead actually fillable?

A fat forward-bps is only money if the book has depth to rest real maker size AND enough turnover for a
resting maker to fill. Reads the Kraken book (ts,mid,spread,bids,asks,buy,sell,n_trades). Reports, in $:
  top$      : median top-of-book $ resting = (best_bid_sz + best_ask_sz)/2 * mid   (what a maker fills first)
  depth10$  : median total 10-level $ resting per side                              (queue behind the touch)
  turn$/hr  : traded $ per hour = sum((buy+sell)*mid) / hours                       (fill speed / capacity)
  spread_bp : median spread in bps                                                  (mid-price P&L overstatement)
No decisions here (pure measurement); one pass, turnover over every line, depth sampled every `stride`.

    python3 depth_probe.py [coin ...]     # default: 16 small caps + btc/eth for scale
"""
import os, sys, json
import numpy as np

STRIDE = 10
DEFAULT = "btc eth aave ada avax bch bnb hype link ltc near sui tao ton xlm xmr xpl zec".split()


def run(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"
    if not os.path.exists(path):
        return None
    tops, d10s, spr = [], [], []
    turn = 0.0; hours = 0; first_ts = last_ts = None; nlines = 0
    with open(path) as f:
        for i, line in enumerate(f):
            r = json.loads(line); m = float(r["mid"]); nlines += 1
            if first_ts is None: first_ts = r.get("ts")
            last_ts = r.get("ts")
            turn += (float(r.get("buy", 0.0)) + float(r.get("sell", 0.0))) * m   # every line
            if i % STRIDE:
                continue
            b, a = r["bids"], r["asks"]
            tops.append((float(b[0][1]) + float(a[0][1])) / 2 * m)
            d10s.append((sum(float(s) for _, s in b[:10]) + sum(float(s) for _, s in a[:10])) / 2 * m)
            spr.append(float(r.get("spread", 0.0)) / m * 1e4)
    # hours from ts if parseable else from 1s-grid line count
    try:
        hours = (float(last_ts) - float(first_ts)) / 3600.0
    except (TypeError, ValueError):
        hours = nlines / 10.0 / 3600.0  # ~100ms raw grid
    if hours <= 0:
        hours = nlines / 10.0 / 3600.0
    return {
        "coin": coin, "hours": hours,
        "top$": float(np.median(tops)), "depth10$": float(np.median(d10s)),
        "turn$/hr": turn / hours, "spread_bp": float(np.median(spr)),
    }


if __name__ == "__main__":
    coins = sys.argv[1:] or DEFAULT
    rows = [r for c in coins if (r := run(c))]
    rows.sort(key=lambda r: r["depth10$"], reverse=True)
    print(f"{'coin':>6}{'hrs':>6}{'top$':>10}{'depth10$':>11}{'turn$/hr':>13}{'spread_bp':>11}")
    for r in rows:
        print(f"{r['coin'].upper():>6}{r['hours']:>6.1f}{r['top$']:>10,.0f}{r['depth10$']:>11,.0f}"
              f"{r['turn$/hr']:>13,.0f}{r['spread_bp']:>11.2f}")
