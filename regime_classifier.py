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
    WHALE_NASCENT_UP = "WHALE_NASCENT_UP"      # directional pressure, moderate
    WHALE_NASCENT_DOWN = "WHALE_NASCENT_DOWN"  # persistence, sub-WHALE evidence
    HERD_UP = "HERD_UP"
    HERD_DOWN = "HERD_DOWN"
    WASH_PAIRED = "WASH_PAIRED"
    WASH_HAWKES = "WASH_HAWKES"    # bivariate Hawkes wash detector (5.1)
    DEPLETED = "DEPLETED"          # low-liquidity quiet
    UNKNOWN = "UNKNOWN"            # genuine fallback (now rare)


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
    vpin: float = 0.0            # informed-flow toxicity, [0,1]; high = imminent move predicted
    vpin_multiplier: float = 1.0 # confidence boost/de-rate from VPIN (HERD/WHALE only)
    cross_asset_multiplier: float = 1.0  # F7: 1.4 if sibling asset same direction, 0.6 if opposite, 1.0 if neutral/no overlap
    event_multiplier: float = 1.0   # F8: dampener around scheduled events / weekend sessions (<=1.0)
    hurst: float = 0.5              # F9: Hurst exponent (DFA-1) on chunk log returns; 0.5 = no signal
    hurst_label: str = ""           # F9: "trending" | "reverting" | "random" | "" (insufficient data)
    hawkes_multiplier: float = 1.0  # F10: 1.15 if η>=p75 of directional cells, 0.85 if η<=p25, 1.0 otherwise

    @property
    def adjusted_confidence(self) -> float:
        """Confidence × cross-venue × vpin × cross-asset × event × hawkes,
        capped at [0, 1]."""
        return max(0.0, min(1.0,
            self.confidence
            * self.cross_venue_multiplier
            * self.vpin_multiplier
            * self.cross_asset_multiplier
            * self.event_multiplier
            * self.hawkes_multiplier))


# F10 Hawkes multiplier defaults (literature priors). Production backend
# overrides via hawkes_eta_calibration.json once enough directional chunks
# accumulate per (asset, venue).
HAWKES_DEFAULT_ELEVATED = 0.45
HAWKES_DEFAULT_DIFFUSE = 0.20
HAWKES_BOOST = 1.15
HAWKES_DAMPEN = 0.85


def _hawkes_multiplier_for_regime(regime: Regime, eta: float, n_events: int,
                                     elevated: float = HAWKES_DEFAULT_ELEVATED,
                                     diffuse: float = HAWKES_DEFAULT_DIFFUSE,
                                     ) -> tuple[float, str]:
    """Return (multiplier, note) for a chunk's Hawkes branching ratio η.

    Like VPIN, only directional regimes (HERD_*, WHALE_*, NASCENT_*) are
    affected — η on EQUILIBRIUM/DEPLETED/UNKNOWN is informational but
    doesn't translate to confidence (no signal to amplify). WASH_*
    regimes have η high by definition; skip the multiplier so the
    classifier's wash-rule confidence isn't double-counted.
    """
    if n_events < 8:
        return 1.0, ""
    name = regime.value
    is_directional = (
        name.startswith("WHALE_") or name.startswith("HERD_")
        or name.startswith("WHALE_NASCENT_")
    )
    if not is_directional:
        return 1.0, ""
    if eta >= elevated:
        return HAWKES_BOOST, (f"hawkes_eta={eta:.2f} >= p75={elevated:.2f} "
                                f"(clustered cascade; +{int((HAWKES_BOOST-1)*100)}% confidence)")
    if eta <= diffuse:
        return HAWKES_DAMPEN, (f"hawkes_eta={eta:.2f} <= p25={diffuse:.2f} "
                                f"(scattered/Poisson; -{int((1-HAWKES_DAMPEN)*100)}% confidence)")
    return 1.0, f"hawkes_eta={eta:.2f}"


