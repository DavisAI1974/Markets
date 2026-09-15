import copy
import hashlib
import json
from pathlib import Path

import pytest

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_emit_frankie_spawn import _delivery_receipt, _result, _repo_with_docs
from research.kalshi.frankie_raw_mbo_benchmark import native_boss_attachment as boss


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(tmp_path):
    _, mission, contract = _repo_with_docs(tmp_path)
    result = _result(mission, contract)
    result['layers']['identity_receipt'].update(source_manifest_hash='1'*64, arm='A_MEMORY', run_id='run-1')
    result['result_hash'] = canonical_hash(result, omit='result_hash')
    result_path = tmp_path / 'calculation_result.json'
    result_path.write_bytes(encoded(result))
    delivery_path = _delivery_receipt(tmp_path)
    delivery = json.loads(delivery_path.read_bytes())
    delivery['run_id'] = result['layers']['identity_receipt']['run_id']
    delivery['manifest_sha256'] = '2' * 64
    delivery['receipt_sha256'] = canonical_hash(delivery, omit='receipt_sha256')
    delivery_path.write_bytes(encoded(delivery))
    export = tmp_path / 'attachment'
    export.mkdir()
    files = {'state.c15.json': b'["dict",[]]', 'controller.c15.jsonl': b'["dict",[]]\n',
             'native.c15.jsonl': b'["dict",[]]\n', 'critic-snapshot.txt': b'producer snapshot',
             'critic-prompt.txt': b'producer prompt', 'record-000000.json': b'{"producer":"boss"}',
             'forecast-000000.bin': b'\x00\xff\x01'}
    for name, raw in files.items():
        (export / name).write_bytes(raw)
    checkpoint = {'schema': 'BOSS_FRANKIE_CONTROLLER_JOURNAL_V1', 'count': 1, 'head_hash': '3' * 64}
    manifest = {'schema': 'BOSS_AGENT_FILE_HANDOFF_V1', 'boss_commit': 'a' * 40, 'agent_commit': 'b' * 40,
                'request_id': 'refresh/1', 'request_hash': '4' * 64, 'status': 'complete',
                'controller_checkpoint': checkpoint, 'native_checkpoint': {**checkpoint, 'schema': 'BOSS_ROLLING_FORECAST_V1'},
                'configuration_hash': '5' * 64,
                'source': {'prefix_hash': '6' * 64, 'through_cursor': 0, 'as_of': 2, 'source_as_of': 1, 'arm_hash': '7' * 64},
                'targets': [{'target': {'instrument': 'SYN', 'target_id': '1', 'target_ns': 20}, 'revision': 1, 'publication_hash': '8'*64,
                             'artifact_digest': '9'*64, 'record_digest': '0'*64,
                             'record_path': 'record-000000.json', 'artifact_path': 'forecast-000000.bin'}],
                'files': [{'path': name, 'bytes': len(raw), 'sha256': sha(raw), 'purpose': (boss.BASE_FILES.get(name) or ('record' if name.startswith('record-') else 'forecast_artifact'))}
                          for name, raw in sorted(files.items())]}
    (export / 'manifest.json').write_bytes(encoded(manifest))
    mapping_path = tmp_path / 'mapping.json'
    mapping_path.write_bytes(encoded({'method': 'SYNTHETIC_EXPLICIT_MAPPING', 'boss_source': manifest['source'],
                                     'agent_source_manifest_hash': '1' * 64, 'row_mapping': [[0, 0]]}))
    attestation = {'schema': 'FRANKIE_BOSS_SOURCE_BINDING_V1', 'boss_source': manifest['source'],
                   'agent': {'run_id': delivery['run_id'], 'arm': 'A_MEMORY', 'source_day': '20211003',
                             'source_manifest_hash': '1' * 64, 'delivery_manifest_sha256': '2' * 64,
                             'delivery_receipt_sha256': delivery['receipt_sha256'], 'result_hash': result['result_hash']},
                   'provenance': {'authority': 'synthetic fixture author', 'method': 'explicit row mapping',
                                  'mapping_artifact_sha256': sha(mapping_path.read_bytes()),
                                  'mapping_artifact_bytes': len(mapping_path.read_bytes())}}
    crosswalk = tmp_path / 'source-binding.json'
    crosswalk.write_bytes(encoded(attestation))
    request = boss.AttachmentRequest(directory=export, expected_manifest_sha256=sha(encoded(manifest)),
                                     expected_boss_commit='a'*40, expected_agent_commit='b'*40,
                                     controller_checkpoint=checkpoint, native_checkpoint=manifest['native_checkpoint'],
                                     crosswalk_path=crosswalk, expected_crosswalk_sha256=sha(encoded(attestation)),
                                     mapping_artifact=mapping_path, mode='attributed_input')
    return request, result_path, delivery_path


