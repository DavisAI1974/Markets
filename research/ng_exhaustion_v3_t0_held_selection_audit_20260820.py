#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TIMING = ["PRIOR", "T0", "H+1", "H+2", "H+3", "H+4", "H+5"]
MIN_COUNTS = {
    1: {"validation_pos": 200, "validation_neg": 1000, "confirmation_pos": 100, "confirmation_neg": 500},
    2: {"validation_pos": 30, "validation_neg": 300, "confirmation_pos": 15, "confirmation_neg": 200},
    3: {"validation_pos": 10, "validation_neg": 50, "confirmation_pos": 5, "confirmation_neg": 50},
}
GENERIC_FLOORS = {
    1: {"validation": 200, "confirmation": 100},
    2: {"validation": 30, "confirmation": 15},
    3: {"validation": 10, "confirmation": 5},
}
JSON_NAME = "NG_EXHAUSTION_V3_T0_HELD_SELECTION_AUDIT_20260820.json"
MD_NAME = "NG_EXHAUSTION_V3_T0_HELD_SELECTION_AUDIT_20260820.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def support_ok(engine_target: str, stage: int, block: str, q: dict[str, Any]) -> bool:
    if int(q.get("n", 0) or 0) <= 0 or len(q.get("class_counts", {})) < 2:
        return False
    if engine_target == "CONTINUATION":
        req = MIN_COUNTS[stage]
        cc = q["class_counts"]
        return (
            int(cc.get("1", 0)) >= req[f"{block}_pos"]
            and int(cc.get("0", 0)) >= req[f"{block}_neg"]
        )
    return int(q.get("n", 0)) >= GENERIC_FLOORS[stage][block]


def validation_confirmation_pass(full: dict[str, Any], stage: int) -> bool:
    engine_target = str(full.get("target"))
    blocks = full.get("blocks", {})
    for block in ("validation", "confirmation"):
        q = blocks.get(block, {})
        if not support_ok(engine_target, stage, block, q):
            return False
        if not (
            float(q.get("log_loss_gain_vs_null", -1)) > 0
            and float(q.get("brier_gain_vs_null", -1)) > 0
        ):
            return False
        week_fraction = q.get("positive_week_fraction_brier")
        if week_fraction is not None and float(week_fraction) < 0.5:
            return False
        if engine_target == "CONTINUATION":
            auc = q.get("roc_auc")
            if auc is None or float(auc) <= 0.5:
                return False
    return True


def timing_key(stage: int, point: dict[str, Any]) -> dict[str, Any]:
    if stage == 0:
        return {
            "phase": point["phase"],
            "root_age_seconds_after_confirmation": int(point["root_age_seconds_after_confirmation"]),
        }
    phase = point["phase"]
    if phase == "PRIOR":
        return {"phase": phase, "prior_age_seconds": int(point["prior_age_seconds"])}
    if phase == "BIRTH_T0":
        return {"phase": phase, "T0_seconds_after_birth": 0}
    if phase == "POST_BIRTH":
        return {"phase": phase, "H_seconds_after_t0": int(point["H_seconds_after_t0"])}
    raise SystemExit(f"unexpected timing phase {phase!r}")


def raw_earliest_key(stage: int, earliest: dict[str, Any] | None) -> dict[str, Any] | None:
    if earliest is None:
        return None
    if stage == 0:
        return {
            "phase": "ROOT_CAUSAL_BEFORE_NEXT_EVENT",
            "root_age_seconds_after_confirmation": int(earliest["root_age_seconds_after_confirmation"]),
        }
    timing_class = earliest.get("timing_class")
    if timing_class == "PRIOR_BEFORE_BIRTH":
        return {"phase": "PRIOR", "prior_age_seconds": int(earliest["prior_age_seconds"])}
    if timing_class == "BIRTH_T0":
        return {"phase": "BIRTH_T0", "T0_seconds_after_birth": 0}
    if timing_class == "POST_BIRTH_EARLY_RECOGNITION":
        return {"phase": "POST_BIRTH", "H_seconds_after_t0": int(earliest["H_seconds_after_t0"])}
    return {"timing_class": timing_class}


def held_veto(full: dict[str, Any]) -> bool:
    held = full.get("blocks", {}).get("held", {})
    return int(held.get("n", 0) or 0) >= 20 and float(held.get("brier_gain_vs_null", 0) or 0) < 0


