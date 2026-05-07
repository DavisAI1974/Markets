"""
edge_tracker.py — multi-horizon per-cell forward-predictive r tracker.

Mechanism: the existing chunk-level Gate I metric (Pearson r of
`(chunk_t.mean_dipole, chunk_{t+1}.log_return)` per regime) collapses
all available data into a single number per cell. That hides time-
dependent signal evolution: a cell that was a STRONG daily signal for
two weeks then faded over the next month would show as "flat aggregate
r" even though it had a tradable daily edge for half its history.

This module tracks each `(asset, venue, regime)` cell's running r over
THREE time-based windows simultaneously:

    daily    = last 24 h
    weekly   = last  7 d
    longterm = last 30 d

For each window we report:
  - strength tag: STRONG / MODERATE / WEAK / NEW (insufficient n)
  - direction:    "fade" (r<0) or "momentum" (r>0)
  - trend (vs the next-broader window):
        STRENGTHENING : |r_short| > 1.3 × |r_broad| AND same sign
        WEAKENING     : |r_short| < 0.7 × |r_broad|, OR sign flip
        STABLE        : neither condition

Surfaces per cell on RegimeStatus + SignalEvent so the PWA / Discord
playbook can say e.g.
    "Long-term flat. Weekly fade strengthening. Daily fade STRONG."

Persists to `backend_edge_history.jsonl` so warm starts retain enough
history to populate weekly/longterm windows immediately.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

import numpy as np


# Window durations (seconds). Hardcoded as policy this session — these
# correspond to canonical "daily / weekly / month" trader horizons.
DAILY_WINDOW_S = 24 * 60 * 60
WEEKLY_WINDOW_S = 7 * 24 * 60 * 60
LONGTERM_WINDOW_S = 30 * 24 * 60 * 60

# Min n per window to report a strength tag. Below this we report "NEW".
MIN_N_DAILY = 6
MIN_N_WEEKLY = 20
MIN_N_LONGTERM = 30

# Strength thresholds on |r|. STRONG also requires p < STRONG_P_MAX.
STRONG_R_MIN = 0.15
STRONG_P_MAX = 0.10
MODERATE_R_MIN = 0.08

# Trend thresholds vs the broader window.
TREND_STRENGTHEN_RATIO = 1.3
TREND_WEAKEN_RATIO = 0.7

# Bound on per-cell history (memory cap). Beyond this oldest entries get
# evicted regardless of the longterm window. Keeps the deque from growing
# without bound for highly-active cells.
MAX_HISTORY_PER_CELL = 5000


@dataclass
class _Sample:
    ts: float           # seconds since epoch — the timestamp of the chunk whose mean_dipole is the predictor
    mean_dipole: float  # x — predictor
    forward_return: float  # y — log return of the FOLLOWING chunk

    def to_dict(self) -> dict:
        return {"ts": self.ts, "mean_dipole": self.mean_dipole,
                 "forward_return": self.forward_return}


@dataclass
class HorizonStat:
    """Per-(cell, window) computed metrics.

    self_trend is computed by splitting the window's samples into 4
    quarter-windows by ts (q1=oldest, q4=most recent) and looking at:
      - sign-change count across consecutive quarters (q1→q2, q2→q3, q3→q4)
      - r magnitudes in q1 and q4 (or first-half vs second-half if too few)

    Categories:
      FLIPPING      : >=2 sign changes across quarters (signal sign is unstable)
      STRENGTHENING : same sign throughout, |r_recent| > 1.3 × |r_old|
      DECAYING      : same sign throughout, |r_recent| < 0.7 × |r_old|
      STABLE        : same sign, |r| roughly constant
      NEW           : not enough data to split (n<8 or sparse quarters)

    Captures "is this edge getting stronger / weaker / flipping WITHIN
    this horizon" — orthogonal to the cross-horizon trend (daily vs
    weekly, weekly vs longterm).
    """
    n: int = 0
    r: float | None = None
    p: float | None = None
    strength: str = "NEW"      # STRONG | MODERATE | WEAK | NEW
    direction: str = ""        # "fade" | "momentum" | ""
    self_trend: str = "NEW"    # STRENGTHENING | DECAYING | FLIPPING | STABLE | NEW
    n_sign_flips: int = 0      # how many of the (q1->q2, q2->q3, q3->q4) transitions flipped sign

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CellTags:
    """Tags for one (asset, venue, regime) cell across all horizons + trends."""
    asset: str = ""
    venue: str = ""
    regime: str = ""
    daily: HorizonStat = field(default_factory=HorizonStat)
    weekly: HorizonStat = field(default_factory=HorizonStat)
    longterm: HorizonStat = field(default_factory=HorizonStat)
    # Trends compare a window to the next-broader one.
    daily_trend: str = "STABLE"     # STRENGTHENING | WEAKENING | STABLE | UNKNOWN
    weekly_trend: str = "STABLE"
    summary: str = ""               # human-readable one-liner for the playbook

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _pearson_with_p(xs: np.ndarray, ys: np.ndarray) -> tuple[float | None, float | None]:
    n = len(xs)
    if n < 3:
        return None, None
    if np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
        return 0.0, 1.0
    r = float(np.corrcoef(xs, ys)[0, 1])
    if not np.isfinite(r) or abs(r) >= 1.0:
        return r, None
    t = r * math.sqrt(n - 2) / math.sqrt(max(1.0 - r * r, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return r, float(p)


def _classify_strength(n: int, r: float | None, p: float | None,
                          min_n: int) -> tuple[str, str]:
    """Return (strength, direction)."""
    if n < min_n or r is None:
        return "NEW", ""
    direction = "fade" if r < 0 else ("momentum" if r > 0 else "")
    if abs(r) >= STRONG_R_MIN and p is not None and p < STRONG_P_MAX:
        return "STRONG", direction
    if abs(r) >= MODERATE_R_MIN:
        return "MODERATE", direction
    return "WEAK", direction


def _quarter_rs(samples: list[_Sample]) -> list[float | None]:
    """Split samples into 4 quarter-windows by ts ordering and compute r
    per quarter. Returns 4 entries, with None for any quarter whose r
    can't be computed (n<3 or zero variance). Caller treats None as
    'no read' for sign-change counting (skip those transitions)."""
    if not samples:
        return [None] * 4
    ordered = sorted(samples, key=lambda s: s.ts)
    n = len(ordered)
    if n < 8:
        # Not enough to split into 4 meaningful chunks.
        return [None] * 4
    # Fenceposts at quartile indices.
    q_size = n / 4.0
    out: list[float | None] = []
    for q in range(4):
        a = int(round(q * q_size))
        b = int(round((q + 1) * q_size))
        seg = ordered[a:b]
        if len(seg) < 3:
            out.append(None)
            continue
        xs = np.asarray([s.mean_dipole for s in seg], dtype=float)
        ys = np.asarray([s.forward_return for s in seg], dtype=float)
        r, _ = _pearson_with_p(xs, ys)
        out.append(r)
    return out


def _classify_self_trend(samples: list[_Sample]
                            ) -> tuple[str, int]:
    """Return (self_trend, n_sign_flips) for one window's samples.

    Splits into 4 quarter-windows by ts; counts sign flips on
    consecutive quarter pairs (skipping any pair with a None r);
    compares oldest-defined-quarter to newest-defined-quarter for
    strengthening/decaying.
    """
    qrs = _quarter_rs(samples)
    defined = [(i, r) for i, r in enumerate(qrs) if r is not None]
    if len(defined) < 2:
        return "NEW", 0
    # Sign flips: walk consecutive defined quarters
    n_flips = 0
    for i in range(len(defined) - 1):
        _, ra = defined[i]
        _, rb = defined[i + 1]
        # Treat |r|<0.02 as effectively zero; don't count near-zero as a flip
        if abs(ra) < 0.02 or abs(rb) < 0.02:
            continue
        if (ra > 0) != (rb > 0):
            n_flips += 1
    if n_flips >= 2:
        return "FLIPPING", n_flips
    # Compare oldest vs newest defined quarters
    _, r_old = defined[0]
    _, r_new = defined[-1]
    if abs(r_old) < 1e-6:
        # Old was zero; if new is meaningful, that's strengthening
        if abs(r_new) >= MODERATE_R_MIN:
            return "STRENGTHENING", n_flips
        return "STABLE", n_flips
    same_sign = (r_new >= 0) == (r_old >= 0)
    if not same_sign:
        # Single sign flip → DECAYING (the old direction has lost grip)
        return "DECAYING", n_flips
    ratio = abs(r_new) / abs(r_old)
    if ratio >= TREND_STRENGTHEN_RATIO:
        return "STRENGTHENING", n_flips
    if ratio <= TREND_WEAKEN_RATIO:
        return "DECAYING", n_flips
    return "STABLE", n_flips


def _classify_trend(short: HorizonStat, broad: HorizonStat) -> str:
    """STRENGTHENING / WEAKENING / STABLE / UNKNOWN.

    UNKNOWN when broad doesn't have enough data yet (we can't compare).
    Strengthening = the short-horizon edge is materially larger AND same
    sign as the broad horizon. Weakening = short is materially smaller
    or sign flipped.
    """
    if short.r is None or broad.r is None:
        return "UNKNOWN"
    s = short.r
    b = broad.r
    # Same-sign ratio comparison — careful with near-zero broad.
    if abs(b) < 1e-6:
        # Broad is ~zero; any meaningful short signal is "strengthening"
        # in the absolute sense, weakening if short is also near-zero.
        return "STRENGTHENING" if abs(s) >= MODERATE_R_MIN else "STABLE"
    same_sign = (s >= 0) == (b >= 0)
    ratio = abs(s) / abs(b)
    if not same_sign:
        return "WEAKENING"
    if ratio >= TREND_STRENGTHEN_RATIO:
        return "STRENGTHENING"
    if ratio <= TREND_WEAKEN_RATIO:
        return "WEAKENING"
    return "STABLE"


def _summary_for(tags: CellTags) -> str:
    """Human-readable one-liner for the playbook.

    Surfaces strength + direction + self_trend per horizon. Cross-horizon
    trends (daily_vs_weekly, weekly_vs_longterm) are appended only when
    they fire (STRENGTHENING / WEAKENING) to keep the line short.
    """
    def _phrase(window: str, st: HorizonStat) -> str:
        if st.strength == "NEW":
            return f"{window} tracking (n={st.n})"
        dir_word = "" if not st.direction else (" " + st.direction)
        trend_word = ""
        if st.self_trend in ("STRENGTHENING", "DECAYING", "FLIPPING"):
            trend_word = f" {st.self_trend.lower()}"
        return f"{window} {st.strength.lower()}{dir_word}{trend_word} (r={st.r:+.2f}, n={st.n})"

    parts = [
        _phrase("Long-term", tags.longterm),
        _phrase("Weekly",    tags.weekly),
        _phrase("Daily",     tags.daily),
    ]
    # Append cross-horizon comparisons only when they fire actionably.
    extras = []
    if tags.weekly_trend in ("STRENGTHENING", "WEAKENING"):
        extras.append(f"weekly {tags.weekly_trend.lower()} vs long-term")
    if tags.daily_trend in ("STRENGTHENING", "WEAKENING"):
        extras.append(f"daily {tags.daily_trend.lower()} vs weekly")
    base = ". ".join(parts) + "."
    if extras:
        base += "  (" + "; ".join(extras) + ".)"
    return base


class MultiHorizonEdgeTracker:
    """Maintains rolling history per `(asset, venue, regime)` cell and
    derives per-window strength + trend tags. Designed for the live
    backend's poll loop: O(1) update, O(n) compute on demand.
    """

    def __init__(self, history_path: str | None = None):
        self._buffers: dict[tuple[str, str, str], deque] = {}
        self.history_path = history_path
        if history_path and os.path.exists(history_path):
            self._restore_from_disk()

    # ----- update path -----

    def update(self, asset: str, venue: str, regime: str,
                 ts: float, mean_dipole: float, forward_return: float) -> None:
        """Append one observation to the cell's history. Caller computes
        forward_return as the log return of the chunk AFTER the chunk
        whose mean_dipole this is (Gate I lag-1 convention).
        """
        if not (math.isfinite(mean_dipole) and math.isfinite(forward_return)):
            return
        key = (asset, venue, regime)
        buf = self._buffers.get(key)
        if buf is None:
            buf = deque(maxlen=MAX_HISTORY_PER_CELL)
            self._buffers[key] = buf
        buf.append(_Sample(ts=float(ts), mean_dipole=float(mean_dipole),
                             forward_return=float(forward_return)))
        if self.history_path:
            try:
                with open(self.history_path, "a") as f:
                    f.write(json.dumps({"asset": asset, "venue": venue,
                                          "regime": regime,
                                          **buf[-1].to_dict()}) + "\n")
            except Exception:
                pass

    # ----- query path -----

    def cell_tags(self, asset: str, venue: str, regime: str,
                    now_ts: float | None = None) -> CellTags:
        if now_ts is None:
            now_ts = time.time()
        key = (asset, venue, regime)
        buf = self._buffers.get(key, deque())
        # Bin samples by recency
        cutoff_d = now_ts - DAILY_WINDOW_S
        cutoff_w = now_ts - WEEKLY_WINDOW_S
        cutoff_l = now_ts - LONGTERM_WINDOW_S
        d_x: list[float] = []
        d_y: list[float] = []
        w_x: list[float] = []
        w_y: list[float] = []
        l_x: list[float] = []
        l_y: list[float] = []
        for s in buf:
            if s.ts >= cutoff_l:
                l_x.append(s.mean_dipole)
                l_y.append(s.forward_return)
                if s.ts >= cutoff_w:
                    w_x.append(s.mean_dipole)
                    w_y.append(s.forward_return)
                    if s.ts >= cutoff_d:
                        d_x.append(s.mean_dipole)
                        d_y.append(s.forward_return)

        # Also collect per-window sample lists for self_trend computation
        # (we need ts to split into quarters; the unzipped lists above lost
        # ordering structure).
        d_samples: list[_Sample] = []
        w_samples: list[_Sample] = []
        l_samples: list[_Sample] = []
        for s in buf:
            if s.ts >= cutoff_l:
                l_samples.append(s)
                if s.ts >= cutoff_w:
                    w_samples.append(s)
                    if s.ts >= cutoff_d:
                        d_samples.append(s)

        def _stat(xs: list[float], ys: list[float], min_n: int,
                    samples: list[_Sample]) -> HorizonStat:
            if not xs:
                return HorizonStat(n=0)
            xa = np.asarray(xs, dtype=float)
            ya = np.asarray(ys, dtype=float)
            r, p = _pearson_with_p(xa, ya)
            strength, direction = _classify_strength(len(xs), r, p, min_n)
            self_trend, n_flips = _classify_self_trend(samples)
            return HorizonStat(
                n=len(xs),
                r=round(r, 4) if r is not None else None,
                p=round(p, 4) if p is not None else None,
                strength=strength, direction=direction,
                self_trend=self_trend, n_sign_flips=n_flips)

        daily = _stat(d_x, d_y, MIN_N_DAILY, d_samples)
        weekly = _stat(w_x, w_y, MIN_N_WEEKLY, w_samples)
        longterm = _stat(l_x, l_y, MIN_N_LONGTERM, l_samples)
        tags = CellTags(asset=asset, venue=venue, regime=regime,
                          daily=daily, weekly=weekly, longterm=longterm)
        # Trends compare each horizon to the next-broader. UNKNOWN if the
        # broader window has no signal yet.
        tags.weekly_trend = _classify_trend(weekly, longterm)
        tags.daily_trend = _classify_trend(daily, weekly)
        tags.summary = _summary_for(tags)
        return tags

    def all_cell_tags(self, now_ts: float | None = None) -> list[CellTags]:
        return [self.cell_tags(a, v, r, now_ts) for (a, v, r) in self._buffers]

    def n_total_samples(self) -> int:
        return sum(len(b) for b in self._buffers.values())

    # ----- persistence -----

    def _restore_from_disk(self) -> None:
        if not self.history_path or not os.path.exists(self.history_path):
            return
        loaded = 0
        try:
            with open(self.history_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    asset = d.get("asset"); venue = d.get("venue"); regime = d.get("regime")
                    ts = d.get("ts"); md = d.get("mean_dipole"); fr = d.get("forward_return")
                    if not all(isinstance(v, str) for v in (asset, venue, regime)):
                        continue
                    if not all(isinstance(v, (int, float)) for v in (ts, md, fr)):
                        continue
                    key = (asset, venue, regime)
                    buf = self._buffers.setdefault(key,
                        deque(maxlen=MAX_HISTORY_PER_CELL))
                    buf.append(_Sample(ts=float(ts), mean_dipole=float(md),
                                          forward_return=float(fr)))
                    loaded += 1
        except Exception:
            return
        # Drop entries outside the longterm window — they can't influence any
        # current report, just waste memory.
        cutoff = time.time() - LONGTERM_WINDOW_S
        for key, buf in list(self._buffers.items()):
            self._buffers[key] = deque(
                (s for s in buf if s.ts >= cutoff),
                maxlen=MAX_HISTORY_PER_CELL)
        print(f"[edge_tracker] restored {loaded} samples across "
              f"{len(self._buffers)} cells from {self.history_path}",
              flush=True)
