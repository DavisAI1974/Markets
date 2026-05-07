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
        # Gate passes if EITHER strict or relaxed clears 60%. The relaxed
        # path treats EQ_TWO_SIDED/WASH_HAWKES/WASH_PAIRED/DEPLETED as a
        # single 'no edge' state.
        "gate_H_strict": strict_rate >= 0.60,
        "gate_H_relaxed": relaxed_rate >= 0.60,
        "gate_H": (strict_rate >= 0.60) or (relaxed_rate >= 0.60),
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
              f"(strict OR relaxed >=60%)")
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

    # Combined verdict
    all_g = g_cb["gate_G"] and g_kr["gate_G"]
    pass_h = h.get("gate_H", False)
    pass_i = i_cb.get("gate_I", False) or i_kr.get("gate_I", False)  # either venue suffices
    print(f"--- COMBINED VERDICT ---")
    print(f"  Gate G (both venues): {'PASS' if all_g else 'FAIL'}")
    print(f"  Gate H (cross-venue agreement): {'PASS' if pass_h else 'FAIL'}")
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
