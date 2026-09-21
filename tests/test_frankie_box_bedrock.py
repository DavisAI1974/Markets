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


# ---- BR-3: project and status_of ----------------------------------------------------------------------------------

BEDROCK_LAYERS = (
    'derived_roll20_and_dipole_state', 'derived_d_family_geometry', 'derived_open_world_predecessor_state', 'derived_ancestry_gaps',
    'derived_unresolved_age_chain_trajectory', 'derived_price_flow_book_paths', 'derived_v4_mechanics_fifo_features',
    'derived_feature_availability_timestamps',
    'prebirth_predecessor_at_risk_state', 'prebirth_unresolved_chain_extension_state', 'prebirth_ancestry_successor_opportunity',
    'prebirth_stopped_chain_false_context_controls', 'prebirth_negative_opportunity_cases',
    'clock_event_time', 'clock_receive_time', 'clock_event_known_by', 'clock_feature_availability',
    'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time')


def synthetic_ledgers(tmp_path):
    ledgers = tmp_path / 'ledgers'
    ledgers.mkdir()
    members = []
    for g in range(3):
        recv = BASE_NS + g * 4 * NS
        members.append(dict(
            group_index=g, ts_recv_ns=recv, ts_event_ns=recv - 150_000, instrument_id=42, decision_basis='REPLAY_EARLIEST_LAWFUL_AVAILABILITY',
            f_last_to_decision_delay_ns=0, causal_availability_clock='ts_recv_ns',
            clocks=dict(first_component_ts_event_ns=recv - 3 * NS, first_component_ts_recv_ns=recv - 3 * NS + 150_000, f_last_ts_recv_ns=recv,
                        first_lawful_availability_ns=recv, decision_ts_recv_ns=recv),
            structure=dict(candidate_family_id='fam%d' % g, side_string='BAB', discovery_status='OPEN_WORLD_CANDIDATE', carried_native_family=None,
                           matches_carried_native_family=False, mirror=dict(orientation='SAME', mirror_pair_key='k%d' % g)),
            book_regime=dict(best_bid=3_500_000_000, total_depth=10 + g, order_count=2, recv_ns=recv),
            book_full=dict(mid=3_505_000_000.0, bid_levels_full=[dict(price=3_500_000_000, fifo_queue=[dict(order_id=701, size=5), dict(order_id=703, size=5)]),
                                                                 dict(price=3_490_000_000, fifo_queue=[dict(order_id=702, size=1)])]),
            activity_since=dict(session_open=dict(top_level_qty_by_action=dict(A=5, C=0), action_side_count=dict(A_B=1)),
                                last_trade=dict(top_level_qty_by_action=dict(A=1), action_side_count=dict(T_A=1))),
            capture_observations={}))
    (ledgers / 'exact_member_rows.jsonl').write_text(''.join(json.dumps(m, sort_keys=True) + '\n' for m in members))
    life = [dict(emitting_section='flow_substrate', emitted_on='SECOND_COMPLETED', second=1633298401 + i, roll20_value=0.5, polarity='BUY') for i in range(4)]
    life += [dict(emitting_section='lineage', emitted_on='STAGE_CLOSED', node_id=700 + i, parent_id=None if i == 0 else 700, depth=i, status='OPEN' if i == 2 else 'CLOSED') for i in range(3)]
    life += [dict(emitting_section='recurrence', emitted_on='STREAM_END', gap_count=2, gaps=[1, 2], run_count=1, runs=[])]
    life += [dict(emitting_section='ladder', emitted_on='GROUP_CLOSED', best_price_moved=False, side='B') for _ in range(2)]
    life += [dict(emitting_section='queue', emitted_on='TERMINAL', order_id=702, lifetime_ns=2 * NS) for _ in range(2)]
    life += [dict(emitting_section='detector_coverage', emitted_on='STREAM_END', seconds_fed_to_section=4, section_totals=dict(rejected=4))]
    life += [dict(emitting_section='replenishment', emitted_on='HORIZON_MATURED', order_id=701)]
    (ledgers / 'exact_lifecycle_rows.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in life))
    (ledgers / 'legacy_observable_rows.jsonl').write_text('')
    return ledgers


RECEIPT = dict(span_seconds=13.0, candidate_warmup_seconds=900, candidate_min_observations=600)


def test_status_of_never_files_an_empty_derived():
    assert B.status_of(3, False, 13.0, 900, 600) == ('derived', None)
    assert B.status_of(3, True, 13.0, 900, 600) == ('derived', None)
    status, reason = B.status_of(0, True, 13.04, 900, 600)
    assert status == 'could_not' and '900 s' in reason and '600 observations' in reason and '13.0 s' in reason
    status, reason = B.status_of(0, False, 13.0, 900, 600)
    assert status == 'could_not' and 'emitted no rows' in reason


def test_select_path_walks_dotted_wildcard_and_list_paths():
    member = dict(clocks=dict(a=1), activity_since=dict(x=dict(k=dict(A=5)), y=dict(k=dict(A=6))),
                  book_full=dict(levels=[dict(q=[dict(o=1), dict(o=2)]), dict(q=[dict(o=3)])]), capture={})
    assert B.select_path(member, 'clocks.a') == (True, 1)
    assert B.select_path(member, 'clocks.missing') == (False, None)
    assert B.select_path(member, 'activity_since.*.k') == (True, dict(x=dict(A=5), y=dict(A=6)))
    assert B.select_path(member, 'book_full.levels[].q[]') == (True, [[dict(o=1), dict(o=2)], [dict(o=3)]])
    assert B.select_path(member, 'book_full.levels[].q[].o') == (True, [[1, 2], [3]])
    assert B.select_path(member, 'capture') == (True, {})
    assert B.select_path(member, 'nothing.here') == (False, None)


def test_crosswalk_records_come_from_the_pinned_checkout_and_refuse_an_unknown_layer():
    producers = P.require_producers()
    records = B.crosswalk_records(producers, BEDROCK_LAYERS)
    assert set(records) == set(BEDROCK_LAYERS)
    assert records['derived_d_family_geometry']['module'] == 'a_memory_member_first_recalculation_20260828'
    assert records['clock_lock_time']['kind'] == 'NO_PRODUCER_FOUND'
    with pytest.raises(ValueError, match='ghost_layer is not in the pinned crosswalk'):
        B.crosswalk_records(producers, ('ghost_layer',))


def test_project_writes_one_honest_file_per_layer_from_synthetic_ledgers(tmp_path):
    producers = P.require_producers()
    ledgers = synthetic_ledgers(tmp_path)
    out = tmp_path / 'derived'
    crosswalk = B.crosswalk_records(producers, BEDROCK_LAYERS)
    layers = B.project(RECEIPT, ledgers, BEDROCK_LAYERS, crosswalk, out)
    assert set(layers) == set(BEDROCK_LAYERS) and all((out / f'{name}.json').is_file() for name in BEDROCK_LAYERS)
    for name in BEDROCK_LAYERS:
        entry = layers[name]
        file = json.loads((out / f'{name}.json').read_bytes())
        assert entry['status'] == file['status'] and entry['sha256'] and entry['path'] == str(out / f'{name}.json')
        assert file['count'] == len(file['member_rows']) + len(file['lifecycle_rows']) == entry['count']
        assert 'carrier' in file and 'lifecycle_sections' in file and 'member_paths' in file and 'section_counts' in file
        assert (file['status'] == 'derived') == (file['count'] > 0), name
        assert (file['reason'] is None) == (file['status'] == 'derived'), name
        assert file['crosswalk_commit'] == P.PIN
    geometry = json.loads((out / 'derived_d_family_geometry.json').read_bytes())
    assert geometry['status'] == 'derived' and geometry['producer'] == 'a_memory_member_first_recalculation_20260828.describe_structure'
    assert len(geometry['member_rows']) == 3 and len(geometry['lifecycle_rows']) == 3
    assert geometry['member_rows'][1] == dict(group_index=1, ts_recv_ns=BASE_NS + 4 * NS, f_last_ts_recv_ns=BASE_NS + 4 * NS,
                                              **{'structure.candidate_family_id': 'fam1', 'structure.side_string': 'BAB',
                                                 'structure.mirror.orientation': 'SAME', 'structure.mirror.mirror_pair_key': 'k1'})
    assert all(r['emitting_section'] == 'lineage' for r in geometry['lifecycle_rows']) and geometry['section_counts'] == dict(lineage=3)
    at_risk = json.loads((out / 'prebirth_predecessor_at_risk_state.json').read_bytes())
    assert at_risk['status'] == 'could_not' and '900 s' in at_risk['reason'] and '13.0 s' in at_risk['reason']
    assert at_risk['section_counts'] == dict(episode=0, candidate=0) and at_risk['count'] == 0
    lock = json.loads((out / 'clock_lock_time.json').read_bytes())
    assert lock['status'] == 'could_not' and lock['reason'].startswith('NO_PRODUCER_FOUND') and lock['producer'] is None
    assert 'output_first_locks_and_no_locks' in lock['reason']
    evaluation = json.loads((out / 'clock_model_evaluation.json').read_bytes())
    assert evaluation['status'] == 'derived' and 'CONVENTION' in evaluation['notes']
    assert evaluation['member_rows'][0]['decision_basis'] == 'REPLAY_EARLIEST_LAWFUL_AVAILABILITY'
    dipole = json.loads((out / 'derived_roll20_and_dipole_state.json').read_bytes())
    assert dipole['status'] == 'derived' and dipole['section_counts'] == dict(flow_substrate=4, episode=0)
    assert len(dipole['partial']) == 1 and dipole['partial'][0]['section'] == 'episode' and '900 s' in dipole['partial'][0]['reason']
    fifo = json.loads((out / 'derived_v4_mechanics_fifo_features.json').read_bytes())
    row = fifo['member_rows'][0]
    assert row['activity_since.*.top_level_qty_by_action'] == dict(session_open=dict(A=5, C=0), last_trade=dict(A=1))
    assert row['book_full.bid_levels_full[].fifo_queue[]'] == [[dict(order_id=701, size=5), dict(order_id=703, size=5)], [dict(order_id=702, size=1)]]
    assert row['capture_observations'] == {} and fifo['section_counts'] == dict(queue=2)
    gaps = json.loads((out / 'derived_ancestry_gaps.json').read_bytes())
    assert gaps['section_counts'] == dict(lineage=3, recurrence=1) and gaps['member_rows'] == []
    known = json.loads((out / 'clock_event_known_by.json').read_bytes())
    assert known['member_rows'][2]['clocks.first_lawful_availability_ns'] == BASE_NS + 8 * NS
    assert known['absent_paths'] == {}


def test_project_records_a_member_path_the_rows_do_not_carry(tmp_path):
    producers = P.require_producers()
    ledgers = synthetic_ledgers(tmp_path)
    crosswalk = B.crosswalk_records(producers, ('clock_receive_time',))
    crosswalk = {k: dict(v, member_paths=list(v['member_paths']) + ['clocks.nowhere']) for k, v in crosswalk.items()}
    layers = B.project(RECEIPT, ledgers, ('clock_receive_time',), crosswalk, tmp_path / 'derived')
    file = json.loads(Path(layers['clock_receive_time']['path']).read_bytes())
    assert file['absent_paths'] == {'clocks.nowhere': 3} and 'clocks.nowhere' not in file['member_rows'][0]


def test_run_then_project_on_the_fixture_stream_files_twenty_layers_with_the_measured_verdict(tmp_path):
    producers = P.require_producers()
    out = tmp_path / 'bedrock'
    receipt = B.run(stream(), container(tmp_path), out, producers, cycle='00', code_commit=P.PIN, day=DAY)
    crosswalk = B.crosswalk_records(producers, BEDROCK_LAYERS)
    layers = B.project(receipt, out / 'ledgers', BEDROCK_LAYERS, crosswalk, tmp_path / 'derived')
    statuses = {name: entry['status'] for name, entry in layers.items()}
    assert statuses['clock_lock_time'] == 'could_not'
    for name in ('prebirth_predecessor_at_risk_state', 'clock_prospective_discovery_confirmation'):
        assert statuses[name] == 'could_not' and '900 s' in layers[name]['reason'] and '10.0 s' in layers[name]['reason'], name
    for name in ('clock_event_time', 'clock_receive_time', 'derived_d_family_geometry', 'derived_price_flow_book_paths',
                 'derived_v4_mechanics_fifo_features', 'derived_ancestry_gaps', 'prebirth_ancestry_successor_opportunity'):
        assert statuses[name] == 'derived', (name, layers[name]['reason'])
    geometry = json.loads(Path(layers['derived_d_family_geometry']['path']).read_bytes())
    assert [r['group_index'] for r in geometry['member_rows']] == [0, 1, 2]
    assert 'torch' not in sys.modules
