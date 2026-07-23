#!/usr/bin/env python3
"""Safely inventory and materialize remote NG corpus objects for exact inspection.

This module bridges a concrete S3 inventory to ``ng_corpus_inspection.py`` without
using object names as contract identity. Remote object existence, explicit operator
bindings, downloaded bytes, and observed instrument definitions remain separate,
fingerprinted facts.

No download is attempted without an explicit confirmation and byte ceiling. The
resulting inspection plan remains outcome-blind, SHADOW-only, and cannot modify a
blind forecast, posterior, ``knowledge/ng_brain.json``, or execution state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection

SNAPSHOT_SCHEMA = "ng_remote_object_inventory.v1"
BINDING_SCHEMA = "ng_corpus_object_binding.v1"
MATERIALIZATION_SCHEMA = "ng_object_materialization_receipt.v1"
BUNDLE_SCHEMA = "ng_corpus_materialization_bundle.v1"
REVIEW_STATUSES = {"REVIEW_REQUIRED", "APPROVED", "REJECTED"}


class CorpusMaterializationError(ValueError):
    """Raised when remote inventory, bindings, or downloaded bytes are unsafe."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusMaterializationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusMaterializationError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusMaterializationError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise CorpusMaterializationError(f"{label} must be a positive integer")
    return number


def _authority() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "remote_presence_inferred": False,
        "identity_inferred_from_object_name": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _validate_authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "remote_presence_inferred",
        "identity_inferred_from_object_name",
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "may_change_posterior",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusMaterializationError(f"{label}: {field} must remain false")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusMaterializationError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusMaterializationError(f"{label}: brokerage must remain tastytrade_not_ibkr")


def _object_id(bucket: str, key: str, version_id: str | None = None) -> str:
    identity = {"bucket": bucket, "key": key, "version_id": version_id or ""}
    return _fp(identity)


def snapshot_s3(
    s3: Any,
    *,
    bucket: str,
    prefixes: Sequence[str],
    observed_at: str,
    scope_complete: bool = False,
    endpoint: str | None = None,
) -> dict[str, Any]:
    """List exact remote objects. Object names are never treated as market identity."""
    if not bucket:
        raise CorpusMaterializationError("bucket is required")
    clean_prefixes = sorted({str(prefix).lstrip("/") for prefix in prefixes})
    if not clean_prefixes:
        raise CorpusMaterializationError("at least one prefix is required")
    objects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for prefix in clean_prefixes:
        token: str | None = None
        while True:
            request: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if token:
                request["ContinuationToken"] = token
            response = s3.list_objects_v2(**request)
            for raw in response.get("Contents", []) or []:
                key = str(raw.get("Key") or "")
                size = int(raw.get("Size") or 0)
                if not key or size <= 0:
                    continue
                object_id = _object_id(bucket, key)
                if object_id in seen:
                    continue
                seen.add(object_id)
                last_modified = raw.get("LastModified")
                if hasattr(last_modified, "isoformat"):
                    last_modified = last_modified.isoformat()
                row = {
                    "object_id": object_id,
                    "bucket": bucket,
                    "key": key,
                    "location": f"s3://{bucket}/{key}",
                    "size_bytes": size,
                    "etag": str(raw.get("ETag") or "").strip('"'),
                    "last_modified": str(last_modified or ""),
                    "storage_class": str(raw.get("StorageClass") or ""),
                    "contract_identity_status": "UNOBSERVED",
                    "identity_inferred_from_object_name": False,
                }
                row["object_fingerprint"] = _fp(row)
                objects.append(row)
            if not response.get("IsTruncated"):
                break
            token = str(response.get("NextContinuationToken") or "")
            if not token:
                raise CorpusMaterializationError("truncated S3 response omitted continuation token")
    objects.sort(key=lambda row: (row["bucket"], row["key"], row["object_id"]))
    value = {
        "schema": SNAPSHOT_SCHEMA,
        "provider": "S3_COMPATIBLE",
        "bucket": bucket,
        "prefixes": clean_prefixes,
        "endpoint": endpoint,
        "observed_at": observed_at,
        "scope_complete": bool(scope_complete),
        "object_count": len(objects),
        "objects": objects,
        **_authority(),
    }
    value["snapshot_fingerprint"] = _fp(value)
    validate_snapshot(value)
    return value


