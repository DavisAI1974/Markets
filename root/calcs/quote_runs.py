"""ROOT part 2, calculation `quote_runs`: the runs of the best bid and of the best ask (Step 2, piece I, first part).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece I, 2026-11-16: "Include
all of your pieces"). The rows carry the best bid and the best ask at every tick, so a move in price is read from
the quote itself, at every tick, and not only where a trade happened to print.

The best bid and the best ask are followed separately (never combined into a midpoint, which is an average of two
prices). A RUN is the best price moving one way: it starts with a move, goes on with each further move the same
way, and ends at the first move the other way, whatever its size. No minimum length and no minimum size: a run of
one move is kept. Every turn is one FACT, recorded at the tick it becomes known and naming its run by the tick the
run started at:
- `run started`: the best price moved, and it is not a further move of the run before;
- `new furthest price`: the best price moved again the same way;
- `first step back`: the best price moved the other way. The run has ended. The same tick starts the next run, so
  it carries two facts: the step back of the run that ended, then the start of the new one.
A run still going at the last tick of the trade day is listed in its own small file, not on a row (there is no tick
at which its end could become known). Columns on every row give the run in progress on each side at that tick.

Claude's calls in the build, stated to Greg (his to correct):
- A run never crosses 6 pm. The best price at the first tick of the trade day is where the following starts; a move
  made by that first tick itself is measured from a price before the trade day, so it is not counted as a move.
- When the book is crossed for a moment during a sweep (the best bid at or above the best ask), each side is
  followed as the book has it. No tick is set aside; every fact carries the gap at its tick, so those moments show.
- Up and down are read off the prices, as the side of the flow is read off the tape. They are not groups.
A side with no best price at all is outside this rule and stops the run with its reason; none occurs on the four
trade days. The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

READS = ['received_time_ns', 'best_bid', 'best_ask']
BEST_BID, BEST_ASK = 'best bid', 'best ask'
QUOTES = (BEST_BID, BEST_ASK)
UP, DOWN = 'up', 'down'
STARTED, FURTHER, STEP_BACK = 'run started', 'new furthest price', 'first step back'
KINDS = (STARTED, FURTHER, STEP_BACK)

RUN_FIGURES = [
    ('run_start_position', 'The run of the {quote} in progress at this tick: the tick it started at (its position '
     'on the tape; a label only). Empty until the {quote} first moves in the trade day.'),
    ('run_direction', 'Which way that run is going: up or down.'),
    ('run_price_before', 'The {quote} just before that run started.'),
    ('run_moves', 'How many moves that run has made so far.'),
    ('run_distance', 'How far that run has gone so far: the {quote} now minus the price before the run (the '
     'tape\'s own price units; below zero for a run down).'),
    ('run_since_start_ns', 'From the tick that run started to this tick.'),
]
COLUMNS = [(f'{quote.split()[-1]}_{key}', what.format(quote=quote)) for quote in QUOTES for key, what in RUN_FIGURES]
COLUMNS.append(('quote_run_facts_known', 'How many facts about runs of the quote became known at this tick (they '
                'are in the facts table).'))
NAMES = [name for name, _ in COLUMNS]
TEXT = {name for name in NAMES if name.endswith('run_direction')}
YES_NO, DECIMALS = set(), set()
NO_RUN = tuple(None for _ in RUN_FIGURES)

FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('quote', 'Which price is followed: best bid or best ask.'),
    ('run_start_position', 'Which run the fact is about: the tick the run started at. A label only.'),
    ('fact', 'The kind of moment: run started, new furthest price, first step back.'),
    ('direction', 'Which way the run goes: up or down.'),
    ('price_before_run', 'The best price just before the run started.'),
    ('price_before_tick', 'The best price just before this tick.'),
    ('price_now', 'The best price just after this tick.'),
    ('furthest_price', 'The furthest price the run has reached, this tick included. On first step back: the price '
     'the run ended at.'),
    ('moves', 'How many moves the run has made, this tick included. On first step back: how many it made in all.'),
    ('distance', 'The furthest price minus the price before the run (below zero for a run down).'),
    ('since_run_start_ns', 'From the tick the run started to this tick.'),
    ('since_previous_move_ns', 'From the move of this quote before this one to this tick. Empty on the first move '
     'of the trade day.'),
    ('step_back', 'On first step back: the best price now minus the furthest price of the run.'),
    ('since_furthest_ns', 'On first step back: from the tick the run reached its furthest price to this tick.'),
    ('gap_now', 'The best ask minus the best bid just after this tick. Zero or below when the book is crossed.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'quote', 'fact', 'direction'}
OPEN_COLUMNS = ['quote', 'run_start_position', 'direction', 'price_before_run', 'furthest_price', 'moves']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, set(), set()),
          'open-at-the-end': (OPEN_COLUMNS, {'quote', 'direction'}, set(), set())}


class Run:
    """One run of one best price, as it stands."""
    __slots__ = ('start', 'started_at', 'direction', 'price_before', 'price', 'moves', 'moved_at')

    def __init__(self, start, started_at, direction, price_before, price):
        self.start, self.started_at, self.direction = start, started_at, direction
        self.price_before, self.price, self.moves, self.moved_at = price_before, price, 1, started_at


class Quote:
    """One best price through one trade day."""

    def __init__(self, name: str):
        self.name, self.price, self.run, self.moved_at, self.seen = name, None, None, None, False


class QuoteRuns:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.quotes = [Quote(name) for name in QUOTES]
        self.counts = {f'{quote}: {kind}': 0 for quote in QUOTES for kind in KINDS}
        self.crossed = 0

    def _fact(self, q: Quote, run: Run, kind, position, received, before, now, gap, back=None) -> tuple:
        self.counts[f'{q.name}: {kind}'] += 1
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, quote=q.name,
                   run_start_position=run.start, fact=kind, direction=run.direction,
                   price_before_run=run.price_before, price_before_tick=before, price_now=now,
                   furthest_price=run.price, moves=run.moves, distance=run.price - run.price_before,
                   since_run_start_ns=received - run.started_at,
                   since_previous_move_ns=None if q.moved_at is None else received - q.moved_at, gap_now=gap)
        if back is not None:
            row.update(step_back=now - run.price, since_furthest_ns=received - run.moved_at)
        return tuple(row[name] for name in FACT_NAMES)

    def tick(self, position, received, best_bid, best_ask) -> tuple:
        facts = []
        if best_bid is None or best_ask is None:
            raise ValueError(f'position {position}: a side of the book has no best price: outside the rule of '
                             f'quote_runs')
        gap = best_ask - best_bid
        if gap <= 0:
            self.crossed += 1
        for q, now in zip(self.quotes, (best_bid, best_ask)):
            before, first = q.price, not q.seen
            q.price, q.seen = now, True
            if first or now == before:
                continue
            direction = UP if now > before else DOWN
            run = q.run
            if run is not None and run.direction == direction:
                run.price, run.moves = now, run.moves + 1
                facts.append(self._fact(q, run, FURTHER, position, received, before, now, gap))
                run.moved_at = received
            else:
                if run is not None:
                    facts.append(self._fact(q, run, STEP_BACK, position, received, before, now, gap, back=True))
                q.run = run = Run(position, received, direction, before, now)
                facts.append(self._fact(q, run, STARTED, position, received, before, now, gap))
            q.moved_at = received
        values = ()
        for q in self.quotes:
            run = q.run
            values += NO_RUN if run is None else (run.start, run.direction, run.price_before, run.moves,
                                                  run.price - run.price_before, received - run.started_at)
        return values + (len(facts),), facts

    def still_going(self) -> list:
        """The runs in progress, as they stand, in OPEN_COLUMNS order."""
        return [(q.name, q.run.start, q.run.direction, q.run.price_before, q.run.price, q.run.moves)
                for q in self.quotes if q.run is not None]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`. `tables`, when given, receives
    the facts and the runs still going at the last tick; `counts` the counts of the run."""
    calc = QuoteRuns()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        values, new = calc.tick(position, *row)
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_going()
    if counts is not None:
        counts.update(dict(facts=calc.counts, ticks_with_the_book_crossed=calc.crossed,
                           runs_still_going_at_the_last_tick=len(calc.still_going())))
