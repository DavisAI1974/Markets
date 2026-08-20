#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

EXPECTED_DEPTH = {"0": 135860, "1": 18837, "2": 1592, "3": 124, "4": 8, "5": 1}
MODELS = {"logistic", "extra_trees", "knn"}
REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE_T0"
TIMING = ["PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5"]


def load_docs(src: Path):
    files = sorted(src.glob("*.json"))
    docs = [json.loads(p.read_text()) for p in files]
    if len(docs) != 14:
        raise SystemExit(f"expected 14 agent artifacts, got {len(docs)}")
    for d in docs:
        if d.get("frozen_exact_depth_counts") != EXPECTED_DEPTH:
            raise SystemExit("frozen depth-count invariant failed")
        if d.get("implementation_revision") != REVISION:
            raise SystemExit("implementation revision invariant failed")
        if d.get("promotion_performed") is not False:
            raise SystemExit("promotion invariant failed")
        if any(d.get("protected_mutations", {}).values()):
            raise SystemExit("protected mutation invariant failed")
    return files, docs


def reconcile(src: Path, out: Path, launch_commit: str, source_run_id: str):
    files, docs = load_docs(src)
    out.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, out / p.name)

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

    if set(d0) != MODELS:
        raise SystemExit(f"D0 model set mismatch: {sorted(d0)}")
    if set(chain) != {(s, m) for s in (1, 2, 3) for m in MODELS}:
        raise SystemExit("D1-D3 model/stage set mismatch")
    if set(sparse) != {4, 5}:
        raise SystemExit(f"sparse stage set mismatch: {sorted(sparse)}")

    findings = []
    unresolved = []
    price = []

    for model, d in sorted(d0.items()):
        for target, rec in d["results"].items():
            row = {"stage": 0, "model": model, "target": target, "earliest": rec["earliest"]}
            findings.append(row)
            if rec["earliest"] is None:
                unresolved.append(row)
            for p in rec["tested"]:
                price.append(
                    {
                        "stage": 0,
                        "model": model,
                        "target": target,
                        "phase": p["phase"],
                        "seconds": p["root_age_seconds_after_confirmation"],
                        "incremental_price_value": p["incremental_price_value"],
                    }
                )

    for (stage, model), d in sorted(chain.items()):
        for target, rec in d["results"].items():
            row = {"stage": stage, "model": model, "target": target, "earliest": rec["earliest"]}
            findings.append(row)
            if rec["earliest"] is None:
                unresolved.append(row)
            for p in rec["tested"]:
                if p["phase"] == "PRIOR":
                    sec = p["prior_age_seconds"]
                elif p["phase"] == "BIRTH_T0":
                    sec = 0
                elif p["phase"] == "POST_BIRTH":
                    sec = p["H_seconds_after_t0"]
                else:
                    raise SystemExit(f"unexpected phase {p['phase']!r}")
                price.append(
                    {
                        "stage": stage,
                        "model": model,
                        "target": target,
                        "phase": p["phase"],
                        "seconds": sec,
                        "incremental_price_value": p["incremental_price_value"],
                    }
                )

    result = {
        "status": "NG_EXHAUSTION_V3_T0_PINNED_CORE_RECONCILED",
        "date": "2026-08-20",
        "launch_commit": launch_commit,
        "source_workflow_run_id": source_run_id,
        "recovery_path": "RECONCILE_ONLY_FROM_PINNED_AGENT_ARTIFACTS",
        "implementation_revision": REVISION,
        "timing_ladder": TIMING,
        "target_polarity_is_primary_question": False,
        "same_flip_role": "SECONDARY_ANNOTATION_CONTEXT_ONLY",
        "model_voting_used": False,
        "independent_model_findings": findings,
        "unresolved_first_band": unresolved,
        "price_increment_evidence": price,
        "D4_D5_case_studies": {"D4": sparse[4], "D5": sparse[5]},
        "V4_relation": "V3_FIXED_CHECKPOINT_BASELINE_ONLY; V4_NOT_LAUNCHED_OR_MODIFIED",
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

    results_path = out / "NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_RESULTS_20260820.json"
    findings_path = out / "NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_FINDINGS_20260820.md"
    results_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    lines = [
        "# NG Exhaustion V3 T0 Pinned Core — 2026-08-20",
        "",
        "Status: **pinned fixed-checkpoint V3 baseline; independent models; no voting.**",
        "",
        f"Launch commit: `{launch_commit}`",
        f"Recovered from source workflow run: `{source_run_id}`",
        "",
        "Timing ladder: PRIOR -> T0 -> H+1..H+5. V4 was not launched or modified by this recovery.",
        "",
        "## Independent findings",
        "",
    ]
    for row in findings:
        earliest = (
            json.dumps(row["earliest"], sort_keys=True)
            if row["earliest"] is not None
            else "unresolved"
        )
        lines.append(f"- D{row['stage']} / {row['model']} / {row['target']}: {earliest}.")
    lines += [
        "",
        "## Preservation",
        "- D4/D5 remain case studies.",
        "- No protected artifact was mutated or promoted.",
        "- All unresolved/model-specific outcomes remain preserved.",
        "- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains in force.",
        "",
    ]
    findings_path.write_text("\n".join(lines))

    check = json.loads(results_path.read_text())
    assert check["implementation_revision"] == REVISION
    assert check["timing_ladder"] == TIMING
    assert check["model_voting_used"] is False
    assert check["promotion_performed"] is False
    assert not any(check["protected_mutations"].values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--launch-commit", required=True)
    ap.add_argument("--source-run-id", required=True)
    args = ap.parse_args()
    reconcile(
        Path(args.artifact_dir),
        Path(args.out_dir),
        args.launch_commit,
        args.source_run_id,
    )


if __name__ == "__main__":
    main()
