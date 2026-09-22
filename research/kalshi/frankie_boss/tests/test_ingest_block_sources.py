"""The block ingestion loop: one continuous stream across members, the declared session policy, both writers equal."""
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
import zstandard

from test_mbo_source import dbn_bytes, record
from compact_journal import CompactReader
from raw_mbo_source_manifest import manifest_hash

_SPEC = importlib.util.spec_from_file_location(
    'ingest_block_sources', Path(__file__).resolve().parents[1] / 'operations' / 'ingest_block_sources.py')
tool = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(tool)
# The tool binds the PACKAGE modules; the scope and pin it checks by isinstance must come from the same classes.
block_source_scope = tool.block_source_scope


def pin():
    return tool.mbo_source.MboSourcePin(3, tool.mbo_source.runtime_hash())

DAY = 1633305600 * 10**9                     # 2021-10-04 00:00:00Z in ns
HOUR = 3600 * 10**9


def _member_file(tmp_path, day, records):
    payload = zstandard.ZstdCompressor().compress(dbn_bytes(records))
    name = f'glbx-mdp3-{day}.mbo.dbn.zst'
    (tmp_path / name).write_bytes(payload)
    return dict(member_key=name, sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload), mbo_records=len(records))


def _block(tmp_path):
    # Two UTC day files; every record is F_LAST (flags=128) so every seam closes a group. Timestamps
    # straddle the 21:00Z halt on the first day: records before it are that day's session, after it
    # the next day's, under the trading-day policy.
    first = [record(1, ts_recv=DAY + 2 * HOUR), record(2, ts_recv=DAY + 20 * HOUR), record(3, ts_recv=DAY + 21 * HOUR),
             record(4, ts_recv=DAY + 23 * HOUR)]
    second = [record(5, ts_recv=DAY + 26 * HOUR), record(6, ts_recv=DAY + 45 * HOUR)]
    sources = [dict(member_index=0, **_member_file(tmp_path, '20211004', first)),
               dict(member_index=1, **_member_file(tmp_path, '20211005', second))]
    body = dict(schema='BOSS_BLOCK_SOURCE_MANIFEST_V1', source_kind='NATIVE_DBN_MBO', role='TEST', causal_clock='ts_recv_ns',
                sampled=False, canonical_source_rewritten=False, member_seams_close_groups=True, halt_boundaries_close_groups=True,
                block='test', bucket='none', prefix='none', halt_utc_hour=21, sources=sources, sessions=[],
                total_mbo_records=6, ingested=False, scheduled=False, prefixes_built=False, model_calls=0)
    body['manifest_hash'] = manifest_hash(body)
    return body


def _run(tmp_path, manifest, *, policy, writer, out, canary=None):
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    name, session = tool.session_policy(policy, halt_utc_hour=manifest['halt_utc_hour'])
    takes = tool.partial_takes(manifest, policy_name=name)          # as main() does: the manifest's partial members
    paths = tuple(tmp_path / m.member_key for m in scope.members)
    return scope, tool.ingest(scope, paths, expected_scope_hash=scope.genesis_hash(), pin=pin(), session=session,
                              source_object='member_key', journal_path=tmp_path / out, writer=writer,
                              canary_records=canary, block_bytes=4096, takes=takes)


