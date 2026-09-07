"""Owner-directed precision and complete evidence reporting regressions."""
from dataclasses import replace
import json
import math
import sys

import pytest

from research.kalshi.frankie_boss.state_serialization import (
    NumericField, ValueState, parse_serialized_state, serialize_state,
)
from research.kalshi.frankie_boss.granite_parser import score, Verdict
from test_state_serialization import snapshot
from test_granite_parser import valid_output


@pytest.mark.parametrize("value", [1.1234567890123457, -0.0, 9007199254740993, 10**80 + 1,
                                   1, 1.0, -1.0, 1e20, sys.float_info.max])
def test_prompt_numeric_values_round_trip_without_precision_reduction(value):
    state = snapshot()
    row = replace(state.rows[0], numeric=(NumericField("exact_value", "raw", ValueState.PRESENT, value),))
    serialized = serialize_state(replace(state, rows=(row,) + state.rows[1:]))
    restored = parse_serialized_state(serialized.text).rows[0].numeric[0].value
    assert restored == value
    assert type(restored) is type(value)
    if type(value) is float:
        assert float(restored).hex() == value.hex()
    assert serialize_state(parse_serialized_state(serialized.text)).text == serialized.text


def test_extra_qsv_values_are_rejected_instead_of_zipped_away():
    raw = json.loads(serialize_state(snapshot()).text)
    raw["qsv"]["values"].append("9E+0")
    with pytest.raises(ValueError, match="width"):
        parse_serialized_state(json.dumps(raw))


def test_model_output_caps_reject_oversize_prose_without_touching_evidence():
    state = serialize_state(snapshot())
    value = valid_output(state)
    ref = {"row": 0, "field": "mid"}
    value["evidence_refs"] = [dict(ref) for _ in range(100)]
    value["contradictions"] = [{"a": dict(ref), "b": dict(ref), "note": "x" * 1000} for _ in range(20)]
    value["missing_evidence"] = ["y" * 1000 for _ in range(20)]
    value["hypotheses"] = [{"label": "z" * 1000, "support": [dict(ref)], "against": []} for _ in range(20)]
    assert score(json.dumps(value), state) == (0.4, Verdict.L2)


@pytest.mark.parametrize('value', ['1E-4000', '1.00000000000000000001E+0'])
def test_float_parser_does_not_silently_round_unrepresentable_decimal(value):
    from state_serialization import _parse_number
    with pytest.raises(ValueError, match='lose precision or underflow'):
        _parse_number(value, 'float')


def test_independent_clock_row_keeps_both_original_timestamps():
    state = snapshot()
    row = replace(state.rows[0], ingest_time_ns=10, event_time_ns=20, independent_clocks=True)
    serialized = serialize_state(replace(state, rows=(row,) + state.rows[1:]))
    restored = parse_serialized_state(serialized.text).rows[0]
    assert (restored.ingest_time_ns, restored.event_time_ns, restored.independent_clocks) == (10, 20, True)
