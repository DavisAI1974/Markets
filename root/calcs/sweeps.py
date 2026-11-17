"""ROOT part 2, calculation `sweeps`: every trade event, and the moments the quote touches or crosses (addition M).

Approved by Greg, 2026-11-16 ("Try them all"; laid out in markets-data `STEP1_STEP2_LAYOUTS.md`, "Additions from
the look at Codex's two pieces", M). How hard a trade hit the book: a trade that fills through more than one price
level is someone paying up to get done.

Three kinds of FACT, each at the tick it becomes known:
- `trade event`: one for EVERY exchange event that holds a trade (not only the ones that go through several
  levels, so nothing is picked in advance), at the tick that carries the exchange's own end-of-event mark: the
  sides of the aggressor as the tape gives them, the size traded (bought, sold, no side), the number of trades,
  of fill messages, of resting orders filled and of price levels filled through, the first and last trade and
  fill price, whether each best price moved and where from and to, and both clocks (the first trade's tick and
  this one).
- `quote touched or crossed`: the first tick at which the best ask is at or below the best bid.
- `quote parted`: the first tick after that at which they are apart again, with how long it lasted, how many
  ticks, and the lowest the gap went.
A touch or cross still standing at the last tick is listed in its own small file. One already standing at the
first tick of the trade day began before the trade day: its facts say so, and its length is counted from the first
tick only, because nothing from before the trade day enters a calculation.

Claude's calls in the build, stated to Greg (his to correct):
- The exchange's own marks define an event. On the four trade days every event with a trade ends on the tick that
  carries the end mark; one that did not would stop the run with its reason.
- When the trades of one event carry more than one side (a handful a trade day), every side is written, in the
  order it came, and the size is split by side. Nothing is called the one aggressor.
- A price level filled through is a distinct price among the event's fill messages.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

READS = ['received_time_ns', 'action', 'side', 'price', 'size', 'order_number', 'exchange_event',
         'ends_exchange_event', 'best_bid', 'best_ask', 'gap', 'best_bid_moved_from', 'best_ask_moved_from']
TRADE, FILL, BUY, SELL = 'T', 'F', 'B', 'A'
EVENT, TOUCHED, PARTED = 'trade event', 'quote touched or crossed', 'quote parted'
KINDS = (EVENT, TOUCHED, PARTED)

COLUMNS = [('sweep_facts_known', 'How many facts about trade events and about the quote touching or crossing '
            'became known at this tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('fact', 'The kind of moment: trade event, quote touched or crossed, quote parted.'),
    ('event_position', 'On trade event: the first tick of the exchange event. A label only.'),
    ('first_trade_position', 'On trade event: the tick of the event\'s first trade. A label only.'),
    ('first_trade_received_time_ns', 'When that first trade was received.'),
    ('since_first_trade_ns', 'From the first trade to this tick.'),
    ('ticks_in_event', 'How many ticks the exchange event holds.'),
    ('aggressor_sides', 'The trade sides the tape gives in this event, in the order they came: B bought, A sold, N '
     'no side.'),
    ('trades', 'How many trade messages the event holds.'),
    ('size_traded', 'The size of those trades.'),
    ('size_bought', 'Of that: the size the tape marks as bought by the aggressor.'),
    ('size_sold', 'Of that: the size the tape marks as sold by the aggressor.'),
    ('size_no_side', 'Of that: the size the tape gives no side for.'),
    ('first_trade_price', 'The price of the first trade.'),
    ('last_trade_price', 'The price of the last trade.'),
    ('fill_messages', 'How many fill messages the event holds.'),
    ('orders_filled', 'How many different resting orders those fill messages name.'),
    ('size_of_fills', 'The size of those fill messages.'),
    ('price_levels_filled', 'How many different prices those fill messages carry.'),
    ('first_fill_price', 'The price of the first fill message.'),
    ('last_fill_price', 'The price of the last fill message.'),
    ('best_bid_moved', 'Yes when a tick of the event moved the best bid.'),
    ('best_ask_moved', 'Yes when a tick of the event moved the best ask.'),
    ('best_bid_before', 'The best bid just before the event.'),
    ('best_bid_after', 'The best bid just after it.'),
    ('best_ask_before', 'The best ask just before the event.'),
    ('best_ask_after', 'The best ask just after it.'),
    ('gap_now', 'The best ask minus the best bid just after this tick.'),
    ('touched_position', 'On quote parted: the tick at which the quote touched or crossed. A label only.'),
    ('lasted_ns', 'On quote parted: from that tick to this one.'),
    ('ticks_lasted', 'On quote parted: how many ticks the quote stayed touching or crossed.'),
    ('lowest_gap', 'On quote parted: the lowest the gap went while it lasted.'),
    ('standing_at_first_tick', 'On quote touched or crossed, and on quote parted: yes when the quote was already '
     'touching or crossed at the first tick of the trade day. It began before the trade day, so how long it lasted '
     'and how many ticks are counted from the first tick only.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'fact', 'aggressor_sides'}
FACT_YES_NO = {'best_bid_moved', 'best_ask_moved', 'standing_at_first_tick'}
OPEN_COLUMNS = ['touched_position', 'ticks_so_far', 'lowest_gap']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, FACT_YES_NO, set()), 'open-at-the-end': (OPEN_COLUMNS, set(), set(), set())}


class Event:
    """One exchange event as it unfolds."""

    def __init__(self, position, bid_before, ask_before):
        self.position, self.ticks = position, 0
        self.bid_before, self.ask_before, self.bid_moved, self.ask_moved = bid_before, ask_before, False, False
        self.sides, self.trades, self.size = '', 0, {BUY: 0, SELL: 0, None: 0}
        self.first_trade = self.first_trade_price = self.last_trade_price = None
        self.fills, self.fill_size, self.orders, self.prices = 0, 0, set(), set()
        self.first_fill_price = self.last_fill_price = None


class Sweeps:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.event = None
        self.touch = None                              # while touching or crossed: [position, received, ticks, lowest,
        self.started = False                           # standing at the first tick]; and whether a tick has come
        self.counts = dict.fromkeys(KINDS, 0)
        self.most_levels = 0

    def _line(self, kind, position, received, gap) -> dict:
        self.counts[kind] += 1
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, fact=kind, gap_now=gap)
        return row

    def tick(self, position, received, action, side, price, size, order, event, ends, best_bid, best_ask, gap,
             bid_from, ask_from) -> tuple:
        facts, e = [], self.event
        if e is None or e.position != event:
            if e is not None and e.trades:
                raise ValueError(f'the exchange event at position {e.position} holds a trade and did not end on a '
                                 f'tick with the end mark: outside the rule of sweeps')
            e = self.event = Event(event, best_bid if bid_from is None else bid_from,
                                   best_ask if ask_from is None else ask_from)
        e.ticks += 1
        e.bid_moved, e.ask_moved = e.bid_moved or bid_from is not None, e.ask_moved or ask_from is not None
        if action == TRADE:
            if not e.trades:
                e.first_trade, e.first_trade_price = (position, received), price
            e.trades, e.last_trade_price = e.trades + 1, price
            e.size[side if side in (BUY, SELL) else None] += size
            if side not in e.sides:
                e.sides += side
        elif action == FILL:
            if not e.fills:
                e.first_fill_price = price
            e.fills, e.fill_size, e.last_fill_price = e.fills + 1, e.fill_size + size, price
            e.orders.add(order)
            e.prices.add(price)
        if ends:
            if e.trades:
                row = self._line(EVENT, position, received, gap)
                row.update(event_position=e.position, first_trade_position=e.first_trade[0],
                           first_trade_received_time_ns=e.first_trade[1], since_first_trade_ns=received - e.first_trade[1],
                           ticks_in_event=e.ticks, aggressor_sides=e.sides, trades=e.trades,
                           size_traded=sum(e.size.values()), size_bought=e.size[BUY], size_sold=e.size[SELL],
                           size_no_side=e.size[None], first_trade_price=e.first_trade_price,
                           last_trade_price=e.last_trade_price, fill_messages=e.fills, orders_filled=len(e.orders),
                           size_of_fills=e.fill_size, price_levels_filled=len(e.prices),
                           first_fill_price=e.first_fill_price, last_fill_price=e.last_fill_price,
                           best_bid_moved=e.bid_moved, best_ask_moved=e.ask_moved, best_bid_before=e.bid_before,
                           best_bid_after=best_bid, best_ask_before=e.ask_before, best_ask_after=best_ask)
                facts.append(tuple(row[name] for name in FACT_NAMES))
                self.most_levels = max(self.most_levels, len(e.prices))
            self.event = None
        if gap <= 0:
            if self.touch is None:
                self.touch = [position, received, 1, gap, not self.started]
                row = self._line(TOUCHED, position, received, gap)
                row.update(standing_at_first_tick=not self.started)
                facts.append(tuple(row[name] for name in FACT_NAMES))
            else:
                self.touch[2], self.touch[3] = self.touch[2] + 1, min(self.touch[3], gap)
        elif self.touch is not None:
            row = self._line(PARTED, position, received, gap)
            row.update(touched_position=self.touch[0], lasted_ns=received - self.touch[1], ticks_lasted=self.touch[2],
                       lowest_gap=self.touch[3], standing_at_first_tick=self.touch[-1])
            facts.append(tuple(row[name] for name in FACT_NAMES))
            self.touch = None
        self.started = True
        return (len(facts),), facts

    def still_touching(self) -> list:
        return [] if self.touch is None else [(self.touch[0], self.touch[2], self.touch[3])]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = Sweeps()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        values, new = calc.tick(position, *row)
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_touching()
    if counts is not None:
        counts.update(dict(facts=calc.counts, most_price_levels_filled_in_one_event=calc.most_levels,
                           touching_or_crossed_at_the_last_tick=len(calc.still_touching())))
