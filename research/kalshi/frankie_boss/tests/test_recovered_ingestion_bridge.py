"""Explicit recovered-ingestion admission: real tiny compact source, no runtime services."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_prepare_trading_day import inputs, sha, witness, write_json, checked_json
from test_day_pipeline import CONFIG
from research.kalshi.frankie_boss import c15_journal
from research.kalshi.frankie_boss.block_source_scope import block_source_scope
from research.kalshi.frankie_boss.causal_prefix_records import RecordPrefixChain
from research.kalshi.frankie_boss.completed_schedule_view import open_completed_schedule_view
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.sealed_compact_recovery import ORIGINAL_CODE_BLOBS, original_identity
from research.kalshi.frankie_boss.source_conformance import SourceCompletion
from research.kalshi.frankie_boss.operations.prepare_trading_day import prepare
from research.kalshi.frankie_boss.operations import day_pipeline as dp

SCHEMA = 'FRANKIE_VERIFIED_RECOVERED_INGESTION_V1'


def recovered_inputs(tmp_path, monkeypatch):
    config, source, output = inputs(tmp_path, monkeypatch)
    configuration = json.loads(config.read_bytes())
    launch = checked_json(configuration['trading_day_launch'])
    legacy = checked_json(launch['ingestion_receipt'])
    recovery_dir = tmp_path / 'separate-recovery'
    recovery_dir.mkdir()
    state = c15_journal.unpack(json.loads((source/'builder-checkpoint.c15.json').read_bytes()))
    state['implementation'] = original_identity(ORIGINAL_CODE_BLOBS)
    state['state_hash'] = c15_journal.evidence_hash({k:v for k,v in state.items() if k != 'state_hash'})
    checkpoint = write_json(recovery_dir/'builder-checkpoint.c15.json', c15_journal.pack(state))
    completion = json.loads((source/'completion.json').read_bytes())
    completion['builder_state_hash'] = state['state_hash']
    completion_pin = write_json(recovery_dir/'completion.json', completion)
    completed = SourceCompletion(**dict(completion, member_counts=tuple(completion['member_counts'])))
    receipt = dict(schema='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1', status='complete',
        original_ingest_status='Cancelled', original_run_id=123, original_ssm_command_id='test-original',
        code_commit='1'*40, container=witness(source/'journal.compact.sqlite'),
        artifacts={key:dict(file=Path(pin['path']).name, bytes=pin['bytes'], sha256=pin['sha256'])
                   for key,pin in [('checkpoint',checkpoint),('completion',completion_pin)]},
        checkpoint_state_hash=state['state_hash'], completion_digest=completed.digest,
        original_implementation=state['implementation'], manifest_hash=legacy['manifest_hash'],
        session_policy='cme_trading_day', trading_day='20211004', sessions=legacy['sessions'],
        source_object_naming='member_key', source_boundary_sha256='a'*64,
        source_replays=0, adapter_apply_calls=0, parent_writes=0, model_calls=0, training_updates=0,
        **{key:completion[key] for key in ('scope_hash','record_count','journal_count',
                                         'journal_hash','group_count','source_prefix_hash')})
    raw_receipt = write_json(recovery_dir/'recovery-receipt.json', receipt)
    verification = dict(schema='FRANKIE_MONDAY_INGESTION_RECOVERY_VERIFIED_V1', status='complete',
        completion_method='sealed_journal_conformance_recovery', original_ingest_status='Cancelled',
        original_implementation_roundtrip=True, recovery_receipt_sha256=raw_receipt['sha256'],
        source_manifest_hash=receipt['manifest_hash'], checkpoint_sha256=checkpoint['sha256'],
        checkpoint_state_hash=state['state_hash'], completion_digest=completed.digest,
        container=receipt['container'], source_replays=0, adapter_apply_calls=0, parent_writes=0, model_calls=0,
        requested_window=dict(clock='ts_recv_ns', start_inclusive_ns=1633298400000000000,
                              end_exclusive_ns=1633381200000000000),
        requested_window_records=2, retained_preopen_context_records=0,
        first_window_source_cursor=0, last_window_source_cursor=1,
        **{key:receipt[key] for key in ('scope_hash','record_count','journal_count',
                                       'journal_hash','group_count','source_prefix_hash')})
    verification_pin = write_json(recovery_dir/'independent-verification.json', verification)
    descriptor = dict(schema=SCHEMA, source_manifest=configuration['source_manifest'],
        recovery_receipt=raw_receipt, verification=verification_pin,
        checkpoint=checkpoint, completion=completion_pin)
    descriptor_pin = write_json(tmp_path/'recovered-ingestion.json', descriptor)
    launch['ingestion_receipt'] = descriptor_pin
    configuration['trading_day_launch'] = write_json(tmp_path/'launch.json', launch)
    write_json(config, configuration)
    # This represents a cancelled producer, whose directory and evidence are immutable.
    write_json(source/'failure.json', dict(status='Cancelled', original_run_id=123))
    before = {str(p):sha(p) for p in source.iterdir() if p.is_file()}
    return SimpleNamespace(config=config, output=output, source=source, recovery_dir=recovery_dir,
        descriptor=descriptor, pin=descriptor_pin, receipt=receipt, verification=verification,
        completion=completion, state=state, before=before)


def repin(fixture, key, value):
    fixture.descriptor[key] = write_json(fixture.descriptor[key]['path'], value)
    fixture.pin = write_json(fixture.pin['path'], fixture.descriptor)


def load(fixture):
    from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
    return load_recovered_ingestion(fixture.pin)


def test_verified_recovery_retains_original_paths_bytes_and_producer_identity(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    value = load(f)
    assert value.receipt['schema'] == 'FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1'
    assert value.state['implementation'] == original_identity(ORIGINAL_CODE_BLOBS)
    assert value.container == f.receipt['container']
    assert value.checkpoint_path == Path(f.descriptor['checkpoint']['path'])
    assert value.completion_path == Path(f.descriptor['completion']['path'])
    assert value.completion == f.completion
    assert value.manifest['manifest_hash'] == f.receipt['manifest_hash']
    assert value.provenance['descriptor'] == f.pin
    assert value.provenance['recovery_receipt'] == f.descriptor['recovery_receipt']
    assert value.provenance['verification'] == f.descriptor['verification']
    assert {str(p):sha(p) for p in f.source.iterdir() if p.is_file()} == f.before


@pytest.mark.parametrize('field,bad', [
    ('status','running'), ('original_ingest_status','Succeeded'),
    ('completion_method','normal_ingestion'), ('original_implementation_roundtrip',False),
    ('recovery_receipt_sha256','0'*64), ('source_manifest_hash','0'*64),
    ('checkpoint_sha256','0'*64), ('completion_digest','0'*64),
    ('source_prefix_hash','0'*64), ('journal_count',2), ('record_count',1),
    ('model_calls',1), ('source_replays',1), ('adapter_apply_calls',1), ('parent_writes',1),
    ('requested_window_records',1), ('first_window_source_cursor',1)])
def test_independent_verification_cannot_be_rebound_by_repinning(tmp_path, monkeypatch, field, bad):
    f = recovered_inputs(tmp_path, monkeypatch)
    repin(f, 'verification', dict(f.verification, **{field:bad}))
    with pytest.raises(ValueError):
        load(f)


def test_raw_receipt_hash_refuses_semantically_identical_reformat(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    path = Path(f.descriptor['recovery_receipt']['path'])
    path.write_text(json.dumps(f.receipt, indent=2))
    f.descriptor['recovery_receipt'] = witness(path)
    f.pin = write_json(f.pin['path'], f.descriptor)
    with pytest.raises(ValueError, match='recovery receipt'):
        load(f)


@pytest.mark.parametrize('key', ['checkpoint','completion','source_manifest'])
def test_pinned_artifact_byte_mutation_is_rejected(tmp_path, monkeypatch, key):
    f = recovered_inputs(tmp_path, monkeypatch)
    with Path(f.descriptor[key]['path']).open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(ValueError):
        load(f)


def test_recovery_rejects_a_different_original_implementation_even_with_rehashed_state(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    f.state['implementation']['code_blobs']['c15_builder.py'] = 'f'*40
    f.state['state_hash'] = c15_journal.evidence_hash({k:v for k,v in f.state.items() if k != 'state_hash'})
    repin(f, 'checkpoint', c15_journal.pack(f.state))
    f.receipt['original_implementation'] = f.state['implementation']
    repin(f, 'recovery_receipt', f.receipt)
    repin(f, 'verification', dict(f.verification,
          recovery_receipt_sha256=f.descriptor['recovery_receipt']['sha256']))
    with pytest.raises(ValueError):
        load(f)


def test_original_container_copy_is_not_the_original_journal(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    original = Path(f.receipt['container']['path'])
    copy = tmp_path/'copied-journal.sqlite'
    copy.write_bytes(original.read_bytes())
    repin(f, 'verification', dict(f.verification, container=witness(copy)))
    with pytest.raises(ValueError):
        load(f)


def test_journal_mutation_and_live_sidecar_are_refused(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    original = Path(f.receipt['container']['path'])
    sidecar = Path(str(original)+'-wal')
    sidecar.write_bytes(b'live')
    with pytest.raises(ValueError, match='sidecar'):
        load(f)
    sidecar.unlink()
    with original.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError):
        load(f)


def test_default_view_still_rejects_original_identity_without_explicit_recovery(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    manifest = checked_json(f.descriptor['source_manifest'])
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    args = (scope, f.receipt['container']['path'], f.descriptor['checkpoint']['path'],
            f.descriptor['checkpoint']['sha256'], f.state['state_hash'], f.completion)
    with pytest.raises(ValueError, match='implementation identity'):
        open_completed_schedule_view(*args, reader_factory=FrankieCompactReader)
    view = open_completed_schedule_view(*args, reader_factory=FrankieCompactReader,
                                        recovery_descriptor=f.pin)
    try:
        assert view.chain.next_cursor == 2
        assert len(list(view.journal.entries())) == 4
    finally:
        view.journal.close()


def test_explicit_view_cannot_be_used_with_a_copied_journal(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    manifest = checked_json(f.descriptor['source_manifest'])
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    copy = tmp_path/'copy.sqlite'
    copy.write_bytes(Path(f.receipt['container']['path']).read_bytes())
    with pytest.raises(ValueError):
        open_completed_schedule_view(scope, copy, f.descriptor['checkpoint']['path'],
            f.descriptor['checkpoint']['sha256'], f.state['state_hash'], f.completion,
            reader_factory=FrankieCompactReader, recovery_descriptor=f.pin)


def prepared_host(f, prepared):
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    from research.kalshi.frankie_boss.operations import run_actual_sunday_compact_source as compact
    from research.kalshi.frankie_boss import sunday_execution
    from research.kalshi.frankie_boss.online_source_prefix import OnlinePrefix, PrefixCursor
    from research.kalshi.frankie_boss.selected_source_scope import source_scope
    from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader
    host = compact.host_class(actual).__new__(compact.host_class(actual))
    host.config, host.host = prepared, prepared['host_runtime']
    host.scope = host.builder = host.context = host.probe = host.cache = None
    host.api = SimpleNamespace(journal=c15_journal, driver=sunday_execution, source_scope=source_scope,
        OnlinePrefix=OnlinePrefix, PrefixCursor=PrefixCursor, FrankieCompactReader=FrankieCompactReader,
        VerifiedJournalReader=VerifiedJournalReader)
    for key in ('memory','mapping','retained_witnesses','delivery_receipt','calculation_result'):
        host.config.setdefault(key, f.descriptor['source_manifest'])
    host.saved = {}
    host.save = lambda name,value: host.saved.__setitem__(name,value)
    return host


def test_prepare_and_compact_host_consume_recovery_without_restarting_ingestion(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    # Ingestion has finished; any subsequent attempt to run it is a test failure.
    from test_ingest_block_sources import tool
    monkeypatch.setattr(tool, 'main', lambda: pytest.fail('ingestion restart'))
    result = prepare(f.config, output_configuration=f.output, cycles=1)
    prepared = checked_json(result['configuration'])
    assert prepared['source_directory'] == str(f.recovery_dir.resolve())
    assert prepared['host_runtime']['compact_journal'] == f.receipt['container']
    assert prepared['host_runtime']['ingestion_receipt'] == f.pin
    assert not (f.recovery_dir/'ingestion-receipt.json').exists()
    outer = checked_json(prepared['host_runtime']['schedule_receipt'])
    assert outer['recovered_ingestion']['descriptor'] == f.pin
    host = prepared_host(f, prepared)
    host.source()
    assert host.source_origins == {f.receipt['container']['path']:4}
    assert host.completion_sha256 == f.descriptor['completion']['sha256']
    cycle_dir = tmp_path/'cycle-test'
    cycle_dir.mkdir()
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
    binding = bind_cycle(prepared['contract']['path'], prepared['contract']['sha256'], 0, host.schedule['steps'][0])
    try:
        host.prefix(binding, cycle_dir)
        assert host.source_checkpoint['count'] == 2
        assert Path(host.source_journal_path).is_file()
    finally:
        if host.builder is not None:
            host.builder.journal.close()
        if getattr(host, '_compact', None) is not None:
            host._compact.close()
    assert {str(p):sha(p) for p in f.source.iterdir() if p.is_file()} == f.before


@pytest.mark.parametrize('change', ['compact_path','outer_provenance'])
def test_runtime_requires_recovery_provenance_and_original_compact_path(tmp_path, monkeypatch, change):
    f = recovered_inputs(tmp_path, monkeypatch)
    result = prepare(f.config, output_configuration=f.output, cycles=1)
    prepared = checked_json(result['configuration'])
    if change == 'compact_path':
        copy = tmp_path/'copied.sqlite'
        copy.write_bytes(Path(f.receipt['container']['path']).read_bytes())
        prepared['host_runtime']['compact_journal'] = witness(copy)
    else:
        outer_pin = prepared['host_runtime']['schedule_receipt']
        outer = checked_json(outer_pin)
        outer.pop('recovered_ingestion', None)
        prepared['host_runtime']['schedule_receipt'] = write_json(outer_pin['path'], outer)
    with pytest.raises(ValueError):
        prepared_host(f, prepared).source()


def test_pipeline_admits_explicit_verified_recovery_with_original_provenance(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    config = dict(CONFIG, trading_day_schedule=dict(trading_day='20211004', step_count=1,
        source_record_count=2, source_manifest_hash=f.receipt['manifest_hash'], schedule_sha256='b'*64))
    pipeline = dp.DayPipeline(config, '20211004', runs_root=tmp_path/'pipeline')
    pipeline.write('stage-sources', dict(manifest=f.descriptor['source_manifest']['path'],
        manifest_hash=f.receipt['manifest_hash'], records=2), command=[])
    pipeline.write('host-start', dict(ssm_online=True), command=[])
    with pytest.raises(dp.StageRefused):
        pipeline.record_external('ingest', f.descriptor['recovery_receipt']['path'])
    assert pipeline.record_external('ingest', f.pin['path']) == 'done'
    gate = pipeline.receipt('ingest')['gate']
    assert gate['journal_count'] == 2 and gate['journal_entries'] == 4
    assert gate['compact_sha256'] == f.receipt['container']['sha256']
    assert gate['recovered_ingestion']['recovery_receipt'] == f.descriptor['recovery_receipt']
    assert gate['recovered_ingestion']['verification'] == f.descriptor['verification']
