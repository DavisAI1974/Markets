"""odcore/swing_bigline.py — the BIG LINE strategy (Greg, S54): ride the trendline, exit on the break.

Greg's spec (S54, from the SPX chart): the optimal shape is the straight line TOUCHING the graph —
a trend support line through successive confirmed pivot lows (long side; mirror with pivot highs on
the way down). You are in for the whole ride while price respects the line, and out exactly once,
when price breaks through it. The line is adaptive: as the trend accelerates it is redrawn through
the two most recent pivots (the re-steepening in the chart). This is a DIFFERENT exit engine from
the fixed-theta zigzag flip: the giveback at exit is the distance to the line, not a fixed retrace.

Causality (falsification-first): a trendline through lows is only drawable in hindsight, so the
engine anchors ONLY on pivots already CONFIRMED by the causal zigzag (a valley is confirmed when
price has risen theta_pivot off it). A line exists only after TWO confirmed rising valleys; entry
happens at the second confirmation, never at the pivot itself. Everything at index t uses data
[0..t] only — `position_signal_at` is provided for odcore.leakage.assert_no_leakage.

This module does NOT touch the zigzag/one-shot/accum code paths (swing_maker / swing_accum are
untouched); it is a sibling engine, per Greg: "we don't overwrite the zigzag code".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class BigLineLeg:
    side: int                 # +1 long (rising support line), -1 short (falling resistance line)
    entry_i: int
    exit_i: int
    entry_px: float
    exit_px: float
    n_redraws: int            # how many times the line was redrawn during the ride
    forced: bool              # True if closed by end-of-data, not by a line break
    segments: List[Tuple[int, int, float, float]] = field(default_factory=list)
    # segments: (i_start, i_end, px_at_i_start, slope_per_cell) — for rendering the line's evolution

    @property
    def gross_bps(self) -> float:
        return self.side * (self.exit_px - self.entry_px) / self.entry_px * 1e4

    @property
    def hold_cells(self) -> int:
        return self.exit_i - self.entry_i


def run_bigline(mid: np.ndarray, theta_pivot_bps: float, break_eps_bps: float,
                align: bool = True) -> List[BigLineLeg]:
    """Single-position long/short big-line engine on a mid series (any uniform grid).

    theta_pivot_bps: causal zigzag scale that CONFIRMS the pivots the lines anchor on.
    break_eps_bps:   price must cross the line by this much (bps of line value) to count as a break.
    align:           Greg's S54 correction — the line must be on the TREND's side. Long only when
                     higher lows AND higher highs (uptrend -> support line below); short only when
                     lower highs AND lower lows (downtrend -> resistance line above). align=False
                     keeps the v1 one-sided behavior (kept for A/B measurement only).
    """
    th = theta_pivot_bps / 1e4
    eps = break_eps_bps / 1e4
    n = len(mid)
    legs: List[BigLineLeg] = []

    lo_i = hi_i = 0
    mode = 0                       # zigzag state: +1 tracking high (last pivot valley), -1 tracking low
    valleys: List[Tuple[int, float]] = []   # (pivot_i, pivot_px), confirmed causally
    peaks: List[Tuple[int, float]] = []

    pos = 0
    anchor_i = -1
    anchor_px = 0.0
    slope = 0.0                    # px per cell
    entry_i = -1
    entry_px = 0.0
    n_redraws = 0
    seg_start = -1
    segments: List[Tuple[int, int, float, float]] = []

    def _line_at(t: int) -> float:
        return anchor_px + slope * (t - anchor_i)

    for t in range(1, n):
        m = float(mid[t])
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t

        new_valley = new_peak = False
        if mode >= 0 and m <= mid[hi_i] * (1.0 - th):    # PEAK confirmed
            peaks.append((hi_i, float(mid[hi_i])))
            mode = -1
            lo_i = t
            new_peak = True
        elif mode <= 0 and m >= mid[lo_i] * (1.0 + th):  # VALLEY confirmed
            valleys.append((lo_i, float(mid[lo_i])))
            mode = +1
            hi_i = t
            new_valley = True

        # ---- exit on line break (checked before any redraw/entry at this cell) ----
        if pos == +1:
            L = _line_at(t)
            if m < L * (1.0 - eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(+1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []
        elif pos == -1:
            L = _line_at(t)
            if m > L * (1.0 + eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(-1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []

        # ---- line formation / redraw on a fresh pivot confirmation ----
        if new_valley and len(valleys) >= 2:
            (i1, p1), (i2, p2) = valleys[-2], valleys[-1]
            hh = (not align) or (len(peaks) >= 2 and peaks[-1][1] > peaks[-2][1])
            if p2 > p1:                                   # rising lows -> a long support line exists
                s = (p2 - p1) / (i2 - i1)
                if pos == +1:                             # redraw (re-steepen/flatten with the trend)
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t
                elif pos == 0 and hh:                     # new ride: uptrend = HH + HL (align)
                    anchor_i, anchor_px, slope = i2, p2, s
                    pos = +1
                    entry_i, entry_px = t, m
                    n_redraws = 0
                    seg_start = t
                    segments = []
        if new_peak and len(peaks) >= 2:
            (i1, p1), (i2, p2) = peaks[-2], peaks[-1]
            ll = (not align) or (len(valleys) >= 2 and valleys[-1][1] < valleys[-2][1])
            if p2 < p1:                                   # falling highs -> a short resistance line
                s = (p2 - p1) / (i2 - i1)
                if pos == -1:
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t
                elif pos == 0 and ll:                     # new ride: downtrend = LL + LH (align)
                    anchor_i, anchor_px, slope = i2, p2, s
                    pos = -1
                    entry_i, entry_px = t, m
                    n_redraws = 0
                    seg_start = t
                    segments = []

    if pos != 0:                                          # end of data: force-close, flagged
        t = n - 1
        segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
        legs.append(BigLineLeg(pos, entry_i, t, entry_px, float(mid[t]), n_redraws, True, segments))
    return legs


def run_bigline_adaptive(mid: np.ndarray, frac: float, window_cells: int,
                         theta_min_bps: float = 15.0, theta_max_bps: float = 120.0,
                         eps_frac: float = 1.0 / 6.0, align: bool = True,
                         lean: Optional[np.ndarray] = None, x_frac: float = 0.5,
                         require_flip: bool = True) -> List[BigLineLeg]:
    """Adaptive-scale big line (Greg, S54: "when it gets choppier, scale the lines down").

    theta_pivot at time t = frac x trailing realized range (rolling hi-lo over `window_cells`,
    in bps), clipped to [theta_min, theta_max]; break eps = eps_frac x theta. Causal: the range
    uses data up to t only. theta re-measures CONTINUOUSLY, in-ride included (Greg, S54 DOGE
    walkthrough): when a move plateaus the bounce-back requirement shrinks with the chop, pivots
    keep confirming, and the line ratchets along hugging the price instead of trailing the entry-
    era chord; "you don't want it hitting every little peak or valley, you want some bounce back
    first — it cuts the chop out" is the theta confirmation itself. Same single-position
    long/short state machine as run_bigline, trend-aligned entries included.

    DIPOLE-FLIP fast confirm (Greg, S54: "for the bounce back you want the dipole flip +
    (x_price)"): if `lean` (trailing flow imbalance, odcore.flip_detector.lean_series — causal)
    is given, a pivot ALSO confirms on the fast path bounce >= x_frac*theta AND the lean's sign
    agreeing with the new direction (flow already changed hands). The full-theta price bounce
    stays as the flow-agnostic fallback, so no turn is ever eliminated — the dipole only
    confirms it earlier. require_flip=False is the honesty ablation (same cheaper bounce, no
    flow requirement): if that scores the same, the dipole adds nothing.
    """
    from collections import deque

    n = len(mid)
    legs: List[BigLineLeg] = []
    maxq: "deque[int]" = deque()   # indices, mid decreasing
    minq: "deque[int]" = deque()   # indices, mid increasing

    lo_i = hi_i = 0
    mode = 0
    valleys: List[Tuple[int, float]] = []
    peaks: List[Tuple[int, float]] = []

    pos = 0
    anchor_i = -1
    anchor_px = 0.0
    slope = 0.0
    entry_i = -1
    entry_px = 0.0
    n_redraws = 0
    seg_start = -1
    segments: List[Tuple[int, int, float, float]] = []
    th = theta_min_bps / 1e4
    eps = th * eps_frac

    for t in range(1, n):
        m = float(mid[t])
        # rolling hi-lo range (causal, O(1) amortized)
        while maxq and mid[maxq[-1]] <= m:
            maxq.pop()
        maxq.append(t)
        while minq and mid[minq[-1]] >= m:
            minq.pop()
        minq.append(t)
        w0 = t - window_cells
        while maxq[0] <= w0:
            maxq.popleft()
        while minq[0] <= w0:
            minq.popleft()
        rng_bps = (mid[maxq[0]] - mid[minq[0]]) / m * 1e4   # continuous re-measure (in-ride too)
        th = min(max(frac * rng_bps, theta_min_bps), theta_max_bps) / 1e4
        eps = th * eps_frac

        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t

        if lean is None:
            fast_dn = fast_up = False
        else:
            fast_dn = (m <= mid[hi_i] * (1.0 - x_frac * th)
                       and ((not require_flip) or lean[t] < 0))
            fast_up = (m >= mid[lo_i] * (1.0 + x_frac * th)
                       and ((not require_flip) or lean[t] > 0))
        new_valley = new_peak = False
        if mode >= 0 and (m <= mid[hi_i] * (1.0 - th) or (mode != 0 and fast_dn)):
            peaks.append((hi_i, float(mid[hi_i])))
            mode = -1
            lo_i = t
            new_peak = True
        elif mode <= 0 and (m >= mid[lo_i] * (1.0 + th) or (mode != 0 and fast_up)):
            valleys.append((lo_i, float(mid[lo_i])))
            mode = +1
            hi_i = t
            new_valley = True

        if pos == +1:
            L = anchor_px + slope * (t - anchor_i)
            if m < L * (1.0 - eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(+1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []
        elif pos == -1:
            L = anchor_px + slope * (t - anchor_i)
            if m > L * (1.0 + eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(-1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []

        if new_valley and len(valleys) >= 2:
            (i1, p1), (i2, p2) = valleys[-2], valleys[-1]
            hh = (not align) or (len(peaks) >= 2 and peaks[-1][1] > peaks[-2][1])
            if p2 > p1:
                s = (p2 - p1) / (i2 - i1)
                if pos == +1:
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t
                elif pos == 0 and hh:
                    anchor_i, anchor_px, slope = i2, p2, s
                    pos = +1
                    entry_i, entry_px = t, m
                    n_redraws = 0
                    seg_start = t
                    segments = []
        if new_peak and len(peaks) >= 2:
            (i1, p1), (i2, p2) = peaks[-2], peaks[-1]
            ll = (not align) or (len(valleys) >= 2 and valleys[-1][1] < valleys[-2][1])
            if p2 < p1:
                s = (p2 - p1) / (i2 - i1)
                if pos == -1:
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t
                elif pos == 0 and ll:
                    anchor_i, anchor_px, slope = i2, p2, s
                    pos = -1
                    entry_i, entry_px = t, m
                    n_redraws = 0
                    seg_start = t
                    segments = []

    if pos != 0:
        t = n - 1
        segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
        legs.append(BigLineLeg(pos, entry_i, t, entry_px, float(mid[t]), n_redraws, True, segments))
    return legs


def ride_from_entries(mid: np.ndarray, entries, frac: float, window_cells: int,
                      theta_min_bps: float = 15.0, theta_max_bps: float = 120.0,
                      eps_frac: float = 1.0 / 6.0) -> List[BigLineLeg]:
    """Greg's S54 hybrid: ZIGZAG ENTRY + BIG LINE EXIT ("use our same entry strategy from zig
    zag ... it's our exit that we want to deploy the big line on").

    entries: [(confirm_idx, pivot_idx, side)] from the deployed fine-scale flip detector
    (odcore.flip_detector.detect_flips or the causal price zigzag) — cloned, not modified.

    Mechanics per ride: enter at the flip's confirm cell. The initial line is FLAT at the entry
    flip's pivot extreme (if price falls back through the turn low, the turn failed). As new
    pivots confirm at the ADAPTIVE line scale (frac x trailing range, continuous re-measure),
    the line is redrawn through the two most recent same-side pivots — RATCHET ONLY (the new
    line must sit at or above the old one at the current cell for longs; mirror for shorts) so
    the trailing stop never loosens. Exit on the line break by eps. Entries firing while in a
    ride are ignored (letting the winner ride IS the point). Single position, both sides.
    """
    from collections import deque

    n = len(mid)
    legs: List[BigLineLeg] = []
    ent = sorted([(int(c), int(p), int(s)) for (c, p, s) in entries])
    e_k = 0
    maxq: "deque[int]" = deque()
    minq: "deque[int]" = deque()

    lo_i = hi_i = 0
    mode = 0
    valleys: List[Tuple[int, float]] = []
    peaks: List[Tuple[int, float]] = []

    pos = 0
    anchor_i = -1
    anchor_px = 0.0
    slope = 0.0
    entry_i = -1
    entry_px = 0.0
    n_redraws = 0
    seg_start = -1
    segments: List[Tuple[int, int, float, float]] = []
    th = theta_min_bps / 1e4
    eps = th * eps_frac

    for t in range(1, n):
        m = float(mid[t])
        while maxq and mid[maxq[-1]] <= m:
            maxq.pop()
        maxq.append(t)
        while minq and mid[minq[-1]] >= m:
            minq.pop()
        minq.append(t)
        w0 = t - window_cells
        while maxq[0] <= w0:
            maxq.popleft()
        while minq[0] <= w0:
            minq.popleft()
        rng_bps = (mid[maxq[0]] - mid[minq[0]]) / m * 1e4
        th = min(max(frac * rng_bps, theta_min_bps), theta_max_bps) / 1e4
        eps = th * eps_frac

        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        new_valley = new_peak = False
        if mode >= 0 and m <= mid[hi_i] * (1.0 - th):
            peaks.append((hi_i, float(mid[hi_i])))
            mode = -1
            lo_i = t
            new_peak = True
        elif mode <= 0 and m >= mid[lo_i] * (1.0 + th):
            valleys.append((lo_i, float(mid[lo_i])))
            mode = +1
            hi_i = t
            new_valley = True

        # ---- exit on line break ----
        if pos == +1:
            L = anchor_px + slope * (t - anchor_i)
            if m < L * (1.0 - eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(+1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []
        elif pos == -1:
            L = anchor_px + slope * (t - anchor_i)
            if m > L * (1.0 + eps):
                segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                legs.append(BigLineLeg(-1, entry_i, t, entry_px, m, n_redraws, False, segments))
                pos = 0
                segments = []

        # ---- ratcheting redraw while riding ----
        if pos == +1 and new_valley and len(valleys) >= 2:
            (i1, p1), (i2, p2) = valleys[-2], valleys[-1]
            if p2 > p1:
                s = (p2 - p1) / (i2 - i1)
                if p2 + s * (t - i2) >= anchor_px + slope * (t - anchor_i):   # ratchet only
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t
        elif pos == -1 and new_peak and len(peaks) >= 2:
            (i1, p1), (i2, p2) = peaks[-2], peaks[-1]
            if p2 < p1:
                s = (p2 - p1) / (i2 - i1)
                if p2 + s * (t - i2) <= anchor_px + slope * (t - anchor_i):
                    segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
                    anchor_i, anchor_px, slope = i2, p2, s
                    n_redraws += 1
                    seg_start = t

        # ---- zigzag entries (cloned stream), only when flat ----
        while e_k < len(ent) and ent[e_k][0] <= t:
            (ci, pi, side) = ent[e_k]
            e_k += 1
            if ci == t and pos == 0:
                pos = int(side)
                entry_i, entry_px = t, m
                anchor_i, anchor_px = int(pi), float(mid[int(pi)])   # flat stop at the turn extreme
                slope = 0.0
                n_redraws = 0
                seg_start = t
                segments = []

    if pos != 0:
        t = n - 1
        segments.append((seg_start, t, anchor_px + slope * (seg_start - anchor_i), slope))
        legs.append(BigLineLeg(pos, entry_i, t, entry_px, float(mid[t]), n_redraws, True, segments))
    return legs


def position_series(mid: np.ndarray, theta_pivot_bps: float, break_eps_bps: float) -> np.ndarray:
    """Per-cell position (+1/0/-1) implied by the legs — for exposure accounting and controls."""
    pos = np.zeros(len(mid), dtype=np.int8)
    for l in run_bigline(mid, theta_pivot_bps, break_eps_bps):
        pos[l.entry_i:l.exit_i] = l.side
    return pos


def position_signal_at(i, ts, p, bv, sv, *, theta_pivot_bps: float, break_eps_bps: float):
    """Leakage-gate adapter (odcore.leakage.assert_no_leakage): position as of index i, computed by
    running the engine on p[:i+1] ONLY. bv/sv unused — the big line is price-only."""
    sub = np.asarray(p[: int(i) + 1], float)
    if len(sub) < 3:
        return 0
    legs = run_bigline(sub, theta_pivot_bps, break_eps_bps)
    if not legs:
        return 0
    last = legs[-1]
    return int(last.side) if last.forced else 0   # forced == still open as of i
