"""
month_characterize.py — per-(commodity, MONTH) CONTINUOUS-tape characterizer. The per-agent TOOL the S88
path-forecaster workflow fans out over (one agent per commodity x month, coin-style). Complements the
release-window `bucket_continuation.py`: this reads the CONTINUOUS all-session tape (data/nymex_cont/),
detects EVERY sustained intraday move (not just the release), and tabulates the per-cell forward-path
distribution FOR THAT MONTH — the intraday analog library one regime at a time.

WHY per-month (Greg S88, anti-lock-in): what worked one month may not work another — the regime differs
(season/geopolitics/vol/curve/temp). Each month is characterized on its OWN, blind to the others; the
workflow's synthesis stage separates "stable across months" from "month-specific" and the verify stage kills
one-month-only patterns. A pattern here is a per-month observation, NOT a global rule.

REUSES: lag_join.scan_moves (the sustained-move detector) + nws_temp_feed / forward_curve (regime tags).
CELLS (intraday, compact key + conditioning tags): tod_bucket x move_dir x book {support|oppose}; tags =
coiled {quiet|active}, curve_regime, temp_regime. Path descriptors in $/contract (CL x1000, NG x10000),
NEVER bps. Leakage-safe: cell features are strictly pre/at-entry (decision-time); path outcome is forward.

Usage:
    python research/kalshi/month_characterize.py --root CL --month 2026-05 [--out <path>]
    python research/kalshi/month_characterize.py --selftest
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lag_join as lj                                             # noqa: E402
import event_move_baseline as emb                                # noqa: E402  (shared raw-tape reader)

CONT_DIR = "data/nymex_cont"
MULT = {"CL": 1000.0, "NG": 10000.0}          # contract size: CL 1000 bbl, NG 10000 MMBtu ($/pt -> $/contract)
# CHARACTERIZER move trigger — DECOUPLED from lag_join's TRADE trigger (Greg S88). For sampling the analog
# library we want richer coverage, so NG is lowered to $0.015 ($150/c): its trade trigger ($0.03) starved
# the intraday sample 50x vs CL (59 vs 2884 moves/month in the S88 validation). Trading keeps its own
# fee-justified trigger; characterization samples smaller moves too. Overridable via --trig-cl/--trig-ng.
TRIG = {"CL": 0.20, "NG": 0.015}
CONFIRM_S = 5.0
COOLDOWN_S = 180.0
POST_S = 1800.0                               # forward path window per move (s)
PRE_S = 120.0                                 # pre-move volume / imbalance window (s)
RUN_THR = 0.5                                 # retention >= this = continuation


def load_cont_full(root: str, day: str, source: str = "local"):
    """Continuous day with DEPTH -> dict of numpy arrays (ts, price, size, bid_dep, ask_dep), ts-sorted.
    Delegates to the shared raw-tape reader (event_move_baseline.load_cont_day): the RAW S89 S3 corpus keeps
    every message + every column, so trade-selection + ladder-aggregation happen at READ time here (Greg S88:
    pre-processing on the trade side), not at ingest. source='local' reads data/nymex_cont/{root}_{day}.jsonl
    (or .jsonl.gz cache); source='s3' streams+caches the day's gz from the bucket. Old reduced tapes still
    load unchanged (normalize_mbp10_row passes them through)."""
    emb.CONT_DIR = CONT_DIR                                       # honor --cont-dir override for the cache
    d = emb.load_cont_day(root, day, source=source, trades_only=True)
    return {"ts": d["ts"], "price": d["price"], "size": d["size"],
            "bid_dep": d["bid_dep"], "ask_dep": d["ask_dep"]}


def _list_cont_days(root: str, ym: str, source: str = "local") -> list[str]:
    """Days 'YYYYMMDD' available for (root, month 'YYYYMM'), from the local cache or the S3 bucket."""
    if source == "s3":
        import boto3
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
        s3 = boto3.client("s3", region_name=region) if region else boto3.client("s3")
        pfx = f"{emb.S3_PREFIX + '/' if emb.S3_PREFIX else ''}nymex_cont/{root}_{ym}"
        days = set()
        tok = None
        while True:
            kw = {"Bucket": emb.S3_BUCKET, "Prefix": pfx}
            if tok:
                kw["ContinuationToken"] = tok
            resp = s3.list_objects_v2(**kw)
            for o in resp.get("Contents", []):
                name = o["Key"].split("/")[-1]                   # {root}_{YYYYMMDD}.jsonl.gz
                days.add(name.split("_")[1][:8])
            if not resp.get("IsTruncated"):
                break
            tok = resp.get("NextContinuationToken")
        return sorted(days)
    return sorted(os.path.basename(p).split("_")[1].split(".")[0]
                  for p in glob.glob(os.path.join(CONT_DIR, f"{root}_{ym}*.jsonl"))
                  + glob.glob(os.path.join(CONT_DIR, f"{root}_{ym}*.jsonl.gz")))


def _tod_bucket(ts: float) -> str:
    """UTC-hour session phase. US releases/open ~13-15 UTC; the liquid US session 13-20."""
    h = datetime.fromtimestamp(ts, timezone.utc).hour
    if 13 <= h < 15:
        return "us_open"        # US open + the 14:30 release cluster
    if 15 <= h < 20:
        return "us_mid"
    if 20 <= h < 24 or h < 2:
        return "us_close_ovn"
    return "asia_euro"          # 02-13 UTC


def _imbalance(bid_dep: float, ask_dep: float) -> float:
    tot = bid_dep + ask_dep
    return 0.0 if tot <= 0 else (bid_dep - ask_dep) / tot


def move_path(a: dict, ei: int, sign: int, mult: float) -> dict:
    """Forward-path descriptors from entry index ei (sign = +1 up / -1 down), $/contract."""
    ts, p = a["ts"], a["price"]
    t0, p0 = ts[ei], p[ei]
    win = (ts >= t0) & (ts <= t0 + POST_S)
    idx = np.nonzero(win)[0]
    if idx.size < 2:
        return {}
    fwd_p = p[idx]
    fav = sign * (fwd_p - p0)                       # favorable excursion in $/pt
    kpk = int(np.argmax(fav))
    peak_pt = float(fav[kpk])
    peak_usd = round(peak_pt * mult, 2)
    ttp = float(ts[idx[kpk]] - t0)
    # 60s capture
    fast_mask = ts[idx] <= t0 + 60.0
    fast_peak = float(np.max(fav[fast_mask])) if fast_mask.any() else 0.0
    fast_capture = round(fast_peak / peak_pt, 3) if peak_pt > 0 else 0.0
    peaked_fast = bool(ttp <= 60.0)
    # retention = end-of-window favorable / peak ; sustain = time favorable stays >= 0.5*peak
    end_val = float(fav[-1])
    retention = round(end_val / peak_pt, 3) if peak_pt > 0 else 0.0
    above = ts[idx][fav >= 0.5 * peak_pt] if peak_pt > 0 else np.array([])
    sustain_s = round(float(above.max() - t0), 1) if above.size else 0.0
    return {"peak_usd": peak_usd, "time_to_peak_s": round(ttp, 1), "fast_capture": fast_capture,
            "peaked_fast": peaked_fast, "retention": retention, "sustain_s": sustain_s,
            "continuation": bool(retention >= RUN_THR)}


def pre_move_pieces(a: dict, ei: int, sign: int) -> dict:
    """Decision-time (pre/at entry) pieces: aligned book imbalance + pre-move volume. Leakage-safe."""
    ts = a["ts"]
    t0 = ts[ei]
    imb = _imbalance(float(a["bid_dep"][ei]), float(a["ask_dep"][ei]))
    aligned_imb = imb * sign                        # >0 = book SUPPORTS the move
    pre = (ts >= t0 - PRE_S) & (ts < t0)
    pre_vol = float(a["size"][pre].sum())
    return {"aligned_imb": round(aligned_imb, 4), "book": "support" if aligned_imb > 0 else "oppose",
            "pre_vol": pre_vol}


def _iso_day(day: str) -> str:
    """Tape filenames use YYYYMMDD; the temp/curve caches key on YYYY-MM-DD. Convert (leakage-critical:
    curve_asof does string date comparison, so a mismatched format silently returns the wrong/latest curve)."""
    return f"{day[:4]}-{day[4:6]}-{day[6:8]}" if len(day) == 8 and "-" not in day else day


def _regime_tags(root: str, day: str) -> dict:
    iso = _iso_day(day)
    try:
        import forward_curve as fc
        cr = fc.curve_asof(fc.load(root), iso)          # leakage-safe D-1 curve (ISO date)
        curve = cr[1]["regime"] if cr else "unknown"
    except Exception:
        curve = "unknown"
    tw = {"temp_regime": "unknown", "gw_hdd": None, "gw_cdd": None, "gw_precip": None}
    try:
        import nws_temp_feed as nt
        v = nt._load_cache().get(iso, {})
        tw = {"temp_regime": v.get("regime", "unknown"), "gw_hdd": v.get("gw_hdd"),
              "gw_cdd": v.get("gw_cdd"), "gw_precip": v.get("gw_precip")}
    except Exception:
        pass
    return {"curve_regime": curve, **tw}   # continuous gas-weighted demand for the weather->NG influence study


def characterize_day(root: str, day: str, source: str = "local") -> list[dict]:
    """All sustained moves in one continuous day -> per-move rows (pieces + path + regime tags)."""
    a = load_cont_full(root, day, source=source)
    if a["ts"].size < 10:
        return []
    moves = lj.scan_moves(a["ts"], a["price"], TRIG[root], CONFIRM_S, COOLDOWN_S)
    tags = _regime_tags(root, day)
    rows = []
    for ei, s in moves:
        path = move_path(a, ei, s, MULT[root])
        if not path:
            continue
        pieces = pre_move_pieces(a, ei, s)
        rows.append({"day": day, "root": root, "entry_idx": int(ei), "dir": "up" if s > 0 else "down",
                     "tod": _tod_bucket(float(a["ts"][ei])), **pieces, **path, **tags})
    return rows


def _q(arr):
    a = np.asarray([x for x in arr if x is not None], float)
    if a.size == 0:
        return {"p25": None, "p50": None, "p75": None, "max": None, "n": 0}
    return {"p25": round(float(np.percentile(a, 25)), 2), "p50": round(float(np.percentile(a, 50)), 2),
            "p75": round(float(np.percentile(a, 75)), 2), "max": round(float(a.max()), 2), "n": int(a.size)}


def _coiled_split(rows: list[dict]) -> dict:
    """Surface the coiled-volume piece: quiet vs active sub-distribution within a cell (S86/graph-learn:
    coiled -> magnitude, per-cell). Absent 'coiled' tag -> {} (e.g. selftest rows)."""
    out = {}
    for lvl in ("quiet", "active"):
        sub = [r for r in rows if r.get("coiled") == lvl]
        if sub:
            out[lvl] = {"n": len(sub), "peak_usd_p50": _q([r["peak_usd"] for r in sub])["p50"],
                        "continuation_rate": round(float(np.mean([r["continuation"] for r in sub])), 3)}
    return out


def tabulate(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    return {"n": n,
            "peak_usd": _q([r["peak_usd"] for r in rows]),
            "fast_capture_p50": round(float(np.median([r["fast_capture"] for r in rows])), 3),
            "peaked_fast_frac": round(float(np.mean([r["peaked_fast"] for r in rows])), 3),
            "retention_p50": round(float(np.median([r["retention"] for r in rows])), 3),
            "sustain_s_p50": round(float(np.median([r["sustain_s"] for r in rows])), 1),
            "continuation_rate": round(float(np.mean([r["continuation"] for r in rows])), 3),
            "by_coiled": _coiled_split(rows)}


def characterize_month(root: str, month: str, source: str = "local") -> dict:
    """month = 'YYYY-MM'. Characterize every sustained move across the month's continuous days, per cell."""
    ym = month.replace("-", "")
    days = _list_cont_days(root, ym, source=source)
    all_rows: list[dict] = []
    for day in days:
        all_rows.extend(characterize_day(root, day, source=source))
    # coiled tag: per-month median pre_vol split (stored)
    coiled_thr = float(np.median([r["pre_vol"] for r in all_rows])) if all_rows else 0.0
    for r in all_rows:
        r["coiled"] = "quiet" if r["pre_vol"] <= coiled_thr else "active"
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        by_cell[f"{r['tod']}|{r['dir']}|{r['book']}"].append(r)
    cells = {k: tabulate(v) for k, v in sorted(by_cell.items(), key=lambda kv: -len(kv[1]))}
    return {"root": root, "month": month, "status": "OK" if all_rows else "NO_DATA",
            "n_days": len(days), "n_moves": len(all_rows), "coiled_thr": round(coiled_thr, 1),
            "cells": cells, "pooled_footnote": tabulate(all_rows),
            "regime_mix": {"curve": _mix(all_rows, "curve_regime"), "temp": _mix(all_rows, "temp_regime")},
            "note": "one month = one regime; a pattern here is NOT a global rule until it recurs (anti-lock-in)."}


