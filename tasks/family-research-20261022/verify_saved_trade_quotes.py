"""Check copied selected quote rows and every trade's new quote comparisons."""
import collections
import csv
import gzip
import json

from continue_trade_chronology import OUT, PARENT, clocks, jsonrows, save


def main():
    views = list(jsonrows(OUT / 'all-saved-selected-quote-views.jsonl.gz'))
    expected = {}
    for view in views:
        for field in ['original_best_bid_records', 'original_best_ask_records']:
            for r in view[field]:
                line = r['original_record_ref']['line_number']
                assert line not in expected
                assert int(r['original_record']['original_measurement_row']['source_ordinal']) == view['source_ordinal']
                expected[line] = r['original_record']
    checked = 0
    with gzip.open(PARENT / 'original-root-native-measurement-rows.jsonl.gz', 'rt') as handle:
        for line, raw in enumerate(handle, 1):
            if line in expected:
                assert json.loads(raw) == expected[line]
                checked += 1
    assert checked == len(expected) == 6634
    with (PARENT.parent / 'price-curve-timestamps.csv').open(newline='') as handle:
        originals = list(csv.DictReader(handle))
    groups = collections.defaultdict(set)
    counts = collections.Counter()
    for i, row in enumerate(jsonrows(OUT / 'every-trade-saved-quote-comparison.jsonl.gz')):
        assert row['trade_ordinal'] == i and row['exact_clocks'] == clocks(originals[i])
        assert row['price_raw'] == int(originals[i]['price_raw'])
        for field, prefix in [('original_prior_quote_view_ref', 'prior'), ('original_emission_quote_view_ref', 'emission')]:
            if row[field] is not None:
                v = views[row[field]['line_number'] - 1]
                assert row[prefix + '_bid_raw_from_decimal_text'] == v['bid']['raw_integer']
                assert row[prefix + '_ask_raw_from_decimal_text'] == v['ask']['raw_integer']
        if row['unchanged_paired_quotes'] is not None:
            before = (row['prior_bid_raw_from_decimal_text'], row['prior_ask_raw_from_decimal_text'])
            after = (row['emission_bid_raw_from_decimal_text'], row['emission_ask_raw_from_decimal_text'])
            assert row['unchanged_paired_quotes'] == (before == after)
            assert row['twice_midpoint_change_raw'] == sum(after) - sum(before)
        for flag in row['interpretation_flags']:
            counts[flag] += 1
            groups[flag].add(row['exact_clocks']['group_close_input_cursor'])
            if flag == 'PRINT_CHANGED_WITH_UNCHANGED_PAIRED_QUOTES':
                assert row['previous_print_step_raw'] != 0 and row['unchanged_paired_quotes'] is True
            if flag == 'PRINT_STEP_OPPOSED_PAIRED_MIDPOINT_CHANGE':
                assert row['previous_print_step_raw'] * row['twice_midpoint_change_raw'] < 0
        counts['all_trades'] += 1
    assert counts['all_trades'] == 30739
    result = dict(status='PASSED_ORIGINAL_SELECTED_QUOTE_ROWS_AND_ALL_TRADE_COMPARISONS',
                  original_quote_records_field_equal=checked, exact_trade_clocks_checked=30739,
                  flag_trade_counts=dict(counts), flag_unique_emission_groups={k: len(v) for k, v in groups.items()},
                  shared_group_contexts_are_not_independent=True,
                  frozen_source_hashes_repeated=False, semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    save('saved-quote-verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