def _vpin_multiplier_for_regime(regime: Regime, vpin: float, vpin_n: int,
                                  elevated: float = 0.30,
                                  diffuse: float = 0.08) -> tuple[float, str]:
    """Return (multiplier, note) for a chunk's VPIN given its regime.

    elevated/diffuse: thresholds for "informed flow concentrated" vs
    "retail/diffuse". Defaults are literature priors; the production
    backend passes per-(asset,venue) p75/p25 from vpin_calibration.json.

    Boosts/de-rates only directional regimes (HERD_*, WHALE_*, NASCENT_*).
    Skipped for EQUILIBRIUM/DEPLETED/UNKNOWN. WASH_PAIRED with high VPIN
    is flagged as suspicious — pair-cancel patterns shouldn't carry
    informed flow.
    """
    if vpin_n < 3:
        return 1.0, ""
    name = regime.value
    is_directional = (
        name.startswith("WHALE_") or name.startswith("HERD_")
        or name.startswith("WHALE_NASCENT_")
    )
    if is_directional:
        if vpin >= elevated:
            return 1.15, (f"vpin={vpin:.2f} >= p75={elevated:.2f} "
                          f"(informed flow concentrated; +15% confidence)")
        if vpin <= diffuse:
            return 0.85, (f"vpin={vpin:.2f} <= p25={diffuse:.2f} "
                          f"(diffuse/retail flow; -15% confidence)")
        return 1.0, f"vpin={vpin:.2f}"
    if name in ("WASH_PAIRED", "WASH_HAWKES") and vpin >= elevated:
        # WASH should be flow-neutral; high VPIN here suggests one side
        # is actually informed and we mislabeled. De-rate.
        return 0.7, (f"vpin={vpin:.2f} >= p75={elevated:.2f} on {name} "
                     f"(suspicious; -30%)")
    return 1.0, ""


# F9 Hurst label thresholds. Hardcoded as policy this session; recalibrate
# once per-cell hurst distributions accumulate (Pass-7 evaluator territory).
HURST_TRENDING = 0.55
HURST_REVERTING = 0.45
HURST_MIN_RETURNS_FOR_LABEL = 8  # mirrors hurst.HURST_MIN_RETURNS

# WASH_HAWKES override thresholds. Wash signature at bar resolution:
# - Both per-side η elevated (each side's events cluster in time).
# - Combined η also elevated (cross-excitation contributes too).
# - Balanced volume (|mean_dipole| small).
# Only EQUILIBRIUM_TWO_SIDED is overridden — directional regimes already
# encode a side bias and shouldn't be relabeled as wash.
#
# Pass-8 finding: with WASH_HAWKES_BOTH_SIDES_MIN=0.30, the WASH_HAWKES
# × η-high subset showed a spurious momentum bias (ETH n=18 r=+0.43
# p=0.06; BTC n=291 r=+0.106 p=0.069). Tightening to 0.35 excludes the
# borderline-clustered high-η chunks that were carrying real order flow.
WASH_HAWKES_BOTH_SIDES_MIN = 0.35   # min(η_buy, η_sell) must clear this
WASH_HAWKES_COMBINED_MIN = 0.40     # combined η must clear this
WASH_HAWKES_DIPOLE_MAX = 0.20       # |mean_dipole| must stay below this


def _hurst_label_for(f: MarketFeatures) -> str:
    h = float(getattr(f, "hurst", 0.5) or 0.5)
    n = int(getattr(f, "hurst_n_returns", 0) or 0)
    if n < HURST_MIN_RETURNS_FOR_LABEL:
        return ""
    if h >= HURST_TRENDING:
        return "trending"
    if h <= HURST_REVERTING:
        return "reverting"
    return "random"


