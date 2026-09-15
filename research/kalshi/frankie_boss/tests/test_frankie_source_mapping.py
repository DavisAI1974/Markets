"""Exact physical source/member witnesses; synthetic DBN and real local journals."""
from dataclasses import asdict
import gzip
import hashlib
import json

import pytest

from research.kalshi.frankie_boss import frankie_source_mapping as mapping
from research.kalshi.frankie_boss.causal_prefix import SourceMember, SourceScope, ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from research.kalshi.frankie_boss.mbo_source import MboSourcePin, runtime_hash, ingest_sources
from test_mbo_source import record, dbn_bytes


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inputs(tmp_path, *, legacy=False, compressed=True, damage=None):
    records = [record(1, flags=0), record(2), record(3)]
    raw = dbn_bytes(records)
    source = tmp_path/'source.dbn'
    source.write_bytes(raw)
    member = SourceMember(0, source.name, sha(raw), len(raw), len(records))
    pin = MboSourcePin(3, runtime_hash())
    def action(value):
        if not legacy:
            return {'source_record': {'wire_bytes_hex': bytes(value).hex()}}
        aliases = {'price_raw': 'price', 'ts_event_ns': 'ts_event',
                   'ts_recv_ns': 'ts_recv', 'ts_in_delta_ns': 'ts_in_delta'}
        names = ('publisher_id', 'instrument_id', 'order_id', 'price_raw', 'size', 'flags',
                 'channel_id', 'ts_event_ns', 'ts_recv_ns', 'ts_in_delta_ns', 'sequence')
        return {**{name: int(getattr(value, aliases.get(name, name))) for name in names},
                'action': str(value.action), 'side': str(value.side)}
    groups = [{'raw_actions': [action(r) for r in records[:2]], 'retained_extra': {'unchanged': True}},
              {'raw_actions': [action(records[2])]}]
    if damage == 'reordered': groups[0]['raw_actions'].reverse()
    if damage == 'missing': groups.pop()
    if damage == 'field': groups[0]['raw_actions'][0].pop('channel_id')
    if damage == 'wire': groups[0]['raw_actions'][0]['source_record']['wire_bytes_hex'] = bytes(records[1]).hex()
    plain = b'\n' + b''.join(json.dumps(row).encode()+b'\n' for row in groups)
    ledger = tmp_path/('member.jsonl.gz' if compressed else 'member.jsonl')
    ledger.write_bytes(gzip.compress(plain) if compressed else plain)
    witness = {'bytes': len(plain), 'sha256': sha(plain)}
    return dict(source_path=source, source_member=member, extraction_pin=pin,
                member_ledger_path=ledger, member_ledger_witness=witness,
                output_directory=tmp_path/'mapping'), records


@pytest.mark.parametrize('legacy,compressed', [(False, True), (False, False), (True, True)])
def test_full_byte_mapping_preserves_physical_rows_and_closed_groups(tmp_path, legacy, compressed):
    args, records = inputs(tmp_path, legacy=legacy, compressed=compressed)
    progress = []
    receipt = mapping.build_mapping(**args, event=progress.append)
    rows = [json.loads(row) for row in (args['output_directory']/'index.jsonl').read_bytes().splitlines()]
    assert receipt['record_count'] == 3 and receipt['group_count'] == 2
    assert rows[0]['cursor_start'] == 0 and rows[0]['cursor_end'] == 1
    assert rows[0]['plain_offset'] == 1 and rows[0]['line_number'] == 2
    assert rows[0]['wire_sha256'] == [sha(bytes(r)) for r in records[:2]]
    assert receipt['encodings'] == {('normalized_fields_reencoded' if legacy else 'source_record_wire'): 3}
    assert receipt['member_ledger']['plain'] == args['member_ledger_witness']
    assert receipt['member_ledger']['physical']['sha256'] == sha(args['member_ledger_path'].read_bytes())
    assert progress[-1] == dict(phase='mapping', plain_bytes=args['member_ledger_witness']['bytes'], records=3, groups=2)


