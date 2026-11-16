"""ROOT `rows`: the one pass. One row per tick, one column per field, sections A to G of SPEC-root.md.

Specification: SPEC-root.md (approved by Greg, 2026-11-16), part `rows`. The tape is walked once from the week's
Sunday start-up; one book is carried for the whole week. Every tick is applied to the book. For a written tick its
row is made in that same step from what the tape and the book say at that tick; nothing from a later tick is used.
Section G (the 13 outside data points) is pinned in that same step by `root.pin`, from the row's own received time and
trade-day label.
Warm-up and shelved ticks only move the book: no row, no figure, nothing kept from them but the book itself.

Columns are fields; rows are ticks (Greg). A field that does not apply to a tick is EMPTY on that row (None): never
0 and never blank text. A zero appears only where the tape or the book says zero (an order's size after it left; how
long an order that has just joined has rested). Greg, 2026-11-16: "empty cells are not included in calcs. That would
artificially water down the output." So a calculation skips an empty cell and never counts it as zero.
Prices are the tape's own integers (billionths of a dollar); times are UTC nanoseconds; order numbers, positions and
clock readings are labels, never values in a formula.
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt

from root import pin, tape
from root.book import ADD, ASK, BID, CANCEL, FILL, MODIFY, Book, compare_with_restatement
from root.calendar import (HALT_EASTERN, OPEN_EASTERN, SETTLE_FROM_EASTERN, SETTLE_TO_EASTERN, STARTUP, STRETCH,
                           TRADE_DAY, eastern, to_ns, trade_day_bounds, week_sunday)

# What happened to the touched order, in the words of the specification (section C).
JOINED = 'joined'
STAYED = 'stayed'
SHRANK = 'shrank'
SHRANK_BY_FILL = 'shrank by fill'
LOST_PLACE_PRICE = 'lost its place: price changed'
LOST_PLACE_SIZE = 'lost its place: size raised'
LEFT_BY_CANCEL = 'left by cancel'
LEFT_BY_FILL = 'left by fill'
NO_CHANGE = 'no change'
CLEARED = 'book cleared'
NOT_APPLIED = 'not applied'
NO_ORDERS = 'no orders'       # the touched line when this tick emptied it: a value in words, never blank text

COLUMNS = [
    # (section, column, what it is)
    ('A. The native tape', 'exchange_time_ns', 'When the exchange says it happened (UTC nanoseconds).'),
    ('A. The native tape', 'received_time_ns', 'When the message reached the data vendor at the exchange: the first '
     'moment it could be known.'),
    ('A. The native tape', 'action', 'The message as the tape writes it: A add, C cancel, M modify, T trade, F fill, '
     'R clear, N none.'),
    ('A. The native tape', 'side', 'As the tape writes it: B bid, A ask, N none. On a trade row, the trade side '
     'exactly as the tape gives it.'),
    ('A. The native tape', 'price', 'The price on the message, the tape\'s own integer (billionths of a dollar). On a '
     'trade row, the trade price. The tape\'s "no price" value is kept as it is.'),
    ('A. The native tape', 'size', 'The size on the message. On a trade row, the trade size.'),
    ('A. The native tape', 'order_number', 'The exchange order number. A label only.'),
    ('A. The native tape', 'flags', 'The flags on the message, as sent.'),
    ('A. The native tape', 'ends_exchange_event', 'Yes when this tick carries the exchange end-of-event flag.'),
    ('A. The native tape', 'sequence_number', 'The exchange sequence number. Shared with other contracts on the '
     'channel, so jumps forward are normal.'),
    ('A. The native tape', 'channel', 'The exchange channel number.'),
    ('A. The native tape', 'publisher', 'The data vendor publisher number.'),
    ('A. The native tape', 'contract_number', 'The exchange number of the contract.'),
    ('A. The native tape', 'send_delay_ns', 'The delay the tape reports between the exchange sending and the vendor '
     'receiving.'),
    ('A. The native tape', 'record_type', 'The vendor\'s record type number (every row here is an order-tape record).'),
    ('A. The native tape', 'record_length', 'The vendor\'s record length field, as stored.'),
    ('B. Our labels', 'row_label', 'One of: trade day; 5 pm to 6 pm stretch; Sunday start-up. Decided by exchange '
     'time.'),
    ('B. Our labels', 'trade_day', 'The trade day (6 pm Eastern the evening before to 5 pm Eastern). Empty on stretch '
     'and start-up rows.'),
    ('B. Our labels', 'position_on_tape', 'The place of this tick on the tape for the week. A label only.'),
    ('B. Our labels', 'raw_file', 'The raw file this row came from.'),
    ('B. Our labels', 'raw_file_fingerprint', 'The fingerprint (SHA256) of that raw file.'),
    ('B. Our labels', 'contract', 'The contract symbol, read from the tape\'s own symbol record.'),
    ('B. Our labels', 'in_settlement_window', 'Yes on rows inside the 2:28 to 2:30 pm Eastern settlement window.'),
    ('B. Our labels', 'exchange_event', 'Which exchange event this tick belongs to: the position of the event\'s '
     'first tick.'),
    ('C. What this tick did', 'what_happened', 'To the touched order: joined; stayed; shrank; shrank by fill; lost '
     'its place (price changed or size raised); left by cancel; left by fill. "no change" on trade, fill and none '
     'messages, which change nothing in the book by themselves.'),
    ('C. What this tick did', 'order_size_before', 'The touched order\'s size just before this tick.'),
    ('C. What this tick did', 'order_size_after', 'The touched order\'s size just after this tick (0 when it left).'),
    ('C. What this tick did', 'orders_ahead_before', 'How many orders were ahead of it in line just before.'),
    ('C. What this tick did', 'size_ahead_before', 'How much size was ahead of it in line just before.'),
    ('C. What this tick did', 'life_step', 'Which step of this order\'s life this is so far (its entry is step 1; '
     'every later message that names it is a step).'),
    ('C. What this tick did', 'first_entered_position', 'The tick where this order first entered.'),
    ('C. What this tick did', 'previous_step_position', 'The tick of this order\'s previous step.'),
    ('C. What this tick did', 'entered_before_written_record', 'Yes when the order entered during ticks that are not '
     'written out (warm-up), so the two positions above name ticks with no row.'),
    ('C. What this tick did', 'first_entered_exchange_time_ns', 'When it first entered, exchange time.'),
    ('C. What this tick did', 'first_entered_received_time_ns', 'When it first entered, received time.'),
    ('C. What this tick did', 'took_place_exchange_time_ns', 'When it last took its place in line (as it stood just '
     'before this tick), exchange time.'),
    ('C. What this tick did', 'took_place_received_time_ns', 'The same, received time.'),
    ('C. What this tick did', 'rested_exchange_ns', 'How long it had held its place when this tick came, on exchange '
     'time.'),
    ('C. What this tick did', 'rested_received_ns', 'The same, on received time.'),
    ('C. What this tick did', 'rested_is_at_least', 'Yes when the order was carried over the weekend, so its true age '
     'is not on the tape.'),
    ('C. What this tick did', 'levels_from_best', 'How many resting price levels on that side were better than the '
     'price this tick acted at, just before it.'),
    ('C. What this tick did', 'left_price', 'When an order changed price: the price it left.'),
    ('C. What this tick did', 'left_line_size_before', 'Total size in the line it left, just before.'),
    ('C. What this tick did', 'left_line_size_after', 'Total size in the line it left, just after.'),
    ('C. What this tick did', 'left_line_orders_before', 'Number of orders in the line it left, just before.'),
    ('C. What this tick did', 'left_line_orders_after', 'Number of orders in the line it left, just after.'),
    ('C. What this tick did', 'irregular', 'Anything irregular on this tick, in words. Empty when nothing is.'),
    ('D. The book at this tick', 'best_bid', 'Best bid price, after this tick.'),
    ('D. The book at this tick', 'best_ask', 'Best ask price, after this tick.'),
    ('D. The book at this tick', 'gap', 'Best ask minus best bid.'),
    ('D. The book at this tick', 'bid_total_size', 'Total size resting on the bid side, whole book.'),
    ('D. The book at this tick', 'bid_orders', 'Number of orders on the bid side, whole book.'),
    ('D. The book at this tick', 'bid_levels', 'Number of price levels on the bid side, whole book.'),
    ('D. The book at this tick', 'ask_total_size', 'Total size resting on the ask side, whole book.'),
    ('D. The book at this tick', 'ask_orders', 'Number of orders on the ask side, whole book.'),
    ('D. The book at this tick', 'ask_levels', 'Number of price levels on the ask side, whole book.'),
]
for _side in ('bid', 'ask'):
    COLUMNS += [
        ('D. The book at this tick', f'best_{_side}_size', f'Size at the best {_side}.'),
        ('D. The book at this tick', f'best_{_side}_orders', f'Number of orders at the best {_side}.'),
        ('D. The book at this tick', f'best_{_side}_front_size', f'Size of the order at the front of the line at the '
         f'best {_side}.'),
        ('D. The book at this tick', f'best_{_side}_front_first_entered_exchange_time_ns', 'When that front order '
         'first entered, exchange time.'),
        ('D. The book at this tick', f'best_{_side}_front_first_entered_received_time_ns', 'When that front order '
         'first entered, received time.'),
        ('D. The book at this tick', f'best_{_side}_front_took_place_exchange_time_ns', 'When that front order last '
         'took its place, exchange time.'),
        ('D. The book at this tick', f'best_{_side}_front_took_place_received_time_ns', 'When that front order last '
         'took its place, received time.'),
        ('D. The book at this tick', f'best_{_side}_front_is_at_least', 'Yes when that front order was carried over '
         'the weekend.'),
    ]
COLUMNS += [
    ('D. The book at this tick', 'touched_price', 'The price this tick acted on (for an order that changed price, the '
     'price it joined).'),
    ('D. The book at this tick', 'touched_line', 'The full line at that price after this tick, front first: each '
     'order as order number|size|first entered exchange|first entered received|took place exchange|took place '
     'received|marks (w = carried over the weekend, b = entered before the written record), orders separated by ; '
     'When this tick emptied the line, the words "no orders".'),
    ('D. The book at this tick', 'touched_line_size_before', 'Total size in that line just before.'),
    ('D. The book at this tick', 'touched_line_size_after', 'Total size in that line just after.'),
    ('D. The book at this tick', 'touched_line_orders_before', 'Number of orders in that line just before.'),
    ('D. The book at this tick', 'touched_line_orders_after', 'Number of orders in that line just after.'),
    ('E. Change-of-state marks', 'best_bid_moved_from', 'The old best bid, when this tick moved it.'),
    ('E. Change-of-state marks', 'best_bid_moved_to', 'The new best bid, when this tick moved it.'),
    ('E. Change-of-state marks', 'best_ask_moved_from', 'The old best ask, when this tick moved it.'),
    ('E. Change-of-state marks', 'best_ask_moved_to', 'The new best ask, when this tick moved it.'),
    ('E. Change-of-state marks', 'level_appeared', 'Yes when this tick made a new price level appear.'),
    ('E. Change-of-state marks', 'level_emptied', 'Yes when this tick emptied a price level.'),
    ('E. Change-of-state marks', 'front_of_line_changed', 'Yes when the order at the front of a line this tick acted '
     'on is a different order afterwards (a new level\'s first order and an emptied level count).'),
]
COLUMNS += [(section, name, what) for section, name, what, _ in pin.COLUMNS]
NAMES = [name for _, name, _ in COLUMNS]
NO_LEFT = tuple(None for name in NAMES if name.startswith('left_'))
NO_TOUCHED = tuple(None for name in NAMES if name.startswith('touched_line_'))
INDEX = {name: i for i, name in enumerate(NAMES)}


def line_text(line) -> str:
    """The full line, front first (the format is described in COLUMNS, touched_line)."""
    return ';'.join(f'{o.id}|{o.size}|{o.entered_event}|{o.entered_recv}|{o.placed_event}|{o.placed_recv}|'
                    f'{"w" if o.carried_over_weekend else ""}{"" if o.entered_written else "b"}'
                    for o in line.orders.values())


def written_span(trade_day: dt.date) -> tuple:
    """[from, to) in exchange time of the rows one trade day's box writes: the stretch before it, the trade day and
    the stretch after it; for the week's first trade day also everything from the Sunday start-up (from is None)."""
    lo = to_ns(eastern(trade_day - dt.timedelta(days=1), HALT_EASTERN))
    hi = to_ns(eastern(trade_day, OPEN_EASTERN))
    return (None if trade_day - dt.timedelta(days=1) == week_sunday(trade_day) else lo), hi


