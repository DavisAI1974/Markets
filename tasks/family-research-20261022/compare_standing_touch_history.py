"""Compare observable fixed-price history before a standing touch shrinks to one."""
from collections import Counter, defaultdict
import json

from compare_thin_touch_onsets import OUTPUT as ONSETS
from replay_local_liquidity import BOOKS, DEST, OUT, point, rows, save_rows

OUTPUT = 'every-standing-touch-pre-onset-path.jsonl.gz'
RECEIPT = 'standing-touch-pre-onset-receipt.json'
PRIOR_CLOSES = 3


def pre_onset_path(books, onset):
    signal, side = onset['signal'], onset['side']
    signal_index = signal['book_line'] - 1
    history = []
    for i in range(max(0, signal_index - PRIOR_CLOSES), signal_index):
        book = books[i]
        touch = book['sides'][side]['original_touch_level']
        prior = point(book, i + 1)
        if signal['group'] - prior['group'] != signal_index - i or not (
                prior['cursor'] < signal['cursor'] and prior['known_by_ns'] <= signal['known_by_ns']):
            raise ValueError('prior book is nonconsecutive or unavailable at the signal')
        history.append(dict(quote=prior, touch_price_raw=int(touch['price_raw']), touch_size=int(touch['size'])))
    if len(history) != PRIOR_CLOSES:
        return 'INSUFFICIENT_PRIOR_BOOKS', history
    if any(row['touch_price_raw'] != onset['source_side_view']['new_best_raw'] for row in history):
        return 'PRIOR_BEST_PRICE_CHANGED', history
    sizes = [row['touch_size'] for row in history]
    if sizes[0] == sizes[1] == sizes[2]:
        return 'FLAT', history
    if sizes[0] >= sizes[1] >= sizes[2]:
        return 'FALLING', history
    if sizes[0] <= sizes[1] <= sizes[2]:
        return 'BUILDING', history
    return 'MIXED', history


def main():
    books = list(rows(OUT / BOOKS))
    cells = defaultdict(Counter)
    evidence, scope = [], Counter()
    for line, onset in enumerate(rows(DEST / ONSETS), 1):
        scope[onset['onset']] += 1
        if onset['onset'] != 'STANDING_BEST_SHRANK':
            continue
        side, tape = onset['side'], onset['recorded_t']
        kind, history = pre_onset_path(books, onset)
        end, timing = onset['first_end'], onset['end_vs_entry']
        cells[side, tape, kind][end['status'], timing] += 1
        evidence.append(dict(source_onset_line=line, source_replay_line=onset['source_replay_line'],
                             source_transition_line=onset['source_transition_line'],
                             side=side, recorded_t=tape, original_trade_ordinals=onset['original_trade_ordinals'],
                             signal=onset['signal'], onset_side_view=onset['source_side_view'],
                             path=kind, prior_closes=history,
                             first_paper_entry=onset['first_paper_entry'], first_end=end, end_vs_entry=timing))
    prior = json.loads((DEST / 'size-one-onset-comparison-receipt.json').read_text(encoding='utf-8'))
    assert sum(scope.values()) == prior['scenarios']
    assert len(evidence) == sum(c['total'] for c in prior['cells'] if c['onset'] == 'STANDING_BEST_SHRANK')
    for cell in prior['cells']:
        if cell['onset'] == 'STANDING_BEST_SHRANK':
            observed = Counter()
            for (side, tape, _), counts in cells.items():
                if (side, tape) == (cell['side'], cell['recorded_t']):
                    observed.update(counts)
            assert observed == {(r['status'], r['timing']): r['count'] for r in cell['outcomes']}
    save_rows(DEST / OUTPUT, evidence)
    receipt = dict(session='20231018', prior_closes=PRIOR_CLOSES, entry_delay_ns=prior['entry_delay_ns'],
                   all_onsets_by_type=dict(scope), original_trades_retained=prior['original_trades_retained'],
                   cells=[dict(side=side, recorded_t=tape, path=kind, total=sum(counts.values()),
                               outcomes=[dict(status=status, timing=timing, count=count)
                                         for (status, timing), count in sorted(counts.items())])
                          for (side, tape, kind), counts in sorted(cells.items())],
                   semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (DEST / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
