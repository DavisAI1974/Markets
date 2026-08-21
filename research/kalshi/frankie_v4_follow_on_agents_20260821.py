#!/usr/bin/env python3
"""Isolated follow-on build-agent receipts for unfinished V4 preparation work.

No external model, no data purchase, no five-year archive mutation, no holdout,
no result-bearing V4 launch, no P0 real receipt execution, and no permanent
Frankie promotion. Each lane audits one newly built preparation surface and
emits a durable machine-readable receipt for reconciliation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MODES = {
    "pilot_chunk_streaming": {
        "files": [
            "research/kalshi/ng_exhaustion_v4_pilot_chunk_guard.py",
            "research/kalshi/tests/test_ng_exhaustion_v4_pilot_chunk_guard.py",
            "research/kalshi/NG_EXHAUSTION_V4_PREP_RULESET_20260821.json",
        ],
        "assertions": [
            "one D/year chunk is frozen",
            "exact candidate/workflow/ruleset/engine/adapter/reconciler/model/source identities are bound",
            "child->parent reconciliation is exact",
            "completed D/year chunk may advance without sibling barrier",
            "generic Proceed is not result-bearing authorization",
        ],
    },
    "end_to_end_adapter": {
        "files": [
            "research/kalshi/ng_exhaustion_v4_end_to_end_adapter.py",
            "research/kalshi/tests/test_ng_exhaustion_v4_end_to_end_adapter.py",
            "research/kalshi/ng_exhaustion_v4_state_assembler.py",
            "research/kalshi/ng_exhaustion_v4_causal_clock.py",
            "research/kalshi/ng_exhaustion_v4_lock_outcome.py",
        ],
        "assertions": [
            "event_known_by precedes all V4 evaluation",
            "source availability drives immutable state prefixes",
            "predecessor lifecycle remains prospective",
            "probability movie is append-only and lock/no-lock is independently recomputed",
            "execution handoff is sealed and reconciliation reruns the pipeline",
        ],
    },
    "detector_intensity_semantics": {
        "files": [
            "research/kalshi/ng_exhaustion_v4_detector_intensity.py",
            "research/kalshi/tests/test_ng_exhaustion_v4_detector_intensity.py",
        ],
        "assertions": [
            "native intensity requires a frozen causal stream with source/revision identities",
            "retrospective endpoint reconstruction cannot prove native intensity",
            "default preparation path uses visibly named v4_proxy polarity roll20 trajectory",
        ],
    },
    "exact_candidate_regression": {
        "files": [
            "research/kalshi/ng_exhaustion_v4_exact_candidate_freeze.py",
            "research/kalshi/tests/test_ng_exhaustion_v4_exact_candidate_freeze.py",
            "research/kalshi/NG_EXHAUSTION_V4_PREP_MODEL_FIXTURE_20260821.json",
            "research/kalshi/NG_EXHAUSTION_V4_PREP_SOURCE_FIXTURE_20260821.json",
        ],
        "assertions": [
            "freeze is exact-commit and hash bound",
            "full engineering checks are all required",
            "protected artifacts are hash checked",
            "engineering freeze grants no empirical authority",
        ],
    },
}


def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(mode: str) -> dict:
    if mode not in MODES:
        raise SystemExit(f"unknown mode: {mode}")
    spec = MODES[mode]
    missing = [p for p in spec["files"] if not Path(p).is_file()]
    if missing:
        raise SystemExit(f"missing required files for {mode}: {missing}")
    files = {p: sha256(p) for p in spec["files"]}
    return {
        "schema": "FRANKIE_V4_FOLLOW_ON_AGENT_V1",
        "status": "V4_FOLLOW_ON_AGENT_COMPLETE",
        "mode": mode,
        "build_assessment": "BUILD_IMPLEMENTED_AWAITING_RECONCILED_REGRESSION",
        "files": files,
        "assertions": list(spec["assertions"]),
        "external_model_calls": False,
        "data_purchase_performed": False,
        "five_year_run_touched": False,
        "release_holdout_consumed": False,
        "v4_result_bearing_launch": False,
        "p0_real_evidence_executed": False,
        "promotion_performed": False,
        "protected_mutations": {
            "frozen_detector": False,
            "frozen_canonical_evidence": False,
            "frozen_runway_clock": False,
            "permanent_frankie": False,
            "frankie_1": False,
            "spawn_py": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(MODES))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = run(args.mode)
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
