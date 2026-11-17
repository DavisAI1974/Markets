"""ROOT part 2: what the chain ways share - the peak lines of a trade day rebuilt through the tape gate, the figures
of what a peak did, and the helpers pinned one to a CPU.

The averaging chain link models that lived in `chain_models.py` were removed on Greg's word (2026-11-17: "take out
all.of the other averages"; every trade individually is the cardinal rule). Their stored results were deleted the
same day. What they shared with the individual way is kept here.
"""
from __future__ import annotations

import os

THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')
for _name in THREADS:                                  # one thread a helper, set before numpy is loaded
    os.environ[_name] = '1'

import multiprocessing
import queue
import time
import traceback
from pathlib import Path

from root import checks, part2, tape
from root.calcs import chain_peaks
from root.calcs import peak_story as P
from root.calendar import parse_trade_day

TICK_PRICE_UNITS = 1_000_000                           # one tick of the contract ($0.001) in the tape's price units
HELPER_POLL_SECONDS = 5                                # how often the runner looks whether a helper has died
STEPS = chain_peaks.STEPS_BACK
AS_IS, LOG, YES_NO, TICKS = 'as it is', 'log(1 + value)', '1 for yes, 0 for no', 'arcsinh of ticks'
FIGURES = [('size', AS_IS), ('low_to_high_ns', LOG), ('ended_by', YES_NO), ('high_to_end_ns', LOG),
           ('lowest_share', AS_IS), ('steps_down', LOG), ('price_move_with_side', TICKS),
           ('furthest_price_with_side', TICKS), ('furthest_price_against_side', TICKS),
           ('same_side_as_peak_before', YES_NO)]
FIGURE_NAMES = [name for name, _ in FIGURES]
queue_empty = queue.Empty



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


_JOBS = {'peak lines': peak_lines}
