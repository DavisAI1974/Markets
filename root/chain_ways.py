"""ROOT part 2: the chain link models taken further, in six ways (beside `root/chain_models.py`, which stays so the
stored six steps can be made again).

Greg, 2026-11-16: "Take the chains as far as they will go. And try the calcs in different ways. Keep the different
results and see what the results are telling you." The six ways, as named to him (Claude's calls, his to correct):
  1. as built: the nearest ended peaks before, one more at each step, out to 24;
  2. each earlier peak alone: only the d-th ended peak back, out to 48;
  3. what a peak does AFTER it becomes known (how it ended, how long, how far it faded, the steps down, the three
     price moves), given its own size and side and then the chain, out to 24;
  4. the same with each earlier peak alone, out to 48;
  5. only the ended peaks before on the peak's own side, the chain, out to 24;
  6. only those on the other side, the chain, out to 24.
The step counts are how far each is run now, not caps: where the gain has not gone by the last step, that way is
run further, and the deeper run is a new set of peaks, written beside this one with its depth in its file names.

How it differs from `chain_models` (Claude's calls, stated to Greg):
- The earlier peaks are worked out here to any depth from the peak lines (the tick a peak became known, the tick
  its story ended, its side), by the rule of `chain_peaks`: an earlier peak counts when its story ended at or
  before the tick this peak became known, nearest first by the tick it became known. The check compares the first
  six steps with the before lines `chain_peaks` writes.
- One fixed set of peaks per way: those with every step of that way available and no empty figure on themselves or
  on any earlier peak used. So the model given g peaks is fitted once, and "without" at step d is "with" at d-1.
- Nine figures, the ones never empty (the time from the low to the high is left out: it is empty on 32 to 42 peaks
  a trade day and would empty out a tenth of the peaks at 24 steps). They enter as in `chain_models`.
- Ways 1, 2, 5 and 6 predict all nine; with no earlier peak a model says the teaching trade days' mean. Ways 3 and
  4 predict the seven figures of what the peak did after it became known, from its own size and side (buy 1, sell
  0) and then each earlier peak's nine figures with whether it is on the same side as this peak (1 or 0); with no
  earlier peak the model is taught on its own size and side alone. Ways 1 and 2 give no side: the peak's own side
  is part of what they predict (same side as the peak before).
- The settings: each model starts from the original's list. When the best setting is the last of the list, the
  list is carried on one more step (ridge times 10, nearest neighbours and leaf size times 2) and the choice made
  again, until the best sits inside the list or no further step exists (nearest neighbours cannot exceed the peaks
  taught on). No end is picked. The receipt lists every setting tried and its error.
- Lines: one per peak, way, model and number of earlier peaks given: each figure's squared error (4-byte numbers)
  and the mean over the figures (8-byte). The gain at a step is the difference of two neighbouring lines (for the
  each-alone ways, against the line with none given). Not known at a tick: made afterwards by models taught on the
  other three trade days.

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

from root import chain_models as CM
from root import checks, part2, store, tape
from root.calcs import chain_peaks
from root.calcs import flow_peak
from root.calendar import parse_trade_day

NINE = [name for name in CM.FIGURE_NAMES if name != 'low_to_high_ns']
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
NEXT_SETTING = {CM.RIDGE: lambda s: s * 10, CM.NEIGHBOURS: lambda s: s * 2, CM.TREES: lambda s: s * 2}
FIRST_LIST = {CM.RIDGE: CM.RIDGE_GRID, CM.NEIGHBOURS: CM.NEIGHBOUR_GRID, CM.TREES: CM.LEAF_GRID}
PREDICT_SLICE = 256                                     # rows a nearest-neighbours predict takes at once
CHECK_STEPS = chain_peaks.STEPS_BACK                    # the steps the before lines of chain_peaks hold
CLOSEST = 'closest single peak'                          # the individual way: one match, nothing blended
ALL_MODELS = CM.MODELS + (CLOSEST,)
MATCH_SLICE = 8                                         # scored peaks compared with every teaching peak at once
MATCH_TOLERANCE = 1e-5                                  # the loop adds in full precision, the slices in 4-byte numbers
LINE_NAMES = ['peak_high_position', 'peak_story_ended_position', 'way', 'model', 'peaks_given', 'setting',
              'matched_trade_day', 'matched_peak_high_position', 'match_distance', 'matches_tied',
              'error_mean'] + [f'error_{name}' for name in NINE]
_D = {}                                                 # trade day -> Ways; set before the helpers are started


class Ways:
    """One trade day's peaks as the ways read them."""

    def __init__(self, lines: dict):
        import numpy as np
        at = {name: k for k, name in enumerate(chain_peaks.FACT_NAMES)}
        base = CM.Day(lines)
        facts = lines['facts']
        self.high, self.ended, self.known = base.high, base.ended, base.known
        self.buy = np.array([float(line[at['side']] == flow_peak.BUY_TEXT) for line in facts])
        keep = [CM.FIGURE_NAMES.index(name) for name in NINE]
        self.figures = base.figures[:, keep]
        self.complete = ~np.isnan(self.figures).any(axis=1)
        self.size = self.figures[:, NINE.index('size')]
        self.earlier = self._earlier(base)
        self.sets = {way: self._fixed_set(way) for way in WAYS}

    def _earlier(self, base) -> dict:
        """For every peak and each of ALL, OWN, OTHER: the places of the ended peaks before it, nearest first, as
        deep as the deepest way reads. Events in tick order; at one tick the stories that end come before the peak
        that becomes known, as in chain_peaks."""
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

    def fixed_set(self, way: int):
        return self.sets[way]

    def _fixed_set(self, way: int):
        """The peaks of this way: every step available, no empty figure on the peak or on any earlier peak used."""
        import numpy as np
        w = WAYS[way]
        keep = []
        for k in range(len(self.high)):
            before = self.earlier[w['earlier']].get(k, [])[:w['depth']]
            if self.complete[k] and len(before) == w['depth'] and self.complete[before].all():
                keep.append(k)
        return np.array(keep, dtype=np.int64)

    def matrices(self, way: int, given: int):
        """For the peaks of this way: the inputs given `given` earlier peaks (the chain: the nearest `given`; each
        alone: only the given-th), and the figures to predict."""
        import numpy as np
        w = WAYS[way]
        rows = self.fixed_set(way)
        steps = range(given) if w['kind'] == CHAIN else ([given - 1] if given else [])
        parts = [np.column_stack([self.size[rows], self.buy[rows]])] if w['own'] else []
        for step in steps:
            places = np.array([self.earlier[w['earlier']][k][step] for k in rows], dtype=np.int64)
            parts.append(self.figures[places])
            if w['own']:
                parts.append((self.buy[places] == self.buy[rows]).astype(float)[:, None])
        x = np.hstack(parts) if parts else np.empty((len(rows), 0))
        y = self.figures[rows][:, [NINE.index(name) for name in w['target']]]
        return x, y, rows


