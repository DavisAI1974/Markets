"""
forward_curve.py — the NYMEX forward-CURVE reader: backwardation/contango + prompt-vs-term conditioning
axis for the path forecaster (S88, FORECAST_AGENT_DIRECTIVE sec 12 / kickoff priority 2).

WHY: the curve SHAPE is a slow-moving structural conditioning axis for the intraday forecast. Backwardation
(front > deferred = tight prompt supply, geopolitical/CL-heavy) vs contango (front < deferred = ample
prompt/storage glut) sets how a catalyst propagates. NG carries a strong SEASONAL curve (winter premium)
the flat degree-day read misses. This is a CONDITIONING driver, not a standalone signal.

DATA: Databento GLBX.MDP3 continuous CALENDAR-RANK contracts CL.c.0..c.N / NG.c.0..c.N (c = nearest-expiry
roll, so rank == horizon), schema ohlcv-1d (daily bars; close ~ settle). The curve is a daily object, so
daily bars are the right/cheapest granularity (~$0.07/yr for both, 12 ranks) — no intraday needed.

LEAKAGE: a daily bar is end-of-session. The curve KNOWN at the morning of day D is D-1's settle. So
decision-time conditioning uses curve_asof(D) = the latest curve STRICTLY BEFORE D. Never same-day.

Cache: data/nymex_curve/<ROOT>_curve.json (gitignored, re-pullable at $0.07). Restored/rebuilt on demand.

Usage:
    DATABENTO_API_KEY=... python research/kalshi/forward_curve.py --pull --start 2025-07-01 --end 2026-07-01
    python research/kalshi/forward_curve.py --selftest
    python research/kalshi/forward_curve.py --show CL           # print cached curve features
"""
from __future__ import annotations

import argparse
import json
import os
import sys

CACHE_DIR = "data/nymex_curve"
N_RANKS = 12
MAX_COST = 1.0                       # daily bars are ~$0.07/yr; gate well above, abort on surprise


def _cache_path(root: str) -> str:
    return os.path.join(CACHE_DIR, f"{root}_curve.json")


