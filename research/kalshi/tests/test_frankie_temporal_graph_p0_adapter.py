from __future__ import annotations

import copy
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_cognition import sha256_json  # noqa: E402
from frankie_temporal_graph_p0_adapter import (  # noqa: E402
    TemporalCallbackResult,
    frozen_static_signed_hash_payload,
    run_temporal_graph_shadow_adapter,
    temporal_event_content_hash,
)


H = "a" * 64


def event(
    event_id,
    sequence,
    *,
    at="2026-08-20T09:00:00Z",
    stream="s1",
    lane="l1",
    source="a",
    target="b",
    event_type="INTERACTION",
    parents=(),
    payload=None,
):
    row = {
        "event_id": event_id,
        "source_hash": H,
        "stream_id": stream,
        "lane_id": lane,
        "source_node_id": source,
        "target_node_id": target,
        "event_type": event_type,
        "source_sequence": sequence,
        "source_at": at,
        "effective_at": at,
        "knowable_at": at,
        "parent_event_ids": list(parents),
        "payload": payload or {"value": event_id},
        "immutable": True,
    }
    row["event_hash"] = temporal_event_content_hash(row)
    return row


def graph(edges):
    nodes = sorted({node for edge in edges for node in edge})
    return {
        "directed": False,
        "graph_schema": "TEMPORAL_TEST_WL",
        "nodes": [{"node_id": node, "wl_label": "SAME"} for node in nodes],
        "edges": [
            {"edge_id": f"e{index}", "source": left, "target": right, "edge_type": "U"}
            for index, (left, right) in enumerate(edges)
        ],
    }


def controls():
    matched = {
        "feature_schema_hash": "1" * 64,
        "split_hash": "2" * 64,
        "case_manifest_hash": "3" * 64,
        "compute_budget_hash": "4" * 64,
    }
    frozen = {
        **matched,
        "architecture": "FROZEN_STATIC",
        "frozen": True,
        "uses_temporal_memory": False,
        "uses_future_events": False,
        "model_version_hash": "5" * 64,
    }
    frozen["signed_contract_hash"] = sha256_json(frozen_static_signed_hash_payload(frozen))
    deep_sets = {
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
    cycle = graph(
        [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "a")]
    )
    triangles = graph(
        [("u", "v"), ("v", "w"), ("w", "u"), ("x", "y"), ("y", "z"), ("z", "x")]
    )
    return {
        "candidate_contract": matched,
        "frozen_static_control": frozen,
        "edgeless_deep_sets_control": deep_sets,
        "one_wl_control": {
            **matched,
            "control_id": "cycle-v-triangles",
            "graph_a": cycle,
            "graph_b": triangles,
        },
    }


def kwargs(**overrides):
    values = {
        "events": [
            event("e1", 1),
            event("e2", 2, at="2026-08-20T09:00:01Z", parents=("e1",)),
        ],
        "source_cutoff_at": "2026-08-20T10:00:00Z",
        "effective_cutoff_at": "2026-08-20T10:00:00Z",
        "knowable_cutoff_at": "2026-08-20T10:00:00Z",
        "target_birth_at": "2026-08-20T11:00:00Z",
        "control_bindings": controls(),
    }
    values.update(overrides)
    return values


def test_complete_replay_is_batch_one_predict_before_update_and_control_bound():
    receipt = run_temporal_graph_shadow_adapter(**kwargs())
    assert receipt["status"] == "COMPLETED"
    assert receipt["batch_size"] == 1
    assert receipt["paper_faithful_tgn_or_tgat"] is False
    assert receipt["performance_evidence"] is False
    assert receipt["promotion_authority"] == "NONE"
    assert receipt["control_bindings"]["all_controls_bound"] is True
    assert receipt["control_bindings"]["controls_executed_for_performance"] is False
    first = receipt["result"]["predictions"][0]
    assert first["stage_order"] == [
        "SNAPSHOT_FROZEN",
        "TIME_ENCODING",
        "ATTENTION",
        "PREDICTION_FROZEN",
        "MESSAGE_AFTER_PREDICTION",
        "AGGREGATE_BATCH_SIZE_1",
        "MEMORY_UPDATE_AFTER_EVENT",
    ]
    assert first["pre_event_memory"] == {}
    assert first["current_event_payload_visible_to_prediction"] is False
    assert receipt["result"]["hash_chain_valid"] is True


