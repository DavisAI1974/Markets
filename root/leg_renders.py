"""ROOT: one picture for every trade leg: its price, with the crypto DIPOLE line and the crypto EXHAUSTION line.

Greg, 2026-11-23: "I want every trade leg compared against the exhaustion and the dipole. And show the prebirths for
the dipole and exhaustion before the trade starts"; "We should not be reinventing the wheel! The instructions should
have been explicit to follow the crypto formulas"; "I want the other 2 graphs exactly like they were in crypto. And no
hardcoded start and stop time for graphs. Dipole and exhaustion start and stop by when the data says and not our
predetermined values".

ONE PICTURE PER TRADE LEG (the stored trade legs of `leg_peaks`: the trade price curve cut into its own moves), three
separate graphs on one clock of real timestamps:
1. THE TRADE PRICE CURVE: the price of every trade, drawn smooth through them (drawing only; every trade is a dot).
2. THE DIPOLE, the crypto formula (`_dipole_price_overlay.py`, Markets `75b15fa`): bought minus sold over bought plus
   sold, over the trades of the last 60 seconds, turned to the trade's side.
3. THE EXHAUSTION, the crypto formula (`research/shape_s71/regroup2.py`, the same commit): the same figure over the
   last 20 seconds, turned to the trade's side.
Both lines are READ FROM WHAT IS STORED: the crypto and ng calculation made them at the nanosecond with the July
rules (`crypto_ng/tick.py`; `crypto-ng-tick/crypto-ng-tick-lean-60s-*` and `crypto-ng-tick-line-20s-*`). Nothing is
worked out here and no other line is drawn under these two names. "Turned to the trade's side" is the crypto step:
for a trade leg up the line is as stored (above zero is buying), for a trade leg down it is turned over (above zero
is selling), so above zero always reads "with this trade leg". A line is empty where nothing traded in its span.

WHAT IS NOT CARRIED FROM THE CRYPTO PICTURES, each on Greg's word: the average over many trades and the winner label;
the cut at 45 or 60 seconds each side; the time grid. One trade leg at a time, every read at its own nanosecond.

WHERE A PICTURE STARTS AND ENDS is said by the data; no number of seconds, typed clock time or count of trades:
- the trade leg sets the frame: from the first trade of the trade leg two before (Greg, 2026-11-23: "Go two trade
  legs back") to the last trade of the trade leg after;
- the dipole and the exhaustion then say where it starts and stops: a HUMP is the time a line stays on one side of
  zero (`whole_humps`), and every hump of either line that the frame touches is in the picture whole.
The receipt names every trade leg whose picture starts at its own first trade (no lead-in).

The trade leg is marked on all three graphs: its own life shaded (first trade to last trade), a line at the print
where it first became known (its first step) and a line at the print that showed it had ended (the step back).
Nothing is averaged, ranked, typed or labelled.

WHAT IS WRITTEN:
- `LEG-RENDERS-COUNT-<trade day>.json`: first, before anything is drawn: how many trade legs the trade day holds
  and how many pictures this run draws.
- `leg-render-<trade day>-<leg number>.png`: one picture per trade leg.
- `leg-renders-index-<trade day>.parquet`: one line per trade leg of the trade day.
- `LEG-RENDERS-<trade day>.json`: the receipt.

    python3 -m root.leg_renders 20231017 --rows <folder of the trade day's stored files> --out <folder> \
        [--stretch <from ns>-<to ns> | --random <how many>] [--keep-cpus]

`--stretch` draws only the trade legs whose first trade was received inside it. `--random` draws that many trade legs
picked at random from the whole trade day (Greg, 2026-11-23: "just pick 10 random ones per day ... to start"); the
pick is the computer's, seeded with the trade day's own number so the same pick comes out again, and the receipt
names it. Either one chooses WHICH trade legs are drawn, never where a picture starts or ends. `--keep-cpus` draws on
the CPUs this program was pinned to (several trade days on one pod, each on its own CPUs).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import numpy as np

from root import checks, store
from root.calcs import leg_peaks as LP
from root.calendar import NS_PER_SECOND, parse_trade_day, trade_day_bounds
from root.crypto_ng_tick import clock, clock_text, whole_humps

LEG_DIGITS = 5                                         # a trade leg's number in its picture's name, written 00000
LEGS_BACK = 2                                          # Greg, 2026-11-23: a picture's frame starts two trade legs back
BYTES_PER_MEGABYTE = 2 ** 20
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
LINES = dict(dipole=('crypto-ng-tick-lean-60s', 60), exhaustion=('crypto-ng-tick-line-20s', 20))   # the stored line
#                                                        each graph reads, and its span in seconds (a label here:
#                                                        the span is in the stored line, `crypto_ng/tick.py`)
SIDE = {LP.UP: (1, 'buying'), LP.DOWN: (-1, 'selling')}   # the crypto turn to the trade's side
INCHES, GRAPHS, DPI = (7.2, 11.5), 3, 110              # drawing only: to be read on a phone
LEAN_LIMIT = 1.05                                      # the lines run from -1 to 1; the graph shows a little more
BIG, SMALL, TINY, DOT = 11, 8, 7, 5                    # drawing only: letter and dot sizes
LINE, THIN, FAINT, SHADE = 1.4, 0.8, 0.25, 0.4         # drawing only: line widths, the grid, the shaded trade leg
GAP, TITLE_AT, TILT, ON_TOP = 0.3, 0.985, 30, 3        # drawing only (the gap leaves room for a two-line graph title)
CURVE_POINTS = 4000                                    # drawing only: how finely the smooth price curve is drawn
PICTURES_AT_ONCE = 4                                   # pictures handed to a drawing helper at once
FACTS = ['fact', 'leg_number', 'direction', 'steps', 'leg_first_trade_position', 'leg_first_trade_received_time_ns',
         'leg_last_trade_position', 'known_position', 'known_received_time_ns', 'leg_start_price', 'price']
INDEX_COLUMNS = [
    ('leg_number', 'The trade leg, counted from the first print of the trade day as `leg_peaks` stores it. A label '
     'only.'),
    ('direction', 'Which way it goes: up or down, read off the prices.'),
    ('steps', 'How many steps of price it made. Empty when it was still going at the last trade.'),
    ('start_price', 'The price it started from, in dollars.'),
    ('end_price', 'The price it ended at, in dollars. Empty when it was still going at the last trade.'),
    ('first_trade_position', 'Its first trade: position on the tape. A label only.'),
    ('first_trade_received_ns', 'When its first trade was received, to the nanosecond.'),
    ('known_position', 'The print where it first became known (its first step): position on the tape.'),
    ('known_received_ns', 'When that print was received.'),
    ('last_trade_position', 'Its last trade. Empty when it was still going at the last trade.'),
    ('last_trade_received_ns', 'When its last trade was received. Empty when it was still going.'),
    ('ended_known_position', 'The print that showed it had ended (the step back). Empty when it was still going.'),
    ('ended_known_received_ns', 'When that print was received.'),
    ('picture_first_ns', 'Where its picture starts, set by the data.'),
    ('picture_last_ns', 'Where its picture ends, set by the data.'),
    ('trades_in_picture', 'How many trades on the tape are inside its picture.'),
    ('render', 'The picture drawn for it in this run. Empty when this run did not draw it.'),
]
INDEX_NAMES = [name for name, _ in INDEX_COLUMNS]
WORK = {}


def table(path: Path, columns: list) -> dict:
    import pyarrow.parquet as pq
    checks.need(path.is_file(), f'{path.name} is not beside the rows')
    return pq.read_table(path, columns=columns).to_pydict()


def stored(rows_folder: Path, day: str) -> dict:
    """Everything a picture is drawn from, as stored for the trade day. Nothing is worked out."""
    tick = rows_folder / 'crypto-ng-tick'
    trades = table(tick / f'crypto-ng-tick-tape-trades-{day}.parquet', ['position_on_tape', 'received_time_ns', 'price'])
    position = np.array(trades['position_on_tape'], np.int64)
    at = np.array(trades['received_time_ns'], np.int64)
    checks.need(len(at) and bool(np.all(np.diff(at) >= 0)) and bool(np.all(np.diff(position) > 0)),
                'the stored trades on the tape are not in tape order')
    s = dict(position=position, time=at, price=np.array(trades['price'], float))
    for name, (file, _) in LINES.items():              # the two crypto lines, each at every moment it changes
        line = table(tick / f'{file}-{day}.parquet', ['moment_received_ns', 'flow'])
        moments = np.array(line['moment_received_ns'], np.int64)
        checks.need(len(moments) and bool(np.all(np.diff(moments) >= 0)), f'the stored {file} is not in time order')
        s[name + '_at'] = moments
        s[name] = np.array([np.nan if v is None else v for v in line['flow']], float)
    return s


def legs_as_stored(rows_folder: Path, day: str) -> list:
    """The stored trade legs in order, each with the facts `leg_peaks` wrote about it."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(f'calc-leg_peaks-facts-{day}-part*.parquet'))
    checks.need(files, 'the stored trade legs (leg_peaks facts) are not beside the rows')
    legs = {}
    for path in files:
        for fact in pq.read_table(path, columns=FACTS).to_pylist():
            leg = legs.setdefault(fact['leg_number'], dict(number=fact['leg_number']))
            if fact['fact'] == LP.STARTED:
                leg.update(direction=fact['direction'], first=fact['leg_first_trade_position'],
                           first_at=fact['leg_first_trade_received_time_ns'], known=fact['known_position'],
                           known_at=fact['known_received_time_ns'], start_price=fact['leg_start_price'])
            if fact['fact'] == LP.ENDED:
                leg.update(steps=fact['steps'], last=fact['leg_last_trade_position'], ended_known=fact['known_position'],
                           ended_known_at=fact['known_received_time_ns'], end_price=fact['price'])
    numbers = sorted(legs)
    checks.need(all('first' in legs[n] and legs[n]['direction'] in SIDE for n in numbers),
                'a stored trade leg has no "leg started" fact, or no direction')
    checks.need(numbers == list(range(numbers[0], numbers[0] + len(numbers))), 'the stored trade legs skip a number')
    checks.need(all('last' in legs[n] for n in numbers[:-1]), 'a trade leg before the last one never ended')
    return [legs[n] for n in numbers]


