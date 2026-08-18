#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

import ng_exhaustion_exact_d1_agents_v2_20260818 as core
from ng_dipole_runway_audit import TICK

SEED = 20260818
CHECKPOINTS = tuple([0, 1, 2, 3, 4, 5, 10, 15, 20] + list(range(25, 3601, 5)))
SURVIVAL_HORIZONS = (1, 2, 3, 4, 5, 10, 30, 60, 120, 300, 600)


def day_from_name(p):
    m = re.search(r"(20\d{6})", Path(p).name)
    if not m:
        raise SystemExit(f"cannot parse day from {p}")
    return m.group(1)


def parse_week(s):
    return datetime.strptime(s, "%Y%m%d")


def load_week_prices(raw_paths, week):
    sun = parse_week(week)
    pts = []
    for p in raw_paths:
        d = day_from_name(p)
        di = (datetime.strptime(d, "%Y%m%d") - sun).days
        if di < 0 or di > 5:
            continue
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                if r.get("action") != "T":
                    continue
                px = float(r.get("price", 0) or 0)
                if px <= 0:
                    continue
                ts = r.get("ts_event", r.get("ts"))
                if ts is None:
                    continue
                try:
                    sec = int(float(ts)) % 86400
                except Exception:
                    continue
                pts.append((di * 86400 + sec, px))
    pts.sort(key=lambda z: (z[0], z[1]))
    return pts


def raw_paths_for_week(raw_dir, week):
    sun = parse_week(week)
    lo = week
    hi = (sun + timedelta(days=5)).strftime("%Y%m%d")
    return sorted(
        p for p in Path(raw_dir).glob("NG_*.jsonl.gz")
        if lo <= day_from_name(p) <= hi
    )


def _metric_dict(pts, requested_start, structural_end, pol):
    """Causal execution: first trade at/after requested_start; exit last trade <= end."""
    if not pts or structural_end <= requested_start:
        return None
    times = [x[0] for x in pts]
    j = bisect.bisect_left(times, int(requested_start))
    e = bisect.bisect_right(times, int(structural_end)) - 1
    if j >= len(pts) or e < 0 or j > e:
        return None
    fill_t, p0 = pts[j]
    exit_t, p1 = pts[e]
    if fill_t > structural_end or exit_t < requested_start:
        return None
    seg = pts[j:e + 1]
    prices = [p for _, p in seg]
    changes = [prices[k] - prices[k - 1] for k in range(1, len(prices))]
    signed = pol * (p1 - p0) / TICK
    if pol > 0:
        mfe = (max(prices) - p0) / TICK
        mae = (min(prices) - p0) / TICK
    else:
        mfe = (p0 - min(prices)) / TICK
        mae = (p0 - max(prices)) / TICK
    total = sum(abs(x) for x in changes)
    max_exc = max(abs(mfe), abs(mae))
    two_min = min(max(mfe, 0.0), max(-mae, 0.0))
    two_max = max(max(mfe, 0.0), max(-mae, 0.0))
    return {
        "requested_entry_idx": int(requested_start),
        "actual_fill_idx": int(fill_t),
        "fill_latency_seconds": int(fill_t - requested_start),
        "entry_price": float(p0),
        "structural_exit_idx": int(structural_end),
        "actual_exit_trade_idx": int(exit_t),
        "exit_lead_seconds": int(structural_end - exit_t),
        "exit_price": float(p1),
        "trade_points": int(len(seg)),
        "actual_fill_to_structural_exit_seconds": int(structural_end - fill_t),
        "tape_fill_to_exit_trade_seconds": int(exit_t - fill_t),
        "signed_endpoint_ticks": float(signed),
        "absolute_endpoint_ticks": float(abs(signed)),
        "mfe_ticks": float(mfe),
        "mae_ticks": float(mae),
        "range_ticks": float(mfe - mae),
        "path_efficiency": float(abs(p1 - p0) / total) if total > 0 else 0.0,
        "endpoint_to_excursion_efficiency": float(abs(signed) / max_exc) if max_exc > 0 else 0.0,
        "two_sidedness": float(two_min / two_max) if two_max > 0 else 0.0,
        "aligned_change_fraction": (
            float(sum(pol * x > 0 for x in changes) / len(changes)) if changes else None
        ),
    }


