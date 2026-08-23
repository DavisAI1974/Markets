#!/usr/bin/env python3
"""Pure fail-closed gates shared by Step-1 launch/completion verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


class CompletionGateError(ValueError):
    pass


PROMOTION_METHOD = "USER_AUTHORIZED_ONE_DAY_CANARY_PROMOTION_V1_20260823"
PROMOTION_CANDIDATE = "0d318335825b4a0e19a5a2881522f3da0374788e"
FINALIZATION_RECOVERY_SCHEMA = "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZATION_RECOVERY_V1_20260823"
FINALIZER_LOCK_SCHEMA = "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZER_LOCK_V1_20260823"
FINALIZATION_RECOVERY_SCOPE = "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY"
EXPECTED_FULL_SEGMENTS = 65
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROMOTION_CANARY_IDENTITY = {
    "schema": "NG_EXHAUSTION_MBO_LEGACY_GROUP_AUDIT_V2_20260823",
    "artifact_id": 9490488236,
    "artifact_json_sha256": "a71b3ead28088eb1f19e919f978fca07b0e44ec6e8b91879bacb6e84e11148f0",
    "github_run_id": 32628933260,
    "date": "20250713",
    "implementation_commit": "6904bdda457f108e98508d43c9f6f53a5aaee1b8",
    "mbo_dbn_sha256": "8eb969be27fe31f2a13d3fe2b2231fee8d74f3e3c7f69a0facb9ea5a8b4eb542",
    "mbp10_gzip_sha256": "0ab2668241466143e2a05a52003d85f71ac813df8670b5de9ff4faaf93108317",
    "mbp10_row_count": 20361,
    "projected_legacy_row_count": 20360,
    "mbp10_only_detector_input_row_count": 1,
    "projection_only_detector_input_row_count": 0,
    "retained_interpretation": "ONE_MBP10_ONLY_DUPLICATE_AND_ZERO_PROJECTION_ONLY_DETECTOR_INPUT_ROWS",
}


def _require_false(body: Mapping[str, Any], *fields: str) -> None:
    for field in fields:
        if body.get(field) is not False:
            raise CompletionGateError(f"{field} must be explicitly false")


def validate_launch_canary(
    launch: Mapping[str, Any], lock: Mapping[str, Any]
) -> str:
    """Accept either the original strict preflight or the exact promoted canary."""
    preflight = launch.get("preflight")
    if isinstance(preflight, Mapping):
        if preflight.get("status") != "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE":
            raise CompletionGateError("launch strict preflight is incomplete")
        if preflight.get("source_manifest_sha256") != lock.get("source_manifest_sha256"):
            raise CompletionGateError("launch preflight source-manifest drift")
        if preflight.get("legacy_overlap_equivalence", {}).get("status") != "PASS":
            raise CompletionGateError("launch preflight equivalence did not pass")
        return "STRICT_PREFLIGHT"

    if launch.get("launch_method") != PROMOTION_METHOD:
        raise CompletionGateError("launch has neither strict preflight nor accepted promotion")
    if launch.get("candidate_commit") != PROMOTION_CANDIDATE:
        raise CompletionGateError("promoted canary candidate identity drift")
    canary = launch.get("canary_evidence")
    if not isinstance(canary, Mapping):
        raise CompletionGateError("promoted launch canary evidence is absent")
    if any(canary.get(field) != expected for field, expected in PROMOTION_CANARY_IDENTITY.items()):
        raise CompletionGateError("promoted canary identity drift")
    if canary.get("user_authorized_as_launch_canary") is not True:
        raise CompletionGateError("promoted canary lacks explicit user acceptance")
    if canary.get("lineage_equivalence_asserted") is not False:
        raise CompletionGateError("promoted canary overclaims lineage equivalence")
    if canary.get("multiweek_equivalence_asserted") is not False:
        raise CompletionGateError("promoted canary overclaims multiweek equivalence")
    _require_false(
        canary,
        "source_prefix_wide_enumeration_used",
        "release_or_virgin_holdout_consumed",
        "predictive_or_trading_experiment_run",
    )
    overlap = launch.get("legacy_overlap_equivalence")
    if not isinstance(overlap, Mapping):
        raise CompletionGateError("promoted launch retained-mismatch evidence is absent")
    if (
        overlap.get("status") != "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED"
        or overlap.get("retained_mismatch_count") != 1
        or overlap.get("lineage_equivalence_asserted") is not False
        or overlap.get("multiweek_equivalence_asserted") is not False
    ):
        raise CompletionGateError("promoted launch retained-mismatch evidence drift")
    return "USER_AUTHORIZED_ONE_DAY_CANARY"


def validate_runtime_state(
    *,
    final_available: bool,
    require_complete_outputs: bool,
    heartbeat_phase: str,
    active_state: str,
    load_state: str,
    sub_state: str,
    main_pid: int,
    pid_alive: bool,
) -> str:
    """Distinguish a live run from a completed collected transient unit."""
    if require_complete_outputs and not final_available:
        raise CompletionGateError("final dual-population receipt is required but unavailable")
    if final_available:
        if heartbeat_phase != "COMPLETE":
            raise CompletionGateError("final receipt exists without COMPLETE controller heartbeat")
        if active_state == "failed" or sub_state == "failed":
            raise CompletionGateError("completed outputs cannot excuse a failed systemd unit")
        live = (
            active_state == "active"
            and load_state == "loaded"
            and sub_state == "running"
            and int(main_pid) > 0
            and pid_alive is True
        )
        clean_stopped = (
            active_state in {"inactive", "unknown", ""}
            and load_state in {"loaded", "not-found", ""}
            and sub_state in {"dead", "not-found", ""}
            and int(main_pid) == 0
            and pid_alive is False
        )
        if not live and not clean_stopped:
            raise CompletionGateError("completed outputs have contradictory systemd/PID state")
        return "COMPLETED_OUTPUTS"
    if active_state != "active" or load_state != "loaded" or sub_state != "running":
        raise CompletionGateError("fresh systemd service is not active/loaded/running")
    if int(main_pid) <= 0 or pid_alive is not True:
        raise CompletionGateError("fresh systemd MainPID is not alive")
    return "ACTIVE_SERVICE"


def classify_recovery_state(
    *,
    final_available: bool,
    active_state: str,
    load_state: str,
    sub_state: str,
    main_pid: int,
    pid_alive: bool,
    completed_segments: int,
    expected_segments: int = EXPECTED_FULL_SEGMENTS,
) -> str:
    """Choose no-op, resume, or finalization without interrupting healthy work."""
    if type(completed_segments) is not int or type(expected_segments) is not int:
        raise CompletionGateError("recovery segment cardinality must be integer")
    if expected_segments != EXPECTED_FULL_SEGMENTS or not 0 <= completed_segments <= expected_segments:
        raise CompletionGateError("recovery segment cardinality drift")
    if final_available:
        return "FINAL_RECEIPT_PRESENT"
    if active_state == "failed" or sub_state == "failed":
        raise CompletionGateError("recovery refuses a failed unit without preserved diagnosis")
    live = (
        active_state == "active"
        and load_state == "loaded"
        and sub_state == "running"
        and int(main_pid) > 0
        and pid_alive is True
    )
    if live:
        return "HEALTHY_RUNNING"
    clean_stopped = (
        active_state in {"inactive", "unknown", ""}
        and load_state in {"loaded", "not-found", ""}
        and sub_state in {"dead", "not-found", ""}
        and int(main_pid) == 0
        and pid_alive is False
    )
    if not clean_stopped:
        raise CompletionGateError("recovery unit/PID state is contradictory")
    if completed_segments == expected_segments:
        return "FINALIZE_FROM_CHILDREN"
    return "RESUME_CONTROLLER"


def validate_finalization_provenance(
    final: Mapping[str, Any],
    launch: Mapping[str, Any],
    launch_lock: Mapping[str, Any],
    *,
    finalizer_lock: Mapping[str, Any],
    launch_receipt_file_sha256: str,
) -> str:
    """Accept either the original finalization or the exact no-replay recovery."""
    launch_mode = validate_launch_canary(launch, launch_lock)
    recovery = final.get("finalization_recovery")
    if recovery is None:
        if final.get("preflight_child_recovery") is not None:
            raise CompletionGateError("original finalization relies on preflight child recovery")
        if final.get("engine_hashes") != launch_lock.get("engine_hashes"):
            raise CompletionGateError("original finalization engine drift")
        if final.get("legacy_overlap_equivalence", {}).get("status") != "PASS":
            raise CompletionGateError("original finalization overlap gate did not pass")
        return "ORIGINAL_CANDIDATE_FINALIZATION"

    if launch_mode != "USER_AUTHORIZED_ONE_DAY_CANARY":
        raise CompletionGateError("recovery finalization requires the exact promoted canary")
    if not isinstance(recovery, Mapping):
        raise CompletionGateError("recovery finalization provenance is malformed")
    if final.get("preflight_child_recovery") is not None:
        raise CompletionGateError("recovery finalization cannot also use preflight recovery")
    if (
        recovery.get("schema") != FINALIZATION_RECOVERY_SCHEMA
        or not SHA256_RE.fullmatch(str(recovery.get("contract_sha256") or ""))
        or recovery.get("parent_candidate_commit") != PROMOTION_CANDIDATE
        or recovery.get("recovery_scope") != FINALIZATION_RECOVERY_SCOPE
        or recovery.get("raw_mbo_replayed") is not False
    ):
        raise CompletionGateError("recovery finalization identity drift")
    if (
        finalizer_lock.get("schema") != FINALIZER_LOCK_SCHEMA
        or finalizer_lock.get("parent_candidate_commit") != PROMOTION_CANDIDATE
        or finalizer_lock.get("recovery_scope") != FINALIZATION_RECOVERY_SCOPE
    ):
        raise CompletionGateError("finalizer lock identity drift")
    lock_hash = str(finalizer_lock.get("finalizer_lock_sha256") or "")
    lock_body = dict(finalizer_lock)
    lock_body.pop("finalizer_lock_sha256", None)
    calculated_lock_hash = hashlib.sha256(
        json.dumps(
            lock_body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
    if (
        not SHA256_RE.fullmatch(lock_hash)
        or calculated_lock_hash != lock_hash
        or recovery.get("finalizer_lock_sha256") != lock_hash
    ):
        raise CompletionGateError("finalizer lock hash drift")
    if (
        recovery.get("producer_engine_hashes") != launch_lock.get("engine_hashes")
        or recovery.get("finalizer_engine_hashes") != finalizer_lock.get("finalizer_engine_hashes")
        or final.get("engine_hashes") != finalizer_lock.get("finalizer_engine_hashes")
    ):
        raise CompletionGateError("recovery finalization engine drift")
    if (
        recovery.get("source_manifest_sha256") != final.get("source_manifest_sha256")
        or recovery.get("source_manifest_sha256") != launch_lock.get("source_manifest_sha256")
        or recovery.get("ruleset_sha256") != final.get("ruleset_sha256")
        or recovery.get("ruleset_sha256") != launch_lock.get("ruleset_sha256")
    ):
        raise CompletionGateError("recovery finalization source/ruleset drift")
    if (
        not SHA256_RE.fullmatch(launch_receipt_file_sha256)
        or recovery.get("accepted_launch_receipt_file_sha256") != launch_receipt_file_sha256
    ):
        raise CompletionGateError("recovery launch-receipt binding drift")
    children = recovery.get("children")
    if not isinstance(children, Mapping) or len(children) != EXPECTED_FULL_SEGMENTS:
        raise CompletionGateError("recovery child cardinality drift")
    pinned_receipts = []
    for segment in sorted(children):
        pin = children[segment]
        if not isinstance(pin, Mapping):
            raise CompletionGateError("recovery child pin malformed")
        receipt_hash = str(pin.get("receipt_sha256") or "")
        seconds_hash = str(pin.get("seconds_gzip_sha256") or "")
        rows = pin.get("seconds_rows")
        if (
            not SHA256_RE.fullmatch(receipt_hash)
            or not SHA256_RE.fullmatch(seconds_hash)
            or type(rows) is not int
            or rows < 0
        ):
            raise CompletionGateError("recovery child pin malformed")
        pinned_receipts.append(receipt_hash)
    if (
        final.get("child_receipt_count") != EXPECTED_FULL_SEGMENTS
        or final.get("child_receipt_hashes") != pinned_receipts
    ):
        raise CompletionGateError("recovery child receipt binding drift")
    overlap = final.get("legacy_overlap_equivalence", {})
    if (
        overlap.get("status") != "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED"
        or overlap.get("retained_mismatch_count") != 1
        or overlap.get("lineage_equivalence_asserted") is not False
        or overlap.get("multiweek_equivalence_asserted") is not False
        or overlap.get("accepted_launch_receipt_file_sha256") != launch_receipt_file_sha256
        or overlap.get("candidate_commit") != PROMOTION_CANDIDATE
        or overlap.get("canary_evidence") != launch.get("canary_evidence")
    ):
        raise CompletionGateError("recovery one-day overlap authorization drift")
    return "ONE_DAY_CANARY_RECOVERY_FINALIZER"


def validate_final_receipt_heartbeat(
    heartbeat: Mapping[str, Any], receipt_sha256: str
) -> None:
    if heartbeat.get("phase") != "COMPLETE":
        raise CompletionGateError("final receipt requires COMPLETE controller heartbeat")
    if (
        not SHA256_RE.fullmatch(receipt_sha256)
        or heartbeat.get("receipt_sha256") != receipt_sha256
    ):
        raise CompletionGateError("COMPLETE heartbeat/final receipt hash drift")


_FINAL_OUTPUTS = (
    ("event_outputs", "legacy", "LEGACY_CONTROL_EVENTS.jsonl.gz"),
    ("event_outputs", "native", "V4_NATIVE_FULL_EVENTS.jsonl.gz"),
    ("lineage_input_outputs", "legacy", "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz"),
    ("lineage_input_outputs", "native", "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz"),
    ("population_outputs", "legacy", "LEGACY_CONTROL_POPULATION.jsonl.gz"),
    ("population_outputs", "native", "V4_NATIVE_FULL_POPULATION.jsonl.gz"),
    ("crosswalk_index_outputs", "legacy", "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz"),
    ("crosswalk_index_outputs", "native", "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz"),
    (None, "crosswalk_output", "DUAL_CENSUS_CROSSWALK.jsonl.gz"),
    (None, "retained_overlap_mismatches", "LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz"),
)


def declared_final_output_hashes(final: Mapping[str, Any]) -> dict[str, str]:
    """Return the exact declared gzip output names and hashes, rejecting drift."""
    outputs: dict[str, str] = {}
    for group, key, expected_name in _FINAL_OUTPUTS:
        metadata = final.get(key) if group is None else final.get(group, {}).get(key)
        if not isinstance(metadata, Mapping):
            raise CompletionGateError(f"final output metadata absent: {expected_name}")
        name = Path(str(metadata.get("path") or "")).name
        if name != expected_name:
            raise CompletionGateError(f"final output path drift: {expected_name}")
        if name in outputs:
            raise CompletionGateError(f"duplicate final output path: {name}")
        digest = str(metadata.get("gzip_sha256") or "")
        if not SHA256_RE.fullmatch(digest):
            raise CompletionGateError(f"final output hash malformed: {name}")
        outputs[name] = digest
    return outputs
