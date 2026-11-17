"""ROOT part 2, calculation `outside_changes`: what was in play when an outside figure changed (addition O).

Approved by Greg, 2026-11-16 ("Try them all"; laid out in markets-data `STEP1_STEP2_LAYOUTS.md`, "Additions from
the look at Codex's two pieces", O). When one of the 13 outside data points changes inside a trade day: what the
flow and the quote were doing at that tick. What they did next is read from the rows and facts that follow; it is
not copied onto this line.

One FACT for every outside column whose value on a row differs from the row before it in the trade day: which
column, its value before and now, the time the new value became known, and what is in play at that tick (the
peaks, as `quote_peaks` writes them, and the run of the quote in progress on each side, as `quote_runs` writes it).

Claude's calls in the build, stated to Greg (his to correct):
- Only the outside figures that are pinned "as known at the tick" are followed. The once-per-trade-day figures
  (the forecast, the sessions since expiry) cannot change inside a trade day.
- The first tick of a trade day has no row before it inside the trade day, so nothing is written for it.
- A figure made of several columns (a report, the curve's shape) gives one line for each column that changed.
  When a new reading became known with the same value as the one before, the line is for its "known from" column,
  so nothing that became known is missed.
- Values are written as words, digit for digit, because the columns are of different kinds; the kind is beside
  them. An empty value is empty.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root import pin
from root.calcs import in_play

GROUPS = [(group['known'], [field[0] for field in group['fields']], {field[0]: field[2] for field in
                                                                    group['fields']}) for group in pin.AS_OF]
OUTSIDE = [column for known, fields, _ in GROUPS for column in [known] + fields]
KIND = {column: kind for _, _, kinds in GROUPS for column, kind in kinds.items()}
KNOWN_FROM = {column: known for known, fields, _ in GROUPS for column in [known] + fields}
TIME = 'time in nanoseconds'
READS = list(in_play.READS) + OUTSIDE
FIRST_OUTSIDE = len(in_play.READS)
COLUMNS = [('outside_change_facts_known', 'How many facts about an outside figure changing became known at this '
            'tick (they are in the facts table).')]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: the first tick whose row carries the new value. '
     'A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('figure', 'The outside column that changed, by its name on the row.'),
    ('kind', 'What kind of value it holds: text, whole number, decimal, or a time in nanoseconds.'),
    ('value_before', 'Its value on the row before, written out digit for digit. Empty when it was empty.'),
    ('value_now', 'Its value on this row, written out digit for digit. Empty when it is empty.'),
    ('known_from_ns', 'When the value now on the row became known (its figure\'s own "known from" time).'),
] + in_play.PEAK_COLUMNS + in_play.RUN_COLUMNS
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
TABLES = {'facts': (FACT_NAMES, {'figure', 'kind', 'value_before', 'value_now'} | in_play.PEAK_TEXT |
                    in_play.RUN_TEXT, set(), set())}


def words(value):
    return None if value is None else repr(value) if isinstance(value, float) else str(value)


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, the row's values
    in READS order) in tape order and must come from `tape.rows_for_calculations()`."""
    state = in_play.InPlay()
    facts = [] if tables is None else tables.setdefault('facts', [])
    before, by_figure = None, {}
    where = {column: k for k, column in enumerate(OUTSIDE)}
    for position, row in ticks:
        state.tick(position, *row[:FIRST_OUTSIDE])
        now, new = row[FIRST_OUTSIDE:], 0
        if before is not None and now != before:
            in_play_now = state.peaks_now(row[0]) + state.runs_now()
            for k, column in enumerate(OUTSIDE):
                if now[k] != before[k]:
                    facts.append((position, row[0], column, KIND.get(column, TIME), words(before[k]), words(now[k]),
                                  now[where[KNOWN_FROM[column]]]) + in_play_now)
                    by_figure[column] = by_figure.get(column, 0) + 1
                    new += 1
        before = now
        yield position, (new,)
    if counts is not None:
        counts.update(dict(facts=sum(by_figure.values()), facts_by_figure=dict(sorted(by_figure.items())),
                           outside_columns_followed=len(OUTSIDE)))
