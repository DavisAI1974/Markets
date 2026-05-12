"""
direction_conflict_audit.py — investigate same-cell direction conflicts
between features in the multi-feature scan output.

A direction conflict happens when multiple features land in Tier 1 on
the same (venue, regime) cell but disagree on direction (momentum vs
fade). The naive response is "the majority wins"; the correct
response is "under what CONDITIONS does each direction win?" — because
each feature is measuring something real about the underlying market.
The conflict often resolves into a conditional rule (e.g. "when basis
is elevated, momentum; when basis is normal, fade") rather than a
contradiction.

Method: for each target cell, slice its chunks into quartiles by each
conflicting feature's per-chunk value. Compute the forward log-return
mean within each quartile. Report a per-feature × quartile table.

If a feature's quartile splits the forward returns by direction —
e.g., Q1+Q2 fade-direction returns, Q3+Q4 momentum-direction returns
— that's the conditioning rule. If quartiles all return the same
direction, the feature isn't a conditioner, it's just noisy.

Usage:
    python direction_conflict_audit.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        --bybit-perp-bins eth_bybit_perp_bins.json \\
        --target-venue KR-ETH --target-regime WHALE_UP \\
        --features mean_dipole mean_ofi perp_spot_basis_z realized_vol_z

For each named feature, prints per-quartile forward-return mean +
sample count. Don't average across features; each tells its own story.
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np

# Reuse the evaluator's machinery so the feature extractors / chunking
# / classifier are identical to what produced the multi-feature scan
# in the first place.
from phase1_5_evaluator import (
    load_bars,
    classify_venue,
    MultiFeatureContext,
    FEATURE_EXTRACTORS,
)


def _forward_log_returns(chunks: list, k: int = 1) -> np.ndarray:
    """Per-chunk forward log return computed the same way the
    classifier does (over the chunk's first/last bar close, then
    lagged by k chunks)."""
    rets = []
    for c in chunks:
        if len(c.bars) >= 2:
            r = math.log(max(c.bars[-1].close, 1e-12)
                            / max(c.bars[0].close, 1e-12))
        else:
            r = 0.0
        rets.append(r)
    arr = np.array(rets)
    # Forward return: shift by k
    if k <= 0:
        return arr
    shifted = np.concatenate([arr[k:], np.full(k, np.nan)])
    return shifted


def _quartile_breakdown(feature_values: np.ndarray,
                          forward_returns: np.ndarray,
                          n_buckets: int = 4) -> list[dict]:
    """Sort chunks by feature value, split into n_buckets equal-count
    groups, compute forward-return mean + SE per group. Returns a list
    of dicts ordered Q1 (lowest feature value) to Qn (highest)."""
    # Mask NaN forward returns (last-chunk rolloff)
    mask = np.isfinite(feature_values) & np.isfinite(forward_returns)
    fv = feature_values[mask]
    fr = forward_returns[mask]
    n = len(fv)
    if n < n_buckets * 2:
        return [{"bucket": q + 1, "n": 0, "feature_range": None,
                   "mean_fwd": None, "se": None, "direction": "n/a"}
                for q in range(n_buckets)]
    order = np.argsort(fv)
    fv_sorted = fv[order]
    fr_sorted = fr[order]
    out = []
    # Equal-count splits (quantile-by-rank)
    cuts = np.linspace(0, n, n_buckets + 1).astype(int)
    for q in range(n_buckets):
        lo, hi = cuts[q], cuts[q + 1]
        sub_fv = fv_sorted[lo:hi]
        sub_fr = fr_sorted[lo:hi]
        if len(sub_fr) == 0:
            out.append({"bucket": q + 1, "n": 0, "feature_range": None,
                          "mean_fwd": None, "se": None, "direction": "n/a"})
            continue
        m = float(np.mean(sub_fr))
        s = float(np.std(sub_fr) / max(math.sqrt(len(sub_fr)), 1.0))
        out.append({
            "bucket": q + 1,
            "n": int(len(sub_fr)),
            "feature_range": (float(sub_fv[0]), float(sub_fv[-1])),
            "mean_fwd": m,
            "se": s,
            "direction": "momentum" if m > 0 else ("fade" if m < 0 else "flat"),
        })
    return out


def audit_cell(venue_label: str,
                regime: str,
                ctx: MultiFeatureContext,
                results: list,
                feature_names: list[str],
                k: int = 1) -> None:
    """Print the per-feature × quartile forward-return breakdown for
    chunks of one (venue, regime) cell."""
    # Build a name → extractor lookup from the registry
    ext_by_name = {name: fn for name, _g, _r, fn in FEATURE_EXTRACTORS}

    chunks = ctx.chunks
    regime_labels = [r.regime.value for r in results]

    # Forward returns indexed by chunk
    fwd = _forward_log_returns(chunks, k=k)

    # Restrict to chunks where this chunk's regime matches the target.
    in_cell = np.array([lbl == regime for lbl in regime_labels])

    # Compute each feature's value across ALL chunks (some features
    # need the global series for z-scoring), then slice to the in-cell
    # subset.
    print(f"\n=== {venue_label}  regime={regime}  ===")
    print(f"chunks in cell: {int(in_cell.sum())}")
    print(f"corpus chunks total: {len(chunks)}")

    for fname in feature_names:
        fn = ext_by_name.get(fname)
        if fn is None:
            print(f"\n  [feature unknown: {fname}]")
            continue
        values, status = fn(ctx)
        if status and not status.startswith(""):
            print(f"\n  [{fname}]  status: {status}")
            continue
        if values is None or not np.any(np.isfinite(values)):
            print(f"\n  [{fname}]  no finite values")
            continue
        # Slice to in-cell chunks; align with forward returns
        v_cell = values[in_cell]
        f_cell = fwd[in_cell]
        if len(v_cell) < 8:
            print(f"\n  [{fname}]  too few in-cell chunks for quartile "
                  f"audit (n={len(v_cell)})")
            continue
        print(f"\n  [{fname}]   chunks={len(v_cell)}   "
              f"feature_mean={float(np.nanmean(v_cell)):+.4f}   "
              f"feature_std={float(np.nanstd(v_cell)):.4f}")
        rows = _quartile_breakdown(v_cell, f_cell, n_buckets=4)
        for r in rows:
            if r["mean_fwd"] is None:
                print(f"    Q{r['bucket']}: n={r['n']}  (empty)")
                continue
            lo, hi = r["feature_range"]
            mark = ""
            if abs(r["mean_fwd"]) > 2 * (r["se"] or 1e9):
                mark = "  ***" if abs(r["mean_fwd"]) > 3 * (r["se"] or 1e9) else "  **"
            elif abs(r["mean_fwd"]) > 1.5 * (r["se"] or 1e9):
                mark = "  *"
            print(f"    Q{r['bucket']}: n={r['n']:>3}  "
                  f"feature ∈ [{lo:+.3f}, {hi:+.3f}]  "
                  f"fwd_r={r['mean_fwd']:+.5f}  SE={r['se']:.5f}  "
                  f"dir={r['direction']}{mark}")

    print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True, choices=["ETH", "BTC"])
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--multi-signal-pelt", action="store_true", default=True)
    p.add_argument("--target-venue", required=True,
                   help="e.g. KR-ETH, CB-ETH, KR-BTC, CB-BTC")
    p.add_argument("--target-regime", required=True,
                   help="e.g. WHALE_UP, EQUILIBRIUM_TWO_SIDED, WASH_HAWKES")
    p.add_argument("--features", nargs="+", required=True,
                   help="Feature names to audit (from FEATURE_EXTRACTORS)")
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=4)
    args = p.parse_args()

    cb_bars = load_bars(args.cb_bins)
    kr_bars = load_bars(args.kr_bins)
    cb_chunks, cb_results, _, _, cb_feats = classify_venue(
        cb_bars, f"CB-{args.asset}", args.chunk_max_size,
        args.chunk_min_segment, multi_signal_pelt=args.multi_signal_pelt,
    )
    kr_chunks, kr_results, _, _, kr_feats = classify_venue(
        kr_bars, f"KR-{args.asset}", args.chunk_max_size,
        args.chunk_min_segment, multi_signal_pelt=args.multi_signal_pelt,
    )

    perp_chunks = None
    perp_feats = None
    if args.bybit_perp_bins and os.path.exists(args.bybit_perp_bins):
        perp_bars = load_bars(args.bybit_perp_bins)
        perp_chunks, _perp_res, _, _, perp_feats = classify_venue(
            perp_bars, f"BB-{args.asset}", args.chunk_max_size,
            args.chunk_min_segment, multi_signal_pelt=args.multi_signal_pelt,
        )

    sib_cb_chunks = None
    sib_cb_feats = None
    sib_kr_chunks = None
    sib_kr_feats = None
    sibling_asset = "ETH" if args.asset == "BTC" else "BTC"
    if args.sibling_cb_bins and os.path.exists(args.sibling_cb_bins):
        sib_cb_bars = load_bars(args.sibling_cb_bins)
        sib_cb_chunks, _, _, _, sib_cb_feats = classify_venue(
            sib_cb_bars, f"CB-{sibling_asset}", args.chunk_max_size,
            args.chunk_min_segment, multi_signal_pelt=args.multi_signal_pelt,
        )
    if args.sibling_kr_bins and os.path.exists(args.sibling_kr_bins):
        sib_kr_bars = load_bars(args.sibling_kr_bins)
        sib_kr_chunks, _, _, _, sib_kr_feats = classify_venue(
            sib_kr_bars, f"KR-{sibling_asset}", args.chunk_max_size,
            args.chunk_min_segment, multi_signal_pelt=args.multi_signal_pelt,
        )

    # Pick venue side based on target_venue
    if args.target_venue.startswith("CB-"):
        ctx = MultiFeatureContext(
            chunks=cb_chunks, feats=cb_feats,
            sibling_chunks=sib_cb_chunks, sibling_feats=sib_cb_feats,
            other_venue_chunks=kr_chunks, other_venue_feats=kr_feats,
            perp_chunks=perp_chunks, perp_feats=perp_feats,
        )
        results = cb_results
    elif args.target_venue.startswith("KR-"):
        ctx = MultiFeatureContext(
            chunks=kr_chunks, feats=kr_feats,
            sibling_chunks=sib_kr_chunks, sibling_feats=sib_kr_feats,
            other_venue_chunks=cb_chunks, other_venue_feats=cb_feats,
            perp_chunks=perp_chunks, perp_feats=perp_feats,
        )
        results = kr_results
    else:
        raise SystemExit(f"target-venue must start with CB- or KR-: {args.target_venue}")

    audit_cell(
        venue_label=args.target_venue,
        regime=args.target_regime,
        ctx=ctx,
        results=results,
        feature_names=args.features,
        k=1,
    )


if __name__ == "__main__":
    main()
