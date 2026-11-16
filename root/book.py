"""ROOT `book`: one order book for the week, every order with its place in line and its times.

Specification: SPEC-root.md (approved by Greg, 2026-11-16), part `book`. The book is seated at the exchange's Sunday
start-up and carried straight through the week; it is never restarted and no vendor snapshot is ever applied to it.

The rule that applies each message is the exchange's own priority rule, written fresh here (assumption 3):
- add: the order joins the back of the line at its price;
- cancel: the order's size is reduced in place by the cancelled amount; at zero it leaves;
- modify: a change of price sends the order to the back of the line at the new price; a rise in size sends it to
  the back of its own line; a fall in size keeps its place;
- trade, fill and the exchange's "none" messages change nothing by themselves. On the held tape every fill is
  followed, inside the same exchange event, by the cancel (fully filled) or the smaller-size modify (partly filled)
  of that order, so "by fill" is read from the tape, not assumed;
- clear: the book is emptied (the exchange's Sunday start-up only).
Its test is the vendor's restatement at the opening of every later raw file (criterion 3), not any earlier program.
A message that cannot be applied is not applied; it is reported with its reason on the tick where it happens.
"""
from __future__ import annotations

import bisect
import collections

from root import tape

ADD, CANCEL, MODIFY, TRADE, FILL, NONE = b'A', b'C', b'M', b'T', b'F', b'N'
BID, ASK = b'B', b'A'


class Order:
    __slots__ = ('id', 'side', 'price', 'size', 'entered_event', 'entered_recv', 'entered_pos', 'placed_event',
                 'placed_recv', 'placed_pos', 'previous_pos', 'steps', 'carried_over_weekend', 'entered_written')


class Line:
    """The orders resting at one price, front first, with the line's running total size."""
    __slots__ = ('orders', 'size')

    def __init__(self):
        self.orders, self.size = {}, 0


class Side:
    """One side of the book: its lines by price, the prices kept sorted, and the running whole-side figures."""
    __slots__ = ('lines', 'prices', 'size', 'orders')

    def __init__(self):
        self.lines, self.prices, self.size, self.orders = {}, [], 0, 0


class Book:
    def __init__(self):
        self.orders = {}
        self.sides = {BID: Side(), ASK: Side()}
        self.last_sequence = None
        self.filled_in_event = {}          # order id -> size filled so far inside the current exchange event
        self.irregular = collections.Counter()
        self.last_bit = tape.flag_bits()['F_LAST']

    # ---- places in line
    def _join(self, order: Order):
        side = self.sides[order.side]
        line = side.lines.get(order.price)
        if line is None:
            line = side.lines[order.price] = Line()
            bisect.insort(side.prices, order.price)
        line.orders[order.id] = order
        line.size += order.size
        side.size += order.size
        side.orders += 1

    def _leave(self, order: Order):
        side = self.sides[order.side]
        line = side.lines[order.price]
        del line.orders[order.id]
        line.size -= order.size
        side.size -= order.size
        side.orders -= 1
        if not line.orders:
            del side.lines[order.price]
            side.prices.pop(bisect.bisect_left(side.prices, order.price))

    def _resize(self, order: Order, size: int):
        side = self.sides[order.side]
        side.lines[order.price].size += size - order.size
        side.size += size - order.size
        order.size = size

    # ---- one tick
    def apply(self, action, side, price, size, order_id, flags, ts_event, ts_recv, sequence, pos,
              carried: bool = False, written: bool = True) -> list:
        """Apply one tick. Returns the irregular notes of this tick (empty when there are none)."""
        notes = []
        if self.last_sequence is not None and sequence < self.last_sequence:
            notes.append('the exchange sequence number went backwards')
        self.last_sequence = sequence
        if action == ADD:
            if order_id in self.orders:
                notes.append('not applied: an add for an order already in the book')
            elif side not in self.sides:
                notes.append('not applied: an add with no side')
            else:
                o = Order()
                o.id, o.side, o.price, o.size = order_id, side, price, size
                o.entered_event = o.placed_event = ts_event
                o.entered_recv = o.placed_recv = ts_recv
                o.entered_pos = o.placed_pos = o.previous_pos = pos
                o.steps, o.carried_over_weekend, o.entered_written = 1, carried, written
                self.orders[order_id] = o
                self._join(o)
        elif action == CANCEL:
            o = self.orders.get(order_id)
            if o is None:
                notes.append('not applied: a cancel for an order the book does not know')
            else:
                if size > o.size:
                    notes.append('a cancel for more than was resting')
                    size = o.size
                o.steps += 1
                o.previous_pos = pos
                if size == o.size:
                    self._leave(o)
                    del self.orders[order_id]
                else:
                    self._resize(o, o.size - size)
        elif action == MODIFY:
            o = self.orders.get(order_id)
            if o is None:
                notes.append('not applied: a modify for an order the book does not know')
            elif side != o.side:
                notes.append('not applied: a modify that changes the side of an order')
            else:
                o.steps += 1
                o.previous_pos = pos
                if price != o.price or size > o.size:
                    self._leave(o)
                    o.price, o.size = price, size
                    o.placed_event, o.placed_recv, o.placed_pos = ts_event, ts_recv, pos
                    self._join(o)
                elif size != o.size:
                    self._resize(o, size)
        elif action == FILL:
            self.filled_in_event[order_id] = self.filled_in_event.get(order_id, 0) + size
        elif action == tape.CLEAR:
            self.orders = {}
            self.sides = {BID: Side(), ASK: Side()}
        elif action not in (TRADE, NONE):
            notes.append(f'not applied: an action the book has no rule for ({action!r})')
        if flags & self.last_bit:
            self.filled_in_event = {}
        for n in notes:
            self.irregular[n] += 1
        return notes

    # ---- reading the book
    def best(self, side):
        prices = self.sides[side].prices
        if not prices:
            return None
        return prices[-1] if side == BID else prices[0]

    def figures(self) -> dict:
        """The running whole-book figures."""
        return {s.decode(): dict(size=self.sides[s].size, orders=self.sides[s].orders, levels=len(self.sides[s].lines))
                for s in (BID, ASK)}

    def fresh_count(self) -> dict:
        """The same figures counted again from every order (criterion 4), and every line's total checked."""
        out = {}
        for s in (BID, ASK):
            side = self.sides[s]
            mine = [o for o in self.orders.values() if o.side == s]
            for price, line in side.lines.items():
                if line.size != sum(o.size for o in line.orders.values()) or not line.orders:
                    raise AssertionError(f'the line at {price} does not add up')
            if side.prices != sorted(side.lines):
                raise AssertionError('the sorted prices differ from the lines held')
            out[s.decode()] = dict(size=sum(o.size for o in mine), orders=len(mine),
                                   levels=len({o.price for o in mine}))
        return out


