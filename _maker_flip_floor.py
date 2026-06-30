"""_maker_flip_floor.py — use BOTH the QuietFloor gate AND the dipole FLIP detector (S45, Greg).

The S45 autopsy showed the maker bleed is adverse selection: the QuietFloor gate fires on an imbalance
SHOCK, but a shock is either a TURN (the valley/peak we want) or a trend-CONTINUATION (a falling knife),
and the floor alone can't tell them apart -> it posts "Buy long" into downtrends and gets run over.

Fix = compose the two validated pieces (neither is enough alone):
  - FLOOR  (odcore.quiet_floor): WHEN. fire only when |innovation| > k*sigma (a real shock broke the
    between-trade AR(1) relaxation), so we don't churn on quiet noise. direction = sign(depth_imb).
  - FLIP   (odcore.info_dipole.divergence, applied to the DEPTH-imbalance channel -- trade-flow
    degenerates on the book, S44): WHICH. act only when the book leans AGAINST the recent price move,
    aligned = imb * sign(price_drift) < 0  => we are at/near a TURN (reversal), not a continuation.
    Then sign(imb) buys the valley / shorts the peak (it is, by construction, fading the recent move).

combined: side = sign(imb)  where  gate_open AND opposing,  else 0.

Leakage-safe: floor fit on TRAIN quiet cells; price_drift uses only past mids; all metrics on the
held-out TEST slice. Per-cell depth-K from S45 (alts=1 top-of-book, btc=10). PROVISIONAL: one ~11.7h
window per alt -- a comparison, not a sizing number.

Run:  python _maker_flip_floor.py [--cells ...] [--pdwin 30]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from _liquidity_dive import build_channels, median_spread_bps, fwd_cum_return
from odcore import quiet_floor
from odcore.maker_book import simulate_arm

KGATE = 1.5
FLOW_W = 20
TRAIN_FRAC = 0.6
FILL_WINDOW = 10
HOLD = 1
QUEUE_FRAC = 1.0
PD_WIN = 30                       # trailing cells (3s) that define "the recent price move" for the flip

PER_CELL_K = {"btc_coinbase": 10, "eth_coinbase": 1, "sol_coinbase": 1,
              "doge_coinbase": 1, "xrp_coinbase": 1}
CELLS = {
    "btc_coinbase": "/tmp/btc_coinbase_book.jsonl.gz",
    "eth_coinbase": "/tmp/eth_coinbase_book.jsonl.gz",
    "sol_coinbase": "/tmp/sol_coinbase_book.jsonl.gz",
    "doge_coinbase": "/tmp/doge_coinbase_book.jsonl.gz",
    "xrp_coinbase": "/tmp/xrp_coinbase_book.jsonl.gz",
}


def hit(sig, fwd, lo, hi):
    a = np.asarray(sig)[lo:hi]; b = fwd[lo:hi]; m = ~np.isnan(b)
    a, b = a[m], b[m]; nz = (a != 0) & (b != 0)
    return (float((np.sign(a) == np.sign(b))[nz].mean()), int(nz.sum())) if nz.any() else (float("nan"), 0)


def opposing_mask(imb, mid, pdwin):
    """aligned = imb * sign(price_drift) < 0  -> book leans against the recent move (near a turn).
    price_drift is trailing (past only): log mid[t] - log mid[t-pdwin]; causal, no look-ahead."""
    lm = np.log(np.where(mid > 0, mid, np.nan))
    pd = np.full(len(mid), 0.0)
    pd[pdwin:] = np.nan_to_num(lm[pdwin:] - lm[:-pdwin])
    aligned = imb * np.sign(pd)
    return aligned < 0


def run_cell(cell, path, pdwin=PD_WIN):
    K = PER_CELL_K.get(cell, 1)
    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)

    gate_open = qf.gate(imb, k=KGATE)
    opp = opposing_mask(imb, mid, pdwin)
    sgn = np.sign(imb)
    floor_sig = np.where(gate_open, sgn, 0.0)               # FLOOR only (current deploy)
    flip_sig = np.where(opp, sgn, 0.0)                      # FLIP only (turn filter, no shock gate)
    both_sig = np.where(gate_open & opp, sgn, 0.0)          # BOTH

    sret = np.nan_to_num(np.concatenate([[0.0], np.diff(np.log(np.where(mid > 0, mid, np.nan)))]))
    fwd1 = fwd_cum_return(sret, 1)
    te = slice(cut, n); s = lambda a: np.asarray(a)[te]

    def arm(sig, name):
        r = simulate_arm(s(sig), s(mid), s(bb), s(ba), s(buy), s(sell), fill_window=FILL_WINDOW,
                         hold=HOLD, queue_frac=QUEUE_FRAC, half_spread_bps=hs_bps, fee_bps=0.0,
                         arm=name).as_dict()
        h, _ = hit(sig, fwd1, cut, n - 1)
        return dict(name=name, gross=r["gross_per_fill_bps"], nf=r["n_fills"],
                    fire=float((np.asarray(sig)[te] != 0).mean()), hit=h,
                    drift=r["adverse_drift_bps"])

    return dict(cell=cell, K=K, hours=round(n * 0.1 / 3600, 2), half_spread_bps=hs_bps,
                floor=arm(floor_sig, "floor"), flip=arm(flip_sig, "flip"), both=arm(both_sig, "both"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="*", default=list(CELLS))
    ap.add_argument("--pdwin", type=int, default=PD_WIN)
    a = ap.parse_args()
    rows = []
    import os
    for cell in a.cells:
        if not os.path.exists(CELLS[cell]):
            print(f"[skip] {cell}: no /tmp book"); continue
        print(f"[run]  {cell}")
        rows.append(run_cell(cell, CELLS[cell], a.pdwin))

    def vd(gross):
        return "NET+" if gross > 0 else ("rebate" if gross > -1.0 else "no")
    print(f"\n# FLOOR vs FLIP vs BOTH  (per-cell K top-of-book for alts; gate k={KGATE}; pdwin={a.pdwin} "
          f"cells; gross/fill BEFORE rebate; PROVISIONAL one window)")
    print(f"{'cell':<14}{'K':>3}{'half_sp':>9}"
          f"{'floor_g':>9}{'floor_v':>8}{'flip_g':>9}{'flip_v':>8}{'BOTH_g':>9}{'BOTH_v':>8}"
          f"{'both_fire':>10}{'both_hit':>9}{'both_nf':>8}")
    for r in rows:
        print(f"{r['cell']:<14}{r['K']:>3}{r['half_spread_bps']:>9.4f}"
              f"{r['floor']['gross']:>9.4f}{vd(r['floor']['gross']):>8}"
              f"{r['flip']['gross']:>9.4f}{vd(r['flip']['gross']):>8}"
              f"{r['both']['gross']:>9.4f}{vd(r['both']['gross']):>8}"
              f"{100*r['both']['fire']:>9.1f}%{100*r['both']['hit']:>8.1f}%{r['both']['nf']:>8}")
    print("\n# floor=QuietFloor shock gate only (current). flip=turn filter only. BOTH=shock AND at-a-turn.")
    json.dump(json.loads(json.dumps(dict(kgate=KGATE, pdwin=a.pdwin, per_cell_K=PER_CELL_K, rows=rows),
              default=float)), open("_maker_flip_floor_results.json", "w"), indent=2)
    print("# wrote _maker_flip_floor_results.json")


if __name__ == "__main__":
    main()
