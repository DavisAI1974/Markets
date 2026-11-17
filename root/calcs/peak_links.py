"""ROOT part 2, calculation `peak_links`: how each peak stands to the peaks around it (Step 2, piece A).

Laid out for Greg and approved before it was written (markets-data `STEP2_PLAN.md`, piece A, 2026-11-16: "Include
all of your pieces"). This is the chain, written as facts, without letters and without a depth. No peak is left
out for being close to another or for overlapping one: overlap is a fact.

Two kinds of FACT, each recorded at the tick it becomes known and naming its peak by the tick of its high:
- `peak known`, at the tick a peak becomes known: the last peak before it on its own side, and the last one on the
  other side. For each: the tick of its high, the time between the two highs, the last trade price at its high,
  and whether its story was still open. And "the peak before" (the one most lately known, which is the nearer of
  those two), with same side or not. Any earlier peak is reached by following these links back one at a time, so
  nothing is capped and nothing is repeated.
- `story ended`, at the tick a peak's story ends (came back, or beaten): how many later peaks became known while
  its story was open, and the first of them.
A peak whose story has not ended at the last tick of the trade day is listed in its own small file with the same
two figures so far. A link never crosses 6 pm: the first peak of a trade day on a side has that link empty, and
the fact says why.

Claude's calls in the build, stated to Greg (his to correct):
- "Before" goes by the tick a peak became known (the order a reader meets them in).
- "Still open at this tick" is read as the stories stand once the tick is done. A story that ends on the very tick
  a later peak becomes known is not open for that peak, and that peak is not counted among its later ones.
- The peaks and their stories are worked out here again by the same code as pieces 1 and 2 (the calculation holds
  a `PeakStory`), not read from their stored files, so that the playback of this piece covers all of it.
Ticks reach this only through `tape.for_calculations()`.
"""
from __future__ import annotations

from root.calcs import flow_peak
from root.calcs import peak_story as P

KNOWN, ENDED = 'peak known', 'story ended'
KINDS = (KNOWN, ENDED)
NO_SAME = 'no earlier peak on its own side in this trade day'
NO_OTHER = 'no earlier peak on the other side in this trade day'