def edges(legs: list, k: int, s: dict, opens: int, closes: int) -> tuple:
    """Where the picture of trade leg `k` starts and ends. The frame: the first trade of the trade leg two before to
    the last trade of the trade leg after. Then the two lines say where it starts and stops: every hump of the
    dipole line and of the exhaustion line that the frame touches is in the picture whole."""
    leg = legs[k]
    left = legs[max(k - LEGS_BACK, 0)]['first_at']
    after = legs[k + 1] if k + 1 < len(legs) else leg
    right = after['last_at'] if 'last_at' in after else int(s['time'][-1])
    reach = [whole_humps(s[name + '_at'], s[name], int(left), int(right), opens, closes) for name in LINES]
    return min([int(left)] + [first for first, _ in reach]), max([int(right)] + [last for _, last in reach])   # the
#                                                        humps only widen the frame (a trade received a moment
#                                                        after the halt stays in its picture)


def helper(cpus, work):
    os.sched_setaffinity(0, {cpus.get()})              # each drawing helper on its own CPU
    WORK.update(work)


def smooth(axis, times, prices):
    """The trade price curve: a dot on every trade, and a shape-keeping curve through the last trade of each
    instant (it does not swing past the points). Drawing only: nothing is averaged."""
    from scipy.interpolate import PchipInterpolator
    since = np.asarray(times, np.int64) - int(times[0])    # nanoseconds from the first trade: exact as decimals
    prices = np.asarray(prices, float)
    last = np.append(np.diff(since) > 0, True)
    if last.sum() > 1:
        fine = np.linspace(0, float(since[-1]), CURVE_POINTS)
        axis.plot([clock(int(times[0]) + v) for v in fine],
                  PchipInterpolator(since[last].astype(float), prices[last])(fine), color='#b03a2e', lw=LINE)
    axis.scatter([clock(int(v)) for v in times], prices, s=DOT, color='#17202a', zorder=ON_TOP)
    axis.set_ylabel('trade price, dollars')


