"""Focused new session boundary tests; no principal or model calls."""
import json
import pytest
from frankie_principal_adapter import (FrankiePrincipalAdapter, PrincipalPending, PrincipalNotDispatched, SECTIONS,
    canonical, digest, file_witness, rebind_delivery_receipt)


def case(tmp_path, executor=None):
    evidence = tmp_path / 'memory.txt'
    evidence.write_text('immutable prior')
    witness = dict(path=str(evidence), **file_witness(evidence))
    prompt = tmp_path / 'prompt.md'
    prompt.write_text('verified attributed inputs')
    adapter = FrankiePrincipalAdapter(receiver_root=tmp_path / 'receiver', receiver_commit='a'*40,
        python='python', directory=tmp_path / 'session', preparation={},
        render={'knowledge-receipt': str(evidence), 'knowledge-receipt-sha256': 'a'*64,
            'knowledge-bundle-sha256': 'b'*64, 'retained-prompt':str(prompt),
            'retained-prompt-sha256':file_witness(prompt)['sha256']}, protected_files={'A': witness},
        section_evidence={section: witness for section in SECTIONS}, feedback_contract={},
        session_executor=executor)
    # These tests isolate the session boundary; production prepare runs frozen receiver.
    adapter._check_preparation = lambda receipt: None
    attachment = {'config_hash': adapter._config_hash(), 'prompt': str(prompt), 'prompt_witness': file_witness(prompt),
        'knowledge_bundle': str(evidence), 'knowledge_bundle_witness': file_witness(evidence),
        'preparation_receipt': {}}
    attachment['attachment_hash'] = digest(attachment)
    return adapter, attachment


def response(request):
    return {'session_id': 'actual-host-session', 'model_identity_as_reported_by_session': 'test-agent',
        'request_sha256': digest(request), 'sections': {s: request['attachment'].get('unused', '') for s in []},
        'feedback': {'request_id': request['request_id'], 'input_hash': 'b'*64, 'source_hash': 'c'*64,
            'available_ns': 100, 'sessions': [{'session_id': 'sunday', 'timing': [], 'gap': None, 'path': []}]},
        'lessons': []}



def attestation(adapter, request, response):
    body = {'schema':'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1','mechanism':'AGENT_SESSION',
        'request_sha256':digest(request),'response_sha256':digest(response),
        'session_id':response['session_id'],
        'model_identity_as_reported_by_session':response['model_identity_as_reported_by_session']}
    path = adapter.directory/'host-record.json'
    path.write_bytes(canonical(dict(body,host_authority='test host dispatch')))
    return dict(body,host_record=dict(path=str(path),**file_witness(path)))

def finish(adapter, attachment):
    with pytest.raises(PrincipalPending):
        adapter.execute('request', attachment)
    request = json.loads((adapter.directory / 'session-request.json').read_bytes())
    result = response(request)
    result['sections'] = {k:v['sha256'] for k,v in adapter.section_evidence.items()}
    adapter.record_session_response(result, host_attestation=attestation(adapter, request, result))
    return adapter.recover('request', attachment)


def test_interrupted_session_never_resubmits(tmp_path):
    calls = []
    def interrupted(request):
        calls.append(request)
        raise RuntimeError('lost session transport')
    adapter, attachment = case(tmp_path, interrupted)
    with pytest.raises(RuntimeError, match='lost session'):
        adapter.execute('request', attachment)
    with pytest.raises(PrincipalPending):
        adapter.execute('request', attachment)
    assert len(calls) == 1
    with pytest.raises(PrincipalPending):
        adapter.recover('request', attachment)


def test_completed_session_recovers_typed_feedback_without_second_call(tmp_path):
    adapter, attachment = case(tmp_path)
    envelope = finish(adapter, attachment)
    feedback = adapter.verify(envelope, 'request', 'b'*64, 'c'*64, 100)
    assert feedback.sessions[0].session_id == 'sunday'
    assert feedback.principal_receipt_hash == envelope['principal_receipt']['receipt_sha256']
    assert adapter.execute('request', attachment) == envelope


def test_changed_request_feedback_or_frozen_memory_refuses(tmp_path):
    adapter, attachment = case(tmp_path)
    envelope = finish(adapter, attachment)
    with pytest.raises(ValueError, match='binding'):
        adapter.verify(envelope, 'request', 'd'*64, 'c'*64, 100)
    changed = json.loads(canonical(envelope))
    changed['feedback']['available_ns'] = 0
    with pytest.raises(ValueError, match='retained session'):
        adapter.verify(changed, 'request', 'b'*64, 'c'*64, 100)
    (tmp_path / 'memory.txt').write_text('changed')
    with pytest.raises(ValueError, match='frozen memory'):
        adapter.recover('request', attachment)


