"""ROOT part 2, calculation `chain_peaks`: what each peak did, on one line, and the ended peaks before it (the
chain link models, first part; Step 1, piece 4).

Laid out for Greg and approved before it was written (markets-data `STEP1_STEP2_LAYOUTS.md`, piece 4: "Let it
produce full values", "Do it"). The chain link models ask how much knowing the peaks before a peak helps say what
that peak did. This calculation writes the two things they read, and nothing else; it holds no model.

Two kinds of line, each at the tick it becomes known:
- a PEAK LINE, at the tick a peak's story ends (came back, or beaten): what the peak did, taken from pieces 1 and
  2 with no fixed moment. Its size; the time from the low its rise started from to its high; how its story ended;
  how long that took from the high; how far it faded (the lowest the flow went on the peak's side, as a share of
  the peak, from the high to the end of the story: below zero when the flow crossed to the other side); how many
  steps down it took before reaching zero; the price at the high and at the end, the highest and lowest trade
  price between them, and the three moves those give with the peak's side counted as forward; and whether the
  peak before it was on the same side. Both clocks are on the line: the tick the peak became known, and this tick.
- a BEFORE LINE, at the tick a peak becomes known: one for each of the nearest peaks before it whose stories had
  ALREADY ENDED by that tick, counted back one step at a time. Only those can be used to say anything about the
  new peak, because only their lines exist yet.
A peak whose story has not ended at the last tick of the trade day has no peak line: it is listed in its own
small file. Nothing is thinned and no peak is left out.

Claude's calls in the build, stated to Greg (his to correct):
- "The peaks before" go by the tick a peak became known, as in piece A, and count only peaks whose stories had
  ended. A story that ends on the very tick a peak becomes known counts as ended for that peak (piece A's call).
- "How far it faded" is one figure for both endings, so it is never empty: for a beaten peak the lowest share
  before it was beaten (above zero); for one that came back, the lowest the flow went while it was away (zero or
  below; no flow counts as zero).
- The three price moves are distances in the tape's own price units from the price at the high. With no trade
  between the high and the end they are zero: the price did not move. The highest and lowest price stay empty then.
- The before lines are written for the first six steps back (`STEPS_BACK`), the six put to Greg. That is how many
  are written out now, not a cap on the chain: every peak line carries the tick the peak became known and the tick
  its story ended, so any further step back follows by the same rule, and the line says how many ended peaks there
  were before it in all.
The peaks and their stories are worked out here again by the same code as pieces 1 and 2 (the calculation holds a
`PeakStory`), not read from their stored files, so that the playback of this piece covers all of it.
Ticks reach this only through `tape.for_calculations()`.
"""
from __future__ import annotations

import bisect
from fractions import Fraction

from root.calcs import flow_peak
from root.calcs import peak_story as P

STEPS_BACK = 6                                         # how many steps back are written out now (see above)
COLUMNS = [
    ('chain_peak_lines_known', 'How many peak lines became known at this tick: peaks whose stories ended here (they '
     'are in the facts table).'),
    ('chain_before_lines_known', 'How many before lines became known at this tick: the ended peaks before a peak '
     'that became known here (they are in the before table).'),
]
NAMES = [name for name, _ in COLUMNS]
TEXT, YES_NO, DECIMALS = set(), set(), set()