def d1_id(r):
    return f"{r['week']}|{r['origin_event_id']}|D1"


def corrected_block(r):
    return {
        "train": "D1_DISCOVERY_OOT",
        "era45": "D1_VALIDATION",
        "conf": "D1_CONFIRMATION",
        "held": "HELD_INSERT_ONLY",
        "prelineage_unlabeled": "PRELINEAGE_UNLABELED",
    }.get(r["block"], r["block"])


def path_record(r, events, pts):
    w = r["week"]
    o = events[w][r["origin_seq"]]
    d = events[w][r["origin_seq"] + 1]
    confirm = None if o.get("confirm") is None else int(o["confirm"])
    desc_t0 = int(d["t0"])
    origin_t0 = int(o["t0"])
    full_state = None if confirm is None else confirm + 60
    rec = {
        "d1_id": d1_id(r),
        "label_source": "FROZEN_PHASE1_FORWARD_OOT_LINEAGE",
        "week_sunday": w,
        "chronological_block": corrected_block(r),
        "origin_sequence_index": int(r["origin_seq"]),
        "origin_event_id": r["origin_event_id"],
        "desc_event_id": r["desc_event_id"],
        "pair": r["pair"],
        "duration_family": r["duration_family"],
        "origin_polarity": int(o["pol"]),
        "origin_t0_idx": origin_t0,
        "detector_confirm_idx": confirm,
        "full_state_known_idx": full_state,
        "descendant_t0_idx": desc_t0,
        "origin_to_descendant_seconds": int(desc_t0 - origin_t0),
        "detector_to_descendant_seconds": None if confirm is None else int(desc_t0 - confirm),
        "full_state_to_descendant_seconds": None if full_state is None else int(desc_t0 - full_state),
        "detector_clock_available": bool(confirm is not None),
        "detector_clock_precedes_descendant": bool(confirm is not None and confirm < desc_t0),
        "full_state_clock_precedes_descendant": bool(full_state is not None and full_state < desc_t0),
        "descriptive_full_origin_to_descendant": _metric_dict(pts, origin_t0, desc_t0, int(o["pol"])),
        "causal_detector_known_to_descendant": (
            None if confirm is None else _metric_dict(pts, confirm, desc_t0, int(o["pol"]))
        ),
        "causal_full_state_known_to_descendant": (
            None if full_state is None else _metric_dict(pts, full_state, desc_t0, int(o["pol"]))
        ),
        "path_shape_group": None,
        "path_shape_basis": "DETECTOR_KNOWN_TO_DESCENDANT_REALIZED_PATH",
        "path_shape_is_origin_known": False,
        "realized_duration_is_origin_known": False,
        "promotion_performed": False,
    }
    if not pts:
        rec["raw_path_status"] = "NO_RAW_TRADE_POINTS_FOR_WEEK"
    elif confirm is None:
        rec["raw_path_status"] = "DETECTOR_CONFIRM_MISSING"
    elif confirm >= desc_t0:
        rec["raw_path_status"] = "DETECTOR_CLOCK_NOT_BEFORE_DESCENDANT"
    elif rec["causal_detector_known_to_descendant"] is None:
        rec["raw_path_status"] = "NO_EXECUTABLE_TRADE_FILL_FROM_DETECTOR_CLOCK"
    else:
        rec["raw_path_status"] = "DETECTOR_CAUSAL_PATH_AVAILABLE"
    return rec


def checkpoint_rows(r, events, pts):
    w = r["week"]
    o = events[w][r["origin_seq"]]
    d = events[w][r["origin_seq"] + 1]
    confirm = None if o.get("confirm") is None else int(o["confirm"])
    desc_t0 = int(d["t0"])
    if confirm is None:
        return []
    out = []
    for offset in CHECKPOINTS:
        target = confirm + int(offset)
        if target >= desc_t0:
            break
        metrics = _metric_dict(pts, target, desc_t0, int(o["pol"]))
        q = {
            "d1_id": d1_id(r),
            "week_sunday": w,
            "chronological_block": corrected_block(r),
            "pair": r["pair"],
            "duration_family": r["duration_family"],
            "origin_polarity": int(o["pol"]),
            "causal_clock": "DETECTOR_KNOWN",
            "checkpoint_offset_seconds": int(offset),
            "checkpoint_idx": int(target),
            "structural_alive_at_checkpoint": True,
            "structural_remaining_seconds_from_checkpoint": int(desc_t0 - target),
            "execution_fill_available": bool(metrics is not None),
            "path_outcome_is_future_realized_annotation": True,
            "promotion_performed": False,
        }
        if metrics is not None:
            q.update(metrics)
        out.append(q)
    return out


