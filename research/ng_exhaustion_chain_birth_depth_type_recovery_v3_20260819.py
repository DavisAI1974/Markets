#!/usr/bin/env python3
from __future__ import annotations

import ng_exhaustion_chain_birth_depth_type_recovery_v2_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate, price_increment

# Rebind the V2 main/IO shell to the V3 causal feature/model surface. The actual
# stage orchestration below is V3-native so T0 is a separate checkpoint, not H=0.
base.build_cases = build_cases
base.load_events_full = load_events_full
base.load_lineage = load_lineage
base.load_price_cache = load_price_cache
base.feature_row = feature_row
base.evaluate = evaluate
base.price_increment = price_increment
base.PRIOR_AGES = PRIOR_AGES
base.POST_H = POST_H
base.VIEWS = VIEWS

TARGETS = base.TARGETS


def _point_views(model, cases, stage, phase, sec, cache, target):
    views = {v: evaluate(model, cases, stage, phase, sec, cache, v, target) for v in VIEWS}
    return views, price_increment(views["FULL_CAUSAL"], views["NO_PRICE_CAUSAL"])


def model_stage(stage: int, model: str, events, lineage, raw_dir: str):
    cases, censored = build_cases(events, lineage, stage)
    cache = load_price_cache(cases, raw_dir)
    results = {}
    for target in TARGETS:
        record = {"earliest": None, "tested": []}

        # First-band PRIOR search. Any later-PRIOR refinement still outranks T0/H
        # and is handled by the dedicated hierarchy-refinement workflow.
        for age in PRIOR_AGES:
            views, inc = _point_views(model, cases, stage, "PRIOR", age, cache, target)
            point = {
                "phase": "PRIOR",
                "prior_age_seconds": int(age),
                "views": views,
                "incremental_price_value": inc,
            }
            record["tested"].append(point)
            if views["FULL_CAUSAL"]["independently_validated"]:
                record["earliest"] = {
                    "timing_class": "PRIOR_BEFORE_BIRTH",
                    "prior_age_seconds": int(age),
                    "view": "FULL_CAUSAL",
                }
                break

        # T0 is the actual frozen birth second, explicitly separate from H. The
        # model sees the live market through t0 and a newborn raw-price block, but
        # no future target polarity/family/state is required or leaked.
        if record["earliest"] is None:
            views, inc = _point_views(model, cases, stage, BIRTH_T0_PHASE, 0, cache, target)
            point = {
                "phase": BIRTH_T0_PHASE,
                "T0_seconds_after_birth": 0,
                "views": views,
                "incremental_price_value": inc,
            }
            record["tested"].append(point)
            if views["FULL_CAUSAL"]["independently_validated"]:
                record["earliest"] = {
                    "timing_class": "BIRTH_T0",
                    "T0_seconds_after_birth": 0,
                    "view": "FULL_CAUSAL",
                    "provisional_until_later_prior_exhausted": True,
                }

        if record["earliest"] is None:
            for h in POST_H:
                views, inc = _point_views(model, cases, stage, "POST_BIRTH", h, cache, target)
                point = {
                    "phase": "POST_BIRTH",
                    "H_seconds_after_t0": int(h),
                    "views": views,
                    "incremental_price_value": inc,
                }
                record["tested"].append(point)
                if views["FULL_CAUSAL"]["independently_validated"]:
                    record["earliest"] = {
                        "timing_class": "POST_BIRTH_EARLY_RECOGNITION",
                        "H_seconds_after_t0": int(h),
                        "view": "FULL_CAUSAL",
                        "provisional_until_later_prior_exhausted": True,
                    }
                    break
        results[target] = record

    return {
        "status": "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_V3_COMPLETE",
        "date": DATE,
        "stage": int(stage),
        "model": model,
        "independent_model_result": True,
        "cross_model_consensus_gate_used": False,
        "primary_information_view": "FULL_CAUSAL",
        "ablation_views": ["NO_PRICE_CAUSAL", "PRICE_POLARITY_ONLY"],
        "implementation_revision": IMPLEMENTATION_REVISION,
        "causal_overlap_fix_revision": CAUSAL_OVERLAP_FIX_REVISION,
        "causal_overlap_policy": CAUSAL_OVERLAP_POLICY,
        "live_market_policy": LIVE_MARKET_POLICY,
        "timing_ladder": list(TIMING_LADDER),
        "clock_semantics": {
            "PRIOR": "GLOBAL_CAUSAL_CHECKPOINT_STRICTLY_BEFORE_TARGET_T0",
            "T0": "THE_FROZEN_TARGET_BIRTH_SECOND_ITSELF; NOT_H_ZERO",
            "H": "SECONDS_AFTER_FROZEN_TARGET_T0_BEGINNING_AT_PLUS_1_ONLY",
        },
        "later_prior_hierarchy": "ANY_VALID_LATER_PREBIRTH_PRIOR_OUTRANKS_T0_OR_H; T0_H_EARLY_RESULTS_ARE_PROVISIONAL_UNTIL_LATER_PRIOR_SEARCH_IS_EXHAUSTED",
        "prior_target_polarity_requirement": "NONE; UNKNOWN_TARGET_POLARITY_NEVER_BLOCKS_OR_FAILS_PRIOR_OR_T0",
        "post_birth_static_policy": POST_BIRTH_STATIC_POLICY,
        "primary_chain_type_policy": PRIMARY_CHAIN_TYPE_POLICY,
        "prior_age_values": list(PRIOR_AGES),
        "birth_T0_values": [0],
        "post_birth_H_values": list(POST_H),
        "positive_continuation_n": int(sum(c["continuation"] for c in cases)),
        "negative_stop_n": int(len(cases) - sum(c["continuation"] for c in cases)),
        "censored_n": int(len(censored)),
        "chain_type_label_contract": "PRIMARY_TARGET_IS_FROZEN_NEXT_LINK_P_O_S_X_STRUCTURAL_STATE_ONLY; SAME_FLIP_TRANSITION_IS_SECONDARY_ANNOTATION_ONLY",
        "all_causal_knowledge_policy": "USE_EVERY_REPRESENTED_FACT_ONCE_ITS_OWN_CAUSAL_AVAILABILITY_TIME_HAS_PASSED; LIVE_MARKET_CONTINUES_THROUGH_T0; UNKNOWN_TARGET_POLARITY_NEVER_FAILS_PRIOR_OR_T0",
        "results": results,
        "censored": censored,
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False, "canonical_rows": False, "phase1": False, "phase2": False,
            "runway_clock": False, "permanent_frankie": False, "frankie_1": False,
            "spawn_py": False, "ssos_play": False,
        },
    }


