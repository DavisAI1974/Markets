"""Stacked V2 route: exact native inverse, refusal on tamper, controller readback, and the real Sunday cycle-0 packet."""
import glob
import hashlib
import json
from pathlib import Path
import pytest
from test_granite_parser import valid_output
from test_granite_stacked_route_integration import snapshot
from research.kalshi.frankie_boss import granite_context as native
from research.kalshi.frankie_boss import granite_context_stacked as v1
from research.kalshi.frankie_boss import granite_context_stacked_v2 as v2
from research.kalshi.frankie_boss.granite_context_route import context_route

PACKAGE = Path(v1.__file__).parent / 'sunday_20260915_package/FB/actual-feedback-run'


def test_v2_route_exact_inverse_prompt_and_scoring(tmp_path):
    source = snapshot(tmp_path)
    route = context_route('stacked_v2')
    encoded = route.encode(source)
    assert route.native(encoded).text == source.text
    assert route.parse(encoded.text, expected_hash=encoded.hash).hash == encoded.hash
    assert route.method == 'critique_stacked_v2'
    assert route.parser_code_hash() != context_route('stacked_v1').parser_code_hash()
    assert route.build_prompt(encoded).system_prompt_hash != hashlib.sha256(context_route('stacked_v1').system_text.encode()).hexdigest()
    value = valid_output(encoded)
    value['evidence_refs'] = [{'row': 0, 'field': '/record/extension/odd~1key/1'}]
    assert route.score(json.dumps(value), encoded)[1].name == 'L4'
    value['snapshot_hash'] = source.hash
    assert route.score(json.dumps(value), encoded)[1].name == 'L3'


def test_v2_refuses_wrong_native_hash_and_v1_body(tmp_path):
    route = context_route('stacked_v2')
    source = snapshot(tmp_path)
    body = json.loads(route.encode(source).text)
    body['native_hash'] = 'f' * 64
    text = native._text(body)
    with pytest.raises(ValueError):
        route.parse(text, expected_hash=hashlib.sha256(text.encode()).hexdigest())
    v1_text = context_route('stacked_v1').encode(source).text
    with pytest.raises(ValueError):
        route.parse(v1_text, expected_hash=hashlib.sha256(v1_text.encode()).hexdigest())


def test_v2_packed_forms_refuse_malformed_digits():
    budget = v1._Budget(v1.DEFAULT_LIMITS)
    assert v2._ints(['P', -2, 2, '000312'], budget) == [-2, 1, 10]
    assert v2._ints(['O', ['P', 0, 1, '1111'], [[2, 900]]], budget) == [1, 1, 900, 1]
    assert v2._ints(['K', 1000, ['P', 0, 1, '12'], [[1, 7]]], budget) == [1000, 7]
    for bad in (['P', 0, 2, '123'], ['P', 0, 1, '1a'], ['O', ['P', 0, 1, '11'], [[5, 1]]], ['K', 1, ['I', [1]], []]):
        with pytest.raises(ValueError):
            v2._ints(bad, v1._Budget(v1.DEFAULT_LIMITS))


def test_v2_controller_readback(tmp_path):
    from research.kalshi.frankie_boss.controller_journal import _critic_context
    source = snapshot(tmp_path)
    route = context_route('stacked_v2')
    encoded = route.encode(source)
    body = json.loads(source.text)
    context = native.unpack(body['receipt'])
    state = {'intent': {'configuration': {'context_encoding': 'stacked_v2'},
        'request': {'as_of': context['as_of'], 'source_as_of': body['source_as_of'],
                    'source_hash': context['source_prefix_hash']}}}
    intent = {'context_encoding': 'stacked_v2', 'snapshot_text': encoded.text, 'snapshot_hash': encoded.hash,
        'native_snapshot_hash': source.hash, 'prompt_text': route.build_prompt(encoded).text,
        'context': context, 'packet_hash': body['packet_hash']}
    assert _critic_context(state, intent)[1].hash == encoded.hash


def test_real_sunday_cycle0_packet_exact_and_smaller():
    """The actual Sunday cycle-0 codec envelope: V2 rebuilds it byte-exact with at least a third fewer tokens."""
    pytest.importorskip('databento_dbn')
    pytest.importorskip('tokenizers')
    path = glob.glob(str(PACKAGE / 'handoff-*/critic-snapshot.txt'))
    if not path:
        pytest.skip('retained Sunday snapshot absent')
    envelope = json.loads(Path(path[0]).read_text())['codec']
    reduced = v1.decode(envelope)
    data = envelope['data']
    recipe = v1._decode(data[2][data[1].index('packet_recipe')], v1._Budget(v1.DEFAULT_LIMITS))
    encoded = v2.encode(reduced, scope_public=recipe['scope_public'], prefix_seed=recipe['prefix_seed'])
    assert v1._exact(v2.decode(encoded)) == v1._exact(reduced)
    before, after = v2._cost(envelope), v2._cost(encoded)
    assert after * 3 < before * 2, (before, after)