def validate_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify(value, "snapshot_fingerprint", label="remote inventory snapshot")
    if checked.get("schema") != SNAPSHOT_SCHEMA:
        raise CorpusMaterializationError("remote inventory snapshot schema mismatch")
    _validate_authority(checked, label="remote inventory snapshot")
    if checked.get("provider") != "S3_COMPATIBLE":
        raise CorpusMaterializationError("unsupported inventory provider")
    bucket = str(checked.get("bucket") or "")
    if not bucket:
        raise CorpusMaterializationError("snapshot bucket is required")
    objects = list(checked.get("objects") or [])
    if checked.get("object_count") != len(objects):
        raise CorpusMaterializationError("snapshot object_count mismatch")
    seen_ids: set[str] = set()
    seen_locations: set[str] = set()
    for row in objects:
        if not isinstance(row, Mapping):
            raise CorpusMaterializationError("snapshot contains a non-object entry")
        payload = copy.deepcopy(dict(row))
        observed = payload.pop("object_fingerprint", None)
        if observed != _fp(payload):
            raise CorpusMaterializationError("snapshot object fingerprint mismatch")
        object_id = str(row.get("object_id") or "")
        key = str(row.get("key") or "")
        if object_id != _object_id(bucket, key):
            raise CorpusMaterializationError("snapshot object_id mismatch")
        location = str(row.get("location") or "")
        if location != f"s3://{bucket}/{key}":
            raise CorpusMaterializationError("snapshot object location mismatch")
        if object_id in seen_ids or location in seen_locations:
            raise CorpusMaterializationError("snapshot contains duplicate object")
        seen_ids.add(object_id)
        seen_locations.add(location)
        _positive_int(row.get("size_bytes"), label=f"{key} size_bytes")
        if row.get("contract_identity_status") != "UNOBSERVED":
            raise CorpusMaterializationError("snapshot may not assert contract identity")
        if row.get("identity_inferred_from_object_name") is not False:
            raise CorpusMaterializationError("snapshot may not infer identity from object name")
    return checked


def binding_template(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    checked = validate_snapshot(snapshot)
    bindings = []
    for row in checked["objects"]:
        binding = {
            "object_id": row["object_id"],
            "location": row["location"],
            "review_status": "REVIEW_REQUIRED",
            "source_id": None,
            "corpus_id": None,
            "lane": None,
            "day": None,
            "definition": None,
            "skip_nonmatching": False,
            "identity_inferred_from_object_name": False,
        }
        binding["binding_fingerprint"] = _fp(binding)
        bindings.append(binding)
    corpora = []
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "expected_days": [],
                "expected_object_count": None,
                "inventory_scope_verified": False,
                "inventory_complete_asserted": False,
                "inventory_observed_at": checked["observed_at"],
            }
        )
    value = {
        "schema": BINDING_SCHEMA,
        "snapshot_fingerprint": checked["snapshot_fingerprint"],
        "corpora": corpora,
        "bindings": bindings,
        "all_bindings_require_explicit_review": True,
        **_authority(),
    }
    value["binding_manifest_fingerprint"] = _fp(value)
    validate_bindings(value, snapshot=checked, require_approved=False)
    return value


def _day_in_window(day: str, *, start: str, end_exclusive: str) -> bool:
    try:
        parsed = date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    except (ValueError, TypeError):
        return False
    return date.fromisoformat(start) <= parsed < date.fromisoformat(end_exclusive)


def checked_snapshot_scope(snapshot: Mapping[str, Any], control: Mapping[str, Any]) -> bool:
    return bool(snapshot.get("scope_complete") and control.get("inventory_scope_verified"))


