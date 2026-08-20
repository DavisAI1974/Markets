#!/usr/bin/env python3
from __future__ import annotations

import numpy as np

from ng_exhaustion_chain_recovery_features_v2_20260819 import *
import ng_exhaustion_chain_recovery_features_v2_20260819 as v2
import ng_exhaustion_live_checkpoint_state_20260819 as live

LIVE_MARKET_POLICY = live.POLICY
IMPLEMENTATION_REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE_T0"
BIRTH_T0_PHASE = "BIRTH_T0"
TIMING_LADDER = ("PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5")


def load_price_cache(cases, raw_dir: str):
    return live.load_cache(cases, raw_dir)


def checkpoint(case: dict, phase: str, sec: int):
    """Return the exact causal cutoff for PRIOR, birth T0, or post-birth H.

    PRIOR remains strictly before target t0. BIRTH_T0 is the target's frozen birth
    second itself and is deliberately not called H=0. POST_BIRTH H begins only at
    +1 second after t0.
    """
    if phase == "PRIOR":
        return v2.checkpoint(case, phase, sec)
    if phase == BIRTH_T0_PHASE:
        if int(sec) != 0:
            raise ValueError("BIRTH_T0 requires sec=0")
        return int(case["target"]["t0_idx"]), 0
    if phase == "POST_BIRTH":
        if int(sec) <= 0:
            raise ValueError("POST_BIRTH H must be >=1; use BIRTH_T0 for the birth second")
        return v2.checkpoint(case, phase, sec)
    raise ValueError(phase)


def feature_row(case: dict, stage: int, phase: str, sec: int, cache, view: str):
    z = checkpoint(case, phase, sec)
    if z is None:
        return None
    cutoff, lead = z
    parts = []
    for e in case["preds"]:
        parts.append(v2.event_vector(e, case["week"], cutoff, cache, False, view, True))

    # PRIOR contains no synthetic/future target block at all. At the actual birth
    # second T0 and after, raw newborn price may be represented immediately. Frozen
    # target polarity/family/state remain governed by their own causal availability
    # inside event_vector and are never required merely because t0 has occurred.
    if phase in (BIRTH_T0_PHASE, "POST_BIRTH"):
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