def test_session_policies_name_the_trading_day_and_the_member_file():
    _, trading = tool.session_policy('cme_trading_day', halt_utc_hour=21)
    _, per_file = tool.session_policy('per_member_file', halt_utc_hour=21)
    _, constant = tool.session_policy('constant:supplied-source', halt_utc_hour=21)
    member = type('M', (), {'member_key': 'glbx-mdp3-20211004.mbo.dbn.zst'})()
    assert trading(member, dict(ts_recv=DAY + 20 * HOUR)) == '20211004'
    assert trading(member, dict(ts_recv=DAY + 21 * HOUR)) == '20211005'      # at the halt: next trading day
    assert trading(member, dict(ts_recv=DAY + 23 * HOUR)) == '20211005'      # the 22:00Z reopen is the next day's evening
    assert per_file(member, dict(ts_recv=DAY + 23 * HOUR)) == '20211004'
    FRIDAY = DAY + 4 * 24 * HOUR                                             # 2021-10-08 00:00Z
    assert trading(member, dict(ts_recv=FRIDAY + 20 * HOUR)) == '20211008'  # Friday before the halt
    assert trading(member, dict(ts_recv=FRIDAY + 22 * HOUR)) == '20211011'  # after Friday's halt: Monday
    assert trading(member, dict(ts_recv=FRIDAY + 30 * HOUR)) == '20211011'  # Saturday: closed, Monday
    assert trading(member, dict(ts_recv=FRIDAY + 60 * HOUR)) == '20211011'  # Sunday 12:00Z, pre-open: Monday
    assert trading(member, dict(ts_recv=FRIDAY + 70 * HOUR)) == '20211011'  # Sunday 22:00Z reopen: Monday
    assert trading(member, dict(ts_recv=DAY - 2 * HOUR)) == '20211004'      # the block's own Sunday reopen
    assert constant(member, dict(ts_recv=0)) == 'supplied-source'
    with pytest.raises(ValueError):
        tool.session_policy('per_record', halt_utc_hour=21)


def test_block_ingests_as_one_stream_and_both_writers_agree(tmp_path):
    manifest = _block(tmp_path)
    scope, compact = _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='journal.compact.sqlite')
    _, raw = _run(tmp_path, manifest, policy='cme_trading_day', writer='raw', out='source.sqlite')
    assert compact['kind'] == raw['kind'] == 'complete'
    assert compact['completion'] == raw['completion'] and compact['state']['state_hash'] == raw['state']['state_hash']
    assert compact['completion']['record_count'] == 6 and tuple(compact['completion']['member_counts']) == (4, 2)
    assert compact['completion']['journal_count'] == 12
    # the stream crossed the member seam without a break: cursors 0..5, one chain
    assert [s['session_id'] for s in compact['sessions']] == ['20211004', '20211005', '20211006']
    assert [s['first_cursor'] for s in compact['sessions']] == [0, 2, 5]
    assert tool.compare_raw_and_compact(tmp_path / 'source.sqlite', tmp_path / 'journal.compact.sqlite',
                                        expected_count=12, expected_head_hash=raw['completion']['journal_hash']) == 12
    with CompactReader(tmp_path / 'journal.compact.sqlite', expected_count=12,
                       expected_head_hash=raw['completion']['journal_hash']) as reader:
        entries = list(reader.entries())
    assert [e['payload']['session_id'] for e in entries if e['kind'] == 'INPUT'] == \
        ['20211004', '20211004', '20211005', '20211005', '20211005', '20211006']
    assert all(e['payload']['source_dbn_object'].startswith('glbx-mdp3-') for e in entries if e['kind'] == 'INPUT')


def test_per_member_file_policy_resets_at_the_file_seam_only(tmp_path):
    manifest = _block(tmp_path)
    _, result = _run(tmp_path, manifest, policy='per_member_file', writer='compact', out='journal.compact.sqlite')
    assert [(s['session_id'], s['first_cursor']) for s in result['sessions']] == [('20211004', 0), ('20211005', 4)]


def test_canary_stops_early_without_a_completion_claim(tmp_path):
    manifest = _block(tmp_path)
    _, result = _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='canary.compact.sqlite', canary=3)
    assert result['kind'] == 'canary' and result['records'] == 3 and result['completion_claimed'] is False
    assert result['journal_count'] == 6 and result['total_records'] == 6
    assert result['extrapolated_hours_for_total'] >= 0
    with sqlite3.connect(tmp_path / 'canary.compact.sqlite') as db:
        assert db.execute('SELECT count(*) FROM seal').fetchone()[0] == 0       # never sealed, never claimed


