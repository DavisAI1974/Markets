"""_s49_window_confirm.py — S49 2nd-window confirmation.

Segments paper_ledger.jsonl by entry ts into:
  W1  = the original S46/S47 window  [book start .. 2026-06-29 23:29 UTC]
  W2  = fresh forward / out-of-sample [2026-06-29 23:29 .. now]
(plus a btc-only deep history, which spans 8 days, segmented at its own midpoint for a fair split).

For each cell x window reports the deployable profile:
  n, flat_net (sum net_bps), sized_net (sum sized_net), net/leg, win%, taker% (1-maker_close), mean size_mult.

THE GATE: does the per-cell profile (net-of-fee sign, low taker% under cover-grace, sizing lift) REPRODUCE
out-of-sample on W2? Per-cell deploy rule — partial coverage is not failure.
"""
import json, os, datetime
import numpy as np

LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper_ledger.jsonl")
# end of the S46/S47 window (UTC)
BOUND = datetime.datetime(2026, 6, 29, 23, 29, 0, tzinfo=datetime.timezone.utc).timestamp()

rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
coins = ["sol", "doge", "xrp", "eth", "btc"]

def prof(rs):
    if not rs:
        return None
    n = len(rs)
    fn = sum(r["net_bps"] for r in rs)
    sn = sum(r["sized_net"] for r in rs)
    win = 100 * np.mean([r["net_bps"] > 0 for r in rs])
    tk = 100 * np.mean([not r["maker_close"] for r in rs])
    msz = float(np.mean([r["size_mult"] for r in rs]))
    return dict(n=n, fn=fn, sn=sn, npl=fn / n, snpl=sn / n, win=win, tk=tk, msz=msz)

def line(tag, p):
    if p is None:
        print(f"  {tag:14s}  (no trades)"); return
    print(f"  {tag:14s} n={p['n']:>5}  flat={p['fn']:>+9.1f} ({p['npl']:>+5.2f}/leg)  "
          f"sized={p['sn']:>+9.1f} ({p['snpl']:>+5.2f}/leg)  win={p['win']:>4.0f}%  "
          f"taker={p['tk']:>4.0f}%  sz={p['msz']:.2f}")

print(f"=== S49 2nd-window confirmation ===  boundary = 2026-06-29 23:29 UTC")
print(f"ledger: {len(rows)} rows\n")
for c in coins:
    rs = [r for r in rows if r["coin"] == c]
    if not rs:
        print(f"[{c}] none\n"); continue
    w1 = [r for r in rs if r["ts"] <= BOUND]
    w2 = [r for r in rs if r["ts"] > BOUND]
    tmin = datetime.datetime.utcfromtimestamp(min(r["ts"] for r in rs))
    tmax = datetime.datetime.utcfromtimestamp(max(r["ts"] for r in rs))
    print(f"[{c}]  {tmin} .. {tmax}")
    p1, p2 = prof(w1), prof(w2)
    line("W1 (in-samp)", p1)
    line("W2 (FRESH/OOS)", p2)
    # reproduction verdict
    if p1 and p2:
        repro_sign = (p1["npl"] > 0) == (p2["npl"] > 0)
        sizing_lift_w2 = p2["snpl"] - p2["npl"]
        print(f"    -> net/leg sign reproduces: {repro_sign} | W2 sizing lift/leg: {sizing_lift_w2:+.2f} | "
              f"W2 taker {p2['tk']:.0f}% (grace target ~0)")
    print()
