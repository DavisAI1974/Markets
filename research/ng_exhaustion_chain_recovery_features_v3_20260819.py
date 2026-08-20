#!/usr/bin/env python3
from __future__ import annotations

import numpy as np

from ng_exhaustion_chain_recovery_features_v2_20260819 import *
import ng_exhaustion_chain_recovery_features_v2_20260819 as v2
import ng_exhaustion_live_checkpoint_state_20260819 as live

LIVE_MARKET_POLICY = live.POLICY
IMPLEMENTATION_REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE"


def load_price_cache(cases, raw_dir: str):
    return live.load_cache(cases, raw_dir)


def feature_row(case: dict, stage: int, phase: str, sec: int, cache, view: str):
    z = checkpoint(case, phase, sec)
    if z is None:
        return None
    cutoff, lead = z
    parts = []
    for e in case["preds"]:
        parts.append(v2.event_vector(e, case["week"], cutoff, cache, False, view, True))

    # PRIOR contains no synthetic/future target block at all. The live market
    # vector below still contains everything actually observable through cutoff.
    if phase == "POST_BIRTH":
        parts.append(v2.event_vector(case["target"], case["week"], cutoff, cache, False, view, False))
        for e in case.get("extra", []):
            born = e is not None and int(e["t0_idx"]) <= cutoff
            parts.append(v2.event_vector(e if born else None, case["week"], cutoff, cache, False, view, False))

    # The market itself is always observable: dense raw price direction, the full
    # last-61-second roll20/dipole path, signed flow, book path and causal clock.
    lp, lm = live.parts(cache, case["week"], cutoff)
    if view == "FULL_CAUSAL":
        parts.append(np.asarray(lp + lm, float))
    elif view == "NO_PRICE_CAUSAL":
        parts.append(np.asarray(lm, float))
    elif view == "PRICE_POLARITY_ONLY":
        parts.append(np.asarray(lp, float))
    else:
        raise ValueError(view)
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
        xs.append(x); ys.append(str(y)); weeks.append(c["week"]); leads.append(int(lead)); ids.append(c["id"])
    if not ys:
        return np.empty((0, 0)), np.asarray([], dtype=object), [], [], []
    return np.vstack(xs), np.asarray(ys, dtype=object), weeks, leads, ids