def verify(request, result, delivery):
    return boss.verify_attachment(request, result_path=result, delivery_receipt=delivery, trusted_agent_commit='b'*40)


def test_preserves_every_byte_and_separate_source_identities(tmp_path):
    request, result, delivery = fixture(tmp_path)
    accepted = verify(request, result, delivery)
    assert dict(accepted.files)['forecast-000000.bin'] == b'\x00\xff\x01'
    assert accepted.receipt['mapping_status'] == 'CALLER_ATTESTED_WITH_BYTE_WITNESS'
    assert accepted.receipt['boss_source']['prefix_hash'] != accepted.receipt['agent']['source_manifest_hash']
    assert 'BOSS/Granite producer evidence' in accepted.input_block()


def test_pinned_legacy_sunday_result_keeps_hash_mismatch_visible(tmp_path):
    from dataclasses import replace
    request, result_path, _ = fixture(tmp_path)
    result = json.loads(result_path.read_bytes())
    result['layers']['identity_receipt']['code_commit'] = boss.LEGACY_SUNDAY_RESULT_COMMIT
    result['runner_result_hash'] = 'a' * 64
    result['result_hash'] = 'b' * 64
    raw = encoded(result)
    request = replace(request, expected_result_sha256=sha(raw))
    integrity = boss._result_integrity(request, result, raw)
    assert integrity['status'] == 'PINNED_LEGACY_DECLARED_HASH_MISMATCH'
    assert integrity['declared_result_hash'] != integrity['recomputed_result_hash']
    with pytest.raises(boss.AttachmentError):
        boss._result_integrity(replace(request, expected_result_sha256='c' * 64), result, raw)


@pytest.mark.parametrize('kind', ['manifest_pin', 'boss_commit', 'agent_commit', 'checkpoint', 'extra', 'changed', 'missing', 'directory', 'crosswalk', 'mapping'])
def test_rejects_changed_pins_or_physical_evidence(tmp_path, kind):
    request, result, delivery = fixture(tmp_path)
    from dataclasses import replace
    if kind == 'manifest_pin': request = replace(request, expected_manifest_sha256='0'*64)
    elif kind == 'boss_commit': request = replace(request, expected_boss_commit='c'*40)
    elif kind == 'agent_commit': request = replace(request, expected_agent_commit='c'*40)
    elif kind == 'checkpoint': request = replace(request, controller_checkpoint={**request.controller_checkpoint, 'count': 2})
    elif kind == 'extra': (request.directory/'extra').write_bytes(b'x')
    elif kind == 'changed': (request.directory/'forecast-000000.bin').write_bytes(b'bad')
    elif kind == 'missing': (request.directory/'critic-prompt.txt').unlink()
    elif kind == 'directory': (request.directory/'extra').mkdir()
    elif kind == 'crosswalk': request.crosswalk_path.write_bytes(b'{}')
    elif kind == 'mapping': request.mapping_artifact.write_bytes(b'bad')
    with pytest.raises(boss.AttachmentError): verify(request, result, delivery)


@pytest.mark.parametrize('field,value', [('through_cursor', 1), ('as_of', 3), ('source_as_of', 0), ('arm_hash', '0'*64)])
def test_source_attestation_cannot_change_cutoff_cursor_or_arm(tmp_path, field, value):
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    body = json.loads(request.crosswalk_path.read_bytes())
    body['boss_source'][field] = value
    request.crosswalk_path.write_bytes(encoded(body))
    request = replace(request, expected_crosswalk_sha256=sha(encoded(body)))
    with pytest.raises(boss.AttachmentError): verify(request, result, delivery)


