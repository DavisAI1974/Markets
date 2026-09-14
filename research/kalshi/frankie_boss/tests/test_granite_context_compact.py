import json
import struct

import pytest

from granite_context import map_native_context, build_native_prompt, native_parser_code_hash
from granite_context_compact import (compact_native_context, parse_compact_context,
    build_compact_prompt, score_compact, compact_parser_code_hash, _encode, _decode)
from context_session import tensor_identity
from c15_journal import pack
from test_granite_context import case
from test_granite_parser import valid_output


def test_exact_native_inverse_and_distinct_pins(tmp_path):
    source = map_native_context(**case(tmp_path, extra=True, qsv=True))
    state = compact_native_context(source)
    assert state.native().text == source.text
    assert tensor_identity(state.reconstruct()) == tensor_identity(source.reconstruct())
    assert parse_compact_context(state.text, expected_hash=state.hash) == state
    assert state.fields(0) == source.fields(0)
    prompt = build_compact_prompt(state)
    assert state.text in prompt.text
    assert prompt.system_prompt_hash != build_native_prompt(source).system_prompt_hash
    assert compact_parser_code_hash() != native_parser_code_hash()
    assert len(prompt.text) < len(build_native_prompt(source).text)


def test_typed_tree_inverse_preserves_all_bits_and_order():
    nan = struct.unpack('>d', bytes.fromhex('7ff8000000000042'))[0]
    value = {'z': (0.0, -0.0, nan, float('inf')), 'a': [True, 1, 1.0, None, b'\x00\xff'],
             'q': [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0000000000000002)], 'empty': {}}
    encoded = _encode(value)
    assert pack(_decode(encoded)) == pack(value)
    assert len(encoded['nodes']) == len({json.dumps(node) for node in encoded['nodes']})


@pytest.mark.parametrize('mutation', ['extra', 'duplicate', 'forward', 'hash', 'space'])
def test_noncanonical_or_tampered_context_rejected(tmp_path, mutation):
    import hashlib
    state = compact_native_context(map_native_context(**case(tmp_path)))
    body = json.loads(state.text)
    if mutation == 'extra':
        body['tree']['nodes'].append(['str', 'unused'])
    elif mutation == 'duplicate':
        body['tree']['nodes'].append(body['tree']['nodes'][0])
    elif mutation == 'forward':
        body['tree']['nodes'][0] = ['list', [len(body['tree']['nodes'])]]
    elif mutation == 'hash':
        body['native_hash'] = 'f'*64
    text = json.dumps(body, sort_keys=True, separators=(',', ':'))
    if mutation == 'space':
        text += ' '
    with pytest.raises(ValueError):
        parse_compact_context(text, expected_hash=hashlib.sha256(text.encode()).hexdigest())


def test_compact_hash_and_logical_named_references(tmp_path):
    source = map_native_context(**case(tmp_path, extra=True, qsv=True))
    state = compact_native_context(source)
    output = valid_output(state)
    output['evidence_refs'] = [{'row': 0, 'field': '/record/extension/odd~1key/1'}]
    assert score_compact(json.dumps(output), state)[1].name == 'L4'
    output['snapshot_hash'] = source.hash
    assert score_compact(json.dumps(output), state)[1].name == 'L3'
    output['snapshot_hash'] = state.hash
    output['evidence_refs'][0]['row'] = 1
    assert score_compact(json.dumps(output), state)[1].name == 'L3'
    with pytest.raises(ValueError, match='capacity'):
        build_compact_prompt(state, max_prompt_bytes=1)


def test_multirow_native_graph_and_different_qsv_inverse(tmp_path, monkeypatch):
    import test_granite_context as fixture
    original_mapper = fixture.map_native_context
    def checked_mapper(**kwargs):
        source = original_mapper(**kwargs)
        compact = compact_native_context(source)
        assert compact.native().text == source.text
        assert tensor_identity(compact.reconstruct()) == tensor_identity(kwargs['tokens'])
        assert compact.fields(1) == source.fields(1)
        return source
    monkeypatch.setattr(fixture, 'map_native_context', checked_mapper)
    fixture.test_multiple_rows_keep_graph_and_qsv_masks_without_global_reduction(tmp_path)


def test_vectors_share_only_exact_values_and_keep_masked_payloads():
    rows = [(1.0, -0.0), (1.0, -0.0), (1.0, 0.0), (1.0, 2.0)]
    masks = [(True, False)]*4
    tree = _encode({'rows': rows, 'masks': masks})
    vectors = [n for n in tree['nodes'] if n[0] == 'tuple:float64']
    assert len(vectors) == 3
    assert pack(_decode(tree)) == pack({'rows': rows, 'masks': masks})


@pytest.mark.parametrize('tree', [
    {'nodes': [['float64', '1.00']], 'root': 0},
    {'nodes': [['float64', 'bits:3ff0000000000000']], 'root': 0},
    {'nodes': [['int', True]], 'root': 0},
    {'nodes': [['list', [0]]], 'root': 0},
    {'nodes': [['str', 'x']], 'root': True},
])
def test_noncanonical_typed_nodes_reject(tree):
    with pytest.raises(ValueError):
        _decode(tree)


@pytest.mark.parametrize('shape',['doubling','deep','repeated_text'])
def test_public_parser_rejects_expansion_before_recursive_reencoding(monkeypatch,shape):
    import hashlib
    import granite_context_compact as codec
    nodes=[['list:int',[1,2]]]
    if shape=='repeated_text': nodes=[['str','x'*100_000]]
    for index in range(70 if shape=='deep' else 30):
        nodes.append(['list',[index] if shape=='deep' else [index,index]])
    text=json.dumps(dict(schema=codec.SCHEMA,native_hash='a'*64,
                         tree=dict(nodes=nodes,root=len(nodes)-1)),sort_keys=True,separators=(',',':'))
    def forbidden(_): pytest.fail('oversized DAG reached recursive encoder')
    monkeypatch.setattr(codec,'_encode',forbidden)
    with pytest.raises(ValueError,match='admission'):
        parse_compact_context(text,expected_hash=hashlib.sha256(text.encode()).hexdigest())


def test_explicit_decode_limits_reject_without_changing_valid_large_inverse():
    from granite_context_compact import DecodeLimits
    value={'rows':[(float(i),-0.0) for i in range(5000)]}
    tree=_encode(value)
    assert pack(_decode(tree))==pack(value)
    with pytest.raises(ValueError,match='admission'):
        _decode(tree,limits=DecodeLimits(max_expanded_nodes=100))
    assert pack(_decode(tree,limits=DecodeLimits(max_expanded_nodes=100_000)))==pack(value)
    with pytest.raises(ValueError): DecodeLimits(max_depth=True)
