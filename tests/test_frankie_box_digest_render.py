"""The dense digest (deploy/aws/box/frankie_box_digest_render.py) is a projection the code proves: every table is
parsed back and compared before it is written. These tests pin each mark of the DIGEST_V3 cell grammar on hand-built
rows shaped like the producers' (book frames, structure groups), and the negative cases: a value that does NOT match
its derivation stays literal, a timestamp that differs from the book table's is not declared cross-derived, and the
two strings the first digest could not render (a tab inside a string, a string starting `J[`) round-trip."""
from __future__ import annotations

import copy
import hashlib
import pytest
import importlib.util
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frankie_box_digest_render', ROOT / 'deploy/aws/box/frankie_box_digest_render.py')
DG = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = DG
spec.loader.exec_module(DG)


def _frame(ts, ev, bid, ask, bd, ad, bo, ao, bl, al, prev):
    book = dict(best_bid=bid, best_ask=ask, spread=None if bid is None or ask is None else ask - bid,
                mid=None if bid is None or ask is None else 0.5 * (bid + ask), depth_imbalance_n=0.125,
                bid_depth_full=bd, ask_depth_full=ad, depth_imbalance_full=float(bd - ad) / float(bd + ad),
                bid_order_count_full=bo, ask_order_count_full=ao, bid_price_level_count_full=bl, ask_price_level_count_full=al)
    row = dict(ts_recv_ns=ts, ts_event_ns=ev)
    row.update({k: book[k] for k in ('best_bid', 'best_ask', 'mid', 'depth_imbalance_n')})
    row.update({k: book[k] for k in DG.BOOK_FIELDS})
    row['transition'] = DG._transition(row, prev)
    return row


def _group(ts, ev, actions, sides, order_ids, prices, filled, cancelled, modified, unresolved):
    both = sorted(set(cancelled) & set(modified))
    sig = dict(fill_id_count=len(filled), cancelled_fill_id_count=len(cancelled), modified_fill_id_count=len(modified),
               same_id_cancel_modify_count=len(both), unresolved_fill_id_count=len(unresolved))
    d = dict(action_string=actions, side_string=sides,
             action_counts={c: actions.count(c) for c in sorted(set(actions))}, side_counts={c: sides.count(c) for c in sorted(set(sides))},
             terminal_action=actions[-1], terminal_side=sides[-1], component_count=len(actions), distinct_price_count=len(set(prices)),
             distinct_order_id_count=len(order_ids), fill_disposition_signature=sig)
    cid = 'ow-' + hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()[:20]
    swap = sides.translate(str.maketrans({'A': 'B', 'B': 'A'})); pair = sorted((sides, swap))
    flat = dict(filled_order_ids=filled, cancelled_fill_order_ids=cancelled, modified_fill_order_ids=modified, same_id_cancel_modify_order_ids=both, unresolved_fill_order_ids=unresolved)
    return dict(ts_recv_ns=ts, ts_event_ns=ev, **d, candidate_family_id=cid, matches_carried_native_family=False, carried_native_family=None,
                discovery_status='OPEN_WORLD_CANDIDATE', price_raw_min=min(prices), price_raw_max=max(prices), price_raw_span=max(prices) - min(prices),
                order_ids=order_ids, fill_disposition=dict({'class': DG._fill_class({'fill_disposition.' + k: v for k, v in flat.items()})}, **flat, signature=dict(sig)),
                mirror=dict(side_string=sides, mirror_side_string=swap, mirror_pair_key='|'.join(pair), orientation='CANONICAL' if sides == pair[0] else 'MIRROR'))


def _tables():
    frames, prev = [], None
    specs = [(1_000_000_000_000, 999_999_950_000, 5.412, 5.413, 100, 120, 10, 12, 8, 9), (1_000_000_400_000, 1_000_000_350_000, 5.412, 5.414, 101, 120, 10, 13, 8, 9),
             (1_000_000_900_000, 1_000_000_880_000, None, None, 99, 118, 9, 13, 8, 9), (1_000_001_000_000, 1_000_000_990_000, 5.411, 5.412, 99, 118, 9, 13, 8, 9)]
    for ts, ev, bid, ask, bd, ad, bo, ao, bl, al in specs:
        row = _frame(ts, ev, bid, ask, bd, ad, bo, ao, bl, al, prev)
        frames.append(row); prev = row
    frames[1]['depth_imbalance_n'] = float('nan')
    groups = [_group(1_000_000_000_000, 999_999_950_000, 'AC', 'AB', [7_000_000_000_001, 7_000_000_000_009], [5_412_000_000_000], [], [], [], []),
              _group(1_000_000_400_000, 1_000_000_350_000, 'FCT', 'BBB', [7_000_000_000_020, 7_000_000_000_031, 7_000_000_000_032], [5_413_000_000_000, 5_412_000_000_000], [7_000_000_000_020], [7_000_000_000_020], [], []),
              _group(1_000_000_900_000, 1_000_000_880_000, 'A', 'N', [], [5_411_000_000_000], [], [], [], []),
              _group(1_000_001_000_000, 1_000_000_990_000, 'FCT', 'BBB', [7_000_000_000_040, 7_000_000_000_041, 7_000_000_000_042], [5_411_000_000_000], [7_000_000_000_040], [], [7_000_000_000_040], [])]
    return {'legacy_book_imbalance': frames, 'legacy_structure_observables': groups}


