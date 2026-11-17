"""ROOT part 2, calculation `resting`: the resting orders through a peak, a run of the quote and a trade leg (Step 2,
piece K), and the orders that were ahead of a filled order in our line.

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece K, 2026-11-16: "Yes to
k"; his go 2026-11-17). Piece C says how much size came and went. This says whether it was the same orders: of the
orders resting in the book at an EARLIER turn, what had become of them by each LATER turn of the same thing.

The earlier turn, and the later turns that name it:
- a peak: the earlier turn is the tick of its high. Later turns: the tick the peak became known, each new low,
  reaching zero, and the end of its story (came back, or beaten), in piece 2's own words;
- a run of the best bid or of the best ask: the earlier turn is the tick the run started. Later turns: each new
  furthest price and the first step back;
- a trade leg: the earlier turn is the leg's first trade. Later turns: the print that shows the leg has started,
  each new furthest price, and the print that ends it.
One line per later turn. For the bid side and the ask side, each for the whole side and for the orders that stood
at that side's best price at the earlier turn: how many orders and how much size rested at the earlier turn; how
many of those were carried in from before the trade day; and by this tick how many still rest and with how much
size, how many left by fill and by cancel, how many were filled at all and how much size, how many gave size up
and how much, how much size was added to them, and how many changed price.

Also written, on Greg's call of 2026-11-16 (the place in line is not run down; it is shown): one line for every
fill of an order that had another order ahead of it in our line, with how many orders and how much size were
ahead, and which orders. Where no order was ahead nothing is written.

Claude's calls in the build, stated to Greg (his to correct):
- The orders at a turn are read once the tick of that turn is done, as the book columns on the row are.
- The orders at a peak's high are held from the tick of the high (the flow's high so far), so nothing is taken
  from a later tick; a line is written only from the tick the peak became known.
- An order resting since before the trade day has no row in it until something happens to it. It is known from
  the row's own count and size of the side, and is counted as still resting until its first row; from then it is
  followed like any other, and it is counted in the carried-in figure. Nothing from before the trade day is
  calculated on: those orders are part of the book.
- The order number only ties an order's rows together. These are counts and sizes of single orders; no average
  is taken and nothing is ranked.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root import rows as R
from root.calcs import in_play
from root.calcs import leg_peaks as LP
from root.calcs import peak_story as P
from root.calcs import quote_runs as Q

BOOK = [f'{side}_{figure}' for side in ('bid', 'ask') for figure in ('orders', 'total_size')] + \
       [f'best_{side}_{figure}' for side in ('bid', 'ask') for figure in ('orders', 'size')]
READS = list(in_play.READS) + ['order_number', 'what_happened', 'order_size_before', 'order_size_after',
                               'touched_price', 'left_price', 'orders_ahead_before', 'size_ahead_before',
                               'touched_line', 'exchange_event'] + BOOK
SIDES = {'B': 'bid', 'A': 'ask'}
FILLS = (R.SHRANK_BY_FILL, R.LEFT_BY_FILL)
LEAVES = (R.LEFT_BY_CANCEL, R.LEFT_BY_FILL)
STEPS = (R.JOINED, R.STAYED, R.SHRANK, R.SHRANK_BY_FILL, R.LOST_PLACE_PRICE, R.LOST_PLACE_SIZE) + LEAVES
PEAK, LEG = 'peak', 'trade leg'
RUN = {Q.BEST_BID: 'run of the best bid', Q.BEST_ASK: 'run of the best ask'}
ABOUT = (PEAK,) + tuple(RUN.values()) + (LEG,)
WHOLE, BEST = 'side', 'best'
SIZE, PRICE, FILLED, PULLED, RAISED, MOVES, RESTS, CARRIED, LEFT_HOW = range(9)     # one order as it stands

COLUMNS = [('resting_facts_known', 'How many lines about resting orders at a later turn became known at this tick '
            '(they are in the facts table).'),
           ('ahead_of_a_fill_known', 'How many lines about a filled order with orders ahead of it in our line '
            'became known at this tick (they are in the ahead table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
FIGURES = [
    ('orders_at_turn', 'orders resting {where} at the earlier turn'),
    ('size_at_turn', 'their size together at the earlier turn'),
    ('carried_in', 'how many of them were resting since before the trade day'),
    ('still_resting_orders', 'how many of them still rest at this tick'),
    ('still_resting_size', 'the size of those still resting, as it stands at this tick'),
    ('left_by_fill', 'how many of them have left by fill'),
    ('left_by_cancel', 'how many of them have left by cancel'),
    ('filled_orders', 'how many of them have been filled at all since the earlier turn'),
    ('filled_size', 'the size filled on them since the earlier turn'),
    ('pulled_orders', 'how many of them have given size up (a cancel, or a cut in size) since the earlier turn'),
    ('pulled_size', 'the size given up on them since the earlier turn'),
    ('added_size', 'the size added to them since the earlier turn'),
    ('moved_orders', 'how many of them have changed price since the earlier turn'),
]
WHERE = {WHOLE: 'on the {side} side', BEST: 'at the best {side} price of the earlier turn'}
FACT_COLUMNS = [
    ('known_position', 'The tick of the later turn: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('about', 'What the turn belongs to: peak, run of the best bid, run of the best ask, trade leg.'),
    ('turn', 'The later turn, in the words of the calculation that writes it.'),
    ('earlier_turn_position', 'The earlier turn: the tick of the peak\'s high, the tick the run started, or the '
     'leg\'s first trade. A label only; it also names which peak, run or leg.'),
    ('earlier_turn_received_time_ns', 'When that tick was received.'),
    ('since_earlier_turn_ns', 'From the earlier turn to this tick.'),
    ('best_bid_at_turn', 'The best bid once the tick of the earlier turn was done.'),
    ('best_ask_at_turn', 'The best ask once the tick of the earlier turn was done.'),
] + [(f'{side}_{scope}_{key}', (what[0].upper() + what[1:] + '.').format(where=WHERE[scope].format(side=side)))
     for side in SIDES.values() for scope in (WHOLE, BEST) for key, what in FIGURES]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
AHEAD_COLUMNS = [
    ('known_position', 'The tick of the filled order\'s own row: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('exchange_event', 'The exchange event the tick belongs to: the position of the event\'s first tick.'),
    ('order_number', 'The filled order. A label only.'),
    ('side', 'The side it rests on: bid or ask.'),
    ('price', 'The price it rested at.'),
    ('what_happened', 'Shrank by fill, or left by fill.'),
    ('size_filled', 'The size filled on it at this tick.'),
    ('orders_ahead', 'How many orders were ahead of it in our line just before.'),
    ('size_ahead', 'How much size was ahead of it in our line just before.'),
    ('orders_ahead_numbers', 'Those orders, front first, separated by ; (labels only).'),
    ('orders_ahead_named', 'How many of them the line on the row names (the same as orders ahead, unless the '
     'line on the row is shorter).'),
]
AHEAD_NAMES = [name for name, _ in AHEAD_COLUMNS]
TABLES = {'facts': (FACT_NAMES, {'about', 'turn'}, set(), set()),
          'ahead': (AHEAD_NAMES, {'side', 'what_happened', 'orders_ahead_numbers'}, set(), set())}
F_KIND, F_PEAK = P.FACT_NAMES.index('fact'), P.FACT_NAMES.index('peak_high_position')
Q_QUOTE, Q_START, Q_KIND = (Q.FACT_NAMES.index(name) for name in ('quote', 'run_start_position', 'fact'))
L_KIND = LP.LEG_FACT_NAMES.index('fact')
HIGH_POSITION = in_play.HIGH_POSITION


class Turn:
    """The book at one earlier turn: every order known to rest on each side once that tick was done, each with
    how it stood then, and the row's own count and size of each side and of each best price."""
    __slots__ = ('position', 'received', 'best', 'held', 'book')

    def __init__(self, position, received, best, resting, book):
        self.position, self.received, self.best, self.book = position, received, best, book
        self.held = {side: [(order, order[SIZE], order[PRICE], order[FILLED], order[PULLED], order[RAISED],
                             order[MOVES]) for order in orders.values()] for side, orders in resting.items()}

    def reveal(self, side, order):
        """An order resting since before the trade day has its first row: it rested here untouched."""
        self.held[side].append((order, order[SIZE], order[PRICE], 0, 0, 0, 0))

    def figures(self) -> tuple:
        out = ()
        for side in SIDES.values():
            best = self.best[side]
            tally = {WHOLE: [0] * len(FIGURES), BEST: [0] * len(FIGURES)}
            for order, size, price, filled, pulled, raised, moves in self.held[side]:
                for t in (tally[WHOLE], tally[BEST]) if price == best else (tally[WHOLE],):
                    t[0] += 1
                    t[1] += size
                    t[2] += order[CARRIED]
                    if order[RESTS]:
                        t[3] += 1
                        t[4] += order[SIZE]
                    elif order[LEFT_HOW] == R.LEFT_BY_FILL:
                        t[5] += 1
                    else:
                        t[6] += 1
                    if order[FILLED] != filled:
                        t[7] += 1
                        t[8] += order[FILLED] - filled
                    if order[PULLED] != pulled:
                        t[9] += 1
                        t[10] += order[PULLED] - pulled
                    t[11] += order[RAISED] - raised
                    t[12] += order[MOVES] != moves
            for scope, (orders, size) in ((WHOLE, self.book[side][:2]), (BEST, self.book[side][2:])):
                t = tally[scope]                       # the orders with no row yet: resting since before the trade
                unseen, unseen_size = orders - t[0], size - t[1]       # day, untouched, so still resting as they were
                if unseen < 0 or unseen_size < 0 or (unseen == 0) != (unseen_size == 0):
                    raise ValueError(f'the {side} {scope} at position {self.position}: the row says {orders} orders '
                                     f'of size {size}; {t[0]} of size {t[1]} are followed')
                t[0], t[1], t[2], t[3], t[4] = orders, size, t[2] + unseen, t[3] + unseen, t[4] + unseen_size
                out += tuple(t)
        return out


