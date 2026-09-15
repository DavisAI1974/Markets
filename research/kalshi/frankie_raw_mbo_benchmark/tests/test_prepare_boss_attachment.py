"""Synthetic coordinator fixtures; none are operational mapping evidence."""
import json
import pytest
from research.kalshi.frankie_raw_mbo_benchmark import native_boss_attachment as boss
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_boss_attachment import fixture, encoded, sha
from research.kalshi.frankie_raw_mbo_benchmark import prepare_boss_attachment as prep


def inputs(tmp_path, monkeypatch, evidence=None):
    request, result, delivery = evidence or fixture(tmp_path)
    binding = json.loads(request.crosswalk_path.read_bytes())
    pins = {'schema': prep.PIN_SCHEMA,
            'pin_origin': {'authority': 'synthetic coordinator', 'method': 'independent fixture pins', 'reference': 'synthetic-only'},
            'expected_manifest_sha256': request.expected_manifest_sha256,
            'expected_boss_commit': request.expected_boss_commit,
            'expected_agent_commit': request.expected_agent_commit,
            'controller_checkpoint': dict(request.controller_checkpoint), 'native_checkpoint': dict(request.native_checkpoint),
            'boss_source': binding['boss_source'], 'agent': binding['agent'], 'provenance': binding['provenance'],
            'result_file_sha256': sha(result.read_bytes()), 'delivery_file_sha256': sha(delivery.read_bytes()),
            'mode': 'attributed_input'}
    path = tmp_path / 'pins.json'
    path.write_bytes(encoded(pins))
    monkeypatch.setattr(boss, '_executing_commit', lambda: 'b'*40)
    return dict(pins_path=path, expected_pins_sha256=sha(path.read_bytes()), directory=request.directory,
                result_path=result, delivery_receipt=delivery, mapping_artifact=request.mapping_artifact,
                output_directory=tmp_path / 'prepared'), pins


def test_preparation_is_accepted_by_authoritative_receiver(tmp_path, monkeypatch):
    kwargs, _ = inputs(tmp_path, monkeypatch)
    receipt = prep.prepare(**kwargs)
    request = boss.load_request(kwargs['output_directory'] / 'attachment-request.json')
    accepted = boss.verify_attachment(request, result_path=kwargs['result_path'], delivery_receipt=kwargs['delivery_receipt'])
    assert receipt['attachment_receipt'] == accepted.receipt
    assert receipt['mapping_status'] == 'CALLER_ATTESTED_WITH_BYTE_WITNESS'
    assert len(receipt['ledger_witnesses']) == 3
    for name, witness in receipt['outputs'].items():
        assert sha((kwargs['output_directory'] / name).read_bytes()) == witness['sha256']
    assert accepted.input_block().endswith('\n')


@pytest.mark.parametrize('section,field,value', [
    ('agent', 'run_id', 'wrong-run'), ('agent', 'source_day', '20211004'),
    ('agent', 'arm', 'A_CLEAN'), ('agent', 'source_manifest_hash', 'f'*64),
    ('boss_source', 'through_cursor', 9), ('boss_source', 'as_of', 9),
    ('boss_source', 'source_as_of', 9), ('boss_source', 'arm_hash', 'f'*64),
    (None, 'expected_boss_commit', 'c'*40), (None, 'expected_agent_commit', 'c'*40),
    (None, 'expected_manifest_sha256', 'f'*64), (None, 'mode', 'post_agent_comparison'),
])
def test_independent_pins_cannot_be_replaced_by_export_claims(tmp_path, monkeypatch, section, field, value):
    kwargs, pins = inputs(tmp_path, monkeypatch)
    (pins[section] if section else pins)[field] = value
    kwargs['pins_path'].write_bytes(encoded(pins))
    kwargs['expected_pins_sha256'] = sha(encoded(pins))
    with pytest.raises(ValueError): prep.prepare(**kwargs)
    assert not kwargs['output_directory'].exists()


@pytest.mark.parametrize('kind', ['pin_hash', 'missing_pin', 'mapping', 'ledger', 'partial', 'result', 'delivery'])
def test_changed_or_missing_evidence_fails_without_output(tmp_path, monkeypatch, kind):
    kwargs, pins = inputs(tmp_path, monkeypatch)
    if kind == 'pin_hash': kwargs['expected_pins_sha256'] = 'f'*64
    elif kind == 'missing_pin':
        del pins['pin_origin']
        kwargs['pins_path'].write_bytes(encoded(pins))
        kwargs['expected_pins_sha256'] = sha(encoded(pins))
    elif kind == 'mapping': kwargs['mapping_artifact'].write_bytes(b'changed')
    elif kind == 'ledger':
        delivery = json.loads(kwargs['delivery_receipt'].read_bytes())
        from pathlib import Path
        Path(next(iter(delivery['ledgers'].values()))['local_path']).write_bytes(b'changed')
    elif kind == 'partial': (kwargs['directory'] / 'critic-prompt.txt').unlink()
    elif kind == 'result': kwargs['result_path'].write_bytes(b'{}')
    elif kind == 'delivery': kwargs['delivery_receipt'].write_bytes(b'{}')
    with pytest.raises(ValueError): prep.prepare(**kwargs)
    assert not kwargs['output_directory'].exists()


def test_existing_evidence_is_not_overwritten(tmp_path, monkeypatch):
    kwargs, _ = inputs(tmp_path, monkeypatch)
    prep.prepare(**kwargs)
    before = {p.name: p.read_bytes() for p in kwargs['output_directory'].iterdir()}
    with pytest.raises(FileExistsError): prep.prepare(**kwargs)
    assert {p.name: p.read_bytes() for p in kwargs['output_directory'].iterdir()} == before


def test_prepared_bytes_and_citation_survive_ordinary_readback(tmp_path, monkeypatch):
    from pathlib import Path
    from research.kalshi.frankie_raw_mbo_benchmark import native_staging as staging
    from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_boss_attachment import stage_readback
    artifact, readback = stage_readback(tmp_path, monkeypatch, 'attributed_input')
    kwargs, _ = inputs(tmp_path, monkeypatch, (readback['boss_attachment'], readback['result_path'], readback['delivery_receipt']))
    receipt = prep.prepare(**kwargs)
    readback['boss_attachment'] = boss.load_request(kwargs['output_directory'] / 'attachment-request.json')
    prompt = emitter.emit(readback['result_path'], delivery_receipt=readback['delivery_receipt'],
                          knowledge_receipt=readback['knowledge_receipt'], boss_attachment=readback['boss_attachment'])
    assert prompt.encode() == readback['prompt'].read_bytes()
    summary = staging.read_back(artifact, **readback)
    combined = json.loads(Path(summary['boss_attachment']['path']).read_bytes())
    assert combined['attachment'] == receipt['attachment_receipt']
    assert summary['findings_attached'] == 1


def test_preparation_cannot_write_inside_export(tmp_path, monkeypatch):
    kwargs, _ = inputs(tmp_path, monkeypatch)
    kwargs['output_directory'] = kwargs['directory'] / 'prepared'
    with pytest.raises(boss.AttachmentError, match='must not mutate'):
        prep.prepare(**kwargs)
    assert not kwargs['output_directory'].exists()