def written_anywhere(week_days) -> list:
    """The spans written by any built trade day of the week (for the mark on orders that entered outside them)."""
    return [written_span(d) for d in sorted(week_days)]


class Walk:
    """The one pass over a week for one trade day's box. Iterate it to get the row of every written tick, as a list
    in COLUMNS order. While it is being iterated `book` is the book exactly as it stands after the row just given.
    `on_last_written(book, position)` is called once, with the book as it stands after the last written row."""

    def __init__(self, week, trade_day: dt.date, on_last_written=None, built=tape.BUILT_TRADE_DAYS, pins=None):
        self.week, self.trade_day, self.on_last_written, self.built = week, trade_day, on_last_written, built
        self.pins = pins if pins is not None else pin.Pins()
        self.book = Book()
        self.restatements, self.compared, self.stats = [], [], {}

    def __iter__(self):
        return _rows(self)


def build(week, trade_day: dt.date, stats: dict | None = None, built=tape.BUILT_TRADE_DAYS, pins=None):
    """The rows of one trade day's box (see Walk). `stats`, when given, receives the counts of the walk."""
    walk = Walk(week, trade_day, built=built, pins=pins)
    yield from walk
    if stats is not None:
        stats.update(walk.stats)


def _rows(walk: Walk):
    week, trade_day, built = walk.week, walk.trade_day, walk.built
    book, pinned = walk.book, walk.pins.at
    last_bit = tape.flag_bits()['F_LAST']
    snap_bit = tape.flag_bits()['F_SNAPSHOT']
    lo, hi = written_span(trade_day)
    opens, halts = trade_day_bounds(trade_day)
    settle_from = to_ns(eastern(trade_day, SETTLE_FROM_EASTERN))
    settle_to = to_ns(eastern(trade_day, SETTLE_TO_EASTERN))
    week_days = [d for d in built if week_sunday(d) == week_sunday(trade_day)]
    spans = written_anywhere(week_days)
    contract = next(iter(week[0].mappings))
    startup_end = to_ns(eastern(week_sunday(trade_day), HALT_EASTERN))
    day_text = trade_day.isoformat()
    counts = collections.Counter()
    sides = book.sides
    pos, event_start, new_event = 0, 0, True
    last_written, told = None, False

    for k, f in enumerate(week):
        if k:           # the vendor's restatement that opens a later file: compared with our book, never applied
            result, same = compare_with_restatement(book, f.records[:f.vendor_snapshot], detail=True)
            walk.compared.append(result)
            walk.restatements.append((f, same))
        c = tape.columns(f.records[f.vendor_snapshot:])
        for (te, tr, a, s, p, z, oid, fl, sq, ch, pub, ins, dly, rt, ln) in zip(
                c['ts_event'], c['ts_recv'], c['action'], c['side'], c['price'], c['size'], c['order_id'], c['flags'],
                c['sequence'], c['channel_id'], c['publisher_id'], c['instrument_id'], c['ts_in_delta'], c['rtype'],
                c['length']):
            if new_event:
                event_start = pos
            new_event = bool(fl & last_bit)
            in_record = any((a_ is None or a_ <= te) and te < b_ for a_, b_ in spans)
            if not ((lo is None or lo <= te) and te < hi):
                # warm-up or shelved: the book moves, nothing else is made or kept
                if last_written is not None and not told:
                    told = True
                    if walk.on_last_written is not None:
                        walk.on_last_written(book, last_written)
                book.apply(a, s, p, z, oid, fl, te, tr, sq, pos, carried=bool(fl & snap_bit), written=in_record)
                counts['warm-up' if te < hi else 'shelved'] += 1
                pos += 1
                continue

            # ---- just before the tick
            sides = book.sides
            bid_before, ask_before = book.best(BID), book.best(ASK)
            o = book.orders.get(oid) if a in (CANCEL, MODIFY, FILL) else None
            by_fill = oid in book.filled_in_event
            size_before = ahead_n = ahead_size = step = entered_pos = prev_pos = None
            e_ev = e_rc = pl_ev = pl_rc = rest_ev = rest_rc = at_least = before_rec = None
            home = home_before = home_front = None          # the line the order rests in, before
            dest_key = dest_before = dest_front = None      # the line this tick puts an order into, before
            levels = None
            if o is not None:
                size_before = o.size
                home = sides[o.side].lines[o.price]
                home_before, home_front = (home.size, len(home.orders)), next(iter(home.orders))
                ahead_n = ahead_size = 0
                for other in home.orders.values():
                    if other is o:
                        break
                    ahead_n += 1
                    ahead_size += other.size
                entered_pos, prev_pos = o.entered_pos, o.previous_pos
                e_ev, e_rc, pl_ev, pl_rc = o.entered_event, o.entered_recv, o.placed_event, o.placed_recv
                rest_ev, rest_rc = te - pl_ev, tr - pl_rc
                at_least, before_rec = o.carried_over_weekend, not o.entered_written
                home_side, home_price = o.side, o.price
            act_side, act_price = (o.side, o.price) if o is not None and a != MODIFY else (s, p)
            if a in (ADD, MODIFY) and s in sides and (o is None or p != o.price):
                dest_key = (s, p)
                dest = sides[s].lines.get(p)
                dest_before = (dest.size, len(dest.orders)) if dest else (0, 0)
                dest_front = next(iter(dest.orders)) if dest else None
            if act_side in sides and a in (ADD, CANCEL, MODIFY, FILL):
                prices = sides[act_side].prices
                levels = len(prices) - bisect.bisect_right(prices, act_price) if act_side == BID else \
                    bisect.bisect_left(prices, act_price)

            notes = book.apply(a, s, p, z, oid, fl, te, tr, sq, pos, carried=bool(fl & snap_bit), written=in_record)

            # ---- just after the tick
            sides = book.sides
            applied = not any(n.startswith('not applied') for n in notes)
            what, size_after = NO_CHANGE, None
            left = NO_LEFT
            touched_price = touched_text = None
            touched = NO_TOUCHED
            appeared = emptied = front_changed = False
            if a == tape.CLEAR:
                what = CLEARED
            elif not applied:
                what = NOT_APPLIED
            elif a == ADD:
                o2 = book.orders[oid]
                what, size_before, size_after, step = JOINED, 0, o2.size, o2.steps
                ahead_n, ahead_size = dest_before[1], dest_before[0]
                entered_pos, prev_pos = o2.entered_pos, None
                e_ev, e_rc, pl_ev, pl_rc = o2.entered_event, o2.entered_recv, o2.placed_event, o2.placed_recv
                rest_ev = rest_rc = 0
                at_least, before_rec = o2.carried_over_weekend, not o2.entered_written
            elif a == FILL and o is not None:
                size_after, step = o.size, o.steps
            elif a in (CANCEL, MODIFY):
                step = o.steps
                gone = oid not in book.orders
                size_after = 0 if gone else o.size
                if gone:
                    what = LEFT_BY_FILL if by_fill else LEFT_BY_CANCEL
                elif dest_key is not None:
                    what = LOST_PLACE_PRICE
                elif size_after > size_before:
                    what = LOST_PLACE_SIZE
                elif size_after < size_before:
                    what = SHRANK_BY_FILL if by_fill else SHRANK
                else:
                    what = STAYED

            # the line this tick acted on, after; and the line an order left when it changed price
            if dest_key is not None and applied:
                line = sides[dest_key[0]].lines[dest_key[1]]
                touched_price, touched_text = dest_key[1], line_text(line)
                touched = (dest_before[0], line.size, dest_before[1], len(line.orders))
                appeared = dest_before[1] == 0
                front_changed = next(iter(line.orders)) != dest_front
                if o is not None:                       # a modify to a new price: the line it left
                    old = sides[home_side].lines.get(home_price)
                    left = (home_price, home_before[0], old.size if old else 0, home_before[1],
                            len(old.orders) if old else 0)
                    emptied = old is None
                    front_changed = front_changed or (next(iter(old.orders)) if old else None) != home_front
            elif o is not None:
                line = sides[home_side].lines.get(home_price)
                touched_price = home_price
                touched_text = line_text(line) if line else NO_ORDERS
                touched = (home_before[0], line.size if line else 0, home_before[1], len(line.orders) if line else 0)
                emptied = line is None
                front_changed = (next(iter(line.orders)) if line else None) != home_front

            bid_after, ask_after = book.best(BID), book.best(ASK)
            row = [te, tr, a.decode(), s.decode(), p, z, oid, fl, new_event, sq, ch, pub, ins, dly, rt, ln,
                   TRADE_DAY if opens <= te < halts else STARTUP if te < startup_end else STRETCH,
                   day_text if opens <= te < halts else None, pos, f.name, f.sha256, contract,
                   settle_from <= te < settle_to, event_start,
                   what, size_before, size_after, ahead_n, ahead_size, step, entered_pos, prev_pos, before_rec,
                   e_ev, e_rc, pl_ev, pl_rc, rest_ev, rest_rc, at_least, levels, *left,
                   '; '.join(notes) or None,
                   bid_after, ask_after,
                   None if bid_after is None or ask_after is None else ask_after - bid_after,
                   sides[BID].size, sides[BID].orders, len(sides[BID].lines),
                   sides[ASK].size, sides[ASK].orders, len(sides[ASK].lines)]
            for side_key, best in ((BID, bid_after), (ASK, ask_after)):
                if best is None:
                    row += [None] * BEST_FIELDS
                else:
                    top = sides[side_key].lines[best]
                    front = next(iter(top.orders.values()))
                    row += [top.size, len(top.orders), front.size, front.entered_event, front.entered_recv,
                            front.placed_event, front.placed_recv, front.carried_over_weekend]
            row += [touched_price, touched_text, *touched,
                    bid_before if bid_after != bid_before else None, bid_after if bid_after != bid_before else None,
                    ask_before if ask_after != ask_before else None, ask_after if ask_after != ask_before else None,
                    appeared, emptied, front_changed]
            row += pinned(tr, day_text if opens <= te < halts else None)
            counts['written'] += 1
            counts[what] += 1
            last_written = pos
            pos += 1
            yield row
    if last_written is not None and not told and walk.on_last_written is not None:
        walk.on_last_written(book, last_written)
    walk.stats.update(counts=dict(counts), ticks=pos, irregular=dict(book.irregular),
                      orders_resting_at_the_end=len(book.orders))


BEST_FIELDS = sum(1 for _, name, _ in COLUMNS if name.startswith('best_bid_') and name not in (
    'best_bid_moved_from', 'best_bid_moved_to'))