@pytest.mark.parametrize('field,value', [('source_day', '20211004'), ('run_id', 'other'), ('arm', 'A_CLEAN'), ('source_manifest_hash', 'f'*64)])
def test_source_attestation_must_match_actual_agent_identity(tmp_path, field, value):
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    body = json.loads(request.crosswalk_path.read_bytes())
    body['agent'][field] = value
    request.crosswalk_path.write_bytes(encoded(body))
    request = replace(request, expected_crosswalk_sha256=sha(encoded(body)))
    with pytest.raises(boss.AttachmentError): verify(request, result, delivery)


def test_accepts_verified_incomplete_when_re_pinned(tmp_path):
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    body = json.loads((request.directory/'manifest.json').read_bytes())
    body['status'] = 'incomplete'
    (request.directory/'manifest.json').write_bytes(encoded(body))
    request = replace(request, expected_manifest_sha256=sha(encoded(body)))
    accepted = verify(request, result, delivery)
    assert accepted.receipt['manifest_sha256'] == request.expected_manifest_sha256


def test_post_comparison_never_renders_input_block(tmp_path):
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    accepted = verify(replace(request, mode='post_agent_comparison'), result, delivery)
    with pytest.raises(boss.AttachmentError): accepted.input_block()


def test_emitter_rejects_post_mode_without_changing_default_prompt(tmp_path, monkeypatch):
    from dataclasses import replace
    from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
    from research.kalshi.frankie_raw_mbo_benchmark import native_knowledge_delivery as knowledge
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_emit_frankie_spawn import _accounted_prompt_test_crosswalk
    request, result_path, delivery_path = fixture(tmp_path)
    # Use actual committed mission/contract bytes and delivered knowledge with the existing
    # small input-registry fixture; the ledger byte checks and new receiver remain real.
    result = json.loads(result_path.read_bytes())
    identity = result['layers']['identity_receipt']
    identity['mission_sha256'] = sha((emitter.REPO_ROOT / emitter.MISSION_PATH).read_bytes())
    identity['calculation_contract_sha256'] = sha((emitter.REPO_ROOT / emitter.CONTRACT_PATH).read_bytes())
    result['result_hash'] = canonical_hash(result, omit='result_hash')
    result_path.write_bytes(encoded(result))
    delivery = json.loads(delivery_path.read_bytes())
    obj = delivery['objects']['calculation_result.json']
    obj.update(sha256_observed=sha(result_path.read_bytes()), sha256_expected=sha(result_path.read_bytes()), bytes_observed=len(result_path.read_bytes()), bytes_expected=len(result_path.read_bytes()))
    delivery['receipt_sha256'] = canonical_hash(delivery, omit='receipt_sha256')
    delivery_path.write_bytes(encoded(delivery))
    binding = json.loads(request.crosswalk_path.read_bytes())
    binding['agent'].update(result_hash=result['result_hash'], delivery_receipt_sha256=delivery['receipt_sha256'])
    request.crosswalk_path.write_bytes(encoded(binding))
    request = replace(request, expected_crosswalk_sha256=sha(encoded(binding)))
    written = knowledge.write_knowledge_delivery(knowledge.build_knowledge_delivery(), tmp_path / 'knowledge')
    monkeypatch.setattr(emitter, 'crosswalk', lambda *args, **kwargs: _accounted_prompt_test_crosswalk())
    monkeypatch.setattr(boss, '_executing_commit', lambda: 'b'*40)
    kwargs = dict(delivery_receipt=delivery_path, knowledge_receipt=written['receipt'])
    default = emitter.emit(result_path, **kwargs)
    enriched = emitter.emit(result_path, boss_attachment=request, **kwargs)
    assert enriched == default + verify(request, result_path, delivery_path).input_block()
    with pytest.raises(emitter.EmitError):
        emitter.emit(result_path, boss_attachment=replace(request, mode='post_agent_comparison'), **kwargs)


