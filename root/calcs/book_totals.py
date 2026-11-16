"""ROOT part 2, calculation `book_totals`: running totals of what happened in the resting orders (Step 2, piece C).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece C, 2026-11-16: "Include
all of your pieces"). On every tick of a trade day, for the bid side and for the ask side, the size so far in the
trade day that was
- ADDED: a new order, an order made larger, or size put back on an order as it traded;
- PULLED: a cancel, or an order made smaller;
- FILLED: traded away, by the tape's own fill messages;
- MOVED: carried by an order from one price to another (nothing left or joined the side).
Each is kept for the whole side and for what happened at the best price. With running totals on every row, the
amount between any two ticks is one subtraction, so no stretch of time is picked in advance. They are sums of single
messages, each of which stays on its own row; they are not averages. They start at zero at the first tick of the
trade day (the book itself carries over; only the counting starts fresh).

The one rule, on the row where a tick changes an order (b its size before, a its size after, f the size the fill
messages of the same exchange event named for it; b is nothing for an order that has just joined):
    filled += f;   left = b - f;   a above left: added += a - left;   a below left: pulled += left - a;
    when the order changed price: moved += the smaller of a and what was left.
With no fill this is: joined = added; cancelled or made smaller = pulled; made larger = added. A fill is counted on
the row where the book shows it (the order's own cancel or modify), never on the fill message's row, so that on
every row the side's total size equals its size at the open plus added minus pulled minus filled.

Claude's calls in the build, stated to Greg (his to correct):
- A fill the book shows no change for (the order is filled and the same message puts the size back: its next row is
  "stayed", "size raised" or "price changed") counts as FILLED and as ADDED both. The size put back is also kept on
  its own (`refilled`), so the totals without it are one subtraction.
- A fill message the tape gives no side for names a resting order all the same. It is counted on that order's side,
  and also on its own (`filled_no_side`).
- "At the best price" is read from the book at that tick. For an order already resting, at the price it rests at:
  that price was the best just before the tick (filled, pulled, made larger, refilled, moved from). For an order
  that joins, or arrives at a new price: that price is the best just after the tick (added, moved to). Moved
  therefore has two best-price totals.
Anything outside this rule table (a clear, a message that was not applied, a fill whose order shows no row in its
exchange event) stops the run with its reason; none occurs on the four trade days.

The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root import rows as R

READS = ['action', 'side', 'size', 'order_number', 'exchange_event', 'what_happened', 'order_size_before',
         'order_size_after', 'touched_price', 'left_price', 'best_bid', 'best_ask', 'best_bid_moved_from',
         'best_ask_moved_from']
FILL, BID, ASK = 'F', 'B', 'A'                         # the tape's codes as the rows store them
SIDES = {BID: 'bid', ASK: 'ask'}
CHANGES = (R.JOINED, R.STAYED, R.SHRANK, R.SHRANK_BY_FILL, R.LOST_PLACE_PRICE, R.LOST_PLACE_SIZE, R.LEFT_BY_CANCEL,
           R.LEFT_BY_FILL)                             # what a tick can do to an order

FIGURES = [
    ('added', 'Size added on the {side} side so far in the trade day: new orders, orders made larger, and size put '
     'back on an order as it traded.'),
    ('pulled', 'Size pulled from the {side} side so far: cancels, and orders made smaller.'),
    ('filled', 'Size of resting {side} orders filled (traded away) so far, by the tape\'s fill messages, counted on '
     'the row where the book shows it.'),
    ('moved', 'Size carried by {side} orders from one price to another so far. In neither added nor pulled.'),
    ('added_at_best', 'Of the size added: the part at the best {side} price (for a new order, best just after its '
     'tick; for an order already resting there, best just before).'),
    ('pulled_at_best', 'Of the size pulled: the part whose price was the best {side} just before its tick.'),
    ('filled_at_best', 'Of the size filled: the part whose price was the best {side} just before its tick.'),
    ('moved_from_best', 'Of the size moved: the part that left the best {side} price (best just before its tick).'),
    ('moved_to_best', 'Of the size moved: the part that joined the best {side} price (best just after its tick).'),
    ('refilled', 'Of the size added: size put back on an order in the same exchange event that filled it, so the '
     'book showed less change than the fill, or none.'),
    ('refilled_at_best', 'Of the size refilled: the part at the best {side} price.'),
    ('filled_no_side', 'Of the size filled: the part whose fill message the tape gives no side for.'),
]
KEYS = [key for key, _ in FIGURES]
COLUMNS = [(f'{name}_{key}', what.format(side=name)) for name in SIDES.values() for key, what in FIGURES]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
TABLES = {}                                            # this calculation keeps no table beside the rows


class BookTotals:
    """One trade day, forward only. `tick()` takes the next stored row and gives that tick's values in NAMES order."""

    def __init__(self):
        self.totals = {side: dict.fromkeys(KEYS, 0) for side in SIDES}
        self.event = None
        self.waiting = {}                              # fills of this exchange event not yet shown by the book:
        self.counts = {}                               # order -> [size, size the tape gives no side for]

    def _count(self, what: str, by: int = 1):
        self.counts[what] = self.counts.get(what, 0) + by

    def tick(self, position, action, side, size, order, event, what, before, after, touched, left, best_bid,
             best_ask, bid_from, ask_from) -> tuple:
        if event != self.event:
            if self.waiting:
                raise ValueError(f'an exchange event ended before position {position} with a fill message whose '
                                 f'order showed no row in it: outside the rule of book_totals')
            self.event = event
        if action == FILL:
            entry = self.waiting.setdefault(order, [0, 0])
            entry[0] += size
            if side not in SIDES:
                entry[1] += size
            self._count('fill messages')
            self._count('size of the fill messages', size)
        elif what in CHANGES:
            if side not in SIDES:
                raise ValueError(f'position {position}: an order changed with no side on the row')
            total = self.totals[side]
            best_after = best_bid if side == BID else best_ask
            came_from = bid_from if side == BID else ask_from
            best_before = best_after if came_from is None else came_from
            price_changed = what == R.LOST_PLACE_PRICE
            price_before = left if price_changed else touched
            leaves_best = price_before == best_before
            joins_best = touched == best_after if price_changed or what == R.JOINED else leaves_best
            fill, no_side = self.waiting.pop(order, (0, 0))
            had = 0 if what == R.JOINED else before    # an order that has just joined had no size before
            if fill:
                total['filled'] += fill
                total['filled_no_side'] += no_side
                if leaves_best:
                    total['filled_at_best'] += fill
            elif what in (R.SHRANK_BY_FILL, R.LEFT_BY_FILL):
                raise ValueError(f'position {position}: "{what}" with no fill message before it in its exchange event')
            remains = had - fill
            if after > remains:
                total['added'] += after - remains
                if joins_best:
                    total['added_at_best'] += after - remains
                if fill:
                    back = min(after - remains, fill)
                    total['refilled'] += back
                    if joins_best:
                        total['refilled_at_best'] += back
                    self._count(f'rows where a fill was put back: {what}')
            elif after < remains:
                total['pulled'] += remains - after
                if leaves_best:
                    total['pulled_at_best'] += remains - after
                if fill:
                    self._count(f'rows where more left than was filled: {what}')
            if price_changed:
                carried = min(max(remains, 0), after)
                total['moved'] += carried
                if leaves_best:
                    total['moved_from_best'] += carried
                if joins_best:
                    total['moved_to_best'] += carried
                if after != before:
                    self._count('price changes that also changed size')
        elif what != R.NO_CHANGE:
            raise ValueError(f'position {position}: "{what}" is outside the rule of book_totals')
        return tuple(self.totals[side][key] for side in SIDES for key in KEYS)

    def result(self) -> dict:
        return dict(self.counts, fills_waiting_for_their_row_at_the_last_tick=len(self.waiting),
                    size_of_fills_waiting_at_the_last_tick=sum(size for size, _ in self.waiting.values()),
                    totals_at_the_last_tick={f'{SIDES[side]}_{key}': self.totals[side][key]
                                             for side in SIDES for key in KEYS})


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = BookTotals()
    for position, row in ticks:
        yield position, calc.tick(position, *row)
    if counts is not None:
        counts.update(calc.result())
