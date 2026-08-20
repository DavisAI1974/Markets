from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_gdl_p0_controls import (  # noqa: E402
    GDLControlError,
    REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES,
    audit_causal_prefix,
    build_one_wl_control_receipt,
    validate_artifact_dag_withdrawal_coverage,
    validate_edgeless_deep_sets_control,
    validate_graph_stability_pair,
)


H = "a" * 64


def event(event_id, occurred_at, knowable_at, *, role="OBSERVATION", payload=None):
    return {
        "event_id": event_id,
        "occurred_at": occurred_at,
        "knowable_at": knowable_at,
        "role": role,
        "payload": payload or {"value": event_id},
    }


def graph(*, directed=True):
    return {
        "directed": directed,
        "graph_schema": "TEST_V1",
        "nodes": [
            {"node_id": "a", "features": {"kind": "x"}},
            {"node_id": "b", "features": {"kind": "x"}},
            {"node_id": "c", "features": {"kind": "x"}},
        ],
        "edges": [
            {
                "edge_id": "e1",
                "source": "a",
                "target": "b",
                "edge_type": "CAUSES",
                "timestamp": "2026-08-20T12:00:00Z",
                "polarity": 1,
                "critical": True,
            },
            {
                "edge_id": "e2",
                "source": "b",
                "target": "c",
                "edge_type": "CAUSES",
                "timestamp": "2026-08-20T12:00:01Z",
                "polarity": -1,
                "critical": False,
            },
        ],
    }


def test_causal_prefix_binds_effective_cutoff_and_exact_order():
    events = [
        event("late", "2026-08-20T12:00:03Z", "2026-08-20T12:00:03Z"),
        event("first", "2026-08-20T12:00:00Z", "2026-08-20T12:00:01Z"),
        event("second", "2026-08-20T12:00:01Z", "2026-08-20T12:00:02Z"),
    ]
    receipt = audit_causal_prefix(
        events,
        prefix_event_ids=["first", "second"],
        requested_cutoff_at="2026-08-20T12:00:04Z",
        availability_ceiling_at="2026-08-20T12:00:02Z",
        target_birth_at="2026-08-20T12:00:05Z",
    )
    assert receipt["effective_cutoff_at"] == "2026-08-20T12:00:02Z"
    assert receipt["prefix_event_ids"] == ["first", "second"]
    assert receipt["target_firewall_passed"] is True


def test_causal_prefix_rejects_missing_eligible_event_and_prebirth_target_field():
    events = [
        event("first", "2026-08-20T12:00:00Z", "2026-08-20T12:00:00Z"),
        event("second", "2026-08-20T12:00:01Z", "2026-08-20T12:00:01Z"),
    ]
    with pytest.raises(GDLControlError, match="exact eligible ordered prefix"):
        audit_causal_prefix(
            events,
            prefix_event_ids=["first"],
            requested_cutoff_at="2026-08-20T12:00:02Z",
        )
    contaminated = [
        event(
            "first",
            "2026-08-20T12:00:00Z",
            "2026-08-20T12:00:00Z",
            payload={"nested": {"target_depth": 3}},
        )
    ]
    with pytest.raises(GDLControlError, match="target-derived information"):
        audit_causal_prefix(
            contaminated,
            prefix_event_ids=["first"],
            requested_cutoff_at="2026-08-20T12:00:00Z",
            target_birth_at="2026-08-20T12:00:05Z",
        )


def test_graph_node_relabel_is_a_lawful_invariant_pair():
    base = graph()
    challenger = copy.deepcopy(base)
    mapping = {"a": "z", "b": "y", "c": "x"}
    for node in challenger["nodes"]:
        node["node_id"] = mapping[node["node_id"]]
    for edge in challenger["edges"]:
        edge["source"] = mapping[edge["source"]]
        edge["target"] = mapping[edge["target"]]
    challenger["nodes"].reverse()
    challenger["edges"].reverse()
    receipt = validate_graph_stability_pair(
        base,
        challenger,
        transform="NODE_RELABEL",
        node_mapping=mapping,
        base_prediction={"NO": 0.4, "YES": 0.6},
        challenger_prediction={"NO": 0.4, "YES": 0.6},
    )
    assert receipt["pair_class"] == "LAWFUL_INVARIANT"
    assert receipt["passed"] is True


@pytest.mark.parametrize(
    ("transform", "mutate"),
    [
        (
            "DIRECTION_REVERSAL",
            lambda candidate: candidate["edges"][0].update(source="b", target="a"),
        ),
        (
            "TIMESTAMP_DELAY",
            lambda candidate: candidate["edges"][0].update(timestamp="2026-08-20T12:00:02Z"),
        ),
        (
            "POLARITY_FLIP",
            lambda candidate: candidate["edges"][0].update(polarity=-1),
        ),
        (
            "CRITICAL_EDGE_REMOVAL",
            lambda candidate: candidate["edges"].pop(0),
        ),
    ],
)
def test_graph_semantic_perturbations_are_not_mislabeled_invariants(transform, mutate):
    base = graph()
    challenger = copy.deepcopy(base)
    mutate(challenger)
    receipt = validate_graph_stability_pair(
        base,
        challenger,
        transform=transform,
        base_prediction={"NO": 0.4, "YES": 0.6},
        challenger_prediction={"NO": 0.6, "YES": 0.4},
    )
    assert receipt["pair_class"] == "INTENTIONAL_SEMANTIC_SENSITIVITY"
    assert receipt["passed"] is True


