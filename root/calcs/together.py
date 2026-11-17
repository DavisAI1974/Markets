"""ROOT part 2, calculation `together`: orders that act together (addition N).

Approved by Greg, 2026-11-16 ("Try them all"; laid out in markets-data `STEP1_STEP2_LAYOUTS.md`, "Additions from
the look at Codex's two pieces", N). Orders that enter or leave at the same instant are likely one hand.

A SET is two or more orders that entered at the same exchange time, to the nanosecond; or two or more that left
at the same exchange time. "The same instant" is an exact match of the exchange's own time stamp, so no stretch of
time is picked. One line per order of a set, written at the first tick with a LATER exchange time, when the set is
known to be complete. Each line has both clocks: the order's own tick, and the tick the set became known.
On the line of an order that left: how it left (cancel or fill), when it entered (if it entered inside this trade
day), and how many others of the set that left with it had also entered at its instant.

Claude's calls in the build, stated to Greg (his to correct):
- Every set is written, of any size and at any price. Nothing is picked.
- Orders that leave by fill at the same instant are one aggressor's doing, not their own. They are in the set, and
  each line says how its order left, so the two can be told apart.
- Whether orders "had also entered together" is said only for orders that entered inside this trade day. For an
  order that entered before it, that cell is empty: nothing from before the trade day enters a calculation.
- A set still waiting for a later exchange time at the last tick of the trade day is listed in its own small file.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root import rows as R

READS = ['exchange_time_ns', 'received_time_ns', 'side', 'order_number', 'what_happened', 'order_size_before',
         'order_size_after', 'touched_price']
ENTERED, LEFT = 'entered together', 'left together'
KINDS = (ENTERED, LEFT)
LEAVING = (R.LEFT_BY_CANCEL, R.LEFT_BY_FILL)
SIDES = {'B': 'bid', 'A': 'ask'}
SET_FROM = 2                                           # a set is two or more orders
COLUMNS = [('together_lines_known', 'How many lines about orders that entered or left together became known at '
            'this tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
FACT_COLUMNS = [
    ('known_position', 'The tick at which the set became known: the first tick with a later exchange time. A label '
     'only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('fact', 'The kind of set: entered together, or left together.'),
    ('set_exchange_time_ns', 'The exchange time every order of the set shares.'),
    ('orders_in_set', 'How many orders the set holds.'),
    ('size_of_set', 'The size of those orders together (as they entered; or as they stood just before leaving).'),
    ('order_position', 'This order\'s own tick. A label only.'),
    ('order_received_time_ns', 'When that tick was received.'),
    ('order_number', 'The order. A label only.'),
    ('side', 'The side the order rests on: bid or ask.'),
    ('price', 'The price it entered at, or rested at when it left.'),
    ('size', 'Its size as it entered, or just before it left.'),
    ('how_left', 'On left together: left by cancel, or left by fill.'),
    ('entered_in_this_trade_day', 'On left together: yes when the order entered inside this trade day.'),
    ('entered_exchange_time_ns', 'On left together: the exchange time it entered at, when that was inside this '
     'trade day.'),
    ('others_that_entered_with_it', 'On left together: how many other orders of this set entered at the same '
     'exchange time as this one. Empty when the order entered before this trade day.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'fact', 'side', 'how_left'}
FACT_YES_NO = {'entered_in_this_trade_day'}
OPEN_COLUMNS = ['fact', 'set_exchange_time_ns', 'order_position', 'order_number']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, FACT_YES_NO, set()),
          'open-at-the-end': (OPEN_COLUMNS, {'fact'}, set(), set())}


class Together:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the lines that became known)."""

    def __init__(self):
        self.waiting = {kind: {} for kind in KINDS}    # kind -> exchange time -> the orders of that instant so far
        self.entered = {}                              # order -> the exchange time it entered at, this trade day
        self.counts = dict(sets={kind: 0 for kind in KINDS}, lines={kind: 0 for kind in KINDS},
                           largest_set={kind: 0 for kind in KINDS}, ticks_with_an_earlier_exchange_time=0)
        self.latest = None

    def _close(self, kind, moment, members, position, received) -> list:
        if len(members) < SET_FROM:
            return []
        self.counts['sets'][kind] += 1
        self.counts['lines'][kind] += len(members)
        self.counts['largest_set'][kind] = max(self.counts['largest_set'][kind], len(members))
        size = sum(member[5] for member in members)
        out = []
        for at, got, order, side, price, mine, how, entry in members:
            row = dict.fromkeys(FACT_NAMES)
            row.update(known_position=position, known_received_time_ns=received, fact=kind,
                       set_exchange_time_ns=moment, orders_in_set=len(members), size_of_set=size, order_position=at,
                       order_received_time_ns=got, order_number=order, side=side, price=price, size=mine)
            if kind == LEFT:
                with_it = None if entry is None else sum(1 for other in members if other[7] == entry) - 1
                row.update(how_left=how, entered_in_this_trade_day=entry is not None, entered_exchange_time_ns=entry,
                           others_that_entered_with_it=with_it)
            out.append(tuple(row[name] for name in FACT_NAMES))
        return out

    def tick(self, position, moment, received, side, order, what, before, after, price) -> tuple:
        lines = []
        if self.latest is not None and moment < self.latest:
            self.counts['ticks_with_an_earlier_exchange_time'] += 1
        self.latest = moment if self.latest is None else max(self.latest, moment)
        for earlier in sorted({t for kind in KINDS for t in self.waiting[kind] if t < moment}):
            for kind in KINDS:                         # every instant before this tick's is complete now
                members = self.waiting[kind].pop(earlier, None)
                if members:
                    lines += self._close(kind, earlier, members, position, received)
        if what == R.JOINED:
            self.entered[order] = moment
            self.waiting[ENTERED].setdefault(moment, []).append(
                (position, received, order, SIDES.get(side), price, after, None, None))
        elif what in LEAVING:
            self.waiting[LEFT].setdefault(moment, []).append(
                (position, received, order, SIDES.get(side), price, before, what, self.entered.pop(order, None)))
        return (len(lines),), lines

    def still_waiting(self) -> list:
        return [(kind, moment, member[0], member[2]) for kind in KINDS
                for moment, members in sorted(self.waiting[kind].items()) if len(members) >= SET_FROM
                for member in members]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = Together()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        values, new = calc.tick(position, *row)
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_waiting()
    if counts is not None:
        counts.update(dict(calc.counts, orders_that_entered_in_the_trade_day_and_are_still_resting=len(calc.entered)))
