"""ROOT part 2: the chain link models (Step 1, piece 4), second part: the models.

Laid out for Greg and approved before it was written (markets-data `STEP1_STEP2_LAYOUTS.md`, piece 4: "Let it
produce full values. That will be the base going forward that we build off of", "Do it"). It is a model score by
his decision, an exception to "no model scores", kept per peak and never pooled.

What it asks, for every peak of one trade day: how much does knowing the peaks before it help say what it did?
- What a peak did is its peak line from `root/calcs/chain_peaks.py` (ten figures, listed in `FIGURES`).
- The peaks before are its before lines: the nearest peaks whose stories had already ended when it became known.
- Three models (ridge, nearest neighbours, extra trees), as in the original programs of 2026-08-17, predict a
  peak's ten figures from the figures of the d peaks before it. Each is TAUGHT ON THE OTHER THREE TRADE DAYS, so
  no peak is scored by a model that saw its own trade day.
- At each step back d, the gain is the error WITHOUT the d-th peak back (the model given d-1 peaks) minus the
  error WITH it (the model given d peaks), on the same peaks. Given no peak at all, a model says the teaching
  trade days' mean.
- Full values: for every peak, every model and every step, each figure's own squared error without and with, the
  mean over the figures beside them, and the gain. No depth, no "member of a chain", no yes or no.

The values are NOT known at a tick. They are made afterwards, by models taught on other trade days, some of them
later ones. They are kept in their own table, one line per peak, model and step, and are never put on a tick row.

Carried from the original: the figures standardised on the teaching trade days; the fixed lists of settings; the
setting chosen inside the teaching trade days by leaving each of them out in turn; the same peaks scored without
and with (the paired sample); the price figures taken in ticks through arcsinh. Not carried: "all models
positive", the depth candidate, the Fisher tables, blocks of weeks, thinning, the depth stop at 12.

Claude's calls in the build, stated to Greg (his to correct):
- Lengths of time and the count of steps down enter as log(1 + value): raw nanoseconds run over many powers of
  ten and a handful of long ones would decide every squared error. Sizes and shares enter as they are. A yes or no
  enters as 1 or 0.
- A peak is scored at step d when it has d ended peaks before it and neither it nor any of them has an empty
  figure. Otherwise its line at that step is there with empty values and the reason. Nothing is filled in.
- The teaching trade days rebuild their peak lines here through `tape.for_calculations()`, by the same
  calculation; no stored file is read.
- Every helper is pinned to its own CPU and runs one thread; the receipt says which CPU ran which piece.

The check: every peak used as an input had a story that ended at or before the tick its target became known; and
ridge is worked out again in closed form and must agree. Nearest neighbours and extra trees have no independent
recount; the receipt says so.

    python3 -m root.chain_models 20231002 --out <markets-data folder> [--tape ...]
"""
from __future__ import annotations

import os

THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')
for _name in THREADS:                                  # one thread a helper, set before numpy is loaded
    os.environ[_name] = '1'

import argparse
import datetime as dt
import json
import multiprocessing
import platform
import queue
import time
import traceback
from pathlib import Path

from root import checks, part2, store, tape
from root.calcs import chain_peaks
from root.calcs import peak_story as P
from root.calendar import parse_trade_day

