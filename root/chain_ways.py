"""ROOT part 2: the chain links, peak by peak, in six ways. Each peak is its own case: nothing is averaged, blended,
pooled or grouped (Greg, 2026-11-17: "we do not average anything to group the things"; "take out all.of the other
averages"; the averaging chain link models and their results were removed the same day).

Greg, 2026-11-16: "Take the chains as far as they will go. And try the calcs in different ways. Keep the different
results and see what the results are telling you." The six ways, as named to him:
  1. the nearest ended peaks before, one more at each step, out to 24;
  2. each earlier peak alone: only the d-th ended peak back, out to 48;
  3. what a peak does AFTER it becomes known (how it ended, how long, how far it faded, the steps down, the three
     price moves), given its own size and side and then the chain, out to 24;
  4. the same with each earlier peak alone, out to 48;
  5. only the ended peaks before on the peak's own side, the chain, out to 24;
  6. only those on the other side, the chain, out to 24.
The step counts are how far each is run now, not caps: a deeper run is a new set of peaks, written beside, its depth in
its file names.

The individual way (Claude's call, stated to Greg): for each peak and each number of earlier peaks given, the single
peak on the other three trade days whose inputs are closest to this peak's. Every teaching peak at the closest
distance gets its own line. Each line names the matched peak (its trade day and the tick of its high), how close it
was, and for each figure this peak's value, the match's value and the difference, in the figure's own units. Nothing
is chosen by a setting and nothing is averaged. To put inputs of different units on one footing, each input is
replaced by its rank among the teaching peaks (its place in their order, a whole number); closeness is the sum of the
rank differences, exact in whole numbers (written over the number of teaching peaks). Whether one more earlier peak brought a closer match is read peak by peak, figure by figure,
from neighbouring lines.

What is shared with the earlier build: the earlier peaks worked out to any depth from the peak lines by the rule of
`chain_peaks` (an earlier peak counts when its story ended at or before the tick this peak became known, nearest
first); one fixed set of peaks per way (every step available, no empty figure on the peak or on an earlier peak
used); the nine figures that are never empty, entered as `chain_common.FIGURES` says. With no earlier peak given
there is nothing to match on, so ways 1, 2, 5 and 6 start at one; ways 3 and 4 match on the peak's own size and side
at none given. The lines are not known at a tick: they come from peaks of other trade days, some of them later.

    python3 -m root.chain_ways 20231002 --out <markets-data folder> [--tape ...]
"""
from __future__ import annotations

import os

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'                            # one thread a helper, set before numpy is loaded

import argparse
import bisect
import datetime as dt
import json
import platform
import time
from pathlib import Path

from root import chain_common as C
from root import checks, part2, store, tape
from root.calcs import chain_peaks
from root.calcs import flow_peak
from root.calendar import parse_trade_day

NINE = [name for name in C.FIGURE_NAMES if name != 'low_to_high_ns']
AFTER = ['ended_by', 'high_to_end_ns', 'lowest_share', 'steps_down', 'price_move_with_side',
         'furthest_price_with_side', 'furthest_price_against_side']
CHAIN, ALONE = 'chain', 'each alone'
ALL, OWN, OTHER = 'all', 'own side', 'other side'
WAYS = {1: dict(kind=CHAIN, earlier=ALL, target=NINE, own=False, depth=24),
        2: dict(kind=ALONE, earlier=ALL, target=NINE, own=False, depth=48),
        3: dict(kind=CHAIN, earlier=ALL, target=AFTER, own=True, depth=24),
        4: dict(kind=ALONE, earlier=ALL, target=AFTER, own=True, depth=48),
        5: dict(kind=CHAIN, earlier=OWN, target=NINE, own=False, depth=24),
        6: dict(kind=CHAIN, earlier=OTHER, target=NINE, own=False, depth=24)}
MATCH_SLICE = 8                                         # scored peaks compared with every teaching peak at once
CHECK_STEPS = chain_peaks.STEPS_BACK                    # the steps the before lines of chain_peaks hold
LINE_NAMES = (['peak_high_position', 'peak_story_ended_position', 'way', 'peaks_given', 'matched_trade_day',
               'matched_peak_high_position', 'match_distance', 'matches_tied']
              + [f'{what}_{name}' for name in NINE for what in ('own', 'match', 'difference')])
