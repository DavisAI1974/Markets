#!/usr/bin/env python3
"""Freeze sequential Work-mode Frankie outputs without provider/API receipts."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tarfile
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.kalshi import (  # noqa: E402
    ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825 as prior,
)
from research.kalshi.frankie_role_context_profiles_20260824 import FrankieRole  # noqa: E402


RT_REQUIRED = {
    "schema", "role", "as_of", "state_summary", "material_omissions",
    "exhaustion_events", "observed_correlations", "direction_and_direction_change",
    "bounded_lookahead", "strategy_hypotheses", "uncertainty", "first_lock",
    "frozen_rt_state", "study_design", "scout_usage",
}
RT_EVENT_REQUIRED = {
    "event_id", "status", "family", "category", "depth", "severity",
    "novel_structure", "mechanism", "searched_interval",
    "earliest_lawful_precursor", "pre_birth_conditions",
    "first_observed_deviation", "observed_onset", "observed_transitions",
    "observed_peak_or_inflection", "clock_ledger", "prebirth_detectability",
    "detection_latency_s", "observed_dipole_runway", "observed_elapsed_age_s",
    "observed_duration_so_far_s", "estimated_total_exhaustion_duration_s",
    "estimated_remaining_exhaustion_duration_s", "observed_end_or_open_status",
    "contradictions", "confidence", "censoring_status", "unknown_status",
    "clock_reasoning", "evidence_refs", "assumptions",
}
FC_REQUIRED = {
    "schema", "role", "as_of", "state_summary", "material_omissions", "events",
    "novel_correlations", "runway_regimes", "uncertainty", "frozen_rt_state",
    "first_lock", "rt_state_sha256", "forecast_curve",
    "forward_exhaustion_correlations", "dipole_scenarios",
    "novel_correlation_search_coverage", "helper_usage", "knowledge_usage",
}
TOKEN_ESTIMATE_PER_BYTE = 0.285
MAX_OUTPUT_TOKENS = 12_000
MAX_OUTPUT_BYTES = int(MAX_OUTPUT_TOKENS / TOKEN_ESTIMATE_PER_BYTE)
HELPER_INPUT_TOKEN_CAP = 48_000
HELPER_OUTPUT_TOKEN_CAP = 6_000
HELPER_INPUT_BYTE_CAP = int(HELPER_INPUT_TOKEN_CAP / TOKEN_ESTIMATE_PER_BYTE)
HELPER_OUTPUT_BYTE_CAP = int(HELPER_OUTPUT_TOKEN_CAP / TOKEN_ESTIMATE_PER_BYTE)
FORECASTER_INPUT_TOKEN_CAP = 150_000
RT_CUMULATIVE_INPUT_TOKEN_CAP = 96_000
RT_SCOUT_ADDITIONAL_INPUT_TOKEN_CAP = 48_000
RT_SCOUT_ADDITIONAL_INPUT_BYTE_CAP = int(
    RT_SCOUT_ADDITIONAL_INPUT_TOKEN_CAP / TOKEN_ESTIMATE_PER_BYTE
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


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
        raise prior.TwoFrankieBlindError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise prior.TwoFrankieBlindError(f"JSON artifact is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(raw)


def copy_exact_exclusive(source: Path, destination: Path) -> None:
    raw = source.read_bytes()
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def resolve_field_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise prior.TwoFrankieBlindError(f"scout requested unavailable field path: {path}")
        current = current[part]
    return current


def verify_self_hash(value: Mapping[str, Any], field: str = "receipt_hash") -> None:
    observed = value.get(field)
    core = dict(value)
    core.pop(field, None)
    if not isinstance(observed, str) or observed != sha256_json(core):
        raise prior.TwoFrankieBlindError(f"artifact {field} does not bind its content")


def verify_outer_packet(
    packet_root: Path, archive: Path, checksum: Path, stage_identity_path: Path,
    expected_implementation_commit: str, expected_authorization_commit: str,
    expected_launch_commit: str, expected_launch_identity: str,
) -> None:
    for commit in (
        expected_implementation_commit, expected_authorization_commit, expected_launch_commit
    ):
        if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
            raise prior.TwoFrankieBlindError("expected commit identity is malformed")
    checksum_parts = checksum.read_text(encoding="utf-8").strip().split()
    if len(checksum_parts) != 2 or Path(checksum_parts[1].lstrip("*")).name != archive.name:
        raise prior.TwoFrankieBlindError("outer packet checksum receipt is malformed")
    archive_hash = sha256_file(archive)
    if checksum_parts[0] != archive_hash:
        raise prior.TwoFrankieBlindError("outer packet archive SHA-256 drift")
    identity = read_json(stage_identity_path)
    if identity.get("schema") != "FRANKIE_KEYLESS_PACKET_STAGE_IDENTITY_V2_20260825":
        raise prior.TwoFrankieBlindError("outer packet stage identity schema drift")
    verify_self_hash(identity)
    if identity.get("source_commit") != expected_launch_commit:
        raise prior.TwoFrankieBlindError("outer packet source/launch commit drift")
    if identity.get("implementation_commit") != expected_implementation_commit:
        raise prior.TwoFrankieBlindError("outer packet implementation commit drift")
    if identity.get("authorization_commit") != expected_authorization_commit:
        raise prior.TwoFrankieBlindError("outer packet authorization commit drift")
    if identity.get("launch_commit") != expected_launch_commit:
        raise prior.TwoFrankieBlindError("outer packet launch commit drift")
    if identity.get("launch_identity") != expected_launch_identity:
        raise prior.TwoFrankieBlindError("outer packet launch identity drift")
    if expected_launch_identity != (
        f"{identity.get('github_run_id')}-{identity.get('github_run_attempt')}"
    ):
        raise prior.TwoFrankieBlindError("outer packet run/attempt identity drift")
    if identity.get("packet_sha256") != archive_hash:
        raise prior.TwoFrankieBlindError("outer packet stage identity/archive drift")
    if identity.get("source_sha256") != prior.EXPECTED_SECONDS_SHA256:
        raise prior.TwoFrankieBlindError("outer packet source identity drift")
    if identity.get("source_bytes") != prior.EXPECTED_SECONDS_BYTES:
        raise prior.TwoFrankieBlindError("outer packet source byte identity drift")
    if identity.get("window") != {
        "start": prior.TARGET_START_ISO,
        "end_exclusive": prior.TARGET_END_EXCLUSIVE_ISO,
    }:
        raise prior.TwoFrankieBlindError("outer packet window drift")
    if any(
        identity.get(field) is not False
        for field in ("provider_api_called", "openai_key_used", "cli_model_called", "canary", "tests")
    ) or identity.get("logical_role_calls_completed") != 0:
        raise prior.TwoFrankieBlindError("outer packet stage execution policy drift")

    archive_files: dict[str, tuple[int, str]] = {}
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle.getmembers():
            name = member.name.removeprefix("./")
            if member.isdir() and name in {"output", "output/"}:
                continue
            if not member.isfile() or not name.startswith("output/"):
                raise prior.TwoFrankieBlindError("outer packet archive member is unsafe")
            relative = name.removeprefix("output/")
            if not relative or Path(relative).name != relative or relative in archive_files:
                raise prior.TwoFrankieBlindError("outer packet archive path is unsafe or duplicated")
            extracted = handle.extractfile(member)
            if extracted is None:
                raise prior.TwoFrankieBlindError("outer packet archive member cannot be read")
            raw = extracted.read()
            archive_files[relative] = (len(raw), hashlib.sha256(raw).hexdigest())
    disk_files = {path.name for path in packet_root.iterdir() if path.is_file()}
    if disk_files != set(archive_files):
        raise prior.TwoFrankieBlindError("extracted packet roster differs from bound archive")
    for name, (size, digest) in archive_files.items():
        path = packet_root / name
        if path.stat().st_size != size or sha256_file(path) != digest:
            raise prior.TwoFrankieBlindError(f"extracted packet differs from archive: {name}")


def verify_packet_root(packet_root: Path) -> None:
    manifest = read_json(packet_root / "WORK_PACKET_MANIFEST.json")
    complete = read_json(packet_root / "PACKET_COMPLETE.json")
    if complete.get("status") != "WORK_PACKETS_READY_MODEL_NOT_CALLED":
        raise prior.TwoFrankieBlindError("packet stage is not complete")
    verify_self_hash(manifest)
    verify_self_hash(complete)
    if complete.get("manifest_receipt_hash") != manifest.get("receipt_hash"):
        raise prior.TwoFrankieBlindError("packet completion/manifest binding drift")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise prior.TwoFrankieBlindError("packet artifact manifest is absent")
    seen: set[str] = set()
    for row in artifacts:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise prior.TwoFrankieBlindError("packet artifact manifest row is malformed")
        name = row["path"]
        if name in seen or Path(name).name != name:
            raise prior.TwoFrankieBlindError("packet artifact path is duplicate or unsafe")
        seen.add(name)
        path = packet_root / name
        if (
            not path.is_file()
            or path.stat().st_size != row.get("bytes")
            or sha256_file(path) != row.get("sha256")
        ):
            raise prior.TwoFrankieBlindError(f"packet artifact identity drift: {name}")
    required = {
        "PREFLIGHT.json", "SOURCE_VERIFY.json", "SLICE_MANIFEST.json", "ANSWER_WALL.json",
        "CAPABILITY_RECONCILIATION.json", "RT_WORK_PACKET.json", "RT_CAPABILITIES.json",
        "RT_SCOUT_ROWS.jsonl.gz", "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
        "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json", "FORECASTER_BASE_WORK_PACKET.json",
    }
    if not required.issubset(seen):
        raise prior.TwoFrankieBlindError("packet artifact roster is incomplete")
    wall = read_json(packet_root / "ANSWER_WALL.json")
    verify_self_hash(wall)
    if wall.get("step1_answer_key_exposed") is not False or wall.get("comparison_accessed") is not False:
        raise prior.TwoFrankieBlindError("packet answer wall failed")


def validate_as_of(value: Mapping[str, Any], source_manifest: Mapping[str, Any], role: str) -> None:
    as_of = value.get("as_of")
    if not isinstance(as_of, Mapping):
        raise prior.TwoFrankieBlindError(f"{role} as_of is absent")
    event = as_of.get("event_time_cutoff_ns")
    recv = as_of.get("receive_time_cutoff_ns")
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (event, recv)):
        raise prior.TwoFrankieBlindError(f"{role} as-of clocks must be integers")
    event_floor = int(source_manifest["first_event_second"]) * 1_000_000_000
    event_ceiling = (int(source_manifest["last_event_second"]) + 1) * 1_000_000_000
    recv_ceiling = int(source_manifest["max_contributing_ts_recv_ns"])
    if not event_floor <= int(event) <= event_ceiling:
        raise prior.TwoFrankieBlindError(f"{role} event-clock cutoff escaped the supplied window")
    if not event_floor <= int(recv) <= recv_ceiling:
        raise prior.TwoFrankieBlindError(f"{role} receive-clock cutoff escaped the supplied evidence")
    if not isinstance(as_of.get("clock_policy"), str) or not as_of["clock_policy"].strip():
        raise prior.TwoFrankieBlindError(f"{role} clock policy is absent")


def reject_rt_forecasting(value: Any, path: str = "rt") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered.startswith("forecast") or lowered.startswith("predicted"):
                raise prior.TwoFrankieBlindError(
                    f"Real-Time Frankie emitted forbidden forecast field: {path}.{key}"
                )
            reject_rt_forecasting(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_rt_forecasting(child, f"{path}[{index}]")


def validate_event_clock_ledger(ledger: Any, index: int) -> None:
    required_stages = ("precursor", "onset", "detection", "confirmation")
    clock_fields = (
        "event_time_ns", "receive_time_ns", "evidence_availability_time_ns",
        "decision_as_of_time_ns",
    )
    if not isinstance(ledger, dict) or not set(required_stages).issubset(ledger):
        raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} clock stages are absent")
    event_times: list[int] = []
    decision_times: list[int] = []
    for stage_name in required_stages:
        stage = ledger[stage_name]
        if not isinstance(stage, dict) or not set(clock_fields).issubset(stage) or not isinstance(
            stage.get("status"), str
        ):
            raise prior.TwoFrankieBlindError(
                f"RT exhaustion event {index} {stage_name} clock stage is malformed"
            )
        values = [stage[field] for field in clock_fields]
        if any(value is not None and (isinstance(value, bool) or not isinstance(value, int)) for value in values):
            raise prior.TwoFrankieBlindError(
                f"RT exhaustion event {index} {stage_name} clock value is invalid"
            )
        event, receive, availability, decision = values
        if receive is not None and availability is not None and receive > availability:
            raise prior.TwoFrankieBlindError("RT evidence availability precedes receive time")
        if availability is not None and decision is not None and availability > decision:
            raise prior.TwoFrankieBlindError("RT decision precedes evidence availability")
        if event is not None:
            event_times.append(event)
        if decision is not None:
            decision_times.append(decision)
    if event_times != sorted(event_times) or decision_times != sorted(decision_times):
        raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} clocks are not ordered")


def validate_rt(value: dict[str, Any], source_manifest: dict[str, Any]) -> None:
    missing = sorted(RT_REQUIRED - set(value))
    if missing:
        raise prior.TwoFrankieBlindError(f"RT output missing fields: {missing}")
    if value.get("role") != FrankieRole.REAL_TIME.value:
        raise prior.TwoFrankieBlindError("RT output role drift")
    study = value.get("study_design")
    if study != {
        "answer_key_blind": True,
        "retrospective_complete_two_day_surface": True,
        "prospective_or_out_of_sample_validation": False,
        "early_warning_claim_status": "RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION",
    }:
        raise prior.TwoFrankieBlindError("RT retrospective study-design receipt drift")
    if not isinstance(value.get("first_lock"), dict) or not isinstance(value.get("frozen_rt_state"), dict):
        raise prior.TwoFrankieBlindError("RT first lock/frozen state is absent")
    events = value.get("exhaustion_events")
    if not isinstance(events, list) or not events:
        raise prior.TwoFrankieBlindError("RT must emit exhaustion evidence or an explicit NONE_FOUND record")
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not RT_EVENT_REQUIRED.issubset(event):
            raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} violates its contract")
        confidence = event.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} confidence is invalid")
        if not isinstance(event.get("evidence_refs"), list) or not isinstance(event.get("assumptions"), list):
            raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} evidence is invalid")
        validate_event_clock_ledger(event.get("clock_ledger"), index)
        if not isinstance(event.get("prebirth_detectability"), dict):
            raise prior.TwoFrankieBlindError(
                f"RT exhaustion event {index} pre-birth detectability is absent"
            )
        if event["prebirth_detectability"].get("validation_status") != (
            "RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION"
        ):
            raise prior.TwoFrankieBlindError(
                f"RT exhaustion event {index} overstates pre-birth validation"
            )
        if not isinstance(event.get("observed_dipole_runway"), dict):
            raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} dipole runway is absent")
        latency = event.get("detection_latency_s")
        if not isinstance(latency, dict) or latency.get("validation_status") != (
            "RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION"
        ) or not isinstance(latency.get("clock_basis"), str):
            raise prior.TwoFrankieBlindError(f"RT exhaustion event {index} latency receipt is invalid")
    validate_as_of(value, source_manifest, FrankieRole.REAL_TIME.value)
    direction = value.get("direction_and_direction_change")
    if not isinstance(direction, dict) or direction.get("current_direction") not in {
        "BUY_PRESSURE", "SELL_PRESSURE", "BALANCED", "UNKNOWN"
    }:
        raise prior.TwoFrankieBlindError("RT direction/direction-change receipt is absent")
    if direction.get("cell_signal_promoted_to_fact") is not False:
        raise prior.TwoFrankieBlindError("RT promoted the provisional dipole cell_signal map")
    imbalance = direction.get("signed_imbalance_and_clock")
    if not isinstance(imbalance, dict) or imbalance.get("method_path") != "odcore/info_dipole.py":
        raise prior.TwoFrankieBlindError("RT signed information-dipole method binding is absent")
    if imbalance.get("formula") != "(sum(buy)-sum(sell))/(sum(buy)+sum(sell))":
        raise prior.TwoFrankieBlindError("RT signed imbalance formula drift")
    if imbalance.get("sign_convention") != "positive=buy_pressure;negative=sell_pressure":
        raise prior.TwoFrankieBlindError("RT signed imbalance convention drift")
    dipole_window = imbalance.get("window")
    dipole_clocks = imbalance.get("clock_ledger")
    if not isinstance(dipole_window, dict) or not isinstance(dipole_clocks, dict):
        raise prior.TwoFrankieBlindError("RT signed imbalance window/clocks are absent")
    window_start = dipole_window.get("event_time_start_ns")
    window_end = dipole_window.get("event_time_end_exclusive_ns")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in (window_start, window_end)):
        raise prior.TwoFrankieBlindError("RT signed imbalance window is invalid")
    floor = int(source_manifest["first_event_second"]) * 1_000_000_000
    ceiling = (int(source_manifest["last_event_second"]) + 1) * 1_000_000_000
    if not floor <= window_start < window_end <= value["as_of"]["event_time_cutoff_ns"] <= ceiling:
        raise prior.TwoFrankieBlindError("RT signed imbalance window crossed the causal cutoff")
    required_dipole_clocks = {
        "event_time_ns", "receive_time_ns", "evidence_availability_time_ns", "decision_as_of_time_ns"
    }
    if not required_dipole_clocks.issubset(dipole_clocks) or any(
        isinstance(dipole_clocks[field], bool) or not isinstance(dipole_clocks[field], int)
        for field in required_dipole_clocks
    ) or not (
        dipole_clocks["receive_time_ns"] <= dipole_clocks["evidence_availability_time_ns"]
        <= dipole_clocks["decision_as_of_time_ns"]
    ):
        raise prior.TwoFrankieBlindError("RT signed imbalance clock causality drift")
    imbalance_value = imbalance.get("value")
    if imbalance_value is not None and (
        isinstance(imbalance_value, bool) or not isinstance(imbalance_value, (int, float))
        or not -1 <= imbalance_value <= 1
    ):
        raise prior.TwoFrankieBlindError("RT signed imbalance value is invalid")
    expected_direction = (
        "UNKNOWN" if imbalance_value is None else
        "BUY_PRESSURE" if imbalance_value > 0 else
        "SELL_PRESSURE" if imbalance_value < 0 else "BALANCED"
    )
    if direction.get("current_direction") != expected_direction:
        raise prior.TwoFrankieBlindError("RT signed imbalance/direction consistency drift")
    dipole_flow = direction.get("dipole_flow_and_clock")
    if not isinstance(dipole_flow, dict) or dipole_flow.get("method_path") != "odcore/info_dipole.py":
        raise prior.TwoFrankieBlindError("RT information-dipole flow binding is absent")
    if not isinstance(dipole_flow.get("clock_ledger"), dict):
        raise prior.TwoFrankieBlindError("RT information-dipole flow clocks are absent")
    if dipole_flow.get("window") != dipole_window or dipole_flow.get("clock_ledger") != dipole_clocks:
        raise prior.TwoFrankieBlindError("RT information-dipole window/clock consistency drift")
    for field in ("mi_flow", "imb_flow"):
        observed = dipole_flow.get(field)
        if observed is not None and (
            isinstance(observed, bool) or not isinstance(observed, (int, float))
        ):
            raise prior.TwoFrankieBlindError("RT information-dipole flow value is invalid")
    lookahead = value.get("bounded_lookahead")
    if not isinstance(lookahead, dict) or lookahead.get("status") != "SHADOW_ONLY":
        raise prior.TwoFrankieBlindError("RT bounded lookahead receipt is absent")
    if lookahead.get("unrevealed_outcomes_accessed") is not False:
        raise prior.TwoFrankieBlindError("RT lookahead crossed the blind wall")
    if lookahead.get("first_lock_mutated") is not False:
        raise prior.TwoFrankieBlindError("RT lookahead mutated the observed first lock")
    if lookahead.get("reasoning_pattern_applied") is not True:
        raise prior.TwoFrankieBlindError("RT did not apply the bounded lookahead reasoning pattern")
    if lookahead.get("runtime_module_executed") is not False:
        raise prior.TwoFrankieBlindError("RT falsely claimed runtime lookahead execution")
    if lookahead.get("causal_cutoff") != value.get("as_of"):
        raise prior.TwoFrankieBlindError("RT lookahead cutoff differs from the locked as-of state")
    budget = lookahead.get("fixed_budget")
    if not isinstance(budget, dict) or any(
        isinstance(budget.get(field), bool) or not isinstance(budget.get(field), int)
        or budget[field] <= 0
        for field in ("depth", "width", "iterations", "resource_limit")
    ):
        raise prior.TwoFrankieBlindError("RT lookahead fixed budget is invalid")
    if not isinstance(lookahead.get("hypothesis_tree"), dict) or not isinstance(
        lookahead["hypothesis_tree"].get("live_hypotheses"), list
    ) or len(lookahead["hypothesis_tree"]["live_hypotheses"]) < 2:
        raise prior.TwoFrankieBlindError("RT lookahead hypothesis tree is empty")
    feedback = lookahead.get("feedback_statuses")
    if not isinstance(feedback, list) or not feedback or not set(feedback).issubset(
        {"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"}
    ):
        raise prior.TwoFrankieBlindError("RT lookahead feedback statuses are invalid")
    if not isinstance(lookahead.get("reflections_and_backpropagation"), dict) or not (
        lookahead["reflections_and_backpropagation"]
    ):
        raise prior.TwoFrankieBlindError("RT lookahead reflection/backpropagation is absent")
    if not isinstance(lookahead.get("pruned_alternatives_and_falsifiers"), list) or not (
        lookahead["pruned_alternatives_and_falsifiers"]
    ):
        raise prior.TwoFrankieBlindError("RT lookahead falsifier roster is absent")
    scout = value.get("scout_usage")
    if not isinstance(scout, dict) or set(scout) != {
        "available", "invoked", "invocation_count", "request_sha256", "response_sha256",
        "response_bytes", "cumulative_estimated_input_tokens",
    }:
        raise prior.TwoFrankieBlindError("RT local-scout usage receipt drift")
    scout_count = scout.get("invocation_count")
    if scout.get("available") is not True or scout_count not in {0, 1}:
        raise prior.TwoFrankieBlindError("RT local-scout count drift")
    if bool(scout.get("invoked")) != (scout_count == 1):
        raise prior.TwoFrankieBlindError("RT local-scout invocation flag/count disagree")
    cumulative = scout.get("cumulative_estimated_input_tokens")
    if isinstance(cumulative, bool) or not isinstance(cumulative, int) or cumulative < 0:
        raise prior.TwoFrankieBlindError("RT cumulative input token receipt is invalid")
    if cumulative > RT_CUMULATIVE_INPUT_TOKEN_CAP:
        raise prior.TwoFrankieBlindError("RT cumulative input token ceiling exceeded")
    if scout_count == 0 and any(
        scout.get(field) not in {None, 0}
        for field in ("request_sha256", "response_sha256", "response_bytes")
    ):
        raise prior.TwoFrankieBlindError("unused RT scout has a fabricated receipt")
    if scout_count == 1:
        if isinstance(scout.get("response_bytes"), bool) or not isinstance(
            scout.get("response_bytes"), int
        ) or scout["response_bytes"] <= 0:
            raise prior.TwoFrankieBlindError("RT scout response-byte receipt is invalid")
        for field in ("request_sha256", "response_sha256"):
            digest = scout.get(field)
            if not isinstance(digest, str) or len(digest) != 64:
                raise prior.TwoFrankieBlindError("RT scout artifact hash is absent")
            try:
                bytes.fromhex(digest)
            except ValueError as exc:
                raise prior.TwoFrankieBlindError("RT scout artifact hash is invalid") from exc
    strategies = value.get("strategy_hypotheses")
    if not isinstance(strategies, list) or not strategies:
        raise prior.TwoFrankieBlindError(
            "RT must emit provisional strategy hypotheses or an explicit NONE_FOUND record"
        )
    required_strategy = {
        "strategy_id", "status", "exhaustion_detection_quality_gate", "causal_trigger", "side_or_position_logic",
        "entry_condition", "hold_or_continuation_condition",
        "exit_or_reversal_condition", "invalidation_or_stop", "expected_horizon",
        "sizing_and_risk", "fees_slippage_and_fill_assumptions",
        "required_unavailable_data", "contradictions", "evidence_refs",
        "execution_authority", "validated_profitability_claim",
    }
    for index, strategy in enumerate(strategies):
        if not isinstance(strategy, dict) or not required_strategy.issubset(strategy):
            raise prior.TwoFrankieBlindError(f"RT strategy hypothesis {index} violates its contract")
        if strategy.get("execution_authority") is not False:
            raise prior.TwoFrankieBlindError("RT strategy may not have execution authority")
        if strategy.get("validated_profitability_claim") is not False:
            raise prior.TwoFrankieBlindError("two-day RT strategy may not claim validated profitability")
        if strategy.get("status") not in {
            "DISCOVERY_ONLY", "PROMISING_RETROSPECTIVE_TWO_DAY_HYPOTHESIS",
            "NONE_FOUND_IN_SEARCHED_COVERAGE"
        }:
            raise prior.TwoFrankieBlindError("RT strategy readiness status is invalid")
        gate = strategy.get("exhaustion_detection_quality_gate")
        required_gate = {
            "event_support", "misses", "false_alerts", "prebirth_or_early_detection",
            "lead_time_distribution_s", "detection_latency_distribution_s",
            "duration_error_or_range_coverage", "readiness_verdict",
            "promotion_or_rejection_reason",
        }
        if not isinstance(gate, dict) or not required_gate.issubset(gate) or gate.get("readiness_verdict") not in {
            "DISCOVERY_ONLY", "PROMISING_RETROSPECTIVE_TWO_DAY_HYPOTHESIS",
            "NONE_FOUND_IN_SEARCHED_COVERAGE"
        }:
            raise prior.TwoFrankieBlindError("RT strategy detection-quality gate is absent")
        for metric in ("event_support", "misses", "false_alerts"):
            metric_value = gate.get(metric)
            if isinstance(metric_value, bool) or not isinstance(metric_value, int) or metric_value < 0:
                raise prior.TwoFrankieBlindError("RT strategy gate count is invalid")
        for field in (
            "prebirth_or_early_detection", "lead_time_distribution_s",
            "detection_latency_distribution_s", "duration_error_or_range_coverage",
        ):
            if not isinstance(gate.get(field), dict) or not gate[field]:
                raise prior.TwoFrankieBlindError(f"RT strategy gate {field} is absent")
        if not isinstance(gate.get("promotion_or_rejection_reason"), str) or not (
            gate["promotion_or_rejection_reason"].strip()
        ):
            raise prior.TwoFrankieBlindError("RT strategy promotion/rejection reason is absent")
        if strategy["status"] != gate["readiness_verdict"]:
            raise prior.TwoFrankieBlindError("RT strategy status/readiness verdict drift")
        if strategy["status"] == "PROMISING_RETROSPECTIVE_TWO_DAY_HYPOTHESIS" and (
            gate["event_support"] < 2 or gate["false_alerts"] > gate["event_support"]
        ):
            raise prior.TwoFrankieBlindError("RT promising strategy lacks retrospective support")
    reject_rt_forecasting(value)


def validate_forecaster(
    value: dict[str, Any], source_manifest: dict[str, Any], frozen_hash: str,
    frozen_event_ids: set[str],
    knowledge_manifest: dict[str, Any], knowledge_manifest_bytes: int,
    fc_packet: dict[str, Any],
) -> None:
    missing = sorted(FC_REQUIRED - set(value))
    if missing:
        raise prior.TwoFrankieBlindError(f"Forecaster output missing fields: {missing}")
    if value.get("role") != FrankieRole.FORECASTER.value:
        raise prior.TwoFrankieBlindError("Forecaster output role drift")
    if value.get("rt_state_sha256") != frozen_hash:
        raise prior.TwoFrankieBlindError("Forecaster did not bind the exact frozen RT state")
    if value.get("first_lock") is not None:
        raise prior.TwoFrankieBlindError("Forecaster may not create or replace RT's first lock")
    if value.get("frozen_rt_state") is not None:
        raise prior.TwoFrankieBlindError("Forecaster may not emit a competing frozen RT state")
    curve = value.get("forecast_curve")
    if not isinstance(curve, dict) or not isinstance(curve.get("points"), list) or not curve["points"]:
        raise prior.TwoFrankieBlindError("Forecaster did not produce a plotted forecast curve")
    if not {
        "curve_id", "as_of_event_clock_ns", "as_of_receive_clock_ns", "path_regime",
        "points", "continuity_reasoning", "multimodal_paths", "abstention",
    }.issubset(curve):
        raise prior.TwoFrankieBlindError("Forecaster curve-level contract is incomplete")
    if curve.get("as_of_event_clock_ns") != value["as_of"]["event_time_cutoff_ns"] or (
        curve.get("as_of_receive_clock_ns") != value["as_of"]["receive_time_cutoff_ns"]
    ):
        raise prior.TwoFrankieBlindError("Forecaster curve as-of clocks drift")
    if not isinstance(curve.get("continuity_reasoning"), str) or not curve["continuity_reasoning"].strip():
        raise prior.TwoFrankieBlindError("Forecaster curve continuity reasoning is absent")
    if not isinstance(curve.get("multimodal_paths"), list) or not isinstance(
        curve.get("abstention"), dict
    ) or not curve["abstention"]:
        raise prior.TwoFrankieBlindError("Forecaster multimodal/abstention contract drift")
    multimodal_path_ids: set[str] = set()
    for path_index, path in enumerate(curve["multimodal_paths"]):
        if not isinstance(path, dict) or not {
            "path_id", "probability", "conditions", "disconfirmers"
        }.issubset(path):
            raise prior.TwoFrankieBlindError(f"Forecaster multimodal path {path_index} is malformed")
        path_id, probability = path.get("path_id"), path.get("probability")
        if not isinstance(path_id, str) or not path_id.strip() or path_id in multimodal_path_ids:
            raise prior.TwoFrankieBlindError("Forecaster multimodal path identity drift")
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise prior.TwoFrankieBlindError("Forecaster multimodal path probability is invalid")
        if not isinstance(path.get("conditions"), list) or not isinstance(path.get("disconfirmers"), list):
            raise prior.TwoFrankieBlindError("Forecaster multimodal path evidence is invalid")
        multimodal_path_ids.add(path_id)
    if multimodal_path_ids and abs(sum(
        float(path["probability"]) for path in curve["multimodal_paths"]
    ) - 1.0) > 1e-6:
        raise prior.TwoFrankieBlindError("Forecaster multimodal probabilities do not sum to one")
    target_times: list[int] = []
    for index, point in enumerate(curve["points"]):
        required = {
            "horizon_or_timestamp", "target_event_time_ns", "scenario_id", "rt_state_sha256",
            "rt_candidate_ids",
            "clock_ledger", "central_path_value", "distribution_or_range",
            "conditions", "catalysts", "disconfirmers", "confidence", "missingness",
            "rt_feed_effect", "dipole_path",
        }
        if not isinstance(point, dict) or not required.issubset(point):
            raise prior.TwoFrankieBlindError(f"forecast point {index} violates the curve contract")
        confidence = point.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise prior.TwoFrankieBlindError(f"forecast point {index} confidence is invalid")
        if not isinstance(point.get("clock_ledger"), dict):
            raise prior.TwoFrankieBlindError(f"forecast point {index} clock ledger is absent")
        ledger = point["clock_ledger"]
        required_clocks = {
            "source_event_time_ns", "receive_time_ns", "evidence_availability_time_ns",
            "decision_as_of_time_ns", "target_event_time_ns",
        }
        if not required_clocks.issubset(ledger) or any(
            isinstance(ledger[field], bool) or not isinstance(ledger[field], int)
            for field in required_clocks
        ):
            raise prior.TwoFrankieBlindError(f"forecast point {index} clock ledger is invalid")
        if not (
            ledger["receive_time_ns"] <= ledger["evidence_availability_time_ns"]
            <= ledger["decision_as_of_time_ns"] < ledger["target_event_time_ns"]
        ):
            raise prior.TwoFrankieBlindError(f"forecast point {index} clock causality drift")
        target = point.get("target_event_time_ns")
        if target != ledger["target_event_time_ns"] or target <= value["as_of"]["event_time_cutoff_ns"]:
            raise prior.TwoFrankieBlindError(f"forecast point {index} is not a future point")
        target_times.append(target)
        if point.get("rt_state_sha256") != frozen_hash:
            raise prior.TwoFrankieBlindError(f"forecast point {index} RT binding drift")
        point_candidate_ids = point.get("rt_candidate_ids")
        if (
            not isinstance(point_candidate_ids, list)
            or len(point_candidate_ids) != len(set(point_candidate_ids))
            or not set(point_candidate_ids).issubset(frozen_event_ids)
        ):
            raise prior.TwoFrankieBlindError(f"forecast point {index} RT candidate binding drift")
        if not isinstance(point.get("scenario_id"), str) or not point["scenario_id"].strip():
            raise prior.TwoFrankieBlindError(f"forecast point {index} scenario identity is absent")
        if point.get("central_path_value") is not None and (
            isinstance(point["central_path_value"], bool)
            or not isinstance(point["central_path_value"], (int, float))
        ):
            raise prior.TwoFrankieBlindError(f"forecast point {index} central path value is invalid")
        distribution = point.get("distribution_or_range")
        if not isinstance(distribution, dict) or distribution.get("kind") not in {
            "RANGE", "QUANTILES", "MULTIMODAL", "ABSTAIN"
        }:
            raise prior.TwoFrankieBlindError(f"forecast point {index} distribution is absent")
        lower, upper = distribution.get("lower"), distribution.get("upper")
        if distribution["kind"] != "ABSTAIN":
            if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in (lower, upper)):
                raise prior.TwoFrankieBlindError(f"forecast point {index} range is invalid")
            if lower > upper:
                raise prior.TwoFrankieBlindError(f"forecast point {index} range ordering drift")
        elif lower is not None or upper is not None:
            raise prior.TwoFrankieBlindError(f"forecast point {index} abstention range must be null")
        if distribution["kind"] == "MULTIMODAL" and not curve["multimodal_paths"]:
            raise prior.TwoFrankieBlindError("Forecaster collapsed a multimodal distribution")
        if distribution["kind"] == "MULTIMODAL":
            path_ids = distribution.get("path_ids")
            if (
                not isinstance(path_ids, list) or not path_ids
                or len(path_ids) != len(set(path_ids))
                or not set(path_ids).issubset(multimodal_path_ids)
            ):
                raise prior.TwoFrankieBlindError(f"forecast point {index} multimodal path binding drift")
        if distribution["kind"] == "QUANTILES":
            quantiles = distribution.get("quantiles")
            if not isinstance(quantiles, list) or len(quantiles) < 2:
                raise prior.TwoFrankieBlindError(f"forecast point {index} quantiles are absent")
            previous_probability = -1.0
            previous_value: float | None = None
            for quantile in quantiles:
                if not isinstance(quantile, dict):
                    raise prior.TwoFrankieBlindError(f"forecast point {index} quantile is malformed")
                probability, quantile_value = quantile.get("probability"), quantile.get("value")
                if (
                    isinstance(probability, bool) or not isinstance(probability, (int, float))
                    or isinstance(quantile_value, bool) or not isinstance(quantile_value, (int, float))
                    or not 0 <= probability <= 1 or probability <= previous_probability
                    or (previous_value is not None and quantile_value < previous_value)
                ):
                    raise prior.TwoFrankieBlindError(f"forecast point {index} quantile ordering drift")
                previous_probability, previous_value = float(probability), float(quantile_value)
        for field in ("conditions", "catalysts", "disconfirmers", "missingness"):
            if not isinstance(point.get(field), list):
                raise prior.TwoFrankieBlindError(f"forecast point {index} {field} is invalid")
        if not isinstance(point.get("rt_feed_effect"), str) or not point["rt_feed_effect"].strip():
            raise prior.TwoFrankieBlindError(f"forecast point {index} RT-feed analysis is absent")
        if not isinstance(point.get("dipole_path"), dict) or not point["dipole_path"]:
            raise prior.TwoFrankieBlindError(f"forecast point {index} dipole path is absent")
    if target_times != sorted(target_times) or len(set(target_times)) != len(target_times):
        raise prior.TwoFrankieBlindError("Forecaster curve target clocks are not strictly increasing")
    helper = value.get("helper_usage")
    if not isinstance(helper, dict):
        raise prior.TwoFrankieBlindError("Forecaster helper-usage receipt is absent")
    expected_helper_fields = {
        "available", "invoked", "invocation_count", "reason", "helper_model",
        "helper_request_hash", "helper_response_hash", "advisory_findings_used",
        "helper_evidence_refs", "rejection_reason",
    }
    if set(helper) != expected_helper_fields or helper.get("available") is not True:
        raise prior.TwoFrankieBlindError("Forecaster helper-usage receipt drift")
    helper_count = helper.get("invocation_count")
    if isinstance(helper_count, bool) or helper_count not in {0, 1}:
        raise prior.TwoFrankieBlindError("Forecaster helper invocation count must be 0 or 1")
    if bool(helper.get("invoked")) != (helper_count == 1):
        raise prior.TwoFrankieBlindError("Forecaster helper invocation flag/count disagree")
    if not isinstance(helper.get("advisory_findings_used"), bool) or not isinstance(
        helper.get("helper_evidence_refs"), list
    ):
        raise prior.TwoFrankieBlindError("Forecaster helper use/citation receipt drift")
    if helper_count == 1:
        if helper.get("helper_model") != prior.MODEL:
            raise prior.TwoFrankieBlindError("Forecaster helper model drift")
        digest = helper.get("helper_response_hash")
        request_digest = helper.get("helper_request_hash")
        if not isinstance(digest, str) or not isinstance(request_digest, str):
            raise prior.TwoFrankieBlindError("Forecaster helper response hash is absent")
        try:
            bytes.fromhex(digest)
            bytes.fromhex(request_digest)
        except ValueError as exc:
            raise prior.TwoFrankieBlindError("Forecaster helper hash is not hexadecimal") from exc
        if len(digest) != 64 or len(request_digest) != 64:
            raise prior.TwoFrankieBlindError("Forecaster helper hash length drift")
        if helper["advisory_findings_used"] and not helper["helper_evidence_refs"]:
            raise prior.TwoFrankieBlindError("used Forecaster helper findings are not cited")
        if not helper["advisory_findings_used"] and not isinstance(
            helper.get("rejection_reason"), str
        ):
            raise prior.TwoFrankieBlindError("unused invoked helper lacks rejection reason")
    elif any(
        helper.get(field) is not None
        for field in (
            "helper_model", "helper_request_hash", "helper_response_hash", "rejection_reason"
        )
    ):
        raise prior.TwoFrankieBlindError("unused Forecaster helper has a fabricated receipt")
    elif helper["advisory_findings_used"] or helper["helper_evidence_refs"]:
        raise prior.TwoFrankieBlindError("unused Forecaster helper claims advisory use")
    knowledge = value.get("knowledge_usage")
    if not isinstance(knowledge, dict) or set(knowledge) != {
        "complete_bundle_available", "inventory_receipt_hash", "sources_consulted",
        "sources_uninspected", "bytes_loaded_into_principal_context",
        "estimated_total_principal_input_tokens", "every_bundle_byte_claimed_loaded",
        "uninspected_source_treated_as_absent",
    }:
        raise prior.TwoFrankieBlindError("Forecaster knowledge-usage receipt drift")
    if knowledge.get("complete_bundle_available") is not True:
        raise prior.TwoFrankieBlindError("Forecaster did not acknowledge the complete knowledge bundle")
    if knowledge.get("inventory_receipt_hash") != knowledge_manifest.get("inventory_receipt_hash"):
        raise prior.TwoFrankieBlindError("Forecaster knowledge inventory binding drift")
    consulted = knowledge.get("sources_consulted")
    uninspected = knowledge.get("sources_uninspected")
    if not isinstance(consulted, list) or not isinstance(uninspected, list):
        raise prior.TwoFrankieBlindError("Forecaster knowledge coverage lists are absent")
    expected_sources = {
        row["path"] for row in knowledge_manifest.get("lawful_content_sources", [])
    }
    if (
        len(consulted) != len(set(consulted))
        or len(uninspected) != len(set(uninspected))
        or set(consulted) & set(uninspected)
        or set(consulted) | set(uninspected) != expected_sources
    ):
        raise prior.TwoFrankieBlindError("Forecaster knowledge coverage does not reconcile")
    lawful_sizes = {
        row["path"]: int(row["retrieval_payload_bytes"])
        for row in knowledge_manifest.get("lawful_content_sources", [])
    }
    loaded_bytes = (
        knowledge_manifest_bytes
        + sum(lawful_sizes[path] for path in consulted)
    )
    if knowledge.get("bytes_loaded_into_principal_context") != loaded_bytes:
        raise prior.TwoFrankieBlindError("Forecaster knowledge byte receipt does not match consulted sources")
    packet_core = dict(fc_packet)
    packet_core.pop("packet_hash", None)
    estimated_total = math.ceil(
        (len(canonical(packet_core)) + loaded_bytes) * TOKEN_ESTIMATE_PER_BYTE
    )
    if estimated_total > FORECASTER_INPUT_TOKEN_CAP:
        raise prior.TwoFrankieBlindError("Forecaster principal context exceeds 150000 tokens")
    if knowledge.get("estimated_total_principal_input_tokens") != estimated_total:
        raise prior.TwoFrankieBlindError("Forecaster principal input token estimate drift")
    all_bytes_loaded = set(consulted) == expected_sources
    if bool(knowledge.get("every_bundle_byte_claimed_loaded")) != all_bytes_loaded:
        raise prior.TwoFrankieBlindError("Forecaster complete-byte visibility claim drift")
    if knowledge.get("uninspected_source_treated_as_absent") is not False:
        raise prior.TwoFrankieBlindError("Forecaster treated uninspected knowledge as absent")
    prior._validate_findings(value, FrankieRole.FORECASTER.value)
    validate_as_of(value, source_manifest, FrankieRole.FORECASTER.value)


def agent_receipt(
    *, role: str, index: int, input_path: Path, output_path: Path, output: dict[str, Any],
    helper_calls: int = 0,
) -> dict[str, Any]:
    output_bytes = output_path.stat().st_size
    if output_bytes > MAX_OUTPUT_BYTES:
        raise prior.TwoFrankieBlindError(
            f"{role} output exceeds the conservative {MAX_OUTPUT_TOKENS}-token byte ceiling"
        )
    core = {
        "schema": "FRANKIE_WORKMODE_AGENT_RECEIPT_V1_20260825",
        "role": role,
        "logical_call_index": index,
        "logical_call_count": 1,
        "model_requested": prior.MODEL,
        "execution_surface": "CHATGPT_WORK_AGENT",
        "provider_api_called": False,
        "openai_key_used": False,
        "cli_model_called": False,
        "repair_calls": 0,
        "fallback_calls": 0,
        "specialist_calls": 0,
        "helper_calls": helper_calls,
        "input_token_cap": 96_000 if role == FrankieRole.REAL_TIME.value else 150_000,
        "output_token_cap": MAX_OUTPUT_TOKENS,
        "output_bytes": output_bytes,
        "max_output_bytes_estimate": MAX_OUTPUT_BYTES,
        "input_path": input_path.name,
        "input_sha256": sha256_file(input_path),
        "output_path": output_path.name,
        "output_sha256": sha256_file(output_path),
        "accepted_output_hash": sha256_json(output),
    }
    return {**core, "receipt_hash": sha256_json(core)}


def freeze_rt(args: argparse.Namespace) -> None:
    packet_root = args.packet_root
    run_root = args.run_root
    verify_outer_packet(
        packet_root, args.packet_archive, args.packet_sha256, args.stage_identity,
        args.expected_implementation_commit, args.expected_authorization_commit,
        args.expected_launch_commit, args.expected_launch_identity,
    )
    verify_packet_root(packet_root)
    if run_root.exists():
        raise prior.TwoFrankieBlindError("RT run root already exists")
    anchor_resolved = args.rt_freeze_anchor_output.resolve()
    run_resolved = run_root.resolve()
    if anchor_resolved == run_resolved or run_resolved in anchor_resolved.parents:
        raise prior.TwoFrankieBlindError("RT freeze anchor must be retained outside run root")
    source_manifest = read_json(packet_root / "SLICE_MANIFEST.json")
    packet = read_json(packet_root / "RT_WORK_PACKET.json")
    output = read_json(args.rt_output)
    validate_rt(output, source_manifest)
    run_root.mkdir(parents=True, exist_ok=False)
    copied_output = run_root / "RT_OUTPUT.json"
    write_json(copied_output, output)
    scout_count = int(output["scout_usage"]["invocation_count"])
    if scout_count == 1:
        if args.rt_scout_request is None or args.rt_scout_output is None:
            raise prior.TwoFrankieBlindError("invoked RT scout lacks request/output artifacts")
        request = read_json(args.rt_scout_request)
        scout_output = read_json(args.rt_scout_output)
        expected_request_fields = {
            "schema", "operation", "candidate_event_id", "decision_cutoff_ns",
            "event_time_start_ns", "event_time_end_exclusive_ns",
            "field_paths", "maximum_rows", "allowed_input_hashes",
        }
        if set(request) != expected_request_fields or request.get("schema") != (
            "FRANKIE_RT_LOCAL_SCOUT_REQUEST_V1_20260825"
        ):
            raise prior.TwoFrankieBlindError("RT scout request contract drift")
        if request.get("operation") not in {"ROW_RANGE", "FIELD_SERIES"}:
            raise prior.TwoFrankieBlindError("RT scout operation is not allowed")
        start = request.get("event_time_start_ns")
        end = request.get("event_time_end_exclusive_ns")
        decision_cutoff = request.get("decision_cutoff_ns")
        floor = int(source_manifest["first_event_second"]) * 1_000_000_000
        ceiling = (int(source_manifest["last_event_second"]) + 1) * 1_000_000_000
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (start, end, decision_cutoff)
        ):
            raise prior.TwoFrankieBlindError("RT scout event-time bounds are invalid")
        if not floor <= start < end <= decision_cutoff <= ceiling:
            raise prior.TwoFrankieBlindError("RT scout request escaped the exact two-day surface")
        if decision_cutoff > int(output["as_of"]["event_time_cutoff_ns"]):
            raise prior.TwoFrankieBlindError("RT scout crossed the role decision cutoff")
        event_ids = {event.get("event_id") for event in output["exhaustion_events"]}
        if request.get("candidate_event_id") not in event_ids:
            raise prior.TwoFrankieBlindError("RT scout candidate binding drift")
        if (
            not isinstance(request.get("field_paths"), list)
            or not request["field_paths"]
            or len(request["field_paths"]) > 32
        ):
            raise prior.TwoFrankieBlindError("RT scout field roster is absent")
        max_rows = request.get("maximum_rows")
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= 10_000:
            raise prior.TwoFrankieBlindError("RT scout maximum rows are invalid")
        expected_hashes = {
            name: sha256_file(packet_root / name)
            for name in ("RT_SCOUT_ROWS.jsonl.gz", "RT_CAPABILITIES.json")
        }
        if request.get("allowed_input_hashes") != expected_hashes:
            raise prior.TwoFrankieBlindError("RT scout input hash allowlist drift")
        additional_bytes = args.rt_scout_request.stat().st_size + args.rt_scout_output.stat().st_size
        if additional_bytes > RT_SCOUT_ADDITIONAL_INPUT_BYTE_CAP:
            raise prior.TwoFrankieBlindError("RT scout continuation exceeds the cumulative input cap")
        if output["scout_usage"]["request_sha256"] != sha256_file(args.rt_scout_request):
            raise prior.TwoFrankieBlindError("RT scout request hash mismatch")
        if output["scout_usage"]["response_sha256"] != sha256_file(args.rt_scout_output):
            raise prior.TwoFrankieBlindError("RT scout response hash mismatch")
        if output["scout_usage"]["response_bytes"] != args.rt_scout_output.stat().st_size:
            raise prior.TwoFrankieBlindError("RT scout response-byte receipt mismatch")
        if set(scout_output) != {
            "schema", "request_sha256", "operation", "rows", "row_count", "truncated"
        } or scout_output.get("schema") != "FRANKIE_RT_LOCAL_SCOUT_RESPONSE_V1_20260825":
            raise prior.TwoFrankieBlindError("RT scout response contract drift")
        if scout_output.get("request_sha256") != sha256_file(args.rt_scout_request):
            raise prior.TwoFrankieBlindError("RT scout response request binding drift")
        if scout_output.get("operation") != request.get("operation"):
            raise prior.TwoFrankieBlindError("RT scout response operation drift")
        scout_rows = scout_output.get("rows")
        if (
            not isinstance(scout_rows, list)
            or any(not isinstance(row, dict) for row in scout_rows)
            or scout_output.get("row_count") != len(scout_rows)
            or len(scout_rows) > max_rows
            or not isinstance(scout_output.get("truncated"), bool)
        ):
            raise prior.TwoFrankieBlindError("RT scout response row contract drift")
        requested_fields = request["field_paths"]
        if len(requested_fields) != len(set(requested_fields)) or any(
            not isinstance(field, str) or not field for field in requested_fields
        ):
            raise prior.TwoFrankieBlindError("RT scout requested-field roster drift")
        response_indices: list[int] = []
        for row in scout_rows:
            if set(row) != {"source_row_index", "event_time_ns", "fields"}:
                raise prior.TwoFrankieBlindError("RT scout response row shape drift")
            index = row.get("source_row_index")
            stamp = row.get("event_time_ns")
            if any(isinstance(value, bool) or not isinstance(value, int) for value in (index, stamp)):
                raise prior.TwoFrankieBlindError("RT scout response provenance is invalid")
            if not start <= stamp < end or stamp > decision_cutoff:
                raise prior.TwoFrankieBlindError("RT scout response crossed its causal cutoff")
            if not isinstance(row.get("fields"), dict) or set(row["fields"]) != set(requested_fields):
                raise prior.TwoFrankieBlindError("RT scout response returned unrequested fields")
            response_indices.append(index)
        if response_indices != sorted(response_indices) or len(set(response_indices)) != len(response_indices):
            raise prior.TwoFrankieBlindError("RT scout response provenance is unordered or duplicated")
        expected_rows: list[dict[str, Any]] = []
        eligible_count = 0
        with gzip.open(packet_root / "RT_SCOUT_ROWS.jsonl.gz", "rt", encoding="utf-8") as handle:
            for source_index, line in enumerate(handle):
                source_row = json.loads(line)
                if not isinstance(source_row, dict):
                    raise prior.TwoFrankieBlindError("bound RT scout source row is malformed")
                expected_stamp = int(source_row["epoch_second"]) * 1_000_000_000
                if not start <= expected_stamp < end or expected_stamp > decision_cutoff:
                    continue
                eligible_count += 1
                if len(expected_rows) < max_rows:
                    expected_rows.append(
                        {
                            "source_row_index": source_index,
                            "event_time_ns": expected_stamp,
                            "fields": {
                                field: resolve_field_path(source_row, field)
                                for field in requested_fields
                            },
                        }
                    )
        if scout_rows != expected_rows:
            raise prior.TwoFrankieBlindError(
                "RT scout response is not the deterministic bound-source first page"
            )
        if scout_output["truncated"] != (eligible_count > max_rows):
            raise prior.TwoFrankieBlindError("RT scout truncation receipt drift")
        direct_estimate = int(packet["direct_packet_token_budget"]["estimated_input_tokens"])
        expected_cumulative = direct_estimate + math.ceil(
            additional_bytes * TOKEN_ESTIMATE_PER_BYTE
        )
        if output["scout_usage"]["cumulative_estimated_input_tokens"] != expected_cumulative:
            raise prior.TwoFrankieBlindError("RT scout cumulative token receipt drift")
        copy_exact_exclusive(args.rt_scout_request, run_root / "RT_SCOUT_REQUEST.json")
        copy_exact_exclusive(args.rt_scout_output, run_root / "RT_SCOUT_OUTPUT.json")
    elif args.rt_scout_request is not None or args.rt_scout_output is not None:
        raise prior.TwoFrankieBlindError("unused RT scout has stray artifacts")
    else:
        direct_estimate = int(packet["direct_packet_token_budget"]["estimated_input_tokens"])
        if output["scout_usage"]["cumulative_estimated_input_tokens"] != direct_estimate:
            raise prior.TwoFrankieBlindError("unused RT scout cumulative token receipt drift")

    frozen_core = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FROZEN_RT_EXHAUSTION_STATE_V2_20260825",
        "role": FrankieRole.REAL_TIME.value,
        "source_manifest_hash": source_manifest["manifest_hash"],
        "rt_packet_hash": packet["packet_hash"],
        "rt_output_hash": sha256_json(output),
        "state": output["frozen_rt_state"],
        "full_validated_rt_output": output,
        "as_of": output["as_of"],
    }
    frozen = {**frozen_core, "frozen_rt_state_hash": sha256_json(frozen_core)}
    context = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_RT_CONTEXT_MANIFEST_V2_WORKMODE_20260825",
        "role": FrankieRole.REAL_TIME.value,
        "packet_hash": packet["packet_hash"],
        "source_manifest_hash": source_manifest["manifest_hash"],
        "answer_wall": "SEALED",
        "provider_api_called": False,
        "role_is_forecasting": False,
    }
    context["receipt_hash"] = sha256_json(context)
    write_json(run_root / "RT_CONTEXT_MANIFEST.json", context)
    write_json(
        run_root / "RT_AGENT_RECEIPT.json",
        agent_receipt(
            role=FrankieRole.REAL_TIME.value,
            index=1,
            input_path=packet_root / "RT_WORK_PACKET.json",
            output_path=copied_output,
            output=output,
        ),
    )
    lock = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_RT_FIRST_LOCK_V2_WORKMODE_20260825",
        "rt_output_hash": sha256_json(output),
        "first_lock": output["first_lock"],
        "first_lock_owner": FrankieRole.REAL_TIME.value,
        "exhaustion_events": output["exhaustion_events"],
    }
    lock["receipt_hash"] = sha256_json(lock)
    write_json(run_root / "RT_FIRST_LOCK.json", lock)
    write_json(run_root / "RT_FROZEN_STATE.json", frozen)
    handoff = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_ONEWAY_HANDOFF_V2_WORKMODE_20260825",
        "from_role": FrankieRole.REAL_TIME.value,
        "to_role": FrankieRole.FORECASTER.value,
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "full_validated_rt_output_included": True,
        "full_validated_rt_output_hash": sha256_json(output),
        "forecaster_may_modify_rt_state": False,
        "forecaster_may_reconstruct_competing_current_state": False,
        "rt_frozen_before_forecaster": True,
    }
    handoff["receipt_hash"] = sha256_json(handoff)
    write_json(run_root / "ONEWAY_HANDOFF.json", handoff)

    fc_base = read_json(packet_root / "FORECASTER_BASE_WORK_PACKET.json")
    fc_base.pop("packet_hash", None)
    fc_packet = {
        **fc_base,
        "authoritative_frozen_rt_state": frozen,
        "authoritative_frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "rt_agent_receipt_hash": read_json(run_root / "RT_AGENT_RECEIPT.json")["receipt_hash"],
    }
    fc_packet["packet_hash"] = sha256_json(fc_packet)
    fc_packet["final_principal_packet_token_budget"] = {
        "estimated_input_tokens": 0,
        "estimator_tokens_per_byte": TOKEN_ESTIMATE_PER_BYTE,
        "maximum_estimated_input_tokens": FORECASTER_INPUT_TOKEN_CAP,
        "complete_lawful_bundle_is_addressable_not_all_bytes_directly_injected": True,
    }
    estimated_fc_tokens = math.ceil(len(canonical(fc_packet)) * TOKEN_ESTIMATE_PER_BYTE)
    fc_packet["final_principal_packet_token_budget"]["estimated_input_tokens"] = (
        estimated_fc_tokens
    )
    estimated_fc_tokens = math.ceil(len(canonical(fc_packet)) * TOKEN_ESTIMATE_PER_BYTE)
    fc_packet["final_principal_packet_token_budget"]["estimated_input_tokens"] = (
        estimated_fc_tokens
    )
    if estimated_fc_tokens > FORECASTER_INPUT_TOKEN_CAP:
        raise prior.TwoFrankieBlindError(
            "Forecaster packet plus complete frozen RT output exceeds its 150000-token ceiling"
        )
    fc_packet.pop("packet_hash", None)
    fc_packet["packet_hash"] = sha256_json(fc_packet)
    write_json(run_root / "FORECASTER_WORK_PACKET.json", fc_packet)
    complete = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_RT_FREEZE_COMPLETE_V1_20260825",
        "status": "RT_FROZEN_FORECASTER_PACKET_READY",
        "published_last": True,
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "forecaster_packet_hash": fc_packet["packet_hash"],
        "next_role": FrankieRole.FORECASTER.value,
    }
    complete["receipt_hash"] = sha256_json(complete)
    write_json(run_root / "RT_FREEZE_COMPLETE.json", complete)
    freeze_rows = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(run_root.iterdir())
        if path.is_file()
    ]
    anchor = {
        "schema": "FRANKIE_RT_FREEZE_EXTERNAL_ANCHOR_V1_20260825",
        "run_root_name": run_root.name,
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "forecaster_packet_hash": fc_packet["packet_hash"],
        "freeze_artifacts": freeze_rows,
    }
    anchor["receipt_hash"] = sha256_json(anchor)
    write_json(args.rt_freeze_anchor_output, anchor)


def verify_rt_freeze(
    packet_root: Path, run_root: Path, source_manifest: dict[str, Any], anchor_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    anchor = read_json(anchor_path)
    verify_self_hash(anchor)
    if anchor.get("schema") != "FRANKIE_RT_FREEZE_EXTERNAL_ANCHOR_V1_20260825":
        raise prior.TwoFrankieBlindError("external RT freeze anchor schema drift")
    if anchor.get("run_root_name") != run_root.name:
        raise prior.TwoFrankieBlindError("external RT freeze anchor run identity drift")
    observed_rows = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(run_root.iterdir())
        if path.is_file()
    ]
    if anchor.get("freeze_artifacts") != observed_rows:
        raise prior.TwoFrankieBlindError("RT freeze artifacts changed after external anchoring")
    rt_output = read_json(run_root / "RT_OUTPUT.json")
    validate_rt(rt_output, source_manifest)
    frozen = read_json(run_root / "RT_FROZEN_STATE.json")
    frozen_core = dict(frozen)
    frozen_hash = frozen_core.pop("frozen_rt_state_hash", None)
    if frozen_hash != sha256_json(frozen_core):
        raise prior.TwoFrankieBlindError("frozen RT state hash drift")
    if frozen.get("full_validated_rt_output") != rt_output:
        raise prior.TwoFrankieBlindError("frozen RT state no longer contains the exact RT output")
    if frozen.get("rt_output_hash") != sha256_json(rt_output):
        raise prior.TwoFrankieBlindError("frozen RT output hash drift")
    rt_packet = read_json(packet_root / "RT_WORK_PACKET.json")
    if frozen.get("source_manifest_hash") != source_manifest.get("manifest_hash"):
        raise prior.TwoFrankieBlindError("frozen RT source-manifest binding drift")
    if frozen.get("rt_packet_hash") != rt_packet.get("packet_hash"):
        raise prior.TwoFrankieBlindError("frozen RT packet binding drift")

    context = read_json(run_root / "RT_CONTEXT_MANIFEST.json")
    agent = read_json(run_root / "RT_AGENT_RECEIPT.json")
    lock = read_json(run_root / "RT_FIRST_LOCK.json")
    handoff = read_json(run_root / "ONEWAY_HANDOFF.json")
    freeze_complete = read_json(run_root / "RT_FREEZE_COMPLETE.json")
    for value in (context, agent, lock, handoff, freeze_complete):
        verify_self_hash(value)
    if context.get("packet_hash") != rt_packet.get("packet_hash"):
        raise prior.TwoFrankieBlindError("RT context packet binding drift")
    if context.get("source_manifest_hash") != source_manifest.get("manifest_hash"):
        raise prior.TwoFrankieBlindError("RT context source-manifest binding drift")
    if (
        agent.get("role") != FrankieRole.REAL_TIME.value
        or agent.get("logical_call_index") != 1
        or agent.get("model_requested") != prior.MODEL
    ):
        raise prior.TwoFrankieBlindError("RT agent identity receipt drift")
    if agent.get("input_sha256") != sha256_file(packet_root / "RT_WORK_PACKET.json"):
        raise prior.TwoFrankieBlindError("RT agent input receipt drift")
    if agent.get("output_sha256") != sha256_file(run_root / "RT_OUTPUT.json"):
        raise prior.TwoFrankieBlindError("RT agent output receipt drift")
    if agent.get("accepted_output_hash") != sha256_json(rt_output):
        raise prior.TwoFrankieBlindError("RT accepted-output receipt drift")
    if lock.get("rt_output_hash") != sha256_json(rt_output):
        raise prior.TwoFrankieBlindError("RT first-lock output binding drift")
    if lock.get("first_lock") != rt_output.get("first_lock"):
        raise prior.TwoFrankieBlindError("RT first lock was mutated")
    if lock.get("exhaustion_events") != rt_output.get("exhaustion_events"):
        raise prior.TwoFrankieBlindError("RT locked event roster was mutated")
    if lock.get("first_lock_owner") != FrankieRole.REAL_TIME.value:
        raise prior.TwoFrankieBlindError("RT first-lock owner drift")
    if handoff.get("frozen_rt_state_hash") != frozen_hash:
        raise prior.TwoFrankieBlindError("one-way handoff frozen-state binding drift")
    if handoff.get("full_validated_rt_output_hash") != sha256_json(rt_output):
        raise prior.TwoFrankieBlindError("one-way handoff RT-output binding drift")
    if handoff.get("forecaster_may_modify_rt_state") is not False:
        raise prior.TwoFrankieBlindError("one-way handoff authority drift")
    if (
        handoff.get("from_role") != FrankieRole.REAL_TIME.value
        or handoff.get("to_role") != FrankieRole.FORECASTER.value
        or handoff.get("rt_frozen_before_forecaster") is not True
    ):
        raise prior.TwoFrankieBlindError("one-way handoff role/order drift")
    if freeze_complete.get("status") != "RT_FROZEN_FORECASTER_PACKET_READY":
        raise prior.TwoFrankieBlindError("RT freeze-complete status drift")
    if freeze_complete.get("frozen_rt_state_hash") != frozen_hash:
        raise prior.TwoFrankieBlindError("RT freeze-complete state hash drift")

    fc_packet = read_json(run_root / "FORECASTER_WORK_PACKET.json")
    fc_packet_core = dict(fc_packet)
    fc_packet_hash = fc_packet_core.pop("packet_hash", None)
    if fc_packet_hash != sha256_json(fc_packet_core):
        raise prior.TwoFrankieBlindError("Forecaster packet hash drift after RT freeze")
    if fc_packet.get("authoritative_frozen_rt_state") != frozen:
        raise prior.TwoFrankieBlindError("Forecaster packet frozen RT state was mutated")
    if fc_packet.get("authoritative_frozen_rt_state_hash") != frozen_hash:
        raise prior.TwoFrankieBlindError("Forecaster packet frozen RT hash drift")
    if freeze_complete.get("forecaster_packet_hash") != fc_packet_hash:
        raise prior.TwoFrankieBlindError("RT freeze-complete Forecaster packet binding drift")
    if anchor.get("frozen_rt_state_hash") != frozen_hash:
        raise prior.TwoFrankieBlindError("external RT freeze state binding drift")
    if anchor.get("forecaster_packet_hash") != fc_packet_hash:
        raise prior.TwoFrankieBlindError("external RT freeze packet binding drift")
    budget = fc_packet.get("final_principal_packet_token_budget")
    if not isinstance(budget, dict):
        raise prior.TwoFrankieBlindError("Forecaster final packet token budget is absent")
    estimated = math.ceil(len(canonical(fc_packet_core)) * TOKEN_ESTIMATE_PER_BYTE)
    if estimated > FORECASTER_INPUT_TOKEN_CAP:
        raise prior.TwoFrankieBlindError("Forecaster final principal packet exceeds 150000 tokens")
    return frozen, fc_packet


def finalize(args: argparse.Namespace) -> None:
    packet_root = args.packet_root
    run_root = args.run_root
    verify_outer_packet(
        packet_root, args.packet_archive, args.packet_sha256, args.stage_identity,
        args.expected_implementation_commit, args.expected_authorization_commit,
        args.expected_launch_commit, args.expected_launch_identity,
    )
    verify_packet_root(packet_root)
    if (run_root / "COMPLETE.json").exists():
        raise prior.TwoFrankieBlindError("run is already complete")
    source_manifest = read_json(packet_root / "SLICE_MANIFEST.json")
    frozen, fc_packet = verify_rt_freeze(
        packet_root, run_root, source_manifest, args.rt_freeze_anchor
    )
    copy_exact_exclusive(
        args.rt_freeze_anchor, run_root / "RT_FREEZE_EXTERNAL_ANCHOR.json"
    )
    output = read_json(args.forecaster_output)
    knowledge_manifest = read_json(
        packet_root / "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json"
    )
    validate_forecaster(
        output, source_manifest, frozen["frozen_rt_state_hash"],
        {
            str(event["event_id"])
            for event in frozen["full_validated_rt_output"]["exhaustion_events"]
        },
        knowledge_manifest,
        (packet_root / "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json").stat().st_size,
        fc_packet,
    )
    helper_calls = int(output["helper_usage"]["invocation_count"])
    request_path = args.forecaster_helper_request
    helper_output_path = args.forecaster_helper_output
    if helper_calls == 1:
        if request_path is None or helper_output_path is None:
            raise prior.TwoFrankieBlindError("invoked Forecaster helper lacks request/output artifacts")
        request = read_json(request_path)
        helper_output = read_json(helper_output_path)
        if request_path.stat().st_size > HELPER_INPUT_BYTE_CAP:
            raise prior.TwoFrankieBlindError("Forecaster helper request exceeds its input cap")
        if helper_output_path.stat().st_size > HELPER_OUTPUT_BYTE_CAP:
            raise prior.TwoFrankieBlindError("Forecaster helper output exceeds its output cap")
        if set(request) != {
            "schema", "task", "allowed_input_files", "allowed_input_hashes",
            "selected_source_paths", "selected_source_bytes", "estimated_input_tokens",
            "model_visible_input_files",
            "causal_cutoff", "no_recursion", "no_specialists", "no_step1_answers",
        }:
            raise prior.TwoFrankieBlindError("Forecaster helper request contract drift")
        allowed_files = {
            "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
            "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
            "RT_FROZEN_STATE.json",
            "ONEWAY_HANDOFF.json",
        }
        if set(request["allowed_input_files"]) != allowed_files:
            raise prior.TwoFrankieBlindError("Forecaster helper input allowlist drift")
        expected_hashes = {
            "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz": sha256_file(
                packet_root / "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz"
            ),
            "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json": sha256_file(
                packet_root / "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json"
            ),
            "RT_FROZEN_STATE.json": sha256_file(run_root / "RT_FROZEN_STATE.json"),
            "ONEWAY_HANDOFF.json": sha256_file(run_root / "ONEWAY_HANDOFF.json"),
        }
        if request.get("allowed_input_hashes") != expected_hashes:
            raise prior.TwoFrankieBlindError("Forecaster helper input hashes drift")
        if set(request.get("model_visible_input_files") or []) != {
            "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
            "RT_FROZEN_STATE.json",
            "ONEWAY_HANDOFF.json",
        }:
            raise prior.TwoFrankieBlindError("Forecaster helper model-visible file roster drift")
        if request.get("causal_cutoff") != frozen.get("as_of"):
            raise prior.TwoFrankieBlindError("Forecaster helper causal cutoff drift")
        selected = request.get("selected_source_paths")
        if not isinstance(selected, list) or len(selected) != len(set(selected)):
            raise prior.TwoFrankieBlindError("Forecaster helper selected-source roster drift")
        lawful_sizes = {
            row["path"]: row["retrieval_payload_bytes"]
            for row in knowledge_manifest.get("lawful_content_sources", [])
        }
        if not set(selected).issubset(lawful_sizes):
            raise prior.TwoFrankieBlindError("Forecaster helper selected a non-lawful source")
        selected_bytes = sum(int(lawful_sizes[path]) for path in selected)
        if request.get("selected_source_bytes") != selected_bytes:
            raise prior.TwoFrankieBlindError("Forecaster helper selected-source bytes drift")
        estimated_helper_tokens = math.ceil(
            (
                selected_bytes
                + (packet_root / "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json").stat().st_size
                + (run_root / "RT_FROZEN_STATE.json").stat().st_size
                + (run_root / "ONEWAY_HANDOFF.json").stat().st_size
                + request_path.stat().st_size
            )
            * TOKEN_ESTIMATE_PER_BYTE
        )
        if (
            estimated_helper_tokens > HELPER_INPUT_TOKEN_CAP
            or request.get("estimated_input_tokens") != estimated_helper_tokens
        ):
            raise prior.TwoFrankieBlindError("Forecaster helper input token ceiling drift")
        if request.get("no_recursion") is not True or request.get("no_specialists") is not True:
            raise prior.TwoFrankieBlindError("Forecaster helper recursion/specialist guard drift")
        if request.get("no_step1_answers") is not True:
            raise prior.TwoFrankieBlindError("Forecaster helper answer wall drift")
        if set(helper_output) != {
            "schema", "findings", "sources_consulted", "uninspected_sources",
            "authority_notes", "causal_cutoff", "answer_wall_crossed", "forecast_owned",
        }:
            raise prior.TwoFrankieBlindError("Forecaster helper output contract drift")
        if helper_output.get("schema") != "FRANKIE_FORECASTER_KNOWLEDGE_HELPER_V1_20260825":
            raise prior.TwoFrankieBlindError("Forecaster helper output schema drift")
        if helper_output.get("causal_cutoff") != frozen.get("as_of"):
            raise prior.TwoFrankieBlindError("Forecaster helper output cutoff drift")
        if helper_output.get("answer_wall_crossed") is not False:
            raise prior.TwoFrankieBlindError("Forecaster helper crossed the answer wall")
        if helper_output.get("forecast_owned") is not False:
            raise prior.TwoFrankieBlindError("Forecaster helper claimed forecast ownership")
        if not set(helper_output.get("sources_consulted") or []).issubset(set(selected)):
            raise prior.TwoFrankieBlindError("Forecaster helper consulted an unselected source")
        helper_consulted = helper_output.get("sources_consulted")
        helper_uninspected = helper_output.get("uninspected_sources")
        if (
            not isinstance(helper_consulted, list)
            or not isinstance(helper_uninspected, list)
            or len(helper_consulted) != len(set(helper_consulted))
            or len(helper_uninspected) != len(set(helper_uninspected))
            or set(helper_consulted) & set(helper_uninspected)
            or set(helper_consulted) | set(helper_uninspected) != set(selected)
        ):
            raise prior.TwoFrankieBlindError("Forecaster helper knowledge coverage drift")
        if not isinstance(helper_output.get("findings"), list) or not isinstance(
            helper_output.get("authority_notes"), list
        ):
            raise prior.TwoFrankieBlindError("Forecaster helper findings/authority notes drift")
        helper_finding_ids: list[str] = []
        for finding in helper_output["findings"]:
            if not isinstance(finding, dict) or not {
                "finding_id", "claim", "source_paths", "authority", "uncertainty"
            }.issubset(finding):
                raise prior.TwoFrankieBlindError("Forecaster helper finding shape drift")
            finding_id = finding.get("finding_id")
            if not isinstance(finding_id, str) or not finding_id.strip():
                raise prior.TwoFrankieBlindError("Forecaster helper finding identity drift")
            if not isinstance(finding.get("source_paths"), list) or not set(
                finding["source_paths"]
            ).issubset(set(helper_consulted)):
                raise prior.TwoFrankieBlindError("Forecaster helper finding source drift")
            helper_finding_ids.append(finding_id)
        if len(helper_finding_ids) != len(set(helper_finding_ids)):
            raise prior.TwoFrankieBlindError("Forecaster helper finding identities are duplicated")
        used_refs = output["helper_usage"]["helper_evidence_refs"]
        if any(not isinstance(ref, str) or not ref.strip() for ref in used_refs):
            raise prior.TwoFrankieBlindError("Forecaster helper citation identity is invalid")
        if not set(used_refs).issubset(set(helper_finding_ids)):
            raise prior.TwoFrankieBlindError("Forecaster helper citations do not match findings")
        if output["helper_usage"]["advisory_findings_used"] and not used_refs:
            raise prior.TwoFrankieBlindError("Forecaster used helper evidence without exact findings")
        request_hash = sha256_file(request_path)
        helper_hash = sha256_file(helper_output_path)
        if output["helper_usage"]["helper_request_hash"] != request_hash:
            raise prior.TwoFrankieBlindError("Forecaster helper request hash mismatch")
        if output["helper_usage"]["helper_response_hash"] != helper_hash:
            raise prior.TwoFrankieBlindError("Forecaster helper response hash mismatch")
        copy_exact_exclusive(request_path, run_root / "FORECASTER_HELPER_REQUEST.json")
        copy_exact_exclusive(helper_output_path, run_root / "FORECASTER_HELPER_OUTPUT.json")
    elif request_path is not None or helper_output_path is not None:
        raise prior.TwoFrankieBlindError("unused Forecaster helper has stray artifacts")
    copied_output = run_root / "FORECASTER_OUTPUT.json"
    write_json(copied_output, output)
    context = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FORECASTER_CONTEXT_MANIFEST_V2_WORKMODE_20260825",
        "role": FrankieRole.FORECASTER.value,
        "packet_hash": fc_packet["packet_hash"],
        "source_manifest_hash": source_manifest["manifest_hash"],
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "answer_wall": "SEALED",
        "provider_api_called": False,
        "forecaster_optional_helper_available": True,
        "forecaster_optional_helper_calls": helper_calls,
        "complete_registry_direct_no_dormant": True,
    }
    context["receipt_hash"] = sha256_json(context)
    write_json(run_root / "FORECASTER_CONTEXT_MANIFEST.json", context)
    write_json(
        run_root / "FORECASTER_AGENT_RECEIPT.json",
        agent_receipt(
            role=FrankieRole.FORECASTER.value,
            index=2,
            input_path=run_root / "FORECASTER_WORK_PACKET.json",
            output_path=copied_output,
            output=output,
            helper_calls=helper_calls,
        ),
    )
    lock = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_FORECASTER_LOCK_V2_WORKMODE_20260825",
        "lock_type": "ADVISORY_FORECAST_LOCK_DOES_NOT_MUTATE_RT_FIRST_LOCK",
        "forecaster_output_hash": sha256_json(output),
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "forecast_curve_hash": sha256_json(output["forecast_curve"]),
    }
    lock["receipt_hash"] = sha256_json(lock)
    write_json(run_root / "FORECASTER_FIRST_LOCK.json", lock)
    usage = {
        "schema": "FRANKIE_WORKMODE_EXECUTION_USAGE_V1_20260825",
        "principal_role_call_count": 2,
        "conditional_forecaster_helper_call_count": helper_calls,
        "total_model_call_count": 2 + helper_calls,
        "role_sequence": [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value],
        "model_requested_for_each": prior.MODEL,
        "provider_api_called": False,
        "openai_key_used": False,
        "cli_model_called": False,
        "provider_token_usage": "NOT_AVAILABLE_FOR_WORKMODE_AGENT_CALLS",
        "provider_api_cost_usd": "NOT_APPLICABLE_NO_PROVIDER_API_CALL",
        "repair_calls": 0,
        "fallback_calls": 0,
        "specialist_calls": 0,
        "optional_forecaster_helper_calls": helper_calls,
    }
    usage["receipt_hash"] = sha256_json(usage)
    write_json(run_root / "EXECUTION_USAGE.json", usage)
    artifacts = []
    for path in sorted(run_root.iterdir()):
        if path.is_file():
            artifacts.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_WORKMODE_RUN_MANIFEST_V1_20260825",
        "artifacts": artifacts,
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "forecaster_output_hash": sha256_json(output),
    }
    manifest["receipt_hash"] = sha256_json(manifest)
    write_json(run_root / "ARTIFACT_MANIFEST.json", manifest)
    complete = {
        "schema": "NG_EXHAUSTION_TWO_FRANKIES_WORKMODE_COMPLETE_V1_20260825",
        "status": "COMPLETE",
        "published_last": True,
        "model": prior.MODEL,
        "principal_role_call_count": 2,
        "conditional_forecaster_helper_call_count": helper_calls,
        "total_model_call_count": 2 + helper_calls,
        "principal_role_call_order": [FrankieRole.REAL_TIME.value, FrankieRole.FORECASTER.value],
        "study_design": "ANSWER_KEY_BLIND_RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION",
        "rt_role_is_forecasting": False,
        "forecaster_curve_hash": sha256_json(output["forecast_curve"]),
        "frozen_rt_state_hash": frozen["frozen_rt_state_hash"],
        "answer_key_or_step1_results_exposed": False,
        "external_provider_api_called": False,
        "openai_key_used": False,
        "cli_model_called": False,
        "automatic_helpers": 0,
        "optional_forecaster_helper_calls": helper_calls,
        "specialist_calls": 0,
        "canary": False,
        "tests": False,
        "manifest_receipt_hash": manifest["receipt_hash"],
    }
    complete["receipt_hash"] = sha256_json(complete)
    write_json(run_root / "COMPLETE.json", complete)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    rt = sub.add_parser("freeze-rt")
    rt.add_argument("--packet-root", type=Path, required=True)
    rt.add_argument("--packet-archive", type=Path, required=True)
    rt.add_argument("--packet-sha256", type=Path, required=True)
    rt.add_argument("--stage-identity", type=Path, required=True)
    rt.add_argument("--expected-implementation-commit", required=True)
    rt.add_argument("--expected-authorization-commit", required=True)
    rt.add_argument("--expected-launch-commit", required=True)
    rt.add_argument("--expected-launch-identity", required=True)
    rt.add_argument("--rt-output", type=Path, required=True)
    rt.add_argument("--rt-scout-request", type=Path)
    rt.add_argument("--rt-scout-output", type=Path)
    rt.add_argument("--run-root", type=Path, required=True)
    rt.add_argument("--rt-freeze-anchor-output", type=Path, required=True)
    fc = sub.add_parser("finalize")
    fc.add_argument("--packet-root", type=Path, required=True)
    fc.add_argument("--packet-archive", type=Path, required=True)
    fc.add_argument("--packet-sha256", type=Path, required=True)
    fc.add_argument("--stage-identity", type=Path, required=True)
    fc.add_argument("--expected-implementation-commit", required=True)
    fc.add_argument("--expected-authorization-commit", required=True)
    fc.add_argument("--expected-launch-commit", required=True)
    fc.add_argument("--expected-launch-identity", required=True)
    fc.add_argument("--run-root", type=Path, required=True)
    fc.add_argument("--rt-freeze-anchor", type=Path, required=True)
    fc.add_argument("--forecaster-output", type=Path, required=True)
    fc.add_argument("--forecaster-helper-request", type=Path)
    fc.add_argument("--forecaster-helper-output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "freeze-rt":
            freeze_rt(args)
        else:
            finalize(args)
    except prior.TwoFrankieBlindError as exc:
        print(f"WORKMODE_COORDINATE=FAIL: {exc}", file=sys.stderr)
        return 2
    print("WORKMODE_COORDINATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
