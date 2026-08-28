"""Contract tests for the experimental BOSS state serialization boundary.

These tests intentionally describe a text-reasoner-neutral interface.  They do
not invoke Granite, Step-1, Frankie, or any provider model.
"""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
from research.kalshi.frankie_boss.state_serialization import (
    CategoricalField,
    GraphNode,
    NumericField,
    QSVState,
    SequenceRow,
    StateSnapshot,
    ValueState,
    ablate_market_fields,
    parse_serialized_state,
    serialize_state,
)


PACKET_HASH = "a" * 64


def qsv_state(*, zero_first: bool = True) -> QSVState:
    values = tuple(0.0 if zero_first and i == 0 else float(i + 1) for i in range(len(QSV_FEATURE_REGISTRY)))
    states = tuple(ValueState.PRESENT for _ in QSV_FEATURE_REGISTRY)
    return QSVState(
        registry_id="research.refrag.qsv_registry.QSV_FEATURE_REGISTRY",
        names=QSV_FEATURE_REGISTRY,
        values=values,
        states=states,
    )


def snapshot(*, versions=None, qsv=None) -> StateSnapshot:
    versions = versions or {
        "code_version": "boss-test",
        "model_version": "boss/1",
        "calibrator_version": "identity/1",
        "feature_spec_version": "fixture/1",
    }
    rows = (
        SequenceRow(
            index=0,
            event_time_ns=100,
            ingest_time_ns=110,
            numeric=(
                NumericField("mid", "USD", ValueState.PRESENT, 2.5),
                NumericField("signed_flow", "contracts", ValueState.PRESENT, 0.0),
            ),
            categorical=(
                CategoricalField("side", ValueState.PRESENT, "BID"),
            ),
            venue="CME",
            instrument="NG",
        ),
        SequenceRow(
            index=1,
            event_time_ns=120,
            ingest_time_ns=125,
            numeric=(
                NumericField("mid", "USD", ValueState.PRESENT, 2.51),
                NumericField("signed_flow", "contracts", ValueState.MISSING, None),
            ),
            categorical=(
                CategoricalField("side", ValueState.PRESENT, "ASK"),
            ),
            venue="CME",
            instrument="NG",
        ),
    )
    return StateSnapshot(
        source_packet_hash=PACKET_HASH,
        entity="NG",
        as_of_ns=130,
        source_versions=versions,
        defects=("mbo: fixture defect",),
        rows=rows,
        graph=(GraphNode(0, None), GraphNode(1, 0)),
        qsv=qsv if qsv is not None else qsv_state(),
        ablation_policy_version="none/1",
    )


def test_same_snapshot_serializes_byte_identically():
    s = snapshot()
    a = serialize_state(s)
    b = serialize_state(s)
    assert a.text == b.text
    assert a.hash == b.hash


def test_mapping_insertion_order_does_not_change_output():
    a = snapshot(
        versions={
            "code_version": "boss-test",
            "model_version": "boss/1",
            "calibrator_version": "identity/1",
            "feature_spec_version": "fixture/1",
        }
    )
    b = snapshot(
        versions={
            "feature_spec_version": "fixture/1",
            "calibrator_version": "identity/1",
            "model_version": "boss/1",
            "code_version": "boss-test",
        }
    )
    assert serialize_state(a).text == serialize_state(b).text


def test_serializer_schema_version_participates_in_identity():
    s = snapshot()
    a = serialize_state(s, schema_version="boss_state_serialization/1")
    b = serialize_state(s, schema_version="boss_state_serialization/test-alt")
    assert a.hash != b.hash


def test_round_trip_preserves_declared_state():
    s = snapshot()
    restored = parse_serialized_state(serialize_state(s).text)
    assert restored == s


def test_round_trip_preserves_graph_parent_and_root():
    restored = parse_serialized_state(serialize_state(snapshot()).text)
    assert restored.graph == (GraphNode(0, None), GraphNode(1, 0))


def test_qsv_registry_names_order_and_states_round_trip():
    restored = parse_serialized_state(serialize_state(snapshot()).text)
    assert restored.qsv is not None
    assert restored.qsv.names == QSV_FEATURE_REGISTRY
    assert restored.qsv.values[0] == 0.0
    assert restored.qsv.states[0] is ValueState.PRESENT


def test_present_zero_missing_and_ablated_are_distinct():
    s = snapshot()
    ablated = ablate_market_fields(
        s,
        numeric_fields=frozenset({"signed_flow"}),
        policy_version="granite-control/1",
    )
    first_flow = ablated.rows[0].numeric[1]
    second_flow = s.rows[1].numeric[1]
    first_qsv = s.qsv
    assert first_flow.state is ValueState.ABLATED and first_flow.value is None
    assert second_flow.state is ValueState.MISSING and second_flow.value is None
    assert first_qsv is not None and first_qsv.states[0] is ValueState.PRESENT
    assert first_qsv.values[0] == 0.0


