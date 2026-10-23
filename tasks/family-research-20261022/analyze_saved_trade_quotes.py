"""Interpret only already saved selected quote measurements, preserving every row."""
import collections
import csv
from decimal import Decimal, InvalidOperation
import gzip
import json

from continue_trade_chronology import PARENT, clocks, jsonrows, save, write_rows

OUT = PARENT / 'chronological-lifecycle-v1'


def exact_projected_quote(values):
    if not values:
        return dict(status='NOT_MATERIALIZED_IN_SAVED_PROJECTION', raw_integer=None)
    numbers = []
    for value in values:
        try:
            number = Decimal(value) * 1_000_000_000
        except InvalidOperation:
            return dict(status='INVALID_SCALAR_RETAINED', raw_integer=None)
        if not number.is_finite() or number != number.to_integral_value():
            return dict(status='NONEXACT_OR_NONFINITE_SCALAR_RETAINED', raw_integer=None)
        numbers.append(int(number))
    if len(set(numbers)) != 1:
        return dict(status='CONFLICTING_ORIGINAL_VALUES_RETAINED', raw_integer=None)
    return dict(status='EXACT_INTEGER_FROM_ORIGINAL_DECIMAL_TEXT', raw_integer=numbers[0])


def quote_position(price, bid, ask):
    if bid is None or ask is None:
        return 'MISSING_PRIOR_QUOTE'
    if bid >= ask:
        return 'LOCKED_OR_CROSSED_PRIOR_QUOTE'
    if price < bid:
        return 'BELOW_PRIOR_BID'
    if price == bid:
        return 'AT_PRIOR_BID'
    if price < ask:
        return 'INSIDE_PRIOR_SPREAD'
    return 'AT_PRIOR_ASK' if price == ask else 'ABOVE_PRIOR_ASK'


