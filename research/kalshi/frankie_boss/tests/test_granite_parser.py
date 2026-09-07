"""Synthetic C23 contracts; no provider, training, or replay execution."""

import json
from dataclasses import replace

import pytest

from research.kalshi.frankie_boss.granite_parser import (
    Verdict, accepts, parse_json_object, runtime_score, score, training_score,
)
from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION, validate_schema
from research.kalshi.frankie_boss.frankie_contract import BLD1_FIELD_NAMES
from research.kalshi.frankie_boss.state_serialization import (
    CategoricalField, GraphNode, NumericField, SequenceRow, SerializedState,
    StateSnapshot, ValueState, parse_serialized_state, serialize_state,
)


def snapshot():
    return serialize_state(StateSnapshot(
        source_packet_hash="a" * 64, entity="NG", as_of_ns=110,
        source_versions={"fixture": "1"}, defects=(),
        rows=(SequenceRow(0, 100, 110,
                          (NumericField("mid", "USD", ValueState.PRESENT, 2.5),),
                          (), "CME", "NG"),),
        graph=(GraphNode(0, None),), qsv=None, ablation_policy_version="none/1",
    ))


def valid_output(state):
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_hash": state.hash,
        "evidence_refs": [{"row": 0, "field": "mid"}],
        "contradictions": [], "missing_evidence": [],
        "hypotheses": [{"label": "consistent", "support": [], "against": []}],
        "evidence_verdict": "CONSISTENT",
    }


def test_ladder_is_deterministic_and_strictly_increasing():
    state = snapshot()
    valid = valid_output(state)
    wrong_types = {**valid, "evidence_verdict": "BUY"}
    foreign = {**valid, "snapshot_hash": "b" * 64}
    fixtures = ["[]", "{}", json.dumps(wrong_types), json.dumps(foreign), json.dumps(valid)]
    expected = [(0.0, Verdict.L0), (0.2, Verdict.L1), (0.4, Verdict.L2),
                (0.6, Verdict.L3), (1.0, Verdict.L4)]
    assert [score(text, state) for text in fixtures] == expected
    assert [score(text, state) for text in fixtures] == expected
    assert [accepts(text, state) for text in fixtures] == [False] * 4 + [True]


def test_training_and_runtime_import_the_identical_score_callable():
    assert runtime_score is score is training_score


def test_source_packet_hash_is_not_the_prompt_identity():
    state = snapshot()
    value = valid_output(state)
    value["snapshot_hash"] = "a" * 64
    assert score(json.dumps(value), state) == (0.6, Verdict.L3)
    assert not accepts(json.dumps(value), state)


@pytest.mark.parametrize("text", [
    "", "null", "true", "1", '"text"', "[]", "{}{}", "{broken}",
    '{"x": 1, "x": 2}', '{"x": {"a": 1, "a": 2}}',
    '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}', '{"x": 1e999}',
    '{"x": [1e999]}', "[" * 2000, b"{}", None,
])
def test_malformed_json_is_l0(text):
    assert parse_json_object(text) is None
    assert score(text, snapshot()) == (0.0, Verdict.L0)


@pytest.mark.parametrize("wrapper", [
    "```json\n{}\n```", "<think>reasoning</think>{}", "Here is the answer: {}",
    "{} trailing prose",
])
def test_final_channel_extraction_is_not_guessed(wrapper):
    state = snapshot()
    assert score(wrapper.format(json.dumps(valid_output(state))), state) == (0.0, Verdict.L0)


@pytest.mark.parametrize("key", list(valid_output(snapshot())))
def test_every_top_level_key_is_required(key):
    state = snapshot()
    value = valid_output(state)
    del value[key]
    assert score(json.dumps(value), state) == (0.2, Verdict.L1)


def test_extra_top_level_key_is_l1_even_if_other_types_are_wrong():
    state = snapshot()
    value = {**valid_output(state), "extra": 1, "evidence_verdict": False}
    assert score(json.dumps(value), state) == (0.2, Verdict.L1)


@pytest.mark.parametrize("key,bad", [
    ("schema_version", "wrong/1"), ("schema_version", None),
    ("snapshot_hash", "a" * 63), ("snapshot_hash", "g" * 64),
    ("snapshot_hash", 123), ("evidence_refs", {}),
    ("evidence_refs", [{"row": True, "field": "mid"}]),
    ("evidence_refs", [{"row": 0.0, "field": "mid"}]),
    ("evidence_refs", [{"row": 0, "field": 1}]),
    ("evidence_refs", [{"row": 0, "field": "mid", "extra": 1}]),
    ("evidence_refs", [{"field": "mid"}]),
    ("contradictions", None), ("contradictions", [{}]),
    ("missing_evidence", [1]), ("missing_evidence", ""),
    ("hypotheses", None),
    ("hypotheses", [{"label": "x", "support": {}, "against": []}]),
    ("hypotheses", [{"label": "x", "support": [], "against": [], "extra": 1}]),
    ("evidence_verdict", "BUY"), ("evidence_verdict", []), ("evidence_verdict", True),
])
def test_wrong_types_enums_and_nested_keys_are_l2(key, bad):
    state = snapshot()
    value = {**valid_output(state), key: bad}
    assert not validate_schema(value)
    assert score(json.dumps(value), state) == (0.4, Verdict.L2)


