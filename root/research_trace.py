"""ROOT: why the stored exhaustion line and a step line's own 20-second flow differ at some first steps, traced.

The research threads job (`root/research_threads.py`) counted, at the first step of every move, the stored
exhaustion line against the figure made from the step line's own 20-second flow: equal at nearly all, NOT EQUAL at
104; 144; 136; 130 first steps on the four trade days. Why was not established, and nothing is said from a guess.

WHAT IS TESTED. That job read a stored line BY TIME: the last read made at or before the nanosecond of the tick. A
nanosecond can hold more than one read (several trades received together), so a read by time can stand on trades
that came AFTER the tick on the tape. Here every such look-up is made a second way, BY PLACE ON THE TAPE: the last
read made before that nanosecond, or at it and not after the tick (trades leaving at a nanosecond leave first; a
trade's read counts when its place on the tape is at or before the tick's). Nothing new is calculated on the tape:
stored lines are read two ways and compared.

IT WRITES, for one trade day:
1. `research-trace-first-steps-<trade day>.parquet`: one line per first step where the stored exhaustion line read
   by time is not the step line's own figure: both figures, the read by place, and how many reads that nanosecond
   holds.
2. The receipt with counts: of those first steps, how many are equal once read by place; and for EVERY look-up of
   the two research tables (a move's first step and end on both lines; a hump's beginning, furthest and end on the
   dipole line and on the quote) how many land on a nanosecond holding more than one read or tick, and how many
   give a different value by place than by time.

No window, no label, no average, no midpoint. Nothing crosses from one trade day to another.

    python3 -m root.research_trace 20231017 --rows <folder of the trade day's stored files> --out <folder>
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from root import checks, store, tape
from root.calendar import parse_trade_day

LINES = dict(exhaustion_20s='crypto-ng-tick-line-20s', dipole_60s='crypto-ng-tick-lean-60s')   # the stored lines
LINE_READS = ['read', 'moment_received_ns', 'what', 'position_on_tape', 'flow']
RECEIVED = 'a trade was received'                      # the stored line's own word for a read made at a trade
STEP, FIRST = 'step', 1                                # a stored step line; a move's first step
CLOSE = 1e-9                                           # a check only: how near two readings must be to be equal
BUY, SELL = 'buy', 'sell'
SIGN = {BUY: 1, SELL: -1}
QUOTE = ['received_time_ns', 'best_bid', 'best_ask']
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
MOVES = ['move', 'move_start_position', 'first_step_position', 'first_step_received_ns', 'end_position',
         'end_received_ns'] + [f'{line}_at_{mark}' for mark in ('first_step', 'end') for line in LINES]
MARKS = dict(began='began_received_ns', furthest='furthest_received_ns', ended='ended_received_ns')
HUMPS = ['hump', 'side', 'furthest_flow'] + list(MARKS.values()) + [
    f'{what}_at_{mark}' for mark in MARKS for what in ('best_bid', 'best_ask', 'dipole_60s')]
COLUMNS = [
    ('move', 'Which move: trade leg, run of the best bid, run of the best ask.'),
    ('move_start_position', 'The move, as the research table names it.'),
    ('first_step_position', 'The tick of its first step: its position on the tape.'),
    ('first_step_received_ns', 'When that tick was received.'),
    ('step_bought_20s', 'Size bought in the 20 seconds, as stored on the step line.'),
    ('step_sold_20s', 'Size sold in the 20 seconds, as stored on the step line.'),
    ('step_flow', 'The figure made from those two: bought minus sold over bought plus sold.'),
    ('line_by_time', 'The stored exhaustion line read by time: the last read at or before that nanosecond.'),
    ('read_by_time', 'The number of that read.'),
    ('line_by_place', 'The stored exhaustion line read by place on the tape: the last read not after the tick.'),
    ('read_by_place', 'The number of that read. Empty when no read had been made yet.'),
    ('reads_at_that_nanosecond', 'How many reads of the stored line share that nanosecond.'),
    ('equal_by_place', 'Yes when the read by place equals the step line\'s own figure.'),
]
NAMES = [name for name, _ in COLUMNS]


def table(path: Path, columns) -> dict:
    import pyarrow.parquet as pq
    checks.need(path.is_file(), f'{path.name} is not beside the rows')
    return pq.read_table(path, columns=columns).to_pydict()


def parts(rows_folder: Path, stem: str, columns) -> dict:
    files = sorted(rows_folder.glob(f'{stem}-part*.parquet'))
    checks.need(files, f'{stem} is not beside the rows')
    held = collections.defaultdict(list)
    for path in files:
        for name, values in table(path, columns).items():
            held[name] += values
    return dict(held)


def same(a, b) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= CLOSE)


def the_lines(rows_folder: Path, day: str) -> dict:
    out = {}
    for name, file in LINES.items():
        held = table(rows_folder / 'crypto-ng-tick' / f'{file}-{day}.parquet', LINE_READS)
        moments = np.array(held['moment_received_ns'], np.int64)
        checks.need(len(moments) and bool(np.all(np.diff(moments) >= 0)), f'the stored {file} is not in time order')
        out[name] = dict(moments=moments, flow=held['flow'], trade=[w == RECEIVED for w in held['what']],
                         position=held['position_on_tape'])
    return out


def by_time(line: dict, at: int) -> int:
    """The read standing at a moment: the last one made at or before it (below zero: none yet)."""
    return int(np.searchsorted(line['moments'], at, 'right')) - 1


def by_place(line: dict, at: int, position) -> int:
    """The read standing at a tick: the last one made before its nanosecond, or at it and not after the tick on the
    tape (trades leaving at a nanosecond leave first). With no tick (`position` empty) only trades leaving count."""
    a, b = int(np.searchsorted(line['moments'], at, 'left')), int(np.searchsorted(line['moments'], at, 'right'))
    k = a - 1
    for r in range(a, b):
        if not line['trade'][r] or (position is not None and line['position'][r] <= position):
            k = r
    return k


def value(line: dict, k: int):
    return line['flow'][k] if k >= 0 else None


def look(tally, name: str, line: dict, at, position, stored):
    """One look-up of a stored line, both ways, counted."""
    if at is None:
        return
    t, p = by_time(line, at), by_place(line, at, position)
    several = int(np.searchsorted(line['moments'], at, 'right')) - int(np.searchsorted(line['moments'], at, 'left'))
    checks.need(same(value(line, t), stored), f'{name}: the stored value is not the line read by time')
    tally[name]['look-ups'] += 1
    tally[name]['on a nanosecond holding more than one read'] += several > 1
    tally[name]['a different value by place than by time'] += not same(value(line, t), value(line, p))


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    lines = the_lines(rows_folder, day)
    tally = collections.defaultdict(lambda: collections.defaultdict(int))

    # the moves: every look-up both ways, and the first steps whose two exhaustion figures differ
    m = table(rows_folder / 'research-threads' / f'research-moves-{day}.parquet', MOVES)
    f = parts(rows_folder, f'calc-move_steps-facts-{day}',
              ['move', 'move_start_position', 'fact', 'step', 'flow_bought_20s', 'flow_sold_20s'])
    first = {(f['move'][k], f['move_start_position'][k]): k for k in range(len(f['move']))
             if f['fact'][k] == STEP and f['step'][k] == FIRST}
    listed, agree = [], collections.Counter()
    for k in range(len(m['move'])):
        for mark, where, when in (('first_step', 'first_step_position', 'first_step_received_ns'),
                                  ('end', 'end_position', 'end_received_ns')):
            for name, line in lines.items():
                look(tally, f'a move\'s {mark.replace("_", " ")}, the {name} line', line, m[when][k], m[where][k],
                     m[f'{name}_at_{mark}'][k])
        s = first[(m['move'][k], m['move_start_position'][k])]
        bought, sold = f['flow_bought_20s'][s], f['flow_sold_20s'][s]
        line, at, position = lines['exhaustion_20s'], m['first_step_received_ns'][k], m['first_step_position'][k]
        t, p = by_time(line, at), by_place(line, at, position)
        if not bought and not sold:
            agree['both empty' if value(line, t) is None else 'the step line holds no flow, the stored line does'] += 1
            continue
        if value(line, t) is None:
            agree['the stored line is empty, the step line holds flow'] += 1
            continue
        own = (bought - sold) / (bought + sold)
        if same(value(line, t), own):
            agree['equal'] += 1
            continue
        agree['not equal'] += 1
        equal = same(value(line, p), own)
        agree['not equal by time: equal by place on the tape' if equal else 'not equal by time: not equal by place either'] += 1
        several = int(np.searchsorted(line['moments'], at, 'right')) - int(np.searchsorted(line['moments'], at, 'left'))
        listed.append([m['move'][k], m['move_start_position'][k], position, at, bought, sold, own, value(line, t), t,
                       value(line, p), p if p >= 0 else None, several, equal])
    before = json.loads((rows_folder / 'research-threads' / f'RESEARCH-THREADS-{day}.json').read_text())['counts'][
        'first_steps_the_stored_exhaustion_line_against_the_step_lines_own_20_second_flow']
    checks.need(all(agree[name] == count for name, count in before.items()),
                'the count of equal and not equal first steps is not the one the research threads job wrote')

    # the humps: the dipole line and the quote at a hump's three moments, both ways
    h = table(rows_folder / 'research-threads' / f'research-humps-{day}.parquet', HUMPS)
    position, received, bid, ask = [], [], [], []
    for at, (moment, best_bid, best_ask) in tape.rows_for_calculations(rows_folder, trade_day, QUOTE):
        position.append(at); received.append(moment); bid.append(best_bid); ask.append(best_ask)
    received, row_of = np.array(received, np.int64), {p: k for k, p in enumerate(position)}
    dollars = lambda price: None if price is None else price / PRICE_UNIT
    line, lean = lines['exhaustion_20s'], lines['dipole_60s']
    for k in range(len(h['hump'])):
        sign = SIGN[h['side'][k]]
        for mark, column in MARKS.items():
            at = h[column][k]
            if at is None:
                continue
            a, b = int(np.searchsorted(line['moments'], at, 'left')), int(np.searchsorted(line['moments'], at, 'right'))
            fits = dict(began=lambda v: v is not None and v * sign > 0,
                        furthest=lambda v: v is not None and same(v, h['furthest_flow'][k]),
                        ended=lambda v: v is None or v * sign <= 0)[mark]
            own = next((r for r in range(a, b) if fits(line['flow'][r])), None)
            checks.need(own is not None, f'hump {h["hump"][k]}: no read of the stored line is its {mark}')
            tick = line['position'][own] if line['trade'][own] else None
            look(tally, f'a hump\'s {mark}, the dipole_60s line', lean, at, tick, h[f'dipole_60s_at_{mark}'][k])
            t = int(np.searchsorted(received, at, 'right')) - 1
            p = row_of[tick] if tick is not None else int(np.searchsorted(received, at, 'left')) - 1
            several = t + 1 - int(np.searchsorted(received, at, 'left'))
            for name, held in (('best_bid', bid), ('best_ask', ask)):
                stored = h[f'{name}_at_{mark}'][k]
                checks.need(same(dollars(held[t]) if t >= 0 else None, stored),
                            f'hump {h["hump"][k]}: the stored {name} is not the quote read by time')
                which = f'a hump\'s {mark}, the {name.replace("_", " ")}'
                tally[which]['look-ups'] += 1
                tally[which]['on a nanosecond holding more than one tick'] += several > 1
                tally[which]['a different value by place than by time'] += not same(
                    dollars(held[t]) if t >= 0 else None, dollars(held[p]) if p >= 0 else None)

    counts = dict(trade_day=trade_day.isoformat(), moves=len(m['move']), humps=len(h['hump']),
                  first_steps_the_stored_exhaustion_line_against_the_step_lines_own_20_second_flow=dict(sorted(agree.items())),
                  every_look_up_both_ways={name: {key: int(v) for key, v in got.items()} for name, got in sorted(tally.items())})
    count_name = f'RESEARCH-TRACE-COUNT-{day}.json'
    (out / count_name).write_text(json.dumps(counts, indent=1) + '\n')
    name = f'research-trace-first-steps-{day}.parquet'
    columns = list(zip(*listed)) if listed else [[] for _ in NAMES]
    pq.write_table(pa.Table.from_arrays(
        [pa.array(list(column), type=pa.string() if c == 'move' else pa.bool_() if c == 'equal_by_place' else None)
         for c, column in zip(NAMES, columns)], names=NAMES), out / name, compression='zstd',
        compression_level=store.ZSTD_LEVEL)
    files = []
    for file_name, rows in ((name, len(listed)), (count_name, None)):
        raw = (out / file_name).read_bytes()
        files.append(dict(file=file_name, rows=rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(
        what='Why the stored exhaustion line and a step line\'s own 20-second flow differ at some first steps: every '
             'look-up of the two research tables made a second way, by place on the tape, and compared',
        asked='Greg, 2026-11-23, the handoff\'s second check: read the job\'s count of first steps where the stored '
              'exhaustion line equals the step line\'s own 20-second flow, and where it does not. The reason for '
              'the ones that do not is found here, not guessed.',
        trade_day=trade_day.isoformat(),
        nothing_applied='No window, no label, no average, no midpoint; nothing new calculated on the tape; nothing '
                        'from another trade day.',
        the_two_ways=dict(by_time='the last read made at or before the nanosecond of the tick (what the research '
                                  'threads job did)',
                          by_place='the last read made before that nanosecond, or at it and not after the tick on '
                                   'the tape; trades leaving at a nanosecond leave first'),
        read_from=[f'research-threads/research-moves-{day}.parquet', f'research-threads/research-humps-{day}.parquet',
                   f'research-threads/RESEARCH-THREADS-{day}.json', f'calc-move_steps-facts-{day}-part*.parquet',
                   f'rows-{day}-part*.parquet (through the rows gate)']
                  + [f'crypto-ng-tick/{file}-{day}.parquet' for file in LINES.values()],
        columns=[dict(column=c, what=w) for c, w in COLUMNS],
        counts=counts,
        checks=dict(passed=True,
                    what='both stored lines are in time order; every stored value of the two research tables is the '
                         'line (or the quote) read by time; the counts of equal and not equal first steps are the '
                         'ones the research threads job wrote; every hump\'s moment is a read of the stored line'),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'RESEARCH-TRACE-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The first steps whose two exhaustion figures differ, traced')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--keep-cpus', action='store_true', help='accepted for the pod runner; this program uses one CPU')
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
