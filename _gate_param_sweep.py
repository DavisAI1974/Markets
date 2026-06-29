"""_gate_param_sweep.py — lock the QuietFloor gate operating point on the existing btc book (S44/prep).

The gate has two free knobs and a hold: depth-K (which top-K depth imbalance is the LEVEL), the gate
threshold k (fire when |innovation| > k*sigma), and the hold horizon for the direction read. S43/S44
used K=5 (maker) and K=10 (gate wiring) ad hoc. This sweeps them on the frozen 1.68M-cell btc_coinbase
book to pick a principled per-cell default, BEFORE the alt books arrive.

Objective (leakage-safe; QuietFloor fit on TRAIN quiet cells, metrics on the held-out TEST slice):
  - keep DIRECTION: gated OOS next-cell sign-agreement hit-rate should stay >= the raw-level hit;
  - cut CHURN: gated fire-rate << raw (raw fires ~100% of cells on a continuous book);
  - be SELECTIVE: gate should open more on trade/shock cells than quiet cells (ratio > 1).
Pick: the (K, k) that maximizes the gated hit subject to a usable fire-rate (>= MIN_FIRE).

Run: python _gate_param_sweep.py [path]   (default /tmp/od_book.jsonl.gz)
"""
from __future__ import annotations

import json
import sys

import numpy as np

from _birth_probe import load_book, to_grid
from _liquidity_dive import fwd_cum_return
from odcore.quiet_floor import fit as fit_quiet

KS = [1, 3, 5, 10]
KGATES = [1.0, 1.5, 2.0, 2.5, 3.0]
HOLDS = [1, 5, 10]
TRAIN_FRAC = 0.6
MIN_FIRE = 0.02          # require >= 2% of test cells to fire, else too sparse to deploy


def hit(sig, fwd, cut, n):
    a = np.asarray(sig)[cut:n - 1]
    b = fwd[cut:n - 1]
    m = ~np.isnan(b)
    a, b = a[m], b[m]
    nz = (a != 0) & (b != 0)
    if not nz.any():
        return float("nan"), 0
    return float((np.sign(a) == np.sign(b))[nz].mean()), int(nz.sum())


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/od_book.jsonl.gz"
    g = to_grid(load_book(path), 0.1)
    mid = g["mid"]
    buy, sell = g["buy"], g["sell"]
    quiet = (buy + sell) <= 0.0
    n = len(mid)
    cut = int(n * TRAIN_FRAC)
    sret = np.nan_to_num(np.concatenate([[0.0], np.diff(np.log(np.where(mid > 0, mid, np.nan)))]))
    fwds = {h: fwd_cum_return(sret, h) for h in HOLDS}
    print(f"# btc book: {n:,} cells ({n*0.1/3600:.1f}h), quiet={100*quiet.mean():.1f}%, "
          f"train_frac={TRAIN_FRAC}, MIN_FIRE={MIN_FIRE}")

    results = []
    print(f"\n{'K':>3}{'k':>5}{'phi':>7}{'fire%':>7}{'sel(t/q)':>10}"
          f"{'raw_hit@1':>10}{'gated@1':>9}{'gated@5':>9}{'gated@10':>9}")
    for K in KS:
        bd, ad = g["bidK"][K], g["askK"][K]
        imb = (bd - ad) / (bd + ad + 1e-12)
        raw_h1, _ = hit(np.sign(imb), fwds[1], cut, n)
        for k in KGATES:
            qf = fit_quiet(imb, quiet, train_frac=TRAIN_FRAC)
            gated = qf.gated_signal(imb, k=k)
            gate_open = gated != 0
            te = slice(cut, n)
            fire = float(gate_open[te].mean())
            oq = float(gate_open[te][quiet[te]].mean()) if quiet[te].any() else float("nan")
            ot = float(gate_open[te][~quiet[te]].mean()) if (~quiet[te]).any() else float("nan")
            sel = ot / (oq + 1e-12)
            gh = {h: hit(gated, fwds[h], cut, n)[0] for h in HOLDS}
            row = dict(K=K, k=k, phi=qf.phi, sigma=qf.sigma, fire=fire, sel=sel,
                       raw_hit_h1=raw_h1, gated_hit={h: gh[h] for h in HOLDS})
            results.append(row)
            print(f"{K:>3}{k:>5.1f}{qf.phi:>7.3f}{100*fire:>7.1f}{sel:>10.2f}"
                  f"{100*raw_h1:>10.1f}{100*gh[1]:>9.1f}{100*gh[5]:>9.1f}{100*gh[10]:>9.1f}")

    # pick: max gated hit@1 subject to fire >= MIN_FIRE and selectivity > 1
    elig = [r for r in results if r["fire"] >= MIN_FIRE and r["sel"] > 1.0
            and not np.isnan(r["gated_hit"][1])]
    best = max(elig, key=lambda r: r["gated_hit"][1]) if elig else None
    if best:
        print(f"\n# BEST operating point (max gated hit@1 | fire>={MIN_FIRE}, sel>1): "
              f"K={best['K']} k={best['k']} -> fire={100*best['fire']:.1f}% sel={best['sel']:.2f} "
              f"gated_hit@1={100*best['gated_hit'][1]:.1f}% (raw {100*best['raw_hit_h1']:.1f}%)")
    else:
        print("\n# no eligible operating point (check MIN_FIRE / selectivity)")
    out = dict(path=path, n=n, train_frac=TRAIN_FRAC, min_fire=MIN_FIRE,
               grid=results, best=best)
    json.dump(json.loads(json.dumps(out, default=float)),
              open("_gate_param_sweep_results.json", "w"), indent=2)
    print("# wrote _gate_param_sweep_results.json")


if __name__ == "__main__":
    main()
