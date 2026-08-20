"""Deterministic GDL-derived P0 controls for provisional Frankie research.

These functions validate causal/provenance and evaluation contracts.  They do
not implement a GNN, TGN, learned topology, Deep Sets model, calibration method,
candidate promotion, permanent memory mutation, or V4 execution.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "FRANKIE_GDL_P0_CONTROLS_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

LAWFUL_INVARIANT_TRANSFORMS = frozenset({"INPUT_REORDER", "NODE_RELABEL"})
INTENTIONALLY_HARMFUL_TRANSFORMS = frozenset(
    {"DIRECTION_REVERSAL", "TIMESTAMP_DELAY", "POLARITY_FLIP", "CRITICAL_EDGE_REMOVAL"}
)

FORBIDDEN_PREBIRTH_FIELDS = frozenset(
    {
        "target_t0",
        "target_birth_at",
        "seconds_to_target_birth",
        "prior_h_identity",
        "target_polarity",
        "target_family",
        "target_depth",
        "future_target_exists",
    }
)

REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES = frozenset(
    {
        "SOURCE_MEMORY",
        "SUMMARY",
        "EMBEDDING",
        "RETRIEVAL_INDEX",
        "CACHE",
        "FEATURE",
        "PREDICTION",
        "EVALUATION",
    }
)


class GDLControlError(ValueError):
    """Raised when a GDL control contract is malformed or contradicted."""


def _sha256_json(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GDLControlError(f"value is not canonical JSON: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 256:
        raise GDLControlError(f"{label} must be a non-empty bounded identifier")
    return text


def _parse_iso(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise GDLControlError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GDLControlError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise GDLControlError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping_sequence(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GDLControlError(f"{label} must be a sequence")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise GDLControlError(f"{label}[{index}] must be an object")
        result.append(dict(item))
    return result


def _nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            keys.update(str(key) for key in current)
            pending.extend(current.values())
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            pending.extend(current)
    return keys


def audit_causal_prefix(
    events: Sequence[Mapping[str, Any]],
    *,
    prefix_event_ids: Sequence[str],
    requested_cutoff_at: str,
    availability_ceiling_at: str | None = None,
    target_birth_at: str | None = None,
    forbidden_prebirth_fields: Iterable[str] = FORBIDDEN_PREBIRTH_FIELDS,
) -> dict[str, Any]:
    """Verify one exact point-in-time prefix and bind its effective cutoff.

    ``events`` is the complete event universe available to the caller.  Prefix
    completeness is checked, not merely the absence of future rows.  An event is
    eligible only when both its occurrence and knowability timestamps are no
    later than ``min(requested_cutoff_at, availability_ceiling_at)``.  Ordering is
    deterministic by effective time, occurrence, knowability, and event id.
    """

    requested = _parse_iso(requested_cutoff_at, "requested_cutoff_at")
    ceiling = (
        _parse_iso(availability_ceiling_at, "availability_ceiling_at")
        if availability_ceiling_at is not None
        else requested
    )
    effective_cutoff = min(requested, ceiling)
    birth = _parse_iso(target_birth_at, "target_birth_at") if target_birth_at else None
    forbidden = {str(value).strip() for value in forbidden_prebirth_fields}
    if not forbidden or any(not value for value in forbidden):
        raise GDLControlError("forbidden_prebirth_fields must contain bounded field names")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(_mapping_sequence(events, "events")):
        event_id = _identifier(raw.get("event_id"), f"events[{index}].event_id")
        if event_id in seen:
            raise GDLControlError(f"duplicate causal event id: {event_id}")
        seen.add(event_id)
        occurred = _parse_iso(raw.get("occurred_at"), f"event {event_id}.occurred_at")
        knowable = _parse_iso(raw.get("knowable_at"), f"event {event_id}.knowable_at")
        effective = max(occurred, knowable)
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise GDLControlError(f"event {event_id}.payload must be an object")
        role = str(raw.get("role") or "OBSERVATION").strip().upper()
        if not role:
            raise GDLControlError(f"event {event_id}.role must be non-empty")
        if birth is not None and role.startswith("TARGET") and effective < birth:
            raise GDLControlError(f"target event {event_id} is represented before target birth")
        normalized.append(
            {
                "event_id": event_id,
                "occurred_at": _iso(occurred),
                "knowable_at": _iso(knowable),
                "effective_at": _iso(effective),
                "role": role,
                "payload": dict(payload),
                "source_hash": _sha256_json(raw),
            }
        )

    eligible = [
        event
        for event in normalized
        if _parse_iso(event["occurred_at"], "normalized occurred_at") <= effective_cutoff
        and _parse_iso(event["knowable_at"], "normalized knowable_at") <= effective_cutoff
    ]
    eligible.sort(
        key=lambda event: (
            event["effective_at"],
            event["occurred_at"],
            event["knowable_at"],
            event["event_id"],
        )
    )
    expected_ids = [event["event_id"] for event in eligible]
    supplied_ids = [_identifier(value, "prefix event id") for value in prefix_event_ids]
    if len(set(supplied_ids)) != len(supplied_ids):
        raise GDLControlError("prefix_event_ids must be unique")
    if supplied_ids != expected_ids:
        missing = sorted(set(expected_ids) - set(supplied_ids))
        extra = sorted(set(supplied_ids) - set(expected_ids))
        raise GDLControlError(
            "causal prefix is not the exact eligible ordered prefix; "
            f"missing={missing}, extra={extra}, expected_order={expected_ids}"
        )

    prebirth = birth is not None and effective_cutoff < birth
    prebirth_violations: list[dict[str, Any]] = []
    if prebirth:
        for event in eligible:
            found = sorted(_nested_keys(event["payload"]).intersection(forbidden))
            if event["role"].startswith("TARGET") or found:
                prebirth_violations.append(
                    {
                        "event_id": event["event_id"],
                        "role": event["role"],
                        "forbidden_fields": found,
                    }
                )
    if prebirth_violations:
        raise GDLControlError(
            "causal prefix contains target-derived information before target birth: "
            + json.dumps(prebirth_violations, sort_keys=True)
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "requested_cutoff_at": _iso(requested),
        "availability_ceiling_at": _iso(ceiling),
        "effective_cutoff_at": _iso(effective_cutoff),
        "target_birth_at": _iso(birth) if birth else None,
        "prebirth_target_firewall_applied": prebirth,
        "target_firewall_passed": True,
        "event_universe_hash": _sha256_json(normalized),
        "prefix_event_ids": expected_ids,
        "prefix_event_hashes": [event["source_hash"] for event in eligible],
        "prefix_hash": _sha256_json(eligible),
        "ordering_policy": "EFFECTIVE_THEN_OCCURRED_THEN_KNOWABLE_THEN_EVENT_ID",
        "validator_only": True,
        "model_authority": "NONE",
    }
    return {**core, "audit_hash": _sha256_json(core)}


def _normalize_graph(graph: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        raise GDLControlError(f"{label} must be an object")
    directed = graph.get("directed")
    if not isinstance(directed, bool):
        raise GDLControlError(f"{label}.directed must be boolean")
    nodes = _mapping_sequence(graph.get("nodes"), f"{label}.nodes")
    edges = _mapping_sequence(graph.get("edges"), f"{label}.edges")
    node_ids: set[str] = set()
    normalized_nodes: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        node_id = _identifier(node.get("node_id"), f"{label}.nodes[{index}].node_id")
        if node_id in node_ids:
            raise GDLControlError(f"{label} has duplicate node id: {node_id}")
        node_ids.add(node_id)
        normalized_nodes.append({**node, "node_id": node_id})
    edge_ids: set[str] = set()
    normalized_edges: list[dict[str, Any]] = []
    for index, edge in enumerate(edges):
        edge_id = _identifier(edge.get("edge_id"), f"{label}.edges[{index}].edge_id")
        source = _identifier(edge.get("source"), f"edge {edge_id}.source")
        target = _identifier(edge.get("target"), f"edge {edge_id}.target")
        if edge_id in edge_ids:
            raise GDLControlError(f"{label} has duplicate edge id: {edge_id}")
        if source not in node_ids or target not in node_ids:
            raise GDLControlError(f"edge {edge_id} cites an unknown endpoint")
        edge_ids.add(edge_id)
        normalized_edges.append({**edge, "edge_id": edge_id, "source": source, "target": target})
    metadata = {key: value for key, value in graph.items() if key not in {"nodes", "edges", "directed"}}
    return {
        "directed": directed,
        "metadata": metadata,
        "nodes": sorted(normalized_nodes, key=lambda node: node["node_id"]),
        "edges": sorted(normalized_edges, key=lambda edge: edge["edge_id"]),
    }


def _by_id(values: Sequence[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(value[key]): dict(value) for value in values}


def _without(value: Mapping[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in keys}


def _prediction_vector(value: Mapping[str, Any], label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise GDLControlError(f"{label} must be a non-empty probability map")
    result: dict[str, float] = {}
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise GDLControlError(f"{label}.{key} must be numeric")
        number = float(raw)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise GDLControlError(f"{label}.{key} must be finite within [0, 1]")
        result[str(key)] = number
    if not math.isclose(sum(result.values()), 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise GDLControlError(f"{label} probabilities must sum to one")
    return result


def _validate_same_nodes_and_metadata(base: Mapping[str, Any], challenger: Mapping[str, Any]) -> None:
    if (
        base["directed"] != challenger["directed"]
        or base["metadata"] != challenger["metadata"]
        or base["nodes"] != challenger["nodes"]
    ):
        raise GDLControlError("graph perturbation changed nodes, directedness, or graph metadata")


def _validate_graph_transform(
    base: Mapping[str, Any],
    challenger: Mapping[str, Any],
    transform: str,
    node_mapping: Mapping[str, str] | None,
) -> list[str]:
    base_edges = _by_id(base["edges"], "edge_id")
    challenger_edges = _by_id(challenger["edges"], "edge_id")

    if transform == "INPUT_REORDER":
        if base != challenger:
            raise GDLControlError("INPUT_REORDER must preserve the canonical graph exactly")
        return []

    if transform == "NODE_RELABEL":
        if not isinstance(node_mapping, Mapping):
            raise GDLControlError("NODE_RELABEL requires node_mapping")
        mapping = {str(key): str(value) for key, value in node_mapping.items()}
        base_nodes = _by_id(base["nodes"], "node_id")
        challenger_nodes = _by_id(challenger["nodes"], "node_id")
        if set(mapping) != set(base_nodes) or set(mapping.values()) != set(challenger_nodes):
            raise GDLControlError("node_mapping must be a bijection over the two node sets")
        if all(key == value for key, value in mapping.items()):
            raise GDLControlError("NODE_RELABEL requires at least one changed node id")
        if base["directed"] != challenger["directed"] or base["metadata"] != challenger["metadata"]:
            raise GDLControlError("NODE_RELABEL changed graph metadata")
        for source_id, target_id in mapping.items():
            if _without(base_nodes[source_id], {"node_id"}) != _without(
                challenger_nodes[target_id], {"node_id"}
            ):
                raise GDLControlError("NODE_RELABEL changed node attributes")
        if set(base_edges) != set(challenger_edges):
            raise GDLControlError("NODE_RELABEL changed edge identities")
        for edge_id, edge in base_edges.items():
            expected = {
                **edge,
                "source": mapping[edge["source"]],
                "target": mapping[edge["target"]],
            }
            if expected != challenger_edges[edge_id]:
                raise GDLControlError(f"NODE_RELABEL changed edge semantics: {edge_id}")
        return sorted(key for key, value in mapping.items() if key != value)

    _validate_same_nodes_and_metadata(base, challenger)
    if transform != "CRITICAL_EDGE_REMOVAL" and set(base_edges) != set(challenger_edges):
        raise GDLControlError(f"{transform} must preserve edge identities")

    changed: list[str] = []
    if transform == "DIRECTION_REVERSAL":
        if not base["directed"]:
            raise GDLControlError("DIRECTION_REVERSAL requires a directed graph")
        for edge_id, edge in base_edges.items():
            other = challenger_edges[edge_id]
            if edge == other:
                continue
            if (
                edge["source"] == other["target"]
                and edge["target"] == other["source"]
                and _without(edge, {"source", "target"})
                == _without(other, {"source", "target"})
            ):
                changed.append(edge_id)
            else:
                raise GDLControlError(f"DIRECTION_REVERSAL made an undeclared change: {edge_id}")
    elif transform == "TIMESTAMP_DELAY":
        for edge_id, edge in base_edges.items():
            other = challenger_edges[edge_id]
            if edge == other:
                continue
            if _without(edge, {"timestamp"}) != _without(other, {"timestamp"}):
                raise GDLControlError(f"TIMESTAMP_DELAY made an undeclared change: {edge_id}")
            before = _parse_iso(edge.get("timestamp"), f"edge {edge_id}.timestamp")
            after = _parse_iso(other.get("timestamp"), f"challenger edge {edge_id}.timestamp")
            if after <= before:
                raise GDLControlError(f"TIMESTAMP_DELAY did not strictly delay edge {edge_id}")
            changed.append(edge_id)
    elif transform == "POLARITY_FLIP":
        for edge_id, edge in base_edges.items():
            other = challenger_edges[edge_id]
            if edge == other:
                continue
            if _without(edge, {"polarity"}) != _without(other, {"polarity"}):
                raise GDLControlError(f"POLARITY_FLIP made an undeclared change: {edge_id}")
            before = edge.get("polarity")
            after = other.get("polarity")
            if (
                isinstance(before, bool)
                or isinstance(after, bool)
                or not isinstance(before, (int, float))
                or not isinstance(after, (int, float))
                or float(before) == 0.0
                or float(after) != -float(before)
            ):
                raise GDLControlError(f"POLARITY_FLIP is not an exact non-zero sign flip: {edge_id}")
            changed.append(edge_id)
    elif transform == "CRITICAL_EDGE_REMOVAL":
        added = sorted(set(challenger_edges) - set(base_edges))
        removed = sorted(set(base_edges) - set(challenger_edges))
        if added or not removed:
            raise GDLControlError("CRITICAL_EDGE_REMOVAL must remove at least one edge and add none")
        for edge_id in set(base_edges).intersection(challenger_edges):
            if base_edges[edge_id] != challenger_edges[edge_id]:
                raise GDLControlError("CRITICAL_EDGE_REMOVAL changed a retained edge")
        if any(base_edges[edge_id].get("critical") is not True for edge_id in removed):
            raise GDLControlError("CRITICAL_EDGE_REMOVAL removed a non-critical edge")
        changed = removed
    else:
        raise GDLControlError(f"unsupported graph transform: {transform}")

    if not changed:
        raise GDLControlError(f"{transform} did not make its declared semantic perturbation")
    return sorted(changed)


def validate_graph_stability_pair(
    base_graph: Mapping[str, Any],
    challenger_graph: Mapping[str, Any],
    *,
    transform: str,
    base_prediction: Mapping[str, float],
    challenger_prediction: Mapping[str, float],
    node_mapping: Mapping[str, str] | None = None,
    invariant_tolerance: float = 1e-9,
    harmful_min_sensitivity: float = 1e-6,
) -> dict[str, Any]:
    """Validate a lawful-invariance or semantic-sensitivity graph pair."""

    normalized_transform = str(transform).strip().upper()
    if normalized_transform not in LAWFUL_INVARIANT_TRANSFORMS | INTENTIONALLY_HARMFUL_TRANSFORMS:
        raise GDLControlError(f"unsupported graph transform: {transform}")
    for value, label in (
        (invariant_tolerance, "invariant_tolerance"),
        (harmful_min_sensitivity, "harmful_min_sensitivity"),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise GDLControlError(f"{label} must be finite and numeric")
        if float(value) < 0.0:
            raise GDLControlError(f"{label} cannot be negative")

    base = _normalize_graph(base_graph, "base_graph")
    challenger = _normalize_graph(challenger_graph, "challenger_graph")
    changed_ids = _validate_graph_transform(base, challenger, normalized_transform, node_mapping)
    base_output = _prediction_vector(base_prediction, "base_prediction")
    challenger_output = _prediction_vector(challenger_prediction, "challenger_prediction")
    if set(base_output) != set(challenger_output):
        raise GDLControlError("paired predictions must have identical label sets")
    distance = max(abs(base_output[label] - challenger_output[label]) for label in base_output)

    invariant = normalized_transform in LAWFUL_INVARIANT_TRANSFORMS
    passed = distance <= float(invariant_tolerance) if invariant else distance >= float(harmful_min_sensitivity)
    core = {
        "schema_version": SCHEMA_VERSION,
        "pair_class": "LAWFUL_INVARIANT" if invariant else "INTENTIONAL_SEMANTIC_SENSITIVITY",
        "transform": normalized_transform,
        "base_graph_hash": _sha256_json(base),
        "challenger_graph_hash": _sha256_json(challenger),
        "changed_ids": changed_ids,
        "base_prediction_hash": _sha256_json(base_output),
        "challenger_prediction_hash": _sha256_json(challenger_output),
        "max_abs_prediction_delta": distance,
        "invariant_tolerance": float(invariant_tolerance),
        "harmful_min_sensitivity": float(harmful_min_sensitivity),
        "passed": passed,
        "validator_only": True,
        "model_authority": "NONE",
    }
    return {**core, "pair_hash": _sha256_json(core)}


def _wl_initial_label(node: Mapping[str, Any]) -> Any:
    if "wl_label" in node:
        return node["wl_label"]
    if "features" in node:
        return node["features"]
    return _without(node, {"node_id"})


def _wl_color_ids(signatures: Mapping[tuple[str, str], Any]) -> dict[tuple[str, str], int]:
    encoded = {key: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) for key, value in signatures.items()}
    palette = {value: index for index, value in enumerate(sorted(set(encoded.values())))}
    return {key: palette[value] for key, value in encoded.items()}


def _simple_undirected_stats(graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = [node["node_id"] for node in graph["nodes"]]
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source == target:
            raise GDLControlError("1-WL controls do not accept self loops")
        adjacency[source].add(target)
        adjacency[target].add(source)
    components: list[int] = []
    remaining = set(nodes)
    while remaining:
        root = min(remaining)
        pending = [root]
        component: set[str] = set()
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node)
            pending.extend(adjacency[node] - component)
        remaining -= component
        components.append(len(component))
    triangle_count = 0
    for left_index, left in enumerate(sorted(nodes)):
        for middle in sorted(nodes)[left_index + 1 :]:
            if middle not in adjacency[left]:
                continue
            triangle_count += len(adjacency[left].intersection(adjacency[middle]) - {left, middle})
    triangle_count //= 3
    return {"component_sizes": sorted(components), "triangle_count": triangle_count}


def build_one_wl_control_receipt(
    control_id: str,
    graph_a: Mapping[str, Any],
    graph_b: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a non-isomorphic pair that 1-WL color refinement cannot separate."""

    identifier = _identifier(control_id, "control_id")
    first = _normalize_graph(graph_a, "graph_a")
    second = _normalize_graph(graph_b, "graph_b")
    if first["directed"] or second["directed"]:
        raise GDLControlError("this control implements the standard undirected 1-WL test")
    if first["metadata"] != second["metadata"]:
        raise GDLControlError("1-WL control graphs must share graph metadata")

    graphs = {"A": first, "B": second}
    signatures: dict[tuple[str, str], Any] = {}
    for graph_name, graph in graphs.items():
        for node in graph["nodes"]:
            signatures[(graph_name, node["node_id"])] = _wl_initial_label(node)
    colors = _wl_color_ids(signatures)
    trace: list[dict[str, Any]] = []
    distinguishable = False
    max_rounds = max(len(first["nodes"]), len(second["nodes"]), 1)

    for round_number in range(max_rounds + 1):
        histograms = {
            name: sorted(Counter(colors[(name, node["node_id"])] for node in graph["nodes"]).items())
            for name, graph in graphs.items()
        }
        trace.append({"round": round_number, "histograms": histograms})
        if histograms["A"] != histograms["B"]:
            distinguishable = True
            break
        if round_number == max_rounds:
            break
        next_signatures: dict[tuple[str, str], Any] = {}
        for graph_name, graph in graphs.items():
            neighbors: dict[str, list[tuple[str, int]]] = defaultdict(list)
            for edge in graph["edges"]:
                edge_type = str(edge.get("edge_type") or "UNTYPED")
                neighbors[edge["source"]].append((edge_type, colors[(graph_name, edge["target"])]))
                neighbors[edge["target"]].append((edge_type, colors[(graph_name, edge["source"])]))
            for node in graph["nodes"]:
                node_id = node["node_id"]
                next_signatures[(graph_name, node_id)] = [
                    colors[(graph_name, node_id)],
                    sorted(neighbors[node_id]),
                ]
        colors = _wl_color_ids(next_signatures)

    first_stats = _simple_undirected_stats(first)
    second_stats = _simple_undirected_stats(second)
    witness: dict[str, Any] | None = None
    if first_stats["component_sizes"] != second_stats["component_sizes"]:
        witness = {
            "kind": "COMPONENT_SIZE_MULTISET",
            "graph_a": first_stats["component_sizes"],
            "graph_b": second_stats["component_sizes"],
        }
    elif first_stats["triangle_count"] != second_stats["triangle_count"]:
        witness = {
            "kind": "TRIANGLE_COUNT",
            "graph_a": first_stats["triangle_count"],
            "graph_b": second_stats["triangle_count"],
        }

    indistinguishable = not distinguishable
    valid_control = indistinguishable and witness is not None
    core = {
        "schema_version": SCHEMA_VERSION,
        "control_id": identifier,
        "graph_a_hash": _sha256_json(first),
        "graph_b_hash": _sha256_json(second),
        "one_wl_indistinguishable": indistinguishable,
        "non_isomorphism_witness": witness,
        "valid_control_case": valid_control,
        "round_trace_hash": _sha256_json(trace),
        "rounds_checked": len(trace) - 1,
        "scope": "STANDARD_UNDIRECTED_TYPED_EDGE_1_WL",
        "claim_limit": "CONTROL_CASE_ONLY_NOT_GENERAL_GRAPH_EXPRESSIVITY",
        "validator_only": True,
        "model_authority": "NONE",
    }
    return {**core, "receipt_hash": _sha256_json(core)}


