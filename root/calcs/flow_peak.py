"""ROOT part 2, calculation `flow_peak`: the signed trade flow at every tick, and every exhaustion peak (Step 1).

Laid out for Greg and approved before it was written (markets-data `STEP1_STEP2_LAYOUTS.md`, piece 1, 2026-11-16:
"Yes rewrite", "Yes"). It is the frozen detector of the 2026-08-17 work written again to read the tick rows, with
its caps and limits off; the old program is untouched on its own branch.

What it works out, on every tick of a trade day:
- bought, sold and no-side size traded in the last 20 seconds (the tape's own trade side; a trade the tape gives no
  side for is counted on its own and is in neither figure);
- the flow: bought minus sold, over bought plus sold. Empty when nothing with a side traded in those 20 seconds.
And on the row where a peak becomes known (the first tick at which the size of the flow has come off its high, or
the flow has gone empty): the peak's side and size, the tick of its high, where it stands among the flow so far in
the trade day, how long it had been the highest, and the time since the peak before. Nothing is written back onto
an earlier row, and no peak is held back by a level, a neighbourhood or a gap: those are figures on the row.

The 20 seconds are measured on the received clock (when each trade could be known). The flow starts empty at the
open of each trade day; one `FlowPeak` is one trade day. Ticks reach it only through `tape.for_calculations()`.
The 20-second roll is the one averaging Greg confirmed as his exception; the single trades stay on their own rows.
"""
from __future__ import annotations

import bisect
import collections
from fractions import Fraction

from root.calendar import NS_PER_SECOND

FLOW_SPAN_SECONDS = 20                                 # the span of the flow: the definition, as in the original
FLOW_SPAN_NS = FLOW_SPAN_SECONDS * NS_PER_SECOND
TRADE, BUY, SELL = b'T', b'B', b'A'                    # the tape's codes: a trade; the aggressor bought; sold
BUY_TEXT, SELL_TEXT = 'buy', 'sell'

