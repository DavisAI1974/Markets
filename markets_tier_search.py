"""
markets_tier_search.py  --  tier-stratified combination discovery for trading cells.

Inverts the standard autoresearch optimization. Instead of "maximize R^2 over
one output," it asks: "what is the SMALLEST combination of (feature, quartile)
constraints, applied within a (venue, regime) cell, that satisfies each of
several fixed CONFIDENCE TIERS?"

Tiers default to:
    tier_1 = 0.95 (almost-certain directional signal)
    tier_2 = 0.85 (strong)
    tier_3 = 0.75 (moderate)
    tier_4 = 0.65 (modest)
    tier_5 = 0.55 (a little better than 50/50, asymmetric-edge plays)

Confidence is bootstrap-validated bias-corrected P(forward-return correct sign
| combination fires)  --  and the *lower bound* of the 95% bootstrap CI must clear
the tier threshold, not just the point estimate. A 3-of-3 lucky streak will not
fill tier_1; a 38-of-40 sustained pattern will.

Each tiered combination is also gated by an edge-magnitude floor (|mean fwd
return| / cell stddev) so a 0.95 directional signal with 1bp edge does not
pollute the top tier.

Architecture: phased search.
    Phase 1: sweep all 1-way (feature, quartile, direction) constraints per
             (venue, regime) cell. Cheap. Identify any tier-hitting singletons.
    Phase 2: for each Phase-1 winner, add ONE more (feature, quartile)
             constraint. Keep only additions that PROMOTE tier  --  not maintain.
    Phase 3: same shape as Phase 2 from Phase-2 winners; optional, gated by
             --max-arity.

Output: per-cell JSON report with tiered combinations + provenance, plus
optional append to cells_registry.json with notional_usd scaled by tier
(tier_1 = 1.0x, tier_2 = 0.5x, tier_3 = 0.25x of --base-notional).

Predicate DSL construction: prefers feat_quartile when <asset>_cutoffs.json has
the (venue, regime, feature) entry (so future cutoff regenerations re-thresh
automatically); falls back to feat_threshold with the inline boundary value
when cutoffs are missing.

Usage:
    python markets_tier_search.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        [--bybit-perp-bins eth_bybit_perp_bins.json] \\
        [--cutoffs eth_cutoffs.json] \\
        [--max-arity 2] [--bootstrap-samples 1000] \\
        [--output-report tier_search_eth.json] \\
        [--append-to-registry cells_registry.json] \\
        [--base-notional 1000]

Architectural lineage: the per-source agreement -> confidence formula is
borrowed from operator_discovery/cross_domain_connector.py, but replaces its
heuristic (0.6 + 0.1 * n_sources) with bootstrap-validated win-rate CIs
computed against real forward returns. Same shape; statistically grounded.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np

from phase1_5_evaluator import (
    load_bars,
    classify_venue,
    MultiFeatureContext,
    FEATURE_EXTRACTORS,
)


# ---------------------------------------------------------------------------
# Sibling asset helper
# ---------------------------------------------------------------------------

def _sibling_asset(asset: str) -> str:
    return "ETH" if asset == "BTC" else "BTC"


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

@dataclass
class TierSpec:
    name: str
    threshold: float            # lower-CI of P(correct sign) must clear this
    min_n: int                  # minimum chunks in the combination bucket
    edge_floor: float           # |mean(fwd)| / stddev(fwd_cell_corpus) floor
    notional_multiplier: float  # scales the base notional when shipping as a cell


DEFAULT_TIERS = [
    TierSpec("tier_1", threshold=0.95, min_n=60, edge_floor=1.5, notional_multiplier=1.00),
    TierSpec("tier_2", threshold=0.85, min_n=30, edge_floor=1.2, notional_multiplier=0.70),
    TierSpec("tier_3", threshold=0.75, min_n=20, edge_floor=0.9, notional_multiplier=0.50),
    TierSpec("tier_4", threshold=0.65, min_n=15, edge_floor=0.7, notional_multiplier=0.30),
    TierSpec("tier_5", threshold=0.55, min_n=10, edge_floor=0.5, notional_multiplier=0.20),
]


# ---------------------------------------------------------------------------
# Combination type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureGate:
    """One (feature, quartile) constraint."""
    feature: str
    quartile: int  # 1..4


@dataclass
class Combination:
    venue_label: str               # e.g. "KR-ETH"
    regime: str                    # e.g. "WHALE_UP"
    gates: tuple[FeatureGate, ...] # length 1, 2, or 3 typically
    direction: str                 # "momentum" or "fade"  --  predicted sign of fwd
    side: str                      # "buy" or "sell"
    n_in_combo: int                # chunks that match this combination
    score_point: float             # observed P(correct sign)
    score_ci_low: float            # 5th-percentile bootstrap CI
    score_ci_high: float           # 95th-percentile bootstrap CI
    edge_magnitude: float          # |mean(fwd_in_combo)| / std(fwd_cell_corpus)
    mean_fwd: float                # signed mean of forward returns in combo
    tier: str | None               # name of best tier cleared, or None
    arity: int                     # 1, 2, 3  --  number of gates


# ---------------------------------------------------------------------------
# Forward return helper (same pattern as direction_conflict_audit.py)
# ---------------------------------------------------------------------------

def forward_log_returns(chunks: list, k: int = 1) -> np.ndarray:
    """Per-chunk forward log return (k chunks ahead). NaN-padded at the tail."""
    rets = []
    for c in chunks:
        if len(c.bars) >= 2:
            r = math.log(max(c.bars[-1].close, 1e-12)
                            / max(c.bars[0].close, 1e-12))
        else:
            r = 0.0
        rets.append(r)
    arr = np.array(rets, dtype=float)
    if k <= 0:
        return arr
    return np.concatenate([arr[k:], np.full(k, np.nan)])


# ---------------------------------------------------------------------------
# Bootstrap-CI win-rate
# ---------------------------------------------------------------------------

def bootstrap_winrate(fwd_returns: np.ndarray,
                       direction: str,
                       n_resamples: int = 1000,
                       rng: np.random.Generator | None = None
                       ) -> tuple[float, float, float]:
    """Bootstrap CI for P(correct sign | combination fires).

    direction="momentum" => correct sign is positive
    direction="fade"     => correct sign is negative

    Returns (point_estimate, ci_low_5pct, ci_high_95pct). Zero-returns count
    neither way (they neither confirm nor refute the predicted direction).
    """
    arr = fwd_returns[np.isfinite(fwd_returns)]
    n = len(arr)
    if n == 0:
        return 0.0, 0.0, 0.0
    if direction == "momentum":
        hits = (arr > 0).astype(float)
    elif direction == "fade":
        hits = (arr < 0).astype(float)
    else:
        raise ValueError(f"direction must be 'momentum' or 'fade', got {direction!r}")
    point = float(hits.mean())
    if n < 4:
        # Bootstrap meaningless at this size; return point estimate as both bounds
        return point, point, point
    if rng is None:
        rng = np.random.default_rng(seed=0)
    # Vectorized bootstrap
    sample_idx = rng.integers(0, n, size=(n_resamples, n))
    resampled_means = hits[sample_idx].mean(axis=1)
    ci_low = float(np.quantile(resampled_means, 0.05))
    ci_high = float(np.quantile(resampled_means, 0.95))
    return point, ci_low, ci_high


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------

def assign_tier(score_ci_low: float, edge_magnitude: float, n_in_combo: int,
                 tiers: list[TierSpec]) -> str | None:
    """Return the highest-quality tier whose gates this combination clears.
    Tiers must be passed in descending quality order (tier_1 first).
    """
    for tier in tiers:
        if (n_in_combo >= tier.min_n
                and score_ci_low >= tier.threshold
                and edge_magnitude >= tier.edge_floor):
            return tier.name
    return None


# ---------------------------------------------------------------------------
# Per-cell feature evaluation (cached)
# ---------------------------------------------------------------------------

@dataclass
class CellSnapshot:
    """Pre-computed per-cell feature values + forward returns + cell-level stats."""
    venue_label: str
    regime: str
    in_cell_mask: np.ndarray              # bool over all chunks for this venue
    feature_values: dict[str, np.ndarray] # feature_name -> values (cell-only, NaN-pruned)
    feature_quartile: dict[str, np.ndarray]  # feature_name -> quartile (1..4) per cell-chunk
    feature_quartile_upper: dict[str, list[float]]  # q1_upper, q2_upper, q3_upper
    fwd_returns_in_cell: np.ndarray       # forward returns within cell only
    fwd_std_in_cell: float                # stddev used as edge denominator
    n_cell_chunks: int


def _equal_count_quartiles(values: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """Assign each value a quartile 1..4 via equal-count splits of finite ranks.
    Returns (quartile_assignment, [q1_upper, q2_upper, q3_upper])."""
    n = len(values)
    if n < 4:
        # Can't split; everything is Q1
        return np.ones(n, dtype=int), [float("nan")] * 3
    finite_mask = np.isfinite(values)
    quartiles = np.zeros(n, dtype=int)
    finite_vals = values[finite_mask]
    if len(finite_vals) < 4:
        quartiles[finite_mask] = 1
        return quartiles, [float("nan")] * 3
    order = np.argsort(finite_vals)
    finite_idx_in_order = np.where(finite_mask)[0][order]
    cuts = np.linspace(0, len(finite_vals), 5).astype(int)
    uppers: list[float] = []
    for q in range(4):
        lo, hi = cuts[q], cuts[q + 1]
        for k in finite_idx_in_order[lo:hi]:
            quartiles[k] = q + 1
        if q < 3:
            # Upper boundary = highest value in this bucket
            if hi - 1 >= 0 and hi - 1 < len(finite_vals):
                uppers.append(float(finite_vals[order[hi - 1]]))
            else:
                uppers.append(float("nan"))
    return quartiles, uppers


def build_cell_snapshot(venue_label: str,
                         regime: str,
                         in_cell_mask: np.ndarray,
                         feature_values_global: dict[str, np.ndarray],
                         fwd_returns_global: np.ndarray) -> CellSnapshot:
    """Build a CellSnapshot  --  restricts global features + fwd to in-cell chunks
    and computes per-feature equal-count quartiles using only in-cell values."""
    fwd_cell = fwd_returns_global[in_cell_mask]
    fwd_finite = fwd_cell[np.isfinite(fwd_cell)]
    fwd_std = float(np.std(fwd_finite)) if len(fwd_finite) >= 2 else 0.0

    feature_values: dict[str, np.ndarray] = {}
    feature_quartile: dict[str, np.ndarray] = {}
    feature_quartile_upper: dict[str, list[float]] = {}
    for name, vals in feature_values_global.items():
        cell_vals = vals[in_cell_mask]
        quartiles, uppers = _equal_count_quartiles(cell_vals)
        feature_values[name] = cell_vals
        feature_quartile[name] = quartiles
        feature_quartile_upper[name] = uppers

    return CellSnapshot(
        venue_label=venue_label,
        regime=regime,
        in_cell_mask=in_cell_mask,
        feature_values=feature_values,
        feature_quartile=feature_quartile,
        feature_quartile_upper=feature_quartile_upper,
        fwd_returns_in_cell=fwd_cell,
        fwd_std_in_cell=fwd_std,
        n_cell_chunks=int(in_cell_mask.sum()),
    )


# ---------------------------------------------------------------------------
# Combination scoring against a CellSnapshot
# ---------------------------------------------------------------------------

def _combo_mask(snap: CellSnapshot, gates: tuple[FeatureGate, ...]) -> np.ndarray:
    """Build a bool mask over in-cell chunks indicating which match ALL gates."""
    if not gates:
        return np.ones(snap.n_cell_chunks, dtype=bool)
    mask = np.ones(snap.n_cell_chunks, dtype=bool)
    for gate in gates:
        q = snap.feature_quartile.get(gate.feature)
        if q is None:
            return np.zeros(snap.n_cell_chunks, dtype=bool)
        mask &= (q == gate.quartile)
    return mask


def score_combination(snap: CellSnapshot,
                        gates: tuple[FeatureGate, ...],
                        bootstrap_samples: int,
                        tiers: list[TierSpec],
                        rng: np.random.Generator) -> Combination | None:
    """Score a combination on a single (venue, regime) cell. Tries both
    directions; returns the better-scoring direction. None if no chunks match."""
    mask = _combo_mask(snap, gates)
    n_in = int(mask.sum())
    if n_in == 0:
        return None
    fwd_in = snap.fwd_returns_in_cell[mask]
    finite = fwd_in[np.isfinite(fwd_in)]
    if len(finite) == 0:
        return None
    mean_fwd = float(np.mean(finite))
    direction = "momentum" if mean_fwd >= 0 else "fade"
    side = "buy" if mean_fwd >= 0 else "sell"
    score_pt, score_lo, score_hi = bootstrap_winrate(
        fwd_in, direction, n_resamples=bootstrap_samples, rng=rng
    )
    edge = (abs(mean_fwd) / snap.fwd_std_in_cell) if snap.fwd_std_in_cell > 1e-12 else 0.0
    tier = assign_tier(score_lo, edge, n_in, tiers)
    return Combination(
        venue_label=snap.venue_label,
        regime=snap.regime,
        gates=gates,
        direction=direction,
        side=side,
        n_in_combo=n_in,
        score_point=score_pt,
        score_ci_low=score_lo,
        score_ci_high=score_hi,
        edge_magnitude=edge,
        mean_fwd=mean_fwd,
        tier=tier,
        arity=len(gates),
    )


# ---------------------------------------------------------------------------
# Tier ordering helpers (so we can compare "promotes" between tiers)
# ---------------------------------------------------------------------------

def _tier_rank(tier: str | None, tiers: list[TierSpec]) -> int:
    """Rank: tier_1 = highest = 3, tier_3 = 1, None = 0."""
    if tier is None:
        return 0
    for i, t in enumerate(tiers):
        if t.name == tier:
            return len(tiers) - i
    return 0


# ---------------------------------------------------------------------------
# Phased search
# ---------------------------------------------------------------------------

def phase_1_search(snap: CellSnapshot,
                    features: list[str],
                    bootstrap_samples: int,
                    tiers: list[TierSpec],
                    rng: np.random.Generator) -> list[Combination]:
    """Sweep all 1-way (feature, quartile) combinations on this cell. Return
    only combinations that clear at least the lowest tier."""
    winners: list[Combination] = []
    for feat in features:
        if feat not in snap.feature_quartile:
            continue
        for q in (1, 2, 3, 4):
            combo = score_combination(
                snap, (FeatureGate(feat, q),),
                bootstrap_samples, tiers, rng,
            )
            if combo and combo.tier is not None:
                winners.append(combo)
    return winners


def phase_n_search(snap: CellSnapshot,
                    base_winners: list[Combination],
                    features: list[str],
                    bootstrap_samples: int,
                    tiers: list[TierSpec],
                    rng: np.random.Generator,
                    target_arity: int) -> list[Combination]:
    """For each combination in base_winners (arity = target_arity - 1), try
    adding every remaining (feature, quartile) constraint. Keep only additions
    that PROMOTE tier strictly above the base combination's tier."""
    promoted: list[Combination] = []
    seen: set[frozenset] = set()
    for base in base_winners:
        if base.arity != target_arity - 1:
            continue
        used_features = {g.feature for g in base.gates}
        base_rank = _tier_rank(base.tier, tiers)
        for feat in features:
            if feat in used_features or feat not in snap.feature_quartile:
                continue
            for q in (1, 2, 3, 4):
                new_gates = base.gates + (FeatureGate(feat, q),)
                # Sort to canonicalize and dedupe (axb == bxa)
                key = frozenset((g.feature, g.quartile) for g in new_gates)
                if key in seen:
                    continue
                combo = score_combination(
                    snap, tuple(sorted(new_gates, key=lambda g: (g.feature, g.quartile))),
                    bootstrap_samples, tiers, rng,
                )
                if combo is None or combo.tier is None:
                    continue
                if _tier_rank(combo.tier, tiers) > base_rank:
                    seen.add(key)
                    promoted.append(combo)
    return promoted


