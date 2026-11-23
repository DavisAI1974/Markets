"""ROOT: one picture for every trade of the crypto and ng program, set up as the crypto pictures were.

Greg, 2026-11-23, on his crypto pictures ("Dipole (flow) over Price ... aligned to the turn" and the July 7 exhaustion
graphs): "Yes I want the prebirths laid out. Not worried about the 2000 averaging. I just want to make sure we are
setting them up the same. Show each individual trade and their prebirths like this without designated start times for
dipole and exhaustion. Their start times are when they start showing up."

THE SET-UP IS THE CRYPTO ONE (Markets `75b15fa`: `_dipole_price_overlay.py`, `research/shape_s71/regroup2.py`):
- THE TRADE is a trade of the crypto and ng program (`crypto_ng/tick.py`, stored in
  `crypto-ng-tick/crypto-ng-tick-program-trades-*`): what the crypto exhaustion graphs were drawn around.
- ZERO on the clock is THE TRADE'S START (its onset), as in those graphs. The clock is in seconds from it; each read
  is still placed at its own nanosecond. The title gives the Eastern time.
- THE PRICE is the MID price (halfway between the best bid and the best ask, the crypto picture's price), in
  dollars as it stood, with TWO POINTS on it and nothing else (Greg, 2026-11-23: "Just show price graph with 2
  points: bought and sold"): where the trade was bought and where it was sold. A buy is bought at its start and
  sold at its end; a sell is sold at its start and bought at its end. Each point sits at the price of the trade on
  the tape that filled it there (at the mid standing then, when the trade ended at no tick).
- THE DIPOLE is the crypto picture's orange line: bought minus sold over bought plus sold over the trades of the
  last 60 seconds, turned to the trade's side.
- THE EXHAUSTION is the July 7 line: the same figure over the last 20 seconds, turned to the trade's side.
The two lines are READ FROM WHAT IS STORED (`crypto-ng-tick-lean-60s-*`, `crypto-ng-tick-line-20s-*`); the mid is
read from the stored rows through the rows gate. The dipole and the exhaustion are "turned to the trade's side":
above zero reads "with this trade". The price is not turned. Five separate graphs on the one clock: the three
lines, then the two rates.

WHAT IS NOT CARRIED, each on Greg's word: the average of many trades; the winner and loser labels; the short or long
split; the cut at 45 or 60 seconds each side; the time grid. One trade at a time.
THE TWO RATE LINES of the crypto dipole picture (how fast the dipole and the price change) are read PER TICK, not per
second (Greg, 2026-11-23: "instead of per sec, we are doing per tick like price"): the dipole's rate is its change at
each of its own reads, and the price's rate is the change of the mid at each tick it moves. Each is drawn as a
stroke at the nanosecond of that tick, in its own graph. Nothing else is worked out here.

NO DESIGNATED START OR STOP. The frame runs from the start of the trade two before (Greg, 2026-11-23: "2 trades back
is great") to the end of the trade after; then the dipole and the exhaustion say where the picture starts and
stops: every hump of either line that the frame touches (the time a line stays on one side of zero) is in the
picture whole, so each line is on the page from where it began to show.

The trade is marked on the four graphs under the price: its own life shaded (start to end), a line at zero, and a
line at the turn the program marked before it. The price graph carries only its two points. Nothing is averaged, ranked, typed or labelled. OBSERVATION ONLY.

WHAT IS WRITTEN: `TRADE-RENDERS-COUNT-<trade day>.json` (first: how many trades the trade day holds and how many
pictures this run draws), `trade-render-<trade day>-<trade number>.png`, `trade-renders-index-<trade day>.parquet`
(one line per trade of the program), `TRADE-RENDERS-<trade day>.json` (the receipt).

    python3 -m root.trade_renders 20231017 --rows <folder of the trade day's stored files> --out <folder> \
        [--random <how many> | --only <trade day>:<trade number> ...] [--quotes] [--keep-cpus]

`--quotes` adds THE BEST BID and THE BEST OFFER, each its own graph under the price (Greg, 2026-11-23: "separate best
bid and offer price curves by tick during the trade period ... I want to see the flow up and down ... make these
curves rounded instead of straight lines unless price isn't changing then it would be straight"). A test of an idea
of his, on trades he names or Claude picks: nothing is worked out, the stored quote is drawn.
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

from root import checks, store, tape
from root import leg_renders as LR
from root.calendar import NS_PER_SECOND, parse_trade_day, trade_day_bounds
from root.crypto_ng_tick import HALVE, clock_text, number, whole_humps

TRADE_DIGITS = 5                                       # a trade's number in its picture's name, written 00000
TRADES_BACK = 2                                        # Greg, 2026-11-23: a picture's frame starts two trades back
GRAPHS, INCHES = 5, (7.2, 18.0)                        # drawing only: the three lines and the two rates, for a phone
SIDE = dict(buy=(1, 'buying'), sell=(-1, 'selling'))   # the crypto turn to the trade's side
RATES = ('dipole', 'price')                            # the crypto picture's two rate lines, in its order
QUOTES = dict(bid=('best bid', '#1f618d'), ask=('best offer', '#b03a2e'))   # Greg's idea of 2026-11-23: each its own graph
PAIR = ('one', 'other')                                # a curve needs two points
CURVE_POINTS = 4000                                    # drawing only: how finely a rounded curve is drawn
READS = ['received_time_ns', 'best_bid', 'best_ask']
TRADES = ['trade', 'side', 'turn_received_ns', 'onset_position_on_tape', 'onset_received_ns', 'ended',
          'end_position_on_tape', 'end_received_ns', 'length_seconds']
POINTS = dict(buy=('bought', 'sold'), sell=('sold', 'bought'))   # what the trade did at its start and at its end
MARKS = dict(bought=('^', '#1e8449'), sold=('v', '#922b21'))     # drawing only: the two points
POINT = 60                                             # drawing only: the size of a point
INDEX_COLUMNS = [
    ('trade', 'The trade of the crypto and ng program, in the order they started. A label only.'),
    ('side', 'buy or sell: the side the program took.'),
    ('turn_received_ns', 'The moment the program marked the turn it was made on.'),
    ('onset_received_ns', 'THE START: when the trade on the tape that filled it was received. Zero on its picture.'),
    ('end_received_ns', 'When it ended. Empty when it was still open at the last tick of the trade day.'),
    ('ended', 'How it ended, in the words of the July rule that ended it.'),
    ('length_seconds', 'From its start to its end, in seconds.'),
    ('start_price', 'The price of the point at its start, in dollars: the trade on the tape that filled it.'),
    ('end_price', 'The price of the point at its end, in dollars: the trade on the tape that ended it, or the mid '
     'price standing then when it ended at no tick. Empty when it was still open.'),
    ('picture_first_ns', 'Where its picture starts, set by the data.'),
    ('picture_last_ns', 'Where its picture ends, set by the data.'),
    ('render', 'The picture drawn for it in this run. Empty when this run did not draw it.'),
]
INDEX_NAMES = [name for name, _ in INDEX_COLUMNS]
WORK = {}


def quotes(rows_folder: Path, trade_day) -> dict:
    """What the stored rows hold of the quote, through the rows gate, in dollars:
    - the MID price at every moment it changes (halfway between the best bid and the best ask, held from the last
      tick that had both);
    - the BEST BID and the BEST ASK, each as the points a rounded curve is drawn through: for every stretch a
      price stands unchanged, its first tick and its last tick. Between the two the price is not changing and the
      curve is a straight line; from the last tick of one price to the first tick of the next it is rounded.
      Where several ticks share one nanosecond the last of them is taken."""
    held = {name: [] for name in READS}
    for _, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        for name, value in zip(READS, row):
            held[name].append(value)
    received = np.array(held['received_time_ns'], np.int64)
    checks.need(len(received) and bool(np.all(np.diff(received) >= 0)), 'the received time goes backwards')
    bid, ask = number(held['best_bid']), number(held['best_ask'])
    both = ~np.isnan(bid) & ~np.isnan(ask)
    checks.need(bool(both.any()), 'no tick of the trade day has both a best bid and a best ask')
    mid, at = ((bid + ask) / HALVE / LR.PRICE_UNIT)[both], received[both]
    changed = np.append(True, np.diff(mid) != 0)
    out = dict(mid_at=at[changed], mid=mid[changed])
    for name, price in (('bid', bid), ('ask', ask)):
        there = ~np.isnan(price)
        t, v = received[there], price[there] / LR.PRICE_UNIT
        last_of_instant = np.append(t[1:] != t[:-1], True)
        t, v = t[last_of_instant], v[last_of_instant]
        starts = np.append(True, v[1:] != v[:-1])      # the first tick of each stretch at one price
        ends = np.append(starts[1:], True)             # and its last tick
        out[name + '_at'], out[name] = t[starts | ends], v[starts | ends]
    return out


def trades_as_stored(rows_folder: Path, day: str) -> list:
    held = LR.table(rows_folder / 'crypto-ng-tick' / f'crypto-ng-tick-program-trades-{day}.parquet', TRADES)
    trades = [dict(zip(TRADES, values)) for values in zip(*(held[name] for name in TRADES))]
    checks.need(trades, 'the stored trades of the program are empty')
    checks.need(all(t['side'] in SIDE for t in trades), 'a stored trade of the program has no side')
    starts = [t['onset_received_ns'] for t in trades]
    checks.need(starts == sorted(starts), 'the stored trades of the program are not in the order they started')
    checks.need(all(t['end_received_ns'] is None or t['end_received_ns'] >= t['onset_received_ns'] for t in trades),
                'a stored trade of the program ends before it starts')
    checks.need(all(t['end_received_ns'] is not None for t in trades[:-1]), 'a trade before the last one never ended')
    return trades


def edges(trades: list, k: int, s: dict, last_tick: int, opens: int, closes: int) -> tuple:
    """Where the picture of trade `k` starts and ends. The frame: the start of the trade two before to the end of
    the trade after. Then every hump of the dipole line and of the exhaustion line that the frame touches is in the
    picture whole. The humps only widen the frame."""
    left = trades[max(k - TRADES_BACK, 0)]['onset_received_ns']
    after = trades[min(k + 1, len(trades) - 1)]
    right = after['end_received_ns'] if after['end_received_ns'] is not None else last_tick
    reach = [whole_humps(s[name + '_at'], s[name], int(left), int(right), opens, closes) for name in LR.LINES]
    return min([int(left)] + [first for first, _ in reach]), max([int(right)] + [last for _, last in reach])


def helper(cpus, work):
    os.sched_setaffinity(0, {cpus.get()})              # each drawing helper on its own CPU
    WORK.update(work)


def rounded(axis, seconds, knots_at: np.ndarray, knots: np.ndarray, first: int, last: int, colour: str):
    """A best price as a rounded curve between the picture's two edges: straight where the price is not changing,
    rounded from one price to the next (a shape-keeping curve: it never swings past a price that stood)."""
    from scipy.interpolate import PchipInterpolator
    a = max(int(np.searchsorted(knots_at, first, 'right')) - 1, 0)
    b = min(int(np.searchsorted(knots_at, last, 'left')) + 1, len(knots_at))
    x, y = knots_at[a:b], knots[a:b]
    if len(x) < len(PAIR):                             # one price through the whole picture, or none at all
        axis.plot(seconds([first, last]), [y[0], y[0]] if len(x) else [np.nan, np.nan], color=colour, lw=LR.LINE)
        return
    left, right = max(first, int(x[0])), min(last, int(x[-1]))
    inside = x[(x >= left) & (x <= right)]
    grid = np.union1d(np.linspace(left, right, CURVE_POINTS).astype(np.int64), inside)
    curve = PchipInterpolator((x - x[0]).astype(float), y)((grid - x[0]).astype(float))
    axis.plot(seconds(grid), curve, color=colour, lw=LR.LINE)


def draw_one(job) -> dict:
    """One trade's picture. `job` is (file path, title, the picture's two edges, the trade's start, its end, the
    moment its turn was marked, its side, the price of its point at the start, the price of its point at the end
    or None, whether the best bid and the best ask are drawn)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, first, last, start, end, turn_at, side, start_price, end_price, with_quotes = job
    w = WORK
    turn, with_it = SIDE[side]
    seconds = lambda moments: (np.asarray(moments, np.int64) - start) / NS_PER_SECOND   # the clock: from the start
    names = ['price'] + (list(QUOTES) if with_quotes else []) + list(LR.LINES) + [name + ' rate' for name in RATES]
    figure, axes = plt.subplots(len(names), 1, figsize=(INCHES[0], INCHES[1] * len(names) / GRAPHS), sharex=True,
                                gridspec_kw={'hspace': LR.GAP})
    graph = dict(zip(names, axes))
    head = lambda name, text: graph[name].set_title(f'{names.index(name) + 1}. {text}', loc='left', fontsize=LR.BIG)

    at, price = LR.cut(w['mid_at'], w['mid'], first, last)
    rates = {'price': (at, price)}                     # each line as drawn, for its change tick by tick
    graph['price'].step(seconds(at), price, where='post', color='#17202a', lw=LR.LINE)
    for did, moment, where in zip(POINTS[side], (start, end), (start_price, end_price)):
        if where is not None:
            shape, colour = MARKS[did]
            graph['price'].scatter([float(seconds(moment))], [where], marker=shape, s=POINT, color=colour,
                                   zorder=LR.ON_TOP, label=f'{did} at {where:.3f}')
    graph['price'].set_ylabel('mid price, dollars')
    head('price', 'THE PRICE: the mid price, with the trade\'s two points:\nwhere it was bought and where it was sold')
    if with_quotes:
        for name, (words, colour) in QUOTES.items():
            rounded(graph[name], seconds, w[name + '_at'], w[name], first, last, colour)
            graph[name].set_ylabel(f'{words}, dollars')
            head(name, f'THE {words.upper()}, by tick: rounded from one price to the next,\nstraight where the '
                       f'price is not changing')
    for name, (_, span) in LR.LINES.items():
        axis = graph[name]
        at, values = LR.cut(w[name + '_at'], w[name], first, last)
        rates[name] = (at, turn * values)
        axis.step(seconds(at), turn * values, where='post', color='#1f618d', lw=1)
        axis.axhline(0, color='#aab7b8', lw=LR.THIN)
        axis.set_ylim(*LR.scale(turn * values))
        axis.set_ylabel(f'above zero: {with_it}\n(with this trade)')
        head(name, f'THE {name.upper()}, the crypto formula: bought minus sold over\nbought plus sold, the trades of '
                   f'the last {span} seconds')
    for name, colour, what in zip(RATES, ('#6c3483', '#1e8449'), (
            'its change at each read (a trade received, or old trades leaving)',
            'the change of the mid price at each tick it moves')):
        axis = graph[name + ' rate']
        at, values = rates[name]
        at, values = at[:-1], values[:-1]              # the reads themselves (the last point only holds the line)
        change = np.diff(values)
        axis.vlines(seconds(at[1:]), 0, change, color=colour, lw=LR.THIN)
        axis.axhline(0, color='#aab7b8', lw=LR.THIN)
        axis.set_ylim(*LR.scale(change))
        axis.set_ylabel('change at the tick\n(above zero: with this trade)' if name in LR.LINES else
                        'change at the tick, dollars\n(above zero: the price went up)')
        head(name + ' rate', f'HOW FAST THE {name.upper()} CHANGES, per tick:\n{what}')
    for axis in axes[1:]:                              # the price graph carries only its two points
        axis.axvspan(0, float(seconds(end)), color='#f9e79f', alpha=LR.SHADE, label='this trade (start to end)')
        axis.axvline(0, color='#1e8449', lw=LR.THIN, ls='--', label='the trade starts (zero on the clock)')
        axis.axvline(float(seconds(turn_at)), color='#922b21', lw=LR.THIN, ls=':',
                     label='the turn the program marked before it')
    for axis in axes:
        axis.grid(alpha=LR.FAINT)
        axis.tick_params(labelsize=LR.SMALL)
    graph['price'].legend(fontsize=LR.SMALL, loc='best')
    axes[1].legend(fontsize=LR.TINY, loc='best')
    axes[-1].set_xlabel('seconds from the trade\'s start (each read at its own nanosecond)')
    figure.suptitle(title, fontsize=LR.BIG - 1, y=LR.TITLE_AT)
    figure.savefig(path, dpi=LR.DPI, bbox_inches='tight')
    plt.close(figure)
    raw = Path(path).read_bytes()
    return dict(file=Path(path).name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path, pick=None, keep_cpus=False, only=None, with_quotes=False) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, closes = trade_day_bounds(trade_day)
    s = LR.stored(rows_folder, day)                    # the two stored crypto lines (and the trades on the tape)
    s.update(quotes(rows_folder, trade_day))
    trades = trades_as_stored(rows_folder, day)
    last_tick = int(max(s['time'][-1], s['mid_at'][-1]))

    asked = list(range(len(trades)))
    if pick is not None:                               # a pick at random, the same one every time it is run
        asked = sorted(np.random.default_rng(int(day)).choice(asked, size=min(pick, len(asked)), replace=False).tolist())
    if only is not None:                               # the trades named, by their own numbers
        number_of = {t['trade']: k for k, t in enumerate(trades)}
        checks.need(only and all(n in number_of for n in only), f'a trade asked for by number is not a trade of {day}')
        asked = sorted(number_of[n] for n in only)
    count = dict(trade_day=trade_day.isoformat(), trades_of_the_program_in_the_trade_day=len(trades),
                 pictures_this_run_draws=len(asked), trades_on_the_tape=len(s['time']),
                 best_bid_and_best_ask_drawn=with_quotes,
                 drawn=f'the trades asked for by number: {[trades[k]["trade"] for k in asked]}' if only is not None else
                       'every trade of the program' if pick is None else
                       f'{len(asked)} trades of the program picked at random by the computer (seeded with the trade '
                       f'day\'s own number, {int(day)}, so the same pick comes out again): '
                       f'{[trades[k]["trade"] for k in asked]}')
    (out / f'TRADE-RENDERS-COUNT-{day}.json').write_text(json.dumps(count, indent=1) + '\n')

    name_of_day = f'Trade day {trade_day:%a %b %d, %Y}'
    jobs, lines, no_lead_in, wanted = [], [], [], set(asked)
    place = {int(p): k for k, p in enumerate(s['position'].tolist())}
    for k, t in enumerate(trades):
        start = t['onset_received_ns']
        end = t['end_received_ns'] if t['end_received_ns'] is not None else last_tick
        first, last = edges(trades, k, s, last_tick, opens, closes)
        checks.need(first <= start and end <= last, f'trade {t["trade"]}: its picture does not hold it whole')
        checks.need(t['onset_position_on_tape'] in place, f'trade {t["trade"]}: its start is not a trade on the stored tape')
        start_price = float(s['price'][place[t['onset_position_on_tape']]])
        end_price = None
        if t['end_received_ns'] is not None:
            if t['end_position_on_tape'] is not None:
                checks.need(t['end_position_on_tape'] in place, f'trade {t["trade"]}: its end is not a trade on the stored tape')
                end_price = float(s['price'][place[t['end_position_on_tape']]])
            else:                                      # it ended at no tick: the mid price standing then
                standing = int(np.searchsorted(s['mid_at'], end, 'right')) - 1
                checks.need(standing >= 0, f'trade {t["trade"]}: no mid price stood as it ended')
                end_price = float(s['mid'][standing])
        if first == start:
            no_lead_in.append(t['trade'])
        name = f'trade-render-{day}-{t["trade"]:0{TRADE_DIGITS}d}.png' if k in wanted else None
        if name:
            went = (f'{(end - start) / NS_PER_SECOND:,.3f} s' if t['end_received_ns'] is not None
                    else 'still open at the last tick')
            jobs.append((str(out / name),
                         f'{name_of_day}. Trade {t["trade"]} of the crypto and ng program: {t["side"]}, {went}.\n'
                         f'It starts {clock_text(start)} Eastern (zero on the clock).\n'
                         f'Drawn: {(first - start) / NS_PER_SECOND:,.3f} s to {(last - start) / NS_PER_SECOND:,.3f} s.\n'
                         f'It runs from two trades before to the trade after, and the dipole and the\n'
                         f'exhaustion set where it starts and stops: every hump of either line is whole.\n'
                         f'Nothing averaged. Every read at its own nanosecond.',
                         first, last, start, end, t['turn_received_ns'], t['side'], start_price, end_price,
                         with_quotes))
        lines.append((t['trade'], t['side'], t['turn_received_ns'], start, t['end_received_ns'], t['ended'],
                      t['length_seconds'], start_price, end_price, first, last, name))

    if not keep_cpus:                                  # the pod pins this program to one CPU; the drawing is
        os.sched_setaffinity(0, range(os.cpu_count()))   # spread over every CPU the pod allows, one helper on each
    cpus = multiprocessing.Manager().Queue()
    mine = sorted(os.sched_getaffinity(0))
    for cpu in mine:
        cpus.put(cpu)
    work = {name: s[name] for name in ('mid_at', 'mid', *LR.LINES, *(name + '_at' for name in LR.LINES), *QUOTES,
                                       *(name + '_at' for name in QUOTES))}
    with multiprocessing.Pool(len(mine), initializer=helper, initargs=(cpus, work)) as pool:
        drawn = pool.map(draw_one, jobs, chunksize=LR.PICTURES_AT_ONCE)
    checks.need(len(drawn) == len(asked) == len({f['file'] for f in drawn}),
                'not every trade asked for was drawn exactly once')

    index = pa.Table.from_arrays([pa.array(list(column), type=pa.string() if name in ('side', 'ended', 'render') else None)
                                  for name, column in zip(INDEX_NAMES, zip(*lines))], names=INDEX_NAMES)
    index_name = f'trade-renders-index-{day}.parquet'
    pq.write_table(index, out / index_name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / index_name).read_bytes()
    picture_bytes = sum(f['bytes'] for f in drawn)
    receipt = dict(
        what='One picture for every trade of the crypto and ng program, set up as the crypto pictures were: zero at '
             'the trade\'s start; the mid price in dollars with the trade\'s two points, bought and sold; the crypto '
             'dipole line (60 seconds) and the crypto exhaustion line (20 seconds), turned to the trade\'s side',
        asked='Greg, 2026-11-23: "Yes I want the prebirths laid out. Not worried about the 2000 averaging. I just want '
              'to make sure we are setting them up the same. Show each individual trade and their prebirths like this '
              'without designated start times for dipole and exhaustion. Their start times are when they start '
              'showing up."',
        trade_day=trade_day.isoformat(),
        the_lines=dict(
            price='the mid price (halfway between the best bid and the best ask on the stored rows, through the rows '
                  'gate), in dollars, not turned; on it two points, where the trade was bought and where it was '
                  'sold, each at the price of the trade on the tape that filled it there (the mid standing then '
                  'when it ended at no tick)',
            best_bid_and_best_ask='drawn in this run' if with_quotes else 'not drawn in this run',
            best_bid_and_best_ask_how='each its own graph, by tick, from the stored rows through the rows gate, in '
                                      'dollars: a rounded curve (shape-keeping, drawing only) through the first and '
                                      'the last tick of every stretch the price stands unchanged, so it is a '
                                      'straight line where the price is not changing and rounded from one price to '
                                      'the next; no value is changed and nothing is averaged',
            rates='per tick, not per second: the dipole line\'s change at each of its own reads, and the mid '
                  'price\'s change at each tick it moves, each drawn as a stroke at that tick',
            **{name: dict(read_from=f'crypto-ng-tick/{file}-{day}.parquet', span_seconds=span,
                          formula='bought minus sold over bought plus sold, over the trades received in the span, '
                                  'read at the nanosecond; turned to the trade\'s side')
               for name, (file, span) in LR.LINES.items()}),
        edges='set by the data: the frame runs from the start of the trade two before to the end of the trade '
              'after; every hump of the dipole line and of the exhaustion line that the frame touches is in the '
              'picture whole',
        index_columns=[dict(column=c, what=w) for c, w in INDEX_COLUMNS],
        counts=dict(count, pictures_drawn=len(drawn), picture_bytes=picture_bytes,
                    picture_megabytes=round(picture_bytes / LR.BYTES_PER_MEGABYTE, 1),
                    largest_picture_bytes=max(f['bytes'] for f in drawn),
                    trades_still_open_at_the_last_tick=sum(t['end_received_ns'] is None for t in trades),
                    trades_whose_picture_starts_at_their_own_start=len(no_lead_in), helpers=len(mine)),
        trades_with_no_lead_in=no_lead_in,
        checks=dict(passed=True,
                    what='the stored trades of the program are in the order they started and none ends before it '
                         'starts; both stored lines and the mid price are in time order; every trade\'s start (and '
                         'its end, where it ended on a trade) is a trade the stored tape holds; every picture holds '
                         'its trade whole; every trade asked for was drawn exactly once'),
        read_from=[f'crypto-ng-tick/crypto-ng-tick-program-trades-{day}.parquet', f'rows-{day}-part*.parquet',
                   f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet'] +
                  [f'crypto-ng-tick/{file}-{day}.parquet' for file, _ in LR.LINES.values()],
        nothing_applied='Nothing is averaged, ranked, typed or labelled. Observation only.',
        files=[dict(file=index_name, rows=index.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())] + drawn,
        seconds=round(time.monotonic() - started, 1))
    (out / f'TRADE-RENDERS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='One picture for every trade of the crypto and ng program')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--random', type=int, help='draw this many trades, picked at random from the trade day')
    ap.add_argument('--only', action='append', help='<trade day>:<trade number>; may be given more than once. Draw '
                    'only the trades named for this trade day')
    ap.add_argument('--quotes', action='store_true', help='add the best bid and the best ask, each its own graph')
    ap.add_argument('--keep-cpus', action='store_true', help='draw on the CPUs this program was pinned to')
    a = ap.parse_args()
    only = None if a.only is None else [int(n) for day, n in (text.split(':') for text in a.only) if day == a.trade_day]
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out, a.random, a.keep_cpus, only, a.quotes)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