def _standardised(teach: list, scored: str, way: int, given: int):
    import numpy as np
    parts = [_D[day].matrices(way, given) for day in teach]
    x, y = np.vstack([p[0] for p in parts]), np.vstack([p[1] for p in parts])
    x_new, y_new, rows = _D[scored].matrices(way, given)
    checks.need(len(y) and len(y_new), f'way {way}: no peak to teach on or to score with {given} given')

    def scale(a, b):
        mean, spread = a.mean(axis=0), a.std(axis=0)
        spread[spread == 0] = 1
        return (a - mean) / spread, (b - mean) / spread
    y, y_new = scale(y, y_new)
    if x.shape[1]:
        x, x_new = scale(x, x_new)
    return x, y, x_new, y_new, rows


def closest(way: int, given: int, teach: tuple, scored: str) -> dict:
    """The individual way (Greg, 2026-11-17: "Average and individual ... just add the individual part"): for each
    scored peak, the single teaching peak whose inputs are closest, nothing blended and no setting chosen. Each input
    is put on one footing by its rank among the teaching peaks (its place in their order, over their number);
    closeness is the sum of the rank differences. Every teaching peak at the closest distance gets its own line."""
    import numpy as np
    x, y, x_new, y_new, rows = _standardised(list(teach), scored, way, given)
    ids = [(day, _D[day].high[k]) for day in teach for k in _D[day].fixed_set(way).tolist()]
    checks.need(len(ids) == len(y), 'the teaching peaks and their names are not in the same order')
    order = np.sort(x, axis=0)
    rank = lambda a: np.column_stack([np.searchsorted(order[:, j], a[:, j], side='left') for j in range(a.shape[1])]
                                     ).astype(np.float32) / len(x)
    taught, new = rank(x), rank(x_new)
    lines = []
    for start in range(0, len(new), MATCH_SLICE):
        distance = np.abs(new[start:start + MATCH_SLICE, None, :] - taught[None, :, :]).sum(axis=2)
        for i, row in enumerate(distance):
            tied = np.flatnonzero(row == row.min())
            for m in tied.tolist():
                lines.append((start + i, ids[m][0], int(ids[m][1]), float(row[m]), len(tied),
                              np.square(y_new[start + i] - y[m])))
    first = [sum(abs(float(p) - float(q)) for p, q in zip(new[0], t)) for t in taught]      # the check, by a loop
    best = min(first)
    checks.need({ids[m][1] for m, v in enumerate(first) if abs(v - best) <= MATCH_TOLERANCE * max(best, 1)} >=
                {line[2] for line in lines if line[0] == 0}, f'way {way} given {given}: the closest match differs')
    print(f'way {way} {CLOSEST} given {given}: {len(lines)} lines for {len(new)} peaks', flush=True)
    return dict(way=way, model=CLOSEST, given=given, rows=rows, setting=None, tried={}, taught_on=len(y), lines=lines)


