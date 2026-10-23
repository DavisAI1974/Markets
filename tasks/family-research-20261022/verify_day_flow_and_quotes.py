"""Check new day-wide derivatives against unchanged saved source records."""
import bisect
import collections
from decimal import Decimal
import json
import re

from analyze_day_flow_and_quotes import BASE, OUT, TRADE, csv_rows, rows, save


def main():
    trades = list(csv_rows(BASE / 'price-curve-timestamps.csv'))
    nav = list(csv_rows(TRADE / 'all-30739-trades.csv.gz'))
    receive = [int(t['receive_ns']) for t in trades]
    seconds = collections.defaultdict(list)
    groups_with_trades = collections.defaultdict(list)
    for i, t in enumerate(trades):
        seconds[int(t['receive_ns']) // 1000000000].append(i)
        groups_with_trades[int(nav[i]['emission_group_source_ordinal'])].append(i)
    originals = list(rows(TRADE / 'source-flow_substrate.jsonl.gz'))
    flow = list(rows(OUT / 'all-8088-original-flow-seconds-with-tape.jsonl.gz'))
    assert len(flow) == len(originals) == 8088
    flow_counts = collections.Counter()
    for line, (new, old) in enumerate(zip(flow, originals), 1):
        assert new['original_flow_record'] == old
        assert new['original_ref']['line_number'] == line
        source = old['original_record']
        sec = source['second']
        assert new['all_original_fresh_tape_ordinals'] == seconds.get(sec, [])
        assert source['trades'] == len(new['all_original_fresh_tape_ordinals'])
        assert new['original_fresh_tape_size'] == sum(int(trades[i]['size']) for i in seconds.get(sec, []))
        lo = (sec - source['window_seconds'] + 1) * 1000000000
        hi = (sec + 1) * 1000000000
        assert new['rolling_window_bounds_ns'] == [lo, hi]
        left, right = bisect.bisect_left(receive, lo), bisect.bisect_left(receive, hi)
        assert new['all_original_window_tape_ordinal_range'] == (None if left == right else [left, right - 1])
        assert type(old['known_by_ns']) is int and type(old['input_cursor']) is int
        assert new['second_end_to_emission_ns'] == old['known_by_ns'] - hi >= 0
        expected_flags = []
        if not seconds.get(sec) and source['window_signed_flow'] != 0:
            expected_flags.append('NONZERO_ROLL_WITHOUT_NEW_TAPE')
        if seconds.get(sec) and source['window_signed_flow'] == 0:
            expected_flags.append('FRESH_TAPE_WITH_ZERO_ROLL')
        if source['net_volume'] * source['window_signed_flow'] < 0:
            expected_flags.append('FRESH_NET_OPPOSES_ROLL')
        assert sorted(new['interpretation_flags']) == sorted(expected_flags)
        flow_counts.update(expected_flags)
        flow_counts['records'] += 1

    endpoints = list(rows(BASE / 'enriched-v2/quote_endpoint_receipts.jsonl.gz'))
    window = list(csv_rows(BASE / 'timestamped-mbo-window-v1/consecutive_quote_books.csv.gz'))
    selected = list(rows(TRADE / 'chronological-lifecycle-v1/all-saved-selected-quote-views.jsonl.gz'))
    bounded = json.loads((TRADE / 'quote-order-gapfill-v1/each-trade-exact-quote-order-analysis.json').read_text())
    quotes = list(rows(OUT / 'all-saved-quote-source-views.jsonl.gz'))
    quote_lookup = {q['source_ordinal']: q for q in quotes}
    assert len(quotes) == len(quote_lookup) == 35147
    seen = set()
    total = 0
    for q in quotes + [dict(all_original_views=list(rows(OUT / 'all-unplaced-quote-endpoints.jsonl.gz')))]:
        for v in q['all_original_views']:
            ref = v['original_ref']
            name = ref['file']
            if name.endswith('quote_endpoint_receipts.jsonl.gz'):
                original = endpoints[ref['line_number'] - 1][ref['field']]
                key = (name, ref['line_number'], ref['field'])
            elif name.endswith('consecutive_quote_books.csv.gz'):
                original = window[ref['csv_data_row'] - 1]
                key = (name, ref['csv_data_row'])
            elif name.endswith('all-saved-selected-quote-views.jsonl.gz'):
                original = selected[ref['line_number'] - 1]
                key = (name, ref['line_number'])
            else:
                original = bounded[ref['array_ordinal']][ref['field']]
                key = (name, ref['array_ordinal'], ref['field'])
            assert key not in seen
            seen.add(key)
            assert v['original_quote_payload'] == original
            total += 1
            if 'source_ordinal' in q:
                g = q['original_group']
                assert int(g['source_ordinal']) == q['source_ordinal']
                assert v['reported_known_by_ns'] is None or v['reported_known_by_ns'] == int(g['known_by_ns'])
                assert v['reported_input_cursor'] is None or v['reported_input_cursor'] == int(g['input_cursor'])
                assert v['clock_match'] is True
                if name.endswith('all-saved-selected-quote-views.jsonl.gz'):
                    bid, ask = original['bid']['raw_integer'], original['ask']['raw_integer']
                else:
                    bid, ask = Decimal(str(original['best_bid'])) * 1000000000, Decimal(str(original['best_ask'])) * 1000000000
                assert bid == int(bid) == v['bid_raw'] and ask == int(ask) == v['ask_raw']
                assert (q['consensus']['bid_raw'], q['consensus']['ask_raw']) == (int(bid), int(ask))
                assert q['consensus']['status'] == 'CONSISTENT_EXACT_SAVED_QUOTES'
    assert total == len(endpoints) * 2 + len(window) + len(selected) + len(bounded) * 2 == 64757
    for g in csv_rows(BASE / 'descriptive-v1/retained_group_sequence.csv.gz'):
        ordinal = int(g['source_ordinal'])
        if ordinal in quote_lookup:
            assert quote_lookup[ordinal]['original_group'] == g

    history = json.loads((BASE / 'external-classroom-audit-v1/original_series_known_values.json').read_text())
    pubs = list(rows(OUT / 'all-declared-external-publications-during-tape.jsonl.gz'))
    stamps = [p['original_declared_publication_ns'] for p in pubs]
    assert stamps == sorted(set(stamps))
    observed = set()
    for line, pub in enumerate(pubs, 1):
        assert pub['publication_line'] == line and type(pub['original_declared_publication_ns']) is int
        for ref in pub['all_original_observation_refs']:
            series = history['series'][ref['source_series_index']]
            original = series['known'][ref['original_known_index']]
            key = ref['source_series_index'], ref['original_known_index']
            assert key not in observed
            observed.add(key)
            assert original['published_ns'] == pub['original_declared_publication_ns']
            assert series['name'] == ref['series_name'] and series['table'] == ref['original_table']
            for out, source in [('original_source_ordinal', 'source_ordinal'), ('original_state', 'state'), ('original_reason', 'reason'), ('original_value', 'value')]:
                assert ref[out] == original.get(source)
    assert observed == {(si, ki) for si, s in enumerate(history['series']) for ki, k in enumerate(s['known']) if receive[0] <= k['published_ns'] <= receive[-1]}

    comparisons = list(rows(OUT / 'every-trade-flow-and-expanded-quote-comparison.jsonl.gz'))
    assert len(comparisons) == len(trades) == 30739
    counts = collections.Counter()
    flow_lines_by_second = collections.defaultdict(list)
    for line, original in enumerate(originals, 1):
        flow_lines_by_second[original['original_record']['second']].append(line)
    for i, (new, old) in enumerate(zip(comparisons, trades)):
        assert new['original_trade'] == old and new['trade_ordinal'] == i
        for k, value in new['exact_clocks'].items():
            assert type(value) is int and value == int(old[k])
        before = quote_lookup.get(new['strict_prior_group_ordinal'])
        after = quote_lookup.get(new['emission_group_ordinal'])
        for prefix, source in [('prior', before), ('emission', after)]:
            for side in ('bid', 'ask'):
                assert new[f'{prefix}_{side}_raw'] == (source['consensus'][f'{side}_raw'] if source else None)
        step = None if i == 0 else int(old['price_raw']) - int(trades[i - 1]['price_raw'])
        assert new['previous_print_step_raw'] == step
        expected = []
        if before and after:
            b, a = before['consensus'], after['consensus']
            delta = a['bid_raw'] + a['ask_raw'] - b['bid_raw'] - b['ask_raw']
            assert new['group_twice_midpoint_change_raw'] == delta
            counts['paired_exact_uncrossed_quotes'] += 1
            if step not in (None, 0) and a == b:
                expected.append('PRINT_CHANGE_WITH_UNCHANGED_GROUP_QUOTES')
            if step is not None and step * delta < 0:
                expected.append('PRINT_STEP_OPPOSES_GROUP_MIDPOINT_CHANGE')
        assert sorted(expected) == sorted(new['interpretation_flags'])
        counts.update(expected)
        assert [r['line_number'] for r in new['original_own_second_flow_refs']] == flow_lines_by_second.get(int(old['receive_ns']) // 1000000000, [])
        counts['trades_with_saved_own_second_flow'] += bool(new['original_own_second_flow_refs'])
        for ref in new['original_own_second_flow_refs']:
            r = flow[ref['line_number'] - 1]['original_flow_record']
            assert r['original_record']['second'] == int(old['receive_ns']) // 1000000000
            assert ref['known_by_ns'] == r['known_by_ns'] and ref['input_cursor'] == r['input_cursor']
        lo = bisect.bisect_right(stamps, receive[i - 1]) if i else 0
        hi = bisect.bisect_right(stamps, receive[i])
        expected_pub_range = [lo + 1, hi] if i and hi > lo else None
        assert new['original_declared_publication_lines_since_previous_trade'] == expected_pub_range
        counts['trades_with_declared_publication_since_previous_trade'] += expected_pub_range is not None
        counts['trades_with_declared_non_curve_traded_publication_since_previous_trade'] += bool(expected_pub_range and any(
            any(o['original_table'] != 'curve.traded_shape' for o in pub['all_original_observation_refs'])
            for pub in pubs[expected_pub_range[0] - 1:expected_pub_range[1]]))
    runs = list(rows(OUT / 'all-consecutive-unchanged-group-quote-runs.jsonl.gz'))
    covered = set()
    for run in runs:
        ordinals = list(range(run['first_group_ordinal'], run['last_group_ordinal'] + 1))
        assert not covered.intersection(ordinals)
        covered.update(ordinals)
        assert run['complete_group_count'] == len(ordinals)
        members = [i for ordinal in ordinals for i in groups_with_trades.get(ordinal, [])]
        assert run['all_original_trade_ordinals'] == members
        for ordinal in ordinals:
            q = quote_lookup[ordinal]['consensus']
            assert run['bid_ask_raw'] == [q['bid_raw'], q['ask_raw']]
        steps = [int(trades[b]['price_raw']) - int(trades[a]['price_raw']) for a, b in zip(members, members[1:])]
        assert run['contains_both_rising_and_falling_prints'] == (any(s > 0 for s in steps) and any(s < 0 for s in steps))
    assert covered == set(quote_lookup)
    receipt = json.loads((OUT / 'analysis-receipt.json').read_text())
    assert dict(flow_counts) == receipt['flow_counts']
    for key, value in counts.items():
        assert value == receipt['trade_comparison_counts'][key]
    for path in [OUT / 'README.md', TRADE / 'README.md', TRADE / 'trade-lifecycle-handoff-20261023.md']:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                resolved = (path.parent / target.split('#')[0]).resolve()
                if resolved != (OUT / 'verification.json').resolve():
                    assert resolved.exists(), (path, target)
    save('verification.json', dict(status='PASSED_DERIVATIVE_PRESERVATION_CHECKS', original_trades_and_integer_clocks=30739,
         unchanged_nested_flow_records=8088, fresh_flow_trade_counts_match_tape=8088,
         individual_original_quote_views_verified=64757, quote_coordinates_verified=35147,
         external_publication_observation_refs_verified=len(observed), all_external_states_values_and_shared_clocks_retained=True,
         all_consecutive_quote_runs_verified=len(runs), original_master_unchanged=True,
         semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print((OUT / 'verification.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
