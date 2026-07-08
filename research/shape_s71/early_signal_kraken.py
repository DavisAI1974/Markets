"""Realize the book early-signal PER KRAKEN CELL (Greg's fit_direction_sign usage).

Our Kraken L2 books are a 100ms grid; downsample to a 1s grid so horizon=60 == 60s forward (matching the
early_signal provenance), then fit direction_sign at horizon=60, min_conviction=0.5 per coin. Reports the
fitted sign + directional hit_rate + mean_signed_bps + the per-cell weight (HIGH/LOW/ZERO-flat).

    sgn = +1 if mean(sign(imb_t) * ret_{t->t+60s}) >= 0 else -1   (Greg)

Uses early_signal.book_imbalance + fit_direction_sign VERBATIM (no reimplementation). Book = fills/direction,
scalar depth read — the entry FILTER/direction, to be STACKED with the shape work. Per coin: python3
early_signal_kraken.py <coin>.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import early_signal as es

K = 10
STRIDE = 10          # 100ms Kraken book -> 1s grid (take every 10th snapshot)
HORIZON = 60         # 60 steps @ 1s = 60s forward (Greg's spec)
MINCONV = 0.5


def stream_imb_1s(path, k=K, stride=STRIDE):
    """Stream the book jsonl (memory-light), downsample to 1s, compute the proximity-weighted imbalance +
    mid per snapshot. Book levels are [offset_from_mid, size] -> reconstruct price = mid + offset."""
    imb, mids = [], []
    with open(path) as f:
        for i, line in enumerate(f):
            if i % stride:
                continue
            r = json.loads(line)
            mid = float(r["mid"])
            bids = [[mid + float(o), float(s)] for o, s in r["bids"][:k]]
            asks = [[mid + float(o), float(s)] for o, s in r["asks"][:k]]
            bk = es.book_imbalance(bids, asks, k, mid)
            imb.append(bk["imb"] if bk["ok"] else 0.0)
            mids.append(mid)
    return imb, mids


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    path = f"/tmp/kbook/{coin}_book.jsonl"
    imb, mids = stream_imb_1s(path)
    print(f"=== {coin.upper()} Kraken book early-signal — {len(imb)} snaps @1s ({len(imb)/3600:.1f}h) ===", flush=True)
    for mc in (0.0, MINCONV):
        r = es.fit_direction_sign(imbalances=imb, mids=mids, horizon=HORIZON, min_conviction=mc)
        hr = r["hit_rate"]; mb = r["mean_signed_bps"]
        print(f"  min_conv={mc:.1f} @60s: sign={r['sign']:+d}  hit_rate={hr:.3f}  "
              f"mean_signed_bps={mb:+.3f}  n={r['n']}  -> {r['recommend']}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
