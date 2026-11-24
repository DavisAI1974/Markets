from __future__ import annotations

import math
import re
from math import comb
from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.storage import load_json, operator_state_path, save_json, utc_now_iso
# Fix D / arch §3.3: lineage writes route through ``registry_writer`` so each
# write gets an audit-log entry. Falls back to ``save_json`` for non-registry
# kinds (the function only handles the lineage kind today). The local import
# avoids a circular dep — ``refrag_discovery.registry`` imports
# ``operator_lineage_tracker`` indirectly via the chain_builder's
# composability scorer.
def _registry_writer_write(operator_id, payload, artifacts_dir, intent):
    from refrag_discovery.registry.registry_writer import write_registry
    return write_registry(
        kind="lineage",
        operator_id=operator_id,
        payload=payload,
        artifacts_dir=artifacts_dir,
        intent=intent,
    )


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _semver_key(version: str) -> tuple[int, int, int, str]:
    match = SEMVER_RE.match(version)
    if not match:
        return (0, 0, 0, version)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), version)


def _increment_patch(version: str) -> str:
    match = SEMVER_RE.match(version)
    if not match:
        return f"{version}.next"
    major, minor, patch = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return f"{major}.{minor}.{patch + 1}"


def _flatten_numeric_metrics(payload: Any, prefix: str = "") -> dict[str, float]:
    metrics: dict[str, float] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            metrics.update(_flatten_numeric_metrics(value, child_prefix))
    elif isinstance(payload, list):
        return metrics
    elif isinstance(payload, bool):
        return metrics
    elif isinstance(payload, (int, float)):
        metrics[prefix] = float(payload)
    return metrics


def _version_score(record: dict[str, Any]) -> float:
    benchmark = record.get("performance_benchmark", {})
    metrics = _flatten_numeric_metrics(benchmark)
    if "summary.overall_score" in metrics:
        return metrics["summary.overall_score"]
    if "summary.health_score" in metrics:
        return metrics["summary.health_score"]
    if metrics:
        return sum(metrics.values()) / max(1, len(metrics))
    return 0.0