def classify_regime(f: MarketFeatures, baselines: Baselines | None = None,
                      *,
                      vpin_elevated: float = 0.30,
                      vpin_diffuse: float = 0.08,
                      hawkes_elevated: float = HAWKES_DEFAULT_ELEVATED,
                      hawkes_diffuse: float = HAWKES_DEFAULT_DIFFUSE,
                      ) -> ClassificationResult:
    """Classify a chunk's MarketFeatures and attach VPIN + Hawkes
    confidence multipliers on directional regimes.

    vpin_elevated / vpin_diffuse: VPIN thresholds. Backend passes per-
    (asset, venue) p75 / p25 from vpin_calibration.json.
    hawkes_elevated / hawkes_diffuse: Hawkes-η thresholds. Backend passes
    per-(asset, venue) p75 / p25 from hawkes_eta_calibration.json,
    computed over directional chunks only (Pass-7 finding: η is regime-
    dependent so venue-wide thresholds would be uninformative).
    Both default to literature priors when no calibration is loaded.
    """
    result = _classify_regime_raw(f, baselines)
    result.vpin = float(getattr(f, "vpin", 0.0) or 0.0)
    vpin_n = int(getattr(f, "vpin_n_buckets", 0) or 0)
    mult, note = _vpin_multiplier_for_regime(
        result.regime, result.vpin, vpin_n,
        elevated=vpin_elevated, diffuse=vpin_diffuse)
    result.vpin_multiplier = float(mult)
    if note:
        result.notes.append(note)

    # F10 Hawkes branching-ratio multiplier on directional regimes.
    eta_val = float(getattr(f, "hawkes_eta", 0.0) or 0.0)
    eta_n = int(getattr(f, "hawkes_n_events", 0) or 0)
    h_mult, h_note = _hawkes_multiplier_for_regime(
        result.regime, eta_val, eta_n,
        elevated=hawkes_elevated, diffuse=hawkes_diffuse)
    result.hawkes_multiplier = float(h_mult)
    if h_note:
        result.notes.append(h_note)
    # F9 Hurst orthogonal label (does NOT modify confidence; layered
    # annotation that downstream consumers can use for sub-cell slicing).
    result.hurst = float(getattr(f, "hurst", 0.5) or 0.5)
    result.hurst_label = _hurst_label_for(f)
    if result.hurst_label:
        result.notes.append(f"hurst={result.hurst:.2f} ({result.hurst_label})")

    # 5.1 WASH_HAWKES override: bivariate Hawkes wash detector. Promotes
    # EQUILIBRIUM_TWO_SIDED chunks with bilateral self-excitation +
    # balanced volume to WASH_HAWKES so the playbook can flag them as
    # likely wash flow. Doesn't touch directional regimes — they already
    # encode a side bias that's incompatible with wash.
    eta_all = float(getattr(f, "hawkes_eta", 0.0) or 0.0)
    eta_buy = float(getattr(f, "hawkes_eta_buy", 0.0) or 0.0)
    eta_sell = float(getattr(f, "hawkes_eta_sell", 0.0) or 0.0)
    if (result.regime == Regime.EQUILIBRIUM_TWO_SIDED
            and eta_all >= WASH_HAWKES_COMBINED_MIN
            and min(eta_buy, eta_sell) >= WASH_HAWKES_BOTH_SIDES_MIN
            and abs(f.mean_dipole) < WASH_HAWKES_DIPOLE_MAX):
        result.regime = Regime.WASH_HAWKES
        result.notes.append(
            f"hawkes_wash: η_all={eta_all:.2f} η_buy={eta_buy:.2f} "
            f"η_sell={eta_sell:.2f} dipole={f.mean_dipole:+.2f} "
            f"(bilateral self-excitation + balanced volume)")
    return result


def _classify_regime_raw(f: MarketFeatures, baselines: Baselines | None = None) -> ClassificationResult:
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

    # 4.5 WHALE_NASCENT: directional dipole (>=0.25) + persistence (acl1>=0.2)
    #     but didn't trip full WHALE thresholds (acl1>=0.4+|dipole|>=0.15, OR
    #     Kyle absorption, OR oscillation). Mechanistically: a trend that has
    #     started forming but hasn't yet shown sustained one-side pressure.
    #     Hypothesis (to be confirmed at higher n): NASCENT continues, full
    #     WHALE fades. n=44 at 30d ETH-KR shows r=+0.21 momentum suggestive.
    notes.append(f"borderline whale: dipole={f.mean_dipole:+.2f}, acl1={f.dipole_autocorr_lag1:+.2f}, vol_ratio={vol_ratio:.2f}")
    regime = Regime.WHALE_NASCENT_UP if f.mean_dipole > 0 else Regime.WHALE_NASCENT_DOWN
    return ClassificationResult(regime, confidence=0.55, notes=notes)


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
# F7: cross-asset confidence multiplier (BTC <-> ETH directional agreement)
# ---------------------------------------------------------------------------

