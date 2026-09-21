"""BR-2/BR-3 (SPEC_CYCLE0_BEDROCK_20260921.md box-bedrock-derive): the box derives cycle 0's bedrock layers by running
the PINNED producers' own traversal (native_replay_driver.NativeReplayDriver at 2ebb8ce8) on the cycle's journal-shaped
INPUT observations and projecting its exact ledgers by the producers' own crosswalk. No arithmetic written here; the
producers are reached through the in-repo worktree (tests/_producers.py). Torch is never imported on this path."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _producers as P  # noqa: E402

BOX = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box'


def load(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


B = load('frankie_box_bedrock')
NS = 1_000_000_000
F_LAST = 128
DAY = '20211003'
BASE_NS = 1633298400 * NS + 300_000_000        # 2021-10-03 22:00:00.3 UTC, the first cycle-0 row's receive second
# Journal-shaped INPUT observation: the wire fields the box's _find_observation returns (record_recipe layout of the
# C15 prefix snapshot; dbn_wire_bytes is bytes and is dropped by the session before the record reaches a producer).
WIRE_KEYS = ('ts_event', 'ts_recv', 'rtype', 'publisher_id', 'instrument_id', 'price', 'size', 'channel_id', 'order_id',
             'flags', 'ts_in_delta', 'sequence', 'action', 'side', 'dbn_length', 'ts_out', 'dbn_extraction_hash')


def observation(seq, event_ns, order_id, action='A', side='B', last=True, price=3_500_000_000, size=5):
    return dict(ts_event=event_ns, ts_recv=event_ns + 150_000, rtype=160, publisher_id=1, instrument_id=42, price=price,
                size=size, channel_id=0, order_id=order_id, flags=F_LAST if last else 0, ts_in_delta=0, sequence=seq,
                action=action, side=side, dbn_length=56, ts_out=0, dbn_extraction_hash='e' * 64)


GROUPS = (
    (('A', 'B', 701, False), ('A', 'A', 702, False), ('C', 'A', 702, False), ('A', 'B', 703, True)),
    (('A', 'B', 704, False), ('M', 'B', 704, False), ('T', 'A', 705, False), ('F', 'B', 704, True)),
    (('A', 'A', 706, False), ('C', 'B', 701, False), ('A', 'B', 707, True)),
)


def stream():
    records, seq = [], 0
    for group_index, group in enumerate(GROUPS):
        for offset, (action, side, order_id, last) in enumerate(group):
            records.append(observation(seq, BASE_NS + (group_index * 4 + offset) * NS, order_id, action, side, last,
                                       price=3_500_000_000 + (10_000_000 if side == 'A' else 0)))
            seq += 1
    assert all(set(r) == set(WIRE_KEYS) for r in records)
    return records


def container(tmp_path):
    prefix = tmp_path / 'prefix-00.sqlite'
    prefix.write_bytes(b'not read by the driver; the container is the source object the records name')
    return dict(path=str(prefix), sha256='c' * 64, count=len(stream()) * 2, layout='raw')


# ---- NeverInvoke -------------------------------------------------------------------------------------------------

def test_never_invoke_never_fires_for_the_cadence_protocol_arguments():
    policy = B.NeverInvoke()
    assert policy.should_invoke(group_index=7, recv_ns=BASE_NS, mark=object(), groups_since_last=3,
                                candidate_events=dict(recognitions_at_this_cutoff=1, change_points_at_this_cutoff=2)) is False
    assert policy.should_invoke() is False
    assert B.NeverInvoke.__name__ == 'NeverInvoke'


# ---- driver_records ----------------------------------------------------------------------------------------------

def test_driver_records_stamp_the_verified_container_as_the_source_object_and_leave_the_input_untouched(tmp_path):
    records = stream()
    before = json.dumps(records, sort_keys=True)
    stamped = B.driver_records(records, container(tmp_path), DAY)
    assert json.dumps(records, sort_keys=True) == before
    assert len(stamped) == len(records)
    for original, record in zip(records, stamped):
        assert record['source_dbn_object'] == 'journal:' + DAY + ':' + container(tmp_path)['path'] and record['source_dbn_sha256'] == 'c' * 64
        assert record['raw_symbol'] is None
        assert {k: v for k, v in record.items() if k not in ('source_dbn_object', 'source_dbn_sha256', 'raw_symbol')} == original
    symbol = B.driver_records([dict(records[0], raw_symbol='NGX1')], container(tmp_path), DAY)[0]
    assert symbol['raw_symbol'] == 'NGX1'
    symbol = B.driver_records([dict(records[0], symbol='NGX1')], container(tmp_path), DAY)[0]
    assert symbol['raw_symbol'] == 'NGX1'


def test_driver_records_refuse_a_container_without_a_path_or_a_sha256_and_a_malformed_day(tmp_path):
    for bad in (dict(container(tmp_path), path=''), dict(container(tmp_path), sha256=None), {}):
        with pytest.raises(ValueError, match='source object'):
            B.driver_records(stream(), bad, DAY)
    for day in ('', None, '2021-10-03', '19991003', 'day'):
        with pytest.raises(ValueError, match='source day must be 20YYMMDD'):
            B.driver_records(stream(), container(tmp_path), day)


def test_the_source_object_leads_with_the_day_so_the_drivers_own_day_rule_reads_it(tmp_path):
    """native_replay_driver._source_day takes the first 20YYMMDD in the object name; a container path that carries a
    date of its own (a records directory) must not win over the session day."""
    dated = dict(container(tmp_path), path='/opt/frankie-box/records/20260921/prefix-00.sqlite')
    obj, _ = B.source_object(dated, DAY)
    import re
    assert re.search(r'(20\d{6})', obj).group(1) == DAY


# ---- run: the pinned driver end to end ----------------------------------------------------------------------------

def test_run_traverses_a_journal_shaped_stream_through_the_pinned_driver_reconciles_and_files_the_ledgers(tmp_path):
    producers = P.require_producers()
    out = tmp_path / 'bedrock'
    receipt = B.run(stream(), container(tmp_path), out, producers, cycle='00', code_commit=P.PIN, day=DAY)
    assert receipt['schema'] == 'FRANKIE_BOX_BEDROCK_RUN_RECEIPT_V1'
    assert receipt['cadence_policy'] == 'NeverInvoke' and receipt['producers_commit'] == P.PIN
    assert receipt['identity']['arm'] == 'A_MEMORY' and receipt['identity']['run_id'] == 'frankie-box-cycle-00'
    assert receipt['identity']['total_mbo_records'] == len(stream()) and receipt['identity']['source_manifest_hash'] == 'c' * 64
    assert receipt['identity']['knowledge_manifest_hash'] == json.loads((producers / B.KNOWLEDGE_MANIFEST_PATH).read_bytes())['manifest_hash']
    assert receipt['candidate_warmup_seconds'] == 900 and receipt['candidate_min_observations'] == 600   # the driver's own constants
    assert receipt['span_seconds'] == pytest.approx(10.0)
    assert receipt['records'] == len(stream()) and receipt['groups'] == len(GROUPS)
    for name in ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl'):
        assert (out / 'ledgers' / name).is_file(), name
        assert receipt['ledgers'][name]['sha256'] and receipt['ledgers'][name]['rows'] >= 0
    assert receipt['ledgers']['exact_member_rows.jsonl']['rows'] == len(GROUPS)
    assert receipt['ledgers']['exact_lifecycle_rows.jsonl']['rows'] > 0
    for name, v in receipt['reconciliation'].items():   # the sink's own reconcile: counted, offered and read back from disk agree
        assert v['rows_read_back_from_disk'] == v['reconciled_against_counter'] == v['row_count'], (name, v)
    result = json.loads((out / 'result.json').read_bytes())
    assert result['traversal']['groups_seen'] == len(GROUPS) and result['traversal']['records_seen'] == len(stream())
    assert result['traversal']['invocation_cutoff_count'] == 0            # NeverInvoke: the BOSS is never asked inside the traversal
    assert result['traversal']['sections_fed']['candidate_unit_events'] == 0   # a 10-second slice never reaches the 900 s warmup
    assert receipt['sections_fed'] == result['traversal']['sections_fed']
    assert 'torch' not in sys.modules
    member = [json.loads(line) for line in (out / 'ledgers' / 'exact_member_rows.jsonl').read_text().splitlines()]
    assert [row['group_index'] for row in member] == list(range(len(GROUPS)))
    assert all('clocks' in row and 'structure' in row and 'book_regime' in row for row in member)


def test_run_refuses_an_empty_stream(tmp_path):
    with pytest.raises(ValueError, match='no INPUT records'):
        B.run([], container(tmp_path), tmp_path / 'bedrock', P.require_producers(), cycle='00', code_commit=P.PIN, day=DAY)


def test_run_moves_an_earlier_bedrock_aside_with_a_receipt_never_deleting_it(tmp_path):
    producers = P.require_producers()
    out = tmp_path / 'bedrock'
    first = B.run(stream(), container(tmp_path), out, producers, cycle='00', code_commit=P.PIN, day=DAY)
    second = B.run(stream(), container(tmp_path), out, producers, cycle='00', code_commit=P.PIN, day=DAY)
    moved = [p for p in tmp_path.iterdir() if p.name.startswith('bedrock-superseded-')]
    assert len(moved) == 1 and (moved[0] / 'ledgers' / 'exact_member_rows.jsonl').is_file()
    receipts = list(tmp_path.glob('bedrock-supersede-*.json'))
    assert len(receipts) == 1 and json.loads(receipts[0].read_bytes())['moved_to'] == str(moved[0])
    assert second['ledgers'] == first['ledgers'] and second['superseded'] == str(moved[0])
