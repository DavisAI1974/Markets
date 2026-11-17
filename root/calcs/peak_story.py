"""ROOT part 2, calculation `peak_story`: what each peak did before and after (Step 1, piece 2).

Laid out for Greg and approved before it was written (markets-data `STEP1_STEP2_LAYOUTS.md`, piece 2 as revised,
2026-11-16: "Build"). His rules for it: no fixed marks ("Let the data be what it is and then we group after we see
how they separate"), and no labels, groups or identifiers in advance. So nothing here is measured against a level,
a length of time or a set of moments picked beforehand, and nothing is given a name for what kind of peak it is.

Every turn in a peak's story is one FACT, recorded at the tick where it becomes known and naming its peak by the
tick of its high. Several peaks are in play at once, so the facts are their own table beside the rows:
- `build-up`: written when the peak becomes known. The low the rise started from: among the ticks after the high
  of the peak before and before this high, the last one at which the flow, taken on this peak's side, was at its
  lowest (no flow counts as zero). After a peak on the other side, that is where that other peak's high ended.
- `new low`: each tick at which the flow, taken on the peak's side, is lower than it has been since the high.
- `reached zero`: the first tick at which that flow is at zero, on the other side, or there is no flow.
- `came back`: the first tick after that at which the flow is on the peak's side again, with how long it was away.
- `beaten`: before reaching zero, the first tick at which the flow is larger than the peak was.
A peak's story ends at `came back` or `beaten`. One that has done neither by the last tick of the trade day is
still open, and is listed in the receipt, not on a row (there is no tick at which that could become known).

Every fact carries the last trade price at its tick and the highest and lowest trade price since the high. The
kinds of fact are kinds of moment, not kinds of peak. Ticks reach this only through `tape.for_calculations()`.
"""
from __future__ import annotations

from fractions import Fraction

from root.calcs import flow_peak
from root.outside import UNDEFINED_PRICE

BUILD_UP, NEW_LOW, REACHED_ZERO, CAME_BACK, BEATEN = 'build-up', 'new low', 'reached zero', 'came back', 'beaten'
KINDS = (BUILD_UP, NEW_LOW, REACHED_ZERO, CAME_BACK, BEATEN)

