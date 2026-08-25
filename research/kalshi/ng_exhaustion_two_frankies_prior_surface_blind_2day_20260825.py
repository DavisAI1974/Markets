#!/usr/bin/env python3
"""Run exactly Real-Time Frankie then Forecaster Frankie on the prior Oct-4/5 surface.

This is an additive, run-specific wrapper.  It never imports Step-1 populations,
crosswalks, self-fit summaries, structural labels, or any answer/reveal artifact.
The only market tape it accepts is the already-validated, reduced October seconds
surface.  Real-Time Frankie receives bounded retrieval tools over the exact two-day
slice; Forecaster Frankie receives the frozen Real-Time state and a direct,
day-specific causal summary.  No helper, specialist, provider-backed scout,
automatic scout, alternate provider, retry, or model fallback is implemented.
One optional deterministic local RT scout is exposed only for an explicit
Real-Time Frankie tool request; it has no model call, fee, or mutation authority.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.kalshi.frankie_role_context_profiles_20260824 import (  # noqa: E402
    FrankieRole,
    build_role_context_payload,
)


SCHEMA = "NG_EXHAUSTION_TWO_FRANKIES_PRIOR_SURFACE_BLIND_2DAY_V1_20260825"
MODEL = "gpt-5.6-sol"
TARGET_START_ISO = "2021-10-04T00:00:00Z"
TARGET_END_EXCLUSIVE_ISO = "2021-10-06T00:00:00Z"
TARGET_START_S = int(dt.datetime(2021, 10, 4, tzinfo=dt.timezone.utc).timestamp())
TARGET_END_S = int(dt.datetime(2021, 10, 6, tzinfo=dt.timezone.utc).timestamp())

EXPECTED_SECONDS_BYTES = 112_852_940
EXPECTED_SECONDS_SHA256 = "93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90"
EXPECTED_RECEIPT_FILE_SHA256 = "80b6cf7199805cf40a0b16b139ee1aa8f705b884acf03856640df4054802f7ab"
EXPECTED_RECEIPT_SHA256 = "4966dac8b25fee7acabf53f880a30155985bd5767ee222381f1188d4eecada3c"

SOURCE_CONTROL = HERE / "NG_EXHAUSTION_PRIOR_SURFACE_OCT45_SOURCE_20260825.json"
CAPABILITY_OVERLAY = HERE / "FRANKIE_PRIOR_SURFACE_OCT45_CAPABILITY_OVERLAY_20260825.json"
LAUNCH_CONTROL = HERE / "NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_LAUNCH_20260825.json"
RT_MISSION_PATH = HERE / "agents/frankie_prior_surface_oct45_realtime_20260825.md"
FORECASTER_MISSION_PATH = HERE / "agents/frankie_prior_surface_oct45_forecaster_20260825.md"
BUILD_CONTROL_PATH = HERE / "NG_EXHAUSTION_PRIOR_SURFACE_OCT45_TWO_FRANKIES_BUILD_CONTROL_20260825.md"

COMMON_MISSION = (
    "Independently use the causally available prior-surface evidence to detect and predict event birth "
    "as early as possible; estimate onset/start and run duration; identify family, category, depth, "
    "severity, and uncertainty; create new structures when the evidence does not fit existing ones; "
    "and search for correlations, interactions, lags, clock relationships, sequence motifs, and "
    "mechanisms that Step-1 may not have found. Preserve exact ts_event/ts_recv as-of reasoning. "
    "Prior Step-1 structures may be similar or exact, but matching them is neither expected nor required."
)

# Token planning is intentionally conservative relative to the measured 0.2581
# tokens/byte floor documented for this repository's prior Sol calls.  Every
# physical Responses request is checked before it is sent.
TOKEN_ESTIMATE_PER_BYTE = 0.285
RT_DIRECT_INPUT_TOKEN_CAP = 48_000
RT_CUMULATIVE_INPUT_TOKEN_CAP = 96_000
FORECASTER_INPUT_TOKEN_CAP = 150_000
MAX_OUTPUT_TOKENS = 12_000
MAX_RT_TOOL_ROUNDS = 12
MAX_PHYSICAL_RESPONSES_REQUESTS = 14
MAX_TOOL_RESULT_BYTES = 450_000
MAX_WINDOW_ROWS = 500

EXPECTED_BIGSUITE_LEAVES = 1_940
EXPECTED_BIGSUITE_BLOCKS = 46

PRIOR_ROW_FIELDS = frozenset(
    {
        "epoch_second",
        "legacy_rows",
        "legacy_buy_qty",
        "legacy_sell_qty",
        "native_buy_qty",
        "native_sell_qty",
        "trade_count",
        "last_trade_price",
        "book_imbalance_sum",
        "book_imbalance_n",
        "last_ts_recv_ns",
        "last_raw_symbol",
        "last_instrument_id",
        "source_dbn_object",
        "source_dbn_key",
        "source_dbn_sha256",
        "source_interval",
        "native_segment_job_id",
        "canonical_interval_job_id",
        "source_requested_symbol",
        "raw_contract_resolution",
        "source_selection_reason",
        "native_state",
        "integrity",
    }
)
NATIVE_STATE_FIELDS = frozenset(
    {
        "spread",
        "depth_imbalance_full",
        "bid_depth_full",
        "ask_depth_full",
        "bid_order_count_full",
        "ask_order_count_full",
        "bid_price_level_count_full",
        "ask_price_level_count_full",
        "activity_20",
        "fifo_priority_reconstructed",
        "full_depth_exposed_in_process",
    }
)
FORBIDDEN_INPUT_KEY_FRAGMENTS = (
    "answer_key",
    "ground_truth",
    "realized_",
    "actual_",
    "future_price",
    "outcome_",
    "post_reveal",
    "postreveal",
    "target_label",
    "structural_depth_label",
)
FORBIDDEN_INPUT_PATH_FRAGMENTS = (
    "population",
    "crosswalk",
    "self_fit",
    "answer",
    "reveal",
    "d0_d5",
    "54w",
)


class TwoFrankieBlindError(RuntimeError):
    """A frozen identity, blind wall, provider, or output contract failed."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TwoFrankieBlindError(f"cannot read deterministic JSON: {path}") from exc
    if not isinstance(value, dict):
        raise TwoFrankieBlindError(f"expected a JSON object: {path}")
    return value


