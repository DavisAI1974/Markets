#!/usr/bin/env python3
"""Consolidate the counterfactual-lineage historical-first NG refinement chain.

Readiness v3 makes the deterministic G15 full-minus-neutral attribution and lesson
lineage mandatory before the exact prepared G16 posterior, refined curve, fixed
scoring, and publication may be considered complete. It is observational only: it
never invents remote objects, reads outcome files itself, mutates blind forecasts or
``ng_brain.json``, grants execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "ng_historical_refinement_readiness.v3"


class HistoricalRefinementReadinessError(ValueError):
    """Raised when the consolidated readiness report is internally inconsistent."""


@dataclass(frozen=True)
class StageSpec:
    key: str
    filename: str
    schema: str
    fingerprint_field: str
    ready_statuses: frozenset[str]
    validator_module: str | None
    validator_names: tuple[str, ...]
    next_action: str
    required_fields: tuple[str, ...] = ()
    pre_outcome: bool = True


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        "corpus_coverage", "ng_corpus_coverage_audit.json",
        "ng_corpus_coverage_audit.v1", "fingerprint",
        frozenset({"FULL_CORPUS_AND_G15_G16_EXACT_READY", "G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED"}),
        "ng_corpus_coverage_audit", ("validate_audit",),
        "Inspect and inventory the one-year L1/dense-trades and spring/summer MBO objects; keep uninspected objects UNKNOWN.",
    ),
    StageSpec(
        "basis_inventory_regeneration", "ng_corpus_basis_inventory_regeneration.json",
        "ng_corpus_basis_inventory_regeneration.v1", "fingerprint",
        frozenset({"G15_G16_BASIS_INVENTORIES_READY", "G15_G16_BASIS_INVENTORIES_READY_WITH_QUEUE_STAND_DOWNS"}),
        None, (),
        "Regenerate exact daily G15/G16 basis inventories from inspected target-day shard bytes; never reuse cumulative counts.",
    ),
    StageSpec(
        "replay_catalog_export", "ng_exact_replay_catalog_export.json",
        "ng_corpus_replay_catalog_export.v1", "fingerprint", frozenset({"READY"}),
        "ng_corpus_replay_catalog_export", ("validate_export_bundle",),
        "Export deterministic exact G15/G16 pairs into canonical replay catalogs.",
    ),
    StageSpec(
        "g15_exact_replay", "g15_exact_replay_completion.json",
        "ng_g15_exact_replay_completion.v1", "completion_fingerprint",
        frozenset({"EXACT_CAUSAL_REPLAY_READY", "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS"}),
        "ng_g15_exact_replay_completion", ("validate_completion",),
        "Prepare and replay all 26 exact G15 sources through the live-causal path.",
    ),
    StageSpec(
        "g15_exact_refinement", "g15_exact_refinement_authorization.json",
        "ng_g15_exact_refinement_authorization.v1", "authorization_fingerprint",
        frozenset({"EXACT_G15_REFINEMENT_READY", "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS"}),
        "ng_g15_exact_refinement_gate", ("validate_authorization",),
        "Run the outcome-blind G15 posterior pipeline bound to exact replay.",
    ),
    StageSpec(
        "g15_counterfactual_attribution", "g15_counterfactual_attribution.json",
        "ng_g15_counterfactual_attribution.v1", "fingerprint",
        frozenset({"READY", "READY_WITH_STAND_DOWNS"}),
        None, (),
        "Reproduce every G15 posterior and quantify onset, signed flow, divergence/exhaustion, queue, price-efficiency, and activity effects before scoring.",
        required_fields=("replay_fingerprint", "anchor_fingerprint", "refine_stream_fingerprint"),
    ),
    StageSpec(
        "g15_publication", "g15_exact_publication_completion.json",
        "ng_g15_exact_publication_completion.v1", "completion_fingerprint",
        frozenset({"EXACT_G15_PUBLICATION_COMPLETE", "EXACT_G15_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"}),
        "ng_g15_exact_publication_gate", ("validate_completion",),
        "Lock and render G15 and score blind/refined separately without rewriting ng_brain.json.",
        pre_outcome=False,
    ),
    StageSpec(
        "g15_counterfactual_lesson_gate", "g15_counterfactual_lesson_gate.json",
        "ng_g15_counterfactual_lesson_gate.v1", "fingerprint",
        frozenset({"G15_COUNTERFACTUAL_LESSONS_ADJUDICATED", "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED_WITH_STAND_DOWNS"}),
        None, (),
        "Adjudicate only the support days fixed by outcome-blind G15 counterfactual rows; preserve the no-brain-write contract.",
        required_fields=("source.counterfactual_fingerprint", "source.adjudication_fingerprint", "source.registry_fingerprint"),
    ),
    StageSpec(
        "g15_g16_counterfactual_lineage", "g15_g16_counterfactual_lineage_gate.json",
        "ng_g15_g16_counterfactual_lineage_gate.v1", "fingerprint",
        frozenset({"G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND", "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND_WITH_STAND_DOWNS"}),
        None, (),
        "Bind G15 publication and every pre-cutoff G16 candidate to the exact counterfactual lesson gate.",
        required_fields=("counterfactual_lesson_gate_fingerprint", "counterfactual_attribution_fingerprint", "g15_publication_fingerprint", "g16_plan_fingerprint"),
    ),
    StageSpec(
        "g16_corpus_basis", "g16_corpus_basis_report.json",
        "ng_g16_corpus_basis_gate.v1", "fingerprint", frozenset({"MATCHED_L1_MBO_READY"}),
        "ng_g16_corpus_basis_gate", ("validate_report",),
        "Verify exact NGK26/996 L1 and MBO basis for every canonical G16 session.",
    ),
    StageSpec(
        "g16_historical_replay", "g16_historical_replay.json",
        "ng_g16_historical_replay.v1", "fingerprint", frozenset({"READY", "READY_WITH_STAND_DOWNS"}),
        "ng_g16_historical_replay", ("validate_replay_output",),
        "Prepare the 23-source exact NGK26 corpus and replay chronologically through the live-causal path.",
    ),
    StageSpec(
        "g16_prepared_replay", "g16_prepared_replay_gate.json",
        "ng_g16_prepared_replay_gate.v1", "fingerprint",
        frozenset({"EXACT_G16_PREPARED_REPLAY_READY", "EXACT_G16_PREPARED_REPLAY_READY_WITH_STAND_DOWNS"}),
        None, (),
        "Validate all 23 prepared-source hashes, raw lineage, completed MBO boundaries, and visible sequence-gap stand-downs.",
        required_fields=("replay_fingerprint", "manifest_fingerprint", "prepared_corpus_fingerprint", "blind_prior_fingerprint"),
    ),
    StageSpec(
        "g16_exact_causal", "g16_exact_causal_pipeline.json",
        "ng_g16_exact_causal_pipeline.v1", "fingerprint", frozenset({"READY", "READY_WITH_STAND_DOWNS"}),
        None, (),
        "Run the pre-cutoff G16 posterior chain using only pre-registered G15 lessons.",
    ),
    StageSpec(
        "g16_prepared_causal_authorization", "g16_prepared_causal_authorization.json",
        "ng_g16_prepared_causal_authorization.v1", "fingerprint",
        frozenset({"EXACT_G16_PREPARED_CAUSAL_AUTHORIZED", "EXACT_G16_PREPARED_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"}),
        None, (),
        "Bind the pre-cutoff posterior to the exact 23-source prepared replay and immutable G16 blind prior.",
        required_fields=("prepared_replay_gate_fingerprint", "replay_fingerprint", "causal_pipeline_fingerprint"),
    ),
    StageSpec(
        "g16_counterfactual_causal_authorization", "g16_counterfactual_causal_authorization.json",
        "ng_g16_counterfactual_causal_authorization.v1", "fingerprint",
        frozenset({"G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED", "G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"}),
        None, (),
        "Require the exact G15 counterfactual lineage inside the prepared pre-cutoff G16 posterior authorization.",
        required_fields=("counterfactual_lineage_gate_fingerprint", "counterfactual_lesson_gate_fingerprint", "prepared_causal_authorization_fingerprint", "replay_fingerprint"),
    ),
    StageSpec(
        "g16_prepared_curve_authorization", "g16_prepared_curve_authorization.json",
        "ng_g16_prepared_curve_authorization.v1", "fingerprint",
        frozenset({"EXACT_G16_PREPARED_CURVE_AUTHORIZED", "EXACT_G16_PREPARED_CURVE_AUTHORIZED_WITH_STAND_DOWNS"}),
        None, (),
        "Reproduce the outcome-blind refined curve deterministically from the authorized posterior stream.",
        required_fields=("prepared_causal_authorization_fingerprint", "prepared_replay_gate_fingerprint", "replay_fingerprint", "refined_curve_fingerprint"),
    ),
    StageSpec(
        "g16_counterfactual_curve_authorization", "g16_counterfactual_curve_authorization.json",
        "ng_g16_counterfactual_curve_authorization.v1", "fingerprint",
        frozenset({"G16_COUNTERFACTUAL_CURVE_AUTHORIZED", "G16_COUNTERFACTUAL_CURVE_AUTHORIZED_WITH_STAND_DOWNS"}),
        None, (),
        "Require the counterfactual causal lineage inside the deterministic outcome-blind G16 curve authorization.",
        required_fields=("counterfactual_causal_authorization_fingerprint", "prepared_curve_authorization_fingerprint", "refined_curve_fingerprint"),
    ),
    StageSpec(
        "g16_counterfactual_curve_lock", "g16_counterfactual_curve_lock.json",
        "ng_g16_counterfactual_curve_lock.v1", "lock_fingerprint",
        frozenset({"EXACT_G16_COUNTERFACTUAL_CURVE_LOCKED"}),
        None, (),
        "Persist the exact refined curve and G15 counterfactual lineage before opening the fixed G16 outcome substrate.",
        required_fields=("counterfactual_curve_authorization_fingerprint", "counterfactual_causal_authorization_fingerprint", "prepared_curve_authorization_fingerprint", "prepared_curve_lock_fingerprint", "replay_fingerprint"),
    ),
    StageSpec(
        "g16_counterfactual_publication", "g16_counterfactual_publication_completion.json",
        "ng_g16_counterfactual_publication_completion.v1", "completion_fingerprint",
        frozenset({"EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE", "EXACT_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"}),
        None, (),
        "Score the fixed G16 holdout, validate chronology, render both paths, and preserve counterfactual lesson lineage through publication.",
        required_fields=("counterfactual_curve_lock_fingerprint", "counterfactual_curve_authorization_fingerprint", "counterfactual_causal_authorization_fingerprint", "prepared_publication_completion_fingerprint", "replay_fingerprint"),
        pre_outcome=False,
    ),
)

# source stage, source fingerprint path, target stage, target provenance path
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("g15_counterfactual_attribution", "fingerprint", "g15_counterfactual_lesson_gate", "source.counterfactual_fingerprint"),
    ("g15_counterfactual_attribution", "fingerprint", "g15_g16_counterfactual_lineage", "counterfactual_attribution_fingerprint"),
    ("g15_counterfactual_lesson_gate", "fingerprint", "g15_g16_counterfactual_lineage", "counterfactual_lesson_gate_fingerprint"),
    ("g15_publication", "completion_fingerprint", "g15_g16_counterfactual_lineage", "g15_publication_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_prepared_replay", "replay_fingerprint"),
    ("g16_prepared_replay", "fingerprint", "g16_prepared_causal_authorization", "prepared_replay_gate_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_prepared_causal_authorization", "replay_fingerprint"),
    ("g16_exact_causal", "fingerprint", "g16_prepared_causal_authorization", "causal_pipeline_fingerprint"),
    ("g15_g16_counterfactual_lineage", "fingerprint", "g16_counterfactual_causal_authorization", "counterfactual_lineage_gate_fingerprint"),
    ("g15_counterfactual_lesson_gate", "fingerprint", "g16_counterfactual_causal_authorization", "counterfactual_lesson_gate_fingerprint"),
    ("g15_counterfactual_attribution", "fingerprint", "g16_counterfactual_causal_authorization", "counterfactual_attribution_fingerprint"),
    ("g15_publication", "completion_fingerprint", "g16_counterfactual_causal_authorization", "g15_publication_fingerprint"),
    ("g16_prepared_causal_authorization", "fingerprint", "g16_counterfactual_causal_authorization", "prepared_causal_authorization_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_counterfactual_causal_authorization", "replay_fingerprint"),
    ("g16_prepared_causal_authorization", "fingerprint", "g16_prepared_curve_authorization", "prepared_causal_authorization_fingerprint"),
    ("g16_prepared_replay", "fingerprint", "g16_prepared_curve_authorization", "prepared_replay_gate_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_prepared_curve_authorization", "replay_fingerprint"),
    ("g16_counterfactual_causal_authorization", "fingerprint", "g16_counterfactual_curve_authorization", "counterfactual_causal_authorization_fingerprint"),
    ("g16_prepared_curve_authorization", "fingerprint", "g16_counterfactual_curve_authorization", "prepared_curve_authorization_fingerprint"),
    ("g16_counterfactual_curve_authorization", "fingerprint", "g16_counterfactual_curve_lock", "counterfactual_curve_authorization_fingerprint"),
    ("g16_counterfactual_causal_authorization", "fingerprint", "g16_counterfactual_curve_lock", "counterfactual_causal_authorization_fingerprint"),
    ("g16_prepared_curve_authorization", "fingerprint", "g16_counterfactual_curve_lock", "prepared_curve_authorization_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_counterfactual_curve_lock", "replay_fingerprint"),
    ("g16_counterfactual_curve_lock", "lock_fingerprint", "g16_counterfactual_publication", "counterfactual_curve_lock_fingerprint"),
    ("g16_counterfactual_curve_authorization", "fingerprint", "g16_counterfactual_publication", "counterfactual_curve_authorization_fingerprint"),
    ("g16_counterfactual_causal_authorization", "fingerprint", "g16_counterfactual_publication", "counterfactual_causal_authorization_fingerprint"),
    ("g15_g16_counterfactual_lineage", "fingerprint", "g16_counterfactual_publication", "counterfactual_lineage_gate_fingerprint"),
    ("g15_counterfactual_lesson_gate", "fingerprint", "g16_counterfactual_publication", "counterfactual_lesson_gate_fingerprint"),
    ("g15_counterfactual_attribution", "fingerprint", "g16_counterfactual_publication", "counterfactual_attribution_fingerprint"),
    ("g15_publication", "completion_fingerprint", "g16_counterfactual_publication", "g15_publication_fingerprint"),
    ("g16_historical_replay", "fingerprint", "g16_counterfactual_publication", "replay_fingerprint"),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HistoricalRefinementReadinessError(f"cannot read JSON artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise HistoricalRefinementReadinessError(f"artifact must be a JSON object: {path}")
    return value


def _path_get(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _path_set(value: dict[str, Any], path: str, item: Any) -> None:
    parts = path.split(".")
    current: dict[str, Any] = value
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = item


def _validate_stage_authority(value: Mapping[str, Any], spec: StageSpec) -> None:
    for field in ("random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started", "options_implementation_authorized"):
        if field in value and value.get(field) is not False:
            raise HistoricalRefinementReadinessError(f"{spec.key}: {field} must remain false")
    for field in ("one_signal_authority_preserved", "blind_forecast_immutable", "blind_forecasts_immutable"):
        if field in value and value.get(field) is not True:
            raise HistoricalRefinementReadinessError(f"{spec.key}: {field} must remain true")
    if "cme_event_contracts_mode" in value and value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError(f"{spec.key}: CME event contracts must remain SHADOW")
    if "brokerage_contract" in value and value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(f"{spec.key}: brokerage must remain tastytrade, not IBKR")
    if spec.pre_outcome:
        for field in ("actual_outcomes_used", "actual_g16_outcomes_used", "actual_outcome_paths_loaded"):
            if field in value and value.get(field) is not False:
                raise HistoricalRefinementReadinessError(f"{spec.key}: pre-outcome stage claims {field}=true")


def _generic_validate(value: Mapping[str, Any], spec: StageSpec) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(spec.fingerprint_field, None)
    if candidate.get("schema") != spec.schema:
        raise HistoricalRefinementReadinessError(f"{spec.key}: schema {candidate.get('schema')!r} != {spec.schema!r}")
    if not isinstance(observed, str) or observed != _fingerprint(candidate):
        raise HistoricalRefinementReadinessError(f"{spec.key}: {spec.fingerprint_field} mismatch")
    missing = [field for field in spec.required_fields if not _path_get(candidate, field)]
    if missing:
        raise HistoricalRefinementReadinessError(f"{spec.key}: required provenance missing: {', '.join(missing)}")
    _validate_stage_authority(candidate, spec)


def _resolve_validator(spec: StageSpec) -> Callable[[Mapping[str, Any]], Any] | None:
    if spec.validator_module is None:
        return None
    module = importlib.import_module(spec.validator_module)
    for name in spec.validator_names:
        function = getattr(module, name, None)
        if callable(function):
            return function
    raise HistoricalRefinementReadinessError(f"{spec.key}: canonical validator not found in {spec.validator_module}")


def _extract_blockers(value: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    explicit = {"errors", "blockers", "missing", "missing_days", "unknown_days", "mbo_blocked_days", "l1_blocked_days", "l1_wrong_basis_days", "event_overlap_blocked_days", "definition_blocked_days", "flow_stand_down_days"}

    def visit(node: Any, prefix: str = "") -> None:
        if len(blockers) >= 64:
            return
        if isinstance(node, Mapping):
            for key, item in node.items():
                label = f"{prefix}.{key}" if prefix else str(key)
                lowered = str(key).lower()
                if key in explicit or lowered.endswith("_blocked_days"):
                    if isinstance(item, list):
                        blockers.extend(f"{label}:{entry}" for entry in item if entry not in (None, ""))
                    elif item not in (None, "", False, [], {}):
                        blockers.append(f"{label}:{item}")
                elif lowered in {"status", "availability"} and str(item).upper() in {"UNKNOWN", "MISSING", "CORRUPT", "BLOCKED", "INVALID", "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"}:
                    blockers.append(f"{label}:{item}")
                elif isinstance(item, (Mapping, list)):
                    visit(item, label)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                if isinstance(item, (Mapping, list)):
                    visit(item, f"{prefix}[{index}]")

    visit(value)
    return sorted(dict.fromkeys(blockers))[:64]


def _stand_downs(value: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for name in ("stand_down_days", "queue_stand_down_days", "all_stand_down_days", "flow_stand_down_days", "lineage_stand_down_days", "prepared_causal_stand_down_days"):
        result.extend(str(day) for day in value.get(name) or [])
    days = value.get("days")
    iterable = days.values() if isinstance(days, Mapping) else days if isinstance(days, list) else []
    for row in iterable:
        if not isinstance(row, Mapping):
            continue
        reasons = row.get("stand_down_reasons") or []
        if isinstance(reasons, Mapping):
            reasons = [key for key, count in reasons.items() if count]
        if reasons:
            result.append(str(row.get("date") or row.get("day") or "UNKNOWN_DAY"))
    return sorted(set(result))


def _broad_corpus_verified(coverage: Mapping[str, Any] | None) -> bool:
    if not coverage:
        return False
    if coverage.get("status") == "FULL_CORPUS_AND_G15_G16_EXACT_READY":
        return True
    broad = coverage.get("broad_coverage") or coverage.get("corpora") or {}
    if isinstance(broad, Mapping):
        booleans = [item for key, item in broad.items() if "complete" in str(key).lower() or "verified" in str(key).lower()]
        return bool(booleans) and all(item is True for item in booleans)
    return False


def evaluate_stage(spec: StageSpec, path: Path, *, validator_override: Callable[[Mapping[str, Any]], Any] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row: dict[str, Any] = {
        "key": spec.key, "path": str(path), "artifact_present": path.is_file(),
        "artifact_status": None, "validation": "NOT_RUN", "effective_status": "MISSING",
        "stand_down_days": [], "blockers": [], "next_action": spec.next_action,
    }
    if not path.is_file():
        row["blockers"] = ["artifact_missing"]
        return row, None
    try:
        value = _load_json(path)
        _generic_validate(value, spec)
        validator = validator_override if validator_override is not None else _resolve_validator(spec)
        if validator is not None:
            validator(copy.deepcopy(value))
        row["validation"] = "PASS"
        row["artifact_status"] = str(value.get("status") or "")
        row["artifact_fingerprint"] = value.get(spec.fingerprint_field)
        row["stand_down_days"] = _stand_downs(value)
        row["blockers"] = _extract_blockers(value)
        if row["artifact_status"] in spec.ready_statuses:
            row["effective_status"] = "READY_WITH_STAND_DOWNS" if row["stand_down_days"] else "READY"
        elif row["artifact_status"].upper() in {"UNKNOWN", "UNVERIFIED"}:
            row["effective_status"] = "UNVERIFIED"
        else:
            row["effective_status"] = "BLOCKED"
        return row, value
    except Exception as error:
        row["validation"] = "FAIL"
        row["effective_status"] = "INVALID"
        row["blockers"] = [str(error)]
        return row, None


def _apply_link_rules(rows: list[dict[str, Any]], values: Mapping[str, Mapping[str, Any]]) -> None:
    row_by_key = {row["key"]: row for row in rows}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        source = values.get(source_key)
        target = values.get(target_key)
        if source is None or target is None:
            continue
        expected = _path_get(source, source_path)
        observed = _path_get(target, target_path)
        if not expected or observed != expected:
            row = row_by_key[target_key]
            row["validation"] = "FAIL"
            row["effective_status"] = "INVALID"
            row["blockers"] = sorted(set(row.get("blockers") or []) | {f"provenance link mismatch: {target_path} != {source_key}.{source_path}"})


def build_readiness_report(artifact_dir: Path, *, stage_paths: Mapping[str, Path] | None = None, validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None) -> dict[str, Any]:
    stage_paths = dict(stage_paths or {})
    validator_overrides = dict(validator_overrides or {})
    rows: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {}
    for spec in STAGES:
        path = stage_paths.get(spec.key, artifact_dir / spec.filename)
        row, value = evaluate_stage(spec, path, validator_override=validator_overrides.get(spec.key))
        rows.append(row)
        if value is not None:
            values[spec.key] = value
    _apply_link_rules(rows, values)
    upstream_ready = True
    for row in rows:
        artifact_ready = row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}
        if artifact_ready and not upstream_ready:
            row["effective_status"] = "BLOCKED_BY_UPSTREAM"
            row["blockers"] = sorted(set(row["blockers"] + ["an earlier stage is not ready"]))
        upstream_ready = upstream_ready and artifact_ready

    first_blocking = next((row for row in rows if row["effective_status"] not in {"READY", "READY_WITH_STAND_DOWNS"}), None)
    ready_keys = [row["key"] for row in rows if row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}]
    g15_complete = "g15_counterfactual_lesson_gate" in ready_keys
    g16_complete = "g16_counterfactual_publication" in ready_keys
    if g16_complete and len(ready_keys) == len(STAGES):
        overall = "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE"
    elif "g16_counterfactual_curve_lock" in ready_keys:
        overall = "G15_COMPLETE_G16_COUNTERFACTUAL_CURVE_LOCKED_SCORING_INCOMPLETE"
    elif "g16_counterfactual_curve_authorization" in ready_keys:
        overall = "G15_COMPLETE_G16_COUNTERFACTUAL_CURVE_AUTHORIZED_LOCK_INCOMPLETE"
    elif "g16_counterfactual_causal_authorization" in ready_keys:
        overall = "G15_COMPLETE_G16_COUNTERFACTUAL_CAUSAL_AUTHORIZED_CURVE_INCOMPLETE"
    elif "g15_g16_counterfactual_lineage" in ready_keys:
        overall = "G15_COUNTERFACTUAL_LINEAGE_BOUND_G16_REPLAY_INCOMPLETE"
    elif g15_complete:
        overall = "G15_COUNTERFACTUAL_LESSONS_READY_G16_LINEAGE_INCOMPLETE"
    elif "g15_publication" in ready_keys:
        overall = "G15_EXACT_PUBLICATION_COMPLETE_COUNTERFACTUAL_LESSONS_INCOMPLETE"
    elif "g15_counterfactual_attribution" in ready_keys:
        overall = "G15_COUNTERFACTUAL_ATTRIBUTION_READY_SCORING_INCOMPLETE"
    elif "g15_exact_refinement" in ready_keys:
        overall = "G15_EXACT_REFINEMENT_READY_ATTRIBUTION_INCOMPLETE"
    elif "g15_exact_replay" in ready_keys:
        overall = "G15_EXACT_REPLAY_READY_REFINEMENT_INCOMPLETE"
    elif "replay_catalog_export" in ready_keys:
        overall = "EXACT_REPLAY_CATALOG_READY_REPLAY_INCOMPLETE"
    elif "corpus_coverage" in ready_keys:
        overall = "EXACT_INTERSECTIONS_READY_INVENTORY_OR_EXPORT_INCOMPLETE"
    else:
        overall = "BLOCKED_OR_UNVERIFIED"

    report = {
        "schema": SCHEMA,
        "status": overall,
        "market": "NG",
        "historical_first": True,
        "artifact_dir": str(artifact_dir),
        "stage_order": [spec.key for spec in STAGES],
        "stages": rows,
        "ready_stage_count": len(ready_keys),
        "ready_stages": ready_keys,
        "first_blocking_stage": None if first_blocking is None else first_blocking["key"],
        "next_action": "NONE_CHAIN_COMPLETE" if first_blocking is None else first_blocking["next_action"],
        "broad_corpus_verified": _broad_corpus_verified(values.get("corpus_coverage")),
        "exact_replay_intersections_ready": "corpus_coverage" in ready_keys,
        "daily_basis_inventories_ready": "basis_inventory_regeneration" in ready_keys,
        "g15_exact_publication_complete": "g15_publication" in ready_keys,
        "g15_counterfactual_attribution_complete": "g15_counterfactual_attribution" in ready_keys,
        "g15_counterfactual_lessons_complete": g15_complete,
        "g15_g16_counterfactual_lineage_complete": "g15_g16_counterfactual_lineage" in ready_keys,
        "g16_prepared_replay_ready": "g16_prepared_replay" in ready_keys,
        "g16_counterfactual_curve_locked_before_scoring": "g16_counterfactual_curve_lock" in ready_keys,
        "g16_prepared_curve_locked_before_scoring": "g16_counterfactual_curve_lock" in ready_keys,
        "g16_exact_publication_complete": g16_complete,
        "hardened_g16_chain_complete": g16_complete,
        "stand_down_days": sorted({day for row in rows for day in row.get("stand_down_days") or []}),
        "remote_presence_inferred": False,
        "actual_outcome_paths_loaded": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "note": (
            "Readiness v3 requires deterministic G15 counterfactual attribution, scored lesson adjudication, "
            "G15-publication/G16-plan lineage, counterfactual causal and curve authorizations, a lineage-bound "
            "pre-scoring lock, and counterfactual publication. Legacy prepared lock/publication artifacts cannot complete the chain."
        ),
    }
    report["fingerprint"] = _fingerprint(report)
    validate_readiness_report(report)
    return report


def validate_readiness_report(report: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(report))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(value):
        raise HistoricalRefinementReadinessError("readiness report schema or fingerprint mismatch")
    if value.get("stage_order") != [spec.key for spec in STAGES]:
        raise HistoricalRefinementReadinessError("readiness stage order mismatch")
    rows = value.get("stages")
    if not isinstance(rows, list) or [row.get("key") for row in rows] != value["stage_order"]:
        raise HistoricalRefinementReadinessError("readiness stage rows are incomplete or reordered")
    ready = [row["key"] for row in rows if row.get("effective_status") in {"READY", "READY_WITH_STAND_DOWNS"}]
    if value.get("ready_stages") != ready or int(value.get("ready_stage_count") or 0) != len(ready):
        raise HistoricalRefinementReadinessError("readiness ready-stage summary mismatch")
    first = next((row["key"] for row in rows if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}), None)
    if value.get("first_blocking_stage") != first:
        raise HistoricalRefinementReadinessError("readiness first-blocking-stage mismatch")
    if value.get("hardened_g16_chain_complete") != ("g16_counterfactual_publication" in ready):
        raise HistoricalRefinementReadinessError("hardened G16 completion summary mismatch")
    if value.get("g16_counterfactual_curve_locked_before_scoring") != ("g16_counterfactual_curve_lock" in ready):
        raise HistoricalRefinementReadinessError("counterfactual curve-lock summary mismatch")
    for field in ("remote_presence_inferred", "actual_outcome_paths_loaded", "paid_live_data_assumed", "random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started"):
        if value.get(field) is not False:
            raise HistoricalRefinementReadinessError(f"readiness must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True or value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("single signal authority and blind immutability must remain preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError("brokerage contract must remain tastytrade, not IBKR")


def _fixture_artifact(spec: StageSpec, status: str, *, stand_down: bool = False) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": spec.schema,
        "status": status,
        "execution_authority": False,
        "may_update_ng_brain": False,
        "random_shuffle_used": False,
        "options_lane_started": False,
    }
    for field in spec.required_fields:
        _path_set(value, field, f"fixture:{spec.key}:{field}")
    if stand_down:
        value["stand_down_days"] = ["20260315"]
    value[spec.fingerprint_field] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = {spec.key: _fixture_artifact(spec, sorted(spec.ready_statuses)[0]) for spec in STAGES}
    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        incoming.setdefault(target_key, []).append((source_key, source_path, target_path))
    for spec in STAGES:
        value = values[spec.key]
        for source_key, source_path, target_path in incoming.get(spec.key, []):
            _path_set(value, target_path, _path_get(values[source_key], source_path))
        value.pop(spec.fingerprint_field, None)
        value[spec.fingerprint_field] = _fingerprint(value)
    return values


def selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_coverage"
        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE"
        assert complete["hardened_g16_chain_complete"] is True
    print("[ng_historical_refinement_readiness] selftest PASS")
    return 0


def _parse_stage_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    allowed = {spec.key for spec in STAGES}
    for raw in values:
        if "=" not in raw:
            raise HistoricalRefinementReadinessError("--stage-path requires KEY=PATH")
        key, path = raw.split("=", 1)
        if key not in allowed or not path:
            raise HistoricalRefinementReadinessError(f"invalid stage path override: {raw!r}")
        result[key] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fail-closed NG historical refinement readiness report")
    parser.add_argument("--artifact-dir", type=Path, default=Path("renders/ng_refine_s95"))
    parser.add_argument("--stage-path", action="append", default=[], metavar="KEY=PATH")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir, stage_paths=_parse_stage_paths(args.stage_path))
    if args.out:
        _atomic_json(args.out, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
