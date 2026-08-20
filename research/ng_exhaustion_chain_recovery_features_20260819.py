#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import ng_exhaustion_d1_d5_chain_birth_agents_20260819 as frozen

DATE = "2026-08-19"
TICK = frozen.TICK
MODELS = tuple(frozen.MODELS)
GRIDS = frozen.GRIDS
SEED = frozen.SEED
FOLD_BLOCK = frozen.FOLD_BLOCK
EXPECTED_EXACT = {0: 135860, 1: 18837, 2: 1592, 3: 124, 4: 8, 5: 1}
PRIOR_AGES = (0, 1, 2, 3, 4, 5)
POST_H = (1, 2, 3, 4, 5)
VIEWS = ("FULL_CAUSAL", "NO_PRICE_CAUSAL", "PRICE_POLARITY_ONLY")
PRICE_LANDMARKS = (1, 2, 3, 4, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1800, 3600)
STATE_CODE = {
    "persistent_exhaustion": "P",
    "collapsed_opposite_flow_reversal": "O",
    "collapsed_same_flow_reload": "S",
    "collapsed_sparse_indeterminate": "X",
}
FAMILIES = ("A", "B", "C")
STATE_CODES = ("P", "O", "S", "X")
A_STATES = ("A-fast-collapse", "A-persistent")