def way_model(way: int, model: str, given: int, teach: tuple, scored: str) -> dict:
    """One way, one model, `given` earlier peaks: the setting chosen inside the teaching trade days by leaving each
    out in turn, the list carried on while the best is its last; then taught on all three and scored."""
    import numpy as np
    if model == CLOSEST:
        return closest(way, given, teach, scored)
    x, y, x_new, y_new, rows = _standardised(list(teach), scored, way, given)
    out = dict(way=way, model=model, given=given, rows=rows, setting=None, tried={}, taught_on=len(y))
    if not x.shape[1]:                                 # nothing given: the teaching trade days' mean
        out['squared_error'] = np.square(y_new)
        return out
    folds = [_standardised([d for d in teach if d != left], left, way, given) for left in teach]
    settings, best = list(FIRST_LIST[model]), None
    k = 0
    while k < len(settings):
        setting = settings[k]
        errors = [float(np.square(b_new - _predict(model, CM._fit(model, setting, a, b, True), a_new)).mean())
                  for a, b, a_new, b_new, _ in folds]
        out['tried'][repr(setting)] = errors
        if best is None or np.mean(errors) < best[0]:   # the first on a tie, as the original
            best = (float(np.mean(errors)), setting)
        k += 1
        if k == len(settings) and best[1] == settings[-1]:
            following = NEXT_SETTING[model](setting)
            smallest = min(len(f[1]) for f in folds)
            if model == CM.NEIGHBOURS and following > smallest:
                out['list_ended_because'] = 'nearest neighbours cannot exceed the peaks taught on'
            elif model == CM.TREES and following > smallest // 2:
                out['list_ended_because'] = 'a leaf cannot hold more than half the peaks taught on'
            else:
                settings.append(type(setting)(following))
    out['setting'] = best[1]
    out['chosen_at_the_end_of_the_list'] = best[1] == settings[-1]
    predicted = _predict(model, CM._fit(model, best[1], x, y, False), x_new)
    if model == CM.RIDGE:
        apart = float(np.abs(predicted - CM._ridge_again(best[1], x, y, x_new)).max())
        checks.need(apart <= CM.RIDGE_RECOUNT_TOLERANCE, f'way {way} ridge given {given}: closed form {apart} apart')
        out['ridge_closed_form_furthest_apart'] = apart
    out['squared_error'] = np.square(y_new - predicted)
    print(f'way {way} {model} given {given}: setting {best[1]} after {len(settings)} tried', flush=True)
    return out


