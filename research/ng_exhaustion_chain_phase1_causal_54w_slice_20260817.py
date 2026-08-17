#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ng_exhaustion_chain_phase1_causal_54w_20260817 as base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event_table")
    ap.add_argument("--horizon", type=int, required=True, choices=base.HORIZONS)
    ap.add_argument("--model", required=True, choices=base.MODELS)
    ap.add_argument(
        "--base-freeze",
        default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json",
    )
    ap.add_argument("--out")
    a = ap.parse_args()

    freeze = json.load(open(a.base_freeze))
    byweek = base.pilot.load_rows(a.event_table)
    if sorted(byweek) != freeze["base_weeks"] or len(byweek) != 54:
        raise SystemExit("54-week base drift")

    weeks = sorted(byweek)
    h = int(a.horizon)
    model = a.model
    folds = {}
    for train_ix, test_ix, name in base.FOLDS:
        tr = [weeks[i] for i in train_ix]
        te = [weeks[i] for i in test_ix]
        fold = {"train_weeks": tr, "test_weeks": te, "depth": {}}
        for d in base.DEPTHS:
            z = base.paired(model, tr, te, byweek, h, d)
            fold["depth"][str(d)] = {model: ({"n": 0, "gain_mean": None} if z is None else z)}
        folds[name] = fold

    result = {
        "status": "PHASE1_CAUSAL_EXECUTABLE_54W_SLICE_COMPLETE",
        "source_engine": "research/ng_exhaustion_chain_phase1_causal_20260817.py",
        "adapter_engine": "research/ng_exhaustion_chain_phase1_causal_54w_20260817.py",
        "horizon_seconds": h,
        "model": model,
        "week_count": 54,
        "weeks": weeks,
        "temporarily_excluded_week": "20260329",
        "characteristics_accessed": False,
        "timing_accessed_only_for_causal_availability": True,
        "folds": folds,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    out = a.out or f"NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_54W_H{h}_{model.upper()}_20260817.json"
    Path(out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "horizon_seconds": h, "model": model}, indent=2))


if __name__ == "__main__":
    main()
