"""Honest k-fold cross-validation of the algebraic-dipole predictor.

Per pair, 5-fold stratified split (preserves win/lose ratio per fold):
  TRAIN -> compute c_win_centroid, c_lose_centroid from train winners/losers
  TEST  -> for each test trade c_i:
              H_a = <c_i, c_win_train> / ||c_win_train||
              H_b = <c_i, c_lose_train> / ||c_lose_train||
              score = H_a - H_b              (signed margin)
              predict win iff score > 0      (zero-threshold rule)

Reports per pair and pooled:
  - accuracy (5-fold mean +- stdev)
  - AUC (computed on pooled OOF scores)
  - confusion matrix (sum across folds)
  - separation Cohen's d on the OOF score (the real out-of-sample d)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
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

DOMAIN_SUFFIX = ""       # fallback, set by --domain-suffix CLI arg
WIN_SUFFIX = None        # if set, overrides DOMAIN_SUFFIX for winners
LOSE_SUFFIX = None       # if set, overrides DOMAIN_SUFFIX for losers

def _suffix() -> str:
    return f"_{DOMAIN_SUFFIX}" if DOMAIN_SUFFIX else ""

def _win_suffix() -> str:
    s = WIN_SUFFIX if WIN_SUFFIX is not None else DOMAIN_SUFFIX
    return f"_{s}" if s else ""

def _lose_suffix() -> str:
    s = LOSE_SUFFIX if LOSE_SUFFIX is not None else DOMAIN_SUFFIX
    return f"_{s}" if s else ""

def load_coefs(domain):
    d = DISC / domain
    if not d.is_dir(): return []
    out = []
    for p in d.glob("*.json"):
        try: obj = json.loads(p.read_text(encoding="utf-8"))
        except: continue
        c = obj.get("result", {}).get("operator_coefficients")
        if isinstance(c, list) and c:
            out.append([float(x) for x in c])
    return out

def vec_mean(vs):
    if not vs: return []
    d = len(vs[0]); out = [0.0]*d
    for v in vs:
        for i in range(d): out[i] += v[i]
    return [x/len(vs) for x in out]

def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))

def cohens_d(a, b):
    if len(a)<2 or len(b)<2: return 0.0
    sa = statistics.pstdev(a); sb = statistics.pstdev(b)
    pooled = math.sqrt((sa*sa + sb*sb)/2.0)
    if pooled == 0: return 0.0
    return (statistics.mean(a) - statistics.mean(b)) / pooled

def auc_from_scores(scores_pos, scores_neg):
    # Mann-Whitney U / (n_pos * n_neg)
    n_pos = len(scores_pos); n_neg = len(scores_neg)
    if n_pos == 0 or n_neg == 0: return 0.5
    combined = [(s, 1) for s in scores_pos] + [(s, 0) for s in scores_neg]
    combined.sort(key=lambda t: t[0])
    rank_sum_pos = 0.0
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0   # 1-based average rank for ties
        for k in range(i, j):
            if combined[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j
    U = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return U / (n_pos * n_neg)

def stratified_kfold_indices(labels, k, rng):
    pos = [i for i, l in enumerate(labels) if l == 1]
    neg = [i for i, l in enumerate(labels) if l == 0]
    rng.shuffle(pos); rng.shuffle(neg)
    pos_folds = [pos[i::k] for i in range(k)]
    neg_folds = [neg[i::k] for i in range(k)]
    return [sorted(pf + nf) for pf, nf in zip(pos_folds, neg_folds)]

def main():
    global DOMAIN_SUFFIX, WIN_SUFFIX, LOSE_SUFFIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-suffix", type=str, default="",
                    help="Read coefficients from <pair>_<outcome>_<suffix>/ instead of "
                         "<pair>_<outcome>/. Used to k-fold pre-entry runs without "
                         "touching the post-hoc dataset.")
    ap.add_argument("--win-domain-suffix", type=str, default=None,
                    help="Override domain suffix for winner dirs only.")
    ap.add_argument("--lose-domain-suffix", type=str, default=None,
                    help="Override domain suffix for loser dirs only.")
    args = ap.parse_args()
    DOMAIN_SUFFIX = args.domain_suffix.strip().lower()
    WIN_SUFFIX = args.win_domain_suffix.strip().lower() if args.win_domain_suffix is not None else None
    LOSE_SUFFIX = args.lose_domain_suffix.strip().lower() if args.lose_domain_suffix is not None else None
    if WIN_SUFFIX is not None or LOSE_SUFFIX is not None:
        print(f"[win{_win_suffix()}/, lose{_lose_suffix()}/]")
    elif DOMAIN_SUFFIX:
        print(f"[domain_suffix={DOMAIN_SUFFIX!r}] reading from <pair>_<outcome>{_suffix()}/")

    rng = random.Random(RNG_SEED)
    print(f"{'pair':30s}  {'n_w':>4s}  {'n_l':>4s}  {'acc_mean':>9s}  {'acc_std':>8s}  {'AUC':>5s}  {'d_OOF':>6s}  {'TP':>4s} {'FP':>4s} {'TN':>4s} {'FN':>4s}")
    print("-"*110)
    pooled = {"TP":0,"FP":0,"TN":0,"FN":0,"scores_pos":[],"scores_neg":[],"per_pair_acc":[]}
    for pair in PAIRS:
        cw = load_coefs(f"{pair}_win{_win_suffix()}"); cl = load_coefs(f"{pair}_lose{_lose_suffix()}")
        if not cw or not cl:
            print(f"{pair:30s}  {len(cw):>4d}  {len(cl):>4d}  --       --       --     --     (incomplete)")
            continue
        coefs = cw + cl
        labels = [1]*len(cw) + [0]*len(cl)
        folds = stratified_kfold_indices(labels, K_FOLDS, rng)
        accs = []; conf = {"TP":0,"FP":0,"TN":0,"FN":0}
        oof_scores_pos = []; oof_scores_neg = []
        for fi in range(K_FOLDS):
            test_idx = folds[fi]
            train_idx = [i for f, fold in enumerate(folds) if f != fi for i in fold]
            train_w = [coefs[i] for i in train_idx if labels[i]==1]
            train_l = [coefs[i] for i in train_idx if labels[i]==0]
            if not train_w or not train_l: continue
            cw_mean = vec_mean(train_w); cl_mean = vec_mean(train_l)
            nw = norm(cw_mean) or 1.0; nl = norm(cl_mean) or 1.0
            correct = 0; total = 0
            for i in test_idx:
                Ha = dot(coefs[i], cw_mean) / nw
                Hb = dot(coefs[i], cl_mean) / nl
                score = Ha - Hb
                pred = 1 if score > 0 else 0
                actual = labels[i]
                if actual == 1: oof_scores_pos.append(score)
                else: oof_scores_neg.append(score)
                if pred == actual: correct += 1
                total += 1
                if pred == 1 and actual == 1: conf["TP"] += 1
                elif pred == 1 and actual == 0: conf["FP"] += 1
                elif pred == 0 and actual == 0: conf["TN"] += 1
                else: conf["FN"] += 1
            if total: accs.append(correct/total)
        acc_mean = statistics.mean(accs) if accs else 0.0
        acc_std = statistics.stdev(accs) if len(accs)>1 else 0.0
        auc = auc_from_scores(oof_scores_pos, oof_scores_neg)
        d_oof = cohens_d(oof_scores_pos, oof_scores_neg)
        print(f"{pair:30s}  {len(cw):>4d}  {len(cl):>4d}  {acc_mean:>9.3f}  {acc_std:>8.3f}  {auc:>5.3f}  {d_oof:>+6.2f}  {conf['TP']:>4d} {conf['FP']:>4d} {conf['TN']:>4d} {conf['FN']:>4d}")
        for k in conf: pooled[k] += conf[k]
        pooled["scores_pos"] += oof_scores_pos
        pooled["scores_neg"] += oof_scores_neg
        pooled["per_pair_acc"].append(acc_mean)

    # Pooled
    if pooled["per_pair_acc"]:
        total = pooled["TP"]+pooled["FP"]+pooled["TN"]+pooled["FN"]
        pool_acc = (pooled["TP"]+pooled["TN"])/total if total else 0
        pool_auc = auc_from_scores(pooled["scores_pos"], pooled["scores_neg"])
        pool_d = cohens_d(pooled["scores_pos"], pooled["scores_neg"])
        print("-"*110)
        print(f"{'POOLED (all pairs)':30s}  {'':>4s}  {'':>4s}  {pool_acc:>9.3f}  {'':>8s}  {pool_auc:>5.3f}  {pool_d:>+6.2f}  {pooled['TP']:>4d} {pooled['FP']:>4d} {pooled['TN']:>4d} {pooled['FN']:>4d}")
        # Per-class precision / recall pooled
        prec_w = pooled["TP"]/(pooled["TP"]+pooled["FP"]) if (pooled["TP"]+pooled["FP"]) else 0
        rec_w  = pooled["TP"]/(pooled["TP"]+pooled["FN"]) if (pooled["TP"]+pooled["FN"]) else 0
        prec_l = pooled["TN"]/(pooled["TN"]+pooled["FN"]) if (pooled["TN"]+pooled["FN"]) else 0
        rec_l  = pooled["TN"]/(pooled["TN"]+pooled["FP"]) if (pooled["TN"]+pooled["FP"]) else 0
        f1_w = 2*prec_w*rec_w/(prec_w+rec_w) if (prec_w+rec_w) else 0
        f1_l = 2*prec_l*rec_l/(prec_l+rec_l) if (prec_l+rec_l) else 0
        print(f"  win  : precision={prec_w:.3f} recall={rec_w:.3f} F1={f1_w:.3f}")
        print(f"  lose : precision={prec_l:.3f} recall={rec_l:.3f} F1={f1_l:.3f}")

if __name__ == "__main__":
    main()
