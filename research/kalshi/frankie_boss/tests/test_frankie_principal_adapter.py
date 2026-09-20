"""Focused new session boundary tests; no principal or model calls."""
import json
import pytest
from frankie_principal_adapter import (FrankiePrincipalAdapter, PrincipalPending, PrincipalNotDispatched, SECTIONS,
    canonical, digest, file_witness, rebind_delivery_receipt, sealed_absence)


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
        session_executor=executor, admission={'output_bundle': 'NOT_PRESENTED', 'sealed_proof': 'UNPROVEN'},
        cycle_index=0)
    # These tests isolate the session boundary; production prepare runs frozen receiver.
    adapter._check_preparation = lambda receipt: None
    attachment = {'config_hash': adapter._config_hash(), 'prompt': str(prompt), 'prompt_witness': file_witness(prompt),
        'knowledge_bundle': str(evidence), 'knowledge_bundle_witness': file_witness(evidence),
        'preparation_receipt': {}, 'admission': adapter._admission_record()}
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
        section_evidence=adapter.section_evidence,feedback_contract={},
        admission={'output_bundle':{'principal_artifact':str(tmp_path/'artifact.json'),'outputs_dir':str(tmp_path/'outputs')},
                   'sealed_proof':str(tmp_path/'sealed.json')})
    render={'knowledge-receipt':str(tmp_path/'knowledge.json'),'knowledge-receipt-sha256':'a'*64,
        'knowledge-bundle-sha256':'b'*64}
    created=FrankiePrincipalAdapter(**args,render=render)
    assert created.render['result']==str((tmp_path/'result.json').resolve())
    with pytest.raises(ValueError,match='pinned pre-Sunday'):
        FrankiePrincipalAdapter(**args,render={'knowledge-receipt':'unpinned'})
    with pytest.raises(ValueError,match='emitter paths differ'):
        FrankiePrincipalAdapter(**args,render=dict(render,result='wrong.json'))


def test_admission_is_declared_never_inferred_and_a_new_render_is_never_exempt(tmp_path):
    adapter,_=case(tmp_path)
    args=dict(receiver_root=adapter.receiver_root,receiver_commit=adapter.receiver_commit,python=adapter.python,
        directory=tmp_path/'other',preparation={'result_path':str(tmp_path/'result.json'),
            'delivery_receipt':str(tmp_path/'delivery.json')},protected_files=adapter.protected_files,
        section_evidence=adapter.section_evidence,feedback_contract={})
    emitter={'knowledge-receipt':str(tmp_path/'knowledge.json'),'knowledge-receipt-sha256':'a'*64,'knowledge-bundle-sha256':'b'*64}
    undeclared=FrankiePrincipalAdapter(**args,render=emitter)
    with pytest.raises(ValueError,match='undeclared'):undeclared.prepare(tmp_path)
    with pytest.raises(ValueError,match='never exempt'):
        FrankiePrincipalAdapter(**args,render=emitter,admission={'output_bundle':'NOT_PRESENTED','sealed_proof':'UNPROVEN'})
    with pytest.raises(ValueError,match='explicitly'):
        FrankiePrincipalAdapter(**args,render=emitter,admission={'output_bundle':'NOT_PRESENTED'})


def test_output_bundle_gate_must_match_the_declared_policy_with_every_current_ledger(tmp_path):
    adapter,_=case(tmp_path)
    adapter._check_output_bundle_gate({'output_bundle_gate':{'status':'NOT_PRESENTED'}})
    with pytest.raises(ValueError,match='historical'):adapter._check_output_bundle_gate({'output_bundle_gate':{'status':'VALIDATED'}})
    adapter.admission['output_bundle']={'principal_artifact':'artifact.json','outputs_dir':'outputs'}
    ids=[f'ledger-{i:02d}' for i in range(32)]
    adapter._check_output_bundle_gate({'output_bundle_gate':{'status':'VALIDATED','required_ledger_ids':ids,'ledgers':{i:{} for i in ids}}})
    with pytest.raises(ValueError,match='32'):
        adapter._check_output_bundle_gate({'output_bundle_gate':{'status':'VALIDATED','required_ledger_ids':ids[:30],'ledgers':{i:{} for i in ids[:30]}}})
    with pytest.raises(ValueError,match='did not validate'):adapter._check_output_bundle_gate({'output_bundle_gate':{'status':'NOT_PRESENTED'}})


