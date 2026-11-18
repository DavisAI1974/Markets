"""ROOT: Greg's three renders for a whole trade day, timed at the tick, and the dipoles that line up with trade legs.

THE THREE RENDERS (Greg, 2026-11-18: "the trade price curve", "dipole and exhaustion ticked by nano"; three
separate graphs on one time axis of real timestamps, no lines laid over each other, no window anywhere):
1. THE TRADE PRICE CURVE: the price of every trade, drawn smooth through them. "Smooth" is drawing only: the curve
   passes through every trade's own price at its own time and nothing is averaged. Where several trades share one
   instant it goes through the last of them; every trade is still a dot.
2. THE DIPOLE at the tick: buying against selling, where the two poles are the run of trades under way and the
   run it took over from: the size of the latest run of buying minus the size of the latest run of selling, over
   the two together. It changes at every trade. Empty until there has been one change of hands. Named as Greg's
   rule asks: a run's size ADDS its trades together; the single trades stay on their own rows.
3. THE EXHAUSTION at the tick: each run of trades on one side as it builds trade by trade, buying up and selling
   down; its high is its last trade (the peak with no window, as stored in `turn_peaks`).
Claude's call, stated to Greg, his to correct: one picture holds 600 trades, and the pictures run end to end over
the whole trade day, none left out, as in the sample he looked at.

THE STACKED PAIRS (Greg, 2026-11-18: "We have a lot of trade legs that line up exactly with dipoles ... Let's start
there"): for every recorded dipole whose birth second holds the FIRST trade of a trade leg, two graphs on one
clock: the trade leg's price above (its own life shaded), the dipole at the tick below. The picture runs from the
first trade of the trade leg before to the last trade of the trade leg after, so no span of time is chosen. The
recorded dipole (Native's) only says where to look and is drawn as a mark; it is made on the 20-second window and
enters no calculation. Beside the count of such dipoles the same count is written for ANY second of the trade day
that holds a trade, so the first count can be read against something.

WHAT IS WRITTEN:
- `tick-dipole-<trade day>.parquet`: one line per tick of the trade day: the run under way, the run before it,
  the dipole at the tick and the exhaustion at the tick.
- `three-renders-<trade day>-NNN.png` and `three-renders-index-<trade day>.parquet` (which trades each holds).
- `dipole-leg-pair-<trade day>-<dipole>.png` and `dipole-leg-pairs-<trade day>.parquet` (one line per recorded
  dipole born with a trade: whether a trade leg starts in its birth second, which, and its picture).
- `TICK-RENDERS-<trade day>.json`: the receipt.

The ticks reach this only through `tape.rows_for_calculations()`. Nothing here is averaged, ranked or fitted.

    python3 -m root.tick_renders 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import numpy as np

from root import checks, store, tape
from root.calendar import (EASTERN, NS_PER_SECOND, SETTLE_FROM_EASTERN, SETTLE_TO_EASTERN, eastern, eastern_text,
                           parse_trade_day, to_ns)

READS = ['received_time_ns', 'action', 'side', 'size', 'price']
TRADE = 'T'
SIDE = {'B': 'buy', 'A': 'sell'}
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
TRADES_PER_PICTURE = 600                               # Claude's call, stated to Greg: as in the sample he saw
CURVE_POINTS = 4000                                    # drawing only: how finely the smooth curve is drawn
THREE_INCHES, PAIR_INCHES = (7.2, 11.5), (7.2, 9.0)
DPI = 110
LEAN_LIMIT = 1.05                                      # the dipole runs from -1 to 1; the graph shows a little more
BIG, SMALL, TINY, DOT, HIGH_DOT = 11, 8, 7, 5, 14      # drawing only: letter and dot sizes
LINE, THIN, FAINT, SHADE = 1.4, 0.8, 0.25, 0.4         # drawing only: line widths, the grid, a shaded stretch
GAP, TITLE_AT, TILT = 0.17, 0.985, 30                  # drawing only
CLOCK = slice(11, 19)                                  # the hour, minute and second inside an Eastern time text
PICTURES_AT_ONCE = 4
THREE_GRAPHS, PAIR_GRAPHS, ON_TOP = 3, 2, 3              # drawing only: graphs in a picture; dots drawn over lines

TICK_COLUMNS = [
    ('position_on_tape', 'The tick: its position on the tape. A label only.'),
    ('received_time_ns', 'When the tick was received.'),
    ('run_side', 'The run of trades on one side under way at this tick: buy or sell. Empty before the first trade '
     'with a side.'),
    ('run_size', 'The size traded in that run so far (a run\'s size adds its trades together).'),
    ('run_before_size', 'The size of the run it took over from, at that run\'s last trade. Empty until there has '
     'been one change of hands.'),
    ('dipole_at_tick', 'THE DIPOLE at the tick: the latest run of buying minus the latest run of selling, over the '
     'two together. +1 all buying, -1 all selling. Empty until there has been one change of hands.'),
    ('exhaustion_at_tick', 'THE EXHAUSTION at the tick: the size of the run under way, above zero for buying and '
     'below for selling.'),
    ('run_high', 'Yes on the last trade of a run that a trade on the other side then ended: the high of the peak '
     'with no window. Known only at that later trade.'),
]
PAIR_COLUMNS = [
    ('dipole', 'Native\'s candidate number. A label only.'),
    ('native_birth_ns', 'Native\'s birth time: the start of the birth second, on the received clock.'),
    ('native_polarity', 'Native\'s polarity: +1 net buying, -1 net selling.'),
    ('trades_in_birth_second', 'How many trades printed in the birth second.'),
    ('leg_number', 'The trade leg whose FIRST trade is in the birth second. Empty when no trade leg starts in it.'),
    ('leg_direction', 'Which way that trade leg went.'),
    ('leg_steps', 'How many steps it made. Empty when it was still going at the last tick.'),
    ('leg_first_trade_position', 'Its first trade: position on the tape. A label only.'),
    ('render', 'The stacked pair drawn for it. Empty when no trade leg starts in the birth second.'),
]
TICK_NAMES, PAIR_NAMES = [n for n, _ in TICK_COLUMNS], [n for n, _ in PAIR_COLUMNS]
WORK = {}


def read(rows_folder: Path, trade_day) -> dict:
    out = {name: [] for name in ['position'] + READS}
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        out['position'].append(position)
        for name, value in zip(READS, row):
            out[name].append(value)
    return out


def at_the_tick(t: dict) -> dict:
    """The run under way, the run before it, the dipole and the exhaustion on every tick, by one forward walk."""
    n = len(t['position'])
    side, size, before, high = [None] * n, [None] * n, [None] * n, [False] * n
    now_side = now_size = was = last = None
    for k in range(n):
        s = SIDE.get(t['side'][k]) if t['action'][k] == TRADE else None
        if s is not None:
            if s == now_side:
                now_size += t['size'][k]
            else:
                if now_side is not None:
                    was, high[last] = now_size, True
                now_side, now_size = s, t['size'][k]
            last = k
        side[k], size[k], before[k] = now_side, now_size, was
    dipole, exhaustion = [None] * n, [None] * n
    for k in range(n):
        if size[k] is None:
            continue
        up = side[k] == SIDE['B']
        exhaustion[k] = size[k] if up else -size[k]
        if before[k] is not None:
            bought, sold = (size[k], before[k]) if up else (before[k], size[k])
            dipole[k] = (bought - sold) / (bought + sold)
    return dict(run_side=side, run_size=size, run_before_size=before, dipole_at_tick=dipole,
                exhaustion_at_tick=exhaustion, run_high=high)


def against_stored_runs(rows_folder: Path, day: str, t: dict, a: dict) -> dict:
    """The second method: the run under way on every tick against the one `turn_peaks` stored."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(f'calc-turn_peaks-{day}-part*.parquet'))
    checks.need(files, 'the stored runs of trades (turn_peaks) are not beside the rows')
    stored = {}
    for path in files:
        table = pq.read_table(path, columns=['position_on_tape', 'run_side', 'run_size'])
        for position, side, size in zip(*(table.column(c).to_pylist() for c in table.column_names)):
            stored[position] = (side, size)
    for k, position in enumerate(t['position']):
        checks.need(stored[position] == (a['run_side'][k], a['run_size'][k]),
                    f'the run of trades at position {position} differs from the stored one')
    return dict(passed=True, ticks_compared=len(t['position']),
                what='the side and size of the run of trades under way on every tick, against the stored turn_peaks')


