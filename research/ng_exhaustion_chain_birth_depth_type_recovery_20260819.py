#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ng_exhaustion_chain_recovery_features_20260819 import (
    DATE, MODELS, EXPECTED_EXACT, PRIOR_AGES, POST_H, VIEWS,
    build_cases, load_events_full, load_lineage, load_price_cache,
    feature_row, event_structure_features,
)
from ng_exhaustion_chain_recovery_models_20260819 import evaluate, price_increment

def model_stage(stage: int, model: str, events, lineage, raw_dir: str):
    cases, censored = build_cases(events, lineage, stage)
    cache = load_price_cache(cases, raw_dir)
    targets = ("CONTINUATION", "EVENTUAL_DEPTH", "CHAIN_TYPE_FAMILY")
    results = {}
    for target in targets:
        record = {"earliest": None, "tested": []}
        for age in PRIOR_AGES:
            views = {v: evaluate(model, cases, stage, "PRIOR", age, cache, v, target) for v in VIEWS}
            point = {"phase": "PRIOR", "prior_age_seconds": int(age), "views": views, "incremental_price_value": price_increment(views["FULL_CAUSAL"], views["NO_PRICE_CAUSAL"])}
            record["tested"].append(point)
            if views["FULL_CAUSAL"]["independently_validated"]:
                record["earliest"] = {"timing_class": "PRIOR_BEFORE_BIRTH", "prior_age_seconds": int(age), "view": "FULL_CAUSAL"}
                break
        if record["earliest"] is None:
            for h in POST_H:
                views = {v: evaluate(model, cases, stage, "POST_BIRTH", h, cache, v, target) for v in VIEWS}
                point = {"phase": "POST_BIRTH", "H_seconds_after_t0": int(h), "views": views, "incremental_price_value": price_increment(views["FULL_CAUSAL"], views["NO_PRICE_CAUSAL"])}
                record["tested"].append(point)
                if views["FULL_CAUSAL"]["independently_validated"]:
                    record["earliest"] = {"timing_class": "POST_BIRTH_EARLY_RECOGNITION", "H_seconds_after_t0": int(h), "view": "FULL_CAUSAL"}
                    break
        results[target] = record
    return {
        "status": "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_COMPLETE",
        "date": DATE,
        "stage": int(stage),
        "model": model,
        "independent_model_result": True,
        "cross_model_consensus_gate_used": False,
        "primary_information_view": "FULL_CAUSAL",
        "ablation_views": ["NO_PRICE_CAUSAL", "PRICE_POLARITY_ONLY"],
        "clock_semantics": {"PRIOR": "GLOBAL_CAUSAL_CHECKPOINT_AFTER_LATEST_PREDECESSOR_CONFIRMATION_STRICTLY_BEFORE_TARGET_T0", "H": "SECONDS_AFTER_FROZEN_TARGET_T0_ONLY"},
        "prior_age_values": list(PRIOR_AGES),
        "post_birth_H_values": list(POST_H),
        "positive_continuation_n": int(sum(c["continuation"] for c in cases)),
        "negative_stop_n": int(len(cases) - sum(c["continuation"] for c in cases)),
        "censored_n": int(len(censored)),
        "chain_type_label_contract": "FROZEN_NEXT_LINK_STATE_P_O_S_X_PLUS_SAME_FLIP; ORDERED_STAGE_LABELS_FORM_THE_CHAIN_GRAMMAR",
        "all_causal_knowledge_policy": "USE_EVERY_CANONICAL_FACT_ONCE_ITS_OWN_CAUSAL_AVAILABILITY_TIME_HAS_PASSED; NEVER_USE_FUTURE_LINEAGE_OR_FUTURE_TARGET_FACTS_EARLY",
        "results": results,
        "censored": censored,
        "promotion_performed": False,
        "protected_mutations": {"detector": False, "canonical_rows": False, "phase1": False, "phase2": False, "runway_clock": False, "permanent_frankie": False, "frankie_1": False, "spawn_py": False, "ssos_play": False},
    }


def sparse_stage(stage: int, events, lineage, raw_dir: str):
    cases, censored = build_cases(events, lineage, stage)
    cache = load_price_cache(cases, raw_dir)
    rows = []
    for c in cases:
        points = []
        for age in PRIOR_AGES:
            fr = feature_row(c, stage, "PRIOR", age, cache, "FULL_CAUSAL")
            points.append({"phase": "PRIOR", "prior_age_seconds": age, "eligible": fr is not None, "lead_seconds": None if fr is None else int(fr[1]), "feature_count": None if fr is None else int(len(fr[0]))})
        for h in POST_H:
            fr = feature_row(c, stage, "POST_BIRTH", h, cache, "FULL_CAUSAL")
            points.append({"phase": "POST_BIRTH", "H_seconds_after_t0": h, "eligible": fr is not None, "feature_count": None if fr is None else int(len(fr[0]))})
        rows.append({"id": c["id"], "week": c["week"], "block": c["block"], "continuation": int(c["continuation"]), "final_depth_annotation_only": int(c["final_depth"]), "chain_type_annotation_only": c["chain_type"], "points": points})
    return {
        "status": "NG_CHAIN_BIRTH_DEPTH_TYPE_SPARSE_CASE_STUDY_COMPLETE",
        "date": DATE,
        "stage": stage,
        "low_support_case_study_only": True,
        "prior_age_values": list(PRIOR_AGES),
        "post_birth_H_values": list(POST_H),
        "clock_semantics": {"PRIOR": "STRICTLY_BEFORE_TARGET_T0", "H": "SECONDS_AFTER_FROZEN_TARGET_T0_ONLY"},
        "chain_type_label_contract": "FROZEN_NEXT_LINK_STATE_P_O_S_X_PLUS_SAME_FLIP",
        "cases": rows,
        "censored": censored,
        "promotion_performed": False,
        "protected_mutations": {"detector": False, "canonical_rows": False, "phase1": False, "phase2": False, "runway_clock": False, "permanent_frankie": False, "frankie_1": False, "spawn_py": False, "ssos_play": False},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, type=int, choices=(1, 2, 3, 4, 5))
    ap.add_argument("--model", required=True, choices=MODELS + ("case_study",))
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
    if a.stage >= 4:
        if a.model != "case_study":
            raise SystemExit("D4/D5 require case_study")
        result = sparse_stage(a.stage, events, lineage, a.raw_dir)
    else:
        if a.model not in MODELS:
            raise SystemExit("D1-D3 require a predeclared model")
        result = model_stage(a.stage, a.model, events, lineage, a.raw_dir)
    result["frozen_exact_depth_counts"] = dict(sorted(exact.items()))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "stage": a.stage, "model": a.model, "earliest": {k: v.get("earliest") for k, v in result.get("results", {}).items()}}, indent=2))


if __name__ == "__main__":
    main()
