#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

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


def model_agent(target, model, events, lineage, raw_dir, exact):
    stage, cases, censored = target_cases(target, events, lineage)
    if target in ("D4", "D5"):
        raise RuntimeError("D4/D5 use sparse case-study mode, not model mode")
    cache = load_cache(cases, raw_dir)
    tested = []
    pos = sum(int(c["y"] == 1) for c in cases)
    neg = len(cases) - pos
    for h in EARLY_H:
        z = base.paired_eval(model, cases, stage, "prior", h, cache)
        ok = base.model_pass(z, stage)
        tested.append({
            "H_seconds": int(h),
            "model": model,
            "passes_gate": bool(ok),
            "evaluation": z,
        })
    return {
        "status": "NG_EXHAUSTION_PRIOR_EARLY_MODEL_AGENT_COMPLETE",
        "date": "2026-08-19",
        "target": target,
        "model": model,
        "stage_for_model": int(stage),
        "search_class": "PRIOR_ONLY_BEFORE_TARGET_BIRTH",
        "fallback_clock_used": False,
        "H_values": list(EARLY_H),
        "positive_n": int(pos),
        "negative_n": int(neg),
        "censored_n": int(len(censored)),
        "frozen_exact_depth_counts": dict(sorted(exact.items())),
        "price_structure_mode": v2.PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_availability_used_as_feature": False,
        "tested_points": tested,
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
        "H_values": list(EARLY_H),
        "positive_n": int(sum(c["y"] for c in cases)),
        "negative_n": int(len(cases) - sum(c["y"] for c in cases)),
        "censored_n": int(len(censored)),
        "frozen_exact_depth_counts": dict(sorted(exact.items())),
        "price_structure_mode": v2.PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_availability_used_as_feature": False,
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
    }, indent=2))


if __name__ == "__main__":
    main()