def test_sealed_proof_is_verified_and_a_receiver_without_its_repository_refuses_cleanly(tmp_path):
    proof=tmp_path/'sealed.json'
    proof.write_text(json.dumps({'schema':'FRANKIE_SEALED_ABSENCE_PROOF_V1','all_absent':True,'tokens_checked':9,'receipt_sha256':'c'*64}))
    assert sealed_absence(str(proof))['status']=='PROVEN'
    proof.write_text(json.dumps({'schema':'FRANKIE_SEALED_ABSENCE_PROOF_V1','all_absent':False,'tokens_checked':9,'receipt_sha256':'c'*64}))
    with pytest.raises(ValueError,match='absent'):sealed_absence(str(proof))
    adapter,_=case(tmp_path)
    with pytest.raises(ValueError,match='not a git repository'):adapter._code()
    witness=adapter._memory_witness()
    assert witness['files']['A']['sha256']==adapter.protected_files['A']['sha256']
    assert witness['receipt_sha256']!=adapter.protected_files['A']['sha256']


@pytest.mark.parametrize('count', [30, 32])
def test_declared_pilot_count_controls_gate_and_configuration_identity(tmp_path, count):
    from frankie_principal_adapter import admission_policy
    adapter, _ = case(tmp_path)
    before = adapter._config_hash()
    adapter.admission = admission_policy({'output_bundle': {'principal_artifact': 'artifact.json',
        'outputs_dir': 'outputs', 'output_ledger_count': count}, 'sealed_proof': 'proof.json'}, retained_prompt=True)
    assert adapter._config_hash() != before
    ids = [f'ledger-{i:02d}' for i in range(count)]
    adapter._check_output_bundle_gate({'output_bundle_gate': {'status': 'VALIDATED',
        'required_ledger_ids': ids, 'ledgers': {i: {} for i in ids}}})
    with pytest.raises(ValueError, match=str(count)):
        adapter._check_output_bundle_gate({'output_bundle_gate': {'status': 'VALIDATED',
            'required_ledger_ids': ids[:-1], 'ledgers': {i: {} for i in ids[:-1]}}})


@pytest.mark.parametrize('count', [0, 29, 31, True, '30'])
def test_pilot_ledger_count_refuses_invalid_configuration(count):
    from frankie_principal_adapter import admission_policy
    with pytest.raises(ValueError, match='output_bundle'):
        admission_policy({'output_bundle': {'principal_artifact': 'artifact.json', 'outputs_dir': 'outputs',
            'output_ledger_count': count}, 'sealed_proof': 'proof.json'}, retained_prompt=True)

def test_receiver_producer_waits_for_actual_prompt_and_uses_cycle_directory(tmp_path):
    from frankie_principal_adapter import admission_policy
    adapter, _ = case(tmp_path)
    adapter.admission = admission_policy({'output_bundle': 'NOT_PRESENTED',
        'sealed_proof': {'producer': 'native_sealed_absence', 'repo_root': 'frozen', 'repo_commit': 'a'*40}},
        retained_prompt=True)
    calls = []
    adapter._run = lambda module, args: calls.append((module, args))
    with pytest.raises(ValueError, match='actual composed'):
        adapter._admission_record()
    assert calls == []
    (adapter.directory / 'prompt.md').write_bytes(b'actual historical prompt plus current BOSS block')
    adapter.preparation['delivery_receipt'] = 'delivered.json'
    def produce(module, args):
        calls.append((module,args))
        assert args['prompt'].read_bytes().endswith(b'current BOSS block')
        assert args['output'] == adapter.directory/'sealed-proof.json'
        if not args.get('verify_existing'):
            args['output'].write_text(json.dumps({'schema':'FRANKIE_SEALED_ABSENCE_PROOF_V1',
                'all_absent':True,'tokens_checked':23,'receipt_sha256':'b'*64}))
    adapter._run = produce
    first = adapter._admission_record()
    assert first['sealed_absence']['status'] == 'PROVEN'
    assert adapter._admission_record() == first
    assert calls[1][1]['verify_existing'] is True

def test_receiver_producer_cannot_use_circular_fresh_emitter_route():
    from frankie_principal_adapter import admission_policy
    with pytest.raises(ValueError, match='retained prompt route'):
        admission_policy({'output_bundle': {'principal_artifact':'artifact.json','outputs_dir':'outputs'},
            'sealed_proof': {'producer':'native_sealed_absence','repo_root':'frozen','repo_commit':'a'*40}},
            retained_prompt=False)