def stage_readback(tmp_path, monkeypatch, mode='post_agent_comparison'):
    from dataclasses import replace
    from research.kalshi.frankie_raw_mbo_benchmark import native_staging as staging
    from research.kalshi.frankie_raw_mbo_benchmark import native_knowledge_delivery as knowledge
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_staging import finished_result, delivered_artifact
    from research.kalshi.frankie_raw_mbo_benchmark.tests.outputs_bundle_fixture import build_bundle, write_bundle
    from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import STREAM_RECEIPT_SCHEMA
    request, result_path, delivery_path = fixture(tmp_path)
    from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_emit_frankie_spawn import _accounted_prompt_test_crosswalk
    result = finished_result()
    result.update(_result(sha((emitter.REPO_ROOT / emitter.MISSION_PATH).read_bytes()), sha((emitter.REPO_ROOT / emitter.CONTRACT_PATH).read_bytes())))
    result['layers']['identity_receipt'].update(run_id='run-1', arm='A_MEMORY', source_manifest_hash='1'*64)
    result['result_hash'] = canonical_hash(result, omit='result_hash')
    result_path.write_bytes(encoded(result))
    delivery = json.loads(delivery_path.read_bytes())
    delivery['objects']['calculation_result.json'].update(sha256_observed=sha(encoded(result)), sha256_expected=sha(encoded(result)), bytes_observed=len(encoded(result)), bytes_expected=len(encoded(result)))
    delivery['receipt_sha256'] = canonical_hash(delivery, omit='receipt_sha256')
    delivery_path.write_bytes(encoded(delivery))
    binding = json.loads(request.crosswalk_path.read_bytes())
    binding['agent'].update(result_hash=result['result_hash'], delivery_receipt_sha256=delivery['receipt_sha256'])
    request.crosswalk_path.write_bytes(encoded(binding))
    request = replace(request, mode=mode, expected_crosswalk_sha256=sha(encoded(binding)))
    stream = dict(schema=STREAM_RECEIPT_SCHEMA, run_id='run-1', arm='A_MEMORY', complete=True, withheld_consumed=True)
    for ledger, lane in zip(staging.EXACT_LEDGERS, ('member_ledger','lifecycle_ledger','legacy_ledger')):
        row = delivery['ledgers'][ledger]
        stream[lane] = {'observed_bytes': row['plain_bytes_observed'], 'observed_sha256': row['plain_sha256_observed']}
    stream['receipt_sha256'] = canonical_hash(stream, omit='receipt_sha256')
    stream_path = tmp_path/'stream.json'
    stream_path.write_bytes(encoded(stream))
    k = knowledge.build_knowledge_delivery()
    written = knowledge.write_knowledge_delivery(k, tmp_path/'knowledge')
    monkeypatch.setattr(boss, '_executing_commit', lambda: 'b'*40)
    monkeypatch.setattr(emitter, 'crosswalk', lambda *a, **kw: _accounted_prompt_test_crosswalk())
    prompt = emitter.emit(result_path, delivery_receipt=delivery_path, knowledge_receipt=written['receipt'], boss_attachment=request if mode == 'attributed_input' else None).encode()
    accepted = verify(request, result_path, delivery_path)
    prompt_path = tmp_path/'prompt.md'
    prompt_path.write_bytes(prompt)
    output_dir = tmp_path/'outputs'
    outputs = write_bundle(build_bundle(delivery_receipt_sha256=delivery['receipt_sha256'], knowledge_receipt_sha256=k.receipt['receipt_sha256'], run_id='run-1'), output_dir)
    artifact = delivered_artifact(evidence_result_hash=result['result_hash'], delivery_receipt_sha256=delivery['receipt_sha256'], stream_receipt_sha256=stream['receipt_sha256'], outputs_receipt_sha256=outputs['receipt_sha256'], knowledge_receipt_sha256=k.receipt['receipt_sha256'], knowledge_use=knowledge.complete_knowledge_use(k.receipt))
    if mode == 'attributed_input': artifact['boss_attachment_receipt_sha256'] = accepted.receipt['receipt_sha256']
    artifact_path = tmp_path/'artifact.json'
    artifact_path.write_bytes(encoded(artifact))
    monkeypatch.setattr(boss, '_executing_commit', lambda: 'b'*40)
    return artifact_path, dict(result_path=result_path, delivery_receipt=delivery_path, stream_receipt=stream_path, knowledge_receipt=written['receipt'], knowledge_bundle=written['bundle'], prompt=prompt_path, outputs_dir=output_dir, render_report=False, boss_attachment=request)


