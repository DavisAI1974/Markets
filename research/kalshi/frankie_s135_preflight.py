#!/usr/bin/env python3
"""Fail-closed S135 preflight for every new CURRENT-FRANKIE group run.

Run this twice:
1. code-stack preflight before staging;
2. state preflight after the group's decision-state has been built/staged.

The second pass is the run gate. A run is not CURRENT FRANKIE unless every mandatory check is PASS.
Historical archive gaps are never hydrated: skipping strict state/tape health requires a separate,
non-empty durable proof file whose hash is recorded in this preflight output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import frankie_s135_current_runtime as s135
import frankie_s135_group_runner as group_runner

_DAY = re.compile(r"^20\d{6}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_archive_gap_proof(path: Path, gid: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"S135 PRECHECK FAIL: archive-gap proof missing/empty: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if gid.lower() not in text.lower():
        raise SystemExit(f"S135 PRECHECK FAIL: archive-gap proof does not identify group {gid}: {path}")
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        "rule": "documented missing families remain unavailable/null; hydration/synthesis forbidden",
    }


def check_state(
    path: Path,
    gid: str,
    expected_mask_after: str | None,
    strict_health: bool,
    *,
    archive_gap_proof: Path | None = None,
) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    build = state.get("_state_build") or {}
    if build.get("group") != gid:
        raise SystemExit(f"S135 PRECHECK FAIL: state group {build.get('group')!r} != {gid!r}")
    if build.get("mask_after") != expected_mask_after:
        raise SystemExit(
            f"S135 PRECHECK FAIL: state mask_after {build.get('mask_after')!r} != explicit expected {expected_mask_after!r}"
        )
    days = sorted(k for k in state if _DAY.fullmatch(str(k)))
    if not days:
        raise SystemExit("S135 PRECHECK FAIL: no decision-day blocks in state")
    for day in days:
        row = state[day]
        scored = row.get("scored_leg") if isinstance(row, dict) else None
        if not isinstance(scored, dict) or scored.get("group") != gid or not scored.get("leg"):
            raise SystemExit(f"S135 PRECHECK FAIL: {day} scored_leg/group context missing: {scored!r}")

    health = "NOT_RUN"
    reconcile = "NOT_RUN"
    gap_proof = None
    if strict_health:
        import state_health
        import tape_reconcile
        state_health.assert_healthy(state, gid)
        health = "PASS"
        tape_reconcile.assert_reconciled(gid, state)
        reconcile = "PASS"
        if archive_gap_proof is not None:
            raise SystemExit("S135 PRECHECK FAIL: --archive-gap-proof is only valid with --skip-strict-health")
    else:
        if archive_gap_proof is None:
            raise SystemExit(
                "S135 PRECHECK FAIL: --skip-strict-health requires --archive-gap-proof; "
                "historical gaps must be explicit and durable"
            )
        gap_proof = check_archive_gap_proof(archive_gap_proof, gid)
        health = "ARCHIVE_GAP_PROVEN"
        reconcile = "ARCHIVE_GAP_PROVEN"

    return {
        "state": str(path),
        "group": gid,
        "mask_after": expected_mask_after,
        "days": days,
        "state_health": health,
        "tape_reconcile": reconcile,
        "archive_gap_proof": gap_proof,
    }


def _mandatory_checks(
    stack: dict[str, Any],
    runner: dict[str, Any],
    spec: group_runner.GroupRunSpec | None,
    state_check: dict[str, Any] | None,
) -> dict[str, bool]:
    req = stack.get("requirements") or {}
    modules = stack.get("modules") or {}
    specialists = stack.get("specialists") or []
    current_brain_policy = str(req.get("current_brain_later_learned_evidence") or "")
    exact_mapping = bool(
        spec and spec.days and all(day.owner in set("ABCDE") and bool(day.leg) for day in spec.days)
    )
    archive_gap_ok = True
    if state_check is not None:
        archive_gap_ok = (
            state_check.get("state_health") == "PASS" and state_check.get("tape_reconcile") == "PASS"
        ) or bool(state_check.get("archive_gap_proof"))

    return {
        "01_canonical_s3_substrate_restored": req.get("full_s3_substrate_before_state") is True,
        "02_exact_group_scored_contract_mapping": exact_mapping,
        "03_current_frankie_full_brain": (
            int(stack.get("canonical_plays_total", -1)) > 0
            and stack.get("canonical_plays_total") == stack.get("full_plays_served")
        ),
        "04_later_learned_brain_evidence_preserved": "allowed" in current_brain_policy.lower(),
        "05_specialists_a_e_full_served_universe": (
            specialists == list("ABCDE")
            and "s126_specialist_parity" in modules
            and stack.get("canonical_plays_total") == stack.get("full_plays_served")
        ),
        "06_current_schema_runtime": str(stack.get("stack_version") or "").startswith("s135.current-frankie"),
        "07_s132_dynamic_event_curve": (
            "s132_event_driven_curve" in modules and req.get("fixed_curve_clock") is False
        ),
        "08_s133_reasoning_authority": "s133_reasoning_authority" in modules,
        "09_sequential_completed_prior_context_legal": (
            req.get("sequential_prior_completed_session") is True
            and runner.get("completed_prior_session_only_after_reveal") is True
            and runner.get("same_day_future_prior_context_blocked") is True
        ),
        "10_friday_e_to_a_weekend_bridge_to_monday_b": runner.get("friday_e_to_a_to_monday_b") is True,
        "11_specialist_handoffs_preserved_between_days": (
            runner.get("configured_owner_curve_preserved_verbatim") is True
            and runner.get("completed_prior_session_only_after_reveal") is True
        ),
        "12_real_archive_gaps_explicitly_unavailable": archive_gap_ok,
        "13_hydration_rejected": (
            req.get("hydration") == "REJECTED_NOT_USED"
            and runner.get("hydration") == "REJECTED_NOT_USED"
        ),
        "14_no_new_datapoint_family": (
            req.get("new_datapoint_family") is False and runner.get("new_datapoint_family") is False
        ),
        "15_no_averaging": (
            req.get("owner_averaging") is False and runner.get("coordinator_averaging") is False
        ),
        "16_no_fixed_curve_clock": (
            req.get("fixed_curve_clock") is False and runner.get("fixed_curve_clock") is False
        ),
        "17_abstain_not_flat": (
            req.get("abstain_flat_curve") is False and runner.get("abstain_flattening") is False
        ),
        "18_target_outcomes_blocked_blind": (
            "target-window outcome wall" in current_brain_policy.lower()
            and runner.get("target_data_provider_called_after_freeze") is True
        ),
        "19_actual_curves_allowed_refine": "REFINE" in group_runner.MODES,
        "20_freeze_before_reveal": (
            runner.get("freeze_before_reveal") is True and runner.get("sha256_freeze") is True
        ),
        "21_score_frozen_artifact_only": runner.get("score_frozen_artifact_only") is True,
    }


def build_preflight(
    *,
    group: str | None = None,
    state: Path | None = None,
    mask_after: str | None = None,
    strict_health: bool = True,
    archive_gap_proof: Path | None = None,
) -> dict[str, Any]:
    stack = s135.stack_manifest()
    runner = group_runner.runner_contract_manifest()
    spec = group_runner.GroupRunSpec.from_group(group, "BLIND") if group else None

    state_check = None
    if state is not None:
        if not group:
            raise SystemExit("--group is required with --state")
        state_check = check_state(
            state,
            str(group).lower(),
            mask_after,
            strict_health=strict_health,
            archive_gap_proof=archive_gap_proof,
        )
    elif archive_gap_proof is not None or not strict_health:
        raise SystemExit("--skip-strict-health/--archive-gap-proof require --state")

    checks = _mandatory_checks(stack, runner, spec, state_check)
    failed = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failed else "FAIL"
    run_gate = "PASS" if (status == "PASS" and group and state_check is not None) else "BLOCKED"
    if failed:
        run_gate = "BLOCKED"

    return {
        "status": status,
        "run_gate": run_gate,
        "current_frankie": stack,
        "sequential_runner": runner,
        "group_run_spec": spec.as_dict() if spec else None,
        "state_check": state_check,
        "mandatory_checks": checks,
        "failed_checks": failed,
        "run_gate_rule": (
            "No blind/refine group execution until run_gate=PASS. That requires explicit --group and --state; "
            "historical strict-health exceptions additionally require durable --archive-gap-proof."
        ),
        "standing_constraints": [
            "restore canonical S3 substrate before state build",
            "stage exact scored per-contract leg + prior tape/L1 for group",
            "current Frankie full brain including later learned evidence; target-window outcomes remain walled in blind",
            "all A-E packets use the complete already-served universe; no role starvation",
            "S132 event-driven curve: no fixed clock/point count; ABSTAIN still emits full curve/range",
            "S133 direction owner required; raw D-1 flow without price/shape cannot corroborate next-day sign",
            "sequential order is forecast -> validate -> SHA freeze -> reveal -> score frozen -> carry",
            "Friday E -> Specialist A weekend bridge -> Monday B; A never owns Monday forecast",
            "coordinator preserves configured owner output verbatim; never average/smooth specialists",
            "historical gaps remain unavailable/null; no hydration and no silent datapoint additions",
            "score immutable frozen artifacts only",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path)
    ap.add_argument("--group")
    ap.add_argument("--mask-after", default="AUTO", help="YYYYMMDD, NONE, or AUTO from group_config")
    ap.add_argument(
        "--skip-strict-health",
        action="store_true",
        help="Historical archive-gap runner only; requires --archive-gap-proof",
    )
    ap.add_argument("--archive-gap-proof", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    group = str(args.group).lower() if args.group else None
    resolved_mask = None
    if args.mask_after.upper() == "AUTO":
        if group:
            resolved_mask = group_runner.GroupRunSpec.from_group(group, "BLIND").mask_after
    elif args.mask_after.upper() == "NONE":
        resolved_mask = None
    else:
        resolved_mask = args.mask_after
        if not re.fullmatch(r"20\d{6}", resolved_mask):
            raise SystemExit(f"invalid --mask-after {args.mask_after!r}")

    result = build_preflight(
        group=group,
        state=args.state,
        mask_after=resolved_mask,
        strict_health=not args.skip_strict_health,
        archive_gap_proof=args.archive_gap_proof,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
