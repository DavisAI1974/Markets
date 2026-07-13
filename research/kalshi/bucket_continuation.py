"""
bucket_continuation.py — the BUCKET CONTINUATION TABLE (forecaster method #1, the honest baseline).

WHAT (PATH_FORECAST_RESEARCH sec method #1 / FORECAST_AGENT_DIRECTIVE sec 7): per cell, tabulate the
historical forward-path DISTRIBUTION off the NYMEX release windows — magnitude ($/contract), front-loaded
-vs-slow-bleed shape (the S85 hold-time map), and continuation rate. The "forecast" for a new day = its
cell's realized forward distribution. Zero new machinery beyond our per-cell discipline; THE baseline every
fancier method (FPCA/GBT/HMM) must beat OOS before it is kept.

CELL KEYS (from GRAPH_LEARN_FINDINGS_S88.md — the only axes ORTHOGONAL to the Apr-Jul calendar ramp are
surprise sign/magnitude + microstructure; temp/curve/weekday collapse at n=12 and wait for the year):
  NG (storage-day):  surprise sign x magnitude  x  coiled pre-release volume {quiet|active}   [shape selector
                     = surprise-magnitude; coiled = magnitude]. Big surprise -> fast spike/short hold; small
                     -> slow grind that sustains.
  CL (inventory-day): surprise sign x magnitude  x  aligned_imb_push {support|oppose}          [imb_push =
                     the CL hold-length key, +0.52 -> sustain]. Geopolitical/vol tail kept honest via a
                     separate stored regime tag (Hormuz must not silently pool).
Temp regime + curve regime are attached as CONDITIONING tags (not split into the key at n=12); they become
key dimensions once the continuous-year library gives cross-season analogs.

OUTPUT is the CANARY (futures) forward-path forecast — the CEILING, NOT Kalshi P&L. Net-of-fee EV is
measured downstream where this feeds the hold-length overlay in lag_join.py (directive sec 8).

DISCIPLINE: per-cell distributions never a pooled mean; $/contract never bps; leakage-safe (cell features
are decision-time-available: pre-release surprise/volume + the initial-push imbalance that sizes the HOLD,
never the forward outcome); Apr-Jul warm-season / n=12 = machinery-validation ONLY, re-run on the year.

Usage:
    python research/kalshi/bucket_continuation.py --run           # fit CL+NG on the 24 weekly tapes, print
    python research/kalshi/bucket_continuation.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import event_move_baseline as emb                                    # noqa: E402

# CL crude = KXWTI series for the surprise/consensus join; NG = KXNATGASD.
CONTRACTS = [("CL", "KXWTI"), ("NG", "KXNATGASD")]
OUT_DIR = "data/forecast"
RUN_THR = 0.5                     # retention >= this = a continuation ("run"); < = blip/fade
BIG_SURPRISE = 10.0               # matches the baseline default (B for gas storage)


def _cfg(depth_dir: str = emb.MBP10_DIR) -> dict:
    return {"pre_s": 120.0, "post_s": 1800.0, "min_pre_ticks": 3, "max_anchor_gap_s": 300.0,
            "run_thr": RUN_THR, "blip_thr": 0.2, "big_surprise": BIG_SURPRISE, "min_cell": 1,
            "emit_events": True, "fast_s": 60.0, "depth": True, "depth_dir": depth_dir,
            "surprise_file": "data/eia_surprise.json"}


# ------------------------------------------------------------------------------------------------------
# enrichment (conditioning tags) + cell key
# ------------------------------------------------------------------------------------------------------
def _curve_regime(root: str, day: str) -> str:
    try:
        import forward_curve as fc
        feats = fc.load(root)
        asof = fc.curve_asof(feats, day)          # leakage-safe D-1 curve
        return asof[1]["regime"] if asof else "unknown"
    except Exception:
        return "unknown"


def _temp_regime(day: str) -> str:
    """Best-effort from the LOCAL nws cache only (no network in the table build)."""
    try:
        import nws_temp_feed as nt
        cache = nt._load_cache()
        return cache.get(day, {}).get("regime", "unknown")
    except Exception:
        return "unknown"


def enrich(events: list[dict], root: str) -> None:
    """Attach decision-time conditioning tags in-place: curve_regime, temp_regime."""
    for e in events:
        day = e.get("day", "")
        e["curve_regime"] = _curve_regime(root, day)
        e["temp_regime"] = _temp_regime(day)


def coiled_thresholds(events: list[dict]) -> dict[str, float]:
    """Per base-cell median of pre-release volume — the quiet/active split, FIT on the corpus and STORED
    (so a live/walk-forward forecast uses the train-window threshold, not a same-day statistic)."""
    by_base: dict[str, list[float]] = {}
    for e in events:
        by_base.setdefault(e["cell"], []).append(float(e.get("pre_vol", 0.0)))
    return {c: float(np.median(v)) for c, v in by_base.items() if v}


def cell_key(e: dict, root: str, thresholds: dict[str, float]) -> str:
    """Per-commodity cell. base = surprise sign x magnitude (emitted 'cell'), plus the commodity's key axis.
    Uses ONLY decision-time-available fields (surprise, pre_vol, aligned_imb_push) — never a forward outcome."""
    base = e["cell"]
    if root == "NG":
        thr = thresholds.get(base)
        coiled = "quiet" if (thr is not None and float(e.get("pre_vol", 0.0)) <= thr) else "active"
        return f"{base}|coiled={coiled}"
    # CL: the initial-push book imbalance is the hold-length key
    push = "support" if float(e.get("aligned_imb_push", 0.0)) > 0 else "oppose"
    return f"{base}|push={push}"


# ------------------------------------------------------------------------------------------------------
# tabulation — the per-cell forward-path distribution IS the forecast
# ------------------------------------------------------------------------------------------------------
def _q(arr: list[float]) -> dict:
    a = np.asarray([x for x in arr if x is not None], dtype=float)
    if a.size == 0:
        return {"p25": None, "p50": None, "p75": None, "max": None, "n": 0}
    return {"p25": round(float(np.percentile(a, 25)), 3), "p50": round(float(np.percentile(a, 50)), 3),
            "p75": round(float(np.percentile(a, 75)), 3), "max": round(float(a.max()), 3), "n": int(a.size)}


def tabulate(evs: list[dict]) -> dict:
    n = len(evs)
    ret = [float(e.get("retention", 0.0)) for e in evs]
    cont_rate = round(float(np.mean([r >= RUN_THR for r in ret])), 3) if n else None
    shape_mix: dict[str, int] = {}
    for e in evs:
        shape_mix[e.get("shape", "?")] = shape_mix.get(e.get("shape", "?"), 0) + 1
    return {
        "n": n,
        "peak_usd": _q([e.get("peak_usd") for e in evs]),
        "fast_capture_p50": round(float(np.median([e.get("fast_capture", 0.0) for e in evs])), 3) if n else None,
        "peaked_fast_frac": round(float(np.mean([bool(e.get("peaked_fast")) for e in evs])), 3) if n else None,
        "retention_p50": round(float(np.median(ret)), 3) if n else None,
        "sustain_s_p50": round(float(np.median([e.get("sustain_s", 0.0) for e in evs])), 1) if n else None,
        "time_to_peak_s_p50": round(float(np.median([e.get("time_to_peak_s", 0.0) for e in evs])), 1) if n else None,
        "continuation_rate": cont_rate,
        "shape_mix": shape_mix,
        "curve_regime_mix": _mix(evs, "curve_regime"),
        "temp_regime_mix": _mix(evs, "temp_regime"),
    }


def _mix(evs: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for e in evs:
        out[e.get(key, "unknown")] = out.get(e.get(key, "unknown"), 0) + 1
    return out


# ------------------------------------------------------------------------------------------------------
# fit / forecast
# ------------------------------------------------------------------------------------------------------
def fit(root: str, series: str, depth_dir: str = emb.MBP10_DIR) -> dict:
    res = emb.build(root, series, _cfg(depth_dir))
    if res.get("status") != "OK":
        return {"root": root, "status": res.get("status"), "msg": res.get("msg", "")}
    events = res["events"]
    enrich(events, root)
    thresholds = coiled_thresholds(events) if root == "NG" else {}
    by_cell: dict[str, list[dict]] = {}
    for e in events:
        by_cell.setdefault(cell_key(e, root, thresholds), []).append(e)
    cells = {k: tabulate(v) for k, v in sorted(by_cell.items(), key=lambda kv: -len(kv[1]))}
    return {
        "root": root, "series": series, "status": "OK",
        "n_events": len(events), "leakage_pass": res["leakage_pass"], "leakage_fails": res["leakage_fails"],
        "run_thr": RUN_THR, "thresholds": thresholds,
        "cells": cells,
        "pooled_footnote": tabulate(events),          # footnote only, never the headline
        "corpus_note": "Apr-Jul 2026 warm-season, n=12, single release-day cell; machinery-validation only "
                       "— re-run on the continuous-year MBP-10 library for tradeable cross-season cells.",
    }


def forecast(table: dict, root: str, state: dict) -> dict | None:
    """
    The forecast for a new day: match its decision-time state to a cell, return that cell's forward
    distribution. Falls back to the pooled footnote if the specific cell is absent/too thin.
    state must carry the same decision-time fields cell_key uses: {cell, pre_vol} (NG) or {cell,
    aligned_imb_push} (CL).
    """
    key = cell_key(state, root, table.get("thresholds", {}))
    cell = table.get("cells", {}).get(key)
    if cell and cell["n"] >= 2:
        return {"matched_cell": key, "n": cell["n"], **cell, "fallback": False}
    return {"matched_cell": key, "fallback": True, **table.get("pooled_footnote", {})}


# ------------------------------------------------------------------------------------------------------
# selftest
# ------------------------------------------------------------------------------------------------------
def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # quantile + continuation math on a known set
    evs = [{"peak_usd": 100, "retention": 0.9, "shape": "run", "fast_capture": 0.7, "peaked_fast": True,
            "sustain_s": 600, "time_to_peak_s": 30},
           {"peak_usd": 200, "retention": 0.1, "shape": "blip", "fast_capture": 0.3, "peaked_fast": False,
            "sustain_s": 100, "time_to_peak_s": 900},
           {"peak_usd": 300, "retention": 0.8, "shape": "run", "fast_capture": 0.6, "peaked_fast": False,
            "sustain_s": 500, "time_to_peak_s": 60}]
    t = tabulate(evs)
    check("peak_usd p50 = 200", t["peak_usd"]["p50"] == 200.0)
    check("continuation_rate = 2/3", t["continuation_rate"] == round(2 / 3, 3))
    check("peaked_fast_frac = 1/3", t["peaked_fast_frac"] == round(1 / 3, 3))

    # coiled threshold split is a per-base-cell median, STORED
    ce = [{"cell": "X|beat|big", "pre_vol": 100}, {"cell": "X|beat|big", "pre_vol": 300},
          {"cell": "X|beat|big", "pre_vol": 500}]
    thr = coiled_thresholds(ce)
    check("coiled threshold = median (300)", thr["X|beat|big"] == 300.0)
    check("NG cell quiet below median",
          cell_key({"cell": "X|beat|big", "pre_vol": 100}, "NG", thr).endswith("coiled=quiet"))
    check("NG cell active above median",
          cell_key({"cell": "X|beat|big", "pre_vol": 500}, "NG", thr).endswith("coiled=active"))

    # CL push bucket
    check("CL push=support when imb_push>0",
          cell_key({"cell": "Y|miss|small", "aligned_imb_push": 0.3}, "CL", {}).endswith("push=support"))
    check("CL push=oppose when imb_push<=0",
          cell_key({"cell": "Y|miss|small", "aligned_imb_push": -0.1}, "CL", {}).endswith("push=oppose"))

    # LEAKAGE (structural): cell_key must be invariant to any forward-outcome field being changed.
    base_ev = {"cell": "X|beat|big", "pre_vol": 100, "aligned_imb_push": 0.2}
    k1 = cell_key(dict(base_ev), "NG", thr)
    poisoned = dict(base_ev, peak_usd=9999, retention=0.0, sustain_s=0, fast_capture=1.0)  # future outcomes
    k2 = cell_key(poisoned, "NG", thr)
    check("cell assignment invariant to forward-outcome fields (leakage gate)", k1 == k2)

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _print_table(res: dict) -> None:
    if res.get("status") != "OK":
        print(f"[{res['root']}] {res.get('status')}: {res.get('msg','')}")
        return
    print(f"\n[{res['root']}/{res['series']}] events={res['n_events']}  leakage_pass={res['leakage_pass']} "
          f"(fails={res['leakage_fails']})  cells={len(res['cells'])}")
    for k, d in res["cells"].items():
        pu = d["peak_usd"]
        print(f"  CELL {k}  n={d['n']}")
        print(f"    peak_usd p25/p50/p75/max = {pu['p25']}/{pu['p50']}/{pu['p75']}/{pu['max']}  "
              f"fast_capture p50={d['fast_capture_p50']}  peaked_fast={d['peaked_fast_frac']}")
        print(f"    sustain_s p50={d['sustain_s_p50']}  time_to_peak p50={d['time_to_peak_s_p50']}  "
              f"retention p50={d['retention_p50']}  continuation={d['continuation_rate']}  {d['shape_mix']}")
    print(f"  (footnote pooled n={res['pooled_footnote']['n']}, "
          f"peak_usd p50={res['pooled_footnote']['peak_usd']['p50']} — never the headline)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Bucket continuation table (forecaster baseline, method #1)")
    ap.add_argument("--run", action="store_true", help="fit CL+NG on the weekly tapes, print + write JSON")
    ap.add_argument("--depth-dir", default=emb.MBP10_DIR)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.run:
        os.makedirs(OUT_DIR, exist_ok=True)
        for root, series in CONTRACTS:
            res = fit(root, series, args.depth_dir)
            _print_table(res)
            json.dump(res, open(os.path.join(OUT_DIR, f"bucket_table_{root}.json"), "w"), indent=2)
        print(f"\n[bucket] tables -> {OUT_DIR}/bucket_table_{{CL,NG}}.json")
        return 0
    ap.error("need --run or --selftest")


if __name__ == "__main__":
    sys.exit(main())