def test_same_batch_leakage_is_rejected_and_current_payload_never_reaches_prediction():
    rejected = run_temporal_graph_shadow_adapter(**kwargs(batch_size=2))
    assert rejected["status"] == "REJECTED"
    assert "batch_size must equal 1" in rejected["reason"]

    seen = {}

    def predict(request):
        seen.update(request)
        return TemporalCallbackResult(
            {"prediction": {"abstain": True}}, read_only=True, side_effect_free=True
        )

    receipt = run_temporal_graph_shadow_adapter(
        **kwargs(callbacks={"predict": predict}, callback_version_hashes={"predict": H})
    )
    assert receipt["status"] == "COMPLETED"
    assert "event" not in seen
    assert "payload" not in seen["event_context"]
    assert seen["current_event_payload_available"] is False
    assert seen["current_event_message_available"] is False


def test_callbacks_observe_prediction_before_message_and_memory_update():
    order = []

    def wrap(stage):
        def callback(request):
            order.append((request["event_context"]["event_id"], stage))
            if stage == "predict":
                return TemporalCallbackResult(
                    {"prediction": {"abstain": True}}, read_only=True, side_effect_free=True
                )
            if stage == "message":
                assert request["prediction_already_frozen"] is True
                return TemporalCallbackResult(
                    {"message": {"event": request["event"]["event_id"]}},
                    read_only=True,
                    side_effect_free=True,
                )
            assert stage == "memory_update"
            assert request["prediction_already_frozen"] is True
            return TemporalCallbackResult(
                {
                    "node_memories": {
                        node: {"updated_at": request["event_context"]["causal_at"]}
                        for node in request["endpoint_node_ids"]
                    }
                },
                read_only=True,
                side_effect_free=True,
            )

        return callback

    callbacks = {stage: wrap(stage) for stage in ("predict", "message", "memory_update")}
    versions = {stage: H for stage in callbacks}
    receipt = run_temporal_graph_shadow_adapter(
        **kwargs(callbacks=callbacks, callback_version_hashes=versions)
    )
    assert receipt["status"] == "COMPLETED"
    assert order[:3] == [("e1", "predict"), ("e1", "message"), ("e1", "memory_update")]


def test_out_of_order_events_and_ambiguous_equal_time_sequences_fail_closed():
    e1 = event("e1", 1, at="2026-08-20T09:00:00Z")
    e2 = event("e2", 2, at="2026-08-20T09:00:01Z", parents=("e1",))
    out_of_order = run_temporal_graph_shadow_adapter(**kwargs(events=[e2, e1]))
    assert out_of_order["status"] == "REJECTED"
    assert "out of chronological" in out_of_order["reason"]

    equal = [event("e1", 1), event("e2", 1)]
    ambiguous = run_temporal_graph_shadow_adapter(**kwargs(events=equal))
    assert ambiguous["status"] == "REJECTED"
    assert "source_sequence" in ambiguous["reason"]

    ordered_equal = run_temporal_graph_shadow_adapter(
        **kwargs(events=[event("e1", 1), event("e2", 2, parents=("e1",))])
    )
    assert ordered_equal["status"] == "COMPLETED"
    assert ordered_equal["result"]["eligible_event_ids"] == ["e1", "e2"]


def test_target_birth_and_each_point_in_time_cutoff_filter_events_before_callbacks():
    rows = [
        event("active", 1, at="2026-08-20T09:00:00Z"),
        event("future", 2, at="2026-08-20T10:30:00Z"),
        event("birth", 3, at="2026-08-20T11:00:00Z"),
    ]
    receipt = run_temporal_graph_shadow_adapter(**kwargs(events=rows))
    assert receipt["status"] == "COMPLETED"
    assert receipt["result"]["eligible_event_ids"] == ["active"]
    assert receipt["result"]["unavailable_events"] == {
        "birth": "AT_OR_AFTER_TARGET_BIRTH",
        "future": "AFTER_SOURCE_CUTOFF",
    }
    assert receipt["result"]["cutoff_receipt"]["future_events_served"] == []

    contaminated = event("target", 1, payload={"nested": {"target_depth": 3}})
    rejected = run_temporal_graph_shadow_adapter(**kwargs(events=[contaminated]))
    assert rejected["status"] == "REJECTED"
    assert "target-derived" in rejected["reason"]


