"""
audit_bounded_form_value.py — heavy-tail audit for bounded-form features.

For each operationalization feature and each (venue, regime) cell, compare the
bounded feature's cell-local distribution to the raw underlying dominance ratio.
If the raw form is well behaved, the bounded form is mostly cosmetic. If the
raw form is heavy tailed, the bounded form is earning its keep operationally.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict

import numpy as np

from markets_tier_search import load_all_venue_contexts, compute_global_feature_values
from phase1_5_evaluator import FEATURE_EXTRACTORS, MultiFeatureContext, _ts_aligned_lookup


SUPPORTED_OPERATIONALIZATION = {
    "mean_dipole",
    "vpin_like",
    "book_depth_imbalance",
    "cross_venue_buy_volume_dipole",
    "cross_venue_sell_volume_dipole",
    "perp_spot_buy_volume_dipole",
    "perp_spot_sell_volume_dipole",
    "cross_venue_l1_bid_depth_dipole",
    "cross_venue_l1_ask_depth_dipole",
}


def _dominance_ratio(a: float, b: float) -> float:
    if a <= 0 and b <= 0:
        return float("nan")
    hi = max(float(a), float(b))
    lo = max(min(float(a), float(b)), 1e-9)
    return hi / lo


def _chunk_buy_sell_ratio(chunk) -> float:
    buy = float(sum(b.buy_vol for b in chunk.bars))
    sell = float(sum(b.sell_vol for b in chunk.bars))
    return _dominance_ratio(buy, sell)


def _chunk_depth_ratio(chunk, side: str) -> float:
    vals = [
        float(getattr(bar, side))
        for bar in chunk.bars
        if float(getattr(bar, side)) > 0
    ]
    if not vals:
        return float("nan")
    other_side = "ask_qty" if side == "bid_qty" else "bid_qty"
    others = [
        float(getattr(bar, other_side))
        for bar in chunk.bars
        if float(getattr(bar, other_side)) > 0
    ]
    if not others:
        return float("nan")
    return _dominance_ratio(float(np.mean(vals)), float(np.mean(others)))


def _chunk_mean_positive(chunk, attr: str) -> float:
    vals = [float(getattr(bar, attr)) for bar in chunk.bars if float(getattr(bar, attr)) > 0]
    if not vals:
        return 0.0
    return float(np.mean(vals))


def _raw_mean_dipole(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.asarray([_chunk_buy_sell_ratio(c) for c in ctx.chunks], dtype=float), ""


def _raw_vpin_like(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return _raw_mean_dipole(ctx)


def _raw_book_depth_imbalance(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    return np.asarray([_chunk_depth_ratio(c, "bid_qty") for c in ctx.chunks], dtype=float), ""


def _aligned_chunk_ratios(this_chunks: list, other_chunks: list,
                          value_getter) -> np.ndarray:
    if other_chunks is None:
        return np.full(len(this_chunks), np.nan, dtype=float)
    other_idx = _ts_aligned_lookup(this_chunks, other_chunks)
    out = []
    for c, oi in zip(this_chunks, other_idx):
        if oi < 0:
            out.append(float("nan"))
            continue
        out.append(value_getter(c, other_chunks[oi]))
    return np.asarray(out, dtype=float)


def _raw_cross_venue_buy_volume(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.other_venue_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no other-venue chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.other_venue_chunks,
        lambda c, oc: _dominance_ratio(
            float(sum(b.buy_vol for b in c.bars)),
            float(sum(b.buy_vol for b in oc.bars)),
        ),
    )
    return arr, ""


def _raw_cross_venue_sell_volume(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.other_venue_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no other-venue chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.other_venue_chunks,
        lambda c, oc: _dominance_ratio(
            float(sum(b.sell_vol for b in c.bars)),
            float(sum(b.sell_vol for b in oc.bars)),
        ),
    )
    return arr, ""


def _raw_perp_spot_buy_volume(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.perp_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no perp chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.perp_chunks,
        lambda c, pc: _dominance_ratio(
            float(sum(b.buy_vol for b in pc.bars)),
            float(sum(b.buy_vol for b in c.bars)),
        ),
    )
    return arr, ""


def _raw_perp_spot_sell_volume(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.perp_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no perp chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.perp_chunks,
        lambda c, pc: _dominance_ratio(
            float(sum(b.sell_vol for b in pc.bars)),
            float(sum(b.sell_vol for b in c.bars)),
        ),
    )
    return arr, ""


def _raw_cross_venue_l1_bid(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.other_venue_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no other-venue chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.other_venue_chunks,
        lambda c, oc: _dominance_ratio(
            _chunk_mean_positive(c, "bid_qty"),
            _chunk_mean_positive(oc, "bid_qty"),
        ),
    )
    return arr, ""


def _raw_cross_venue_l1_ask(ctx: MultiFeatureContext) -> tuple[np.ndarray, str]:
    if ctx.other_venue_chunks is None:
        return np.full(len(ctx.chunks), np.nan, dtype=float), "no other-venue chunks loaded"
    arr = _aligned_chunk_ratios(
        ctx.chunks,
        ctx.other_venue_chunks,
        lambda c, oc: _dominance_ratio(
            _chunk_mean_positive(c, "ask_qty"),
            _chunk_mean_positive(oc, "ask_qty"),
        ),
    )
    return arr, ""


RAW_RATIO_EXTRACTORS = {
    "mean_dipole": _raw_mean_dipole,
    "vpin_like": _raw_vpin_like,
    "book_depth_imbalance": _raw_book_depth_imbalance,
    "cross_venue_buy_volume_dipole": _raw_cross_venue_buy_volume,
    "cross_venue_sell_volume_dipole": _raw_cross_venue_sell_volume,
    "perp_spot_buy_volume_dipole": _raw_perp_spot_buy_volume,
    "perp_spot_sell_volume_dipole": _raw_perp_spot_sell_volume,
    "cross_venue_l1_bid_depth_dipole": _raw_cross_venue_l1_bid,
    "cross_venue_l1_ask_depth_dipole": _raw_cross_venue_l1_ask,
}


def _excess_kurtosis(values: np.ndarray) -> float | None:
    arr = values[np.isfinite(values)]
    if len(arr) < 4:
        return None
    mu = float(np.mean(arr))
    sd = float(np.std(arr))
    if sd < 1e-12:
        return 0.0
    z = (arr - mu) / sd
    return float(np.mean(z ** 4) - 3.0)


def _stats(values: np.ndarray) -> dict | None:
    arr = values[np.isfinite(values)]
    if len(arr) < 4:
        return None
    p50 = float(np.quantile(arr, 0.50))
    p95 = float(np.quantile(arr, 0.95))
    p99 = float(np.quantile(arr, 0.99))
    ratio = float(p99 / max(p50, 1e-9))
    kurt = _excess_kurtosis(arr)
    return {
        "n": int(len(arr)),
        "min": float(np.min(arr)),
        "mean": float(np.mean(arr)),
        "median": p50,
        "p95": p95,
        "p99": p99,
        "p99_to_p50": ratio,
        "excess_kurtosis": kurt,
    }


def _verdict(raw_stats: dict) -> str:
    ratio = float(raw_stats.get("p99_to_p50") or 0.0)
    kurt = raw_stats.get("excess_kurtosis")
    kurt_v = float(kurt) if kurt is not None else 0.0
    if ratio >= 3.0 or kurt_v >= 10.0:
        return "bounded_form_valuable"
    if ratio <= 1.5 and kurt_v <= 3.0:
        return "raw_form_well_behaved"
    return "mixed"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True)
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--chunk-max", type=int, default=30)
    p.add_argument("--chunk-min", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true")
    p.add_argument("--min-n", type=int, default=12)
    p.add_argument("--output-path", default="bounded_form_audit.json")
    args = p.parse_args()

    operationalization = [
        name for name, _group, role, _fn in FEATURE_EXTRACTORS
        if role == "operationalization" and name in SUPPORTED_OPERATIONALIZATION
    ]
    contexts = load_all_venue_contexts(
        args.asset,
        cb_bins=args.cb_bins,
        kr_bins=args.kr_bins,
        perp_bins=args.bybit_perp_bins,
        sibling_cb_bins=args.sibling_cb_bins,
        sibling_kr_bins=args.sibling_kr_bins,
        chunk_max=args.chunk_max,
        chunk_min=args.chunk_min,
        multi_pelt=args.multi_signal_pelt,
        compute_hawkes=False,
        compute_hurst=False,
        feature_names=operationalization,
    )

    findings: list[dict] = []
    summary = defaultdict(int)
    for venue_label, ctx, results in contexts:
        bounded = compute_global_feature_values(ctx, operationalization)
        raw_values = {}
        for feat in operationalization:
            extractor = RAW_RATIO_EXTRACTORS.get(feat)
            if extractor is None:
                continue
            arr, status = extractor(ctx)
            if status:
                continue
            raw_values[feat] = arr
        regimes = sorted({r.regime.value for r in results})
        for regime in regimes:
            mask = np.asarray([r.regime.value == regime for r in results], dtype=bool)
            if int(mask.sum()) < args.min_n:
                continue
            for feat in operationalization:
                if feat not in bounded or feat not in raw_values:
                    continue
                raw_stats = _stats(raw_values[feat][mask])
                bounded_stats = _stats(np.abs(bounded[feat][mask]))
                if raw_stats is None or bounded_stats is None:
                    continue
                if raw_stats["n"] < args.min_n:
                    continue
                verdict = _verdict(raw_stats)
                summary[verdict] += 1
                findings.append({
                    "cell_key": f"{venue_label}/{regime}",
                    "feature": feat,
                    "verdict": verdict,
                    "raw": raw_stats,
                    "bounded_abs": bounded_stats,
                })

    findings.sort(
        key=lambda row: (
            {"bounded_form_valuable": 0, "mixed": 1, "raw_form_well_behaved": 2}.get(
                row["verdict"], 9),
            -(row["raw"].get("p99_to_p50") or 0.0),
        )
    )
    out = {
        "schema_version": 1,
        "asset": args.asset,
        "generated_utc": int(time.time()),
        "summary": dict(summary),
        "n_findings": len(findings),
        "findings": findings,
    }
    with open(args.output_path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[bounded-audit] wrote {args.output_path} with {len(findings)} feature/cell findings")
    for verdict in ("bounded_form_valuable", "mixed", "raw_form_well_behaved"):
        print(f"  {verdict}: {summary.get(verdict, 0)}")


if __name__ == "__main__":
    main()