def test_retained_prompt_renders_the_run_findings_ledger_and_prior_lessons_never_hidden(tmp_path, monkeypatch):
    """Greg, 2026-09-20: the run-findings ledger and Frankie's own prior lessons are rendered into the
    prompt, exact bytes, witnessed beside it; Memory A and the historical prompt are untouched."""
    import sqlite3
    from frankie_principal_adapter import RUN_FINDINGS_SIDECAR
    from c15_journal import pack
    from causal_packet import canonical_bytes
    module, receipt, bundle = retained_case(tmp_path, monkeypatch)
    adapter, _ = case(tmp_path)
    adapter.directory = tmp_path / 'run' / 'execution' / 'cycle-01' / 'principal'
    adapter.directory.mkdir(parents=True)
    prior = tmp_path / 'historical.md'
    prior.write_bytes(b'ORIGINAL\ncomplete prior prompt\n')
    ledger = tmp_path / 'RUN_FINDINGS.md'
    ledger.write_bytes(b'# ledger\n2026-09-20: the critic returned zero hypotheses; recorded, not hidden.\n')
    adapter.render = {'retained-prompt': str(prior), 'retained-prompt-sha256': file_witness(prior)['sha256'],
        'knowledge-receipt': str(receipt), 'knowledge-receipt-sha256': file_witness(receipt)['sha256'],
        'knowledge-bundle-sha256': file_witness(bundle)['sha256'], 'run-findings': str(ledger)}
    adapter.preparation = {'delivery_receipt': str(tmp_path / 'new-delivery.json')}
    adapter.feedback_contract = {'as_of': 500}
    lessons = tmp_path / 'run' / 'lessons.sqlite'
    db = sqlite3.connect(lessons)
    db.execute('CREATE TABLE lessons (request TEXT PRIMARY KEY, available_ns INTEGER, payload BLOB, digest TEXT)')
    for request, available_ns, text in (('cycle-00', 400, 'earlier lesson, visible'), ('cycle-07', 900, 'later lesson, not yet available')):
        db.execute('INSERT INTO lessons VALUES (?,?,?,?)', (request, available_ns, canonical_bytes(pack({'lessons': [text]})), 'd'))
    db.commit(); db.close()
    exact_block = b'\nBOSS_AGENT_ATTRIBUTED_INPUT_V1\nVERIFIED EXACT BYTES\n'
    adapter._receiver_input_block = lambda prepared: exact_block
    output = tmp_path / 'current-prompt.md'
    adapter._render_retained(output, tmp_path / 'receiver')
    body = output.read_bytes()
    assert body.endswith(b'# Preserved historical principal prompt (exact bytes follow)\n' + prior.read_bytes() + exact_block)
    assert ledger.read_bytes() in body and file_witness(ledger)['sha256'].encode() in body
    assert b'earlier lesson, visible' in body and b'later lesson, not yet available' not in body
    assert b'available at or before as_of 500' in body
    assert body.index(b'# Run findings ledger') < body.index(b'# Preserved historical principal prompt')
    assert b"THIS CYCLE'S PIN (cycle 0)" in body and body.index(b"THIS CYCLE'S PIN") < body.index(b'# Run findings ledger')
    sidecar = json.loads((adapter.directory / RUN_FINDINGS_SIDECAR).read_bytes())
    assert sidecar == dict(file_witness(ledger), path=str(ledger))
    assert (adapter.directory / 'historical-prompt.md').read_bytes() == prior.read_bytes()


def test_retained_prompt_without_lessons_store_says_so(tmp_path, monkeypatch):
    module, receipt, bundle = retained_case(tmp_path, monkeypatch)
    adapter, _ = case(tmp_path)
    prior = tmp_path / 'historical.md'
    prior.write_bytes(b'ORIGINAL\n')
    ledger = tmp_path / 'RUN_FINDINGS.md'
    ledger.write_bytes(b'# ledger\n')
    adapter.render = {'retained-prompt': str(prior), 'retained-prompt-sha256': file_witness(prior)['sha256'],
        'knowledge-receipt': str(receipt), 'knowledge-receipt-sha256': file_witness(receipt)['sha256'],
        'knowledge-bundle-sha256': file_witness(bundle)['sha256'], 'run-findings': str(ledger)}
    adapter.preparation = {'delivery_receipt': str(tmp_path / 'new-delivery.json')}
    adapter._receiver_input_block = lambda prepared: b'\nBLOCK\n'
    output = tmp_path / 'current-prompt.md'
    adapter._render_retained(output, tmp_path / 'receiver')
    assert b'(none recorded before this cycle)' in output.read_bytes()


