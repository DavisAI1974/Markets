#!/usr/bin/env python3
from __future__ import annotations

import numpy as np

import ng_exhaustion_d1_d5_predictability_agents_20260819 as base


def cases_for_depth_preserve_all(events, lineage, depth):
    rows = []
    for lr in lineage:
        if int(lr.get("all_model_consecutive_positive_depth", 0)) != depth:
            continue
        w = lr["week_sunday"]
        i = int(lr["origin_sequence_index"])
        rs = events.get(w, {})
        preds = [rs.get(i + j) for j in range(depth)]
        target = rs.get(i + depth)
        nxt = rs.get(i + depth + 1)
        if any(x is None for x in preds) or target is None:
            # A structurally impossible index mismatch is preserved as an explicit
            # source-integrity failure by the workflow invariant rather than
            # manufactured into a model row.
            continue
        block = base.FOLD_BLOCK.get(str(lr.get("fold")))
        if block is None:
            continue
        y = base.target_vector(target)
        rows.append({
            "id": f"{w}|{lr['origin_event_id']}|D{depth}",
            "week": w,
            "block": block,
            "preds": preds,
            "target": target,
            "next": nxt,
            "y": y,
            "model_target_eligible": bool(y is not None),
        })
    return rows


def dataset_preserve_all(cases, depth, mode, h, cache, which):
    xs, ys, ids, weeks = [], [], [], []
    for c in cases:
        if c.get("y") is None:
            continue
        fp = base.feature_pair(c, depth, mode, h, cache)
        if fp is None:
            continue
        x = fp[0] if which == "long" else fp[1]
        xs.append(x)
        ys.append(c["y"])
        ids.append(c["id"])
        weeks.append(c["week"])
    if not ys:
        return np.empty((0, 0)), np.empty((0, 22)), [], []
    X = np.vstack(xs) if xs[0].size else np.empty((len(xs), 0))
    return X, np.vstack(ys), ids, weeks


base.cases_for_depth = cases_for_depth_preserve_all
base.dataset = dataset_preserve_all

if __name__ == "__main__":
    base.main()