def control_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TwoFrankieBlindError(f"required run-specific control is missing: {path}")
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _validate_control_files() -> dict[str, Any]:
    controls = {
        "source": control_identity(SOURCE_CONTROL),
        "capability_overlay": control_identity(CAPABILITY_OVERLAY),
        "launch": control_identity(LAUNCH_CONTROL),
        "realtime_mission": control_identity(RT_MISSION_PATH),
        "forecaster_mission": control_identity(FORECASTER_MISSION_PATH),
        "build_control": control_identity(BUILD_CONTROL_PATH),
    }
    source = read_json(SOURCE_CONTROL)
    overlay = read_json(CAPABILITY_OVERLAY)
    launch = read_json(LAUNCH_CONTROL)
    expected_source_keys = {
        "schema", "run_id", "source_identity", "window", "information_surface",
        "clock_policy", "blind_firewall", "fail_closed",
    }
    if set(source) != expected_source_keys:
        raise TwoFrankieBlindError("run-specific source-control schema drift")
    source_identity = source.get("source_identity")
    if not isinstance(source_identity, Mapping) or (
        source_identity.get("bytes") != EXPECTED_SECONDS_BYTES
        or source_identity.get("sha256") != EXPECTED_SECONDS_SHA256
        or source_identity.get("child_receipt_file_sha256") != EXPECTED_RECEIPT_FILE_SHA256
        or source_identity.get("child_receipt_canonical_sha256") != EXPECTED_RECEIPT_SHA256
        or source_identity.get("provider_visibility") != "SEALED_ROOT_ONLY_IDENTITY"
    ):
        raise TwoFrankieBlindError("run-specific source identity drift")
    if source.get("window") != {
        "start": TARGET_START_ISO,
        "end_exclusive": TARGET_END_EXCLUSIVE_ISO,
        "included_utc_dates": ["2021-10-04", "2021-10-05"],
    }:
        raise TwoFrankieBlindError("run-specific target window drift")
    information = source.get("information_surface")
    if not isinstance(information, Mapping) or (
        information.get("surface_label") != "PRIOR_REDUCED_NON_FULL_MBO_SURFACE"
        or information.get("may_be_described_as_full_mbo") is not False
        or information.get("raw_mbo_replayed") is not False
        or information.get("added_current_full_mbo_fields") is not False
    ):
        raise TwoFrankieBlindError("prior reduced/non-full-MBO information-surface drift")

    registry = overlay.get("registry_contract")
    if not isinstance(registry, Mapping) or (
        overlay.get("evidence_surface_label") != "PRIOR_REDUCED_NON_FULL_MBO_SURFACE"
        or registry.get("expected_exact_leaf_count") != EXPECTED_BIGSUITE_LEAVES
        or registry.get("expected_exact_block_count") != EXPECTED_BIGSUITE_BLOCKS
        or registry.get("leaf_items_key") != "leaf_items"
        or registry.get("block_items_key") != "block_items"
        or registry.get("zero_silent_omissions") is not True
    ):
        raise TwoFrankieBlindError("run-specific capability-overlay registry drift")

    if launch.get("launch_authorized") is not True:
        raise TwoFrankieBlindError("run-specific launch marker is not authorized")
    model = launch.get("model")
    if not isinstance(model, Mapping) or model.get("requested") != MODEL or model.get("store") is not False:
        raise TwoFrankieBlindError("run-specific launch marker model drift")
    logical = launch.get("logical_call_contract")
    if not isinstance(logical, Mapping) or (
        logical.get("role_order") != [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value]
        or logical.get("logical_role_calls") != 2
        or logical.get("specialist_model_calls") != 0
        or logical.get("rt_optional_local_scout_auto_called") is not False
        or logical.get("rt_max_tool_continuation_rounds") != MAX_RT_TOOL_ROUNDS
        or logical.get("maximum_responses_api_requests") != MAX_PHYSICAL_RESPONSES_REQUESTS
        or logical.get("invalid_response_repair_calls") != 0
    ):
        raise TwoFrankieBlindError("run-specific launch marker must authorize exactly two logical calls")
    caps = launch.get("token_caps")
    if caps != {
        "rt_direct_input": RT_DIRECT_INPUT_TOKEN_CAP,
        "rt_cumulative_billable_input": RT_CUMULATIVE_INPUT_TOKEN_CAP,
        "rt_output": MAX_OUTPUT_TOKENS,
        "forecaster_input": FORECASTER_INPUT_TOKEN_CAP,
        "forecaster_output": MAX_OUTPUT_TOKENS,
        "combined_conservative_input": RT_CUMULATIVE_INPUT_TOKEN_CAP + FORECASTER_INPUT_TOKEN_CAP,
        "combined_conservative_output": MAX_OUTPUT_TOKENS * 2,
    }:
        raise TwoFrankieBlindError("run-specific token caps drift")
    pricing = launch.get("pricing")
    if not isinstance(pricing, Mapping) or any(
        pricing.get(key) is None
        for key in (
            "input_usd_per_million", "cached_input_usd_per_million",
            "output_usd_per_million", "pricing_source", "pricing_as_of", "max_budget_usd",
        )
    ):
        raise TwoFrankieBlindError("verified pricing and maximum budget must be bound before launch")
    for launch_key, control_key in (("source_config", "source"), ("capability_overlay", "capability_overlay")):
        binding = launch.get(launch_key)
        if not isinstance(binding, Mapping) or binding.get("sha256") != controls[control_key]["sha256"]:
            raise TwoFrankieBlindError(f"launch marker does not hash-bind {launch_key}")
    build_control = launch.get("build_control")
    if not isinstance(build_control, Mapping) or build_control.get("sha256") != controls["build_control"]["sha256"]:
        raise TwoFrankieBlindError("launch marker does not hash-bind build control")
    missions = launch.get("mission_files")
    if not isinstance(missions, Mapping):
        raise TwoFrankieBlindError("launch marker mission bindings are absent")
    for role, control_key in (
        (FrankieRole.REAL_TIME.value, "realtime_mission"),
        (FrankieRole.FORECASTER.value, "forecaster_mission"),
    ):
        binding = missions.get(role)
        if not isinstance(binding, Mapping) or (
            binding.get("sha256") != controls[control_key]["sha256"]
            or binding.get("read_byte_for_byte") is not True
            or binding.get("summary_or_rewrite_allowed") is not False
        ):
            raise TwoFrankieBlindError(f"launch marker does not byte-bind {role} mission")
    package_manifest = read_json(REPO_ROOT / "PACKAGE_MANIFEST.json")
    source_commit = str(package_manifest.get("source_commit") or "")
    implementation_commit = str(package_manifest.get("implementation_commit") or "")
    authorized_commit = str((launch.get("authorization") or {}).get("exact_commit") or "")
    if (
        not source_commit
        or not implementation_commit
        or source_commit == implementation_commit
        or authorized_commit != implementation_commit
    ):
        raise TwoFrankieBlindError(
            "launch marker must bind the implementation commit preceding the distinct authorization commit"
        )
    canonical = launch.get("canonical_immutability")
    canonical_files = canonical.get("files") if isinstance(canonical, Mapping) else None
    if not isinstance(canonical_files, Mapping) or canonical.get("all_canonical_files_must_remain_byte_identical") is not True:
        raise TwoFrankieBlindError("canonical immutability roster is absent")
    for relative, expected_hash in canonical_files.items():
        path = (REPO_ROOT / str(relative)).resolve()
        if not path.is_relative_to(REPO_ROOT) or not path.is_file() or sha256_file(path) != expected_hash:
            raise TwoFrankieBlindError(f"canonical protected file hash drift: {relative}")
    workflow = launch.get("workflow")
    if not isinstance(workflow, Mapping) or not workflow.get("sha256"):
        raise TwoFrankieBlindError("launch workflow hash is not bound")
    workflow_path = (REPO_ROOT / str(workflow.get("path") or "")).resolve()
    if not workflow_path.is_relative_to(REPO_ROOT) or not workflow_path.is_file() or sha256_file(workflow_path) != workflow["sha256"]:
        raise TwoFrankieBlindError("launch workflow hash drift")
    return {
        "controls": controls,
        "launch_control": launch,
        "source_control_hash": controls["source"]["sha256"],
        "overlay_control_hash": controls["capability_overlay"]["sha256"],
        "authorization_commit": source_commit,
        "implementation_commit": implementation_commit,
    }


def _mission_binding_hash() -> str:
    rows = {}
    for role, path in (
        (FrankieRole.REAL_TIME.value, RT_MISSION_PATH),
        (FrankieRole.FORECASTER.value, FORECASTER_MISSION_PATH),
    ):
        body = path.read_bytes()
        body.decode("utf-8")
        rows[role] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    binding = {
        "schema": "PRIOR_REDUCED_NON_FULL_MBO_MISSION_BINDING_V1_20260825",
        "missions": rows,
        "warning": (
            "Missing historical capability evidence remains UNAVAILABLE, UNKNOWN, or DORMANT; "
            "it is never false or numeric zero. Full-MBO evidence is unavailable on this prior reduced surface."
        ),
    }
    return sha256_json(binding)


def _validate_october_child(seconds_path: Path) -> dict[str, Any]:
    if not seconds_path.is_file():
        raise TwoFrankieBlindError("validated October seconds surface is missing")
    if seconds_path.stat().st_size != EXPECTED_SECONDS_BYTES:
        raise TwoFrankieBlindError("October seconds byte identity drift")
    if sha256_file(seconds_path) != EXPECTED_SECONDS_SHA256:
        raise TwoFrankieBlindError("October seconds SHA-256 identity drift")
    return {
        "status": "SOURCE_BYTES_VERIFIED_RECEIPT_IDENTITY_PREVERIFIED_BY_PRIVILEGED_LAUNCHER",
        "receipt_file_sha256": EXPECTED_RECEIPT_FILE_SHA256,
        "receipt_canonical_sha256": EXPECTED_RECEIPT_SHA256,
    }


def _validate_prior_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != PRIOR_ROW_FIELDS:
        raise TwoFrankieBlindError("prior seconds row schema drift")
    native = row.get("native_state")
    if native is not None and (not isinstance(native, dict) or set(native) != NATIVE_STATE_FIELDS):
        raise TwoFrankieBlindError("prior seconds native_state schema drift")
    second = row.get("epoch_second")
    recv = row.get("last_ts_recv_ns")
    if isinstance(second, bool) or not isinstance(second, int):
        raise TwoFrankieBlindError("prior seconds epoch_second is invalid")
    if isinstance(recv, bool) or not isinstance(recv, int) or recv < second * 1_000_000_000:
        raise TwoFrankieBlindError("prior seconds receive clock is invalid")
    return row