def test_round_trip_and_marks():
    tables = _tables()
    text = DG.render_layers(tables)
    assert DG._same(DG.parse_digest(text), tables)
    book_head, group_head = [line for line in text.split('\n') if line.startswith('### table ')]
    assert '\t=spread\t' in book_head + '\t' and '\t=mid\t' in book_head and '=depth_imbalance_full' in book_head and '=transition' in book_head
    assert '=ts_recv_ns' in group_head and '=ts_event_ns' in group_head    # cross-derived from the book table
    for column in ('=candidate_family_id', '=terminal_action', '=component_count', '=mirror.mirror_pair_key', '=fill_disposition.class',
                   '=fill_disposition.signature.fill_id_count', '=price_raw_span', '=discovery_status', '=action_counts.A'):
        assert column in group_head, column
    body = text.split(group_head, 1)[1]
    assert re.search(r'(^|[ \t])K0([ \t]|$)', body, re.M)   # a disposition list as positions in order_ids
    assert '~-50000' in text                              # ts_event as an offset from ts_recv
    assert 'I7000000000001,+8' in body                    # an integer list: first, then differences
    assert re.search(r'[ \t]I\+19,', body)                # the next list's first as a delta from the previous row's first


def test_negative_cases_stay_literal_and_round_trip():
    tables = _tables()
    groups = tables['legacy_structure_observables']
    groups[1]['candidate_family_id'] = 'ow-0000tampered'
    groups[2]['side_string'] = 'A\tB'                     # a tab inside a string
    groups[3]['action_string'] = 'J[x'                    # a string that looks like a JSON cell
    groups[0]['ts_recv_ns'] += 1                          # no longer the book table's timestamp
    text = DG.render_layers(tables)
    assert DG._same(DG.parse_digest(text), tables)
    group_head = [line for line in text.split('\n') if line.startswith('### table legacy_structure')][0]
    assert '=ts_recv_ns' not in group_head and '=ts_event_ns' in group_head
    assert 'Sow-0000tampered' in text and '=candidate_family_id' not in group_head


def test_constants_and_same_marks():
    rows = [dict(a=1, b='x', c=[1, 2], d=2.5), dict(a=1, b='x', c=[1, 2], d=2.5), dict(a=1, b='y', c=[1, 2], d=float('nan'))]
    block = DG.render_table('t', rows)
    head = block.split('\n')[0]
    assert '^a' in head and '^c' in head and 'constants: ' in block
    name, parsed = DG.parse_table(block)
    assert name == 't' and DG._same(parsed, rows)
    assert block.split('\n')[3] == '^2'                  # row 1 repeats row 0's b and d (DIGEST_V4: two `^` cells collapse to `^2`); a and c are constants, omitted
    assert block.split('\n')[2] == 'Sx 2.5'              # 'x' is written once inline: its second occurrence is a `^`, so it never repeats as a literal; sep=space


def test_v4_separator_is_a_space_only_when_no_cell_holds_one():
    rows = [dict(a='no space', b=1), dict(a='no space', b=2), dict(a='x', b=3)]
    block = DG.render_table('t', rows)
    assert 'sep=tab' in block.split('\n')[0] and '\t' in block.split('\n')[-2]   # `Sno space` holds a space: tabs
    assert DG._same(DG.parse_table(block)[1], rows)
    rows = [dict(a='nospace', b=1), dict(a='y', b=2)]
    block = DG.render_table('t', rows)
    assert 'sep=space' in block.split('\n')[0] and block.split('\n')[1] == 'Snospace 1'
    assert DG._same(DG.parse_table(block)[1], rows)


def test_v4_run_collapse_expands_back_and_never_touches_minus():
    rows = [dict(a=1, b=2, c=3, d=None, e=None, f=-3), dict(a=1, b=2, c=3, d=None, e=None, f=-3), dict(a=1, b=9, c=3, d=None, e=None, f=-3)]
    block = DG.render_table('t', rows)
    lines = block.split('\n')
    assert '^a' in lines[0] and '^c' in lines[0] and '^d' in lines[0] and '^e' in lines[0] and '^f' in lines[0]   # constants
    assert lines[2] == '2' and lines[3] == '^'            # (constants line at 1) one `^` stays bare
    rows = [dict(a=1, b=2, c=3, d=4), dict(a=1, b=2, c=3, d=5), dict(a=1, b=2, c=3, d=5), dict(a=7, b=2, c=3, d=5)]
    block = DG.render_table('t', rows)
    lines = block.split('\n')
    assert lines[2] == '1 4' and lines[3] == '^ 5' and lines[4] == '^2' and lines[5] == '7 ^'   # b and c are constants (line 1); a and d kept
    assert DG._same(DG.parse_table(block)[1], rows)
    assert DG._expand(['^3', '=2', '-3', 'x', '^']) == ['^', '^', '^', '=', '=', '-3', 'x', '^']


