"""Control-plane discovery operators."""

from __future__ import annotations

import os

from refrag_discovery.control_plane.cross_domain_transfer_detector import detect_cross_domain_transfer
from refrag_discovery.control_plane.exploration_policy_controller import plan_exploration_policy
from refrag_discovery.control_plane.manifest_synthesizer import synthesize_manifests
from refrag_discovery.control_plane.production_readiness import (
    heuristic_production_readiness,
    is_heuristic_control_plane_operator,
)
from typing import Any

from refrag_discovery.control_plane.operator_chain_builder import build_operator_chain
from refrag_discovery.control_plane.operator_benchmark_suite import benchmark_operators
from refrag_discovery.control_plane.operator_composability_scorer import score_operator_composability
from refrag_discovery.control_plane.operator_gap_finder import analyze_operator_gaps
from refrag_discovery.control_plane.operator_graph_rewriter import rewrite_operator_graph
from refrag_discovery.control_plane.operator_lifecycle_tracker import track_operator_lifecycle
from refrag_discovery.control_plane.operator_lineage_tracker import track_operator_lineage
from refrag_discovery.control_plane.operator_promotion_recommender import recommend_operator_promotion
from refrag_discovery.control_plane.pipeline_performance_optimizer import optimize_pipeline_performance
from refrag_discovery.control_plane.stubs import CONTROL_PLANE_STUBS, get_control_plane_stub as _get_stub
from refrag_discovery.control_plane.task_meta_learner import run_task_meta_learner


# Arch §8 Phase 6 + Rule 6: operator_graph_rewriter must remain DISABLED until
# Phase 5 validation results are reviewed. Self-rewriting systems are dangerous
# early. Set ENABLE_GRAPH_REWRITER=1 in the environment to opt in once Phase 5
# review is complete; otherwise the dispatcher refuses to invoke it.
_GRAPH_REWRITER_ENABLE_ENV = "ENABLE_GRAPH_REWRITER"


