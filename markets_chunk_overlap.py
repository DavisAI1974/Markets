"""
markets_chunk_overlap.py -- diagnostic for tier_search feature redundancy.

When markets_tier_search.py emits a cluster of singleton winners in the same
(venue, regime) cell with near-identical n, score, and CI, the most likely
explanation is that all those features are gating the SAME set of chunks --
i.e., they're literally redundant at the chunk-membership level, not just
correlated in some abstract sense.

This script proves or disproves that directly by computing pairwise Jaccard
overlap between the chunk-index sets each (feature, quartile) gate selects
within a given cell.

Reads tier_search's report JSON, groups singleton (arity=1) winners by
(venue, regime), recomputes each winner's chunk-set in-cell by rerunning
classify_venue + feature extraction + quartile assignment, then dumps the
Jaccard matrix per cluster.

A cluster with all pairwise Jaccard >= overlap_threshold (default 0.85) is
flagged: pick one representative (the one with highest CI-low * edge), drop
the rest, repeat tier_search with --features restricted to surviving
features.

A cluster with mixed Jaccard (say 0.4 - 0.8) is informational: the features
DO carry partially distinct information; per-cell permutation importance
(option B') is the appropriate next disambiguator.

A cluster with mostly low Jaccard means the redundancy hypothesis was wrong
and the score similarity was coincidence on this corpus -- commit them all.

Usage:
    python markets_chunk_overlap.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        --bybit-perp-bins eth_bybit_perp_bins.json \\
        --sibling-cb-bins btc_coinbase_bins.json --sibling-kr-bins btc_kraken_bins.json \\
        --tier-report /tmp/tier_eth_pairs.json \\
        [--overlap-threshold 0.85]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from markets_tier_search import (
    forward_log_returns,
    compute_global_feature_values,
    load_all_venue_contexts,
    build_cell_snapshot,
    resolve_feature_names,
)


def _build_chunk_indices_for_gate(snap, feature: str, quartile: int) -> set[int]:
    """Return the set of in-cell chunk positions where the named feature
    falls into the specified quartile, using the snapshot's pre-computed
    equal-count quartile assignments."""
    q = snap.feature_quartile.get(feature)
    if q is None:
        return set()
    return set(int(i) for i in np.where(q == quartile)[0])


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def analyze_cluster(cell_key: str,
                     winners: list[dict],
                     snap,
                     overlap_threshold: float) -> dict:
    """Compute pairwise Jaccard between the winner gates' chunk sets; return
    a verdict and a representative ranking."""
    # Build gate -> chunk-set map
    gate_sets: dict[tuple[str, int], set[int]] = {}
    for w in winners:
        # arity=1 only in this analysis
        if w["arity"] != 1:
            continue
        gate = w["gates"][0]
        key = (gate["feature"], gate["quartile"])
        gate_sets[key] = _build_chunk_indices_for_gate(
            snap, gate["feature"], gate["quartile"]
        )

    gate_list = list(gate_sets.keys())
    n = len(gate_list)
    if n < 2:
        return {
            "cell_key": cell_key,
            "n_singleton_winners": n,
            "verdict": "too_few_to_compare",
        }

    # Pairwise Jaccard
    matrix: list[list[float]] = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            jac = jaccard(gate_sets[gate_list[i]], gate_sets[gate_list[j]])
            matrix[i][j] = jac
            matrix[j][i] = jac

    # Identify high-overlap clusters: connected components where each edge
    # has Jaccard >= overlap_threshold. Simple union-find / BFS.
    cluster_id = list(range(n))
    def find(x):
        while cluster_id[x] != x:
            cluster_id[x] = cluster_id[cluster_id[x]]
            x = cluster_id[x]
        return x
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            cluster_id[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] >= overlap_threshold:
                union(i, j)

    cluster_groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        cluster_groups[find(i)].append(i)

    # For each cluster, rank members by (CI_low * edge_magnitude) to pick
    # the representative. Higher = better.
    winner_by_gate: dict[tuple[str, int], dict] = {
        (w["gates"][0]["feature"], w["gates"][0]["quartile"]): w
        for w in winners if w["arity"] == 1
    }
    cluster_summaries: list[dict] = []
    for cid, members in cluster_groups.items():
        ranked = sorted(
            members,
            key=lambda idx: -(winner_by_gate[gate_list[idx]]["score_ci_low"]
                                * winner_by_gate[gate_list[idx]]["edge_magnitude"]),
        )
        representative_idx = ranked[0]
        cluster_summaries.append({
            "size": len(members),
            "members": [f"{gate_list[i][0]}=Q{gate_list[i][1]}" for i in members],
            "representative": (f"{gate_list[representative_idx][0]}="
                                f"Q{gate_list[representative_idx][1]}"),
            "duplicates": [f"{gate_list[i][0]}=Q{gate_list[i][1]}"
                            for i in ranked[1:]],
            "min_intracluster_jaccard": (
                min(matrix[i][j] for i in members for j in members if i < j)
                if len(members) > 1 else 1.0
            ),
        })

    cluster_summaries.sort(key=lambda c: -c["size"])

    return {
        "cell_key": cell_key,
        "n_singleton_winners": n,
        "gate_list": [f"{g[0]}=Q{g[1]}" for g in gate_list],
        "jaccard_matrix": matrix,
        "clusters": cluster_summaries,
        "verdict": (
            "duplicates_found" if any(c["size"] > 1 for c in cluster_summaries)
            else "all_distinct"
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True, choices=["ETH", "BTC"])
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--tier-report", required=True,
                   help="Path to the markets_tier_search JSON report")
    p.add_argument("--overlap-threshold", type=float, default=0.85)
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true")
    p.add_argument("--output-report", default=None)
    args = p.parse_args()

    with open(args.tier_report) as f:
        report = json.load(f)
    print(f"=== loaded tier report: {report.get('n_winners', 0)} winners ===")

    # Group winners by (venue, regime), arity-1 only
    by_cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for w in report.get("winners", []):
        if w["arity"] != 1:
            continue
        by_cell[(w["venue_label"], w["regime"])].append(w)

    print(f"  arity-1 winners across {len(by_cell)} (venue, regime) cells")
    for (v, r), ws in sorted(by_cell.items()):
        print(f"    {v}/{r}: {len(ws)} singleton winners")

    # Reload classification to build cell snapshots
    feature_names_needed: set[str] = set()
    for w in report.get("winners", []):
        for g in w["gates"]:
            feature_names_needed.add(g["feature"])
    feature_names, skipped_pending, skipped_unknown = resolve_feature_names(
        sorted(feature_names_needed),
        include_hawkes_default=True,
    )
    if skipped_pending:
        print(f"  [skip] infrastructure-pending features removed from reload: "
              f"{', '.join(skipped_pending)}")
    if skipped_unknown:
        print(f"  [warn] unknown features ignored: {', '.join(skipped_unknown)}")
    if not feature_names:
        raise SystemExit("No active features left to reload after removing pending/unknown entries")
    compute_hawkes = "hawkes_eta" in feature_names
    compute_hurst = "hurst_delta" in feature_names

    print(f"\n=== reloading classification (features needed: {len(feature_names)}) ===")
    contexts = load_all_venue_contexts(
        asset=args.asset, cb_bins=args.cb_bins, kr_bins=args.kr_bins,
        perp_bins=args.bybit_perp_bins,
        sibling_cb_bins=args.sibling_cb_bins,
        sibling_kr_bins=args.sibling_kr_bins,
        chunk_max=args.chunk_max_size, chunk_min=args.chunk_min_segment,
        multi_pelt=args.multi_signal_pelt,
        compute_hawkes=compute_hawkes,
        compute_hurst=compute_hurst,
        feature_names=feature_names,
    )

    # Index contexts by venue label
    ctx_by_venue = {label: (ctx, results) for label, ctx, results in contexts}

    cluster_reports = []
    for (venue_label, regime), winners in sorted(by_cell.items()):
        if venue_label not in ctx_by_venue:
            print(f"\n  [skip] venue {venue_label} not in contexts")
            continue
        ctx, results = ctx_by_venue[venue_label]
        # Build the in-cell mask
        regime_mask = np.array([r.regime.value == regime for r in results])
        if int(regime_mask.sum()) < 8:
            print(f"\n  [skip] {venue_label}/{regime}: too few chunks ({int(regime_mask.sum())})")
            continue
        feat_vals = compute_global_feature_values(ctx, feature_names)
        fwd = forward_log_returns(ctx.chunks, k=1)
        snap = build_cell_snapshot(venue_label, regime, regime_mask, feat_vals, fwd)

        result = analyze_cluster(f"{venue_label}/{regime}", winners, snap,
                                    args.overlap_threshold)
        cluster_reports.append(result)

        print(f"\n=== {result['cell_key']} -- "
              f"{result['n_singleton_winners']} singleton winners, "
              f"verdict: {result['verdict']} ===")
        if "clusters" in result:
            for c in result["clusters"]:
                if c["size"] > 1:
                    print(f"  CLUSTER (size={c['size']}, "
                          f"min_intra_jaccard={c['min_intracluster_jaccard']:.3f}):")
                    print(f"    representative: {c['representative']}")
                    print(f"    duplicates ({len(c['duplicates'])}): {', '.join(c['duplicates'])}")
                else:
                    print(f"  SINGLETON: {c['members'][0]}")
        if "jaccard_matrix" in result and len(result["gate_list"]) <= 12:
            # Print compact Jaccard matrix
            gl = result["gate_list"]
            print(f"\n  Jaccard matrix:")
            short = [g[:30] for g in gl]
            print(f"    {'':>32} " + " ".join(f"{i:>5}" for i in range(len(gl))))
            for i, g in enumerate(short):
                row = " ".join(f"{result['jaccard_matrix'][i][j]:>5.2f}"
                                 for j in range(len(gl)))
                print(f"    [{i}] {g:<30} {row}")

    if args.output_report:
        with open(args.output_report, "w") as f:
            json.dump({"cluster_reports": cluster_reports,
                          "overlap_threshold": args.overlap_threshold},
                       f, indent=2)
        print(f"\n  report saved: {args.output_report}")


if __name__ == "__main__":
    main()
