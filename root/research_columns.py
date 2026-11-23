"""ROOT: the research columns put ONTO THE EVERY-TICK TABLES, lined up row for row with the stored rows.

Greg, 2026-11-23: "Put the research columns on the every tick tables. Yes we want every tick. Why are you rebuilding
things that are already there? Just update what already exists".

NOTHING THAT EXISTS IS REWRITTEN. Like every calculation's columns, these are written as
`calc-research_columns-<trade day>-partNNN.parquet`: one file beside each stored rows file, the same number of rows
in the same order, the position on the tape first. Nothing new is calculated on the tape: stored values are looked
up at each tick BY PLACE ON THE TAPE (no trade that came after a tick is in its read) or set on the tick they
belong to.

THE COLUMNS, on every tick of the trade day (empty on the rows outside it):
- `exhaustion_20s`, `dipole_60s`: the stored natural gas exhaustion line (20 seconds) and dipole line (60 seconds)
  as they stood at that tick.
- `info_...`: the stored information measure at the read of the exhaustion line standing at that tick, with
  `info_ratio_made_by_division`.
- `leg__...`, `bid_run__...`, `ask_run__...`: a move in price (a trade leg, a run of the best bid, a run of the
  best offer) ON THE TICK OF ITS FIRST STEP: every column of the stored research table of the moves, and the
  measure at its first step and its end.
- `hump__...`: a hump of the exhaustion line ON THE TICK IT BEGAN ON, when it began on a trade.
- `hump_between_ticks__...`: a hump that began at a moment with no tick (old trades leaving the 20 seconds) is set
  on THE LAST TICK RECEIVED BEFORE THAT MOMENT; its own nanosecond is in its `began_received_ns`. When more than
  one hump began before the next tick, the first is here, `humps_begun_between_ticks` counts them, and every one is
  whole in the stored research table of the humps.

    python3 -m root.research_columns 20231017 --rows <folder of the trade day's stored files> --out <folder>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from root import checks, store, tape
from root.calendar import parse_trade_day
from root.research_excel import DIVISION, MEASURE, PINNED, TABLES, laid_out, measure_at
from root.research_threads import standing

NAME = 'research_columns'
LINES = dict(exhaustion_20s='crypto-ng-tick-line-20s', dipole_60s='crypto-ng-tick-lean-60s')   # the stored lines
KINDS = {'trade leg': 'leg', 'run of the best bid': 'bid_run', 'run of the best ask': 'ask_run'}   # a move's block
BETWEEN, COUNT = 'hump_between_ticks', 'humps_begun_between_ticks'
JOIN = '__'                                            # between a block's name and a column's name
CLOSE = 1e-9                                           # a check only: how near two readings of one line must be
AT_TICK = [('exhaustion_20s', 'THE EXHAUSTION LINE at this tick: bought minus sold over bought plus sold, the trades '
            'of the last 20 seconds; the stored line read by place on the tape. Above zero buying, below selling.'),
           ('dipole_60s', 'THE DIPOLE LINE at this tick: the same figure over the last 60 seconds, read the same way.')] \
    + [(name, 'THE INFORMATION MEASURE at this tick (not the dipole, not the exhaustion). ' + what)
       for name, _, what in MEASURE] + [(DIVISION[0], DIVISION[1])]


def a_line(folder: Path, file: str, day: str) -> dict:
    import pyarrow.parquet as pq
    held = pq.read_table(folder / 'crypto-ng-tick' / f'{file}-{day}.parquet',
                         columns=['moment_received_ns', 'what', 'position_on_tape', 'flow']).to_pydict()
    return dict(moments=np.array(held['moment_received_ns'], np.int64), what=held['what'],
                position=held['position_on_tape'], flow=held['flow'])


def research(folder: Path, day: str, kind: str) -> tuple:
    """One stored research table with the measure looked up at its moments: its column names, types and columns."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    stem, _ = TABLES[kind]
    table = pq.read_table(folder / 'research-threads' / f'{stem}-{day}.parquet')
    kinds = {field.name: field.type for field in table.schema}
    stored = table.to_pydict()
    added = measure_at(folder, day, kind, stored)
    for name in added:
        kinds[name] = pa.bool_() if name.startswith(DIVISION[0]) else \
            pa.int64() if 'pieces_with_a_trade' in name else pa.float64()
    stored.update(added)
    names = [name for _, name, _ in laid_out(kind) if name != PINNED[kind][1]]
    return names, kinds, stored


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)

    # every tick of the trade day, through the rows gate
    position, received = [], []
    for at, (moment,) in tape.rows_for_calculations(rows_folder, trade_day, ['received_time_ns']):
        position.append(at); received.append(moment)
    n = len(position)
    place = {p: k for k, p in enumerate(position)}
    received_at = np.array(received, np.int64)
    columns, kinds, what = {}, {}, dict(AT_TICK)

    # the two lines and the measure at every tick, by place on the tape
    lines = {name: a_line(rows_folder, file, day) for name, file in LINES.items()}
    measure = pq.read_table(rows_folder / 'info-measure' / f'info-measure-{day}.parquet',
                            columns=[source for _, source, _ in MEASURE]).to_pydict()
    for name, _ in AT_TICK:
        columns[name] = [None] * n
        kinds[name] = pa.bool_() if name == DIVISION[0] else pa.int64() if 'pieces_with_a_trade' in name else pa.float64()
    for k in range(n):
        r = standing(lines['exhaustion_20s'], received[k], position[k])
        r60 = standing(lines['dipole_60s'], received[k], position[k])
        if r60 >= 0:
            columns['dipole_60s'][k] = lines['dipole_60s']['flow'][r60]
        if r >= 0:
            columns['exhaustion_20s'][k] = lines['exhaustion_20s']['flow'][r]
            for name, source, _ in MEASURE:
                columns[name][k] = measure[source][r]
            shared = measure['mi_level'][r]
            columns[DIVISION[0]][k] = None if shared is None else shared == 0
    trades = pq.read_table(rows_folder / 'crypto-ng-tick' / f'crypto-ng-tick-tape-trades-{day}.parquet',
                           columns=['position_on_tape', 'read_20s', 'flow_20s_at']).to_pydict()
    for p, read, flow in zip(trades['position_on_tape'], trades['read_20s'], trades['flow_20s_at']):
        if read is not None:                           # at a trade with a side the line is that trade's own read
            ours = columns['exhaustion_20s'][place[p]]
            checks.need((ours is None and flow is None) or (ours is not None and flow is not None
                                                            and abs(ours - flow) <= CLOSE),
                        f'the exhaustion line at the trade at {p} is not the stored one')

    def block(prefix: str, names: list, types: dict, described: dict):
        for name in names:
            columns[f'{prefix}{JOIN}{name}'] = [None] * n
            kinds[f'{prefix}{JOIN}{name}'] = types[name]
            what[f'{prefix}{JOIN}{name}'] = described[name]

    def put(prefix: str, names: list, stored: dict, line: int, k: int):
        checks.need(columns[f'{prefix}{JOIN}{names[0]}'][k] is None, f'two lines of {prefix} on one tick')
        for name in names:
            columns[f'{prefix}{JOIN}{name}'][k] = stored[name][line]

    # the moves: each on the tick of its first step, in the block of its kind
    names, types, stored = research(rows_folder, day, 'moves')
    described = {name: text for _, name, text in laid_out('moves')}
    counts = dict(trade_day=trade_day.isoformat(), ticks=n)
    for kind, prefix in KINDS.items():
        block(prefix, names, types, {name: f'A {kind}, on the tick of its first step. ' + described[name] for name in names})
        counts[f'{prefix}_moves_set_on_their_first_step'] = 0
    for line in range(len(stored['move'])):
        prefix = KINDS[stored['move'][line]]
        put(prefix, names, stored, line, place[stored['first_step_position'][line]])
        counts[f'{prefix}_moves_set_on_their_first_step'] += 1
    moves = len(stored['move'])

    # the humps: on the tick they began on, or on the last tick received before the moment they began at
    names, types, stored = research(rows_folder, day, 'humps')
    described = {name: text for _, name, text in laid_out('humps')}
    block('hump', names, types, {name: 'A hump of the exhaustion line, on the tick it began on. ' + described[name]
                                 for name in names})
    block(BETWEEN, names, types, {name: 'A hump that began at a moment with no tick (old trades leaving the 20 '
                                        'seconds), set on the last tick received before that moment. ' + described[name]
                                  for name in names})
    columns[COUNT], kinds[COUNT] = [None] * n, pa.int64()
    what[COUNT] = ('How many humps began at a moment with no tick after this tick and before the next. The first is in '
                   f'the {BETWEEN} columns; every one is whole in the stored research table of the humps.')
    counts.update(humps_set_on_the_tick_they_began_on=0, humps_that_began_with_no_tick=0,
                  of_them_set_on_the_last_tick_before=0, of_them_second_or_later_before_the_next_tick=0,
                  of_them_before_the_first_tick_of_the_trade_day=0)
    for line in range(len(stored['hump'])):
        on = stored['began_position'][line]
        if on is not None:
            put('hump', names, stored, line, place[on])
            counts['humps_set_on_the_tick_they_began_on'] += 1
            continue
        counts['humps_that_began_with_no_tick'] += 1
        k = int(np.searchsorted(received_at, stored['began_received_ns'][line], 'left')) - 1
        if k < 0:
            counts['of_them_before_the_first_tick_of_the_trade_day'] += 1
            continue
        columns[COUNT][k] = (columns[COUNT][k] or 0) + 1
        if columns[COUNT][k] == 1:
            put(BETWEEN, names, stored, line, k)
            counts['of_them_set_on_the_last_tick_before'] += 1
        else:
            counts['of_them_second_or_later_before_the_next_tick'] += 1
    counts.update(moves=moves, humps=len(stored['hump']), columns=len(columns))

    # one file beside each stored rows file: the same rows in the same order
    order = list(columns)
    files, done = [], 0
    for part, path in enumerate(tape.stored_row_files(rows_folder, trade_day)):
        there = pq.read_table(path, columns=[tape.ROW_POSITION]).column(tape.ROW_POSITION).to_pylist()
        where = [place.get(p) for p in there]
        arrays = [pa.array(there, type=pa.int64())] + [
            pa.array([None if k is None else columns[name][k] for k in where], type=kinds[name]) for name in order]
        name = f'calc-{NAME}-{day}-part{part:03d}.parquet'
        pq.write_table(pa.Table.from_arrays(arrays, names=[tape.ROW_POSITION] + order), out / name, compression='zstd',
                       compression_level=store.ZSTD_LEVEL)
        raw = (out / name).read_bytes()
        files.append(dict(file=name, rows=len(there), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                          beside=path.name, beside_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        done += sum(k is not None for k in where)
    checks.need(done == n, 'a tick of the trade day is in no stored rows file, or in two')
    count_name = f'CALC-{NAME}-COUNT-{day}.json'
    (out / count_name).write_text(json.dumps(counts, indent=1) + '\n')
    raw = (out / count_name).read_bytes()
    files.append(dict(file=count_name, rows=None, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(
        what='The research columns on the every-tick table: the natural gas exhaustion and dipole lines and the '
             'information measure at every tick, each move on the tick of its first step, each hump on the tick it '
             'began on',
        asked='Greg, 2026-11-23: "Put the research columns on the every tick tables. Yes we want every tick ... Just '
              'update what already exists"',
        trade_day=trade_day.isoformat(),
        nothing_rewritten='These are new column files lined up row for row with the stored rows, as every '
                          'calculation\'s columns are. No stored file is changed. Nothing new is calculated on the '
                          'tape; no window, no label, no average, no midpoint; nothing from another trade day.',
        read_from=[f'rows-{day}-part*.parquet (through the rows gate)', f'research-threads/research-moves-{day}.parquet',
                   f'research-threads/research-humps-{day}.parquet', f'info-measure/info-measure-{day}.parquet',
                   f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet']
                  + [f'crypto-ng-tick/{file}-{day}.parquet' for file in LINES.values()],
        columns=[dict(column=tape.ROW_POSITION, what='The tick: its position on the tape, as on the stored row.')]
                + [dict(column=name, what=what[name]) for name in order],
        counts=counts,
        checks=dict(passed=True,
                    what='each file holds the rows of the stored rows file beside it, in the same order; every tick '
                         'of the trade day is in exactly one of them; at every trade with a side the exhaustion line '
                         'is that trade\'s own stored read; every move sits on the tick of its first step and no two '
                         'of one kind share a tick; every hump that began on a trade sits on that tick'),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'CALC-{NAME}-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The research columns on the every-tick table')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--keep-cpus', action='store_true', help='accepted for the pod runner; this program uses one CPU')
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
