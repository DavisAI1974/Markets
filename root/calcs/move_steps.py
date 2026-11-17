"""ROOT part 2, calculation `move_steps`: every step of every move in price, with what was in play at that tick.

Greg, 2026-11-17: "I'll let you pick one other calc to do with them that you feel will have the biggest impact for
your strategies that we haven't done yet". Claude's pick, stated to him: the question every strategy comes down to
is whether a move that has just taken a step goes on or turns. This writes, for the three moves already followed
with no window (the trade leg, the run of the best bid, the run of the best ask):
- one line at the tick of every step a move takes (its first step, and each new furthest price), with the step's
  number and price, and what was in play once that tick was done: the 20-second flow (bought and sold), the flow
  with no window (the run of trades on one side: its side, size and number of trades), the best bid and best ask
  with the size and the number of orders at each, each side's total size, and the peaks in play;
- one line when the move ends: how many steps it made in all, the price it ended at, and what it gave back.
A step line never says how the move went on: that is on the move's own closing line, written when it is known.

Claude's calls in the build (his to correct): no step is left out and none is named a kind of step; no span of
time is chosen; nothing is ranked or grouped. The run of trades on one side is the one `turn_peaks` writes on
every row. The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root.calcs import in_play
from root.calcs import leg_peaks as LP
from root.calcs import quote_runs as Q
from root.calcs import turn_peaks as T

BOOK = ['best_bid_size', 'best_ask_size', 'best_bid_orders', 'best_ask_orders', 'bid_total_size', 'ask_total_size']
READS = list(in_play.READS) + BOOK
LEG = T.LEG
RUN = T.RUN
STEP, ENDED = 'step', 'ended'
COLUMNS = [('move_step_facts_known', 'How many lines about a step or the end of a move in price became known at '
            'this tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
OWN_COLUMNS = [
    ('known_position', 'The tick of the step, or of the end of the move: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('move', 'Which move: trade leg, run of the best bid, run of the best ask.'),
    ('fact', 'step: the move took a step (its first, or a new furthest price). ended: the move ended at this tick.'),
    ('move_start_position', 'The move: the trade leg\'s first trade, or the tick the run started. A label only.'),
    ('direction', 'Which way the move goes: up or down.'),
    ('step', 'On step: which step of the move this is (1 for its first).'),
    ('price', 'On step: the price the move has reached. On ended: the price the move ended at.'),
    ('steps_in_all', 'On ended: how many steps the move made in all.'),
    ('given_back', 'On ended: the price once this tick is done minus the price the move ended at.'),
    ('flow_bought_20s', 'Size bought by aggressors in the last 20 seconds, this tick included.'),
    ('flow_sold_20s', 'Size sold by aggressors in the last 20 seconds, this tick included.'),
    ('run_side', 'The run of trades on one side in progress (the flow with no window): buy or sell.'),
    ('run_size', 'The size traded in that run so far.'),
    ('run_trades', 'How many trades that run holds so far.'),
    ('best_bid', 'The best bid once this tick is done.'),
    ('best_ask', 'The best ask once this tick is done.'),
    ('best_bid_size', 'Size at the best bid.'),
    ('best_ask_size', 'Size at the best ask.'),
    ('best_bid_orders', 'Number of orders at the best bid.'),
    ('best_ask_orders', 'Number of orders at the best ask.'),
    ('bid_total_size', 'Total size resting on the bid side.'),
    ('ask_total_size', 'Total size resting on the ask side.'),
]
FACT_COLUMNS = OWN_COLUMNS + in_play.PEAK_COLUMNS
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
TABLES = {'facts': (FACT_NAMES, {'move', 'fact', 'direction', 'run_side'} | in_play.PEAK_TEXT, set(), set())}
Q_QUOTE, Q_START, Q_KIND, Q_DIRECTION, Q_FURTHEST, Q_MOVES, Q_BACK = (Q.FACT_NAMES.index(name) for name in (
    'quote', 'run_start_position', 'fact', 'direction', 'furthest_price', 'moves', 'step_back'))
L_KIND, L_FIRST, L_DIRECTION, L_PRICE, L_STEPS, L_BACK = (LP.LEG_FACT_NAMES.index(name) for name in (
    'fact', 'leg_first_trade_position', 'direction', 'price', 'steps', 'step_back'))


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    state, legs, run = in_play.InPlay(), LP.Legs(), None
    facts = [] if tables is None else tables.setdefault('facts', [])
    tally = {f'{move}: {kind}': 0 for move in T.MOVES for kind in (STEP, ENDED)}
    for position, row in ticks:
        received, action, side, size, price, best_bid, best_ask = row[:7]
        run_facts = state.tick(position, *row[:7])
        leg_facts = legs.trade(position, received, price) if action == LP.TRADE else []
        if action == LP.TRADE and side in T.SIDE:
            if run is not None and run[0] == T.SIDE[side]:
                run[1], run[2] = run[1] + size, run[2] + 1
            else:
                run = [T.SIDE[side], size, 1]
        moments = [(RUN[f[Q_QUOTE]], f[Q_KIND] == Q.STEP_BACK, f[Q_START], f[Q_DIRECTION], f[Q_FURTHEST], f[Q_MOVES],
                    f[Q_BACK]) for f in run_facts]
        moments += [(LEG, f[L_KIND] == LP.ENDED, f[L_FIRST], f[L_DIRECTION], f[L_PRICE], f[L_STEPS], f[L_BACK])
                    for f in leg_facts]
        if moments:
            flow = state.peaks.story.flow
            here = (flow.bought, flow.sold) + ((None, None, None) if run is None else tuple(run)) + \
                (best_bid, best_ask) + tuple(row[7:]) + state.peaks_now(received)
            for move, ended, start, direction, at_price, steps, back in moments:
                tally[f'{move}: {ENDED if ended else STEP}'] += 1
                facts.append((position, received, move, ENDED if ended else STEP, start, direction,
                              None if ended else steps, at_price, steps if ended else None,
                              back if ended else None) + here)
        yield position, (len(moments),)
    if counts is not None:
        counts.update(dict(lines=len(facts), lines_by_move_and_kind=tally))
