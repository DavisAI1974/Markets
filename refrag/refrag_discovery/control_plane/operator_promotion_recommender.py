from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.operator_lifecycle_tracker import track_operator_lifecycle
from refrag_discovery.control_plane.operator_lineage_tracker import track_operator_lineage
from refrag_discovery.registry import build_default_operator_query


def recommend_operator_promotion(
    *,
    operator_id: str,
    evaluation_window: str = "P30D",
    include_schema_suggestions: bool = True,
    run_counterfactual: bool = True,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    query = build_default_operator_query()
    manifest = query.get_manifest(operator_id)
    # Fix B: thread ``artifacts_dir`` so sandbox isolation works. Without
    # this, both lifecycle + lineage calls always read the global state,
    # breaking per-scenario benchmark runs (arch §3.3 sandbox isolation).
    lifecycle = track_operator_lifecycle(
        operator_id=operator_id,
        artifacts_dir=artifacts_dir,
    )
    lineage = track_operator_lineage(
        operator_id=operator_id,
        version=str(manifest.get("lineage", {}).get("version", "0.0.0")),
        schema_snapshot=manifest,
        artifacts_dir=artifacts_dir,
    )

    promotion_score = 0.22
    blocking_issues: list[str] = []
    state = lifecycle["current_state"]
    if state in {"stable", "promoted"}:
        promotion_score += 0.28
    else:
        blocking_issues.append(f"Lifecycle state is {state}")
    if lifecycle["drift_status"]["drift_detected"]:
        promotion_score -= 0.12
        blocking_issues.append("Drift is currently detected")
    if manifest.get("visibility") != "public":
        blocking_issues.append("Manifest visibility is internal")
    if manifest.get("governance", {}).get("approval_required"):
        blocking_issues.append("Governance requires explicit approval")
    if lineage["schema_diff"].get("breaking_change"):
        blocking_issues.append("Latest schema change is breaking")
    if manifest.get("operator_type") == "template":
        promotion_score += 0.08
    if manifest.get("execution_class") == "runtime":
        promotion_score += 0.1

    promotion_score = round(max(0.0, min(1.0, promotion_score)), 4)
    recommendation = "hold"
    if promotion_score >= 0.75 and not blocking_issues:
        recommendation = "promote"
    elif promotion_score < 0.25:
        recommendation = "retire"

    schema_suggestions: dict[str, Any] = {}
    if include_schema_suggestions:
        schema_suggestions = {
            "public_name": operator_id.replace("operator_", ""),
            "expose_inputs": [item.get("name") for item in manifest.get("inputs", [])[:3]],
            "expose_outputs": [item.get("name") for item in manifest.get("outputs", [])[:3]],
            "hide_internal_fields": ["governance", "lineage", "registry"],
        }

    counterfactual_analysis = {}
    if run_counterfactual:
        counterfactual_analysis = {
            "if_visibility_public": round(min(1.0, promotion_score + 0.18), 4),
            "if_stable_no_drift": round(min(1.0, promotion_score + 0.24), 4),
            "evaluation_window": evaluation_window,
        }

    return with_production_readiness(
        "operator_promotion_recommender",
        {
            "promotion_score": promotion_score,
            "recommendation": recommendation,
            "blocking_issues": blocking_issues,
            "schema_suggestions": schema_suggestions,
            "feature_importances": {
                "lifecycle_state": 0.36,
                "drift_status": 0.24,
                "visibility": 0.2,
                "schema_stability": 0.12,
                "operator_type": 0.08,
            },
            "counterfactual_analysis": counterfactual_analysis,
        },
    )
