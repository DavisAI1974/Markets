"""
event_move_baseline.py — the NYMEX-canary EVENT-MOVE baseline (S85).

Expectation-setting, NOT a trade-fire signal. NYMEX is the canary (NYMEX_CANARY_NOTES_S84.md): the
release move happens on the futures tape first, then reprices onto Kalshi seconds-to-a-minute later.
Before we can size the lagged Kalshi scalp we have to know, per surprise-cell, what the CANARY move
itself looks like: how BIG (magnitude) and how LONG it lasts (a blip that reverts vs a run that holds).
This measures exactly that on the TRUE-TICK futures tape (Databento `trades`, every print).

For each scheduled release event with a tape around it we anchor a strictly-pre-release baseline and
measure the forward move:
  MAGNITUDE  peak absolute displacement from the baseline within [R, R+post], reported three ways —
             TICKS (peak_abs / tick_size), DOLLARS (ticks x tick_value), and BPS (peak_abs/baseline*1e4).
             Plus the signed net displacement at R+post.
  DURATION   time_to_peak (s); sustain_s = how long the move holds >= half the peak before it first
             decays back (the "run length" in seconds; right-censored if it never decays in-window);
             retention = |net_end| / peak_abs (1.0 = a run that fully held, ~0 = a blip that round-tripped)
             -> shape in {run, fade, blip}. `blip-vs-run-is-the-duration`.

Everything is reported as DISTRIBUTIONS per cell (quantiles + the run/blip/fade mix), never a lone mean.
Cell = series x surprise-sign x surprise-magnitude (surprise = actual - forecast from the consensus feed;
falls back to 'unknown' when consensus/actual are missing — the unconditional per-series move IS the
coarsest expectation, partial coverage is not failure). `each-trade-individually-never-average`,
`per-cell-never-pool`.

TICK SIZE + VALUE are POINT-IN-TIME from Databento's `definition` schema (min_price_increment x
unit_of_measure_qty), read from data/pyth_ticks/{ROOT}_definitions.jsonl (populate it with
`databento_backfill.py --schema definition`). If that store is absent we fall back to a REFERENCE spec
but tag every move `tick_source=reference_unverified` so it is never silently trusted — the canary notes
are explicit that the reference is to VERIFY against, not to hardcode.

Discipline: the leakage gate (odcore.leakage.assert_no_leakage) runs on the strictly-pre-release anchor
closure BEFORE any distribution — the baseline + pre-vol computed 'as of R' must be invariant to every
tick after R. The forward move metrics are descriptive OUTCOMES (post-event), not predictive features.
Settle window: releases (14:30 UTC) sit well before the 21:00/22:00 UTC daily settle, and the forward
window is capped at post seconds, so it never runs into settle. Zero synthetic. Provisional-until-live.

Usage:
    python research/kalshi/event_move_baseline.py --symbol NG --series KXNATGASD --out data/event_move_NG.json
    python research/kalshi/event_move_baseline.py --symbol CL --series KXWTI --pre 120 --post 1800
    python research/kalshi/event_move_baseline.py --selftest      # math + leakage-closure unit check
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _ROOT)
from odcore.leakage import assert_no_leakage            # noqa: E402

TAPE_DIR = "data/pyth_ticks"
CONSENSUS = "data/kalshi/consensus.jsonl"

# symbol -> underlying ROOT (for the definition store, reference spec, and release calendar).
def sym_root(symbol: str) -> str:
    s = symbol.upper()
    if s.startswith("NG"):
        return "NG"
    if s.startswith(("CL", "WTI")):
        return "CL"
    if s.startswith("BRENT") or s.startswith("BZ"):
        return "BRENT"
    return s

# Scheduled release (UTC hh, mm, weekday 0=Mon..6=Sun) per ROOT — the catalyst.
# EIA weekly natgas storage Thu 10:30 ET = 14:30 UTC; EIA weekly crude Wed 10:30 ET = 14:30 UTC.
RELEASE_BY_ROOT = {"NG": (14, 30, 3), "CL": (14, 30, 2), "BRENT": (14, 30, 2)}

# REFERENCE tick specs — TO VERIFY against the definition schema, NEVER the source of truth. Only used
# (and loudly tagged) when the definition store is missing. CL: $0.01/bbl x 1000 bbl = $10/tick.
# NG: $0.001/MMBtu x 10000 MMBtu = $10/tick.
REFERENCE_TICKS = {
    "CL": {"tick_size": 0.01, "unit_qty": 1000.0},
    "NG": {"tick_size": 0.001, "unit_qty": 10000.0},
    "BRENT": {"tick_size": 0.01, "unit_qty": 1000.0},
}

# consensus-forecast series -> the numeric surprise unit is native to the release (B for gas storage,
# M for crude inventories). We parse the number and its sign; magnitude bucketing is relative.
_NUM_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")


# ---- tape + definitions --------------------------------------------------------------------------
def _parse_ts(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def load_tape(symbol: str):
    """All ticks for a symbol across day-files -> time-sorted (ts, price, size) arrays, dedup on ts.

    Consumes the {ts,price,size,symbol,src} shape written by databento_backfill / pyth_backfill / the
    live collector identically."""
    paths = sorted(glob.glob(os.path.join(TAPE_DIR, f"{symbol}_*.jsonl")))
    paths = [p for p in paths if "_definitions" not in os.path.basename(p)]
    rows = []
    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("price") is None or r.get("ts") is None:
                continue
            rows.append((_parse_ts(r["ts"]), float(r["price"]), float(r.get("size") or 0.0)))
    if not rows:
        return np.array([]), np.array([]), np.array([])
    rows.sort(key=lambda x: x[0])
    ts = np.array([r[0] for r in rows], float)
    p = np.array([r[1] for r in rows], float)
    sz = np.array([r[2] for r in rows], float)
    # dedup exact-duplicate timestamps (keep last), keeps the leakage permutation well-defined
    keep = np.concatenate([np.diff(ts) > 0, [True]])
    return ts[keep], p[keep], sz[keep]


def load_defs(root: str):
    """Point-in-time tick definitions for a ROOT -> list of (ts_effective, tick_size, tick_value),
    time-sorted. Empty if the store is absent (caller falls back to the reference spec)."""
    path = os.path.join(TAPE_DIR, f"{root}_definitions.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = r.get("ts")
        tsz = r.get("tick_size")
        if ts is None or tsz is None:
            continue
        tval = r.get("tick_value")
        if tval is None and r.get("unit_qty") is not None:
            tval = float(tsz) * float(r["unit_qty"])
        out.append((_parse_ts(ts), float(tsz), float(tval) if tval is not None else None))
    out.sort(key=lambda x: x[0])
    return out


def tick_spec_at(root: str, event_ts: float, defs):
    """The tick (size, value, source) in effect AT event_ts — the latest definition row <= event_ts.
    Falls back to the reference spec (loudly tagged) when no definition covers the event."""
    chosen = None
    for ts_eff, tsz, tval in defs:
        if ts_eff <= event_ts:
            chosen = (tsz, tval)
        else:
            break
    if chosen is not None and chosen[1] is not None:
        return chosen[0], chosen[1], "definition"
    ref = REFERENCE_TICKS.get(root)
    if ref is None:
        return None, None, "unknown"
    return ref["tick_size"], ref["tick_size"] * ref["unit_qty"], "reference_unverified"


# ---- consensus / surprise --------------------------------------------------------------------------
def parse_number(s):
    """'-0.1%' -> -0.1 ; '3.0M' -> 3.0 ; '61B' -> 61.0 ; None/'' -> None. Unit-agnostic (compared
    within the same release only), sign preserved."""
    if s is None:
        return None
    m = _NUM_RE.match(str(s))
    return float(m.group(1)) if m else None


def load_consensus():
    """series -> list of {day (UTC date), forecast, actual} from the consensus feed. A release's
    surprise = actual - forecast, keyed to the release day."""
    by_series = defaultdict(list)
    if not os.path.exists(CONSENSUS):
        return by_series
    for line in open(CONSENSUS):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        dt = r.get("date")
        if not dt:
            continue
        try:
            day = datetime.fromisoformat(dt).astimezone(timezone.utc).date().isoformat()
        except ValueError:
            continue
        f = parse_number(r.get("forecast"))
        a = parse_number(r.get("actual"))
        for series in (r.get("series") or []):
            by_series[series].append({"day": day, "forecast": f, "actual": a,
                                      "title": r.get("title")})
    return by_series


def surprise_for(series, day, consensus):
    """(forecast, actual, surprise) for a release on `day` (UTC ISO date), or (None,None,None)."""
    for row in consensus.get(series, []):
        if row["day"] == day and row["forecast"] is not None and row["actual"] is not None:
            return row["forecast"], row["actual"], row["actual"] - row["forecast"]
    return None, None, None


def surprise_cell(series, surprise, big_abs):
    """Cell suffix from the surprise. 'unknown' when we lack consensus+actual (still a valid, coarser
    per-series cell — partial coverage is not failure)."""
    if surprise is None:
        return f"{series}|surprise=unknown"
    sign = "beat" if surprise > 0 else ("miss" if surprise < 0 else "inline")
    mag = "big" if abs(surprise) >= big_abs else "small"
    return f"{series}|{sign}|{mag}"


# ---- pre-release anchor (the ONLY pre-event quantity; leakage-gated) -------------------------------
def anchor_at(rel_idx, ts, p, pre_s):
    """Baseline price + pre-release volatility 'as of the release index' — reads only ticks <= rel_idx.

    baseline = last trade price at/just before R (point-in-time anchor). pre_vol = std of tick log-returns
    over [R-pre_s, R] (context/normalizer). MUST be invariant to any tick after rel_idx — that is what the
    leakage gate asserts."""
    if rel_idx < 1:
        return None
    baseline = float(p[rel_idx])
    lo = rel_idx
    t0 = ts[rel_idx] - pre_s
    while lo > 0 and ts[lo - 1] >= t0:
        lo -= 1
    seg = p[lo:rel_idx + 1]
    if seg.size >= 3:
        rets = np.diff(np.log(seg))
        pre_vol = float(np.std(rets)) if rets.size else 0.0
    else:
        pre_vol = 0.0
    return {"baseline": baseline, "pre_vol": pre_vol, "n_pre": int(rel_idx - lo + 1)}


def _anchor_scalar(i, ts, p, bv, sv, pre_s):
    """Collapse the pre-release anchor to one scalar for the leakage gate (baseline + pre_vol)."""
    a = anchor_at(i, ts, p, pre_s)
    if a is None:
        return None
    return round(a["baseline"] * 1e4 + a["pre_vol"] * 1e6, 4)


# ---- forward move metrics (descriptive outcome; post-event) ---------------------------------------
def move_metrics(rel_idx, ts, p, baseline, tick_size, tick_value, post_s, run_thr, blip_thr):
    """Magnitude + duration of the forward move in [R, R+post]. All displacements vs the pre-release
    baseline. Returns None if the window has too few forward ticks."""
    R = ts[rel_idx]
    hi = rel_idx
    horizon = R + post_s
    while hi + 1 < len(ts) and ts[hi + 1] <= horizon:
        hi += 1
    if hi - rel_idx < 3:                           # need a real forward window
        return None
    fts = ts[rel_idx:hi + 1]
    disp = p[rel_idx:hi + 1] - baseline            # signed displacement path
    k_peak = int(np.argmax(np.abs(disp)))
    peak = float(disp[k_peak])                      # signed peak displacement
    peak_abs = abs(peak)
    sgn = 1.0 if peak >= 0 else -1.0
    net_end = float(disp[-1])                        # signed displacement at R+post
    time_to_peak = float(fts[k_peak] - R)
    # sustain: from the peak, time until |disp| first falls below half the peak (the run length in s).
    half = 0.5 * peak_abs
    sustain_s = float(fts[-1] - fts[k_peak])
    censored = True
    for k in range(k_peak, len(disp)):
        if abs(disp[k]) < half:
            sustain_s = float(fts[k] - fts[k_peak]); censored = False
            break
    retention = (net_end * sgn) / peak_abs if peak_abs > 0 else 0.0   # signed toward the peak dir
    shape = "run" if retention >= run_thr else ("blip" if retention < blip_thr else "fade")
    ticks = peak_abs / tick_size if tick_size else float("nan")
    return {
        "peak_bps": round(peak_abs / baseline * 1e4, 2) if baseline else None,
        "peak_signed_bps": round(peak / baseline * 1e4, 2) if baseline else None,
        "peak_ticks": round(ticks, 2),
        "peak_usd": round(ticks * tick_value, 2) if tick_value else None,
        "net_end_bps": round(net_end / baseline * 1e4, 2) if baseline else None,
        "time_to_peak_s": round(time_to_peak, 1),
        "sustain_s": round(sustain_s, 1),
        "sustain_censored": bool(censored),
        "retention": round(float(retention), 3),
        "shape": shape,
        "n_fwd": int(hi - rel_idx + 1),
    }


# ---- event enumeration --------------------------------------------------------------------------
def tape_days(ts):
    return sorted({datetime.fromtimestamp(t, timezone.utc).date() for t in ts})


def build(symbol, series, cfg):
    ts, p, sz = load_tape(symbol)
    if ts.size == 0:
        return {"symbol": symbol, "status": "NO_DATA",
                "msg": f"no tape in {os.path.join(TAPE_DIR, symbol + '_*.jsonl')} — "
                       f"run databento_backfill.py (needs DATABENTO_API_KEY) first"}
    root = sym_root(symbol)
    rel = RELEASE_BY_ROOT.get(root)
    if rel is None:
        return {"symbol": symbol, "status": "NO_RELEASE_CAL", "msg": f"no release calendar for root {root}"}
    rhh, rmm, rwd = rel
    defs = load_defs(root)
    consensus = load_consensus()

    # one event per release-weekday present in the tape
    events = []
    for d in tape_days(ts):
        if d.weekday() != rwd:
            continue
        R = datetime(d.year, d.month, d.day, rhh, rmm, tzinfo=timezone.utc).timestamp()
        # release index = last tick at/before R (the anchor point); require ticks on both sides.
        idx = int(np.searchsorted(ts, R, side="right") - 1)
        if idx < 1 or idx >= len(ts) - 1:
            continue
        if abs(ts[idx] - R) > cfg["max_anchor_gap_s"]:     # tape doesn't actually cover the release
            continue
        anc = anchor_at(idx, ts, p, cfg["pre_s"])
        if anc is None or anc["n_pre"] < cfg["min_pre_ticks"]:
            continue
        tsz, tval, tsrc = tick_spec_at(root, R, defs)
        if tsz is None:
            continue
        mv = move_metrics(idx, ts, p, anc["baseline"], tsz, tval,
                          cfg["post_s"], cfg["run_thr"], cfg["blip_thr"])
        if mv is None:
            continue
        f, a, surp = surprise_for(series, d.isoformat(), consensus)
        events.append({"day": d.isoformat(), "release_idx": idx,
                       "baseline": round(anc["baseline"], 5), "pre_vol": round(anc["pre_vol"], 6),
                       "n_pre": anc["n_pre"], "tick_size": tsz, "tick_value": tval,
                       "tick_source": tsrc, "forecast": f, "actual": a, "surprise": surp,
                       "cell": surprise_cell(series, surp, cfg["big_surprise"]), **mv})

    if not events:
        return {"symbol": symbol, "status": "NO_EVENTS",
                "msg": f"tape present but no release-weekday ({rwd}) windows covered "
                       f"(days={len(tape_days(ts))}, ticks={ts.size})"}

    # leakage gate on the pre-release anchor closure at the real release indices
    idxs = [e["release_idx"] for e in events][:12]
    idxs = [i for i in idxs if cfg["pre_s"] and i >= 2 and i < len(p) - 1]
    if len(idxs) >= 2:
        bv = sz; sv = np.zeros_like(sz)
        leak_pass, fails = assert_no_leakage(
            lambda i, ts_, p_, bv_, sv_: _anchor_scalar(i, ts_, p_, bv_, sv_, cfg["pre_s"]),
            ts, p, bv, sv, idxs, reps=3, seed=0)
        leak_pass, leak_fails = bool(leak_pass), len(fails)
    else:
        leak_pass, leak_fails = True, 0

    # per-cell distributions (never pooled; the pooled line appears only as a footnote)
    by_cell = defaultdict(list)
    for e in events:
        by_cell[e["cell"]].append(e)
    cells = {}
    for k, evs in sorted(by_cell.items(), key=lambda kv: -len(kv[1])):
        if len(evs) < cfg["min_cell"]:
            continue
        cells[k] = _move_dist(evs)
    src_counts = defaultdict(int)               # tick-source is PER EVENT (roll/definition-window), aggregate it
    for e in events:
        src_counts[e["tick_source"]] += 1
    return {
        "symbol": symbol, "series": series, "status": "OK",
        "n_events": len(events), "tape_days": len(tape_days(ts)), "ticks": int(ts.size),
        "tick_source": dict(src_counts),
        "leakage_pass": leak_pass, "leakage_fails": leak_fails,
        "n_cells_reported": len(cells),
        "cells": cells,
        "pooled_footnote": _move_dist(events),          # footnote only, never the headline
        "events": events if cfg["emit_events"] else None,
        "cfg": {k: v for k, v in cfg.items()},
    }


def _q(a, ps):
    return {f"p{p}": round(float(np.percentile(a, p)), 3) for p in ps}


def _move_dist(evs):
    """Distribution summary of a cell's event moves — quantiles + the run/blip/fade mix, NOT a lone mean."""
    n = len(evs)
    peak_bps = np.array([e["peak_bps"] for e in evs], float)
    peak_ticks = np.array([e["peak_ticks"] for e in evs], float)
    peak_usd = np.array([e["peak_usd"] for e in evs if e["peak_usd"] is not None], float)
    ttp = np.array([e["time_to_peak_s"] for e in evs], float)
    sustain = np.array([e["sustain_s"] for e in evs], float)
    retention = np.array([e["retention"] for e in evs], float)
    shapes = defaultdict(int)
    for e in evs:
        shapes[e["shape"]] += 1
    dirs = defaultdict(int)
    for e in evs:
        dirs["up" if (e["peak_signed_bps"] or 0) >= 0 else "down"] += 1
    return {
        "n": n,
        "peak_bps": {**_q(peak_bps, [10, 50, 90]), "max": round(float(peak_bps.max()), 2)},
        "peak_ticks": {**_q(peak_ticks, [10, 50, 90]), "max": round(float(peak_ticks.max()), 2)},
        "peak_usd": ({**_q(peak_usd, [10, 50, 90]), "max": round(float(peak_usd.max()), 2)}
                     if peak_usd.size else None),
        "time_to_peak_s": _q(ttp, [10, 50, 90]),
        "sustain_s": _q(sustain, [10, 50, 90]),
        "retention": _q(retention, [10, 50, 90]),
        "shape_mix": {k: round(v / n, 3) for k, v in shapes.items()},
        "dir_mix": {k: round(v / n, 3) for k, v in dirs.items()},
    }


