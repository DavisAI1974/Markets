"""ROOT: which exhaustions and dipoles at the tick CONTINUE over more than one trade (the search, per trade day).

Greg, 2026-11-18: "how can we see with the data we have if there are any dipoles or exhaustions that continue on to
cover more than one trade? We should probably expand our searches for those"; "We need the data to be telling us
what those times are"; "Go on the runs of trades and the dipole search".

Two things already stored at the tick are followed, each from its own beginning to its own end. No number of ours
sets a start or an end, and nothing is averaged, ranked, typed or labelled.

1. THE EXHAUSTION AT THE TICK: a run of trades on one side (the peak with no window, `turn_peaks`). It begins at its
   first trade and ends at its last, when the other side hits.
2. THE DIPOLE AT THE TICK (`tick-renders/tick-dipole-*`: the run of trades under way against the run before it). A
   STRETCH is the time it stays on one side: it begins at the trade that brings it onto that side and ends at the
   last trade before it stands at zero, is empty, or has crossed.

For each run and each stretch, on its own line: its side, its first and last trade to the nanosecond, how many
trades it holds, what the trade price did across it, and the stored trade legs under way during it (`leg_peaks`).

WHAT IS WRITTEN:
- `continuing-runs-<trade day>.parquet`: one line per run of trades on one side.
- `continuing-dipole-<trade day>.parquet`: one line per stretch the dipole at the tick stays on one side.
- `CONTINUING-<trade day>.json`: the receipt: the columns, the counts, the checks, every file's fingerprint.

The ticks reach this only through `tape.rows_for_calculations()`: the four trade days, nothing from outside them.
What it reads beside the rows are outputs already stored for the same trade day.

    python3 -m root.continuing 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from root import checks, store, tape
from root.calendar import NS_PER_SECOND, parse_trade_day

READS = ['received_time_ns', 'action', 'side', 'size', 'price']
TRADE = 'T'
SIDE = {'B': 'buy', 'A': 'sell'}                       # the tape's codes for the aggressor side, as the rows store them
SIDE_OF = {1: 'buy', -1: 'sell'}                       # the side of zero the dipole stands on
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
BEFORE = {None: 'the dipole was empty before (no change of hands yet)', 0: 'the dipole stood at zero before'}
AFTER = {None: 'the dipole went empty', 0: 'the dipole came to zero'}
CROSSED_IN, CROSSED_OUT = 'the dipole crossed from the other side', 'the dipole crossed to the other side'
LAST = 'still on this side at the last trade of the trade day'

SHARED = [
    ('side', 'buy or sell.'),
    ('first_trade_position', 'Its first trade: position on the tape. A label only.'),
    ('last_trade_position', 'Its last trade.'),
    ('began_received_ns', 'When its first trade was received, to the nanosecond.'),
    ('ended_received_ns', 'When its last trade was received.'),
    ('length_seconds', 'From its first trade to its last, in seconds. 0 when it is a single trade.'),
    ('trades', 'How many trades with a side it holds.'),
    ('first_trade_price', 'The price of its first trade, in dollars.'),
    ('last_trade_price', 'The price of its last trade.'),
    ('highest_trade_price', 'The highest price traded inside it.'),
    ('lowest_trade_price', 'The lowest price traded inside it.'),
    ('first_trade_leg', 'The stored trade leg under way at its first trade: its number.'),
    ('last_trade_leg', 'The stored trade leg under way at its last trade.'),
    ('trade_legs_under_way', 'How many different stored trade legs were under way at its trades.'),
]
RUN_COLUMNS = [('run', 'The number of this run of trades on one side, in order through the trade day. A label only.')] + \
    SHARED + [('lots', 'The size traded in the run (a run\'s size adds its trades together), as `turn_peaks` stores it.')]
DIPOLE_COLUMNS = [('stretch', 'The number of this stretch, in order through the trade day. A label only.')] + SHARED + [
    ('runs_of_trades', 'How many different runs of trades on one side it passes through.'),
    ('how_it_began', 'What the dipole was at the trade before: empty, at zero, or on the other side.'),
    ('how_it_ended', 'What the dipole did at the trade after: went empty, came to zero, or crossed.'),
    ('furthest_dipole', 'The furthest the dipole stood from zero during it (above zero buying, below selling).'),
]
names_of = lambda columns: [name for name, _ in columns]


def read(rows_folder: Path, trade_day) -> dict:
    """The trade day's ticks as whole columns, through the stored-rows gate."""
    out = {name: [] for name in ['position'] + READS}
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        out['position'].append(position)
        for name, value in zip(READS, row):
            out[name].append(value)
    return out


