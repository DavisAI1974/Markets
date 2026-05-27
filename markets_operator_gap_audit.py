"""Markets operator-gap audit: build a manifest registry for our admission +
exit operators, call refrag's operator_gap_finder formally, and surface what
admission rules / data types / tasks our current stack is missing.

Adapter pattern — refrag tools are meta-tools that operate on operator
registries. To use them on Markets we have to express our admission stack
as a registry of manifests. This file is that adapter.

Usage:
    python markets_operator_gap_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any

# Add E:\refrag to path so we can import refrag_discovery modules directly.
REFRAG_ROOT = Path(r"E:\refrag")
if str(REFRAG_ROOT) not in sys.path:
    sys.path.insert(0, str(REFRAG_ROOT))

from refrag_discovery.control_plane.operator_gap_finder import analyze_operator_gaps  # noqa: E402


# ---------------------------------------------------------------------------
# Markets operator manifests
# ---------------------------------------------------------------------------

MARKETS_OPERATOR_REGISTRY: list[dict[str, Any]] = [
    {
        "operator_id": "wilson_admission",
        "operator_name": "Wilson Admission Gate",
        "description": (
            "Per-canonical-key Wilson lower bound vs rolling break-even win-rate. "
            "Returns admit_bank / admit_shadow / reject based on self-evidence on the "
            "outcome ledger. Cold-start (n<10) defaults to admit_shadow."
        ),
        "domain": "per_trade_admission",
        "capabilities": [
            "wilson_lower_bound",
            "break_even_winrate_derivation",
            "per_canonical_key_evidence",
            "cold_start_to_shadow",
        ],
        "inputs": [
            {"name": "canonical_trade_key", "type": "canonical_trade_key"},
            {"name": "outcome_ledger", "type": "outcome_ledger"},
            {"name": "rolling_payoff_stats", "type": "payoff_stats"},
        ],
        "outputs": [
            {"name": "admission_decision", "type": "admission_decision"},
        ],
    },
    {
        "operator_id": "protective_admission",
        "operator_name": "Protective Admission Gate (Wilson + K-NN demote)",
        "description": (
            "Wilson admission + K-NN identity-pooled demote on marginal admissions. "
            "Demotes admit_bank/admit_shadow to reject when same-identity (strategy, "
            "asset, side) neighbors are clearly losing."
        ),
        "domain": "per_trade_admission",
        "capabilities": [
            "wilson_lower_bound",
            "knn_identity_pool",
            "negative_evidence_override_to_reject",
            "structural_correlation_guard",
        ],
        "inputs": [
            {"name": "canonical_trade_key", "type": "canonical_trade_key"},
            {"name": "outcome_ledger", "type": "outcome_ledger"},
            {"name": "identity_neighbors", "type": "identity_neighbors"},
        ],
        "outputs": [
            {"name": "admission_decision", "type": "admission_decision"},
        ],
    },
    {
        "operator_id": "in_flight_promote",
        "operator_name": "In-Flight Shadow→Bank Promotion",
        "description": (
            "Mid-trade per-tick check that flips role from oracle_shadow to "
            "bank_allocated when a winning shape emerges: hold_min>=60 (with positive "
            "net_bps) OR first crossing of +20 bps within 30 minutes, gated by a "
            "quality floor of net_bps_per_min >= 0.3."
        ),
        "domain": "per_trade_in_flight",
        "capabilities": [
            "reached_20bps_within_30m_signal",
            "hold_min_ge_60_signal",
            "net_bps_per_min_quality_gate",
            "mid_trade_role_flip_shadow_to_bank",
            "monotonic_event_tracking",
        ],
        "inputs": [
            {"name": "trade_state", "type": "trade_state"},
            {"name": "net_bps", "type": "net_bps"},
            {"name": "elapsed_min", "type": "elapsed_min"},
        ],
        "outputs": [
            {"name": "role_flip", "type": "role_flip"},
            {"name": "promotion_signal", "type": "promotion_signal"},
        ],
    },
    {
        "operator_id": "promoted_context_allowlist",
        "operator_name": "Promoted-Context Allowlist (Phase 2, parked)",
        "description": (
            "Pre-protective upgrade: when wilson admit_shadow AND (asset, venue, "
            "side, session, family) matches a high-conviction entry from "
            "_study_list.json (pnl_R >= 100, trades >= 30, WR <= 0.95), upgrade to "
            "admit_bank. Currently parked due to data-source mismatch on the 67k "
            "tape — kept for reference."
        ),
        "domain": "per_trade_admission",
        "capabilities": [
            "context_family_lookup",
            "pnl_r_conviction_filter",
            "trades_sample_filter",
            "wr_ceiling_filter",
            "pre_protective_positive_evidence_override",
        ],
        "inputs": [
            {"name": "wilson_decision", "type": "admission_decision"},
            {"name": "context_family_tuple", "type": "context_family_tuple"},
            {"name": "allowlist_state", "type": "allowlist_state"},
        ],
        "outputs": [
            {"name": "admission_decision", "type": "admission_decision"},
        ],
    },
    {
        "operator_id": "fee_cover_15m_exit",
        "operator_name": "Fee-Cover-By-15m Hard Exit",
        "description": (
            "Cuts the trade at 15 minutes if fees have not been covered (net_bps "
            "never crossed 0). Per policy ground truth, 98% of historic winners "
            "covered fees within 15m, so the non-covering 2% tail are losers."
        ),
        "domain": "per_trade_exit",
        "capabilities": [
            "fee_cover_observation",
            "fixed_15min_timeout",
            "hard_negative_gate",
        ],
        "inputs": [
            {"name": "trade_state", "type": "trade_state"},
            {"name": "elapsed_min", "type": "elapsed_min"},
            {"name": "net_bps", "type": "net_bps"},
        ],
        "outputs": [
            {"name": "exit_decision", "type": "exit_decision"},
        ],
    },
    {
        "operator_id": "trailing_safety_net_exit",
        "operator_name": "Trailing Safety Net (arm at 20bps, giveback)",
        "description": (
            "Once net_bps >= +20, arm a trailing stop with giveback = max(12 bps, "
            "25% of peak). Catches winners that reverse before hitting oracle "
            "horizon."
        ),
        "domain": "per_trade_exit",
        "capabilities": [
            "trailing_arm_at_20bps",
            "giveback_max_12bps_or_25pct",
            "peak_tracking",
        ],
        "inputs": [
            {"name": "trade_state", "type": "trade_state"},
            {"name": "max_net_unrealized_bps", "type": "net_bps"},
            {"name": "current_net_bps", "type": "net_bps"},
        ],
        "outputs": [
            {"name": "exit_decision", "type": "exit_decision"},
        ],
    },
    {
        "operator_id": "oracle_horizon_exit",
        "operator_name": "Oracle Horizon Default Exit",
        "description": (
            "Default: hold each open trade to the oracle entry's horizon_minutes "
            "(typically 1-40 min, median ~17-22 min for current 52-entry JSON)."
        ),
        "domain": "per_trade_exit",
        "capabilities": [
            "oracle_horizon_min_hold",
            "default_exit_path",
        ],
        "inputs": [
            {"name": "trade_state", "type": "trade_state"},
            {"name": "elapsed_min", "type": "elapsed_min"},
            {"name": "hold_minutes_horizon", "type": "hold_minutes_horizon"},
        ],
        "outputs": [
            {"name": "exit_decision", "type": "exit_decision"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Gap-finder inputs: target domains, known data types, known tasks
# ---------------------------------------------------------------------------

# What we want covered. Items NOT present in any manifest will surface as gaps.
TARGET_DOMAINS = [
    "per_trade_admission",
    "per_trade_in_flight",
    "per_trade_exit",
    "continuous_feature_similarity",    # Phase 3 / refrag retrieval
    "chunk_pattern_matching",            # Phase 3.5 / chunk analyzer integration
    "expected_value_ranking",            # rankcore territory
    "bank_demote_in_flight",             # symmetric to in_flight_promote, not built
    "in_flight_reject",                  # mid-trade kill on stall, not built
    "drawdown_invariants",               # guarantee-system territory
    "operator_lifecycle_tracking",       # refrag_discovery territory
]

# Data types our system observes or wants to consume. Items with no producer or
# consumer in any manifest surface as orphan data.
KNOWN_DATA_TYPES = [
    "canonical_trade_key",
    "net_bps",
    "elapsed_min",
    "tte_20bps_min",
    "hold_min",
    "net_bps_per_min",
    "cover_by_15m",
    "mfe_bps",
    "mae_bps",
    "outcome_ledger",
    "identity_neighbors",
    "context_family_tuple",
    "allowlist_state",
    "trade_state",
    "admission_decision",
    "exit_decision",
    "role_flip",
    "promotion_signal",
    "continuous_feature_embedding",      # not used yet — Phase 3 would consume
    "chunk_feature_vector",              # not used yet — chunk analyzer output
    "operator_lineage",                  # not tracked
    "drawdown_state",                    # not tracked
    "expected_value_score",              # not produced
    "rolling_payoff_stats",
]

# Plain-language tasks we want done by SOME operator. Tasks with zero token
# overlap with the operator descriptions/capabilities surface as anomalous.
KNOWN_TASKS = [
    "reject known losers at entry by per-key Wilson lower bound",
    "shadow uncertain evidence at entry until enough self-evidence accumulates",
    "admit strong evidence to bank at entry when confidence clears break-even",
    "promote a winning shadow trade to bank attribution mid-flight when winning shape emerges",
    "demote a falling bank trade to shadow mid-flight when negative signals fire",
    "kill a stalled trade at 15 minutes if fees have not been covered",
    "rank candidate trades by expected value to prioritize the best opportunities",
    "match in-flight path against historical winning chunk patterns",
    "detect a drawdown invariant violation and halt trading on that platform",
    "match continuous feature similarity to find positive sub-cohorts inside rejected canonical keys",
    "track operator lifecycle state (candidate, stable, decaying, promoted)",
]


def main():
    print("=" * 100, flush=True)
    print("MARKETS OPERATOR GAP AUDIT", flush=True)
    print("(refrag_discovery.operator_gap_finder applied to current admission + exit stack)", flush=True)
    print("=" * 100, flush=True)

    print(f"\nRegistry: {len(MARKETS_OPERATOR_REGISTRY)} operators", flush=True)
    for m in MARKETS_OPERATOR_REGISTRY:
        print(f"  - {m['operator_id']:30s} domain={m['domain']:30s} "
              f"caps={len(m['capabilities'])}", flush=True)

    print(f"\nProbing:", flush=True)
    print(f"  target_domains = {len(TARGET_DOMAINS)}", flush=True)
    print(f"  known_data_types = {len(KNOWN_DATA_TYPES)}", flush=True)
    print(f"  known_tasks = {len(KNOWN_TASKS)}", flush=True)

    report = analyze_operator_gaps(
        registry_snapshot=MARKETS_OPERATOR_REGISTRY,
        target_domains=TARGET_DOMAINS,
        known_data_types=KNOWN_DATA_TYPES,
        known_tasks=KNOWN_TASKS,
        depth="geometric",
    )

    print("\n" + "=" * 100, flush=True)
    print("GAP-FINDER OUTPUT", flush=True)
    print("=" * 100, flush=True)

    gaps = report.get("gaps", [])
    if gaps:
        print(f"\n--- DOMAIN / DATA-TYPE GAPS ({len(gaps)}) ---", flush=True)
        for g in sorted(gaps, key=lambda r: -r["severity"]):
            print(f"  [{g['kind']:>10s}]  severity={g['severity']:.2f}  "
                  f"target='{g['target']}'  {g['reason']}", flush=True)

    dead_ends = report.get("dead_ends", [])
    if dead_ends:
        print(f"\n--- DEAD-END OPERATORS ({len(dead_ends)}) ---", flush=True)
        print("  (output type not consumed by any other manifest)", flush=True)
        for d in dead_ends:
            print(f"    {d}", flush=True)

    unreachable = report.get("unreachable_outputs", [])
    if unreachable:
        print(f"\n--- UNREACHABLE OUTPUT TYPES ({len(unreachable)}) ---", flush=True)
        print("  (produced by an operator but consumed by none — orphan data)", flush=True)
        for u in unreachable:
            print(f"    {u}", flush=True)

    anomalous = report.get("anomalous_tasks", [])
    if anomalous:
        print(f"\n--- ANOMALOUS TASKS ({len(anomalous)}) ---", flush=True)
        print("  (task description has zero token overlap with any operator)", flush=True)
        for a in anomalous:
            print(f"  err={a['reconstruction_error']:.2f}  '{a['task']}'", flush=True)
            print(f"            -> {a['reason']}", flush=True)

    heatmap = report.get("coverage_heatmap", {})
    print(f"\n--- COVERAGE HEATMAP ---", flush=True)
    print(f"  domain_counts:", flush=True)
    for d, c in sorted(heatmap.get("domain_counts", {}).items(), key=lambda kv: -kv[1]):
        print(f"    {d:>32s}  {c}", flush=True)
    print(f"  input_type_counts (top 10):", flush=True)
    for t, c in sorted(heatmap.get("input_type_counts", {}).items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {t:>32s}  {c}", flush=True)
    print(f"  output_type_counts (top 10):", flush=True)
    for t, c in sorted(heatmap.get("output_type_counts", {}).items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {t:>32s}  {c}", flush=True)
    print(f"  capability_counts (top 10):", flush=True)
    for c, n in sorted(heatmap.get("capability_counts", {}).items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {c:>32s}  {n}", flush=True)

    recs = report.get("recommendations", [])
    if recs:
        print(f"\n--- RECOMMENDATIONS ({len(recs)}) ---", flush=True)
        for r in recs:
            print(f"  Suggested operator: {r['operator_id']}", flush=True)
            print(f"    name: {r['draft_manifest']['operator_name']}", flush=True)
            print(f"    description: {r['draft_manifest']['description']}", flush=True)

    pr = report.get("production_readiness", {})
    if pr:
        print(f"\n--- PRODUCTION-READINESS NOTES ---", flush=True)
        for k, v in pr.items():
            if isinstance(v, (str, int, float)):
                print(f"  {k}: {v}", flush=True)
            elif isinstance(v, list) and v and isinstance(v[0], str):
                print(f"  {k}:", flush=True)
                for item in v:
                    print(f"    - {item}", flush=True)


if __name__ == "__main__":
    main()