@pytest.mark.parametrize("location", ["evidence", "a", "b", "support", "against"])
@pytest.mark.parametrize("bad_ref", [
    {"row": -1, "field": "mid"}, {"row": 1, "field": "mid"},
    {"row": 0, "field": "absent"}, {"row": 0, "field": ""},
])
def test_every_nested_ref_must_resolve(location, bad_ref):
    state = snapshot()
    value = valid_output(state)
    good = {"row": 0, "field": "mid"}
    if location == "evidence":
        value["evidence_refs"] = [bad_ref]
    elif location in {"a", "b"}:
        value["contradictions"] = [{"a": good, "b": good, "note": ""}]
        value["contradictions"][0][location] = bad_ref
    else:
        value["hypotheses"][0][location] = [bad_ref]
    assert validate_schema(value)
    assert score(json.dumps(value), state) == (0.6, Verdict.L3)


def test_previous_caps_and_longer_outputs_are_all_valid_under_v2():
    state = snapshot()
    value = valid_output(state)
    ref = {"row": 0, "field": "mid"}
    value["evidence_refs"] = [ref] * 16
    value["contradictions"] = [{"a": ref, "b": ref, "note": "x" * 200}] * 8
    value["missing_evidence"] = ["x" * 120] * 8
    value["hypotheses"] = [{"label": "x" * 40, "support": [ref] * 17, "against": []}] * 4
    assert score(json.dumps(value), state) == (1.0, Verdict.L4)
    value["contradictions"].append(value["contradictions"][0])
    assert score(json.dumps(value), state) == (1.0, Verdict.L4)


@pytest.mark.parametrize("key,uncapped", [
    ("evidence_refs", [{"row": 0, "field": "mid"}] * 17),
    ("contradictions", [{"a": {"row": 0, "field": "mid"},
                         "b": {"row": 0, "field": "mid"}, "note": "x" * 201}]),
    ("missing_evidence", ["x" * 121]), ("missing_evidence", [""] * 9),
    ("hypotheses", []),
    ("hypotheses", [{"label": "x" * 41, "support": [], "against": []}]),
    ("hypotheses", [{"label": "x", "support": [], "against": []}] * 5),
])
def test_former_reduction_fixtures_are_preserved_and_accepted(key, uncapped):
    state = snapshot()
    value = {**valid_output(state), key: uncapped}
    assert validate_schema(value)
    assert score(json.dumps(value), state) == (1.0, Verdict.L4)


def test_numeric_categorical_metadata_missing_and_ablated_names_resolve():
    original = parse_serialized_state(snapshot().text)
    row = replace(original.rows[0], numeric=(
        NumericField("mid", "USD", ValueState.MISSING, None),
        NumericField("flow", "contracts", ValueState.ABLATED, None),
    ), categorical=(CategoricalField("side", ValueState.PRESENT, "BID"),))
    state = serialize_state(replace(original, rows=(row,)))
    value = valid_output(state)
    value["evidence_refs"] = [{"row": 0, "field": field} for field in (
        "mid", "flow", "side", "index", "event_time_ns", "ingest_time_ns", "venue", "instrument",
    )]
    assert score(json.dumps(value), state) == (1.0, Verdict.L4)


def test_empty_snapshot_accepts_no_refs_but_rejects_references():
    state = serialize_state(replace(parse_serialized_state(snapshot().text), rows=(), graph=()))
    value = valid_output(state)
    assert score(json.dumps(value), state) == (0.6, Verdict.L3)
    value["evidence_refs"] = []
    assert score(json.dumps(value), state) == (1.0, Verdict.L4)


def test_invalid_snapshot_is_a_caller_error_not_a_reward():
    state = snapshot()
    text = json.dumps(valid_output(state))
    with pytest.raises(TypeError, match="SerializedState"):
        score(text, parse_serialized_state(state.text))
    with pytest.raises(ValueError, match="schema_version"):
        score(text, replace(state, schema_version="unknown"))
    with pytest.raises(ValueError, match="canonical"):
        score(text, replace(state, text=state.text + " "))
    raw = json.loads(state.text)
    raw["rows"][0]["future_answer"] = "forbidden"
    with pytest.raises(ValueError, match="unknown"):
        score(text, SerializedState(state.schema_version, json.dumps(raw)))


def test_parser_result_exposes_no_bld1_fields_and_does_not_modify_input():
    state = snapshot()
    text = json.dumps(valid_output(state))
    result = score(text, state)
    assert isinstance(result, tuple) and len(result) == 2
    assert set(dir(type(result))).isdisjoint(BLD1_FIELD_NAMES)
    assert set(dir(Verdict)).isdisjoint(BLD1_FIELD_NAMES)
    assert result == (1.0, Verdict.L4)
    assert state == snapshot()


def test_p6_schema_keys_have_no_bld1_collision_and_old_field_rejected():
    from research.kalshi.frankie_boss.granite_output_schema import REQUIRED_KEYS
    assert REQUIRED_KEYS.isdisjoint(BLD1_FIELD_NAMES)
    state = snapshot()
    old = valid_output(state)
    old["disposition"] = old.pop("evidence_verdict")
    assert score(json.dumps(old), state) == (0.2, Verdict.L1)
