"""ROOT: the natural gas exhaustion calculation of the "crypto and ng" program, made AT THE TICK.

Greg, 2026-11-18: "Whatever crypto did to generate those renders do that. If one of the calcs was a 20 sec. Use it
just like crypto did ... I want everything in our new exhaustion calc to be exactly like the old calc"; "The only
difference between the two should be that was crypto and we're doing ng"; "Bring back the program and just
designate it crypto and ng ... observation or verification purpose only"; "Definitely run it on nano ticks";
"We have to rerun the exhaustion data on the pods first".

Every trade enters each line at the nanosecond it was received and leaves it exactly 20 (or 60) seconds later.
Nothing is put on a time grid of any size. The rules and their numbers are the July ones, written at the
nanosecond (`crypto_ng/tick.py` states them, rule by rule).

WHAT IT MAKES, for one trade day:
1. THE 20-SECOND LINE (the exhaustion line), for the WHOLE trade day: bought minus sold over bought plus sold, over
   the trades received in the last 20 seconds, written at every moment it changes (a trade is received; trades
   leave the 20 seconds at a moment with no tick). Empty where nothing traded in the 20 seconds (July wrote 0).
2. THE TURN FINDER'S 60-SECOND LEAN, written the same way, and every turn the July turn finder marks on it.
3. THE PROGRAM'S TRADES: in at the first trade on the other side after a turn (only if before the next turn), out
   by the July rules. Each trade's start, end, side and length; nothing averaged, no kind put on a trade.
4. EVERY TRADE ON THE TAPE, each on its own line: where it sits on the 20-second line (the line just before it and
   at it), and the trade of the program under way at it. So any single trade's own exhaustion line, a trade of
   the program or a trade of the tape, is a cut of the one line around that trade, from as far before it to as
   far after it as is wanted: nothing is cut off at 45 and 60 seconds in the data.

LEFT OUT ON GREG'S WORD (2026-11-18): the winner and loser labels; the average line of each kind; the short or
long split. NOT WRITTEN: the program's divergence read beside each trade (`dipole_class`, `rev_conv`): it was
never used on this path (the entry gate is off), and its July form is not a calculation at the tick.

WHAT IS WRITTEN (all for observation and verification only; never a signal, never an input):
- `crypto-ng-tick-line-20s-<trade day>.parquet`, `crypto-ng-tick-lean-60s-<trade day>.parquet`: one line per read.
- `crypto-ng-tick-turns-<trade day>.parquet`: every turn found and what became of it. Nothing filtered.
- `crypto-ng-tick-program-trades-<trade day>.parquet`: one line per trade of the program.
- `crypto-ng-tick-tape-trades-<trade day>.parquet`: one line per trade on the tape.
- `CRYPTO-NG-TICK-COUNT-<trade day>.json`: written FIRST, as soon as the trades are made: how many trades get a line.
- `CRYPTO-NG-TICK-<trade day>.json`: the receipt: counts, the rules, the inputs, the checks, every file's fingerprint.
- NO PICTURE IN THE DATA RUN. A trade's own graph is printed afterwards from the stored line: one picture for one
  trade, one graph in it, drawn twice (as the steps it moves in, and as a smooth curve through its own points,
  drawing only) so Greg can say which he wants.

The ticks reach this only through `tape.rows_for_calculations()`: the four trade days, nothing from outside them.

    python3 -m root.crypto_ng_tick 20231002 --rows <stored rows folder> --out <folder>
        the data run
    python3 -m root.crypto_ng_tick 20231002 --rows <...> --out <folder of the data run> --moment <ns>
        prints the graph of the program's trade under way at that moment on the received clock (when it held no
        trade then: the next trade to start), from the stored line; nothing is worked out again
    ... --trade <number>            the same for a trade of the program named by its number
    ... --tape <position on tape>   the same for one trade on the tape: 45 seconds before it to 60 after
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from crypto_ng import tick
from root import checks, store, tape
from root.calendar import NS_PER_SECOND, eastern_text, parse_trade_day, trade_day_bounds

READS = ['received_time_ns', 'action', 'side', 'size', 'price', 'best_bid', 'best_ask']
TRADE, BUY, SELL = 'T', 'B', 'A'                       # the tape's codes, as the rows store them
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
HALVE = 2                                              # a mid price is halfway between the best bid and best ask
RULES_FILE = Path(tick.__file__)
SIDE_TEXT = {1: 'buy', -1: 'sell'}                     # the program's +1 (it bought) and -1 (it sold)
RECEIVED, LEFT = 'a trade was received', 'trades left the span at a moment with no tick'
CLOCK = slice(11, 19)                                  # the hour, minute and second inside an Eastern time text
GRAPH_INCHES = (7.2, 5.4)                              # drawing only: one trade's own graph, to be read on a phone
LEGEND_AT = (0.5, -0.16)                               # drawing only: the key sits under the graph, off the line
DPI = 100
FLOW_LIMIT = 1.08                                      # the flow runs from -1 to 1; the graph shows a little more
BIG, SMALL, LINE, THIN, FAINT = 10, 8, 1.4, 0.8, 0.25  # drawing only: two letter sizes, two line widths, the grid
CURVE_POINTS = 4000                                    # drawing only: how finely a smooth curve is drawn
TRADE_DIGITS = 5                                       # a trade's number in its picture's name, written 00000

LINE_COLUMNS = [
    ('read', 'The number of this read of the line, in order from the open of the trade day (0 is the first).'),
    ('moment_received_ns', 'The moment of the read on the received clock, to the nanosecond.'),
    ('what', 'What changed the line: a trade was received, or trades left the span at a moment with no tick.'),
    ('position_on_tape', 'The trade received: its position on the tape. Empty when the read is trades leaving.'),
    ('trades_left', 'How many trades left the span at this moment (those leaving at the very nanosecond a trade '
     'is received leave first and are read with it).'),
    ('bought', 'Size bought by aggressors inside the span, after this read.'),
    ('sold', 'Size sold by aggressors inside the span, after this read.'),
    ('flow', 'THE LINE: bought minus sold over bought plus sold. It holds this value until the next read. Empty '
     'where nothing with a side traded inside the span (the July rule wrote 0 there).'),
    ('nothing_traded', 'Yes where nothing with a side traded inside the span.'),
]
TURN_COLUMNS = [
    ('turn', 'The number of this turn, in the order the turn finder marked them. A label only.'),
    ('side', 'buy or sell: the side the turn calls for.'),
    ('marked_read', 'The read of the 60-second lean at which the turn was marked.'),
    ('marked_received_ns', 'The moment of that read.'),
    ('marked_at', 'Whether the turn was marked as a trade was received, or at a moment trades left the 60 seconds '
     '(no tick: nothing new had traded).'),
    ('lean_at_mark', 'The 60-second lean at the mark. Empty when the 60 seconds held no trade (the July rule read 0).'),
    ('furthest_read', 'The read at which the lean stood furthest before it turned. Empty when that was the open of '
     'the trade day, before any trade.'),
    ('furthest_received_ns', 'The moment of that read (the open of the trade day when there is none).'),
    ('lean_at_furthest', 'The lean there. Empty when the 60 seconds held no trade.'),
    ('what_became_of_it', 'Filled (a trade of the program started), or why not. Nothing is filtered.'),
    ('program_trade', 'The trade of the program this turn started. Empty when it started none.'),
]
TRADE_COLUMNS = [
    ('trade', 'The number of this trade of the crypto and ng program, in the order they started. A label only.'),
    ('side', 'buy or sell: the side the program took.'),
    ('turn', 'The turn it was made on (a line of the turns table).'),
    ('turn_received_ns', 'The moment that turn was marked.'),
    ('onset_position_on_tape', 'THE ONSET: the trade on the tape that filled it (the first trade on the other side '
     'after the turn). Its position on the tape.'),
    ('onset_received_ns', 'When that trade was received, to the nanosecond.'),
    ('onset_read_20s', 'The read of the 20-second line made as that trade was received.'),
    ('ended', 'How the trade ended, in the words of the July rule that ended it.'),
    ('end_position_on_tape', 'The trade on the tape that ended it. Empty when it ended at no tick or is still open.'),
    ('end_received_ns', 'When it ended. Empty when it was still open at the last tick of the trade day.'),
    ('length_seconds', 'From the onset to the end, in seconds. A measured number; no short or long label is made.'),
    ('program_open_px', 'The program\'s own entry price: the mid at the turn with the half spread added or taken off.'),
    ('program_close_px', 'The program\'s own exit price.'),
    ('program_close_maker', 'The program\'s own mark: yes when it counted the exit as filled at its own quote.'),
    ('program_gross_bps', 'The program\'s own result in hundredths of a percent, before its fees. Observation only.'),
    ('program_net_bps', 'The same after the program\'s fee settings (the Kraken ones: 0 and 5). Observation only. '
     'No winner or loser is made from it and nothing is drawn or coloured by it.'),
    ('program_swing_bps', 'The program\'s own figure: how far the mid moved from the turn to the end.'),
    ('program_dive_depth', 'Written by the program beside each trade: the size of the 60-second lean at its furthest.'),
    ('program_lean_flip', 'Written by the program: the lean at the turn, measured with the trade before.'),
    ('program_lean_close', 'Written by the program: the lean at the end, measured with this trade.'),
    ('seconds_from_the_open_to_the_onset', 'How long after the open of the trade day the onset came. When it is '
     'under 45 the line before the onset is shorter than 45 seconds; nothing is left out for it.'),
]
TAPE_COLUMNS = [
    ('position_on_tape', 'The trade: its position on the tape. A label only.'),
    ('received_time_ns', 'When it was received, to the nanosecond.'),
    ('side', 'buy or sell: the tape\'s own aggressor side. Empty when the tape gives none.'),
    ('size', 'Its size, in lots.'),
    ('price', 'Its price, in dollars.'),
    ('read_20s', 'The read of the 20-second line made as this trade was received. Empty for a trade with no side '
     '(it is in neither bought nor sold, so the line does not change at it).'),
    ('flow_20s_before', 'The 20-second line as it stood just before this trade was received. Empty when nothing '
     'had traded in those 20 seconds.'),
    ('flow_20s_at', 'The 20-second line with this trade in it. Empty when nothing with a side is inside it.'),
    ('program_trade_under_way', 'The trade of the program under way as this trade was received. Empty when the '
     'program held none.'),
    ('starts_program_trade', 'The trade of the program this trade started (it filled it). Empty otherwise.'),
    ('ends_program_trade', 'The trade of the program this trade ended. Empty otherwise.'),
]
names_of = lambda columns: [name for name, _ in columns]


def clock_text(ns: int) -> str:
    """The Eastern time of day of a moment, written to the nanosecond (a label)."""
    return f'{eastern_text(ns)[CLOCK]}.{ns % NS_PER_SECOND:09d}'


def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()


def read(rows_folder: Path, trade_day) -> dict:
    """The trade day's ticks as whole columns, through the stored-rows gate."""
    out = {name: [] for name in ['position'] + READS}
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        out['position'].append(position)
        for name, value in zip(READS, row):
            out[name].append(value)
    return out