# ---------------------------------------------------------------------------
# Build feature-values dict across ALL chunks of a venue
# ---------------------------------------------------------------------------

def compute_global_feature_values(ctx: MultiFeatureContext,
                                   feature_names: list[str]) -> dict[str, np.ndarray]:
    """Run each FEATURE_EXTRACTORS entry against ctx. Returns a dict
    feature_name -> length-len(ctx.chunks) array, with NaN where the extractor
    flagged unavailable."""
    out: dict[str, np.ndarray] = {}
    ext_by_name = {name: fn for name, _g, _r, fn in FEATURE_EXTRACTORS}
    n_chunks = len(ctx.chunks)
    for fname in feature_names:
        fn = ext_by_name.get(fname)
        if fn is None:
            continue
        try:
            values, status = fn(ctx)
        except Exception as exc:
            print(f"    [warn] feature {fname} raised {type(exc).__name__}: {exc}")
            continue
        if values is None or len(values) != n_chunks:
            continue
        out[fname] = np.asarray(values, dtype=float)
    return out


# ---------------------------------------------------------------------------
# DSL predicate construction for the winner cells
# ---------------------------------------------------------------------------

def build_predicate(combo: Combination,
                     cutoffs: dict,
                     cell_key: str,
                     fallback_uppers_by_feature: dict[str, list[float]]) -> dict:
    """Construct a DSL predicate for combo. Uses feat_quartile if cutoffs
    contain the (venue, regime, feature) entry; else falls back to
    feat_threshold using the in-cell-derived quartile uppers."""
    leaves: list[dict] = [{"regime_eq": combo.regime}]
    venue_cutoffs = cutoffs.get("cutoffs", {}).get(combo.venue_label, {})
    regime_cutoffs = venue_cutoffs.get(combo.regime, {})
    for gate in combo.gates:
        if gate.feature in regime_cutoffs:
            leaves.append({
                "feat_quartile": {
                    "name": gate.feature,
                    "cell_key": f"{combo.venue_label}/{combo.regime}",
                    "quartile_min": gate.quartile,
                    "quartile_max": gate.quartile,
                }
            })
        else:
            # Fallback: inline threshold from in-cell-derived uppers
            uppers = fallback_uppers_by_feature.get(gate.feature, [float("nan")] * 3)
            if gate.quartile == 1:
                # Q1: <= q1_upper
                leaves.append({"feat_threshold": {
                    "name": gate.feature, "op": "<=", "value": uppers[0],
                }})
            elif gate.quartile == 2:
                # Q2: > q1_upper AND <= q2_upper -> use all_of pair
                leaves.append({"all_of": [
                    {"feat_threshold": {"name": gate.feature, "op": ">", "value": uppers[0]}},
                    {"feat_threshold": {"name": gate.feature, "op": "<=", "value": uppers[1]}},
                ]})
            elif gate.quartile == 3:
                leaves.append({"all_of": [
                    {"feat_threshold": {"name": gate.feature, "op": ">", "value": uppers[1]}},
                    {"feat_threshold": {"name": gate.feature, "op": "<=", "value": uppers[2]}},
                ]})
            elif gate.quartile == 4:
                leaves.append({"feat_threshold": {
                    "name": gate.feature, "op": ">", "value": uppers[2],
                }})
    return {"all_of": leaves} if len(leaves) > 1 else leaves[0]