def test_v4_fraction_cells_are_exact_and_only_when_shorter():
    x = float(-37) / float(301)
    rows = [dict(f=x, g=5.412, h=0.5, i=1e-7, j=float(1) / float(3)), dict(f=x + 1e-3, g=5.413, h=0.25, i=2e-7, j=float(2) / float(3))]
    block = DG.render_table('t', rows)
    body = block.split('\n')[1]
    assert body.split(' ')[0] == '-37/301' and body.split(' ')[1] == '5.412' and body.split(' ')[2] == '0.5' and body.split(' ')[4] == '1/3'
    parsed = DG.parse_table(block)[1]
    assert DG._same(parsed, rows) and parsed[0]['f'] == x and parsed[1]['j'] == float(2) / float(3)
    assert DG._float_text(0.1 + 0.2) == '0.30000000000000004'    # not an IEEE division of small integers: decimal stays


def test_v4_column_scale_declared_once_and_deltas_written_divided():
    rows = [dict(price_raw_min=5412001000000, price_raw_max=5413000000000, n=1000, ts_recv_ns=1_000_000_000_000),
            dict(price_raw_min=5412001000000, price_raw_max=5424000000000, n=35000, ts_recv_ns=1_000_000_000_777),
            dict(price_raw_min=5401000000000, price_raw_max=5424000000000, n=30000, ts_recv_ns=1_000_000_000_777)]
    block = DG.render_table('t', rows)
    lines = block.split('\n')
    assert lines[1] == 'scales: price_raw_min=1000000\tprice_raw_max=1000000000\tn=1000'   # ts_recv_ns: +777 is not a multiple of 1000
    assert lines[2] == '5412001 5413 1 1000000000000'
    assert lines[3] == '^ +11 35 +777'
    assert lines[4] == '-11001 ^ 30 ^'
    assert DG._same(DG.parse_table(block)[1], rows)


def test_paired_offset_resolves_whatever_the_column_order_and_when_the_pair_is_constant():
    rows = [dict(ts_event_ns=999, x=1, ts_recv_ns=1000), dict(ts_event_ns=1000, x=2, ts_recv_ns=1000), dict(ts_event_ns=1005, x=3, ts_recv_ns=1000)]
    block = DG.render_table('t', rows)                    # ts_recv_ns is constant here, so it is declared in the header and absent from the rows
    assert '^ts_recv_ns' in block.split('\n')[0] and '~-1' in block
    assert DG._same(DG.parse_table(block)[1], rows)
    rows = [dict(ts_event_ns=999, ts_recv_ns=1000), dict(ts_event_ns=1001, ts_recv_ns=1000), dict(ts_event_ns=1001, ts_recv_ns=1004)]
    block = DG.render_table('t', rows)                    # ts_recv_ns repeats between rows 0 and 1 (a `^`), then moves (a delta)
    assert DG._same(DG.parse_table(block)[1], rows)


def test_v4_tuple_cells_parse_back_as_tuples_and_nested_tuples_refuse():
    rows = [dict(a=i, q=(5.4, 5.41, 5.42), n=(1, 2)) for i in range(3)]
    block = DG.render_table('t', rows)
    assert 'constants: q=U[5.4,5.41,5.42]\tn=U[1,2]' in block and '^q' in block.split('\n')[0]     # a constant tuple column is declared once, with its mark
    rows2 = [dict(a=i, q=(5.4, 5.41 + i, 5.42)) for i in range(3)]
    assert 'U[5.4,6.41,5.42]' in DG.render_table('t', rows2) and DG._same(DG.parse_table(DG.render_table('t', rows2))[1], rows2)
    parsed = DG.parse_table(block)[1]
    assert DG._same(parsed, rows) and isinstance(parsed[0]['q'], tuple) and isinstance(parsed[0]['n'], tuple)
    assert not DG._same([dict(q=[1, 2])], [dict(q=(1, 2))])                 # a list is not a tuple
    try:
        DG.render_table('t', [dict(a=((1, 2), 3))])
    except ValueError as err:
        assert 'nested in a tuple' in str(err)
    else:
        raise AssertionError('a tuple nested in a tuple has no exact cell and must refuse')


def test_a_table_whose_every_column_is_constant_round_trips():
    for rows in ([dict(a=1, b='x')], [dict(a=1)] * 3, [dict(action_string='FCT', count=5)]):
        assert DG._same(DG.parse_table(DG.render_table('structure_families', rows))[1], rows)
        DG.render_layers({'structure_families': rows})                  # a one-family cycle must not crash the digest
    assert DG.parse_table(DG.render_table('t', []))[1] == []


def test_negative_zero_is_never_folded_into_positive_zero():
    assert not DG._same(0.0, -0.0) and DG._same(-0.0, -0.0)
    rows = [dict(x=0.0, y=1), dict(x=-0.0, y=2), dict(x=1.0, y=3)]
    parsed = DG.parse_table(DG.render_table('t', rows))[1]
    assert math.copysign(1.0, parsed[1]['x']) == -1.0 and DG._same(parsed, rows)
    parsed = DG.parse_table(DG.render_table('t', [dict(x=-0.0), dict(x=0.0), dict(x=-0.0)]))[1]
    assert [math.copysign(1.0, r['x']) for r in parsed] == [-1.0, 1.0, -1.0]
    rows = [dict(best_bid=-1.0, best_ask=1.0, mid=-0.0, y=1), dict(best_bid=-1.0, best_ask=1.0, mid=0.0, y=2)]
    parsed = DG.parse_table(DG.render_table('t', rows))[1]
    assert repr(parsed[0]['mid']) == '-0.0' and repr(parsed[1]['mid']) == '0.0'


