"""P6-P8 sealed prompt checks using synthetic serializer outputs only."""
import hashlib
import inspect
import json
from dataclasses import replace

import pytest

from research.kalshi.frankie_boss.frankie_contract import BLD1_FIELD_NAMES
from research.kalshi.frankie_boss.granite_prompt import build_prompt
from research.kalshi.frankie_boss.state_serialization import (
    SerializedState, ablate_market_fields, parse_serialized_state, serialize_state,
)
from test_granite_parser import snapshot, valid_output
from research.kalshi.frankie_boss.granite_parser import accepts


def test_p7_exact_state_bytes_hash_and_fixed_system_instruction():
    state = snapshot()
    prompt = build_prompt(state)
    assert prompt.snapshot_text.encode() == state.text.encode()
    assert state.text.encode() in prompt.text.encode()
    assert prompt.snapshot_hash == state.hash
    assert state.hash in prompt.text
    assert not any(name in prompt.text for name in BLD1_FIELD_NAMES)
    assert prompt.system_prompt_hash == hashlib.sha256(prompt.system_text.encode()).hexdigest()
    assert prompt == build_prompt(state)
    assert accepts(json.dumps(valid_output(state)), state)


def test_ablation_uses_existing_serializer_and_changes_only_snapshot_identity():
    state = snapshot()
    changed = serialize_state(ablate_market_fields(
        parse_serialized_state(state.text), numeric_fields=frozenset({'mid'}),
        policy_version='mechanics/1'))
    first, second = build_prompt(state), build_prompt(changed)
    assert first.system_prompt_hash == second.system_prompt_hash
    assert first.snapshot_hash != second.snapshot_hash
    assert second.snapshot_text == changed.text
    assert changed.text in second.text


@pytest.mark.parametrize('name', BLD1_FIELD_NAMES)
@pytest.mark.parametrize('location', ['numeric', 'metadata', 'defect'])
def test_p7_no_exception_for_any_bld1_name_anywhere(name, location):
    state = parse_serialized_state(snapshot().text)
    if location == 'numeric':
        row = state.rows[0]
        state = replace(state, rows=(replace(row, numeric=(replace(row.numeric[0], name=name),)),))
    elif location == 'metadata':
        state = replace(state, source_versions={name: '1'})
    else:
        state = replace(state, defects=(name,))
    with pytest.raises(ValueError, match='answer wall'):
        build_prompt(serialize_state(state))


@pytest.mark.parametrize('name', ['target', 'future_outcome', 'labels', 'OUTCOME'])
def test_training_target_or_outcome_names_cannot_enter_snapshot(name):
    state = parse_serialized_state(snapshot().text)
    row = state.rows[0]
    state = replace(state, rows=(replace(row, numeric=(replace(row.numeric[0], name=name),)),))
    with pytest.raises(ValueError, match='answer wall'):
        build_prompt(serialize_state(state))


@pytest.mark.parametrize('kind', ['text', 'schema', 'noncanonical'])
def test_invalid_snapshot_rejected_without_rewriting(kind):
    state = snapshot()
    if kind == 'text':
        state = replace(state, text='{}')
    elif kind == 'schema':
        state = replace(state, schema_version='unknown')
    else:
        state = replace(state, text=json.dumps(json.loads(state.text), indent=2))
    with pytest.raises(ValueError):
        build_prompt(state)


def test_p8_no_model_or_arbitrary_prompt_arguments():
    assert tuple(inspect.signature(build_prompt).parameters) == ('snapshot',)
    with pytest.raises(TypeError):
        build_prompt(snapshot().text)
