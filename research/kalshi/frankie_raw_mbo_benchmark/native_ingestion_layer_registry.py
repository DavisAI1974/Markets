#!/usr/bin/env python3
"""Versioned, fail-closed ingestion-layer gates for corrected Frankie A arms."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REGISTRY_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_INGESTION_LAYER_REGISTRY_V1"
PRE_CALL_RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRE_CALL_LAYER_RECEIPT_V1"
GROUP_DELIVERY_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_CAUSAL_GROUP_DELIVERY_V1"
HARD_MINIMUM_CONCRETE_LAYER_COUNT = 90
EXPECTED_UNION_LAYER_COUNT = 99
"""Was 105. Six helper layers were removed 2026-08-30 - see D64 and the note below."""
EXPECTED_ARM_LAYER_COUNTS = {"A_CLEAN": 96, "A_MEMORY": 98}
EXPECTED_LAYER_ID_SET_SHA256 = (
    "fbb79cde505cb9a119b31a716d9516839d3bcbc2710a15be70266b3069b14eef"
)
EXPECTED_POLICY_COUNTS = {
    "STATIC_REQUIRED_INPUT": 19,
    "ARM_REQUIRED_INPUT": 4,
    "CAUSAL_STREAM_REQUIRED": 55,
    "SEALED_FOR_A_SCOPE": 9,
    "PROVISIONAL_SHADOW": 2,
    "APPEND_ONLY_OUTPUT": 10,
}
# D64 (Greg, 2026-08-30): "get any mention of the 4 helpers out. He can call with different
# persona options as part of his tools." D54 retired the four-helper architecture for the A
# arms and D63 reaffirmed it, but the registry went on REQUIRING it - these constants
# enforced `("AVAILABLE", model_visible=True, "SHA")` on the layer that documents it, so
# Frankie would have read a superseded architecture as a binding input on every run. A
# decision the enforcement layer contradicts is worse than one nothing enforces, and it had
# not bitten only because no run reached the pre-call gate.
#
# SIX layer identities were removed, and the counts above are what that costs:
#   extra_agent_four_helper_architecture_roles   (corrected_extra_agent_carryforward)
#   helper_pair_triplet_recurrence_scout         )
#   helper_extension_propensity_scout            ) the whole helper_role_configuration
#   helper_timing_lifespan_family_scout          ) group, which no longer exists
#   helper_true_false_context_investigator       )
#   output_helper_evidence_movie                 (append_only_outputs)
#
# NOTHING SOURCE-LEVEL WAS DROPPED, which is what D60 requires. The removed carryforward
# layer named exactly the same three V3 files as
# `extra_agent_corrected_information_and_gap_diagnoses`, which remains required and
# model-visible, and those files contain no helper text - the four-helper architecture lived
# in the layer DESCRIPTION and in the feed inventory, not in the evidence. What was removed
# is the instruction to read them as a helper architecture, not the evidence itself.
#
# 99 still clears HARD_MINIMUM_CONCRETE_LAYER_COUNT (90) with nine to spare.
ALLOWED_ARMS = frozenset(EXPECTED_ARM_LAYER_COUNTS)
ALLOWED_V3_LAYER_IDS = frozenset(
    {
        "extra_agent_corrected_information_and_gap_diagnoses",
        "learned_structure_proposal_index_material",
    }
)
"""Two members. `extra_agent_four_helper_architecture_roles` left under D64 (2026-08-30).
`learned_structure_proposal_index_material` joined 2026-09-02 under Greg's ruling that THE
PROPOSAL LINEAGE GOES IN WHOLE (DROP_IN_S121 item zero, ruling 3): the two `_V3_V4_` brain
trade-proposal addenda of source-inventory section D are knowledge he receives, so the layer
that binds them carries V3-derived material and says so. The feed inventory's section 3
sentence that the extra-agent carryforward is the ONLY admissible V3-derived material is
superseded for the proposal lineage by that ruling; recorded here because a decision written
where nothing enforces it has not landed."""
ALLOWED_V3_SOURCE_PATHS = frozenset(
    {
        "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json",
        "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md",
        "research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
        # Greg, 2026-09-02: the proposal lineage goes in whole. Exactly these two files of
        # source-inventory section D; nothing else V3-named is admitted by this line.
        "research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md",
        "research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_FINAL_ADDENDUM_20260820.md",
    }
)
SEALED_LAYER_IDS = frozenset(
    {
        "later_outcome_reveal",
        "target_ground_truth_onset_time",
        "step1_existing_october_seconds",
        "step1_populations",
        "step1_crosswalks",
        "step1_target_membership_receipts",
        "step1_labels_and_classifications",
        "step1_result_prefixes",
        "step1_reconciliation_outputs",
    }
)
REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "frankie_native_raw_mbo_ingestion_layer_registry_20260828.json"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LAYER_ID_RE = re.compile(r"^[a-z0-9_]+$")
TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "version",
        "hard_minimum_concrete_layer_count",
        "source_authority",
        "permitted_v3_source_paths",
        "groups",
        "registry_sha256",
    }
)
GROUP_KEYS = frozenset(
    {
        "group_id",
        "policy",
        "activation_stage",
        "authority",
        "arms",
        "principal_route",
        "proof_mode",
        "entries",
    }
)
ENTRY_KEYS = frozenset(
    {"layer_id", "description", "source_paths", "v3_derived"}
)
PRE_CALL_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "arm",
        "stage",
        "registry_sha256",
        "layers",
        "receipt_sha256",
    }
)
PRE_CALL_LAYER_KEYS = frozenset(
    {"layer_id", "status", "model_visible", "evidence_receipt_sha256"}
)
GROUP_DELIVERY_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "arm",
        "registry_sha256",
        "group_id",
        "group_sha256",
        "f_last_closed",
        "clocks",
        "delivered_layers",
        "previous_delivery_receipt_sha256",
        "receipt_sha256",
    }
)
GROUP_CLOCK_KEYS = frozenset(
    {"event_time_ns", "receive_time_ns", "availability_time_ns", "decision_time_ns"}
)
DELIVERED_LAYER_KEYS = frozenset(
    {"layer_id", "model_visible", "evidence_receipt_sha256"}
)


class IngestionLayerGateError(ValueError):
    """A registry or runtime receipt cannot prove complete lawful ingestion."""


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


def _require_exact_keys(value: Any, keys: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise IngestionLayerGateError(f"{label} fields are incomplete or unknown")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IngestionLayerGateError(f"{label} must be a non-empty string")
    return value


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise IngestionLayerGateError(f"{label} must be a lowercase SHA-256")
    return value


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise IngestionLayerGateError("ingestion registry must be a JSON object")
    return value


def _flatten_registry(
    registry: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    groups = registry.get("groups")
    if not isinstance(groups, list) or not groups:
        raise IngestionLayerGateError("registry groups must be a non-empty list")
    groups_by_id: dict[str, Mapping[str, Any]] = {}
    layers_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_group in groups:
        group = _require_exact_keys(raw_group, GROUP_KEYS, "registry group")
        group_id = _require_text(group.get("group_id"), "group_id")
        if LAYER_ID_RE.fullmatch(group_id) is None or group_id in groups_by_id:
            raise IngestionLayerGateError("registry group ids must be unique snake-case ids")
        groups_by_id[group_id] = group
        policy = group.get("policy")
        if policy not in EXPECTED_POLICY_COUNTS:
            raise IngestionLayerGateError(f"unsupported registry policy: {policy}")
        for field in ("activation_stage", "authority", "principal_route", "proof_mode"):
            _require_text(group.get(field), f"{group_id}.{field}")
        arms = group.get("arms")
        if (
            not isinstance(arms, list)
            or not arms
            or len(set(arms)) != len(arms)
            or not set(arms).issubset(ALLOWED_ARMS)
        ):
            raise IngestionLayerGateError(f"{group_id}.arms is invalid")
        entries = group.get("entries")
        if not isinstance(entries, list) or not entries:
            raise IngestionLayerGateError(f"{group_id}.entries must be non-empty")
        for raw_entry in entries:
            entry = _require_exact_keys(raw_entry, ENTRY_KEYS, "registry layer")
            layer_id = _require_text(entry.get("layer_id"), "layer_id")
            if LAYER_ID_RE.fullmatch(layer_id) is None or layer_id in layers_by_id:
                raise IngestionLayerGateError("layer ids must be unique snake-case ids")
            _require_text(entry.get("description"), f"{layer_id}.description")
            paths = entry.get("source_paths")
            if (
                not isinstance(paths, list)
                or not paths
                or any(not isinstance(path, str) or not path.strip() for path in paths)
            ):
                raise IngestionLayerGateError(f"{layer_id}.source_paths is invalid")
            if not isinstance(entry.get("v3_derived"), bool):
                raise IngestionLayerGateError(f"{layer_id}.v3_derived must be boolean")
            layers_by_id[layer_id] = {"group": group, "entry": entry}
    return groups_by_id, layers_by_id


def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact V1 registry identity and its hard cardinality floor."""
    _require_exact_keys(registry, TOP_LEVEL_KEYS, "ingestion registry")
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise IngestionLayerGateError("unsupported ingestion registry schema")
    _require_text(registry.get("version"), "registry version")
    _require_text(registry.get("source_authority"), "source authority")
    if registry.get("hard_minimum_concrete_layer_count") != HARD_MINIMUM_CONCRETE_LAYER_COUNT:
        raise IngestionLayerGateError("registry hard minimum must remain exactly 90")
    if registry.get("registry_sha256") != canonical_hash(registry, omit="registry_sha256"):
        raise IngestionLayerGateError("ingestion registry hash mismatch")
    if set(registry.get("permitted_v3_source_paths", [])) != ALLOWED_V3_SOURCE_PATHS:
        raise IngestionLayerGateError("V3 source allowlist drift")

    _groups, layers = _flatten_registry(registry)
    layer_count = len(layers)
    if layer_count < HARD_MINIMUM_CONCRETE_LAYER_COUNT:
        raise IngestionLayerGateError("registry violates hard floor of 90 concrete layers")
    if layer_count != EXPECTED_UNION_LAYER_COUNT:
        raise IngestionLayerGateError(
            f"V1 registry must contain exactly {EXPECTED_UNION_LAYER_COUNT} layer identities"
        )
    id_set_hash = hashlib.sha256(canonical_bytes(sorted(layers))).hexdigest()
    if id_set_hash != EXPECTED_LAYER_ID_SET_SHA256:
        raise IngestionLayerGateError("V1 exact layer identity set drift")

    policy_counts = Counter(
        binding["group"]["policy"] for binding in layers.values()
    )
    if dict(policy_counts) != EXPECTED_POLICY_COUNTS:
        raise IngestionLayerGateError("V1 layer policy counts drift")
    arm_counts = {
        arm: sum(arm in binding["group"]["arms"] for binding in layers.values())
        for arm in sorted(ALLOWED_ARMS)
    }
    if arm_counts != EXPECTED_ARM_LAYER_COUNTS:
        raise IngestionLayerGateError("V1 arm-applicable layer counts drift")

    placeholder_ids = sorted(
        layer_id
        for layer_id, binding in layers.items()
        if any(
            token in (layer_id + " " + binding["entry"]["description"]).lower()
            for token in ("placeholder", "unnamed", "other provisional", "tbd", "todo")
        )
    )
    if placeholder_ids:
        raise IngestionLayerGateError("placeholder layers cannot count toward the hard floor")

    v3_ids = sorted(
        layer_id
        for layer_id, binding in layers.items()
        if binding["entry"]["v3_derived"]
    )
    if set(v3_ids) != ALLOWED_V3_LAYER_IDS:
        raise IngestionLayerGateError("only corrected extra-agent V3 carryforward is allowed")
    for layer_id, binding in layers.items():
        entry = binding["entry"]
        v3_paths = {path for path in entry["source_paths"] if "_V3_" in path}
        if v3_paths - ALLOWED_V3_SOURCE_PATHS:
            raise IngestionLayerGateError(f"unapproved V3 source path: {layer_id}")
        if bool(v3_paths) != entry["v3_derived"]:
            raise IngestionLayerGateError(f"V3 provenance flag mismatch: {layer_id}")

    sealed_ids = sorted(
        layer_id
        for layer_id, binding in layers.items()
        if binding["group"]["policy"] == "SEALED_FOR_A_SCOPE"
    )
    if set(sealed_ids) != SEALED_LAYER_IDS:
        raise IngestionLayerGateError("the exact nine A-scope sealed identities drifted")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_INGESTION_REGISTRY_GATE_V1",
        "registry_sha256": registry["registry_sha256"],
        "hard_minimum_concrete_layer_count": HARD_MINIMUM_CONCRETE_LAYER_COUNT,
        "concrete_layer_count": layer_count,
        "a_clean_applicable_layer_count": arm_counts["A_CLEAN"],
        "a_memory_applicable_layer_count": arm_counts["A_MEMORY"],
        "sealed_layer_count": len(sealed_ids),
        "sealed_layer_ids": sealed_ids,
        "v3_derived_layer_ids": v3_ids,
        "placeholder_layer_ids": placeholder_ids,
        "exact_layer_id_set_sha256": id_set_hash,
    }