def test_nonfinite_present_numeric_fails_closed():
    bad_row = replace(
        snapshot().rows[0],
        numeric=(NumericField("mid", "USD", ValueState.PRESENT, float("nan")),),
    )
    bad = replace(snapshot(), rows=(bad_row, snapshot().rows[1]))
    with pytest.raises(ValueError, match="finite"):
        serialize_state(bad)


def test_missing_or_ablated_field_cannot_carry_numeric_payload():
    with pytest.raises(ValueError, match="must not carry"):
        NumericField("x", "USD", ValueState.MISSING, 0.0)
    with pytest.raises(ValueError, match="must not carry"):
        NumericField("x", "USD", ValueState.ABLATED, 0.0)


def test_malformed_parent_reference_is_rejected():
    bad = replace(snapshot(), graph=(GraphNode(0, None), GraphNode(1, 7)))
    with pytest.raises(ValueError, match="parent"):
        serialize_state(bad)


def test_qsv_registry_order_drift_is_rejected():
    names = list(QSV_FEATURE_REGISTRY)
    names[0], names[1] = names[1], names[0]
    bad_qsv = replace(qsv_state(), names=tuple(names))
    with pytest.raises(ValueError, match="QSV_FEATURE_REGISTRY"):
        serialize_state(snapshot(qsv=bad_qsv))


def test_qsv_width_drift_is_rejected():
    q = qsv_state()
    bad_qsv = replace(q, values=q.values[:-1], states=q.states[:-1])
    with pytest.raises(ValueError, match="width"):
        serialize_state(snapshot(qsv=bad_qsv))


def test_source_packet_identity_is_preserved():
    restored = parse_serialized_state(serialize_state(snapshot()).text)
    assert restored.source_packet_hash == PACKET_HASH
    assert restored.as_of_ns == 130
    assert restored.defects == ("mbo: fixture defect",)


def test_real_state_change_moves_serialized_identity():
    s = snapshot()
    changed_row = replace(
        s.rows[0],
        numeric=(
            NumericField("mid", "USD", ValueState.PRESENT, 9.99),
            s.rows[0].numeric[1],
        ),
    )
    changed = replace(s, rows=(changed_row, s.rows[1]))
    assert serialize_state(s).hash != serialize_state(changed).hash


def test_market_ablation_preserves_schema_shape_and_nonablated_fields():
    s = snapshot()
    a = serialize_state(s)
    masked = ablate_market_fields(
        s,
        numeric_fields=frozenset({"signed_flow"}),
        qsv_fields=frozenset({QSV_FEATURE_REGISTRY[0]}),
        policy_version="granite-control/1",
    )
    b = serialize_state(masked)

    raw_a = json.loads(a.text)
    raw_b = json.loads(b.text)
    assert raw_a.keys() == raw_b.keys()
    assert raw_a["rows"][0].keys() == raw_b["rows"][0].keys()
    assert raw_a["rows"][0]["numeric"][0] == raw_b["rows"][0]["numeric"][0]
    assert raw_a["rows"][0]["numeric"][1].keys() == raw_b["rows"][0]["numeric"][1].keys()
    assert raw_a["qsv"].keys() == raw_b["qsv"].keys()
    assert raw_a["qsv"]["names"] == raw_b["qsv"]["names"]
    assert raw_b["rows"][0]["numeric"][1]["state"] == "ablated"
    assert raw_b["qsv"]["states"][0] == "ablated"


def test_ablation_rejects_unknown_field_names():
    with pytest.raises(ValueError, match="unknown numeric"):
        ablate_market_fields(
            snapshot(),
            numeric_fields=frozenset({"future_return"}),
            policy_version="bad/1",
        )
    with pytest.raises(ValueError, match="unknown QSV"):
        ablate_market_fields(
            snapshot(),
            qsv_fields=frozenset({"secret_alpha"}),
            policy_version="bad/1",
        )


def test_typed_snapshot_has_no_unrestricted_extra_payload():
    with pytest.raises(TypeError):
        StateSnapshot(
            source_packet_hash=PACKET_HASH,
            entity="NG",
            as_of_ns=130,
            source_versions={},
            defects=(),
            rows=(),
            graph=(),
            qsv=None,
            ablation_policy_version="none/1",
            extra={"realized_return": 999.0},
        )
