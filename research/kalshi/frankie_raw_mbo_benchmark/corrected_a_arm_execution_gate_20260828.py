#!/usr/bin/env python3
"""Fail-closed execution and lock gates for corrected native-MBO A-arm runs."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


SURFACE_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_RT_SURFACE_INVENTORY_V1"
EXECUTION_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_EXECUTION_V1"
FIRST_LOCK_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_RT_FIRST_LOCK_V1"
FREEZE_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_RT_FREEZE_V1"
ALLOWED_ARMS = frozenset({"A_CLEAN", "A_MEMORY"})
ALLOWED_ROLES = frozenset({"REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"})
SURFACE_IDS = frozenset(
    {
        "candidate_contradiction_memory",
        "causal_history_all_scales",
        "current_brain_and_learned_knowledge",
        "current_causal_operating_state",
        "day_specific_forecast_context",
        "forecast_scenarios_and_disconfirmers",
        "frozen_rt_state",
        "full_bigsuite",
        "full_raw_mbo_events",
        "full_source_catalog_and_availability",
        "fundamentals_and_storage",
        "historical_analogs_and_calibration",
        "market_mechanics_state",
        "power_stack_and_generation",
        "provisional_capabilities",
        "rt_on_demand_evidence_scout",
        "selected_exemplars_falsifiers_negatives",
        "source_integrity_and_clocks",
        "step1_revealed_retrospective_evidence",
        "step1_structural_census_methodology",
        "structure_lifecycle",
        "synchronized_curve_and_roll",
        "top20_book_and_fifo",
        "weather_forward_forcing",
    }
)
MANDATORY_NATIVE_RT_SURFACES = frozenset(
    {
        "current_causal_operating_state",
        "full_raw_mbo_events",
        "full_source_catalog_and_availability",
        "market_mechanics_state",
        "source_integrity_and_clocks",
        "structure_lifecycle",
        "top20_book_and_fifo",
    }
)
SURFACE_KEYS = frozenset(
    {
        "surface_id",
        "route",
        "availability",
        "required_for_principal",
        "model_visible",
        "evidence_receipt_sha256",
    }
)
EXECUTION_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "arm",
        "role",
        "provider",
        "requested_model",
        "served_model",
        "principal_invocation_id",
        "actual_principal_invocation",
        "controller_only",
        "profile_id",
        "mission_sha256",
        "calculation_contract_sha256",
        "knowledge_manifest_hash",
        "context_bundle_sha256",
        "model_visible_context_sha256",
        "serialized_principal_input_sha256",
        "knowledge_use_receipt_sha256",
        "surface_inventory_hash",
        "calculation_receipt_sha256",
        "pre_call_checkpoint_hash",
        "post_call_checkpoint_hash",
        "usage",
        "response",
        "execution_receipt_hash",
    }
)
USAGE_KEYS = frozenset(
    {"input_tokens", "output_tokens", "total_tokens", "provider_usage_receipt_sha256"}
)
RESPONSE_KEYS = frozenset(
    {"response_id", "response_sha256", "output_sha256", "analysis_author"}
)


class CorrectedExecutionGateError(ValueError):
    """Corrected A-arm evidence cannot advance through the execution gate."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Mapping[str, Any], *, omit: str | None = None) -> str:
    body = dict(value)
    if omit is not None:
        body.pop(omit, None)
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _require_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CorrectedExecutionGateError(f"{label} must be a lowercase SHA-256")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CorrectedExecutionGateError(f"{label} must be a non-empty string")
    return value


