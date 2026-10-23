"""Verify retained local-liquidity paths and original-data navigation without a raw restore."""
import collections
from decimal import Decimal
import json
import re

from analyze_local_liquidity import BASE, OUT, TRADE, WINDOW, csv_rows, rows, save


def main():
    books = list(rows(OUT / 'all-22194-window-local-liquidity-books.jsonl.gz'))
    transitions = list(rows(OUT / 'all-22193-consecutive-local-liquidity-transitions.jsonl.gz'))
    original_quotes = list(csv_rows(WINDOW / 'consecutive_quote_books.csv.gz'))
    assert len(books) == len(original_quotes) == 22194 and len(transitions) == 22193
    by_ordinal = {b['source_ordinal']: b for b in books}
    near = collections.defaultdict(lambda: collections.defaultdict(list))
    count = 0
    for line, wrapper in enumerate(rows(OUT / 'all-original-first-ten-level-rows.jsonl.gz'), 1):
        r = wrapper['original_level']
        ordinal, side, rank = int(r['source_ordinal']), r['side'], int(r['rank'])
        book = by_ordinal[ordinal]
        side_meta = book['sides'][side]
        assert line == side_meta['near_original_record_lines'][0] + rank - 1
        assert wrapper['original_csv_data_row'] == side_meta['full_original_csv_data_row_range'][0] + rank - 1
        for field in ('input_cursor', 'known_by_ns', 'event_ns', 'receive_ns'):
            assert int(r[field]) == int(book['original_quote_book'][field])
        assert rank == len(near[ordinal][side]) + 1
        near[ordinal][side].append(r)
        count += 1
    assert count == 443880
    full_row_cursor = 1
    flags = collections.Counter()
    for book, original in zip(books, original_quotes):
        assert book['original_quote_book'] == original
        for side, prefix in [('B', 'bid'), ('A', 'ask')]:
            meta = book['sides'][side]
            levels = near[book['source_ordinal']][side]
            assert len(levels) == 10
            assert meta['original_touch_level'] == levels[0]
            assert meta['first_ten_size'] == sum(int(r['size']) for r in levels) == int(original[f'{prefix}_depth_n'])
            assert meta['full_size'] == int(original[f'{prefix}_depth_full'])
            lo, hi = meta['full_original_csv_data_row_range']
            assert lo == full_row_cursor and hi - lo + 1 == int(original[f'{prefix}_level_n'])
            full_row_cursor = hi + 1
        b, a = book['sides']['B'], book['sides']['A']
        assert book['full_size_skew'] == b['full_size'] - a['full_size']
        assert book['first_ten_size_skew'] == b['first_ten_size'] - a['first_ten_size']
        assert book['touch_size_skew'] == int(b['original_touch_level']['size']) - int(a['original_touch_level']['size'])
        expected = []
        if book['full_size_skew'] * book['touch_size_skew'] < 0:
            expected.append('FULL_BOOK_SIZE_SKEW_OPPOSES_TOUCH_SIZE_SKEW')
        if book['full_size_skew'] * book['first_ten_size_skew'] < 0:
            expected.append('FULL_BOOK_SIZE_SKEW_OPPOSES_FIRST_TEN_SIZE_SKEW')
        assert book['interpretation_flags'] == expected
        flags.update(expected)
    assert full_row_cursor - 1 == 10267320
    # Independent previously saved full-depth checkpoints, rather than a second full-stream read.
    checkpoints = 0
    for r in csv_rows(BASE / 'instance-market-review-20261023/instance-375-checkpoint-ladders.csv.gz'):
        ordinal, rank = int(r['source_ordinal']), int(r['rank'])
        if ordinal not in near or rank > 10:
            continue
        current = near[ordinal][r['side']][rank - 1]
        for key in ('price_raw', 'size', 'order_count', 'front_order_size', 'input_cursor', 'event_ns', 'receive_ns', 'known_by_ns'):
            assert Decimal(current[key]) == Decimal(r[key]), (ordinal, rank, key)
        checkpoints += 1
    assert checkpoints > 0
    trades = list(csv_rows(BASE / 'price-curve-timestamps.csv'))
    nav = list(csv_rows(TRADE / 'all-30739-trades.csv.gz'))
    old_comparisons = list(rows(TRADE / 'day-wide-mechanisms-v1/every-trade-flow-and-expanded-quote-comparison.jsonl.gz'))
    tape = collections.defaultdict(list)
    for i, t in enumerate(trades):
        tape[int(t['group_close_input_cursor'])].append(i)
    for line, (old, new, change) in enumerate(zip(books, books[1:], transitions), 1):
        assert change['before_group_ordinal'] == old['source_ordinal']
        assert change['after_group_ordinal'] == new['source_ordinal'] == old['source_ordinal'] + 1
        assert change['before_book_line'] == line and change['after_book_line'] == line + 1
        for prefix, book in [('before', old), ('after', new)]:
            for field in ('known_by_ns', 'input_cursor'):
                assert type(change[f'{prefix}_{field}']) is int
                assert change[f'{prefix}_{field}'] == int(book['original_quote_book'][field])
        assert change['original_trade_ordinals'] == tape.get(change['after_input_cursor'], [])
        if any(c['quote_step_raw'] for c in change['sides'].values()) and not change['original_trade_ordinals']:
            flags['QUOTE_CHANGE_IN_GROUP_WITH_NO_RECORDED_T'] += 1
        old_skew = old['full_size_skew']
        if change['twice_midpoint_step_raw'] * old_skew < 0:
            flags['PRIOR_FULL_SIZE_SKEW_OPPOSES_MIDPOINT_STEP'] += 1
        for side, c in change['sides'].items():
            ob, nb = old['sides'][side], new['sides'][side]
            assert c['old_best_raw'] == int(ob['original_touch_level']['price_raw'])
            assert c['new_best_raw'] == int(nb['original_touch_level']['price_raw'])
            assert c['quote_step_raw'] == c['new_best_raw'] - c['old_best_raw']
            assert c['old_touch_size_before'] == int(ob['original_touch_level']['size'])
            assert c['new_touch_size_after'] == int(nb['original_touch_level']['size'])
            assert c['full_size_before'] == ob['full_size'] and c['full_size_after'] == nb['full_size']
            assert c['first_ten_size_before'] == ob['first_ten_size'] and c['first_ten_size_after'] == nb['first_ten_size']
            if c['quote_step_raw'] == 0:
                assert c['unchanged_touch_size_change'] == int(nb['original_touch_level']['size']) - int(ob['original_touch_level']['size'])
                if c['unchanged_touch_size_change']:
                    flags[f'{side}_UNCHANGED_QUOTE_WITH_TOUCH_SIZE_CHANGE'] += 1
            else:
                flags[f'{side}_QUOTE_CHANGED'] += 1
                if c['new_best_equals_previous_second_level']:
                    flags[f'{side}_NEW_BEST_EQUALS_PRIOR_SECOND_LEVEL'] += 1
    membership = list(rows(OUT / 'all-22193-first-ten-membership-effects.jsonl.gz'))
    assert len(membership) == len(transitions)
    for line, (effects, transition) in enumerate(zip(membership, transitions), 1):
        assert effects['original_transition_line'] == line
        for side, effect in effects['sides'].items():
            old = {int(r['price_raw']): int(r['size']) for r in near[transition['before_group_ordinal']][side]}
            new = {int(r['price_raw']): int(r['size']) for r in near[transition['after_group_ordinal']][side]}
            assert effect['first_ten_size_change'] == sum(new.values()) - sum(old.values())
            assert effect['shared_price_size_change'] == sum(new[p] - old[p] for p in old.keys() & new.keys())
            assert effect['entering_prices_raw'] == sorted(new.keys() - old.keys())
            assert effect['leaving_prices_raw'] == sorted(old.keys() - new.keys())
            assert effect['first_ten_size_change'] == effect['shared_price_size_change'] + effect['entering_rank_window_size'] - effect['leaving_rank_window_size']
    paths = list(rows(OUT / 'all-window-constant-quote-liquidity-paths.jsonl.gz'))
    expected_first_line = 1
    for path in paths:
        assert path['first_book_line'] == expected_first_line
        group = books[path['first_book_line'] - 1:path['last_book_line']]
        expected_first_line = path['last_book_line'] + 1
        for side in ('B', 'A'):
            values = [int(b['sides'][side]['original_touch_level']['size']) for b in group]
            assert path['sides'][side]['all_step_changes'] == [b - a for a, b in zip(values, values[1:])]
            assert path['sides'][side]['endpoint_size_change'] == values[-1] - values[0]
        assert all([int(b['sides'][s]['original_touch_level']['price_raw']) for s in ('B', 'A')] == path['bid_ask_raw'] for b in group)
        assert path['all_original_trade_ordinals'] == [i for b in group for i in tape.get(int(b['original_quote_book']['input_cursor']), [])]
    assert expected_first_line == 22195
    selected = list(rows(OUT / 'all-selected-day-depth-views.jsonl.gz'))
    expected_measurements = {}
    for s in selected:
        for prefix in ('bid', 'ask'):
            values = {Decimal(r['original_record']['original_measurement_row']['value']) for r in s['all_original_measurements'][f'root.{prefix}_depth_full']}
            if len(values) == 1:
                value = next(iter(values))
                assert value == int(value) == s[f'{prefix}_full_size']
        assert s['full_size_skew'] == s['bid_full_size'] - s['ask_full_size']
        for group in s['all_original_measurements'].values():
            for record in group:
                key = record['original_ref']['line_number']
                assert key not in expected_measurements
                expected_measurements[key] = record['original_record']
    verified_measurements = 0
    for line, original in enumerate(rows(TRADE / 'original-root-native-measurement-rows.jsonl.gz'), 1):
        if line in expected_measurements:
            assert original == expected_measurements[line]
            verified_measurements += 1
    assert verified_measurements == len(expected_measurements) == 13268
    links = list(rows(OUT / 'every-trade-local-liquidity-links.jsonl.gz'))
    assert len(links) == len(trades) == 30739
    trade_counts = collections.Counter()
    for i, (r, original) in enumerate(zip(links, trades)):
        assert r['trade_ordinal'] == i and r['original_trade'] == original
        for field, value in r['exact_clocks'].items():
            assert type(value) is int and value == int(original[field])
        for prefix, nav_key in [('prior', 'pre_group_source_ordinal'), ('emission', 'emission_group_source_ordinal')]:
            line = r[f'{prefix}_selected_depth_line']
            if line is not None:
                assert selected[line - 1]['source_ordinal'] == int(nav[i][nav_key])
        line = r['window_transition_line']
        if line is not None:
            assert transitions[line - 1]['after_input_cursor'] == int(original['group_close_input_cursor'])
        assert old_comparisons[i]['exact_clocks'] == r['exact_clocks']
        pre = selected[r['prior_selected_depth_line'] - 1] if r['prior_selected_depth_line'] else None
        expected_flags = []
        if pre and pre['full_size_skew_opposes_source_depth_n_imbalance']:
            expected_flags.append('PRIOR_FULL_SIZE_SKEW_OPPOSES_SOURCE_DEPTH_N_SKEW')
        delta = old_comparisons[i]['group_twice_midpoint_change_raw']
        if pre and pre['full_size_skew'] is not None and delta is not None and pre['full_size_skew'] * delta < 0:
            expected_flags.append('PRIOR_FULL_SIZE_SKEW_OPPOSES_GROUP_MIDPOINT_CHANGE')
        assert r['interpretation_flags'] == expected_flags
        trade_counts.update(expected_flags)
        trade_counts['with_selected_prior_full_sizes'] += bool(pre and pre['bid_full_size'] is not None and pre['ask_full_size'] is not None)
        trade_counts['with_continuous_window_transition'] += r['window_transition_line'] is not None
    policy = json.loads((OUT / 'frankie-local-liquidity-use.json').read_text())
    brain = json.loads((BASE / 'full-context-audit/canonical-sources/research/kalshi/knowledge/ng_brain.json').read_text())
    claims = json.loads((TRADE / 'all-510-frankie-knowledge-claims.json').read_text())
    assert policy['original_book_play_with_contrary_audit'] == brain['plays'][1]
    for claim in policy['original_step_endpoint_claims']:
        assert claim['original_claim'] == claims[claim['original_array_ordinal']]
    receipt = json.loads((OUT / 'analysis-receipt.json').read_text())
    assert dict(flags) == receipt['window_counts']
    assert dict(trade_counts) == receipt['trade_counts']
    for doc in (OUT / 'README.md', TRADE / 'README.md', TRADE / 'trade-lifecycle-handoff-20261023.md'):
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                path = (doc.parent / target.split('#')[0]).resolve()
                if path != (OUT / 'verification.json').resolve():
                    assert path.exists(), (doc, target)
    save('verification.json', dict(status='PASSED_DERIVATIVE_AND_SOURCE_POINTER_CHECKS',
        original_trades_and_exact_integer_clocks=30739, unchanged_selected_original_measurements=verified_measurements,
        original_quote_book_rows=22194, original_near_level_rows_structurally_checked=count,
        original_full_level_rows_conserved_in_producer_pass=10267320,
        independent_saved_checkpoint_level_comparisons=checkpoints, consecutive_transitions_verified=22193,
        exact_first_ten_membership_decompositions_verified=44386, complete_constant_quote_paths=len(paths),
        original_frankie_play_audit_and_claims_preserved=True, no_source_rehash_or_second_full_level_stream=True,
        whole_day_causal_completion='UNFINISHED', quantity_gaps_119_134='UNRESOLVED',
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print((OUT / 'verification.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
