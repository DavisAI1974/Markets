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


# Window durations (seconds). Four canonical trader horizons —
# intraday / daily / weekly / monthly.
INTRADAY_WINDOW_S = 4 * 60 * 60          # last 4 hours — "tradeable right now"
DAILY_WINDOW_S = 24 * 60 * 60
WEEKLY_WINDOW_S = 7 * 24 * 60 * 60
LONGTERM_WINDOW_S = 30 * 24 * 60 * 60

# Min n per window to report a strength tag. Below this we report "NEW".
# Intraday is intentionally low because at 30min stride a 4h window can
# only hold 8 samples — even 4 is enough to flag a STRONG fresh signal
# to the user.
MIN_N_INTRADAY = 4
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
    rho: float | None = None
    p_rho: float | None = None
    dcor: float | None = None
    p_dcor: float | None = None
    primary_metric: str = ""   # "r" | "rho" | ""
    non_linear: bool = False   # dCor sees structure the directional stack misses
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
    intraday: HorizonStat = field(default_factory=HorizonStat)
    daily: HorizonStat = field(default_factory=HorizonStat)
    weekly: HorizonStat = field(default_factory=HorizonStat)
    longterm: HorizonStat = field(default_factory=HorizonStat)
    # Trends compare a window to the next-broader one.
    intraday_trend: str = "STABLE"  # STRENGTHENING | WEAKENING | STABLE | UNKNOWN
    daily_trend: str = "STABLE"
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


