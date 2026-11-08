"""Audit saved touch changes and replay two working rules with exact quote clocks."""
from bisect import bisect_left
from collections import Counter, defaultdict
import gzip
import json

from analyze_local_liquidity import OUT, sign
from analyze_day_flow_and_quotes import rows

BOOKS = 'all-22194-window-local-liquidity-books.jsonl.gz'
TRANSITIONS = 'all-22193-consecutive-local-liquidity-transitions.jsonl.gz'
MEMBERSHIP = 'all-22193-first-ten-membership-effects.jsonl.gz'
TRADES = 'every-trade-local-liquidity-links.jsonl.gz'
DEST = OUT.parent / 'historical-paper-replay-v1'
ENTRY_DELAY_NS = 1_000_000
HORIZONS_S = (1, 5, 30)


def geometry(side, view):
    retreat = -1 if side == 'B' else 1
    step = sign(view['quote_step_raw'])
    if not step:
        return 'stable_size_changed' if view['unchanged_touch_size_change'] else 'stable_size_unchanged'
    if step != retreat:
        return 'improved_old_touch_remains' if view['old_touch_size_after'] else 'improved_old_touch_also_gone'
    if view['old_touch_size_after']:
        raise ValueError('a worse complete best cannot coexist with the old best on that side')
    if view['new_best_equals_previous_second_level']:
        return 'retreat_to_previous_second'
    return 'retreat_to_deeper_prior_level' if view['new_touch_size_before'] else 'retreat_to_new_level'


def point(book, line):
    original = book['original_quote_book']
    return dict(book_line=line, group=book['source_ordinal'], cursor=int(original['input_cursor']),
                event_ns=int(original['event_ns']), receive_ns=int(original['receive_ns']),
                known_by_ns=int(original['known_by_ns']),
                bid_raw=int(book['sides']['B']['original_touch_level']['price_raw']),
                ask_raw=int(book['sides']['A']['original_touch_level']['price_raw']))


def thin_episode_end(books, points, index, side, direction):
    price_key = 'bid_raw' if side == 'B' else 'ask_raw'
    price = points[index][price_key]
    for i in range(index + 1, len(points)):
        end = points[i]
        price_step = direction * (end[price_key] - price)
        if price_step:
            return dict(status='RETREATED' if price_step > 0 else 'IMPROVED', quote=end)
        if int(books[i]['sides'][side]['original_touch_level']['size']) != 1:
            return dict(status='SIZE_RECOVERED_AT_SAME_PRICE', quote=end)
    return dict(status='WINDOW_CENSORED', quote=None)


def replay(points, clocks, index, direction):
    signal = points[index]
    start = bisect_left(clocks, signal['known_by_ns'] + ENTRY_DELAY_NS, lo=index + 1)
    entry = points[start] if start < len(points) else None
    outcomes = {}
    for horizon in HORIZONS_S:
        if entry is None:
            outcomes[horizon] = dict(status='ENTRY_CENSORED')
            continue
        stop = bisect_left(clocks, entry['known_by_ns'] + horizon * 1_000_000_000, lo=start + 1)
        if stop == len(points):
            outcomes[horizon] = dict(status='EXIT_CENSORED')
            continue
        exit_quote = points[stop]
        mid_delta2 = exit_quote['bid_raw'] + exit_quote['ask_raw'] - entry['bid_raw'] - entry['ask_raw']
        quote_pnl = (exit_quote['bid_raw'] - entry['ask_raw'] if direction == 1
                     else entry['bid_raw'] - exit_quote['ask_raw'])
        outcomes[horizon] = dict(status='OBSERVED', exit=exit_quote,
                                 signed_twice_midpoint_change_raw=direction * mid_delta2,
                                 cross_spread_pnl_raw=quote_pnl)
    return entry, outcomes


