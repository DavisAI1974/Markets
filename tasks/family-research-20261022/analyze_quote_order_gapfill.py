"""Verify every transported original row and analyze the bounded trade sequence.

Original chunks remain byte-preserving. Derived facts and pointers supplement
the complete records; no trades or contradictory source fields are removed.
"""
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
PARENT = BASE / 'trade-lifecycle-targeted-v1'
OUT = PARENT / 'quote-order-gapfill-v1'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


with gzip.open(OUT / 'original-record-index.jsonl.gz', 'rt') as handle:
    index = [json.loads(line) for line in handle]
by_location = {(r['chunk'], r['chunk_line_number']): r for r in index}
refs = {(r['source'], r['source_ordinal']): r for r in index}
assert len(by_location) == len(refs) == len(index)
with (BASE / 'price-curve-timestamps.csv').open(newline='') as handle:
    original = list(csv.DictReader(handle))
with gzip.open(PARENT / 'all-30739-trades.csv.gz', 'rt', newline='') as handle:
    nav = list(csv.DictReader(handle))
assert len(original) == len(nav) == 30739
wanted = {int(t[key]) for t in nav[118:150]
          for key in ['pre_group_source_ordinal', 'emission_group_source_ordinal']}
states = {}
native_selected = {}
all_actions = []
life = []
counts = collections.Counter()
root_clocks = {}


def iterate(source):
    paths = sorted({r['chunk'] for r in index if r['source'] == source})
    for name in paths:
        with gzip.open(OUT / name, 'rb') as handle:
            for line_number, raw in enumerate(handle, 1):
                ref = by_location[(name, line_number)]
                assert ref['source'] == source and len(raw) == ref['source_length']
                assert hashlib.sha256(raw).hexdigest() == ref['original_row_sha256']
                counts[source] += 1
                yield ref, json.loads(raw)


for ref, row in iterate('native.member'):
    ordinal = ref['source_ordinal']
    assert row['frankie_emission']['input_cursor'] == ref['input_cursor']
    assert row['ts_event_ns'] == ref['event_ns'] and row['ts_recv_ns'] == ref['known_by_ns']
    assert type(row['ts_recv_ns']) is int and row['instrument_id'] == 150611
    book = row['book_full']
    bid = book['bid_levels_full'][0]['price_raw']
    ask = book['ask_levels_full'][0]['price_raw']
    states[ordinal] = dict(source_ref=ref, best_bid_raw=bid, best_ask_raw=ask,
                           source_mid=row['book']['mid'],
                           integrity=row['integrity'], integrity_delta=row['integrity_delta'],
                           sequence_contiguous=row['sequence_contiguous'])
    all_actions.append(dict(source_ref=ref, original_raw_actions=row['raw_actions']))
    if ordinal in wanted:
        native_selected[ordinal] = row
for ref, row in iterate('root.frames'):
    assert row[0] == 'dict'
    fields = dict(row[1])
    event = fields['ts_event_ns'][1]
    receive = fields['ts_recv_ns'][1]
    assert type(event) is int and type(receive) is int
    assert event == ref['event_ns'] and receive == ref['known_by_ns']
    root_clocks[ref['source_ordinal']] = (event, receive)
for ref, row in iterate('second_set'):
    assert row['key']['input_cursor'] == ref['input_cursor']
    assert row['key']['instrument_id'] == 150611
    assert row['clocks']['clock_event_known_by'] == ref['known_by_ns']
for ref, row in iterate('native.lifecycle'):
    assert row['frankie_emission']['input_cursor'] == ref['input_cursor']
    assert row['frankie_emission']['ts_recv_ns'] == ref['known_by_ns']
    life.append((ref, row))
expected = json.loads((OUT / 'source-read-receipt.json').read_text())['original_record_counts']
assert dict(counts) == expected
assert len(states) == len(root_clocks) == 1667
with gzip.open(OUT / 'all-original-actions-in-episode.jsonl.gz', 'wt') as handle:
    for row in all_actions:
        handle.write(json.dumps(row, separators=(',', ':')) + '\n')

