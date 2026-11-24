from __future__ import annotations

from collections import Counter
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness

def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in text.replace("-", " ").replace("_", " ").split() if token}


def _default_registry_snapshot() -> list[dict[str, Any]]:
    from refrag_discovery.registry import build_default_operator_query

    return build_default_operator_query().list_manifests()


def analyze_operator_gaps(
    *,
    registry_snapshot: list[dict[str, Any]] | None = None,
    target_domains: list[str] | None = None,
    known_data_types: list[str] | None = None,
    known_tasks: list[str] | None = None,
    depth: str = "geometric",
) -> dict[str, Any]:
    manifests = list(registry_snapshot or _default_registry_snapshot())
    target_domains = [str(item).lower() for item in (target_domains or [])]
    known_data_types = [str(item).lower() for item in (known_data_types or [])]
    known_tasks = [str(item) for item in (known_tasks or [])]

    capability_counts = Counter(
        capability
        for manifest in manifests
        for capability in manifest.get("capabilities", [])
    )
    domain_counts = Counter(str(manifest.get("domain", "unknown")).lower() for manifest in manifests)
    input_types = Counter(
        str(item.get("type", "")).lower()
        for manifest in manifests
        for item in manifest.get("inputs", [])
        if item.get("type")
    )
    output_types = Counter(
        str(item.get("type", "")).lower()
        for manifest in manifests
        for item in manifest.get("outputs", [])
        if item.get("type")
    )

    gaps: list[dict[str, Any]] = []
    for domain in target_domains:
        if domain_counts.get(domain, 0) == 0:
            gaps.append(
                {
                    "kind": "domain",
                    "target": domain,
                    "severity": 0.95,
                    "reason": "No operators cover this domain.",
                }
            )
    for data_type in known_data_types:
        if input_types.get(data_type, 0) == 0 and output_types.get(data_type, 0) == 0:
            gaps.append(
                {
                    "kind": "data_type",
                    "target": data_type,
                    "severity": 0.85,
                    "reason": "No manifest references this data type.",
                }
            )

    dead_ends: list[str] = []
    produced_types = {
        str(item.get("type", "")).lower()
        for manifest in manifests
        for item in manifest.get("outputs", [])
        if item.get("type")
    }
    consumed_types = {
        str(item.get("type", "")).lower()
        for manifest in manifests
        for item in manifest.get("inputs", [])
        if item.get("type")
    }
    for manifest in manifests:
        output_type_set = {
            str(item.get("type", "")).lower()
            for item in manifest.get("outputs", [])
            if item.get("type")
        }
        if output_type_set and output_type_set.isdisjoint(consumed_types):
            dead_ends.append(str(manifest["operator_id"]))

    unreachable_outputs = sorted(produced_types - consumed_types)

    anomalous_tasks: list[dict[str, Any]] = []
    search_corpus = " ".join(
        " ".join(
            [
                str(manifest.get("operator_id", "")),
                str(manifest.get("operator_name", "")),
                str(manifest.get("description", "")),
                " ".join(str(item) for item in manifest.get("capabilities", [])),
            ]
        )
        for manifest in manifests
    ).lower()
    for task in known_tasks:
        task_tokens = _tokenize(task)
        overlap = len(task_tokens & _tokenize(search_corpus))
        if overlap == 0:
            anomalous_tasks.append(
                {
                    "task": task,
                    "reconstruction_error": 1.0,
                    "reason": "No token overlap with current operator registry.",
                }
            )

    recommendations = [
        {
            "operator_id": f"{gap['target']}_bridge_operator",
            "draft_manifest": {
                "operator_name": f"{gap['target'].title()} Bridge Operator",
                "description": f"Suggested to cover missing {gap['kind']} gap for {gap['target']}.",
                "capabilities": ["gap_closure"],
            },
        }
        for gap in gaps[:3]
    ]

    coverage_heatmap = {
        "depth": depth,
        "domain_counts": dict(domain_counts),
        "input_type_counts": dict(input_types),
        "output_type_counts": dict(output_types),
        "capability_counts": dict(capability_counts),
    }

    return with_production_readiness(
        "operator_gap_finder",
        {
            "gaps": gaps,
            "dead_ends": sorted(dead_ends),
            "unreachable_outputs": unreachable_outputs,
            "coverage_heatmap": coverage_heatmap,
            "anomalous_tasks": anomalous_tasks,
            "recommendations": recommendations,
        },
    )
