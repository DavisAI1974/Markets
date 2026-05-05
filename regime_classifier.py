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
    cross_venue_multiplier: float = 1.0   # F6: 1.5 if other venue agrees, 0.5 if disagrees, 1.0 if unknown
    herd_persistence: int = 1    # 1 = isolated chunk; N>=2 = part of N-chunk consecutive same-HERD run
    herd_rescued: bool = False   # set True when a borderline EQUILIBRIUM chunk was reclassified by apply_herd_borderline_rescue

    @property
    def adjusted_confidence(self) -> float:
        """Confidence × cross-venue multiplier, capped at [0, 1]."""
        return max(0.0, min(1.0, self.confidence * self.cross_venue_multiplier))


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
# Per-session baselines: bucket chunks by session_phase before averaging
# ---------------------------------------------------------------------------

def _session_phase_of(f: MarketFeatures) -> str:
    """Discrete session-phase label based on UTC hour and weekday flags."""
    h = f.hour_utc
    if f.day_of_week >= 5:
        return "weekend"
    if f.is_london_lunch:
        return "london_lunch"
    if f.is_us_lunch:
        return "us_lunch"
    if f.is_us_market_hours and not f.is_us_lunch:
        return "us_active"
    if 7.0 <= h < 11.0 or 12.0 <= h < 13.5:
        return "london_active"  # London hrs ex-lunch and pre-NY
    if 0.0 <= h < 7.0:
        return "asia_overnight"
    return "off_hours"


def baselines_per_session(features_list: list[MarketFeatures]) -> dict[str, Baselines]:
    """Compute Baselines bucketed by session_phase.

    Each session_phase gets its own median of (rv, range, kyle, volume).
    Falls back to the global baseline for phases with too few samples (<3).
    """
    import numpy as np
    by_phase: dict[str, list[MarketFeatures]] = {}
    for f in features_list:
        phase = _session_phase_of(f)
        by_phase.setdefault(phase, []).append(f)
    global_base = baselines_from_corpus(features_list)
    out: dict[str, Baselines] = {"_global": global_base}
    for phase, items in by_phase.items():
        if len(items) < 3:
            out[phase] = global_base
            continue
        rvs = [f.realized_vol for f in items if f.realized_vol > 0]
        rgs = [f.range_atr for f in items if f.range_atr > 0]
        kys = [f.kyle_proxy for f in items if f.kyle_proxy > 0]
        vols = [f.chunk_total_volume for f in items if f.chunk_total_volume > 0]
        out[phase] = Baselines(
            rv=float(np.median(rvs)) if rvs else global_base.rv,
            range_atr=float(np.median(rgs)) if rgs else global_base.range_atr,
            kyle=float(np.median(kys)) if kys else global_base.kyle,
            chunk_volume=float(np.median(vols)) if vols else global_base.chunk_volume,
        )
    return out


def classify_with_session_baselines(f: MarketFeatures,
                                      session_baselines: dict[str, Baselines]
                                      ) -> ClassificationResult:
    """Classify using the baseline appropriate to f's session phase."""
    phase = _session_phase_of(f)
    base = session_baselines.get(phase, session_baselines.get("_global", Baselines()))
    result = classify_regime(f, base)
    result.notes.insert(0, f"[session={phase}, baseline rv={base.rv:.5f}]")
    return result


# ---------------------------------------------------------------------------
# HERD persistence: annotate consecutive same-HERD chunk runs.
#
# The "slow build" signature of HERD activity (multiple actors gradually
# piling in over multiple chunks) is structurally distinct from WHALE
# activity (single-actor impulse, isolated chunks). This pass surfaces
# multi-chunk HERD runs without changing the classification rules.
# ---------------------------------------------------------------------------

_HERD_REGIME_VALUES = frozenset({Regime.HERD_UP.value, Regime.HERD_DOWN.value})


def apply_herd_persistence(results: list[ClassificationResult]) -> list[tuple[int, int, str]]:
    """Mutate results in place: set herd_persistence = N for chunks in an
    N-chunk consecutive run of the same HERD regime.

    HERD_UP and HERD_DOWN runs are tracked independently. Any non-HERD
    chunk (or a switch from HERD_UP to HERD_DOWN) breaks the run.

    Returns a list of (start_idx, run_length, regime_value) for runs
    with length >= 2 (sustained HERD events).
    """
    sustained: list[tuple[int, int, str]] = []
    n = len(results)
    i = 0
    while i < n:
        if results[i].regime.value not in _HERD_REGIME_VALUES:
            i += 1
            continue
        regime_val = results[i].regime.value
        j = i + 1
        while j < n and results[j].regime.value == regime_val:
            j += 1
        run_len = j - i
        for k in range(i, j):
            results[k].herd_persistence = run_len
            if run_len >= 2:
                results[k].notes.append(
                    f"sustained {run_len}-chunk HERD ({k - i + 1}/{run_len})")
        if run_len >= 2:
            sustained.append((i, run_len, regime_val))
        i = j
    return sustained


