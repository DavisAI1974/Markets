"""ROOT part 2, calculation `quote_peaks`: the peaks in play at every turn of a run of the quote (Step 2, piece I,
the lines that name peaks).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece I, 2026-11-16: "Include
all of your pieces"). The first part of I (`quote_runs`) writes every turn of a run of the best bid and of the best
ask. This lays the flow against them: one FACT for every such turn, at the same tick, naming the run and carrying
the peaks in play: the buy peak and the sell peak most lately known (the tick of its high, the time since it, where
its story stands), and the rise under way if the flow has a high that has not come off.

The other direction needs no new calculation (nothing is stated twice): on the tick of any fact about a peak, the
run of the quote in progress on each side is already on that row, written there by `quote_runs`.

Claude's calls in the build, stated to Greg (his to correct):
- "The nearest peak on each side" is the one most lately known on that side, as in piece A.
- Where a story stands is read once the tick is done, as in pieces A and B.
- The print legs are not here: they wait on Greg's answer about trade days Oct 2 and Oct 17.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root.calcs import in_play
from root.calcs import quote_runs as Q

READS = list(in_play.READS)
COLUMNS = [('quote_peak_facts_known', 'How many facts laying the peaks against a turn of a run of the quote '
            'became known at this tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
RUN_KEYS = ['known_position', 'known_received_time_ns', 'quote', 'run_start_position', 'fact']
FACT_COLUMNS = [(name, what) for name, what in Q.FACT_COLUMNS if name in RUN_KEYS] + in_play.PEAK_COLUMNS
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
TABLES = {'facts': (FACT_NAMES, {'quote', 'fact'} | in_play.PEAK_TEXT, set(), set())}
PICK = [Q.FACT_NAMES.index(name) for name in RUN_KEYS]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    state = in_play.InPlay()
    facts = [] if tables is None else tables.setdefault('facts', [])
    lines = 0
    for position, row in ticks:
        turns = state.tick(position, *row)
        if turns:
            now = state.peaks_now(row[0])
            facts.extend(tuple(turn[k] for k in PICK) + now for turn in turns)
            lines += len(turns)
        yield position, (len(turns),)
    if counts is not None:
        counts.update(dict(facts=lines))
