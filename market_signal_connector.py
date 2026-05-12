"""
market_signal_connector.py — offline prototype of the Pass-18 convergence layer.

Runs the existing tier search, then detects chunks where multiple tier-hitting
feature cells all point in the same direction at once. Those are the
"convergence chunks" the handoff calls out as the next confidence tier above
single-feature high-conviction signals.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict

import numpy as np

from markets_tier_search import (
    DEFAULT_TIERS,
    _combo_mask,
    dedupe_keep_best_tier,
    dedupe_singletons_by_chunk_jaccard,
    load_all_venue_contexts,
    resolve_feature_names,
    run_search,
)


def _winner_key(combo) -> str:
    gates = ",".join(f"{gate.feature}=Q{gate.quartile}" for gate in combo.gates)
    return f"{combo.venue_label}/{combo.regime}/{gates}/{combo.direction}/{combo.tier}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True)
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--features", nargs="*", default=None)
    p.add_argument("--max-arity", type=int, default=2)
    p.add_argument("--bootstrap-samples", type=int, default=1000)
    p.add_argument("--multi-signal-pelt", action="store_true")
    p.add_argument("--dedupe-by-jaccard", type=float, default=0.85)
    p.add_argument("--min-support", type=int, default=3)
    p.add_argument("--output-path", default="market_signal_connector.json")
    args = p.parse_args()

    feature_names, skipped_pending, skipped_unknown = resolve_feature_names(args.features)
    if skipped_pending:
        print(f"[connector] skipped pending: {', '.join(skipped_pending)}", flush=True)
    if skipped_unknown:
        print(f"[connector] skipped unknown: {', '.join(skipped_unknown)}", flush=True)
    if not feature_names:
        raise SystemExit("no active features selected")

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
    winners, snapshot_cache = run_search(
        args.asset,
        contexts,
        feature_names=feature_names,
        tiers=DEFAULT_TIERS,
        bootstrap_samples=args.bootstrap_samples,
        max_arity=args.max_arity,
        rng=rng,
    )
    winners = dedupe_keep_best_tier(winners, DEFAULT_TIERS)
    if args.dedupe_by_jaccard > 0:
        winners, dedup_log = dedupe_singletons_by_chunk_jaccard(
            winners, snapshot_cache, args.dedupe_by_jaccard, DEFAULT_TIERS)
    else:
        dedup_log = []

    support_by_chunk: dict[tuple[str, int], list[dict]] = defaultdict(list)
    chunk_meta: dict[tuple[str, int], dict] = {}
    for combo in winners:
        snap = snapshot_cache.get((combo.venue_label, combo.regime))
        if snap is None:
            continue
        cell_idx = np.where(snap.in_cell_mask)[0]
        fired_local = np.where(_combo_mask(snap, combo.gates))[0]
        fired_global = cell_idx[fired_local]
        venue_ctx = next((ctx for label, ctx, _results in contexts if label == combo.venue_label), None)
        if venue_ctx is None:
            continue
        for global_idx in fired_global:
            key = (combo.venue_label, int(global_idx))
            bars = venue_ctx.chunks[int(global_idx)].bars
            chunk_meta[key] = {
                "venue_label": combo.venue_label,
                "chunk_index": int(global_idx),
                "regime": combo.regime,
                "ts_start": float(bars[0].ts) if bars else 0.0,
                "ts_end": float(bars[-1].ts) if bars else 0.0,
            }
            support_by_chunk[key].append({
                "winner_key": _winner_key(combo),
                "feature_gates": [
                    {"feature": gate.feature, "quartile": gate.quartile}
                    for gate in combo.gates
                ],
                "direction": combo.direction,
                "tier": combo.tier,
                "score_ci_low": combo.score_ci_low,
                "edge_magnitude": combo.edge_magnitude,
            })

    convergence_events: list[dict] = []
    for key, support in support_by_chunk.items():
        by_direction: dict[str, list[dict]] = defaultdict(list)
        for item in support:
            by_direction[item["direction"]].append(item)
        for direction, aligned in by_direction.items():
            if len(aligned) < args.min_support:
                continue
            avg_ci = float(np.mean([item["score_ci_low"] for item in aligned]))
            avg_edge = float(np.mean([item["edge_magnitude"] for item in aligned]))
            event = {
                **chunk_meta[key],
                "direction": direction,
                "support_count": len(aligned),
                "supporting_winners": aligned,
                "confidence_tier": "convergence" if len(aligned) >= max(args.min_support + 1, 4) else "high_conviction",
                "avg_score_ci_low": avg_ci,
                "avg_edge_magnitude": avg_edge,
            }
            convergence_events.append(event)

    convergence_events.sort(
        key=lambda row: (-row["support_count"], -row["avg_score_ci_low"], row["venue_label"], row["chunk_index"])
    )
    out = {
        "schema_version": 1,
        "asset": args.asset,
        "generated_utc": int(time.time()),
        "min_support": args.min_support,
        "n_winners": len(winners),
        "n_convergence_events": len(convergence_events),
        "dedupe_log": dedup_log,
        "events": convergence_events,
    }
    with open(args.output_path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[connector] wrote {args.output_path}: {len(convergence_events)} convergence chunks from {len(winners)} winners")


if __name__ == "__main__":
    main()