def finite(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def load_events_full(*paths: str) -> dict[str, dict[int, dict[str, Any]]]:
    by: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                ep = r.get("dynamic_endpoint") or {}
                e = {
                    "event_id": r["event_id"],
                    "week_sunday": r["week_sunday"],
                    "sequence_index": int(r["sequence_index"]),
                    "t0_idx": int(r["t0_idx"]),
                    "polarity": int(r["polarity"]),
                    "family": r.get("family"),
                    "pre_family_distances": list(r.get("pre_family_distances") or []),
                    "a_frozen_post_state": r.get("a_frozen_post_state"),
                    "seed_state": r.get("seed_state"),
                    "feature": dict(r.get("feature") or {}),
                    "dynamic_endpoint": dict(ep),
                    "time_context": dict(r.get("time_context") or {}),
                }
                by[e["week_sunday"]][e["sequence_index"]] = e
    return dict(by)


def load_lineage(*paths: str) -> list[dict[str, Any]]:
    out = []
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                block = FOLD_BLOCK.get(str(r.get("fold")))
                if block is None:
                    continue
                out.append({
                    "week": r["week_sunday"],
                    "origin_event_id": r["origin_event_id"],
                    "origin_sequence_index": int(r["origin_sequence_index"]),
                    "depth": int(r.get("all_model_consecutive_positive_depth", 0)),
                    "block": block,
                })
    return out


def event_confirm(e: dict[str, Any]) -> int | None:
    v = (e.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")
    return None if v is None else int(v)


def build_cases(events: dict[str, dict[int, dict[str, Any]]], lineage: list[dict[str, Any]], stage: int):
    cases, censored = [], []
    for lr in lineage:
        q = int(lr["depth"])
        if q < stage - 1:
            continue
        w = lr["week"]
        i = int(lr["origin_sequence_index"])
        rs = events.get(w, {})
        preds = [rs.get(i + j) for j in range(stage)]
        target = rs.get(i + stage)
        if any(e is None for e in preds) or target is None:
            censored.append({
                "week": w,
                "origin_event_id": lr["origin_event_id"],
                "final_depth": q,
                "reason": "FROZEN_WEEK_END_OR_CANONICAL_TARGET_UNAVAILABLE",
            })
            continue
        rel = "S" if int(target["polarity"]) == int(preds[-1]["polarity"]) else "F"
        tcode = STATE_CODE.get(str(target.get("seed_state")), "X")
        extra = [rs.get(i + stage + k) for k in (1, 2)]
        cases.append({
            "id": f"{w}|{lr['origin_event_id']}|D{stage}",
            "week": w,
            "block": lr["block"],
            "final_depth": q,
            "continuation": 1 if q >= stage else 0,
            "preds": preds,
            "target": target,
            "extra": extra,
            "chain_type": f"{tcode}|{rel}" if q >= stage else None,
        })
    return cases, censored


def load_price_cache(cases: list[dict[str, Any]], raw_dir: str):
    cache = {"times": {}, "prices": {}}
    for w in sorted({c["week"] for c in cases}):
        t, p = frozen.load_week_prices(raw_dir, w)
        if len(t) == 0:
            raise RuntimeError(f"authoritative raw price tape missing week={w}")
        cache["times"][w] = t
        cache["prices"][w] = p
    return cache


def price_at_or_before(times: np.ndarray, prices: np.ndarray, t: float) -> float | None:
    j = int(np.searchsorted(times, float(t), side="right")) - 1
    return None if j < 0 else float(prices[j])


def price_window_features(times: np.ndarray, prices: np.ndarray, start: int | None, cutoff: int, pol: int):
    out: list[float] = []
    if start is None or cutoff < int(start):
        width = 2 + 4 + 2 * len(PRICE_LANDMARKS) + 10
        return [0.0] * width
    start = int(start)
    p0 = price_at_or_before(times, prices, start)
    if p0 is None:
        raise RuntimeError(f"no causal baseline trade at/before start={start}")
    age = int(cutoff - start)
    k = int(np.searchsorted(times, float(cutoff), side="right")) - 1
    if k < 0:
        raise RuntimeError(f"no causal trade known by cutoff={cutoff}")
    pnow = float(prices[k])
    j0 = int(np.searchsorted(times, float(start), side="right")) - 1
    seg = prices[max(0, j0): k + 1]
    if len(seg) == 0:
        seg = np.asarray([p0], float)
    oriented = float(pol) * (seg - p0) / TICK
    cur = float(pol) * (pnow - p0) / TICK
    out.extend([1.0, math.asinh(max(age, 0)), math.asinh(cur), math.asinh(float(np.max(oriented))), math.asinh(float(np.min(oriented))), math.asinh(float(np.max(oriented) - np.min(oriented)))])
    for s in PRICE_LANDMARKS:
        if s <= age:
            px = price_at_or_before(times, prices, start + s)
            if px is None:
                raise RuntimeError(f"no causal price by landmark={s} start={start}")
            z = float(pol) * (px - p0) / TICK
            out.extend([1.0, math.asinh(z)])
        else:
            out.extend([0.0, 0.0])
    for lag in (4, 3, 2, 1, 0):
        t = cutoff - lag
        if t >= start:
            px = price_at_or_before(times, prices, t)
            if px is None:
                raise RuntimeError(f"no causal recent price t={t}")
            z = float(pol) * (px - p0) / TICK
            out.extend([1.0, math.asinh(z)])
        else:
            out.extend([0.0, 0.0])
    return out


def onehot(value: Any, levels: tuple[str, ...]) -> list[float]:
    return [1.0 if str(value) == x else 0.0 for x in levels]


def scaled(v: Any, scale: float = 1.0) -> tuple[float, float]:
    if finite(v):
        return 1.0, math.asinh(float(v) / scale)
    return 0.0, 0.0


def event_structure_features(e: dict[str, Any] | None, cutoff: int, allow_birth_static: bool) -> list[float]:
    out: list[float] = []
    if e is None or int(e["t0_idx"]) > cutoff:
        return [0.0] * 48
    t0 = int(e["t0_idx"])
    c = event_confirm(e)
    static_ready = allow_birth_static or (c is not None and c <= cutoff)
    out.append(1.0)
    out.append(float(e["polarity"]) if static_ready else 0.0)
    out.extend(onehot(e.get("family") if static_ready else None, FAMILIES))
    dists = list(e.get("pre_family_distances") or [])[:3]
    dists += [None] * (3 - len(dists))
    for x in dists:
        k, v = scaled(x, 1.0) if static_ready else (0.0, 0.0)
        out.extend([k, v])
    feat = e.get("feature") or {}
    for key, sc in (("peak_abs", 1.0), ("pre_prominence", 1.0)):
        k, v = scaled(feat.get(key), sc) if static_ready else (0.0, 0.0)
        out.extend([k, v])
    tc = e.get("time_context") or {}
    if static_ready:
        hour = tc.get("local_hour")
        if finite(hour):
            theta = 2.0 * math.pi * float(hour) / 24.0
            out.extend([1.0, math.sin(theta), math.cos(theta)])
        else:
            out.extend([0.0, 0.0, 0.0])
        for key, sc in (("seconds_since_reopen_trade", 3600.0), ("week_position_fraction", 1.0)):
            k, v = scaled(tc.get(key), sc)
            out.extend([k, v])
    else:
        out.extend([0.0] * 7)
    ep = e.get("dynamic_endpoint") or {}
    if c is not None and c <= cutoff:
        out.extend([1.0, math.asinh(float(c - t0))])
        k, v = scaled(ep.get("structural_onset_offset_s"), 1.0)
        out.extend([k, v])
    else:
        out.extend([0.0] * 4)
    for key in ("exh_t50_s", "exh_t25_s", "exh_t10_s", "exh_zero_onset_within60_s"):
        v = feat.get(key)
        ready = (finite(v) and t0 + int(float(v)) <= cutoff) or (cutoff >= t0 + 60)
        if ready:
            out.extend([1.0, -1.0 if not finite(v) else math.asinh(float(v))])
        else:
            out.extend([0.0, 0.0])
    plus60 = cutoff >= t0 + 60
    out.extend(onehot(STATE_CODE.get(str(e.get("seed_state"))) if plus60 else None, STATE_CODES))
    out.extend(onehot(e.get("a_frozen_post_state") if plus60 else None, A_STATES))
    for key, sc in (("roll20_at60", 1.0), ("late_flow_pressure_41_60", 1.0), ("book_aligned_late_mean", 1.0), ("book_aligned_change_from_t0_window", 1.0)):
        k, v = scaled(feat.get(key), sc) if plus60 else (0.0, 0.0)
        out.extend([k, v])
    assert len(out) == 48, len(out)
    return out


def event_vector(e: dict[str, Any] | None, week: str, cutoff: int, cache, allow_birth_static: bool, view: str, predecessor: bool):
    if e is None or int(e["t0_idx"]) > cutoff:
        struct = event_structure_features(None, cutoff, allow_birth_static)
        price = [0.0] * (2 + 4 + 2 * len(PRICE_LANDMARKS) + 10)
        price2 = list(price)
        pol = [0.0, 0.0]
    else:
        struct = event_structure_features(e, cutoff, allow_birth_static)
        pol = [1.0, float(e["polarity"])]
        times, prices = cache["times"][week], cache["prices"][week]
        price = price_window_features(times, prices, int(e["t0_idx"]), cutoff, int(e["polarity"]))
        c = event_confirm(e)
        price2 = price_window_features(times, prices, c if c is not None and c <= cutoff else None, cutoff, int(e["polarity"]))
    if view == "FULL_CAUSAL":
        return np.asarray(struct + price + price2, float)
    if view == "NO_PRICE_CAUSAL":
        return np.asarray(struct, float)
    if view == "PRICE_POLARITY_ONLY":
        return np.asarray(pol + price + price2, float)
    raise ValueError(view)


def checkpoint(case: dict[str, Any], phase: str, sec: int):
    if phase == "PRIOR":
        confirms = [event_confirm(e) for e in case["preds"]]
        if any(c is None for c in confirms):
            return None
        t = max(int(c) for c in confirms) + int(sec)
        if t >= int(case["target"]["t0_idx"]):
            return None
        return t, int(case["target"]["t0_idx"] - t)
    if phase == "POST_BIRTH":
        t = int(case["target"]["t0_idx"]) + int(sec)
        return t, 0
    raise ValueError(phase)


def feature_row(case: dict[str, Any], stage: int, phase: str, sec: int, cache, view: str):
    z = checkpoint(case, phase, sec)
    if z is None:
        return None
    cutoff, lead = z
    parts = []
    for e in case["preds"]:
        parts.append(event_vector(e, case["week"], cutoff, cache, True, view, True))
    allow_target_static = phase == "POST_BIRTH"
    parts.append(event_vector(case["target"] if allow_target_static else None, case["week"], cutoff, cache, allow_target_static, view, False))
    for e in case.get("extra", []):
        born = e is not None and int(e["t0_idx"]) <= cutoff
        parts.append(event_vector(e if born else None, case["week"], cutoff, cache, born, view, False))
    return np.concatenate(parts), lead


def target_label(case: dict[str, Any], target: str):
    if target == "CONTINUATION":
        return str(int(case["continuation"]))
    if target == "EVENTUAL_DEPTH":
        return str(int(case["final_depth"]))
    if target == "CHAIN_TYPE_FAMILY":
        return case["chain_type"]
    raise ValueError(target)


def dataset(cases, stage, phase, sec, cache, view, target):
    xs, ys, weeks, leads, ids = [], [], [], [], []
    for c in cases:
        y = target_label(c, target)
        if y is None:
            continue
        fr = feature_row(c, stage, phase, sec, cache, view)
        if fr is None:
            continue
        x, lead = fr
        xs.append(x); ys.append(str(y)); weeks.append(c["week"]); leads.append(int(lead)); ids.append(c["id"])
    if not ys:
        return np.empty((0, 0)), np.asarray([], dtype=object), [], [], []
    return np.vstack(xs), np.asarray(ys, dtype=object), weeks, leads, ids


def split_cases(cases, blocks):
    return [c for c in cases if c["block"] in blocks]
