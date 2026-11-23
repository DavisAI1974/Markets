"""ROOT: one picture for every trade leg, with the dipole and the exhaustion before, through and after it.

Greg, 2026-11-23: "I want every trade leg compared against the exhaustion and the dipole. And show the prebirths for
the dipole and exhaustion before the trade starts"; "Those 3 renders I mean. Per trade". Before it (2026-11-18): "we
need to get the individual trade renders. we decided that the full day doesn't really tell us much when done on one
render".

ONE PICTURE PER TRADE LEG (the stored trade legs of `leg_peaks`: the trade price curve cut into its own moves), each
his THREE RENDERS (`root/tick_renders.py`) as three separate graphs on one clock of real timestamps, no window
anywhere:
1. the trade price curve; 2. the dipole at the tick; 3. the exhaustion at the tick.
The trade leg is marked on all three graphs: its own life shaded (first trade to last trade), a line at the print
where it first became known (its first step) and a line at the print that showed it had ended (the step back).

WHERE A PICTURE STARTS AND ENDS is said by the data (Greg, 2026-11-18: "We need the data to be telling us what those
times are"); no number of seconds, typed clock time or count of trades is in it:
- it starts at the first trade of the trade leg TWO BEFORE this one (Greg, 2026-11-23: "Go two trade legs back"; one
  back could leave a few seconds and a single trade), so what the dipole and the exhaustion did before the trade
  leg began (the prebirth) is in the picture;
- it ends at the last trade of the trade leg AFTER this one;
- both edges are then moved outward so that nothing they touch is cut: the run of trades on one side (the
  exhaustion at the tick) and the stretch of the dipole standing there, as stored in `continuing/`, are in the
  picture whole.
The first trade leg of a trade day has no trade leg before it, the second has one, and the last has none after it; a trade leg still
going at the last trade runs to the last trade. The receipt names every trade leg whose picture starts at its own
first trade (no lead-in).

Nothing is worked out here: every value drawn is read from an output already stored for the trade day. Nothing is
averaged, ranked, typed or labelled. The index table holds, for every trade leg, its own stored facts and the two
edges of its picture.

WHAT IS WRITTEN:
- `LEG-RENDERS-COUNT-<trade day>.json`: first, before anything is drawn: how many trade legs the trade day holds
  and how many pictures this run draws.
- `leg-render-<trade day>-<leg number>.png`: one picture per trade leg.
- `leg-renders-index-<trade day>.parquet`: one line per trade leg of the trade day.
- `LEG-RENDERS-<trade day>.json`: the receipt: the counts, the checks, the size of the pictures, every file's
  fingerprint.

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
from root import tick_renders as TR
from root.calcs import leg_peaks as LP
from root.calendar import NS_PER_SECOND, parse_trade_day
from root.crypto_ng_tick import clock, clock_text

LEG_DIGITS = 5                                         # a trade leg's number in its picture's name, written 00000
LEGS_BACK = 2                                          # Greg, 2026-11-23: a picture starts two trade legs back
BYTES_PER_MEGABYTE = 2 ** 20
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
    ticks = table(rows_folder / 'tick-renders' / f'tick-dipole-{day}.parquet',
                  ['position_on_tape', 'dipole_at_tick', 'exhaustion_at_tick', 'run_high'])
    position = np.array(trades['position_on_tape'], np.int64)
    at = np.array(trades['received_time_ns'], np.int64)
    checks.need(len(at) and bool(np.all(np.diff(at) >= 0)) and bool(np.all(np.diff(position) > 0)),
                'the stored trades on the tape are not in tape order')
    tick_position = np.array(ticks['position_on_tape'], np.int64)
    where = np.minimum(np.searchsorted(tick_position, position), len(tick_position) - 1)
    checks.need(np.array_equal(tick_position[where], position),
                'a trade on the tape has no line in the stored dipole at the tick')
    empty = lambda values: np.array([np.nan if values[k] is None else values[k] for k in where.tolist()], float)
    spans = {}
    for name in ('runs', 'dipole'):                    # each run of trades and each stretch of the dipole, as stored
        held = table(rows_folder / 'continuing' / f'continuing-{name}-{day}.parquet',
                     ['began_received_ns', 'ended_received_ns'])
        began, ended = np.array(held['began_received_ns'], np.int64), np.array(held['ended_received_ns'], np.int64)
        checks.need(bool(np.all(np.diff(began) >= 0)) and bool(np.all(ended >= began)),
                    f'the stored {name} of the search are not in order')
        spans[name] = (began, ended)
    return dict(position=position, time=at, price=np.array(trades['price'], float), dipole=empty(ticks['dipole_at_tick']),
                exhaustion=empty(ticks['exhaustion_at_tick']), high=[bool(ticks['run_high'][k]) for k in where.tolist()],
                spans=spans)


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
    checks.need(all('first' in legs[n] for n in numbers), 'a stored trade leg has no "leg started" fact')
    checks.need(numbers == list(range(numbers[0], numbers[0] + len(numbers))), 'the stored trade legs skip a number')
    checks.need(all('last' in legs[n] for n in numbers[:-1]), 'a trade leg before the last one never ended')
    return [legs[n] for n in numbers]


def standing(span: tuple, moment: int) -> tuple:
    """The stored run (or stretch) the moment falls inside: where it began and where it ended. The moment itself,
    twice, when none holds it."""
    began, ended = span
    k = int(np.searchsorted(began, moment, 'right')) - 1
    if k < 0 or ended[k] < moment:
        return moment, moment
    last = int(ended[k])
    while k > 0 and ended[k - 1] >= moment:            # several trades received at one nanosecond: the earliest
        k -= 1
    return int(began[k]), last


def edges(legs: list, k: int, s: dict) -> tuple:
    """Where the picture of trade leg `k` starts and ends: from the first trade of the trade leg two before to the
    last trade of the trade leg after, moved outward so no run of trades or stretch of the dipole it touches is cut."""
    leg = legs[k]
    left = legs[max(k - LEGS_BACK, 0)]['first_at']
    after = legs[k + 1] if k + 1 < len(legs) else leg
    right = after['last_at'] if 'last_at' in after else int(s['time'][-1])
    for span in s['spans'].values():
        left, right = min(left, standing(span, left)[0]), max(right, standing(span, right)[1])
    return int(left), int(right)


def helper(cpus, work):
    os.sched_setaffinity(0, {cpus.get()})              # each drawing helper on its own CPU
    WORK.update(work)


def draw_one(job) -> dict:
    """One trade leg's picture: the three renders, the trade leg marked on each. `job` is (file path, title, the
    picture's two edges, the leg's first and last trade, the print where it became known, the print that showed it
    had ended or None)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, first, last, leg_from, leg_to, known_at, ended_at = job
    w = WORK
    a, b = int(np.searchsorted(w['time'], first, 'left')), int(np.searchsorted(w['time'], last, 'right'))
    x = [clock(int(v)) for v in w['time'][a:b]]
    figure, axes = plt.subplots(TR.THREE_GRAPHS, 1, figsize=TR.THREE_INCHES, sharex=True,
                                gridspec_kw={'hspace': TR.GAP})
    price, dipole, exhaustion = axes
    TR.smooth(price, w['time'][a:b], w['price'][a:b])
    price.set_title('1. THE TRADE PRICE CURVE, drawn smooth: through every trade, nothing averaged', loc='left',
                    fontsize=TR.BIG)
    dipole.step(x, w['dipole'][a:b], where='post', color='#1f618d', lw=1)
    dipole.axhline(0, color='#aab7b8', lw=TR.THIN)
    dipole.set_ylim(-TR.LEAN_LIMIT, TR.LEAN_LIMIT)
    dipole.set_ylabel('buying against selling\n(+1 all buying, -1 all selling)')
    dipole.set_title('2. THE DIPOLE, at the tick: the run of trades under way against the run before it', loc='left',
                     fontsize=TR.BIG)
    exhaustion.step(x, w['exhaustion'][a:b], where='post', color='#17202a', lw=1)
    highs = [k for k in range(a, b) if w['high'][k]]
    exhaustion.scatter([clock(int(w['time'][k])) for k in highs], [w['exhaustion'][k] for k in highs], s=TR.HIGH_DOT,
                       color='#ca6f1e', zorder=TR.ON_TOP, label='the high of a run (its last trade)')
    exhaustion.axhline(0, color='#aab7b8', lw=TR.THIN)
    exhaustion.set_ylabel('lots in the run\n(buying up, selling down)')
    exhaustion.set_title('3. THE EXHAUSTION, at the tick: each run of trades on one side, built trade by trade',
                         loc='left', fontsize=TR.BIG)
    for axis in axes:
        axis.axvspan(clock(leg_from), clock(leg_to), color='#f9e79f', alpha=TR.SHADE,
                     label='this trade leg (first trade to last)')
        axis.axvline(clock(known_at), color='#1e8449', lw=TR.THIN, ls='--',
                     label='the print where it became known (its first step)')
        if ended_at is not None:
            axis.axvline(clock(ended_at), color='#922b21', lw=TR.THIN, ls=':',
                         label='the print that showed it had ended (the step back)')
        axis.grid(alpha=TR.FAINT)
        axis.tick_params(labelsize=TR.SMALL)
    exhaustion.legend(fontsize=TR.TINY, loc='best')
    exhaustion.set_xlabel('Eastern time (the received clock)')
    figure.suptitle(title, fontsize=TR.BIG - 1, y=TR.TITLE_AT)
    figure.autofmt_xdate(rotation=TR.TILT)
    figure.savefig(path, dpi=TR.DPI, bbox_inches='tight')
    plt.close(figure)
    raw = Path(path).read_bytes()
    return dict(file=Path(path).name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path, stretch=None, pick=None, keep_cpus=False) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
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
    counted_before = [json.loads(p.read_text())['counts']['trade_legs']
                      for p in sorted(rows_folder.rglob(f'TICK-RENDERS-{day}.json'))]
    checks.need(all(n == len(legs) for n in counted_before),
                f'{len(legs)} trade legs here, {counted_before} in the stored receipt of the tick renders')

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
    dollars = lambda price: None if price is None else price / TR.PRICE_UNIT
    jobs, lines, no_lead_in, wanted = [], [], [], set(asked)
    for k, leg in enumerate(legs):
        first, last = edges(legs, k, s)
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
                         f'It starts at the first trade of the trade leg two before and ends at the last trade of the\n'
                         f'trade leg after; every run of trades and dipole stretch it touches is whole.\n'
                         f'Nothing averaged. Every trade at its own nanosecond.',
                         first, last, leg['first_at'], leg_to, leg['known_at'], leg.get('ended_known_at')))
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
    work = {name: s[name] for name in ('time', 'price', 'dipole', 'exhaustion', 'high')}
    with multiprocessing.Pool(len(mine), initializer=helper, initargs=(cpus, work)) as pool:
        drawn = pool.map(draw_one, jobs, chunksize=TR.PICTURES_AT_ONCE)
    checks.need(len(drawn) == len(asked) == len({f['file'] for f in drawn}),
                'not every trade leg asked for was drawn exactly once')

    index = pa.Table.from_arrays([pa.array(list(column), type=pa.string() if name in ('direction', 'render') else None)
                                  for name, column in zip(INDEX_NAMES, zip(*lines))], names=INDEX_NAMES)
    index_name = f'leg-renders-index-{day}.parquet'
    pq.write_table(index, out / index_name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / index_name).read_bytes()
    picture_bytes = sum(f['bytes'] for f in drawn)
    receipt = dict(
        what='One picture for every trade leg: his three renders (the trade price curve, the dipole at the tick, the '
             'exhaustion at the tick) on one clock, the trade leg marked on all three, with what came before it and '
             'after it',
        asked='Greg, 2026-11-23: "I want every trade leg compared against the exhaustion and the dipole. And show '
              'the prebirths for the dipole and exhaustion before the trade starts"; "Those 3 renders I mean. Per '
              'trade"',
        trade_day=trade_day.isoformat(),
        edges='set by the data: from the first trade of the trade leg two before to the last trade of the trade leg '
              'after, moved outward so no run of trades or stretch of the dipole it touches is cut',
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
                         'moments are in order; the count of trade legs is the one in the stored receipt of the tick '
                         'renders; every picture holds its trade leg whole; every trade leg asked for was drawn '
                         'exactly once',
                    stored_receipts_compared=len(counted_before)),
        read_from=[f'calc-leg_peaks-facts-{day}-part*.parquet', f'tick-renders/tick-dipole-{day}.parquet',
                   f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet',
                   f'continuing/continuing-runs-{day}.parquet', f'continuing/continuing-dipole-{day}.parquet'],
        nothing_applied='Nothing is worked out, averaged, ranked, typed or labelled: stored values, drawn.',
        files=[dict(file=index_name, rows=index.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())] + drawn,
        seconds=round(time.monotonic() - started, 1))
    (out / f'LEG-RENDERS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='One picture for every trade leg, the three renders on one clock')
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
