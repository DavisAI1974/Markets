#!/usr/bin/env python3
"""Freeze verified Step-1 outputs as non-result-bearing V4 pilot inputs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from research.kalshi.ng_exhaustion_step1_completion_gate import (
    CompletionGateError,
    validate_finalization_provenance,
    validate_launch_canary,
)


SCHEMA = "NG_EXHAUSTION_STEP1_TO_V4_FROZEN_REGISTRY_V1_20260823"
POPULATION_SCHEMA = "NG_EXHAUSTION_STEP1_POPULATION_CASE_V1_20260822"
RECEIPT_SCHEMA = "NG_EXHAUSTION_MBO_5Y_STEP1_RECONCILIATION_V1_20260822"
LAUNCH_SCHEMA = "NG_EXHAUSTION_MBO_5Y_STEP1_LAUNCH_RECEIPT_V1_20260822"
REVISION = "NG_EXHAUSTION_MBO_5Y_STEP1_DUAL_CENSUS_V1_20260822"
ADAPTER_REVISION = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"
NATIVE_TAXONOMY = "NG_EXHAUSTION_V4_NATIVE_STRUCTURE_TAXONOMY_V1_20260822"
RETENTION_POLICY = "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL"
CROSSWALK_SCHEMA = "NG_EXHAUSTION_STEP1_DUAL_CENSUS_CROSSWALK_V1_20260822"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_RE = re.compile(r"^[0-9a-f]{40}$")
EDGE_STATUSES = frozenset({"MATCH", "SPLIT", "MERGE", "COMPLEX_SPLIT_MERGE"})
ALL_CROSSWALK_STATUSES = EDGE_STATUSES | frozenset(
    {"LEGACY_CONTROL_ONLY", "V4_NATIVE_FULL_ONLY"}
)


class RegistryError(ValueError):
    pass


def _canonical_hash(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise RegistryError(f"{path.name}:{line_number} is not a JSON object")
                yield row
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"invalid gzip JSONL input {path.name}: {exc}") from exc


def _validate_output(
    path: Path, metadata: Mapping[str, Any], expected_rows: int, label: str
) -> None:
    if not path.is_file():
        raise RegistryError(f"{label} input is absent")
    claimed = metadata.get("gzip_sha256")
    if not SHA256_RE.fullmatch(str(claimed)) or _file_hash(path) != claimed:
        raise RegistryError(f"{label} gzip hash drift")
    if type(metadata.get("rows")) is not int or metadata.get("rows") != expected_rows:
        raise RegistryError(f"{label} receipt row accounting drift")


def _read_population(
    path: Path,
    *,
    view: str,
    expected_rows: int,
    engine_hashes: Mapping[str, str],
    ruleset_sha256: str,
    adapter_revision: str,
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in _jsonl(path):
        if row.get("schema") != POPULATION_SCHEMA or row.get("census_view") != view:
            raise RegistryError(f"{view} population schema/view drift")
        event_id = str(row.get("chain_origin_event_id") or "")
        chain_id = str(row.get("chain_id") or "")
        if not event_id or not chain_id or event_id in rows:
            raise RegistryError(f"{view} population event identity is absent or duplicated")
        depth = row.get("realized_structural_depth")
        if type(depth) is not int or depth not in range(6):
            raise RegistryError(f"{view} population realized depth is outside D0-D5")
        if not isinstance(row.get("unresolved"), bool):
            raise RegistryError(f"{view} population unresolved flag must be boolean")
        week = str(row.get("week_sunday") or "")
        if not re.fullmatch(r"20\d{6}", week):
            raise RegistryError(f"{view} population week identity is malformed")
        try:
            sunday = dt.datetime.strptime(week, "%Y%m%d").date()
        except ValueError as exc:
            raise RegistryError(f"{view} population week is not a calendar date") from exc
        if sunday.weekday() != 6:
            raise RegistryError(f"{view} population week_sunday is not Sunday")
        if view == "LEGACY_CONTROL" and row.get("legacy_d_label") != f"D{depth}":
            raise RegistryError("legacy population D label/depth drift")
        if row.get("engine_hashes") != engine_hashes:
            raise RegistryError(f"{view} population engine hash drift")
        if row.get("ruleset_sha256") != ruleset_sha256:
            raise RegistryError(f"{view} population ruleset hash drift")
        if row.get("adapter_revision") != adapter_revision:
            raise RegistryError(f"{view} population adapter revision drift")
        if row.get("retention_policy") != RETENTION_POLICY:
            raise RegistryError(f"{view} population retention policy drift")
        if row.get("short_long_state") != "UNDECLARED_STRUCTURAL_CENSUS_ONLY":
            raise RegistryError(f"{view} population overclaims short/long state")
        provenance = row.get("source_provenance")
        if not isinstance(provenance, Mapping):
            raise RegistryError(f"{view} population provenance is absent")
        if row.get("unresolved") is False and (
            not str(provenance.get("source_dbn_key") or "")
            or not SHA256_RE.fullmatch(str(provenance.get("source_dbn_sha256") or ""))
        ):
            raise RegistryError(f"{view} resolved population provenance is incomplete")
        rows[event_id] = row
    if len(rows) != expected_rows:
        raise RegistryError(f"{view} population physical row count drift")
    return rows


def build_registry(
    launch_receipt_path: str | Path,
    receipt_path: str | Path,
    legacy_population_path: str | Path,
    native_population_path: str | Path,
    crosswalk_path: str | Path,
    *,
    candidate_commit: str,
    result_prefix: str,
    finalizer_lock_path: str | Path | None = None,
) -> dict[str, Any]:
    launch_receipt_path = Path(launch_receipt_path)
    receipt_path = Path(receipt_path)
    legacy_path = Path(legacy_population_path)
    native_path = Path(native_population_path)
    crosswalk_path = Path(crosswalk_path)
    if not CANDIDATE_RE.fullmatch(candidate_commit):
        raise RegistryError("candidate_commit must be an exact 40-character commit")
    if not result_prefix.startswith("s3://") or not result_prefix.endswith("/"):
        raise RegistryError("result_prefix must be an exact S3 results prefix")
    if not result_prefix.endswith("/full/results/"):
        raise RegistryError("result_prefix must end at the exact full/results boundary")
    launch = json.loads(launch_receipt_path.read_text(encoding="utf-8"))
    if launch.get("schema") != LAUNCH_SCHEMA:
        raise RegistryError("Step-1 launch receipt schema drift")
    if launch.get("candidate_commit") != candidate_commit:
        raise RegistryError("candidate does not match the authoritative launch receipt")
    if launch.get("full_census_launched") is not True:
        raise RegistryError("Step-1 launch receipt does not prove full launch")
    if launch.get("result_prefix") != result_prefix.removesuffix("results/"):
        raise RegistryError("Step-1 launch/result prefix drift")
    for field in (
        "release_or_virgin_holdout_consumed",
        "predictive_or_trading_experiment_run",
        "permanent_frankie_mutated",
    ):
        if launch.get(field) is not False:
            raise RegistryError(f"unsafe Step-1 launch field: {field}")
    launch_lock = launch.get("candidate_lock")
    if not isinstance(launch_lock, Mapping):
        raise RegistryError("Step-1 launch candidate lock is absent")
    try:
        launch_canary_mode = validate_launch_canary(launch, launch_lock)
    except CompletionGateError as exc:
        raise RegistryError(f"Step-1 launch canary evidence invalid: {exc}") from exc
    if launch_canary_mode != "USER_AUTHORIZED_ONE_DAY_CANARY":
        raise RegistryError("Step-1 registry requires the exact promoted one-day canary")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    claimed_receipt_hash = receipt.get("receipt_sha256")
    receipt_body = dict(receipt)
    receipt_body.pop("receipt_sha256", None)
    if (
        not SHA256_RE.fullmatch(str(claimed_receipt_hash))
        or _canonical_hash(receipt_body) != claimed_receipt_hash
    ):
        raise RegistryError("Step-1 receipt hash drift")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise RegistryError("Step-1 receipt schema drift")
    if receipt.get("status") != "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE":
        raise RegistryError("Step-1 census is not complete")
    if receipt.get("revision") != REVISION:
        raise RegistryError("Step-1 receipt revision drift")
    if receipt.get("adapter_revision") != ADAPTER_REVISION:
        raise RegistryError("Step-1 adapter revision drift")
    if receipt.get("native_taxonomy") != NATIVE_TAXONOMY:
        raise RegistryError("Step-1 native taxonomy drift")
    if receipt.get("retention_policy") != RETENTION_POLICY:
        raise RegistryError("Step-1 retention policy drift")
    if receipt.get("weeks_filter") is not None:
        raise RegistryError("Step-1 receipt is filtered")
    for field, message in (
        ("release_or_virgin_holdout_consumed", "holdout consumption is forbidden"),
        ("predictive_or_trading_experiment_run", "prediction/trading is forbidden"),
        ("permanent_frankie_mutated", "permanent Frankie mutation is forbidden"),
        ("frozen_detector_mutated", "frozen detector mutation is forbidden"),
    ):
        if receipt.get(field) is not False:
            raise RegistryError(message)
    for field in ("source_manifest_sha256", "ruleset_sha256"):
        if not SHA256_RE.fullmatch(str(receipt.get(field))):
            raise RegistryError(f"Step-1 {field} is malformed")
    engine_hashes = receipt.get("engine_hashes")
    if not isinstance(engine_hashes, dict) or not engine_hashes:
        raise RegistryError("Step-1 engine hashes are absent")
    if any(not SHA256_RE.fullmatch(str(value)) for value in engine_hashes.values()):
        raise RegistryError("Step-1 engine hash is malformed")
    if (
        launch_lock.get("source_manifest_sha256") != receipt["source_manifest_sha256"]
        or launch_lock.get("ruleset_sha256") != receipt["ruleset_sha256"]
    ):
        raise RegistryError("Step-1 launch lock/final receipt identity drift")
    finalizer_lock: Mapping[str, Any] = {}
    if receipt.get("finalization_recovery") is not None:
        if finalizer_lock_path is None:
            raise RegistryError("Step-1 recovery finalizer lock is required")
        finalizer_lock = json.loads(Path(finalizer_lock_path).read_text(encoding="utf-8"))
    try:
        finalization_mode = validate_finalization_provenance(
            receipt,
            launch,
            launch_lock,
            finalizer_lock=finalizer_lock,
            launch_receipt_file_sha256=_file_hash(launch_receipt_path),
        )
    except CompletionGateError as exc:
        raise RegistryError(f"Step-1 finalization provenance invalid: {exc}") from exc

    outputs = receipt.get("population_outputs")
    summaries = {
        "legacy": receipt.get("legacy_population_summary"),
        "native": receipt.get("native_population_summary"),
    }
    if not isinstance(outputs, dict) or any(not isinstance(x, dict) for x in summaries.values()):
        raise RegistryError("Step-1 population metadata is absent")
    legacy_count = summaries["legacy"].get("population_count")
    native_count = summaries["native"].get("population_count")
    if (
        type(legacy_count) is not int
        or type(native_count) is not int
        or legacy_count < 0
        or native_count < 0
        or summaries["legacy"].get("case_retention_exact") is not True
        or summaries["native"].get("case_retention_exact") is not True
        or summaries["legacy"].get("view") != "LEGACY_CONTROL"
        or summaries["native"].get("view") != "V4_NATIVE_FULL"
        or summaries["legacy"].get("event_count") != legacy_count
        or summaries["native"].get("event_count") != native_count
    ):
        raise RegistryError("Step-1 population retention or event/case count metadata drift")
    _validate_output(legacy_path, outputs["legacy"], legacy_count, "legacy population")
    _validate_output(native_path, outputs["native"], native_count, "native population")
    legacy = _read_population(
        legacy_path,
        view="LEGACY_CONTROL",
        expected_rows=legacy_count,
        engine_hashes=engine_hashes,
        ruleset_sha256=receipt["ruleset_sha256"],
        adapter_revision=receipt["adapter_revision"],
    )
    native = _read_population(
        native_path,
        view="V4_NATIVE_FULL",
        expected_rows=native_count,
        engine_hashes=engine_hashes,
        ruleset_sha256=receipt["ruleset_sha256"],
        adapter_revision=receipt["adapter_revision"],
    )

    crosswalk_metadata = receipt.get("crosswalk_output")
    crosswalk_summary = receipt.get("crosswalk_summary")
    if not isinstance(crosswalk_metadata, dict) or not isinstance(crosswalk_summary, dict):
        raise RegistryError("Step-1 crosswalk metadata is absent")
    if crosswalk_summary.get("schema") != CROSSWALK_SCHEMA:
        raise RegistryError("Step-1 crosswalk schema drift")
    if crosswalk_summary.get("retention_policy") != RETENTION_POLICY:
        raise RegistryError("Step-1 crosswalk retention policy drift")
    expected_crosswalk_rows = crosswalk_metadata.get("rows")
    if type(expected_crosswalk_rows) is not int or expected_crosswalk_rows < 0:
        raise RegistryError("Step-1 crosswalk row count is absent")
    _validate_output(crosswalk_path, crosswalk_metadata, expected_crosswalk_rows, "crosswalk")
    if "NO_CASE_DROPPED" not in str(crosswalk_summary.get("splits_merges_policy", "")):
        raise RegistryError("Step-1 crosswalk no-case-drop policy is absent")

    status_counts: Counter[str] = Counter()
    inventory: dict[str, Counter[str]] = defaultdict(Counter)
    eligible_edges = 0
    unresolved_edges = 0
    physical_crosswalk_rows = 0
    covered_legacy: set[str] = set()
    covered_native: set[str] = set()
    crosswalk_identities: set[tuple[str, Any, Any]] = set()
    edge_rows: list[tuple[str, str, str]] = []
    left_degree: Counter[str] = Counter()
    right_degree: Counter[str] = Counter()
    primary_matches = 0
    depth_agreements = 0
    reset_agreements = 0
    for edge in _jsonl(crosswalk_path):
        physical_crosswalk_rows += 1
        status = str(edge.get("status") or "")
        if status not in ALL_CROSSWALK_STATUSES:
            raise RegistryError("unknown crosswalk status")
        status_counts[status] += 1
        legacy_id = edge.get("legacy_event_id")
        native_id = edge.get("native_event_id")
        identity = (status, legacy_id, native_id)
        if identity in crosswalk_identities:
            raise RegistryError("duplicate crosswalk row identity")
        crosswalk_identities.add(identity)
        if status == "LEGACY_CONTROL_ONLY":
            if legacy_id not in legacy or native_id is not None:
                raise RegistryError("legacy-only crosswalk row identity drift")
            covered_legacy.add(legacy_id)
            continue
        if status == "V4_NATIVE_FULL_ONLY":
            if native_id not in native or legacy_id is not None:
                raise RegistryError("native-only crosswalk row identity drift")
            covered_native.add(native_id)
            continue
        if legacy_id not in legacy or native_id not in native:
            raise RegistryError("crosswalk edge references an absent population case")
        if type(edge.get("legacy_depth")) is not int or type(edge.get("native_depth")) is not int:
            raise RegistryError("crosswalk edge depth must be an integer")
        covered_legacy.add(legacy_id)
        covered_native.add(native_id)
        edge_rows.append((status, legacy_id, native_id))
        left_degree[legacy_id] += 1
        right_degree[native_id] += 1
        legacy_row = legacy[legacy_id]
        native_row = native[native_id]
        if (
            edge.get("legacy_depth") != legacy_row["realized_structural_depth"]
            or edge.get("native_depth") != native_row["realized_structural_depth"]
        ):
            raise RegistryError("crosswalk edge depth/population drift")
        if legacy_row["week_sunday"] != native_row["week_sunday"]:
            raise RegistryError("crosswalk edge joins cases from different weeks")
        depth_agreement = (
            legacy_row["realized_structural_depth"]
            == native_row["realized_structural_depth"]
        )
        if edge.get("depth_agreement") is not depth_agreement:
            raise RegistryError("crosswalk depth_agreement annotation drift")
        if not isinstance(edge.get("primary_one_to_one_match"), bool):
            raise RegistryError("crosswalk primary match annotation must be boolean")
        if not isinstance(edge.get("reset_agreement"), bool):
            raise RegistryError("crosswalk reset agreement annotation must be boolean")
        native_reset = native_row.get("reset_event_id")
        expected_reset_agreement = legacy_row.get("reset_event_id") == (
            None if native_reset is None else str(native_reset).removeprefix("V4N1|")
        )
        if edge["reset_agreement"] is not expected_reset_agreement:
            raise RegistryError("crosswalk reset_agreement annotation drift")
        primary_matches += int(edge["primary_one_to_one_match"])
        depth_agreements += int(depth_agreement)
        reset_agreements += int(expected_reset_agreement)
        d_lane = legacy_row["legacy_d_label"]
        year = native_row["week_sunday"][:4]
        if legacy_row.get("unresolved") or native_row.get("unresolved"):
            unresolved_edges += 1
            continue
        eligible_edges += 1
        inventory[d_lane][year] += 1
    if physical_crosswalk_rows != expected_crosswalk_rows:
        raise RegistryError("crosswalk physical row count drift")
    if covered_legacy != set(legacy) or covered_native != set(native):
        raise RegistryError("crosswalk population coverage is incomplete")
    for status, legacy_id, native_id in edge_rows:
        if left_degree[legacy_id] > 1 and right_degree[native_id] > 1:
            expected_status = "COMPLEX_SPLIT_MERGE"
        elif left_degree[legacy_id] > 1:
            expected_status = "SPLIT"
        elif right_degree[native_id] > 1:
            expected_status = "MERGE"
        else:
            expected_status = "MATCH"
        if status != expected_status:
            raise RegistryError("crosswalk relationship does not match graph degrees")
    expected_status_counts = {
        "MATCH": crosswalk_summary.get("match_edges", 0),
        "SPLIT": crosswalk_summary.get("split_edges", 0),
        "MERGE": crosswalk_summary.get("merge_edges", 0),
        "COMPLEX_SPLIT_MERGE": crosswalk_summary.get("complex_split_merge_edges", 0),
        "LEGACY_CONTROL_ONLY": crosswalk_summary.get("legacy_control_only", 0),
        "V4_NATIVE_FULL_ONLY": crosswalk_summary.get("v4_native_full_only", 0),
    }
    expected_counters = {
        **expected_status_counts,
        "primary_matches": crosswalk_summary.get("primary_matches"),
        "depth_agreements": crosswalk_summary.get("depth_agreements"),
        "depth_disagreements": crosswalk_summary.get("depth_disagreements"),
        "reset_agreements": crosswalk_summary.get("reset_agreements"),
        "reset_disagreements": crosswalk_summary.get("reset_disagreements"),
    }
    if any(type(value) is not int or value < 0 for value in expected_counters.values()):
        raise RegistryError("crosswalk summary counter is absent or malformed")
    observed_counters = {
        **{key: status_counts[key] for key in expected_status_counts},
        "primary_matches": primary_matches,
        "depth_agreements": depth_agreements,
        "depth_disagreements": len(edge_rows) - depth_agreements,
        "reset_agreements": reset_agreements,
        "reset_disagreements": len(edge_rows) - reset_agreements,
    }
    if observed_counters != expected_counters:
        raise RegistryError("crosswalk status accounting drift")

    input_metadata = {
        "launch_receipt": {
            "name": launch_receipt_path.name,
            "object_sha256": _file_hash(launch_receipt_path),
        },
        "step1_receipt": {
            "name": receipt_path.name,
            "object_sha256": _file_hash(receipt_path),
            "canonical_receipt_sha256": claimed_receipt_hash,
            "s3_uri": result_prefix + receipt_path.name,
        },
        "legacy_population": {
            "name": legacy_path.name,
            "sha256": outputs["legacy"]["gzip_sha256"],
            "rows": legacy_count,
            "s3_uri": result_prefix + legacy_path.name,
        },
        "native_population": {
            "name": native_path.name,
            "sha256": outputs["native"]["gzip_sha256"],
            "rows": native_count,
            "s3_uri": result_prefix + native_path.name,
        },
        "crosswalk": {
            "name": crosswalk_path.name,
            "sha256": crosswalk_metadata["gzip_sha256"],
            "rows": expected_crosswalk_rows,
            "s3_uri": result_prefix + crosswalk_path.name,
        },
    }
    core = {
        "schema": SCHEMA,
        "status": "STEP1_TO_V4_FROZEN_REGISTRY_READY",
        "candidate_commit": candidate_commit,
        "launch_canary_mode": launch_canary_mode,
        "finalization_mode": finalization_mode,
        "source_manifest_sha256": receipt["source_manifest_sha256"],
        "ruleset_sha256": receipt["ruleset_sha256"],
        "engine_hashes": engine_hashes,
        "adapter_revision": receipt.get("adapter_revision"),
        "inputs": input_metadata,
        "crosswalk_status_counts": dict(sorted(status_counts.items())),
        "eligible_crosswalk_edge_count": eligible_edges,
        "unresolved_crosswalk_edge_count": unresolved_edges,
        "inventory_by_d_year": {
            d_lane: dict(sorted(years.items())) for d_lane, years in sorted(inventory.items())
        },
        "pilot_selection_status": "UNDECLARED",
        "pilot_manifest_sha256": None,
        "result_bearing_launch_authorized": False,
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "permanent_frankie_mutated": False,
    }
    return {**core, "registry_sha256": _canonical_hash(core)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-receipt", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--legacy-population", required=True)
    parser.add_argument("--native-population", required=True)
    parser.add_argument("--crosswalk", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--result-prefix", required=True)
    parser.add_argument("--finalizer-lock")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    registry = build_registry(
        args.launch_receipt,
        args.receipt,
        args.legacy_population,
        args.native_population,
        args.crosswalk,
        candidate_commit=args.candidate_commit,
        result_prefix=args.result_prefix,
        finalizer_lock_path=args.finalizer_lock,
    )
    Path(args.output).write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": registry["status"],
        "registry_sha256": registry["registry_sha256"],
        "eligible_crosswalk_edge_count": registry["eligible_crosswalk_edge_count"],
        "result_bearing_launch_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