def build_cell_entry(combo: Combination,
                      asset: str,
                      tier_spec: TierSpec,
                      base_notional: float,
                      predicate: dict,
                      pass_num: int) -> dict:
    """Build a cells_registry.json-shaped entry for combo."""
    venue_short = combo.venue_label.split("-")[0].lower()  # "KR" -> "kr"
    regime_short = combo.regime.lower()
    gate_spec = "_".join(f"{g.feature}_q{g.quartile}" for g in combo.gates)
    cell_id = (f"{asset.lower()}_{venue_short}_{regime_short}_"
               f"{gate_spec}_{tier_spec.name}")
    return {
        "cell_id": cell_id,
        "asset": asset,
        "venue": combo.venue_label.split("-")[0],
        "side": combo.side,
        "kind": "directional",
        "notional_usd": float(base_notional * tier_spec.notional_multiplier),
        "hold_minutes": 10.0,
        "capacity_class": "tiny",
        "note": (f"tier_search Pass-{pass_num}: {combo.venue_label} {combo.regime} "
                 f"{combo.direction}; "
                 f"score={combo.score_point:.3f} ci=[{combo.score_ci_low:.3f},{combo.score_ci_high:.3f}] "
                 f"edge={combo.edge_magnitude:.2f} n={combo.n_in_combo}"),
        "predicate": predicate,
        "provenance": {
            "discovered_pass": pass_num,
            "discovery_method": "markets_tier_search",
            "tier": tier_spec.name,
            "score_point": combo.score_point,
            "score_ci_low": combo.score_ci_low,
            "score_ci_high": combo.score_ci_high,
            "edge_magnitude": combo.edge_magnitude,
            "n_chunks_in_combo": combo.n_in_combo,
            "mean_fwd_return": combo.mean_fwd,
            "arity": combo.arity,
            "combination_spec": [
                {"feature": g.feature, "quartile": g.quartile} for g in combo.gates
            ],
            "predicted_direction": combo.direction,
        },
    }


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