def number(values) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], float)


def or_empty(value):
    """A stored value: empty, never a not-a-number and never 0, when there is none."""
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else value


def save(out: Path, name: str, columns: dict, text=()) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_arrays([pa.array(v, type=pa.string() if k in text else None) for k, v in columns.items()],
                                 names=list(columns))
    pq.write_table(table, out / name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / name).read_bytes()
    return dict(file=name, rows=table.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def line_table(r: dict, flow: np.ndarray, quiet: np.ndarray, sided_position: np.ndarray) -> dict:
    at_trade = r['trade'] != tick.NONE
    return dict(zip(names_of(LINE_COLUMNS), [
        list(range(len(flow))), r['moment'].tolist(), [RECEIVED if a else LEFT for a in at_trade],
        [int(sided_position[i]) if a else None for i, a in zip(r['trade'], at_trade)], r['left'].tolist(),
        r['bought'].tolist(), r['sold'].tolist(), [None if q else float(v) for v, q in zip(flow, quiet)],
        quiet.tolist()]))


def against_stored_flow(rows_folder: Path, day: str, position: np.ndarray, received: np.ndarray, sided: np.ndarray,
                        s_recv: np.ndarray, s_buy: np.ndarray, s_size: np.ndarray) -> dict:
    """The inputs against the stored `flow_20s` of piece 1, on EVERY tick of the trade day: the size bought and
    sold in the 20 seconds up to each tick, worked out here from running totals on the clock, must equal the
    stored `flow_bought_20s` and `flow_sold_20s` of that tick exactly."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(f'calc-flow_peak-{day}-part*.parquet'))
    checks.need(files, 'the stored flow of piece 1 is not beside the rows')
    columns = ['position_on_tape', 'flow_bought_20s', 'flow_sold_20s']
    stored = [np.concatenate([pq.read_table(path, columns=[c]).column(c).to_numpy() for path in files])
              for c in columns]
    at = np.searchsorted(stored[0], position)          # the stored flow has a line for every stored row, those of
    #                                                    the 5 pm to 6 pm stretch included; ours are the trade day's
    checks.need(bool(np.all(at < len(stored[0]))) and np.array_equal(stored[0][np.minimum(at, len(stored[0]) - 1)],
                                                                     position),
                'a tick of the trade day has no line in the stored flow')
    stored = [column[at] for column in stored]
    cb = np.concatenate([[0], np.cumsum(np.where(s_buy, s_size, 0))])
    cs = np.concatenate([[0], np.cumsum(np.where(s_buy, 0, s_size))])
    through = np.cumsum(sided)                         # the sided trades up to and including each tick
    gone = np.searchsorted(s_recv, received - tick.LINE_NS, 'right')
    differ = np.flatnonzero((cb[through] - cb[gone] != stored[1]) | (cs[through] - cs[gone] != stored[-1]))
    checks.need(not len(differ), f'the 20 seconds at the tick at position '
                                 f'{int(position[differ[0]]) if len(differ) else None} differ from the stored flow')
    return dict(passed=True, ticks_compared=int(len(position)),
                what='bought and sold over the 20 seconds on every tick of the trade day, against the stored '
                     'flow_bought_20s and flow_sold_20s of piece 1')


def recounted(name: str, r: dict, span_ns: int, s_recv, s_buy, s_size) -> dict:
    bought, sold = tick.recount(s_recv, s_buy, s_size, span_ns, r)
    differ = np.flatnonzero((bought != r['bought']) | (sold != r['sold']))
    checks.need(not len(differ), f'{name}: read {int(differ[0]) if len(differ) else None} differs from the recount')
    return dict(passed=True, reads=int(len(bought)),
                what=f'{name}: bought and sold at every read, from running totals and two look-ups on the clock')


def trades_hold_together(made: list, fate: list, found: list, r60: dict, s_buy: np.ndarray) -> dict:
    """What the July rules promise about the trades, read back off what was made."""
    checks.need(len(fate) == len(found), 'a turn has no line saying what became of it')
    checks.need(sum(f == tick.TURN_FILLED for f in fate) == len(made), 'the turns filled are not the trades made')
    before = None
    for k, leg in enumerate(made):
        j = leg['onset_trade']
        checks.need(bool(s_buy[j]) == (leg['side'] < 0), f'trade {k}: its onset is not a trade on the other side')
        marked = r60['trade'][leg['turn_read']]
        checks.need(int(r60['moment'][leg['turn_read']]) <= leg['onset_ns'] and (marked == tick.NONE or marked < j),
                    f'trade {k}: its onset is not after its turn')
        checks.need(leg['end_ns'] is None or leg['end_ns'] >= leg['onset_ns'], f'trade {k}: it ends before it starts')
        checks.need(leg['end_ns'] is not None or k == len(made) - 1, f'trade {k}: left open with a trade after it')
        checks.need(before is None or (before['end_ns'] is not None and before['end_ns'] <= leg['onset_ns']),
                    f'trade {k}: it starts before the trade before it ended')
        before = leg
    return dict(passed=True, trades=len(made),
                what='every trade of the program starts at a trade on the other side after its turn, ends at or '
                     'after its start, and no two are under way at once; every turn has a line saying what became '
                     'of it')


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, closes = trade_day_bounds(trade_day)
    t = read(rows_folder, trade_day)
    position = np.array(t['position'], np.int64)
    received = np.array(t['received_time_ns'], np.int64)
    checks.need(len(received) and received[0] >= opens, 'a tick was received before the open of the trade day')
    until = max(closes, int(received[-1]) + 1)         # the line is read to the end of the trade day (a last tick
    #                                                    can be received a moment after the halt it was sent before)
    checks.need(bool(np.all(np.diff(received) >= 0)), 'the received time goes backwards: no span can be read on it')
    action, side = np.array(t['action'], object), np.array(t['side'], object)
    size = number(t['size'])
    trade = action == TRADE
    sided = trade & ((side == BUY) | (side == SELL))
    rows_sided = np.flatnonzero(sided)
    s_recv, s_buy, s_size = received[sided], side[sided] == BUY, size[sided].astype(np.int64)
    s_position = position[sided]

    bid, ask = number(t['best_bid']), number(t['best_ask'])
    both = ~np.isnan(bid) & ~np.isnan(ask)
    checks.need(bool(both.any()), 'no tick of the trade day has both a best bid and a best ask')
    mid_own = (bid + ask) / HALVE / PRICE_UNIT
    last_both = np.maximum.accumulate(np.where(both, np.arange(len(both)), -1))   # the latest tick with both sides
    mid = np.where(last_both >= 0, mid_own[np.maximum(last_both, 0)], np.nan)
    hs = tick.half_spread_bps(mid_own[both], ((ask - bid) / PRICE_UNIT)[both])
    mid_at_moment = lambda ns: float(mid[np.searchsorted(received, ns, 'right') - 1]) \
        if np.searchsorted(received, ns, 'right') else float('nan')
    mid_at_trade = lambda j: float(mid[rows_sided[j]])

    r20 = tick.reads(s_recv, s_buy, s_size, tick.LINE_NS, until)
    r60 = tick.reads(s_recv, s_buy, s_size, tick.LEAN_NS, until)
    flow, quiet20 = tick.line(r20['bought'], r20['sold'])
    lean, quiet60 = tick.line(r60['bought'], r60['sold'])
    mid_at_read = lambda c: mid_at_trade(r60['trade'][c]) if r60['trade'][c] != tick.NONE \
        else mid_at_moment(int(r60['moment'][c]))
    found = tick.turns(lean)
    made, fate = tick.trades(r60, lean, found, s_recv, s_buy, mid_at_read, mid_at_trade, mid_at_moment, hs,
                             int(received[-1]))

    counted = dict(
        trade_day=trade_day.isoformat(), trades_on_the_tape=int(trade.sum()),
        trades_on_the_tape_with_a_side=int(sided.sum()), trades_of_the_program=len(made),
        what='How many trades get a line. Every trade on the tape has its own line in the tape-trades table and '
             'every trade of the program its own in the program-trades table; each one\'s exhaustion line is a cut '
             'of the one 20-second line of the whole trade day.')
    (out / f'CRYPTO-NG-TICK-COUNT-{day}.json').write_text(json.dumps(counted, indent=1) + '\n')

    check = dict(
        the_20_second_line_recounted=recounted('the 20-second line', r20, tick.LINE_NS, s_recv, s_buy, s_size),
        the_60_second_lean_recounted=recounted('the 60-second lean', r60, tick.LEAN_NS, s_recv, s_buy, s_size),
        against_the_stored_flow=against_stored_flow(rows_folder, day, position, received, sided, s_recv, s_buy, s_size),
        the_trades_hold_together=trades_hold_together(made, fate, found, r60, s_buy))

    files = [save(out, f'crypto-ng-tick-line-20s-{day}.parquet', line_table(r20, flow, quiet20, s_position), {'what'}),
             save(out, f'crypto-ng-tick-lean-60s-{day}.parquet', line_table(r60, lean, quiet60, s_position), {'what'})]

    started_by = {leg['turn']: k for k, leg in enumerate(made)}
    value = lambda x, q, at: None if at == tick.NONE or q[at] else float(x[at])
    files.append(save(out, f'crypto-ng-tick-turns-{day}.parquet', dict(zip(names_of(TURN_COLUMNS), map(list, zip(*[
        (k, SIDE_TEXT[s], c, int(r60['moment'][c]), RECEIVED if r60['trade'][c] != tick.NONE else LEFT,
         value(lean, quiet60, c), None if p == tick.NONE else p, opens if p == tick.NONE else int(r60['moment'][p]),
         value(lean, quiet60, p), fate[k], started_by.get(k))
        for k, (c, p, s) in enumerate(found)])) if found else [[] for _ in TURN_COLUMNS])),
        {'side', 'marked_at', 'what_became_of_it'}))

    read20_of = np.full(len(s_recv), tick.NONE, np.int64)
    at_trade = r20['trade'] != tick.NONE
    read20_of[r20['trade'][at_trade]] = np.flatnonzero(at_trade)
    lines = []
    for k, leg in enumerate(made):
        j, e = leg['onset_trade'], leg['end_trade']
        lines.append((
            k, SIDE_TEXT[leg['side']], leg['turn'], int(r60['moment'][leg['turn_read']]), int(s_position[j]),
            leg['onset_ns'], int(read20_of[j]), leg['ended'], None if e == tick.NONE else int(s_position[e]),
            leg['end_ns'], None if leg['end_ns'] is None else (leg['end_ns'] - leg['onset_ns']) / NS_PER_SECOND,
            or_empty(leg['open_px']), or_empty(leg['close_px']), leg['close_maker'], or_empty(leg['gross_bps']),
            or_empty(leg['net_bps']), or_empty(leg['swing_bps']), leg['dive_depth'], leg['lean_flip'],
            leg['lean_close'], (leg['onset_ns'] - opens) / NS_PER_SECOND))
    files.append(save(out, f'crypto-ng-tick-program-trades-{day}.parquet', dict(zip(
        names_of(TRADE_COLUMNS), map(list, zip(*lines)) if lines else [[] for _ in TRADE_COLUMNS])),
        {'side', 'ended'}))

    # every trade on the tape, each on its own line
    place = np.cumsum(sided) - 1                        # a sided trade's place among the sided trades
    rows_trade = np.flatnonzero(trade)
    starts = {leg['onset_trade']: k for k, leg in enumerate(made)}
    ends = {leg['end_trade']: k for k, leg in enumerate(made) if leg['end_trade'] != tick.NONE}
    under, k = [], 0                                    # the trade of the program under way at each tape trade
    for row in rows_trade.tolist():
        at = int(received[row])
        while k < len(made) and made[k]['end_ns'] is not None and (
                made[k]['end_ns'] < at or (made[k]['end_trade'] != tick.NONE
                                           and rows_sided[made[k]['end_trade']] <= row)):
            k += 1
        on = k < len(made) and rows_sided[made[k]['onset_trade']] <= row
        under.append(k if on else None)
    flow_at = lambda rd: None if rd < 0 or quiet20[rd] else float(flow[rd])
    tape_lines = []
    for row, now in zip(rows_trade.tolist(), under):
        j = int(place[row]) if sided[row] else None
        rd = None if j is None else int(read20_of[j])
        if rd is None:                                 # a trade with no side: the line as it stands at its moment,
            standing = int(np.searchsorted(r20['moment'], received[row], 'right')) - 1   # before any sided trade
            later = int(place[row]) + 1                # that comes after it on the tape in the same nanosecond
            if later < len(read20_of):
                standing = min(standing, int(read20_of[later]) - 1)
            before = at_it = flow_at(standing)
        else:
            before, at_it = flow_at(rd - 1), flow_at(rd)
        tape_lines.append((int(position[row]), int(received[row]),
                           {BUY: SIDE_TEXT[1], SELL: SIDE_TEXT[-1]}.get(side[row]), int(size[row]),
                           t['price'][row] / PRICE_UNIT, rd, before, at_it, now,
                           None if j is None else starts.get(j), None if j is None else ends.get(j)))
    files.append(save(out, f'crypto-ng-tick-tape-trades-{day}.parquet', dict(zip(
        names_of(TAPE_COLUMNS), map(list, zip(*tape_lines)))), {'side'}))

    no_side = trade & ~sided
    marked_left = [c for c, _, _ in found if r60['trade'][c] == tick.NONE]
    receipt = dict(
        what='The natural gas exhaustion calculation of the crypto and ng program, made at the tick: every trade '
             'at its own nanosecond',
        asked='Greg, 2026-11-18: "I want everything in our new exhaustion calc to be exactly like the old calc"; '
              '"Definitely run it on nano ticks"; "We have to rerun the exhaustion data on the pods first"',
        use='OBSERVATION AND VERIFICATION ONLY. Never a signal, never an input to another calculation.',
        left_out_on_his_word=['the winner and loser labels', 'the average line of each kind',
                              'the short or long split (each trade\'s length is a stored number, no label)'],
        not_written=['the program\'s divergence read beside each trade (dipole_class, rev_conv): it was never used '
                     'on this path, and its July form is not a calculation at the tick'],
        trade_day=trade_day.isoformat(),
        rules=dict(
            source='the rules of the July 2026 crypto calculation (DavisAI1974/Markets '
                   '75b15fa10193fab218b6469e5e5f0f49359880e1), written at the nanosecond',
            rules_file_git_blob_id=blob(RULES_FILE.read_bytes()),
            natural_gas_settings=tick.SETTINGS, half_spread_bps=hs,
            how_time_is_read='a trade enters each line at the nanosecond it was received and leaves it exactly 20 '
                             '(or 60) seconds later; the turn finder is walked over every moment the 60-second lean '
                             'changes; the wait is 30 seconds',
            read_order='a line is read after every sided trade is received (one read per trade, in tape order, '
                       'also when several share a nanosecond) and at every moment trades leave the span (one read '
                       'per moment; trades leaving at the nanosecond a trade is received leave first and are read '
                       'with it)',
            the_start='the turn finder starts at the open of the trade day, where nothing has traded and the July '
                      'rule reads 0'),
        inputs=[
            dict(input='buy', what='every trade on the tape with the tape\'s own aggressor side B, each at its own '
                                   'nanosecond', trades=int(s_buy.sum()), size=int(s_size[s_buy].sum())),
            dict(input='sell', what='every trade on the tape with the tape\'s own aggressor side A',
                 trades=int((~s_buy).sum()), size=int(s_size[~s_buy].sum())),
            dict(input='a trade with no side', what='a trade the tape gives no aggressor side for: in neither '
                                                    'bought nor sold; it has its own line in the tape-trades table',
                 trades=int(no_side.sum()), size=int(size[no_side].sum())),
            dict(input='mid', what='halfway between the best bid and the best ask on the stored row: the row of the '
                                   'trade, or the latest row at or before a moment with no tick. Used only for the '
                                   'program\'s own price columns; no line, turn or trade of the program reads it',
                 ticks_with_both_sides_standing=int(both.sum()), ticks_with_one_side_empty=int((~both).sum())),
            dict(input='half_spread_bps', what='half the middle value of spread over mid, every 50th tick with both '
                                               'sides standing (the July figure). Used only for the '
                                               'program\'s own price columns'),
        ],
        columns=dict(line=[dict(column=c, what=w) for c, w in LINE_COLUMNS],
                     turns=[dict(column=c, what=w) for c, w in TURN_COLUMNS],
                     program_trades=[dict(column=c, what=w) for c, w in TRADE_COLUMNS],
                     tape_trades=[dict(column=c, what=w) for c, w in TAPE_COLUMNS]),
        counts=dict(
            ticks=int(len(position)), trades_on_the_tape=int(trade.sum()), trades_with_a_side=int(sided.sum()),
            trades_the_tape_gives_no_side_for=int(no_side.sum()),
            reads_of_the_20_second_line=int(len(flow)),
            of_them_at_a_moment_trades_left_with_no_tick=int((r20['trade'] == tick.NONE).sum()),
            reads_of_the_20_second_line_with_nothing_traded=int(quiet20.sum()),
            reads_of_the_60_second_lean=int(len(lean)),
            turns_found=len(found), turns_marked_at_a_moment_with_no_tick=len(marked_left),
            of_them_marked_as_the_60_seconds_emptied=sum(1 for c in marked_left if quiet60[c]),
            what_became_of_the_turns=dict(collections.Counter(fate)),
            trades_of_the_program=len(made),
            how_they_ended=dict(collections.Counter(leg['ended'] for leg in made)),
            trades_of_the_program_starting_inside_the_first_45_seconds=sum(
                1 for leg in made if leg['onset_ns'] - opens < tick.PRE_NS),
            pictures_in_this_run=0),
        built_in='Every onset is a trade against the trade\'s own side (the program is filled by the next trade on '
                 'the other side), so the line steps against the trade at the onset and steps back exactly 20 '
                 'seconds later when that trade leaves. A turn is marked only after recent trading has moved the '
                 'trade\'s way, so the rise into the onset is partly made by how the trades are chosen. On thin '
                 'tape a turn can be marked when old trades leave the 60 seconds with nothing new traded: counted '
                 'above, nothing filtered.',
        checks=check, files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'CRYPTO-NG-TICK-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def draw(path: Path, title: str, x: np.ndarray, y: np.ndarray, marks: list, curve: bool) -> dict:
    """One trade, one picture, one graph. `x`: seconds from the trade's start at every read of the stretch, `y`:
    the line after each read, turned to the trade's side (not-a-number where nothing traded)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axis = plt.subplots(figsize=GRAPH_INCHES)
    empty = np.isnan(y)
    if curve:                                          # drawing only: a shape-keeping curve through the line's own
        from scipy.interpolate import PchipInterpolator   # points; no value moves; the line itself moves in steps
        last = np.append(np.diff(x) > 0, True) & ~empty
        runs = np.split(np.flatnonzero(last), np.flatnonzero(np.diff(np.cumsum(empty)[last]) > 0) + 1)
        for k, run_ in enumerate(runs):
            label = 'the 20-second flow, turned to the trade\'s side, DRAWN SMOOTH (the line itself moves in steps)'
            if len(run_) > 1:
                fine = np.linspace(x[run_[0]], x[run_[-1]], CURVE_POINTS)
                axis.plot(fine, PchipInterpolator(x[run_], y[run_])(fine), color='#1f618d', lw=LINE,
                          label=None if k else label)
            axis.scatter(x[run_], y[run_], s=SMALL, color='#1f618d')
    else:
        axis.step(x, y, where='post', color='#1f618d', lw=LINE, label='the 20-second flow, turned to the trade\'s side')
    if empty.any():
        axis.step(x, np.where(empty, 0.0, np.nan), where='post', color='gray', ls=':', lw=LINE,
                  label='nothing traded in these 20 seconds (the July line reads 0 here)')
    for at, colour, style, label in marks:
        axis.axvline(at, color=colour, ls=style, lw=THIN if colour == 'black' else LINE, label=label)
    axis.axhline(0, color='gray', lw=THIN)
    axis.set_ylim(-FLOW_LIMIT, FLOW_LIMIT)
    axis.set_xlabel('seconds from the trade\'s start (0)')
    axis.set_ylabel('flow (up = with the trade)')
    axis.set_title(title, fontsize=BIG)
    axis.legend(fontsize=SMALL, loc='upper center', bbox_to_anchor=LEGEND_AT)
    axis.grid(alpha=FAINT)
    figure.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(figure)
    raw = path.read_bytes()
    return dict(file=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def print_one(trade_day, out: Path, moment=None, trade=None, tape_position=None) -> dict:
    """One trade's own exhaustion graph, printed twice (steps; a smooth curve, drawing only) from what the data
    run stored in `out`. A trade of the program is named by its number or by a moment on the received clock (the
    trade under way then; when the program held none, the next to start). Its stretch (Greg, 2026-11-18: "We also
    want to be measuring exhaustion prior to trade start and after trade ends"; "It looks like we are truncating
    the exhaustion data in the render at the start and end"): from the start of the trade before it to the end of
    the trade after it, and never less than 45 seconds before its start and 60 seconds after its END. A trade of
    the tape is named by its position: 45 seconds before it to 60 seconds after it."""
    import pyarrow.parquet as pq
    day = f'{trade_day:%Y%m%d}'
    opens, closes = trade_day_bounds(trade_day)
    line = pq.read_table(out / f'crypto-ng-tick-line-20s-{day}.parquet', columns=['moment_received_ns', 'flow'])
    moments = line.column('moment_received_ns').to_numpy()
    values = np.array([np.nan if v is None else v for v in line.column('flow').to_pylist()], float)
    if tape_position is not None:
        named = [t for t in pq.read_table(out / f'crypto-ng-tick-tape-trades-{day}.parquet').to_pylist()
                 if t['position_on_tape'] == tape_position]
        checks.need(named, f'no trade on the tape of this trade day at position {tape_position}')
        chosen, why = named[0], 'a trade on the tape, named by its position'
        checks.need(chosen['side'] is not None, 'the tape gives this trade no side: its line cannot be turned to it')
        start = end = chosen['received_time_ns']
        first, last = start - tick.PRE_NS, end + tick.POST_NS
        stem = f'{day}-tape-{tape_position}'
        head = (f'Trade on the tape at position {tape_position}: a {chosen["side"]} of {chosen["size"]} at '
                f'{chosen["price"]}.\nReceived {clock_text(start)} Eastern.\nThe 20-second line from 45 s '
                f'before it to 60 s after it.')
        marks = [(0.0, 'black', '--', 'the trade (0)')]
    else:
        trades = pq.read_table(out / f'crypto-ng-tick-program-trades-{day}.parquet').to_pylist()
        checks.need(trades, 'the data run stored no trade of the program for this trade day')
        still = lambda t: closes if t['end_received_ns'] is None else t['end_received_ns']
        if trade is None:
            under_way = [t for t in trades if t['onset_received_ns'] <= moment < still(t)]
            later = [t for t in trades if t['onset_received_ns'] > moment]
            checks.need(under_way or later, 'no trade of the program was under way at that moment and none started after')
            chosen, why = ((under_way[0], 'the trade under way at that moment') if under_way else
                           (later[0], 'the program held no trade at that moment: the next trade to start'))
        else:
            named = [t for t in trades if t['trade'] == trade]
            checks.need(named, f'the program made no trade numbered {trade} on this trade day')
            chosen, why = named[0], 'named by its number'
        start, end = chosen['onset_received_ns'], still(chosen)
        before = [t for t in trades if t['trade'] == chosen['trade'] - 1]
        after = [t for t in trades if t['trade'] == chosen['trade'] + 1]
        first = min([start - tick.PRE_NS] + [t['onset_received_ns'] for t in before])
        last = max([end + tick.POST_NS] + [still(t) for t in after])
        stem = f'{day}-trade-{chosen["trade"]:0{TRADE_DIGITS}d}'
        lasted = 'still open at the last tick' if chosen['length_seconds'] is None \
            else f'lasted {chosen["length_seconds"]:,.3f} s'
        head = (f'Trade {chosen["trade"]} of the program: its {chosen["side"]}. Started '
                f'{clock_text(start)} Eastern; {lasted}.\nIts own exhaustion line, from the start of the '
                f'trade before it to the end of the trade after it\n(never less than 45 s before its start and '
                f'60 s after its end).')
        marks = [(0.0, 'black', '--', 'the trade starts (0): it was filled'),
                 ((end - start) / NS_PER_SECOND, '#b03a2e', ':', 'where this trade ended')]
    first, last = max(first, opens), min(last, closes)
    a = max(int(np.searchsorted(moments, first, 'right')) - 1, 0)       # the read standing at the left edge
    b = int(np.searchsorted(moments, last, 'right'))
    checks.need(b > a, 'the stored line has no read inside this stretch')
    sign = 1 if chosen['side'] == SIDE_TEXT[1] else -1
    x = np.r_[np.maximum(moments[a:b], first), last].astype(float) - start
    y = np.r_[values[a:b], values[b - 1]] * sign
    if moments[a] > first:                             # no read yet at the left edge: nothing had traded
        x, y = np.r_[float(first - start), x], np.r_[np.nan, y]
    x = x / NS_PER_SECOND
    title = (f'Crypto and ng program at the tick, natural gas. Trade day {trade_day:%a %b %d, %Y}.\n{head}\n'
             f'Nothing averaged. Every trade at its own nanosecond.')
    files = [draw(out / f'crypto-ng-tick-exhaustion-{stem}-{how}.png', title, x, y, marks, how == 'curve')
             for how in ('steps', 'curve')]
    receipt = dict(what='One trade\'s own exhaustion graph, printed twice from the stored 20-second line of the '
                        'data run: as the steps the line moves in, and as a smooth curve through its own points '
                        '(drawing only)',
                   asked='Greg, 2026-11-18: "Each trade should have its own exhaustion graph. No more than one graph '
                         'per render"; "We also want to be measuring exhaustion prior to trade start and after trade '
                         'ends"; "we want the line to look like a curve and not like straight lines right or does it '
                         'matter?"',
                   trade_day=trade_day.isoformat(),
                   asked_for=dict(moment_received_ns=moment, trade=trade, position_on_tape=tape_position),
                   chosen=why, trade=chosen,
                   stretch=dict(first_received_ns=int(first), last_received_ns=int(last),
                                first_eastern=eastern_text(int(first)), last_eastern=eastern_text(int(last)),
                                seconds_before_the_start=(start - first) / NS_PER_SECOND,
                                seconds_after_the_end=(last - end) / NS_PER_SECOND, reads_drawn=int(b - a)),
                   files=files)
    (out / f'CRYPTO-NG-TICK-PRINT-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The natural gas exhaustion calculation, crypto and ng, at the tick')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--moment', type=int, help='print the graph of the program\'s trade under way at this received ns')
    ap.add_argument('--trade', type=int, help='print the graph of the program\'s trade with this number')
    ap.add_argument('--tape', type=int, help='print the graph of the trade on the tape at this position')
    a = ap.parse_args()
    if a.moment is not None or a.trade is not None or a.tape is not None:
        print(json.dumps(print_one(parse_trade_day(a.trade_day), a.out, a.moment, a.trade, a.tape), indent=1))
        return
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
