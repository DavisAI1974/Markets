"""Stack the algebraic-dipole predictor with per-trade chunker features.

Per-trade feature vector:
  Dipole side (2 dims):    H_a = <c, c_w_train>/||c_w_train||
                           H_b = <c, c_l_train>/||c_l_train||
  Chunker side (3 dims):   spectral_entropy_mean, range_atr_mean,
                           realized_vol_mean   (mean across chunks per trade)

Three classifiers via 5-fold stratified CV:
  A) DIPOLE-ALONE        (2-feature logistic regression on H_a, H_b)
  B) CHUNKER-ALONE       (3-feature LR on chunker means)
  C) STACKED (dipole+chunker, 5 features)

For each, report per-pair and pooled accuracy + AUC. Compare C vs A: lift
indicates orthogonal information; flat indicates redundancy.

Note: chunker features come from re-running MarketChunker on each trade's
[entry_ts, exit_ts] bar slice; this is the same chunker the refrag pipeline
uses (Phase 1), so we're testing whether the pre-encoder waveform shape
adds information beyond the post-encoder operator_coefficients dipole.
"""
from __future__ import annotations

import json, math, random, statistics, sys, time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, r"E:\Markets")
sys.path.insert(0, r"E:\refrag\adapters")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from markets_adapter import MarketChunker, MarketChunkEncoder
from markets_bar_loader import load_closes  # the durable archive loader

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
PER_BUCKET = Path(r"E:\Markets\research\strategy_evolution\per_bucket")
PAIRS = [
    "markets_btc_bybit_buy", "markets_btc_bybit_sell",
    "markets_btc_coinbase_buy", "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy", "markets_btc_kraken_sell",
    "markets_eth_bybit_buy", "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy", "markets_eth_coinbase_sell",
    "markets_eth_kraken_buy", "markets_eth_kraken_sell",
]
K_FOLDS = 5
RNG_SEED = 1974
TARGET_N = 20  # the top20/bottom20 list we built earlier
MIN_BARS_FOR_CHUNK = 16

# ---------- 1. Index operator_coefficients per source_id per domain
def index_coefs_by_source_id(domain: str) -> dict[str, list[float]]:
    """Build {source_id: operator_coefficients} for a domain.
    source_id is extracted from the document node in evidence_graph (the trade ID
    used at run time)."""
    out: dict[str, list[float]] = {}
    d = DISC / domain
    if not d.is_dir():
        return out
    for p in d.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        coefs = obj.get("result", {}).get("operator_coefficients")
        if not isinstance(coefs, list) or not coefs:
            continue
        # find source_id from evidence_graph document node
        sid = None
        for n in obj.get("result", {}).get("evidence_graph", {}).get("nodes", []):
            if isinstance(n, dict) and n.get("type") == "document":
                sid = n.get("metadata", {}).get("source_id") or n.get("id", "").replace("document:", "")
                break
        if sid:
            out[sid] = [float(c) for c in coefs]
    return out

# ---------- 2. Compute chunker features per entry
def compute_chunker_features_for_entries(entries: list[dict]) -> dict[str, dict]:
    """Returns {source_id: {spectral_entropy_mean, range_atr_mean, realized_vol_mean}}.
    Loads bars once per (asset, venue), chunks per entry, averages per trade."""
    by_av = defaultdict(list)
    for e in entries:
        by_av[(e["asset"], e["venue"])].append(e)

    chunker = MarketChunker(max_window_size=192, stride=96, min_segment=MIN_BARS_FOR_CHUNK, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64, compute_hawkes=False, compute_hurst=False)
    out: dict[str, dict] = {}

    for (asset, venue), elist in by_av.items():
        ts_lo = min(float(e["entry_ts_utc"]) for e in elist)
        ts_hi = max(float(e["entry_ts_utc"]) + float(e.get("horizon_minutes") or 0)*60 for e in elist)
        BUFFER_S = 6 * 3600
        closes = load_closes(asset=asset, venue=venue, t_min=ts_lo - BUFFER_S, t_max=ts_hi + BUFFER_S)
        if not closes:
            continue

        # build MarketBar-compatible list from closes
        # MarketBar needs ts, ohlc; we only have close. Use close for all OHLC.
        from markets_adapter import MarketBar
        bars_all = [MarketBar(ts=c.ts, close=c.close, open_=c.close,
                              high=c.close, low=c.close) for c in closes]
        ts_list = [b.ts for b in bars_all]
        import bisect

        for e in elist:
            sid = e["source_id"]
            entry_ts = float(e["entry_ts_utc"])
            exit_ts = entry_ts + float(e.get("horizon_minutes") or 0) * 60
            i0 = bisect.bisect_left(ts_list, entry_ts)
            i1 = bisect.bisect_right(ts_list, exit_ts)
            bars = bars_all[i0:i1]
            if len(bars) < MIN_BARS_FOR_CHUNK:
                continue
            try:
                chunks = chunker.chunk(sid, bars, multi_signal=False)
                if not chunks:
                    continue
                feats_per_chunk = [encoder._extract(c) for c in chunks]
            except Exception as _ex:
                continue
            if not feats_per_chunk:
                continue
            mean_se = statistics.mean([f.spectral_entropy for f in feats_per_chunk])
            mean_ra = statistics.mean([f.range_atr for f in feats_per_chunk])
            mean_rv = statistics.mean([f.realized_vol for f in feats_per_chunk])
            out[sid] = {"spectral_entropy_mean": mean_se,
                        "range_atr_mean":         mean_ra,
                        "realized_vol_mean":      mean_rv}
    return out