def validate_bindings(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    require_approved: bool,
) -> dict[str, Any]:
    checked = _verify(value, "binding_manifest_fingerprint", label="binding manifest")
    if checked.get("schema") != BINDING_SCHEMA:
        raise CorpusMaterializationError("binding manifest schema mismatch")
    _validate_authority(checked, label="binding manifest")
    snap = validate_snapshot(snapshot)
    if checked.get("snapshot_fingerprint") != snap.get("snapshot_fingerprint"):
        raise CorpusMaterializationError("binding manifest snapshot mismatch")
    if checked.get("all_bindings_require_explicit_review") is not True:
        raise CorpusMaterializationError("binding manifest must require explicit review")
    objects = {row["object_id"]: row for row in snap["objects"]}
    seen_objects: set[str] = set()
    seen_sources: set[str] = set()
    for raw in checked.get("bindings") or []:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("binding_fingerprint", None)
        if observed != _fp(row):
            raise CorpusMaterializationError("binding fingerprint mismatch")
        status = str(raw.get("review_status") or "")
        if status not in REVIEW_STATUSES:
            raise CorpusMaterializationError(f"invalid review_status {status!r}")
        object_id = str(raw.get("object_id") or "")
        if object_id not in objects or object_id in seen_objects:
            raise CorpusMaterializationError("unknown or duplicate bound object")
        seen_objects.add(object_id)
        if raw.get("location") != objects[object_id]["location"]:
            raise CorpusMaterializationError("binding object location mismatch")
        if raw.get("identity_inferred_from_object_name") is not False:
            raise CorpusMaterializationError("binding may not infer identity from object name")
        if status != "APPROVED":
            if require_approved and status == "REVIEW_REQUIRED":
                raise CorpusMaterializationError("unreviewed object remains in binding manifest")
            continue
        source_id = str(raw.get("source_id") or "")
        corpus_id = str(raw.get("corpus_id") or "")
        lane = str(raw.get("lane") or "")
        day = str(raw.get("day") or "").replace("-", "")
        if not source_id or source_id in seen_sources:
            raise CorpusMaterializationError("approved binding has missing or duplicate source_id")
        seen_sources.add(source_id)
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or lane != expected["lane"]:
            raise CorpusMaterializationError("approved binding corpus/lane mismatch")
        if not _day_in_window(day, start=expected["start"], end_exclusive=expected["end_exclusive"]):
            raise CorpusMaterializationError("approved binding day lies outside corpus window")
        definition = raw.get("definition")
        if not isinstance(definition, Mapping):
            raise CorpusMaterializationError("approved binding requires observed definition")
        inspection.validate_definition(definition)
    controls = list(checked.get("corpora") or [])
    if len(controls) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusMaterializationError("binding manifest must contain both corpus controls")
    seen_controls: set[str] = set()
    for control in controls:
        corpus_id = str(control.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_controls:
            raise CorpusMaterializationError("unexpected or duplicate corpus control")
        seen_controls.add(corpus_id)
        if control.get("lane") != expected["lane"]:
            raise CorpusMaterializationError("corpus control lane mismatch")
        expected_days = [str(day).replace("-", "") for day in control.get("expected_days") or []]
        if len(expected_days) != len(set(expected_days)):
            raise CorpusMaterializationError("corpus control has duplicate expected days")
        for day in expected_days:
            if not _day_in_window(day, start=expected["start"], end_exclusive=expected["end_exclusive"]):
                raise CorpusMaterializationError("corpus control expected day outside window")
        count = control.get("expected_object_count")
        if count is not None:
            _positive_int(count, label=f"{corpus_id} expected_object_count")
        if control.get("inventory_complete_asserted") is True:
            if not checked_snapshot_scope(snap, control):
                raise CorpusMaterializationError("complete corpus assertion lacks verified snapshot scope")
            if not expected_days or count is None:
                raise CorpusMaterializationError("complete corpus assertion requires days and count")
    return checked


def _download_one(s3: Any, *, bucket: str, key: str, target: Path) -> None:
    if hasattr(s3, "download_file"):
        s3.download_file(bucket, key, str(target))
        return
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    with target.open("wb") as handle:
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def materialize_approved(
    s3: Any,
    *,
    snapshot: Mapping[str, Any],
    bindings: Mapping[str, Any],
    output_root: Path,
    confirm_download: bool,
    max_total_bytes: int,
) -> dict[str, Any]:
    """Download approved objects atomically and produce byte-level receipts."""
    if confirm_download is not True:
        raise CorpusMaterializationError("remote download requires explicit confirmation")
    limit = _positive_int(max_total_bytes, label="max_total_bytes")
    snap = validate_snapshot(snapshot)
    bound = validate_bindings(bindings, snapshot=snap, require_approved=False)
    objects = {row["object_id"]: row for row in snap["objects"]}
    approved = [row for row in bound["bindings"] if row["review_status"] == "APPROVED"]
    total = sum(int(objects[row["object_id"]]["size_bytes"]) for row in approved)
    if total > limit:
        raise CorpusMaterializationError(
            f"approved download size {total} exceeds max_total_bytes {limit}"
        )
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    receipts = []
    for binding in approved:
        obj = objects[binding["object_id"]]
        suffix = Path(str(obj["key"])).suffix or ".bin"
        target = output_root / f"{binding['object_id']}{suffix}"
        if target.exists():
            raise CorpusMaterializationError(f"refusing to overwrite {target}")
        temp = target.with_suffix(target.suffix + ".partial")
        if temp.exists():
            temp.unlink()
        _download_one(s3, bucket=obj["bucket"], key=obj["key"], target=temp)
        size = temp.stat().st_size
        if size != int(obj["size_bytes"]):
            temp.unlink(missing_ok=True)
            raise CorpusMaterializationError(
                f"downloaded size mismatch for {obj['location']}: {size} != {obj['size_bytes']}"
            )
        sha = _sha256(temp)
        os.replace(temp, target)
        row = {
            "object_id": binding["object_id"],
            "location": obj["location"],
            "materialized_path": str(target),
            "size_bytes": size,
            "sha256": sha,
            "snapshot_object_fingerprint": obj["object_fingerprint"],
            "raw_input_untouched": True,
            "identity_inferred_from_object_name": False,
        }
        row["materialization_fingerprint"] = _fp(row)
        receipts.append(row)
    value = {
        "schema": MATERIALIZATION_SCHEMA,
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "binding_manifest_fingerprint": bound["binding_manifest_fingerprint"],
        "output_root": str(output_root),
        "approved_object_count": len(approved),
        "materialized_object_count": len(receipts),
        "total_size_bytes": total,
        "objects": receipts,
        **_authority(),
    }
    value["receipt_fingerprint"] = _fp(value)
    validate_materialization(value, snapshot=snap, bindings=bound, verify_files=True)
    return value


def validate_materialization(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    bindings: Mapping[str, Any],
    verify_files: bool,
) -> dict[str, Any]:
    checked = _verify(value, "receipt_fingerprint", label="materialization receipt")
    if checked.get("schema") != MATERIALIZATION_SCHEMA:
        raise CorpusMaterializationError("materialization receipt schema mismatch")
    _validate_authority(checked, label="materialization receipt")
    snap = validate_snapshot(snapshot)
    bound = validate_bindings(bindings, snapshot=snap, require_approved=False)
    if checked.get("snapshot_fingerprint") != snap["snapshot_fingerprint"]:
        raise CorpusMaterializationError("materialization snapshot mismatch")
    if checked.get("binding_manifest_fingerprint") != bound["binding_manifest_fingerprint"]:
        raise CorpusMaterializationError("materialization binding mismatch")
    approved_ids = {
        row["object_id"] for row in bound["bindings"] if row["review_status"] == "APPROVED"
    }
    objects = {row["object_id"]: row for row in snap["objects"]}
    rows = list(checked.get("objects") or [])
    if checked.get("approved_object_count") != len(approved_ids):
        raise CorpusMaterializationError("materialization approved count mismatch")
    if checked.get("materialized_object_count") != len(rows):
        raise CorpusMaterializationError("materialization object count mismatch")
    if {row.get("object_id") for row in rows} != approved_ids:
        raise CorpusMaterializationError("materialization does not cover approved objects exactly")
    total = 0
    for raw in rows:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("materialization_fingerprint", None)
        if observed != _fp(row):
            raise CorpusMaterializationError("materialization object fingerprint mismatch")
        object_id = str(raw.get("object_id") or "")
        obj = objects[object_id]
        if raw.get("location") != obj["location"]:
            raise CorpusMaterializationError("materialization object location mismatch")
        if raw.get("snapshot_object_fingerprint") != obj["object_fingerprint"]:
            raise CorpusMaterializationError("materialization snapshot-object mismatch")
        size = _positive_int(raw.get("size_bytes"), label="materialized size")
        if size != int(obj["size_bytes"]):
            raise CorpusMaterializationError("materialized size differs from snapshot")
        sha = str(raw.get("sha256") or "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
            raise CorpusMaterializationError("materialized sha256 must be 64 hex characters")
        if raw.get("raw_input_untouched") is not True:
            raise CorpusMaterializationError("materialized raw input must remain untouched")
        if raw.get("identity_inferred_from_object_name") is not False:
            raise CorpusMaterializationError("materialization may not infer identity from object name")
        if verify_files:
            path = Path(str(raw.get("materialized_path") or "")).expanduser().resolve()
            if not path.is_file() or path.stat().st_size != size or _sha256(path) != sha:
                raise CorpusMaterializationError(f"materialized file verification failed: {path}")
        total += size
    if checked.get("total_size_bytes") != total:
        raise CorpusMaterializationError("materialization total size mismatch")
    return checked


def build_inspection_plan(
    *,
    snapshot: Mapping[str, Any],
    bindings: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Join reviewed object bindings, exact definitions, and downloaded bytes."""
    snap = validate_snapshot(snapshot)
    bound = validate_bindings(bindings, snapshot=snap, require_approved=True)
    materialized = validate_materialization(
        receipt,
        snapshot=snap,
        bindings=bound,
        verify_files=True,
    )
    by_object = {row["object_id"]: row for row in materialized["objects"]}
    plan = inspection.plan_template(allowed_roots=[materialized["output_root"]])
    plan_corpora = {row["corpus_id"]: row for row in plan["corpora"]}
    controls = {row["corpus_id"]: row for row in bound["corpora"]}
    approved = [row for row in bound["bindings"] if row["review_status"] == "APPROVED"]
    for binding in approved:
        object_receipt = by_object[binding["object_id"]]
        corpus = plan_corpora[binding["corpus_id"]]
        definition = inspection.validate_definition(binding["definition"])
        corpus["sources"].append(
            {
                "source_id": binding["source_id"],
                "location": binding["location"],
                "materialized_path": object_receipt["materialized_path"],
                "day": str(binding["day"]).replace("-", ""),
                "lane": binding["lane"],
                "definition": definition,
                "inventory_observed_at": snap["observed_at"],
                "skip_nonmatching": binding.get("skip_nonmatching") is True,
                "remote_object_fingerprint": next(
                    row["object_fingerprint"]
                    for row in snap["objects"]
                    if row["object_id"] == binding["object_id"]
                ),
                "materialization_fingerprint": object_receipt["materialization_fingerprint"],
                "identity_inferred_from_filename": False,
            }
        )
    for corpus_id, corpus in plan_corpora.items():
        control = controls[corpus_id]
        corpus["publisher_id"] = None
        corpus["expected_days"] = [str(day).replace("-", "") for day in control.get("expected_days") or []]
        corpus["expected_object_count"] = control.get("expected_object_count")
        corpus["inventory_scope_verified"] = checked_snapshot_scope(snap, control)
        corpus["inventory_complete_asserted"] = bool(control.get("inventory_complete_asserted"))
        corpus["inventory_observed_at"] = snap["observed_at"]
        corpus["sources"].sort(key=lambda row: (row["day"], row["source_id"]))
    plan.pop("plan_fingerprint")
    plan["plan_fingerprint"] = inspection._fp(plan)
    inspection._validate_plan(plan)
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "status": "INSPECTION_PLAN_READY",
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "binding_manifest_fingerprint": bound["binding_manifest_fingerprint"],
        "materialization_receipt_fingerprint": materialized["receipt_fingerprint"],
        "inspection_plan_fingerprint": plan["plan_fingerprint"],
        "approved_source_count": len(approved),
        "inspection_plan": plan,
        **_authority(),
    }
    bundle["bundle_fingerprint"] = _fp(bundle)
    validate_bundle(bundle, snapshot=snap, bindings=bound, receipt=materialized)
    return plan, bundle


def validate_bundle(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    bindings: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    checked = _verify(value, "bundle_fingerprint", label="materialization bundle")
    if checked.get("schema") != BUNDLE_SCHEMA or checked.get("status") != "INSPECTION_PLAN_READY":
        raise CorpusMaterializationError("materialization bundle schema/status mismatch")
    _validate_authority(checked, label="materialization bundle")
    snap = validate_snapshot(snapshot)
    bound = validate_bindings(bindings, snapshot=snap, require_approved=True)
    materialized = validate_materialization(
        receipt,
        snapshot=snap,
        bindings=bound,
        verify_files=True,
    )
    if checked.get("snapshot_fingerprint") != snap["snapshot_fingerprint"]:
        raise CorpusMaterializationError("bundle snapshot mismatch")
    if checked.get("binding_manifest_fingerprint") != bound["binding_manifest_fingerprint"]:
        raise CorpusMaterializationError("bundle binding mismatch")
    if checked.get("materialization_receipt_fingerprint") != materialized["receipt_fingerprint"]:
        raise CorpusMaterializationError("bundle receipt mismatch")
    plan = copy.deepcopy(dict(checked.get("inspection_plan") or {}))
    inspection._validate_plan(plan)
    if checked.get("inspection_plan_fingerprint") != plan.get("plan_fingerprint"):
        raise CorpusMaterializationError("bundle inspection-plan mismatch")
    approved_count = sum(row["review_status"] == "APPROVED" for row in bound["bindings"])
    if checked.get("approved_source_count") != approved_count:
        raise CorpusMaterializationError("bundle approved source count mismatch")
    return checked


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise CorpusMaterializationError(f"{path}: expected JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _s3_client() -> Any:
    try:
        import boto3
    except ImportError as error:
        raise CorpusMaterializationError("boto3 is required for S3 operations") from error
    kwargs: dict[str, Any] = {}
    endpoint = os.environ.get("AWS_S3_ENDPOINT")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs)


def selftest() -> int:
    class FakeS3:
        def __init__(self) -> None:
            self.data = {"prefix/a.bin": b"abc"}

        def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "IsTruncated": False,
                "Contents": [
                    {
                        "Key": "prefix/a.bin",
                        "Size": 3,
                        "ETag": '"etag"',
                        "LastModified": "2026-07-22T00:00:00Z",
                    }
                ],
            }

        def download_file(self, bucket: str, key: str, target: str) -> None:
            Path(target).write_bytes(self.data[key])

    fake = FakeS3()
    snap = snapshot_s3(
        fake,
        bucket="bucket",
        prefixes=["prefix/"],
        observed_at="2026-07-22T00:00:00Z",
    )
    bindings = binding_template(snap)
    assert bindings["bindings"][0]["review_status"] == "REVIEW_REQUIRED"
    assert snap["objects"][0]["contract_identity_status"] == "UNOBSERVED"
    print("[ng_corpus_materialization] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory and materialize NG corpus objects safely")
    sub = parser.add_subparsers(dest="command", required=False)

    snapshot = sub.add_parser("snapshot-s3")
    snapshot.add_argument("--bucket", required=True)
    snapshot.add_argument("--prefix", action="append", required=True)
    snapshot.add_argument("--observed-at", default=datetime.now(timezone.utc).isoformat())
    snapshot.add_argument("--scope-complete", action="store_true")
    snapshot.add_argument("--out", type=Path, required=True)

    template = sub.add_parser("init-bindings")
    template.add_argument("--snapshot", type=Path, required=True)
    template.add_argument("--out", type=Path, required=True)

    materialize = sub.add_parser("materialize")
    materialize.add_argument("--snapshot", type=Path, required=True)
    materialize.add_argument("--bindings", type=Path, required=True)
    materialize.add_argument("--output-root", type=Path, required=True)
    materialize.add_argument("--max-total-bytes", type=int, required=True)
    materialize.add_argument("--confirm-download", action="store_true")
    materialize.add_argument("--receipt-out", type=Path, required=True)

    plan = sub.add_parser("build-plan")
    plan.add_argument("--snapshot", type=Path, required=True)
    plan.add_argument("--bindings", type=Path, required=True)
    plan.add_argument("--receipt", type=Path, required=True)
    plan.add_argument("--plan-out", type=Path, required=True)
    plan.add_argument("--bundle-out", type=Path, required=True)

    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.command == "snapshot-s3":
        value = snapshot_s3(
            _s3_client(),
            bucket=args.bucket,
            prefixes=args.prefix,
            observed_at=args.observed_at,
            scope_complete=args.scope_complete,
            endpoint=os.environ.get("AWS_S3_ENDPOINT"),
        )
        _write_json(args.out, value)
        return 0
    if args.command == "init-bindings":
        _write_json(args.out, binding_template(_load_json(args.snapshot)))
        return 0
    if args.command == "materialize":
        value = materialize_approved(
            _s3_client(),
            snapshot=_load_json(args.snapshot),
            bindings=_load_json(args.bindings),
            output_root=args.output_root,
            confirm_download=args.confirm_download,
            max_total_bytes=args.max_total_bytes,
        )
        _write_json(args.receipt_out, value)
        return 0
    if args.command == "build-plan":
        value, bundle = build_inspection_plan(
            snapshot=_load_json(args.snapshot),
            bindings=_load_json(args.bindings),
            receipt=_load_json(args.receipt),
        )
        _write_json(args.plan_out, value)
        _write_json(args.bundle_out, bundle)
        return 0
    parser.error("select a command or --selftest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
