"""ROOT part 2, calculation `leg_peaks`: the trade legs beside the peaks (Step 2, piece I, the print legs).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece I, 2026-11-16; his go
2026-11-17: "Write the 3 calcs and run them on the pods"). The trade leg is the earlier work's own (Markets
`0408df44` `continue_trade_chronology.py`): the trade prints of the trade day in tape order; prints at one price in
a row are one stretch; a leg is a run of steps from stretch to stretch that all go the same way, and the stretch
where the direction turns belongs to both legs. That rule is not changed. Here it is followed forward, print by
print, from the first print of the trade day (6 pm Eastern on all four trade days), so that every moment of a leg
is written at the tick it could first be known:
- leg started: the first print that steps away from the stretch the leg starts on. The leg's first trade is the
  first trade of that stretch, which is earlier; both ticks are written;
- new furthest price: each later print that steps the same way;
- leg ended: the first print that steps the other way. The leg ends on the stretch before it, and the next leg
  starts on that same stretch, at this same tick.
Each of those lines carries the peaks in play at its tick: the buy peak and the sell peak most lately known (the
tick of its high, the time since it, where its story stands) and the rise under way, exactly as `quote_peaks`
writes them for the quote's runs. The other direction needs no second table: on the tick of any fact about a peak,
the leg in progress is on that row, in this calculation's columns.

Claude's calls in the build, stated to Greg (his to correct):
- A moment of a leg is known at the tick of the print that shows it. The earlier record's "available" time (the
  end of the print's exchange event) is not used to place it; the row carries the end-of-event mark.
- Legs are counted from the first print of the trade day. On trade days Oct 2 and Oct 17 the earlier record counts
  from 8 pm; the check proves every earlier leg comes out again and the receipt gives the difference in the count.
- Up and down are read off the prices. No leg is named a kind of leg (his rule on labels): the eight trade types
  are not assigned.
- No minimum length: a leg of one step is kept, as every peak is kept.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root.calcs import in_play

READS = list(in_play.READS)
RECEIVED, ACTION, PRICE = (READS.index(name) for name in ('received_time_ns', 'action', 'price'))
TRADE = 'T'
UP, DOWN = 'up', 'down'
STARTED, FURTHER, ENDED = 'leg started', 'new furthest price', 'leg ended'
KINDS = (STARTED, FURTHER, ENDED)

COLUMNS = [
    ('leg_number', 'The trade leg in progress at this tick, counted from the first print of the trade day (a label '
     'only). Empty until the first print that steps away from the first price.'),
    ('leg_direction', 'Which way that leg goes: up or down.'),
    ('leg_first_trade_position', 'The first trade of that leg: its position on the tape. A label only.'),
    ('leg_start_price', 'The price that leg started from (the tape\'s own price units).'),
    ('leg_furthest_price', 'The furthest price that leg has printed so far.'),
    ('leg_steps', 'How many steps of price that leg has made so far.'),
    ('leg_facts_known', 'How many facts about trade legs became known at this tick (they are in the facts table).'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = {'leg_direction'}, set(), set()
NO_LEG = tuple(None for _ in COLUMNS[:-1])

LEG_FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('fact', 'The kind of moment: leg started, new furthest price, leg ended.'),
    ('leg_number', 'Which leg the fact is about, counted from the first print of the trade day. A label only.'),
    ('direction', 'Which way the leg goes: up or down.'),
    ('leg_first_trade_position', 'The first trade of the leg: its position on the tape. A label only.'),
    ('leg_first_trade_received_time_ns', 'When that first trade was received.'),
    ('leg_start_price', 'The price the leg started from.'),
    ('price', 'On leg started and new furthest price: the price of this print, the furthest the leg has reached. '
     'On leg ended: the price the leg ended at.'),
    ('steps', 'How many steps of price the leg has made, this print included. On leg ended: how many in all.'),
    ('price_change', 'The price in the column before minus the price the leg started from (below zero for a leg '
     'down).'),
    ('since_first_trade_ns', 'From the leg\'s first trade to this tick.'),
    ('leg_last_trade_position', 'On leg ended: the last trade of the leg (the last print at the price it ended '
     'at). A label only.'),
    ('step_back', 'On leg ended: the price of this print minus the price the leg ended at.'),
]
FACT_COLUMNS = LEG_FACT_COLUMNS + in_play.PEAK_COLUMNS
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
LEG_FACT_NAMES = [name for name, _ in LEG_FACT_COLUMNS]
OPEN_COLUMNS = ['leg_number', 'direction', 'leg_first_trade_position', 'leg_start_price', 'furthest_price', 'steps']
TABLES = {'facts': (FACT_NAMES, {'fact', 'direction'} | in_play.PEAK_TEXT, set(), set()),
          'open-at-the-end': (OPEN_COLUMNS, {'direction'}, set(), set())}


class Leg:
    """One trade leg, as it stands."""
    __slots__ = ('number', 'direction', 'first', 'first_at', 'start_price', 'price', 'steps')

    def __init__(self, number, direction, first, first_at, start_price, price):
        self.number, self.direction, self.first, self.first_at = number, direction, first, first_at
        self.start_price, self.price, self.steps = start_price, price, 1


class Legs:
    """The trade legs of one trade day, forward only. `trade()` takes the next print and gives the facts about
    legs that became known at it, each in LEG_FACT_NAMES order."""

    def __init__(self):
        self.stretch_price = None                      # the price of the stretch in progress,
        self.stretch_first = None                      # its first trade: (position, received),
        self.last_trade = None                         # and the print before this one: its position
        self.leg = None
        self.counts = dict.fromkeys(('trades', 'stretches', 'legs') + KINDS, 0)

    def _fact(self, leg: Leg, kind, position, received, price, **more) -> tuple:
        self.counts[kind] += 1
        row = dict.fromkeys(LEG_FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, fact=kind, leg_number=leg.number,
                   direction=leg.direction, leg_first_trade_position=leg.first,
                   leg_first_trade_received_time_ns=leg.first_at, leg_start_price=leg.start_price, price=price,
                   steps=leg.steps, price_change=price - leg.start_price, since_first_trade_ns=received - leg.first_at,
                   **more)
        return tuple(row[name] for name in LEG_FACT_NAMES)

    def trade(self, position, received, price) -> list:
        self.counts['trades'] += 1
        facts = []
        if self.stretch_price is None:
            self.counts['stretches'] += 1
            self.stretch_price, self.stretch_first = price, (position, received)
        elif price != self.stretch_price:
            self.counts['stretches'] += 1
            direction, leg = UP if price > self.stretch_price else DOWN, self.leg
            if leg is not None and leg.direction == direction:
                leg.price, leg.steps = price, leg.steps + 1
                facts.append(self._fact(leg, FURTHER, position, received, price))
            else:
                if leg is not None:
                    facts.append(self._fact(leg, ENDED, position, received, leg.price,
                                            leg_last_trade_position=self.last_trade, step_back=price - leg.price))
                self.leg = leg = Leg(self.counts['legs'], direction, *self.stretch_first, self.stretch_price, price)
                self.counts['legs'] += 1
                facts.append(self._fact(leg, STARTED, position, received, price))
            self.stretch_price, self.stretch_first = price, (position, received)
        self.last_trade = position
        return facts

    def now(self) -> tuple:
        """The leg in progress, in the order of COLUMNS (without the count of facts)."""
        leg = self.leg
        return NO_LEG if leg is None else (leg.number, leg.direction, leg.first, leg.start_price, leg.price,
                                           leg.steps)

    def still_going(self) -> list:
        leg = self.leg
        return [] if leg is None else [(leg.number, leg.direction, leg.first, leg.start_price, leg.price, leg.steps)]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    state, legs = in_play.InPlay(), Legs()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        state.tick(position, *row)
        new = legs.trade(position, row[RECEIVED], row[PRICE]) if row[ACTION] == TRADE else []
        if new:
            now = state.peaks_now(row[RECEIVED])
            facts.extend(fact + now for fact in new)
        yield position, legs.now() + (len(new),)
    if tables is not None:
        tables['open-at-the-end'] = legs.still_going()
    if counts is not None:
        counts.update(dict(legs.counts, legs_still_going_at_the_last_tick=len(legs.still_going())))
