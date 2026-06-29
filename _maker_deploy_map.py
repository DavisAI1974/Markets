"""_maker_deploy_map.py — turnkey PER-CELL maker+gate deploy map (S44 prep; the decisive test, batched).

When the multi-venue/coin book has accrued, this is ONE command that produces the per-cell deploy
verdict the maker thread has been waiting for. For each cell it:
  1. fetches data/<coin>-book and extracts the gzipped book to /tmp (skips cleanly if not yet accrued);
  2. builds the depth-imbalance signal at the locked operating point (K=10 from _gate_param_sweep) +
     the QuietFloor gate (k=1.5), fit on the TRAIN slice, evaluated on the HELD-OUT test slice;
  3. runs the honest maker/queue + adverse-selection simulator (odcore.maker_book) for the key arms;
  4. emits one row per cell: half-spread, gated direction hit, fav-minus-anti (signal as a side filter),
     the gate arm's gross/fill, and the breakeven rebate.

The deploy question per cell (Greg, S43): on a WIDER-SPREAD cell does half-spread capture (2-5 bps)
dominate adverse selection (~0.5 bps) so the gated signal-as-filter clears NET? btc_coinbase was the
spread-starved negative control (1-tick, gross < 0 before rebate). SOL/DOGE/XRP are the real test.

Run:
  python _maker_deploy_map.py                 # all alts + btc control (auto-fetch each data branch)
  python _maker_deploy_map.py --cells sol doge # subset
  python _maker_deploy_map.py --no-fetch       # use already-extracted /tmp/<coin>_book.jsonl.gz
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

import numpy as np

from _liquidity_dive import build_channels, median_spread_bps, fwd_cum_return
from _birth_probe import to_grid, load_book  # noqa: F401  (build_channels uses them)
from odcore import quiet_floor
from odcore.maker_book import simulate_arm

# locked operating point (see _gate_param_sweep_results.json)
K = 10
KGATE = 1.5
FLOW_W = 20
TRAIN_FRAC = 0.6
FILL_WINDOW = 10
HOLD = 1                    # shortest hold is best (next-cell signal decays) — S43
QUEUE_FRAC = 1.0

# cell -> (data branch, filename). Coinbase venue; extend here for other venues.
CELLS = {
    "btc_coinbase":  ("data/btc-book",  "btc_coinbase_book.jsonl.gz"),   # frozen control
    "eth_coinbase":  ("data/eth-book",  "eth_coinbase_book.jsonl.gz"),
    "sol_coinbase":  ("data/sol-book",  "sol_coinbase_book.jsonl.gz"),
    "doge_coinbase": ("data/doge-book", "doge_coinbase_book.jsonl.gz"),
    "xrp_coinbase":  ("data/xrp-book",  "xrp_coinbase_book.jsonl.gz"),
}


def fetch_book(cell: str, fetch: bool) -> str | None:
    """Fetch+extract the cell's book to /tmp; return the path, or None if not yet accrued."""
    branch, fn = CELLS[cell]
    out = f"/tmp/{cell}_book.jsonl.gz"
    if not fetch and os.path.exists(out):
        return out
    # branch present?
    r = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
                       capture_output=True)
    if r.returncode != 0:
        return None
    subprocess.run(["git", "fetch", "origin", branch], capture_output=True)
    show = subprocess.run(["git", "show", f"origin/{branch}:{fn}"], capture_output=True)
    if show.returncode != 0 or not show.stdout:
        return None
    with open(out, "wb") as f:
        f.write(show.stdout)
    return out


def hit(sig, fwd, cut, n):
    a = np.asarray(sig)[cut:n - 1]; b = fwd[cut:n - 1]; m = ~np.isnan(b)
    a, b = a[m], b[m]
    nz = (a != 0) & (b != 0)
    return float((np.sign(a) == np.sign(b))[nz].mean()) if nz.any() else float("nan")


