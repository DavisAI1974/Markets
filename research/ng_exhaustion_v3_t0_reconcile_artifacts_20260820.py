#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

EXPECTED_REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE_T0"
EXPECTED_COUNTS = {"0": 135860, "1": 18837, "2": 1592, "3": 124, "4": 8, "5": 1}
EXPECTED_MODELS = {"logistic", "extra_trees", "knn"}
RESULT_NAME = "NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_RESULTS_20260820.json"
FINDINGS_NAME = "NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_FINDINGS_20260820.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_docs(agent_dir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    files = sorted(agent_dir.glob("*.json"))
    require(len(files) == 14, f"expected 14 pinned agent artifacts, got {len(files)}: {[p.name for p in files]}")
    docs = [json.loads(p.read_text()) for p in files]
    return files, docs


def validate_common(docs: list[dict[str, Any]]) -> None:
    for d in docs:
        require(d.get("implementation_revision") == EXPECTED_REVISION, f"wrong implementation revision: {d.get('implementation_revision')}")
        require(d.get("frozen_exact_depth_counts") == EXPECTED_COUNTS, f"frozen depth count mismatch: {d.get('frozen_exact_depth_counts')}")
        require(d.get("promotion_performed") is False, "promotion_performed must remain false")
        protected = d.get("protected_mutations")
        require(isinstance(protected, dict), "protected_mutations missing")
        require(not any(bool(v) for v in protected.values()), f"protected mutation detected: {protected}")


def partition(docs: list[dict[str, Any]]):
    d0 = {
        d["model"]: d
        for d in docs
        if d.get("status") == "NG_D0_FULL_CAUSAL_RECOVERY_V3_MODEL_AGENT_COMPLETE"
    }
    chain = {
        (int(d["stage"]), d["model"]): d
        for d in docs
        if d.get("status") == "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_V3_COMPLETE"
    }
    sparse = {
        int(d["stage"]): d
        for d in docs
        if d.get("status") == "NG_CHAIN_BIRTH_DEPTH_TYPE_SPARSE_CASE_STUDY_V3_COMPLETE"
    }
    require(set(d0) == EXPECTED_MODELS, f"D0 model set mismatch: {set(d0)}")
    require(
        set(chain) == {(stage, model) for stage in (1, 2, 3) for model in EXPECTED_MODELS},
        f"D1-D3 model-stage set mismatch: {set(chain)}",
    )
    require(set(sparse) == {4, 5}, f"sparse stage set mismatch: {set(sparse)}")
    for d in d0.values():
        require(d.get("cross_model_consensus_gate_used") is False, "D0 cross-model gate must remain false")
        require(d.get("exact_d0_preserved_n") == 135860, "exact D0 preservation mismatch")
        require(d.get("week_end_censored_d0_n") == 37, "D0 censored count mismatch")
    for (stage, _), d in chain.items():
        require(d.get("cross_model_consensus_gate_used") is False, f"D{stage} cross-model gate must remain false")
        require(d.get("timing_ladder") == ["PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5"], f"D{stage} timing ladder mismatch")
        require(set(d.get("results", {})) == {"CONTINUATION", "EVENTUAL_DEPTH", "CHAIN_TYPE_FAMILY"}, f"D{stage} result heads mismatch")
    for stage, d in sparse.items():
        require(d.get("low_support_case_study_only") is True, f"D{stage} must remain low-support case study only")
        require(d.get("timing_ladder") == ["PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5"], f"D{stage} timing ladder mismatch")
    return d0, chain, sparse