def test_parse_table_refuses_a_truncated_or_tampered_block():
    block = DG.render_table('t', [dict(a=1, b=2), dict(a=1, b=3), dict(a=4, b=3)])
    lines = block.split('\n')
    for bad in ('\n'.join(lines[:-2]) + '\n', block.replace('4 ^', '4'), block.replace('4 ^', '4 ^ 9'), block.replace('^ 3', '^3')):
        try:
            DG.parse_table(bad)
        except ValueError:
            continue
        raise AssertionError('accepted a tampered block: %r' % bad[-30:])


def test_float_edge_literals_and_mark_looking_strings():
    rows = [dict(x=float('inf')), dict(x=float('-inf')), dict(x=float('nan')), dict(x=1e22), dict(x=5e-324), dict(x=1.7976931348623157e308)]
    block = DG.render_table('t', rows)
    assert block.split('\n')[1:7] == ['inf', '-inf', 'nan', '1e+22', '5e-324', '1.7976931348623157e+308']
    assert DG._same(DG.parse_table(block)[1], rows)
    assert DG._float_text(2.5) == '2.5' and DG._float_text(0.1) == '0.1'
    rows = [dict(s=v) for v in ('-3', '12/34', '^', '=', 'nan', 'T', '@0', '+5', '?', 'K0', 'I1', '~1', 'U[', 'J[', 'a\rb', '', '  lead', 'trail ', 'caf\u00e9')]
    parsed = DG.parse_table(DG.render_table('t', rows))[1]
    assert all(isinstance(r['s'], str) for r in parsed) and DG._same(parsed, rows)


def test_column_names_that_cannot_be_spelled_refuse_with_a_value_error():
    for rows in ([{'^a': 1}, {'^a': 2}], [{'=b': 1}, {'=b': 2}], [{'a=b': 1}, {'a=b': 1}], [{'a\tb': 1}, {'a\tb': 2}], [{'a.b': 1}, {'a.b': 2}]):
        try:
            DG.render_layers({'t': rows})
        except ValueError:
            continue
        raise AssertionError('accepted an unspellable column: %r' % list(rows[0]))


def test_random_structural_rows_round_trip():
    import random
    rnd = random.Random(20260921)
    names = ['a', 'ts_recv_ns', 'ts_event_ns', 'price_raw_min', 'n', 'f', 's', 'l', 'd', 'best_bid', 'best_ask', 'mid', 'spread']
    def value(c):
        k = rnd.random()
        if k < 0.1: return None
        if k < 0.2: return rnd.random() < 0.5
        if k < 0.4: return rnd.randint(-5, 5) * (1000 if rnd.random() < 0.5 else 1)
        if k < 0.6: return rnd.choice([rnd.random(), float(rnd.randint(-9, 9)) / float(rnd.randint(1, 9)), float('nan'), -0.0, 1e-9, 2.5])
        if k < 0.75: return rnd.choice(['x', '-3', '^', '12/34', 'a b', 'S', ''])
        if k < 0.85: return [rnd.randint(0, 9) for _ in range(rnd.randint(0, 4))]
        if k < 0.95: return dict(u=rnd.randint(0, 3), v='q')
        return (rnd.randint(0, 3), 'x')
    for _ in range(400):
        cols = rnd.sample(names, rnd.randint(1, 6))
        rows = []
        for i in range(rnd.randint(1, 8)):
            row = {c: value(c) for c in cols if rnd.random() < 0.9}
            if rows and rnd.random() < 0.3:
                row = dict(rows[-1])
            if row:
                rows.append(row)
        if not rows:
            continue
        block = DG.render_table('t', rows)
        assert DG._same(DG.parse_table(block)[1], rows), block


# ---- DIGEST_V6: the bedrock tables (BR-5; SPEC_CYCLE0_BEDROCK_20260921.md) ------------------------------------------

