"""Export schema-v2 production gate file: per-pair centroids PLUS flow-arm
feature weights, per-feature train-set mean/std, and the calibrated decision
threshold -- everything the live admission gate (gate_v2) needs in ONE file.

This is the DEPLOYMENT REFIT of the classifier validated by
_markets_combined_info_flow_kfold.py --mode info_score_plus_flow
--calibrated-threshold (5-fold OOF: 0.794 acc / 0.855 AUC / FN=183, n=2254).

It reuses that script's join + math (imported) so the exported gate is
guaranteed to match the validated classifier; the only difference is this
fits on ALL trades per pair (no held-out fold) because the gate ships one
fixed set of centroids/weights/stats/threshold. In-sample accuracy here will
therefore sit ABOVE the 0.794 OOF figure and BELOW ~1.0 -- that band is the
refit sanity check.

Output: E:\\Markets\\_markets_dipole_centroids_preentry_cs100_v2_schemav2.json
Leaves the existing schema_version 1 file untouched.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _markets_combined_info_flow_kfold import (  # noqa: E402
    PAIRS, WIN_SUFFIX, LOSE_SUFFIX, join_pair, vec_mean, dot, norm, cohens_d,
)

# Feature order matches gate_v2's expected keys in HANDOFF_NEXT_CHAT.md.
FEATURE_SET = ["info_score", "mean_dipole_signed", "volume_zscore", "trade_present_score"]

DEFAULT_OUTPUT = Path(r"E:\Markets\_markets_dipole_centroids_preentry_cs100_v2_schemav2.json")


def project(t: dict, c_w: list[float], nw: float, c_l: list[float], nl: float) -> dict[str, float]:
    """Project one trade's coefs to the 4-feature space the gate scores.
    info_score = <c, c_win>/||c_win|| - <c, c_lose>/||c_lose||  (the H_a - H_b of the kfold script).
    """
    return {
        "info_score": dot(t["coefs"], c_w) / nw - dot(t["coefs"], c_l) / nl,
        "mean_dipole_signed": t["mean_dipole_signed"],
        "volume_zscore": t["volume_zscore"],
        "trade_present_score": t["trade_present_score"],
    }


def fit_pair(pair: str) -> dict | None:
    winners, losers = join_pair(pair)
    if not winners or not losers:
        return None

    # Info-arm centroids on operator coefficients (full data).
    c_w = vec_mean([t["coefs"] for t in winners]); nw = norm(c_w) or 1.0
    c_l = vec_mean([t["coefs"] for t in losers]); nl = norm(c_l) or 1.0

    proj_w = [project(t, c_w, nw, c_l, nl) for t in winners]
    proj_l = [project(t, c_w, nw, c_l, nl) for t in losers]
    proj_all = proj_w + proj_l

    feature_stats: dict[str, dict[str, float]] = {}
    feature_weights: dict[str, float] = {}
    for k in FEATURE_SET:
        vals_all = [p[k] for p in proj_all]
        mu = statistics.mean(vals_all)
        sd = statistics.pstdev(vals_all) or 1.0
        d = cohens_d([p[k] for p in proj_w], [p[k] for p in proj_l])
        feature_stats[k] = {"mean": mu, "std": sd}
        feature_weights[k] = d

    def score(p: dict[str, float]) -> float:
        s = 0.0
        for k in FEATURE_SET:
            mu = feature_stats[k]["mean"]; sd = feature_stats[k]["std"]
            z = (p[k] - mu) / sd if sd > 0 else 0.0
            s += feature_weights[k] * z
        return s

    w_scores = [score(p) for p in proj_w]
    l_scores = [score(p) for p in proj_l]
    threshold = (statistics.mean(w_scores) + statistics.mean(l_scores)) / 2.0

    tp = sum(1 for s in w_scores if s > threshold); fn = len(w_scores) - tp
    tn = sum(1 for s in l_scores if s <= threshold); fp = len(l_scores) - tn
    insample_acc = (tp + tn) / (len(w_scores) + len(l_scores))

    return {
        "n_win": len(winners), "n_lose": len(losers),
        "c_win_centroid": c_w, "c_lose_centroid": c_l,
        "c_win_norm": nw, "c_lose_norm": nl,
        "feature_weights": feature_weights,
        "feature_stats": feature_stats,
        "threshold": threshold,
        "insample": {"acc": insample_acc, "TP": tp, "FP": fp, "TN": tn, "FN": fn},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    print(f"win={WIN_SUFFIX}/  lose={LOSE_SUFFIX}/  features={FEATURE_SET}")
    print(f"{'pair':30s}  {'n_w':>4s}  {'n_l':>4s}  {'thr':>7s}  {'acc*':>5s}  "
          f"{'w_info':>7s} {'w_md':>7s} {'w_vz':>7s} {'w_tps':>7s}")
    print("-" * 100)

    pairs_out: dict[str, dict] = {}
    pooled = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    for pair in PAIRS:
        r = fit_pair(pair)
        if r is None:
            print(f"{pair:30s}  {'--':>4s}  {'--':>4s}  (no join -- skipped)")
            continue
        ins = r.pop("insample")
        for k in ("TP", "FP", "TN", "FN"):
            pooled[k] += ins[k]
        w = r["feature_weights"]
        print(f"{pair:30s}  {r['n_win']:>4d}  {r['n_lose']:>4d}  {r['threshold']:>7.3f}  "
              f"{ins['acc']:>5.3f}  {w['info_score']:>7.3f} {w['mean_dipole_signed']:>7.3f} "
              f"{w['volume_zscore']:>7.3f} {w['trade_present_score']:>7.3f}")
        pairs_out[pair] = r

    n_total = sum(pooled.values())
    acc_pool = (pooled["TP"] + pooled["TN"]) / n_total if n_total else 0.0
    print("-" * 100)
    print(f"POOLED in-sample acc = {acc_pool:.3f}  "
          f"(TP={pooled['TP']} FP={pooled['FP']} TN={pooled['TN']} FN={pooled['FN']} n={n_total})")
    print("  sanity: in-sample acc should be ABOVE the 0.794 OOF figure and BELOW ~1.0")

    blob = {
        "schema_version": 2,
        "source": "win=preentry_cs100_v2;lose=preentry_cs100",
        "win_domain_suffix": WIN_SUFFIX,
        "lose_domain_suffix": LOSE_SUFFIX,
        "window": "[entry_ts - 30m, entry_ts]",
        "feature_set": FEATURE_SET,
        "decision_rule": (
            "admit iff score > threshold, where "
            "score = sum_k feature_weights[k] * (feature[k] - feature_stats[k].mean)"
            " / feature_stats[k].std; "
            "info_score = <c,c_win>/||c_win|| - <c,c_lose>/||c_lose||"
        ),
        "weights_definition": "per-pair Cohen's d (winners vs losers), sign-preserved, on full data",
        "threshold_definition": "midpoint of mean(winner scores) and mean(loser scores), full data",
        "side_sign_convention": "mean_dipole_signed = mean_dipole * (+1 buy/long/bullish, -1 sell/short/bearish)",
        "cv_validation": {
            "mode": "info_score_plus_flow",
            "calibrated_threshold": True,
            "pooled_acc": 0.794,
            "pooled_auc": 0.855,
            "FN": 183,
            "n": 2254,
            "folds": 5,
            "source_script": "_markets_combined_info_flow_kfold.py",
        },
        "refit_note": (
            "This file is a full-data refit (no held-out fold) of the CV-validated classifier; "
            "in-sample acc here exceeds the 0.794 OOF figure by construction. "
            "OOF 0.794/0.855 is the honest expectation for live admit-hit-rate."
        ),
        "pairs": pairs_out,
    }
    args.output.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"\nWrote {len(pairs_out)} pairs -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