def _graph_rewriter_enabled() -> bool:
    return os.environ.get(_GRAPH_REWRITER_ENABLE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


IMPLEMENTED_CONTROL_PLANE_OPERATORS = {
    "cross_domain_transfer_detector": {
        "status": "available",
        "message": "Cross-domain transfer analysis is enabled.",
    },
    "exploration_policy_controller": {
        "status": "available",
        "message": "Exploration policy planning is enabled.",
    },
    "manifest_synthesizer": {
        "status": "available",
        "message": "Manifest synthesis from execution traces is enabled.",
    },
    "operator_chain_builder": {
        "status": "available",
        "message": "Deterministic operator chain planning is enabled.",
    },
    "operator_benchmark_suite": {
        "status": "available",
        "message": "Persistence-backed benchmark runs are enabled.",
    },
    "operator_composability_scorer": {
        "status": "available",
        "message": "Deterministic operator composability scoring is enabled.",
    },
    "operator_gap_finder": {
        "status": "available",
        "message": "Registry gap analysis is enabled.",
    },
    "operator_graph_rewriter": {
        # Arch §8 Phase 6 / Rule 6 gate: real status is computed dynamically
        # by ``get_control_plane_stub`` based on ENABLE_GRAPH_REWRITER. The
        # entry stays in the table so registry lookups still find the operator;
        # the dispatcher refuses to actually invoke it when the gate is off.
        "status": "gated",
        "message": (
            "graph_rewriter is gated per arch §8 Phase 6 / Rule 6. "
            "Set ENABLE_GRAPH_REWRITER=1 to opt in after Phase 5 review."
        ),
    },
    "operator_lifecycle_tracker": {
        "status": "available",
        "message": "Persistence-backed lifecycle tracking is enabled.",
    },
    "operator_lineage_tracker": {
        "status": "available",
        "message": "Persistence-backed lineage tracking is enabled.",
    },
    "operator_promotion_recommender": {
        "status": "available",
        "message": "Promotion readiness analysis is enabled.",
    },
    "pipeline_performance_optimizer": {
        "status": "available",
        "message": "Persistence-backed pipeline optimization is enabled.",
    },
    "task_meta_learner": {
        "status": "available",
        "message": "Persistence-backed task meta-learning is enabled.",
    },
}


def get_control_plane_stub(operator_id: str) -> dict[str, Any]:
    implemented = IMPLEMENTED_CONTROL_PLANE_OPERATORS.get(operator_id)
    if implemented is not None:
        response = {"operator_id": operator_id, **implemented}
        # Resolve the §8 Phase 6 gate dynamically so the reported status
        # reflects the current environment instead of the dict's static label.
        if operator_id == "operator_graph_rewriter":
            if _graph_rewriter_enabled():
                response["status"] = "available"
                response["message"] = (
                    "Graph rewrite analysis is enabled "
                    "(ENABLE_GRAPH_REWRITER=1)."
                )
            else:
                response["status"] = "disabled"
        if is_heuristic_control_plane_operator(operator_id):
            response["production_readiness"] = heuristic_production_readiness(operator_id)
        return response
    return _get_stub(operator_id)


def call_control_plane_operator(
    operator_id: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    arguments = dict(arguments or {})
    if operator_id == "cross_domain_transfer_detector":
        return detect_cross_domain_transfer(**arguments)
    if operator_id == "exploration_policy_controller":
        return plan_exploration_policy(**arguments)
    if operator_id == "manifest_synthesizer":
        return synthesize_manifests(**arguments)
    if operator_id == "operator_chain_builder":
        return build_operator_chain(**arguments)
    if operator_id == "operator_lineage_tracker":
        return track_operator_lineage(**arguments)
    if operator_id == "operator_lifecycle_tracker":
        return track_operator_lifecycle(**arguments)
    if operator_id == "operator_benchmark_suite":
        return benchmark_operators(**arguments)
    if operator_id == "operator_composability_scorer":
        return score_operator_composability(**arguments)
    if operator_id == "operator_gap_finder":
        return analyze_operator_gaps(**arguments)
    if operator_id == "operator_graph_rewriter":
        # Arch §8 Phase 6 + Rule 6: graph rewriter STAYS DISABLED until Phase
        # 5 validation is reviewed. Refuse to dispatch unless the operator is
        # explicitly opted-in via ENABLE_GRAPH_REWRITER=1.
        if not _graph_rewriter_enabled():
            return {
                "operator_id": "operator_graph_rewriter",
                "status": "disabled",
                "message": (
                    "graph_rewriter disabled per arch §8 Phase 6 / Rule 6. "
                    "Set ENABLE_GRAPH_REWRITER=1 to opt in after Phase 5 "
                    "review."
                ),
            }
        return rewrite_operator_graph(**arguments)
    if operator_id == "operator_promotion_recommender":
        return recommend_operator_promotion(**arguments)
    if operator_id == "pipeline_performance_optimizer":
        return optimize_pipeline_performance(**arguments)
    if operator_id == "task_meta_learner":
        return run_task_meta_learner(**arguments)
    if operator_id in CONTROL_PLANE_STUBS:
        return _get_stub(operator_id)
    raise KeyError(operator_id)


__all__ = [
    "CONTROL_PLANE_STUBS",
    "IMPLEMENTED_CONTROL_PLANE_OPERATORS",
    "benchmark_operators",
    "build_operator_chain",
    "call_control_plane_operator",
    "get_control_plane_stub",
    "optimize_pipeline_performance",
    "analyze_operator_gaps",
    "recommend_operator_promotion",
    "run_task_meta_learner",
    "detect_cross_domain_transfer",
    "plan_exploration_policy",
    "rewrite_operator_graph",
    "score_operator_composability",
    "synthesize_manifests",
    "track_operator_lifecycle",
    "track_operator_lineage",
]