def compare_with_restatement(book: Book, records) -> dict:
    """Criterion 3: our carried book against the vendor's restatement at the opening of a raw file. The same orders,
    sides, prices and sizes; the same order in every line; and the restatement's time for each order equal to the
    exchange time at which we say that order last took its place. The restatement is never applied."""
    c = tape.columns(records)
    theirs, lines = {}, collections.defaultdict(list)
    for a, s, p, z, oid, t in zip(c['action'], c['side'], c['price'], c['size'], c['order_id'], c['ts_event']):
        if a == ADD:
            theirs[oid] = (s, p, z, t)
            lines[(s, p)].append(oid)
    ours = {oid: (o.side, o.price, o.size, o.placed_event) for oid, o in book.orders.items()}
    our_lines = {(s, p): list(line.orders) for s in (BID, ASK) for p, line in book.sides[s].lines.items()}
    differing = [oid for oid in set(ours) & set(theirs) if ours[oid][:3] != theirs[oid][:3]]
    times = [oid for oid in set(ours) & set(theirs) if ours[oid][3] != theirs[oid][3]]
    order = [k for k in set(lines) & set(our_lines) if lines[k] != our_lines[k]]
    result = dict(orders_in_restatement=len(theirs), orders_in_our_book=len(ours),
                  only_in_restatement=len(set(theirs) - set(ours)), only_in_our_book=len(set(ours) - set(theirs)),
                  side_price_or_size_differs=len(differing), place_time_differs=len(times),
                  lines_in_a_different_order=len(order))
    result['equal'] = not (result['only_in_restatement'] or result['only_in_our_book'] or differing or times or order)
    return result


def carry_week(week, written=None, check_every_trade: bool = False) -> tuple:
    """Walk a week once: every tick applied to one book, the restatement at each later file compared first. Returns
    (book, the comparison per later file, the whole-book check at each file boundary). `written(ts_event)` says
    whether a tick is a written row (for the mark on orders that entered before the written record). With
    `check_every_trade` the running figures are counted afresh at every trade too (criterion 4) and the number of
    trades checked is added to the last boundary entry; a difference stops the walk."""
    book, compared, boundaries, pos, trades_checked = Book(), [], [], 0, 0
    snap = tape.flag_bits()['F_SNAPSHOT']
    for k, f in enumerate(week):
        if k:
            r = compare_with_restatement(book, f.records[:f.vendor_snapshot])
            r['file'] = f.name
            compared.append(r)
            boundaries.append(dict(file=f.name, running=book.figures(), fresh=book.fresh_count()))
        c = tape.columns(f.records[f.vendor_snapshot:])
        for a, s, p, z, oid, fl, te, tr, sq in zip(c['action'], c['side'], c['price'], c['size'], c['order_id'],
                                                   c['flags'], c['ts_event'], c['ts_recv'], c['sequence']):
            book.apply(a, s, p, z, oid, fl, te, tr, sq, pos, carried=bool(fl & snap),
                       written=True if written is None else written(te))
            if check_every_trade and a == TRADE:
                if book.figures() != book.fresh_count():
                    raise AssertionError(f'{f.name}: the running figures differ from a fresh count at tick {pos}')
                trades_checked += 1
            pos += 1
    boundaries.append(dict(file='end of the record', running=book.figures(), fresh=book.fresh_count(),
                           ticks=pos, trades_checked=trades_checked))
    return book, compared, boundaries


def check_book(folder, trade_day, check_every_trade: bool = True) -> dict:
    """The check-book record for one trade day's week: criterion 3 at every later file, criterion 4 at every file
    boundary and at every trade, and every irregular message counted by its reason."""
    import time
    started = time.monotonic()
    week = tape.read_week(folder, trade_day)
    book, compared, boundaries = carry_week(week, check_every_trade=check_every_trade)
    return dict(what='ROOT book: check-book (the carried book against the vendor restatement; the book adds up)',
                specification='SPEC-root.md (approved 2026-11-16), part book; criteria 3 and 4',
                trade_day=trade_day.isoformat(), files=[f.name for f in week],
                book_equals_restatement=compared, all_equal=all(c['equal'] for c in compared),
                whole_book_figures=boundaries, all_add_up=all(b['running'] == b['fresh'] for b in boundaries),
                irregular=dict(book.irregular),
                irregular_note='the sequence number goes backwards only inside the Sunday start-up block, where the '
                               're-listed orders are grouped by price and not by sequence number',
                orders_resting_at_the_end=len(book.orders), seconds=round(time.monotonic() - started, 1))