def sparse_stage(stage: int, events, lineage, raw_dir: str):
    cases, censored = build_cases(events, lineage, stage)
    cache = load_price_cache(cases, raw_dir)
    rows = []
    for c in cases:
        points = []
        for age in PRIOR_AGES:
            fr = feature_row(c, stage, "PRIOR", age, cache, "FULL_CAUSAL")
            points.append({
                "phase": "PRIOR", "prior_age_seconds": age, "eligible": fr is not None,
                "lead_seconds": None if fr is None else int(fr[1]),
                "feature_count": None if fr is None else int(len(fr[0])),
            })
        fr = feature_row(c, stage, BIRTH_T0_PHASE, 0, cache, "FULL_CAUSAL")
        points.append({
            "phase": BIRTH_T0_PHASE, "T0_seconds_after_birth": 0, "eligible": fr is not None,
            "feature_count": None if fr is None else int(len(fr[0])),
        })
        for h in POST_H:
            fr = feature_row(c, stage, "POST_BIRTH", h, cache, "FULL_CAUSAL")
            points.append({
                "phase": "POST_BIRTH", "H_seconds_after_t0": h, "eligible": fr is not None,
                "feature_count": None if fr is None else int(len(fr[0])),
            })
        rows.append({
            "id": c["id"], "week": c["week"], "block": c["block"],
            "continuation": int(c["continuation"]),
            "final_depth_annotation_only": int(c["final_depth"]),
            "primary_chain_state_family_annotation_only": c.get("chain_state_family"),
            "same_flip_transition_annotation_only": c.get("chain_transition_annotation"),
            "legacy_combined_chain_type_annotation_only": c.get("chain_type"),
            "points": points,
        })
    return {
        "status": "NG_CHAIN_BIRTH_DEPTH_TYPE_SPARSE_CASE_STUDY_V3_COMPLETE",
        "date": DATE,
        "stage": stage,
        "low_support_case_study_only": True,
        "implementation_revision": IMPLEMENTATION_REVISION,
        "causal_overlap_fix_revision": CAUSAL_OVERLAP_FIX_REVISION,
        "causal_overlap_policy": CAUSAL_OVERLAP_POLICY,
        "live_market_policy": LIVE_MARKET_POLICY,
        "timing_ladder": list(TIMING_LADDER),
        "prior_age_values": list(PRIOR_AGES),
        "birth_T0_values": [0],
        "post_birth_H_values": list(POST_H),
        "clock_semantics": {
            "PRIOR": "STRICTLY_BEFORE_TARGET_T0",
            "T0": "TARGET_BIRTH_SECOND_ITSELF_NOT_H_ZERO",
            "H": "SECONDS_AFTER_FROZEN_TARGET_T0_BEGINNING_AT_PLUS_1_ONLY",
        },
        "later_prior_hierarchy": "ANY_VALID_LATER_PREBIRTH_PRIOR_OUTRANKS_T0_OR_H",
        "prior_target_polarity_requirement": "NONE",
        "post_birth_static_policy": POST_BIRTH_STATIC_POLICY,
        "primary_chain_type_policy": PRIMARY_CHAIN_TYPE_POLICY,
        "chain_type_label_contract": "PRIMARY_P_O_S_X_STATE_ONLY; SAME_FLIP_SECONDARY_ANNOTATION_ONLY",
        "cases": rows,
        "censored": censored,
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False, "canonical_rows": False, "phase1": False, "phase2": False,
            "runway_clock": False, "permanent_frankie": False, "frankie_1": False,
            "spawn_py": False, "ssos_play": False,
        },
    }


base.model_stage = model_stage
base.sparse_stage = sparse_stage


def main():
    base.main()


if __name__ == "__main__":
    main()
