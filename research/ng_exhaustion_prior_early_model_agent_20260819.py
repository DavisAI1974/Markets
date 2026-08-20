#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

import ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819 as v2

base = v2.base

EXPECTED_EXACT = {0: 135860, 1: 18837, 2: 1592, 3: 124, 4: 8, 5: 1}
EARLY_H = (1, 2, 3, 4, 5)
MODELS = tuple(base.MODELS)


def load_common(a):
    events = base.load_events(a.base, a.held)
    lineage = base.load_lineage(a.base_lineage, a.held_lineage)
    exact = Counter(int(r["depth"]) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT, (dict(sorted(exact.items())), EXPECTED_EXACT)
    return events, lineage, exact


def target_cases(target, events, lineage):
    if target == "D0":
        cases, censored = base.birth_cases(events, lineage, 1)
        out = []
        for c in cases:
            z = dict(c)
            z["y"] = 1 - int(c["y"])
            out.append(z)
        assert sum(int(c["y"] == 1) for c in out) == 135823
        assert sum(int(c["y"] == 0) for c in out) == 20562
        assert len(censored) == 37
        return 1, out, censored
    stage = int(target[1:])
    cases, censored = base.birth_cases(events, lineage, stage)
    return stage, cases, censored


def load_cache(cases, raw_dir):
    weeks = sorted({c["week"] for c in cases})
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks:
        t, p = base.load_week_prices(raw_dir, w)
        if len(t) == 0:
            raise RuntimeError(f"authoritative raw price tape missing target week={w}")
        cache["times"][w] = t
        cache["prices"][w] = p
    return cache


def polarity_only_snapshot(cache, week, event, h):
    # PRIOR eligibility is still enforced by base.feature_pair before this call.
    # The full price-path evaluation is always run first and therefore enforces
    # per-occurrence raw-tape/baseline integrity before this ablation is scored.
    return np.asarray([float(event["polarity"])], dtype=float)


def independent_validation(model_eval, stage):
    # This is an independent per-model/per-view validation check. It is NOT a
    # cross-model vote and is never combined into a 2-of-3 consensus gate.
    return bool(base.model_pass(model_eval, stage))


def price_increment(price_eval, polarity_eval):
    out = {}
    for block in ("validation", "confirmation", "held"):
        p = price_eval.get("blocks", {}).get(block, {})
        q = polarity_eval.get("blocks", {}).get(block, {})
        if not p or not q or not p.get("n") or not q.get("n"):
            out[block] = {"n": 0}
            continue
        if p.get("n") != q.get("n"):
            raise RuntimeError(f"price/polarity ablation row-count mismatch block={block}: {p.get('n')} vs {q.get('n')}")
        rec = {
            "n": int(p["n"]),
            "price_minus_polarity_log_loss_improvement": float(q["log_loss"] - p["log_loss"]),
            "price_minus_polarity_brier_improvement": float(q["brier"] - p["brier"]),
            "price_log_loss": float(p["log_loss"]),
            "polarity_only_log_loss": float(q["log_loss"]),
            "price_brier": float(p["brier"]),
            "polarity_only_brier": float(q["brier"]),
        }
        if p.get("roc_auc") is not None and q.get("roc_auc") is not None:
            rec["price_minus_polarity_auc_delta"] = float(p["roc_auc"] - q["roc_auc"])
        else:
            rec["price_minus_polarity_auc_delta"] = None
        out[block] = rec
    return out


def evaluate_views(model, cases, stage, h, cache):
    # Full causal predecessor price path is primary and runs first so that raw
    # tape integrity fails closed before the polarity-only ablation is allowed.
    saved = base.cache_snapshot
    base.cache_snapshot = v2.causal_second_path
    try:
        price_eval = base.paired_eval(model, cases, stage, "prior", h, cache)
    finally:
        base.cache_snapshot = saved

    saved = base.cache_snapshot
    base.cache_snapshot = polarity_only_snapshot
    try:
        polarity_eval = base.paired_eval(model, cases, stage, "prior", h, cache)
    finally:
        base.cache_snapshot = saved

    price_valid = independent_validation(price_eval, stage)
    polarity_valid = independent_validation(polarity_eval, stage)
    return {
        "H_seconds": int(h),
        "model": model,
        "views": {
            "POLARITY_PLUS_PRICE_PATH": {
                "independently_validated": price_valid,
                "evaluation": price_eval,
            },
            "POLARITY_ONLY": {
                "independently_validated": polarity_valid,
                "evaluation": polarity_eval,
            },
        },
        "incremental_prebirth_price_value": price_increment(price_eval, polarity_eval),
        "any_view_independently_validated": bool(price_valid or polarity_valid),
    }


def model_agent(target, model, events, lineage, raw_dir, exact):
    stage, cases, censored = target_cases(target, events, lineage)
    if target in ("D4", "D5"):
        raise RuntimeError("D4/D5 use sparse case-study mode, not model mode")
    cache = load_cache(cases, raw_dir)
    tested = []
    pos = sum(int(c["y"] == 1) for c in cases)
    neg = len(cases) - pos
    earliest = {"POLARITY_PLUS_PRICE_PATH": None, "POLARITY_ONLY": None}
    for h in EARLY_H:
        z = evaluate_views(model, cases, stage, h, cache)
        tested.append(z)
        for view in earliest:
            if earliest[view] is None and z["views"][view]["independently_validated"]:
                earliest[view] = int(h)
    return {
        "status": "NG_EXHAUSTION_PRIOR_EARLY_MODEL_AGENT_COMPLETE",
        "date": "2026-08-19",
        "target": target,
        "model": model,
        "stage_for_model": int(stage),
        "search_class": "PRIOR_ONLY_BEFORE_TARGET_BIRTH",
        "fallback_clock_used": False,
        "cross_model_consensus_gate_used": False,
        "H_values": list(EARLY_H),
        "positive_n": int(pos),
        "negative_n": int(neg),
        "censored_n": int(len(censored)),
        "frozen_exact_depth_counts": dict(sorted(exact.items())),
        "price_structure_mode": v2.PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_availability_used_as_feature": False,
        "prebirth_information_views": ["POLARITY_ONLY", "POLARITY_PLUS_PRICE_PATH"],
        "earliest_independently_validated_H_by_view": earliest,
        "tested_points": tested,
        "postbirth_price_policy": "WHEN_TARGET_IS_BORN_ADD_TARGET_OWN_CAUSAL_PRICE_PATH_FOR_RECOGNITION_MANAGEMENT_AND_DOWNSTREAM_PREDICTION_WITHOUT_LEAKING_BACKWARD",
        "characteristics_accessed": False,
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


def sparse_case_study(target, events, lineage, raw_dir, exact):
    stage, cases, censored = target_cases(target, events, lineage)
    assert stage in (4, 5)
    cache = load_cache(cases, raw_dir)
    rows = []
    for c in cases:
        tt = int(c["target"]["t0_idx"])
        points = []
        for h in EARLY_H:
            cs = [base.event_confirm(e) for e in c["preds"]]
            eligible = all(x is not None for x in cs) and max(int(x) + h for x in cs) <= tt
            rec = {"H_seconds": int(h), "prior_eligible": bool(eligible)}
            if eligible:
                rec["lead_seconds"] = int(tt - max(int(x) + h for x in cs))
                rec["predecessor_polarities"] = [int(e["polarity"]) for e in c["preds"]]
                # Force causal path construction for every predecessor occurrence.
                rec["predecessor_path_lengths"] = [
                    int(len(v2.causal_second_path(cache, c["week"], e, h)) - 1)
                    for e in c["preds"]
                ]
            points.append(rec)
        rows.append({
            "id": c["id"],
            "week": c["week"],
            "block": c["block"],
            "birth_label": int(c["y"]),
            "final_depth_annotation_only": int(c["final_depth"]),
            "prior_points": points,
        })
    return {
        "status": "NG_EXHAUSTION_PRIOR_EARLY_SPARSE_CASE_STUDY_COMPLETE",
        "date": "2026-08-19",
        "target": target,
        "stage": int(stage),
        "search_class": "PRIOR_ONLY_BEFORE_TARGET_BIRTH",
        "fallback_clock_used": False,
        "cross_model_consensus_gate_used": False,
        "H_values": list(EARLY_H),
        "positive_n": int(sum(c["y"] for c in cases)),
        "negative_n": int(len(cases) - sum(c["y"] for c in cases)),
        "censored_n": int(len(censored)),
        "frozen_exact_depth_counts": dict(sorted(exact.items())),
        "price_structure_mode": v2.PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_availability_used_as_feature": False,
        "prebirth_information_views_preserved": ["POLARITY_ONLY", "POLARITY_PLUS_PRICE_PATH"],
        "postbirth_price_policy": "WHEN_TARGET_IS_BORN ADD ITS OWN CAUSAL PRICE PATH FOR DOWNSTREAM STATE WORK; NEVER LEAK IT INTO PRIOR",
        "sparse_cases": rows,
        "low_support_case_study_only": True,
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
    ap.add_argument("--target", required=True, choices=("D0", "D1", "D2", "D3", "D4", "D5"))
    ap.add_argument("--model", required=True, choices=MODELS + ("case_study",))
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    events, lineage, exact = load_common(a)
    if a.target in ("D4", "D5"):
        assert a.model == "case_study"
        result = sparse_case_study(a.target, events, lineage, a.raw_dir, exact)
    else:
        assert a.model in MODELS
        result = model_agent(a.target, a.model, events, lineage, a.raw_dir, exact)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "target": result["target"],
        "model": result.get("model"),
        "H_values": result["H_values"],
        "cross_model_consensus_gate_used": result["cross_model_consensus_gate_used"],
        "earliest_by_view": result.get("earliest_independently_validated_H_by_view"),
    }, indent=2))


if __name__ == "__main__":
    main()