COLUMNS = [
    ('peak_facts_known', 'How many facts about peaks became known at this tick (they are in the facts table).'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()

FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('peak_high_position', 'Which peak the fact is about: the tick of its high. A label only.'),
    ('fact', 'The kind of moment: build-up, new low, reached zero, came back, beaten.'),
    ('since_high_ns', 'From the high of the peak to this tick.'),
    ('share_of_peak_left', 'The flow at this tick, taken on the peak\'s side, over the size of the peak. Below zero '
     'when the flow is on the other side. Empty when there is no flow.'),
    ('lowest_share_so_far', 'The lowest that share has been since the high, this tick included, until zero is '
     'reached. Empty on build-up.'),
    ('away_ns', 'On came back: from reaching zero to this tick.'),
    ('low_position', 'On build-up: the tick of the low the rise started from. Empty when the trade day opened into '
     'the rise.'),
    ('low_size', 'On build-up: the size of the flow at that low, whichever side it was on. Empty when there was no '
     'flow.'),
    ('low_flow', 'On build-up: the flow at that low, with its sign (bought minus sold, over both).'),
    ('low_to_high_ns', 'On build-up: from that low to the high.'),
    ('low_price', 'On build-up: the last trade price at that low.'),
    ('price_at_high', 'The last trade price at the high.'),
    ('price_now', 'The last trade price at this tick.'),
    ('highest_price_since_high', 'The highest trade price from the tick of the high to this tick.'),
    ('lowest_price_since_high', 'The lowest trade price from the tick of the high to this tick.'),
    ('highest_price_since_zero', 'On came back: the highest trade price from reaching zero to this tick.'),
    ('lowest_price_since_zero', 'On came back: the lowest trade price from reaching zero to this tick.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'fact'}
FACT_DECIMALS = {'share_of_peak_left', 'lowest_share_so_far', 'low_size', 'low_flow'}
OPEN_COLUMNS = ['peak_high_position', 'reached_zero', 'lowest_share_so_far']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, set(), FACT_DECIMALS),
          'open-at-the-end': (OPEN_COLUMNS, set(), {'reached_zero'}, {'lowest_share_so_far'})}
I_HIGH = flow_peak.NAMES.index('peak_high_position')


def higher(a, b):
    return b if a is None else a if b is None else max(a, b)


def lower(a, b):
    return b if a is None else a if b is None else min(a, b)


class Story:
    """One peak being followed."""
    __slots__ = ('high', 'sign', 'size', 'high_at', 'price_at_high', 'lowest', 'top', 'bottom', 'zero_at',
                 'zero_top', 'zero_bottom')

    def __init__(self, high, sign, size, high_at, price_at_high, top, bottom):
        self.high, self.sign, self.size, self.high_at, self.price_at_high = high, sign, size, high_at, price_at_high
        self.lowest, self.top, self.bottom = size, top, bottom
        self.zero_at = self.zero_top = self.zero_bottom = None


class PeakStory:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.flow = flow_peak.FlowPeak()
        self.open = []
        self.price = None              # the last trade price
        self.rising = None             # while a high has not come off: [price at high, top, bottom, the low the
                                       # rise started from, this high's own tick]
        self.ends = None               # over the ticks since the last high: the last tick at which the flow (bought
                                       # minus sold, over both; no flow counts as zero) was lowest, and highest:
                                       # each (flow, position, flow as stored, price, received)
        self.traded = None             # (bought, sold) at the tick before
        self.counts = {kind: 0 for kind in KINDS}

    def tick(self, position: int, received: int, action, side, size: int, price: int) -> tuple:
        before = self.flow.high
        values = self.flow.tick(position, received, action, side, size)
        after = self.flow.high
        bought, sold = self.flow.bought, self.flow.sold
        total = bought + sold
        trade = price if action == flow_peak.TRADE and price != UNDEFINED_PRICE else None
        if trade is not None:
            self.price = trade
            for s in self.open:
                s.top, s.bottom = higher(s.top, trade), lower(s.bottom, trade)
                if s.zero_at is not None:
                    s.zero_top, s.zero_bottom = higher(s.zero_top, trade), lower(s.zero_bottom, trade)
        facts, born = [], None
        ends_before = self.ends                              # the two ends of the flow since the last high, so far
        if values[I_HIGH] is not None:                       # the high that was standing has come off: a peak
            v, sign_text, high, high_at = before[0], before[1], before[2], before[3]
            price_at_high, top, bottom, low, _ = self.rising
            born = Story(high, 1 if sign_text == flow_peak.BUY_TEXT else -1, v, high_at, price_at_high,
                         higher(top, trade), lower(bottom, trade))
            self.open.append(born)
            row = self._fact(born, BUILD_UP, position, received, None, None)
            if low is not None:
                _, low_position, low_flow, low_price, low_received = low
                row[FACT_NAMES.index('low_position')] = low_position
                row[FACT_NAMES.index('low_size')] = None if low_flow is None else abs(low_flow)
                row[FACT_NAMES.index('low_flow')] = low_flow
                row[FACT_NAMES.index('low_to_high_ns')] = high_at - low_received
                row[FACT_NAMES.index('low_price')] = low_price
            facts.append(tuple(row))
        signed = Fraction(bought - sold, total) if total else Fraction(0)          # no flow counts as zero
        here = (signed, position, (bought - sold) / total if total else None, self.price, received)
        if after is not None and after[2] == position:       # a high is set at this tick
            buying = after[1] == flow_peak.BUY_TEXT          # a buy rise starts from the lowest flow since the last
            since = None if ends_before is None else ends_before[0 if buying else 1]       # peak, a sell rise from
            if before is not None and born is None:          # the highest. If the rise was already under way, its
                since = self._lower_end(buying, (self.rising[3], self.rising[4], since))   # earlier ticks count too
            self.rising = [self.price, trade, trade, since, here]
            self.ends = None
        else:
            if after is None:
                self.rising = None
            else:                                            # the high stands: its prices so far
                self.rising[1], self.rising[2] = higher(self.rising[1], trade), lower(self.rising[2], trade)
            if self.ends is None:
                self.ends = [here, here]
            else:                                            # the last tick at the lowest, and at the highest
                if signed <= self.ends[0][0]:
                    self.ends[0] = here
                if signed >= self.ends[1][0]:
                    self.ends[1] = here

        if (bought, sold) != self.traded or born is not None:
            still = []
            for s in self.open:
                if (bought, sold) == self.traded and s is not born:
                    still.append(s)
                    continue
                now = Fraction(s.sign * (bought - sold), total) if total else None
                share = None if now is None else now / s.size
                if s.zero_at is None:
                    if now is None or now <= 0:
                        s.zero_at, s.zero_top, s.zero_bottom = received, trade, trade
                        facts.append(tuple(self._fact(s, REACHED_ZERO, position, received, share, s.lowest)))
                    elif now > s.size:
                        facts.append(tuple(self._fact(s, BEATEN, position, received, share, s.lowest)))
                        continue
                    elif now < s.lowest:
                        s.lowest = now
                        facts.append(tuple(self._fact(s, NEW_LOW, position, received, share, s.lowest)))
                elif now is not None and now > 0:
                    row = self._fact(s, CAME_BACK, position, received, share, None)
                    row[FACT_NAMES.index('away_ns')] = received - s.zero_at
                    row[FACT_NAMES.index('highest_price_since_zero')] = s.zero_top
                    row[FACT_NAMES.index('lowest_price_since_zero')] = s.zero_bottom
                    facts.append(tuple(row))
                    continue
                still.append(s)
            self.open = still
        self.traded = (bought, sold)
        return values, (len(facts),), facts

    @staticmethod
    def _lower_end(buying: bool, moments):
        """Of some moments in time order, the last one at which the flow was lowest on the rise's own side."""
        best = None
        for moment in moments:
            if moment is not None and (best is None or (moment[0] <= best[0] if buying else moment[0] >= best[0])):
                best = moment
        return best

    def _fact(self, s: Story, kind: str, position: int, received: int, share, lowest) -> list:
        self.counts[kind] += 1
        row = [None] * len(FACT_NAMES)
        for name, value in (('known_position', position), ('known_received_time_ns', received),
                            ('peak_high_position', s.high), ('fact', kind), ('since_high_ns', received - s.high_at),
                            ('share_of_peak_left', None if share is None else float(share)),
                            ('lowest_share_so_far', None if lowest is None else float(lowest / s.size)),
                            ('price_at_high', s.price_at_high), ('price_now', self.price),
                            ('highest_price_since_high', s.top), ('lowest_price_since_high', s.bottom)):
            row[FACT_NAMES.index(name)] = value
        return row

    def still_open(self) -> list:
        """The peaks whose story has not ended, as they stand: (the tick of the high, reached zero or not, the
        lowest share so far)."""
        return [(s.high, s.zero_at is not None, float(s.lowest / s.size)) for s in self.open]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, record) in tape
    order and must come from `tape.for_calculations()`. `tables`, when given, receives the facts and the peaks
    still open at the last tick; `counts` the counts of the run."""
    calc = PeakStory()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, record in ticks:
        _, values, new = calc.tick(position, int(record['ts_recv']), bytes(record['action']), bytes(record['side']),
                                   int(record['size']), int(record['price']))
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_open()
    if counts is not None:
        counts.update(dict(facts=calc.counts, peaks=calc.flow.counts['peaks'],
                           peaks_still_open_at_the_last_tick=len(calc.open)))