def _monday_manifest(tmp_path, take, rows=None, partition=None):
    # ONE partition (the 20211004 UTC file: two records before the 21:00Z halt, two after) declared as a PARTIAL member:
    # the Monday trading day takes `take` records of it; the manifest says so in partial_members (Greg, 2026-09-22:
    # Monday by itself; the trading day, not the partition, is the unit). `partition` overrides the declared partition
    # count (a manifest whose declaration disagrees with the file it names).
    rows = rows or [record(1, ts_recv=DAY + 2 * HOUR), record(2, ts_recv=DAY + 20 * HOUR), record(3, ts_recv=DAY + 21 * HOUR),
                    record(4, ts_recv=DAY + 23 * HOUR)]
    member = _member_file(tmp_path, '20211004', rows)
    partition = partition or member['mbo_records']; member['mbo_records'] = take
    body = dict(schema='BOSS_BLOCK_SOURCE_MANIFEST_V1', source_kind='NATIVE_DBN_MBO', role='TEST', causal_clock='ts_recv_ns',
                sampled=False, canonical_source_rewritten=False, member_seams_close_groups=True, halt_boundaries_close_groups=True,
                block='20211004', trading_day='20211004', bucket='none', prefix='none', halt_utc_hour=21,
                sources=[dict(member_index=0, **member)], sessions=[], total_mbo_records=take,
                partial_members=[dict(member_key=member['member_key'], partition_mbo_records=partition, take=take,
                                      reason='records before the 21:00Z halt belong to this trading day; the rest are the next day')],
                ingested=False, scheduled=False, prefixes_built=False, model_calls=0)
    body['manifest_hash'] = manifest_hash(body)
    return body


def test_a_partial_member_take_ends_the_trading_day_at_the_halt_and_completes(tmp_path):
    manifest = _monday_manifest(tmp_path, take=2)
    scope, result = _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='monday.compact.sqlite')
    assert result['kind'] == 'complete' and result['records'] == 2 and result['completion']['record_count'] == 2
    assert [s['session_id'] for s in result['sessions']] == ['20211004']
    assert result['partial_members'] == [dict(member_key=manifest['sources'][0]['member_key'], take=2, declared_partition_mbo_records=4,
                                              next_session_id='20211005', boundary='trading_day')]   # declared: the remainder is never counted


def test_a_take_that_reaches_the_end_of_its_partition_is_refused_not_receipted_as_a_boundary(tmp_path):
    # the ship review 2026-09-22 (chat 9): the manifest declares take < partition count, so a file that ENDS at the take
    # contradicts the declaration; the boundary cannot be verified on a record that does not exist
    rows = [record(1, ts_recv=DAY + 2 * HOUR), record(2, ts_recv=DAY + 20 * HOUR)]
    manifest = _monday_manifest(tmp_path, take=2, rows=rows, partition=3)
    with pytest.raises(ValueError, match='ends at its take'):
        _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='eof.compact.sqlite')


def test_a_canary_that_ends_exactly_at_the_take_claims_nothing(tmp_path):
    # the ship review 2026-09-22 (chat 9): the take's break came before the canary stop, so a canary of exactly the take on
    # the last member ran complete() and wrote an ingestion receipt inside a canary directory
    manifest = _monday_manifest(tmp_path, take=2)
    _, result = _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='canary-take.compact.sqlite', canary=2)
    assert result['kind'] == 'canary' and result['records'] == 2 and result['completion_claimed'] is False
    assert result['partial_members'] == []                      # a canary verifies no boundary and claims no take
    assert not (tmp_path / 'canary-take.compact.sqlite.completion.json').exists()


def test_a_partial_take_that_does_not_end_at_a_trading_day_boundary_is_refused(tmp_path):
    manifest = _monday_manifest(tmp_path, take=3)          # record 3 (21:00Z) is already the next day; record 4 is the same day as 3
    with pytest.raises(ValueError, match='does not end at a trading-day boundary'):
        _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='bad.compact.sqlite')