RIDGE, NEIGHBOURS, TREES = 'ridge', 'nearest neighbours', 'extra trees'
MODELS = (RIDGE, NEIGHBOURS, TREES)
RIDGE_GRID = (0.1, 1.0, 10.0, 100.0, 1000.0)           # the original's fixed lists of settings
NEIGHBOUR_GRID = (10, 20, 40, 80, 160)
LEAF_GRID = (10, 20, 40, 80)
TREE_COUNT = 140                                       # trees in a scoring forest, as in the original's
TREE_COUNT_CHOOSING = 50                               # "known at the time" pilot; and while choosing a setting
SEED = 20260817                                        # the original's seed
TICK_PRICE_UNITS = 1_000_000                           # one tick of the contract ($0.001) in the tape's price units
RIDGE_RECOUNT_TOLERANCE = 1e-8                         # how far the closed-form ridge may sit from the library's
HELPER_POLL_SECONDS = 5                                # how often the runner looks whether a helper has died
STEPS = chain_peaks.STEPS_BACK
AS_IS, LOG, YES_NO, TICKS = 'as it is', 'log(1 + value)', '1 for yes, 0 for no', 'arcsinh of ticks'
FIGURES = [('size', AS_IS), ('low_to_high_ns', LOG), ('ended_by', YES_NO), ('high_to_end_ns', LOG),
           ('lowest_share', AS_IS), ('steps_down', LOG), ('price_move_with_side', TICKS),
           ('furthest_price_with_side', TICKS), ('furthest_price_against_side', TICKS),
           ('same_side_as_peak_before', YES_NO)]
FIGURE_NAMES = [name for name, _ in FIGURES]
TOO_FEW = 'fewer ended peaks before it than this step'
EMPTY_FIGURE = 'an empty figure on this peak or on one of the peaks before it'
STILL_OPEN = 'its story was still open at the last tick of the trade day'
LINE_COLUMNS = [
    ('peak_high_position', 'Which peak the line is about: the tick of its high. A label only.'),
    ('peak_story_ended_position', 'The tick the peak\'s story ended, where its own peak line became known. A label '
     'only. The values on THIS line are not known at any tick: they come from models taught on other trade days.'),
    ('model', 'The model: ridge, nearest neighbours, or extra trees.'),
    ('steps_back', 'The step back: the d-th ended peak before this one.'),
    ('not_scored_because', 'Why the values are empty at this step. Empty when the peak is scored.'),
    ('setting_without', 'The setting chosen for the model given d-1 peaks (empty at step 1: it says the mean).'),
    ('setting_with', 'The setting chosen for the model given d peaks.'),
    ('error_without', 'The mean over the ten figures of the squared error of the model given d-1 peaks.'),
    ('error_with', 'The mean over the ten figures of the squared error of the model given d peaks.'),
    ('gain', 'error_without less error_with: above zero when the d-th peak back helped.'),
] + [(f'without_{name}', f'The squared error on {name} of the model given d-1 peaks (standardised figure).')
     for name in FIGURE_NAMES] + [(f'with_{name}', f'The squared error on {name} of the model given d peaks.')
                                  for name in FIGURE_NAMES]
LINE_NAMES = [name for name, _ in LINE_COLUMNS]
LINE_TEXT = {'model', 'not_scored_because'}
LINE_DECIMALS = set(LINE_NAMES) - LINE_TEXT - {'peak_high_position', 'peak_story_ended_position', 'steps_back'}
queue_empty = queue.Empty
_DAYS = {}                                             # trade day -> Day; set before the model helpers are started


# ---------------------------------------------------------------- the helpers: one a CPU, pinned, one thread each
def _helper(cpu: int, jobs, results):
    os.sched_setaffinity(0, {cpu})
    while True:
        job = jobs.get()
        if job is None:
            return
        started = time.monotonic()
        try:
            results.put((job, cpu, _JOBS[job[0]](*job[1:]), None, time.monotonic() - started))
        except Exception:                              # the reason goes back to the runner, which stops
            results.put((job, cpu, None, traceback.format_exc(), time.monotonic() - started))


def on_pinned_helpers(jobs: list) -> dict:
    """Runs every job on helpers started together, one for each CPU this process may use, each pinned to its own.
    Gives {job: (CPU it ran on, seconds, what it returned)}. A helper that fails stops the run with its reason."""
    context = multiprocessing.get_context('fork')
    cpus = sorted(os.sched_getaffinity(0))[:max(len(jobs), 1)]
    waiting, results = context.Queue(), context.Queue()
    for job in jobs:
        waiting.put(job)
    helpers = [context.Process(target=_helper, args=(cpu, waiting, results)) for cpu in cpus]
    for helper in helpers:
        waiting.put(None)
        helper.start()
    out = {}
    while len(out) < len(jobs):
        try:
            job, cpu, value, failed, seconds = results.get(timeout=HELPER_POLL_SECONDS)
        except queue_empty:
            failed, job, cpu = next(((f'it stopped with exit code {h.exitcode}', None, c)
                                     for h, c in zip(helpers, cpus) if h.exitcode), (None, None, None))
            if not failed:
                continue
        if failed:
            for helper in helpers:
                helper.terminate()
            raise checks.CheckFailed(f'the helper on CPU {cpu} failed on {job}:\n{failed}')
        out[job] = (cpu, round(seconds, 1), value)
    for helper in helpers:
        helper.join()
    return out