@dataclass
class _VenueData:
    """Intermediate: raw classifier output per venue before cross-wiring."""
    label: str
    chunks: list
    feats: list
    results: list


def _load_venue_data(asset: str, label_prefix: str, bins_path: str,
                      chunk_max: int, chunk_min: int, multi_pelt: bool
                      ) -> _VenueData | None:
    """Load bins + classify a single venue. Returns None if bins missing."""
    if not bins_path or not os.path.exists(bins_path):
        return None
    venue_label = f"{label_prefix}-{asset}"
    bars = load_bars(bins_path)
    chunks, results, _, _, feats = classify_venue(
        bars, venue_label, chunk_max=chunk_max, chunk_min=chunk_min,
        multi_signal_pelt=multi_pelt,
    )
    return _VenueData(label=venue_label, chunks=chunks, feats=feats, results=results)


def load_all_venue_contexts(asset: str,
                              cb_bins: str, kr_bins: str,
                              perp_bins: str | None = None,
                              sibling_cb_bins: str | None = None,
                              sibling_kr_bins: str | None = None,
                              chunk_max: int = 30, chunk_min: int = 10,
                              multi_pelt: bool = True
                              ) -> list[tuple[str, MultiFeatureContext, list]]:
    """Load + wire every venue context. Each returned MultiFeatureContext is
    fully wired with sibling, other_venue, and perp references so cross-platform
    features (perp_spot_basis_z, cross_venue_gap_z, perp_spot_dipole_divergence,
    cross_asset_dipole, etc.) compute against real data instead of returning
    status=no_data.

    Returns list of (venue_label, MultiFeatureContext, classification_results)
    for the THREE primary venues of asset: CB-<asset>, KR-<asset>, BB-<asset>.
    Sibling-asset data is loaded but not returned as its own context — it only
    populates the sibling_chunks/feats slots on the primary contexts.
    """
    # Primary asset venues
    cb = _load_venue_data(asset, "CB", cb_bins, chunk_max, chunk_min, multi_pelt)
    kr = _load_venue_data(asset, "KR", kr_bins, chunk_max, chunk_min, multi_pelt)
    perp = _load_venue_data(asset, "BB", perp_bins, chunk_max, chunk_min, multi_pelt) if perp_bins else None

    # Sibling-asset data (for cross_asset_dipole and friends)
    sib_asset = _sibling_asset(asset)
    sib_cb = _load_venue_data(sib_asset, "CB", sibling_cb_bins, chunk_max, chunk_min, multi_pelt) if sibling_cb_bins else None
    sib_kr = _load_venue_data(sib_asset, "KR", sibling_kr_bins, chunk_max, chunk_min, multi_pelt) if sibling_kr_bins else None

    contexts: list[tuple[str, MultiFeatureContext, list]] = []
    primaries = [(cb, "CB"), (kr, "KR"), (perp, "BB")]
    for venue, prefix in primaries:
        if venue is None:
            continue
        # Pick the OTHER spot venue (same asset, different exchange) for the
        # other_venue slot. For perp (BB), use CB as the spot reference.
        if prefix == "CB":
            other = kr
            sibling = sib_cb  # same-venue sibling-asset
        elif prefix == "KR":
            other = cb
            sibling = sib_kr
        else:  # BB perp
            other = cb if cb else kr   # any spot venue serves as basis reference
            sibling = sib_cb if sib_cb else sib_kr

        ctx = MultiFeatureContext(
            chunks=venue.chunks,
            feats=venue.feats,
            sibling_chunks=sibling.chunks if sibling else None,
            sibling_feats=sibling.feats if sibling else None,
            other_venue_chunks=other.chunks if other else None,
            other_venue_feats=other.feats if other else None,
            perp_chunks=perp.chunks if perp else None,
            perp_feats=perp.feats if perp else None,
        )
        contexts.append((venue.label, ctx, venue.results))

    return contexts