def earlier_as_written(day: str, lines: dict) -> dict:
    """The check: the earlier peaks worked out here agree with the before lines chain_peaks writes, for the first
    six steps, peak by peak; and every earlier peak had ended at or before the tick its peak became known."""
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
    return dict(passed=True, before_lines_compared=compared,
                what='the earlier peaks worked out to any depth agree with chain_peaks\' before lines for the first '
                     'six steps; every earlier peak ended at or before its peak became known; own and other side '
                     'hold only peaks of that side')


def _predict(model: str, fitted, x):
    """The predictions, made a slice of rows at a time for nearest neighbours: the same values, with the memory
    of one slice (the neighbours of every row times the nine figures would not fit at once once the list of
    settings is carried on toward the number of peaks taught on)."""
    import numpy as np
    if model != CM.NEIGHBOURS or len(x) <= PREDICT_SLICE:
        return fitted.predict(x)
    return np.vstack([fitted.predict(x[start:start + PREDICT_SLICE]) for start in range(0, len(x), PREDICT_SLICE)])


CM._JOBS['way model'] = way_model


def _cost(way: int, model: str, given: int) -> float:
    """A rough order of the work a fit takes, only to start the longest first: the inputs it is given."""
    w = WAYS[way]
    inputs = (2 if w['own'] else 0) + (min(given, 1) if w['kind'] == ALONE else given) * (10 if w['own'] else 9)
    return inputs * {CM.TREES: 3.0, CM.NEIGHBOURS: 2.0, CLOSEST: 1.0, CM.RIDGE: 0.1}[model]


