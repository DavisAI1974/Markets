"""
regime_classifier.py — Phase 1.5 rule-based 6-class regime classifier.

Maps a MarketChunk's MarketFeatures into one of:
    EQUILIBRIUM_TWO_SIDED  - healthy two-sided trading (baseline; no edge)
    WHALE_UP / WHALE_DOWN  - one big buyer/seller; sustained one-side pressure
    HERD_UP / HERD_DOWN    - panic / FOMO; mass aligned movement
    WASH_PAIRED            - self-trades / coordinated wash; manipulation, exclude

This is the rule-based v0 per HANDOFF_PHASE1_5.md. Migrate to DPGMM auto-
taxonomy via task_meta_learner once N>=200 labeled chunks accumulate.

Calibration is asset/venue-specific. Baselines (baseline_rv, baseline_range,
baseline_kyle) should be running 24-hour medians per asset, refreshed daily.
For now we accept asset-agnostic defaults that work on the Phase 1 corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from markets_adapter import MarketFeatures


class Regime(str, Enum):
    EQUILIBRIUM_TWO_SIDED = "EQUILIBRIUM_TWO_SIDED"
    WHALE_UP = "WHALE_UP"
    WHALE_DOWN = "WHALE_DOWN"
    HERD_UP = "HERD_UP"
    HERD_DOWN = "HERD_DOWN"
    WASH_PAIRED = "WASH_PAIRED"
    DEPLETED = "DEPLETED"          # added: low-liquidity quiet
    UNKNOWN = "UNKNOWN"


@dataclass
class Baselines:
    """Per-asset reference values; ideally a rolling 24-hour median."""
    rv: float = 0.0005           # baseline realized vol (std of log returns per chunk)
    range_atr: float = 0.001     # baseline range/close
    kyle: float = 1e-3           # baseline kyle_proxy (price_move per unit volume)
    chunk_volume: float = 1.0    # baseline chunk total volume (asset-specific units)
    rv_min_for_active: float = 1e-5    # below this = depleted (no work happening)


@dataclass
class ClassificationResult:
    regime: Regime
    confidence: float            # 0-1 rough confidence based on rule strength
    notes: list[str]             # human-readable reasons for the verdict


def classify_regime(f: MarketFeatures, baselines: Baselines | None = None) -> ClassificationResult:
    """Classify a chunk's MarketFeatures into one of the universal regime states.

    Decision order matters: most-disqualifying conditions first.
    """
    b = baselines or Baselines()
    notes: list[str] = []

    # Chunk-level volume ratio vs corpus baseline (1.0 = baseline volume)
    vol_ratio = f.chunk_total_volume / max(b.chunk_volume, 1e-9)

    # 0. DEPLETED: realized vol below activity threshold OR low-vol lunch lull.
    if f.realized_vol < b.rv_min_for_active:
        notes.append(f"rv={f.realized_vol:.6f} below activity floor")
        return ClassificationResult(Regime.DEPLETED, confidence=0.9, notes=notes)
    if f.realized_vol < 0.5 * b.rv and (f.is_london_lunch or f.is_us_lunch) and vol_ratio < 0.7:
        sess = "London" if f.is_london_lunch else "NY"
        notes.append(f"{sess} lunch + rv={f.realized_vol:.5f} ({f.realized_vol/b.rv:.1%} base) + vol_ratio={vol_ratio:.2f}")
        return ClassificationResult(Regime.DEPLETED, confidence=0.8, notes=notes)
    if vol_ratio < 0.3 and f.realized_vol < 0.5 * b.rv:
        notes.append(f"vol_ratio={vol_ratio:.2f} + rv={f.realized_vol:.5f} (low activity)")
        return ClassificationResult(Regime.DEPLETED, confidence=0.7, notes=notes)

    # 1. WASH_PAIRED: anti-corr dipole + LOW vol + tight range.
    if (f.dipole_autocorr_lag1 < -0.3
        and f.realized_vol < 0.3 * b.rv
        and f.range_atr < 0.5 * b.range_atr):
        notes.append(f"acl1={f.dipole_autocorr_lag1:+.2f} + low rv + tight range")
        return ClassificationResult(Regime.WASH_PAIRED, confidence=0.8, notes=notes)

    # 2. HERD_*: high vol + above-baseline volume + dipole-aligned. Check BEFORE
    #    WHALE so a high-vol-with-acl1 event gets HERD label if vol_ratio is high
    #    (multi-actor) rather than single-actor whale.
    if (f.realized_vol > 1.8 * b.rv and vol_ratio > 1.5
        and abs(f.mean_dipole) > 0.1):
        notes.append(f"rv={f.realized_vol:.5f} ({f.realized_vol/b.rv:.1f}x base) + vol_ratio={vol_ratio:.2f} = cascade")
        regime = Regime.HERD_UP if f.mean_dipole > 0 else Regime.HERD_DOWN
        return ClassificationResult(regime, confidence=0.75, notes=notes)

    # 3. WHALE_*: sustained one-side pressure (F1 acl1) with directional dipole, OR
    #    Kyle absorption (F3) with elevated volume, OR oscillation (F2).
    is_whale = False
    whale_ev: list[str] = []
    if f.dipole_autocorr_lag1 > 0.4 and abs(f.mean_dipole) > 0.15:
        is_whale = True
        whale_ev.append(f"acl1={f.dipole_autocorr_lag1:.2f} + dipole={f.mean_dipole:+.2f} (sustained)")
    if f.kyle_proxy < 0.3 * b.kyle and vol_ratio > 1.3 and abs(f.mean_dipole) > 0.15:
        is_whale = True
        whale_ev.append(f"kyle={f.kyle_proxy:.6f} (low) + vol_ratio={vol_ratio:.2f} (absorption)")
    if (f.dipole_peak_power > 0.3 and 0.05 < f.dipole_peak_freq < 0.4
        and abs(f.mean_dipole) > 0.15):
        is_whale = True
        whale_ev.append(f"peak_pow={f.dipole_peak_power:.2f} at freq={f.dipole_peak_freq:.2f} (range-trader)")
    if is_whale:
        notes.extend(whale_ev)
        regime = Regime.WHALE_UP if f.mean_dipole > 0 else Regime.WHALE_DOWN
        return ClassificationResult(regime, confidence=0.7, notes=notes)

    # 4. EQUILIBRIUM: balanced flow, no whale/herd/wash signature.
    if abs(f.mean_dipole) < 0.25 or f.dipole_autocorr_lag1 < 0.2:
        notes.append(f"dipole={f.mean_dipole:+.2f}, acl1={f.dipole_autocorr_lag1:+.2f} (balanced)")
        return ClassificationResult(Regime.EQUILIBRIUM_TWO_SIDED, confidence=0.65, notes=notes)

    # 5. UNKNOWN fallback (now genuinely rare)
    notes.append(f"unmatched: dipole={f.mean_dipole:+.2f}, acl1={f.dipole_autocorr_lag1:+.2f}, vol_ratio={vol_ratio:.2f}, rv_ratio={f.realized_vol/b.rv:.2f}")
    return ClassificationResult(Regime.UNKNOWN, confidence=0.3, notes=notes)


def baselines_from_corpus(features_list: list[MarketFeatures]) -> Baselines:
    """Compute per-asset baselines as median of corpus (24hr recommended)."""
    import numpy as np
    if not features_list:
        return Baselines()
    rvs = [f.realized_vol for f in features_list if f.realized_vol > 0]
    rgs = [f.range_atr for f in features_list if f.range_atr > 0]
    kys = [f.kyle_proxy for f in features_list if f.kyle_proxy > 0]
    vols = [f.chunk_total_volume for f in features_list if f.chunk_total_volume > 0]
    return Baselines(
        rv=float(np.median(rvs)) if rvs else 0.0005,
        range_atr=float(np.median(rgs)) if rgs else 0.001,
        kyle=float(np.median(kys)) if kys else 1e-3,
        chunk_volume=float(np.median(vols)) if vols else 1.0,
    )


# ---------------------------------------------------------------------------
# CLI for testing on existing bins
# ---------------------------------------------------------------------------

def main():
    import argparse
    import json
    from collections import Counter
    from markets_adapter import (
        MarketBar, MarketChunker, MarketChunkEncoder, MarketChunk,
    )

    p = argparse.ArgumentParser()
    p.add_argument("--bins-path", type=str, required=True)
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--label", type=str, default="dataset")
    args = p.parse_args()

    # Load bins, aggregate to minute bars
    with open(args.bins_path) as f:
        sec_bins = {float(k): v for k, v in json.load(f).items()}
    from collections import defaultdict
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

    chunker = MarketChunker(
        max_window_size=args.chunk_max_size,
        stride=args.chunk_max_size // 2,
        min_segment=args.chunk_min_segment,
        mode="hybrid",
    )
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(args.label, bars)
    if not chunks:
        print(f"[{args.label}] no chunks produced from {len(bars)} bars")
        return

    # Extract features for each chunk
    feats = [encoder._extract(c) for c in chunks]
    # Compute baselines from this corpus (proxy for proper 24hr baselines)
    base = baselines_from_corpus(feats)
    print(f"[{args.label}] corpus baselines: rv={base.rv:.5f}, range_atr={base.range_atr:.5f}, kyle={base.kyle:.6f}")

    print(f"\n[{args.label}] {len(chunks)} chunks classified:")
    print(f"{'idx':>3}  {'window':>10}  {'rv':>8}  {'mdipole':>8}  {'acl1':>6}  {'kyle':>10}  {'regime':<24}  notes")
    counts: Counter[str] = Counter()
    for i, (c, f) in enumerate(zip(chunks, feats)):
        result = classify_regime(f, base)
        counts[result.regime.value] += 1
        print(f"{i:>3}  [{c.window_start:>3}:{c.window_end:>3}]  {c.realized_vol:>8.5f}  "
              f"{f.mean_dipole:>+8.3f}  {f.dipole_autocorr_lag1:>+6.2f}  {f.kyle_proxy:>10.6f}  "
              f"{result.regime.value:<24}  {'; '.join(result.notes[:1])}")

    print(f"\n[{args.label}] regime distribution:")
    for r, n in counts.most_common():
        pct = n / len(chunks) * 100
        print(f"  {r:<24}  {n:>3}  ({pct:>5.1f}%)")

    print(f"\n[{args.label}] gate G evaluation (>=4 distinct classes, modal not >70%):")
    n_classes = len(counts)
    modal_pct = max(counts.values()) / len(chunks) * 100
    gate_g = n_classes >= 4 and modal_pct < 70
    print(f"  n_distinct_classes: {n_classes}")
    print(f"  modal class share : {modal_pct:.1f}%")
    print(f"  GATE G: {'PASS' if gate_g else 'FAIL'}")


if __name__ == "__main__":
    main()