analyses = []
for number in range(118, 150):
    trade = original[number]
    current = int(nav[number]['emission_group_source_ordinal'])
    prior = int(nav[number]['pre_group_source_ordinal'])
    after = native_selected[current]
    before = native_selected[prior]
    assert after['ts_recv_ns'] == int(trade['available_ns'])
    assert after['ts_event_ns'] == int(trade['event_ns'])
    assert before['ts_recv_ns'] < int(trade['receive_ns'])
    assert before['frankie_emission']['input_cursor'] < int(trade['trade_input_cursor'])
    matches = [a for a in after['raw_actions'] if a['action'] == 'T'
               and a['ts_event_ns'] == int(trade['event_ns'])
               and a['ts_recv_ns'] == int(trade['receive_ns'])
               and a['price_raw'] == int(trade['price_raw']) and a['size'] == int(trade['size'])]
    assert len(matches) == 1, (number, 'exact T match', len(matches))
    fills = [a for a in after['raw_actions'] if a['action'] == 'F'
             and a['ts_event_ns'] == int(trade['event_ns'])
             and a['price_raw'] == int(trade['price_raw'])]
    maker_ids = {a['order_id'] for a in fills}
    cleanup = [a for a in after['raw_actions'] if a['action'] == 'C' and a['order_id'] in maker_ids]
    orders = [dict(source_ref=ref, original_record=row) for ref, row in life
              if ref['input_cursor'] == int(trade['group_close_input_cursor'])
              and row.get('order_id') in maker_ids]
    bid_delta = states[current]['best_bid_raw'] - states[prior]['best_bid_raw']
    ask_delta = states[current]['best_ask_raw'] - states[prior]['best_ask_raw']
    maker_queues = []
    for side, key in [('B', 'bid_levels_full'), ('A', 'ask_levels_full')]:
        for level in before['book_full'][key]:
            found = [q for q in level['fifo_queue'] if q['order_id'] in maker_ids]
            if found:
                maker_queues.append(dict(side=side, original_full_price_level=level,
                                         matched_order_ids=[q['order_id'] for q in found]))
    analyses.append(dict(trade_ordinal=number, original_trade=trade,
                         exact_before_group_ref=refs[('native.member', prior)],
                         exact_after_group_ref=refs[('native.member', current)],
                         exact_root_before_ref=refs[('root.frames', prior)],
                         exact_root_after_ref=refs[('root.frames', current)],
                         rich_second_set_ref=refs[('second_set', int(trade['group_close_input_cursor']))],
                         before_book=dict(best_bid=before['book']['best_bid'], best_ask=before['book']['best_ask'],
                                          mid=before['book']['mid'], bid_depth_full=before['book']['bid_depth_full'],
                                          ask_depth_full=before['book']['ask_depth_full']),
                         after_book=dict(best_bid=after['book']['best_bid'], best_ask=after['book']['best_ask'],
                                         mid=after['book']['mid'], bid_depth_full=after['book']['bid_depth_full'],
                                         ask_depth_full=after['book']['ask_depth_full']),
                         individual_quote_change=dict(bid_raw=bid_delta, ask_raw=ask_delta),
                         original_matched_trade_actions=matches, original_maker_fill_actions=fills,
                         original_same_id_removal_actions=cleanup,
                         original_maker_price_levels_before_trade=maker_queues,
                         original_same_emission_order_records=orders,
                         source_integrity=states[current]['integrity'],
                         source_integrity_delta=states[current]['integrity_delta'],
                         source_sequence_contiguous=states[current]['sequence_contiguous'],
                         limit='Full original records are in the referenced chunks. Same-id F/C evidence supports fill cleanup; no snapshot-only execution or cancellation inference.'))
save('each-trade-exact-quote-order-analysis.json', analyses)
with gzip.open(OUT / 'every-trade-new-source-links.jsonl.gz', 'wt') as handle:
    for number, trade in enumerate(original):
        current = int(nav[number]['emission_group_source_ordinal'])
        prior = int(nav[number]['pre_group_source_ordinal']) if nav[number]['pre_group_source_ordinal'] else None
        current_ref = refs.get(('native.member', current))
        prior_ref = refs.get(('native.member', prior))
        row = dict(trade_ordinal=number, original_trade=trade,
                   exact_emission_original_native_ref=current_ref,
                   exact_prior_original_native_ref=prior_ref,
                   original_root_emission_ref=refs.get(('root.frames', current)),
                   original_rich_second_set_ref=refs.get(('second_set', int(trade['group_close_input_cursor']))),
                   original_complete_evidence_bundle='../every-trade-evidence-bundle.jsonl.gz',
                   disposition='NEW_EXACT_SOURCE_COVERAGE' if current_ref else 'RETAINED_UNCHANGED_OUTSIDE_THIS_BOUNDED_SOURCE_READ')
        handle.write(json.dumps(row, separators=(',', ':')) + '\n')

transitions = []
ordinals = sorted(states)
for previous, current in zip(ordinals, ordinals[1:]):
    a, b = states[previous], states[current]
    if (a['best_bid_raw'], a['best_ask_raw']) != (b['best_bid_raw'], b['best_ask_raw']):
        transitions.append(dict(before_ref=a['source_ref'], after_ref=b['source_ref'],
                                observed_before=dict(bid_raw=a['best_bid_raw'], ask_raw=a['best_ask_raw']),
                                observed_after=dict(bid_raw=b['best_bid_raw'], ask_raw=b['best_ask_raw']),
                                original_actions=next(r['original_raw_actions'] for r in all_actions
                                                      if r['source_ref']['source_ordinal'] == current)))
save('every-observed-quote-transition.json', transitions)
verification = dict(status='PASSED_EXACT_SOURCE_TRANSPORT_AND_TRADE_CHECKS',
                    every_original_row_digest_checked=True, original_row_counts=dict(counts),
                    total_original_rows=sum(counts.values()), continuous_group_records=len(states),
                    exact_trade_actions_matched=len(analyses), exact_pre_and_after_trade_books=len(analyses),
                    original_root_clocks_match_native=True, all_30739_trades_retained=True,
                    dropped_trades=0, averaged_prices_or_model_votes=False,
                    original_nested_sources_untouched=True, frozen_source_database_rehash=False,
                    quote_transitions=len(transitions), semantic_coverage='NOT_PASSED',
                    mlp_reproducibility='Unresolved original evidence unchanged')
save('gapfill-verification.json', verification)
print(json.dumps(verification, indent=2), flush=True)
for row in analyses:
    if row['trade_ordinal'] in [122, 127, 134, 136, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149]:
        print(json.dumps(dict(trade=row['trade_ordinal'], price=row['original_trade']['price'],
              before=row['before_book'], after=row['after_book'],
              fills=[(a['order_id'], a['side'], a['size']) for a in row['original_maker_fill_actions']],
              maker_queue=[(r['side'], r['original_full_price_level']['price_raw'],
                            [(q['order_id'], q['volume_ahead'], q['size']) for q in r['original_full_price_level']['fifo_queue']])
                           for r in row['original_maker_price_levels_before_trade']]), separators=(',', ':')))
