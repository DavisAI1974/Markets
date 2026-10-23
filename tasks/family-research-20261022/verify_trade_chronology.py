"""Verify all new annotations against saved originals, without rehashing sources."""
import collections
import csv
import json

from continue_trade_chronology import OUT, PARENT, clocks, jsonrows, save


def main():
    with (PARENT.parent / 'price-curve-timestamps.csv').open(newline='') as handle:
        original = list(csv.DictReader(handle))
    stretches = list(jsonrows(OUT / 'all-price-stretches.jsonl.gz'))
    legs = list(jsonrows(OUT / 'all-overlapping-print-legs.jsonl.gz'))
    seen = []
    turn_count = 0
    for i, stretch in enumerate(stretches):
        lo, hi = stretch['first_trade_ordinal'], stretch['last_trade_ordinal']
        assert stretch['stretch_ordinal'] == i
        assert all(int(original[n]['price_raw']) == stretch['price_raw'] for n in range(lo, hi + 1))
        assert lo == (0 if i == 0 else stretches[i - 1]['last_trade_ordinal'] + 1)
        assert stretch['first_exact_clocks'] == clocks(original[lo])
        assert stretch['last_exact_clocks'] == clocks(original[hi])
        if i:
            assert stretch['price_raw'] != stretches[i - 1]['price_raw']
        if i and i + 1 < len(stretches):
            before = int(original[lo]['price_raw']) - int(original[lo - 1]['price_raw'])
            after = int(original[hi + 1]['price_raw']) - int(original[hi]['price_raw'])
            assert stretch['print_direction_turn'] == (before * after < 0)
        turn_count += stretch['print_direction_turn'] is True
        seen.extend(range(lo, hi + 1))
    assert seen == list(range(30739))
    for i, leg in enumerate(legs):
        lo, hi = leg['first_stretch_ordinal'], leg['last_stretch_ordinal']
        assert hi > lo and leg['leg_ordinal'] == i
        changes = [stretches[n]['price_raw'] - stretches[n - 1]['price_raw'] for n in range(lo + 1, hi + 1)]
        assert all(change * leg['step_sign'] > 0 for change in changes)
        if i:
            assert legs[i - 1]['last_stretch_ordinal'] == lo
            assert legs[i - 1]['step_sign'] != leg['step_sign']
    assert legs[0]['first_stretch_ordinal'] == 0
    assert legs[-1]['last_stretch_ordinal'] == len(stretches) - 1
    counts = collections.Counter()
    for i, row in enumerate(jsonrows(OUT / 'every-trade-chronological-lifecycle.jsonl.gz')):
        assert row['trade_ordinal'] == i and row['original_trade'] == original[i]
        assert row['exact_clocks'] == clocks(original[i])
        assert all(type(v) is int for v in row['exact_clocks'].values())
        stretch = stretches[row['equal_price_stretch_ref']['line_number'] - 1]
        assert stretch['first_trade_ordinal'] <= i <= stretch['last_trade_ordinal']
        for ref in row['overlapping_print_leg_refs']:
            leg = legs[ref['line_number'] - 1]
            assert leg['first_trade_ordinal'] <= i <= leg['last_trade_ordinal']
        for name in ['original_evidence_bundle', 'original_second_set_ref', 'original_external_links_ref',
                     'original_root_measurement_links_ref', 'continuous_native_links_ref']:
            assert row[name]['line_number'] == i + 1 and (OUT / row[name]['file']).exists()
        assert row['lifecycle_status']['semantic_coverage'] == 'NOT_PASSED'
        assert row['all_later_evidence_eligible'] is True
        counts['trades'] += 1
        counts['with_exact_quote_order_context'] += row['checked_quote_order_role_context'] is not None
        if i in [0, 32, 33, 149, 150, 151, 152, 153, 154, 155, 30738]:
            print(json.dumps(dict(trade=i, price=original[i]['price'], stretch=stretch['stretch_ordinal'],
                                  next_different=row['next_different_price_trade_ordinal'],
                                  removal_refs=len(row['same_emission_recorded_removal_refs']))))
    assert counts['trades'] == 30739 and counts['with_exact_quote_order_context'] == 32
    save('verification.json', dict(status='PASSED_ALL_30739_ORIGINAL_TRADE_AND_PATH_CHECKS',
                                   counts=dict(counts), all_original_fields_compared=True,
                                   every_plateau_member_and_leg_step_checked=True,
                                   shared_turning_stretches_preserved=True, print_direction_turn_stretches=turn_count,
                                   exact_integer_clocks_checked=True, complete_later_tail_references=True,
                                   frozen_sources_rehashed=False, semantic_coverage='NOT_PASSED',
                                   mlp_reproducibility='UNRESOLVED'))


if __name__ == '__main__':
    main()
