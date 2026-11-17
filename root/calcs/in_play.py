"""ROOT part 2: what is in play at a tick, for the pieces that lay one thing against another (Step 2, pieces I and
O). Not a calculation by itself: it writes no file. It follows, from the stored rows, the peaks (pieces 1 and 2,
by their own code) and the runs of the quote (piece I's first part, by its own code), and says how they stand once
a tick is done:
- for buy peaks and for sell peaks: the peak most lately known on that side (the tick of its high), the time since
  that high, and where its story stands: open, past zero (it has reached zero and not come back), or ended;
- the rise under way, if the flow has a high that has not come off yet: its side, the tick of the high so far, and
  the time since it. It is not a peak yet and may never be the peak's own high;
- the run in progress of the best bid and of the best ask, exactly as `quote_runs` writes it on every row.
The words for where a story stands are where one peak's story stands at one tick, not kinds of peak.
The rows reach this only through `tape.rows_for_calculations()`.
"""
from __future__ import annotations

from root.calcs import flow_peak
from root.calcs import peak_links as L
from root.calcs import quote_runs as Q

READS = ['received_time_ns', 'action', 'side', 'size', 'price', 'best_bid', 'best_ask']
OPEN, PAST_ZERO, ENDED = 'open', 'past zero', 'ended'
SIDES = (flow_peak.BUY_TEXT, flow_peak.SELL_TEXT)
PEAK_COLUMNS = [(f'{side}_peak_{key}', what.format(side=side)) for side in SIDES for key, what in (
    ('high_position', 'The {side} peak most lately known at this tick: the tick of its high. A label only. Empty '
     'when no {side} peak has become known yet in the trade day.'),
    ('since_high_ns', 'From that high to this tick.'),
    ('story', 'Where that peak\'s story stands once this tick is done: open, past zero, or ended.'))] + [
    ('rise_side', 'The rise under way at this tick, if the flow has a high that has not come off yet: buy or sell. '
     'Empty when there is none.'),
    ('rise_high_position', 'The tick of that rise\'s high so far. A label only. It is not a peak yet.'),
    ('rise_since_high_ns', 'From that high so far to this tick.')]
PEAK_NAMES = [name for name, _ in PEAK_COLUMNS]
PEAK_TEXT = {name for name in PEAK_NAMES if name.endswith('_story') or name == 'rise_side'}
RUN_COLUMNS = Q.COLUMNS[:-1]                           # the run in progress on each side, as quote_runs writes it
RUN_NAMES = [name for name, _ in RUN_COLUMNS]
RUN_TEXT = set(Q.TEXT)
HIGH_SIDE, HIGH_POSITION, HIGH_AT = 1, 2, 3            # where these sit in the flow calculation's standing high


class InPlay:
    """One trade day, forward only, from the stored rows. `tick()` gives the facts about runs of the quote that
    became known at this tick; `peaks_now()` and `runs_now()` say how things stand once the tick is done."""

    def __init__(self):
        self.peaks, self.runs = L.Peaks(), Q.QuoteRuns()
        self.last, self.run_values = {}, None

    def tick(self, position, received, action, side, size, price, best_bid, best_ask) -> list:
        born, _, _ = self.peaks.tick(position, received, (action or '').encode(), (side or '').encode(), size, price)
        if born is not None:
            self.last[born.side] = born
        values, facts = self.runs.tick(position, received, best_bid, best_ask)
        self.run_values = values[:-1]
        return facts

    def peaks_now(self, received) -> tuple:
        out = ()
        for side in SIDES:
            peak = self.last.get(side)
            if peak is None:
                out += (None, None, None)
            else:
                still = self.peaks.open.get(peak.high)
                out += (peak.high, received - peak.high_at,
                        ENDED if still is None else PAST_ZERO if still.past_zero else OPEN)
        high = self.peaks.story.flow.high
        return out + ((None, None, None) if high is None else
                      (high[HIGH_SIDE], high[HIGH_POSITION], received - high[HIGH_AT]))

    def runs_now(self) -> tuple:
        return self.run_values