def write_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")


def shard_mode(a):
    weeks_all = json.load(open(a.summary))["weeks"]
    events = core.load_events(a.base, a.held)
    lineage = core.load_lineage(a.base_lineage, a.held_lineage)
    d1, family_model = core.d1_records(events, lineage, weeks_all)
    wanted = set(w.strip() for w in a.weeks.split(",") if w.strip())
    selected = [r for r in d1 if r["week"] in wanted]
    missing_weeks = sorted(wanted - {r["week"] for r in selected})
    raw_dir = Path(a.raw_dir)
    path_rows = []
    cp_rows = []
    raw_point_counts = {}
    for w in sorted(wanted):
        wp = raw_paths_for_week(raw_dir, w)
        pts = load_week_prices(wp, w)
        raw_point_counts[w] = int(len(pts))
        for r in (z for z in selected if z["week"] == w):
            path_rows.append(path_record(r, events, pts))
            cp_rows.extend(checkpoint_rows(r, events, pts))
    out_prefix = Path(a.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths_p = str(out_prefix) + "_PATHS.jsonl.gz"
    cps_p = str(out_prefix) + "_CHECKPOINTS.jsonl.gz"
    summary_p = str(out_prefix) + "_SUMMARY.json"
    write_gz(paths_p, path_rows)
    write_gz(cps_p, cp_rows)
    summary = {
        "status": "D1_ALL_RAWPATH_SHARD_COMPLETE",
        "requested_weeks": sorted(wanted),
        "weeks_with_zero_d1": missing_weeks,
        "d1_rows": int(len(path_rows)),
        "checkpoint_rows": int(len(cp_rows)),
        "raw_trade_points_by_week": raw_point_counts,
        "checkpoint_grid": list(CHECKPOINTS),
        "clock_priority": "DETECTOR_KNOWN_FIRST_FULL_STATE_SEPARATE_ONLY_WHEN_REQUIRED",
        "causal_entry_price_rule": "FIRST_TRADE_AT_OR_AFTER_REQUESTED_CHECKPOINT",
        "structural_exit_price_rule": "LAST_TRADE_AT_OR_BEFORE_FROZEN_DESCENDANT_T0",
        "family_model": {
            "centers_seconds": family_model["centers"],
            "labels": family_model["labels"],
            "selected_components": family_model["k"],
        },
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "held_rows": False,
            "phase1_lineage": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
    }
    Path(summary_p).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": summary["status"], "d1_rows": len(path_rows), "checkpoint_rows": len(cp_rows)}, indent=2))


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _logit(x):
    x = min(max(float(x), 1e-6), 1 - 1e-6)
    return math.log(x / (1 - x))


def fit_shape(path_rows):
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    keys = ("path_efficiency", "endpoint_to_excursion_efficiency", "two_sidedness")
    train = []
    for r in path_rows:
        if r["chronological_block"] != "D1_DISCOVERY_OOT":
            continue
        z = r.get("causal_detector_known_to_descendant")
        if not z or not all(finite(z.get(k)) for k in keys):
            continue
        train.append(r)
    if len(train) < 20:
        raise SystemExit(f"insufficient discovery detector-known raw paths for shape model: {len(train)}")
    raw = np.asarray([
        [_logit(r["causal_detector_known_to_descendant"][k]) for k in keys]
        for r in train
    ], float)
    scaler = StandardScaler().fit(raw)
    X = scaler.transform(raw)
    gmm = GaussianMixture(n_components=2, random_state=SEED, n_init=30).fit(X)
    centers_logit = scaler.inverse_transform(gmm.means_)
    inv = lambda v: 1.0 / (1.0 + math.exp(-float(v)))
    centers = [[inv(x) for x in row] for row in centers_logit]
    score = [row[0] + row[1] - row[2] for row in centers]
    chop = int(min(range(2), key=lambda i: score[i]))
    return scaler, gmm, chop, centers, len(train)


def assign_shape(model, r):
    scaler, gmm, chop, _, _ = model
    z = r.get("causal_detector_known_to_descendant")
    keys = ("path_efficiency", "endpoint_to_excursion_efficiency", "two_sidedness")
    if not z or not all(finite(z.get(k)) for k in keys):
        return "UNCLASSIFIED_NO_DETECTOR_CAUSAL_PATH"
    x = np.asarray([[_logit(z[k]) for k in keys]], float)
    c = int(gmm.predict(scaler.transform(x))[0])
    return "CHOP_ROTATION" if c == chop else "DIRECTIONAL"


def iter_gz(path):
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def basic_summary(xs):
    a = sorted(float(x) for x in xs if finite(x))
    if not a:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None, "p95": None, "p99": None, "max": None}
    return {
        "n": len(a),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p25": float(np.quantile(a, 0.25)),
        "p75": float(np.quantile(a, 0.75)),
        "p95": float(np.quantile(a, 0.95)),
        "p99": float(np.quantile(a, 0.99)),
        "max": float(max(a)),
    }


