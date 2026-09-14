"""Synthetic exact native-context mapping; no model/provider calls."""
from dataclasses import replace
import json
import struct

import pytest
import torch

from granite_context import map_native_context, parse_native_context, build_native_prompt, score_native
from context_session import ContextReceipt, tensor_identity
from c15_journal import evidence_hash, pack
from native_mbo_encoder import NativeRegistry, encode
from test_native_forecast_refresh import build_refresh
from test_granite_parser import valid_output
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY


def case(tmp_path, *, extra=False, qsv=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bridge, sessions = build_refresh(tmp_path)
    tokens, info, input_hash, _, context = bridge.context._prepare(2, 0)
    registry = bridge.context.model.trunk.registry
    if extra:
        from context_session import record_metadata
        registry = NativeRegistry(('extension',))
        raw = dict(context[0]['raw_record'], extension={'odd/key': [None, b'\x00\xff', -0.0]})
        tokens = encode([raw], as_of=2, registry=registry, metadata=[record_metadata(context[0])])
        info = dict(info, registry_hash=registry.digest)
    binding = None
    if qsv:
        tokens['qsv'] = torch.arange(len(QSV_FEATURE_REGISTRY), dtype=torch.float64).reshape(1, 1, -1)
        tokens['qsv_mask'] = torch.ones_like(tokens['qsv'], dtype=torch.bool)
        tokens['qsv_mask'][0, 0, 0] = False
        binding = 'c'*64
    input_hash = evidence_hash(dict(info=info, entity=(1, 1), tensors=tensor_identity(tokens),
                                   **({'qsv_binding': binding} if qsv else {})))
    receipt = ContextReceipt(**info, input_hash=input_hash, model_hash='d'*64)
    packet = evidence_hash(info if not qsv else dict(context=info, input_hash=input_hash))
    return dict(tokens=tokens, receipt=receipt, entity=(1, 1), registry=registry,
                expected_input_hash=input_hash, expected_packet_hash=packet,
                source_as_of=1, expected_qsv_binding=binding)


def test_exact_context_roundtrip_and_named_references(tmp_path):
    args = case(tmp_path, extra=True, qsv=True)
    snapshot = map_native_context(**args)
    restored = parse_native_context(snapshot.text, expected_hash=snapshot.hash)
    assert restored == snapshot
    inverse = restored.reconstruct()
    assert tensor_identity(inverse) == tensor_identity(args['tokens'])
    assert '/record/extension/odd~1key/1' in snapshot.fields(0)
    assert '/qsv/' + QSV_FEATURE_REGISTRY[0] in snapshot.fields(0)
    assert struct.pack('>d', snapshot.payloads()[0]['record']['extension']['odd/key'][2]) == struct.pack('>d', -0.0)
    prompt = build_native_prompt(snapshot)
    assert snapshot.text in prompt.text
    output = valid_output(snapshot)
    output['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
    assert score_native(json.dumps(output), snapshot)[1].name == 'L4'


@pytest.mark.parametrize('field', ['expected_input_hash', 'expected_packet_hash', 'expected_qsv_binding'])
def test_wrong_trusted_bindings_reject(tmp_path, field):
    args = case(tmp_path, qsv=True)
    args[field] = 'f'*64
    with pytest.raises(ValueError):
        map_native_context(**args)


@pytest.mark.parametrize('lane', ['numeric', 'numeric_mask', 'categorical', 'parent', 'byte_values', 'qsv_mask'])
def test_every_native_lane_is_bound(tmp_path, lane):
    args = case(tmp_path, qsv=True)
    tensor = args['tokens'][lane]
    tensor.flatten()[0] = not tensor.flatten()[0] if tensor.dtype == torch.bool else tensor.flatten()[0] + 1
    with pytest.raises(ValueError):
        map_native_context(**args)


def test_no_implicit_qsv_binding_or_global_vector(tmp_path):
    args = case(tmp_path, qsv=True)
    args['expected_qsv_binding'] = None
    with pytest.raises(ValueError):
        map_native_context(**args)


def test_future_event_and_foreign_entity_reject(tmp_path):
    for changes in ({'source_as_of': 0}, {'entity': (1, 2)}):
        with pytest.raises(ValueError):
            map_native_context(**dict(case(tmp_path / str(len(str(changes)))), **changes))


def test_output_ladder_and_no_generic_field_alias(tmp_path):
    snapshot = map_native_context(**case(tmp_path))
    output = valid_output(snapshot)
    assert score_native('bad', snapshot)[1].name == 'L0'
    assert score_native('{}', snapshot)[1].name == 'L1'
    assert score_native(json.dumps({**output, 'hypotheses': []}), snapshot)[1].name == 'L2'
    assert score_native(json.dumps(output), snapshot)[1].name == 'L3'
    output['evidence_refs'] = [{'row': 0, 'field': '/record/price'}]
    assert score_native(json.dumps({**output, 'snapshot_hash': 'e'*64}), snapshot)[1].name == 'L3'


def test_explicit_capacity_rejects_instead_of_truncating(tmp_path):
    snapshot = map_native_context(**case(tmp_path))
    with pytest.raises(ValueError, match='capacity'):
        build_native_prompt(snapshot, max_prompt_bytes=1)


def test_noncanonical_or_tampered_snapshot_rejected(tmp_path):
    snapshot = map_native_context(**case(tmp_path))
    with pytest.raises(ValueError):
        parse_native_context(snapshot.text + ' ', expected_hash=snapshot.hash)
    with pytest.raises(ValueError):
        parse_native_context(snapshot.text, expected_hash='f'*64)


@pytest.mark.parametrize('content', ['outcome', b'future_labels', {'teacher': [1]}, {'reasoning': 'secret'}])
def test_registered_extensions_cannot_smuggle_answers(tmp_path, content):
    from native_mbo_encoder import reconstruct_payloads
    args = case(tmp_path, extra=True)
    payloads = reconstruct_payloads(args['tokens'], args['registry'])
    payloads[0]['record']['extension'] = content
    args['tokens'] = encode([p['record'] for p in payloads], as_of=2,
                            registry=args['registry'], metadata=[p['metadata'] for p in payloads])
    from granite_context import PACKET_FIELDS
    info = {field: getattr(args['receipt'], field) for field in PACKET_FIELDS}
    digest = evidence_hash(dict(info=info, entity=args['entity'], tensors=tensor_identity(args['tokens'])))
    args['receipt'] = replace(args['receipt'], input_hash=digest)
    args['expected_input_hash'] = digest
    with pytest.raises(ValueError, match='answer wall'):
        map_native_context(**args)


def test_canonical_body_mutations_cannot_rewrite_views_or_graph(tmp_path):
    import hashlib
    snapshot = map_native_context(**case(tmp_path, qsv=True))
    for field, changed in [('graph', [0]), ('field_paths', [['/imaginary']]),
                           ('scalar_views', [[]]), ('entity', [9, 9])]:
        body = json.loads(snapshot.text)
        body[field] = changed
        text = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        with pytest.raises(ValueError):
            parse_native_context(text, expected_hash=hashlib.sha256(text.encode()).hexdigest())


def test_display_preserves_original_type_and_signed_zero(tmp_path):
    snapshot = map_native_context(**case(tmp_path, extra=True))
    views = {item['path']: item for item in json.loads(snapshot.text)['scalar_views'][0]}
    assert views['/record/price']['display'] == 101
    assert views['/record/extension/odd~1key/2']['display'] == '-0.0'
    assert views['/record/extension/odd~1key/1']['source_type'] == 'bytes'


def test_multiple_rows_keep_graph_and_qsv_masks_without_global_reduction(tmp_path):
    from test_c15_full_evidence import submit, row
    bridge, _ = build_refresh(tmp_path)
    submit(bridge.context.builder, row(1, action='M', size=7))
    tokens, info, _, _, _ = bridge.context._prepare(102, 1)
    width = len(QSV_FEATURE_REGISTRY)
    tokens['qsv'] = torch.arange(2*width, dtype=torch.float64).reshape(1, 2, width)
    tokens['qsv_mask'] = torch.ones((1, 2, width), dtype=torch.bool)
    tokens['qsv_mask'][0, 1, 0] = False
    binding = 'e'*64
    digest = evidence_hash(dict(info=info, entity=(1, 1), tensors=tensor_identity(tokens), qsv_binding=binding))
    receipt = ContextReceipt(**info, input_hash=digest, model_hash='d'*64)
    snapshot = map_native_context(tokens=tokens, receipt=receipt, entity=(1, 1),
        registry=bridge.context.model.trunk.registry, expected_input_hash=digest,
        expected_packet_hash=evidence_hash(dict(context=info, input_hash=digest)),
        source_as_of=101, expected_qsv_binding=binding)
    assert json.loads(snapshot.text)['graph'] == [-1, 0]
    rebuilt = snapshot.reconstruct()
    assert rebuilt['qsv'][0, 0, 0] != rebuilt['qsv'][0, 1, 0]
    assert rebuilt['qsv_mask'][0, 0, 0] and not rebuilt['qsv_mask'][0, 1, 0]
    assert tensor_identity(rebuilt) == tensor_identity(tokens)
    original = snapshot.text
    tokens['qsv'].zero_()
    assert snapshot.text == original
    assert tensor_identity(snapshot.reconstruct()) == tensor_identity(rebuilt)


def test_absent_and_explicit_null_are_different_named_paths(tmp_path):
    snapshot = map_native_context(**case(tmp_path, extra=True))
    assert '/record/rtype' not in snapshot.fields(0)
    assert '/record/extension/odd~1key/0' in snapshot.fields(0)
    assert snapshot.payloads()[0]['record']['extension']['odd/key'][0] is None


def test_same_native_parser_callable_for_training_and_runtime():
    from granite_context import training_score, runtime_score
    assert training_score is runtime_score is score_native