def _require_exact_keys(value: Any, keys: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise CorrectedExecutionGateError(f"{label} fields are incomplete or unknown")
    return value


def validate_rt_surface_inventory(
    inventory: Mapping[str, Any], *, arm: str
) -> dict[str, Any]:
    """Require all 24 identities and the complete lawful native RT surface."""
    if arm not in ALLOWED_ARMS:
        raise CorrectedExecutionGateError("invalid A-arm identity")
    if not isinstance(inventory, Mapping) or inventory.get("schema") != SURFACE_SCHEMA:
        raise CorrectedExecutionGateError("unsupported RT surface inventory schema")
    if inventory.get("arm") != arm or inventory.get("role") != "REAL_TIME_FRANKIE":
        raise CorrectedExecutionGateError("RT surface inventory arm/role mismatch")
    if inventory.get("inventory_hash") != canonical_hash(inventory, omit="inventory_hash"):
        raise CorrectedExecutionGateError("RT surface inventory hash mismatch")

    rows = inventory.get("surfaces")
    if not isinstance(rows, list) or len(rows) != 24:
        raise CorrectedExecutionGateError("RT inventory must contain 24 exact surface identities")
    by_id: dict[str, Mapping[str, Any]] = {}
    for raw in rows:
        row = _require_exact_keys(raw, SURFACE_KEYS, "surface")
        surface_id = row["surface_id"]
        if not isinstance(surface_id, str) or surface_id in by_id:
            raise CorrectedExecutionGateError("surface identities must be unique strings")
        by_id[surface_id] = row
    if set(by_id) != SURFACE_IDS:
        raise CorrectedExecutionGateError("RT inventory must contain 24 exact surface identities")

    step1 = by_id["step1_revealed_retrospective_evidence"]
    if (
        step1["route"] != "SEALED"
        or step1["availability"] != "SEALED"
        or step1["required_for_principal"] is not False
        or step1["model_visible"] is not False
        or step1["evidence_receipt_sha256"] is not None
    ):
        raise CorrectedExecutionGateError("Step-1/reveal surface is not fully sealed")

    frozen = by_id["frozen_rt_state"]
    if (
        frozen["route"] != "PENDING"
        or frozen["availability"] != "PENDING"
        or frozen["required_for_principal"] is not False
        or frozen["model_visible"] is not False
        or frozen["evidence_receipt_sha256"] is not None
    ):
        raise CorrectedExecutionGateError("frozen RT state must be pending before RT")

    required_ids: list[str] = []
    for surface_id, row in by_id.items():
        required = row["required_for_principal"]
        visible = row["model_visible"]
        if not isinstance(required, bool) or not isinstance(visible, bool):
            raise CorrectedExecutionGateError("surface boolean policy is malformed")
        if surface_id in MANDATORY_NATIVE_RT_SURFACES and required is not True:
            raise CorrectedExecutionGateError(f"required surface is not mandatory: {surface_id}")
        if required:
            if row["route"] not in {"DIRECT", "TOOL_ACCESSIBLE"}:
                raise CorrectedExecutionGateError(f"required surface has invalid route: {surface_id}")
            if row["availability"] != "AVAILABLE" or visible is not True:
                raise CorrectedExecutionGateError(f"required surface is unavailable: {surface_id}")
            _require_sha(row["evidence_receipt_sha256"], f"{surface_id}.evidence_receipt")
            required_ids.append(surface_id)
        elif row["evidence_receipt_sha256"] is not None:
            _require_sha(row["evidence_receipt_sha256"], f"{surface_id}.evidence_receipt")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_RT_SURFACE_GATE_V1",
        "arm": arm,
        "surface_inventory_hash": inventory["inventory_hash"],
        "surface_count": len(rows),
        "required_surface_ids": sorted(required_ids),
        "step1_sealed": True,
        "frozen_rt_state_pending": True,
        "native_full_mbo_available": True,
        "full_fifo_available": True,
    }


def validate_principal_execution(
    execution: Mapping[str, Any],
    *,
    expected_arm: str,
    expected_role: str,
    expected_mission_sha256: str,
    expected_calculation_contract_sha256: str,
    expected_surface_inventory_hash: str,
) -> dict[str, Any]:
    """Reject controller work or an incompletely identified model response."""
    _require_exact_keys(execution, EXECUTION_KEYS, "principal execution")
    if execution.get("schema") != EXECUTION_SCHEMA:
        raise CorrectedExecutionGateError("unsupported principal execution schema")
    if expected_arm not in ALLOWED_ARMS or execution.get("arm") != expected_arm:
        raise CorrectedExecutionGateError("principal execution arm mismatch")
    if expected_role not in ALLOWED_ROLES or execution.get("role") != expected_role:
        raise CorrectedExecutionGateError("principal execution role mismatch")
    if execution.get("execution_receipt_hash") != canonical_hash(
        execution, omit="execution_receipt_hash"
    ):
        raise CorrectedExecutionGateError("principal execution receipt hash mismatch")
    if execution.get("actual_principal_invocation") is not True or execution.get(
        "controller_only"
    ) is not False:
        raise CorrectedExecutionGateError("actual principal invocation is not proven")

    for field in (
        "run_id",
        "provider",
        "requested_model",
        "served_model",
        "principal_invocation_id",
        "profile_id",
    ):
        _require_text(execution.get(field), field)
    expected_profile = {
        ("A_CLEAN", "REAL_TIME_FRANKIE"): "RT_A_CLEAN_SECOND_PASS",
        ("A_MEMORY", "REAL_TIME_FRANKIE"): "RT_A_MEMORY_SECOND_PASS",
        ("A_CLEAN", "FORECASTER_FRANKIE"): "FORECASTER_A_CLEAN_REVIEW",
        ("A_MEMORY", "FORECASTER_FRANKIE"): "FORECASTER_A_MEMORY_REVIEW",
    }[(expected_arm, expected_role)]
    if execution["profile_id"] != expected_profile:
        raise CorrectedExecutionGateError("principal execution profile mismatch")

    for field in (
        "mission_sha256",
        "calculation_contract_sha256",
        "knowledge_manifest_hash",
        "context_bundle_sha256",
        "model_visible_context_sha256",
        "serialized_principal_input_sha256",
        "knowledge_use_receipt_sha256",
        "surface_inventory_hash",
        "calculation_receipt_sha256",
        "pre_call_checkpoint_hash",
        "post_call_checkpoint_hash",
    ):
        _require_sha(execution.get(field), field)
    if execution["mission_sha256"] != _require_sha(
        expected_mission_sha256, "expected mission"
    ):
        raise CorrectedExecutionGateError("mission identity drift")
    if execution["calculation_contract_sha256"] != _require_sha(
        expected_calculation_contract_sha256, "expected calculation contract"
    ):
        raise CorrectedExecutionGateError("calculation-contract identity drift")
    if execution["surface_inventory_hash"] != _require_sha(
        expected_surface_inventory_hash, "expected surface inventory"
    ):
        raise CorrectedExecutionGateError("surface-inventory identity drift")
    if execution["pre_call_checkpoint_hash"] == execution["post_call_checkpoint_hash"]:
        raise CorrectedExecutionGateError("pre/post principal checkpoints are not distinct")

    usage = _require_exact_keys(execution.get("usage"), USAGE_KEYS, "usage")
    counts = []
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise CorrectedExecutionGateError("positive provider token usage is required")
        counts.append(value)
    if counts[0] + counts[1] != counts[2]:
        raise CorrectedExecutionGateError("provider token usage does not reconcile")
    _require_sha(usage.get("provider_usage_receipt_sha256"), "provider usage receipt")

    response = _require_exact_keys(execution.get("response"), RESPONSE_KEYS, "response")
    _require_text(response.get("response_id"), "response_id")
    _require_sha(response.get("response_sha256"), "response_sha256")
    output_sha = _require_sha(response.get("output_sha256"), "output_sha256")
    if response.get("analysis_author") != expected_role:
        raise CorrectedExecutionGateError("principal analysis author does not match role")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_EXECUTION_GATE_V1",
        "run_id": execution["run_id"],
        "arm": expected_arm,
        "role": expected_role,
        "execution_receipt_hash": execution["execution_receipt_hash"],
        "provider": execution["provider"],
        "requested_model": execution["requested_model"],
        "served_model": execution["served_model"],
        "principal_invocation_id": execution["principal_invocation_id"],
        "response_id": response["response_id"],
        "response_output_sha256": output_sha,
        "controller_only": False,
        "actual_principal_invocation": True,
    }