def reconcile(
    files: list[Path],
    docs: list[dict[str, Any]],
    out_dir: Path,
    launch_commit: str,
    source_run_id: str,
) -> dict[str, Any]:
    validate_common(docs)
    d0, chain, sparse = partition(docs)

    out_dir.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, out_dir / p.name)

    findings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    price: list[dict[str, Any]] = []

    for model, d in sorted(d0.items()):
        for target, rec in d["results"].items():
            row = {"stage": 0, "model": model, "target": target, "earliest": rec["earliest"]}
            findings.append(row)
            if rec["earliest"] is None:
                unresolved.append(row)
            for point in rec["tested"]:
                price.append(
                    {
                        "stage": 0,
                        "model": model,
                        "target": target,
                        "phase": point["phase"],
                        "seconds": point["root_age_seconds_after_confirmation"],
                        "incremental_price_value": point["incremental_price_value"],
                    }
                )

    for (stage, model), d in sorted(chain.items()):
        for target, rec in d["results"].items():
            row = {"stage": stage, "model": model, "target": target, "earliest": rec["earliest"]}
            findings.append(row)
            if rec["earliest"] is None:
                unresolved.append(row)
            for point in rec["tested"]:
                if point["phase"] == "PRIOR":
                    seconds = point["prior_age_seconds"]
                elif point["phase"] == "BIRTH_T0":
                    seconds = 0
                elif point["phase"] == "POST_BIRTH":
                    seconds = point["H_seconds_after_t0"]
                else:
                    raise SystemExit(f"unexpected V3 timing phase: {point['phase']}")
                price.append(
                    {
                        "stage": stage,
                        "model": model,
                        "target": target,
                        "phase": point["phase"],
                        "seconds": seconds,
                        "incremental_price_value": point["incremental_price_value"],
                    }
                )

    result = {
        "status": "NG_EXHAUSTION_V3_T0_PINNED_CORE_RECONCILED",
        "date": "2026-08-20",
        "launch_commit": launch_commit,
        "source_workflow_run_id": source_run_id,
        "implementation_revision": EXPECTED_REVISION,
        "timing_ladder": ["PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5"],
        "target_polarity_is_primary_question": False,
        "same_flip_role": "SECONDARY_ANNOTATION_CONTEXT_ONLY",
        "model_voting_used": False,
        "probability_aggregation_used": False,
        "agent_artifact_count": len(files),
        "agent_artifact_files": [p.name for p in files],
        "independent_model_findings": findings,
        "unresolved_first_band": unresolved,
        "price_increment_evidence": price,
        "D4_D5_case_studies": {"D4": sparse[4], "D5": sparse[5]},
        "V4_relation": "V3_FIXED_CHECKPOINT_BASELINE_ONLY; V4_CONTINUOUS_PER_INSTANCE_TIMING_IS_SEPARATE_AND_NOT_LAUNCHED_HERE",
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "recovery_scope": "RECONCILE_AND_PUBLISH_EXISTING_EXACT_COMMIT_PINNED_AGENT_ARTIFACTS_ONLY",
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

    (out_dir / RESULT_NAME).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    lines = [
        "# NG Exhaustion V3 T0 Pinned Core - 2026-08-20",
        "",
        "Status: **recovered from the exact-commit-pinned V3-T0 agent artifacts; independent models; no voting.**",
        "",
        f"Launch commit: `{launch_commit}`",
        f"Source workflow run id: `{source_run_id}`",
        "",
        "Timing ladder: PRIOR -> T0 -> H+1..H+5. V4 continuous timing is separate and was not launched or used here.",
        "",
        "## Independent findings",
        "",
    ]
    for row in findings:
        earliest = "unresolved" if row["earliest"] is None else json.dumps(row["earliest"], sort_keys=True)
        lines.append(f"- D{row['stage']} / {row['model']} / {row['target']}: {earliest}.")
    lines += [
        "",
        "## Preservation",
        "",
        "- All 14 pinned agent artifacts are copied into this durable output directory.",
        "- D4/D5 remain low-support case studies and are not promoted.",
        "- All censored, unresolved, losing, false, low-support, and model-disagreement evidence remains inside the preserved agent artifacts.",
        "- No protected artifact was mutated or promoted.",
        "- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains in force.",
        "",
    ]
    (out_dir / FINDINGS_NAME).write_text("\n".join(lines))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--launch-commit", required=True)
    ap.add_argument("--source-run-id", required=True)
    args = ap.parse_args()

    agent_dir = Path(args.agent_dir)
    out_dir = Path(args.out_dir)
    files, docs = load_docs(agent_dir)
    result = reconcile(files, docs, out_dir, args.launch_commit, args.source_run_id)
    print(
        json.dumps(
            {
                "status": result["status"],
                "launch_commit": result["launch_commit"],
                "source_workflow_run_id": result["source_workflow_run_id"],
                "agent_artifact_count": result["agent_artifact_count"],
                "independent_finding_count": len(result["independent_model_findings"]),
                "unresolved_first_band_count": len(result["unresolved_first_band"]),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