def apply_herd_borderline_rescue(
    results: list[ClassificationResult],
    features: list[MarketFeatures],
    baselines: Baselines,
) -> int:
    """Reclassify borderline EQUILIBRIUM chunks adjacent to a confirmed HERD
    run (persistence>=2) as HERD if they meet RELAXED thresholds:

      rv_ratio    > 1.4  (vs the strict 1.8 in classify_regime)
      vol_ratio   > 1.2  (vs the strict 1.5)
      |dipole|    > 0.08 (vs the strict 0.10)
      direction matches the adjacent HERD run

    Returns count of chunks rescued. Mutates results + sets herd_rescued=True.

    NOTE: This is borderline-threshold tuning. Do not enable by default
    until n>=30 HERD chunks accumulate; it can fire spuriously on small
    samples. Call apply_herd_persistence again after rescue to recompute
    persistence counts including the rescued chunks.
    """
    rescued = 0
    n = len(results)
    if n != len(features):
        raise ValueError("results and features must align 1:1 with chunks")

    # Build set of confirmed HERD-run boundaries (start, end_exclusive, regime)
    runs: list[tuple[int, int, str]] = []
    i = 0
    while i < n:
        if (results[i].regime.value in _HERD_REGIME_VALUES
                and results[i].herd_persistence >= 2):
            j = i + 1
            while (j < n
                   and results[j].regime.value == results[i].regime.value
                   and results[j].herd_persistence >= 2):
                j += 1
            runs.append((i, j, results[i].regime.value))
            i = j
        else:
            i += 1

    candidates: list[tuple[int, str]] = []  # (idx, target_regime)
    for start, end, regime in runs:
        if start - 1 >= 0:
            candidates.append((start - 1, regime))
        if end < n:
            candidates.append((end, regime))

    for idx, target_regime in candidates:
        r = results[idx]
        if r.regime != Regime.EQUILIBRIUM_TWO_SIDED:
            continue
        f = features[idx]
        rv_ratio = f.realized_vol / max(baselines.rv, 1e-9)
        vol_ratio = f.chunk_total_volume / max(baselines.chunk_volume, 1e-9)
        dipole_dir = +1 if target_regime == Regime.HERD_UP.value else -1
        if (rv_ratio > 1.4
                and vol_ratio > 1.2
                and abs(f.mean_dipole) > 0.08
                and (f.mean_dipole > 0) == (dipole_dir > 0)):
            r.regime = Regime.HERD_UP if target_regime == Regime.HERD_UP.value else Regime.HERD_DOWN
            r.herd_rescued = True
            r.notes.append(
                f"rescued: rv_ratio={rv_ratio:.2f} vol_ratio={vol_ratio:.2f} "
                f"|dipole|={abs(f.mean_dipole):.3f} adjacent to {target_regime} run")
            rescued += 1
    return rescued


# ---------------------------------------------------------------------------
# WHALE -> HERD cascade detection (notification-worthy events).
#
# Pattern: a WHALE chunk (single-actor sustained pressure) that flows
# directly into a HERD chunk (multi-actor cascade) in the SAME direction
# without an intervening EQUILIBRIUM/DEPLETED gap. This is the canonical
# "whale trips the herd" sequence: one big seller pushes, the herd piles
# on. Empirically the WHALE and HERD chunks often overlap (chunker stride
# = max_window/2) so they are "happening at the same time" in the
# wall-clock sense.
#
# These events warrant immediate notification because:
#   1. high directional conviction (two independent signal types align)
#   2. typically the start of a multi-percent move
#   3. the playbook differs from either alone: "get out of the way of the
#      whale + fade the herd overshoot once the cascade exhausts"
# ---------------------------------------------------------------------------


def _direction(regime_value: str) -> str | None:
    if regime_value.endswith("_UP"):
        return "UP"
    if regime_value.endswith("_DOWN"):
        return "DOWN"
    return None


