"""
phase1_5_evaluator.py — runs all three Phase 1.5 stop gates (G, H, I).

Inputs: paired bins files for the same asset on two venues.
Outputs: per-venue regime trajectories, cross-venue agreement rate,
         per-regime forward predictive R^2, gate verdicts.

Gate G: classifier produces >=4 distinct regime classes (modal <70%) on each venue
Gate H: cross-venue regime agreement >=60% on overlapping wall-clock minutes
Gate I: per-regime forward predictive R^2 differs across regime classes

Run: python phase1_5_evaluator.py --asset BTC \\
        --cb-bins phase1_bins.json --kr-bins kraken_bins.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from markets_adapter import (
    MarketBar, MarketChunk, MarketChunker, MarketChunkEncoder, MarketFeatures,
)
from regime_classifier import (
    Regime, Baselines, ClassificationResult,
    classify_regime, baselines_from_corpus,
    baselines_per_session, classify_with_session_baselines,
    apply_cross_venue_multiplier, _session_phase_of,
    apply_herd_persistence, apply_herd_borderline_rescue,
    detect_whale_to_herd_cascades,
    detect_cross_venue_whale_herd_simultaneity,
    apply_cross_asset_multiplier,
    apply_event_multiplier,
)
from event_calendar import EventCalendar


def load_bars(bins_path: str) -> list[MarketBar]:
    with open(bins_path) as f:
        sec_bins = {float(k): v for k, v in json.load(f).items()}
    minute_groups: dict[float, list[tuple[float, dict]]] = defaultdict(list)
    for ts, b in sec_bins.items():
        if b.get("mid") is None:
            continue
        m_ts = int(ts / 60.0) * 60.0
        minute_groups[m_ts].append((ts, b))
    bars: list[MarketBar] = []
    for m_ts in sorted(minute_groups):
        members = sorted(minute_groups[m_ts], key=lambda x: x[0])
        mids = [b["mid"] for _, b in members if b["mid"] is not None]
        if not mids:
            continue
        last_bid = 0.0
        last_ask = 0.0
        last_bid_qty = 0.0
        last_ask_qty = 0.0
        last_aggressor = ""
        for _, bb in members:
            if bb.get("bid"):
                last_bid = float(bb["bid"])
            if bb.get("ask"):
                last_ask = float(bb["ask"])
            if bb.get("bid_qty"):
                last_bid_qty = float(bb["bid_qty"])
            if bb.get("ask_qty"):
                last_ask_qty = float(bb["ask_qty"])
            if bb.get("last_aggressor"):
                last_aggressor = str(bb["last_aggressor"])
        bars.append(MarketBar(
            ts=float(m_ts),
            close=float(mids[-1]), open_=float(mids[0]),
            high=float(max(mids)), low=float(min(mids)),
            volume=float(sum(b["buy"] + b["sell"] for _, b in members)),
            buy_vol=float(sum(b["buy"] for _, b in members)),
            sell_vol=float(sum(b["sell"] for _, b in members)),
            n_trades=int(sum(b.get("n_trades", 0) for _, b in members)),
            bid=last_bid, ask=last_ask,
            bid_qty=last_bid_qty, ask_qty=last_ask_qty,
            last_aggressor=last_aggressor,
        ))
    return bars


def classify_venue(bars: list[MarketBar], label: str,
                    chunk_max: int = 30, chunk_min: int = 10,
                    multi_signal_pelt: bool = False,
                    use_session_baselines: bool = False,
                    herd_rescue: bool = False,
                    hawkes_elevated: float | None = None,
                    hawkes_diffuse: float | None = None,
                    ) -> tuple[list[MarketChunk], list[ClassificationResult], Baselines, dict, list[MarketFeatures]]:
    chunker = MarketChunker(max_window_size=chunk_max, stride=chunk_max // 2,
                             min_segment=chunk_min, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(label, bars, multi_signal=multi_signal_pelt)
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    # Hawkes thresholds: pass through to classify_regime, fall back to
    # the function's own literature defaults if caller didn't supply.
    haw_kwargs: dict = {}
    if hawkes_elevated is not None:
        haw_kwargs["hawkes_elevated"] = float(hawkes_elevated)
    if hawkes_diffuse is not None:
        haw_kwargs["hawkes_diffuse"] = float(hawkes_diffuse)
    if use_session_baselines:
        session_base = baselines_per_session(feats)
        results = [classify_with_session_baselines(f, session_base) for f in feats]
    else:
        session_base = {"_global": base}
        results = [classify_regime(f, base, **haw_kwargs) for f in feats]
    apply_herd_persistence(results)
    if herd_rescue:
        apply_herd_borderline_rescue(results, feats, base)
        apply_herd_persistence(results)  # recompute including rescued chunks
    return chunks, results, base, session_base, feats


def _herd_runs(results: list[ClassificationResult]
                ) -> list[tuple[int, int, str, int]]:
    """Group consecutive same-regime HERD chunks (persistence>=2) into runs.

    Returns list of (start_idx, length, regime_value, n_rescued).
    """
    out: list[tuple[int, int, str, int]] = []
    i = 0
    while i < len(results):
        if results[i].herd_persistence < 2:
            i += 1
            continue
        regime = results[i].regime.value
        j = i
        while (j < len(results)
                and results[j].regime.value == regime
                and results[j].herd_persistence >= 2):
            j += 1
        rescued = sum(1 for k in range(i, j) if results[k].herd_rescued)
        out.append((i, j - i, regime, rescued))
        i = j
    return out


# ---------------------------------------------------------------------------
# GATE G: classifier diversity per venue
# ---------------------------------------------------------------------------

def evaluate_gate_G(label: str, results: list[ClassificationResult]) -> dict:
    counts = Counter(r.regime.value for r in results)
    n = sum(counts.values())
    if n == 0:
        return {"label": label, "gate_G": False, "reason": "no chunks"}
    n_classes = len(counts)
    modal = max(counts.values())
    modal_pct = modal / n
    passing = n_classes >= 4 and modal_pct < 0.70
    return {
        "label": label,
        "n_chunks": n,
        "n_classes": n_classes,
        "modal_class": counts.most_common(1)[0][0],
        "modal_pct": modal_pct,
        "distribution": dict(counts),
        "gate_G": passing,
    }


# ---------------------------------------------------------------------------
# GATE H: cross-venue regime agreement on wall-clock-aligned minutes
# ---------------------------------------------------------------------------

def chunk_to_minute_regime(chunks: list[MarketChunk], results: list[ClassificationResult],
                            bars: list[MarketBar]) -> dict[float, str]:
    """Map each wall-clock minute (ts) to its regime label.

    A minute belongs to whichever chunk's [window_start, window_end) contains it.
    For overlapping chunks (hybrid mode subdivision), the LAST chunk wins
    (approximates the "most recent regime read" at that minute).
    """
    minute_label: dict[float, str] = {}
    for c, r in zip(chunks, results):
        for bar_idx in range(c.window_start, c.window_end):
            if 0 <= bar_idx < len(bars):
                ts = bars[bar_idx].ts
                minute_label[ts] = r.regime.value
    return minute_label


# Regimes that all encode "no directional edge" — collapsed to a single
# bucket for the relaxed Gate H scoring. Pass-8 introduced WASH_HAWKES
# which fires on one venue without firing on the other (different MM
# ecosystems); penalizing that asymmetry as "disagreement" understates
# real cross-venue alignment. EQ_TWO_SIDED, WASH_HAWKES, and DEPLETED
# all signal "don't trade" — disagreement among them is uninformative.
_NO_EDGE_BUCKET = frozenset({"EQUILIBRIUM_TWO_SIDED", "WASH_HAWKES",
                              "WASH_PAIRED", "DEPLETED"})


def _bucketed_label(label: str) -> str:
    """Collapse the no-edge cluster to a single 'NO_EDGE' bucket; pass other
    labels through unchanged."""
    return "NO_EDGE" if label in _NO_EDGE_BUCKET else label


def load_lag_calibration(path: str) -> dict:
    """Load cross_venue_lag_calibration.json. Returns {} on any failure
    so the calibrated-gate path silently degrades to the base Gate H."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def evaluate_gate_H_calibrated(asset: str,
                                  cb_minute: dict[float, str],
                                  kr_minute: dict[float, str],
                                  calibration: dict) -> dict:
    """Asset-specific Gate H using a persisted lag calibration entry.

    Pass-12 found CB-BTC leads KR-BTC by 15 min while ETH cross-venue
    divergence is structural at any lag. The base Gate H scores both
    assets at lag=0 which understates BTC alignment and miscategorizes
    ETH as fixable. This function applies the per-asset calibration:

      - structural_divergence=True : verdict='STRUCTURAL_DIVERGENCE'
        (informational; not a hard pass/fail — per-venue Gate I findings
        stand on their own).
      - lag_min=K : compare cb_minute[t] to kr_minute[t-K*60], strict
        and relaxed scored normally; PASS if either ≥ 60%.
      - no entry : verdict='NO_CALIBRATION' (caller falls back to base).
    """
    entry = (calibration or {}).get(asset)
    if entry is None:
        return {"verdict": "NO_CALIBRATION",
                  "reason": f"no calibration entry for asset={asset}"}
    if entry.get("structural_divergence"):
        # Empirical: prior lag scan found no offset clears 60% strict.
        # Verdict driven by max_strict_at_any_lag — the structural-
        # divergence flag is INFORMATIONAL metadata only, NOT a pass
        # override. Relaxed metric is reported alongside but does not
        # drive the verdict (see evaluate_gate_H docstring).
        max_strict = float(entry.get("max_strict_at_any_lag") or 0.0)
        max_relaxed = float(entry.get("max_relaxed_at_any_lag") or 0.0)
        return {
            "verdict": "PASS" if max_strict >= 0.60 else "FAIL",
            "interpretation_note": entry.get("interpretation", ""),
            "max_strict_at_any_lag": max_strict,
            "max_relaxed_at_any_lag": max_relaxed,
            "structural_divergence_flag": True,
            "calibration_pass": entry.get("calibration_pass"),
        }
    lag_min = int(entry.get("lag_min", 0))
    if lag_min == 0:
        h = evaluate_gate_H(cb_minute, kr_minute)
    else:
        kr_shifted = {ts + lag_min * 60.0: r for ts, r in kr_minute.items()}
        h = evaluate_gate_H(cb_minute, kr_shifted)
    if "reason" in h:
        return {"verdict": "INSUFFICIENT_OVERLAP", "lag_min": lag_min, **h}
    strict_pass = h["agreement_rate"] >= 0.60
    relaxed_pass = h["agreement_rate_relaxed"] >= 0.60
    return {
        # Verdict driven by STRICT agreement at the calibrated lag.
        # Relaxed reported alongside as informational only.
        "verdict": "PASS" if strict_pass else "FAIL",
        "lag_min": lag_min,
        "primary_venue": entry.get("primary_venue"),
        "secondary_venue": entry.get("secondary_venue"),
        "strict_at_lag": h["agreement_rate"],
        "relaxed_at_lag": h["agreement_rate_relaxed"],
        "n_overlap": h["n_overlap_minutes"],
        "strict_pass": strict_pass,
        "relaxed_pass": relaxed_pass,
        "calibration_pass": entry.get("calibration_pass"),
    }


def evaluate_gate_H_lag_scan(cb_minute: dict[float, str],
                                kr_minute: dict[float, str],
                                lag_range_min: range = range(-10, 11)) -> dict:
    """Scan lag offsets in 1-minute steps; return the lag that maximizes
    strict agreement plus the per-lag agreement curve.

    Pass-10 found ETH Gate H still failing (strict 35.2% / relaxed 57.7%)
    after the WASH_HAWKES ceiling change, dominated by `EQ | WHALE_UP`
    disagreement pairs (640). Two interpretations:
      - TIMING: CB sees the EQ tail at minute t, KR sees the same flow
        as WHALE_UP at minute t±Δ (where Δ is propagation latency
        between venues). If true, scoring at the right lag should clear
        the gate.
      - STRUCTURAL: CB and KR genuinely classify the same flow
        differently (different MM ecosystems, different fill patterns).
        No lag should help.

    Comparison: cb_minute[t] vs kr_minute[t - lag*60]. Positive lag means
    KR's classification at minute (t - lag) is compared to CB at t —
    i.e. positive lag indicates CB LEADS KR by `lag` minutes. Negative
    lag indicates KR leads CB.

    Returns the full per-lag table so the writeup can show the curve,
    plus the argmax and a binary "is timing-driven" flag (true if the
    best lag's strict agreement clears 60% AND lag != 0).
    """
    base = evaluate_gate_H(cb_minute, kr_minute)
    if "reason" in base:
        return {"reason": base["reason"], "lag_scan": None}
    per_lag: list[dict] = []
    best_lag = 0
    best_strict = base["agreement_rate"]
    best_relaxed = base["agreement_rate_relaxed"]
    for lag in lag_range_min:
        if lag == 0:
            kr_shifted = kr_minute
        else:
            # Shift KR by `lag` minutes: ts in kr_minute moves to ts + lag*60.
            # Then compare cb_minute[t] vs kr_shifted[t] which equals
            # kr_minute[t - lag*60].
            kr_shifted = {ts + lag * 60.0: r for ts, r in kr_minute.items()}
        h = evaluate_gate_H(cb_minute, kr_shifted)
        if "reason" in h:
            per_lag.append({
                "lag_min": lag, "n_overlap": h.get("n_overlap", 0),
                "strict": None, "relaxed": None,
            })
            continue
        per_lag.append({
            "lag_min": lag,
            "n_overlap": h["n_overlap_minutes"],
            "strict": h["agreement_rate"],
            "relaxed": h["agreement_rate_relaxed"],
            "strict_n": h["n_agreements"],
            "relaxed_n": h["n_agreements_relaxed"],
        })
        if h["agreement_rate"] > best_strict:
            best_strict = h["agreement_rate"]
            best_lag = lag
            best_relaxed = h["agreement_rate_relaxed"]
    return {
        "lag_scan": per_lag,
        "best_lag_min": best_lag,
        "best_strict": best_strict,
        "best_relaxed_at_best_lag": best_relaxed,
        "base_strict": base["agreement_rate"],
        "base_relaxed": base["agreement_rate_relaxed"],
        "is_timing_driven": (best_lag != 0
                                and best_strict >= 0.60
                                and base["agreement_rate"] < 0.60),
    }