_D = {}                                                 # trade day -> Ways; set before the helpers are started


class Ways:
    """One trade day's peaks as the ways read them."""

    def __init__(self, lines: dict):
        import numpy as np
        at = {name: k for k, name in enumerate(chain_peaks.FACT_NAMES)}
        base = C.Day(lines)
        self.high, self.ended, self.known = base.high, base.ended, base.known
        self.buy = np.array([float(line[at['side']] == flow_peak.BUY_TEXT) for line in lines['facts']])
        self.figures = base.figures[:, [C.FIGURE_NAMES.index(name) for name in NINE]]
        self.complete = ~np.isnan(self.figures).any(axis=1)
        self.size = self.figures[:, NINE.index('size')]
        self.earlier = self._earlier()
        self.sets = {way: self._fixed_set(way) for way in WAYS}

    def _earlier(self) -> dict:
        """For every peak and each of ALL, OWN, OTHER: the places of the ended peaks before it, nearest first. Events
        in tick order; at one tick the stories that end come before the peak that becomes known, as in chain_peaks."""
        deepest = max(w['depth'] for w in WAYS.values())
        order = sorted([(end, 0, k) for k, end in enumerate(self.ended)] +
                       [(known, 1, k) for k, known in enumerate(self.known)])
        ended = {ALL: [], 'buy': [], 'sell': []}
        out = {ALL: {}, OWN: {}, OTHER: {}}
        for _, what, k in order:
            side = 'buy' if self.buy[k] else 'sell'
            if what == 0:
                for name in (ALL, side):
                    bisect.insort(ended[name], (self.known[k], self.high[k], k))
                continue
            other = 'sell' if side == 'buy' else 'buy'
            for name, held in ((ALL, ended[ALL]), (OWN, ended[side]), (OTHER, ended[other])):
                out[name][k] = [e[2] for e in reversed(held[-deepest:])]
        return out

    def _fixed_set(self, way: int):
        import numpy as np
        w = WAYS[way]
        keep = []
        for k in range(len(self.high)):
            before = self.earlier[w['earlier']].get(k, [])[:w['depth']]
            if self.complete[k] and len(before) == w['depth'] and self.complete[before].all():
                keep.append(k)
        return np.array(keep, dtype=np.int64)

    def matrices(self, way: int, given: int):
        """For the peaks of this way: their inputs given `given` earlier peaks (the chain: the nearest `given`; each
        alone: only the given-th) and the figures it is about."""
        import numpy as np
        w = WAYS[way]
        rows = self.sets[way]
        steps = range(given) if w['kind'] == CHAIN else ([given - 1] if given else [])
        parts = [np.column_stack([self.size[rows], self.buy[rows]])] if w['own'] else []
        for step in steps:
            places = np.array([self.earlier[w['earlier']][k][step] for k in rows], dtype=np.int64)
            parts.append(self.figures[places])
            if w['own']:
                parts.append((self.buy[places] == self.buy[rows]).astype(float)[:, None])
        x = np.hstack(parts) if parts else np.empty((len(rows), 0))
        return x, self.figures[rows][:, [NINE.index(name) for name in w['target']]], rows


