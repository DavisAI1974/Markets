"""The dense digest (deploy/aws/box/frankie_box_digest_render.py) is a projection the code proves: every table is
parsed back and compared before it is written. These tests pin each mark of the DIGEST_V3 cell grammar on hand-built
rows shaped like the producers' (book frames, structure groups), and the negative cases: a value that does NOT match
its derivation stays literal, a timestamp that differs from the book table's is not declared cross-derived, and the
two strings the first digest could not render (a tab inside a string, a string starting `J[`) round-trip."""
from __future__ import annotations

import copy
import hashlib
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
