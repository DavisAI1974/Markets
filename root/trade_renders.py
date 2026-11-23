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
- THE PRICE is the crypto picture's black line: the MID price (halfway between the best bid and the best ask), as
  its change from where it stood at the trade's start, in hundredths of a percent, turned to the trade's side.
- THE DIPOLE is the crypto picture's orange line: bought minus sold over bought plus sold over the trades of the
  last 60 seconds, turned to the trade's side.
- THE EXHAUSTION is the July 7 line: the same figure over the last 20 seconds, turned to the trade's side.
The two lines are READ FROM WHAT IS STORED (`crypto-ng-tick-lean-60s-*`, `crypto-ng-tick-line-20s-*`); the mid is
read from the stored rows through the rows gate. "Turned to the trade's side": above zero always reads "with this
trade". Five separate graphs on the one clock: the three lines, then the two rates.

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

The trade is marked on all three graphs: its own life shaded (start to end), a line at zero, and a line at the turn
the program marked before it. Nothing is averaged, ranked, typed or labelled. OBSERVATION ONLY.

WHAT IS WRITTEN: `TRADE-RENDERS-COUNT-<trade day>.json` (first: how many trades the trade day holds and how many
pictures this run draws), `trade-render-<trade day>-<trade number>.png`, `trade-renders-index-<trade day>.parquet`
(one line per trade of the program), `TRADE-RENDERS-<trade day>.json` (the receipt).

    python3 -m root.trade_renders 20231017 --rows <folder of the trade day's stored files> --out <folder> \
        [--random <how many>] [--keep-cpus]
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
BPS = 10 ** 4                                          # hundredths of a percent, the crypto picture's price unit
SIDE = dict(buy=(1, 'buying'), sell=(-1, 'selling'))   # the crypto turn to the trade's side
RATES = ('dipole', 'price')                            # the crypto picture's two rate lines, in its order
READS = ['received_time_ns', 'best_bid', 'best_ask']
TRADES = ['trade', 'side', 'turn_received_ns', 'onset_position_on_tape', 'onset_received_ns', 'ended',
          'end_received_ns', 'length_seconds']
INDEX_COLUMNS = [
    ('trade', 'The trade of the crypto and ng program, in the order they started. A label only.'),
    ('side', 'buy or sell: the side the program took.'),
    ('turn_received_ns', 'The moment the program marked the turn it was made on.'),
    ('onset_received_ns', 'THE START: when the trade on the tape that filled it was received. Zero on its picture.'),
    ('end_received_ns', 'When it ended. Empty when it was still open at the last tick of the trade day.'),
    ('ended', 'How it ended, in the words of the July rule that ended it.'),
    ('length_seconds', 'From its start to its end, in seconds.'),
    ('mid_at_the_start', 'The mid price standing as it started, in dollars: the level its price line is measured from.'),
    ('picture_first_ns', 'Where its picture starts, set by the data.'),
    ('picture_last_ns', 'Where its picture ends, set by the data.'),
    ('render', 'The picture drawn for it in this run. Empty when this run did not draw it.'),
]
INDEX_NAMES = [name for name, _ in INDEX_COLUMNS]
WORK = {}


def mids(rows_folder: Path, trade_day) -> tuple:
    """The mid price at every moment it changes: halfway between the best bid and the best ask, read from the
    stored rows through the rows gate, in dollars. Held from the last tick that had both."""
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
    return at[changed], mid[changed]


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