def closest(way: int, given: int, teach: tuple, scored: str) -> dict:
    """For each scored peak, the single teaching peak whose inputs are closest. The check: the first peak's match
    found again by a plain loop in full precision."""
    import numpy as np
    parts = [_D[day].matrices(way, given) for day in teach]
    x, y = np.vstack([p[0] for p in parts]), np.vstack([p[1] for p in parts])
    x_new, y_new, rows = _D[scored].matrices(way, given)
    ids = [(day, int(_D[day].high[k])) for day in teach for k in _D[day].sets[way].tolist()]
    checks.need(len(ids) == len(y) and x.shape[1] > 0 and len(y_new), f'way {way} given {given}: nothing to match')
    order = np.sort(x, axis=0)
    rank = lambda a: np.column_stack([np.searchsorted(order[:, j], a[:, j], side='left')
                                      for j in range(a.shape[1])]).astype(np.int64)
    taught, new = rank(x), rank(x_new)
    lines = []
    for start in range(0, len(new), MATCH_SLICE):
        distance = np.abs(new[start:start + MATCH_SLICE, None, :] - taught[None, :, :]).sum(axis=2)
        for i, row in enumerate(distance):
            tied = np.flatnonzero(row == row.min()).tolist()
            for m in tied:
                lines.append((start + i, ids[m][0], ids[m][1], float(row[m]) / len(x), len(tied), y_new[start + i],
                              y[m]))
    first = [sum(abs(int(p) - int(q)) for p, q in zip(new[0], t)) for t in taught]       # the check, by a loop
    checks.need({ids[m][1] for m, v in enumerate(first) if v == min(first)} ==
                {line[2] for line in lines if line[0] == 0}, f'way {way} given {given}: the closest match differs')
    print(f'way {way} given {given}: {len(lines)} lines for {len(new)} peaks', flush=True)
    return dict(way=way, given=given, rows=rows, taught_on=len(y), lines=lines)


C._JOBS['closest'] = closest


def earlier_as_written(day: str, lines: dict) -> dict:
    """The check of the earlier peaks: they agree with the before lines chain_peaks writes for the first six steps,
    peak by peak; every one ended at or before the tick its peak became known; own and other side hold only peaks of
    that side."""
    w = _D[day]
    place = {high: k for k, high in enumerate(w.high)}
    b = {name: k for k, name in enumerate(chain_peaks.BEFORE_NAMES)}
    written = {}
    for line in lines['before']:
        if line[b['peak_high_position']] in place:
            written.setdefault(place[line[b['peak_high_position']]], {})[line[b['steps_back']]] = \
                place[line[b['earlier_high_position']]]
    compared = 0
    for k in range(len(w.high)):
        mine = w.earlier[ALL].get(k, [])[:CHECK_STEPS]
        theirs = written.get(k, {})
        checks.need(mine == [theirs[s] for s in range(1, len(theirs) + 1)],
                    f'{day}: the earlier peaks of the peak at {w.high[k]} differ from chain_peaks\' before lines')
        compared += len(mine)
        for name in (ALL, OWN, OTHER):
            for e in w.earlier[name].get(k, []):
                checks.need(w.ended[e] <= w.known[k] and w.known[e] < w.known[k],
                            f'{day}: the peak at {w.high[k]} was given a peak whose story had not ended')
                checks.need((name == ALL) or ((w.buy[e] == w.buy[k]) == (name == OWN)),
                            f'{day}: a peak of the wrong side among the {name} earlier peaks')
    return dict(passed=True, before_lines_compared=compared)