# ---------- 3. Build per-trade dataset for a pair
def build_pair_dataset(pair: str):
    """Returns (X_dipole_raw, X_chunker, y, source_ids) for win-top20 + lose-bot20.
    X_dipole_raw is the raw operator_coefficients (per fold we'll project onto
    train centroids to get H_a, H_b)."""
    win_p = PER_BUCKET / f"{pair}_win.top{TARGET_N}.json"
    lose_p = PER_BUCKET / f"{pair}_lose.bottom{TARGET_N}.json"
    if not win_p.exists() or not lose_p.exists():
        return None
    w_entries = json.load(win_p.open()).get("entries", [])
    l_entries = json.load(lose_p.open()).get("entries", [])

    # 1) operator_coefficients
    coef_w = index_coefs_by_source_id(f"{pair}_win")
    coef_l = index_coefs_by_source_id(f"{pair}_lose")

    # 2) chunker features for these specific entries
    chunk_feats = compute_chunker_features_for_entries(w_entries + l_entries)

    # 3) Assemble
    rows = []
    for e, label, coef_idx in [
        *[(e, 1, coef_w) for e in w_entries],
        *[(e, 0, coef_l) for e in l_entries],
    ]:
        sid = e["source_id"]
        c = coef_idx.get(sid)
        f = chunk_feats.get(sid)
        if c is None or f is None:
            continue
        rows.append({
            "source_id": sid,
            "label": label,
            "coefs": c,
            "se": f["spectral_entropy_mean"],
            "ra": f["range_atr_mean"],
            "rv": f["realized_vol_mean"],
        })
    return rows

# ---------- 4. Classifier helpers
def auc_score(y_true, y_score):
    pos = [s for s, l in zip(y_score, y_true) if l == 1]
    neg = [s for s, l in zip(y_score, y_true) if l == 0]
    if not pos or not neg:
        return 0.5
    combined = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg], key=lambda x: x[0])
    n = len(combined)
    rank_sum_pos = 0.0
    i = 0
    while i < n:
        j = i
        while j < n and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            if combined[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j
    U = rank_sum_pos - len(pos)*(len(pos)+1)/2.0
    return U / (len(pos) * len(neg))

def stratified_folds(labels, k, rng):
    pos = [i for i,l in enumerate(labels) if l==1]
    neg = [i for i,l in enumerate(labels) if l==0]
    rng.shuffle(pos); rng.shuffle(neg)
    return [sorted(pos[i::k] + neg[i::k]) for i in range(k)]

# ---------- 5. K-fold for each variant
def eval_kfold(rows, variant: str, rng):
    """variant in {'dipole','chunker','stacked'}."""
    n = len(rows)
    if n < K_FOLDS * 2:
        return None
    labels = [r["label"] for r in rows]
    coefs = [r["coefs"] for r in rows]
    chunker = [[r["se"], r["ra"], r["rv"]] for r in rows]
    folds = stratified_folds(labels, K_FOLDS, rng)
    oof_scores = [None] * n
    accs = []
    conf = {"TP":0,"FP":0,"TN":0,"FN":0}
    for fi in range(K_FOLDS):
        test_idx = folds[fi]
        train_idx = [i for f in range(K_FOLDS) if f != fi for i in folds[f]]
        # Project coefs onto train centroids -> per-trade H_a, H_b
        train_w = [coefs[i] for i in train_idx if labels[i]==1]
        train_l = [coefs[i] for i in train_idx if labels[i]==0]
        if not train_w or not train_l:
            continue
        cw = np.mean(np.array(train_w), axis=0)
        cl = np.mean(np.array(train_l), axis=0)
        nw = np.linalg.norm(cw) or 1.0
        nl = np.linalg.norm(cl) or 1.0
        def dipole_feats(idx_list):
            X = []
            for i in idx_list:
                Ha = float(np.dot(coefs[i], cw) / nw)
                Hb = float(np.dot(coefs[i], cl) / nl)
                X.append([Ha, Hb])
            return np.array(X)
        if variant == "dipole":
            Xtr, Xte = dipole_feats(train_idx), dipole_feats(test_idx)
        elif variant == "chunker":
            Xtr = np.array([chunker[i] for i in train_idx])
            Xte = np.array([chunker[i] for i in test_idx])
        else:  # stacked
            Xtr = np.hstack([dipole_feats(train_idx), np.array([chunker[i] for i in train_idx])])
            Xte = np.hstack([dipole_feats(test_idx),  np.array([chunker[i] for i in test_idx])])
        ytr = np.array([labels[i] for i in train_idx])
        yte = np.array([labels[i] for i in test_idx])
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ])
        pipe.fit(Xtr, ytr)
        proba = pipe.predict_proba(Xte)[:, 1]
        pred = (proba >= 0.5).astype(int)
        for idx, s in zip(test_idx, proba):
            oof_scores[idx] = float(s)
        accs.append(float(np.mean(pred == yte)))
        for p, t in zip(pred, yte):
            if p==1 and t==1: conf["TP"] += 1
            elif p==1 and t==0: conf["FP"] += 1
            elif p==0 and t==0: conf["TN"] += 1
            else: conf["FN"] += 1
    pos_scores = [s for s,l in zip(oof_scores, labels) if l==1 and s is not None]
    neg_scores = [s for s,l in zip(oof_scores, labels) if l==0 and s is not None]
    return {
        "acc_mean": statistics.mean(accs) if accs else 0.0,
        "acc_std":  statistics.stdev(accs) if len(accs) > 1 else 0.0,
        "auc": auc_score([1]*len(pos_scores)+[0]*len(neg_scores), pos_scores+neg_scores),
        "conf": conf,
    }