def _bedrock_files():
    """Two bedrock layer files as frankie_box_bedrock.project writes them (member projections beside the group key; lifecycle
    rows whole), one could_not layer, and the shapes the real ledgers carry (nested dicts, lists of dicts, JSON cells)."""
    members = []
    for g in range(3):
        recv = 1633298400_300150000 + g * 4_000_000_000
        members.append({'group_index': g, 'ts_recv_ns': recv, 'f_last_ts_recv_ns': recv, 'clocks.first_lawful_availability_ns': recv,
                        'structure.candidate_family_id': 'ow-%d' % g, 'structure.mirror.orientation': 'SAME',
                        'activity_since.*.top_level_qty_by_action': {'session_open': {'A': 5 + g, 'C': 0}, 'last_trade': {'A': 1}},
                        'book_full.bid_levels_full[].fifo_queue[]': [[{'order_id': 701, 'size': 5}], [{'order_id': 702, 'size': 1}]],
                        'capture_observations': {}})
    clocks = [dict(m) for m in members]
    for c in clocks:
        c.pop('structure.candidate_family_id'); c.pop('structure.mirror.orientation'); c.pop('activity_since.*.top_level_qty_by_action')
        c.pop('book_full.bid_levels_full[].fifo_queue[]'); c.pop('capture_observations')
        c['clocks.decision_ts_recv_ns'] = c['ts_recv_ns']; c['decision_basis'] = 'REPLAY_EARLIEST_LAWFUL_AVAILABILITY'; c['f_last_to_decision_delay_ns'] = 0
    lineage = [dict(emitting_section='lineage', emitted_on='STAGE_CLOSED', emitted_at_recv_ns=1633298400_300150000 + i * 4_000_000_000, node_id=700 + i,
                    parent_id=None if i == 0 else 700, depth=i, depth_label='D%d' % i, status='OPEN' if i == 2 else 'CLOSED', side_orientation='B') for i in range(3)]
    flow = [dict(emitting_section='flow_substrate', emitted_on='SECOND_COMPLETED', emitted_at_recv_ns=1633298401_000000000 + i * 1_000_000_000, second=1633298401 + i,
                 roll20_value=None if i < 2 else 0.5, roll20_defined=i >= 2, polarity='BUY', rows=[dict(a=1)], last_quote=dict(bid=3_500_000_000, ask=3_510_000_000)) for i in range(4)]
    return {
        'derived_d_family_geometry': dict(layer='derived_d_family_geometry', status='derived', reason=None, producer='a_memory_member_first_recalculation_20260828.describe_structure',
                                          member_paths=['structure.candidate_family_id', 'structure.mirror.orientation'], lifecycle_sections=['lineage'],
                                          member_rows=members, lifecycle_rows=lineage, section_counts=dict(lineage=3), count=6, partial=[]),
        'derived_v4_mechanics_fifo_features': dict(layer='derived_v4_mechanics_fifo_features', status='derived', reason=None, producer='native_full_capture_adapter._window_extras',
                                                   member_paths=['activity_since.*.top_level_qty_by_action', 'book_full.bid_levels_full[].fifo_queue[]', 'capture_observations'],
                                                   lifecycle_sections=['queue'], member_rows=members, lifecycle_rows=[], section_counts=dict(queue=0), count=3, partial=[]),
        'derived_roll20_and_dipole_state': dict(layer='derived_roll20_and_dipole_state', status='derived', reason=None, producer='native_flow_substrate.complete_second',
                                                member_paths=[], lifecycle_sections=['flow_substrate', 'episode'], member_rows=[], lifecycle_rows=flow,
                                                section_counts=dict(flow_substrate=4, episode=0), count=4,
                                                partial=[dict(section='episode', rows=0, reason='the candidate lane needs 900 s of warmup and 600 observations before any candidate can be detected; this cycle\'s rows span 13.0 s')]),
        'clock_model_evaluation': dict(layer='clock_model_evaluation', status='derived', reason=None, producer='native_clocks.member_clock_row',
                                       member_paths=['clocks.decision_ts_recv_ns', 'decision_basis', 'f_last_to_decision_delay_ns'], lifecycle_sections=[],
                                       member_rows=clocks, lifecycle_rows=[], section_counts={}, count=3, partial=[]),
        'prebirth_predecessor_at_risk_state': dict(layer='prebirth_predecessor_at_risk_state', status='could_not', producer='native_replay_driver._open_candidate',
                                                   reason='the candidate lane needs 900 s of warmup and 600 observations before any candidate can be detected; this cycle\'s rows span 13.0 s',
                                                   member_paths=[], lifecycle_sections=['episode', 'candidate'], member_rows=[], lifecycle_rows=[],
                                                   section_counts=dict(episode=0, candidate=0), count=0, partial=[]),
        'clock_lock_time': dict(layer='clock_lock_time', status='could_not', producer=None, reason='NO_PRODUCER_FOUND: lock time is Frankie\'s OUTPUT',
                                member_paths=[], lifecycle_sections=[], member_rows=[], lifecycle_rows=[], section_counts={}, count=0, partial=[]),
    }


def test_v6_schema_and_header_name_the_bedrock_tables():
    assert DG.SCHEMA == 'DIGEST_V6'
    receipt = dict(rows=dict(path='p', count=2, kinds={}, head='h' * 64, head_is_request_source_hash=True), input_records=1, legacy_rows=1, f_last_groups=1,
                   failure_count=0, pin_group='legacy_observable_crosswalk', layers={})
    text = DG.digest_text(receipt, {}, [], [], [], [], 0, [], [], bedrock=_bedrock_files())
    head = text.split('## Layer status')[0]
    assert head.startswith('# Derivation digest DIGEST_V6 ')
    assert 'bedrock.members' in head and 'bedrock.lifecycle.<section>' in head and 'bedrock.layers' in head and 'bedrock.run' in head and '#count' in head
    without = DG.digest_text(receipt, {}, [], [], [], [], 0, [], [])
    assert '## Bedrock' not in without and '### table bedrock.' not in without


