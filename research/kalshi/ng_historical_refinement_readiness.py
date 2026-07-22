#!/usr/bin/env python3
"""Consolidate the historical-first NG refinement chain into one fail-closed report.

The report is observational only. It does not inspect unconfigured AWS/S3 objects,
construct forecasts, read outcome paths, update ``ng_brain.json``, or grant execution
authority. Missing artifacts remain MISSING, invalid artifacts remain INVALID, and a
ready downstream artifact cannot bypass an unready upstream stage.
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

SCHEMA = "ng_historical_refinement_readiness.v1"


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


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        "corpus_coverage",
        "ng_corpus_coverage_audit.json",
        "ng_corpus_coverage_audit.v1",
        "fingerprint",
        frozenset({
            "FULL_CORPUS_AND_G15_G16_EXACT_READY",
            "G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED",
        }),
        "ng_corpus_coverage_audit",
        ("validate_audit",),
        "Inspect and inventory the one-year L1/dense-trades and spring/summer MBO objects; keep uninspected objects UNKNOWN.",
    ),
    StageSpec(
        "replay_catalog_export",
        "ng_exact_replay_catalog_export.json",
        "ng_corpus_replay_catalog_export.v1",
        "fingerprint",
        frozenset({"READY"}),
        "ng_corpus_replay_catalog_export",
        ("validate_export_bundle",),
        "Export the deterministic exact G15/G16 source pairs into the canonical replay catalogs.",
    ),
    StageSpec(
        "g15_exact_replay",
        "g15_exact_replay_completion.json",
        "ng_g15_exact_replay_completion.v1",
        "completion_fingerprint",
        frozenset({"EXACT_CAUSAL_REPLAY_READY", "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS"}),
        "ng_g15_exact_replay_completion",
        ("validate_completion",),
        "Prepare and replay all 26 exact G15 sources through NGLiveOperator and completed MBO boundaries.",
    ),
    StageSpec(
        "g15_exact_refinement",
        "g15_exact_refinement_authorization.json",
        "ng_g15_exact_refinement_authorization.v1",
        "authorization_fingerprint",
        frozenset({"EXACT_G15_REFINEMENT_READY", "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS"}),
        "ng_g15_exact_refinement_gate",
        ("validate_authorization",),
        "Run the outcome-blind G15 posterior pipeline and bind it to the exact replay completion.",
    ),
    StageSpec(
        "g15_publication",
        "g15_exact_publication_completion.json",
        "ng_g15_exact_publication_completion.v1",
        "completion_fingerprint",
        frozenset({"EXACT_G15_PUBLICATION_COMPLETE", "EXACT_G15_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"}),
        "ng_g15_exact_publication_gate",
        ("validate_completion",),
        "Lock the refined G15 curve, render blind/refined paths, score them separately, and adjudicate lessons.",
    ),
    StageSpec(
        "g16_corpus_basis",
        "g16_corpus_basis_report.json",
        "ng_g16_corpus_basis_gate.v1",
        "fingerprint",
        frozenset({"MATCHED_L1_MBO_READY"}),
        "ng_g16_corpus_basis_gate",
        ("validate_report",),
        "Inspect exact NGK26/996 L1 and MBO objects for every canonical G16 session.",
    ),
    StageSpec(
        "g16_historical_replay",
        "g16_historical_replay.json",
        "ng_g16_historical_replay.v1",
        "fingerprint",
        frozenset({"READY", "READY_WITH_STAND_DOWNS"}),
        "ng_g16_historical_replay",
        ("validate_replay_output",),
        "Prepare the 23-source exact NGK26 corpus and replay it chronologically through the live-causal path.",
    ),
    StageSpec(
        "g16_exact_causal",
        "g16_exact_causal_pipeline.json",
        "ng_g16_exact_causal_pipeline.v1",
        "fingerprint",
        frozenset({"READY", "READY_WITH_STAND_DOWNS"}),
        None,
        (),
        "Run the pre-cutoff G16 authorization and posterior chain using only the locked G15 lesson registry.",
    ),
    StageSpec(
        "g16_publication",
        "g16_exact_publication_completion.json",
        "ng_g16_exact_publication_completion.v1",
        "completion_fingerprint",
        frozenset({"EXACT_G16_PUBLICATION_COMPLETE", "EXACT_G16_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"}),
        "ng_g16_exact_publication_gate",
        ("validate_completion",),
        "Lock the G16 refined curve, score the fixed forward holdout, render both paths, and close publication.",
    ),
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


def _generic_validate(value: Mapping[str, Any], spec: StageSpec) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(spec.fingerprint_field, None)
    if candidate.get("schema") != spec.schema:
        raise HistoricalRefinementReadinessError(
            f"{spec.key}: schema {candidate.get('schema')!r} != {spec.schema!r}"
        )
    if not isinstance(observed, str) or observed != _fingerprint(candidate):
        raise HistoricalRefinementReadinessError(
            f"{spec.key}: {spec.fingerprint_field} mismatch"
        )


def _resolve_validator(spec: StageSpec) -> Callable[[Mapping[str, Any]], Any] | None:
    if spec.validator_module is None:
        return None
    module = importlib.import_module(spec.validator_module)
    for name in spec.validator_names:
        function = getattr(module, name, None)
        if callable(function):
            return function
    raise HistoricalRefinementReadinessError(
        f"{spec.key}: canonical validator not found in {spec.validator_module}"
    )


def _extract_blockers(value: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    explicit_names = {
        "errors", "blockers", "missing", "missing_days", "unknown_days",
        "mbo_blocked_days", "l1_blocked_days", "l1_wrong_basis_days",
        "event_overlap_blocked_days", "definition_blocked_days",
    }

    def visit(node: Any, prefix: str = "") -> None:
        if len(blockers) >= 64:
            return
        if isinstance(node, Mapping):
            for key, item in node.items():
                label = f"{prefix}.{key}" if prefix else str(key)
                lowered = str(key).lower()
                if key in explicit_names or lowered.endswith("_blocked_days"):
                    if isinstance(item, list):
                        blockers.extend(f"{label}:{entry}" for entry in item if entry not in (None, ""))
                    elif item not in (None, "", False, [], {}):
                        blockers.append(f"{label}:{item}")
                elif lowered in {"status", "availability"} and str(item).upper() in {
                    "UNKNOWN", "MISSING", "CORRUPT", "BLOCKED", "INVALID",
                    "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED",
                }:
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
    for name in ("stand_down_days", "queue_stand_down_days"):
        result.extend(str(day) for day in value.get(name) or [])
    days = value.get("days")
    if isinstance(days, Mapping):
        iterable = days.values()
    elif isinstance(days, list):
        iterable = days
    else:
        iterable = []
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
        booleans = [
            value for key, value in broad.items()
            if "complete" in str(key).lower() or "verified" in str(key).lower()
        ]
        return bool(booleans) and all(value is True for value in booleans)
    return False


def evaluate_stage(
    spec: StageSpec,
    path: Path,
    *,
    validator_override: Callable[[Mapping[str, Any]], Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row: dict[str, Any] = {
        "key": spec.key,
        "path": str(path),
        "artifact_present": path.is_file(),
        "artifact_status": None,
        "validation": "NOT_RUN",
        "effective_status": "MISSING",
        "stand_down_days": [],
        "blockers": [],
        "next_action": spec.next_action,
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
            row["effective_status"] = (
                "READY_WITH_STAND_DOWNS" if row["stand_down_days"] else "READY"
            )
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


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    stage_paths = dict(stage_paths or {})
    validator_overrides = dict(validator_overrides or {})
    rows: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {}
    upstream_ready = True

    for spec in STAGES:
        path = stage_paths.get(spec.key, artifact_dir / spec.filename)
        row, value = evaluate_stage(
            spec,
            path,
            validator_override=validator_overrides.get(spec.key),
        )
        if value is not None:
            values[spec.key] = value
        artifact_ready = row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}
        if artifact_ready and not upstream_ready:
            row["effective_status"] = "BLOCKED_BY_UPSTREAM"
            row["blockers"] = sorted(set(row["blockers"] + ["an earlier stage is not ready"]))
        upstream_ready = upstream_ready and artifact_ready
        rows.append(row)

    first_blocking = next(
        (row for row in rows if row["effective_status"] not in {"READY", "READY_WITH_STAND_DOWNS"}),
        None,
    )
    ready_keys = [row["key"] for row in rows if row["effective_status"] in {"READY", "READY_WITH_STAND_DOWNS"}]
    g15_complete = "g15_publication" in ready_keys
    g16_complete = "g16_publication" in ready_keys
    broad_verified = _broad_corpus_verified(values.get("corpus_coverage"))

    if g16_complete and len(ready_keys) == len(STAGES):
        overall = "G15_G16_EXACT_PUBLICATION_COMPLETE"
    elif g15_complete:
        overall = "G15_EXACT_PUBLICATION_COMPLETE_G16_INCOMPLETE"
    elif "g15_exact_refinement" in ready_keys:
        overall = "G15_EXACT_REFINEMENT_READY_PUBLICATION_INCOMPLETE"
    elif "g15_exact_replay" in ready_keys:
        overall = "G15_EXACT_REPLAY_READY_REFINEMENT_INCOMPLETE"
    elif "replay_catalog_export" in ready_keys:
        overall = "EXACT_REPLAY_CATALOG_READY_REPLAY_INCOMPLETE"
    elif "corpus_coverage" in ready_keys:
        overall = "EXACT_INTERSECTIONS_READY_EXPORT_INCOMPLETE"
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
        "broad_corpus_verified": broad_verified,
        "exact_replay_intersections_ready": "corpus_coverage" in ready_keys,
        "g15_exact_publication_complete": g15_complete,
        "g16_exact_publication_complete": g16_complete,
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
            "This report consolidates canonical artifact validation and upstream ordering only. "
            "It does not invent remote objects, read outcome paths, or authorize options/live execution."
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
    first = next(
        (row["key"] for row in rows if row.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}),
        None,
    )
    if value.get("first_blocking_stage") != first:
        raise HistoricalRefinementReadinessError("readiness first-blocking-stage mismatch")
    for field in (
        "remote_presence_inferred", "actual_outcome_paths_loaded", "paid_live_data_assumed",
        "random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started",
    ):
        if value.get(field) is not False:
            raise HistoricalRefinementReadinessError(f"readiness must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError("single signal authority must remain preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts must remain immutable")
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
    }
    if stand_down:
        value["stand_down_days"] = ["20260315"]
    value[spec.fingerprint_field] = _fingerprint(value)
    return value


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["status"] == "BLOCKED_OR_UNVERIFIED"
        assert missing["first_blocking_stage"] == "corpus_coverage"
        for spec in STAGES:
            status = sorted(spec.ready_statuses)[0]
            _atomic_json(root / spec.filename, _fixture_artifact(spec, status))
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_EXACT_PUBLICATION_COMPLETE"
        assert complete["first_blocking_stage"] is None
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