def run(tape_folder: Path, scored_day: dt.date, out: Path) -> dict:
    import numpy as np
    import pyarrow as pa
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    days = sorted(tape.BUILT_TRADE_DAYS)
    text = {day: f'{day:%Y%m%d}' for day in days}
    scored = text[scored_day]
    teach = tuple(text[day] for day in days if day != scored_day)
    built = C.on_pinned_helpers([('peak lines', str(tape_folder), text[day]) for day in days])
    lines = {job[-1]: value for job, (_, _, value) in built.items()}
    _D.update({day: Ways(lines[day]) for day in lines})
    the_check = {day: earlier_as_written(day, lines[day]) for day in sorted(lines)}
    jobs = [('closest', way, given, teach, scored) for way, w in WAYS.items()
            for given in range(0 if w['own'] else 1, w['depth'] + 1)]
    jobs.sort(key=lambda j: -(j[2] if WAYS[j[1]]['kind'] == CHAIN else 1))       # the longest first
    done = C.on_pinned_helpers(jobs)
    at = {(job[1], job[2]): value for job, (_, _, value) in done.items()}
    me = _D[scored]
    schema = pa.schema([(n, pa.string() if n == 'matched_trade_day' else
                         pa.float64() if n == 'match_distance' or n.split('_')[0] in ('own', 'match', 'difference')
                         else pa.int64()) for n in LINE_NAMES])
    files, receipt_ways = {}, {}
    for way, w in WAYS.items():
        table = []
        for given in range(0 if w['own'] else 1, w['depth'] + 1):
            fit = at[(way, given)]
            for place, name, high, distance, tied, own, match in fit['lines']:
                k = int(fit['rows'][place])
                row = dict.fromkeys(LINE_NAMES)
                row.update(peak_high_position=me.high[k], peak_story_ended_position=me.ended[k], way=way,
                           peaks_given=given, matched_trade_day=name, matched_peak_high_position=high,
                           match_distance=distance, matches_tied=tied)
                for f, figure in enumerate(w['target']):
                    row.update({f'own_{figure}': float(own[f]), f'match_{figure}': float(match[f]),
                                f'difference_{figure}': float(match[f] - own[f])})
                table.append(tuple(row[n] for n in LINE_NAMES))
        stem = f'chain-way{way}-to{w["depth"]}-{scored}'
        files[way] = [part2.write(out, f'{stem}-part{part:03d}.parquet', schema,
                                  [list(c) for c in zip(*table[start:start + store.ROWS_PER_PART])])
                      for part, start in enumerate(range(0, len(table), store.ROWS_PER_PART))]
        receipt_ways[str(way)] = dict(
            what=dict(kind=w['kind'], earlier_peaks=w['earlier'], about=w['target'], own_size_and_side_given=w['own'],
                      run_to=w['depth']),
            peaks={day: int(len(_D[day].sets[way])) for day in sorted(_D)}, lines=len(table), files=files[way],
            matches=[dict(peaks_given=g, peaks_taught_on=v['taught_on'], peaks_scored=len(v['rows']),
                          lines=len(v['lines'])) for (wy, g), v in sorted(at.items()) if wy == way])
    receipt = dict(
        what='ROOT part 2: the chain links in six ways, peak by peak: each peak\'s single closest peak on the other '
             'three trade days; nothing averaged', trade_day_scored=scored_day.isoformat(),
        trade_days_matched_against=[day.isoformat() for day in days if day != scored_day],
        decided='Greg, 2026-11-16 and 2026-11-17 (markets-data ROOT_GAMEPLAN_DECISIONS.md, ninth and tenth sessions)',
        not_known_at_a_tick='Made afterwards from peaks of other trade days, some of them later. Own tables; never put '
                            'on a tick row.',
        inputs={day: lines[day]['inputs'] for day in lines},
        figures=[dict(figure=name, enters_as=dict(C.FIGURES)[name]) for name in NINE],
        footing='each input replaced by its rank among the teaching peaks; closeness = the sum of rank differences',
        libraries=dict(python=platform.python_version(), numpy=np.__version__), columns=LINE_NAMES,
        ways=receipt_ways,
        helpers=dict(threads_each=1, pinned=True,
                     jobs=[dict(way=j[1], peaks_given=j[2], cpu=cpu, seconds=s)
                           for j, (cpu, s, _) in sorted(done.items(), key=lambda e: e[0][1:3])]),
        checks=dict(earlier_peaks=the_check,
                    closest=dict(passed=True, what='for every way and number given, the first peak\'s closest match '
                                                   'found again by a plain loop in full precision')),
        empty_cells='a peak not in a way\'s set has no line in that way; a figure a way is not about stays empty',
        seconds=round(time.monotonic() - started, 1))
    (out / f'CHAIN-WAYS-{scored}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='ROOT part 2: the chain links in six ways, peak by peak')
    ap.add_argument('trade_day')
    ap.add_argument('--tape', type=Path, default=Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' /
                    'nymex_mbo' / 'ng_v0_oct2023')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(a.tape, parse_trade_day(a.trade_day), a.out)
    print(json.dumps(dict(trade_day=receipt['trade_day_scored'], checks=receipt['checks'],
                          ways={w: dict(peaks=v['peaks'], lines=v['lines']) for w, v in receipt['ways'].items()},
                          seconds=receipt['seconds']), indent=1))


if __name__ == '__main__':
    main()
