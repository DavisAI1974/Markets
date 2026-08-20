#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np

from ng_exhaustion_chain_recovery_features_v2_20260819 import (
    DATE,
    EXPECTED_EXACT,
    MODELS,
    SEED,
    VIEWS,
    build_cases,
    event_confirm,
    load_events_full,
    load_lineage,
    split_cases,
    target_label,
    event_vector,
)
import ng_exhaustion_live_checkpoint_state_20260819 as live

IMPLEMENTATION_REVISION = "V4_CONTINUOUS_PER_INSTANCE_TIMING"
PRIMARY_VIEW = "FULL_CAUSAL"
TIMING_POLICY = "NO_PREDECLARED_PRIOR_OR_H_GRID; SCORE_EVERY_CAUSAL_SECOND_AND_ALIGN_DECISION_TIME_TO_T0_ONLY_AFTER_PREDICTIONS_EXIST"
TARGET_T0_FEATURE_POLICY = "FROZEN_TARGET_T0_AND_TARGET_RELATIVE_FEATURES_WITHHELD_FROM_PRIMARY_MODEL; T0_USED_ONLY_FOR_POSTHOC_TIMING_COORDINATE"
TRAJECTORY_END_POLICY = "NO_FIXED_TIME_HORIZON; UNRESOLVED_STAGE_IS_CENSORED_AT_NEXT_ACTUAL_CANONICAL_BIRTH_OR_AUTHORITATIVE_WEEK_TAPE_END; CENSOR_TIME_IS_NOT_A_MODEL_FEATURE"


def load_cache(cases: list[dict[str, Any]], raw_dir: str):
    return live.load_cache(cases, raw_dir)


def predecessor_available_time(case: dict[str, Any]) -> int | None:
    confirms = [event_confirm(e) for e in case["preds"]]
    if any(x is None for x in confirms):
        return None
    return max(int(x) for x in confirms)


def stage_censor_time(case: dict[str, Any], cache) -> int:
    """First second that no longer belongs to this stage's prediction window.

    The next actual canonical birth after the candidate is a posthoc censoring
    boundary, never a model feature or countdown. If absent, authoritative tape end
    closes the historical opportunity window.
    """
    for e in case.get("extra", []):
        if e is not None:
            return int(e["t0_idx"])
    return int(math.floor(float(cache["last_trade"][case["week"]]))) + 1


def trajectory_bounds(case: dict[str, Any], cache) -> tuple[int, int] | None:
    start = predecessor_available_time(case)
    if start is None:
        return None
    end = stage_censor_time(case, cache) - 1
    if end < int(start):
        return None
    return int(start), int(end)


def continuous_feature_row(case: dict[str, Any], cutoff: int, cache, view: str = PRIMARY_VIEW):
    """Fixed-width feature at an arbitrary causal second.

    No target t0, seconds-to-birth, PRIOR/H identity, target polarity, target state,
    target-relative price anchor, or censor countdown is supplied. The model sees
    confirmed predecessor memory plus the observed raw market movie through cutoff.
    """
    start = predecessor_available_time(case)
    if start is None or int(cutoff) < int(start):
        return None
    parts = []
    for e in case["preds"]:
        parts.append(event_vector(e, case["week"], int(cutoff), cache, False, view, True))

    lp, lm = live.parts(cache, case["week"], int(cutoff))
    age = math.asinh(max(0, int(cutoff) - int(start)))
    if view == "FULL_CAUSAL":
        parts.append(np.asarray([age] + lp + lm, float))
    elif view == "NO_PRICE_CAUSAL":
        parts.append(np.asarray([age] + lm, float))
    elif view == "PRICE_POLARITY_ONLY":
        parts.append(np.asarray([age] + lp, float))
    else:
        raise ValueError(view)
    return np.concatenate(parts)


def birth_relative_coordinate(case: dict[str, Any], decision_time: int, stage: int) -> dict[str, Any]:
    """Convert a completed decision timestamp to a reporting coordinate only.

    A stopped-chain control never receives a synthetic H label. Only a true positive
    continuation at D1+ may be reported as H after its actual target birth.
    """
    t0 = int(case["target"]["t0_idx"])
    delta = int(decision_time) - t0
    if stage == 0:
        if delta < 0:
            return {"timing_class": "PRIOR_TO_CANDIDATE_T0", "seconds": int(-delta), "signed_seconds_from_candidate_t0": delta}
        if delta == 0:
            return {"timing_class": "CANDIDATE_T0", "seconds": 0, "signed_seconds_from_candidate_t0": 0}
        return {"timing_class": "CANDIDATE_PLUS", "seconds": int(delta), "signed_seconds_from_candidate_t0": delta}
    if int(case.get("continuation", 0)) != 1:
        if delta < 0:
            return {"timing_class": "PRIOR_TO_CONTROL_CANDIDATE", "seconds": int(-delta), "signed_seconds_from_candidate_t0": delta}
        if delta == 0:
            return {"timing_class": "CONTROL_CANDIDATE_T0", "seconds": 0, "signed_seconds_from_candidate_t0": 0}
        return {"timing_class": "CONTROL_CANDIDATE_PLUS", "seconds": int(delta), "signed_seconds_from_candidate_t0": delta}
    if delta < 0:
        return {"timing_class": "PRIOR", "seconds": int(-delta), "signed_seconds_from_t0": delta}
    if delta == 0:
        return {"timing_class": "T0", "seconds": 0, "signed_seconds_from_t0": 0}
    return {"timing_class": "H", "seconds": int(delta), "signed_seconds_from_t0": delta}


def deterministic_sample_times(case: dict[str, Any], cache, count: int, salt: str) -> list[int]:
    """Timing-agnostic training samples inside the natural stage trajectory.

    `count` is a compute/training budget only. No PRIOR/H/t0-relative timestamp is
    favored. OOT timing is still scored at every causal second until lock/censoring.
    """
    b = trajectory_bounds(case, cache)
    if b is None or count <= 0:
        return []
    lo, hi = b
    n = hi - lo + 1
    if n <= count:
        return list(range(lo, hi + 1))
    chosen = set()
    j = 0
    while len(chosen) < count:
        raw = f"{SEED}|{salt}|{case['id']}|{j}".encode()
        h = int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big")
        chosen.add(lo + (h % n))
        j += 1
    return sorted(chosen)


def case_truth(case: dict[str, Any], target: str) -> str | None:
    return target_label(case, target)