def run(tape_folder: Path, scored_day: dt.date, out: Path) -> dict:
    import numpy as np
    import pyarrow as pa
    import sklearn
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    days = sorted(tape.BUILT_TRADE_DAYS)
    text = {day: f'{day:%Y%m%d}' for day in days}
    scored = text[scored_day]
    teach = tuple(text[day] for day in days if day != scored_day)
    built = CM.on_pinned_helpers([('peak lines', str(tape_folder), text[day]) for day in days])
    lines = {job[-1]: value for job, (_, _, value) in built.items()}
    _D.update({day: Ways(lines[day]) for day in lines})
    the_check = {day: earlier_as_written(day, lines[day]) for day in sorted(lines)}
    jobs = [('way model', way, model, given, teach, scored) for way, w in WAYS.items()
            for given in range(w['depth'] + 1) for model in ALL_MODELS
            if given or w['own'] or model == CM.RIDGE]           # with nothing given the mean needs no model, and
    #                                                              the individual way has nothing to match on
    jobs.sort(key=lambda j: -_cost(j[1], j[2], j[3]))        # the longest pieces first
    fitted = CM.on_pinned_helpers(jobs)
    at = {(job[1], job[2], job[3]): value for job, (_, _, value) in fitted.items()}
    me = _D[scored]
    files, receipt_ways = {}, {}
    for way, w in WAYS.items():
        table = []
        for given in range(w['depth'] + 1):
            fit = at.get((way, CLOSEST, given))
            for place, name, high, distance, tied, errors in (fit['lines'] if fit else []):
                k = int(fit['rows'][place])
                row = dict.fromkeys(LINE_NAMES)
                row.update(peak_high_position=me.high[k], peak_story_ended_position=me.ended[k], way=way, model=CLOSEST,
                           peaks_given=given, matched_trade_day=name, matched_peak_high_position=high,
                           match_distance=distance, matches_tied=tied, error_mean=float(errors.mean()))
                row.update({f'error_{n}': float(errors[f]) for f, n in enumerate(w['target'])})
                table.append(tuple(row[n] for n in LINE_NAMES))
        for model in CM.MODELS:
            for given in range(w['depth'] + 1):
                fit = at.get((way, model, given)) or at[(way, CM.RIDGE, given)]   # the mean, shared by the models
                for place, k in enumerate(fit['rows'].tolist()):
                    row = dict.fromkeys(LINE_NAMES)
                    errors = fit['squared_error'][place]
                    row.update(peak_high_position=me.high[k], peak_story_ended_position=me.ended[k], way=way,
                               model=model, peaks_given=given, setting=CM._number(fit['setting']),
                               error_mean=float(errors.mean()))
                    row.update({f'error_{name}': float(errors[f]) for f, name in enumerate(w['target'])})
                    table.append(tuple(row[name] for name in LINE_NAMES))
        floats = {'setting', 'match_distance', 'error_mean'} | {n for n in LINE_NAMES if n.startswith('error_')}
        schema = store.schema(LINE_NAMES, {'model', 'matched_trade_day'}, set(), floats)
        schema = pa.schema([pa.field(f.name, pa.float32()) if f.name.startswith('error_') and f.name != 'error_mean'
                            else f for f in schema])
        stem = f'chain-way{way}-to{w["depth"]}-{scored}'
        files[way] = [part2.write(out, f'{stem}-part{part:03d}.parquet', schema,
                                  [list(c) for c in zip(*table[start:start + store.ROWS_PER_PART])])
                      for part, start in enumerate(range(0, len(table), store.ROWS_PER_PART))]
        receipt_ways[str(way)] = dict(
            what=dict(kind=w['kind'], earlier_peaks=w['earlier'], predicts=w['target'],
                      own_size_and_side_given=w['own'], run_to=w['depth']),
            peaks={day: int(len(_D[day].fixed_set(way))) for day in sorted(_D)},
            lines=len(table), files=files[way],
            fits=[dict(model=v['model'], peaks_given=v['given'], setting=CM._number(v['setting']),
                       tried=v['tried'], chosen_at_the_end_of_the_list=v.get('chosen_at_the_end_of_the_list'),
                       list_ended_because=v.get('list_ended_because'), peaks_taught_on=v['taught_on'],
                       peaks_scored=len(v['rows']), match_lines=len(v['lines']) if 'lines' in v else None,
                       mean_squared_error=float(v['squared_error'].mean()) if 'squared_error' in v else None,
                       ridge_closed_form_furthest_apart=v.get('ridge_closed_form_furthest_apart'))
                  for (wy, _, _), v in sorted(at.items(), key=lambda e: (ALL_MODELS.index(e[0][1]), e[0][2]))
                  if wy == way])
    receipt = dict(
        what='ROOT part 2: the chain link models in six ways, one trade day scored by models taught on the other '
             'three', trade_day_scored=scored_day.isoformat(),
        trade_days_taught_on=[day.isoformat() for day in days if day != scored_day],
        laid_out='Greg, 2026-11-16: "Take the chains as far as they will go. And try the calcs in different ways"; '
                 'the six ways named to him the same minute (markets-data ROOT_GAMEPLAN_DECISIONS.md, ninth session)',
        not_known_at_a_tick='Made afterwards by models taught on other trade days, some of them later. Own tables; '
                            'never put on a tick row.',
        inputs={day: lines[day]['inputs'] for day in lines},
        figures=[dict(figure=name, enters_as=dict(CM.FIGURES)[name]) for name in NINE],
        first_lists={m: list(v) for m, v in FIRST_LIST.items()},
        settings=dict(trees=CM.TREE_COUNT, trees_while_choosing=CM.TREE_COUNT_CHOOSING, seed=CM.SEED,
                      tick_in_price_units=CM.TICK_PRICE_UNITS),
        libraries=dict(python=platform.python_version(), numpy=np.__version__, scikit_learn=sklearn.__version__),
        columns=LINE_NAMES, ways=receipt_ways,
        helpers=dict(threads_each=1, pinned=True,
                     fits=[dict(way=j[1], model=j[2], peaks_given=j[3], cpu=cpu, seconds=s)
                           for j, (cpu, s, _) in sorted(fitted.items(), key=lambda e: e[0][1:4])]),
        checks=dict(earlier_peaks=the_check,
                    ridge_closed_form=dict(passed=True, tolerance=CM.RIDGE_RECOUNT_TOLERANCE),
                    no_independent_recount='nearest neighbours and extra trees rest on the library, pinned by '
                                           'version and seed'),
        empty_cells='a peak not in a way\'s set has no line in that way; the receipt counts each way\'s peaks',
        seconds=round(time.monotonic() - started, 1))
    (out / f'CHAIN-WAYS-{scored}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='ROOT part 2: the chain link models in six ways for one trade day')
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
