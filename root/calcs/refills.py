"""ROOT part 2, calculation `refills`: orders that are traded against and have size put back (addition L).

Approved by Greg, 2026-11-16 ("Try them all"; laid out in markets-data `STEP1_STEP2_LAYOUTS.md`, "Additions from
the look at Codex's two pieces", L). A resting order is filled and shows the same size, or more, straight after:
it marks a price where someone is taking trades and reloading.

One FACT at the tick of the order's own row in the exchange event that filled it, whenever that row shows size put
back (its size after is more than its size before less the fill), and also whenever a filled order changes price
in that row. The fact names the order (a label only) and carries the row's own words for what happened (stayed,
size raised, price changed, shrank by fill, left by fill), the size the fill took, the sizes before and after, the
size put back, whether the order is the same size or larger than before (the layout's "refill"), how many times
size has been put back on this order so far in the trade day, the total filled on it so far, and when it first
entered. The size put back is the figure `book_totals` calls `refilled`: what the row shows above what the fill
left, and never more than the fill took (an order raised beyond its old size at the same tick added the rest; both
sizes are on the line). So the facts of a side add up to that side's `refilled` total exactly.

Claude's calls in the build, stated to Greg (his to correct):
- Every row with size put back gets a fact, also where the order ends smaller than it began or leaves (a fill
  larger than the size shown). Nothing is picked: `same_size_or_larger` says which ones the layout calls a refill.
- A fill followed by a change of price is its own kind of moment: the fact's words say "price changed".
- "So far" counts start at the first tick of the trade day.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root import rows as R

READS = ['received_time_ns', 'action', 'side', 'size', 'order_number', 'exchange_event', 'what_happened',
         'order_size_before', 'order_size_after', 'touched_price', 'left_price', 'levels_from_best',
         'first_entered_exchange_time_ns', 'first_entered_received_time_ns', 'entered_before_written_record']
FILL = 'F'
SIDES = {'B': 'bid', 'A': 'ask'}
CHANGES = (R.STAYED, R.SHRANK, R.SHRANK_BY_FILL, R.LOST_PLACE_PRICE, R.LOST_PLACE_SIZE, R.LEFT_BY_CANCEL,
           R.LEFT_BY_FILL)                             # what a tick can do to an order already resting

COLUMNS = [('refill_facts_known', 'How many facts about filled orders with size put back became known at this '
            'tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('order_number', 'The order the fact is about. A label only.'),
    ('fact', 'What the tick did to the order, in the row\'s own words: stayed, size raised, price changed, shrank '
     'by fill, left by fill.'),
    ('side', 'The side the order rests on: bid or ask.'),
    ('price', 'The price the order rested at when it was filled.'),
    ('price_after', 'The price it rests at after this tick (different only when it changed price).'),
    ('levels_from_best', 'As on the row: how many resting price levels on that side were better than the price '
     'this tick acted at, just before it.'),
    ('size_filled', 'The size the fill messages of this exchange event took from the order.'),
    ('size_before', 'The order\'s size just before this tick.'),
    ('size_after', 'The order\'s size just after this tick.'),
    ('size_put_back', 'The size put back: its size after, less what was left of it after the fill, and never more '
     'than the fill took. The same figure as `refilled` in the book totals.'),
    ('same_size_or_larger', 'Yes when the order is the same size as before the fill, or larger.'),
    ('times_put_back_so_far', 'How many times size has been put back on this order so far in the trade day, this '
     'one included.'),
    ('size_filled_so_far', 'The total size filled on this order so far in the trade day, this fill included.'),
    ('first_entered_exchange_time_ns', 'When the order first entered, exchange time.'),
    ('first_entered_received_time_ns', 'When the order first entered, received time.'),
    ('entered_before_written_record', 'Yes when the order entered during ticks that are not written out.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
TABLES = {'facts': (FACT_NAMES, {'fact', 'side'}, {'same_size_or_larger', 'entered_before_written_record'}, set())}


class Refills:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.event, self.waiting = None, {}            # fills of this exchange event not yet shown by the book
        self.filled, self.times = {}, {}               # per order, so far in the trade day
        self.counts = {}

    def tick(self, position, received, action, side, size, order, event, what, before, after, touched, left,
             levels, entered_exchange, entered_received, entered_before) -> tuple:
        if event != self.event:
            if self.waiting:
                raise ValueError(f'an exchange event ended before position {position} with a fill message whose '
                                 f'order showed no row in it: outside the rule of refills')
            self.event = event
        if action == FILL:
            self.waiting[order] = self.waiting.get(order, 0) + size
            return (0,), []
        fill = self.waiting.pop(order, 0) if what in CHANGES else 0
        if not fill:
            return (0,), []
        self.filled[order] = self.filled.get(order, 0) + fill
        back = after - (before - fill)
        if back <= 0 and what != R.LOST_PLACE_PRICE:
            return (0,), []
        if back > 0:
            self.times[order] = self.times.get(order, 0) + 1
        self.counts[what] = self.counts.get(what, 0) + 1
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, order_number=order, fact=what,
                   side=SIDES[side], price=left if what == R.LOST_PLACE_PRICE else touched, price_after=touched,
                   levels_from_best=levels, size_filled=fill, size_before=before, size_after=after,
                   size_put_back=min(max(back, 0), fill), same_size_or_larger=after >= before,
                   times_put_back_so_far=self.times.get(order, 0), size_filled_so_far=self.filled[order],
                   first_entered_exchange_time_ns=entered_exchange, first_entered_received_time_ns=entered_received,
                   entered_before_written_record=entered_before)
        return (1,), [tuple(row[name] for name in FACT_NAMES)]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = Refills()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        values, new = calc.tick(position, *row)
        facts.extend(new)
        yield position, values
    if counts is not None:
        counts.update(dict(facts_by_what_happened=calc.counts, orders_with_size_put_back=len(calc.times),
                           most_times_on_one_order=max(calc.times.values(), default=0),
                           fills_waiting_for_their_row_at_the_last_tick=len(calc.waiting)))
