#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ng_exhaustion_chain_phase1_causal_54w_20260817 as base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fragments", nargs="+")
    ap.add_argument("--out", default="NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_54W_20260817.json")
    a = ap.parse_args()

    expected_h = list(base.HORIZONS)
    expected_models = list(base.MODELS)
    expected_folds = [name for _, _, name in base.FOLDS]
    expected_depths = [str(d) for d in base.DEPTHS]

    fragments = {}
    common_weeks = None
    for p in a.fragments:
        z = json.load(open(p))
        if z.get("status") != "PHASE1_CAUSAL_EXECUTABLE_54W_SLICE_COMPLETE":
            raise SystemExit(f"bad slice status: {p}")
        h = int(z["horizon_seconds"])
        model = z["model"]
        key = (h, model)
        if h not in expected_h or model not in expected_models or key in fragments:
            raise SystemExit(f"unexpected/duplicate causal slice {key}")
        if z.get("week_count") != 54 or z.get("temporarily_excluded_week") != "20260329":
            raise SystemExit(f"causal slice base drift {key}")
        if z.get("characteristics_accessed") is not False:
            raise SystemExit(f"causal characteristics wall drift {key}")
        if z.get("timing_accessed_only_for_causal_availability") is not True:
            raise SystemExit(f"causal timing wall drift {key}")
        if z.get("runway_clock_mutated") is not False or z.get("permanent_frankie_mutated") is not False:
            raise SystemExit(f"protected-state mutation flag {key}")
        weeks = z["weeks"]
        if common_weeks is None:
            common_weeks = weeks
        elif weeks != common_weeks:
            raise SystemExit(f"week roster drift {key}")
        if list(z["folds"].keys()) != expected_folds and set(z["folds"].keys()) != set(expected_folds):
            raise SystemExit(f"fold roster drift {key}")
        fragments[key] = z

    expected_keys = {(h, m) for h in expected_h for m in expected_models}
    if set(fragments) != expected_keys:
        missing = sorted(expected_keys - set(fragments))
        extra = sorted(set(fragments) - expected_keys)
        raise SystemExit(f"causal slice set mismatch missing={missing} extra={extra}")

    out = {}
    for h in expected_h:
        hz = {}
        for train_ix, test_ix, name in base.FOLDS:
            train_weeks = [common_weeks[i] for i in train_ix]
            test_weeks = [common_weeks[i] for i in test_ix]
            fold = {"train_weeks": train_weeks, "test_weeks": test_weeks, "depth": {}}
            for d in expected_depths:
                fold["depth"][d] = {}
                for model in expected_models:
                    src = fragments[(h, model)]["folds"][name]
                    if src["train_weeks"] != train_weeks or src["test_weeks"] != test_weeks:
                        raise SystemExit(f"paired week drift h={h} model={model} fold={name}")
                    if set(src["depth"]) != set(expected_depths):
                        raise SystemExit(f"depth roster drift h={h} model={model} fold={name}")
                    if set(src["depth"][d]) != {model}:
                        raise SystemExit(f"model payload drift h={h} model={model} fold={name} depth={d}")
                    fold["depth"][d][model] = src["depth"][d][model]
            hz[name] = fold
        out[str(h)] = hz

    result = {
        "status": "PHASE1_CAUSAL_EXECUTABLE_54W_PROVISIONAL_COMPLETE",
        "source_engine": "research/ng_exhaustion_chain_phase1_causal_20260817.py",
        "week_count": 54,
        "weeks": common_weeks,
        "temporarily_excluded_week": "20260329",
        "characteristics_accessed": False,
        "timing_accessed_only_for_causal_availability": True,
        "by_information_horizon_seconds": out,
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
        "recovery": {
            "reason": "original monolithic Agent 4 hit GitHub Actions 360-minute timeout",
            "semantics_changed": False,
            "model_settings_changed": False,
            "parallelization_axes": ["information_horizon_seconds", "model_family"],
            "slice_count": 21,
        },
    }
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "slice_count": 21}, indent=2))


if __name__ == "__main__":
    main()
