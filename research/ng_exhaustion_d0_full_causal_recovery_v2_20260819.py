#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ng_exhaustion_chain_recovery_features_v2_20260819 import (
    DATE, EXPECTED_EXACT, MODELS, PRIOR_AGES, VIEWS, PRIMARY_CHAIN_TYPE_POLICY,
    build_cases, load_events_full, load_lineage, load_price_cache,
)
from ng_exhaustion_chain_recovery_models_v2_20260819 import evaluate, price_increment

TARGETS = ("D0_TERMINALITY", "EVENTUAL_DEPTH", "FIRST_CHAIN_TYPE")


def direct_root_cases(events, lineage):
    cases, censored = build_cases(events, lineage, 1)
    d0_positive = []
    for c in cases:
        z = dict(c)
        z["continuation"] = 1 - int(c["continuation"])
        d0_positive.append(z)
    assert sum(int(c["continuation"] == 1) for c in d0_positive) == 135823
    assert sum(int(c["continuation"] == 0) for c in d0_positive) == 20562
    assert len(censored) == 37
    return cases, d0_positive, censored


def eval_target(model, original_cases, d0_cases, cache, target):
    if target == "D0_TERMINALITY":
        cases = d0_cases
        engine_target = "CONTINUATION"
    elif target == "EVENTUAL_DEPTH":
        cases = original_cases
        engine_target = "EVENTUAL_DEPTH"
    elif target == "FIRST_CHAIN_TYPE":
        cases = original_cases
        engine_target = "CHAIN_TYPE_FAMILY"
    else:
        raise ValueError(target)

    record = {"earliest": None, "tested": []}
    for root_age in PRIOR_AGES:
        views = {
            v: evaluate(model, cases, 1, "PRIOR", root_age, cache, v, engine_target)
            for v in VIEWS
        }
        point = {
            "phase": "ROOT_CAUSAL_BEFORE_NEXT_EVENT",
            "root_age_seconds_after_confirmation": int(root_age),
            "views": views,
            "incremental_price_value": price_increment(
                views["FULL_CAUSAL"], views["NO_PRICE_CAUSAL"]
            ),
        }
        record["tested"].append(point)
        if views["FULL_CAUSAL"]["independently_validated"]:
            record["earliest"] = {
                "timing_class": "ROOT_CAUSAL_BEFORE_NEXT_EVENT",
                "root_age_seconds_after_confirmation": int(root_age),
                "view": "FULL_CAUSAL",
            }
            break
    return record


def run_model(model, events, lineage, raw_dir):
    original_cases, d0_cases, censored = direct_root_cases(events, lineage)
    cache = load_price_cache(original_cases, raw_dir)
    results = {
        target: eval_target(model, original_cases, d0_cases, cache, target)
        for target in TARGETS
    }
    return {
        "status": "NG_D0_FULL_CAUSAL_RECOVERY_V2_MODEL_AGENT_COMPLETE",
        "date": DATE,
        "model": model,
        "independent_model_result": True,
        "cross_model_consensus_gate_used": False,
        "primary_information_view": "FULL_CAUSAL",
        "ablation_views": ["NO_PRICE_CAUSAL", "PRICE_POLARITY_ONLY"],
        "root_clock_semantics": {
            "ROOT_AGE": "SECONDS_AFTER_FROZEN_ROOT_CAUSAL_CONFIRMATION_WHILE_STRICTLY_BEFORE_THE_NEXT_CANONICAL_EVENT_T0",
            "H": "NOT_USED_FOR_D0_TERMINALITY_BECAUSE_A_TERMINAL_D0_HAS_NO_NEW_DESCENDANT_BIRTH",
        },
        "prior_target_polarity_requirement": "NONE; UNKNOWN_DESCENDANT_POLARITY_NEVER_FAILS_OR_BLOCKS_A_ROOT_PRIOR",
        "root_age_values_first_pass": list(PRIOR_AGES),
        "targets": list(TARGETS),
        "exact_d0_preserved_n": 135860,
        "executable_exact_d0_positive_n": 135823,
        "d1plus_continuation_control_n": 20562,
        "week_end_censored_d0_n": 37,
        "first_chain_type_population": "D1PLUS_ONLY; EXACT_D0_HAS_NO_CHAIN_TYPE_LABEL",
        "primary_chain_type_policy": PRIMARY_CHAIN_TYPE_POLICY,
        "first_chain_type_label_contract": "FROZEN_FIRST_DESCENDANT_P_O_S_X_STRUCTURAL_STATE_ONLY; SAME_FLIP_PRESERVED_SECONDARY_ANNOTATION",
        "D1_complement_crosscheck": "COMPARE_DIRECT_D0_WITH_ONE_MINUS_D1_CONTINUATION_ON_MATCHED_MODEL_VIEW_CHECKPOINT_ROWS; CALIBRATION_NOT_ADDITIONAL_EVIDENCE",
        "root_information_deeper_crosscheck": "COMPARE_FULL_ROOT_RETAINED_VS_ROOT_ABLATED_D2_D3_MODELS_ON_IDENTICAL_ROWS_AND_CHECKPOINTS",
        "results": results,
        "censored": censored,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "phase1": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie_1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    events = load_events_full(a.base, a.held)
    lineage = load_lineage(a.base_lineage, a.held_lineage)
    exact = Counter(int(r["depth"]) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT, (dict(sorted(exact.items())), EXPECTED_EXACT)

    result = run_model(a.model, events, lineage, a.raw_dir)
    result["frozen_exact_depth_counts"] = dict(sorted(exact.items()))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "model": a.model,
        "earliest": {k: v["earliest"] for k, v in result["results"].items()},
    }, indent=2))


if __name__ == "__main__":
    main()