def test_v6_bedrock_tables_are_one_members_table_one_table_per_section_and_an_index_all_parsing_back():
    tables = DG.bedrock_tables(_bedrock_files())
    assert list(tables) == ['bedrock.layers', 'bedrock.members', 'bedrock.lifecycle.flow_substrate', 'bedrock.lifecycle.lineage']   # no traversal in this fixture: no bedrock.run
    index = tables['bedrock.layers']
    assert [r['layer'] for r in index] == ['derived_d_family_geometry', 'derived_v4_mechanics_fifo_features', 'derived_roll20_and_dipole_state',
                                            'clock_model_evaluation', 'prebirth_predecessor_at_risk_state', 'clock_lock_time']
    assert index[0]['status'] == 'derived' and index[0]['member_paths'] == 'structure.candidate_family_id structure.mirror.orientation'
    assert index[2]['partial'] == 'episode' and index[4]['status'] == 'could_not' and '900 s' in index[4]['reason']
    members = tables['bedrock.members']
    assert len(members) == 3 and [r['group_index'] for r in members] == [0, 1, 2]
    columns = set(DG._flatten(members[0]))                  # the codec's columns: every derived layer's carrier path, each once
    assert {'group_index', 'ts_recv_ns', 'f_last_ts_recv_ns', 'clocks.first_lawful_availability_ns', 'structure.candidate_family_id',
            'structure.mirror.orientation', 'book_full.bid_levels_full[].fifo_queue[]#count', 'capture_observations', 'clocks.decision_ts_recv_ns',
            'decision_basis', 'f_last_to_decision_delay_ns', 'activity_since.*.top_level_qty_by_action.session_open.A'} <= columns
    assert members[1]['activity_since']['*']['top_level_qty_by_action'] == {'session_open': {'A': 6, 'C': 0}, 'last_trade': {'A': 1}}
    assert members[0]['capture_observations'] == '{}'       # an empty mapping is one JSON string cell (it cannot flatten to a column)
    assert len(tables['bedrock.lifecycle.lineage']) == 3 and len(tables['bedrock.lifecycle.flow_substrate']) == 4
    text = DG.render_layers(tables)                          # rendered, parsed back and compared by the codec itself
    parsed = DG.parse_digest(text)
    assert set(parsed) == set(tables)
    assert parsed['bedrock.members'][2]['book_full']['bid_levels_full[]']['fifo_queue[]#count'] == 2     # a list-valued path rides as its leaf count
    assert 'fifo_queue[]' not in parsed['bedrock.members'][2]['book_full']['bid_levels_full[]']
    assert parsed['bedrock.members'] == members
    assert parsed['bedrock.lifecycle.flow_substrate'][0]['roll20_value'] is None and parsed['bedrock.lifecycle.flow_substrate'][3]['roll20_value'] == 0.5
    assert parsed['bedrock.lifecycle.flow_substrate'][1]['last_quote']['bid'] == 3_500_000_000   # nested dicts flatten to dotted columns and back
    assert parsed['bedrock.lifecycle.lineage'][1]['parent_id'] == 700 and parsed['bedrock.lifecycle.lineage'][0]['parent_id'] is None


def test_v6_a_nested_key_the_table_cannot_spell_becomes_one_json_string_cell():
    files = _bedrock_files()
    flow = files['derived_roll20_and_dipole_state']['lifecycle_rows']
    for row in flow:
        row['section_totals'] = {'rejected: no quote': 2, 'a=b': 1}
    tables = DG.bedrock_tables(files)
    cell = tables['bedrock.lifecycle.flow_substrate'][0]['section_totals']
    assert isinstance(cell, str) and json.loads(cell) == {'rejected: no quote': 2, 'a=b': 1}
    parsed = DG.parse_digest(DG.render_layers(tables))
    assert json.loads(parsed['bedrock.lifecycle.flow_substrate'][0]['section_totals']) == {'rejected: no quote': 2, 'a=b': 1}


def test_v6_a_conflicting_member_projection_between_layers_refuses():
    files = _bedrock_files()
    files['clock_model_evaluation']['member_rows'][1]['ts_recv_ns'] += 1     # the same group projected with a different key value
    try:
        DG.bedrock_tables(files)
    except ValueError as err:
        assert 'group 1' in str(err) and 'ts_recv_ns' in str(err)
    else:
        raise AssertionError('two layers disagreeing on a group key must refuse')


def test_v6_a_nested_key_containing_a_dot_becomes_one_json_string_cell():
    files = _bedrock_files()
    for row in files['derived_roll20_and_dipole_state']['lifecycle_rows']:
        row['section_totals'] = {'a.b': 1, 'c': 2}
    files['derived_d_family_geometry']['member_rows'][0]['activity_since.*.top_level_qty_by_action'] = {'session_open': {'A.C': 5}}
    tables = DG.bedrock_tables(files)
    assert json.loads(tables['bedrock.lifecycle.flow_substrate'][0]['section_totals']) == {'a.b': 1, 'c': 2}
    assert json.loads(tables['bedrock.members'][0]['activity_since']['*']['top_level_qty_by_action']['session_open']) == {'A.C': 5}
    parsed = DG.parse_digest(DG.render_layers(tables))
    assert json.loads(parsed['bedrock.lifecycle.flow_substrate'][0]['section_totals']) == {'a.b': 1, 'c': 2}