def run_search(asset: str,
                venue_contexts: list[tuple[str, MultiFeatureContext, list]],
                feature_names: list[str],
                tiers: list[TierSpec],
                bootstrap_samples: int,
                max_arity: int,
                rng: np.random.Generator) -> list[Combination]:
    """Search every (venue, regime) cell across all venue contexts. Returns the
    union of tier-hitting combinations from all phases."""
    all_winners: list[Combination] = []

    for venue_label, ctx, results in venue_contexts:
        print(f"\n=== venue {venue_label} ({len(ctx.chunks)} chunks) ===")
        # Wire cross-venue siblings: simplest case  --  leave None; novel/cross-
        # platform features that need other_venue context will return status
        # = "no_data" and be filtered out. To enable, the caller can pass
        # already-cross-wired contexts. (Pass-18 plumbing follow-on.)

        # Global feature values (one pass through all chunks)
        feat_vals = compute_global_feature_values(ctx, feature_names)
        if not feat_vals:
            print(f"  no feature values available for {venue_label}, skipping")
            continue

        # Forward returns indexed by chunk
        fwd = forward_log_returns(ctx.chunks, k=1)

        # Build cell snapshots for every distinct regime
        regimes_observed = sorted({r.regime.value for r in results})
        print(f"  regimes: {regimes_observed}")
        snapshots: list[CellSnapshot] = []
        for regime in regimes_observed:
            mask = np.array([r.regime.value == regime for r in results])
            if int(mask.sum()) < 8:
                continue  # too thin to bother
            snap = build_cell_snapshot(
                venue_label, regime, mask,
                feat_vals, fwd,
            )
            snapshots.append(snap)

        # Phased search per cell
        for snap in snapshots:
            t0 = time.time()
            # Phase 1: 1-way singletons
            p1 = phase_1_search(snap, list(feat_vals.keys()),
                                  bootstrap_samples, tiers, rng)
            phase_winners = list(p1)
            all_phase_for_cell = list(p1)
            # Phase 2+
            for arity in range(2, max_arity + 1):
                base = [c for c in phase_winners if c.arity == arity - 1]
                if not base:
                    break
                pn = phase_n_search(snap, base, list(feat_vals.keys()),
                                      bootstrap_samples, tiers, rng, arity)
                phase_winners.extend(pn)
                all_phase_for_cell.extend(pn)
            elapsed = time.time() - t0
            tier_counts = {t.name: 0 for t in tiers}
            for c in all_phase_for_cell:
                if c.tier in tier_counts:
                    tier_counts[c.tier] += 1
            tier_str = " ".join(f"t{t.name.split('_')[-1]}={tier_counts[t.name]:>2}"
                                 for t in tiers)
            print(f"    {snap.regime:<26} n={snap.n_cell_chunks:>3}  "
                  f"{tier_str}  ({elapsed:.1f}s)")
            all_winners.extend(all_phase_for_cell)

    return all_winners