class Resting:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts, the ahead lines)."""

    def __init__(self):
        self.story, self.runs, self.legs = P.PeakStory(), Q.QuoteRuns(), LP.Legs()
        self.orders = {}                               # every order with a row so far: order number -> as it stands
        self.resting = {side: {} for side in SIDES.values()}
        self.rise = None                               # the book at the flow's high so far
        self.peaks = {}                                # open stories: the tick of the high -> the book at the high
        self.run = {}                                  # quote -> the book at the start of its run in progress
        self.stretch = self.leg = None                 # the book at the first print of the stretch in progress,
        self.counts = dict.fromkeys(ABOUT, 0)          # and at the first trade of the leg in progress
        self.counts.update(orders_carried_in_with_a_row=0, ahead_of_a_fill=0)

    def _held(self):
        turns = [self.rise, self.stretch, self.leg] + list(self.peaks.values()) + list(self.run.values())
        return {id(turn): turn for turn in turns if turn is not None}.values()

    def _order(self, position, side, number, what, before, after, touched_price, left_price):
        order = self.orders.get(number)
        if what == R.JOINED:
            if order is not None:
                raise ValueError(f'position {position}: order {number} joins a second time')
            order = self.orders[number] = [after, touched_price, 0, 0, 0, 0, True, 0, None]
            self.resting[side][number] = order
            return
        if order is None:                              # resting since before the trade day: its first row
            order = self.orders[number] = [before, left_price if what == R.LOST_PLACE_PRICE else touched_price,
                                           0, 0, 0, 0, True, 1, None]
            self.resting[side][number] = order
            self.counts['orders_carried_in_with_a_row'] += 1
            for turn in self._held():
                turn.reveal(side, order)
        if not order[RESTS] or order[SIZE] != before:
            raise ValueError(f'position {position}: order {number} stood at size {order[SIZE]}, resting '
                             f'{order[RESTS]}; the row says {before} before')
        if what in FILLS:
            order[FILLED] += before - after
        elif after < before:
            order[PULLED] += before - after
        else:
            order[RAISED] += after - before
        if what == R.LOST_PLACE_PRICE:
            order[MOVES] += 1
            order[PRICE] = touched_price
        order[SIZE] = after
        if what in LEAVES:
            order[RESTS], order[LEFT_HOW] = False, what
            del self.resting[side][number]

    def tick(self, position, row) -> tuple:
        (received, action, side, size, price, best_bid, best_ask, number, what, before, after, touched_price,
         left_price, ahead, size_ahead, line, event) = row[:len(READS) - len(BOOK)]
        book = dict(zip(SIDES.values(), (row[-8:-6] + row[-4:-2], row[-6:-4] + row[-2:])))
        lines = []
        if what in STEPS:
            self._order(position, SIDES[side], number, what, before, after, touched_price, left_price)
            if what in FILLS and ahead:
                front = [] if line == R.NO_ORDERS or not line else [entry.split('|')[0] for entry in line.split(';')]
                self.counts['ahead_of_a_fill'] += 1
                lines.append((position, received, event, number, SIDES[side], touched_price, what, before - after,
                              ahead, size_ahead, ';'.join(front[:ahead]), len(front[:ahead])))
        elif what == R.CLEARED:
            raise ValueError(f'position {position}: the book is cleared inside a trade day: outside the rule of '
                             f'resting')
        _, _, story_facts = self.story.tick(position, received, (action or '').encode(), (side or '').encode(),
                                            size, price)
        _, run_facts = self.runs.tick(position, received, best_bid, best_ask)
        leg_facts = self.legs.trade(position, received, price) if action == LP.TRADE else []
        now = None                                     # the book once this tick is done, made once if needed

        def book_now():
            nonlocal now
            if now is None:
                now = Turn(position, received, dict(zip(SIDES.values(), (best_bid, best_ask))), self.resting, book)
            return now
        facts = []

        def write(about, turn, earlier: Turn):
            self.counts[about] += 1
            facts.append((position, received, about, turn, earlier.position, earlier.received,
                          received - earlier.received, earlier.best['bid'], earlier.best['ask']) + earlier.figures())
        for fact in story_facts:
            kind, high = fact[F_KIND], fact[F_PEAK]
            if kind == P.BUILD_UP:
                if self.rise is None or self.rise.position != high:
                    raise ValueError(f'position {position}: the peak with its high at {high} became known and the '
                                     f'book at that high was not held')
                self.peaks[high] = self.rise
            write(PEAK, kind, self.peaks[high])
            if kind in (P.CAME_BACK, P.BEATEN):
                del self.peaks[high]
        high = self.story.flow.high
        if high is not None and high[HIGH_POSITION] == position:
            self.rise = book_now()
        for fact in run_facts:
            quote, kind = fact[Q_QUOTE], fact[Q_KIND]
            if kind == Q.STARTED:
                self.run[quote] = book_now()
            else:
                write(RUN[quote], kind, self.run[quote])
        for fact in leg_facts:
            if fact[L_KIND] == LP.STARTED:
                self.leg = self.stretch
            write(LEG, fact[L_KIND], self.leg)
        if action == LP.TRADE and self.legs.stretch_first[0] == position:
            self.stretch = book_now()
        return (len(facts), len(lines)), facts, lines


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = Resting()
    facts = [] if tables is None else tables.setdefault('facts', [])
    ahead = [] if tables is None else tables.setdefault('ahead', [])
    for position, row in ticks:
        values, new, lines = calc.tick(position, row)
        facts.extend(new)
        ahead.extend(lines)
        yield position, values
    if counts is not None:
        counts.update(dict(lines_by_what_the_turn_belongs_to={k: calc.counts[k] for k in ABOUT},
                           lines=sum(calc.counts[k] for k in ABOUT),
                           orders_with_a_row=len(calc.orders),
                           orders_carried_in_with_a_row=calc.counts['orders_carried_in_with_a_row'],
                           ahead_of_a_fill_lines=calc.counts['ahead_of_a_fill']))
