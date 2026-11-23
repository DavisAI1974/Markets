"""ROOT: the earlier research threads read again on the rebuilt data. Questions only; no old value is carried.

Greg, 2026-11-23: "Did we redo the research threads to have value with our current data yet? If not ... rerun those
threads with the better data ... Just use the research avenues that are already there"; "not the research values,
just the questions"; "Go but make sure these research threads are adding value. We don't have to rerun the ones
that aren't". The questions are those of `root-audit-20261116/RESEARCH_INTENTIONS.md` (Codex's reanalysis and
discovery work, Desktop's family research, Claude's reanalysis), and Desktop's three concepts of 2026-11-23.

NOTHING NEW IS CALCULATED ON THE TAPE. Stored lines are laid side by side at moments the data itself sets, and
counted. Two tables for one trade day, every line one event, and one page of counts:

1. THE MOVES (`research-moves-<trade day>.parquet`): one line per move in price that the stored `move_steps`
   follows (a trade leg, a run of the best bid, a run of the best ask). From its own stored lines: the tick it
   first could be known (its first step), how many steps it made in all, where it ended, what it gave back, and
   what stood at the best prices at that first step. Laid beside it, each a stored value read at that tick:
   - the natural gas EXHAUSTION line (20 seconds) and DIPOLE line (60 seconds) as they stood at the first step and
     at the end (the stored crypto-formula lines; as stored, above zero buying; Greg, 2026-11-23: "The ng version
     of these absolutely should be used");
   - for a run of the quote that took a second step: what became of the orders that stood at that quote's best
     price when the run started, by the second step (the stored `resting` line): how many were filled, how many
     were pulled, how many still rested;
   - for a trade leg: the best bid and the best offer at its first trade, so the leg in the prints can be read
     against the quote (a print bouncing between bid and offer, or the quote really stepping).
   Threads: how much of a move is left when it can first be known; do large moves come back; the print against
   the quote; the thin quote and the whole side at the start of a move; a level eaten or pulled.
2. THE HUMPS (`research-humps-<trade day>.parquet`): one line per hump of the stored 20-second exhaustion line
   (the time it stays on one side of zero: the data's own event). The stored hump, and beside it:
   - whether it began, and ended, on a trade or at a moment old trades left the 20 seconds with nothing new
     traded (made by the span, not by the market);
   - the best bid and the best offer, EACH ON ITS OWN AND NO MIDPOINT, and the dipole line, at the moment it
     began, at the moment the line first stood at its furthest, and at the moment it ended;
   - what came next on the tape after it began, and what came last before it: a step of the best bid, a step of
     the best offer, a trade on the hump's side, a trade on the other side; for each, its tick and nanosecond.
   Threads: is anything observable before an event begins; the dive, the flip and the tail against the price;
   which comes first, the trade or the quote stepping; a change in flow that is fresh trading against one that is
   old trades leaving.
3. THE COUNTS (in the receipt): each a count of lines of these two tables, for this trade day alone.

WHAT IS NOT DONE HERE, and why (said to Greg): the models over every layer together and anything on Native's births
or the eight trade types (his standing rules); the outside figures (too few changes inside four trade days, and
held by him for the later stage); the orders standing at EVERY level of a move, one order's life after a part
fill, and Codex's information measure (each would be a new calculation: the last one also needs one-second bins).
NO WINDOW, NO LABEL, NO AVERAGE, NO MIDPOINT, NOTHING RANKED. Nothing crosses from one trade day to another.

EVERY STORED LINE IS READ BY PLACE ON THE TAPE, NEVER BY TIME ALONE (corrected 2026-11-23). The first run took "the
last read at or before the tick's nanosecond"; several trades can share a nanosecond, so that read stood on trades
that came after the tick. `root/research_trace.py` traced it: every first step whose two exhaustion figures
differed is equal once read by place. A read now holds nothing that came after its tick on the tape.

    python3 -m root.research_threads 20231017 --rows <folder of the trade day's stored files> --out <folder>
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
from root import leg_renders as LR
from root.calendar import parse_trade_day
from root.crypto_ng_tick import HUMP_COLUMNS

LEG, RUNS = 'trade leg', {'run of the best bid': 'bid', 'run of the best ask': 'ask'}   # the stored moves
STEP, ENDED = 'step', 'ended'                          # the two kinds of line `move_steps` stores
FIRST, SECOND, THIRD = 1, 2, 3                         # a move's first, second and third step
UP = 'up'                                              # the stored word for a move going up
CLOSE = 1e-9                                           # a check only: how near two readings of one line must be
BUY, SELL = 'buy', 'sell'
TRADE_READ = 'a trade was received'                    # the stored line's own word for a read made at a trade
LINES = dict(exhaustion_20s='crypto-ng-tick-line-20s', dipole_60s='crypto-ng-tick-lean-60s')   # the stored lines
READS = ['received_time_ns', 'best_bid', 'best_ask', 'best_bid_moved_from', 'best_bid_moved_to',
         'best_ask_moved_from', 'best_ask_moved_to', 'exchange_event']
AT_STEP = ['best_bid', 'best_ask', 'best_bid_size', 'best_ask_size', 'best_bid_orders', 'best_ask_orders',
           'bid_total_size', 'ask_total_size', 'run_side', 'run_size', 'run_trades']   # stored on a step line
PRICES = {'best_bid', 'best_ask'}
LEVEL = ['orders_at_turn', 'size_at_turn', 'left_by_fill', 'left_by_cancel', 'still_resting_orders', 'moved_orders']
NEXT = dict(bid_step='a step of the best bid', ask_step='a step of the best offer',
            same_side_trade='a trade on the hump\'s side', other_side_trade='a trade on the other side')
MARKS = dict(began='began_received_ns', furthest='furthest_received_ns', ended='ended_received_ns')
MOVE_COLUMNS = [
    ('move', 'Which move: trade leg, run of the best bid, run of the best ask.'),
    ('direction', 'Which way it goes: up or down.'),
    ('move_start_position', 'The move: the trade leg\'s first trade, or the tick the run started. A label only.'),
    ('first_step_position', 'The tick of its first step: the first moment it could be known. Position on the tape.'),
    ('first_step_received_ns', 'When that tick was received.'),
    ('first_step_price', 'The price it had reached at its first step, in dollars.'),
    ('second_step_received_ns', 'When its second step was received. Empty when it made one step only.'),
    ('steps_in_all', 'How many steps it made in all. Empty when it was still going at the last tick.'),
    ('end_position', 'The tick it ended at. Empty when it was still going.'),
    ('end_received_ns', 'When that tick was received.'),
    ('end_price', 'The price it ended at, in dollars.'),
    ('given_back', 'The price once the ending tick was done minus the price it ended at, in dollars.'),
] + [(f'{name}_at_first_step', f'As stored on its first step line, once that tick was done: {name}'
      + (' (dollars).' if name in PRICES else '.')) for name in AT_STEP] + [
    ('exhaustion_20s_at_first_step', 'THE EXHAUSTION LINE at its first step: bought minus sold over bought plus sold, '
     'the trades of the last 20 seconds, the stored line as it stood AT THAT TICK (read by place on the tape: no '
     'trade that came after the tick is in it, also when it shares the tick\'s nanosecond). Above zero buying, below '
     'zero selling. Empty where nothing with a side had traded in the span.'),
    ('dipole_60s_at_first_step', 'THE DIPOLE LINE at its first step: the same figure over the last 60 seconds.'),
    ('best_bid_at_end', 'The best bid once its ending tick was done, in dollars.'),
    ('best_ask_at_end', 'The best offer once its ending tick was done, in dollars.'),
    ('exhaustion_20s_at_end', 'The exhaustion line as it stood at its end.'),
    ('dipole_60s_at_end', 'The dipole line as it stood at its end.'),
    ('best_bid_at_first_trade', 'Trade legs only: the best bid once the tick of its first trade was done, in dollars.'),
    ('best_ask_at_first_trade', 'Trade legs only: the best offer once the tick of its first trade was done.'),
] + [(f'level_{name}', 'Runs of the quote that took a second step only, from the stored resting line at that second '
      f'step, for the orders that stood at that quote\'s best price when the run started: {what}')
     for name, what in zip(LEVEL, ('how many orders stood there.', 'their size.', 'how many had left by being filled.',
                                   'how many had left by being pulled.', 'how many still rested.',
                                   'how many had changed price.'))]
HUMP_ADDED = [
    ('began_on', 'What the stored line says changed it as the hump began: a trade was received, or trades left the '
     'span at a moment with no tick (nothing new had traded).'),
    ('began_position', 'The trade it began on: its position on the tape. Empty when it began with no tick.'),
    ('ended_on', 'The same for the read at which it ended. Empty when it had not ended.'),
] + [(f'{what}_at_{mark}', f'{words} as it stood at the moment the hump {said}'
      + (', in dollars: once the tick of that read was done (when the read is trades leaving the span: once the '
         'last tick received before that moment was done).' if what != 'dipole_60s'
         else ', read by place on the tape: no trade that came after that read is in it.'))
     for mark, said in (('began', 'began'), ('furthest', 'first stood at its furthest'), ('ended', 'ended'))
     for what, words in (('best_bid', 'The best bid'), ('best_ask', 'The best offer'),
                         ('dipole_60s', 'The dipole line (60 seconds)'))] + [
    (f'{when}_{name}_{part}', f'{("The first" if when == "next" else "The last")} {words} '
     f'{("after" if when == "next" else "before")} the hump began: '
     + dict(position='its position on the tape.', received_ns='when it was received.',
            price_from='the price it stepped from, in dollars.', price_to='the price it stepped to, in dollars.',
            same_event='yes when it is in the same exchange event as the trade the hump began on.')[part])
    for when in ('next', 'last') for name, words in NEXT.items()
    for part in (('position', 'received_ns') + (('price_from', 'price_to') if name.endswith('step') else ())
                 + (('same_event',) if when == 'next' else ()))]
HUMP_NAMES = [name for name, _ in HUMP_COLUMNS] + [name for name, _ in HUMP_ADDED]
MOVE_NAMES = [name for name, _ in MOVE_COLUMNS]
TEXT = {'move', 'direction', 'run_side_at_first_step', 'side', 'how_it_began', 'how_it_ended', 'began_on', 'ended_on'}
YES_NO = {name for name in HUMP_NAMES if name.endswith('same_event')}


def dollars(price):
    return None if price is None else price / LR.PRICE_UNIT


def parts(rows_folder: Path, stem: str, columns=None) -> dict:
    """Every part of one stored table, in order, as one set of columns."""
    files = sorted(rows_folder.glob(f'{stem}-part*.parquet'))
    checks.need(files, f'{stem} is not beside the rows')
    held = collections.defaultdict(list)
    for path in files:
        for name, values in LR.table(path, columns).items():
            held[name] += values
    return dict(held)


def standing(line: dict, at: int, position) -> int:
    """The read of a stored line standing AT A TICK: the last one made before the tick's nanosecond, or at it and not
    after the tick on the tape (trades leaving at a nanosecond leave first; a trade's read counts when its place on
    the tape is at or before the tick's). With no tick (`position` empty: a moment trades left the span) only
    trades leaving at that nanosecond count. Below zero: none yet. NEVER BY TIME ALONE: several trades can share a
    nanosecond, and the last read at that nanosecond stands on trades that came after the tick (traced by
    `root/research_trace.py`, 2026-11-23)."""
    a, b = int(np.searchsorted(line['moments'], at, 'left')), int(np.searchsorted(line['moments'], at, 'right'))
    k = a - 1
    for r in range(a, b):
        if line['what'][r] != TRADE_READ or (position is not None and line['position'][r] <= position):
            k = r
    return k


def the_lines(rows_folder: Path, day: str) -> dict:
    out = {}
    for name, file in LINES.items():
        held = LR.table(rows_folder / 'crypto-ng-tick' / f'{file}-{day}.parquet',
                        ['moment_received_ns', 'what', 'position_on_tape', 'flow'])
        moments = np.array(held['moment_received_ns'], np.int64)
        checks.need(len(moments) and bool(np.all(np.diff(moments) >= 0)), f'the stored {file} is not in time order')
        out[name] = dict(moments=moments, flow=held['flow'], what=held['what'], position=held['position_on_tape'])
    return out


def line_at(line: dict, at, position):
    if at is None:
        return None
    k = standing(line, at, position)
    return line['flow'][k] if k >= 0 else None


def the_quote(rows_folder: Path, trade_day) -> dict:
    """What the stored rows hold of the quote, through the rows gate: at every tick, the best bid and best offer
    once that tick was done, and the marks of a step of either."""
    held = {name: [] for name in ['position'] + READS}
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        held['position'].append(position)
        for name, value in zip(READS, row):
            held[name].append(value)
    q = dict(position=np.array(held['position'], np.int64), received=np.array(held['received_time_ns'], np.int64),
             event=held['exchange_event'], bid=held['best_bid'], ask=held['best_ask'])
    checks.need(len(q['received']) and bool(np.all(np.diff(q['received']) >= 0)), 'the received time goes backwards')
    for side in ('bid', 'ask'):
        to = held[f'best_{side}_moved_to']
        where = np.array([k for k, v in enumerate(to) if v is not None], np.int64)
        q[f'{side}_step'] = dict(rows=where, position=q['position'][where],
                                 price_from=[held[f'best_{side}_moved_from'][k] for k in where],
                                 price_to=[to[k] for k in where])
    return q


def quote_at(q: dict, row_of: dict, at, position):
    """The best bid and the best offer standing at a tick: once that tick was done. With no tick (a moment trades
    left the span): once the last tick received before that moment was done."""
    if at is None:
        return None, None
    k = row_of[position] if position is not None else int(np.searchsorted(q['received'], at, 'left')) - 1
    return (dollars(q['bid'][k]), dollars(q['ask'][k])) if k >= 0 else (None, None)


def the_moves(rows_folder: Path, day: str, lines: dict, q: dict) -> tuple:
    f = parts(rows_folder, f'calc-move_steps-facts-{day}')
    n = len(f['move'])
    steps, ended = collections.defaultdict(dict), {}
    for k in range(n):
        key = (f['move'][k], f['move_start_position'][k])
        if f['fact'][k] == STEP:
            checks.need(f['step'][k] not in steps[key], f'{key}: one step is stored twice')
            steps[key][f['step'][k]] = k
        else:
            checks.need(f['fact'][k] == ENDED and key not in ended, f'{key}: a move ends twice, or a line is neither')
            ended[key] = k
    checks.need(set(ended) <= set(steps), 'a move has an ending line and no step line')
    agree = collections.Counter()                      # the stored line against the step line's own 20-second flow
    r = parts(rows_folder, f'calc-resting-facts-{day}',
              ['about', 'earlier_turn_position', 'known_position'] + [f'{s}_best_{x}' for s in RUNS.values() for x in LEVEL])
    level = {(a, e, p): k for k, (a, e, p) in enumerate(zip(r['about'], r['earlier_turn_position'], r['known_position']))}
    place = {int(p): k for k, p in enumerate(q['position'].tolist())}
    out, missing_level = [], 0
    for key in sorted(steps, key=lambda key: f['known_position'][steps[key][FIRST]] if FIRST in steps[key] else key[1]):
        kind, start = key
        checks.need(FIRST in steps[key], f'{key}: a move with no first step line')
        a, z = steps[key][FIRST], ended.get(key)
        checks.need(sorted(steps[key]) == list(range(FIRST, len(steps[key]) + FIRST)), f'{key}: its steps are not in a row')
        if z is not None:
            checks.need(f['steps_in_all'][z] == len(steps[key]), f'{key}: its steps do not add up to the stored count')
        b = steps[key].get(SECOND)
        line = {name: None for name in MOVE_NAMES}
        line.update(move=kind, direction=f['direction'][a], move_start_position=start,
                    first_step_position=f['known_position'][a], first_step_received_ns=f['known_received_time_ns'][a],
                    first_step_price=dollars(f['price'][a]),
                    second_step_received_ns=f['known_received_time_ns'][b] if b is not None else None)
        for name in AT_STEP:
            line[f'{name}_at_first_step'] = dollars(f[name][a]) if name in PRICES else f[name][a]
        for name, stored_line in lines.items():
            line[f'{name}_at_first_step'] = line_at(stored_line, f['known_received_time_ns'][a], f['known_position'][a])
        bought, sold, ours = f['flow_bought_20s'][a], f['flow_sold_20s'][a], line['exhaustion_20s_at_first_step']
        if not bought and not sold:
            agree['both empty' if ours is None else 'the step line holds no flow, the stored line does'] += 1
        elif ours is None:
            agree['the stored line is empty, the step line holds flow'] += 1
        else:
            agree['equal' if abs((bought - sold) / (bought + sold) - ours) <= CLOSE else 'not equal'] += 1
        if z is not None:
            line.update(steps_in_all=f['steps_in_all'][z], end_position=f['known_position'][z],
                        end_received_ns=f['known_received_time_ns'][z], end_price=dollars(f['price'][z]),
                        given_back=dollars(f['given_back'][z]), best_bid_at_end=dollars(f['best_bid'][z]),
                        best_ask_at_end=dollars(f['best_ask'][z]))
            for name, stored_line in lines.items():
                line[f'{name}_at_end'] = line_at(stored_line, f['known_received_time_ns'][z], f['known_position'][z])
        if kind == LEG:
            checks.need(start in place, f'{key}: its first trade is not a tick of the trade day')
            line['best_bid_at_first_trade'] = dollars(q['bid'][place[start]])
            line['best_ask_at_first_trade'] = dollars(q['ask'][place[start]])
        elif b is not None:
            k = level.get((kind, start, f['known_position'][b]))
            if k is None:
                missing_level += 1
            else:
                for x in LEVEL:
                    line[f'level_{x}'] = r[f'{RUNS[kind]}_best_{x}'][k]
        out.append([line[name] for name in MOVE_NAMES])
    return out, dict(moves=len(out), moves_that_ended=len(ended), moves_still_going_at_the_last_tick=len(out) - len(ended),
                     runs_with_a_second_step_and_no_resting_line=missing_level,
                     first_steps_the_stored_exhaustion_line_against_the_step_lines_own_20_second_flow=dict(agree))


def nearest(positions: np.ndarray, p0: int, after: bool, on_a_trade: bool):
    """The first of some ticks after a place on the tape, or the last before it (None when there is none)."""
    if after:
        k = int(np.searchsorted(positions, p0, 'right'))
        return k if k < len(positions) else None
    k = int(np.searchsorted(positions, p0, 'left' if on_a_trade else 'right')) - 1
    return k if k >= 0 else None


def the_humps(rows_folder: Path, day: str, lines: dict, q: dict) -> tuple:
    tick = rows_folder / 'crypto-ng-tick'
    stored = LR.table(tick / f'crypto-ng-tick-humps-{day}.parquet', [name for name, _ in HUMP_COLUMNS])
    trades = LR.table(tick / f'crypto-ng-tick-tape-trades-{day}.parquet', ['position_on_tape', 'received_time_ns', 'side'])
    by_side = {}
    for side in (BUY, SELL):
        keep = [k for k, s in enumerate(trades['side']) if s == side]
        by_side[side] = dict(position=np.array([trades['position_on_tape'][k] for k in keep], np.int64),
                             received=[trades['received_time_ns'][k] for k in keep])
    line, lean = lines['exhaustion_20s'], lines['dipole_60s']
    sign = {BUY: 1, SELL: -1}
    row_of = {int(p): k for k, p in enumerate(q['position'].tolist())}
    out = []
    for h in range(len(stored['hump'])):
        got = {name: stored[name][h] for name, _ in HUMP_COLUMNS}
        side, began, ended = got['side'], got['began_received_ns'], got['ended_received_ns']
        a, b = int(np.searchsorted(line['moments'], began, 'left')), int(np.searchsorted(line['moments'], began, 'right'))
        first = next((k for k in range(a, b) if line['flow'][k] is not None and line['flow'][k] * sign[side] > 0), None)
        checks.need(first is not None, f'hump {got["hump"]}: no read of the stored line begins it')
        on_a_trade = line['what'][first] == TRADE_READ
        got.update(began_on=line['what'][first], began_position=line['position'][first] if on_a_trade else None)
        own = dict(began=first)                        # the read of the stored line each of its moments is
        if ended is not None:
            a, b = int(np.searchsorted(line['moments'], ended, 'left')), int(np.searchsorted(line['moments'], ended, 'right'))
            last = next((k for k in range(a, b) if line['flow'][k] is None or line['flow'][k] * sign[side] <= 0), None)
            checks.need(last is not None, f'hump {got["hump"]}: no read of the stored line ends it')
            got['ended_on'] = line['what'][last]
            own['ended'] = last
        a, b = (int(np.searchsorted(line['moments'], got['furthest_received_ns'], edge)) for edge in ('left', 'right'))
        far = next((k for k in range(max(a, first), b) if line['flow'][k] == got['furthest_flow']), None)
        checks.need(far is not None, f'hump {got["hump"]}: no read of the stored line is its furthest')
        own['furthest'] = far
        for mark, column in MARKS.items():              # each read by place on the tape, never by time alone
            r = own.get(mark)
            place = line['position'][r] if r is not None and line['what'][r] == TRADE_READ else None
            got[f'best_bid_at_{mark}'], got[f'best_ask_at_{mark}'] = quote_at(q, row_of, got[column], place)
            got[f'dipole_60s_at_{mark}'] = line_at(lean, got[column], place)
        # the place on the tape the hump began at: its own trade, or the last tick received before its moment
        p0 = got['began_position'] if on_a_trade else \
            (int(q['position'][k]) if (k := int(np.searchsorted(q['received'], began, 'left')) - 1) >= 0 else -1)
        own_event = q['event'][row_of[p0]] if on_a_trade and p0 in row_of else None
        other = SELL if side == BUY else BUY
        for when, after in (('next', True), ('last', False)):
            for name in NEXT:
                if name.endswith('step'):
                    s = q[name]
                    k = nearest(s['position'], p0, after, on_a_trade)
                    if k is None:
                        continue
                    row = int(s['rows'][k])
                    got.update({f'{when}_{name}_position': int(s['position'][k]),
                                f'{when}_{name}_received_ns': int(q['received'][row]),
                                f'{when}_{name}_price_from': dollars(s['price_from'][k]),
                                f'{when}_{name}_price_to': dollars(s['price_to'][k])})
                    event = q['event'][row]
                else:
                    t = by_side[side if name.startswith('same') else other]
                    k = nearest(t['position'], p0, after, on_a_trade)
                    if k is None:
                        continue
                    got.update({f'{when}_{name}_position': int(t['position'][k]),
                                f'{when}_{name}_received_ns': t['received'][k]})
                    event = q['event'][row_of[int(t['position'][k])]] if int(t['position'][k]) in row_of else None
                if after:
                    got[f'{when}_{name}_same_event'] = bool(own_event is not None and event == own_event)
        out.append([got.get(name) for name in HUMP_NAMES])
    return out, dict(humps=len(out))


def sided(value, direction: str) -> str:
    """A stored line against a move's direction, in words (a count is made of these; nothing is typed on a line)."""
    if value is None:
        return 'the line was empty'
    if value == 0:
        return 'the line stood at zero'
    return 'the line was on the move\'s side' if (value > 0) == (direction == UP) else 'the line was against the move'


def emptied(orders, filled, pulled) -> str:
    if not orders:
        return 'no order stood there'
    if filled == orders:
        return 'every order filled'
    if pulled == orders:
        return 'every order pulled'
    if filled and pulled and filled + pulled == orders:
        return 'some filled, some pulled'
    return 'other (an order still rested or changed price)'


def the_counts(moves: list, humps: list) -> dict:
    """Counts of lines of the two tables, this trade day alone. Nothing is averaged and no trade day is added to
    another."""
    M, H = {name: k for k, name in enumerate(MOVE_NAMES)}, {name: k for k, name in enumerate(HUMP_NAMES)}
    tally = collections.defaultdict(lambda: collections.defaultdict(int))
    for m in moves:
        kind, way, steps = m[M['move']], m[M['direction']], m[M['steps_in_all']]
        if steps is None:
            continue
        who = f'{kind} {way}'
        tally[f'how much of a move was left at its first step | {who}'][f'{steps} steps in all'] += 1
        back = m[M['given_back']]
        tally[f'what a move gave back | {who}'][f'{steps} steps in all, gave back '
                                                + ('nothing stored' if back is None else f'{back:+.3f}')] += 1
        went_on = 'took a second step' if steps >= SECOND else 'one step only'
        for name in LINES:
            tally[f'the {name} line at the first step | {who}'][f'{sided(m[M[f"{name}_at_first_step"]], way)}: {went_on}'] += 1
        if kind == LEG:
            still = (m[M['best_bid_at_first_trade']], m[M['best_ask_at_first_trade']]) == \
                (m[M['best_bid_at_end']], m[M['best_ask_at_end']])
            tally[f'the print against the quote | {who}'][
                f'{steps} steps in all: the best bid and the best offer ' + ('both stood where they were' if still else
                                                                             'were not both where they were')] += 1
        elif steps >= SECOND and m[M['level_orders_at_turn']] is not None:
            how = emptied(m[M['level_orders_at_turn']], m[M['level_left_by_fill']], m[M['level_left_by_cancel']])
            tally[f'how the first level emptied by the second step | {who}'][
                f'{how}: ' + ('took a third step' if steps >= THIRD else 'two steps only')] += 1
    for h in humps:
        side = h[H['side']]
        tally[f'how a hump began | {side}'][f'{h[H["began_on"]]}; trades inside: '
                                            + ('none' if not h[H['trades_inside']] else 'one or more')] += 1
        firsts = {name: h[H[f'next_{name}_position']] for name in NEXT if h[H[f'next_{name}_position']] is not None}
        if firsts:
            least = min(firsts.values())
            tally[f'what came first after a hump began | {side}, began on: {h[H["began_on"]]}'][
                ' and '.join(NEXT[name] for name in NEXT if firsts.get(name) == least)] += 1
    return {name: dict(sorted(counts.items())) for name, counts in sorted(tally.items())}


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    lines = the_lines(rows_folder, day)
    q = the_quote(rows_folder, trade_day)
    moves, move_counts = the_moves(rows_folder, day, lines, q)
    humps, hump_counts = the_humps(rows_folder, day, lines, q)
    count = dict(trade_day=trade_day.isoformat(), **move_counts, **hump_counts)
    (out / f'RESEARCH-THREADS-COUNT-{day}.json').write_text(json.dumps(count, indent=1) + '\n')
    files = []
    for stem, names, table in (('research-moves', MOVE_NAMES, moves), ('research-humps', HUMP_NAMES, humps)):
        columns = list(zip(*table)) if table else [[] for _ in names]
        arrays = [pa.array(list(column), type=pa.string() if name in TEXT else pa.bool_() if name in YES_NO else None)
                  for name, column in zip(names, columns)]
        name = f'{stem}-{day}.parquet'
        pq.write_table(pa.Table.from_arrays(arrays, names=names), out / name, compression='zstd',
                       compression_level=store.ZSTD_LEVEL)
        raw = (out / name).read_bytes()
        files.append(dict(file=name, rows=len(table), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    M = {name: k for k, name in enumerate(MOVE_NAMES)}
    H = {name: k for k, name in enumerate(HUMP_NAMES)}
    in_order = all(m[M['end_received_ns']] is None or m[M['end_received_ns']] >= m[M['first_step_received_ns']] for m in moves) \
        and all(h[H['ended_received_ns']] is None or h[H['began_received_ns']] <= h[H['furthest_received_ns']]
                <= h[H['ended_received_ns']] for h in humps)
    checks.need(in_order, 'a move or a hump ends before it begins')
    after = all(h[H[f'next_{name}_position']] is None or h[H[f'last_{name}_position']] is None or
                h[H[f'last_{name}_position']] < h[H[f'next_{name}_position']] for h in humps for name in NEXT)
    checks.need(after, 'a hump\'s last tick before it is not before its next tick after it')
    receipt = dict(
        what='The earlier research threads read again on the rebuilt data: every move in price and every hump of the '
             'exhaustion line, each on its own line, with stored values laid beside it; and counts of those lines',
        asked='Greg, 2026-11-23: "rerun those threads with the better data ... Just use the research avenues that are '
              'already there"; "not the research values, just the questions"; "make sure these research threads are '
              'adding value"',
        trade_day=trade_day.isoformat(),
        nothing_applied='No window, no label, no average, no midpoint, nothing ranked; no value of the old research; '
                        'nothing from another trade day. Prices are in dollars.',
        read_from=[f'calc-move_steps-facts-{day}-part*.parquet', f'calc-resting-facts-{day}-part*.parquet',
                   f'rows-{day}-part*.parquet (through the rows gate)', f'crypto-ng-tick/crypto-ng-tick-humps-{day}.parquet',
                   f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet']
                  + [f'crypto-ng-tick/{file}-{day}.parquet' for file in LINES.values()],
        tables=dict(moves=[dict(column=c, what=w) for c, w in MOVE_COLUMNS],
                    humps=[dict(column=c, what=w) for c, w in list(HUMP_COLUMNS) + HUMP_ADDED]),
        counts=count,
        the_counts=the_counts(moves, humps),
        checks=dict(passed=True,
                    what='every move has its first step line and its steps in a row, and they add up to the stored '
                         'count; no step is stored twice and no move ends twice; every trade leg\'s first trade is a '
                         'tick of the trade day; the stored lines and the rows are in time order; every hump is begun '
                         'and ended by a read of the stored line; no move or hump ends before it begins; a hump\'s '
                         'last tick before it is before its next tick after it; every moment of a hump is a '
                         'read of the stored line, and every stored line is read by place on the tape'),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'RESEARCH-THREADS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The earlier research threads read again on the rebuilt data')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--keep-cpus', action='store_true', help='accepted for the pod runner; this program uses one CPU')
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