@pytest.mark.parametrize('mode', boss.MODES)
def test_readback_joins_only_after_actual_principal_admission(tmp_path, monkeypatch, mode):
    from research.kalshi.frankie_raw_mbo_benchmark import native_staging as staging
    artifact, kwargs = stage_readback(tmp_path, monkeypatch, mode)
    summary = staging.read_back(artifact, **kwargs)
    combined = json.loads(Path(summary['boss_attachment']['path']).read_bytes())
    assert combined['attachment']['mode'] == mode
    assert combined['principal_artifact_sha256'] == summary['artifact_sha256']
    assert combined['principal_input_sha256']
    assert combined['outputs_receipt_sha256'] == summary['outputs_receipt_sha256']
    assert combined['receipt_sha256'] == canonical_hash(combined, omit='receipt_sha256')
    assert summary['findings_attached'] == 1


@pytest.mark.parametrize('fault', ['undrained', 'changed_ledger', 'changed_attachment', 'missing_knowledge', 'missing_prompt', 'missing_citation', 'existing_join'])
def test_join_failure_writes_no_readback_or_handoff(tmp_path, monkeypatch, fault):
    from research.kalshi.frankie_raw_mbo_benchmark import native_staging as staging
    artifact, kwargs = stage_readback(tmp_path, monkeypatch, 'attributed_input')
    if fault == 'undrained':
        stream = json.loads(kwargs['stream_receipt'].read_bytes())
        stream['withheld_consumed'] = False
        stream['receipt_sha256'] = canonical_hash(stream, omit='receipt_sha256')
        kwargs['stream_receipt'].write_bytes(encoded(stream))
        body = json.loads(artifact.read_bytes())
        body['stream_receipt_sha256'] = stream['receipt_sha256']
        artifact.write_bytes(encoded(body))
    elif fault == 'changed_ledger':
        delivery = json.loads(kwargs['delivery_receipt'].read_bytes())
        Path(delivery['ledgers'][staging.EXACT_LEDGERS[0]]['local_path']).write_bytes(b'changed')
    elif fault == 'changed_attachment': (kwargs['boss_attachment'].directory/'record-000000.json').write_bytes(b'{}')
    elif fault == 'missing_knowledge': kwargs['knowledge_bundle'] = None
    elif fault == 'missing_prompt': kwargs['prompt'] = None
    elif fault == 'missing_citation':
        body = json.loads(artifact.read_bytes())
        body.pop('boss_attachment_receipt_sha256')
        artifact.write_bytes(encoded(body))
    elif fault == 'existing_join': (tmp_path/'calculation_result_with_findings.boss.json').write_bytes(b'prior')
    with pytest.raises((staging.StagingError, boss.AttachmentError, ValueError)):
        staging.read_back(artifact, **kwargs)
    assert not (tmp_path/'calculation_result_with_findings.json').exists()
    assert not (tmp_path/'ONEWAY_HANDOFF.json').exists()


def test_accepts_actual_frozen_producer_export_without_boss_imports(tmp_path):
    import zipfile
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    archive = Path(__file__).parent/'fixtures/boss_handoff_8a79d775.zip'
    assert sha(archive.read_bytes()) == 'c6215567324ed7d8a586a163448c6d13268d7a83847d9b457c860048d80639ab'
    export = tmp_path/'real-producer'
    export.mkdir()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            assert Path(name).name == name
            (export/name).write_bytes(z.read(name))
    manifest = json.loads((export/'manifest.json').read_bytes())
    assert sha((export/'manifest.json').read_bytes()) == 'aee433b0d0251bb2519403a83c92d55b512d43f5d71914413a3b419144703044'
    binding = json.loads(request.crosswalk_path.read_bytes())
    binding['boss_source'] = manifest['source']
    mapping = {'kind': 'SYNTHETIC_TEST_ONLY_EXPLICIT_BINDING', 'boss_source': manifest['source'], 'agent': binding['agent']}
    request.mapping_artifact.write_bytes(encoded(mapping))
    binding['provenance'].update(mapping_artifact_sha256=sha(encoded(mapping)), mapping_artifact_bytes=len(encoded(mapping)))
    request.crosswalk_path.write_bytes(encoded(binding))
    request = replace(request, directory=export, expected_manifest_sha256=sha((export/'manifest.json').read_bytes()),
                      expected_boss_commit=manifest['boss_commit'], expected_agent_commit='9'*40,
                      controller_checkpoint=manifest['controller_checkpoint'], native_checkpoint=manifest['native_checkpoint'],
                      expected_crosswalk_sha256=sha(encoded(binding)))
    accepted = boss.verify_attachment(request, result_path=result, delivery_receipt=delivery, trusted_agent_commit='9'*40)
    assert len(json.loads(accepted.manifest_bytes)['targets']) == 3
    assert len(accepted.files) == 11