def _spearman_with_p(xs: np.ndarray, ys: np.ndarray) -> tuple[float | None, float | None]:
    """Mirror phase1_5_evaluator's Spearman stack for live edge tracking."""
    n = len(xs)
    if n < 3:
        return None, None
    if np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
        return 0.0, 1.0
    rx = np.argsort(np.argsort(xs)).astype(np.float64)
    ry = np.argsort(np.argsort(ys)).astype(np.float64)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    if not np.isfinite(rho) or abs(rho) >= 1.0:
        return rho, None
    t = rho * math.sqrt(n - 2) / math.sqrt(max(1.0 - rho * rho, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return rho, float(p)


def _dcor(xs: np.ndarray, ys: np.ndarray) -> float | None:
    n = len(xs)
    if n < 4:
        return None
    if np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
        return 0.0
    a = np.abs(xs[:, None] - xs[None, :])
    b = np.abs(ys[:, None] - ys[None, :])
    a_dc = a - a.mean(axis=0, keepdims=True) - a.mean(axis=1, keepdims=True) + a.mean()
    b_dc = b - b.mean(axis=0, keepdims=True) - b.mean(axis=1, keepdims=True) + b.mean()
    dcov2 = float((a_dc * b_dc).mean())
    dvarx2 = float((a_dc * a_dc).mean())
    dvary2 = float((b_dc * b_dc).mean())
    denom = math.sqrt(max(dvarx2 * dvary2, 1e-24))
    if denom < 1e-12:
        return 0.0
    val = math.sqrt(max(dcov2, 0.0)) / math.sqrt(denom)
    return min(1.0, max(0.0, val))


def _dcor_with_p(xs: np.ndarray, ys: np.ndarray,
                 n_perm: int = 200,
                 seed: int = 0) -> tuple[float | None, float | None]:
    observed = _dcor(xs, ys)
    if observed is None:
        return None, None
    if len(xs) < 8:
        return observed, None
    rng = np.random.default_rng(seed=seed)
    ge = 0
    for _ in range(n_perm):
        yp = ys[rng.permutation(len(ys))]
        d = _dcor(xs, yp)
        if d is not None and d >= observed:
            ge += 1
    return observed, float((ge + 1) / (n_perm + 1))


def _best_directional_metric(r: float | None, p: float | None,
                             rho: float | None, p_rho: float | None
                             ) -> tuple[str, float | None, float | None, str]:
    candidates: list[tuple[str, float, float | None]] = []
    if r is not None and np.isfinite(r):
        candidates.append(("r", float(r), p))
    if rho is not None and np.isfinite(rho):
        candidates.append(("rho", float(rho), p_rho))
    if not candidates:
        return "", None, None, ""
    metric, value, pval = max(candidates, key=lambda item: abs(item[1]))
    direction = "fade" if value < 0 else ("momentum" if value > 0 else "")
    return metric, value, pval, direction


def _classify_strength(n: int, directional_value: float | None,
                       directional_p: float | None, min_n: int,
                       direction: str) -> tuple[str, str]:
    """Return (strength, direction) using the strongest directional metric."""
    if n < min_n or directional_value is None:
        return "NEW", ""
    if abs(directional_value) >= STRONG_R_MIN and directional_p is not None and directional_p < STRONG_P_MAX:
        return "STRONG", direction
    if abs(directional_value) >= MODERATE_R_MIN:
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

    Surfaces strength + direction + self_trend per horizon, in
    long-term → weekly → daily → intraday order so the reader sees the
    broad-context first then drills down to "tradeable right now."
    Cross-horizon trends are appended only when they fire actionably.
    """
    def _phrase(window: str, st: HorizonStat) -> str:
        if st.strength == "NEW":
            return f"{window} tracking (n={st.n})"
        dir_word = "" if not st.direction else (" " + st.direction)
        trend_word = ""
        if st.self_trend in ("STRENGTHENING", "DECAYING", "FLIPPING"):
            trend_word = f" {st.self_trend.lower()}"
        metric_note = ""
        metric_val = st.r if st.primary_metric == "r" else st.rho
        if st.primary_metric == "rho" and metric_val is not None:
            metric_note = f" via rho={metric_val:+.2f}"
        elif st.non_linear and st.dcor is not None:
            metric_note = f" nonlinear dCor={st.dcor:.2f}"
        base_r = f"{st.r:+.2f}" if st.r is not None else "n/a"
        return f"{window} {st.strength.lower()}{dir_word}{trend_word} (r={base_r}, n={st.n}{metric_note})"

    parts = [
        _phrase("Long-term", tags.longterm),
        _phrase("Weekly",    tags.weekly),
        _phrase("Daily",     tags.daily),
        _phrase("Intraday",  tags.intraday),
    ]
    extras = []
    if tags.weekly_trend in ("STRENGTHENING", "WEAKENING"):
        extras.append(f"weekly {tags.weekly_trend.lower()} vs long-term")
    if tags.daily_trend in ("STRENGTHENING", "WEAKENING"):
        extras.append(f"daily {tags.daily_trend.lower()} vs weekly")
    if tags.intraday_trend in ("STRENGTHENING", "WEAKENING"):
        extras.append(f"intraday {tags.intraday_trend.lower()} vs daily")
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
        cutoff_i = now_ts - INTRADAY_WINDOW_S
        cutoff_d = now_ts - DAILY_WINDOW_S
        cutoff_w = now_ts - WEEKLY_WINDOW_S
        cutoff_l = now_ts - LONGTERM_WINDOW_S
        i_samples: list[_Sample] = []
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
                        if s.ts >= cutoff_i:
                            i_samples.append(s)

        def _stat(samples: list[_Sample], min_n: int) -> HorizonStat:
            if not samples:
                return HorizonStat(n=0)
            xa = np.asarray([s.mean_dipole for s in samples], dtype=float)
            ya = np.asarray([s.forward_return for s in samples], dtype=float)
            r, p = _pearson_with_p(xa, ya)
            rho, p_rho = _spearman_with_p(xa, ya)
            # dCor permutation is the expensive leg; cap it to windows
            # where the sample size is still modest enough for live use.
            if len(samples) <= 200:
                dc, p_dc = _dcor_with_p(xa, ya, n_perm=200, seed=int(len(samples)))
            else:
                dc = _dcor(xa, ya)
                p_dc = None
            primary_metric, primary_value, primary_p, direction = _best_directional_metric(
                r, p, rho, p_rho)
            strength, direction = _classify_strength(
                len(samples), primary_value, primary_p, min_n, direction)
            self_trend, n_flips = _classify_self_trend(samples)
            non_linear = bool(
                dc is not None
                and p_dc is not None
                and p_dc < STRONG_P_MAX
                and (primary_value is None or abs(primary_value) < MODERATE_R_MIN)
                and dc >= MODERATE_R_MIN
            )
            return HorizonStat(
                n=len(samples),
                r=round(r, 4) if r is not None else None,
                p=round(p, 4) if p is not None else None,
                rho=round(rho, 4) if rho is not None else None,
                p_rho=round(p_rho, 4) if p_rho is not None else None,
                dcor=round(dc, 4) if dc is not None else None,
                p_dcor=round(p_dc, 4) if p_dc is not None else None,
                primary_metric=primary_metric,
                non_linear=non_linear,
                strength=strength, direction=direction,
                self_trend=self_trend, n_sign_flips=n_flips)

        intraday = _stat(i_samples, MIN_N_INTRADAY)
        daily = _stat(d_samples, MIN_N_DAILY)
        weekly = _stat(w_samples, MIN_N_WEEKLY)
        longterm = _stat(l_samples, MIN_N_LONGTERM)
        tags = CellTags(asset=asset, venue=venue, regime=regime,
                          intraday=intraday, daily=daily,
                          weekly=weekly, longterm=longterm)
        tags.weekly_trend = _classify_trend(weekly, longterm)
        tags.daily_trend = _classify_trend(daily, weekly)
        tags.intraday_trend = _classify_trend(intraday, daily)
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
