"""S35 parallel-safe — which micro features carry the de-confounded AUC?

Per cell, univariate directed AUC of each micro feature vs the true-horizon label
(de-confounded chunkhash universe). Univariate AUC needs no model fit, so it is
leakage-free. Reports, per cell, the AUC of each feature (>0.5 = higher feature
=> win; <0.5 = higher feature => lose), so we can see which features drive the
strong cells (eth_coinbase_buy 0.84, btc_bybit_sell 0.81, etc.) and whether the
same feature dominates everywhere (=> compute that one live) or it is per-cell.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

SHARD_DIR = Path(r"E:\Markets\_cs2000_coeff_index")
RELABEL = Path(r"E:\Markets\_relabel_true_horizon_results.json")
CLEAN_BUCKETS = Path(r"E:\Markets\research\strategy_evolution\per_bucket\clean")
MICRO = ["mean_dipole", "dipole_acl1", "volume_zscore", "trade_present_score",
         "trade_recent_2chunk_bps", "trade_from_onset_bps"]
PAIRS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]


def pair_of(sid):
    p = sid.split("|")
    return f"{p[0].lower()}_{p[1].lower()}_{p[-1].lower()}" if len(p) >= 4 else None


def auc(scores, labels):
    pos = scores[labels == 1]; neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores)); ranks[order] = np.arange(1, len(scores) + 1)
    s = scores[order]; i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        if j - i > 1:
            ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    U = ranks[labels == 1].sum() - len(pos) * (len(pos) + 1) / 2.0
    return float(U / (len(pos) * len(neg)))


def main() -> int:
    coefs = {}
    for sh in glob.glob(str(SHARD_DIR / "*_win_preentry_cs2000_clean.json")):
        for _u, rec in json.loads(Path(sh).read_text()).items():
            coefs[rec["source_id"]] = True
    lab = {t["source_id"]: t.get("new_label") for t in json.loads(RELABEL.read_text())["trades"]}
    micro = {}
    for fp in CLEAN_BUCKETS.glob("markets_*_win.clean.json"):
        for e in json.loads(fp.read_text(encoding="utf-8")).get("entries", []) or []:
            sid = e.get("source_id")
            if not sid:
                continue
            row = {}
            for k in MICRO:
                try:
                    row[k] = float(e.get(k))
                except (TypeError, ValueError):
                    row[k] = np.nan
            micro[sid] = row

    data = {p: {"M": [], "y": []} for p in PAIRS}
    for sid in coefs:
        l = lab.get(sid); p = pair_of(sid); m = micro.get(sid)
        if l not in ("win", "lose") or p not in data or m is None:
            continue
        if any(np.isnan(m[k]) for k in MICRO):
            continue
        data[p]["M"].append([m[k] for k in MICRO]); data[p]["y"].append(1 if l == "win" else 0)

    print(f"{'cell':18s} {'n_w':>4s} {'n_l':>4s} | " + " ".join(f"{m[:10]:>10s}" for m in MICRO))
    print("-" * (28 + 11 * len(MICRO)))
    agg = {m: [] for m in MICRO}
    for p in PAIRS:
        M = np.array(data[p]["M"], float); y = np.array(data[p]["y"], int)
        nw = int((y == 1).sum()); nl = int((y == 0).sum())
        if nw < 8 or nl < 8:
            print(f"{p:18s} {nw:>4d} {nl:>4d} | (too few)"); continue
        cells = []
        for j, m in enumerate(MICRO):
            a = auc(M[:, j], y)
            agg[m].append(abs(a - 0.5))
            cells.append(f"{a:>10.3f}")
        print(f"{p:18s} {nw:>4d} {nl:>4d} | " + " ".join(cells))
    print("-" * (28 + 11 * len(MICRO)))
    print(f"{'mean |AUC-0.5|':18s} {'':>4s} {'':>4s} | "
          + " ".join(f"{np.mean(agg[m]):>10.3f}" if agg[m] else f"{'-':>10s}" for m in MICRO))
    print("\n(AUC>0.5: higher feature => win; <0.5: higher => lose. |AUC-0.5| = strength.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