def clock(ns):
    return dt.datetime.fromtimestamp(ns / NS_PER_SECOND, EASTERN).replace(tzinfo=None)


def smooth(axis, times, prices, label=None):
    """The trade price curve: a dot on every trade, and a shape-keeping curve through the last trade of each
    instant (it does not swing past the points)."""
    from scipy.interpolate import PchipInterpolator
    since = np.asarray(times, np.int64) - int(times[0])     # nanoseconds from the first trade: exact as decimals
    prices = np.asarray(prices, float)
    last = np.append(np.diff(since) > 0, True)
    if last.sum() > 1:
        fine = np.linspace(0, float(since[-1]), CURVE_POINTS)
        axis.plot([clock(times[0] + v) for v in fine], PchipInterpolator(since[last].astype(float), prices[last])(fine),
                  color='#b03a2e', lw=LINE)
    axis.scatter([clock(v) for v in times], prices, s=DOT, color='#17202a', zorder=ON_TOP, label=label)
    axis.set_ylabel('trade price, dollars')
    return int((~last).sum())


def finish(figure, axes, path, title):
    for axis in axes:
        lo, hi = WORK['settle']
        left, right = axis.get_xlim()
        axis.axvspan(clock(lo), clock(hi), color='#d5d8dc', alpha=SHADE, label='the settlement window')
        axis.set_xlim(left, right)
        axis.grid(alpha=FAINT)
        axis.tick_params(labelsize=SMALL)
    axes[-1].set_xlabel('Eastern time (the received clock)')
    figure.suptitle(title, fontsize=BIG - 1, y=TITLE_AT)
    figure.autofmt_xdate(rotation=TILT)
    figure.savefig(path, dpi=DPI, bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(figure)
    raw = Path(path).read_bytes()
    return Path(path).name, len(raw), hashlib.sha256(raw).hexdigest()


def draw_three(job) -> tuple:
    """One picture of the three renders. `job` is (file path, title, first trade, one past the last trade)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, a, b = job
    w = WORK
    times, x = w['time'][a:b], [clock(v) for v in w['time'][a:b]]
    figure, axes = plt.subplots(THREE_GRAPHS, 1, figsize=THREE_INCHES, sharex=True, gridspec_kw={'hspace': GAP})
    smooth(axes[0], times, w['price'][a:b])
    axes[0].set_title('1. THE TRADE PRICE CURVE, drawn smooth: through every trade, nothing averaged', loc='left',
                      fontsize=BIG)
    axes[1].step(x, w['dipole'][a:b], where='post', color='#1f618d', lw=1)
    axes[1].axhline(0, color='#aab7b8', lw=THIN)
    axes[1].set_ylim(-LEAN_LIMIT, LEAN_LIMIT)
    axes[1].set_ylabel('buying against selling\n(+1 all buying, -1 all selling)')
    axes[1].set_title('2. THE DIPOLE, at the tick: the run of trades under way against the run before it',
                      loc='left', fontsize=BIG)
    axes[2].step(x, w['exhaustion'][a:b], where='post', color='#17202a', lw=1)
    highs = [k for k in range(a, b) if w['high'][k]]
    axes[2].scatter([clock(w['time'][k]) for k in highs], [w['exhaustion'][k] for k in highs], s=HIGH_DOT,
                    color='#ca6f1e', zorder=ON_TOP, label='the high of a run (its last trade): the peak with no window')
    axes[2].axhline(0, color='#aab7b8', lw=THIN)
    axes[2].set_ylabel('lots in the run\n(buying up, selling down)')
    axes[2].set_title('3. THE EXHAUSTION, at the tick: each run of trades on one side, built trade by trade',
                      loc='left', fontsize=BIG)
    axes[2].legend(fontsize=TINY, loc='best')
    return finish(figure, axes, path, title)


def draw_pair(job) -> tuple:
    """One stacked pair. `job` is (file path, title, first trade, one past the last trade, the leg's first and last
    trade times, the dipole's birth)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, a, b, leg_from, leg_to, birth = job
    w = WORK
    x = [clock(v) for v in w['time'][a:b]]
    figure, axes = plt.subplots(PAIR_GRAPHS, 1, figsize=PAIR_INCHES, sharex=True, gridspec_kw={'hspace': GAP})
    smooth(axes[0], w['time'][a:b], w['price'][a:b], label='a trade')
    axes[0].axvspan(clock(leg_from), clock(leg_to), color='#f9e79f', alpha=SHADE,
                    label='this trade leg\'s own life (first trade to last)')
    axes[0].set_title('THE TRADE LEG: the price of every trade, drawn smooth through them', loc='left', fontsize=BIG)
    axes[1].step(x, w['dipole'][a:b], where='post', color='#1f618d', lw=1)
    axes[1].axhline(0, color='#aab7b8', lw=THIN)
    axes[1].set_ylim(-LEAN_LIMIT, LEAN_LIMIT)
    axes[1].set_ylabel('buying against selling\n(+1 all buying, -1 all selling)')
    axes[1].set_title('THE DIPOLE, at the tick: the run of trades under way against the run before it', loc='left',
                      fontsize=BIG)
    for axis in axes:
        axis.axvspan(clock(birth), clock(birth + NS_PER_SECOND), color='#5d6d7e', alpha=SHADE,
                     label='the second the recorded dipole was born')
        axis.legend(fontsize=TINY, loc='best')
    return finish(figure, axes, path, title)


def helper(cpus, work):
    os.sched_setaffinity(0, {cpus.get()})              # each drawing helper on its own CPU
    WORK.update(work)


def legs_as_stored(rows_folder: Path, day: str) -> dict:
    """The stored trade legs: for each, its first trade, and (when it ended) its last trade, direction and steps."""
    import pyarrow.parquet as pq
    from root.calcs import leg_peaks as LP
    names = ['fact', 'leg_number', 'leg_first_trade_position', 'leg_last_trade_position', 'direction', 'steps']
    legs = {}
    for path in sorted(Path(rows_folder).glob(f'calc-leg_peaks-facts-{day}-part*.parquet')):
        for line in pq.read_table(path, columns=names).to_pylist():
            leg = legs.setdefault(line['leg_number'], dict(number=line['leg_number']))
            if line['fact'] == LP.STARTED:
                leg.update(first=line['leg_first_trade_position'], direction=line['direction'])
            if line['fact'] == LP.ENDED:
                leg.update(first=line['leg_first_trade_position'], last=line['leg_last_trade_position'],
                           direction=line['direction'], steps=line['steps'])
    checks.need(legs, 'the stored trade legs (leg_peaks facts) are not beside the rows')
    return legs


def pins_as_stored(rows_folder: Path, day: str) -> list:
    """Native's dipoles as they were pinned to our tape (`root/dipole_renders.py`): a mark saying where to look."""
    import pyarrow.parquet as pq
    return pq.read_table(Path(rows_folder) / 'renders' / f'dipoles-pinned-{day}.parquet').to_pylist()


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    t = read(rows_folder, trade_day)
    a = at_the_tick(t)
    check = against_stored_runs(rows_folder, day, t, a)
    n = len(t['position'])

    def save(name, columns, text=()):
        table = pa.Table.from_arrays([pa.array(v, type=pa.string() if k in text else None)
                                      for k, v in columns.items()], names=list(columns))
        pq.write_table(table, out / name, compression='zstd', compression_level=store.ZSTD_LEVEL)
        raw = (out / name).read_bytes()
        return dict(file=name, rows=table.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    files = [save(f'tick-dipole-{day}.parquet', dict(
        position_on_tape=t['position'], received_time_ns=t['received_time_ns'], **a), text={'run_side'})]

    prints = [k for k in range(n) if t['action'][k] == TRADE]
    work = dict(time=[t['received_time_ns'][k] for k in prints], price=[t['price'][k] / PRICE_UNIT for k in prints],
                dipole=[float('nan') if a['dipole_at_tick'][k] is None else a['dipole_at_tick'][k] for k in prints],
                exhaustion=[float('nan') if a['exhaustion_at_tick'][k] is None else a['exhaustion_at_tick'][k]
                            for k in prints],
                high=[a['run_high'][k] for k in prints],
                settle=(to_ns(eastern(trade_day, SETTLE_FROM_EASTERN)), to_ns(eastern(trade_day, SETTLE_TO_EASTERN))))
    name_of_day = f'Trade day {trade_day:%a %b %d, %Y}'
    pictures = range(0, len(prints), TRADES_PER_PICTURE)
    three, index = [], []
    for p, first in enumerate(pictures):
        last = min(first + TRADES_PER_PICTURE, len(prints))
        span = (work['time'][last - 1] - work['time'][first]) / NS_PER_SECOND
        name = f'three-renders-{day}-{p:03d}.png'
        three.append((str(out / name),
                      f'{name_of_day}. Picture {p + 1} of {len(pictures)}. No window anywhere.\n{last - first} '
                      f'trades, {span:,.1f} s, from {eastern_text(work["time"][first])[CLOCK]} to '
                      f'{eastern_text(work["time"][last - 1])[CLOCK]} Eastern', first, last))
        index.append((name, t['position'][prints[first]], t['position'][prints[last - 1]], work['time'][first],
                      work['time'][last - 1], last - first))

    legs = legs_as_stored(rows_folder, day)
    starts = sorted((leg['first'], number) for number, leg in legs.items() if 'first' in leg)
    row_of = {position: k for k, position in enumerate(t['position'])}
    trade_of = {k: j for j, k in enumerate(prints)}    # a tick's row -> its place among the trades
    pins = pins_as_stored(rows_folder, day)
    pairs, pair_lines = [], []
    for d in sorted(pins, key=lambda d: d['native_birth_ns']):
        if not d['trades_in_birth_second']:
            continue
        lo, hi = d['first_position_in_birth_second'], d['last_position_in_birth_second']
        here = [number for position, number in starts if lo <= position <= hi]
        if not here:
            pair_lines.append((d['dipole'], d['native_birth_ns'], d['native_polarity'], d['trades_in_birth_second'],
                               None, None, None, None, None))
            continue
        leg = legs[here[0]]
        earlier, later = legs.get(leg['number'] - 1), legs.get(leg['number'] + 1)
        first = trade_of[row_of[earlier['first']]] if earlier and 'first' in earlier else 0
        last = trade_of[row_of[later['last']]] + 1 if later and 'last' in later else len(prints)
        leg_from = t['received_time_ns'][row_of[leg['first']]]
        leg_to = t['received_time_ns'][row_of[leg['last']]] if 'last' in leg else work['time'][-1]
        name = f'dipole-leg-pair-{day}-{d["dipole"]}.png'
        ended = (f'{leg["steps"]} step(s), {(leg_to - leg_from) / NS_PER_SECOND:,.1f} s' if 'last' in leg
                 else 'still going at the last tick')
        pairs.append((str(out / name),
                      f'{name_of_day}. No window.\nRecorded dipole born {eastern_text(d["native_birth_ns"])[CLOCK]} '
                      f'Eastern ({"buying" if (d["native_polarity"] or 0) > 0 else "selling"}; '
                      f'{d["trades_in_birth_second"]} trade(s) in that second, the first trade of trade leg '
                      f'{leg["number"]}).\nLeg {leg["number"]}: {leg["direction"]}, {ended}. Picture: {last - first} '
                      f'trades, {(work["time"][last - 1] - work["time"][first]) / NS_PER_SECOND:,.1f} s.',
                      first, last, leg_from, leg_to, d['native_birth_ns']))
        pair_lines.append((d['dipole'], d['native_birth_ns'], d['native_polarity'], d['trades_in_birth_second'],
                           leg['number'], leg['direction'], leg.get('steps'), leg['first'], name))

    os.sched_setaffinity(0, range(os.cpu_count()))     # the pod pins this program to one CPU; the drawing is
    cpus = multiprocessing.Manager().Queue()           # spread over every CPU the pod allows, one helper on each
    mine = sorted(os.sched_getaffinity(0))
    for cpu in mine:
        cpus.put(cpu)
    with multiprocessing.Pool(len(mine), initializer=helper, initargs=(cpus, work)) as pool:
        drawn = pool.map(draw_three, three, chunksize=PICTURES_AT_ONCE)
        drawn += pool.map(draw_pair, pairs, chunksize=PICTURES_AT_ONCE)
    files.append(save(f'three-renders-index-{day}.parquet', dict(zip(
        ['render', 'first_trade_position', 'last_trade_position', 'first_trade_received_ns',
         'last_trade_received_ns', 'trades'], map(list, zip(*index)))), text={'render'}))
    files.append(save(f'dipole-leg-pairs-{day}.parquet', dict(zip(
        PAIR_NAMES, map(list, zip(*pair_lines)) if pair_lines else [[] for _ in PAIR_NAMES])),
        text={'dipole', 'leg_direction', 'render'}))
    files += [dict(file=name, bytes=size, sha256=sha) for name, size, sha in drawn]

    # the same count for ANY second of the trade day that holds a trade: how many hold a trade leg's first trade
    second = lambda k: t['received_time_ns'][k] // NS_PER_SECOND
    with_a_trade = {second(k) for k in prints}
    with_a_leg_start = {second(row_of[position]) for position, _ in starts}
    receipt = dict(
        what='Greg\'s three renders for the whole trade day, timed at the tick, and the dipoles that line up with '
             'trade legs as stacked pairs',
        asked='Greg, 2026-11-18: "the trade price curve ... dipole and exhaustion ticked by nano"; "We have a lot of '
              'trade legs that line up exactly with dipoles ... Let\'s start there"',
        trade_day=trade_day.isoformat(),
        tick_columns=[dict(column=c, what=w) for c, w in TICK_COLUMNS],
        pair_columns=[dict(column=c, what=w) for c, w in PAIR_COLUMNS],
        counts=dict(
            ticks=n, trades=len(prints), runs_of_trades_ended=sum(a['run_high']),
            three_render_pictures=len(three), trades_in_a_picture=TRADES_PER_PICTURE,
            recorded_dipoles=len(pins), recorded_dipoles_born_with_a_trade=len(pair_lines),
            of_them_with_the_first_trade_of_a_trade_leg_in_the_birth_second=len(pairs),
            seconds_of_the_trade_day_with_a_trade=len(with_a_trade),
            of_them_holding_the_first_trade_of_a_trade_leg=len(with_a_trade & with_a_leg_start),
            trade_legs=len(starts)),
        how_to_read_the_two_counts='A recorded dipole born with a trade has the first trade of a trade leg in its '
                                   'birth second in so many cases; a second with a trade, taken anywhere in the '
                                   'trade day, holds the first trade of a trade leg in so many. Two counts set '
                                   'side by side; no test of chance is made.',
        checks=dict(the_runs_against_the_stored_ones=check),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'TICK-RENDERS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The three renders at the tick, and the dipoles on trade legs')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
