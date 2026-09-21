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
    assert '\tK0\t' in body or '\tK0' in body            # a disposition list as positions in order_ids
    assert '~-50000' in text                              # ts_event as an offset from ts_recv
    assert 'I7000000000001,+8' in body                    # an integer list: first, then differences
    assert '\tI+19,' in body                              # the next list's first as a delta from the previous row's first


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
    assert block.split('\n')[3] == '^\t^'                # row 1 repeats row 0's b and d; a and c are constants, omitted
    assert block.split('\n')[2] == 'Sx\t2.5'             # 'x' is written once inline: its second occurrence is a `^`, so it never repeats as a literal