# ---------------------------------------------------------------- the peak lines of one trade day, through the gate
def peak_lines(tape_folder: str, day_text: str) -> dict:
    trade_day = parse_trade_day(day_text)
    week = tape.read_week(Path(tape_folder), trade_day)
    counts, tables = {}, {}
    for _ in chain_peaks.calculate(part2.gated(week, trade_day), counts, tables):
        pass
    return dict(facts=tables['facts'], before=tables['before'], still_open=tables['open-at-the-end'], counts=counts,
                inputs=[dict(file=f.name, sha256=f.sha256) for f in week])


class Day:
    """One trade day's peaks as the models read them: the ten figures of every peak line (empty stays empty, as
    not-a-number), and for every peak the place of each ended peak before it (-1 where there is none)."""

    def __init__(self, lines: dict):
        import numpy as np
        at = {name: k for k, name in enumerate(chain_peaks.FACT_NAMES)}
        facts = lines['facts']
        self.high = [line[at['peak_high_position']] for line in facts]
        self.ended = [line[at['known_position']] for line in facts]
        self.known = [line[at['peak_known_position']] for line in facts]
        self.still_open = [high for high, _ in lines['still_open']]
        place = {high: k for k, high in enumerate(self.high)}
        self.figures = np.full((len(facts), len(FIGURES)), np.nan)
        for k, line in enumerate(facts):
            for f, (name, how) in enumerate(FIGURES):
                value = line[at[name]]
                if value is None:
                    continue
                if how == LOG:
                    value = np.log1p(value)
                elif how == TICKS:
                    value = np.arcsinh(value / TICK_PRICE_UNITS)
                elif name == 'ended_by':
                    value = float(value == P.CAME_BACK)
                self.figures[k, f] = float(value)
        self.before = np.full((len(facts), STEPS), -1, dtype=np.int64)
        b = {name: k for k, name in enumerate(chain_peaks.BEFORE_NAMES)}
        for line in lines['before']:
            if line[b['peak_high_position']] in place:
                self.before[place[line[b['peak_high_position']]], line[b['steps_back']] - 1] = \
                    place[line[b['earlier_high_position']]]
        self.complete = ~np.isnan(self.figures).any(axis=1)

    def enough(self, d: int):
        """The peaks that have d ended peaks before them."""
        return (self.before[:, :d] >= 0).all(axis=1)

    def scored(self, d: int):
        """The places of the peaks scored at step d: d ended peaks before, and no empty figure on any of them."""
        import numpy as np
        ok = self.complete & self.enough(d)
        ok[ok] = self.complete[self.before[ok, :d]].all(axis=1)
        return np.flatnonzero(ok)

    def matrices(self, d: int, given: int):
        """For the peaks scored at step d: the figures of the `given` nearest peaks before each, side by side, and
        the peak's own figures."""
        import numpy as np
        rows = self.scored(d)
        x = (np.hstack([self.figures[self.before[rows, k]] for k in range(given)]) if given
             else np.empty((len(rows), 0)))
        return x, self.figures[rows], rows


