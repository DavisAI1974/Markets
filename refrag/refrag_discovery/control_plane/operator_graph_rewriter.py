from __future__ import annotations

from uuid import uuid4
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness


# Arch §8 Phase 6 + Rule 6 ("Analyze-only first ... Propose-and-simulate after
# trust ... Execute with approval tokens only"). Defaulting to analyze keeps
# every unparameterised invocation in the safe, read-only band of the manifest
# enum. The two side-effecting modes (``propose_and_simulate``, ``execute``)
# both require a non-empty approval_token; ``analyze`` is the only token-free
# entry point per spec §8 ("Analyze-only first. Propose-and-simulate after
# trust. Execute with approval tokens only.").
_TOKEN_REQUIRED_MODES = frozenset({"propose_and_simulate", "execute"})
_KNOWN_REWRITE_MODES = frozenset({"analyze", "analyze_only", "propose", "propose_and_simulate", "execute"})


def rewrite_operator_graph(
    *,
    operator_graph: dict[str, Any],
    performance_history: dict[str, Any],
    rewrite_mode: str = "analyze",
    approval_token: str | None = None,
    rewrite_budget: int = 3,
    max_graph_disruption: float = 0.15,
) -> dict[str, Any]:
    # Approval-token gate per arch §8 Phase 6 / Rule 6. Both side-effecting
    # modes — ``propose_and_simulate`` (writes simulation traces) and
    # ``execute`` (writes graph edits) — require a non-empty token. Only the
    # read-only ``analyze`` / ``analyze_only`` paths run without one.
    if rewrite_mode in _TOKEN_REQUIRED_MODES and not approval_token:
        raise ValueError(
            f"approval_token is required for rewrite_mode={rewrite_mode!r} "
            f"(arch §8 Phase 6 / Rule 6)."
        )
    nodes = list(operator_graph.get("nodes", []))
    edges = list(operator_graph.get("edges", []))
    stage_scores = performance_history.get("stage_scores", {})
    stage_latencies = performance_history.get("stage_latencies_ms", {})

    bottlenecks = sorted(stage_latencies, key=stage_latencies.get, reverse=True)[:rewrite_budget]
    low_health = [node_id for node_id, score in stage_scores.items() if float(score) < 0.5]
    redundancies = [node for node in nodes if sum(1 for edge in edges if edge.get("source") == node.get("id")) > 1]

    # Observable-driven health, proposal improvement, and proposal risk. The
    # previous version used hardcoded constants (0.08/0.07 in health_score,
    # 0.12/0.08 and 0.07/0.11 in proposals). The production_readiness block
    # for this operator still calls out that proposals aren't *learned from
    # historical graph edits* — that requires propose_and_simulate / execute
    # history that doesn't exist yet — but the values below are now derived
    # from the per-run perf data passed in via performance_history, so they
    # vary with the actual pipeline state instead of being constants.
    total_latency = sum(float(v) for v in stage_latencies.values()) or 1.0
    total_edges = max(1, len(edges))

    # Health composite of two normalised sub-scores in [0, 1]:
    #
    #   latency_balance: 1 - normalised HHI concentration. HHI = sum(share^2)
    #   over per-operator latency shares. Normalised concentration =
    #   (N*HHI - 1) / (N - 1), which is 0 for a perfectly balanced pipeline
    #   and 1 when a single operator owns 100% of latency. latency_balance =
    #   1 - that. This does NOT saturate to 0 when one operator dominates —
    #   e.g. one op at 90%, six others tiny → concentration ≈ 0.78, balance
    #   ≈ 0.22.
    #
    #   score_floor: mean over scored operators of (min(1, score / 0.5)),
    #   so a perfectly-scoring fleet → 1.0, all-zero scores → 0.0. score_floor
    #   only varies per-bucket if the upstream benchmark_suite call was made
    #   with per-bucket runtime_feedback (external_metrics_by_operator); when
    #   the adapter passes no feedback, scores collapse to manifest-property
    #   constants and score_floor becomes registry-invariant. The fix is at
    #   the adapter / benchmark_suite layer (pass per-bucket trace stats),
    #   not here.
    #
    # health_score = (latency_balance + score_floor) / 2. Both components
    # reported separately in `analysis` so consumers see what is driving
    # the composite rather than a single opaque number.
    n_lat = len(stage_latencies)
    if n_lat >= 2 and total_latency > 0:
        hhi = sum((float(v) / total_latency) ** 2 for v in stage_latencies.values())
        normalised_concentration = max(0.0, (n_lat * hhi - 1.0) / (n_lat - 1))
        latency_balance = max(0.0, 1.0 - normalised_concentration)
    elif n_lat == 1:
        latency_balance = 0.0  # single op owns everything
        normalised_concentration = 1.0
    else:
        latency_balance = 1.0  # no perf data → no concentration evidence
        normalised_concentration = 0.0

    # score_floor: mean of raw per-operator scores in [0, 1]. Earlier this
    # had a min(1, score/0.5) cap that mapped any score ≥ 0.5 to 1.0, which
    # made the metric invariant whenever most operators happened to be
    # above the 0.5 floor — losing the very per-bucket signal we needed.
    # Raw mean preserves that signal: a bucket where spectral_chunker scores
    # 0.85 vs 0.68 in another bucket actually changes score_floor now.
    if stage_scores:
        clean_scores = [max(0.0, min(1.0, float(s))) for s in stage_scores.values()]
        score_floor = sum(clean_scores) / len(clean_scores)
    else:
        score_floor = 1.0  # no score data → don't penalise

    health_score = round((latency_balance + score_floor) / 2, 4)

    analysis = {
        "bottlenecks": bottlenecks,
        "redundancies": [node.get("id") for node in redundancies[:rewrite_budget]],
        "friction_points": low_health[:rewrite_budget],
        "health_score": health_score,
        "health_components": {
            "latency_balance": round(latency_balance, 4),
            "latency_concentration": round(normalised_concentration, 4),
            "score_floor": round(score_floor, 4),
            "n_operators_with_latency": n_lat,
            "n_operators_with_score": len(stage_scores),
        },
    }
    proposed_rewrites = []
    for operator_id in bottlenecks[:rewrite_budget]:
        # cache_or_parallelize: improvement scales with the operator's share
        # of pipeline wall time, times a conservative cache-hit assumption of
        # 50% (caching never eliminates all of an operator's cost). Risk is
        # the operator's downstream fan-out as a fraction of total edges — a
        # blast-radius proxy.
        op_latency_share = float(stage_latencies.get(operator_id, 0.0)) / total_latency
        downstream_count = sum(1 for e in edges if e.get("source") == operator_id)
        proposed_rewrites.append(
            {
                "type": "cache_or_parallelize",
                "target": operator_id,
                "expected_improvement": round(0.5 * op_latency_share, 4),
                "risk": round(downstream_count / total_edges, 4),
            }
        )
    for node in redundancies[: max(0, rewrite_budget - len(proposed_rewrites))]:
        # merge_redundant_node: improvement is the node's latency share scaled
        # by the redundant fraction of its fan-out ((n-1)/n — merging n
        # consumers into one deduplicates n-1 of them). Risk gets a 1.5x bump
        # over caching because topology changes propagate more broadly than
        # transparent caches.
        node_id = node.get("id")
        node_latency_share = float(stage_latencies.get(node_id, 0.0)) / total_latency
        downstream_count = sum(1 for e in edges if e.get("source") == node_id)
        redundant_share = (downstream_count - 1) / max(1, downstream_count)
        proposed_rewrites.append(
            {
                "type": "merge_redundant_node",
                "target": node_id,
                "expected_improvement": round(node_latency_share * redundant_share, 4),
                "risk": round(min(1.0, 1.5 * (downstream_count / total_edges)), 4),
            }
        )

    simulation_results = [
        {
            "target": item["target"],
            "expected_health_delta": round(item["expected_improvement"] - item["risk"], 4),
            "regression_risk": item["risk"],
        }
        for item in proposed_rewrites
    ]

    execution_log = {
        "mode": rewrite_mode,
        "applied": [],
        "rollback_tokens": [],
    }
    if rewrite_mode == "execute":
        # approval_token presence already enforced above by _TOKEN_REQUIRED_MODES.
        allowed_rewrites = min(rewrite_budget, max(1, int(max_graph_disruption * max(1, len(edges)))))
        applied = proposed_rewrites[:allowed_rewrites]
        execution_log = {
            "mode": rewrite_mode,
            "approval_token": approval_token,
            "applied": applied,
            "rollback_tokens": [str(uuid4()) for _ in applied],
        }

    return with_production_readiness(
        "operator_graph_rewriter",
        {
            "analysis": analysis,
            "proposed_rewrites": proposed_rewrites,
            "simulation_results": simulation_results if rewrite_mode in {"propose_and_simulate", "execute"} else [],
            "execution_log": execution_log,
        },
    )