def test_graph_semantic_pair_detects_an_insensitive_model_response():
    base = graph()
    challenger = copy.deepcopy(base)
    challenger["edges"][0].update(source="b", target="a")
    receipt = validate_graph_stability_pair(
        base,
        challenger,
        transform="DIRECTION_REVERSAL",
        base_prediction={"NO": 0.4, "YES": 0.6},
        challenger_prediction={"NO": 0.4, "YES": 0.6},
    )
    assert receipt["passed"] is False


def undirected_graph(edges):
    nodes = sorted({node for edge in edges for node in edge})
    return {
        "directed": False,
        "graph_schema": "WL_TEST_V1",
        "nodes": [{"node_id": node, "wl_label": "SAME"} for node in nodes],
        "edges": [
            {"edge_id": f"e{index}", "source": source, "target": target, "edge_type": "U"}
            for index, (source, target) in enumerate(edges)
        ],
    }


def test_one_wl_control_and_edgeless_deep_sets_contract():
    cycle6 = undirected_graph(
        [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "a")]
    )
    two_triangles = undirected_graph(
        [("u", "v"), ("v", "w"), ("w", "u"), ("x", "y"), ("y", "z"), ("z", "x")]
    )
    wl_receipt = build_one_wl_control_receipt("cycle6-v-two-triangles", cycle6, two_triangles)
    assert wl_receipt["one_wl_indistinguishable"] is True
    assert wl_receipt["non_isomorphism_witness"]["kind"] == "COMPONENT_SIZE_MULTISET"
    assert wl_receipt["valid_control_case"] is True

    matched = {
        "feature_schema_hash": "1" * 64,
        "split_hash": "2" * 64,
        "case_manifest_hash": "3" * 64,
        "compute_budget_hash": "4" * 64,
    }
    graph_contract = {**matched, "model_version_hash": "5" * 64}
    control_contract = {
        **matched,
        "architecture": "DEEP_SETS",
        "aggregation": "SUM",
        "uses_edges": False,
        "uses_node_ids": False,
        "uses_ordered_sequence": False,
        "permutation_invariant": True,
        "phi_version_hash": "6" * 64,
        "rho_version_hash": "7" * 64,
    }
    control_receipt = validate_edgeless_deep_sets_control(graph_contract, control_contract)
    assert control_receipt["control_ready"] is True
    assert control_receipt["edgeless"] is True


def test_deep_sets_contract_rejects_edges_or_an_unmatched_budget():
    matched = {
        "feature_schema_hash": "1" * 64,
        "split_hash": "2" * 64,
        "case_manifest_hash": "3" * 64,
        "compute_budget_hash": "4" * 64,
    }
    control = {
        **matched,
        "architecture": "DEEP_SETS",
        "aggregation": "SUM",
        "uses_edges": True,
        "uses_node_ids": False,
        "uses_ordered_sequence": False,
        "permutation_invariant": True,
        "phi_version_hash": "6" * 64,
        "rho_version_hash": "7" * 64,
    }
    with pytest.raises(GDLControlError, match="uses_edges"):
        validate_edgeless_deep_sets_control(matched, control)
    control["uses_edges"] = False
    control["compute_budget_hash"] = "8" * 64
    with pytest.raises(GDLControlError, match="compute_budget_hash"):
        validate_edgeless_deep_sets_control(matched, control)


def artifact(artifact_id, artifact_class, parent_ids=()):
    return {
        "artifact_id": artifact_id,
        "artifact_class": artifact_class,
        "content_hash": H,
        "parent_ids": list(parent_ids),
    }


def full_artifact_dag():
    return [
        artifact("source", "SOURCE_MEMORY"),
        artifact("summary", "SUMMARY", ["source"]),
        artifact("embedding", "EMBEDDING", ["summary"]),
        artifact("index", "RETRIEVAL_INDEX", ["embedding"]),
        artifact("cache", "CACHE", ["index"]),
        artifact("feature", "FEATURE", ["cache"]),
        artifact("prediction", "PREDICTION", ["feature"]),
        artifact("evaluation", "EVALUATION", ["prediction"]),
    ]


def test_artifact_dag_requires_exact_transitive_withdrawal_and_no_serving_leak():
    dag = full_artifact_dag()
    ids = {item["artifact_id"] for item in dag}
    receipt = validate_artifact_dag_withdrawal_coverage(
        dag,
        declared_artifact_classes=REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES,
        directly_invalidated_ids=["source"],
        withdrawn_ids=ids,
        served_ids=[],
    )
    assert receipt["withdrawal_coverage_rate"] == 1.0
    assert receipt["withdrawal_paths"]["evaluation"] == [
        "source",
        "summary",
        "embedding",
        "index",
        "cache",
        "feature",
        "prediction",
        "evaluation",
    ]

    with pytest.raises(GDLControlError, match="exact descendant closure"):
        validate_artifact_dag_withdrawal_coverage(
            dag,
            declared_artifact_classes=REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES,
            directly_invalidated_ids=["source"],
            withdrawn_ids=ids - {"evaluation"},
        )
    with pytest.raises(GDLControlError, match="remain servable"):
        validate_artifact_dag_withdrawal_coverage(
            dag,
            declared_artifact_classes=REQUIRED_WITHDRAWAL_ARTIFACT_CLASSES,
            directly_invalidated_ids=["source"],
            withdrawn_ids=ids,
            served_ids=["prediction"],
        )


def test_artifact_dag_rejects_an_incomplete_class_declaration():
    with pytest.raises(GDLControlError, match="omits required classes"):
        validate_artifact_dag_withdrawal_coverage(
            full_artifact_dag(),
            declared_artifact_classes={"SOURCE_MEMORY", "SUMMARY"},
            directly_invalidated_ids=["source"],
            withdrawn_ids=["source", "summary"],
        )
