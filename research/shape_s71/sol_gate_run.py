"""S73 GATE RUNNER (selection logic only — reuses the agent's ORIGINAL shape builder arc_gate.py; builds
NO shapes itself). Functionally-correct entry gate on SOL: match each forming trade to the INDIVIDUAL
pre-onset curve shapes (k nearest, no averaging, no AUC), assign the nearest archetype, and DON'T FIRE on
the loser shapes. LIVE lean+exit (run_kraken_cell), one-sided maker, no deep-bail, $5k every fired signal.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,   # the agent's builder
                      run_kraken_cell, KRAKEN, PRE, CPS, PRE_SEC)
SMOOTH_SEC = 20            # same trailing flow smoothing as the agent's builder
CAP = 5000.0              # $5k per fired trade

def extract_sol():
    """Use the agent's builder to run SOL through the LIVE executor and lift each leg's pre-onset arc."""
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    print(f"  SOL cfg (strategy doc/KRAKEN): side={cfg.side} rev={cfg.rev} bail={cfg.bail} grace={cfg.grace} "
          f"improve={cfg.improve}  (no deep-bail; one-sided maker; exit=flow turn+cover-grace)", flush=True)
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; N = len(mid); hours = N * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)          # LIVE decision path, verbatim
    imb = rolling_imb(buy, sell, SMOOTH_SEC)                            # agent's flow builder
    pre_arcs, net, dur = [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx)
        if o - PRE < 0 or c <= o:
            continue
        pre = imb[o-PRE:o+1] * int(l.side)                             # strictly pre-onset curve (leakage-free)
        pre_arcs.append(pre); net.append(float(l.net_bps)); dur.append((c-o)*0.1)
    return np.array(pre_arcs), np.array(net), np.array(dur), hours, len(res.legs)

def knn_bucket(A_ref, buk_ref, A_q, k, exclude_self=False):
    """Assign each query CURVE the majority archetype among its k nearest INDIVIDUAL reference curves
    (matched on the full pre-onset arc — the exact shape; nothing averaged). k = the wiggle room."""
    q2 = (A_q**2).sum(1)[:, None]; r2 = (A_ref**2).sum(1)[None, :]
    d = q2 + r2 - 2.0 * A_q @ A_ref.T
    if exclude_self:
        np.fill_diagonal(d, np.inf)
    idx = np.argpartition(d, k, axis=1)[:, :k]
    neigh = buk_ref[idx]
    return np.array([np.bincount(row, minlength=4).argmax() for row in neigh])

def report(net, keep, hours, tag):
    ung = net.sum(); g = net[keep].sum(); nk = int(keep.sum()); n = len(net)
    wa = (net > 0).mean(); wk = (net[keep] > 0).mean() if nk else float("nan")
    print(f"    [{tag}]  UNGATED win%={wa*100:.1f} $/hr={ung/1e4*CAP/hours:6.3f}  ->  "
          f"GATED win%={wk*100:.1f} $/hr={g/1e4*CAP/hours:6.3f}  fired={nk}/{n} ({keep.mean()*100:.0f}%)  "
          f"PnL-ret={100*g/ung if ung else float('nan'):.0f}%", flush=True)

def main():
    print("=== S73 GATE RUNNER — SOL, individual-curve shape match, SKIP loser shapes (agent builder) ===", flush=True)
    A, net, dur, hours, n_all = extract_sol()
    n = len(A)
    print(f"  SOL legs (all $5k): {n} of {n_all}  (~{hours:.1f}h)", flush=True)
    win = net > 0; med = np.median(dur); short = dur < med
    # bucket per leg: 0=SHORT-WIN 1=LONG-WIN 2=SHORT-LOSE 3=LONG-LOSE  (losers=2,3)
    buk = np.where(win & short, 0, np.where(win & ~short, 1, np.where(~win & short, 2, 3)))
    print(f"  baseline: win%={win.mean()*100:.1f}  |  buckets  SW={int((buk==0).sum())} LW={int((buk==1).sum())} "
          f"SL={int((buk==2).sum())} LL={int((buk==3).sum())}\n", flush=True)
    cut = int(n*0.6); tr = slice(0, cut); te = slice(cut, n); hte = hours*(n-cut)/n
    for k in (11, 21, 41):
        print(f"  --- wiggle k={k} nearest individual curves ---", flush=True)
        b_is = knn_bucket(A, buk, A, k, exclude_self=True)                       # in-sample (leave-one-out)
        b_oos = knn_bucket(A[tr], buk[tr], A[te], k)                             # OOS (train ref / test query)
        for name, drop in [("skip SHORT-LOSE", {2}), ("skip BOTH losers", {2, 3})]:
            report(net, ~np.isin(b_is, list(drop)), hours, f"IN-SAMPLE  {name}")
            report(net[te], ~np.isin(b_oos, list(drop)), hte, f"OOS-40%    {name}")
        print("", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