def save_rows(path, values):
    with path.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
        for value in values:
            handle.write((json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode())


def main():
    books = list(rows(OUT / BOOKS))
    points = [point(book, line) for line, book in enumerate(books, 1)]
    clocks = [p['known_by_ns'] for p in points]
    assert len(points) == 22194 and all(p['bid_raw'] < p['ask_raw'] for p in points)
    assert len({b['original_quote_book']['instrument_id'] for b in books}) == 1
    for prev, cur in zip(points, points[1:]):
        assert prev['group'] + 1 == cur['group'] and prev['cursor'] < cur['cursor']
        assert prev['known_by_ns'] <= cur['known_by_ns']
    trade_links = list(rows(OUT / TRADES))
    assert [int(r['original_trade']['source_ordinal']) for r in trade_links] == list(range(30739))
    assert all(r['trade_ordinal'] == i for i, r in enumerate(trade_links))
    signals, audit = [], []
    geometry_counts, same_group_tape = defaultdict(Counter), defaultdict(Counter)
    outcomes = defaultdict(lambda: defaultdict(Counter))
    thin_end_counts, thin_end_by_entry = Counter(), Counter()
    for index, (transition, rank) in enumerate(zip(rows(OUT / TRANSITIONS), rows(OUT / MEMBERSHIP), strict=True), 1):
        before, after = points[index - 1:index + 1]
        assert (transition['before_group_ordinal'], transition['after_group_ordinal']) == (before['group'], after['group'])
        assert (transition['before_input_cursor'], transition['after_input_cursor']) == (before['cursor'], after['cursor'])
        assert (transition['before_known_by_ns'], transition['after_known_by_ns']) == (before['known_by_ns'], after['known_by_ns'])
        assert rank['original_transition_line'] == index
        tape = transition['original_trade_ordinals']
        assert tape == books[index]['original_trade_ordinals']
        classifications = {}
        for side, view in transition['sides'].items():
            kind = geometry(side, view)
            classifications[side] = kind
            geometry_counts[side][kind] += 1
            same_group_tape[side][kind] += bool(tape)
            thin_start = view['new_touch_size_after'] == 1 and (
                view['old_touch_size_before'] != 1 or view['quote_step_raw'] != 0)
            for fires, rule in ((thin_start, 'size_one_touch_onset'),
                                (kind == 'retreat_to_previous_second', 'retreat_to_previous_second')):
                if not fires:
                    continue
                direction = -1 if side == 'B' else 1
                entry, future = replay(points, clocks, index, direction)
                signal = dict(rule=rule, side=side, direction=direction, transition_line=index,
                              signal=after, entry=entry, outcomes=future)
                if rule == 'size_one_touch_onset':
                    episode_end = thin_episode_end(books, points, index, side, direction)
                    signal['thin_episode_end'] = episode_end
                    thin_end_counts[episode_end['status']] += 1
                    if entry is not None and episode_end['quote'] is not None and episode_end['quote']['cursor'] <= entry['cursor']:
                        thin_end_by_entry[episode_end['status']] += 1
                signals.append(signal)
                for horizon, result in future.items():
                    counts = outcomes[rule][horizon]
                    counts[result['status']] += 1
                    if result['status'] == 'OBSERVED':
                        for metric in ('signed_twice_midpoint_change_raw', 'cross_spread_pnl_raw'):
                            counts[f"{metric}_{sign(result[metric])}"] += 1
        audit.append(dict(source_transition_line=index, before_group=before['group'], after_group=after['group'],
                          sides=classifications, original_trade_ordinals=tape))
    assert len(audit) == len(books) - 1
    for row in audit:
        for ordinal in row['original_trade_ordinals']:
            assert trade_links[ordinal]['window_transition_line'] == row['source_transition_line']
    DEST.mkdir(exist_ok=True)
    save_rows(DEST / 'every-saved-window-transition-classification.jsonl.gz', audit)
    save_rows(DEST / 'every-paper-signal-and-outcome.jsonl.gz', signals)
    receipt = dict(trading_session='20231018', source_files=[BOOKS, TRANSITIONS, MEMBERSHIP, TRADES],
                   original_trades_retained=len(trade_links), observed_books=len(points),
                   first_book=points[0], last_book=points[-1], transitions=len(audit),
                   geometry_counts=geometry_counts, groups_with_original_t=same_group_tape,
                   signal_counts=Counter(s['rule'] for s in signals), entry_delay_ns=ENTRY_DELAY_NS,
                   hold_seconds=HORIZONS_S, outcomes=outcomes,
                   thin_episode_end_counts=thin_end_counts, thin_episode_end_by_entry=thin_end_by_entry,
                   master='../../completed-run-source-list.json',
                   frankie='../local-liquidity-v1/frankie-local-liquidity-use.json',
                   oct03_status='PROTOCOL_READY_SOURCE_BYTES_UNAVAILABLE',
                   semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (DEST / 'receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