def test_stream_and_lane_state_are_isolated():
    rows = [
        event("a1", 1, stream="a", lane="x", source="n1", target="n2"),
        event("b1", 1, at="2026-08-20T09:00:01Z", stream="b", lane="x", source="n1", target="n2"),
    ]
    receipt = run_temporal_graph_shadow_adapter(**kwargs(events=rows))
    assert receipt["status"] == "COMPLETED"
    assert receipt["result"]["predictions"][0]["pre_event_memory"] == {}
    assert receipt["result"]["predictions"][1]["pre_event_memory"] == {}
    assert set(receipt["result"]["final_scoped_memories"]) == {"a::x", "b::x"}
    assert receipt["result"]["cross_scope_reads"] == []


def test_invalidation_resets_and_replays_without_invalidated_descendants_or_future_topology():
    rows = [
        event("root", 1, at="2026-08-20T09:00:00Z"),
        event("child", 2, at="2026-08-20T09:00:01Z", parents=("root",)),
        event(
            "invalidate",
            3,
            at="2026-08-20T09:00:02Z",
            event_type="INVALIDATION",
            payload={"invalidates_event_ids": ["root"], "reason": "source withdrawn"},
        ),
        event("late-child", 4, at="2026-08-20T09:00:03Z", parents=("child",)),
        event("independent", 5, at="2026-08-20T09:00:04Z", source="c", target="d"),
    ]
    receipt = run_temporal_graph_shadow_adapter(**kwargs(events=rows))
    assert receipt["status"] == "COMPLETED"
    assert receipt["result"]["withdrawn_event_ids_by_scope"]["s1::l1"] == [
        "child",
        "late-child",
        "root",
    ]
    paths = receipt["result"]["withdrawal_paths_by_scope"]["s1::l1"]
    assert paths["late-child"] == ["root", "child", "late-child"]
    invalidation_link = receipt["result"]["hash_chain"][2]
    assert invalidation_link["kind"] == "INVALIDATION_RESET_REPLAY"
    assert invalidation_link["event"]["replayed_active_event_ids"] == []
    assert invalidation_link["event"]["future_topology_used"] is False
    assert receipt["result"]["prediction_count"] == 3


def test_callback_mutation_failure_budget_and_faults_have_failure_removal_receipts():
    def mutator(request):
        request["active_prior_event_ids"].append("illicit")
        return TemporalCallbackResult(
            {"attention": {}}, read_only=True, side_effect_free=True
        )

    mutated = run_temporal_graph_shadow_adapter(
        **kwargs(callbacks={"attention": mutator}, callback_version_hashes={"attention": H})
    )
    assert mutated["status"] == "REJECTED"
    assert "mutated its detached input" in mutated["reason"]
    assert mutated["removal_receipt"]["canonical_state_changed"] is False

    def failed(_request):
        raise RuntimeError("offline")

    callback_failed = run_temporal_graph_shadow_adapter(
        **kwargs(callbacks={"message": failed}, callback_version_hashes={"message": H})
    )
    assert callback_failed["status"] == "REJECTED"
    assert callback_failed["failed_stage"] == "message"

    budget = run_temporal_graph_shadow_adapter(**kwargs(max_callback_calls=2))
    assert budget["status"] == "REJECTED"
    assert "budget exceeded" in budget["reason"]

    fault = run_temporal_graph_shadow_adapter(**kwargs(faults=["predict:e2"]))
    assert fault["status"] == "REJECTED"
    assert fault["failed_stage"] == "predict"


def test_reset_and_replay_are_byte_identical_for_exact_inputs():
    first = run_temporal_graph_shadow_adapter(**kwargs())
    second = run_temporal_graph_shadow_adapter(**kwargs(events=copy.deepcopy(kwargs()["events"])))
    assert first["status"] == second["status"] == "COMPLETED"
    assert first["result_hash"] == second["result_hash"]
    assert first["result"]["reset_identity"] == second["result"]["reset_identity"]
    assert first["result"]["hash_chain_head"] == second["result"]["hash_chain_head"]
    assert first["result"]["final_scoped_memories_hash"] == second["result"]["final_scoped_memories_hash"]
