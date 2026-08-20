#!/usr/bin/env python3
from __future__ import annotations

import numpy as np

from ng_exhaustion_chain_recovery_features_20260819 import *
import ng_exhaustion_chain_recovery_features_20260819 as v1

POST_BIRTH_STATIC_POLICY = "TARGET_SPECIFIC_STATIC_AND_POLARITY_REQUIRE_CAUSAL_CONFIRMATION; PRECONFIRM_TARGET_PRICE_IS_RAW_UNORIENTED_FROM_FROZEN_T0"
PRIMARY_CHAIN_TYPE_POLICY = "P_O_S_X_STRUCTURAL_STATE_ONLY; SAME_FLIP_IS_PRESERVED_SECONDARY_ANNOTATION_NOT_A_PRIMARY_PREDICTION_TARGET"
CAUSAL_OVERLAP_FIX_REVISION = "V3_CAUSAL_OVERLAP_SAFE_20260820"
CAUSAL_OVERLAP_POLICY = (
    "A_SUCCESSOR_MAY_BE_BORN_BEFORE_A_PREDECESSOR_CAUSALLY_CONFIRMS; "
    "PRECONFIRM_PREDECESSOR_STRUCTURE_AND_POLARITY_REMAIN_WITHHELD; "
    "ONLY_RAW_UNORIENTED_PRICE_IS_SERVED_UNTIL_OWN_CONFIRMATION"
)


def build_cases(events, lineage, stage: int):
    cases, censored = v1.build_cases(events, lineage, stage)
    for c in cases:
        combined = c.get("chain_type")
        c["chain_transition_annotation"] = None
        if combined and "|" in str(combined):
            state, rel = str(combined).split("|", 1)
            c["chain_state_family"] = state
            c["chain_transition_annotation"] = rel
        else:
            c["chain_state_family"] = None
    return cases, censored


def event_structure_features(e: dict | None, cutoff: int, allow_birth_static: bool = False) -> list[float]:
    """V2: no target-specific structural fact exists as a feature before causal confirmation.

    `allow_birth_static` is retained only for call compatibility and is deliberately ignored.
    PRIOR predecessors are confirmed by their checkpoint construction. At successor T0/H,
    a valid overlapping predecessor can still be unconfirmed; it remains structurally zero
    until its own causal confirmation. Newborn/extra events follow the same availability rule.
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
        # Frozen chains explicitly contain overlap cases where a successor is born
        # before the predecessor's endpoint can be causally confirmed. That is a
        # valid information state, not a clock failure. The overlapping predecessor
        # is therefore treated like any born-but-unconfirmed event: its frozen
        # structure and polarity stay withheld while its causal raw, unoriented
        # price path remains visible. PRIOR checkpoints still require predecessor
        # confirmation through checkpoint(); this applies at successor T0/later H.
        del predecessor
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


def target_label(case: dict, target: str):
    if target == "CONTINUATION":
        return str(int(case["continuation"]))
    if target == "EVENTUAL_DEPTH":
        return str(int(case["final_depth"]))
    if target == "CHAIN_TYPE_FAMILY":
        # Primary type recovery is structural state/family only. SAME/FLIP is
        # deliberately not part of this label and therefore cannot cause a PRIOR
        # to fail, become ineligible, or be scored as a polarity prediction.
        return case.get("chain_state_family")
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
        xs.append(x)
        ys.append(str(y))
        weeks.append(c["week"])
        leads.append(int(lead))
        ids.append(c["id"])
    if not ys:
        return np.empty((0, 0)), np.asarray([], dtype=object), [], [], []
    return np.vstack(xs), np.asarray(ys, dtype=object), weeks, leads, ids