def audit_record(stage: int, model: str, target: str, rec: dict[str, Any]) -> dict[str, Any]:
    selected = None
    selected_full = None
    pass_points = []
    for point in rec.get("tested", []):
        full = point.get("views", {}).get("FULL_CAUSAL", {})
        passed = validation_confirmation_pass(full, 1 if stage == 0 else stage)
        if passed:
            item = {
                "timing": timing_key(stage, point),
                "agent_independently_validated": bool(full.get("independently_validated")),
                "held_veto_under_agent_gate": held_veto(full),
            }
            pass_points.append(item)
            if selected is None:
                selected = item["timing"]
                selected_full = full

    raw = rec.get("earliest")
    raw_key = raw_earliest_key(stage, raw)
    changed = raw_key != selected
    return {
        "stage": stage,
        "model": model,
        "target": target,
        "agent_reported_earliest": raw,
        "agent_reported_earliest_key": raw_key,
        "validation_confirmation_only_earliest": selected,
        "selection_changed_if_held_is_evaluation_only": changed,
        "validation_confirmation_pass_points": pass_points,
        "selected_validation_block": None if selected_full is None else selected_full.get("blocks", {}).get("validation"),
        "selected_confirmation_block": None if selected_full is None else selected_full.get("blocks", {}).get("confirmation"),
        "selected_held_evaluation_block": None if selected_full is None else selected_full.get("blocks", {}).get("held"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--launch-commit", required=True)
    ap.add_argument("--source-run-id", required=True)
    args = ap.parse_args()

    src = Path(args.artifact_dir)
    out = Path(args.out_dir)
    files = sorted(src.glob("*.json"))
    require(len(files) == 14, f"expected 14 pinned V3 artifacts, got {len(files)}")
    docs = [json.loads(path.read_text()) for path in files]

    rows = []
    for d in docs:
        status = d.get("status")
        if status == "NG_D0_FULL_CAUSAL_RECOVERY_V3_MODEL_AGENT_COMPLETE":
            for target, rec in d.get("results", {}).items():
                rows.append(audit_record(0, str(d["model"]), str(target), rec))
        elif status == "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_V3_COMPLETE":
            stage = int(d["stage"])
            for target, rec in d.get("results", {}).items():
                rows.append(audit_record(stage, str(d["model"]), str(target), rec))

    rows.sort(key=lambda row: (row["stage"], row["model"], row["target"]))
    changed = [row for row in rows if row["selection_changed_if_held_is_evaluation_only"]]
    raw_unresolved = [row for row in rows if row["agent_reported_earliest"] is None]
    vc_unresolved = [row for row in rows if row["validation_confirmation_only_earliest"] is None]

    payload = {
        "status": "NG_EXHAUSTION_V3_T0_HELD_SELECTION_AUDIT_COMPLETE_NO_AGENT_MUTATION",
        "date": "2026-08-20",
        "launch_commit": args.launch_commit,
        "source_workflow_run_id": args.source_run_id,
        "scope": "AUDIT_ONLY; RAW_PINNED_AGENT_ARTIFACTS_AND_AGENT_REPORTED_EARLIEST_VALUES_ARE_UNCHANGED",
        "issue_under_test": "AGENT_INDEPENDENT_PASS_USES_HELD_BRIER_AS_A_VETO_WHILE_SCANNING_FOR_EARLIEST_CHECKPOINT",
        "counterfactual_selection_rule": "SELECT_ON_VALIDATION_PLUS_CONFIRMATION_ONLY; REPORT_HELD_SEPARATELY; DO_NOT_USE_HELD_TO_MOVE_OR_VETO_TIMING",
        "authoritative_interpretation_promoted": False,
        "timing_ladder": TIMING,
        "audited_model_target_rows": len(rows),
        "agent_reported_unresolved_n": len(raw_unresolved),
        "validation_confirmation_only_unresolved_n": len(vc_unresolved),
        "selection_changed_n": len(changed),
        "selection_changed_rows": changed,
        "all_rows": rows,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
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
            "pinned_agent_artifacts": False
        }
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / JSON_NAME).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    lines = [
        "# NG Exhaustion V3 T0 Held-Selection Audit - 2026-08-20",
        "",
        "Status: **audit only; pinned agent artifacts and their reported earliest values are unchanged.**",
        "",
        f"Launch commit: `{args.launch_commit}`",
        f"Source workflow run: `{args.source_run_id}`",
        "",
        "The pinned V3 model gate uses validation + confirmation and then lets held Brier performance veto a checkpoint while the runner searches for the earliest timing. This audit measures the effect of removing only that held veto. It does not promote the counterfactual interpretation automatically.",
        "",
        f"- Audited model/target rows: {len(rows)}",
        f"- Agent-reported unresolved rows: {len(raw_unresolved)}",
        f"- Validation+confirmation-only unresolved rows: {len(vc_unresolved)}",
        f"- Timing selections changed by the held veto: {len(changed)}",
        "",
        "## Changed selections",
        "",
    ]
    if not changed:
        lines.append("- None. The held veto did not change any first-band earliest selection in this run.")
    else:
        for row in changed:
            lines.append(
                f"- D{row['stage']} / {row['model']} / {row['target']}: agent={json.dumps(row['agent_reported_earliest_key'], sort_keys=True)}; validation+confirmation={json.dumps(row['validation_confirmation_only_earliest'], sort_keys=True)}."
            )
    lines += [
        "",
        "## Preservation",
        "",
        "- No pinned agent output is rewritten.",
        "- Held metrics remain preserved and visible as evaluation evidence.",
        "- No model voting, probability aggregation, promotion, or protected mutation is introduced.",
        "- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains in force.",
        "",
    ]
    (out / MD_NAME).write_text("\n".join(lines))
    print(json.dumps({
        "status": payload["status"],
        "audited_model_target_rows": len(rows),
        "selection_changed_n": len(changed),
        "agent_reported_unresolved_n": len(raw_unresolved),
        "validation_confirmation_only_unresolved_n": len(vc_unresolved),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
