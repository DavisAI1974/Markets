"""Split the saved size-one episode outcomes by information observable at onset."""
from collections import Counter, defaultdict
import json

from replay_local_liquidity import DEST, OUT, TRADES, TRANSITIONS, rows, save_rows

SIGNALS = 'every-paper-signal-and-outcome.jsonl.gz'
OUTPUT = 'every-size-one-onset-comparison.jsonl.gz'
RECEIPT = 'size-one-onset-comparison-receipt.json'


def compare(signal, transition, trade_links):
    line, side = signal['transition_line'], signal['side']
    close = signal['signal']
    if (transition['after_group_ordinal'], transition['after_input_cursor'], transition['after_known_by_ns']) != (
            close['group'], close['cursor'], close['known_by_ns']):
        raise ValueError('onset and original transition have different source coordinates')
    view = transition['sides'][side]
    changed = view['old_best_raw'] != view['new_best_raw']
    if view['new_touch_size_after'] != 1 or (not changed and view['old_touch_size_before'] <= 1):
        raise ValueError('source does not establish a newly thin touch')
    tape = transition['original_trade_ordinals']
    for ordinal in tape:
        trade = trade_links[ordinal]
        clocks = trade['exact_clocks']
        if (trade['trade_ordinal'] != ordinal or trade['window_transition_line'] != line
                or clocks['group_close_input_cursor'] != close['cursor']
                or clocks['available_ns'] > close['known_by_ns']):
            raise ValueError('same-group tape link cannot be used at signal time')
    end = signal['thin_episode_end']
    entry, end_quote = signal['entry'], end['quote']
    timing = 'NO_OBSERVED_END' if end_quote is None else 'NO_OBSERVED_ENTRY'
    if entry is not None and end_quote is not None:
        timing = 'BY_ENTRY' if end_quote['cursor'] <= entry['cursor'] else 'AFTER_ENTRY'
    return dict(side=side, onset='NEW_BEST' if changed else 'STANDING_BEST_SHRANK',
                recorded_t=bool(tape), original_trade_ordinals=tape, source_transition_line=line,
                source_lifecycle_refs=transition['same_emission_lifecycle_refs'],
                source_side_view=view, signal=close, first_paper_entry=entry,
                first_end=end, end_vs_entry=timing)


def main():
    source = json.loads((DEST / 'receipt.json').read_text(encoding='utf-8'))
    trade_links = list(rows(OUT / TRADES))
    transitions = list(rows(OUT / TRANSITIONS))
    evidence = []
    cells = defaultdict(Counter)
    for line, signal in enumerate(rows(DEST / SIGNALS), 1):
        if signal['rule'] != 'size_one_touch_onset':
            continue
        original = transitions[signal['transition_line'] - 1]
        row = compare(signal, original, trade_links)
        row['source_replay_line'] = line
        evidence.append(row)
        key = row['side'], row['onset'], row['recorded_t']
        cells[key][row['first_end']['status'], row['end_vs_entry']] += 1
    assert len(evidence) == source['signal_counts']['size_one_touch_onset']
    assert Counter(row['first_end']['status'] for row in evidence) == source['thin_episode_end_counts']
    assert Counter(row['first_end']['status'] for row in evidence if row['end_vs_entry'] == 'BY_ENTRY') == source['thin_episode_end_by_entry']
    save_rows(DEST / OUTPUT, evidence)
    receipt = dict(session='20231018', scenarios=len(evidence), original_trades_retained=len(trade_links),
                   entry_delay_ns=source['entry_delay_ns'],
                   cells=[dict(side=side, onset=onset, recorded_t=recorded_t, total=sum(counts.values()),
                               outcomes=[dict(status=status, timing=timing, count=count)
                                         for (status, timing), count in sorted(counts.items())])
                          for (side, onset, recorded_t), counts in sorted(cells.items())],
                   semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (DEST / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