# Cross-asset agreement is a *direction* match (UP / DOWN), not a regime-label
# match. ETH WHALE_UP and BTC HERD_UP both confirm UP. Multiplier band is
# tighter than F6 because cross-asset is a weaker prior than cross-venue
# (different asset, different liquidity profile).
CROSS_ASSET_AGREE = 1.4
CROSS_ASSET_DISAGREE = 0.6


def apply_cross_asset_multiplier_uniform(
    results: list[ClassificationResult],
    sibling_direction: str | None,
) -> None:
    """Live-backend variant: set cross_asset_multiplier on each result using
    a single sibling-asset direction (UP/DOWN/None) instead of a minute-
    level stream. The live backend tracks one 'current_status' per
    (asset, venue), so its cross-asset lookup is naturally uniform.
    """
    for r in results:
        primary_dir = _direction(r.regime.value)
        if primary_dir is None or sibling_direction is None:
            r.cross_asset_multiplier = 1.0
        elif primary_dir == sibling_direction:
            r.cross_asset_multiplier = CROSS_ASSET_AGREE
        else:
            r.cross_asset_multiplier = CROSS_ASSET_DISAGREE


def apply_cross_asset_multiplier(
    primary_results: list[ClassificationResult],
    primary_chunks: list,
    primary_bars: list,
    sibling_minute_regime: dict[float, str],
) -> None:
    """Mutate primary_results in place: set cross_asset_multiplier per result.

    For each chunk on the primary asset, look up the most-common regime label
    observed on the SIBLING asset across the chunk's wall-clock range. Use
    direction agreement (UP/DOWN) — not exact regime match — to set the
    multiplier:
      CROSS_ASSET_AGREE    if both directions match
      CROSS_ASSET_DISAGREE if directions oppose
      1.0                  if either side is non-directional
                           (EQUILIBRIUM/DEPLETED/WASH/UNKNOWN) or no overlap
    """
    from collections import Counter
    for c, r in zip(primary_chunks, primary_results):
        primary_dir = _direction(r.regime.value)
        if primary_dir is None:
            r.cross_asset_multiplier = 1.0
            continue
        sibling_labels: list[str] = []
        for bar_idx in range(c.window_start, c.window_end):
            if 0 <= bar_idx < len(primary_bars):
                ts = primary_bars[bar_idx].ts
                if ts in sibling_minute_regime:
                    sibling_labels.append(sibling_minute_regime[ts])
        if not sibling_labels:
            r.cross_asset_multiplier = 1.0
            continue
        most_common = Counter(sibling_labels).most_common(1)[0][0]
        sibling_dir = _direction(most_common)
        if sibling_dir is None:
            r.cross_asset_multiplier = 1.0
        elif sibling_dir == primary_dir:
            r.cross_asset_multiplier = CROSS_ASSET_AGREE
        else:
            r.cross_asset_multiplier = CROSS_ASSET_DISAGREE


# ---------------------------------------------------------------------------
# F8: scheduled-event proximity + weekend confidence dampener
# ---------------------------------------------------------------------------

def apply_event_multiplier(
    results: list[ClassificationResult],
    chunks: list,
    bars: list,
    calendar,  # event_calendar.EventCalendar | None
) -> None:
    """Mutate results in place: set event_multiplier per chunk based on the
    chunk's wall-clock midpoint timestamp.

    Reads the chunk's last bar timestamp (most recent moment in the chunk)
    and asks event_calendar.event_multiplier_for_ts() for the dampener:
      - 0.7 when within ±30 min of a scheduled FOMC/CPI/etc. event
      - 0.85 when within ±60 min OR on a weekend
      - 1.0 otherwise

    No-op when calendar is None.
    """
    if calendar is None:
        return
    # Local import to avoid circular dep at module load
    from event_calendar import event_multiplier_for_ts
    for c, r in zip(chunks, results):
        if not c.bars:
            continue
        ts = float(c.bars[-1].ts) if hasattr(c.bars[-1], 'ts') else None
        if ts is None and c.window_end - 1 < len(bars):
            ts = float(bars[c.window_end - 1].ts)
        if ts is None:
            continue
        mult, note = event_multiplier_for_ts(ts, calendar)
        r.event_multiplier = float(mult)
        if note:
            r.notes.append(note)


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