def _mix(rows, key):
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r.get(key, "unknown")] += 1
    return dict(out)


def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # synthetic day: a clean +$0.50 sustained up-move on CL, book supporting, then holds.
    n = 400
    ts = np.arange(n, dtype=float)                 # 1s spacing
    price = np.concatenate([np.full(50, 77.0), np.linspace(77.0, 77.5, 50), np.full(300, 77.5)])
    a = {"ts": ts, "price": price, "size": np.ones(n),
         "bid_dep": np.full(n, 30.0), "ask_dep": np.full(n, 10.0)}   # bid-heavy = supports an up-move
    moves = lj.scan_moves(ts, price, 0.20, 5.0, 180.0)
    check("detects the sustained up-move", len(moves) >= 1)
    ei, s = moves[0]
    check("move sign = up", s > 0)
    path = move_path(a, ei, s, MULT["CL"])
    # entry fires AFTER the $0.20 trigger (~77.25), so peak-from-entry is ~$250, not the full $500 swing
    check("peak_usd from post-trigger entry ~250 (200-320)", 200 <= path["peak_usd"] <= 320)
    check("high retention (holds)", path["retention"] >= 0.9)
    check("continuation True", path["continuation"] is True)
    pc = pre_move_pieces(a, ei, s)
    check("book supports up-move (aligned_imb>0)", pc["aligned_imb"] > 0 and pc["book"] == "support")

    # tod buckets
    check("14 UTC -> us_open", _tod_bucket(datetime(2026, 5, 4, 14, tzinfo=timezone.utc).timestamp()) == "us_open")

    # LEAKAGE (structural): cell features (pre_move_pieces) invariant to forward price being poisoned.
    a2 = dict(a); a2["price"] = a["price"].copy(); a2["price"][ei + 5:] = 999.0   # poison the future
    pc2 = pre_move_pieces(a2, ei, s)
    check("pre-move pieces invariant to future price (leakage gate)", pc2 == pc)

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-(commodity,month) continuous-tape characterizer")
    ap.add_argument("--root", help="CL or NG")
    ap.add_argument("--month", help="YYYY-MM")
    ap.add_argument("--cont-dir", default=None,
                    help="continuous-tape dir to READ (default data/nymex_cont; use a SEPARATE dir while the "
                         "year pull owns data/nymex_cont as its live scratch)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--source", choices=["local", "s3"], default="local",
                    help="where to read the continuous tape: 'local' (data/nymex_cont cache) or 's3' "
                         "(stream+cache from the bucket; needs AWS env creds). S89: the corpus lives on S3.")
    ap.add_argument("--trig-cl", type=float, default=None, help="override CL characterizer move trigger ($)")
    ap.add_argument("--trig-ng", type=float, default=None, help="override NG characterizer move trigger ($)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.cont_dir:
        global CONT_DIR
        CONT_DIR = args.cont_dir
    if args.trig_cl is not None:
        TRIG["CL"] = args.trig_cl
    if args.trig_ng is not None:
        TRIG["NG"] = args.trig_ng
    if not (args.root and args.month):
        ap.error("need --root and --month (or --selftest)")
    res = characterize_month(args.root, args.month, source=args.source)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(res, open(args.out, "w"), indent=2)
    print(f"[{res['root']} {res['month']}] {res['status']}  days={res['n_days']} moves={res['n_moves']} "
          f"cells={len(res.get('cells', {}))}  coiled_thr={res.get('coiled_thr')}")
    for k, d in res.get("cells", {}).items():
        if d["n"] < 2:
            continue
        print(f"  CELL {k}  n={d['n']}  peak_usd p50={d['peak_usd']['p50']} max={d['peak_usd']['max']}  "
              f"fast_cap={d['fast_capture_p50']}  sustain_s={d['sustain_s_p50']}  cont={d['continuation_rate']}")
    print(f"  regime_mix={res.get('regime_mix')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
