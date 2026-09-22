"""Actual SDK synthetic bytes only; no Databento connection or market data."""
import hashlib
from dataclasses import replace

import databento_dbn as dbn
import pytest
import zstandard

from causal_prefix import SourceMember, SourceScope, ScopeKind
from causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from source_conformance import SourceConformanceDriver
from mbo_source import (MboSourcePin, runtime_hash, extract_mbo, ingest_sources,
                        SOURCE_EXTRA_FIELDS)


ALL_FIXTURE_ROWS = 1 << 20   # a declared window larger than any fixture: the row window has no default (Greg, 2026-09-22)

def pin(version=3):
    return MboSourcePin(version, runtime_hash())


def record(sequence=1, ts_out=None, **changes):
    args = dict(publisher_id=1, instrument_id=1, ts_event=sequence * 100,
                order_id=2**60 + sequence, price=3100000000, size=7,
                action=dbn.Action.ADD, side=dbn.Side.BID, ts_recv=sequence * 100 + 1,
                flags=128, channel_id=1, ts_in_delta=-1, sequence=sequence)
    if ts_out is not None:
        args['ts_out'] = ts_out
    return dbn.MBOMsg(**dict(args, **changes))


def dbn_bytes(records, *, version=3, ts_out=False, schema=dbn.Schema.MBO):
    metadata = dbn.Metadata(dataset='SYNTHETIC', start=0,
        stype_in=dbn.SType.RAW_SYMBOL, stype_out=dbn.SType.INSTRUMENT_ID,
        schema=schema, version=version, ts_out=ts_out)
    return bytes(metadata) + b''.join(bytes(r) for r in records)


def source(tmp_path, payload, count, name='synthetic.dbn'):
    path = tmp_path / name
    path.write_bytes(payload)
    member = SourceMember(0, name, hashlib.sha256(payload).hexdigest(), len(payload), count)
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a' * 64, (member,), SUPPORTED_ADAPTER_REVISION)
    return path, scope