def test_v6_the_run_table_carries_the_traversal_verdict_and_rows_without_a_group_key_refuse():
    files = _bedrock_files()
    for f in files.values():
        f['traversal'] = dict(verdict='REJECTED', failed_gates=['coverage', 'denominators'], groups=3, records=11, span_seconds=10.0,
                              candidate_warmup_seconds=900, candidate_min_observations=600)
    tables = DG.bedrock_tables(files)
    assert tables['bedrock.run'] == [dict(verdict='REJECTED', failed_gates='coverage denominators', groups=3, records=11, span_seconds=10.0,
                                          candidate_warmup_seconds=900, candidate_min_observations=600)]
    text = DG.render_layers(tables)
    assert DG.parse_digest(text)['bedrock.run'] == tables['bedrock.run']
    receipt = dict(rows=dict(path='p', count=2, kinds={}, head='h' * 64, head_is_request_source_hash=True), input_records=1, legacy_rows=1, f_last_groups=1,
                   failure_count=0, pin_group='legacy_observable_crosswalk', layers={})
    assert 'verdict over this slice: REJECTED, failed gates coverage, denominators' in DG.digest_text(receipt, {}, [], [], [], [], 0, [], [], bedrock=files)
    del files['clock_model_evaluation']['member_rows'][1]['group_index']
    with pytest.raises(ValueError, match='row without the group key group_index'):
        DG.bedrock_tables(files)


def test_v6_a_none_group_index_sorts_last_and_round_trips():
    files = _bedrock_files()
    files['clock_model_evaluation']['member_rows'].append({'group_index': None, 'ts_recv_ns': 5, 'f_last_ts_recv_ns': 5, 'clocks.decision_ts_recv_ns': 5,
                                                          'decision_basis': 'REPLAY_EARLIEST_LAWFUL_AVAILABILITY', 'f_last_to_decision_delay_ns': 0})
    tables = DG.bedrock_tables(files)
    assert [r['group_index'] for r in tables['bedrock.members']] == [0, 1, 2, None]
    assert DG.parse_digest(DG.render_layers(tables))['bedrock.members'] == tables['bedrock.members']


def _section_files():
    """The two BR-9 section files (frankie_box_bedrock.project_sections' shape) with rows the pinned run's own shape carries."""
    decl = dict(causal_cutoff='snapshot receive time (ts_recv_ns)', missingness_rule='no exclusions', numerator_formula='bid_depth_full + ask_depth_full',
                population='full-book snapshots within the day', status='RESOLVED')
    stratum = dict(chain_signature='', clock='ts_recv_ns', cluster_version='NO_CLUSTERING_D5', continuity_segment=18904, family_id='POOLED',
                   session_phase='PRE_SETTLEMENT', source_day='20211003', source_role='SCORED_FINDINGS_DAY')
    value = dict(n=3, arithmetic_mean=15.0, minimum=10, maximum=20, p50=15.0)
    companions = [dict(measure='book_total_depth', kind='DISTRIBUTION', section='4.2', stratum=stratum, declaration=decl, excluded_missing_members=0, value=value),
                  dict(measure='relative_imbalance', kind='DISTRIBUTION', section='4.2', stratum=stratum, declaration=dict(decl, numerator_formula='(b - a) / (b + a)'),
                       excluded_missing_members=1, value=dict(value, arithmetic_mean=0.75, minimum=0.5, maximum=1.0, p50=0.75))]
    pairs = [dict(source_day='20211003', source_role='SCORED_FINDINGS_DAY', continuity_segment=18904, session_phase='PRE_SETTLEMENT',
                  first_book=dict(best_bid=3, best_ask=None, bid_depth=10, ask_depth=0, spread_raw=None, total_depth=10, recv_ns=1633298403300150000),
                  last_book=dict(best_bid=3, best_ask=3, bid_depth=15, ask_depth=5, spread_raw=0, total_depth=20, recv_ns=1633298410300150000))]
    mirror = [dict(emitting_section='mirror', emitted_on='GROUP_CLOSE', emitted_at_recv_ns=1633298403300150000 + i * 3_500_000_000, member_id=f'grp-20211003-{i}',
                   disposition='PENDING', mirror_pair_key='ABB|BAA', orientation='CANONICAL' if i == 2 else 'MIRROR', counterparts_considered=0,
                   nearest_candidate_distance=None) for i in range(3)]
    mirror += [dict(emitting_section='mirror', emitted_on='STREAM_END', emitted_at_recv_ns=1633298410300150000, member_id=f'grp-20211003-{i}',
                    disposition='UNMATCHED', mirror_pair_key='ABB|BAA', orientation='MIRROR', nearest_candidate_distance=None,
                    unmatched_reason='NO_COUNTERPART_IN_SCOPE') for i in range(3)]
    rule = dict(rule_id='MIRROR_EXACT_SIDE_SWAP_NEAREST_COORDINATE_V1', attribution='ONE_TO_ONE', attributions_per_member=1, coordinate_name='group_ts_recv_ns',
                distance_bound=60000000000.0, lookahead='none; a member matches only against members already offered',
                scope_fields=['source_day', 'source_role', 'continuity_segment', 'family_id', 'session_phase', 'subfamily_id'])
    base = dict(member_paths=[], member_rows=[], partial=[], section_counts={}, absent_paths={}, reason=None, status='derived')
    return {
        'bedrock_section_4_2': dict(base, layer='bedrock_section_4_2', section='4.2', kind='SECTION_COMPANION', producer='native_book_regime.BookRegimeCalculator',
                                    lifecycle_sections=[], lifecycle_rows=[], companion_rows=companions, first_last_pairs=pairs,
                                    declarations=[dict(measure='book_total_depth', kind='DISTRIBUTION', **decl),
                                                  dict(measure='relative_imbalance', kind='DISTRIBUTION', **dict(decl, numerator_formula='(b - a) / (b + a)'))],
                                    matching_rule=None, count=3),
        'bedrock_section_4_4': dict(base, layer='bedrock_section_4_4', section='4.4', kind='SECTION_LIFECYCLE', producer='native_mirror.MirrorMatcher',
                                    lifecycle_sections=['mirror'], lifecycle_rows=mirror, section_counts=dict(mirror=6), companion_rows=[], first_last_pairs=[],
                                    declarations=[], matching_rule=rule, count=6),
    }