# ---------------------------------------------------------------- one model, one step, taught and scored
def _prepare(teach: list, scored: str, d: int, given: int):
    """The teaching and scoring matrices, each figure standardised on the teaching trade days."""
    import numpy as np
    parts = [_DAYS[day].matrices(d, given) for day in teach]
    x, y = np.vstack([p[0] for p in parts]), np.vstack([p[1] for p in parts])
    x_new, y_new, rows = _DAYS[scored].matrices(d, given)
    checks.need(len(y) and len(y_new), f'no peak to teach on or to score at step {d}')

    def standardise(a, b):
        mean, spread = a.mean(axis=0), a.std(axis=0)
        spread[spread == 0] = 1
        return (a - mean) / spread, (b - mean) / spread
    y, y_new = standardise(y, y_new)
    if given:
        x, x_new = standardise(x, x_new)
    return x, y, x_new, y_new, rows


def _fit(model: str, setting, x, y, choosing: bool):
    if model == RIDGE:
        from sklearn.linear_model import Ridge
        return Ridge(alpha=float(setting)).fit(x, y)
    if model == NEIGHBOURS:
        from sklearn.neighbors import KNeighborsRegressor
        return KNeighborsRegressor(n_neighbors=min(int(setting), len(x)), weights='distance', n_jobs=1).fit(x, y)
    from sklearn.ensemble import ExtraTreesRegressor
    return ExtraTreesRegressor(n_estimators=TREE_COUNT_CHOOSING if choosing else TREE_COUNT,
                               min_samples_leaf=int(setting), max_features=1.0, random_state=SEED,
                               n_jobs=1).fit(x, y)


def _ridge_again(setting, x, y, x_new):
    """Ridge in closed form: centred, the penalty on the weights only, as the library does it."""
    import numpy as np
    x_mean, y_mean = x.mean(axis=0), y.mean(axis=0)
    centred = x - x_mean
    weights = np.linalg.solve(centred.T @ centred + float(setting) * np.eye(x.shape[1]), centred.T @ (y - y_mean))
    return (x_new - x_mean) @ weights + y_mean


def model_at_step(model: str, d: int, given: int, teach: tuple, scored: str) -> dict:
    """One model at one step, given `given` peaks before: its setting chosen inside the teaching trade days, then
    taught on all of them and scored on the trade day it never saw. Gives each scored peak's squared error on each
    figure."""
    import numpy as np
    grid = {RIDGE: RIDGE_GRID, NEIGHBOURS: NEIGHBOUR_GRID, TREES: LEAF_GRID}[model]
    out = dict(model=model, step=d, given=given, setting=None, choosing={})
    x, y, x_new, y_new, rows = _prepare(list(teach), scored, d, given)
    out.update(rows=rows, peaks_taught_on=len(y), peaks_scored=len(y_new))
    if not given:                                      # no peak before: the teaching trade days' mean
        out['squared_error'] = np.square(y_new)
        return out
    best = None
    for setting in grid:                               # leave each teaching trade day out in turn
        errors = []
        for left_out in teach:
            a, b, a_new, b_new, _ = _prepare([day for day in teach if day != left_out], left_out, d, given)
            errors.append(float(np.square(b_new - _fit(model, setting, a, b, True).predict(a_new)).mean()))
        out['choosing'][str(setting)] = errors
        mean = float(np.mean(errors))
        if best is None or mean < best[0]:             # the first of the list on a tie, as the original
            best = (mean, setting)
    out['setting'] = best[1]
    predicted = _fit(model, best[1], x, y, False).predict(x_new)
    if model == RIDGE:
        apart = float(np.abs(predicted - _ridge_again(best[1], x, y, x_new)).max())
        checks.need(apart <= RIDGE_RECOUNT_TOLERANCE, f'ridge at step {d} given {given}: the closed form sits '
                                                      f'{apart} from the library')
        out['ridge_closed_form_furthest_apart'] = apart
    out['squared_error'] = np.square(y_new - predicted)
    return out


_JOBS = {'peak lines': peak_lines, 'model': model_at_step}