def test_missing_section_or_self_minted_receipt_refuses(tmp_path):
    adapter, attachment = case(tmp_path)
    with pytest.raises(PrincipalPending):
        adapter.execute('request', attachment)
    request = json.loads((adapter.directory / 'session-request.json').read_bytes())
    result = response(request)
    adapter.record_session_response(result, host_attestation=attestation(adapter, request, result))
    with pytest.raises(ValueError, match='18 preserved'):
        adapter.recover('request', attachment)


def test_redelivery_preserves_original_and_attests_new_physical_paths(tmp_path):
    local = tmp_path / 'delivered'
    local.mkdir()
    (local / 'raw.jsonl').write_bytes(b'full raw rows\n')
    witness = file_witness(local / 'raw.jsonl')
    prior = {'schema': 'FRANKIE_LEDGER_DELIVERY_RECEIPT_V1', 'ledgers': {'raw': {
        'file': 'raw.jsonl', 'plain_bytes_expected': witness['bytes'],
        'plain_sha256_expected': witness['sha256']}}, 'objects': {}}
    prior['receipt_sha256'] = digest(prior)
    original = tmp_path / 'old.json'
    original.write_bytes(canonical(prior))
    output = tmp_path / 'new.json'
    actual = rebind_delivery_receipt(original, file_witness(original)['sha256'], local, output)
    assert json.loads(original.read_bytes()) == prior
    assert actual['receipt_sha256'] != prior['receipt_sha256']
    assert actual['local_redelivery']['original_receipt_sha256'] == prior['receipt_sha256']
    assert actual['ledgers']['raw']['local_path'] == str(local / 'raw.jsonl')
    (local / 'raw.jsonl').write_bytes(b'sampled')
    with pytest.raises(ValueError, match='plaintext ledger differs'):
        rebind_delivery_receipt(original, file_witness(original)['sha256'], local, tmp_path / 'bad.json')


def test_preparation_rejects_changed_independent_pin_before_session(tmp_path):
    adapter, attachment = case(tmp_path)
    pins = tmp_path / 'pins.json'
    pins.write_text('{}')
    adapter.preparation = {'pins_path': str(pins), 'expected_pins_sha256': 'f'*64}
    adapter._code = lambda: None
    with pytest.raises(ValueError, match='independent preparation pins changed'):
        FrankiePrincipalAdapter._check_preparation(adapter, {'executing_agent_commit': 'a'*40})


def test_changed_session_contract_cannot_reuse_completed_response(tmp_path):
    adapter, attachment = case(tmp_path)
    finish(adapter, attachment)
    adapter.feedback_contract = {'different': 'policy'}
    with pytest.raises(ValueError, match='configuration differs'):
        adapter.recover('request', attachment)

def retained_case(tmp_path, monkeypatch):
    import frankie_principal_adapter as module
    import hashlib
    seed = b'0' * 166700
    seed_hash = hashlib.sha256(seed).hexdigest()
    monkeypatch.setattr(module, 'FROZEN_MEMORY_SHA256', seed_hash)
    bundle = tmp_path / 'KNOWLEDGE_BUNDLE.md'
    bundle.write_bytes(('===== BEGIN KNOWLEDGE seed_a_memory_20260902 ' + seed_hash + ' =====\n').encode()
        + seed + b'\n===== END KNOWLEDGE seed_a_memory_20260902 =====\n')
    receipt = {'artifacts': [{'id': 'seed_a_memory_20260902', 'sha256': seed_hash, 'bytes': 166700}],
        'model_visible_context_bytes': file_witness(bundle)['bytes'],
        'model_visible_context_sha256': file_witness(bundle)['sha256']}
    receipt['receipt_sha256'] = digest(receipt)
    path = tmp_path / 'KNOWLEDGE_RECEIPT.json'
    path.write_bytes(canonical(receipt))
    return module, path, bundle


