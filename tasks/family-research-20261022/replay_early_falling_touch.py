"""Replay earlier falling-size onsets without conditioning on later thinness."""
from collections import Counter
import json

from replay_local_liquidity import BOOKS, DEST, ENTRY_DELAY_NS, HORIZONS_S, OUT, point, replay, rows, save_rows

LEDGER = 'every-early-falling-touch-signal.jsonl.gz'
RECEIPT = 'early-falling-touch-replay-receipt.json'


def qualifying_indices(prices, sizes):
    was_eligible = False
    for i in range(2, len(prices)):
        eligible = (prices[i - 2] == prices[i - 1] == prices[i]
                    and sizes[i - 2] >= sizes[i - 1] >= sizes[i] > 1
                    and sizes[i - 2] > sizes[i])
        if eligible and not was_eligible:
            yield i
        was_eligible = eligible


def first_thinning_boundary(prices, sizes, index, direction):
    for later in range(index + 1, len(prices)):
        if prices[later] != prices[index]:
            status = 'RETREATED_BEFORE_ONE' if direction * (prices[later] - prices[index]) > 0 else 'IMPROVED_BEFORE_ONE'
            return status, later
        if sizes[later] == 1:
            return 'REACHED_ONE_AT_SAME_PRICE', later
    return 'WINDOW_CENSORED', None


def main():
    books = list(rows(OUT / BOOKS))
    points = [point(book, line) for line, book in enumerate(books, 1)]
    clocks = [quote['known_by_ns'] for quote in points]
    assert len(points) == 22194 and len({b['original_quote_book']['instrument_id'] for b in books}) == 1
    assert all(quote['bid_raw'] < quote['ask_raw'] for quote in points)
    for before, after in zip(points, points[1:]):
        assert after['group'] == before['group'] + 1 and after['cursor'] > before['cursor']
        assert after['known_by_ns'] >= before['known_by_ns']
    ledger, side_results = [], {}
    for side, direction, price in (('B', -1, 'bid_raw'), ('A', 1, 'ask_raw')):
        prices = [quote[price] for quote in points]
        sizes = [int(b['sides'][side]['original_touch_level']['size']) for b in books]
        indices = list(qualifying_indices(prices, sizes))
        boundaries = Counter()
        summary = {seconds: Counter() for seconds in HORIZONS_S}
        for i in indices:
            entry, outcomes = replay(points, clocks, i, direction)
            status, boundary = first_thinning_boundary(prices, sizes, i, direction)
            boundaries[status] += 1
            ledger.append(dict(side=side, direction=direction, signal=points[i],
                               path=[dict(quote=points[j], size=sizes[j]) for j in range(i - 2, i + 1)],
                               original_t_ordinals_at_signal=books[i]['original_trade_ordinals'],
                               later_same_price_thinning=dict(status=status, quote=None if boundary is None else points[boundary]),
                               entry=entry, outcomes=outcomes))
            for seconds, result in outcomes.items():
                summary[seconds][result['status']] += 1
                if result['status'] == 'OBSERVED':
                    for field in ('signed_twice_midpoint_change_raw', 'cross_spread_pnl_raw'):
                        delta = result[field]
                        label = 'positive' if delta > 0 else 'negative' if delta < 0 else 'flat'
                        summary[seconds][f'{field}_{label}'] += 1
        side_results[side] = dict(signals=len(indices), thinning_boundaries=boundaries, outcomes=summary)
        assert all(sum(counts[k] for k in ('OBSERVED', 'ENTRY_CENSORED', 'EXIT_CENSORED')) == len(indices)
                   for counts in summary.values())
    ledger.sort(key=lambda row: (row['signal']['book_line'], row['side']))
    save_rows(DEST / LEDGER, ledger)
    prior = json.loads((DEST / 'receipt.json').read_text(encoding='utf-8'))
    receipt = dict(session='20231018', original_trades_retained=prior['original_trades_retained'],
                   observed_books=len(books), source_book_file=BOOKS, entry_delay_ns=ENTRY_DELAY_NS,
                   hold_seconds=HORIZONS_S, results_by_side=side_results,
                   dipole_use='RESEARCH_CONTEXT_ONLY_NO_STAGE_OR_CLASSROOM_LABEL_USED_FOR_SIGNAL_OR_ENTRY',
                   semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (DEST / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