def detect_whale_to_herd_cascades(
    results: list[ClassificationResult],
) -> list[dict]:
    """Detect single-venue WHALE -> HERD direct transitions in the same
    direction with no intervening non-WHALE-non-HERD chunk.

    Returns a list of event dicts:
      {"type": "WHALE_TO_HERD_CASCADE",
       "direction": "UP" | "DOWN",
       "whale_idx": int, "herd_start_idx": int,
       "herd_run_length": int,
       "summary": "..."}
    """
    events: list[dict] = []
    for i in range(len(results) - 1):
        cur = results[i]
        nxt = results[i + 1]
        if "WHALE" not in cur.regime.value or "HERD" not in nxt.regime.value:
            continue
        cur_dir = _direction(cur.regime.value)
        nxt_dir = _direction(nxt.regime.value)
        if cur_dir is None or cur_dir != nxt_dir:
            continue
        events.append({
            "type": "WHALE_TO_HERD_CASCADE",
            "direction": cur_dir,
            "whale_idx": i,
            "herd_start_idx": i + 1,
            "herd_run_length": nxt.herd_persistence,
            "summary": (
                f"WHALE_{cur_dir} at chunk {i} flows directly into "
                f"HERD_{nxt_dir} run of {nxt.herd_persistence} chunk(s) "
                f"starting at chunk {i + 1}"
            ),
        })
    return events


def detect_cross_venue_whale_herd_simultaneity(
    primary_results: list[ClassificationResult],
    primary_chunks: list,
    primary_bars: list,
    other_minute_regime: dict[float, str],
    primary_label: str = "primary",
    other_label: str = "other",
) -> list[dict]:
    """Detect chunks where the primary venue is WHALE and the other venue
    is HERD in the SAME direction over the chunk's wall-clock window
    (or vice versa).

    Returns events dicts:
      {"type": "CROSS_VENUE_WHALE_HERD_SIMULTANEITY",
       "primary_regime": "WHALE_DOWN", "other_regime": "HERD_DOWN",
       "primary_chunk_idx": int, "direction": "UP"|"DOWN",
       "primary_label": ..., "other_label": ...,
       "summary": "..."}
    """
    from collections import Counter
    events: list[dict] = []
    for idx, (c, r) in enumerate(zip(primary_chunks, primary_results)):
        primary_dir = _direction(r.regime.value)
        if primary_dir is None:
            continue
        primary_kind = ("WHALE" if "WHALE" in r.regime.value
                         else ("HERD" if "HERD" in r.regime.value else None))
        if primary_kind is None:
            continue
        other_labels: list[str] = []
        for bar_idx in range(c.window_start, c.window_end):
            if 0 <= bar_idx < len(primary_bars):
                ts = primary_bars[bar_idx].ts
                if ts in other_minute_regime:
                    other_labels.append(other_minute_regime[ts])
        if not other_labels:
            continue
        most_common = Counter(other_labels).most_common(1)[0][0]
        other_dir = _direction(most_common)
        other_kind = ("WHALE" if "WHALE" in most_common
                       else ("HERD" if "HERD" in most_common else None))
        if other_dir != primary_dir or other_kind is None:
            continue
        # WHALE+HERD or HERD+WHALE in same direction
        if {primary_kind, other_kind} == {"WHALE", "HERD"}:
            events.append({
                "type": "CROSS_VENUE_WHALE_HERD_SIMULTANEITY",
                "primary_regime": r.regime.value,
                "other_regime": most_common,
                "primary_chunk_idx": idx,
                "direction": primary_dir,
                "primary_label": primary_label,
                "other_label": other_label,
                "summary": (
                    f"{primary_label} {r.regime.value} at chunk {idx} "
                    f"co-occurs with {other_label} {most_common} over "
                    f"the same wall-clock window"
                ),
            })
    return events


# ---------------------------------------------------------------------------
# F6: cross-venue confidence multiplier
# ---------------------------------------------------------------------------

def apply_cross_venue_multiplier(
    primary_results: list[ClassificationResult],
    primary_chunks: list,
    primary_bars: list,
    other_minute_regime: dict[float, str],
) -> None:
    """Mutate primary_results in place: set cross_venue_multiplier per result.

    For each chunk on the primary venue, look up the most-common regime
    label observed on the other venue across the chunk's wall-clock range.
    Multiplier:
      1.5 if same regime    (both venues confirm)
      0.5 if different      (single-venue event)
      1.0 if no overlap     (other venue had no data)
    """
    from collections import Counter
    for c, r in zip(primary_chunks, primary_results):
        # Collect other-venue regime labels for the wall-clock minutes covered
        other_labels: list[str] = []
        for bar_idx in range(c.window_start, c.window_end):
            if 0 <= bar_idx < len(primary_bars):
                ts = primary_bars[bar_idx].ts
                if ts in other_minute_regime:
                    other_labels.append(other_minute_regime[ts])
        if not other_labels:
            r.cross_venue_multiplier = 1.0
            continue
        most_common = Counter(other_labels).most_common(1)[0][0]
        if most_common == r.regime.value:
            r.cross_venue_multiplier = 1.5
        else:
            r.cross_venue_multiplier = 0.5


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