def draw_one(job) -> dict:
    """One trade's picture. `job` is (file path, title, the picture's two edges, the trade's start, its end, the
    moment its turn was marked, its side, the mid standing as it started)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, first, last, start, end, turn_at, side, level = job
    w = WORK
    turn, with_it = SIDE[side]
    seconds = lambda moments: (np.asarray(moments, np.int64) - start) / NS_PER_SECOND   # the clock: from the start
    figure, axes = plt.subplots(GRAPHS, 1, figsize=INCHES, sharex=True, gridspec_kw={'hspace': LR.GAP})
    at, values = LR.cut(w['mid_at'], w['mid'], first, last)
    price = turn * (values - level) / level * BPS
    rates = {'price': (at, price)}                     # each line as drawn, for its change tick by tick
    axes[0].step(seconds(at), price, where='post', color='#17202a', lw=LR.LINE)
    axes[0].axhline(0, color='#aab7b8', lw=LR.THIN)
    axes[0].set_ylim(*LR.scale(price))
    axes[0].set_ylabel('hundredths of a percent\n(above zero: with this trade)')
    axes[0].set_title('1. THE PRICE, as in crypto: the mid price, from where it stood\nat the trade\'s start, turned '
                      'to the trade\'s side', loc='left', fontsize=LR.BIG)
    for number_of, (name, (_, span)) in enumerate(LR.LINES.items(), start=1):
        axis = axes[number_of]
        at, values = LR.cut(w[name + '_at'], w[name], first, last)
        rates[name] = (at, turn * values)
        axis.step(seconds(at), turn * values, where='post', color='#1f618d', lw=1)
        axis.axhline(0, color='#aab7b8', lw=LR.THIN)
        axis.set_ylim(*LR.scale(turn * values))
        axis.set_ylabel(f'above zero: {with_it}\n(with this trade)')
        axis.set_title(f'{number_of + 1}. THE {name.upper()}, the crypto formula: bought minus sold over\nbought plus '
                       f'sold, the trades of the last {span} seconds', loc='left', fontsize=LR.BIG)
    for axis, name, colour, what in zip(axes[len(LR.LINES) + 1:], RATES, ('#6c3483', '#1e8449'), (
            'its change at each read (a trade received, or old trades leaving)',
            'the change of the mid price at each tick it moves')):
        at, values = rates[name]
        at, values = at[:-1], values[:-1]              # the reads themselves (the last point only holds the line)
        change = np.diff(values)
        axis.vlines(seconds(at[1:]), 0, change, color=colour, lw=LR.THIN)
        axis.axhline(0, color='#aab7b8', lw=LR.THIN)
        axis.set_ylim(*LR.scale(change))
        axis.set_ylabel('change at the tick\n(above zero: with this trade)')
        axis.set_title(f'{list(axes).index(axis) + 1}. HOW FAST THE {name.upper()} CHANGES, per tick:\n{what}', loc='left',
                       fontsize=LR.BIG)
    for axis in axes:
        axis.axvspan(0, float(seconds(end)), color='#f9e79f', alpha=LR.SHADE, label='this trade (start to end)')
        axis.axvline(0, color='#1e8449', lw=LR.THIN, ls='--', label='the trade starts (zero on the clock)')
        axis.axvline(float(seconds(turn_at)), color='#922b21', lw=LR.THIN, ls=':',
                     label='the turn the program marked before it')
        axis.grid(alpha=LR.FAINT)
        axis.tick_params(labelsize=LR.SMALL)
    axes[0].legend(fontsize=LR.TINY, loc='best')
    axes[-1].set_xlabel('seconds from the trade\'s start (each read at its own nanosecond)')
    figure.suptitle(title, fontsize=LR.BIG - 1, y=LR.TITLE_AT)
    figure.savefig(path, dpi=LR.DPI, bbox_inches='tight')
    plt.close(figure)
    raw = Path(path).read_bytes()
    return dict(file=Path(path).name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path, pick=None, keep_cpus=False) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, closes = trade_day_bounds(trade_day)
    s = LR.stored(rows_folder, day)                    # the two stored crypto lines (and the trades on the tape)
    s['mid_at'], s['mid'] = mids(rows_folder, trade_day)
    trades = trades_as_stored(rows_folder, day)
    last_tick = int(max(s['time'][-1], s['mid_at'][-1]))

    asked = list(range(len(trades)))
    if pick is not None:                               # a pick at random, the same one every time it is run
        asked = sorted(np.random.default_rng(int(day)).choice(asked, size=min(pick, len(asked)), replace=False).tolist())
    count = dict(trade_day=trade_day.isoformat(), trades_of_the_program_in_the_trade_day=len(trades),
                 pictures_this_run_draws=len(asked), trades_on_the_tape=len(s['time']),
                 drawn='every trade of the program' if pick is None else
                       f'{len(asked)} trades of the program picked at random by the computer (seeded with the trade '
                       f'day\'s own number, {int(day)}, so the same pick comes out again): '
                       f'{[trades[k]["trade"] for k in asked]}')
    (out / f'TRADE-RENDERS-COUNT-{day}.json').write_text(json.dumps(count, indent=1) + '\n')

    name_of_day = f'Trade day {trade_day:%a %b %d, %Y}'
    jobs, lines, no_lead_in, wanted = [], [], [], set(asked)
    for k, t in enumerate(trades):
        start = t['onset_received_ns']
        end = t['end_received_ns'] if t['end_received_ns'] is not None else last_tick
        first, last = edges(trades, k, s, last_tick, opens, closes)
        checks.need(first <= start and end <= last, f'trade {t["trade"]}: its picture does not hold it whole')
        standing = int(np.searchsorted(s['mid_at'], start, 'right')) - 1
        checks.need(standing >= 0, f'trade {t["trade"]}: no mid price stood as it started')
        level = float(s['mid'][standing])
        if first == start:
            no_lead_in.append(t['trade'])
        name = f'trade-render-{day}-{t["trade"]:0{TRADE_DIGITS}d}.png' if k in wanted else None
        if name:
            went = (f'{(end - start) / NS_PER_SECOND:,.3f} s' if t['end_received_ns'] is not None
                    else 'still open at the last tick')
            jobs.append((str(out / name),
                         f'{name_of_day}. Trade {t["trade"]} of the crypto and ng program: {t["side"]}, {went}.\n'
                         f'It starts {clock_text(start)} Eastern (zero on the clock); mid price there {level:.4f}.\n'
                         f'Drawn: {(first - start) / NS_PER_SECOND:,.3f} s to {(last - start) / NS_PER_SECOND:,.3f} s.\n'
                         f'It runs from two trades before to the trade after, and the dipole and the\n'
                         f'exhaustion set where it starts and stops: every hump of either line is whole.\n'
                         f'Nothing averaged. Every read at its own nanosecond.',
                         first, last, start, end, t['turn_received_ns'], t['side'], level))
        lines.append((t['trade'], t['side'], t['turn_received_ns'], start, t['end_received_ns'], t['ended'],
                      t['length_seconds'], level, first, last, name))

    if not keep_cpus:                                  # the pod pins this program to one CPU; the drawing is
        os.sched_setaffinity(0, range(os.cpu_count()))   # spread over every CPU the pod allows, one helper on each
    cpus = multiprocessing.Manager().Queue()
    mine = sorted(os.sched_getaffinity(0))
    for cpu in mine:
        cpus.put(cpu)
    work = {name: s[name] for name in ('mid_at', 'mid', *LR.LINES, *(name + '_at' for name in LR.LINES))}
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
             'the trade\'s start; the mid price from where it stood there; the crypto dipole line (60 seconds); the '
             'crypto exhaustion line (20 seconds); all turned to the trade\'s side',
        asked='Greg, 2026-11-23: "Yes I want the prebirths laid out. Not worried about the 2000 averaging. I just want '
              'to make sure we are setting them up the same. Show each individual trade and their prebirths like this '
              'without designated start times for dipole and exhaustion. Their start times are when they start '
              'showing up."',
        trade_day=trade_day.isoformat(),
        the_lines=dict(
            price='the mid price (halfway between the best bid and the best ask on the stored rows, through the rows '
                  'gate), its change from where it stood at the trade\'s start, in hundredths of a percent, turned '
                  'to the trade\'s side',
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
                         'starts; both stored lines and the mid price are in time order; a mid price stood as every '
                         'trade started; every picture holds its trade whole; every trade asked for was drawn '
                         'exactly once'),
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
    ap.add_argument('--keep-cpus', action='store_true', help='draw on the CPUs this program was pinned to')
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out, a.random, a.keep_cpus)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