def main():
    with gzip.open(PARENT / 'all-30739-trades.csv.gz', 'rt', newline='') as handle:
        trades = list(csv.DictReader(handle))
    assert len(trades) == 30739
    selected = collections.defaultdict(lambda: collections.defaultdict(list))
    record_count = 0
    # This is the existing 1,872,499-row materialized projection, not a raw ledger/DB scan.
    for line_number, wrapper in enumerate(jsonrows(PARENT / 'original-root-native-measurement-rows.jsonl.gz'), 1):
        row = wrapper['original_measurement_row']
        if row['feature'] not in ['root.best_bid', 'root.best_ask']:
            continue
        selected[int(row['source_ordinal'])][row['feature']].append(dict(
            original_record=wrapper,
            original_record_ref=dict(file='../original-root-native-measurement-rows.jsonl.gz', line_number=line_number)))
        record_count += 1
    views = []
    view_lookup = {}
    for ordinal, features in sorted(selected.items()):
        view = dict(source_ordinal=ordinal,
                    original_best_bid_records=features['root.best_bid'],
                    original_best_ask_records=features['root.best_ask'],
                    bid=exact_projected_quote([r['original_record']['original_measurement_row']['value'] for r in features['root.best_bid']]),
                    ask=exact_projected_quote([r['original_record']['original_measurement_row']['value'] for r in features['root.best_ask']]),
                    scope='ORIGINAL_SELECTED_SCALAR_PROJECTION; exact decimal conversion does not certify raw producer precision or channel completeness')
        view_lookup[ordinal] = (len(views) + 1, view)
        views.append(view)
    write_rows('all-saved-selected-quote-views.jsonl.gz', views)
    counts = collections.Counter()
    examples = collections.defaultdict(list)

    def get_view(ordinal):
        found = view_lookup.get(int(ordinal)) if ordinal else None
        if found is None:
            return None, None, None
        line_number, view = found
        return dict(file='all-saved-selected-quote-views.jsonl.gz', line_number=line_number), view['bid']['raw_integer'], view['ask']['raw_integer']

    def comparisons():
        previous_price = None
        for i, trade in enumerate(trades):
            before_ref, bid, ask = get_view(trade['pre_group_source_ordinal'])
            after_ref, after_bid, after_ask = get_view(trade['emission_group_source_ordinal'])
            price = int(trade['price_raw'])
            position = quote_position(price, bid, ask)
            counts[position] += 1
            same = None
            delta2 = None
            if None not in [bid, ask, after_bid, after_ask] and bid < ask and after_bid < after_ask:
                same = bid == after_bid and ask == after_ask
                delta2 = after_bid + after_ask - bid - ask
                counts['paired_uncrossed_quotes'] += 1
            print_step = None if previous_price is None else price - previous_price
            flags = []
            if print_step is not None and same and print_step != 0:
                flags.append('PRINT_CHANGED_WITH_UNCHANGED_PAIRED_QUOTES')
            if print_step is not None and delta2 is not None and print_step * delta2 < 0:
                flags.append('PRINT_STEP_OPPOSED_PAIRED_MIDPOINT_CHANGE')
            for flag in flags:
                counts[flag] += 1
                # Examples only; the complete population and flags remain in the JSONL.
                if len(examples[flag]) < 5:
                    examples[flag].append(i)
            prior = None if not trade['pre_group_known_by_ns'] else dict(
                source_ordinal=int(trade['pre_group_source_ordinal']),
                known_by_ns=int(trade['pre_group_known_by_ns']), input_cursor=int(trade['pre_group_input_cursor']),
                age_at_trade_receive_ns=int(trade['receive_ns']) - int(trade['pre_group_known_by_ns']))
            if prior:
                assert prior['known_by_ns'] < int(trade['receive_ns'])
                assert prior['input_cursor'] < int(trade['trade_input_cursor'])
            yield dict(trade_ordinal=i, original_trade_ref=dict(file='../every-trade-evidence-bundle.jsonl.gz', line_number=i + 1),
                       exact_clocks=clocks(trade), price_raw=price, original_strict_prior_group=prior,
                       original_prior_quote_view_ref=before_ref, original_emission_quote_view_ref=after_ref,
                       prior_bid_raw_from_decimal_text=bid, prior_ask_raw_from_decimal_text=ask,
                       emission_bid_raw_from_decimal_text=after_bid, emission_ask_raw_from_decimal_text=after_ask,
                       observed_position_relative_to_prior_quote=position, unchanged_paired_quotes=same,
                       twice_midpoint_change_raw=delta2, previous_print_step_raw=print_step, interpretation_flags=flags,
                       source_completeness='Selected saved quote contexts only; no inferred aggressor, order mechanism, or exhaustion',
                       semantic_coverage='NOT_PASSED')
            previous_price = price
        assert sum(counts[p] for p in ['BELOW_PRIOR_BID', 'AT_PRIOR_BID', 'INSIDE_PRIOR_SPREAD', 'AT_PRIOR_ASK',
                                      'ABOVE_PRIOR_ASK', 'MISSING_PRIOR_QUOTE', 'LOCKED_OR_CROSSED_PRIOR_QUOTE']) == 30739
    write_rows('every-trade-saved-quote-comparison.jsonl.gz', comparisons())
    save('saved-quote-comparison-receipt.json', dict(
        status='ALL_TRADES_RETAINED_WITH_SAVED_SELECTED_QUOTE_COMPARISONS', trades=30739,
        original_quote_measurement_records_retained=record_count, source_ordinals_with_saved_quote_rows=len(views),
        counts=dict(counts), example_trade_ordinals=dict(examples),
        original_quote_rows_retained_individually=True, scalar_values_never_averaged_or_rounded=True,
        source_scope='Existing selected-context export only; no raw ledger/database/archive scan',
        aws_operations=0, source_retrieval=False, model_fits=0, semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print(json.dumps(dict(quote_records=record_count, quote_source_ordinals=len(views), counts=counts, examples=examples)))


if __name__ == '__main__':
    main()
