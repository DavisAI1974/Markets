"""Exercise preparation with real tiny test-fixture journal evidence."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from test_ingest_block_sources import DAY, HOUR, _monday_manifest, tool
from test_mbo_source import record
from test_source_contract_runtime import fixture as contract_fixture
from research.kalshi.frankie_boss.operations.prepare_trading_day import prepare
from research.kalshi.frankie_boss.compact_journal import CompactReader

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def witness(path):
    path = Path(path)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))

def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    return witness(path)

def checked_json(pin):
    path = Path(pin['path'])
    assert sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes']
    return json.loads(path.read_bytes())

def inputs(tmp_path, monkeypatch, foreign_manifest=False):
    first, last, following = DAY + 2*HOUR, DAY + 20*HOUR, DAY + 21*HOUR
    rows = [record(i, ts_event=t-1, ts_recv=t) for i, t in enumerate((first,last,following),1)]
    manifest = _monday_manifest(tmp_path, take=2, rows=rows)
    manifest_path = tmp_path / 'source-manifest.json'
    manifest_pin = write_json(manifest_path, manifest)
    source = tmp_path / 'completed-source'
    with monkeypatch.context() as arguments:
        arguments.setattr(sys, 'argv', ['ingest', '--manifest', str(manifest_path),
            '--sources-dir', str(tmp_path), '--output-dir', str(source),
            '--session-policy', 'cme_trading_day', '--writer', 'compact', '--workers', '0'])
        tool.main()
    ingestion_path = source / 'ingestion-receipt.json'
    ingestion = json.loads(ingestion_path.read_bytes())
    assert ingestion['record_count'] == 2 and ingestion['journal_count'] == 4
    mapping = tmp_path / 'mapping.jsonl'
    mapping.write_text(''.join(json.dumps(dict(cursor_start=i,cursor_end=i))+'\n' for i in range(2)))
    cutoffs = write_json(tmp_path / 'cutoffs.json', dict(invocation_cutoffs=[
        dict(group_index=0, recv_ns=first, first_lawful_availability_ns=first)]))
    contract_path, _, _ = contract_fixture(tmp_path)
    contract = json.loads(contract_path.read_bytes())
    contract.update(schema='FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1', trading_day='20211004',
        source_manifest_hash='f'*64 if foreign_manifest else manifest['manifest_hash'],
        cycle_count=1, cycles=contract['cycles'][:1])
    cycle = contract['cycles'][0]
    cycle.update(historical_group_index=0,
        source_prefix=dict(source_cursor=0, receive_cutoff_ns=first, event_cutoff_ns=first-1),
        learning_cutoff_ns=last, learning_through_source_cursor=1)
    session = cycle['forecast_session']
    session.update(session_id='test-monday', open_ns=DAY-2*HOUR, close_ns=DAY+21*HOUR,
        event_cutoff_ns=first-1, receive_cutoff_ns=first)
    session['prior_close'].update(event_ns=DAY-3*HOUR, receive_ns=DAY-3*HOUR+1)
    session['opening'].update(event_ns=DAY-2*HOUR, receive_ns=DAY-2*HOUR+1)
    contract_pin = write_json(contract_path, contract)
    launch = write_json(tmp_path/'launch.json', dict(schema='FRANKIE_TRADING_DAY_LAUNCH_V1',
        trading_day='20211004', source_manifest=dict(manifest_pin,manifest_hash=manifest['manifest_hash']),
        declared_record_count=2, model_context_rows=1, cutoff_rule='first closed test group; feedback through terminal',
        cutoffs=cutoffs, ingestion_receipt=witness(ingestion_path), mapping=witness(mapping),
        source_contract=contract_pin, publish_route='test-only'))
    config = tmp_path/'configuration.json'
    write_json(config, dict(trading_day_launch=launch, source_manifest=manifest_pin,
        schedule_directory=str(tmp_path/'new-schedule'), host_runtime=dict(source_entity=[1,1],
        prefixes_directory=str(tmp_path/'new-prefixes'), data_workers=1)))
    return config, source, tmp_path/'prepared.json'

def test_prepare_builds_verified_cycle_zero_from_completed_compact_source(tmp_path, monkeypatch):
    config, source, output = inputs(tmp_path, monkeypatch)
    before = {p.name:sha(p) for p in source.iterdir() if p.is_file()}
    original_config = config.read_bytes()
    result = prepare(config, output_configuration=output, cycles=1)
    assert result['prefix_count'] == 1 and result['source_records'] == 2 and result['day'] == '20211004'
    prepared = checked_json(result['configuration'])
    host = prepared['host_runtime']
    assert prepared['source_directory'] == str(source.resolve())
    assert host['compact_journal']['sha256'] == before['journal.compact.sqlite']
    schedule = checked_json(host['schedule'])
    assert schedule['step_count'] == 1 and schedule['source_record_count'] == 2
    assert schedule['steps'][0]['through_cursor'] == 0
    assert schedule['steps'][0]['feedback_available_through']['through_cursor'] == 1
    assert schedule['schedule_sha256'] == result['schedule_sha256']
    manifest = checked_json(host['prefix_manifest'])
    assert manifest['prefixes'] == manifest['scheduled_cycles'] == 1
    assert manifest['source_replays'] == manifest['model_calls'] == 0
    assert host['prefix_manifest']['sha256'] == result['prefixes_sha256']
    files = checked_json(manifest['witnesses'][0])
    receipt = checked_json(files['receipt'])
    snapshot = Path(files['snapshot']['path'])
    assert sha(snapshot) == files['snapshot']['sha256']
    assert snapshot.stat().st_size == files['snapshot']['bytes']
    assert receipt['through_cursor'] == 0 and receipt['journal_count'] == 2
    assert receipt['full_source_complete'] is False
    with CompactReader(snapshot, expected_count=receipt['journal_count'],
                       expected_head_hash=receipt['journal_head_hash']) as reader:
        entries = list(reader.entries())
    assert [e['kind'] for e in entries] == ['INPUT','APPLIED']
    assert entries[-1]['payload']['cursor'] == 0
    seed = checked_json(manifest['prefix_seed_witnesses']['0'])
    assert seed['cycle_index'] == 0 and seed['through_cursor'] == 0
    assert seed['entity'] == [1,1] and seed['t_ctx'] == 1
    assert seed['source_prefix_hash'] == schedule['steps'][0]['source_hash']
    assert seed['snapshot_sha256'] == files['snapshot']['sha256']
    assert config.read_bytes() == original_config
    assert {p.name:sha(p) for p in source.iterdir() if p.is_file()} == before

def test_prepare_refuses_contract_for_different_source_manifest(tmp_path, monkeypatch):
    config, source, output = inputs(tmp_path, monkeypatch, foreign_manifest=True)
    original = sha(source/'journal.compact.sqlite')
    with pytest.raises(ValueError, match='manifest'):
        prepare(config, output_configuration=output, cycles=1)
    assert not output.exists() and not (tmp_path/'new-schedule').exists()
    assert not (tmp_path/'new-prefixes').exists()
    assert sha(source/'journal.compact.sqlite') == original