def test_v6_the_two_section_files_render_as_companion_declaration_first_last_mirror_and_matching_rule_tables():
    # BR-9 (Greg, 2026-09-22: 4.2 and 4.4 reach Frankie as TABLES): every fact once, parsed back equal
    files = dict(_bedrock_files(), **_section_files())
    tables = DG.bedrock_tables(files)
    assert list(tables) == ['bedrock.layers', 'bedrock.members', 'bedrock.lifecycle.flow_substrate', 'bedrock.lifecycle.lineage', 'bedrock.lifecycle.mirror',
                            'bedrock.companions.4.2', 'bedrock.declarations.4.2', 'bedrock.first_last.4.2', 'bedrock.matching_rule.4.4']
    index = {r['layer']: r for r in tables['bedrock.layers']}
    assert index['bedrock_section_4_2']['count'] == 3 and index['bedrock_section_4_4']['lifecycle_count'] == 6 and index['bedrock_section_4_4']['lifecycle_sections'] == 'mirror'
    assert len(tables['bedrock.lifecycle.mirror']) == 6 and tables['bedrock.lifecycle.mirror'][5]['unmatched_reason'] == 'NO_COUNTERPART_IN_SCOPE'
    companions = tables['bedrock.companions.4.2']
    assert len(companions) == 2 and 'declaration' not in companions[0] and 'section' not in companions[0]      # the declaration once, in its own table
    assert companions[0]['measure'] == 'book_total_depth' and companions[0]['value']['arithmetic_mean'] == 15.0 and companions[0]['stratum']['source_day'] == '20211003'
    assert [d['measure'] for d in tables['bedrock.declarations.4.2']] == ['book_total_depth', 'relative_imbalance']
    assert tables['bedrock.declarations.4.2'][1]['numerator_formula'] == '(b - a) / (b + a)'
    assert tables['bedrock.first_last.4.2'][0]['first_book']['spread_raw'] is None and tables['bedrock.first_last.4.2'][0]['last_book']['total_depth'] == 20
    assert tables['bedrock.matching_rule.4.4'][0]['rule_id'] == 'MIRROR_EXACT_SIDE_SWAP_NEAREST_COORDINATE_V1' and tables['bedrock.matching_rule.4.4'][0]['scope_fields'][0] == 'source_day'
    assert 'bedrock.members' in tables and len(tables['bedrock.members']) == 3                 # the section files add no member columns
    text = DG.render_layers(tables)
    parsed = DG.parse_digest(text)
    assert set(parsed) == set(tables)
    for name in ('bedrock.lifecycle.mirror', 'bedrock.companions.4.2', 'bedrock.declarations.4.2', 'bedrock.first_last.4.2', 'bedrock.matching_rule.4.4'):
        assert parsed[name] == tables[name], name
    head = DG.digest_text(dict(rows=dict(path='p', count=2, kinds={}, head='h' * 64, head_is_request_source_hash=True), input_records=1, legacy_rows=1,
                               f_last_groups=1, failure_count=0, pin_group='legacy_observable_crosswalk', layers={}), {}, [], [], [], [], 0, [], [], bedrock=files).split('## Layer status')[0]
    assert 'bedrock.companions.<section>' in head and 'bedrock.declarations.<section>' in head and 'bedrock.first_last.<section>' in head and 'bedrock.matching_rule.<section>' in head


def test_v6_a_could_not_section_file_renders_no_section_table_and_stays_in_the_index():
    files = dict(_bedrock_files(), **_section_files())
    files['bedrock_section_4_4'] = dict(files['bedrock_section_4_4'], status='could_not', reason='the traversal emitted no rows for this carrier on this cycle\'s rows',
                                        lifecycle_rows=[], section_counts=dict(mirror=0), matching_rule=None, count=0)
    tables = DG.bedrock_tables(files)
    assert 'bedrock.lifecycle.mirror' not in tables and 'bedrock.matching_rule.4.4' not in tables and 'bedrock.companions.4.2' in tables
    assert {r['layer']: r['status'] for r in tables['bedrock.layers']}['bedrock_section_4_4'] == 'could_not'