def load_prior_surface(seconds_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prior_second: int | None = None
    digest = hashlib.sha256()
    with gzip.open(seconds_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = _validate_prior_row(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise TwoFrankieBlindError("October seconds surface contains invalid JSONL") from exc
            second = int(row["epoch_second"])
            if prior_second is not None and second <= prior_second:
                raise TwoFrankieBlindError("October seconds are not strictly increasing")
            prior_second = second
            if TARGET_START_S <= second < TARGET_END_S:
                encoded = canonical(row).encode()
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
                rows.append(row)
    if not rows:
        raise TwoFrankieBlindError("exact Oct-4/5 prior-surface selection is empty")
    if rows[0]["epoch_second"] < TARGET_START_S or rows[-1]["epoch_second"] >= TARGET_END_S:
        raise TwoFrankieBlindError("selected prior surface escaped the half-open target")
    max_recv = max(int(row["last_ts_recv_ns"]) for row in rows)
    manifest_core = {
        "schema": "NG_EXHAUSTION_PRIOR_SURFACE_OCT45_SELECTION_V1_20260825",
        "source_kind": "PRIOR_REDUCED_SECONDS_NOT_FULL_RAW_MBO",
        "source_seconds_bytes": EXPECTED_SECONDS_BYTES,
        "source_seconds_sha256": EXPECTED_SECONDS_SHA256,
        "window": {
            "start": TARGET_START_ISO,
            "end_exclusive": TARGET_END_EXCLUSIVE_ISO,
            "semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
        },
        "selected_row_count": len(rows),
        "first_event_second": rows[0]["epoch_second"],
        "last_event_second": rows[-1]["epoch_second"],
        "max_contributing_ts_recv_ns": max_recv,
        "selected_rows_content_hash": digest.hexdigest(),
        "available_fields": sorted(PRIOR_ROW_FIELDS),
        "native_state_fields": sorted(NATIVE_STATE_FIELDS),
        "explicitly_unavailable": [
            "raw_MBO_actions",
            "raw_order_lifecycle",
            "raw_publisher_channel_flags_sequence",
            "raw_ts_in_delta",
            "exact_modify_cancel_before_after_priority_effects",
            "per_order_FIFO_checkpoint",
            "Step1_event_population",
            "Step1_family_or_depth_labels",
            "realized_runway_or_outcomes",
            "54_week_answer_population",
        ],
    }
    return rows, {**manifest_core, "manifest_hash": sha256_json(manifest_core)}


def _flatten_numeric(row: Mapping[str, Any], path: str) -> float | None:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "min": None, "max": None, "range": None, "unique": 0, "quantiles": None}
    def q(frac: float) -> float:
        return ordered[min(len(ordered) - 1, int(frac * (len(ordered) - 1)))]
    return {
        "n": len(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "range": ordered[-1] - ordered[0],
        "unique": len(set(ordered)),
        "quantiles": {"p05": q(0.05), "p25": q(0.25), "p50": q(0.50), "p75": q(0.75), "p95": q(0.95)},
    }


def build_day_context(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    for day_start in (TARGET_START_S, TARGET_START_S + 86_400):
        selected = [row for row in rows if day_start <= int(row["epoch_second"]) < day_start + 86_400]
        numeric_paths = (
            "last_trade_price",
            "legacy_buy_qty",
            "legacy_sell_qty",
            "native_buy_qty",
            "native_sell_qty",
            "native_state.spread",
            "native_state.depth_imbalance_full",
            "native_state.bid_depth_full",
            "native_state.ask_depth_full",
            "native_state.bid_order_count_full",
            "native_state.ask_order_count_full",
        )
        distributions = {}
        for path in numeric_paths:
            values = [value for row in selected if (value := _flatten_numeric(row, path)) is not None]
            distributions[path] = _distribution(values)
        day_iso = dt.datetime.fromtimestamp(day_start, tz=dt.timezone.utc).date().isoformat()
        days.append(
            {
                "date": day_iso,
                "row_count": len(selected),
                "event_clock_range_ns": [day_start * 1_000_000_000, (day_start + 86_400) * 1_000_000_000],
                "recv_clock_min_ns": min((int(row["last_ts_recv_ns"]) for row in selected), default=None),
                "recv_clock_max_ns": max((int(row["last_ts_recv_ns"]) for row in selected), default=None),
                "numeric_distributions_not_mean_only": distributions,
                "row_content_hash": sha256_json(selected),
            }
        )
    core = {
        "schema": "NG_EXHAUSTION_PRIOR_SURFACE_OCT45_DIRECT_DAY_CONTEXT_V1_20260825",
        "source_manifest_hash": manifest["manifest_hash"],
        "days": days,
        "availability_rule": "Only exact prior-surface fields causally received by the final supplied row are present.",
        "outcomes_or_step1_answers_present": False,
    }
    return {**core, "context_hash": sha256_json(core)}


def _capability_availability(
    role_context: Mapping[str, Any], overlay: Mapping[str, Any]
) -> dict[str, Any]:
    reconciliation = role_context.get("capability_reconciliation")
    if not isinstance(reconciliation, Mapping):
        raise TwoFrankieBlindError("role context lacks capability reconciliation")
    bigsuite = reconciliation.get("bigsuite")
    if not isinstance(bigsuite, Mapping):
        raise TwoFrankieBlindError("role context lacks BigSuite reconciliation")
    if bigsuite.get("leaf_count") != EXPECTED_BIGSUITE_LEAVES:
        raise TwoFrankieBlindError("BigSuite leaf count is not exactly 1,940")
    if bigsuite.get("block_count") != EXPECTED_BIGSUITE_BLOCKS:
        raise TwoFrankieBlindError("BigSuite block count is not exactly 46")
    items = bigsuite.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_BIGSUITE_LEAVES:
        raise TwoFrankieBlindError("BigSuite item roster is incomplete")
    role = str(role_context["operating_role"])
    role_overrides = overlay.get("role_surface_overrides", {}).get(role, {})
    full_bigsuite_override = role_overrides.get("full_bigsuite", {})
    availability = []
    for item in items:
        if not isinstance(item, Mapping) or not str(item.get("path") or ""):
            raise TwoFrankieBlindError("BigSuite capability item is malformed")
        path = str(item["path"])
        block = path.split(".", 1)[0]
        availability.append(
            {
                "item_id": item["item_id"],
                "path": path,
                "block": block,
                "state": full_bigsuite_override.get("state", item["activation"]),
                "availability": full_bigsuite_override.get("availability", "UNKNOWN"),
                "coverage": full_bigsuite_override.get("coverage"),
                "provenance": full_bigsuite_override.get(
                    "provenance", "NO_RUN_SPECIFIC_OCTOBER_2021_LEAF_VALUE_RECEIPT"
                ),
                "omission_reason": full_bigsuite_override.get(
                    "omission_reason", "NOT_PROVEN_FOR_THIS_RUN"
                ),
                "semantic_rule": "UNAVAILABLE/UNKNOWN/DORMANT never means false or zero.",
            }
        )
    blocks = []
    for block in sorted({item["block"] for item in availability}):
        block_leaves = [item for item in availability if item["block"] == block]
        states = sorted({str(item["state"]) for item in block_leaves})
        availabilities = sorted({str(item["availability"]) for item in block_leaves})
        blocks.append(
            {
                "block_id": block,
                "leaf_count": len(block_leaves),
                "state": states[0] if len(states) == 1 else "MIXED",
                "availability": availabilities[0] if len(availabilities) == 1 else "MIXED",
                "coverage": None,
                "provenance": "DERIVED_FROM_EXACT_LEAF_ITEMS",
                "omission_reason": "NOT_PROVEN_FOR_THIS_RUN",
            }
        )
    if len(blocks) != EXPECTED_BIGSUITE_BLOCKS:
        raise TwoFrankieBlindError("materialized BigSuite block roster is not exactly 46")
    profile_activation = role_context.get("role_profile", {}).get("activation")
    if not isinstance(profile_activation, Mapping) or len(profile_activation) != 24:
        raise TwoFrankieBlindError("role profile does not preserve all 24 surface IDs")
    surface_items = []
    for surface_id, canonical_state in sorted(profile_activation.items()):
        override = role_overrides.get(surface_id, {})
        surface_items.append(
            {
                "surface_id": surface_id,
                "state": override.get("state", canonical_state),
                "availability": override.get("availability", "UNKNOWN"),
                "coverage": override.get("coverage"),
                "provenance": override.get("provenance", "RUN_SPECIFIC_VALUE_NOT_PROVEN"),
                "omission_reason": override.get("omission_reason", "NOT_PROVEN_FOR_THIS_RUN"),
            }
        )
    executable_tools = reconciliation.get("executable_tools")
    if not isinstance(executable_tools, Mapping) or (
        executable_tools.get("unregistered_tool_count") != 0
        or executable_tools.get("silently_omitted_tool_count") != 0
    ):
        raise TwoFrankieBlindError("installed executable-tool reconciliation is incomplete")
    core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_CAPABILITY_AVAILABILITY_V1_20260825",
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "role": role,
        "registry_leaf_count": EXPECTED_BIGSUITE_LEAVES,
        "registry_block_count": EXPECTED_BIGSUITE_BLOCKS,
        "registry_leaf_hash": bigsuite["registry_leaf_hash"],
        "leaf_items": availability,
        "block_items": blocks,
        "surface_items": surface_items,
        "installed_executable_tools": {
            "tool_count": executable_tools.get("tool_count"),
            "manifest_hash": executable_tools.get("manifest_hash"),
            "unregistered_tool_count": 0,
            "silently_omitted_tool_count": 0,
        },
        "duplicate_leaf_count": 0,
        "unregistered_leaf_count": 0,
        "silently_omitted_leaf_count": 0,
    }
    return {**core, "receipt_hash": sha256_json(core)}


def _compact_role_context(role_context: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the complete build identities while respecting the run's direct-token cap."""
    direct_static = role_context.get("direct_static_surfaces")
    if not isinstance(direct_static, Mapping):
        raise TwoFrankieBlindError("role context direct-static manifest is absent")
    static_manifest: dict[str, Any] = {}
    for surface_id, value in direct_static.items():
        if not isinstance(value, Mapping):
            raise TwoFrankieBlindError("role context direct-static surface is malformed")
        sources = []
        for source in value.get("direct_sources") or []:
            if not isinstance(source, Mapping):
                raise TwoFrankieBlindError("role context direct source is malformed")
            sources.append(
                {key: source[key] for key in ("path", "sha256", "byte_length")}
            )
        static_manifest[str(surface_id)] = {
            "bundle_schema": value.get("bundle_schema"),
            "bundle_hash": value.get("bundle_hash"),
            "direct_source_identities": sources,
            "tool_reference_sources": value.get("tool_reference_sources"),
            "content_route": "PRESERVED_BY_HASH_NOT_DUPLICATED_IN_DIRECT_PACKET_TOKEN_CAP",
        }
    reconciliation = role_context["capability_reconciliation"]
    return {
        "schema": role_context["schema"],
        "operating_role": role_context["operating_role"],
        "uniform_superset_build_hash": role_context["uniform_superset_build_hash"],
        "role_profile": role_context["role_profile"],
        "collaboration_contract": role_context["collaboration_contract"],
        "direct_static_surface_manifest": static_manifest,
        "capability_reconciliation_summary": {
            "receipt_hash": reconciliation["receipt_hash"],
            "bigsuite_manifest_hash": reconciliation["bigsuite"]["manifest_hash"],
            "bigsuite_leaf_count": reconciliation["bigsuite"]["leaf_count"],
            "bigsuite_block_count": reconciliation["bigsuite"]["block_count"],
            "executable_tools_manifest_hash": reconciliation["executable_tools"]["manifest_hash"],
            "executable_tool_count": reconciliation["executable_tools"]["tool_count"],
            "full_leaf_receipt_route": "rt_evidence_scout.capability_lookup",
        },
        "native_context_only": role_context["native_context_only"],
        "nova_token_optimization": role_context["nova_token_optimization"],
        "role_build_hash": role_context["role_build_hash"],
    }


def _blind_path_check(path: Path) -> None:
    lowered = str(path).lower()
    if any(fragment in lowered for fragment in FORBIDDEN_INPUT_PATH_FRAGMENTS):
        raise TwoFrankieBlindError(f"answer/reveal-like input path is forbidden: {path}")


def _blind_object_check(value: Any, path: str = "input") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in FORBIDDEN_INPUT_KEY_FRAGMENTS):
                raise TwoFrankieBlindError(f"answer/outcome-like input key is forbidden: {path}.{key}")
            _blind_object_check(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _blind_object_check(child, f"{path}[{index}]")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _jsonable(dump(mode="json"))
    return str(value)


def _usage(value: Any) -> dict[str, Any]:
    usage = _jsonable(getattr(value, "usage", None))
    if not isinstance(usage, dict):
        usage = {}
    return {
        "provider_usage": usage,
        "cost_usd": None,
        "cost_status": "CALCULATED_ONLY_IN_FINAL_USAGE_RECEIPT_FROM_HASH_BOUND_PRICE_AUTHORITY",
    }


def _usage_cost(call_receipts: Sequence[Mapping[str, Any]], pricing: Mapping[str, Any]) -> dict[str, Any]:
    input_tokens = cached_input_tokens = output_tokens = 0
    response_count = 0
    for call in call_receipts:
        for response in call.get("provider_responses") or []:
            usage = response.get("provider_usage") if isinstance(response, Mapping) else None
            if not isinstance(usage, Mapping):
                raise TwoFrankieBlindError("provider usage is absent; exact cost cannot be receipted")
            raw_input = usage.get("input_tokens", usage.get("input"))
            raw_output = usage.get("output_tokens", usage.get("output"))
            details = usage.get("input_tokens_details", {})
            cached = details.get("cached_tokens", 0) if isinstance(details, Mapping) else 0
            if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (raw_input, raw_output, cached)):
                raise TwoFrankieBlindError("provider token usage fields are invalid")
            if cached > raw_input:
                raise TwoFrankieBlindError("provider cached input exceeds total input")
            input_tokens += raw_input
            cached_input_tokens += cached
            output_tokens += raw_output
            response_count += 1
    input_rate = float(pricing["input_usd_per_million"])
    cached_rate = float(pricing["cached_input_usd_per_million"])
    output_rate = float(pricing["output_usd_per_million"])
    cost = (
        (input_tokens - cached_input_tokens) * input_rate
        + cached_input_tokens * cached_rate
        + output_tokens * output_rate
    ) / 1_000_000
    call_rows = []
    for call in call_receipts:
        call_input = call_cached = call_output = 0
        for response in call.get("provider_responses") or []:
            usage = response["provider_usage"]
            details = usage.get("input_tokens_details", {})
            call_input += int(usage.get("input_tokens", usage.get("input")))
            call_output += int(usage.get("output_tokens", usage.get("output")))
            call_cached += int(details.get("cached_tokens", 0)) if isinstance(details, Mapping) else 0
        call_cost = (
            (call_input - call_cached) * input_rate
            + call_cached * cached_rate
            + call_output * output_rate
        ) / 1_000_000
        call_rows.append(
            {
                "role": call["role"],
                "logical_call_index": call["logical_call_index"],
                "input_tokens": call_input,
                "cached_input_tokens": call_cached,
                "output_tokens": call_output,
                "cost_usd": call_cost,
                "provider_response_ids": [
                    response["response_id"] for response in call.get("provider_responses") or []
                ],
            }
        )
    core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_USAGE_COST_V1_20260825",
        "model": MODEL,
        "logical_call_count": 2,
        "role_sequence": [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value],
        "calls": call_rows,
        "physical_provider_response_count": response_count,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": input_tokens - cached_input_tokens,
        "output_tokens": output_tokens,
        "pricing": dict(pricing),
        "total_cost_usd": cost,
        "maximum_budget_usd": float(pricing["max_budget_usd"]),
        "within_budget": cost <= float(pricing["max_budget_usd"]),
        "local_scout_invocation_fee_usd": 0,
    }
    if not core["within_budget"]:
        raise TwoFrankieBlindError("actual provider usage cost exceeds the authorized maximum budget")
    return {**core, "receipt_hash": sha256_json(core)}


def _response_id(response: Any) -> str:
    value = str(getattr(response, "id", "") or "").strip()
    if not value:
        raise TwoFrankieBlindError("provider response has no stable response ID")
    return value


def _output_items(response: Any) -> list[Any]:
    output = getattr(response, "output", None)
    if not isinstance(output, (list, tuple)):
        raise TwoFrankieBlindError("provider response output is not replayable")
    return [_jsonable(item) for item in output]


def _function_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for item in _output_items(response):
        if isinstance(item, dict) and item.get("type") == "function_call":
            arguments = item.get("arguments")
            try:
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError as exc:
                raise TwoFrankieBlindError("provider emitted invalid function arguments") from exc
            if not isinstance(parsed, dict):
                raise TwoFrankieBlindError("provider function arguments are not an object")
            calls.append({"call_id": item.get("call_id"), "name": item.get("name"), "arguments": parsed})
    return calls


def _output_text(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts: list[str] = []
    for item in _output_items(response):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if not texts:
        raise TwoFrankieBlindError("provider response contains no final text")
    return "\n".join(texts).strip()


def _estimate_tokens(instructions: str, input_value: Any, *, input_cap: int) -> dict[str, Any]:
    raw = canonical({"instructions": instructions, "input": _jsonable(input_value)}).encode()
    estimate = math.ceil(len(raw) * TOKEN_ESTIMATE_PER_BYTE)
    if estimate > input_cap:
        raise TwoFrankieBlindError(
            f"provider request estimated at {estimate} input tokens; cap is {input_cap}"
        )
    return {
        "request_bytes": len(raw),
        "estimated_input_tokens": estimate,
        "estimator_tokens_per_byte": TOKEN_ESTIMATE_PER_BYTE,
        "max_estimated_input_tokens": input_cap,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def _required_output_contract(role: str) -> dict[str, Any]:
    return {
        "schema": "FRANKIE_PRIOR_SURFACE_BLIND_FINDINGS_V1_20260825",
        "role": role,
        "as_of": {
            "event_time_cutoff_ns": "integer",
            "receive_time_cutoff_ns": "integer",
            "clock_policy": "string",
        },
        "state_summary": "open object",
        "material_omissions": [
            {"capability_or_field": "string", "availability": "string", "confidence_impact": "string"}
        ],
        "events": [
            {
                "event_id": "canonical content-derived string",
                "status": "open-world string",
                "family": "open-world string; new names allowed",
                "category": "open-world string; new names allowed",
                "depth": "open-world value or null",
                "severity": "open-world value or null",
                "novel_structure": "boolean",
                "mechanism": "string",
                "first_observed": {"ts_event_ns": "integer or null", "ts_recv_ns": "integer or null"},
                "predicted_onset_range": {
                    "start_ts_event_ns": "integer or null",
                    "end_ts_event_ns": "integer or null",
                    "start_ts_recv_ns": "integer or null",
                    "end_ts_recv_ns": "integer or null",
                },
                "event_age_elapsed_s": "number or null",
                "predicted_remaining_runway_s": "distribution/open object or null",
                "predicted_total_run_duration_s": "distribution/open object or null",
                "predicted_end_time_range": {
                    "start_ts_event_ns": "integer or null",
                    "end_ts_event_ns": "integer or null",
                    "start_ts_recv_ns": "integer or null",
                    "end_ts_recv_ns": "integer or null",
                    "event_clock_basis": "string",
                    "recv_clock_basis": "string",
                },
                "runway_regime": "open-world string; split distinct regimes rather than averaging",
                "confidence": "number in [0,1]",
                "censoring_status": "string",
                "unknown_status": "string",
                "clock_reasoning": "string",
                "evidence_refs": ["exact row/tool/source references"],
                "assumptions": ["string"],
            }
        ],
        "novel_correlations": [
            {
                "relationship_id": "string",
                "fields": ["string"],
                "lags_seconds": ["number"],
                "clock_basis": "string",
                "mechanism": "string",
                "evidence_refs": ["string"],
                "uncertainty": "string",
            }
        ],
        "runway_regimes": ["open-world objects; never collapse dispersed regimes to one mean"],
        "uncertainty": "open object",
        "first_lock": "required open object for REAL_TIME_FRANKIE; null for FORECASTER_FRANKIE",
        "frozen_rt_state": "required open object for REAL_TIME_FRANKIE; null for FORECASTER_FRANKIE",
        "additional_properties": "allowed everywhere; no fixed event/family/category/count possibilities",
    }


def _validate_findings(value: Any, role: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TwoFrankieBlindError(f"{role} output is not a JSON object")
    required = {
        "schema", "role", "as_of", "state_summary", "material_omissions", "events",
        "novel_correlations", "runway_regimes", "uncertainty", "frozen_rt_state",
        "first_lock",
    }
    missing = sorted(required - set(value))
    if missing:
        raise TwoFrankieBlindError(f"{role} output is missing fields: {missing}")
    if value.get("role") != role:
        raise TwoFrankieBlindError(f"{role} output role drift")
    as_of = value.get("as_of")
    if not isinstance(as_of, dict):
        raise TwoFrankieBlindError(f"{role} as-of receipt is not an object")
    for clock in ("event_time_cutoff_ns", "receive_time_cutoff_ns"):
        stamp = as_of.get(clock)
        if isinstance(stamp, bool) or not isinstance(stamp, int):
            raise TwoFrankieBlindError(f"{role} as-of {clock} is not an integer")
    if not isinstance(as_of.get("clock_policy"), str) or not as_of["clock_policy"].strip():
        raise TwoFrankieBlindError(f"{role} as-of clock policy is absent")
    if not isinstance(value.get("events"), list):
        raise TwoFrankieBlindError(f"{role} events must be a list")
    if not value["events"]:
        raise TwoFrankieBlindError(
            f"{role} must emit at least one explicit candidate or NO_EVENT_FOUND_YET record"
        )
    event_required = {
        "event_id", "status", "family", "category", "depth", "severity", "novel_structure",
        "mechanism", "first_observed", "predicted_onset_range", "event_age_elapsed_s",
        "predicted_remaining_runway_s", "predicted_total_run_duration_s",
        "predicted_end_time_range", "runway_regime", "confidence", "censoring_status",
        "unknown_status", "clock_reasoning", "evidence_refs", "assumptions",
    }
    for index, event in enumerate(value["events"]):
        if not isinstance(event, dict) or not event_required.issubset(event):
            raise TwoFrankieBlindError(f"{role} event {index} violates the mandatory open-world contract")
        confidence = event.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise TwoFrankieBlindError(f"{role} event {index} confidence is invalid")
        if not isinstance(event.get("evidence_refs"), list) or not isinstance(event.get("assumptions"), list):
            raise TwoFrankieBlindError(f"{role} event {index} evidence/assumptions are invalid")
    if role == FrankieRole.REAL_TIME.value and not isinstance(value.get("frozen_rt_state"), dict):
        raise TwoFrankieBlindError("Real-Time Frankie did not emit a frozen_rt_state object")
    if role == FrankieRole.REAL_TIME.value and not isinstance(value.get("first_lock"), dict):
        raise TwoFrankieBlindError("Real-Time Frankie did not emit a first_lock object")
    if role == FrankieRole.FORECASTER.value and value.get("first_lock") is not None:
        raise TwoFrankieBlindError("Forecaster Frankie may not create or replace the RT first lock")
    return value


def _validate_causal_cutoff(
    findings: Mapping[str, Any], role: str, source_manifest: Mapping[str, Any]
) -> None:
    """Fail closed if a blind finding claims evidence beyond the supplied tape."""
    as_of = findings["as_of"]
    event_cutoff = int(as_of["event_time_cutoff_ns"])
    recv_cutoff = int(as_of["receive_time_cutoff_ns"])
    event_floor = int(source_manifest["first_event_second"]) * 1_000_000_000
    event_ceiling = (int(source_manifest["last_event_second"]) + 1) * 1_000_000_000
    recv_ceiling = int(source_manifest["max_contributing_ts_recv_ns"])
    if not event_floor <= event_cutoff <= event_ceiling:
        raise TwoFrankieBlindError(f"{role} event-clock as-of exceeds supplied evidence")
    if not event_floor <= recv_cutoff <= recv_ceiling:
        raise TwoFrankieBlindError(f"{role} receive-clock as-of exceeds supplied evidence")
    for index, event in enumerate(findings["events"]):
        first = event.get("first_observed")
        if not isinstance(first, Mapping):
            raise TwoFrankieBlindError(f"{role} event {index} first_observed is invalid")
        for key, ceiling in (("ts_event_ns", event_cutoff), ("ts_recv_ns", recv_cutoff)):
            stamp = first.get(key)
            if stamp is not None and (
                isinstance(stamp, bool) or not isinstance(stamp, int) or stamp > ceiling
            ):
                raise TwoFrankieBlindError(
                    f"{role} event {index} first_observed {key} exceeds its causal cutoff"
                )


def _blind_runway_predictions(findings: Mapping[str, Any]) -> list[dict[str, Any]]:
    as_of = findings["as_of"]
    return [
        {
            "event_id": event["event_id"],
            "family": event["family"],
            "category": event["category"],
            "elapsed_age": event["event_age_elapsed_s"],
            "remaining_runway": event["predicted_remaining_runway_s"],
            "total_run_duration": event["predicted_total_run_duration_s"],
            "end_time_range": event["predicted_end_time_range"],
            "as_of_event_clock": as_of.get("event_time_cutoff_ns"),
            "as_of_receive_clock": as_of.get("receive_time_cutoff_ns"),
            "confidence": event["confidence"],
            "censoring_status": event["censoring_status"],
            "unknown_fields": event["unknown_status"],
            "evidence_refs": event["evidence_refs"],
            "assumptions": event["assumptions"],
            "aggregation_policy": "RAW_OR_RANGE_NO_AVERAGING",
            "category_policy": "OPEN_WORLD_NO_OLD_CATEGORY_CONSTRAINT",
        }
        for event in findings["events"]
    ]


def _bind_accepted_findings(call_receipt: Mapping[str, Any], findings: Mapping[str, Any]) -> dict[str, Any]:
    core = dict(call_receipt)
    core.pop("receipt_hash", None)
    core["accepted_findings_hash"] = sha256_json(findings)
    core["accepted_findings"] = dict(findings)
    return {**core, "receipt_hash": sha256_json(core)}


class PriorSurfaceTools:
    def __init__(self, rows: Sequence[Mapping[str, Any]], capabilities: Mapping[str, Any]) -> None:
        self.rows = list(rows)
        self.capabilities = list(capabilities["leaf_items"])

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function", "name": "rt_evidence_scout",
                "description": (
                    "Optional deterministic, read-only scout over the exact prior reduced/non-full-MBO "
                    "Oct-4/5 surface. Call only when you decide more evidence is material. It has no "
                    "model/provider subcall, file, shell, network, probability, or lock authority."
                ),
                "strict": True,
                "parameters": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "state_window", "event_range", "field_history",
                                "search_correlations", "capability_lookup",
                            ],
                        },
                        "clock": {"type": ["string", "null"], "enum": ["ts_event", "ts_recv", None]},
                        "start_ns": {"type": ["integer", "null"]},
                        "end_ns_exclusive": {"type": ["integer", "null"]},
                        "field": {"type": ["string", "null"]},
                        "x_field": {"type": ["string", "null"]},
                        "y_field": {"type": ["string", "null"]},
                        "lag_seconds": {"type": ["integer", "null"], "minimum": -3600, "maximum": 3600},
                        "query": {"type": ["string", "null"]},
                        "reverse": {"type": "boolean"},
                        "cursor": {"type": "integer", "minimum": 0},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_WINDOW_ROWS}
                    },
                    "required": [
                        "action", "clock", "start_ns", "end_ns_exclusive", "field",
                        "x_field", "y_field", "lag_seconds", "query", "reverse", "cursor", "limit"
                    ],
                },
            },
        ]

    def execute(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name != "rt_evidence_scout":
            raise TwoFrankieBlindError(f"unsupported Real-Time tool namespace: {name}")
        action = arguments.get("action")
        if action in {"state_window", "event_range"}:
            return self._window(arguments)
        if action == "field_history":
            return self._field_history(arguments)
        if action == "search_correlations":
            return self._correlation(arguments)
        if action == "capability_lookup":
            return self._capability(arguments)
        raise TwoFrankieBlindError(f"unsupported rt_evidence_scout action: {action}")

    def _window(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        clock = arguments.get("clock")
        start = arguments.get("start_ns")
        end = arguments.get("end_ns_exclusive")
        cursor = arguments.get("cursor")
        limit = arguments.get("limit")
        if clock not in {"ts_event", "ts_recv"} or any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end, cursor, limit)):
            raise TwoFrankieBlindError("prior_surface_window arguments are invalid")
        if end <= start or not 0 <= cursor or not 1 <= limit <= MAX_WINDOW_ROWS:
            raise TwoFrankieBlindError("prior_surface_window range/page is invalid")
        def stamp(row: Mapping[str, Any]) -> int:
            return int(row["epoch_second"]) * 1_000_000_000 if clock == "ts_event" else int(row["last_ts_recv_ns"])
        matches = [row for row in self.rows if start <= stamp(row) < end]
        if arguments.get("reverse") is True:
            matches.reverse()
        page = matches[cursor:cursor + limit]
        while page and len(canonical(page).encode()) > MAX_TOOL_RESULT_BYTES - 8_192:
            page = page[:-1]
        if not page and cursor < len(matches):
            raise TwoFrankieBlindError("one prior-surface row exceeds the scout page byte cap")
        next_cursor = cursor + len(page)
        if next_cursor >= len(matches):
            next_cursor = None
        core = {
            "clock": clock, "start_ns": start, "end_ns_exclusive": end,
            "cursor": cursor, "next_cursor": next_cursor, "total_matches": len(matches),
            "requested_limit": limit, "returned_rows": len(page),
            "page_byte_cap": MAX_TOOL_RESULT_BYTES,
            "rows": page,
        }
        return {**core, "result_hash": sha256_json(core)}

    def _field_history(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        field = str(arguments.get("field") or "")
        if not field:
            raise TwoFrankieBlindError("field_history requires a field")
        window = self._window(arguments)
        rows = window.pop("rows")
        values = [
            {
                "epoch_second": row["epoch_second"],
                "last_ts_recv_ns": row["last_ts_recv_ns"],
                "value": _flatten_numeric(row, field),
                "source_dbn_sha256": row["source_dbn_sha256"],
            }
            for row in rows
        ]
        core = {**window, "field": field, "values": values}
        return {**core, "result_hash": sha256_json(core)}

    def _correlation(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        x_field = str(arguments.get("x_field") or "")
        y_field = str(arguments.get("y_field") or "")
        lag = arguments.get("lag_seconds")
        if not x_field or not y_field or isinstance(lag, bool) or not isinstance(lag, int) or abs(lag) > 3600:
            raise TwoFrankieBlindError("prior_surface_correlation arguments are invalid")
        by_second = {int(row["epoch_second"]): row for row in self.rows}
        pairs: list[tuple[float, float, int, int]] = []
        for second, row in by_second.items():
            other = by_second.get(second + lag)
            x = _flatten_numeric(row, x_field)
            y = None if other is None else _flatten_numeric(other, y_field)
            if x is not None and y is not None:
                pairs.append((x, y, second, second + lag))
        xs = [item[0] for item in pairs]
        ys = [item[1] for item in pairs]
        if len(pairs) >= 2 and statistics.pstdev(xs) > 0 and statistics.pstdev(ys) > 0:
            correlation = statistics.correlation(xs, ys)
        else:
            correlation = None
        refs = [{"x_event_second": p[2], "y_event_second": p[3]} for p in pairs]
        core = {
            "x_field": x_field, "y_field": y_field, "lag_seconds": lag,
            "n": len(pairs), "pearson": correlation,
            "x_distribution_not_mean_only": _distribution(xs),
            "y_distribution_not_mean_only": _distribution(ys),
            "raw_pair_clock_refs_hash": sha256_json(refs),
            "raw_pair_clock_refs_first": refs[:20], "raw_pair_clock_refs_last": refs[-20:],
            "clock_policy": "x at event second t; y at event second t+lag; no receive-clock substitution",
        }
        return {**core, "result_hash": sha256_json(core)}

    def _capability(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "").casefold()
        cursor = arguments.get("cursor")
        limit = arguments.get("limit")
        if len(query) > 256 or isinstance(cursor, bool) or not isinstance(cursor, int) or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise TwoFrankieBlindError("capability_lookup arguments are invalid")
        matches = [item for item in self.capabilities if query in str(item["path"]).casefold()]
        page = matches[cursor:cursor + limit]
        next_cursor = cursor + len(page)
        if next_cursor >= len(matches):
            next_cursor = None
        core = {"query": query, "cursor": cursor, "next_cursor": next_cursor, "total_matches": len(matches), "items": page}
        return {**core, "result_hash": sha256_json(core)}


def _create_client() -> Any:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise TwoFrankieBlindError("OpenAI SDK is unavailable") from exc
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MARKETS_OPENAI_API_KEY")
    if not api_key:
        raise TwoFrankieBlindError("OpenAI credential is unavailable")
    return OpenAI(api_key=api_key)


def _provider_call(
    client: Any,
    *,
    role: str,
    logical_call_index: int,
    instructions: str,
    payload: Mapping[str, Any],
    tools: PriorSurfaceTools | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    conversation: list[Any] = [{"role": "user", "content": canonical(payload)}]
    responses: list[dict[str, Any]] = []
    tool_receipts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    cumulative_estimated_input_tokens = 0
    cumulative_reported_input_tokens = 0
    for round_index in range(MAX_RT_TOOL_ROUNDS + 1):
        input_cap = (
            (RT_DIRECT_INPUT_TOKEN_CAP if round_index == 0 else RT_CUMULATIVE_INPUT_TOKEN_CAP)
            if role == FrankieRole.REAL_TIME.value
            else FORECASTER_INPUT_TOKEN_CAP
        )
        budget = _estimate_tokens(instructions, conversation, input_cap=input_cap)
        cumulative_estimated_input_tokens += int(budget["estimated_input_tokens"])
        if (
            role == FrankieRole.REAL_TIME.value
            and cumulative_estimated_input_tokens > RT_CUMULATIVE_INPUT_TOKEN_CAP
        ):
            raise TwoFrankieBlindError("Real-Time cumulative estimated input token cap exceeded")
        kwargs: dict[str, Any] = {
            "model": MODEL,
            "instructions": instructions,
            "input": conversation,
            "store": False,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        if tools is not None:
            kwargs["tools"] = tools.definitions
            kwargs["parallel_tool_calls"] = False
        response = client.responses.create(**kwargs)
        resolved_model = str(getattr(response, "model", "") or "")
        if resolved_model != MODEL:
            raise TwoFrankieBlindError(
                f"provider resolved model {resolved_model!r}; exact required model is {MODEL!r}"
            )
        response_id = _response_id(response)
        if response_id in seen_ids:
            raise TwoFrankieBlindError("provider reused a response ID")
        seen_ids.add(response_id)
        responses.append(
            {
                "response_id": response_id,
                "requested_model": MODEL,
                "resolved_model": resolved_model,
                "request_budget": budget,
                **_usage(response),
            }
        )
        usage = responses[-1]["provider_usage"]
        reported_input = usage.get("input_tokens", usage.get("input", 0)) if isinstance(usage, Mapping) else 0
        if isinstance(reported_input, int) and not isinstance(reported_input, bool):
            cumulative_reported_input_tokens += reported_input
        if (
            role == FrankieRole.REAL_TIME.value
            and cumulative_reported_input_tokens > RT_CUMULATIVE_INPUT_TOKEN_CAP
        ):
            raise TwoFrankieBlindError("Real-Time cumulative provider-reported input token cap exceeded")
        calls = _function_calls(response)
        if not calls:
            try:
                parsed = json.loads(_output_text(response))
            except json.JSONDecodeError as exc:
                raise TwoFrankieBlindError(f"{role} did not return one JSON object") from exc
            findings = _validate_findings(parsed, role)
            logical = {
                "role": role,
                "model": MODEL,
                "resolved_model": resolved_model,
                "store": False,
                "logical_call_index": logical_call_index,
                "logical_call_count": 1,
                "provider_response_id": response_id,
                "automatic_helper_calls": 0,
                "automatic_scout_calls": 0,
                "model_requested_local_scout_invocations": len(tool_receipts),
                "physical_responses_requests": len(responses),
                "provider_responses": responses,
                "tool_receipts": tool_receipts,
                "tool_round_count": len(tool_receipts),
                "max_tool_rounds": MAX_RT_TOOL_ROUNDS if tools is not None else 0,
                "cumulative_estimated_input_tokens": cumulative_estimated_input_tokens,
                "cumulative_provider_reported_input_tokens": cumulative_reported_input_tokens,
                "no_retry": True,
                "no_fallback_model": True,
                "receipt_hash": "",
            }
            logical["receipt_hash"] = sha256_json({key: value for key, value in logical.items() if key != "receipt_hash"})
            return findings, logical
        if tools is None:
            raise TwoFrankieBlindError("Forecaster attempted an unauthorized tool call")
        if len(calls) != 1:
            raise TwoFrankieBlindError("Real-Time Frankie must issue at most one sequential tool call per round")
        if round_index >= MAX_RT_TOOL_ROUNDS:
            raise TwoFrankieBlindError("Real-Time Frankie exhausted the bounded tool round budget")
        call = calls[0]
        call_id = str(call.get("call_id") or "")
        name = str(call.get("name") or "")
        if not call_id or not name:
            raise TwoFrankieBlindError("provider function call identity is absent")
        result = tools.execute(name, call["arguments"])
        output_json = canonical(result)
        if len(output_json.encode()) > MAX_TOOL_RESULT_BYTES:
            raise TwoFrankieBlindError("provider tool result exceeds the fixed byte cap")
        tool_receipts.append(
            {
                "call_id": call_id,
                "tool_name": name,
                "arguments_hash": sha256_json(call["arguments"]),
                "result_hash": sha256_json(result),
                "result_bytes": len(output_json.encode()),
            }
        )
        conversation.extend(_output_items(response))
        conversation.append({"type": "function_call_output", "call_id": call_id, "output": output_json})
    raise TwoFrankieBlindError("provider loop did not terminate")


def _instructions(role: FrankieRole, mission_path: Path) -> str:
    role_mission = mission_path.read_text(encoding="utf-8")
    authority = (
        "You are Real-Time Frankie. You own current causal reality and the first lock. "
        "Use exact available evidence and freeze a versioned RT state for Forecaster."
        if role is FrankieRole.REAL_TIME
        else
        "You are Forecaster Frankie. Consume the frozen RT state as authoritative current reality. "
        "Do not reconstruct a competing current state. Produce advisory forward timing and distributions."
    )
    return "\n\n".join(
        [
            authority,
            COMMON_MISSION,
            role_mission,
            (
                "STRICT BLIND FIREWALL: Step-1 event/family/depth structures, populations, crosswalks, "
                "self-fit results, realized runway/outcomes, 54-week answers, and any post-reveal analysis "
                "are absent and forbidden. Never infer their contents from filenames, counts, or expectations."
            ),
            (
                "The full 1,940-leaf/46-block registry is preserved. Oct-2021 availability is separate. "
                "UNAVAILABLE, UNKNOWN, or DORMANT means not supplied/not proven, never false or zero. "
                "Enumerate material omissions and confidence impact; never fabricate or substitute."
            ),
            (
                "Outputs are open-world: any number of events, families, categories, mechanisms, and runway "
                "regimes may be created. No prior count/name/match is expected or required. Do not average "
                "distinct regimes. Preserve event and receive clocks and exact evidence references. If no "
                "positive event is supported, emit one explicit NO_EVENT_FOUND_YET candidate with null/unknown "
                "runway fields and searched-coverage evidence instead of returning an empty event list."
            ),
            "Return exactly one JSON object matching the supplied mandatory/open-world output contract.",
        ]
    )


def _atomic_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(raw)


def run(seconds_path: Path, output_root: Path, run_id: str) -> dict[str, Any]:
    _blind_path_check(seconds_path)
    if not run_id.strip():
        raise TwoFrankieBlindError("run-id is required")
    controls = _validate_control_files()
    launch_control = controls["launch_control"]
    overlay = read_json(CAPABILITY_OVERLAY)
    pricing = launch_control["pricing"]
    conservative_cost_ceiling = (
        launch_control["token_caps"]["combined_conservative_input"]
        * float(pricing["input_usd_per_million"])
        + launch_control["token_caps"]["combined_conservative_output"]
        * float(pricing["output_usd_per_million"])
    ) / 1_000_000
    if conservative_cost_ceiling > float(pricing["max_budget_usd"]):
        raise TwoFrankieBlindError("conservative two-call token cost exceeds the authorized budget")
    october_receipt = _validate_october_child(seconds_path)
    rows, source_manifest = load_prior_surface(seconds_path)
    day_context = build_day_context(rows, source_manifest)

    rt_context = build_role_context_payload(REPO_ROOT, FrankieRole.REAL_TIME)
    fc_context = build_role_context_payload(REPO_ROOT, FrankieRole.FORECASTER)
    rt_availability = _capability_availability(rt_context, overlay)
    fc_availability = _capability_availability(fc_context, overlay)
    rt_provider_context = _compact_role_context(rt_context)
    fc_provider_context = _compact_role_context(fc_context)
    _blind_object_check(day_context)

    output_root.mkdir(parents=True, exist_ok=False)
    preflight_core = {
        "schema": SCHEMA,
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "status": "PREFLIGHT_PASS_PROVIDER_NOT_CALLED",
        "provider_called": False,
        "run_id": run_id,
        "model": MODEL,
        "logical_call_plan": [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value],
        "logical_call_count": 2,
        "helpers_auto_called": False,
        "specialists_auto_called": False,
        "optional_rt_scout_installed": True,
        "optional_rt_scout_authorized_or_auto_called": False,
        "automatic_scout": False,
        "target_window": source_manifest["window"],
        "source_manifest": source_manifest,
        "source_receipt_sha256": EXPECTED_RECEIPT_SHA256,
        "source_receipt_file_sha256": EXPECTED_RECEIPT_FILE_SHA256,
        "source_child_status": october_receipt.get("status"),
        "control_files": controls["controls"],
        "implementation_commit": controls["implementation_commit"],
        "authorization_commit": controls["authorization_commit"],
        "common_mission_sha256": hashlib.sha256(COMMON_MISSION.encode()).hexdigest(),
        "mission_sha256": _mission_binding_hash(),
        "rt_role_build_hash": rt_context["role_build_hash"],
        "forecaster_role_build_hash": fc_context["role_build_hash"],
        "rt_capability_availability_receipt_hash": rt_availability["receipt_hash"],
        "forecaster_capability_availability_receipt_hash": fc_availability["receipt_hash"],
        "bigsuite_leaf_count": EXPECTED_BIGSUITE_LEAVES,
        "bigsuite_block_count": EXPECTED_BIGSUITE_BLOCKS,
        "answer_key_or_step1_results_exposed": False,
        "blind_firewall": {
            "prior_seconds_row_schema_allowlisted": True,
            "step1_population_crosswalk_self_fit_outcomes_forbidden": True,
            "54_week_answer_population_forbidden": True,
        },
        "token_caps": {
            "estimator_tokens_per_byte": TOKEN_ESTIMATE_PER_BYTE,
            "rt_direct_input_tokens": RT_DIRECT_INPUT_TOKEN_CAP,
            "rt_cumulative_input_tokens": RT_CUMULATIVE_INPUT_TOKEN_CAP,
            "forecaster_input_tokens": FORECASTER_INPUT_TOKEN_CAP,
            "max_output_tokens_per_physical_request": MAX_OUTPUT_TOKENS,
            "max_rt_tool_rounds": MAX_RT_TOOL_ROUNDS,
            "max_tool_result_bytes": MAX_TOOL_RESULT_BYTES,
        },
        "pricing": pricing,
        "conservative_cost_ceiling_usd": conservative_cost_ceiling,
        "authorized_max_budget_usd": pricing["max_budget_usd"],
    }
    preflight = {**preflight_core, "receipt_hash": sha256_json(preflight_core)}
    _atomic_json(output_root / "PREFLIGHT.json", preflight)
    source_verify = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_SOURCE_VERIFY_V1_20260825",
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "bytes": EXPECTED_SECONDS_BYTES,
        "sha256": EXPECTED_SECONDS_SHA256,
        "window_start": TARGET_START_ISO,
        "window_end_exclusive": TARGET_END_EXCLUSIVE_ISO,
        "receipt_file_sha256": EXPECTED_RECEIPT_FILE_SHA256,
        "receipt_canonical_sha256": EXPECTED_RECEIPT_SHA256,
        "source_control_sha256": controls["source_control_hash"],
        "verified": True,
    }
    source_verify["receipt_hash"] = sha256_json(source_verify)
    _atomic_json(output_root / "SOURCE_VERIFY.json", source_verify)
    _atomic_json(output_root / "SLICE_MANIFEST.json", source_manifest)
    answer_wall_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_ANSWER_WALL_V1_20260825",
        "answer_key_or_step1_results_exposed": False,
        "step1_answer_key_exposed": False,
        "comparison_accessed": False,
        "answer_key_release_authorized": False,
        "allowed_surface": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "forbidden_classes": list(FORBIDDEN_INPUT_PATH_FRAGMENTS),
        "54_week_answer_population_exposed": False,
        "step1_answer_clocks_exposed": False,
    }
    _atomic_json(
        output_root / "ANSWER_WALL.json",
        {**answer_wall_core, "receipt_hash": sha256_json(answer_wall_core)},
    )
    capability_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_DUAL_ROLE_CAPABILITY_RECONCILIATION_V1_20260825",
        "overlay_sha256": controls["overlay_control_hash"],
        "REAL_TIME_FRANKIE": rt_availability,
        "FORECASTER_FRANKIE": fc_availability,
        "leaf_items": rt_availability["leaf_items"],
        "block_items": rt_availability["block_items"],
        "surface_items": rt_availability["surface_items"],
        "leaf_count": EXPECTED_BIGSUITE_LEAVES,
        "block_count": EXPECTED_BIGSUITE_BLOCKS,
        "surface_count": 24,
        "zero_silent_omissions": True,
        "duplicate_leaf_count": 0,
        "unregistered_leaf_count": 0,
        "silently_omitted_leaf_count": 0,
        "installed_executable_tools_reconciled": True,
    }
    _atomic_json(
        output_root / "CAPABILITY_RECONCILIATION.json",
        {**capability_core, "receipt_hash": sha256_json(capability_core)},
    )

    client = _create_client()
    rt_tools = PriorSurfaceTools(rows, rt_availability)
    rt_payload = {
        "schema": SCHEMA,
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "role": FrankieRole.REAL_TIME.value,
        "mission": COMMON_MISSION,
        "source_manifest": source_manifest,
        "direct_day_specific_context": day_context,
        "role_context": rt_provider_context,
        "capability_availability_summary": {
            "receipt_hash": rt_availability["receipt_hash"],
            "leaf_count": EXPECTED_BIGSUITE_LEAVES,
            "block_count": EXPECTED_BIGSUITE_BLOCKS,
            "full_receipt_route": "rt_evidence_scout.capability_lookup",
        },
        "required_output_contract": _required_output_contract(FrankieRole.REAL_TIME.value),
        "answer_key_present": False,
    }
    rt_payload_sha256 = sha256_json(rt_payload)
    rt_findings, rt_call = _provider_call(
        client,
        role=FrankieRole.REAL_TIME.value,
        logical_call_index=1,
        instructions=_instructions(FrankieRole.REAL_TIME, RT_MISSION_PATH),
        payload=rt_payload,
        tools=rt_tools,
    )
    _validate_causal_cutoff(rt_findings, FrankieRole.REAL_TIME.value, source_manifest)
    rt_call = _bind_accepted_findings(rt_call, rt_findings)
    rt_findings_hash = sha256_json(rt_findings)
    frozen_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FROZEN_RT_STATE_V1_20260825",
        "role": FrankieRole.REAL_TIME.value,
        "source_manifest_hash": source_manifest["manifest_hash"],
        "role_build_hash": rt_context["role_build_hash"],
        "provider_findings_hash": rt_findings_hash,
        "state": rt_findings["frozen_rt_state"],
        "as_of": rt_findings["as_of"],
    }
    frozen_rt = {**frozen_core, "frozen_rt_state_hash": sha256_json(frozen_core)}
    rt_context_manifest_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_RT_CONTEXT_MANIFEST_V1_20260825",
        "role": FrankieRole.REAL_TIME.value,
        "mission_sha256": _mission_binding_hash(),
        "role_build_hash": rt_context["role_build_hash"],
        "source_manifest_hash": source_manifest["manifest_hash"],
        "day_context_hash": day_context["context_hash"],
        "capability_receipt_hash": rt_availability["receipt_hash"],
        "answer_wall": "SEALED",
        "step1_answer_key_exposed": False,
        "forbidden_information_matches": [],
        "automatic_helpers": False,
        "automatic_scout": False,
        "provider_bound_payload_sha256": rt_payload_sha256,
    }
    _atomic_json(
        output_root / "RT_CONTEXT_MANIFEST.json",
        {**rt_context_manifest_core, "receipt_hash": sha256_json(rt_context_manifest_core)},
    )
    _atomic_json(output_root / "RT_PROVIDER_RECEIPT.json", rt_call)
    rt_lock_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_RT_FIRST_LOCK_V1_20260825",
        "rt_findings_hash": rt_findings_hash,
        "first_lock": rt_findings["first_lock"],
        "first_lock_owner": FrankieRole.REAL_TIME.value,
        "blind_runway_predictions": _blind_runway_predictions(rt_findings),
    }
    _atomic_json(
        output_root / "RT_FIRST_LOCK.json",
        {**rt_lock_core, "receipt_hash": sha256_json(rt_lock_core)},
    )
    _atomic_json(output_root / "RT_FROZEN_STATE.json", frozen_rt)
    handoff_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_ONEWAY_HANDOFF_V1_20260825",
        "from_role": FrankieRole.REAL_TIME.value,
        "to_role": FrankieRole.FORECASTER.value,
        "frozen_rt_state_hash": frozen_rt["frozen_rt_state_hash"],
        "forecaster_may_modify_rt_state": False,
        "forecaster_may_reconstruct_competing_current_state": False,
        "rt_frozen_before_forecaster": True,
    }
    _atomic_json(
        output_root / "ONEWAY_HANDOFF.json",
        {**handoff_core, "receipt_hash": sha256_json(handoff_core)},
    )

    fc_payload = {
        "schema": SCHEMA,
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "role": FrankieRole.FORECASTER.value,
        "mission": COMMON_MISSION,
        "authoritative_frozen_rt_state": frozen_rt,
        "direct_day_specific_context": day_context,
        "source_manifest": source_manifest,
        "role_context": fc_provider_context,
        "capability_availability_summary": {
            "receipt_hash": fc_availability["receipt_hash"],
            "leaf_count": EXPECTED_BIGSUITE_LEAVES,
            "block_count": EXPECTED_BIGSUITE_BLOCKS,
        },
        "required_output_contract": _required_output_contract(FrankieRole.FORECASTER.value),
        "answer_key_present": False,
        "current_reconstruction_authority": "DENIED_USE_FROZEN_RT_STATE",
    }
    fc_payload_sha256 = sha256_json(fc_payload)
    fc_findings, fc_call = _provider_call(
        client,
        role=FrankieRole.FORECASTER.value,
        logical_call_index=2,
        instructions=_instructions(FrankieRole.FORECASTER, FORECASTER_MISSION_PATH),
        payload=fc_payload,
        tools=None,
    )
    _validate_causal_cutoff(fc_findings, FrankieRole.FORECASTER.value, source_manifest)
    fc_call = _bind_accepted_findings(fc_call, fc_findings)
    fc_context_manifest_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FORECASTER_CONTEXT_MANIFEST_V1_20260825",
        "role": FrankieRole.FORECASTER.value,
        "mission_sha256": _mission_binding_hash(),
        "role_build_hash": fc_context["role_build_hash"],
        "frozen_rt_state_hash": frozen_rt["frozen_rt_state_hash"],
        "day_context_hash": day_context["context_hash"],
        "capability_receipt_hash": fc_availability["receipt_hash"],
        "answer_wall": "SEALED",
        "step1_answer_key_exposed": False,
        "forbidden_information_matches": [],
        "automatic_helpers": False,
        "automatic_scout": False,
        "provider_bound_payload_sha256": fc_payload_sha256,
    }
    _atomic_json(
        output_root / "FORECASTER_CONTEXT_MANIFEST.json",
        {**fc_context_manifest_core, "receipt_hash": sha256_json(fc_context_manifest_core)},
    )
    _atomic_json(output_root / "FORECASTER_PROVIDER_RECEIPT.json", fc_call)
    fc_lock_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FORECASTER_FIRST_LOCK_V1_20260825",
        "lock_type": "ADVISORY_FORECAST_LOCK_DOES_NOT_MUTATE_RT_FIRST_LOCK",
        "forecaster_findings_hash": sha256_json(fc_findings),
        "frozen_rt_state_hash": frozen_rt["frozen_rt_state_hash"],
        "blind_runway_predictions": _blind_runway_predictions(fc_findings),
    }
    _atomic_json(
        output_root / "FORECASTER_FIRST_LOCK.json",
        {**fc_lock_core, "receipt_hash": sha256_json(fc_lock_core)},
    )
    usage_cost = _usage_cost([rt_call, fc_call], pricing)
    _atomic_json(output_root / "USAGE_COST.json", usage_cost)

    final_core = {
        "schema": SCHEMA,
        "status": "TWO_FRANKIES_COMPLETE_BLIND",
        "model": MODEL,
        "logical_provider_call_count": 2,
        "logical_call_order": [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value],
        "physical_provider_request_count": (
            rt_call["physical_responses_requests"] + fc_call["physical_responses_requests"]
        ),
        "rt_call_receipt_hash": rt_call["receipt_hash"],
        "forecaster_call_receipt_hash": fc_call["receipt_hash"],
        "rt_findings_hash": rt_findings_hash,
        "frozen_rt_state_hash": frozen_rt["frozen_rt_state_hash"],
        "forecaster_findings_hash": sha256_json(fc_findings),
        "source_manifest_hash": source_manifest["manifest_hash"],
        "answer_key_or_step1_results_exposed": False,
        "helper_specialist_provider_calls": 0,
        "automatic_scout_calls": 0,
        "model_requested_local_rt_scout_invocations": rt_call[
            "model_requested_local_scout_invocations"
        ],
        "usage_cost_receipt_hash": usage_cost["receipt_hash"],
        "cost_usd": usage_cost["total_cost_usd"],
        "within_authorized_budget": usage_cost["within_budget"],
    }
    final = {**final_core, "receipt_hash": sha256_json(final_core)}
    artifact_rows = []
    for path in sorted(output_root.iterdir()):
        if path.is_file():
            artifact_rows.append(
                {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            )
    artifact_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_ARTIFACT_MANIFEST_V1_20260825",
        "artifacts": artifact_rows,
    }
    artifact_manifest = {**artifact_core, "receipt_hash": sha256_json(artifact_core)}
    _atomic_json(output_root / "ARTIFACT_MANIFEST.json", artifact_manifest)
    complete_core = {
        **final_core,
        "status": "COMPLETE",
        "artifact_manifest_receipt_hash": artifact_manifest["receipt_hash"],
        "published_last": True,
    }
    final = {**complete_core, "receipt_hash": sha256_json(complete_core)}
    _atomic_json(output_root / "COMPLETE.json", final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--capability-overlay", required=True, type=Path)
    parser.add_argument("--rt-mission", required=True, type=Path)
    parser.add_argument("--forecaster-mission", required=True, type=Path)
    parser.add_argument("--launch-control", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        supplied_controls = {
            args.source_config.resolve(): SOURCE_CONTROL.resolve(),
            args.capability_overlay.resolve(): CAPABILITY_OVERLAY.resolve(),
            args.rt_mission.resolve(): RT_MISSION_PATH.resolve(),
            args.forecaster_mission.resolve(): FORECASTER_MISSION_PATH.resolve(),
            args.launch_control.resolve(): LAUNCH_CONTROL.resolve(),
        }
        if any(actual != expected for actual, expected in supplied_controls.items()):
            raise TwoFrankieBlindError("CLI control path differs from the exact run-specific clone")
        result = run(args.source, args.output_root, args.run_id)
    except Exception as exc:
        print(f"TWO_FRANKIES_STOP={type(exc).__name__}:{exc}", file=sys.stderr)
        return 2
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