COLUMNS = [
    ('flow_bought_20s', 'Size bought by aggressors in the last 20 seconds, this tick included.'),
    ('flow_sold_20s', 'Size sold by aggressors in the last 20 seconds, this tick included.'),
    ('flow_no_side_20s', 'Size traded in the last 20 seconds that the tape gives no side for. In neither figure above.'),
    ('flow_20s', 'The flow: bought minus sold, over bought plus sold. Empty when nothing with a side traded.'),
    ('peak_side', 'On the row where a peak becomes known: buy or sell, the side of the flow at its high.'),
    ('peak_size', 'The size of the flow at the high (0 to 1).'),
    ('peak_high_position', 'The tick of the high: its position on the tape. A label only.'),
    ('peak_high_received_time_ns', 'When the tick of the high was received.'),
    ('peak_standing_so_far', 'The share of the time so far in this trade day, while there was a flow, that the flow '
     'was smaller than this peak.'),
    ('peak_highest_for_ns', 'At the high: how long since the flow was last larger than this. When it never was in '
     'this trade day, the time since the first trade of the trade day.'),
    ('peak_highest_since_open', 'Yes when the flow was never larger than this earlier in the trade day.'),
    ('peak_since_previous_peak_ns', 'From the high of the peak before to this high. Empty on the first peak.'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT = {'peak_side'}
YES_NO = {'peak_highest_since_open'}
DECIMALS = {'flow_20s', 'peak_size', 'peak_standing_so_far'}
NO_PEAK = tuple(None for name in NAMES if name.startswith('peak_'))


class Standing:
    """How long the flow has stood at each size so far in the trade day, exactly, in nanoseconds."""

    def __init__(self):
        self.sizes, self.time, self.total = [], [], 0

    def add(self, size: Fraction, ns: int):
        if ns <= 0:
            return
        k = bisect.bisect_left(self.sizes, size)
        if k < len(self.sizes) and self.sizes[k] == size:
            self.time[k] += ns
        else:
            self.sizes.insert(k, size)
            self.time.insert(k, ns)
        self.total += ns

    def below(self, size: Fraction) -> int:
        return sum(self.time[:bisect.bisect_left(self.sizes, size)])


class FlowPeak:
    """One trade day, forward only. `tick()` takes the next tick and gives that tick's values in NAMES order."""

    def __init__(self):
        self.window = collections.deque()              # the trades of the last 20 seconds: (received, side, size)
        self.bought = self.sold = self.no_side = 0
        self.size = None                               # the size of the flow as it stands; None when there is none
        self.since = None                              # when it took that size
        self.standing = Standing()
        self.larger = []                               # sizes still unbeaten, each with when it last ended
        self.first_flow_at = None
        self.last_reading = None                       # the size read at the tick before
        self.high = None                               # a high not yet come off: (size, side, position, received,
        self.previous_high_at = None                   # highest for, highest since open)
        self.last_received = None
        self.counts = collections.Counter()

    def _changed(self, at: int):
        """The traded sizes changed at `at`: close the stretch that just ended and open the next."""
        total = self.bought + self.sold
        size = Fraction(abs(self.bought - self.sold), total) if total else None
        if size == self.size:
            return
        if self.size is not None:
            self.standing.add(self.size, at - self.since)
            self.larger[-1][1] = at
        if size is not None:
            while self.larger and self.larger[-1][0] <= size:
                self.larger.pop()
            self.larger.append([size, at])
            if self.first_flow_at is None:
                self.first_flow_at = at
        self.size, self.since = size, at

    def _drop(self, side, size):
        if side == BUY:
            self.bought -= size
        elif side == SELL:
            self.sold -= size
        else:
            self.no_side -= size

    def tick(self, position: int, received: int, action, side, size: int) -> tuple:
        if self.last_received is not None and received < self.last_received:
            raise ValueError(f'the received time goes backwards at position {position}: the 20 seconds cannot be '
                             f'measured on it')
        self.last_received = received
        # trades older than 20 seconds leave, each at its own moment; one that leaves exactly now is part of this tick
        left_at = None
        while self.window and self.window[0][0] + FLOW_SPAN_NS <= received:
            at = self.window[0][0] + FLOW_SPAN_NS
            if left_at is not None and left_at != at:
                self._changed(left_at)
            self._drop(*self.window.popleft()[1:])
            left_at = at
        if left_at is not None and left_at < received:
            self._changed(left_at)
        if action == TRADE:
            self.window.append((received, side, size))
            self.counts['trades'] += 1
            if side == BUY:
                self.bought += size
            elif side == SELL:
                self.sold += size
            else:
                self.no_side += size
                self.counts['trades the tape gives no side for'] += 1
        self._changed(received)
        self.counts['ticks'] += 1

        reading, peak = self.size, NO_PEAK
        if reading is None:
            if self.high is not None:
                peak = self._known(received)
        else:
            self.counts['ticks with a flow'] += 1
            if self.last_reading is None or reading > self.last_reading:
                beaten = self.larger[-2][1] if len(self.larger) > 1 else None
                self.high = (reading, BUY_TEXT if self.bought > self.sold else SELL_TEXT, position, received,
                             received - (self.first_flow_at if beaten is None else beaten), beaten is None)
            elif reading < self.last_reading and self.high is not None:
                peak = self._known(received)
        self.last_reading = reading
        total = self.bought + self.sold
        flow = (self.bought - self.sold) / total if total else None
        return (self.bought, self.sold, self.no_side, flow) + peak

    def _known(self, now: int) -> tuple:
        """The flow has come off its high: the peak is known now, and is written on this tick's row. Its standing
        counts all the time up to now, the stretch still running included."""
        size, side, position, received, highest_for, since_open = self.high
        if not size:
            raise ValueError(f'a high of no flow at position {position}: not a peak')
        self.high = None
        self.counts['peaks'] += 1
        running = now - self.since if self.size is not None else 0
        total = self.standing.total + running
        below = self.standing.below(size) + (running if self.size is not None and self.size < size else 0)
        standing = below / total if total else None
        gap = None if self.previous_high_at is None else received - self.previous_high_at
        self.previous_high_at = received
        return side, float(size), position, received, standing, highest_for, since_open, gap

    def result(self) -> dict:
        return dict(self.counts, high_still_standing_at_the_last_tick=self.high is not None,
                    different_sizes_of_flow=len(self.standing.sizes))


def calculate(ticks, counts: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, record) in tape
    order and must come from `tape.for_calculations()`. `counts`, when given, receives the counts of the run."""
    calc = FlowPeak()
    for position, record in ticks:
        yield position, calc.tick(position, int(record['ts_recv']), bytes(record['action']), bytes(record['side']),
                                  int(record['size']))
    if counts is not None:
        counts.update(calc.result())