def ingest(tmp_path, payload, count=1, **changes):
    path, scope = source(tmp_path, payload, count)
    args = dict(expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    args.update(changes)
    return ingest_sources(scope, (path,), tmp_path/'journal.sqlite', pin(), **args), scope


@pytest.mark.parametrize('ts_out', [None, 123, 2**64 - 1])
def test_actual_sdk_mapping_preserves_exact_fields_and_bytes(ts_out):
    native = record(ts_out=ts_out)
    raw = extract_mbo(native, pin())
    assert raw['dbn_wire_bytes'] == bytes(native)
    assert raw['dbn_length'] * 4 == len(bytes(native))
    # The pinned SDK omits UNDEF_TIMESTAMP from the physical record. Preserve
    # physical presence rather than inventing an optional field from constructor input.
    assert raw['ts_out'] == (ts_out if len(bytes(native)) == 64 else None)
    assert raw['order_id'] == 2**60 + 1
    assert raw['ts_in_delta'] == -1
    assert raw['price'] == 3100000000
    assert raw['action'] == 'A' and raw['side'] == 'B'
    assert raw['rtype'] == 160


@pytest.mark.parametrize('compressed', [False, True])
def test_file_to_driver_restore_and_native_tensor_roundtrip(tmp_path, compressed):
    records = [record(1), record(2)]
    payload = dbn_bytes(records)
    if compressed:
        payload = zstandard.ZstdCompressor().compress(payload)
    result, scope = ingest(tmp_path, payload, 2)
    assert result.completion.record_count == 2
    assert result.metadata[0].startswith(b'DBN\x03')
    restored = SourceConformanceDriver.restore(scope, tmp_path/'journal.sqlite',
        result.checkpoint, expected_scope_hash=scope.genesis_hash(),
        expected_state_hash=result.completion.builder_state_hash)
    try:
        rows = [entry['raw_record'] for entry in restored.evidence_stream()]
        assert [r['dbn_wire_bytes'] for r in rows] == [bytes(r) for r in records]
        from native_mbo_encoder import NativeRegistry, encode, reconstruct
        registry = NativeRegistry(extra_fields=SOURCE_EXTRA_FIELDS)
        assert reconstruct(encode(rows, as_of=201, registry=registry), registry) == rows
        from native_mbo_encoder import NativeTrunk
        from context_session import ContextSessionRunner
        model = NativeTrunk(registry, d_model=16, n_heads=2, n_layers=1).double().eval()
        output = ContextSessionRunner(model, restored._builder, entity=(1, 1),t_ctx=ALL_FIXTURE_ROWS).run(
            as_of=201, through_cursor=1)
        assert output.receipt.consumed_rows == 2
        assert restored.complete() == result.completion
    finally:
        restored.close()


def test_wrong_source_hash_rejects_before_journal_creation(tmp_path):
    path, scope = source(tmp_path, dbn_bytes([record()]), 1)
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='source'):
        ingest_sources(scope, (path,), tmp_path/'journal.sqlite', pin(),
            expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    assert not (tmp_path/'journal.sqlite').exists()


def test_runtime_pin_rejects_before_journal_creation(tmp_path):
    path, scope = source(tmp_path, dbn_bytes([record()]), 1)
    with pytest.raises(ValueError, match='runtime'):
        ingest_sources(scope, (path,), tmp_path/'journal.sqlite', replace(pin(), runtime_hash='b'*64),
            expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    assert not (tmp_path/'journal.sqlite').exists()


@pytest.mark.parametrize('payload', [dbn_bytes([record()])[:-1],
    dbn_bytes([record()]) + b'\x01', dbn_bytes([record()], version=2),
    dbn_bytes([record()], schema=dbn.Schema.TRADES)])
def test_truncation_trailing_bytes_and_metadata_disagreement_fail(tmp_path, payload):
    with pytest.raises(ValueError):
        ingest(tmp_path, payload)


def test_compressed_truncation_and_concatenated_frames(tmp_path):
    raw = dbn_bytes([record()])
    compressor = zstandard.ZstdCompressor()
    with pytest.raises(ValueError):
        ingest(tmp_path, compressor.compress(raw)[:-1])
    other = tmp_path/'valid'; other.mkdir()
    result, _ = ingest(other, compressor.compress(raw[:65]) + compressor.compress(raw[65:]))
    assert result.completion.record_count == 1


def test_non_mbo_record_is_never_silently_skipped(tmp_path):
    non_mbo = dbn.SystemMsg(ts_event=1, msg='synthetic')
    with pytest.raises(ValueError, match='MBO'):
        ingest(tmp_path, dbn_bytes([record(), non_mbo]))


@pytest.mark.parametrize('version', [1, 2, 3])
def test_explicit_versions_and_physical_ts_out(tmp_path, version):
    native = record(ts_out=123)
    path, scope = source(tmp_path, dbn_bytes([native], version=version, ts_out=True), 1)
    result = ingest_sources(scope, (path,), tmp_path/'journal.sqlite', pin(version),
        expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    driver = SourceConformanceDriver.restore(scope, tmp_path/'journal.sqlite', result.checkpoint,
        expected_scope_hash=scope.genesis_hash(), expected_state_hash=result.completion.builder_state_hash)
    try:
        raw = list(driver.evidence_stream())[0]['raw_record']
        assert raw['ts_out'] == 123 and raw['dbn_wire_bytes'] == bytes(native)
    finally:
        driver.close()


def test_original_file_changes_cannot_change_verified_snapshot(tmp_path, monkeypatch):
    import mbo_source
    payload = dbn_bytes([record()])
    path, scope = source(tmp_path, payload, 1)
    original = mbo_source._metadata
    def alter_path_after_snapshot(*args):
        path.write_bytes(b'changed after verification')
        return original(*args)
    monkeypatch.setattr(mbo_source, '_metadata', alter_path_after_snapshot)
    result = ingest_sources(scope, (path,), tmp_path/'journal.sqlite', pin(),
        expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    assert result.completion.record_count == 1


def test_compressed_trailing_junk_is_not_ignored(tmp_path):
    payload = zstandard.ZstdCompressor().compress(dbn_bytes([record()])) + b'junk'
    with pytest.raises(ValueError):
        ingest(tmp_path, payload)


def test_multi_member_roster_ingests_in_declared_order(tmp_path):
    payloads = [dbn_bytes([record(1)]), dbn_bytes([record(2)])]
    paths = tuple(tmp_path / f'{i}.dbn' for i in range(2))
    for path, payload in zip(paths, payloads):
        path.write_bytes(payload)
    members = tuple(SourceMember(i, path.name, hashlib.sha256(payload).hexdigest(),
                                 len(payload), 1)
                    for i, (path, payload) in enumerate(zip(paths, payloads)))
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a'*64, members, SUPPORTED_ADAPTER_REVISION)
    result = ingest_sources(scope, paths, tmp_path/'journal.sqlite', pin(),
        expected_scope_hash=scope.genesis_hash(), session_ids=('day1', 'day2'))
    assert result.completion.member_counts == (1, 1)


def test_physically_present_undefined_ts_out_is_preserved(tmp_path):
    ordinary = bytes(record())
    physical = bytes([16]) + ordinary[1:] + (2**64 - 1).to_bytes(8, 'little')
    metadata = dbn_bytes([], ts_out=True)
    result, scope = ingest(tmp_path, metadata + physical)
    driver = SourceConformanceDriver.restore(scope, tmp_path/'journal.sqlite', result.checkpoint,
        expected_scope_hash=scope.genesis_hash(), expected_state_hash=result.completion.builder_state_hash)
    try:
        raw = list(driver.evidence_stream())[0]['raw_record']
        assert raw['ts_out'] == 2**64 - 1
        assert raw['dbn_length'] == 16
        assert raw['dbn_wire_bytes'] == physical
    finally:
        driver.close()


def test_actual_sdk_receive_regression_retains_wire_and_completes_restore(tmp_path):
    records=[record(1,ts_recv=201),record(2,ts_recv=101)]
    result,scope=ingest(tmp_path,dbn_bytes(records),2)
    driver=SourceConformanceDriver.restore(scope,tmp_path/'journal.sqlite',result.checkpoint,
        expected_scope_hash=scope.genesis_hash(),expected_state_hash=result.completion.builder_state_hash)
    try:
        evidence=list(driver.evidence_stream())
        assert [e['raw_record']['dbn_wire_bytes'] for e in evidence]==[bytes(r) for r in records]
        assert [e['raw_record']['ts_recv'] for e in evidence]==[201,101]
        assert evidence[-1]['integrity']['receive_time_regression']==1
        assert driver.complete()==result.completion
    finally:
        driver.close()