def cut(moments: np.ndarray, values: np.ndarray, first: int, last: int) -> tuple:
    """A stored line between the picture's two edges: the read standing at the left edge, every read inside, and
    the last one held to the right edge (the line holds its value until its next read)."""
    a = max(int(np.searchsorted(moments, first, 'right')) - 1, 0)
    b = max(int(np.searchsorted(moments, last, 'right')), a + 1)
    return np.r_[np.maximum(moments[a:b], first), last], np.r_[values[a:b], values[b - 1]]


def draw_one(job) -> dict:
    """One trade leg's picture. `job` is (file path, title, the picture's two edges, the leg's first and last trade,
    the print where it became known, the print that showed it had ended or None, the leg's direction)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, first, last, leg_from, leg_to, known_at, ended_at, direction = job
    w = WORK
    turn, with_it = SIDE[direction]
    a, b = int(np.searchsorted(w['time'], first, 'left')), int(np.searchsorted(w['time'], last, 'right'))
    figure, axes = plt.subplots(GRAPHS, 1, figsize=INCHES, sharex=True, gridspec_kw={'hspace': GAP})
    smooth(axes[0], w['time'][a:b], w['price'][a:b])
    axes[0].set_title('1. THE TRADE PRICE CURVE, drawn smooth: through every trade, nothing averaged', loc='left',
                      fontsize=BIG)
    for number, (name, (_, seconds)) in enumerate(LINES.items(), start=GRAPHS - len(LINES)):
        axis = axes[number]
        at, values = cut(w[name + '_at'], w[name], first, last)
        axis.step([clock(int(v)) for v in at], turn * values, where='post', color='#1f618d', lw=1)
        axis.axhline(0, color='#aab7b8', lw=THIN)
        axis.set_ylim(-LEAN_LIMIT, LEAN_LIMIT)
        axis.set_ylabel(f'turned to this trade leg\'s side\n(+1 all {with_it}, with it; -1 all against)')
        axis.set_title(f'{number + 1}. THE {name.upper()}, the crypto formula: bought minus sold over\nbought plus '
                       f'sold, the trades of the last {seconds} seconds', loc='left', fontsize=BIG)
    for axis in axes:
        axis.axvspan(clock(leg_from), clock(leg_to), color='#f9e79f', alpha=SHADE,
                     label='this trade leg (first trade to last)')
        axis.axvline(clock(known_at), color='#1e8449', lw=THIN, ls='--',
                     label='the print where it became known (its first step)')
        if ended_at is not None:
            axis.axvline(clock(ended_at), color='#922b21', lw=THIN, ls=':',
                         label='the print that showed it had ended (the step back)')
        axis.grid(alpha=FAINT)
        axis.tick_params(labelsize=SMALL)
    axes[0].legend(fontsize=TINY, loc='best')
    axes[-1].set_xlabel('Eastern time (the received clock)')
    figure.suptitle(title, fontsize=BIG - 1, y=TITLE_AT)
    figure.autofmt_xdate(rotation=TILT)
    figure.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(figure)
    raw = Path(path).read_bytes()
    return dict(file=Path(path).name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path, stretch=None, pick=None, keep_cpus=False) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, closes = trade_day_bounds(trade_day)
    s = stored(rows_folder, day)
    legs = legs_as_stored(rows_folder, day)

    place = {int(p): k for k, p in enumerate(s['position'].tolist())}
    for leg in legs:                                   # every trade leg sits on trades the stored tape holds
        checks.need(leg['first'] in place and leg['known'] in place and leg.get('last', leg['first']) in place,
                    f'trade leg {leg["number"]} names a trade the stored tape does not hold')
        checks.need(int(s['time'][place[leg['first']]]) == leg['first_at'],
                    f'trade leg {leg["number"]}: its first trade is stored with another time on the tape')
        if 'last' in leg:
            leg['last_at'] = int(s['time'][place[leg['last']]])
            checks.need(leg['first_at'] <= leg['known_at'] and leg['first_at'] <= leg['last_at'] <= leg['ended_known_at'],
                        f'trade leg {leg["number"]}: its stored moments are out of order')

    asked = [k for k, leg in enumerate(legs) if stretch is None or stretch[0] <= leg['first_at'] <= stretch[1]]
    checks.need(asked, 'no trade leg has its first trade inside the stretch asked for')
    if pick is not None:                               # a pick at random, the same one every time it is run
        asked = sorted(np.random.default_rng(int(day)).choice(asked, size=min(pick, len(asked)), replace=False).tolist())
    count = dict(trade_day=trade_day.isoformat(), trade_legs_in_the_trade_day=len(legs), pictures_this_run_draws=len(asked),
                 trades_on_the_tape=len(s['time']),
                 drawn=('every trade leg of the trade day' if stretch is None else
                        f'the trade legs whose first trade was received from {clock_text(stretch[0])} to '
                        f'{clock_text(stretch[1])} Eastern') if pick is None else
                       f'{len(asked)} trade legs picked at random by the computer (seeded with the trade day\'s own '
                       f'number, {int(day)}, so the same pick comes out again): {[legs[k]["number"] for k in asked]}')
    (out / f'LEG-RENDERS-COUNT-{day}.json').write_text(json.dumps(count, indent=1) + '\n')

    name_of_day = f'Trade day {trade_day:%a %b %d, %Y}'
    dollars = lambda price: None if price is None else price / PRICE_UNIT
    jobs, lines, no_lead_in, wanted = [], [], [], set(asked)
    for k, leg in enumerate(legs):
        first, last = edges(legs, k, s, opens, closes)
        leg_to = leg.get('last_at', int(s['time'][-1]))
        checks.need(first <= leg['first_at'] and leg_to <= last,
                    f'trade leg {leg["number"]}: its picture does not hold it whole')
        inside = int(np.searchsorted(s['time'], last, 'right')) - int(np.searchsorted(s['time'], first, 'left'))
        if first == leg['first_at']:
            no_lead_in.append(leg['number'])
        name = f'leg-render-{day}-{leg["number"]:0{LEG_DIGITS}d}.png' if k in wanted else None
        if name:
            went = (f'{leg["steps"]} step(s), {dollars(leg["start_price"]):.3f} to {dollars(leg["end_price"]):.3f}, '
                    f'{(leg_to - leg["first_at"]) / NS_PER_SECOND:,.3f} s' if 'last' in leg else
                    f'from {dollars(leg["start_price"]):.3f}, still going at the last trade')
            jobs.append((str(out / name),
                         f'{name_of_day}. Trade leg {leg["number"]}: {leg["direction"]}, {went}.\n'
                         f'The trade leg (shaded): {clock_text(leg["first_at"])} to {clock_text(leg_to)} Eastern.\n'
                         f'Drawn: {clock_text(first)} to {clock_text(last)}, {inside} trades.\n'
                         f'It runs from two trade legs before to the trade leg after, and the dipole and the\n'
                         f'exhaustion set where it starts and stops: every hump of either line is whole.\n'
                         f'Nothing averaged. Every read at its own nanosecond.',
                         first, last, leg['first_at'], leg_to, leg['known_at'], leg.get('ended_known_at'),
                         leg['direction']))
        lines.append((leg['number'], leg['direction'], leg.get('steps'), dollars(leg['start_price']),
                      dollars(leg.get('end_price')), leg['first'], leg['first_at'], leg['known'], leg['known_at'],
                      leg.get('last'), leg.get('last_at'), leg.get('ended_known'), leg.get('ended_known_at'),
                      first, last, inside, name))

    if not keep_cpus:                                  # the pod pins this program to one CPU; the drawing is
        os.sched_setaffinity(0, range(os.cpu_count()))   # spread over every CPU the pod allows, one helper on each
    cpus = multiprocessing.Manager().Queue()
    mine = sorted(os.sched_getaffinity(0))
    for cpu in mine:
        cpus.put(cpu)
    work = {name: s[name] for name in ('time', 'price', *LINES, *(name + '_at' for name in LINES))}
    with multiprocessing.Pool(len(mine), initializer=helper, initargs=(cpus, work)) as pool:
        drawn = pool.map(draw_one, jobs, chunksize=PICTURES_AT_ONCE)
    checks.need(len(drawn) == len(asked) == len({f['file'] for f in drawn}),
                'not every trade leg asked for was drawn exactly once')

    index = pa.Table.from_arrays([pa.array(list(column), type=pa.string() if name in ('direction', 'render') else None)
                                  for name, column in zip(INDEX_NAMES, zip(*lines))], names=INDEX_NAMES)
    index_name = f'leg-renders-index-{day}.parquet'
    pq.write_table(index, out / index_name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / index_name).read_bytes()
    picture_bytes = sum(f['bytes'] for f in drawn)
    receipt = dict(
        what='One picture for every trade leg: the trade price curve, the crypto dipole line (60 seconds) and the '
             'crypto exhaustion line (20 seconds) on one clock, both turned to the trade leg\'s side, the trade leg '
             'marked on all three, with what came before it and after it',
        asked='Greg, 2026-11-23: "I want every trade leg compared against the exhaustion and the dipole. And show '
              'the prebirths for the dipole and exhaustion before the trade starts"; "I want the other 2 graphs '
              'exactly like they were in crypto. And no hardcoded start and stop time for graphs. Dipole and '
              'exhaustion start and stop by when the data says and not our predetermined values"',
        trade_day=trade_day.isoformat(),
        the_two_lines={name: dict(read_from=f'crypto-ng-tick/{file}-{day}.parquet', span_seconds=seconds,
                                  formula='bought minus sold over bought plus sold, over the trades received in '
                                          'the span, read at the nanosecond; turned to the trade leg\'s side')
                       for name, (file, seconds) in LINES.items()},
        edges='set by the data: the frame runs from the first trade of the trade leg two before to the last trade '
              'of the trade leg after; every hump of the dipole line and of the exhaustion line that the frame '
              'touches is in the picture whole (a hump is the time a line stays on one side of zero)',
        index_columns=[dict(column=c, what=w) for c, w in INDEX_COLUMNS],
        counts=dict(count, pictures_drawn=len(drawn), picture_bytes=picture_bytes,
                    picture_megabytes=round(picture_bytes / BYTES_PER_MEGABYTE, 1),
                    largest_picture_bytes=max(f['bytes'] for f in drawn),
                    trade_legs_still_going_at_the_last_trade=sum('last' not in leg for leg in legs),
                    trade_legs_whose_picture_starts_at_their_own_first_trade=len(no_lead_in),
                    helpers=len(mine)),
        trade_legs_with_no_lead_in=no_lead_in,
        checks=dict(passed=True,
                    what='every trade leg sits on trades the stored tape holds, with the stored time; its stored '
                         'moments are in order; both stored lines are in time order; every picture holds its trade '
                         'leg whole; every trade leg asked for was drawn exactly once'),
        read_from=[f'calc-leg_peaks-facts-{day}-part*.parquet',
                   f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet'] +
                  [f'crypto-ng-tick/{file}-{day}.parquet' for file, _ in LINES.values()],
        nothing_applied='Nothing is worked out, averaged, ranked, typed or labelled: stored values, drawn.',
        files=[dict(file=index_name, rows=index.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())] + drawn,
        seconds=round(time.monotonic() - started, 1))
    (out / f'LEG-RENDERS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='One picture for every trade leg: price, crypto dipole, crypto exhaustion')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--stretch', help='<from ns>-<to ns>: draw only the trade legs whose first trade is inside it')
    ap.add_argument('--random', type=int, help='draw this many trade legs, picked at random from the trade day')
    ap.add_argument('--keep-cpus', action='store_true', help='draw on the CPUs this program was pinned to')
    a = ap.parse_args()
    stretch = tuple(int(v) for v in a.stretch.split('-')) if a.stretch else None
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out, stretch, a.random, a.keep_cpus)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