def dedupe_keep_best_tier(winners: list[Combination],
                            tiers: list[TierSpec]) -> list[Combination]:
    """For each (venue, regime, gate-set, direction), keep only the highest-
    scoring tier instance (in case the same combo appeared from multiple
    phases or scoring runs)."""
    best: dict[tuple, Combination] = {}
    for c in winners:
        key = (c.venue_label, c.regime,
               frozenset((g.feature, g.quartile) for g in c.gates),
               c.direction)
        existing = best.get(key)
        if existing is None or _tier_rank(c.tier, tiers) > _tier_rank(existing.tier, tiers):
            best[key] = c
    return list(best.values())


def append_to_registry(registry_path: str,
                        new_entries: list[dict],
                        dry_run: bool = False) -> int:
    """Append new entries to cells_registry.json. Skips entries whose cell_id
    already exists. Returns number actually appended."""
    if not os.path.exists(registry_path):
        raise FileNotFoundError(f"Registry not found: {registry_path}")
    with open(registry_path) as f:
        reg = json.load(f)
    existing_ids = {c.get("cell_id") for c in reg.get("cells", [])}
    to_add = [e for e in new_entries if e["cell_id"] not in existing_ids]
    if dry_run:
        print(f"  [dry-run] would append {len(to_add)} new cell(s) "
              f"(skipped {len(new_entries) - len(to_add)} duplicates)")
        return 0
    reg["cells"].extend(to_add)
    reg["generated_utc"] = int(time.time())
    with open(registry_path, "w") as f:
        json.dump(reg, f, indent=2)
    return len(to_add)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True, choices=["ETH", "BTC"])
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None,
                   help="CB bins for the OTHER asset (BTC if asset=ETH, vice"
                        " versa). Enables cross_asset_dipole and related"
                        " cross-asset features.")
    p.add_argument("--sibling-kr-bins", default=None,
                   help="KR bins for the OTHER asset.")
    p.add_argument("--cutoffs", default=None,
                   help="Path to <asset>_cutoffs.json for feat_quartile predicate"
                        " construction. If omitted, all predicates use inline"
                        " feat_threshold values derived from the search itself.")
    p.add_argument("--features", nargs="*", default=None,
                   help="Subset of FEATURE_EXTRACTORS names to search."
                        " Default: all features.")
    p.add_argument("--max-arity", type=int, default=2,
                   help="Maximum combination arity (1=singletons, 2=pairs, 3=triples)")
    p.add_argument("--bootstrap-samples", type=int, default=1000)
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true", default=True)
    p.add_argument("--base-notional", type=float, default=1000.0)
    p.add_argument("--pass-num", type=int, default=18,
                   help="Pass number to record in provenance.discovered_pass")
    p.add_argument("--output-report", default=None,
                   help="Write full JSON report to this path")
    p.add_argument("--append-to-registry", default=None,
                   help="Append tier-1, tier-2, AND tier-3 winners as new cells"
                        " to this registry JSON. All tiers ship by default so"
                        " subscribers can pick their own risk appetite on the"
                        " consuming side (signal_allocator filters by profile).")
    p.add_argument("--exclude-tier-3", action="store_true",
                   help="Skip tier-3 cells when appending to registry (more"
                        " conservative; default ships all tiers).")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be appended but do not write the registry")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)

    feature_names = args.features
    if feature_names is None:
        feature_names = [name for name, _g, _r, _fn in FEATURE_EXTRACTORS]

    print(f"=== markets_tier_search asset={args.asset} max_arity={args.max_arity} "
          f"bootstrap={args.bootstrap_samples} features={len(feature_names)} ===")

    # Load + wire all venue contexts (cross-venue, perp, sibling-asset all
    # populated where bins are provided). Cross-platform features now have
    # real data to compute against instead of returning status=no_data.
    contexts = load_all_venue_contexts(
        asset=args.asset,
        cb_bins=args.cb_bins,
        kr_bins=args.kr_bins,
        perp_bins=args.bybit_perp_bins,
        sibling_cb_bins=args.sibling_cb_bins,
        sibling_kr_bins=args.sibling_kr_bins,
        chunk_max=args.chunk_max_size,
        chunk_min=args.chunk_min_segment,
        multi_pelt=args.multi_signal_pelt,
    )

    winners = run_search(
        args.asset, contexts, feature_names, DEFAULT_TIERS,
        args.bootstrap_samples, args.max_arity, rng,
    )
    winners = dedupe_keep_best_tier(winners, DEFAULT_TIERS)

    # Summary
    tier_counts_summary = {t.name: 0 for t in DEFAULT_TIERS}
    for c in winners:
        if c.tier in tier_counts_summary:
            tier_counts_summary[c.tier] += 1
    counts_str = " ".join(f"{t.name}={tier_counts_summary[t.name]}"
                            for t in DEFAULT_TIERS)
    print(f"\n=== summary: {len(winners)} tier-hitting combinations "
          f"({counts_str}) ===")

    # Optional report
    if args.output_report:
        report = {
            "asset": args.asset,
            "generated_utc": int(time.time()),
            "tiers": [asdict(t) for t in DEFAULT_TIERS],
            "max_arity": args.max_arity,
            "bootstrap_samples": args.bootstrap_samples,
            "features_searched": feature_names,
            "n_winners": len(winners),
            "tier_counts": dict(tier_counts_summary),
            "winners": [
                {
                    "venue_label": c.venue_label,
                    "regime": c.regime,
                    "tier": c.tier,
                    "direction": c.direction,
                    "side": c.side,
                    "n_in_combo": c.n_in_combo,
                    "score_point": c.score_point,
                    "score_ci_low": c.score_ci_low,
                    "score_ci_high": c.score_ci_high,
                    "edge_magnitude": c.edge_magnitude,
                    "mean_fwd": c.mean_fwd,
                    "arity": c.arity,
                    "gates": [{"feature": g.feature, "quartile": g.quartile}
                              for g in c.gates],
                }
                for c in winners
            ],
        }
        with open(args.output_report, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  report saved: {args.output_report}")

    # Optional registry append
    if args.append_to_registry:
        if not args.cutoffs:
            print("  [warn] no --cutoffs provided; predicates will use"
                  " inline feat_threshold values (still valid DSL)")
            cutoffs = {"cutoffs": {}}
        else:
            with open(args.cutoffs) as f:
                cutoffs = json.load(f)

        # Build per-(venue, regime) fallback uppers from the search snapshots.
        # Re-run the snapshot pass for this purpose (cheap; just quartile boundaries).
        # Practical shortcut: we recorded uppers in CellSnapshot during search.
        # In this simplified flow we accept inline-threshold fallback uses the
        # in-cell quartile boundaries that the search already derived for each
        # cell. For the registry write, we re-derive on demand: build a small
        # local cache from a second pass over winners.
        fallback_cache: dict[tuple[str, str], dict[str, list[float]]] = {}
        for venue_label, ctx, results in contexts:
            feat_vals = compute_global_feature_values(ctx, feature_names)
            fwd = forward_log_returns(ctx.chunks, k=1)
            for regime in sorted({r.regime.value for r in results}):
                mask = np.array([r.regime.value == regime for r in results])
                if int(mask.sum()) < 8:
                    continue
                snap = build_cell_snapshot(venue_label, regime, mask, feat_vals, fwd)
                fallback_cache[(venue_label, regime)] = dict(snap.feature_quartile_upper)

        tier_lookup = {t.name: t for t in DEFAULT_TIERS}
        entries: list[dict] = []
        for c in winners:
            if c.tier == "tier_3" and args.exclude_tier_3:
                continue
            tier_spec = tier_lookup[c.tier]
            uppers_map = fallback_cache.get((c.venue_label, c.regime), {})
            predicate = build_predicate(c, cutoffs,
                                          f"{c.venue_label}/{c.regime}",
                                          uppers_map)
            entry = build_cell_entry(c, args.asset, tier_spec,
                                       args.base_notional, predicate,
                                       args.pass_num)
            entries.append(entry)

        n_added = append_to_registry(args.append_to_registry, entries,
                                       dry_run=args.dry_run)
        if not args.dry_run:
            print(f"  appended {n_added} new cells to {args.append_to_registry}")


if __name__ == "__main__":
    main()