# ---- selftest (math + leakage-closure unit check; NOT trading data) -------------------------------
def selftest():
    """Deterministic unit check of the conversion math and the leakage closure. Uses a constructed ramp
    array — a CODE test of the tool, not synthetic trading data (no cell/distribution is emitted)."""
    ok = True
    # 1. tick/$/bps conversion on a known NG-style move: baseline 3.000, peak +0.030 = 30 ticks @ $10.
    ts = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], float)
    p = np.array([3.000, 3.000, 3.000, 3.010, 3.020, 3.030, 3.028, 3.026, 3.024, 3.022, 3.020], float)
    mv = move_metrics(2, ts, p, baseline=3.000, tick_size=0.001, tick_value=10.0,
                      post_s=20, run_thr=0.5, blip_thr=0.2)
    exp_ticks = 30.0
    if mv is None or abs(mv["peak_ticks"] - exp_ticks) > 1e-6:
        print(f"  FAIL peak_ticks: {mv and mv['peak_ticks']} != {exp_ticks}"); ok = False
    else:
        print(f"  ok  peak_ticks={mv['peak_ticks']} peak_usd={mv['peak_usd']} "
              f"peak_bps={mv['peak_bps']} shape={mv['shape']} retention={mv['retention']} "
              f"sustain_s={mv['sustain_s']}")
    if mv and abs(mv["peak_usd"] - 300.0) > 1e-6:
        print(f"  FAIL peak_usd: {mv['peak_usd']} != 300.0"); ok = False
    if mv and abs(mv["peak_bps"] - 100.0) > 1e-6:                   # 0.030/3.000*1e4 = 100 bps
        print(f"  FAIL peak_bps: {mv['peak_bps']} != 100.0"); ok = False
    # 2. leakage closure: the anchor at the release index must be invariant to ticks AFTER it.
    bv = np.ones_like(p); sv = np.zeros_like(p)
    leak_pass, fails = assert_no_leakage(
        lambda i, ts_, p_, bv_, sv_: _anchor_scalar(i, ts_, p_, bv_, sv_, pre_s=5),
        ts, p, bv, sv, idxs=[3, 5, 7], reps=3, seed=0)
    if leak_pass:
        print("  ok  leakage closure invariant to post-index ticks (3/3)")
    else:
        print(f"  FAIL leakage: {fails}"); ok = False
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description="NYMEX-canary EVENT-MOVE baseline (magnitude + duration)")
    ap.add_argument("--symbol", default="NG", help="tape symbol (NG/CL or a raw contract like NGDQ6)")
    ap.add_argument("--series", default="KXNATGASD", help="Kalshi series (for the surprise/consensus join)")
    ap.add_argument("--pre", type=float, default=120.0, dest="pre_s", help="pre-release anchor/vol window (s)")
    ap.add_argument("--post", type=float, default=1800.0, dest="post_s", help="forward move window (s)")
    ap.add_argument("--min-pre-ticks", type=int, default=3, help="min ticks in the pre-window to anchor")
    ap.add_argument("--max-anchor-gap-s", type=float, default=300.0,
                    help="max gap between the release time and the nearest tick (tape must cover it)")
    ap.add_argument("--run-thr", type=float, default=0.5, help="retention >= this = a 'run'")
    ap.add_argument("--blip-thr", type=float, default=0.2, help="retention < this = a 'blip'")
    ap.add_argument("--big-surprise", type=float, default=10.0,
                    help="|actual-forecast| >= this = a 'big' surprise (release-native units)")
    ap.add_argument("--min-cell", type=int, default=3, help="min events to report a cell")
    ap.add_argument("--emit-events", action="store_true", help="include the per-event rows in the JSON")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    cfg = {"pre_s": args.pre_s, "post_s": args.post_s, "min_pre_ticks": args.min_pre_ticks,
           "max_anchor_gap_s": args.max_anchor_gap_s, "run_thr": args.run_thr, "blip_thr": args.blip_thr,
           "big_surprise": args.big_surprise, "min_cell": args.min_cell, "emit_events": args.emit_events}
    res = build(args.symbol, args.series, cfg)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(res, open(args.out, "w"), indent=2)
    if res["status"] != "OK":
        print(f"[{res['symbol']}] {res['status']}: {res.get('msg', '')}")
        return
    print(f"[{res['symbol']}/{res['series']}] events={res['n_events']} over {res['tape_days']} tape-days "
          f"({res['ticks']} ticks)  tick_source={res['tick_source']}  "
          f"leakage_pass={res['leakage_pass']} (fails={res['leakage_fails']})")
    if res["tick_source"].get("reference_unverified"):
        print(f"  WARNING {res['tick_source']['reference_unverified']} event(s) fell back to the UNVERIFIED "
              f"reference tick — extend {TAPE_DIR}/{sym_root(res['symbol'])}_definitions.jsonl earlier "
              "(databento_backfill.py defs) so every event has a preceding definition.")
    print(f"  cells reported (>= {args.min_cell}): {res['n_cells_reported']}")
    for k, d in res["cells"].items():
        print(f"\n  CELL {k}  n={d['n']}")
        print(f"    peak_bps p50={d['peak_bps']['p50']} p90={d['peak_bps']['p90']} max={d['peak_bps']['max']}  "
              f"peak_ticks p50={d['peak_ticks']['p50']}  "
              f"peak_usd p50={d['peak_usd']['p50'] if d['peak_usd'] else 'n/a'}")
        print(f"    time_to_peak_s p50={d['time_to_peak_s']['p50']}  sustain_s p50={d['sustain_s']['p50']}  "
              f"retention p50={d['retention']['p50']}")
        print(f"    shape_mix={d['shape_mix']}  dir_mix={d['dir_mix']}")
    pf = res["pooled_footnote"]
    print(f"\n  [footnote, pooled — never the headline] n={pf['n']} peak_bps p50={pf['peak_bps']['p50']} "
          f"shape_mix={pf['shape_mix']}")
    print("  expectation-setting only — distributions not means, per-cell, leakage-gated. NOT a trade-fire signal.")


if __name__ == "__main__":
    main()