def test_retained_prompt_keeps_original_bytes_and_exact_receiver_block(tmp_path, monkeypatch):
    module, receipt, bundle = retained_case(tmp_path, monkeypatch)
    adapter, _ = case(tmp_path)
    prior = tmp_path / 'historical.md'
    prior.write_bytes(b'ORIGINAL\ncomplete prior prompt\n')
    adapter.render = {'retained-prompt': str(prior), 'retained-prompt-sha256': file_witness(prior)['sha256'],
        'knowledge-receipt': str(receipt), 'knowledge-receipt-sha256': file_witness(receipt)['sha256'],
        'knowledge-bundle-sha256': file_witness(bundle)['sha256']}
    adapter.preparation = {'delivery_receipt': str(tmp_path / 'new-delivery.json')}
    exact_block = b'\nBOSS_AGENT_ATTRIBUTED_INPUT_V1\nVERIFIED EXACT BYTES\n'
    adapter._receiver_input_block = lambda prepared: exact_block
    output = tmp_path / 'current-prompt.md'
    adapter._render_retained(output, tmp_path / 'receiver')
    assert (adapter.directory / 'historical-prompt.md').read_bytes() == prior.read_bytes()
    assert output.read_bytes().endswith(prior.read_bytes() + exact_block)
    assert b'No separate source day' in output.read_bytes()


def test_retained_prompt_rejects_post_sunday_memory_even_with_valid_self_hash(tmp_path, monkeypatch):
    module, receipt, bundle = retained_case(tmp_path, monkeypatch)
    body = json.loads(receipt.read_bytes())
    body['artifacts'][0]['sha256'] = 'b'*64
    body['receipt_sha256'] = digest({k:v for k,v in body.items() if k != 'receipt_sha256'})
    receipt.write_bytes(canonical(body))
    with pytest.raises(ValueError, match='pre-Sunday Memory'):
        module.retained_knowledge(receipt, file_witness(receipt)['sha256'], bundle, file_witness(bundle)['sha256'])


def test_recovery_distinguishes_undispatched_from_pending(tmp_path):
    adapter, attachment = case(tmp_path)
    with pytest.raises(PrincipalNotDispatched):
        adapter.recover('request', attachment)
    with pytest.raises(PrincipalPending):
        adapter.execute('request', attachment)
    with pytest.raises(PrincipalPending):
        adapter.recover('request', attachment)


def test_response_requires_host_witness_and_detects_changed_host_record(tmp_path):
    adapter, attachment = case(tmp_path)
    with pytest.raises(PrincipalPending):
        adapter.execute('request', attachment)
    request=json.loads((adapter.directory/'session-request.json').read_bytes())
    result=response(request)
    result['sections']={k:v['sha256'] for k,v in adapter.section_evidence.items()}
    host=attestation(adapter,request,result)
    with pytest.raises(TypeError):
        adapter.record_session_response(result)
    host['response_sha256']='0'*64
    with pytest.raises(ValueError,match='host attestation'):
        adapter.record_session_response(result,host_attestation=host)
    host=attestation(adapter,request,result)
    adapter.record_session_response(result,host_attestation=host)
    Path = __import__('pathlib').Path
    Path(host['host_record']['path']).write_text('changed')
    with pytest.raises(ValueError,match='host session record bytes'):
        adapter.recover('request',attachment)


def test_partial_receiver_output_is_retained_before_new_preparation(tmp_path):
    adapter,attachment=case(tmp_path)
    partial=adapter.directory/'receiver'
    partial.mkdir()
    (partial/'source-binding.json').write_text('partial bytes')
    def stop_after_recovery(module,args):
        assert not partial.exists()
        assert len(list(adapter.directory.glob('receiver.partial-*')))==1
        raise RuntimeError('preparation not executed in this seam check')
    adapter._run=stop_after_recovery
    with pytest.raises(RuntimeError,match='preparation not executed'):
        adapter.prepare(tmp_path/'handoff')
    assert next(adapter.directory.glob('receiver.partial-*')).joinpath('source-binding.json').read_text()=='partial bytes'


def test_constructor_enforces_pinned_memory_and_emitter_path_identity(tmp_path):
    adapter,_=case(tmp_path)
    args=dict(receiver_root=adapter.receiver_root,receiver_commit=adapter.receiver_commit,
        python=adapter.python,directory=tmp_path/'other',preparation={'result_path':str(tmp_path/'result.json'),
            'delivery_receipt':str(tmp_path/'delivery.json')},protected_files=adapter.protected_files,
        section_evidence=adapter.section_evidence,feedback_contract={})
    render={'knowledge-receipt':str(tmp_path/'knowledge.json'),'knowledge-receipt-sha256':'a'*64,
        'knowledge-bundle-sha256':'b'*64}
    created=FrankiePrincipalAdapter(**args,render=render)
    assert created.render['result']==str((tmp_path/'result.json').resolve())
    with pytest.raises(ValueError,match='pinned pre-Sunday'):
        FrankiePrincipalAdapter(**args,render={'knowledge-receipt':'unpinned'})
    with pytest.raises(ValueError,match='emitter paths differ'):
        FrankiePrincipalAdapter(**args,render=dict(render,result='wrong.json'))
