"""ROOT part 2, calculation `open_stories`: the state at each tick (Step 2, piece B).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece B, 2026-11-16: "Include
all of your pieces"). At any tick, what is in play: which peak stories have not ended yet, on each side. The old
work inferred a rolling state afterwards from letters and model scores; here it is recorded directly.

On every tick of a trade day, for the buy side and for the sell side (the side of the peak, read off the tape):
- how many peak stories are open at this tick;
- how many of those have reached zero and not yet come back;
- the tick of the high of the oldest open one, of the newest open one, and of the largest open one.
"Open" means the peak has become known and its story has not ended, by piece 2's own ending (coming back, or
beaten). These are counts and places on the tape: no average is taken. With no open story on a side its three tick
columns are empty, not zero.

Claude's calls in the build, stated to Greg (his to correct):
- The state is read as it stands once the tick is done: a peak that becomes known at this tick is open on its row;
  a story that ends at this tick is not.
- Oldest and newest go by the tick a peak became known. Of two open peaks of the same size, the largest is the
  one known earlier.
Ticks reach this only through `tape.for_calculations()`.
"""
from __future__ import annotations

from root.calcs import flow_peak
from root.calcs.peak_links import Peaks

SIDES = (flow_peak.BUY_TEXT, flow_peak.SELL_TEXT)
FIGURES = [
    ('open_stories', 'How many {side} peak stories are open at this tick.'),
    ('open_stories_past_zero', 'How many of those have reached zero and not yet come back.'),
    ('oldest_open_high_position', 'The oldest open {side} peak: the tick of its high. Empty when none is open.'),
    ('newest_open_high_position', 'The newest open {side} peak: the tick of its high. Empty when none is open.'),
    ('largest_open_high_position', 'The largest open {side} peak: the tick of its high. Empty when none is open.'),
]
COLUMNS = [(f'{side}_{key}', what.format(side=side)) for side in SIDES for key, what in FIGURES]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()
TABLES = {}                                            # this calculation keeps no table beside the rows


class OpenStories:
    """One trade day, forward only. `tick()` gives that tick's values in NAMES order."""

    def __init__(self):
        self.peaks = Peaks()
        self.values = self._read()
        self.most = dict.fromkeys(SIDES, 0)

    def _read(self) -> tuple:
        out = ()
        for side in SIDES:
            mine = [peak for peak in self.peaks.open.values() if peak.side == side]
            if not mine:
                out += (0, 0, None, None, None)
                continue
            largest = mine[0]
            for peak in mine:
                if peak.size > largest.size:
                    largest = peak
            out += (len(mine), sum(1 for peak in mine if peak.past_zero), mine[0].high, mine[-1].high, largest.high)
        return out

    def tick(self, position, received, action, side, size, price) -> tuple:
        born, ended, zero = self.peaks.tick(position, received, action, side, size, price)
        if born is not None or ended or zero:
            self.values = self._read()
            for k, name in enumerate(SIDES):
                self.most[name] = max(self.most[name], self.values[k * len(FIGURES)])
        return self.values


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, record) in tape
    order and must come from `tape.for_calculations()`."""
    calc = OpenStories()
    for position, record in ticks:
        yield position, calc.tick(position, int(record['ts_recv']), bytes(record['action']), bytes(record['side']),
                                  int(record['size']), int(record['price']))
    if counts is not None:
        counts.update({f'most {side} stories open at one tick': calc.most[side] for side in SIDES},
                      stories_open_at_the_last_tick=len(calc.peaks.open))