def merge_mode(a):
    shard_dir = Path(a.shard_dir)
    path_files = sorted(shard_dir.rglob("*_PATHS.jsonl.gz"))
    cp_files = sorted(shard_dir.rglob("*_CHECKPOINTS.jsonl.gz"))
    summary_files = sorted(shard_dir.rglob("*_SUMMARY.json"))
    if not path_files or not cp_files or not summary_files:
        raise SystemExit("missing lane2 shard files")
    path_rows = []
    seen = set()
    for p in path_files:
        for r in iter_gz(p):
            if r["d1_id"] in seen:
                raise SystemExit(f"duplicate D1 path row {r['d1_id']}")
            seen.add(r["d1_id"])
            path_rows.append(r)
    if len(path_rows) != 18837:
        raise SystemExit(f"preserve-all forward D1 invariant failed expected=18837 actual={len(path_rows)}")

    shape = fit_shape(path_rows)
    for r in path_rows:
        r["path_shape_group"] = assign_shape(shape, r)
    shape_counts = Counter(r["path_shape_group"] for r in path_rows)
    block_counts = Counter(r["chronological_block"] for r in path_rows)
    status_counts = Counter(r["raw_path_status"] for r in path_rows)

    cp_acc = defaultdict(lambda: {
        "n_alive": 0,
        "n_fill": 0,
        "remaining": [],
        "signed_endpoint": [],
        "mfe": [],
        "mae": [],
        "fill_latency": [],
    })
    checkpoint_n = 0
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cp_out = out_dir / "NG_EXHAUSTION_D1_ALL_DETECTOR_CHECKPOINTS_20260818.jsonl.gz"
    with gzip.open(cp_out, "wt") as fo:
        for p in cp_files:
            for r in iter_gz(p):
                checkpoint_n += 1
                off = int(r["checkpoint_offset_seconds"])
                z = cp_acc[off]
                z["n_alive"] += 1
                rem = r.get("structural_remaining_seconds_from_checkpoint")
                if finite(rem):
                    z["remaining"].append(float(rem))
                if r.get("execution_fill_available"):
                    z["n_fill"] += 1
                    for src, key in (("signed_endpoint_ticks", "signed_endpoint"), ("mfe_ticks", "mfe"), ("mae_ticks", "mae"), ("fill_latency_seconds", "fill_latency")):
                        if finite(r.get(src)):
                            z[key].append(float(r[src]))
                fo.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")

    detector_known_n = sum(r["detector_clock_available"] for r in path_rows)
    checkpoint_summary = {}
    for off in CHECKPOINTS:
        z = cp_acc.get(off)
        if not z:
            checkpoint_summary[str(off)] = {
                "n_alive": 0,
                "alive_fraction_of_all_d1": 0.0,
                "alive_fraction_of_detector_known": 0.0 if detector_known_n else None,
            }
            continue
        rem = z["remaining"]
        checkpoint_summary[str(off)] = {
            "n_alive": int(z["n_alive"]),
            "alive_fraction_of_all_d1": float(z["n_alive"] / len(path_rows)),
            "alive_fraction_of_detector_known": float(z["n_alive"] / detector_known_n) if detector_known_n else None,
            "n_execution_fill": int(z["n_fill"]),
            "execution_fill_fraction_of_alive": float(z["n_fill"] / z["n_alive"]) if z["n_alive"] else None,
            "remaining_structural_seconds": basic_summary(rem),
            "conditional_survival_probability": {
                str(h): (float(sum(x > h for x in rem) / len(rem)) if rem else None)
                for h in SURVIVAL_HORIZONS
            },
            "future_realized_path_from_checkpoint": {
                "signed_endpoint_ticks_origin_polarity": basic_summary(z["signed_endpoint"]),
                "mfe_ticks_origin_polarity": basic_summary(z["mfe"]),
                "mae_ticks_origin_polarity": basic_summary(z["mae"]),
                "fill_latency_seconds": basic_summary(z["fill_latency"]),
            },
        }

    path_out = out_dir / "NG_EXHAUSTION_D1_ALL_RAWPATH_MASTER_20260818.jsonl.gz"
    write_gz(path_out, path_rows)
    _, _, chop, centers, train_n = shape
    summary = {
        "status": "D1_ALL_RAWPATH_ENTRY_CLOCK_LANE2_COMPLETE",
        "forward_exact_d1_n": int(len(path_rows)),
        "filtered_exact_d1_rows": 0,
        "checkpoint_rows": int(checkpoint_n),
        "chronological_block_counts": dict(block_counts),
        "raw_path_status_counts": dict(status_counts),
        "detector_clock_available_n": int(detector_known_n),
        "detector_clock_precedes_descendant_n": int(sum(r["detector_clock_precedes_descendant"] for r in path_rows)),
        "full_state_clock_precedes_descendant_n": int(sum(r["full_state_clock_precedes_descendant"] for r in path_rows)),
        "entry_hierarchy": "DETECTOR_KNOWN_FIRST; FULL_STATE_KNOWN_ONLY_SEPARATE_WHEN_RULE_REQUIRES_IT",
        "checkpoint_grid": list(CHECKPOINTS),
        "checkpoint_grid_source": "research/NG_EXHAUSTION_ENTRY_TIMING_CHECKPOINT_DENSITY_ADDENDUM_20260818.md",
        "checkpoint_survivorship": checkpoint_summary,
        "path_shape_model": {
            "basis": "realized detector-known-to-descendant path; descriptive only, never origin-known",
            "method": "D1_DISCOVERY_OOT-only 2-component GaussianMixture on standardized logit(path_efficiency, endpoint_to_excursion_efficiency, two_sidedness)",
            "train_n": int(train_n),
            "centers_original_ordered_by_component": centers,
            "chop_component": int(chop),
            "shape_counts": dict(shape_counts),
        },
        "causal_entry_price_rule": "FIRST_TRADE_AT_OR_AFTER_REQUESTED_ENTRY_TIME",
        "exit_price_rule": "LAST_TRADE_AT_OR_BEFORE_FROZEN_DESCENDANT_T0",
        "guardrails": [
            "Every frozen forward-OOT exact D1 is preserved even if no causal detector path or no tape fill exists.",
            "Realized path shape, final duration, MFE, MAE and descendant identity are outcome annotations, not causal checkpoint inputs.",
            "No +60 wait is imposed on rules that can be tested at detector confirmation.",
            "FULL_STATE_KNOWN remains a separate confirm+60 annotation only for rules genuinely requiring that wall.",
        ],
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "held_rows": False,
            "phase1_lineage": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
        "outputs": {
            "path_master": str(path_out),
            "detector_checkpoints": str(cp_out),
        },
    }
    summary_out = out_dir / "NG_EXHAUSTION_D1_ALL_RAWPATH_SUMMARY_20260818.json"
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "d1": len(path_rows),
        "checkpoint_rows": checkpoint_n,
        "shape_counts": dict(shape_counts),
        "status_counts": dict(status_counts),
    }, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("shard")
    s.add_argument("--base", required=True)
    s.add_argument("--held", required=True)
    s.add_argument("--base-lineage", required=True)
    s.add_argument("--held-lineage", required=True)
    s.add_argument("--summary", required=True)
    s.add_argument("--raw-dir", required=True)
    s.add_argument("--weeks", required=True)
    s.add_argument("--out-prefix", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--shard-dir", required=True)
    m.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if a.mode == "shard":
        shard_mode(a)
    else:
        merge_mode(a)


if __name__ == "__main__":
    main()