def test_request_instruction_makes_the_calculations_frankies_and_names_the_ten_output_ledgers():
    """Greg, 2026-09-20 (standing rule restated): the calculations are Frankie's, not the runner's; the
    ten append-only output ledgers of the native ingestion registry are filed as lesson entries."""
    from frankie_principal_adapter import RUN_ANALYSIS_INSTRUCTION, OUTPUT_LEDGERS
    assert len(OUTPUT_LEDGERS) == 10 and len(set(OUTPUT_LEDGERS)) == 10
    assert "THE CALCULATIONS ARE YOURS, NOT THE RUNNER'S" in RUN_ANALYSIS_INSTRUCTION
    for name in ('exhaustion chains', 'D structures and families', 'dipoles and geometry', 'pair and triplet recurrences',
                 'pre-birth opportunities', 'provenance, never a substitute'):
        assert name in RUN_ANALYSIS_INSTRUCTION, name
    for ledger in OUTPUT_LEDGERS:
        assert ledger in RUN_ANALYSIS_INSTRUCTION, ledger
    assert 'without rerunning' not in RUN_ANALYSIS_INSTRUCTION


def test_request_instruction_requires_the_registry_calculation_set_verbatim_from_the_crosswalk():
    """Greg, 2026-09-20: 'don't look at who did them but look at the ones that were done'. The required
    set is the registry's calculation layers as the 2026-09-16 crosswalk of the August 28 recalculation
    lists them; the constant must equal that file, group by group, and the instruction must carry every
    layer and demand a per-layer accounting entry."""
    from pathlib import Path
    from frankie_principal_adapter import (RUN_ANALYSIS_INSTRUCTION, REGISTRY_CALCULATION_SET,
                                           FROZEN_LEARNED_STRUCTURE, CALCULATION_ACCOUNTING_LEDGER)
    crosswalk = json.loads((Path(__file__).resolve().parents[1] / 'audits'
                            / 'CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json').read_bytes())
    by_group = {}
    for layer in crosswalk['layers']:
        by_group.setdefault(layer['group_id'], []).append(layer['layer_id'])
    assert len(crosswalk['layers']) == 99
    for group, layers in REGISTRY_CALCULATION_SET:
        assert list(layers) == by_group[group], group
        assert all(l['policy'] == 'CAUSAL_STREAM_REQUIRED' for l in crosswalk['layers'] if l['group_id'] == group)
    assert list(FROZEN_LEARNED_STRUCTURE) == by_group['frozen_learned_structure']
    assert sum(len(layers) for _, layers in REGISTRY_CALCULATION_SET) == 49
    for _, layers in REGISTRY_CALCULATION_SET:
        for layer in layers:
            assert layer in RUN_ANALYSIS_INSTRUCTION
    assert 'THE REQUIRED SET FOR EACH CYCLE IS ITS PIN' in RUN_ANALYSIS_INSTRUCTION
    assert 'drawn from THE REGISTRY, not a summary of it' in RUN_ANALYSIS_INSTRUCTION
    assert '"' + CALCULATION_ACCOUNTING_LEDGER + '"' in RUN_ANALYSIS_INSTRUCTION
    assert 'no layer is omitted and no layer is delegated to a runner' in RUN_ANALYSIS_INSTRUCTION


def _repo_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[4]


def _pins_document():
    from pathlib import Path
    from frankie_principal_adapter import CYCLE_CALCULATION_PINS_PATH, CYCLE_CALCULATION_PINS_SCHEMA
    document = json.loads(Path(CYCLE_CALCULATION_PINS_PATH).read_bytes())
    assert document['schema'] == CYCLE_CALCULATION_PINS_SCHEMA
    return document