def stored_on(rows_folder: Path, pattern: str, columns: list, position: np.ndarray) -> dict:
    """Columns of an output already stored for this trade day, lined up with the ticks by position on the tape."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(pattern))
    checks.need(files, f'{pattern} is not stored beside the rows')
    held = {name: [] for name in ['position_on_tape'] + columns}
    for path in files:
        table = pq.read_table(path, columns=list(held))
        for name in held:
            held[name] += table.column(name).to_pylist()
    at = np.array(held['position_on_tape'], np.int64)
    where = np.searchsorted(at, position)
    checks.need(bool(np.all(where < len(at))) and np.array_equal(at[np.minimum(where, len(at) - 1)], position),
                f'a tick of the trade day has no line in {pattern}')
    return {name: [held[name][k] for k in where.tolist()] for name in columns}


def shared(rows: list, s: dict) -> tuple:
    """The values every line carries, for the trades `rows` (places among the sided trades) of one run or stretch."""
    a, b = rows[0], rows[-1]
    prices = s['price'][a:b + 1]
    legs = [leg for leg in s['leg'][a:b + 1] if leg is not None]
    return (int(s['position'][a]), int(s['position'][b]), int(s['received'][a]), int(s['received'][b]),
            (int(s['received'][b]) - int(s['received'][a])) / NS_PER_SECOND, len(rows), float(prices[0]),
            float(prices[-1]), float(max(prices)), float(min(prices)), legs[0] if legs else None,
            legs[-1] if legs else None, len(set(legs)))


def save(out: Path, name: str, columns: dict, text=()) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_arrays([pa.array(v, type=pa.string() if k in text else None) for k, v in columns.items()],
                                 names=list(columns))
    pq.write_table(table, out / name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / name).read_bytes()
    return dict(file=name, rows=table.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    t = read(rows_folder, trade_day)
    position = np.array(t['position'], np.int64)
    sided = [k for k in range(len(position)) if t['action'][k] == TRADE and t['side'][k] in SIDE]
    checks.need(sided, 'the trade day holds no trade with a side')
    at = position[sided]
    runs = stored_on(rows_folder, f'calc-turn_peaks-{day}-part*.parquet',
                     ['run_first_trade_position', 'run_trades', 'run_size'], at)
    leg = stored_on(rows_folder, f'calc-leg_peaks-{day}-part*.parquet', ['leg_number'], at)['leg_number']
    dipole = stored_on(rows_folder, f'tick-renders/tick-dipole-{day}.parquet', ['dipole_at_tick'], at)['dipole_at_tick']
    s = dict(position=at, received=[t['received_time_ns'][k] for k in sided],
             price=[t['price'][k] / PRICE_UNIT for k in sided], leg=leg, side=[SIDE[t['side'][k]] for k in sided])
    n = len(sided)

    # 1. every run of trades on one side, from its first trade to its last
    run_lines, run_of, k = [], [0] * n, 0
    while k < n:
        j = k
        while j + 1 < n and runs['run_first_trade_position'][j + 1] == runs['run_first_trade_position'][k]:
            j += 1
        rows = list(range(k, j + 1))
        checks.need(runs['run_first_trade_position'][k] == int(at[k]) and runs['run_trades'][j] == len(rows)
                    and len({s['side'][i] for i in rows}) == 1,
                    f'the run of trades starting at position {int(at[k])} is not the one turn_peaks stored')
        for i in rows:
            run_of[i] = len(run_lines)                  # each sided trade's run
        run_lines.append((len(run_lines), s['side'][k]) + shared(rows, s) + (int(runs['run_size'][j]),))
        k = j + 1
    checks.need(sum(line[names_of(RUN_COLUMNS).index('trades')] for line in run_lines) == n,
                'the runs of trades do not hold every trade with a side once')

    # 2. every stretch the dipole at the tick stays on one side
    state = [None if d is None else (d > 0) - (d < 0) for d in dipole]      # empty, at zero (0), or a side
    stretch_lines, held_elsewhere, k = [], 0, 0
    while k < n:
        j = k
        while j + 1 < n and state[j + 1] == state[k]:
            j += 1
        if state[k]:
            rows = list(range(k, j + 1))
            far = max(rows, key=lambda i: abs(dipole[i]))
            before = state[k - 1] if k else None
            after = state[j + 1] if j + 1 < n else LAST
            stretch_lines.append(
                (len(stretch_lines), SIDE_OF[state[k]]) + shared(rows, s)
                + (len({run_of[i] for i in rows}), BEFORE.get(before, CROSSED_IN),
                   after if after == LAST else AFTER.get(after, CROSSED_OUT), float(dipole[far])))
        else:
            held_elsewhere += j + 1 - k
        k = j + 1
    T = names_of(DIPOLE_COLUMNS).index('trades')
    checks.need(sum(line[T] for line in stretch_lines) + held_elsewhere == n,
                'the stretches of the dipole do not hold every trade with a side once')

    table = lambda columns, lines: dict(zip(names_of(columns), map(list, zip(*lines)) if lines
                                            else [[] for _ in columns]))
    files = [save(out, f'continuing-runs-{day}.parquet', table(RUN_COLUMNS, run_lines), {'side'}),
             save(out, f'continuing-dipole-{day}.parquet', table(DIPOLE_COLUMNS, stretch_lines),
                  {'side', 'how_it_began', 'how_it_ended'})]
    R = {name: i for i, name in enumerate(names_of(RUN_COLUMNS))}
    D = {name: i for i, name in enumerate(names_of(DIPOLE_COLUMNS))}
    more = lambda lines, at_column: sum(1 for line in lines if line[at_column] > 1)
    receipt = dict(
        what='Which exhaustions and dipoles at the tick continue over more than one trade: every run of trades on '
             'one side and every stretch the dipole at the tick stays on one side, each on its own line, from its '
             'own beginning to its own end',
        asked='Greg, 2026-11-18: "how can we see with the data we have if there are any dipoles or exhaustions that '
              'continue on to cover more than one trade?"; "We need the data to be telling us what those times '
              'are"; "Go on the runs of trades and the dipole search"',
        trade_day=trade_day.isoformat(),
        nothing_applied='No type, label or kind is put on any line. Nothing is averaged or ranked. Not in the Excel '
                        'sheets (Greg, 2026-11-18: nothing is applied until it is decided with him).',
        read_from=['the stored rows, through the rows gate', f'calc-turn_peaks-{day} (the run of trades on every tick)',
                   f'calc-leg_peaks-{day} (the trade leg under way on every tick)',
                   f'tick-renders/tick-dipole-{day} (the dipole at the tick; Claude\'s figure of the thirteenth '
                   f'session, stored without Greg\'s yes as a calculation)'],
        columns=dict(runs=[dict(column=c, what=w) for c, w in RUN_COLUMNS],
                     dipole=[dict(column=c, what=w) for c, w in DIPOLE_COLUMNS]),
        counts=dict(
            trades_with_a_side=n,
            runs_of_trades=len(run_lines),
            runs_of_one_trade=sum(1 for line in run_lines if line[R['trades']] == 1),
            runs_of_more_than_one_trade=more(run_lines, R['trades']),
            runs_with_more_than_one_trade_leg_under_way=more(run_lines, R['trade_legs_under_way']),
            stretches_of_the_dipole=len(stretch_lines),
            stretches_of_one_trade=sum(1 for line in stretch_lines if line[D['trades']] == 1),
            stretches_of_more_than_one_trade=more(stretch_lines, D['trades']),
            stretches_through_more_than_one_run_of_trades=more(stretch_lines, D['runs_of_trades']),
            stretches_with_more_than_one_trade_leg_under_way=more(stretch_lines, D['trade_legs_under_way']),
            trades_at_which_the_dipole_is_empty_or_at_zero=held_elsewhere),
        checks=dict(
            the_runs_are_the_stored_ones=dict(
                passed=True, runs=len(run_lines),
                what='every run found by walking the trades begins at the first trade turn_peaks stored for it, '
                     'holds the number of trades turn_peaks stored, and is on one side; together they hold every '
                     'trade with a side once'),
            the_stretches_hold_every_trade=dict(
                passed=True, trades=n,
                what='the stretches of the dipole, and the trades at which it is empty or at zero, hold every '
                     'trade with a side once')),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'CONTINUING-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='Exhaustions and dipoles at the tick that continue over more than one trade')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