def validate_edgeless_deep_sets_control(
    graph_candidate_contract: Mapping[str, Any],
    deep_sets_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind an edgeless Deep Sets control to the graph candidate's exact inputs."""

    if not isinstance(graph_candidate_contract, Mapping) or not isinstance(deep_sets_contract, Mapping):
        raise GDLControlError("graph and Deep Sets contracts must be objects")
    matched_fields = (
        "feature_schema_hash",
        "split_hash",
        "case_manifest_hash",
        "compute_budget_hash",
    )
    for name in matched_fields:
        graph_value = str(graph_candidate_contract.get(name) or "")
        control_value = str(deep_sets_contract.get(name) or "")
        if not SHA256_RE.fullmatch(graph_value) or control_value != graph_value:
            raise GDLControlError(f"Deep Sets control is not exactly matched on {name}")
    if str(deep_sets_contract.get("architecture") or "").strip().upper() != "DEEP_SETS":
        raise GDLControlError("edgeless control architecture must be DEEP_SETS")
    if str(deep_sets_contract.get("aggregation") or "").strip().upper() != "SUM":
        raise GDLControlError("Deep Sets control must use a symmetric SUM aggregation")
    required_flags = {
        "uses_edges": False,
        "uses_node_ids": False,
        "uses_ordered_sequence": False,
        "permutation_invariant": True,
    }
    for name, expected in required_flags.items():
        if deep_sets_contract.get(name) is not expected:
            raise GDLControlError(f"Deep Sets control flag {name} must be {expected}")
    for name in ("phi_version_hash", "rho_version_hash"):
        if not SHA256_RE.fullmatch(str(deep_sets_contract.get(name) or "")):
            raise GDLControlError(f"Deep Sets control requires {name}")

    core = {
        "schema_version": SCHEMA_VERSION,
        "graph_candidate_contract_hash": _sha256_json(dict(graph_candidate_contract)),
        "deep_sets_contract_hash": _sha256_json(dict(deep_sets_contract)),
        "matched_artifacts": {name: graph_candidate_contract[name] for name in matched_fields},
        "edgeless": True,
        "permutation_invariant": True,
        "matched_compute": True,
        "control_ready": True,
        "validator_only": True,
        "model_authority": "NONE",
    }
    return {**core, "receipt_hash": _sha256_json(core)}


def validate_artifact_dag_withdrawal_coverage(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    declared_artifact_classes: Iterable[str],
    directly_invalidated_ids: Iterable[str],
    withdrawn_ids: Iterable[str],
    served_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Verify exact descendant withdrawal over a declared artifact DAG.

    Coverage is limited to the supplied, hash-bound artifact registry.  Passing
    this helper is not evidence that every production artifact has been enrolled.
    """

    declared = {str(value).strip().upper() for value in declared_artifact_classes}
    if not declared or any(not value for value in declared):
        raise GDLControlError("declared_artifact_classes must be non-empty")
    missing_required = sorted(REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES - declared)
    if missing_required:
        raise GDLControlError(
            "artifact withdrawal declaration omits required classes: " + ", ".join(missing_required)
        )

    normalized: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_mapping_sequence(artifacts, "artifacts")):
        artifact_id = _identifier(raw.get("artifact_id"), f"artifacts[{index}].artifact_id")
        artifact_class = str(raw.get("artifact_class") or "").strip().upper()
        if artifact_class not in declared:
            raise GDLControlError(f"artifact {artifact_id} has undeclared class: {artifact_class}")
        content_hash = str(raw.get("content_hash") or "")
        if not SHA256_RE.fullmatch(content_hash):
            raise GDLControlError(f"artifact {artifact_id} requires a SHA-256 content_hash")
        parent_raw = raw.get("parent_ids", [])
        if not isinstance(parent_raw, Sequence) or isinstance(parent_raw, (str, bytes)):
            raise GDLControlError(f"artifact {artifact_id}.parent_ids must be a sequence")
        parents = tuple(_identifier(value, f"artifact {artifact_id} parent") for value in parent_raw)
        if len(set(parents)) != len(parents) or artifact_id in parents:
            raise GDLControlError(f"artifact {artifact_id} has duplicate or self parents")
        if artifact_id in by_id:
            raise GDLControlError(f"duplicate artifact id: {artifact_id}")
        record = {
            "artifact_id": artifact_id,
            "artifact_class": artifact_class,
            "content_hash": content_hash,
            "parent_ids": parents,
        }
        by_id[artifact_id] = record
        normalized.append(record)

    children: dict[str, list[str]] = {artifact_id: [] for artifact_id in by_id}
    for record in normalized:
        for parent_id in record["parent_ids"]:
            if parent_id not in by_id:
                raise GDLControlError(
                    f"artifact {record['artifact_id']} cites unknown parent: {parent_id}"
                )
            children[parent_id].append(record["artifact_id"])
    for values in children.values():
        values.sort()

    indegree = {artifact_id: len(record["parent_ids"]) for artifact_id, record in by_id.items()}
    pending = deque(sorted(artifact_id for artifact_id, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    while pending:
        artifact_id = pending.popleft()
        visited.append(artifact_id)
        for child_id in children[artifact_id]:
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                pending.append(child_id)
    if len(visited) != len(by_id):
        raise GDLControlError("artifact influence graph contains a cycle")

    direct = {_identifier(value, "directly invalidated artifact id") for value in directly_invalidated_ids}
    if not direct or not direct.issubset(by_id):
        raise GDLControlError("directly_invalidated_ids must be known and non-empty")
    expected = set(direct)
    paths: dict[str, list[str]] = {artifact_id: [artifact_id] for artifact_id in sorted(direct)}
    queue = deque(sorted(direct))
    while queue:
        parent_id = queue.popleft()
        for child_id in children[parent_id]:
            candidate = [*paths[parent_id], child_id]
            if child_id not in paths or tuple(candidate) < tuple(paths[child_id]):
                paths[child_id] = candidate
                queue.append(child_id)
            expected.add(child_id)

    supplied = {_identifier(value, "withdrawn artifact id") for value in withdrawn_ids}
    if not supplied.issubset(by_id):
        raise GDLControlError("withdrawn_ids contains an unknown artifact")
    if supplied != expected:
        raise GDLControlError(
            "artifact withdrawal is not the exact descendant closure; "
            f"missing={sorted(expected - supplied)}, extra={sorted(supplied - expected)}"
        )
    served = {_identifier(value, "served artifact id") for value in served_ids}
    if not served.issubset(by_id):
        raise GDLControlError("served_ids contains an unknown artifact")
    leaked = sorted(served.intersection(expected))
    if leaked:
        raise GDLControlError("withdrawn artifacts remain servable: " + ", ".join(leaked))

    class_counts = Counter(record["artifact_class"] for record in normalized)
    withdrawn_class_counts = Counter(by_id[artifact_id]["artifact_class"] for artifact_id in expected)
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_registry_hash": _sha256_json(sorted(normalized, key=lambda item: item["artifact_id"])),
        "declared_artifact_classes": sorted(declared),
        "required_artifact_classes": sorted(REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES),
        "classes_without_current_instances": sorted(declared - set(class_counts)),
        "artifact_class_counts": dict(sorted(class_counts.items())),
        "directly_invalidated_ids": sorted(direct),
        "withdrawn_ids": sorted(expected),
        "withdrawal_paths": {artifact_id: paths[artifact_id] for artifact_id in sorted(paths)},
        "withdrawn_class_counts": dict(sorted(withdrawn_class_counts.items())),
        "served_ids_hash": _sha256_json(sorted(served)),
        "withdrawal_coverage_rate": 1.0,
        "serving_leaks": [],
        "coverage_scope": "DECLARED_HASH_BOUND_ARTIFACT_REGISTRY_ONLY",
        "validator_only": True,
        "mutation_authority": "NONE",
    }
    return {**core, "audit_hash": _sha256_json(core)}