@pytest.mark.parametrize('damage', ['reordered', 'missing', 'field', 'wire', 'hash'])
def test_incomplete_or_changed_evidence_never_commits_mapping(tmp_path, damage):
    args, _ = inputs(tmp_path, legacy=damage == 'field', damage=damage)
    if damage == 'hash': args['member_ledger_witness']['sha256'] = 'f'*64
    with pytest.raises(ValueError):
        mapping.build_mapping(**args)
    assert not args['output_directory'].exists()


def test_real_journal_prefix_binding_reuses_index_and_refuses_open_group(tmp_path):
    args, _ = inputs(tmp_path)
    mapping.build_mapping(**args)
    mapping_hash = sha((args['output_directory']/'mapping.json').read_bytes())
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a'*64, (args['source_member'],), SUPPORTED_ADAPTER_REVISION)
    journal_path = tmp_path/'boss.sqlite'
    ingestion = ingest_sources(scope, (args['source_path'],), journal_path, args['extraction_pin'],
        expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    journal = EvidenceJournal(journal_path)
    applied = [row['payload'] for row in journal.entries() if row['kind'] == 'APPLIED']
    checkpoint = {'count': journal.count, 'head_hash': journal.head_hash}
    journal.close()
    # The completed mapping is reusable without opening the original source/large ledger.
    args['source_path'].unlink()
    args['member_ledger_path'].unlink()
    source = dict(prefix_hash=applied[1]['terminal_prefix_hash'], through_cursor=1,
                  as_of=201, source_as_of=200, arm_hash='b'*64)
    bound = mapping.bind_prefix(mapping_directory=args['output_directory'], expected_mapping_sha256=mapping_hash,
        boss_journal_path=journal_path, journal_checkpoint=checkpoint, boss_source=source,
        output_path=tmp_path/'binding.json')
    assert bound['matched_records'] == 2 and bound['matched_groups'] == 1
    assert bound['boss_source'] == source
    for damaged in (dict(source, through_cursor=0), dict(source, prefix_hash='f'*64), dict(source, as_of=100)):
        with pytest.raises(ValueError):
            mapping.bind_prefix(mapping_directory=args['output_directory'], expected_mapping_sha256=mapping_hash,
                boss_journal_path=journal_path, journal_checkpoint=checkpoint, boss_source=damaged,
                output_path=tmp_path/'refused.json')
    assert not (tmp_path/'refused.json').exists()


@pytest.mark.parametrize('damage', ['source_identity', 'wire'])
def test_validly_hashed_journal_still_requires_mapped_source_bytes_and_identity(tmp_path, damage):
    args, _ = inputs(tmp_path)
    mapping.build_mapping(**args)
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a'*64, (args['source_member'],), SUPPORTED_ADAPTER_REVISION)
    original_path = tmp_path/'original.sqlite'
    ingest_sources(scope, (args['source_path'],), original_path, args['extraction_pin'],
        expected_scope_hash=scope.genesis_hash(), session_ids=('synthetic',))
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    original = EvidenceJournal(original_path)
    changed = EvidenceJournal(tmp_path/'changed.sqlite', create=True)
    terminal = None
    for entry in original.entries():
        payload = entry['payload']
        if damage == 'source_identity' and entry['kind'] == 'APPLIED':
            payload['normalized']['source_dbn_sha256'] = 'f'*64
        if damage == 'wire':
            raw = payload['record'] if entry['kind'] == 'INPUT' else payload['raw_record']
            raw['dbn_wire_bytes'] = b'x'*56
        if entry['kind'] == 'APPLIED': terminal = payload
        changed.append(entry['kind'], payload)
    checkpoint = {'count': changed.count, 'head_hash': changed.head_hash}
    original.close()
    changed.close()
    source = dict(prefix_hash=terminal['terminal_prefix_hash'], through_cursor=2,
                  as_of=301, source_as_of=300, arm_hash='b'*64)
    with pytest.raises(ValueError, match='raw bytes|identity'):
        mapping.bind_prefix(mapping_directory=args['output_directory'],
            expected_mapping_sha256=sha((args['output_directory']/'mapping.json').read_bytes()),
            boss_journal_path=tmp_path/'changed.sqlite', journal_checkpoint=checkpoint,
            boss_source=source, output_path=tmp_path/'bad-binding.json')
    assert not (tmp_path/'bad-binding.json').exists()