# ------------------------------------------------------------------------------------------------------
# Curve metrics (pure, testable)
# ------------------------------------------------------------------------------------------------------
def curve_features(closes: dict[int, float], symbols: dict[int, str] | None = None) -> dict | None:
    """
    closes: {rank: settle} for one date (rank 0 = nearest expiry). Returns the conditioning features, or
    None if the front two ranks are missing. All spreads in $ (never bps); shape sign is the read.

    symbols: optional {rank: raw_symbol} (e.g. {0: "NGG26", 1: "NGH26"}). When supplied, the
    MONTH-SPECIFIC spreads are added — notably `mar_apr_spread` (NGH - NGJ), the most-watched
    structural spread in NG (the end of withdrawal season). Missing is None, never 0.0.
    """
    if 0 not in closes or 1 not in closes:
        return None
    front = closes[0]
    c1 = closes[1]
    ranks = sorted(closes)
    back = closes[ranks[-1]]
    # near slope: deferred - front. >0 contango (deferred richer), <0 backwardation (front premium).
    slope_1 = c1 - front
    slope_back = back - front
    # normalized (fraction of front) — comparable across price levels / commodities
    slope_1_pct = slope_1 / front if front else 0.0
    slope_back_pct = slope_back / front if front else 0.0
    # curvature: is the curve bowed (seasonal hump) vs monotone? mid vs chord.
    mid_rank = ranks[len(ranks) // 2]
    chord = front + (back - front) * (mid_rank / ranks[-1]) if ranks[-1] else front
    curvature = closes[mid_rank] - chord
    if slope_1 < 0:
        regime = "backwardation"
    elif slope_1 > 0:
        regime = "contango"
    else:
        regime = "flat"
    # MONTH-SPECIFIC structural spreads. NG month codes: F=Jan G=Feb H=Mar J=Apr K=May ... Z=Dec.
    # mar_apr (H-J) straddles the end of the withdrawal season and is NG's most-watched spread.
    # A month pair that is not on the curve stays None - NEVER 0.0 (0.0 reads as "at parity").
    month_spreads: dict[str, float | None] = {"mar_apr_spread": None, "mar_apr_pair": None}
    if symbols:
        by_sym = {}
        for rk, sym in symbols.items():
            if rk in closes and sym:
                by_sym[str(sym).upper()] = closes[rk]
        # take the FRONT-MOST H/J pair of the same delivery year present on the curve
        for yr in sorted({s[3:] for s in by_sym if len(s) >= 5 and s.startswith("NG")}):
            h, j = f"NGH{yr}", f"NGJ{yr}"
            if h in by_sym and j in by_sym:
                month_spreads["mar_apr_spread"] = round(by_sym[h] - by_sym[j], 4)
                month_spreads["mar_apr_pair"] = f"{h}-{j}"
                break

    return {
        **month_spreads,
        "symbols": {str(k): v for k, v in (symbols or {}).items()} or None,
        "front": round(front, 4), "c1": round(c1, 4), "back_rank": ranks[-1], "back": round(back, 4),
        "slope_1": round(slope_1, 4), "slope_back": round(slope_back, 4),
        "slope_1_pct": round(slope_1_pct, 6), "slope_back_pct": round(slope_back_pct, 6),
        "curvature": round(curvature, 4), "regime": regime, "n_ranks": len(closes),
    }


def curve_asof(features_by_date: dict[str, dict], date: str) -> tuple[str, dict] | None:
    """
    LEAKAGE-SAFE decision-time read: the latest curve STRICTLY BEFORE `date` (D-1 settle is what the
    morning of D knows). Returns (asof_date, features) or None.
    """
    prior = [d for d in features_by_date if d < date]
    if not prior:
        return None
    d = max(prior)
    return d, features_by_date[d]


# ------------------------------------------------------------------------------------------------------
# Pull (Databento) + cache
# ------------------------------------------------------------------------------------------------------
def pull(root: str, start: str, end: str, n_ranks: int = N_RANKS) -> dict[str, dict]:
    """
    Pull daily bars for {root}.c.0..c.{n-1} over [start, end), build per-date curve features, cache.
    Returns {date: features}.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import databento_backfill as dbf

    client = dbf._client()
    syms = [f"{root}.c.{i}" for i in range(n_ranks)]
    cost = client.metadata.get_cost(dataset=dbf.DATASET, symbols=syms, stype_in="continuous",
                                    schema="ohlcv-1d", start=start, end=end)
    print(f"[curve] {root} est. cost ${cost:.4f} ({n_ranks} ranks {start}..{end})")
    if cost > MAX_COST:
        raise SystemExit(f"[curve] over --max-cost ${MAX_COST}; aborting")
    data = client.timeseries.get_range(dataset=dbf.DATASET, symbols=syms, stype_in="continuous",
                                       schema="ohlcv-1d", start=start, end=end)
    # rank per raw symbol; map each record's instrument back to its continuous rank via the symbol
    closes_by_date: dict[str, dict[int, float]] = {}
    syms_by_date: dict[str, dict[int, str]] = {}
    df = data.to_df()
    # to_df carries a 'symbol' column with the continuous alias (e.g. 'CL.c.3'). Resolve each rank's
    # ACTUAL delivery contract (e.g. 'NGH26') via the per-day instrument map so month-specific
    # structural spreads (mar_apr) can be taken. Unresolvable -> the rank simply carries no symbol.
    instmap = _instrument_map(root)
    for _, row in df.iterrows():
        sym = str(row.get("symbol", ""))
        if ".c." not in sym:
            continue
        rank = int(sym.rsplit(".", 1)[1])
        date = row.name.strftime("%Y-%m-%d") if hasattr(row.name, "strftime") else str(row.name)[:10]
        closes_by_date.setdefault(date, {})[rank] = float(row["close"])
        iid = row.get("instrument_id")
        raw = instmap.get(date.replace("-", ""), {}).get(str(int(iid))) if iid is not None else None
        if raw:
            syms_by_date.setdefault(date, {})[rank] = raw
    features = {}
    for date, closes in sorted(closes_by_date.items()):
        f = curve_features(closes, syms_by_date.get(date))
        if f:
            features[date] = f
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(root), "w") as fh:
        json.dump(features, fh, sort_keys=True, indent=0)
    print(f"[curve] {root}: {len(features)} dated curves -> {_cache_path(root)}")
    return features


def _instrument_map(root: str) -> dict:
    """{'YYYYMMDD': {instrument_id_str: raw_symbol}} from the contract_structure definitions cache.
    Absent cache -> {} (ranks then carry no symbol; month spreads stay None, never 0)."""
    p = os.path.join("data/contract_structure", f"{root}_instrument_map.json.gz")
    if not os.path.exists(p):
        return {}
    try:
        import gzip
        with gzip.open(p, "rt") as f:
            return json.load(f).get("per_day", {})
    except Exception:
        return {}


def load(root: str) -> dict[str, dict]:
    p = _cache_path(root)
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------------------
# selftest
# ------------------------------------------------------------------------------------------------------
def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # backwardation: front above deferred -> slope_1 < 0
    back = curve_features({0: 80.0, 1: 79.0, 2: 78.5, 11: 76.0})
    check("backwardation regime", back["regime"] == "backwardation")
    check("backwardation slope_1 < 0", back["slope_1"] == -1.0)
    check("backwardation slope_back < 0", back["slope_back"] == -4.0)

    # contango: front below deferred -> slope_1 > 0
    cont = curve_features({0: 3.0, 1: 3.2, 2: 3.4, 11: 4.5})
    check("contango regime", cont["regime"] == "contango")
    check("contango slope_1 > 0", cont["slope_1"] == 0.2)

    # missing front two -> None
    check("missing ranks -> None", curve_features({0: 3.0}) is None)

    # LEAKAGE: curve_asof returns the STRICTLY-PRIOR date only
    feats = {"2025-07-01": {"x": 1}, "2025-07-02": {"x": 2}, "2025-07-03": {"x": 3}}
    asof = curve_asof(feats, "2025-07-03")
    check("asof strictly-prior (no same-day leak)", asof is not None and asof[0] == "2025-07-02")
    check("asof before earliest -> None", curve_asof(feats, "2025-07-01") is None)

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="NYMEX forward-curve reader (backwardation/contango axis)")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--start", help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", help="YYYY-MM-DD exclusive")
    ap.add_argument("--roots", default="CL,NG")
    ap.add_argument("--ranks", type=int, default=N_RANKS)
    ap.add_argument("--show", help="print cached curve for a root (CL/NG)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.show:
        feats = load(args.show)
        for d in sorted(feats):
            v = feats[d]
            print(f"  {d}  front {v['front']:8.3f}  slope1 {v['slope_1']:+7.3f}  "
                  f"slopeBack {v['slope_back']:+7.3f}  curv {v['curvature']:+6.3f}  {v['regime']}")
        print(f"[curve] {len(feats)} dated curves for {args.show}")
        return 0
    if args.pull:
        if not (args.start and args.end):
            ap.error("--pull needs --start and --end")
        for root in args.roots.split(","):
            pull(root.strip(), args.start, args.end, args.ranks)
        return 0
    ap.error("need --pull / --show / --selftest")


if __name__ == "__main__":
    sys.exit(main())
