"""The search's step transforms: each turns one series on the day's axis into a step series of -1/0/+1.

Brief piece C (CHATGPT_BRIEF_EXPERIMENT_20260929.md), built by Claude on Greg's word ("I'm going to have you do
chatgpts part", 2026-09-29). The search (frankie_box_experiment_search.py) counts couplings between step series with
ONE statistic and ONE chance check (the joined teacher's, `couple`); every transform here returns the same shape so the
statistic and the chance check stay unchanged:

    f(values: np.ndarray of length n, float, NaN where the series was not yet known) -> np.ndarray of length n-1, int8

Step i of the output belongs to the move from axis row i to axis row i+1 (the same alignment as np.diff), so a step
series from any transform lines up with every other on the same cells and lags.

CAUSAL. Step i uses only axis rows 0..i+1, never a later row: the running statistics (the medians) are taken over the
rows BEFORE the one being classified, so a row never enters its own threshold. Nothing is capped, trimmed, sampled,
smoothed or normalized; the running medians are the LOWER median (an observed value, never the mean of the two middle
values). A step that cannot be classified (a NaN on either side, no earlier data for the running median) is 0 and is
counted by `unclassified`, never filled in.

These are orientation for the search; the finding stays counts per pair, cell, lag and day (D37).
"""
import heapq

import numpy as np


def _steps(values):
    """First differences with NaN (unknown) kept as NaN."""
    v = np.asarray(values, dtype=np.float64)
    return np.diff(v)


def _sign(d):
    s = np.sign(d)
    s[~np.isfinite(d)] = 0
    return s.astype(np.int8)


class _RunningLowerMedian:
    """The lower median of every value added so far (two heaps; exact, no window, no cap)."""

    def __init__(self):
        self.lo = []          # max-heap (negated): the lower half, holds the median on top
        self.hi = []          # min-heap: the upper half

    def __len__(self):
        return len(self.lo) + len(self.hi)

    def add(self, x):
        if self.lo and x > -self.lo[0]:
            heapq.heappush(self.hi, x)
        else:
            heapq.heappush(self.lo, -x)
        if len(self.lo) > len(self.hi) + 1:
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
        elif len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def median(self):
        return -self.lo[0]


def sign_of_step(values):
    """+1 the series rose from the previous axis row, -1 it fell, 0 unchanged or unknown. The search's original step."""
    return _sign(_steps(values))


def run_length(values):
    """+1 when a move continues the run (same sign as the last non-zero move), -1 when it breaks the run (the opposite
    sign), 0 when the series did not move, is unknown, or has no earlier move to compare with. Unchanged rows do not end
    a run: the run is the sequence of non-zero moves, so a pause carries the last move's sign through."""
    s = sign_of_step(values)
    out = np.zeros(s.size, dtype=np.int8)
    nz = np.nonzero(s)[0]
    if nz.size > 1:
        out[nz[1:]] = np.where(s[nz[1:]] == s[nz[:-1]], 1, -1)
    return out


def magnitude_class(values):
    """+1 when the size of a move is above the running lower median of the sizes of all EARLIER non-zero moves of the
    same series, -1 when below, 0 when equal, when the series did not move (a zero step has no size class), when either
    side is unknown, or when no earlier move exists. The size is |step|; the sign of the move is not in this series
    (sign_of_step carries it)."""
    d = _steps(values)
    out = np.zeros(d.size, dtype=np.int8)
    med = _RunningLowerMedian()
    for i in range(d.size):
        x = d[i]
        if not np.isfinite(x) or x == 0:
            continue
        a = abs(float(x))
        if len(med):
            m = med.median()
            out[i] = 1 if a > m else (-1 if a < m else 0)
        med.add(a)
    return out


def level_crossing(values):
    """+1 when the series crosses UP through the running lower median of all its EARLIER known values, -1 when it crosses
    DOWN, 0 otherwise. The side of row j is the sign of (value[j] - median of the known values before row j); a crossing
    is a side that differs from the last non-zero side. Step i reports the crossing at row i+1; row 0 has no earlier
    value, so the first side is set at the first row with an earlier known value and no crossing is reported for it."""
    v = np.asarray(values, dtype=np.float64)
    out = np.zeros(max(v.size - 1, 0), dtype=np.int8)
    med = _RunningLowerMedian()
    last_side = 0
    for j in range(v.size):
        x = v[j]
        if not np.isfinite(x):
            continue
        x = float(x)
        if len(med):
            m = med.median()
            side = 1 if x > m else (-1 if x < m else 0)
            if side != 0:
                if last_side != 0 and side != last_side and j >= 1:
                    out[j - 1] = side
                last_side = side
        med.add(x)
    return out


def acceleration(values):
    """The sign of the first difference of the first difference: +1 when this move is larger (more up, less down) than
    the previous move, -1 when smaller, 0 when equal or when either move is unknown. Step 0 has no previous move."""
    d = _steps(values)
    out = np.zeros(d.size, dtype=np.int8)
    if d.size > 1:
        out[1:] = _sign(np.diff(d))
    return out


TRANSFORMS = {
    'sign_of_step': sign_of_step,
    'run_length': run_length,
    'magnitude_class': magnitude_class,
    'level_crossing': level_crossing,
    'acceleration': acceleration,
}


def unclassified(values, steps):
    """Steps a transform left at 0 because an input was unknown (NaN on either side): listed per series, never filled."""
    v = np.asarray(values, dtype=np.float64)
    unknown = ~(np.isfinite(v[:-1]) & np.isfinite(v[1:]))
    return int(np.count_nonzero(unknown & (np.asarray(steps) == 0)))
