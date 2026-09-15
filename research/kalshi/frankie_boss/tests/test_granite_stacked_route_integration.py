"""New synthetic route seam; no provider call or source recovery."""
from dataclasses import asdict
import hashlib
import json
import pytest
from test_granite_context import case
from test_granite_parser import valid_output
from research.kalshi.frankie_boss import granite_context as native
from research.kalshi.frankie_boss.granite_context_route import context_route
from research.kalshi.frankie_boss.native_mbo_encoder import NativeRegistry


def snapshot(tmp_path):
    args = case(tmp_path, extra=True, qsv=True)
    args['receipt'] = native.ContextReceipt(**asdict(args['receipt']))
    args['registry'] = NativeRegistry(('extension',))
    return native.map_native_context(**args)


def test_stacked_route_exact_inverse_identity_and_named_output(tmp_path):
    source = snapshot(tmp_path)
    route = context_route('stacked_v1')
    encoded = route.encode(source)
    assert route.native(encoded).text == source.text
    assert route.parse(encoded.text, expected_hash=encoded.hash).hash == encoded.hash
    assert route.parser_code_hash() != context_route('compact_v1').parser_code_hash()
    assert route.build_prompt(encoded).system_prompt_hash != hashlib.sha256(context_route('compact_v1').system_text.encode()).hexdigest()
    value = valid_output(encoded)
    value['evidence_refs'] = [{'row':0,'field':'/record/extension/odd~1key/1'}]
    assert route.score(json.dumps(value), encoded)[1].name == 'L4'
    value['snapshot_hash'] = source.hash
    assert route.score(json.dumps(value), encoded)[1].name == 'L3'
    value['snapshot_hash'] = encoded.hash
    value['evidence_refs'][0]['row'] = -1
    assert route.score(json.dumps(value), encoded)[1].name == 'L3'
    with pytest.raises(ValueError):
        context_route('compact_v1').encode(source, scope_public={})


def test_stacked_outer_hash_cannot_hide_wrong_native_inverse(tmp_path):
    route=context_route('stacked_v1');encoded=route.encode(snapshot(tmp_path))
    body=json.loads(encoded.text);body['native_hash']='f'*64
    text=native._text(body)
    with pytest.raises(ValueError):
        route.parse(text,expected_hash=hashlib.sha256(text.encode()).hexdigest())


def test_new_preflight_records_exact_encoding_and_options(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from research.kalshi.frankie_boss import sunday_native_runtime as runtime
    source=snapshot(tmp_path)
    info=native.unpack(json.loads(source.text)['receipt'])
    info.pop('input_hash');info.pop('model_hash')
    context=SimpleNamespace(_prepare=lambda *args:({},info,'a'*64,None,[]),
        _model_hash=lambda:'d'*64,qsv=None,teacher=None,builder=None,entity=(1,1),
        model=SimpleNamespace(trunk=SimpleNamespace(registry=None)))
    monkeypatch.setattr(runtime,'journal_prefix',lambda *args:[])
    monkeypatch.setattr(runtime,'map_native_context',lambda **kwargs:source)
    options={'scope_public':None,'prefix_seed':None}
    body,receipt=runtime.prepare_critic_request(context,as_of=2,through_cursor=0,source_as_of=1,
        context_encoding='stacked_v1',context_encoding_options=options)
    assert receipt['context_encoding']=='stacked_v1'
    assert receipt['context_encoding_options']==options
    assert receipt['request_sha256']==hashlib.sha256(body).hexdigest()
    assert receipt['model_forward_performed'] is False
    assert 'stacked_native_context:' in json.loads(body)['messages'][0]['content']
    assert 'compact_snapshot_hash' not in receipt


def test_stacked_controller_readback_requires_original_native_hash(tmp_path):
    from research.kalshi.frankie_boss.controller_journal import _critic_context
    source=snapshot(tmp_path);route=context_route('stacked_v1');encoded=route.encode(source)
    body=json.loads(source.text);context=native.unpack(body['receipt'])
    state={'intent':{'configuration':{'context_encoding':'stacked_v1'},
        'request':{'as_of':context['as_of'],'source_as_of':body['source_as_of'],
                   'source_hash':context['source_prefix_hash']}}}
    intent={'context_encoding':'stacked_v1','snapshot_text':encoded.text,'snapshot_hash':encoded.hash,
        'native_snapshot_hash':source.hash,'prompt_text':route.build_prompt(encoded).text,
        'context':context,'packet_hash':body['packet_hash']}
    assert _critic_context(state,intent)[1].hash==encoded.hash
    del intent['native_snapshot_hash']
    with pytest.raises(ValueError,match='exact native snapshot'):
        _critic_context(state,intent)
