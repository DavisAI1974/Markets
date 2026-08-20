#!/usr/bin/env python3
from __future__ import annotations

import numpy as np

from ng_exhaustion_chain_recovery_features_20260819 import *
import ng_exhaustion_chain_recovery_features_20260819 as v1

POST_BIRTH_STATIC_POLICY = "TARGET_SPECIFIC_STATIC_AND_POLARITY_REQUIRE_CAUSAL_CONFIRMATION; PRECONFIRM_TARGET_PRICE_IS_RAW_UNORIENTED_FROM_FROZEN_T0"


def event_structure_features(e: dict | None, cutoff: int, allow_birth_static: bool = False) -> list[float]:
    """V2: no target-specific structural fact exists as a feature before causal confirmation.

    `allow_birth_static` is retained only for call compatibility and is deliberately ignored.
    Predecessors are already confirmed by their checkpoint construction, so they retain the
    same structural information as V1. Newborn/extra events remain structurally zero until
    their own causal confirmation is reached.
    """
    if e is None or int(e["t0_idx"]) > cutoff:
        return [0.0] * 48
    c = event_confirm(e)
    if c is None or int(c) > cutoff:
        return [0.0] * 48
    return v1.event_structure_features(e, cutoff, False)


def event_vector(e: dict | None, week: str, cutoff: int, cache, allow_birth_static: bool, view: str, predecessor: bool):
    width = 2 + 4 + 2 * len(PRICE_LANDMARKS) + 10
    if e is None or int(e["t0_idx"]) > cutoff:
        struct = [0.0] * 48
        price = [0.0] * width
        price2 = [0.0] * width
        pol = [0.0, 0.0]
    else:
        c = event_confirm(e)
        known = c is not None and int(c) <= cutoff
        if predecessor and not known:
            raise RuntimeError(f"predecessor reached checkpoint before causal confirmation event={e.get('event_id')} cutoff={cutoff} confirm={c}")
        struct = event_structure_features(e, cutoff, False)
        pol = [1.0, float(e["polarity"])] if known else [0.0, 0.0]
        times, prices = cache["times"][week], cache["prices"][week]
        # Price itself is causal market data. Before the newborn event is confirmed,
        # retain a raw/unoriented t0-anchored path rather than leaking frozen polarity.
        orient = int(e["polarity"]) if known else 1
        price = price_window_features(times, prices, int(e["t0_idx"]), cutoff, orient)
        price2 = price_window_features(
            times,
            prices,
            int(c) if known else None,
            cutoff,
            int(e["polarity"]) if known else 1,
        )
    if view == "FULL_CAUSAL":
        return np.asarray(struct + price + price2, float)
    if view == "NO_PRICE_CAUSAL":
        return np.asarray(struct, float)
    if view == "PRICE_POLARITY_ONLY":
        return np.asarray(pol + price + price2, float)
    raise ValueError(view)


def feature_row(case: dict, stage: int, phase: str, sec: int, cache, view: str):
    z = checkpoint(case, phase, sec)
    if z is None:
        return None
    cutoff, lead = z
    parts = []
    for e in case["preds"]:
        parts.append(event_vector(e, case["week"], cutoff, cache, False, view, True))
    # PRIOR has no target vector. POST_BIRTH may use raw newborn price immediately,
    # while target-specific polarity/structure remains gated by causal confirmation.
    parts.append(event_vector(
        case["target"] if phase == "POST_BIRTH" else None,
        case["week"], cutoff, cache, False, view, False,
    ))
    for e in case.get("extra", []):
        born = e is not None and int(e["t0_idx"]) <= cutoff
        parts.append(event_vector(e if born else None, case["week"], cutoff, cache, False, view, False))
    return np.concatenate(parts), lead


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
        xs.append(x)
        ys.append(str(y))
        weeks.append(c["week"])
        leads.append(int(lead))
        ids.append(c["id"])
    if not ys:
        return np.empty((0, 0)), np.asarray([], dtype=object), [], [], []
    return np.vstack(xs), np.asarray(ys, dtype=object), weeks, leads, ids