def validate_pre_call_receipt(
    receipt: Mapping[str, Any], *, registry: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Prove static readiness without exposing future causal values or sealed answers."""
    active_registry = load_registry() if registry is None else dict(registry)
    registry_gate = validate_registry(active_registry)
    _groups, layers = _flatten_registry(active_registry)
    _require_exact_keys(receipt, PRE_CALL_KEYS, "pre-call layer receipt")
    if receipt.get("schema") != PRE_CALL_RECEIPT_SCHEMA or receipt.get("stage") != "PRE_CALL":
        raise IngestionLayerGateError("unsupported pre-call layer receipt")
    _require_text(receipt.get("run_id"), "run_id")
    arm = receipt.get("arm")
    if arm not in ALLOWED_ARMS:
        raise IngestionLayerGateError("invalid pre-call A-arm")
    if receipt.get("registry_sha256") != active_registry["registry_sha256"]:
        raise IngestionLayerGateError("pre-call registry identity mismatch")
    if receipt.get("receipt_sha256") != canonical_hash(receipt, omit="receipt_sha256"):
        raise IngestionLayerGateError("pre-call receipt hash mismatch")
    raw_rows = receipt.get("layers")
    if not isinstance(raw_rows, list):
        raise IngestionLayerGateError("pre-call layers must enumerate the complete registry")
    by_id: dict[str, Mapping[str, Any]] = {}
    for raw_row in raw_rows:
        row = _require_exact_keys(raw_row, PRE_CALL_LAYER_KEYS, "pre-call layer")
        layer_id = row.get("layer_id")
        if not isinstance(layer_id, str) or layer_id in by_id:
            raise IngestionLayerGateError("pre-call layer identities must be unique")
        by_id[layer_id] = row
    if set(by_id) != set(layers):
        raise IngestionLayerGateError("pre-call receipt must enumerate the complete registry")

    required_count = 0
    sealed_count = 0
    for layer_id, binding in layers.items():
        group = binding["group"]
        row = by_id[layer_id]
        if not isinstance(row.get("model_visible"), bool):
            raise IngestionLayerGateError(f"malformed visibility flag: {layer_id}")
        if arm not in group["arms"]:
            expected = ("NOT_APPLICABLE", False, None)
        elif group["policy"] in {"STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"}:
            expected = ("AVAILABLE", True, "SHA")
            required_count += 1
        elif group["policy"] == "CAUSAL_STREAM_REQUIRED":
            expected = ("READY_CAUSAL_STREAM", False, "SHA")
            required_count += 1
        elif group["policy"] == "SEALED_FOR_A_SCOPE":
            expected = ("SEALED", False, "SHA")
            sealed_count += 1
        elif group["policy"] == "PROVISIONAL_SHADOW":
            if row.get("status") not in {"SHADOW_DISABLED", "SHADOW_READY"}:
                raise IngestionLayerGateError(f"invalid shadow status: {layer_id}")
            expected = (row["status"], False, "SHA")
        else:
            expected = ("PENDING", False, None)
        status, visible, hash_policy = expected
        if row.get("status") != status or row.get("model_visible") is not visible:
            label = "required input" if "REQUIRED" in group["policy"] else "sealed layer"
            raise IngestionLayerGateError(f"{label} pre-call policy failed: {layer_id}")
        evidence_hash = row.get("evidence_receipt_sha256")
        if hash_policy == "SHA":
            _require_sha(evidence_hash, f"{layer_id}.evidence_receipt")
        elif evidence_hash is not None:
            raise IngestionLayerGateError(f"unexpected pre-call evidence hash: {layer_id}")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRE_CALL_LAYER_GATE_V1",
        "run_id": receipt["run_id"],
        "arm": arm,
        "registry_sha256": registry_gate["registry_sha256"],
        "registered_layer_count": len(layers),
        "applicable_layer_count": EXPECTED_ARM_LAYER_COUNTS[arm],
        "required_input_count": required_count,
        "sealed_layer_count": sealed_count,
        "answer_wall_sealed": sealed_count == len(SEALED_LAYER_IDS),
        "all_required_inputs_available": True,
        "future_causal_values_visible_pre_call": False,
        "pre_call_receipt_sha256": receipt["receipt_sha256"],
    }


def validate_causal_group_delivery_receipt(
    receipt: Mapping[str, Any], *, registry: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Require all lawful causal-stream layers at one closed F_LAST group."""
    active_registry = load_registry() if registry is None else dict(registry)
    validate_registry(active_registry)
    _groups, layers = _flatten_registry(active_registry)
    _require_exact_keys(receipt, GROUP_DELIVERY_KEYS, "causal group delivery")
    if receipt.get("schema") != GROUP_DELIVERY_SCHEMA:
        raise IngestionLayerGateError("unsupported causal group delivery schema")
    _require_text(receipt.get("run_id"), "run_id")
    arm = receipt.get("arm")
    if arm not in ALLOWED_ARMS:
        raise IngestionLayerGateError("invalid causal-delivery A-arm")
    if receipt.get("registry_sha256") != active_registry["registry_sha256"]:
        raise IngestionLayerGateError("causal-delivery registry identity mismatch")
    if receipt.get("receipt_sha256") != canonical_hash(receipt, omit="receipt_sha256"):
        raise IngestionLayerGateError("causal group delivery hash mismatch")
    group_id = receipt.get("group_id")
    if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 0:
        raise IngestionLayerGateError("causal group id must be a non-negative integer")
    _require_sha(receipt.get("group_sha256"), "group_sha256")
    _require_sha(
        receipt.get("previous_delivery_receipt_sha256"),
        "previous_delivery_receipt_sha256",
    )
    if receipt.get("f_last_closed") is not True:
        raise IngestionLayerGateError("causal layers cannot be delivered before F_LAST")
    clocks = _require_exact_keys(receipt.get("clocks"), GROUP_CLOCK_KEYS, "causal clocks")
    for name, value in clocks.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise IngestionLayerGateError(f"invalid causal clock: {name}")
    if clocks["availability_time_ns"] < clocks["receive_time_ns"]:
        raise IngestionLayerGateError("availability cannot precede receive time")
    if clocks["decision_time_ns"] < clocks["availability_time_ns"]:
        raise IngestionLayerGateError("decision cannot precede availability")

    expected_ids = {
        layer_id
        for layer_id, binding in layers.items()
        if binding["group"]["policy"] == "CAUSAL_STREAM_REQUIRED"
        and arm in binding["group"]["arms"]
    }
    raw_rows = receipt.get("delivered_layers")
    if not isinstance(raw_rows, list):
        raise IngestionLayerGateError("delivery must contain the complete causal layer set")
    by_id: dict[str, Mapping[str, Any]] = {}
    for raw_row in raw_rows:
        row = _require_exact_keys(raw_row, DELIVERED_LAYER_KEYS, "delivered layer")
        layer_id = row.get("layer_id")
        if not isinstance(layer_id, str) or layer_id in by_id:
            raise IngestionLayerGateError("delivered layer ids must be unique")
        by_id[layer_id] = row
    if set(by_id) != expected_ids:
        raise IngestionLayerGateError("delivery must contain the complete causal layer set")
    for layer_id, row in by_id.items():
        if row.get("model_visible") is not True:
            raise IngestionLayerGateError(f"causal layer was not model visible: {layer_id}")
        _require_sha(row.get("evidence_receipt_sha256"), f"{layer_id}.evidence_receipt")

    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_CAUSAL_GROUP_DELIVERY_GATE_V1",
        "run_id": receipt["run_id"],
        "arm": arm,
        "group_id": group_id,
        "group_sha256": receipt["group_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "f_last_closed": True,
        "delivered_layer_count": len(by_id),
        "delivered_layer_ids": sorted(by_id),
        "all_causal_layers_delivered": True,
        "answer_wall_visible": False,
    }