COLUMNS = [
    ('peak_link_facts_known', 'How many facts about the links between peaks became known at this tick (they are in '
     'the facts table).'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()

FACT_COLUMNS = [
    ('known_position', 'The tick at which this fact became known: its position on the tape. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('peak_high_position', 'Which peak the fact is about: the tick of its high. A label only.'),
    ('fact', 'The kind of moment: peak known, story ended.'),
    ('side', 'The side of the peak: buy or sell, read off the tape.'),
    ('price_at_high', 'The last trade price at the peak\'s high.'),
    ('same_side_high_position', 'On peak known: the last peak before it on its own side (the tick of its high).'),
    ('same_side_high_to_high_ns', 'From that peak\'s high to this peak\'s high.'),
    ('same_side_price_at_high', 'The last trade price at that peak\'s high.'),
    ('same_side_story_open', 'Yes when that peak\'s story was still open once this tick was done.'),
    ('other_side_high_position', 'On peak known: the last peak before it on the other side (the tick of its high).'),
    ('other_side_high_to_high_ns', 'From that peak\'s high to this peak\'s high.'),
    ('other_side_price_at_high', 'The last trade price at that peak\'s high.'),
    ('other_side_story_open', 'Yes when that peak\'s story was still open once this tick was done.'),
    ('before_high_position', 'On peak known: the peak before, the one most lately known (the tick of its high).'),
    ('before_same_side', 'Yes when the peak before is on the same side as this peak.'),
    ('no_link_because', 'On peak known: why a link is empty. Empty when both links are there.'),
    ('ended_by', 'On story ended: the moment that ended the story (came back, or beaten).'),
    ('later_peaks_while_open', 'On story ended: how many later peaks became known while this story was open.'),
    ('first_later_high_position', 'On story ended: the first of those later peaks (the tick of its high).'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'fact', 'side', 'no_link_because', 'ended_by'}
FACT_YES_NO = {'same_side_story_open', 'other_side_story_open', 'before_same_side'}
OPEN_COLUMNS = ['peak_high_position', 'later_peaks_so_far', 'first_later_high_position']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, FACT_YES_NO, set()),
          'open-at-the-end': (OPEN_COLUMNS, set(), set(), set())}
I_SIDE, I_SIZE = flow_peak.NAMES.index('peak_side'), flow_peak.NAMES.index('peak_size')
I_HIGH_AT = flow_peak.NAMES.index('peak_high_received_time_ns')
F_KIND, F_PEAK = P.FACT_NAMES.index('fact'), P.FACT_NAMES.index('peak_high_position')
F_PRICE = P.FACT_NAMES.index('price_at_high')


class Peak:
    """One peak, from the tick it became known."""
    __slots__ = ('high', 'side', 'size', 'high_at', 'price_at_high', 'past_zero', 'later', 'first_later')

    def __init__(self, high, side, size, high_at, price_at_high):
        self.high, self.side, self.size, self.high_at, self.price_at_high = high, side, size, high_at, price_at_high
        self.past_zero, self.later, self.first_later = False, 0, None


class Peaks:
    """The peaks of one trade day as they stand at each tick, read from the facts of piece 2 as they become known.
    `open` holds the peaks whose stories have not ended, in the order they became known."""

    def __init__(self):
        self.story = P.PeakStory()
        self.open = {}

    def tick(self, position, received, action, side, size, price) -> tuple:
        """(the peak that became known at this tick or None, the peaks whose stories ended with how each ended,
        whether any open story reached zero)."""
        values, _, facts = self.story.tick(position, received, action, side, size, price)
        born, ended, zero = None, [], False
        for fact in facts:
            kind, high = fact[F_KIND], fact[F_PEAK]
            if kind == P.BUILD_UP:
                born = self.open[high] = Peak(high, values[I_SIDE], values[I_SIZE], values[I_HIGH_AT], fact[F_PRICE])
            elif kind == P.REACHED_ZERO:
                self.open[high].past_zero = zero = True
            elif kind in (P.CAME_BACK, P.BEATEN):
                ended.append((self.open.pop(high), kind))
        return born, ended, zero


class PeakLinks:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the facts that became known)."""

    def __init__(self):
        self.peaks = Peaks()
        self.last = {}                                 # side -> the peak most lately known on that side
        self.before = None                             # the peak most lately known
        self.counts = dict.fromkeys(KINDS, 0)
        self.most_later = 0

    def _line(self, kind, peak: Peak, position, received) -> dict:
        self.counts[kind] += 1
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, peak_high_position=peak.high, fact=kind,
                   side=peak.side, price_at_high=peak.price_at_high)
        return row

    def tick(self, position, received, action, side, size, price) -> tuple:
        born, ended, _ = self.peaks.tick(position, received, action, side, size, price)
        facts = []
        if born is not None:                           # every story still open has one more later peak
            for peak in self.peaks.open.values():
                if peak is not born:
                    peak.later += 1
                    if peak.first_later is None:
                        peak.first_later = born.high
        for peak, how in ended:
            row = self._line(ENDED, peak, position, received)
            row.update(ended_by=how, later_peaks_while_open=peak.later, first_later_high_position=peak.first_later)
            self.most_later = max(self.most_later, peak.later)
            facts.append(tuple(row[name] for name in FACT_NAMES))
        if born is not None:
            row, missing = self._line(KNOWN, born, position, received), []
            for key, earlier, why in (('same_side', self.last.get(born.side), NO_SAME),
                                      ('other_side', self._other(born.side), NO_OTHER)):
                if earlier is None:
                    missing.append(why)
                    continue
                row[f'{key}_high_position'] = earlier.high
                row[f'{key}_high_to_high_ns'] = born.high_at - earlier.high_at
                row[f'{key}_price_at_high'] = earlier.price_at_high
                row[f'{key}_story_open'] = earlier.high in self.peaks.open
            if self.before is not None:
                row.update(before_high_position=self.before.high, before_same_side=self.before.side == born.side)
            row['no_link_because'] = '; '.join(missing) if missing else None
            facts.append(tuple(row[name] for name in FACT_NAMES))
            self.last[born.side] = self.before = born
        return (len(facts),), facts

    def _other(self, side):
        return self.last.get(flow_peak.SELL_TEXT if side == flow_peak.BUY_TEXT else flow_peak.BUY_TEXT)

    def still_open(self) -> list:
        """The peaks whose stories have not ended, as they stand, in OPEN_COLUMNS order."""
        return [(peak.high, peak.later, peak.first_later) for peak in self.peaks.open.values()]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, record) in tape
    order and must come from `tape.for_calculations()`. `tables`, when given, receives the facts and the peaks
    still open at the last tick; `counts` the counts of the run."""
    calc = PeakLinks()
    facts = [] if tables is None else tables.setdefault('facts', [])
    for position, record in ticks:
        values, new = calc.tick(position, int(record['ts_recv']), bytes(record['action']), bytes(record['side']),
                                int(record['size']), int(record['price']))
        facts.extend(new)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_open()
    if counts is not None:
        counts.update(dict(facts=calc.counts, most_later_peaks_while_one_story_was_open=calc.most_later,
                           peaks_still_open_at_the_last_tick=len(calc.peaks.open)))