def evaluate_gate_H(cb_minute: dict[float, str], kr_minute: dict[float, str]) -> dict:
    common = sorted(set(cb_minute) & set(kr_minute))
    if len(common) < 30:
        return {"gate_H": False, "n_overlap": len(common), "reason": "too few overlapping minutes"}
    # Strict (raw label match) — historical metric for Pass-comparison continuity
    strict_agreements = sum(1 for m in common if cb_minute[m] == kr_minute[m])
    strict_rate = strict_agreements / len(common)
    # Relaxed (post-Pass-8) — collapse no-edge labels to one bucket so
    # EQ↔WASH_HAWKES and similar count as agreement.
    relaxed_agreements = sum(
        1 for m in common
        if _bucketed_label(cb_minute[m]) == _bucketed_label(kr_minute[m]))
    relaxed_rate = relaxed_agreements / len(common)
    # Confusion matrix on raw labels (most informative for debugging).
    confusion: Counter[tuple[str, str]] = Counter()
    for m in common:
        confusion[(cb_minute[m], kr_minute[m])] += 1
    return {
        "n_overlap_minutes": len(common),
        "n_agreements": strict_agreements,           # back-compat
        "agreement_rate": strict_rate,
        "n_agreements_relaxed": relaxed_agreements,
        "agreement_rate_relaxed": relaxed_rate,
        "confusion_top_5": confusion.most_common(5),
        # Gate verdict is STRICT only. The relaxed metric (NO_EDGE
        # bucket collapsing EQ/WASH/DEPLETED) is reported alongside as
        # informational context, but does not drive the pass/fail
        # verdict — that lets the gate be softened by routing
        # disagreements through a definitional bucket I created. The
        # measurement we report is the direct one: "do CB and KR emit
        # the same regime label?" The 60% threshold applies to that.
        "gate_H_strict": strict_rate >= 0.60,
        "gate_H_relaxed": relaxed_rate >= 0.60,
        "gate_H": strict_rate >= 0.60,
    }


# ---------------------------------------------------------------------------
# GATE I: per-regime forward predictive R^2
# ---------------------------------------------------------------------------

