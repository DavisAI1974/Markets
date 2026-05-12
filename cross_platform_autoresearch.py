"""cross_platform_autoresearch.py — pairwise cross-platform cell discovery.

Searches pairwise feature-quartile interactions inside each (venue, regime)
cell, applies BH-FDR discipline per cell, and emits appendable suggestions for
`cells_registry.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from itertools import combinations, product

import numpy as np

from phase1_5_evaluator import FEATURE_EXTRACTORS
from markets_tier_search import (
    DEFAULT_TIERS,
    FeatureGate,
    append_to_registry,
    build_cell_entry,
    build_cell_snapshot,
    build_predicate,
    compute_global_feature_values,
    dedupe_keep_best_tier,
    forward_log_returns,
    load_all_venue_contexts,
    resolve_feature_names,
    score_combination,
)


FEATURE_META = {
    name: {"group": group, "role": role, "fn": fn}
    for name, group, role, fn in FEATURE_EXTRACTORS
}


def _default_feature_names() -> list[str]:
    names, _, _ = resolve_feature_names(None)
    selected: list[str] = []
    for name in names:
        meta = FEATURE_META.get(name) or {}
        if meta.get("role") != "predictor":
            continue
        if name == "hawkes_eta":
            continue
        selected.append(name)
    return selected


def _pair_is_relevant(left: str, right: str) -> bool:
    lmeta = FEATURE_META.get(left) or {}
    rmeta = FEATURE_META.get(right) or {}
    lgroup = lmeta.get("group")
    rgroup = rmeta.get("group")
    return (
        lgroup == "cross_platform"
        or rgroup == "cross_platform"
        or lgroup == "novel"
        or rgroup == "novel"
        or lgroup != rgroup
    )


def _binom_tail_ge(n: int, k: int) -> float:
    if n <= 0:
        return 1.0
    numer = sum(math.comb(n, i) for i in range(k, n + 1))
    denom = 2 ** n
    return float(numer / denom)


def _combo_p_value(combo) -> float:
    n = int(combo.n_in_combo)
    if n <= 0:
        return 1.0
    hit_rate = float(combo.score_point)
    hits = int(round(hit_rate * n))
    hits = max(0, min(n, hits))
    extreme = max(hits, n - hits)
    return min(1.0, 2.0 * _binom_tail_ge(n, extreme))


def _bh_fdr(rows: list[dict], q: float) -> list[dict]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: row["p_value"])
    m = len(ordered)
    cutoff_rank = 0
    for idx, row in enumerate(ordered, start=1):
        if row["p_value"] <= (idx / m) * q:
            cutoff_rank = idx
    out: list[dict] = []
    for idx, row in enumerate(ordered, start=1):
        bh_q = min(1.0, row["p_value"] * m / idx)
        row = dict(row)
        row["bh_rank"] = idx
        row["bh_q"] = bh_q
        row["passes_fdr"] = idx <= cutoff_rank
        out.append(row)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True, choices=["ETH", "BTC"])
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--cutoffs", default=None)
    p.add_argument("--features", nargs="*", default=None)
    p.add_argument("--bootstrap-samples", type=int, default=1000)
    p.add_argument("--multi-signal-pelt", action="store_true")
    p.add_argument("--fdr-q", type=float, default=0.10)
    p.add_argument("--min-n", type=int, default=10)
    p.add_argument("--base-notional", type=float, default=1000.0)
    p.add_argument("--pass-num", type=int, default=18)
    p.add_argument("--append-to-registry", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output-path", default="cross_platform_autoresearch.json")
    args = p.parse_args()

    if args.features is None:
        feature_names = _default_feature_names()
        skipped_pending: list[str] = []
        skipped_unknown: list[str] = []
    else:
        feature_names, skipped_pending, skipped_unknown = resolve_feature_names(args.features)
        feature_names = [
            name for name in feature_names
            if (FEATURE_META.get(name) or {}).get("role") == "predictor"
        ]
    if skipped_pending:
        print(f"[autoresearch] skipped pending: {', '.join(skipped_pending)}", flush=True)
    if skipped_unknown:
        print(f"[autoresearch] skipped unknown: {', '.join(skipped_unknown)}", flush=True)
    if not feature_names:
        raise SystemExit("no active predictor features selected")

    contexts = load_all_venue_contexts(
        args.asset,
        cb_bins=args.cb_bins,
        kr_bins=args.kr_bins,
        perp_bins=args.bybit_perp_bins,
        sibling_cb_bins=args.sibling_cb_bins,
        sibling_kr_bins=args.sibling_kr_bins,
        multi_pelt=args.multi_signal_pelt,
        compute_hawkes=("hawkes_eta" in feature_names),
        compute_hurst=("hurst_delta" in feature_names),
        feature_names=feature_names,
    )
    rng = np.random.default_rng(seed=0)
    cutoffs = {}
    if args.cutoffs:
        with open(args.cutoffs) as fh:
            cutoffs = json.load(fh)

    cell_reports: list[dict] = []
    suggestions: list[dict] = []

    for venue_label, ctx, results in contexts:
        feat_vals = compute_global_feature_values(ctx, feature_names)
        if not feat_vals:
            continue
        fwd = forward_log_returns(ctx.chunks, k=1)
        regimes_observed = sorted({r.regime.value for r in results})
        for regime in regimes_observed:
            mask = np.array([r.regime.value == regime for r in results], dtype=bool)
            if int(mask.sum()) < 8:
                continue
            snap = build_cell_snapshot(venue_label, regime, mask, feat_vals, fwd)
            tests: list[dict] = []
            active_features = [name for name in feature_names if name in snap.feature_quartile]
            for left, right in combinations(active_features, 2):
                if not _pair_is_relevant(left, right):
                    continue
                for q_left, q_right in product((1, 2, 3, 4), repeat=2):
                    combo = score_combination(
                        snap,
                        tuple(sorted(
                            (FeatureGate(left, q_left), FeatureGate(right, q_right)),
                            key=lambda gate: (gate.feature, gate.quartile),
                        )),
                        args.bootstrap_samples,
                        DEFAULT_TIERS,
                        rng,
                    )
                    if combo is None or combo.n_in_combo < args.min_n:
                        continue
                    tests.append({
                        "combo": combo,
                        "p_value": _combo_p_value(combo),
                    })

            tested = _bh_fdr(tests, args.fdr_q)
            survivors = [row for row in tested if row["passes_fdr"] and row["combo"].tier is not None]
            winners = dedupe_keep_best_tier([row["combo"] for row in survivors], DEFAULT_TIERS)
            winner_keys = {
                (
                    combo.venue_label,
                    combo.regime,
                    frozenset((gate.feature, gate.quartile) for gate in combo.gates),
                    combo.direction,
                )
                for combo in winners
            }

            winner_rows = []
            for row in survivors:
                combo = row["combo"]
                key = (
                    combo.venue_label,
                    combo.regime,
                    frozenset((gate.feature, gate.quartile) for gate in combo.gates),
                    combo.direction,
                )
                if key not in winner_keys:
                    continue
                winner_rows.append(row)

            winner_rows.sort(
                key=lambda row: (
                    row["combo"].tier or "",
                    row["combo"].score_ci_low,
                    row["combo"].edge_magnitude,
                ),
                reverse=True,
            )

            append_entries: list[dict] = []
            for row in winner_rows:
                combo = row["combo"]
                tier_spec = next(t for t in DEFAULT_TIERS if t.name == combo.tier)
                predicate = build_predicate(
                    combo,
                    cutoffs,
                    cell_key=f"{combo.venue_label}/{combo.regime}",
                    fallback_uppers_by_feature=snap.feature_quartile_upper,
                )
                entry = build_cell_entry(
                    combo,
                    asset=args.asset,
                    tier_spec=tier_spec,
                    base_notional=args.base_notional,
                    predicate=predicate,
                    pass_num=args.pass_num,
                )
                entry["provenance"]["discovery_method"] = "cross_platform_autoresearch"
                entry["provenance"]["fdr_q_target"] = args.fdr_q
                entry["provenance"]["binomial_p_value"] = row["p_value"]
                entry["provenance"]["bh_q_value"] = row["bh_q"]
                append_entries.append(entry)
                suggestions.append(entry)

            cell_reports.append({
                "venue_label": venue_label,
                "regime": regime,
                "n_cell_chunks": snap.n_cell_chunks,
                "n_tests": len(tests),
                "n_fdr_survivors": len(survivors),
                "n_winners": len(winner_rows),
                "winners": [
                    {
                        "tier": row["combo"].tier,
                        "direction": row["combo"].direction,
                        "side": row["combo"].side,
                        "n_in_combo": row["combo"].n_in_combo,
                        "score_point": row["combo"].score_point,
                        "score_ci_low": row["combo"].score_ci_low,
                        "score_ci_high": row["combo"].score_ci_high,
                        "edge_magnitude": row["combo"].edge_magnitude,
                        "mean_fwd": row["combo"].mean_fwd,
                        "p_value": row["p_value"],
                        "bh_q": row["bh_q"],
                        "gates": [
                            {"feature": gate.feature, "quartile": gate.quartile}
                            for gate in row["combo"].gates
                        ],
                    }
                    for row in winner_rows
                ],
                "append_entries": append_entries,
            })

    appended = 0
    if args.append_to_registry and suggestions:
        appended = append_to_registry(
            args.append_to_registry,
            suggestions,
            dry_run=args.dry_run,
        )

    out = {
        "schema_version": 1,
        "generated_utc": int(time.time()),
        "asset": args.asset,
        "fdr_q": args.fdr_q,
        "n_feature_candidates": len(feature_names),
        "n_suggestions": len(suggestions),
        "appended": appended,
        "cells": cell_reports,
    }
    with open(args.output_path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(
        f"[autoresearch] wrote {args.output_path}: "
        f"{len(suggestions)} suggestions across {len(cell_reports)} cells"
    )


if __name__ == "__main__":
    main()