def validate_first_lock_and_freeze(
    execution: Mapping[str, Any],
    first_lock: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove that lock/freeze bind the actual principal output, never a controller summary."""
    if execution.get("schema") != EXECUTION_SCHEMA:
        raise CorrectedExecutionGateError("invalid execution object at lock gate")
    if execution.get("execution_receipt_hash") != canonical_hash(
        execution, omit="execution_receipt_hash"
    ):
        raise CorrectedExecutionGateError("execution hash drift at lock gate")
    response = execution.get("response")
    if not isinstance(response, Mapping):
        raise CorrectedExecutionGateError("principal response is absent at lock gate")

    if first_lock.get("schema") != FIRST_LOCK_SCHEMA:
        raise CorrectedExecutionGateError("unsupported first-lock schema")
    if first_lock.get("first_lock_hash") != canonical_hash(first_lock, omit="first_lock_hash"):
        raise CorrectedExecutionGateError("first-lock hash mismatch")
    if first_lock.get("run_id") != execution.get("run_id"):
        raise CorrectedExecutionGateError("first-lock run mismatch")
    if first_lock.get("execution_receipt_hash") != execution.get("execution_receipt_hash"):
        raise CorrectedExecutionGateError("first lock is not linked to principal execution")
    if first_lock.get("principal_response_id") != response.get("response_id"):
        raise CorrectedExecutionGateError("first lock is not linked to principal response")
    if first_lock.get("principal_output_sha256") != response.get("output_sha256"):
        raise CorrectedExecutionGateError("first lock does not bind principal output")
    _require_sha(first_lock.get("output_validation_receipt_sha256"), "output validation")
    if first_lock.get("controller_summary_locked") is not False:
        raise CorrectedExecutionGateError("controller summary cannot be first-locked")
    if first_lock.get("principal_output_locked") is not True:
        raise CorrectedExecutionGateError("principal output was not first-locked")

    if freeze.get("schema") != FREEZE_SCHEMA:
        raise CorrectedExecutionGateError("unsupported freeze schema")
    if freeze.get("freeze_hash") != canonical_hash(freeze, omit="freeze_hash"):
        raise CorrectedExecutionGateError("freeze hash mismatch")
    if freeze.get("run_id") != execution.get("run_id"):
        raise CorrectedExecutionGateError("freeze run mismatch")
    if freeze.get("first_lock_hash") != first_lock.get("first_lock_hash"):
        raise CorrectedExecutionGateError("freeze does not link to first lock")
    if freeze.get("principal_output_sha256") != response.get("output_sha256"):
        raise CorrectedExecutionGateError("freeze does not bind principal output")
    if freeze.get("one_way_handoff_not_yet_created") is not True:
        raise CorrectedExecutionGateError("freeze must precede one-way handoff")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_RT_LOCK_FREEZE_GATE_V1",
        "run_id": execution["run_id"],
        "execution_receipt_hash": execution["execution_receipt_hash"],
        "first_lock_hash": first_lock["first_lock_hash"],
        "freeze_hash": freeze["freeze_hash"],
        "locked_output_sha256": response["output_sha256"],
        "principal_output_locked": True,
        "controller_summary_locked": False,
        "freeze_precedes_one_way_handoff": True,
    }