def run_cell(cell: str, path: str) -> dict:
    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]
    mid, bb, ba, buy, sell = g["mid"], g["bidK"][1], g["askK"][1], g["buy"], g["sell"]
    n = len(mid)
    cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    sret = np.nan_to_num(np.concatenate([[0.0], np.diff(np.log(np.where(mid > 0, mid, np.nan)))]))
    fwd1 = fwd_cum_return(sret, 1)

    sign = np.sign(imb)
    gated = qf.gated_signal(imb, k=KGATE)
    te = slice(cut, n)
    s = lambda a: np.asarray(a)[te]

    def arm(side, name):
        return simulate_arm(side, s(mid), s(bb), s(ba), s(buy), s(sell),
                            fill_window=FILL_WINDOW, hold=HOLD, queue_frac=QUEUE_FRAC,
                            half_spread_bps=hs_bps, fee_bps=0.0, arm=name).as_dict()
    base_b = arm(np.ones(n - cut), "base_bid")
    base_a = arm(-np.ones(n - cut), "base_ask")
    fav = arm(s(sign), "signal_fav")
    anti = arm(-s(sign), "signal_anti")
    gate = arm(s(gated), "gate")

    gate_open = gated != 0
    fire = float(gate_open[te].mean())
    oq = float(gate_open[te][quiet[te]].mean()) if quiet[te].any() else float("nan")
    ot = float(gate_open[te][~quiet[te]].mean()) if (~quiet[te]).any() else float("nan")
    base_gross = 0.5 * (base_b["gross_per_fill_bps"] + base_a["gross_per_fill_bps"])
    return dict(
        cell=cell, n=n, hours=round(n * 0.1 / 3600, 2), half_spread_bps=hs_bps,
        phi=qf.phi, fire=fire, selectivity=ot / (oq + 1e-12),
        raw_hit_h1=hit(sign, fwd1, cut, n), gated_hit_h1=hit(gated, fwd1, cut, n),
        fav_gross=fav["gross_per_fill_bps"], anti_gross=anti["gross_per_fill_bps"],
        base_gross=base_gross, gate_gross=gate["gross_per_fill_bps"],
        gate_drift=gate["adverse_drift_bps"], gate_fillrate=gate["fill_rate"],
        fav_minus_anti=fav["gross_per_fill_bps"] - anti["gross_per_fill_bps"],
        gate_breakeven_fee=gate["breakeven_fee_bps"],
    )


def main():
    ap = argparse.ArgumentParser(description="Per-cell maker+gate deploy map")
    ap.add_argument("--cells", nargs="*", default=list(CELLS), help="subset of cell labels")
    ap.add_argument("--no-fetch", action="store_true", help="use already-extracted /tmp files")
    a = ap.parse_args()
    rows, skipped = [], []
    for cell in a.cells:
        if cell not in CELLS:
            print(f"[skip] unknown cell {cell}"); continue
        path = fetch_book(cell, fetch=not a.no_fetch)
        if not path:
            skipped.append(cell); print(f"[skip] {cell}: book not accrued yet ({CELLS[cell][0]})")
            continue
        print(f"[run]  {cell}: {path}")
        rows.append(run_cell(cell, path))

    if rows:
        print(f"\n# PER-CELL MAKER DEPLOY MAP (K={K}, gate k={KGATE}, hold={HOLD} cell, "
              f"half-spread from data; gross/fill BEFORE rebate)")
        hdr = (f"{'cell':<14}{'hrs':>6}{'half_sp':>9}{'gated_hit':>10}{'fav-anti':>10}"
               f"{'gate_gross':>11}{'breakeven':>10}{'verdict':>9}")
        print(hdr)
        for r in rows:
            verdict = "NET+" if r["gate_gross"] > 0 else ("rebate" if r["gate_gross"] > -1.0 else "no")
            print(f"{r['cell']:<14}{r['hours']:>6.1f}{r['half_spread_bps']:>9.4f}"
                  f"{100*r['gated_hit_h1']:>9.1f}%{r['fav_minus_anti']:>10.4f}"
                  f"{r['gate_gross']:>11.4f}{r['gate_breakeven_fee']:>10.4f}{verdict:>9}")
        print("\n# verdict: NET+ = gross/fill > 0 before any rebate (half-spread beats adverse "
              "selection — DEPLOYABLE); rebate = needs a maker rebate to clear; no = bleeds.")
    if skipped:
        print(f"\n# not yet accrued (trigger/await the book matrix): {', '.join(skipped)}")
    json.dump(json.loads(json.dumps(dict(K=K, kgate=KGATE, hold=HOLD, rows=rows,
              skipped=skipped), default=float)), open("_maker_deploy_map_results.json", "w"), indent=2)
    print("# wrote _maker_deploy_map_results.json")


if __name__ == "__main__":
    main()
