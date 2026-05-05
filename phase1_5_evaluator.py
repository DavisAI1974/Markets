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
)


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
        bars.append(MarketBar(
            ts=float(m_ts),
            close=float(mids[-1]), open_=float(mids[0]),
            high=float(max(mids)), low=float(min(mids)),
            volume=float(sum(b["buy"] + b["sell"] for _, b in members)),
            buy_vol=float(sum(b["buy"] for _, b in members)),
            sell_vol=float(sum(b["sell"] for _, b in members)),
        ))
    return bars


def classify_venue(bars: list[MarketBar], label: str,
                    chunk_max: int = 30, chunk_min: int = 10,
                    multi_signal_pelt: bool = False,
                    use_session_baselines: bool = False,
                    herd_rescue: bool = False,
                    ) -> tuple[list[MarketChunk], list[ClassificationResult], Baselines, dict]:
    chunker = MarketChunker(max_window_size=chunk_max, stride=chunk_max // 2,
                             min_segment=chunk_min, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(label, bars, multi_signal=multi_signal_pelt)
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    if use_session_baselines:
        session_base = baselines_per_session(feats)
        results = [classify_with_session_baselines(f, session_base) for f in feats]
    else:
        session_base = {"_global": base}
        results = [classify_regime(f, base) for f in feats]
    apply_herd_persistence(results)
    if herd_rescue:
        apply_herd_borderline_rescue(results, feats, base)
        apply_herd_persistence(results)  # recompute including rescued chunks
    return chunks, results, base, session_base


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


def evaluate_gate_H(cb_minute: dict[float, str], kr_minute: dict[float, str]) -> dict:
    common = sorted(set(cb_minute) & set(kr_minute))
    if len(common) < 30:
        return {"gate_H": False, "n_overlap": len(common), "reason": "too few overlapping minutes"}
    agreements = sum(1 for m in common if cb_minute[m] == kr_minute[m])
    rate = agreements / len(common)
    # Confusion matrix: how often does each (CB, KR) pair occur?
    confusion: Counter[tuple[str, str]] = Counter()
    for m in common:
        confusion[(cb_minute[m], kr_minute[m])] += 1
    return {
        "n_overlap_minutes": len(common),
        "n_agreements": agreements,
        "agreement_rate": rate,
        "confusion_top_5": confusion.most_common(5),
        "gate_H": rate >= 0.60,
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


def evaluate_gate_I(label: str, chunks: list[MarketChunk],
                     results: list[ClassificationResult],
                     k: int = 1) -> dict:
    """For each regime label, compute Pearson r/r2 of (chunk_mean_dipole_t,
    chunk_log_return_{t+k}) restricted to consecutive chunk pairs in that regime.
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
    for regime in set(labels):
        # Indices where chunk t is this regime AND chunk t+k exists
        idx = [i for i in range(len(chunks) - k) if labels[i] == regime]
        n = len(idx)
        if n < 3:
            per_regime[regime] = {"n": n, "r": None, "r2": None, "p": None,
                                   "note": "insufficient chunks"}
            continue
        x = md[idx]
        y = cr[[i + k for i in idx]]
        r, p, npairs = _pearsonr_with_p(x, y)
        per_regime[regime] = {
            "n": npairs,
            "r": round(r, 4) if np.isfinite(r) else None,
            "r2": round(r * r, 5) if np.isfinite(r) else None,
            "p": round(p, 4) if np.isfinite(p) else None,
        }
    # Gate I: pass if any regime has r2 > 0.05 with p < 0.10 AND we have >=2 regimes evaluated
    evaluable = {k: v for k, v in per_regime.items() if v.get("r") is not None}
    has_signal = any(
        (v["r2"] or 0) > 0.05 and (v["p"] or 1) < 0.10
        for v in evaluable.values()
    )
    n_evaluable = len(evaluable)
    return {
        "label": label,
        "lag_k": k,
        "n_evaluable_regimes": n_evaluable,
        "per_regime": per_regime,
        "has_at_least_one_significant_regime": has_signal,
        "gate_I": has_signal and n_evaluable >= 2,
    }


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
    args = p.parse_args()

    print(f"=== Phase 1.5 Evaluation: {args.asset} ===\n")

    cb_bars = load_bars(args.cb_bins)
    kr_bars = load_bars(args.kr_bins)
    print(f"Coinbase bars: {len(cb_bars)}, Kraken bars: {len(kr_bars)}\n")

    cb_chunks, cb_results, cb_base, cb_session = classify_venue(
        cb_bars, f"CB-{args.asset}", args.chunk_max_size, args.chunk_min_segment,
        multi_signal_pelt=args.multi_signal_pelt,
        use_session_baselines=args.session_baselines,
        herd_rescue=args.herd_rescue,
    )
    kr_chunks, kr_results, kr_base, kr_session = classify_venue(
        kr_bars, f"KR-{args.asset}", args.chunk_max_size, args.chunk_min_segment,
        multi_signal_pelt=args.multi_signal_pelt,
        use_session_baselines=args.session_baselines,
        herd_rescue=args.herd_rescue,
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
        print(f"  Agreements: {h['n_agreements']} ({h['agreement_rate']:.1%})")
        print(f"  Top regime pairs (CB, KR):")
        for (cb_r, kr_r), n in h["confusion_top_5"]:
            tag = "AGREE" if cb_r == kr_r else "disagree"
            print(f"    {cb_r:<22} | {kr_r:<22} | {n:>4} ({tag})")
        print(f"  -> {'PASS' if h['gate_H'] else 'FAIL'} (need >=60%)")
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
                print(f"    {regime:<24}  n={stat['n']:>2}  insufficient data")
            else:
                marker = " <- significant" if (stat["r2"] or 0) > 0.05 and (stat["p"] or 1) < 0.10 else ""
                print(f"    {regime:<24}  n={stat['n']:>2}  r={stat['r']:+.3f}  R^2={stat['r2']:.4f}  p={stat['p']:.3f}{marker}")
        print(f"    -> {'PASS' if ig['gate_I'] else 'FAIL'} (need >=1 significant regime, >=2 evaluable)")
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