def _pearsonr_with_p(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    n = len(x)
    if n < 3:
        return float("nan"), float("nan"), int(n)
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0, 1.0, int(n)
    r = float(np.corrcoef(x, y)[0, 1])
    if not np.isfinite(r) or abs(r) >= 1.0:
        return r, float("nan"), int(n)
    t = r * np.sqrt(n - 2) / np.sqrt(max(1.0 - r * r, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return r, p, int(n)


def _spearmanr_with_p(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """Spearman rank correlation. Captures monotonic non-linear dependence
    that Pearson r misses (saturation curves, threshold effects, ranks).
    Returns (rho, p_value, n). Same NaN-safe contract as _pearsonr_with_p.

    p-value uses the same t-approximation as Pearson on the ranked series;
    valid for n>=10. For smaller n, treat p as advisory."""
    n = len(x)
    if n < 3:
        return float("nan"), float("nan"), int(n)
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0, 1.0, int(n)
    # argsort.argsort gives ranks (with ties averaged-ish — good enough here).
    rx = np.argsort(np.argsort(x)).astype(np.float64)
    ry = np.argsort(np.argsort(y)).astype(np.float64)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    if not np.isfinite(rho) or abs(rho) >= 1.0:
        return rho, float("nan"), int(n)
    t = rho * np.sqrt(n - 2) / np.sqrt(max(1.0 - rho * rho, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return rho, p, int(n)


def _dcor(x: np.ndarray, y: np.ndarray) -> float:
    """Distance correlation (Székely-Rizzo, 2007). Zero iff x and y are
    independent. Captures any dependence — linear, monotonic non-linear,
    OR non-monotonic (U-shapes, threshold reversals). Range [0, 1].

    Sign-less by construction — useful as a detector but not as a
    direction indicator. For tradeability, pair dCor with sign from
    Pearson/Spearman."""
    n = len(x)
    if n < 4:
        return float("nan")
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0
    a = np.abs(x[:, None] - x[None, :])
    b = np.abs(y[:, None] - y[None, :])
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


def _dcor_with_p(x: np.ndarray, y: np.ndarray,
                   n_perm: int = 500,
                   seed: int = 0) -> tuple[float, float, int]:
    """Distance correlation + permutation p-value. p = fraction of
    permutations whose dCor >= observed dCor. n_perm=500 → p resolution
    of 0.002, adequate for the BH-FDR pipeline at q=0.10.

    Returns (dcor, p, n). For n<8 returns (dcor, nan, n) — permutation
    on tiny samples isn't meaningful."""
    n = len(x)
    if n < 4:
        return float("nan"), float("nan"), int(n)
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0, 1.0, int(n)
    observed = _dcor(x, y)
    if not np.isfinite(observed):
        return observed, float("nan"), int(n)
    if n < 8:
        return observed, float("nan"), int(n)
    rng = np.random.default_rng(seed)
    ge = 0
    y_arr = np.asarray(y)
    for _ in range(n_perm):
        y_perm = rng.permutation(y_arr)
        d = _dcor(x, y_perm)
        if np.isfinite(d) and d >= observed:
            ge += 1
    p = (ge + 1) / (n_perm + 1)  # +1 smoothing to avoid p=0
    return observed, p, int(n)


def _bh_fdr(pvalues: list[float], q: float = 0.10) -> tuple[list[float], list[bool]]:
    """Benjamini-Hochberg FDR. Returns (q_values, reject_at_q). q_value is the
    smallest q at which the test is rejected; reject is True iff q_value <= q.
    Empty input returns ([], [])."""
    m = len(pvalues)
    if m == 0:
        return [], []
    order = sorted(range(m), key=lambda i: pvalues[i])
    qvals = [1.0] * m
    running_min = 1.0
    # Walk from largest p to smallest, applying step-up enforcement.
    for rank_from_top, idx in enumerate(reversed(order)):
        rank = m - rank_from_top  # 1-based rank from smallest
        adj = pvalues[idx] * m / rank
        if adj < running_min:
            running_min = adj
        qvals[idx] = min(running_min, 1.0)
    reject = [qv <= q for qv in qvals]
    return qvals, reject


def classify_cell_tradability(label: str,
                                  chunks: list[MarketChunk],
                                  results: list[ClassificationResult],
                                  k: int = 1,
                                  strong_r: float = 0.15,
                                  moderate_r: float = 0.10,
                                  min_n_intraday: int = 4,
                                  min_n_daily: int = 6,
                                  min_n_weekly: int = 20,
                                  min_n_longterm: int = 30,
                                  feature_values: np.ndarray | None = None,
                                  feature_name: str = "mean_dipole") -> dict:
    """Per-cell horizon-based tradability classifier (Pass-15 — three-
    statistic stack: Pearson r, Spearman ρ, distance correlation).

    Mirrors edge_tracker.MultiHorizonEdgeTracker for offline data.
    Uses the same horizon definitions and thresholds so the offline
    and live views report the same way.

      Intraday  = last 4 hours of the corpus
      Daily     = last 24 hours
      Weekly    = last 7 days
      Long-term = last 30 days (or all)

    Per horizon compute three statistics on
    (chunk_t.mean_dipole, chunk_{t+k}.log_return) for chunks whose
    predictor timestamp falls inside the horizon:

      r    Pearson         linear dependence
      ρ    Spearman        monotonic non-linear dependence
      dC   distance corr   any dependence (incl. non-monotonic)

    Strength tier uses the larger of |r| and |ρ| (monotonic
    confidence) so a direction can be assigned:

      confidence = max(|r|, |ρ|)
      direction  = sign of whichever monotonic statistic has the larger
                   magnitude
      STRONG     confidence >= strong_r AND n >= min_n_horizon
      MODERATE   confidence >= moderate_r AND n >= min_n_horizon
      WEAK       confidence <  moderate_r AND n >= min_n_horizon
      NEW        n  <  min_n_horizon

    Diagnostic flags:
      non_linear     |ρ| − |r| >= 0.10 AND confidence >= moderate_r
                     (rank correlation differs from level correlation)
      non_monotonic  dC >= moderate_r AND confidence < moderate_r
                     (distance correlation detects dependence both
                     monotonic statistics missed; direction is undefined,
                     so the cell stays WEAK in the strength tier but
                     gets flagged for manual inspection)

    Tradability category derived from horizon strengths:

      ALWAYS_TRADEABLE              long-term STRONG AND weekly STRONG
                                     AND (daily STRONG OR daily MODERATE)
                                     AND signs match across those horizons
      CURRENTLY_TRADEABLE            intraday STRONG, OR daily STRONG,
                                     and not ALWAYS_TRADEABLE
      HISTORICALLY_TRADEABLE_NOT_NOW long-term STRONG (or weekly STRONG)
                                     but both daily AND intraday are
                                     WEAK or NEW
      NEVER_TRADEABLE                no horizon ever reached STRONG
                                     (all WEAK or NEW)
      AMBIGUOUS                      partial signal that doesn't fit
                                     a clear category (e.g. only
                                     weekly MODERATE, mixed signs)
      INSUFFICIENT_DATA              long-term horizon has n<min_n_longterm
    """
    if len(chunks) < k + 2:
        return {"label": label, "verdict": "INSUFFICIENT_DATA",
                  "reason": "too few chunks"}

    # Per-chunk feature value (defaults to chunk-mean dipole — same as
    # the Pass-14 baseline) + forward log return + predictor timestamp.
    chunk_returns: list[float] = []
    chunk_ts: list[float] = []
    if feature_values is None:
        feature_values = np.array([
            float(np.mean([b.dipole for b in c.bars])) if c.bars else 0.0
            for c in chunks
        ])
    for c in chunks:
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12)
                              / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
        chunk_ts.append(float(c.bars[0].ts) if c.bars else 0.0)
    md = np.asarray(feature_values, dtype=float)
    cr = np.array(chunk_returns)
    labels = [r.regime.value for r in results]

    # Anchor "now" to the end of the corpus (the latest predictor ts that
    # has a forward chunk).
    if len(chunk_ts) <= k or not any(chunk_ts):
        return {"label": label, "verdict": "INSUFFICIENT_DATA",
                  "reason": "no usable timestamps"}
    now_ts = max(chunk_ts[:len(chunks) - k])
    HOUR = 3600.0
    DAY = 24 * HOUR
    horizons = (
        ("intraday", 4 * HOUR, min_n_intraday),
        ("daily",    24 * HOUR, min_n_daily),
        ("weekly",   7 * DAY,   min_n_weekly),
        ("longterm", 30 * DAY,  min_n_longterm),
    )

    def _strength(n: int,
                  r: float | None,
                  rho: float | None,
                  min_n: int) -> tuple[str, str, float | None]:
        """Return (strength_tag, direction, confidence). Confidence is
        max(|r|, |rho|); direction follows the sign of whichever
        statistic has the larger magnitude (or matches both if signs
        agree). When the two disagree in sign at moderate-or-stronger
        strength, the direction is taken from the stronger statistic
        but the divergence is logged downstream."""
        if (r is None and rho is None) or n < min_n:
            return "NEW", "", None
        r_mag = abs(r) if r is not None else 0.0
        rho_mag = abs(rho) if rho is not None else 0.0
        conf = max(r_mag, rho_mag)
        if r_mag >= rho_mag:
            sign = (1 if (r or 0) > 0 else (-1 if (r or 0) < 0 else 0))
        else:
            sign = (1 if (rho or 0) > 0 else (-1 if (rho or 0) < 0 else 0))
        direction = "fade" if sign < 0 else ("momentum" if sign > 0 else "")
        if conf >= strong_r:
            return "STRONG", direction, conf
        if conf >= moderate_r:
            return "MODERATE", direction, conf
        return "WEAK", direction, conf

    per_regime: dict[str, dict] = {}
    for regime in sorted(set(labels)):
        all_idx = [i for i in range(len(chunks) - k) if labels[i] == regime]
        n_total = len(all_idx)
        if n_total < min_n_longterm:
            per_regime[regime] = {"n": n_total, "verdict": "INSUFFICIENT_DATA",
                                    "reason": f"long-term n<{min_n_longterm}"}
            continue
        cell_horizons: dict[str, dict] = {}
        for hname, hsec, hmin_n in horizons:
            cutoff = now_ts - hsec
            seg = [i for i in all_idx if chunk_ts[i] >= cutoff]
            n_h = len(seg)
            if n_h < 3:
                cell_horizons[hname] = {"n": n_h, "r": None, "p": None,
                                          "strength": "NEW", "direction": ""}
                continue
            x = md[seg]
            y = cr[[i + k for i in seg]]
            r, p, _ = _pearsonr_with_p(x, y)
            rho, p_rho, _ = _spearmanr_with_p(x, y)
            # dCor permutation is O(n^2 * n_perm); skip when the
            # monotonic stack is already STRONG (no information gain
            # from also computing dCor) or when n is too small for
            # permutation testing.
            r_v = float(r) if np.isfinite(r) else None
            rho_v = float(rho) if np.isfinite(rho) else None
            mono_conf = max(abs(r_v or 0.0), abs(rho_v or 0.0))
            if n_h >= 8 and mono_conf < strong_r:
                dc, p_dc, _ = _dcor_with_p(x, y, n_perm=500, seed=int(n_h))
            else:
                dc = _dcor(x, y) if n_h >= 4 else float("nan")
                p_dc = float("nan")
            dc_v = float(dc) if np.isfinite(dc) else None
            strength, direction, conf = _strength(n_h, r_v, rho_v, hmin_n)
            non_linear = (
                r_v is not None and rho_v is not None
                and abs(abs(rho_v) - abs(r_v)) >= 0.10
                and max(abs(r_v), abs(rho_v)) >= moderate_r
            )
            # Non-monotonic flag: dC clears moderate but the monotonic
            # stack does not. Means there's dependence Pearson and
            # Spearman BOTH missed; direction is undefined so the
            # cell stays WEAK in the strength tier, but it's surfaced
            # downstream for manual inspection.
            non_monotonic = (
                dc_v is not None and dc_v >= moderate_r
                and mono_conf < moderate_r
                and n_h >= hmin_n
            )
            cell_horizons[hname] = {
                "n": n_h,
                "r": round(r_v, 4) if r_v is not None else None,
                "rho": round(rho_v, 4) if rho_v is not None else None,
                "dcor": round(dc_v, 4) if dc_v is not None else None,
                "p": round(float(p), 4) if np.isfinite(p) else None,
                "p_rho": round(float(p_rho), 4) if np.isfinite(p_rho) else None,
                "p_dcor": round(float(p_dc), 4) if np.isfinite(p_dc) else None,
                "confidence": round(conf, 4) if conf is not None else None,
                "strength": strength,
                "direction": direction,
                "non_linear": bool(non_linear),
                "non_monotonic": bool(non_monotonic),
            }

        # Derive tradability category from horizon strengths.
        intraday = cell_horizons["intraday"]
        daily = cell_horizons["daily"]
        weekly = cell_horizons["weekly"]
        longterm = cell_horizons["longterm"]

        intraday_strong = intraday["strength"] == "STRONG"
        daily_strong = daily["strength"] == "STRONG"
        weekly_strong = weekly["strength"] == "STRONG"
        longterm_strong = longterm["strength"] == "STRONG"
        daily_ok = daily["strength"] in ("STRONG", "MODERATE")
        intraday_quiet = intraday["strength"] in ("WEAK", "NEW")
        daily_quiet = daily["strength"] in ("WEAK", "NEW")

        # Sign consistency across long-term / weekly / daily (when
        # present at MODERATE+). Uses the strength-determining statistic
        # (whichever of r/rho has larger magnitude — captured in the
        # 'direction' field) so non-linear signals are not penalized for
        # disagreeing on Pearson sign.
        signs = []
        for h in (longterm, weekly, daily):
            conf = h.get("confidence")
            dirn = h.get("direction")
            if conf is not None and conf >= moderate_r and dirn:
                signs.append(1 if dirn == "momentum" else -1)
        consistent_sign = (len(signs) >= 2
                              and (all(s > 0 for s in signs)
                                    or all(s < 0 for s in signs)))

        if longterm_strong and weekly_strong and daily_ok and consistent_sign:
            verdict = "ALWAYS_TRADEABLE"
        elif intraday_strong or daily_strong:
            verdict = "CURRENTLY_TRADEABLE"
        elif (longterm_strong or weekly_strong) and daily_quiet and intraday_quiet:
            verdict = "HISTORICALLY_TRADEABLE_NOT_NOW"
        elif not any(h["strength"] == "STRONG"
                      for h in cell_horizons.values()):
            verdict = "NEVER_TRADEABLE"
        else:
            verdict = "AMBIGUOUS"

        # Headline direction: prefer intraday if strong; else daily;
        # else weekly; else long-term.
        direction = ""
        for h in (intraday, daily, weekly, longterm):
            if h["strength"] in ("STRONG", "MODERATE") and h.get("direction"):
                direction = h["direction"]
                break

        per_regime[regime] = {
            "n": n_total,
            "horizons": cell_horizons,
            "verdict": verdict,
            "direction": direction,
        }

    return {"label": label, "feature": feature_name,
            "per_regime": per_regime, "now_ts": now_ts}


# ---------------------------------------------------------------------------
# Pass-15: multi-feature scan. The dipole equation is one candidate
# predictor; the test infrastructure (Pearson + Spearman + dCor at four
# horizons) can be aimed at any per-chunk feature. This section defines
# a registry of 10+ candidate features and a runner that evaluates each
# one through classify_cell_tradability so we get a unified
# (feature × asset × venue × regime) tradeability map.
#
# Feature roster (Pass-15):
#   PROVEN microstructure (computable from existing chunk data):
#     1. mean_dipole           baseline; signed volume / total volume
#     2. mean_ofi              raw signed volume (un-normalized dipole)
#     3. vpin_like             |buy - sell| / total per bar, mean over chunk
#                              (Volume-Synchronized Probability of Informed
#                              Trading proxy — bar-bucketed)
#     4. hawkes_eta            self-excitation intensity (existing feature)
#     5. realized_vol_z        vol-regime indicator
#
#   NOVEL (computable from existing chunk data):
#     6. cross_asset_dipole    sibling-asset dipole × this asset's dipole
#                              (sign-aligned: positive = coordinated flow)
#     7. cross_venue_gap_z     (this venue mid − other venue mid), z-scored
#                              (cross-venue arb pressure)
#     8. hurst_delta           Δhurst from prior chunk; flags regime breaks
#
#   EXPERIMENTAL (theoretical, computable):
#     9. trade_size_entropy    Shannon H of per-bar trade-size distribution
#                              within chunk (informed-flow signature)
#    10. microprice_drift      (chunk-final microprice − chunk-mean mid)
#                              (Stoikov hidden-edge proxy; requires L1
#                              size capture — falls back to 0 when bins
#                              predate the 2026-05 schema bump)
#
#   INFRASTRUCTURE-PENDING (named in roster; no backfill yet):
#    11. funding_rate_z        perp funding z-score (8h cycles)
#    12. oi_delta_z            open-interest delta z-score
# ---------------------------------------------------------------------------


@dataclass
class MultiFeatureContext:
    """Inputs to a multi-feature scan for one (asset, venue)."""
    chunks: list  # this venue's chunks for this asset
    feats: list   # parallel MarketFeatures per chunk
    sibling_chunks: list | None = None   # same-venue chunks for the OTHER asset
    sibling_feats: list | None = None
    other_venue_chunks: list | None = None  # OTHER venue, same asset
    other_venue_feats: list | None = None
    perp_chunks: list | None = None      # Bybit perp, same asset
    perp_feats: list | None = None


def _ts_aligned_lookup(this_chunks: list,
                         other_chunks: list,
                         tolerance_sec: float = 90.0) -> list[int]:
    """For each chunk in this_chunks, return the index of the
    closest-in-time chunk in other_chunks (by chunk-start ts), or -1
    if no match within tolerance_sec. Linear in min(len) — good
    enough for ~hundreds of chunks per venue."""
    if not other_chunks:
        return [-1] * len(this_chunks)
    other_ts = [float(c.bars[0].ts) if c.bars else 0.0 for c in other_chunks]
    out = []
    for c in this_chunks:
        this_ts = float(c.bars[0].ts) if c.bars else 0.0
        if this_ts == 0.0:
            out.append(-1); continue
        # Find closest in other_ts via binary-search-ish linear scan.
        best_i = -1
        best_dt = float("inf")
        for i, t in enumerate(other_ts):
            dt = abs(t - this_ts)
            if dt < best_dt:
                best_dt = dt
                best_i = i
        if best_dt <= tolerance_sec:
            out.append(best_i)
        else:
            out.append(-1)
    return out


def _feat_mean_dipole(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.array([
        float(np.mean([b.dipole for b in c.bars])) if c.bars else 0.0
        for c in ctx.chunks
    ]), ""


def _feat_mean_ofi(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.array([
        float(np.mean([b.signed_volume for b in c.bars])) if c.bars else 0.0
        for c in ctx.chunks
    ]), ""


def _feat_vpin_like(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    out = []
    for c in ctx.chunks:
        if not c.bars:
            out.append(0.0); continue
        imbs = []
        for b in c.bars:
            tot = b.buy_vol + b.sell_vol
            if tot > 0:
                imbs.append(abs(b.buy_vol - b.sell_vol) / tot)
        out.append(float(np.mean(imbs)) if imbs else 0.0)
    return np.array(out), ""


def _feat_hawkes_eta(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if not ctx.feats:
        return np.zeros(len(ctx.chunks)), "no MarketFeatures available"
    return np.array([float(getattr(f, "hawkes_eta", 0.0) or 0.0)
                     for f in ctx.feats]), ""


def _feat_realized_vol_z(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if not ctx.feats:
        return np.zeros(len(ctx.chunks)), "no MarketFeatures available"
    rv = np.array([float(getattr(f, "realized_vol", 0.0) or 0.0)
                    for f in ctx.feats])
    mu, sd = float(np.mean(rv)), float(np.std(rv))
    return (rv - mu) / (sd + 1e-9), ""


def _feat_cross_asset_dipole(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.sibling_chunks is None:
        return np.zeros(len(ctx.chunks)), "no sibling-asset chunks loaded"
    sib_idx = _ts_aligned_lookup(ctx.chunks, ctx.sibling_chunks)
    out = []
    for c, si in zip(ctx.chunks, sib_idx):
        self_d = float(np.mean([b.dipole for b in c.bars])) if c.bars else 0.0
        if si < 0:
            out.append(0.0); continue
        sc = ctx.sibling_chunks[si]
        sib_d = float(np.mean([b.dipole for b in sc.bars])) if sc.bars else 0.0
        # Sign-aligned product: |self||sib| with sign of self*sib.
        # Captures coordinated flow magnitude.
        out.append(self_d * sib_d)
    return np.array(out), ""


def _feat_cross_venue_gap_z(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.other_venue_chunks is None:
        return np.zeros(len(ctx.chunks)), "no other-venue chunks loaded"
    other_idx = _ts_aligned_lookup(ctx.chunks, ctx.other_venue_chunks)
    out = []
    for c, oi in zip(ctx.chunks, other_idx):
        if not c.bars or oi < 0:
            out.append(0.0); continue
        self_mid = float(np.mean([b.mid for b in c.bars if b.mid > 0]) or 0.0)
        oc = ctx.other_venue_chunks[oi]
        other_mid = float(np.mean([b.mid for b in oc.bars if b.mid > 0]) or 0.0)
        if self_mid > 0 and other_mid > 0:
            out.append(self_mid - other_mid)
        else:
            out.append(0.0)
    arr = np.array(out)
    mu, sd = float(np.mean(arr)), float(np.std(arr))
    return (arr - mu) / (sd + 1e-9), ""


def _feat_hurst_delta(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if not ctx.feats:
        return np.zeros(len(ctx.chunks)), "no MarketFeatures available"
    h = np.array([float(getattr(f, "hurst", 0.5) or 0.5)
                  for f in ctx.feats])
    delta = np.concatenate([[0.0], np.diff(h)])
    return delta, ""


def _feat_trade_size_entropy(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    out = []
    for c in ctx.chunks:
        if not c.bars:
            out.append(0.0); continue
        # Use per-bar total volume as a proxy for trade-size distribution
        # (the bin schema doesn't retain individual trade sizes by default).
        vols = np.array([b.buy_vol + b.sell_vol for b in c.bars])
        s = vols.sum()
        if s <= 0:
            out.append(0.0); continue
        p = vols / s
        # Shannon entropy in nats; mask zero probabilities.
        nz = p[p > 0]
        h = float(-np.sum(nz * np.log(nz)))
        out.append(h)
    return np.array(out), ""


def _feat_microprice_drift(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    has_l1 = False
    out = []
    for c in ctx.chunks:
        if not c.bars:
            out.append(0.0); continue
        # Microprice − mid, averaged. Microprice falls back to mid when
        # L1 sizes aren't captured, so drift is 0 on pre-2026-05 bins.
        drift_samples = []
        for b in c.bars:
            if b.bid_qty > 0 and b.ask_qty > 0 and b.bid > 0 and b.ask > 0:
                has_l1 = True
                mp = (b.bid_qty * b.ask + b.ask_qty * b.bid) / (b.bid_qty + b.ask_qty)
                simple_mid = 0.5 * (b.bid + b.ask)
                drift_samples.append(mp - simple_mid)
        out.append(float(np.mean(drift_samples)) if drift_samples else 0.0)
    status = "" if has_l1 else "L1 sizes not captured in any bar (pre-2026-05 bins)"
    return np.array(out), status


def _feat_book_depth_imbalance(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    """L1 depth imbalance: (bid_qty − ask_qty) / (bid_qty + ask_qty),
    in [−1, +1], averaged per chunk. Stoikov microstructure: when one
    side is heavier, price tends to move AWAY from it (toward the
    thinner side). Cleanest direct expression of that observation."""
    has_l1 = False
    out = []
    for c in ctx.chunks:
        if not c.bars:
            out.append(0.0); continue
        samples = []
        for b in c.bars:
            if b.bid_qty > 0 and b.ask_qty > 0:
                has_l1 = True
                samples.append((b.bid_qty - b.ask_qty) / (b.bid_qty + b.ask_qty))
        out.append(float(np.mean(samples)) if samples else 0.0)
    status = "" if has_l1 else "L1 sizes not captured in any bar (pre-2026-05 bins)"
    return np.array(out), status


def _feat_cross_venue_book_imbalance_delta(ctx: MultiFeatureContext
                                              ) -> tuple[np.ndarray, str]:
    """(this venue book imbalance) − (other venue book imbalance), per
    chunk. Cross-platform: when this venue's order book leans buy but
    the other venue's leans sell, only one side is informed. The
    direction of the delta tells us which venue is leading."""
    if ctx.other_venue_chunks is None:
        return np.zeros(len(ctx.chunks)), "no other-venue chunks loaded"
    other_idx = _ts_aligned_lookup(ctx.chunks, ctx.other_venue_chunks)

    def _bi(chunk) -> float | None:
        s = []
        for b in chunk.bars:
            if b.bid_qty > 0 and b.ask_qty > 0:
                s.append((b.bid_qty - b.ask_qty) / (b.bid_qty + b.ask_qty))
        return float(np.mean(s)) if s else None

    out = []
    seen_l1 = False
    for c, oi in zip(ctx.chunks, other_idx):
        if oi < 0:
            out.append(0.0); continue
        self_bi = _bi(c); other_bi = _bi(ctx.other_venue_chunks[oi])
        if self_bi is None or other_bi is None:
            out.append(0.0); continue
        seen_l1 = True
        out.append(self_bi - other_bi)
    status = "" if seen_l1 else "L1 sizes not captured on either venue"
    return np.array(out), status


def _feat_cross_venue_aggressor_agreement(ctx: MultiFeatureContext
                                            ) -> tuple[np.ndarray, str]:
    """Per chunk: fraction of bars where this venue's last_aggressor
    matches the other venue's last_aggressor (within the
    timestamp-aligned chunk). Cross-platform consensus on which side
    is crossing the spread. High agreement = real flow on both venues;
    low agreement = one-venue informed flow or pure noise."""
    if ctx.other_venue_chunks is None:
        return np.zeros(len(ctx.chunks)), "no other-venue chunks loaded"
    other_idx = _ts_aligned_lookup(ctx.chunks, ctx.other_venue_chunks)
    out = []
    seen_any = False
    for c, oi in zip(ctx.chunks, other_idx):
        if oi < 0 or not c.bars:
            out.append(0.0); continue
        oc = ctx.other_venue_chunks[oi]
        # Tally per-bar aggressor on this venue, and per-bar aggressor
        # on the other venue (each chunk has roughly aligned bar count
        # but timestamps may differ — use the chunk-mode last_aggressor
        # as a proxy).
        self_aggr = [b.last_aggressor for b in c.bars if b.last_aggressor]
        other_aggr = [b.last_aggressor for b in oc.bars if b.last_aggressor]
        if not self_aggr or not other_aggr:
            out.append(0.0); continue
        seen_any = True
        # Most-common aggressor on each side; +1 if they match, −1 if not.
        # Encoded as a signed value so the classifier can correlate
        # against direction.
        self_mode = max(set(self_aggr), key=self_aggr.count)
        other_mode = max(set(other_aggr), key=other_aggr.count)
        if self_mode == other_mode:
            # Match: +1 if both "buy" (bullish), −1 if both "sell".
            out.append(1.0 if self_mode == "buy" else -1.0)
        else:
            out.append(0.0)
    status = "" if seen_any else "no last_aggressor info on bars"
    return np.array(out), status


def _feat_perp_spot_basis_z(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    """(perp mid − this venue spot mid), z-scored across the corpus.
    Cross-platform: basis is the carry implied by funding. Persistent
    positive basis → perp longs paying carry → leveraged longs
    crowded. Sign predicts the direction of basis-normalization."""
    if ctx.perp_chunks is None:
        return np.zeros(len(ctx.chunks)), "no Bybit perp chunks loaded (--bybit-perp-bins not supplied)"
    perp_idx = _ts_aligned_lookup(ctx.chunks, ctx.perp_chunks)
    out = []
    seen_any = False
    for c, pi in zip(ctx.chunks, perp_idx):
        if pi < 0 or not c.bars:
            out.append(0.0); continue
        pc = ctx.perp_chunks[pi]
        self_mid = float(np.mean([b.mid for b in c.bars if b.mid > 0]) or 0.0)
        perp_mid = float(np.mean([b.mid for b in pc.bars if b.mid > 0]) or 0.0)
        if self_mid > 0 and perp_mid > 0:
            seen_any = True
            out.append(perp_mid - self_mid)
        else:
            out.append(0.0)
    arr = np.array(out)
    mu, sd = float(np.mean(arr)), float(np.std(arr))
    status = "" if seen_any else "perp/spot mid overlap empty"
    return (arr - mu) / (sd + 1e-9), status


def _feat_perp_spot_dipole_divergence(ctx: MultiFeatureContext
                                          ) -> tuple[np.ndarray, str]:
    """(perp chunk-mean dipole − spot chunk-mean dipole). Cross-platform:
    perp dipole reflects leveraged flow; spot dipole reflects cash flow.
    When perp leans hard one way and spot doesn't follow, leverage is
    being deployed without spot conviction — typically gets unwound."""
    if ctx.perp_chunks is None:
        return np.zeros(len(ctx.chunks)), "no Bybit perp chunks loaded"
    perp_idx = _ts_aligned_lookup(ctx.chunks, ctx.perp_chunks)
    out = []
    for c, pi in zip(ctx.chunks, perp_idx):
        if pi < 0 or not c.bars:
            out.append(0.0); continue
        pc = ctx.perp_chunks[pi]
        self_dip = float(np.mean([b.dipole for b in c.bars]) or 0.0)
        perp_dip = float(np.mean([b.dipole for b in pc.bars]) or 0.0)
        out.append(perp_dip - self_dip)
    return np.array(out), ""


def _feat_triangulated_consensus(ctx: MultiFeatureContext
                                    ) -> tuple[np.ndarray, str]:
    """Sign-aligned three-platform consensus: (CB dipole sign + KR
    dipole sign + Bybit perp dipole sign) / 3 ∈ {−1, −⅓, +⅓, +1}.
    +1 = all three agree bullish, −1 = all three bearish.
    Captures the moments when no venue disagrees — the strongest
    cross-platform conviction signal we can measure."""
    if ctx.other_venue_chunks is None or ctx.perp_chunks is None:
        return np.zeros(len(ctx.chunks)), ("triangulation requires both "
            "other-venue and perp chunks (--bybit-perp-bins not supplied)")
    other_idx = _ts_aligned_lookup(ctx.chunks, ctx.other_venue_chunks)
    perp_idx = _ts_aligned_lookup(ctx.chunks, ctx.perp_chunks)
    out = []
    seen = False
    for c, oi, pi in zip(ctx.chunks, other_idx, perp_idx):
        if oi < 0 or pi < 0 or not c.bars:
            out.append(0.0); continue
        seen = True
        self_dip = float(np.mean([b.dipole for b in c.bars]) or 0.0)
        other_dip = float(np.mean([b.dipole for b in ctx.other_venue_chunks[oi].bars]) or 0.0)
        perp_dip = float(np.mean([b.dipole for b in ctx.perp_chunks[pi].bars]) or 0.0)
        sign_sum = (
            (1 if self_dip > 0 else (-1 if self_dip < 0 else 0)) +
            (1 if other_dip > 0 else (-1 if other_dip < 0 else 0)) +
            (1 if perp_dip > 0 else (-1 if perp_dip < 0 else 0))
        )
        out.append(sign_sum / 3.0)
    status = "" if seen else "no three-platform timestamp overlap"
    return np.array(out), status


def _feat_funding_rate_z(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.zeros(len(ctx.chunks)), "infrastructure-pending: no historical funding backfill"


def _feat_oi_delta_z(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.zeros(len(ctx.chunks)), "infrastructure-pending: no historical OI backfill"


# Registry: ordered for deterministic report output. Cross-platform
# features (cross_*, perp_*, triangulated_*) are the differentiation
# pitch — no competing retail-signal product is publishing this stack.
#
# The `role` field distinguishes how a feature is meant to be used.
# Pass-17 reframe based on the bounded-dipole-thrives findings:
#
#   "predictor" — feature whose value-add is discriminating future
#     forward returns. AUC against forward return is the success
#     metric. Goes into the multi-feature BH-FDR family. Cross-venue
#     z-scores, perp-spot basis, microprice drift, etc.
#
#   "operationalization" — bounded within-channel imbalance form
#     (canonical dipole or close relative). Per the bounded-form theory:
#     these are AUC-equivalent to their underlying raw ratio so they
#     are NOT predictors that generate novel signal. Their value-add is
#     bounded [-1, +1] thresholding for gating + sizing on top of the
#     predictors, plus outlier compression that keeps the heavy-tail
#     end of the distribution operationally tractable. Pass-18 will
#     pull these out of the predictive FDR family (testing them
#     predictively is the wrong test); for now they stay in for
#     measurement continuity but consumers should treat their Tier-2
#     standings as confirmation of the theory, not as regressions.
FEATURE_EXTRACTORS: list[tuple[str, str, str, callable]] = [
    # (feature_id, group, role, extractor)
    # Proven microstructure — single-venue, single-asset
    ("mean_dipole",                       "proven",       "operationalization", _feat_mean_dipole),
    ("mean_ofi",                          "proven",       "predictor",          _feat_mean_ofi),
    ("vpin_like",                         "proven",       "operationalization", _feat_vpin_like),
    ("hawkes_eta",                        "proven",       "predictor",          _feat_hawkes_eta),
    ("realized_vol_z",                    "proven",       "predictor",          _feat_realized_vol_z),
    ("book_depth_imbalance",              "proven",       "operationalization", _feat_book_depth_imbalance),
    # Novel — cross-asset / cross-venue
    ("cross_asset_dipole",                "novel",        "predictor",          _feat_cross_asset_dipole),
    ("cross_venue_gap_z",                 "novel",        "predictor",          _feat_cross_venue_gap_z),
    ("cross_venue_book_imbalance_delta",  "novel",        "predictor",          _feat_cross_venue_book_imbalance_delta),
    ("cross_venue_aggressor_agreement",   "novel",        "predictor",          _feat_cross_venue_aggressor_agreement),
    ("hurst_delta",                       "novel",        "predictor",          _feat_hurst_delta),
    # Cross-platform — spot ↔ perp
    ("perp_spot_basis_z",                 "cross_platform", "predictor",        _feat_perp_spot_basis_z),
    ("perp_spot_dipole_divergence",       "cross_platform", "predictor",        _feat_perp_spot_dipole_divergence),
    ("triangulated_consensus",            "cross_platform", "predictor",        _feat_triangulated_consensus),
    # Experimental — theoretical, low evidence
    ("trade_size_entropy",                "experimental", "predictor",          _feat_trade_size_entropy),
    ("microprice_drift",                  "experimental", "predictor",          _feat_microprice_drift),
    # Infrastructure-pending — wired but skip until backfill exists
    ("funding_rate_z",                    "pending",      "predictor",          _feat_funding_rate_z),
    ("oi_delta_z",                        "pending",      "predictor",          _feat_oi_delta_z),
]


def run_multi_feature_scan(label: str,
                              ctx: MultiFeatureContext,
                              results: list,
                              k: int = 1) -> list[dict]:
    """Run classify_cell_tradability once per feature in the registry.
    Returns one classification result per feature, with the feature
    name + group + extractor-status attached."""
    out = []
    for name, group, role, fn in FEATURE_EXTRACTORS:
        values, status = fn(ctx)
        if status.startswith("infrastructure-pending"):
            out.append({"feature": name, "group": group, "role": role,
                          "status": status, "per_regime": {}})
            continue
        if values is None or not np.any(np.isfinite(values)) or np.std(values) < 1e-12:
            out.append({"feature": name, "group": group, "role": role,
                          "status": status or "zero variance",
                          "per_regime": {}})
            continue
        cell = classify_cell_tradability(
            label, ctx.chunks, results, k=k,
            feature_values=values, feature_name=name)
        cell["group"] = group
        cell["role"] = role
        cell["status"] = status
        out.append(cell)
    return out


def _combined_horizon_p(horizon: dict) -> float | None:
    """Bonferroni-combine the {Pearson, Spearman, dCor permutation}
    p-values within a single horizon. min(p_*) × number-of-finite-stats,
    clipped to 1.0. Returns None when no stat has a finite p (e.g.
    NEW horizon)."""
    ps = []
    for key in ("p", "p_rho", "p_dcor"):
        v = horizon.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= fv <= 1.0):
            continue
        ps.append(fv)
    if not ps:
        return None
    return min(1.0, min(ps) * len(ps))


def apply_multi_feature_fdr(scan_results_by_venue: dict,
                              fdr_q: float = 0.10) -> dict:
    """Apply Benjamini-Hochberg FDR across the full multi-feature
    family: every (feature, venue, regime, horizon) tuple that has a
    finite combined p-value. Mutates the horizon dicts in place to add
    `q` (BH-adjusted q-value) and `bh_significant` (boolean at fdr_q).

    The combined p per horizon is Bonferroni-adjusted across the 2-3
    statistics tested on the same data (Pearson, Spearman, dCor),
    making the per-horizon p conservative; BH-FDR is then applied
    across the family.

    Returns a summary dict: counts of total tests, BH-significant
    rejections, family q-level."""
    flat: list[tuple[float, dict]] = []
    for venue_label, scan in scan_results_by_venue.items():
        for feat_result in scan:
            for regime, cell in feat_result.get("per_regime", {}).items():
                horizons = cell.get("horizons", {})
                if not isinstance(horizons, dict):
                    continue
                for hname in ("intraday", "daily", "weekly", "longterm"):
                    h = horizons.get(hname)
                    if not isinstance(h, dict):
                        continue
                    pc = _combined_horizon_p(h)
                    if pc is None:
                        h["p_combined"] = None
                        h["q"] = None
                        h["bh_significant"] = False
                        continue
                    h["p_combined"] = round(pc, 4)
                    flat.append((pc, h))
    if not flat:
        return {"n_tests": 0, "n_significant": 0, "fdr_q": fdr_q}
    ps = [p for p, _ in flat]
    qvals, rejects = _bh_fdr(ps, q=fdr_q)
    for (_, h), qv, rej in zip(flat, qvals, rejects):
        h["q"] = round(float(qv), 4)
        h["bh_significant"] = bool(rej)
    return {"n_tests": len(flat),
              "n_significant": int(sum(rejects)),
              "fdr_q": fdr_q}


def evaluate_gate_I(label: str, chunks: list[MarketChunk],
                     results: list[ClassificationResult],
                     k: int = 1,
                     min_n: int = 30,
                     fdr_q: float = 0.10) -> dict:
    """For each regime label, compute Pearson r AND Spearman ρ on
    (chunk_mean_dipole_t, chunk_log_return_{t+k}) restricted to
    consecutive chunk pairs in that regime. The p-value driving BH-FDR
    is Bonferroni-adjusted min(p_r, p_ρ) — testing the same data with
    two statistics doubles the family size, so the conservative
    correction divides each p in half before taking the min, or
    equivalently doubles the minimum.

    Cells with n < min_n are recorded but excluded from the test
    (prevents tiny-n artifacts). Surviving cells go through
    Benjamini-Hochberg FDR at q=fdr_q across regimes within this venue.

    Effect size is r2 = max(|r|, |ρ|)² — using the larger of the two
    monotonic statistics so non-linear-but-monotonic edges register.
    """
    if len(chunks) < k + 2:
        return {"label": label, "gate_I": None, "reason": "too few chunks"}

    # Compute per-chunk dipole and per-chunk log return
    mean_dipoles = []
    chunk_returns = []
    for c in chunks:
        bar_dipoles = [b.dipole for b in c.bars]
        mean_dipoles.append(float(np.mean(bar_dipoles)) if bar_dipoles else 0.0)
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12) / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
    md = np.array(mean_dipoles)
    cr = np.array(chunk_returns)
    labels = [r.regime.value for r in results]

    per_regime: dict[str, dict] = {}
    testable_regimes: list[str] = []
    testable_pvalues: list[float] = []
    for regime in set(labels):
        # Indices where chunk t is this regime AND chunk t+k exists
        idx = [i for i in range(len(chunks) - k) if labels[i] == regime]
        n = len(idx)
        if n < min_n:
            per_regime[regime] = {"n": n, "r": None, "rho": None,
                                    "r2": None, "p": None, "note": f"n<{min_n}"}
            continue
        x = md[idx]
        y = cr[[i + k for i in idx]]
        r, p_r, npairs = _pearsonr_with_p(x, y)
        rho, p_rho, _ = _spearmanr_with_p(x, y)
        r_v = float(r) if np.isfinite(r) else None
        rho_v = float(rho) if np.isfinite(rho) else None
        # Effect size on whichever monotonic statistic dominates.
        eff = max(abs(r_v or 0.0), abs(rho_v or 0.0))
        # Bonferroni: testing two stats on the same data doubles
        # family size, so report adjusted min p.
        p_candidates = []
        if np.isfinite(p_r): p_candidates.append(float(p_r))
        if np.isfinite(p_rho): p_candidates.append(float(p_rho))
        if p_candidates:
            p_combined = min(p_candidates) * len(p_candidates)
            p_combined = min(1.0, p_combined)
        else:
            p_combined = float("nan")
        per_regime[regime] = {
            "n": npairs,
            "r": round(r_v, 4) if r_v is not None else None,
            "rho": round(rho_v, 4) if rho_v is not None else None,
            "r2": round(eff * eff, 5) if eff is not None else None,
            "p": round(p_combined, 4) if np.isfinite(p_combined) else None,
            "p_r": round(float(p_r), 4) if np.isfinite(p_r) else None,
            "p_rho": round(float(p_rho), 4) if np.isfinite(p_rho) else None,
            "q": None,
        }
        if np.isfinite(p_combined):
            testable_regimes.append(regime)
            testable_pvalues.append(float(p_combined))

    # Benjamini-Hochberg FDR across testable regimes within this venue.
    qvals, rejects = _bh_fdr(testable_pvalues, q=fdr_q)
    for regime, qv, rej in zip(testable_regimes, qvals, rejects):
        per_regime[regime]["q"] = round(qv, 4)
        per_regime[regime]["bh_reject"] = bool(rej)

    # Gate I: pass if any testable regime has r2 > 0.05 AND survives BH-FDR
    # AND we have >=2 testable regimes (so the FDR correction is meaningful).
    n_testable = len(testable_regimes)
    has_signal = any(
        per_regime[r].get("bh_reject") and (per_regime[r].get("r2") or 0) > 0.05
        for r in testable_regimes
    )
    return {
        "label": label,
        "lag_k": k,
        "min_n": min_n,
        "fdr_q": fdr_q,
        "n_testable_regimes": n_testable,
        "n_evaluable_regimes": n_testable,  # alias for backward compat
        "per_regime": per_regime,
        "has_at_least_one_significant_regime": has_signal,
        "gate_I": has_signal and n_testable >= 2,
    }


# ---------------------------------------------------------------------------
# PASS-7 additions: per-cell feature distributions + sub-cell Gate I
# ---------------------------------------------------------------------------

def _percentiles(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "p25": None, "p50": None, "p75": None,
                 "min": None, "max": None}
    arr = np.asarray(vals, dtype=float)
    return {
        "n": int(len(arr)),
        "p25": round(float(np.percentile(arr, 25)), 4),
        "p50": round(float(np.percentile(arr, 50)), 4),
        "p75": round(float(np.percentile(arr, 75)), 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
    }


def feature_distributions_per_cell(label: str,
                                       chunks: list[MarketChunk],
                                       results: list[ClassificationResult],
                                       feats: list[MarketFeatures]) -> dict:
    """Per-(regime) distributions of: hawkes_eta, hawkes_eta_buy,
    hawkes_eta_sell, hurst, |mean_dipole|. Also tracks Hurst-label split.
    """
    by_regime: dict[str, list[int]] = {}
    for i, r in enumerate(results):
        by_regime.setdefault(r.regime.value, []).append(i)

    out: dict = {"label": label, "by_regime": {}}
    for regime, idxs in by_regime.items():
        eta = [float(feats[i].hawkes_eta) for i in idxs]
        eta_buy = [float(feats[i].hawkes_eta_buy) for i in idxs]
        eta_sell = [float(feats[i].hawkes_eta_sell) for i in idxs]
        hurst = [float(feats[i].hurst) for i in idxs
                  if int(feats[i].hurst_n_returns or 0) >= 8]
        adipole = [abs(float(feats[i].mean_dipole)) for i in idxs]
        h_lbl_counts = {"trending": 0, "reverting": 0, "random": 0, "": 0}
        for i in idxs:
            h_lbl_counts[results[i].hurst_label] = h_lbl_counts.get(
                results[i].hurst_label, 0) + 1
        out["by_regime"][regime] = {
            "n": len(idxs),
            "hawkes_eta": _percentiles(eta),
            "hawkes_eta_buy": _percentiles(eta_buy),
            "hawkes_eta_sell": _percentiles(eta_sell),
            "hurst": _percentiles(hurst),
            "abs_mean_dipole": _percentiles(adipole),
            "hurst_label_counts": h_lbl_counts,
        }
    return out


def evaluate_gate_I_subcells(label: str,
                                chunks: list[MarketChunk],
                                results: list[ClassificationResult],
                                feats: list[MarketFeatures],
                                k: int = 1,
                                min_n_subcell: int = 15) -> dict:
    """Per-(regime, sub-axis) Gate I splits. Two sub-axes:
      - hawkes_eta tier (low/mid/high split at the regime's p33/p67)
      - hurst_label (trending vs reverting vs random)

    A sub-cell that produces a meaningfully different forward predictive r
    from its parent regime's r is evidence the sub-axis is informative.
    Cells with n < min_n_subcell skip sub-cell evaluation (too noisy).
    """
    if len(chunks) < k + 2:
        return {"label": label, "subcells": {}, "reason": "too few chunks"}

    mean_dipoles = []
    chunk_returns = []
    for c in chunks:
        bar_dipoles = [b.dipole for b in c.bars]
        mean_dipoles.append(float(np.mean(bar_dipoles)) if bar_dipoles else 0.0)
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12)
                              / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
    md = np.array(mean_dipoles)
    cr = np.array(chunk_returns)
    labels = [r.regime.value for r in results]

    by_regime: dict[str, list[int]] = {}
    for i, lbl in enumerate(labels):
        if i + k < len(chunks):
            by_regime.setdefault(lbl, []).append(i)

    subcells: dict = {}
    for regime, idxs in by_regime.items():
        if len(idxs) < min_n_subcell * 2:
            # Need at least 2x min_n to split even into 2 tiers
            continue
        # ETA tier split
        etas = np.array([feats[i].hawkes_eta for i in idxs], dtype=float)
        if np.std(etas) > 1e-9:
            p33 = float(np.percentile(etas, 33.33))
            p67 = float(np.percentile(etas, 66.66))
            tiers = {
                "low":  [i for i in idxs if feats[i].hawkes_eta <= p33],
                "mid":  [i for i in idxs if p33 < feats[i].hawkes_eta <= p67],
                "high": [i for i in idxs if feats[i].hawkes_eta > p67],
            }
            eta_subcell: dict = {"p33": round(p33, 3), "p67": round(p67, 3),
                                  "tiers": {}}
            for tier_name, tier_idx in tiers.items():
                if len(tier_idx) < min_n_subcell:
                    eta_subcell["tiers"][tier_name] = {
                        "n": len(tier_idx), "r": None, "p": None,
                        "note": f"n<{min_n_subcell}"}
                    continue
                x = md[tier_idx]
                y = cr[[i + k for i in tier_idx]]
                r, p, npairs = _pearsonr_with_p(x, y)
                eta_subcell["tiers"][tier_name] = {
                    "n": npairs,
                    "r": round(r, 4) if np.isfinite(r) else None,
                    "p": round(p, 4) if np.isfinite(p) else None,
                }
            subcells.setdefault(regime, {})["by_eta"] = eta_subcell

        # Hurst label split
        h_groups: dict[str, list[int]] = {}
        for i in idxs:
            h_groups.setdefault(results[i].hurst_label, []).append(i)
        hurst_subcell: dict = {}
        for lbl, gi in h_groups.items():
            if not lbl:
                continue  # skip "insufficient data"
            if len(gi) < min_n_subcell:
                hurst_subcell[lbl] = {"n": len(gi), "r": None, "p": None,
                                        "note": f"n<{min_n_subcell}"}
                continue
            x = md[gi]
            y = cr[[i + k for i in gi]]
            r, p, npairs = _pearsonr_with_p(x, y)
            hurst_subcell[lbl] = {
                "n": npairs,
                "r": round(r, 4) if np.isfinite(r) else None,
                "p": round(p, 4) if np.isfinite(p) else None,
            }
        if hurst_subcell:
            subcells.setdefault(regime, {})["by_hurst_label"] = hurst_subcell

    return {"label": label, "subcells": subcells,
             "min_n_subcell": min_n_subcell, "lag_k": k}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", type=str, required=True, help="e.g. BTC, ETH")
    p.add_argument("--cb-bins", type=str, required=True)
    p.add_argument("--kr-bins", type=str, required=True)
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--report-path", type=str, default=None)
    p.add_argument("--multi-signal-pelt", action="store_true",
                   help="Run PELT on price + dipole + OFI signals (Phase 1.5 enhancement)")
    p.add_argument("--session-baselines", action="store_true",
                   help="Use per-session baselines (london_active, london_lunch, etc.) instead of global")
    p.add_argument("--herd-rescue", action="store_true",
                   help="Reclassify EQUILIBRIUM chunks adjacent to a confirmed HERD run if they meet relaxed thresholds. Premature; only enable for diagnostic comparison until n>=30 HERD chunks.")
    p.add_argument("--sibling-cb-bins", type=str, default=None,
                   help="Sibling-asset CB bins (e.g. btc_coinbase_bins.json when --asset ETH). Enables F7 cross-asset directional confirmation multiplier on each chunk.")
    p.add_argument("--sibling-kr-bins", type=str, default=None,
                   help="Sibling-asset KR bins (e.g. btc_kraken_bins.json when --asset ETH).")
    p.add_argument("--bybit-perp-bins", type=str, default=None,
                   help="Same-asset Bybit perp bins. When supplied, the "
                        "multi-feature scan computes perp-spot basis, "
                        "perp-spot dipole divergence, and triangulated "
                        "(CB+KR+perp) flow consensus.")
    p.add_argument("--events-calendar", type=str, default="events_calendar.json",
                   help="Path to scheduled-event calendar JSON. Enables F8 event/weekend confidence dampener. Empty/missing file leaves events disabled but weekend dampener still applies.")
    p.add_argument("--hawkes-calibration", type=str,
                   default="hawkes_eta_calibration.json",
                   help="Path to hawkes_eta_calibration.json. When present, per-(asset,venue) elevated/diffuse thresholds drive the F10 hawkes_multiplier. Falls back to literature defaults if missing or entry not found.")
    p.add_argument("--features-out", type=str, default=None,
                   help="Path to JSON dump of per-(asset,venue,regime) feature distributions + sub-cell Gate I (Pass-7 evaluator output).")
    p.add_argument("--subcell-min-n", type=int, default=15,
                   help="Minimum n per sub-cell for Pass-7 sub-cell Gate I. Lower for small corpora; default 15 keeps signal/noise reasonable.")
    p.add_argument("--lag-scan-range", type=int, default=10,
                   help="Half-width (in minutes) of the Gate H lag-scan range. Scan covers [-N, +N] in 1-min steps. Default 10 keeps ETH cheap; raise to 30+ for BTC investigations of CB->KR lead time (Pass-11 found BTC scan hit edge at +10 still rising).")
    p.add_argument("--lag-calibration", type=str,
                   default="cross_venue_lag_calibration.json",
                   help="Path to per-asset cross-venue lag calibration JSON. When present, the evaluator scores Gate H at the calibrated lag (BTC: +15 min CB->KR per Pass-12) and treats structural-divergence assets (ETH per Pass-11) as informational rather than hard-fail. Falls back to base Gate H if file missing or asset entry missing.")
    args = p.parse_args()

    # Load hawkes calibration once; per-(asset, venue) thresholds drive F10
    haw_cal = {}
    if args.hawkes_calibration:
        try:
            with open(args.hawkes_calibration) as _f:
                _payload = json.load(_f)
            haw_cal = _payload.get("calibration", {}) or {}
            print(f"[hawkes] loaded calibration for {len(haw_cal)} entries from "
                  f"{args.hawkes_calibration}")
        except FileNotFoundError:
            print(f"[hawkes] no calibration at {args.hawkes_calibration}; "
                  f"using literature defaults")
        except Exception as e:
            print(f"[hawkes] could not parse calibration ({e}); "
                  f"using literature defaults")

    def _haw_thr(asset: str, venue: str) -> tuple[float | None, float | None]:
        entry = haw_cal.get(f"{asset}/{venue}") or {}
        return entry.get("elevated"), entry.get("diffuse")

    print(f"=== Phase 1.5 Evaluation: {args.asset} ===\n")

    cb_bars = load_bars(args.cb_bins)
    kr_bars = load_bars(args.kr_bins)
    print(f"Coinbase bars: {len(cb_bars)}, Kraken bars: {len(kr_bars)}\n")

    cb_haw_e, cb_haw_d = _haw_thr(args.asset, "Coinbase")
    kr_haw_e, kr_haw_d = _haw_thr(args.asset, "Kraken")
    cb_chunks, cb_results, cb_base, cb_session, cb_feats = classify_venue(
        cb_bars, f"CB-{args.asset}", args.chunk_max_size, args.chunk_min_segment,
        multi_signal_pelt=args.multi_signal_pelt,
        use_session_baselines=args.session_baselines,
        herd_rescue=args.herd_rescue,
        hawkes_elevated=cb_haw_e, hawkes_diffuse=cb_haw_d,
    )
    kr_chunks, kr_results, kr_base, kr_session, kr_feats = classify_venue(
        kr_bars, f"KR-{args.asset}", args.chunk_max_size, args.chunk_min_segment,
        multi_signal_pelt=args.multi_signal_pelt,
        use_session_baselines=args.session_baselines,
        herd_rescue=args.herd_rescue,
        hawkes_elevated=kr_haw_e, hawkes_diffuse=kr_haw_d,
    )

    print(f"CB-{args.asset}: {len(cb_chunks)} chunks, baselines rv={cb_base.rv:.5f}")
    print(f"KR-{args.asset}: {len(kr_chunks)} chunks, baselines rv={kr_base.rv:.5f}")

    # Optional Bybit perp chunks for cross-platform (perp vs spot) features.
    # Same chunker + classifier as spot; the perp feed has the same
    # MarketBar shape, so the existing pipeline applies unchanged.
    perp_chunks = None
    perp_feats = None
    if args.bybit_perp_bins:
        perp_bars = load_bars(args.bybit_perp_bins)
        perp_chunks, _perp_results, perp_base, _perp_session, perp_feats = classify_venue(
            perp_bars, f"BB-{args.asset}", args.chunk_max_size,
            args.chunk_min_segment,
            multi_signal_pelt=args.multi_signal_pelt,
            use_session_baselines=args.session_baselines,
            herd_rescue=args.herd_rescue,
        )
        print(f"BB-{args.asset} (Bybit perp): {len(perp_chunks)} chunks, "
              f"baselines rv={perp_base.rv:.5f}")
    print()
    if args.session_baselines:
        print("  Session-baseline phases:")
        for phase, b in sorted(cb_session.items()):
            if phase != "_global":
                print(f"    CB {phase}: rv={b.rv:.5f}, vol={b.chunk_volume:.3f}")

    # F6: apply cross-venue multipliers to each side's results
    cb_minute_pre = chunk_to_minute_regime(cb_chunks, cb_results, cb_bars)
    kr_minute_pre = chunk_to_minute_regime(kr_chunks, kr_results, kr_bars)
    apply_cross_venue_multiplier(cb_results, cb_chunks, cb_bars, kr_minute_pre)
    apply_cross_venue_multiplier(kr_results, kr_chunks, kr_bars, cb_minute_pre)

    # F7: classify the sibling asset (if bins supplied) and apply cross-asset
    # directional confirmation multipliers per same-venue pairing. ETH and
    # BTC lead each other intraday; same-direction sibling regime boosts
    # confidence, opposite direction damps it. Multiplier band is 1.4 / 0.6
    # (tighter than F6's 1.5 / 0.5) since cross-asset is a weaker prior
    # than cross-venue.
    sib_cb_chunks = None; sib_cb_feats = None
    sib_kr_chunks = None; sib_kr_feats = None
    if args.sibling_cb_bins or args.sibling_kr_bins:
        sibling_asset = "ETH" if args.asset.upper() == "BTC" else (
            "BTC" if args.asset.upper() == "ETH" else None)
        sib_label = sibling_asset or "SIBLING"
        if args.sibling_cb_bins:
            sib_cb_bars = load_bars(args.sibling_cb_bins)
            sib_cb_chunks, sib_cb_results, _, _, sib_cb_feats = classify_venue(
                sib_cb_bars, f"CB-{sib_label}", args.chunk_max_size,
                args.chunk_min_segment,
                multi_signal_pelt=args.multi_signal_pelt,
                use_session_baselines=args.session_baselines,
                herd_rescue=args.herd_rescue,
            )
            sib_cb_minute = chunk_to_minute_regime(
                sib_cb_chunks, sib_cb_results, sib_cb_bars)
            apply_cross_asset_multiplier(
                cb_results, cb_chunks, cb_bars, sib_cb_minute)
        if args.sibling_kr_bins:
            sib_kr_bars = load_bars(args.sibling_kr_bins)
            sib_kr_chunks, sib_kr_results, _, _, sib_kr_feats = classify_venue(
                sib_kr_bars, f"KR-{sib_label}", args.chunk_max_size,
                args.chunk_min_segment,
                multi_signal_pelt=args.multi_signal_pelt,
                use_session_baselines=args.session_baselines,
                herd_rescue=args.herd_rescue,
            )
            sib_kr_minute = chunk_to_minute_regime(
                sib_kr_chunks, sib_kr_results, sib_kr_bars)
            apply_cross_asset_multiplier(
                kr_results, kr_chunks, kr_bars, sib_kr_minute)

    # F8: load scheduled-event calendar (FOMC/CPI/etc.) and apply confidence
    # dampener around event windows + on weekends. No-op if calendar is
    # empty; weekend dampener still applies whenever the file exists.
    event_cal = EventCalendar(args.events_calendar) if args.events_calendar else None
    if event_cal is not None:
        apply_event_multiplier(cb_results, cb_chunks, cb_bars, event_cal)
        apply_event_multiplier(kr_results, kr_chunks, kr_bars, event_cal)

    # Gate G per venue
    g_cb = evaluate_gate_G(f"CB-{args.asset}", cb_results)
    g_kr = evaluate_gate_G(f"KR-{args.asset}", kr_results)
    print(f"--- GATE G (classifier diversity) ---")
    for g in (g_cb, g_kr):
        print(f"  {g['label']}: {g['n_classes']} classes, modal={g['modal_class']} "
              f"({g['modal_pct']:.1%}) -> {'PASS' if g['gate_G'] else 'FAIL'}")
        for cls, n in sorted(g['distribution'].items(), key=lambda x: -x[1]):
            print(f"    {cls:<24} {n:>3}")
    print()

    # Gate H: cross-venue agreement
    cb_minute = chunk_to_minute_regime(cb_chunks, cb_results, cb_bars)
    kr_minute = chunk_to_minute_regime(kr_chunks, kr_results, kr_bars)
    h = evaluate_gate_H(cb_minute, kr_minute)
    print(f"--- GATE H (cross-venue agreement) ---")
    if "reason" in h:
        print(f"  {h['reason']}")
    else:
        print(f"  Overlap minutes: {h['n_overlap_minutes']}")
        print(f"  Strict agreements: {h['n_agreements']} ({h['agreement_rate']:.1%})  "
              f"[{'PASS' if h['gate_H_strict'] else 'FAIL'}]")
        print(f"  Relaxed (no-edge bucket): {h['n_agreements_relaxed']} "
              f"({h['agreement_rate_relaxed']:.1%})  "
              f"[{'PASS' if h['gate_H_relaxed'] else 'FAIL'}]")
        print(f"  Top regime pairs (CB, KR):")
        for (cb_r, kr_r), n in h["confusion_top_5"]:
            tag = "AGREE" if cb_r == kr_r else "disagree"
            print(f"    {cb_r:<22} | {kr_r:<22} | {n:>4} ({tag})")
        print(f"  -> {'PASS' if h['gate_H'] else 'FAIL'} "
              f"(strict >=60%; relaxed reported as info only)")
    print()

    # Gate H lag-scan: timing vs structural divergence (Pass-11)
    lag_half_width = max(1, int(args.lag_scan_range))
    print(f"--- GATE H lag-scan (timing-vs-structural disambiguation, "
          f"±{lag_half_width} min) ---")
    lag = evaluate_gate_H_lag_scan(
        cb_minute, kr_minute,
        lag_range_min=range(-lag_half_width, lag_half_width + 1))
    if lag.get("lag_scan") is None:
        print(f"  {lag.get('reason', 'no scan')}")
    else:
        print(f"  base @ lag=0: strict={lag['base_strict']:.1%}  "
              f"relaxed={lag['base_relaxed']:.1%}")
        print(f"  best lag: {lag['best_lag_min']:+d} min "
              f"(strict={lag['best_strict']:.1%}, "
              f"relaxed_at_best={lag['best_relaxed_at_best_lag']:.1%})")
        if lag["is_timing_driven"]:
            print(f"  -> TIMING-DRIVEN: best lag != 0 clears strict 60% threshold")
        else:
            print(f"  -> structural at scanned lags (best lag doesn't clear 60% strict)")
        print(f"  per-lag agreement (lag_min : strict / relaxed / n_overlap):")
        for entry in lag["lag_scan"]:
            if entry["strict"] is None:
                print(f"    {entry['lag_min']:+3d} : --   /   --  / n={entry['n_overlap']}")
            else:
                print(f"    {entry['lag_min']:+3d} : {entry['strict']:.1%} / "
                      f"{entry['relaxed']:.1%} / n={entry['n_overlap']}")
    print()

    # Gate H calibrated: per-asset cross-venue lag + structural-divergence
    # handling (Pass-13). Uses cross_venue_lag_calibration.json — a
    # persisted record of Pass-11/12 findings (BTC: CB leads KR by 15min;
    # ETH: structural divergence at any lag).
    lag_calibration = load_lag_calibration(args.lag_calibration)
    h_calibrated = evaluate_gate_H_calibrated(
        args.asset, cb_minute, kr_minute, lag_calibration)
    print(f"--- GATE H (asset-specific, calibrated) ---")
    if h_calibrated.get("structural_divergence_flag"):
        # Asset previously flagged as structural in the calibration file.
        # The flag is informational only — the gate verdict reflects the
        # recorded max strict at any lag.
        print(f"  {args.asset}: structural-divergence flag set "
              f"(prior scan {h_calibrated.get('calibration_pass', '?')})")
        print(f"    max strict at any lag (recorded): "
              f"{h_calibrated['max_strict_at_any_lag']:.1%}")
        print(f"    max relaxed at any lag (recorded): "
              f"{h_calibrated['max_relaxed_at_any_lag']:.1%} (info only)")
        print(f"  -> {h_calibrated['verdict']} "
              f"(no lag in scanned range clears 60% strict)")
    elif h_calibrated["verdict"] == "NO_CALIBRATION":
        print(f"  {h_calibrated['reason']} — falling back to base Gate H verdict")
    elif h_calibrated["verdict"] == "INSUFFICIENT_OVERLAP":
        print(f"  insufficient overlap at calibrated lag={h_calibrated['lag_min']}")
    else:
        primary = h_calibrated.get("primary_venue", "?")
        secondary = h_calibrated.get("secondary_venue", "?")
        lag = h_calibrated["lag_min"]
        print(f"  {args.asset}: {primary} leads {secondary} by {lag:+d} min "
              f"(calibrated {h_calibrated.get('calibration_pass', '?')})")
        print(f"    strict at lag={lag:+d}: "
              f"{h_calibrated['strict_at_lag']:.1%}  "
              f"[{'PASS' if h_calibrated['strict_pass'] else 'FAIL'}]")
        print(f"    relaxed at lag={lag:+d}: "
              f"{h_calibrated['relaxed_at_lag']:.1%}  "
              f"(info only)")
        print(f"  -> {h_calibrated['verdict']} (strict >=60% at calibrated lag)")
    print()

    # Gate I per venue
    i_cb = evaluate_gate_I(f"CB-{args.asset}", cb_chunks, cb_results, k=1)
    i_kr = evaluate_gate_I(f"KR-{args.asset}", kr_chunks, kr_results, k=1)
    print(f"--- GATE I (per-regime forward predictive R^2 at lag k=1, "
          f"r + ρ, Bonferroni-adjusted) ---")
    for ig in (i_cb, i_kr):
        print(f"  {ig['label']}:")
        if "reason" in ig:
            print(f"    {ig['reason']}")
            continue
        for regime, stat in sorted(ig["per_regime"].items(), key=lambda x: -(x[1].get("n") or 0)):
            if stat.get("r") is None:
                note = stat.get("note", "insufficient data")
                print(f"    {regime:<24}  n={stat['n']:>3}  {note}")
            else:
                q = stat.get("q")
                marker = " <- significant (BH q<=0.10)" if stat.get("bh_reject") and (stat["r2"] or 0) > 0.05 else ""
                qstr = f"  q={q:.3f}" if q is not None else ""
                rho_v = stat.get("rho")
                rho_str = f"  ρ={rho_v:+.3f}" if rho_v is not None else ""
                print(f"    {regime:<24}  n={stat['n']:>3}  r={stat['r']:+.3f}"
                      f"{rho_str}  R^2={stat['r2']:.4f}  p={stat['p']:.3f}{qstr}{marker}")
        print(f"    -> {'PASS' if ig['gate_I'] else 'FAIL'} "
              f"(need >=1 BH-significant regime with R^2>0.05, >=2 testable cells, "
              f"min n={ig.get('min_n','?')})")
    print()

    # HERD persistence summary (sustained N-chunk runs)
    print(f"--- HERD persistence (consecutive same-direction chunks) ---")
    for label, results in [(f"CB-{args.asset}", cb_results), (f"KR-{args.asset}", kr_results)]:
        runs = _herd_runs(results)
        if not runs:
            print(f"  {label}: no sustained HERD runs (all HERD chunks isolated)")
            continue
        for start, length, regime, rescued in runs:
            extra = f" [{rescued} rescued]" if rescued else ""
            print(f"  {label}: {regime} run of {length} chunks "
                  f"starting at idx {start}{extra}")
    print()

    # WHALE -> HERD cascade detection (notification-worthy events)
    print(f"--- WHALE -> HERD cascade events ---")
    for label, results in [(f"CB-{args.asset}", cb_results), (f"KR-{args.asset}", kr_results)]:
        events = detect_whale_to_herd_cascades(results)
        if not events:
            print(f"  {label}: no single-venue WHALE->HERD cascades")
            continue
        for ev in events:
            print(f"  {label}: {ev['summary']}  [direction={ev['direction']}]")
    cb_minute_now = chunk_to_minute_regime(cb_chunks, cb_results, cb_bars)
    kr_minute_now = chunk_to_minute_regime(kr_chunks, kr_results, kr_bars)
    cross_events = (
        detect_cross_venue_whale_herd_simultaneity(
            cb_results, cb_chunks, cb_bars, kr_minute_now,
            primary_label=f"CB-{args.asset}", other_label=f"KR-{args.asset}")
        + detect_cross_venue_whale_herd_simultaneity(
            kr_results, kr_chunks, kr_bars, cb_minute_now,
            primary_label=f"KR-{args.asset}", other_label=f"CB-{args.asset}")
    )
    if cross_events:
        for ev in cross_events:
            print(f"  CROSS-VENUE: {ev['summary']}  [direction={ev['direction']}]")
    else:
        print(f"  CROSS-VENUE: no WHALE+HERD simultaneity detected")
    print()

    # F6 confidence multiplier summary
    print(f"--- F6 cross-venue confidence multipliers ---")
    cb_confirm = sum(1 for r in cb_results if r.cross_venue_multiplier > 1.0)
    cb_disagree = sum(1 for r in cb_results if r.cross_venue_multiplier < 1.0)
    kr_confirm = sum(1 for r in kr_results if r.cross_venue_multiplier > 1.0)
    kr_disagree = sum(1 for r in kr_results if r.cross_venue_multiplier < 1.0)
    print(f"  CB-{args.asset}: {cb_confirm}/{len(cb_results)} chunks confirmed by KR (mult=1.5),"
          f" {cb_disagree} disagreement (mult=0.5)")
    print(f"  KR-{args.asset}: {kr_confirm}/{len(kr_results)} chunks confirmed by CB (mult=1.5),"
          f" {kr_disagree} disagreement (mult=0.5)")
    print()

    # F7 cross-asset multiplier summary (only if sibling bins were supplied)
    if args.sibling_cb_bins or args.sibling_kr_bins:
        print(f"--- F7 cross-asset confidence multipliers ---")
        for label, results in [(f"CB-{args.asset}", cb_results),
                                (f"KR-{args.asset}", kr_results)]:
            agree = sum(1 for r in results if r.cross_asset_multiplier > 1.0)
            disagree = sum(1 for r in results if r.cross_asset_multiplier < 1.0)
            neutral = len(results) - agree - disagree
            print(f"  {label}: {agree}/{len(results)} same-direction sibling "
                  f"(mult=1.4), {disagree} opposite (mult=0.6), "
                  f"{neutral} neutral/no-overlap (mult=1.0)")
        print()

    # F8 event / weekend dampener summary
    if event_cal is not None:
        print(f"--- F8 event-proximity / weekend confidence dampeners ---")
        print(f"  Calendar: {len(event_cal.events)} events loaded from {args.events_calendar}")
        for label, results in [(f"CB-{args.asset}", cb_results),
                                (f"KR-{args.asset}", kr_results)]:
            tight = sum(1 for r in results if abs(r.event_multiplier - 0.7) < 1e-6)
            loose = sum(1 for r in results if abs(r.event_multiplier - 0.85) < 1e-6)
            unaffected = sum(1 for r in results if r.event_multiplier > 0.999)
            print(f"  {label}: {tight} chunks ±30min event (mult=0.70), "
                  f"{loose} ±60min event/weekend (mult=0.85), "
                  f"{unaffected} unaffected (mult=1.0)")
        print()

    # F10 Hawkes-multiplier distribution (directional regimes only)
    print(f"--- F10 Hawkes multiplier distribution (directional cells) ---")
    for label, results in [(f"CB-{args.asset}", cb_results),
                            (f"KR-{args.asset}", kr_results)]:
        boost = sum(1 for r in results if abs(r.hawkes_multiplier - 1.15) < 1e-6)
        dampen = sum(1 for r in results if abs(r.hawkes_multiplier - 0.85) < 1e-6)
        neutral = sum(1 for r in results if abs(r.hawkes_multiplier - 1.0) < 1e-6)
        print(f"  {label}: {boost} chunks η>=p75 (mult=1.15), "
              f"{dampen} η<=p25 (mult=0.85), {neutral} neutral (mult=1.0)")
    print()

    # F9 Hurst label distribution (orthogonal trending/reverting axis)
    print(f"--- F9 Hurst label distribution (DFA on chunk log returns) ---")
    for label, results in [(f"CB-{args.asset}", cb_results),
                            (f"KR-{args.asset}", kr_results)]:
        trending = sum(1 for r in results if r.hurst_label == "trending")
        reverting = sum(1 for r in results if r.hurst_label == "reverting")
        random_ = sum(1 for r in results if r.hurst_label == "random")
        unset = sum(1 for r in results if not r.hurst_label)
        h_vals = [r.hurst for r in results if r.hurst_label]
        h_mean = float(np.mean(h_vals)) if h_vals else 0.5
        print(f"  {label}: trending={trending}  reverting={reverting}  "
              f"random={random_}  insufficient-data={unset}  "
              f"mean_H={h_mean:.3f}")
    print()

    # --- Pass-7: per-(asset, venue, regime) feature distributions ---
    print("--- PASS-7 per-cell feature distributions ---")
    pass7 = {}
    for label, chunks, results, feats in [
        (f"CB-{args.asset}", cb_chunks, cb_results, cb_feats),
        (f"KR-{args.asset}", kr_chunks, kr_results, kr_feats),
    ]:
        dist = feature_distributions_per_cell(label, chunks, results, feats)
        pass7[label] = {"distributions": dist}
        print(f"\n  [{label}]")
        for regime, stats in sorted(dist["by_regime"].items(),
                                       key=lambda x: -x[1]["n"]):
            n = stats["n"]
            eta = stats["hawkes_eta"]
            eta_b = stats["hawkes_eta_buy"]
            eta_s = stats["hawkes_eta_sell"]
            hu = stats["hurst"]
            ad = stats["abs_mean_dipole"]
            print(f"    {regime:<22} n={n:>4}  η={eta['p25']:.2f}/{eta['p50']:.2f}/{eta['p75']:.2f}  "
                  f"ηb={eta_b['p50']:.2f}  ηs={eta_s['p50']:.2f}  "
                  f"H={hu['p50'] if hu['p50'] is not None else float('nan'):.2f}  "
                  f"|d|p50={ad['p50']:.2f}")

    print()
    print("--- PASS-7 Gate I sub-cells (η-tier and hurst-label splits) ---")
    for label, chunks, results, feats in [
        (f"CB-{args.asset}", cb_chunks, cb_results, cb_feats),
        (f"KR-{args.asset}", kr_chunks, kr_results, kr_feats),
    ]:
        sub = evaluate_gate_I_subcells(label, chunks, results, feats,
                                          min_n_subcell=args.subcell_min_n)
        pass7[label]["subcells"] = sub
        print(f"\n  [{label}]")
        if not sub["subcells"]:
            print(f"    (no cells with n>={2*args.subcell_min_n} for sub-split)")
            continue
        for regime, axes in sub["subcells"].items():
            print(f"    {regime}:")
            if "by_eta" in axes:
                e = axes["by_eta"]
                print(f"      η-tier (cuts p33={e['p33']}, p67={e['p67']}):")
                for tier in ("low", "mid", "high"):
                    t = e["tiers"].get(tier, {})
                    if "note" in t:
                        print(f"        {tier:<5} n={t.get('n', 0):>3}  {t['note']}")
                    else:
                        rstr = f"{t.get('r'):+.3f}" if t.get('r') is not None else "  nan"
                        pstr = f"{t.get('p'):.3f}" if t.get('p') is not None else " nan"
                        print(f"        {tier:<5} n={t.get('n', 0):>3}  r={rstr}  p={pstr}")
            if "by_hurst_label" in axes:
                print(f"      hurst-label split:")
                for lbl, t in axes["by_hurst_label"].items():
                    if "note" in t:
                        print(f"        {lbl:<10} n={t.get('n', 0):>3}  {t['note']}")
                    else:
                        rstr = f"{t.get('r'):+.3f}" if t.get('r') is not None else "  nan"
                        pstr = f"{t.get('p'):.3f}" if t.get('p') is not None else " nan"
                        print(f"        {lbl:<10} n={t.get('n', 0):>3}  r={rstr}  p={pstr}")
    print()

    if args.features_out:
        with open(args.features_out, "w") as f:
            json.dump(pass7, f, indent=2, default=str)
        print(f"Pass-7 features dump: {args.features_out}\n")

    # TRADEABLE SIGNAL REPORT (Pass-14) — the headline. Per-cell
    # horizon-based classification using the same horizons + thresholds
    # as edge_tracker.MultiHorizonEdgeTracker:
    #   intraday=4h, daily=24h, weekly=7d, longterm=30d
    # Tradability categories: ALWAYS / CURRENTLY / HISTORICALLY_NOT_NOW /
    # NEVER / AMBIGUOUS / INSUFFICIENT_DATA. Goal: find strong tradeable
    # signals right now. Gate reports below are diagnostics.
    print(f"--- TRADEABLE SIGNAL REPORT (per-cell, multi-horizon) ---")
    cb_trade = classify_cell_tradability(f"CB-{args.asset}",
                                            cb_chunks, cb_results, k=1)
    kr_trade = classify_cell_tradability(f"KR-{args.asset}",
                                            kr_chunks, kr_results, k=1)
    by_category: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
    for venue_report in (cb_trade, kr_trade):
        venue = venue_report["label"]
        for regime, cell in venue_report.get("per_regime", {}).items():
            by_category[cell["verdict"]].append((venue, regime, cell))
    # Print in priority order — actionable categories first.
    for cat in ("ALWAYS_TRADEABLE",
                  "CURRENTLY_TRADEABLE",
                  "HISTORICALLY_TRADEABLE_NOT_NOW",
                  "AMBIGUOUS",
                  "NEVER_TRADEABLE",
                  "INSUFFICIENT_DATA"):
        cells = by_category.get(cat, [])
        if not cells:
            continue
        print(f"\n  [{cat}]  ({len(cells)} cell(s))")
        for venue, regime, cell in cells:
            if cat == "INSUFFICIENT_DATA":
                reason = cell.get("reason", "")
                print(f"    {venue:<8} {regime:<22} n={cell.get('n', 0):>4}  "
                      f"({reason})")
                continue
            horizons = cell.get("horizons", {})
            dir_word = cell.get("direction", "") or "-"
            h_strs = []
            non_linear_marks: list[str] = []
            non_monotonic_marks: list[str] = []
            for hname in ("intraday", "daily", "weekly", "longterm"):
                h = horizons.get(hname, {})
                if h.get("r") is None and h.get("rho") is None:
                    h_strs.append(f"{hname}={h.get('strength', 'NEW')}"
                                    f"(n={h.get('n', 0)})")
                    continue
                r_v = h.get("r")
                rho_v = h.get("rho")
                dc_v = h.get("dcor")
                # Show whichever monotonic stat has larger magnitude
                # (the strength driver); annotate with the other when
                # it diverges by >=0.05. Append dC only when it
                # exceeds the larger monotonic by >=0.10 (means there's
                # non-monotonic structure on top of any monotonic edge).
                r_mag = abs(r_v) if r_v is not None else -1
                rho_mag = abs(rho_v) if rho_v is not None else -1
                if rho_mag > r_mag:
                    primary, prim_name = rho_v, "ρ"
                    secondary, sec_name = r_v, "r"
                else:
                    primary, prim_name = r_v, "r"
                    secondary, sec_name = rho_v, "ρ"
                tag = f"{prim_name}={primary:+.2f}"
                if (secondary is not None and primary is not None
                        and abs(abs(primary) - abs(secondary)) >= 0.05):
                    tag += f"|{sec_name}={secondary:+.2f}"
                if (dc_v is not None
                        and dc_v - max(r_mag, rho_mag, 0.0) >= 0.10):
                    tag += f"|dC={dc_v:.2f}"
                h_strs.append(f"{hname}={h['strength']}/"
                                f"{tag}(n={h['n']})")
                if h.get("non_linear"):
                    non_linear_marks.append(hname)
                if h.get("non_monotonic"):
                    non_monotonic_marks.append(hname)
            tags = []
            if non_linear_marks:
                tags.append(f"non-linear:{','.join(non_linear_marks)}")
            if non_monotonic_marks:
                tags.append(f"non-monotonic:{','.join(non_monotonic_marks)}")
            tag_suffix = (f"  [{' | '.join(tags)}]" if tags else "")
            print(f"    {venue:<8} {regime:<22} n={cell.get('n', 0):>4}  "
                  f"{dir_word:<9}  " + "  ".join(h_strs) + tag_suffix)
    print()

    # MULTI-FEATURE TRADEABLE SIGNAL REPORT (Pass-16). The same
    # horizon-based classifier (Pearson + Spearman + dCor) is run for
    # each candidate feature in FEATURE_EXTRACTORS, then BH-FDR is
    # applied across every (feature, venue, regime, horizon) test
    # in one family at q=0.10. Cells surviving BH-FDR are "BH-significant"
    # — the tier-1 / high-conviction discovery list. Cells that classify
    # as ALWAYS/CURRENTLY_TRADEABLE by strength tier but DON'T survive
    # BH-FDR are "exploratory" tier — interesting but consistent with
    # multiple-comparisons noise at q=0.10.
    print(f"--- MULTI-FEATURE TRADEABLE SIGNAL REPORT (Pass-16, FDR-corrected) ---")
    venue_ctxs = [
        (f"CB-{args.asset}", MultiFeatureContext(
            chunks=cb_chunks, feats=cb_feats,
            sibling_chunks=sib_cb_chunks, sibling_feats=sib_cb_feats,
            other_venue_chunks=kr_chunks, other_venue_feats=kr_feats,
            perp_chunks=perp_chunks, perp_feats=perp_feats),
         cb_results),
        (f"KR-{args.asset}", MultiFeatureContext(
            chunks=kr_chunks, feats=kr_feats,
            sibling_chunks=sib_kr_chunks, sibling_feats=sib_kr_feats,
            other_venue_chunks=cb_chunks, other_venue_feats=cb_feats,
            perp_chunks=perp_chunks, perp_feats=perp_feats),
         kr_results),
    ]
    scan_by_venue: dict[str, list[dict]] = {}
    for venue_label, ctx, results in venue_ctxs:
        scan_by_venue[venue_label] = run_multi_feature_scan(
            venue_label, ctx, results, k=1)
    fdr_summary = apply_multi_feature_fdr(scan_by_venue, fdr_q=0.10)
    print(f"  Family size: {fdr_summary['n_tests']} (feature, venue, regime, "
          f"horizon) tests at fdr_q={fdr_summary['fdr_q']}; "
          f"{fdr_summary['n_significant']} survive BH-FDR.\n")

    # Collect actionable rows, tagging by tier.
    # Tier 1 = strength tier surfaces it AND at least one BH-significant horizon
    # Tier 2 = strength tier surfaces it but NO horizon is BH-significant
    # Tier 3 = no surface verdict but a non-linear or non-monotonic flag fires
    tier_rows: dict[int, list] = {1: [], 2: [], 3: []}
    pending_status: list[tuple[str, str]] = []
    for venue_label, scan in scan_by_venue.items():
        for feat_result in scan:
            fname = feat_result["feature"]
            group = feat_result["group"]
            if feat_result.get("status", "").startswith("infrastructure-pending"):
                if (fname, feat_result["status"]) not in pending_status:
                    pending_status.append((fname, feat_result["status"]))
                continue
            if feat_result.get("status"):
                if (fname, feat_result["status"]) not in pending_status:
                    pending_status.append((fname, feat_result["status"]))
                continue
            for regime, cell in feat_result.get("per_regime", {}).items():
                verdict = cell.get("verdict", "INSUFFICIENT_DATA")
                horizons = cell.get("horizons", {})
                any_bh = any(isinstance(h, dict) and h.get("bh_significant")
                              for h in horizons.values())
                nl_flag = any(isinstance(h, dict) and h.get("non_linear")
                               for h in horizons.values())
                nm_flag = any(isinstance(h, dict) and h.get("non_monotonic")
                               for h in horizons.values())
                actionable_verdict = verdict in (
                    "ALWAYS_TRADEABLE", "CURRENTLY_TRADEABLE",
                    "HISTORICALLY_TRADEABLE_NOT_NOW")
                if actionable_verdict and any_bh:
                    tier_rows[1].append((group, fname, venue_label, regime, verdict, cell))
                elif actionable_verdict:
                    tier_rows[2].append((group, fname, venue_label, regime, verdict, cell))
                elif nl_flag or nm_flag:
                    tier_rows[3].append((group, fname, venue_label, regime, verdict, cell))

    group_order = {"proven": 0, "novel": 1, "cross_platform": 2,
                       "experimental": 3, "pending": 4}
    verdict_order = {"ALWAYS_TRADEABLE": 0, "CURRENTLY_TRADEABLE": 1,
                       "HISTORICALLY_TRADEABLE_NOT_NOW": 2,
                       "AMBIGUOUS": 3, "NEVER_TRADEABLE": 4,
                       "INSUFFICIENT_DATA": 5}

    def _best_conf(cell):
        return max((h.get("confidence") or 0.0)
                   for h in cell.get("horizons", {}).values()
                   if isinstance(h, dict))

    def _min_q(cell):
        qs = [h.get("q") for h in cell.get("horizons", {}).values()
              if isinstance(h, dict) and h.get("q") is not None]
        return min(qs) if qs else 1.0

    def _print_row(group, fname, venue, regime, verdict, cell):
        horizons = cell.get("horizons", {})
        dir_word = cell.get("direction", "") or "-"
        h_strs = []
        flags = []
        for hname in ("intraday", "daily", "weekly", "longterm"):
            h = horizons.get(hname, {})
            strength = h.get("strength", "NEW")
            conf = h.get("confidence")
            sig_mark = "*" if h.get("bh_significant") else ""
            if conf is None:
                h_strs.append(f"{hname}={strength}")
            else:
                qv = h.get("q")
                q_str = f",q={qv:.3f}" if qv is not None else ""
                h_strs.append(f"{hname}={strength}{sig_mark}/c={conf:.2f}{q_str}")
            if h.get("non_linear"):
                flags.append(f"NL:{hname}")
            if h.get("non_monotonic"):
                flags.append(f"NM:{hname}")
        flag_suffix = f"  [{','.join(flags)}]" if flags else ""
        print(f"    {venue:<8} {regime:<22} {verdict:<32} "
              f"{dir_word:<9}  " + "  ".join(h_strs) + flag_suffix)

    tier_titles = {
        1: "TIER 1 — BH-SIGNIFICANT (survives FDR at q=0.10)",
        2: "TIER 2 — STRENGTH-TIER ACTIONABLE BUT NOT BH-SIGNIFICANT (exploratory)",
        3: "TIER 3 — NON-LINEAR / NON-MONOTONIC FLAGS (no surface verdict)",
    }
    for tier in (1, 2, 3):
        rows = tier_rows[tier]
        print(f"\n  ## {tier_titles[tier]}  ({len(rows)} cell(s))")
        if not rows:
            print("    (none)")
            continue
        # Tier 1 sorted by lowest q (most BH-significant first); tiers
        # 2 + 3 by group → verdict → confidence as before.
        if tier == 1:
            rows.sort(key=lambda row: (_min_q(row[5]),
                                          group_order.get(row[0], 99),
                                          -_best_conf(row[5])))
        else:
            rows.sort(key=lambda row: (group_order.get(row[0], 99),
                                          verdict_order.get(row[4], 99),
                                          -_best_conf(row[5])))
        prev_group = None
        prev_feature = None
        for group, fname, venue, regime, verdict, cell in rows:
            if tier > 1 and group != prev_group:
                print(f"\n    === {group.upper()} ===")
                prev_group = group
                prev_feature = None
            if fname != prev_feature:
                print(f"    [{fname}]")
                prev_feature = fname
            _print_row(group, fname, venue, regime, verdict, cell)
    if pending_status:
        print(f"\n  === SKIPPED ===")
        for fname, status in pending_status:
            print(f"  [{fname}] {status}")
    print()

    # Combined verdict — Gate H prefers the calibrated path when present
    # (per-asset lag-aligned scoring + structural-divergence handling
    # introduced Pass-13). Falls back to base Gate H if the calibration
    # file is missing or has no entry for this asset.
    all_g = g_cb["gate_G"] and g_kr["gate_G"]
    base_pass_h = h.get("gate_H", False)
    if h_calibrated["verdict"] == "PASS":
        pass_h = True
        if h_calibrated.get("structural_divergence_flag"):
            h_source = "calibrated:PASS (max-at-any-lag>=60%)"
        else:
            h_source = f"calibrated:PASS@lag={h_calibrated.get('lag_min')}"
    elif h_calibrated["verdict"] == "FAIL":
        pass_h = False
        if h_calibrated.get("structural_divergence_flag"):
            h_source = (f"calibrated:FAIL "
                        f"(max strict {h_calibrated['max_strict_at_any_lag']:.1%}, "
                        f"max relaxed {h_calibrated['max_relaxed_at_any_lag']:.1%} "
                        f"— neither clears 60%)")
        else:
            h_source = f"calibrated:FAIL@lag={h_calibrated.get('lag_min')}"
    else:
        # NO_CALIBRATION or INSUFFICIENT_OVERLAP → fall back to base
        pass_h = base_pass_h
        h_source = "base (no calibration)"
    pass_i = i_cb.get("gate_I", False) or i_kr.get("gate_I", False)  # either venue suffices
    print(f"--- COMBINED VERDICT ---")
    print(f"  Gate G (both venues): {'PASS' if all_g else 'FAIL'}")
    print(f"  Gate H (cross-venue, {h_source}): "
          f"{'PASS' if pass_h else 'FAIL'}")
    print(f"  Gate I (per-regime predictive): {'PASS' if pass_i else 'FAIL'}")
    print(f"  ALL GATES G+H+I: {'PASS' if (all_g and pass_h and pass_i) else 'FAIL'}")

    if args.report_path:
        report = {
            "asset": args.asset,
            "gate_G": {"CB": g_cb, "KR": g_kr},
            "gate_H": h,
            "gate_I": {"CB": i_cb, "KR": i_kr},
            "combined": {
                "all_G": all_g,
                "H": pass_h,
                "I": pass_i,
                "GHI": all_g and pass_h and pass_i,
            },
        }
        with open(args.report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport saved: {args.report_path}")


if __name__ == "__main__":
    main()