def test_cycle_calculation_pins_are_committed_evidence_and_cover_every_cycle_once():
    """Greg, 2026-09-20 22:23Z: cycle 0 is pinned to the first group of calculations we did, cycle 1 to the
    second, later cycles to the remaining original calculations as of the date we came up with them. The
    pin is evidence, not memory: every source receipt it names must be the committed file with that sha256,
    every pinned layer must be a registry calculation layer, and the pins together must cover the registry."""
    import hashlib
    from pathlib import Path
    from frankie_principal_adapter import REGISTRY_CALCULATION_SET, load_cycle_calculation_pin
    document = _pins_document()
    crosswalk = json.loads((Path(__file__).resolve().parents[1] / 'audits'
                            / 'CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json').read_bytes())
    assert document['registry_sha256'] == crosswalk['registry_sha256']
    registry = {layer['layer_id'] for layer in crosswalk['layers'] if layer['policy'] == 'CAUSAL_STREAM_REQUIRED'}
    registry &= {layer for _, layers in REGISTRY_CALCULATION_SET for layer in layers}
    assert len(registry) == 49
    by_registry_group = {group: list(layers) for group, layers in REGISTRY_CALCULATION_SET}
    covered = {}
    pinned_layers = set()
    root = _repo_root()
    previous_date = ''
    for pin in document['pins']:
        assert pin['defined_on'] >= previous_date, pin['group']
        previous_date = pin['defined_on']
        for cycle in pin['cycles']:
            assert cycle not in covered, cycle
            covered[cycle] = pin['group']
        assert pin['registry_layers'] and set(pin['registry_layers']) <= registry, pin['group']
        if pin.get('complete_registry'):
            assert set(pin['registry_layers']) == registry and pinned_layers == registry, pin['group']
            continue
        assert not pinned_layers & set(pin['registry_layers']), pin['group']
        pinned_layers |= set(pin['registry_layers'])
        assert pin['registry_layers'] == by_registry_group[pin['group']], pin['group']
        assert pin['calculations'] and pin['source_receipts']
        for receipt in pin['source_receipts']:
            path = root / receipt['path']
            assert path.is_file(), receipt['path']
            body = path.read_bytes()
            assert len(body) == receipt['bytes'] and hashlib.sha256(body).hexdigest() == receipt['sha256'], receipt['path']
    assert sorted(covered) == list(range(19))
    assert pinned_layers == registry
    assert document['pins'][0]['cycles'] == [0] and document['pins'][1]['cycles'] == [1]
    for index in range(19):
        assert load_cycle_calculation_pin(index)['group'] == covered[index]


def test_instruction_carries_this_cycles_pin_and_refuses_without_one(tmp_path):
    from frankie_principal_adapter import (FrankiePrincipalAdapter, CYCLE_CALCULATION_PIN_SIDECAR,
                                           RUN_ANALYSIS_INSTRUCTION, load_cycle_calculation_pin)
    adapter, _ = case(tmp_path)
    text = adapter._instruction()
    pin = load_cycle_calculation_pin(0)
    assert text.startswith(RUN_ANALYSIS_INSTRUCTION)
    assert "THIS CYCLE'S PIN (cycle 0)" in text and pin['group'] in text and pin['defined_on'] in text
    for layer in pin['registry_layers']:
        assert layer in text, layer
    for receipt in pin['source_receipts']:
        assert receipt['sha256'] in text
    sidecar = json.loads((adapter.directory / CYCLE_CALCULATION_PIN_SIDECAR).read_bytes())
    assert sidecar['cycle_index'] == 0 and sidecar['group'] == pin['group'] and sidecar['sha256'] == pin['pins_witness']['sha256']
    assert adapter._instruction() == text  # idempotent against its own sidecar
    other = FrankiePrincipalAdapter(receiver_root=adapter.receiver_root, receiver_commit=adapter.receiver_commit,
        python=adapter.python, directory=tmp_path / 'other', preparation={}, render=dict(adapter.render),
        protected_files=adapter.protected_files, section_evidence=adapter.section_evidence, feedback_contract={},
        admission=dict(adapter.admission), cycle_index=1)
    second = other._instruction()
    assert "THIS CYCLE'S PIN (cycle 1)" in second and load_cycle_calculation_pin(1)['group'] in second
    assert other._config_hash() != adapter._config_hash()
    unpinned = FrankiePrincipalAdapter(receiver_root=adapter.receiver_root, receiver_commit=adapter.receiver_commit,
        python=adapter.python, directory=tmp_path / 'unpinned', preparation={}, render=dict(adapter.render),
        protected_files=adapter.protected_files, section_evidence=adapter.section_evidence, feedback_contract={},
        admission=dict(adapter.admission))
    with pytest.raises(ValueError, match='cycle calculation pin required'):
        unpinned._instruction()
    with pytest.raises(ValueError, match='valid Sunday cycle index'):
        FrankiePrincipalAdapter(receiver_root=adapter.receiver_root, receiver_commit=adapter.receiver_commit,
            python=adapter.python, directory=tmp_path / 'bad', preparation={}, render=dict(adapter.render),
            protected_files=adapter.protected_files, section_evidence=adapter.section_evidence, feedback_contract={},
            admission=dict(adapter.admission), cycle_index=19)
    with pytest.raises(ValueError, match='is absent'):
        load_cycle_calculation_pin(0, tmp_path / 'missing.json')