def test_a_partial_member_must_be_the_last_member_and_there_is_one(tmp_path):
    # the ship review 2026-09-22 (chat 9): after a take the stream ENDS (the trading day is the unit); a later member would be
    # ingested whole after it and completion claimed for a container holding another day's records. Refused at the
    # manifest (partial_takes), before any record is decoded.
    first = [record(1, ts_recv=DAY + 2 * HOUR), record(2, ts_recv=DAY + 20 * HOUR), record(3, ts_recv=DAY + 21 * HOUR)]
    second = [record(4, ts_recv=DAY + 26 * HOUR)]
    partial = _member_file(tmp_path, '20211004', first); partial['mbo_records'] = 2
    later = _member_file(tmp_path, '20211005', second)
    body = dict(schema='BOSS_BLOCK_SOURCE_MANIFEST_V1', source_kind='NATIVE_DBN_MBO', role='TEST', causal_clock='ts_recv_ns',
                sampled=False, canonical_source_rewritten=False, member_seams_close_groups=True, halt_boundaries_close_groups=True,
                block='20211004', bucket='none', prefix='none', halt_utc_hour=21,
                sources=[dict(member_index=0, **partial), dict(member_index=1, **later)], sessions=[], total_mbo_records=3,
                partial_members=[dict(member_key=partial['member_key'], partition_mbo_records=3, take=2, reason='test')],
                ingested=False, scheduled=False, prefixes_built=False, model_calls=0)
    body['manifest_hash'] = manifest_hash(body)
    with pytest.raises(ValueError, match='last member'):
        _run(tmp_path, body, policy='cme_trading_day', writer='compact', out='not-last.compact.sqlite')
    two = _monday_manifest(tmp_path, take=2)
    two['partial_members'].append(dict(two['partial_members'][0]))
    two['manifest_hash'] = manifest_hash(two)
    with pytest.raises(ValueError, match='one partial member'):
        tool.partial_takes(two, policy_name='cme_trading_day')


def test_a_partial_member_needs_the_trading_day_policy(tmp_path):
    manifest = _monday_manifest(tmp_path, take=2)
    with pytest.raises(ValueError, match='partial members need the cme_trading_day policy'):
        _run(tmp_path, manifest, policy='per_member_file', writer='compact', out='policy.compact.sqlite')


def test_profile_files_a_report_and_leaves_the_result_unchanged(tmp_path, capsys):
    # Greg, 2026-09-22: measure where the parent's time goes before optimising; the profile is a report beside the run
    calls = []
    result = tool.profiled(lambda: calls.append(1) or dict(kind='canary'), tmp_path / 'profile.txt')
    assert result == dict(kind='canary') and calls == [1]
    report = (tmp_path / 'profile.txt').read_text()
    assert report.startswith('### top 40 by tottime') and '### top 40 by cumulative' in report
    assert '### profile (' in capsys.readouterr().out


def test_the_ingest_packs_boxes_to_the_standard_derived_from_the_declared_records(tmp_path):
    # the box standard (TARGET_BOXES 1189) derived from 2 x the declared records (INPUT + APPLIED per record), clamped by the
    # format: on this six-record block one entry per box; the receipt says so
    from journal_stack_execution import partition_entries_for
    manifest = _block(tmp_path)
    _, result = _run(tmp_path, manifest, policy='cme_trading_day', writer='compact', out='packed.compact.sqlite')
    assert result['packing'] == dict(block_rows=partition_entries_for(12), block_bytes=4096,     # 4096 = this helper's bound
                                     standard='journal_stack_execution.TARGET_BOXES 1189: rows per box = partition_entries_for(2 x declared records), bytes per box = the format ceiling')
    assert tool.ingest.__kwdefaults__['block_bytes'] == 16 * 1024 * 1024 and tool.ingest.__kwdefaults__['block_rows'] is None
    with sqlite3.connect(tmp_path / 'packed.compact.sqlite') as db:
        assert [r[0] for r in db.execute('SELECT count FROM blocks ORDER BY start')] == [1] * 12