def main():
    rng = random.Random(RNG_SEED)
    print(f"{'pair':30s}  | {'dipole-only':^22s} | {'chunker-only':^22s} | {'STACKED':^22s} | lift")
    print(f"{'':30s}  | {'acc':>5s} {'AUC':>5s} {'TP/FP/TN/FN':>10s} | {'acc':>5s} {'AUC':>5s} {'TP/FP/TN/FN':>10s} | {'acc':>5s} {'AUC':>5s} {'TP/FP/TN/FN':>10s} |")
    print("-"*145)
    summaries = []
    for pair in PAIRS:
        rng_pair = random.Random(RNG_SEED + hash(pair) % 100)
        print(f"  building {pair} ...", flush=True)
        t0 = time.time()
        rows = build_pair_dataset(pair)
        if rows is None or len(rows) < K_FOLDS * 2:
            print(f"{pair:30s}  | skipped (insufficient data: {len(rows) if rows else 0} rows)", flush=True)
            continue
        d_res = eval_kfold(rows, "dipole", rng_pair)
        c_res = eval_kfold(rows, "chunker", random.Random(RNG_SEED + hash(pair) % 100))
        s_res = eval_kfold(rows, "stacked", random.Random(RNG_SEED + hash(pair) % 100))
        if d_res is None or c_res is None or s_res is None:
            continue
        lift = s_res["acc_mean"] - d_res["acc_mean"]
        summaries.append((pair, d_res, c_res, s_res))
        def fmt(r):
            return f"{r['acc_mean']:.3f} {r['auc']:.3f} {r['conf']['TP']:>2}/{r['conf']['FP']:>2}/{r['conf']['TN']:>2}/{r['conf']['FN']:>2}"
        print(f"{pair:30s}  | {fmt(d_res):>22s} | {fmt(c_res):>22s} | {fmt(s_res):>22s} | {lift:+.3f}  ({(time.time()-t0):.0f}s)", flush=True)

    if summaries:
        print("-"*145)
        for name, idx in (("DIPOLE", 1), ("CHUNKER", 2), ("STACKED", 3)):
            accs = [s[idx]["acc_mean"] for s in summaries]
            aucs = [s[idx]["auc"] for s in summaries]
            print(f"  {name:8s} mean_acc = {statistics.mean(accs):.3f}  mean_AUC = {statistics.mean(aucs):.3f}")
        lifts = [s[3]["acc_mean"] - s[1]["acc_mean"] for s in summaries]
        print(f"  stacked - dipole acc lift: mean {statistics.mean(lifts):+.3f}, range [{min(lifts):+.3f}, {max(lifts):+.3f}]")

if __name__ == "__main__":
    main()