def _schema_components(snapshot: dict[str, Any] | None, field_name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return {}
    components = snapshot.get(field_name, [])
    if not isinstance(components, list):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for item in components:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        normalized[name] = {
            "type": str(item.get("type", "")),
            "required": bool(item.get("required", False)),
        }
    return normalized


def _schema_diff(current_snapshot: dict[str, Any], parent_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    parent_inputs = _schema_components(parent_snapshot, "inputs")
    current_inputs = _schema_components(current_snapshot, "inputs")
    parent_outputs = _schema_components(parent_snapshot, "outputs")
    current_outputs = _schema_components(current_snapshot, "outputs")

    def added(current: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"name": name, **current[name]}
            for name in sorted(set(current) - set(previous))
        ]

    def removed(current: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"name": name, **previous[name]}
            for name in sorted(set(previous) - set(current))
        ]

    def modified(current: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for name in sorted(set(current) & set(previous)):
            before = previous[name]
            after = current[name]
            if before != after:
                changes.append({"name": name, "before": before, "after": after})
        return changes

    added_inputs = added(current_inputs, parent_inputs)
    removed_inputs = removed(current_inputs, parent_inputs)
    modified_inputs = modified(current_inputs, parent_inputs)
    added_outputs = added(current_outputs, parent_outputs)
    removed_outputs = removed(current_outputs, parent_outputs)
    modified_outputs = modified(current_outputs, parent_outputs)

    breaking_change = any(
        [
            removed_inputs,
            removed_outputs,
            modified_inputs,
            modified_outputs,
            [item for item in added_inputs if item.get("required")],
        ]
    )

    return {
        "added_inputs": added_inputs,
        "removed_inputs": removed_inputs,
        "modified_inputs": modified_inputs,
        "added_outputs": added_outputs,
        "removed_outputs": removed_outputs,
        "modified_outputs": modified_outputs,
        "breaking_change": breaking_change,
    }


def _version_depth(version: str, versions: dict[str, dict[str, Any]]) -> int:
    depth = 0
    current = version
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        parent = str(versions.get(current, {}).get("parent_version", "") or "")
        if not parent:
            break
        current = parent
        depth += 1
    return depth


def _sign_test_p_value(positive: int, negative: int) -> float:
    sample_count = positive + negative
    if sample_count == 0:
        return 1.0
    lower_tail = sum(comb(sample_count, idx) for idx in range(0, min(positive, negative) + 1))
    return min(1.0, round((2.0 * lower_tail) / (2**sample_count), 6))


def _version_comparison(current: dict[str, Any], parent: dict[str, Any] | None) -> dict[str, Any]:
    if parent is None:
        return {
            "compared_to": None,
            "statistical_test": "not_available",
            "sample_count": 0,
            "positive_deltas": 0,
            "negative_deltas": 0,
            "median_delta": 0.0,
            "effect_size": 0.0,
            "p_value": 1.0,
            "trajectory": "baseline",
        }

    current_metrics = _flatten_numeric_metrics(current.get("performance_benchmark", {}))
    parent_metrics = _flatten_numeric_metrics(parent.get("performance_benchmark", {}))
    common_keys = sorted(set(current_metrics) & set(parent_metrics))
    deltas = [current_metrics[key] - parent_metrics[key] for key in common_keys if current_metrics[key] != parent_metrics[key]]

    positive = sum(1 for value in deltas if value > 0)
    negative = sum(1 for value in deltas if value < 0)
    median_delta = 0.0
    if deltas:
        ordered = sorted(deltas)
        median_delta = ordered[len(ordered) // 2]
        if len(ordered) % 2 == 0:
            median_delta = (ordered[(len(ordered) // 2) - 1] + ordered[len(ordered) // 2]) / 2.0

    effect_size = 0.0
    if deltas:
        effect_size = sum(deltas) / max(1, len(deltas))

    trajectory = "flat"
    if positive and not negative:
        trajectory = "improving"
    elif negative and not positive:
        trajectory = "regressing"
    elif positive and negative:
        trajectory = "mixed"

    return {
        "compared_to": parent.get("version"),
        "statistical_test": "sign_test",
        "sample_count": len(deltas),
        "positive_deltas": positive,
        "negative_deltas": negative,
        "median_delta": round(median_delta, 6),
        "effect_size": round(effect_size, 6),
        "p_value": _sign_test_p_value(positive, negative),
        "trajectory": trajectory,
        "common_metrics": common_keys,
    }


def _version_embeddings(versions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ordered_versions = sorted(versions, key=_semver_key)
    embeddings: dict[str, dict[str, Any]] = {}
    for version in ordered_versions:
        record = versions[version]
        snapshot = record.get("schema_snapshot", {})
        schema_complexity = len(_schema_components(snapshot, "inputs")) + len(_schema_components(snapshot, "outputs"))
        embeddings[version] = {
            "embedding": [
                float(_version_depth(version, versions)),
                round(_version_score(record), 6),
                float(schema_complexity),
                float(len(record.get("changelog", []))),
            ]
        }

    predicted_next_version = _increment_patch(ordered_versions[-1]) if ordered_versions else "0.0.1"
    return {
        "embeddings": embeddings,
        "predicted_next_version": predicted_next_version,
    }


def _recommendations(
    version: str,
    versions: dict[str, dict[str, Any]],
    schema_diff: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    best_version = version
    best_score = float("-inf")
    for candidate_version, record in versions.items():
        score = _version_score(record)
        if score > best_score or (math.isclose(score, best_score) and _semver_key(candidate_version) > _semver_key(best_version)):
            best_score = score
            best_version = candidate_version

    promotion_candidate = None
    if not schema_diff.get("breaking_change") and comparison.get("trajectory") != "regressing":
        promotion_candidate = version

    return {
        "best_version_for_production": best_version,
        "best_version_for_performance": best_version,
        "promotion_candidate_version": promotion_candidate,
        "regression_detected": comparison.get("trajectory") == "regressing",
    }


def track_operator_lineage(
    *,
    operator_id: str,
    version: str,
    parent_version: str | None = None,
    derivation_type: str = "upgrade",
    changelog: list[str] | None = None,
    schema_snapshot: dict[str, Any] | None = None,
    performance_benchmark: dict[str, Any] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    path = operator_state_path("lineage", operator_id, artifacts_dir)
    state = load_json(
        path,
        {
            "operator_id": operator_id,
            "versions": {},
            "history": [],
        },
    )

    versions = dict(state.get("versions", {}))
    record = {
        "version": version,
        "parent_version": parent_version,
        "derivation_type": derivation_type,
        "changelog": list(changelog or []),
        "schema_snapshot": dict(schema_snapshot or {}),
        "performance_benchmark": dict(performance_benchmark or {}),
        "recorded_at": utc_now_iso(),
    }
    versions[version] = record
    history = list(state.get("history", []))
    history.append(
        {
            "event": "lineage_registered",
            "version": version,
            "parent_version": parent_version,
            "recorded_at": record["recorded_at"],
        }
    )

    ordered_versions = sorted(versions, key=_semver_key)
    parent_record = versions.get(parent_version) if parent_version else None
    schema_diff = _schema_diff(record["schema_snapshot"], parent_record.get("schema_snapshot") if parent_record else None)
    comparison = _version_comparison(record, parent_record)

    lineage_graph = {
        "nodes": [
            {
                "version": candidate_version,
                "parent_version": versions[candidate_version].get("parent_version"),
                "depth": _version_depth(candidate_version, versions),
                "score": round(_version_score(versions[candidate_version]), 6),
            }
            for candidate_version in ordered_versions
        ],
        "edges": [
            {
                "source": versions[candidate_version]["parent_version"],
                "target": candidate_version,
                "derivation_type": versions[candidate_version].get("derivation_type", "upgrade"),
            }
            for candidate_version in ordered_versions
            if versions[candidate_version].get("parent_version")
        ],
        "current_best_version": _recommendations(version, versions, schema_diff, comparison)["best_version_for_production"],
        "current_depth": _version_depth(version, versions),
    }
    embeddings = _version_embeddings(versions)
    recommendations = _recommendations(version, versions, schema_diff, comparison)

    _registry_writer_write(
        operator_id=operator_id,
        payload={
            "operator_id": operator_id,
            "versions": versions,
            "history": history,
            "latest_version": version,
        },
        artifacts_dir=artifacts_dir,
        intent="lineage_registration",
    )

    return {
        "lineage_graph": lineage_graph,
        "schema_diff": schema_diff,
        "version_comparison": comparison,
        "version_embeddings": embeddings,
        "recommendations": recommendations,
    }
