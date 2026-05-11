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
                                  min_n_longterm: int = 30) -> dict:
    """Per-cell horizon-based tradability classifier (Pass-14, +Spearman).

    Mirrors edge_tracker.MultiHorizonEdgeTracker for offline data.
    Uses the same horizon definitions and thresholds so the offline
    and live views report the same way.

      Intraday  = last 4 hours of the corpus
      Daily     = last 24 hours
      Weekly    = last 7 days
      Long-term = last 30 days (or all)

    Per horizon, compute BOTH Pearson r AND Spearman rho over
    (chunk_t.mean_dipole, chunk_{t+k}.log_return) using only chunks
    whose predictor timestamp falls inside the horizon. Pearson is
    linear; Spearman captures monotonic non-linearity. Strength uses
    the larger of |r| and |rho| as the confidence proxy:

      confidence = max(|r|, |rho|)
      direction  = sign of whichever is the larger-magnitude statistic
      STRONG     confidence >= strong_r AND n >= min_n_horizon
      MODERATE   confidence >= moderate_r AND n >= min_n_horizon
      WEAK       confidence <  moderate_r AND n >= min_n_horizon
      NEW        n  <  min_n_horizon

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

    # Per-chunk dipole + forward log return + predictor timestamp.
    mean_dipoles: list[float] = []
    chunk_returns: list[float] = []
    chunk_ts: list[float] = []
    for c in chunks:
        bar_dipoles = [b.dipole for b in c.bars]
        mean_dipoles.append(float(np.mean(bar_dipoles)) if bar_dipoles else 0.0)
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12)
                              / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
        chunk_ts.append(float(c.bars[0].ts) if c.bars else 0.0)
    md = np.array(mean_dipoles)
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
            r_v = float(r) if np.isfinite(r) else None
            rho_v = float(rho) if np.isfinite(rho) else None
            strength, direction, conf = _strength(n_h, r_v, rho_v, hmin_n)
            # Non-linear flag: |rho - r| > 0.10 AND both above moderate_r.
            # Means a monotonic non-linear structure that Pearson alone
            # would have read as weaker. Diagnostic only.
            non_linear = (
                r_v is not None and rho_v is not None
                and abs(abs(rho_v) - abs(r_v)) >= 0.10
                and max(abs(r_v), abs(rho_v)) >= moderate_r
            )
            cell_horizons[hname] = {
                "n": n_h,
                "r": round(r_v, 4) if r_v is not None else None,
                "rho": round(rho_v, 4) if rho_v is not None else None,
                "p": round(float(p), 4) if np.isfinite(p) else None,
                "p_rho": round(float(p_rho), 4) if np.isfinite(p_rho) else None,
                "confidence": round(conf, 4) if conf is not None else None,
                "strength": strength,
                "direction": direction,
                "non_linear": bool(non_linear),
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

    return {"label": label, "per_regime": per_regime, "now_ts": now_ts}


def evaluate_gate_I(label: str, chunks: list[MarketChunk],
                     results: list[ClassificationResult],
                     k: int = 1,
                     min_n: int = 30,
                     fdr_q: float = 0.10) -> dict:
    """For each regime label, compute Pearson r/r2 of (chunk_mean_dipole_t,
    chunk_log_return_{t+k}) restricted to consecutive chunk pairs in that regime.

    Cells with n < min_n are recorded but excluded from the test (prevents
    tiny-n artifacts from passing the gate). Surviving cells go through
    Benjamini-Hochberg FDR at q=fdr_q across regimes within this venue.
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
            per_regime[regime] = {"n": n, "r": None, "r2": None, "p": None,
                                   "note": f"n<{min_n}"}
            continue
        x = md[idx]
        y = cr[[i + k for i in idx]]
        r, p, npairs = _pearsonr_with_p(x, y)
        per_regime[regime] = {
            "n": npairs,
            "r": round(r, 4) if np.isfinite(r) else None,
            "r2": round(r * r, 5) if np.isfinite(r) else None,
            "p": round(p, 4) if np.isfinite(p) else None,
            "q": None,
        }
        if np.isfinite(p):
            testable_regimes.append(regime)
            testable_pvalues.append(float(p))

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
    print(f"KR-{args.asset}: {len(kr_chunks)} chunks, baselines rv={kr_base.rv:.5f}\n")
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
    if args.sibling_cb_bins or args.sibling_kr_bins:
        sibling_asset = "ETH" if args.asset.upper() == "BTC" else (
            "BTC" if args.asset.upper() == "ETH" else None)
        sib_label = sibling_asset or "SIBLING"
        if args.sibling_cb_bins:
            sib_cb_bars = load_bars(args.sibling_cb_bins)
            sib_cb_chunks, sib_cb_results, _, _, _ = classify_venue(
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
            sib_kr_chunks, sib_kr_results, _, _, _ = classify_venue(
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
    print(f"--- GATE I (per-regime forward predictive R^2 at lag k=1) ---")
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
                print(f"    {regime:<24}  n={stat['n']:>3}  r={stat['r']:+.3f}  R^2={stat['r2']:.4f}  p={stat['p']:.3f}{qstr}{marker}")
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
            for hname in ("intraday", "daily", "weekly", "longterm"):
                h = horizons.get(hname, {})
                if h.get("r") is None and h.get("rho") is None:
                    h_strs.append(f"{hname}={h.get('strength', 'NEW')}"
                                    f"(n={h.get('n', 0)})")
                    continue
                r_v = h.get("r")
                rho_v = h.get("rho")
                # Show whichever has larger magnitude (the strength
                # driver); annotate with the other when it diverges
                # by >=0.05.
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
                h_strs.append(f"{hname}={h['strength']}/"
                                f"{tag}(n={h['n']})")
                if h.get("non_linear"):
                    non_linear_marks.append(hname)
            nl_tag = (f"  [non-linear: {','.join(non_linear_marks)}]"
                      if non_linear_marks else "")
            print(f"    {venue:<8} {regime:<22} n={cell.get('n', 0):>4}  "
                  f"{dir_word:<9}  " + "  ".join(h_strs) + nl_tag)
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