# ---------------------------------------------------------------- the run
def inputs_had_ended() -> dict:
    """The check on what the models were given: every peak used as an input became known before its target did,
    and its story had ended at or before the tick the target became known."""
    used = 0
    for name, day in _DAYS.items():
        for d in range(1, STEPS + 1):
            for row in day.scored(d).tolist():
                earlier = int(day.before[row, d - 1])
                checks.need(day.ended[earlier] <= day.known[row] and day.known[earlier] < day.known[row],
                            f'{name}: the peak at {day.high[row]} was given a peak whose story had not ended')
                used += 1
    return dict(passed=True, inputs_looked_at=used,
                what='every peak given to a model had a story that ended at or before the tick its target became '
                     'known')


def run(tape_folder: Path, scored_day: dt.date, out: Path) -> dict:
    """The chain link models for one trade day, taught on the other three: its table and its receipt."""
    import numpy as np
    import sklearn
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    days = sorted(tape.BUILT_TRADE_DAYS)
    text = {day: f'{day:%Y%m%d}' for day in days}
    scored = text[scored_day]
    teach = tuple(text[day] for day in days if day != scored_day)
    built = on_pinned_helpers([('peak lines', str(tape_folder), text[day]) for day in days])
    lines = {job[-1]: value for job, (_, _, value) in built.items()}
    _DAYS.update({day: Day(lines[day]) for day in lines})
    ended_first = inputs_had_ended()
    jobs = [('model', model, d, given, teach, scored) for model in reversed(MODELS)
            for d in range(STEPS, 0, -1) for given in (d, d - 1)]          # the longest pieces first
    fitted = on_pinned_helpers(jobs)
    at = {(job[1], job[2], job[3]): value for job, (_, _, value) in fitted.items()}

    me = _DAYS[scored]
    table = []
    for k, high in enumerate(me.high):
        for model in MODELS:
            for d in range(1, STEPS + 1):
                row = dict.fromkeys(LINE_NAMES)
                row.update(peak_high_position=high, peak_story_ended_position=me.ended[k], model=model, steps_back=d)
                without, with_it = at[model, d, d - 1], at[model, d, d]
                checks.need(np.array_equal(without['rows'], with_it['rows']), 'the paired sample is not the same')
                where = np.searchsorted(with_it['rows'], k)
                if where < len(with_it['rows']) and with_it['rows'][where] == k:
                    a, b = without['squared_error'][where], with_it['squared_error'][where]
                    row.update(setting_without=_number(without['setting']), setting_with=_number(with_it['setting']),
                               error_without=float(a.mean()), error_with=float(b.mean()),
                               gain=float(a.mean() - b.mean()))
                    row.update({f'without_{name}': float(a[f]) for f, name in enumerate(FIGURE_NAMES)})
                    row.update({f'with_{name}': float(b[f]) for f, name in enumerate(FIGURE_NAMES)})
                else:
                    row['not_scored_because'] = EMPTY_FIGURE if me.enough(d)[k] else TOO_FEW
                table.append(tuple(row[name] for name in LINE_NAMES))
    for high in me.still_open:
        for model in MODELS:
            for d in range(1, STEPS + 1):
                row = dict.fromkeys(LINE_NAMES)
                row.update(peak_high_position=high, model=model, steps_back=d, not_scored_because=STILL_OPEN)
                table.append(tuple(row[name] for name in LINE_NAMES))
    schema = store.schema(LINE_NAMES, LINE_TEXT, set(), LINE_DECIMALS)
    files = [part2.write(out, f'chain-models-{scored}-part{part:03d}.parquet', schema,
                         [list(c) for c in zip(*table[start:start + store.ROWS_PER_PART])])
             for part, start in enumerate(range(0, len(table), store.ROWS_PER_PART))]
    not_scored = {}
    for line in table:
        why, at_step = line[LINE_NAMES.index('not_scored_because')], line[LINE_NAMES.index('steps_back')]
        if why and line[LINE_NAMES.index('model')] == RIDGE:
            not_scored.setdefault(why, {}).setdefault(str(at_step), 0)
            not_scored[why][str(at_step)] += 1
    receipt = dict(
        what='ROOT part 2: the chain link models, one trade day scored by models taught on the other three',
        laid_out_and_approved=part2.LAID_OUT['chain_peaks'], trade_day_scored=scored_day.isoformat(),
        trade_days_taught_on=[day.isoformat() for day in days if day != scored_day],
        not_known_at_a_tick='These values are made afterwards by models taught on other trade days, some of them '
                            'later. They are kept in their own table and are never put on a tick row.',
        inputs={day: lines[day]['inputs'] for day in lines},
        figures=[dict(figure=name, enters_as=how) for name, how in FIGURES],
        settings=dict(ridge=RIDGE_GRID, nearest_neighbours=NEIGHBOUR_GRID, extra_trees_leaf=LEAF_GRID,
                      trees=TREE_COUNT, trees_while_choosing=TREE_COUNT_CHOOSING, seed=SEED, steps_back=STEPS,
                      tick_in_price_units=TICK_PRICE_UNITS),
        libraries=dict(python=platform.python_version(), numpy=np.__version__, scikit_learn=sklearn.__version__),
        columns=[dict(column=c, what=w) for c, w in LINE_COLUMNS],
        peaks={day: dict(peak_lines=len(_DAYS[day].high), still_open_at_the_last_tick=len(_DAYS[day].still_open),
                         with_an_empty_figure=int((~_DAYS[day].complete).sum()),
                         empty_by_figure={name: int(np.isnan(_DAYS[day].figures[:, f]).sum())
                                          for f, name in enumerate(FIGURE_NAMES)},
                         scored_at_each_step={str(d): int(len(_DAYS[day].scored(d))) for d in range(1, STEPS + 1)},
                         counts=lines[day]['counts']) for day in sorted(lines)},
        lines=len(table), not_scored_by_reason_and_step=not_scored, files=files,
        models=[dict(model=v['model'], step=v['step'], peaks_given=v['given'], setting=_number(v['setting']),
                     error_while_choosing_by_setting=v['choosing'], peaks_taught_on=v['peaks_taught_on'],
                     peaks_scored=v['peaks_scored'], mean_squared_error=float(v['squared_error'].mean()),
                     ridge_closed_form_furthest_apart=v.get('ridge_closed_form_furthest_apart'))
                for _, v in sorted(at.items(), key=lambda e: (MODELS.index(e[0][0]), e[0][1], e[0][2]))],
        helpers=dict(threads_each=1, pinned=True,
                     peak_lines=[dict(trade_day=job[-1], cpu=cpu, seconds=seconds)
                                 for job, (cpu, seconds, _) in sorted(built.items())],
                     models=[dict(model=job[1], step=job[2], peaks_given=job[3], cpu=cpu, seconds=seconds)
                             for job, (cpu, seconds, _) in sorted(fitted.items(),
                                                                  key=lambda e: (e[0][1], e[0][2], e[0][3]))]),
        checks=dict(inputs_had_ended=ended_first,
                    ridge_closed_form=dict(passed=True, tolerance=RIDGE_RECOUNT_TOLERANCE,
                                           what='ridge worked out again in closed form agrees with the library at '
                                                'every step'),
                    no_independent_recount='nearest neighbours and extra trees are not worked out a second way: '
                                           'their values rest on the library, pinned by version and seed'),
        empty_cells='stored as empty (null): never 0, never blank text',
        seconds=round(time.monotonic() - started, 1))
    (out / f'CHAIN-MODELS-{scored}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def _number(setting):
    return None if setting is None else float(setting)


def main():
    ap = argparse.ArgumentParser(description='ROOT part 2: the chain link models for one trade day')
    ap.add_argument('trade_day')
    ap.add_argument('--tape', type=Path, default=Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' /
                    'nymex_mbo' / 'ng_v0_oct2023')
    ap.add_argument('--out', type=Path, required=True, help='output folder (in markets-data, never in Markets)')
    a = ap.parse_args()
    receipt = run(a.tape, parse_trade_day(a.trade_day), a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day_scored', 'trade_days_taught_on', 'lines', 'peaks',
                                              'not_scored_by_reason_and_step', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