FACT_COLUMNS = [
    ('known_position', 'The tick at which this line became known: the tick the peak\'s story ended. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('peak_high_position', 'Which peak the line is about: the tick of its high. A label only.'),
    ('peak_high_received_time_ns', 'When the tick of the high was received.'),
    ('peak_known_position', 'The tick at which the peak became known. A label only.'),
    ('peak_known_received_time_ns', 'When that tick was received.'),
    ('side', 'The side of the peak: buy or sell, read off the tape.'),
    ('size', 'The size of the flow at the high (0 to 1).'),
    ('low_to_high_ns', 'From the low the rise started from to the high. Empty when piece 2 has no low for it.'),
    ('ended_by', 'How the story ended: came back, or beaten.'),
    ('high_to_end_ns', 'From the high to the tick the story ended.'),
    ('lowest_share', 'How far it faded: the lowest the flow went on the peak\'s side, over the size of the peak, '
     'from the high to the end of the story. Zero or below when the flow reached zero or crossed (no flow counts '
     'as zero).'),
    ('steps_down', 'How many times the flow set a new low on the way down, before reaching zero or being beaten.'),
    ('price_at_high', 'The last trade price at the high.'),
    ('price_at_end', 'The last trade price at the tick the story ended.'),
    ('highest_price_since_high', 'The highest trade price from the high to the end. Empty when no trade came.'),
    ('lowest_price_since_high', 'The lowest trade price from the high to the end. Empty when no trade came.'),
    ('price_move_with_side', 'The price at the end less the price at the high, with the peak\'s side counted as '
     'forward (up for a buy peak, down for a sell peak). The tape\'s own price units.'),
    ('furthest_price_with_side', 'The furthest the trade price went forward from the price at the high, on the '
     'way. Zero when it never did.'),
    ('furthest_price_against_side', 'The furthest the trade price went the other way from the price at the high, '
     'on the way. Zero when it never did.'),
    ('before_high_position', 'The peak before: the one most lately known when this peak became known, whether its '
     'story had ended or not (the tick of its high). Empty on the first peak of the trade day.'),
    ('same_side_as_peak_before', 'Yes when that peak is on the same side as this one.'),
    ('ended_peaks_before', 'How many peaks of the trade day had stories that had ended when this peak became '
     'known.'),
]
FACT_NAMES = [name for name, _ in FACT_COLUMNS]
FACT_TEXT = {'side', 'ended_by'}
FACT_YES_NO = {'same_side_as_peak_before'}
FACT_DECIMALS = {'size', 'lowest_share'}
BEFORE_COLUMNS = [
    ('known_position', 'The tick at which this line became known: the tick the peak became known. A label only.'),
    ('known_received_time_ns', 'When that tick was received.'),
    ('peak_high_position', 'Which peak the line is about: the tick of its high. A label only.'),
    ('steps_back', 'How many steps back this earlier peak is, among the peaks whose stories had ended: 1 is the '
     'nearest.'),
    ('earlier_high_position', 'The earlier peak: the tick of its high. A label only.'),
    ('earlier_known_position', 'The tick at which the earlier peak became known. A label only.'),
    ('earlier_ended_position', 'The tick at which the earlier peak\'s story ended: at or before this line\'s tick. '
     'A label only.'),
]
BEFORE_NAMES = [name for name, _ in BEFORE_COLUMNS]
OPEN_COLUMNS = ['peak_high_position', 'peak_known_position']
TABLES = {'facts': (FACT_NAMES, FACT_TEXT, FACT_YES_NO, FACT_DECIMALS),
          'before': (BEFORE_NAMES, set(), set(), set()),
          'open-at-the-end': (OPEN_COLUMNS, set(), set(), set())}
I_SIDE, I_SIZE = flow_peak.NAMES.index('peak_side'), flow_peak.NAMES.index('peak_size')
I_HIGH, I_HIGH_AT = flow_peak.NAMES.index('peak_high_position'), flow_peak.NAMES.index('peak_high_received_time_ns')
F = {name: k for k, name in enumerate(P.FACT_NAMES)}


class Peak:
    """One peak, from the tick it became known to the tick its story ends."""
    __slots__ = ('high', 'high_at', 'known', 'known_at', 'side', 'forward', 'size', 'exact_size', 'price_at_high',
                 'low_to_high', 'steps', 'past_zero', 'lowest', 'before', 'same_side', 'ended_before')


class ChainPeaks:
    """One trade day, forward only. `tick()` gives (values in NAMES order, the peak lines, the before lines)."""

    def __init__(self):
        self.story = P.PeakStory()
        self.open = {}                                 # the tick of the high -> the peak, while its story is open
        self.ended = []                                # the peaks whose stories have ended, in the order they became
        self.last = None                               # known: (known, high, ended); and the peak most lately known
        self.traded = None                             # (bought, sold) at the tick before
        self.counts = dict(peak_lines=0, before_lines=0, came_back=0, beaten=0,
                           peaks_with_fewer_ended_peaks_before_than_steps_written=0,
                           lines_with_no_low_to_high=0, lines_with_no_peak_before=0,
                           lines_with_no_trade_between_high_and_end=0, lines_with_no_price_at_high=0)

    def tick(self, position, received, action, side, size, price) -> tuple:
        standing = self.story.flow.high
        values, _, facts = self.story.tick(position, received, action, side, size, price)
        bought, sold = self.story.flow.bought, self.story.flow.sold
        changed = (bought, sold) != self.traded
        self.traded = (bought, sold)
        born, ended, lines, before = None, [], [], []
        for fact in facts:
            kind, high = fact[F['fact']], fact[F['peak_high_position']]
            if kind == P.BUILD_UP:
                born = self.open[high] = self._born(values, standing[0], position, received, fact)
            elif kind == P.NEW_LOW:
                self.open[high].steps += 1
            elif kind == P.REACHED_ZERO:
                self.open[high].past_zero = True
            else:                                      # came back, or beaten: the story ends at this tick
                ended.append((self.open.pop(high), kind, fact))
        if changed or born is not None:                # how low the flow goes on a peak's side while it is away
            total = bought + sold
            for peak in self.open.values():
                if peak.past_zero:
                    now = Fraction(peak.forward * (bought - sold), total) if total else Fraction(0)
                    peak.lowest = now if peak.lowest is None else min(peak.lowest, now)
        for peak, kind, fact in ended:
            lines.append(self._line(peak, kind, fact, position, received))
            bisect.insort(self.ended, (peak.known, peak.high, position))
        if born is not None:                           # the ended peaks before it, as the stories stand once the
            born.ended_before = len(self.ended)        # tick is done
            if born.ended_before < STEPS_BACK:
                self.counts['peaks_with_fewer_ended_peaks_before_than_steps_written'] += 1
            for step, (known, high, ended_at) in enumerate(reversed(self.ended[-STEPS_BACK:]), 1):
                before.append((position, received, born.high, step, high, known, ended_at))
            self.counts['before_lines'] += len(before)
        return (len(lines), len(before)), lines, before

    def _born(self, values, exact_size, position, received, fact) -> Peak:
        peak = Peak()
        peak.high, peak.high_at, peak.known, peak.known_at = values[I_HIGH], values[I_HIGH_AT], position, received
        peak.side, peak.size, peak.exact_size = values[I_SIDE], values[I_SIZE], exact_size
        peak.forward = 1 if peak.side == flow_peak.BUY_TEXT else -1
        peak.price_at_high, peak.low_to_high = fact[F['price_at_high']], fact[F['low_to_high_ns']]
        peak.steps, peak.past_zero, peak.lowest = 0, False, None
        peak.before = None if self.last is None else self.last.high
        peak.same_side = None if self.last is None else self.last.side == peak.side
        peak.ended_before = None
        self.last = peak
        return peak

    def _line(self, peak: Peak, kind, fact, position, received) -> tuple:
        self.counts['peak_lines'] += 1
        self.counts['came_back' if kind == P.CAME_BACK else 'beaten'] += 1
        lowest = (float(peak.lowest / peak.exact_size) if kind == P.CAME_BACK else fact[F['lowest_share_so_far']])
        at_high, at_end = peak.price_at_high, fact[F['price_now']]
        top, bottom = fact[F['highest_price_since_high']], fact[F['lowest_price_since_high']]
        move = with_side = against = None
        if at_high is not None:
            up = 0 if top is None else max(top - at_high, 0)
            down = 0 if bottom is None else max(at_high - bottom, 0)
            move = peak.forward * (at_end - at_high)
            with_side, against = (up, down) if peak.forward > 0 else (down, up)
        else:
            self.counts['lines_with_no_price_at_high'] += 1
        self.counts['lines_with_no_low_to_high'] += peak.low_to_high is None
        self.counts['lines_with_no_peak_before'] += peak.before is None
        self.counts['lines_with_no_trade_between_high_and_end'] += top is None
        row = dict.fromkeys(FACT_NAMES)
        row.update(known_position=position, known_received_time_ns=received, peak_high_position=peak.high,
                   peak_high_received_time_ns=peak.high_at, peak_known_position=peak.known,
                   peak_known_received_time_ns=peak.known_at, side=peak.side, size=peak.size,
                   low_to_high_ns=peak.low_to_high, ended_by=kind, high_to_end_ns=fact[F['since_high_ns']],
                   lowest_share=lowest, steps_down=peak.steps, price_at_high=at_high, price_at_end=at_end,
                   highest_price_since_high=top, lowest_price_since_high=bottom, price_move_with_side=move,
                   furthest_price_with_side=with_side, furthest_price_against_side=against,
                   before_high_position=peak.before, same_side_as_peak_before=peak.same_side,
                   ended_peaks_before=peak.ended_before)
        return tuple(row[name] for name in FACT_NAMES)

    def still_open(self) -> list:
        """The peaks whose stories have not ended, in OPEN_COLUMNS order."""
        return [(peak.high, peak.known) for peak in self.open.values()]


def calculate(ticks, counts: dict | None = None, tables: dict | None = None):
    """(position, values in NAMES order) for every tick of ONE trade day. `ticks` gives (position, record) in tape
    order and must come from `tape.for_calculations()`. `tables`, when given, receives the peak lines (`facts`),
    the before lines and the peaks still open at the last tick; `counts` the counts of the run."""
    calc = ChainPeaks()
    facts = [] if tables is None else tables.setdefault('facts', [])
    before = [] if tables is None else tables.setdefault('before', [])
    for position, record in ticks:
        values, lines, earlier = calc.tick(position, int(record['ts_recv']), bytes(record['action']),
                                           bytes(record['side']), int(record['size']), int(record['price']))
        facts.extend(lines)
        before.extend(earlier)
        yield position, values
    if tables is not None:
        tables['open-at-the-end'] = calc.still_open()
    if counts is not None:
        counts.update(dict(calc.counts, steps_back_written=STEPS_BACK,
                           peaks_still_open_at_the_last_tick=len(calc.open)))
