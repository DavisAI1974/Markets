"""Compare fixed-price liquidity in saved books; never infer action causes from deltas."""
import collections
from decimal import Decimal, InvalidOperation
import gzip
import io
import itertools
import json

from analyze_day_flow_and_quotes import BASE, TRADE, csv_rows, rows

OUT = TRADE / 'local-liquidity-v1'
WINDOW = BASE / 'timestamped-mbo-window-v1'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(name, values):
    with (OUT / name).open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
            for value in values:
                handle.write((json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode())


def exact_consensus(values, integral=False):
    try:
        numbers = [Decimal(v) for v in values]
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not numbers or any(not v.is_finite() for v in numbers) or len(set(numbers)) != 1:
        return None
    value = numbers[0]
    if integral:
        return int(value) if value == value.to_integral_value() else None
    return value


def sign(value):
    return (value > 0) - (value < 0)


def size_path_effect(sizes):
    steps = [b - a for a, b in zip(sizes, sizes[1:])]
    return dict(endpoint_size_change=sizes[-1] - sizes[0], all_step_changes=steps,
                positive_step_changes=[s for s in steps if s > 0], negative_step_changes=[s for s in steps if s < 0],
                both_size_increases_and_decreases=any(s > 0 for s in steps) and any(s < 0 for s in steps),
                equal_endpoints_with_intermediate_changes=sizes[-1] == sizes[0] and any(s != 0 for s in steps))


def rank_window_effect(before, after):
    old = {int(r['price_raw']): int(r['size']) for r in before[:10]}
    new = {int(r['price_raw']): int(r['size']) for r in after[:10]}
    shared, entering, leaving = set(old) & set(new), set(new) - set(old), set(old) - set(new)
    return dict(first_ten_size_change=sum(new.values()) - sum(old.values()),
                shared_price_size_change=sum(new[p] - old[p] for p in shared),
                entering_rank_window_size=sum(new[p] for p in entering), leaving_rank_window_size=sum(old[p] for p in leaving),
                entering_prices_raw=sorted(entering), leaving_prices_raw=sorted(leaving),
                shared_price_changes=[dict(price_raw=p, before_size=old[p], after_size=new[p]) for p in sorted(shared)],
                interpretation='Exact rank-window decomposition. Entry/exit from the first ten is not evidence of a new add/cancel; shared-price net changes do not establish order survival or gross executed volume.')


def side_transition(side, before, after):
    old_price, new_price = int(before[0]['price_raw']), int(after[0]['price_raw'])
    old_sizes = {int(r['price_raw']): int(r['size']) for r in before}
    new_sizes = {int(r['price_raw']): int(r['size']) for r in after}
    return dict(side=side, old_best_raw=old_price, new_best_raw=new_price,
                quote_step_raw=new_price - old_price,
                old_touch_size_before=old_sizes[old_price], old_touch_size_after=new_sizes.get(old_price, 0),
                new_touch_size_before=old_sizes.get(new_price, 0), new_touch_size_after=new_sizes[new_price],
                previous_second_level_price_raw=int(before[1]['price_raw']) if len(before) > 1 else None,
                new_best_equals_previous_second_level=len(before) > 1 and new_price == int(before[1]['price_raw']),
                unchanged_touch_size_change=new_sizes[new_price] - old_sizes[old_price] if old_price == new_price else None,
                full_size_before=sum(old_sizes.values()), full_size_after=sum(new_sizes.values()),
                first_ten_size_before=sum(int(r['size']) for r in before[:10]),
                first_ten_size_after=sum(int(r['size']) for r in after[:10]),
                interpretation='Fixed side and absolute price, using complete observed levels. Missing price means absent at this group close. Size differences do not allocate fills, cancellations, modifications or new order identities.')


class Parts(io.RawIOBase):
    def __init__(self, paths):
        self.paths, self.current = iter(paths), None

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            if self.current is None:
                try:
                    self.current = next(self.paths).open('rb')
                except StopIteration:
                    return 0
            n = self.current.readinto(buffer)
            if n:
                return n
            self.current.close()
            self.current = None

    def close(self):
        if self.current is not None:
            self.current.close()
        super().close()


def main():
    import csv
    OUT.mkdir(exist_ok=True)
    master = json.loads((BASE / 'completed-run-source-list.json').read_text())
    assert len(master['original_99_plane_records']) == 99
    trades = list(csv_rows(BASE / 'price-curve-timestamps.csv'))
    nav = list(csv_rows(TRADE / 'all-30739-trades.csv.gz'))
    compared = list(rows(TRADE / 'day-wide-mechanisms-v1/every-trade-flow-and-expanded-quote-comparison.jsonl.gz'))
    assert len(trades) == len(nav) == len(compared) == 30739
    trade_at = collections.defaultdict(list)
    for i, trade in enumerate(trades):
        trade_at[int(trade['group_close_input_cursor'])].append(i)
    lifecycle = collections.defaultdict(list)
    for section in ('queue', 'replenishment'):
        for line, r in enumerate(rows(TRADE / f'source-{section}.jsonl.gz'), 1):
            lifecycle[r['input_cursor']].append(dict(file=f'../source-{section}.jsonl.gz', line_number=line,
                record_sha256=r['record_sha256'], known_by_ns=r['known_by_ns'], input_cursor=r['input_cursor']))
    quote_books = {int(q['source_ordinal']): q for q in csv_rows(WINDOW / 'consecutive_quote_books.csv.gz')}
    book_rows, transitions, book_line = [], [], {}
    counts = collections.Counter()
    previous = None
    parts = [WINDOW / f'consecutive_bid_ask_levels.csv.gz.part{i:03d}' for i in range(1, 5)]
    level_count, near_count = 0, 0
    with io.BufferedReader(Parts(parts)) as stream, gzip.GzipFile(fileobj=stream) as gz, io.TextIOWrapper(gz, encoding='utf-8', newline='') as text:
        reader = enumerate(csv.DictReader(text), 1)
        with (OUT / 'all-original-first-ten-level-rows.jsonl.gz').open('wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as near_out:
                for ordinal, group in itertools.groupby(reader, key=lambda pair: int(pair[1]['source_ordinal'])):
                    all_levels = list(group)
                    level_count += len(all_levels)
                    quote = quote_books[ordinal]
                    by_side = {side: [(line, r) for line, r in all_levels if r['side'] == side] for side in ('B', 'A')}
                    sides = {}
                    for side, pairs in by_side.items():
                        assert [int(r['rank']) for _, r in pairs] == list(range(1, len(pairs) + 1))
                        levels = [r for _, r in pairs]
                        prices = [int(r['price_raw']) for r in levels]
                        assert len(set(prices)) == len(prices) and prices == sorted(prices, reverse=side == 'B')
                        name = 'bid' if side == 'B' else 'ask'
                        assert sum(int(r['size']) for r in levels) == int(quote[f'{name}_depth_full'])
                        assert sum(int(r['size']) for r in levels[:10]) == int(quote[f'{name}_depth_n'])
                        assert len(levels) == int(quote[f'{name}_level_n'])
                        assert Decimal(quote[f'best_{name}']) * 1000000000 == prices[0]
                        assert all(int(r['known_by_ns']) == int(quote['known_by_ns']) and int(r['input_cursor']) == int(quote['input_cursor']) for r in levels)
                        first_near = near_count + 1
                        for source_line, original in pairs[:10]:
                            near_count += 1
                            near_out.write((json.dumps(dict(original_csv_data_row=source_line, original_level=original), separators=(',', ':')) + '\n').encode())
                        sides[side] = dict(full_original_csv_data_row_range=[pairs[0][0], pairs[-1][0]],
                                           near_original_record_lines=[first_near, near_count],
                                           original_touch_level=levels[0], original_touch_csv_data_row=pairs[0][0],
                                           full_size=sum(int(r['size']) for r in levels),
                                           first_ten_size=sum(int(r['size']) for r in levels[:10]))
                    full_skew = sides['B']['full_size'] - sides['A']['full_size']
                    near_skew = sides['B']['first_ten_size'] - sides['A']['first_ten_size']
                    touch_skew = int(sides['B']['original_touch_level']['size']) - int(sides['A']['original_touch_level']['size'])
                    flags = []
                    if full_skew * touch_skew < 0:
                        flags.append('FULL_BOOK_SIZE_SKEW_OPPOSES_TOUCH_SIZE_SKEW')
                    if full_skew * near_skew < 0:
                        flags.append('FULL_BOOK_SIZE_SKEW_OPPOSES_FIRST_TEN_SIZE_SKEW')
                    counts.update(flags)
                    book_line[ordinal] = len(book_rows) + 1
                    book_rows.append(dict(source_ordinal=ordinal, original_quote_book=quote, sides=sides,
                        full_size_skew=full_skew, first_ten_size_skew=near_skew, touch_size_skew=touch_skew,
                        interpretation_flags=flags, original_trade_ordinals=trade_at.get(int(quote['input_cursor']), []),
                        original_full_level_source='../../timestamped-mbo-window-v1/consecutive_bid_ask_levels.csv.gz.part001 through part004; one concatenated gzip stream'))
                    if previous is not None:
                        old_ordinal, old_levels, old_quote = previous
                        assert ordinal == old_ordinal + 1
                        side_changes = {side: side_transition(side, [r for _, r in old_levels[side]], [r for _, r in by_side[side]]) for side in ('B', 'A')}
                        flags = []
                        midpoint2 = sum(c['quote_step_raw'] for c in side_changes.values())
                        if midpoint2 and int(old_quote['bid_depth_full']) != int(old_quote['ask_depth_full']) and midpoint2 * (int(old_quote['bid_depth_full']) - int(old_quote['ask_depth_full'])) < 0:
                            flags.append('PRIOR_FULL_SIZE_SKEW_OPPOSES_MIDPOINT_STEP')
                        for side, change in side_changes.items():
                            if change['quote_step_raw']:
                                counts[f'{side}_QUOTE_CHANGED'] += 1
                                if change['new_best_equals_previous_second_level']:
                                    counts[f'{side}_NEW_BEST_EQUALS_PRIOR_SECOND_LEVEL'] += 1
                            elif change['unchanged_touch_size_change']:
                                counts[f'{side}_UNCHANGED_QUOTE_WITH_TOUCH_SIZE_CHANGE'] += 1
                        tape = trade_at.get(int(quote['input_cursor']), [])
                        if any(c['quote_step_raw'] for c in side_changes.values()) and not tape:
                            flags.append('QUOTE_CHANGE_IN_GROUP_WITH_NO_RECORDED_T')
                        counts.update(flags)
                        transitions.append(dict(before_group_ordinal=old_ordinal, after_group_ordinal=ordinal,
                            before_book_line=book_line[old_ordinal], after_book_line=book_line[ordinal],
                            before_known_by_ns=int(old_quote['known_by_ns']), after_known_by_ns=int(quote['known_by_ns']),
                            before_input_cursor=int(old_quote['input_cursor']), after_input_cursor=int(quote['input_cursor']),
                            sides=side_changes, twice_midpoint_step_raw=midpoint2, original_trade_ordinals=tape,
                            same_emission_lifecycle_refs=lifecycle.get(int(quote['input_cursor']), []),
                            interpretation_flags=flags, causation='UNALLOCATED: complete-group snapshots plus any saved lifecycle refs; no automatic fill/cancel/replenishment or order-survival inference'))
                    previous = ordinal, by_side, quote
                    if len(book_rows) % 5000 == 0:
                        print(f'Checked {len(book_rows)} complete saved books.', flush=True)
    assert level_count == 10267320 and len(book_rows) == 22194 and len(transitions) == 22193
    write_rows('all-22194-window-local-liquidity-books.jsonl.gz', book_rows)
    write_rows('all-22193-consecutive-local-liquidity-transitions.jsonl.gz', transitions)

    # Existing selected scalar data extends the comparison outside the continuous window.
    features = ('root.bid_depth_full', 'root.ask_depth_full', 'root.depth_imbalance_n', 'root.depth_imbalance_full')
    selected = collections.defaultdict(lambda: collections.defaultdict(list))
    for line, wrapper in enumerate(rows(TRADE / 'original-root-native-measurement-rows.jsonl.gz'), 1):
        r = wrapper['original_measurement_row']
        if r['feature'] in features:
            selected[int(r['source_ordinal'])][r['feature']].append(dict(original_record=wrapper,
                original_ref=dict(file='../original-root-native-measurement-rows.jsonl.gz', line_number=line)))
    selected_rows, selected_lookup = [], {}
    for ordinal, fields in sorted(selected.items()):
        values = {f: exact_consensus([r['original_record']['original_measurement_row']['value'] for r in fields[f]], integral=f.endswith('_full') and 'imbalance' not in f) for f in features}
        bid, ask = values['root.bid_depth_full'], values['root.ask_depth_full']
        skew = None if bid is None or ask is None else bid - ask
        n_value = values['root.depth_imbalance_n']
        selected_lookup[ordinal] = len(selected_rows) + 1
        selected_rows.append(dict(source_ordinal=ordinal, all_original_measurements=fields,
            bid_full_size=bid, ask_full_size=ask, full_size_skew=skew,
            source_depth_n_imbalance_sign=None if n_value is None else sign(n_value),
            full_size_skew_opposes_source_depth_n_imbalance=None if skew is None or n_value is None else skew * n_value < 0,
            interpretation='Repeated observations retained; no averaging. Producer depth_n meaning is not broadened beyond independently checked scopes.'))
    write_rows('all-selected-day-depth-views.jsonl.gz', selected_rows)
    transition_lookup = {r['after_group_ordinal']: i for i, r in enumerate(transitions, 1)}
    trade_counts = collections.Counter()
    all_trade_rows = []
    for i, (trade, navigation, quote) in enumerate(zip(trades, nav, compared)):
        assert quote['original_trade'] == trade
        prior = int(navigation['pre_group_source_ordinal']) if navigation['pre_group_source_ordinal'] else None
        emission = int(navigation['emission_group_source_ordinal'])
        pre_line, close_line = selected_lookup.get(prior), selected_lookup.get(emission)
        pre = selected_rows[pre_line - 1] if pre_line else None
        flags = []
        if pre and pre['full_size_skew_opposes_source_depth_n_imbalance']:
            flags.append('PRIOR_FULL_SIZE_SKEW_OPPOSES_SOURCE_DEPTH_N_SKEW')
        delta = quote['group_twice_midpoint_change_raw']
        if pre and pre['full_size_skew'] is not None and delta is not None and pre['full_size_skew'] * delta < 0:
            flags.append('PRIOR_FULL_SIZE_SKEW_OPPOSES_GROUP_MIDPOINT_CHANGE')
        trade_counts.update(flags)
        trade_counts['with_selected_prior_full_sizes'] += bool(pre and pre['bid_full_size'] is not None and pre['ask_full_size'] is not None)
        trade_counts['with_continuous_window_transition'] += emission in transition_lookup
        all_trade_rows.append(dict(trade_ordinal=i, original_trade=trade, exact_clocks=quote['exact_clocks'],
            prior_selected_depth_line=pre_line, emission_selected_depth_line=close_line,
            selected_depth_file='all-selected-day-depth-views.jsonl.gz', window_book_line=book_line.get(emission),
            window_transition_line=transition_lookup.get(emission), interpretation_flags=flags,
            previous_whole_day_evidence_ref=dict(file='../day-wide-mechanisms-v1/every-trade-flow-and-expanded-quote-comparison.jsonl.gz', line_number=i + 1),
            knowledge_policy='frankie-local-liquidity-use.json', semantic_coverage='NOT_PASSED',
            limitation='Full-size skew is resting liquidity, not fresh aggression or a universal direction rule. All unobserved, later and contradictory original evidence remains eligible.'))
    write_rows('every-trade-local-liquidity-links.jsonl.gz', all_trade_rows)
    brain_path = BASE / 'full-context-audit/canonical-sources/research/kalshi/knowledge/ng_brain.json'
    brain = json.loads(brain_path.read_text())
    assert brain['plays'][1]['id'] == 'direction.book_contrarian'
    claims = json.loads((TRADE / 'all-510-frankie-knowledge-claims.json').read_text())
    save('frankie-local-liquidity-use.json', dict(
        controlling_master='../../completed-run-source-list.json', all_original_claims='../all-510-frankie-knowledge-claims.json',
        original_brain_file='../../full-context-audit/canonical-sources/research/kalshi/knowledge/ng_brain.json',
        original_book_play_array_ordinal=1, original_book_play_with_contrary_audit=brain['plays'][1],
        original_step_endpoint_claims=[dict(original_array_ordinal=i, original_claim=claims[i]) for i in (0, 2, 8)],
        application=['Keep resting-book size distinct from aggressor flow; retain the PROVISIONAL/UNCLEAR audit and narrow original trigger.',
                     'Inspect fixed-price step sequences as well as endpoints; do not turn far-book co-movement into touch-order identity.',
                     'Compare touch, first ten and full depth separately; preserve both confirming and opposing observations.',
                     'No claim to have tested the original book-contrarian rule, its flat-flow trigger, or its leg population.'],
        all_later_knowledge_eligible=True, semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    save('analysis-receipt.json', dict(
        source_master='../../completed-run-source-list.json', original_source_roles=99, original_master_unchanged=True,
        trades=30739, dropped_trades=0, original_level_rows_streamed=level_count, original_near_level_rows_saved=near_count,
        complete_window_books=len(book_rows), consecutive_window_transitions=len(transitions),
        window_counts=dict(counts), selected_depth_source_ordinals=len(selected_rows),
        selected_original_measurements=sum(len(records) for fields in selected.values() for records in fields.values()),
        trade_counts=dict(trade_counts), new_causal_resolutions=0, original_actions_and_contradictions_retained=True,
        raw_market_journal_reads=0, frozen_source_hash_repeats=0, aws_operations=0, refits=0, averaging=False,
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print(json.dumps(dict(window=counts, trade=trade_counts, selected_depth_ordinals=len(selected_rows))), flush=True)
    annotate_quote_plateaus()


def annotate_quote_plateaus():
    books = list(rows(OUT / 'all-22194-window-local-liquidity-books.jsonl.gz'))
    runs = []
    for line, book in enumerate(books, 1):
        quote = book['original_quote_book']
        pair = [int(book['sides'][s]['original_touch_level']['price_raw']) for s in ('B', 'A')]
        if runs and pair == runs[-1]['bid_ask_raw'] and book['source_ordinal'] == runs[-1]['last_group_ordinal'] + 1:
            runs[-1].update(last_group_ordinal=book['source_ordinal'], last_book_line=line)
        else:
            runs.append(dict(run_ordinal=len(runs), first_group_ordinal=book['source_ordinal'], last_group_ordinal=book['source_ordinal'],
                             first_book_line=line, last_book_line=line, bid_ask_raw=pair))
    counts = collections.Counter()
    for run in runs:
        selected = books[run['first_book_line'] - 1:run['last_book_line']]
        run['sides'] = {s: size_path_effect([int(b['sides'][s]['original_touch_level']['size']) for b in selected]) for s in ('B', 'A')}
        run['all_original_trade_ordinals'] = [i for b in selected for i in b['original_trade_ordinals']]
        run['internal_transition_line_range'] = None if len(selected) == 1 else [run['first_book_line'], run['last_book_line'] - 1]
        run['interpretation'] = 'All fixed-price displayed-size steps retained. Endpoint equality does not imply unchanged depth or orders; positive/negative snapshot steps are not gross additions, executions or cancellations.'
        counts['runs'] += 1
        counts['runs_with_multiple_books'] += len(selected) > 1
        for side, effect in run['sides'].items():
            counts[f'{side}_BOTH_SIZE_INCREASES_AND_DECREASES'] += effect['both_size_increases_and_decreases']
            counts[f'{side}_EQUAL_ENDPOINTS_WITH_INTERMEDIATE_CHANGES'] += effect['equal_endpoints_with_intermediate_changes']
    write_rows('all-window-constant-quote-liquidity-paths.jsonl.gz', runs)
    receipt = json.loads((OUT / 'analysis-receipt.json').read_text())
    receipt['constant_quote_size_path_counts'] = dict(counts)
    thin = collections.Counter()
    for transition in rows(OUT / 'all-22193-consecutive-local-liquidity-transitions.jsonl.gz'):
        for side, change in transition['sides'].items():
            if change['old_touch_size_before'] == 1:
                outcome = 'UNCHANGED' if change['quote_step_raw'] == 0 else ('HIGHER' if change['quote_step_raw'] > 0 else 'LOWER')
                thin[f'{side}_SIZE_1_TOUCH_NEXT_BEST_{outcome}'] += 1
    receipt['all_size_one_touch_outcomes'] = dict(thin)
    near_by_book = collections.defaultdict(lambda: collections.defaultdict(list))
    for wrapper in rows(OUT / 'all-original-first-ten-level-rows.jsonl.gz'):
        r = wrapper['original_level']
        near_by_book[int(r['source_ordinal'])][r['side']].append(r)
    memberships, membership_counts = [], collections.Counter()
    for line, transition in enumerate(rows(OUT / 'all-22193-consecutive-local-liquidity-transitions.jsonl.gz'), 1):
        effects = {s: rank_window_effect(near_by_book[transition['before_group_ordinal']][s], near_by_book[transition['after_group_ordinal']][s]) for s in ('B', 'A')}
        for s, effect in effects.items():
            assert effect['first_ten_size_change'] == effect['shared_price_size_change'] + effect['entering_rank_window_size'] - effect['leaving_rank_window_size']
            change = transition['sides'][s]
            if (s == 'B' and change['quote_step_raw'] < 0) or (s == 'A' and change['quote_step_raw'] > 0):
                if effect['first_ten_size_change'] > 0:
                    membership_counts[f'{s}_WORSE_QUOTE_WITH_FIRST_TEN_SIZE_INCREASE'] += 1
                    if effect['shared_price_size_change'] <= 0:
                        membership_counts[f'{s}_INCREASE_WITH_NONPOSITIVE_SHARED_PRICE_CHANGE'] += 1
        memberships.append(dict(original_transition_line=line, before_group_ordinal=transition['before_group_ordinal'],
                                after_group_ordinal=transition['after_group_ordinal'], sides=effects))
    write_rows('all-22193-first-ten-membership-effects.jsonl.gz', memberships)
    receipt['rank_window_membership_counts'] = dict(membership_counts)
    save('analysis-receipt.json', receipt)
    print(json.dumps(dict(constant_quote_size_paths=counts, size_one_touch_outcomes=thin, rank_window_membership=membership_counts)), flush=True)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--paths-only']:
        annotate_quote_plateaus()
    elif sys.argv[1:]:
        raise SystemExit('Only --paths-only is supported; default reads the saved projections.')
    else:
        main()
