"""ROOT part 2, calculation `turn_peaks`: the peak worked out with no window, and every peak laid against the turns
of the price (Greg, 2026-11-17: "We need to calc this without the window and find the peak number ... And if the
peaks are peaking at the turns, then we have a huge problem solved").

Two kinds of peak are followed, side by side; neither replaces the other:
- the 20-second peak: piece 1's own (`flow_peak`), unchanged;
- the peak with no window (Claude's call, stated to Greg): the flow is counted from the moment the aggressor side
  last changed, not over any span of the clock. Every run of trades on one side is its own event. It peaks at
  its last trade, and its number is the size traded in the run. It is known at the first trade on the other side.
  A trade the tape gives no side for neither continues nor breaks a run; its size is kept on its own.

What is written, every peak on its own lines, each at the tick it could first be known:
- peak known: the peak (kind, side, number, the tick of its high, the price of the last print at its high) and
  the price of the last print at the tick it became known;
- one line for each of three moves in price that were under way at the peak's high, written when that move has
  ended (or at the tick the peak became known, when it had ended already): the trade leg, the run of the best bid
  and the run of the best ask. Each says which way the move went, how many steps it had made at the peak's high,
  how many it made in all, and so how many it made AFTER the high. None after the high means the move ended where
  the peak's high found it: the peak sat at the turn of that move.
The turns are the ones already followed with no window: the trade legs (the earlier work's rule) and the runs of
the quote (piece I). No span of time is chosen anywhere here, nothing is ranked, and no peak is grouped or named a
kind: side, direction and counts are read off the tape.

A move still going at the last tick of the trade day leaves its peaks without that line; they are listed in their
own table. The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root.calcs import flow_peak, in_play
from root.calcs import leg_peaks as LP
from root.calcs import peak_story as P
from root.calcs import quote_runs as Q

READS = list(in_play.READS)
WINDOW, NO_WINDOW = '20-second flow', 'no window'
KINDS = (WINDOW, NO_WINDOW)
KNOWN = 'peak known'
LEG = 'trade leg'
RUN = {Q.BEST_BID: 'run of the best bid', Q.BEST_ASK: 'run of the best ask'}
MOVES = (LEG,) + tuple(RUN.values())
ENDED = {move: f'{move} ended' for move in MOVES}
BUY, SELL = flow_peak.BUY_TEXT, flow_peak.SELL_TEXT
SIDE = {'B': BUY, 'A': SELL}

COLUMNS = [
    ('run_side', 'The run of trades on one side in progress at this tick (the flow with no window): buy or sell. '
     'Empty until the first trade with a side in the trade day.'),
    ('run_size', 'The size traded in that run so far.'),
    ('run_trades', 'How many trades that run holds so far.'),
    ('run_first_trade_position', 'The first trade of that run: its position on the tape. A label only.'),
    ('run_no_side_size', 'Size traded during that run that the tape gives no side for. In no figure above.'),
    ('turn_peak_facts_known', 'How many lines about a peak against the turns of the price became known at this '
     'tick (they are in the facts table).'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = {'run_side'}, set(), set()
NO_RUN = (None,) * (len(COLUMNS) - 1)
FACT_COLUMNS = [
    ('known_position', 'The tick at which this line became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('peak_kind', 'Which peak: 20-second flow, or no window.'),
    ('fact', 'Peak known; or which move in price under way at the peak\'s high has ended: trade leg ended, run of '
     'the best bid ended, run of the best ask ended.'),
    ('peak_side', 'Buy or sell.'),
    ('peak_high_position', 'The tick of the peak\'s high. A label only; with the kind it names the peak.'),
    ('peak_high_received_time_ns', 'When that tick was received.'),
    ('peak_number', 'The peak\'s number. 20-second flow: the size of the flow at the high (0 to 1). No window: the '
     'size traded in the run of trades on one side.'),
    ('peak_trades', 'No window: how many trades the run held.'),
    ('peak_first_trade_position', 'No window: the first trade of the run. A label only.'),
    ('print_price_at_high', 'The price of the last print at the tick of the high.'),
    ('print_price_when_known', 'On peak known: the price of the last print at the tick the peak became known.'),
    ('since_high_ns', 'From the high to this tick.'),
    ('move_direction', 'On a move ended: which way the move went, up or down.'),
    ('move_start_position', 'The move: the trade leg\'s first trade, or the tick the run of the quote started. A '
     'label only.'),
    ('move_price_at_high', 'The furthest price the move had reached at the peak\'s high.'),
    ('move_steps_at_high', 'How many steps the move had made at the peak\'s high.'),
    ('move_steps_in_all', 'How many steps the move made in all.'),
    ('move_steps_after_high', 'How many steps the move made after the peak\'s high. None means the move ended '
     'where the peak\'s high found it.'),
    ('move_end_price', 'The price the move ended at.'),
    ('move_ended_position', 'The tick at which the end of the move was known. A label only. It is before the tick '
     'of this line when the move had ended before the peak became known.'),
    ('move_ended_received_time_ns', 'When that tick was received.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
OPEN_COLUMNS = ['peak_kind', 'peak_side', 'peak_high_position', 'move', 'move_start_position', 'move_steps_at_high']
TABLES = {'facts': (FACT_NAMES, {'peak_kind', 'fact', 'peak_side', 'move_direction'}, set(), {'peak_number'}),
          'open-at-the-end': (OPEN_COLUMNS, {'peak_kind', 'peak_side', 'move'}, set(), set())}
F_KIND, F_PEAK, F_PRICE = (P.FACT_NAMES.index(name) for name in ('fact', 'peak_high_position', 'price_at_high'))
V_SIDE, V_SIZE, V_HIGH_AT = (flow_peak.NAMES.index(name) for name in
                             ('peak_side', 'peak_size', 'peak_high_received_time_ns'))
Q_QUOTE, Q_START, Q_KIND, Q_DIRECTION, Q_FURTHEST, Q_MOVES = (Q.FACT_NAMES.index(name) for name in (
    'quote', 'run_start_position', 'fact', 'direction', 'furthest_price', 'moves'))
L_KIND, L_FIRST, L_DIRECTION, L_PRICE, L_STEPS = (LP.LEG_FACT_NAMES.index(name) for name in (
    'fact', 'leg_first_trade_position', 'direction', 'price', 'steps'))
HIGH_POSITION = in_play.HIGH_POSITION


class TurnPeaks:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.story, self.runs, self.legs = P.PeakStory(), Q.QuoteRuns(), LP.Legs()
        self.moves = dict.fromkeys(MOVES)              # each move in progress: (start, direction, price, steps)
        self.ended = {}                                # (move, start) -> (direction, steps in all, end price,
        self.waiting = {}                              # position, received); and the peaks waiting on a move
        self.last_print = None                         # the price of the last print
        self.rise = None                               # at the flow's high so far: (position, moves, last print)
        self.run = None                                # the run of trades on one side in progress: [side, size,
        self.counts = {f'{kind}: {fact}': 0 for kind in KINDS for fact in (KNOWN,) + tuple(ENDED.values())}
        self.counts.update({f'{kind}: {move}: no step after the high': 0 for kind in KINDS for move in MOVES})

    def _line(self, position, received, kind, fact, peak, **more) -> tuple:
        self.counts[f'{kind}: {fact}'] += 1
        side, high, high_at, number, trades, first, at_high = peak
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, peak_kind=kind, fact=fact,
                   peak_side=side, peak_high_position=high, peak_high_received_time_ns=high_at, peak_number=number,
                   peak_trades=trades, peak_first_trade_position=first, print_price_at_high=at_high,
                   since_high_ns=received - high_at, **more)
        return tuple(row[name] for name in FACT_NAMES)

    def _move_line(self, position, received, kind, peak, move, held, end) -> tuple:
        start, _, price, steps = held
        direction, in_all, end_price, ended_position, ended_at = end
        if in_all == steps:
            self.counts[f'{kind}: {move}: no step after the high'] += 1
        return self._line(position, received, kind, ENDED[move], peak, move_direction=direction,
                          move_start_position=start, move_price_at_high=price, move_steps_at_high=steps,
                          move_steps_in_all=in_all, move_steps_after_high=in_all - steps, move_end_price=end_price,
                          move_ended_position=ended_position, move_ended_received_time_ns=ended_at)

    def _peak(self, position, received, kind, peak, at_high: dict) -> list:
        """A peak has become known: its own line, and a line for each move under way at its high that has ended
        already; the others wait for their move to end."""
        lines = [self._line(position, received, kind, KNOWN, peak, print_price_when_known=self.last_print)]
        for move, held in at_high.items():
            if held is None:                           # no such move had started yet at the high
                continue
            end = self.ended.get((move, held[0]))
            if end is None:
                self.waiting.setdefault((move, held[0]), []).append((kind, peak, held))
            else:
                lines.append(self._move_line(position, received, kind, peak, move, held, end))
        return lines

    def _end(self, position, received, move, start, direction, steps, price) -> list:
        self.ended[move, start] = end = (direction, steps, price, position, received)
        return [self._move_line(position, received, kind, peak, move, held, end)
                for kind, peak, held in self.waiting.pop((move, start), [])]

    def tick(self, position, received, action, side, size, price, best_bid, best_ask) -> tuple:
        values, _, story_facts = self.story.tick(position, received, (action or '').encode(),
                                                 (side or '').encode(), size, price)
        _, run_facts = self.runs.tick(position, received, best_bid, best_ask)
        trade = action == LP.TRADE
        leg_facts = self.legs.trade(position, received, price) if trade else []
        facts = []
        # the moves: what ended at this tick, and how each stands once this tick is done
        for fact in leg_facts:
            if fact[L_KIND] == LP.ENDED:
                facts += self._end(position, received, LEG, fact[L_FIRST], fact[L_DIRECTION], fact[L_STEPS],
                                   fact[L_PRICE])
            else:
                self.moves[LEG] = (fact[L_FIRST], fact[L_DIRECTION], fact[L_PRICE], fact[L_STEPS])
        for fact in run_facts:
            move = RUN[fact[Q_QUOTE]]
            if fact[Q_KIND] == Q.STEP_BACK:
                facts += self._end(position, received, move, fact[Q_START], fact[Q_DIRECTION], fact[Q_MOVES],
                                   fact[Q_FURTHEST])
            else:
                self.moves[move] = (fact[Q_START], fact[Q_DIRECTION], fact[Q_FURTHEST], fact[Q_MOVES])
        ended_run = None
        if trade:
            self.last_print = price
            run, name = self.run, SIDE.get(side)
            if name is None:
                if run is not None:
                    run[5] += size
            elif run is not None and run[0] == name:
                run[1], run[2] = run[1] + size, run[2] + 1
                run[6:] = [position, received, price, dict(self.moves)]
            else:
                ended_run = run
                self.run = [name, size, 1, position, 0, 0, position, received, price, dict(self.moves)]
        # the 20-second peak: known at this tick, with the moves as they stood at its high
        for fact in story_facts:
            if fact[F_KIND] == P.BUILD_UP:
                high = fact[F_PEAK]
                if self.rise is None or self.rise[0] != high:
                    raise ValueError(f'position {position}: the peak with its high at {high} became known and the '
                                     f'moves at that high were not held')
                peak = (values[V_SIDE], high, values[V_HIGH_AT], values[V_SIZE], None, None, self.rise[2])
                facts += self._peak(position, received, WINDOW, peak, self.rise[1])
        high = self.story.flow.high
        if high is not None and high[HIGH_POSITION] == position:
            self.rise = (position, dict(self.moves), self.last_print)
        # the peak with no window: the run of trades on one side that this trade ended
        if ended_run is not None:
            name, total, trades, first, _, _, last, last_at, last_price, at_high = ended_run
            facts += self._peak(position, received, NO_WINDOW,
                                (name, last, last_at, float(total), trades, first, last_price), at_high)
        run = self.run
        return (NO_RUN if run is None else (run[0], run[1], run[2], run[3], run[5])) + (len(facts),), facts

    def still_waiting(self) -> list:
        return [(kind, peak[0], peak[1], move, start, held[3])
                for (move, start), peaks in self.waiting.items() for kind, peak, held in peaks]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    calc = TurnPeaks()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, row in ticks:
        values, new = calc.tick(position, *row)
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_waiting()
    if counts is not None:
        counts.update(dict(calc.counts, run_of_trades_still_going_at_the_last_tick=calc.run is not None,
                           lines_waiting_on_a_move_still_going_at_the_last_tick=len(calc.still_waiting())))