@pytest.mark.parametrize('fault', ['traversal', 'duplicate', 'unknown_field', 'zero_revision', 'checkpoint_schema', 'target_shape', 'noncanonical'])
def test_repinned_malformed_manifest_is_rejected(tmp_path, fault):
    from dataclasses import replace
    request, result, delivery = fixture(tmp_path)
    path = request.directory/'manifest.json'
    manifest = json.loads(path.read_bytes())
    if fault == 'traversal': manifest['files'][0]['path'] = '../mapping.json'
    elif fault == 'duplicate': manifest['files'].append(manifest['files'][-1])
    elif fault == 'unknown_field': manifest['secret_extra'] = 1
    elif fault == 'zero_revision': manifest['targets'][0]['revision'] = 0
    elif fault == 'checkpoint_schema': manifest['native_checkpoint']['schema'] = 'other'
    elif fault == 'target_shape': manifest['targets'][0]['target']['extra'] = 1
    raw = encoded(manifest) + (b'\n' if fault == 'noncanonical' else b'')
    path.write_bytes(raw)
    request = replace(request, expected_manifest_sha256=sha(raw))
    with pytest.raises(boss.AttachmentError): verify(request, result, delivery)


def test_hardlinked_attachment_is_rejected(tmp_path):
    import os
    request, result, delivery = fixture(tmp_path)
    os.link(request.directory/'forecast-000000.bin', tmp_path/'linked')
    with pytest.raises(boss.AttachmentError): verify(request, result, delivery)


def test_default_runtime_refuses_uncommitted_sources(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(boss.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1))
    monkeypatch.setattr(boss.subprocess, 'check_output', lambda *a, **kw: '')
    with pytest.raises(boss.AttachmentError, match='clean committed'): boss._executing_commit()


def test_default_runtime_refuses_untracked_sources(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(boss.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(boss.subprocess, 'check_output', lambda *a, **kw: 'research/injected.py')
    with pytest.raises(boss.AttachmentError, match='clean committed'): boss._executing_commit()


def test_request_configuration_has_explicit_relative_paths_and_no_version_override(tmp_path):
    from dataclasses import asdict
    request, _, _ = fixture(tmp_path)
    body = asdict(request)
    for name in ('directory', 'crosswalk_path', 'mapping_artifact'):
        body[name] = str(body[name].relative_to(tmp_path))
    path = tmp_path/'request.json'
    path.write_bytes(encoded(body))
    assert boss.load_request(path) == request
    body['trusted_agent_commit'] = 'b'*40
    path.write_bytes(encoded(body))
    with pytest.raises(boss.AttachmentError): boss.load_request(path)


def test_attachment_cli_preserves_emitted_lf_bytes(tmp_path, monkeypatch):
    from dataclasses import asdict
    from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
    request, result, delivery = fixture(tmp_path)
    body = asdict(request)
    for name in ('directory', 'crosswalk_path', 'mapping_artifact'): body[name] = str(body[name])
    config = tmp_path/'request.json'
    config.write_bytes(encoded(body))
    text = 'exact prompt\nBOSS block\n'
    monkeypatch.setattr(emitter, 'emit', lambda *a, **kw: text)
    output = tmp_path/'emitted.md'
    assert emitter.main(['--result', str(result), '--delivery-receipt', str(delivery), '--knowledge-receipt', 'unused', '--boss-attachment-request', str(config), '--output', str(output)]) == 0
    assert output.read_bytes() == text.encode()


def test_default_runtime_requires_implementation_modules_to_be_tracked(monkeypatch):
    from types import SimpleNamespace
    import subprocess
    monkeypatch.setattr(boss.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    def output(command, **kwargs):
        if '--error-unmatch' in command:
            raise subprocess.CalledProcessError(1, command)
        return '' if '--others' in command else 'b'*40
    monkeypatch.setattr(boss.subprocess, 'check_output', output)
    with pytest.raises(boss.AttachmentError, match='committed agent identity unavailable'):
        boss._executing_commit()
