from __future__ import annotations

from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.registry import build_default_operator_query


def score_operator_composability(
    *,
    operator_a: str,
    operator_b: str,
    evaluation_mode: str = "full",
    context_chain: list[str] | None = None,
) -> dict[str, Any]:
    query = build_default_operator_query()
    manifest_a = query.get_manifest(operator_a)
    manifest_b = query.get_manifest(operator_b)
    outputs_a = {str(item.get("type", "")).lower() for item in manifest_a.get("outputs", []) if item.get("type")}
    inputs_b = {str(item.get("type", "")).lower() for item in manifest_b.get("inputs", []) if item.get("type")}
    shared_types = sorted(outputs_a & inputs_b)

    capabilities_a = {str(item).lower() for item in manifest_a.get("capabilities", [])}
    capabilities_b = {str(item).lower() for item in manifest_b.get("capabilities", [])}
    capability_overlap = len(capabilities_a & capabilities_b)
    dependency_bonus = 0.15 if operator_a in query.resolve_dependencies(operator_b, transitive=False) else 0.0
    shared_type_score = 0.55 if shared_types else 0.1
    context_bonus = 0.05 if context_chain and operator_a in context_chain else 0.0

    learned_compatibility_score = round(
        min(1.0, shared_type_score + (0.08 * capability_overlap) + dependency_bonus + context_bonus),
        4,
    )
    composability_score = round(min(1.0, learned_compatibility_score + (0.1 if evaluation_mode in {"empirical", "full"} else 0.0)), 4)

    predicted_failure_modes = []
    if not shared_types:
        predicted_failure_modes.append({"mode": "io_type_mismatch", "probability": 0.72})
    if capability_overlap == 0:
        predicted_failure_modes.append({"mode": "semantic_drift", "probability": 0.41})

    adapter_suggestions = []
    if not shared_types:
        search_results = query.search(text="adapter bridge transform", top_k=5)
        adapter_suggestions = [item.operator_id for item in search_results]

    return with_production_readiness(
        "operator_composability_scorer",
        {
            "composability_score": composability_score,
            "type_compatibility": {
                "shared_output_input_types": shared_types,
                "compatible": bool(shared_types),
            },
            "learned_compatibility_score": learned_compatibility_score,
            "predicted_failure_modes": predicted_failure_modes,
            "adapter_suggestions": adapter_suggestions,
        },
    )
