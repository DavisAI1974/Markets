#!/usr/bin/env python3
"""Freeze the exact native-MBO population for the five-year Step-1 census.

The scientific population is derived only from the deterministic 61-interval
calendar and the exact job/segment receipts created by acquisition.  This
module deliberately has no S3 list operation and never treats a prefix as a
population definition.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_REGION = "us-east-2"
DEFAULT_BUCKET = "bento-568968024170-us-east-2-an"
DEFAULT_PREFIX = "nymex/ng_mbo_5y_v0/"
START = dt.date(2021, 8, 20)
END = dt.date(2026, 8, 20)
REVISION = "NG_EXHAUSTION_MBO_5Y_CANONICAL_MANIFEST_V1_20260822"
DATASET = "GLBX.MDP3"
SCHEMA = "mbo"
SYMBOL = "NG.v.0"
STYPE_IN = "continuous"


class ManifestFreezeError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def payload_sha256(value: dict[str, Any], hash_field: str = "manifest_sha256") -> str:
    body = {k: v for k, v in value.items() if k != hash_field}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def expected_intervals(start: dt.date = START, end: dt.date = END) -> list[tuple[dt.date, dt.date]]:
    rows = []
    cur = start
    while cur < end:
        nxt = dt.date(cur.year + 1, 1, 1) if cur.month == 12 else dt.date(cur.year, cur.month + 1, 1)
        stop = min(nxt, end)
        rows.append((cur, stop))
        cur = stop
    return rows


def acquisition_intervals(start: dt.date = START, end: dt.date = END) -> list[tuple[dt.date, dt.date]]:
    """Return the exact year-lane/month segments written by native acquisition.

    The acquisition lanes were year-bounded at August 20, so four August
    calendar intervals are represented by two adjacent native manifests.  This
    deterministic 65-segment grid is reconciled into the scientific 61-month
    grid below; it is not discovered by listing S3.
    """
    rows = []
    lane_start = start
    while lane_start < end:
        lane_end = min(dt.date(lane_start.year + 1, lane_start.month, lane_start.day), end)
        rows.extend(expected_intervals(lane_start, lane_end))
        lane_start = lane_end
    return rows


def segment_id(start: dt.date, end: dt.date) -> str:
    return f"{start:%Y%m%d}_{end:%Y%m%d}"


def _require_equal(row: dict[str, Any], field: str, expected: Any, source: str) -> None:
    if row.get(field) != expected:
        raise ManifestFreezeError(
            f"{source}: {field} drift: expected={expected!r} actual={row.get(field)!r}"
        )


def _normalize_file_entry(entry: dict[str, Any], prefix: str, segment: str) -> dict[str, Any]:
    key = entry.get("s3_key") or entry.get("key")
    if not isinstance(key, str):
        raise ManifestFreezeError(f"segment {segment}: manifest file lacks s3_key")
    expected_root = f"{prefix.rstrip('/')}/native/{segment}/"
    if not key.startswith(expected_root) or not key.endswith((".dbn", ".dbn.zst")):
        raise ManifestFreezeError(f"segment {segment}: out-of-scope native key {key!r}")
    try:
        size = int(entry["bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestFreezeError(f"segment {segment}: invalid bytes for {key}") from exc
    digest = str(entry.get("sha256", "")).lower()
    if size <= 0 or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ManifestFreezeError(f"segment {segment}: invalid size/SHA-256 for {key}")
    return {"key": key, "bytes": size, "sha256": digest}


def _head_last_modified(head: dict[str, Any]) -> str | None:
    value = head.get("LastModified")
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def freeze_manifest(
    *,
    bucket: str,
    prefix: str,
    get_json_bytes: Callable[[str], bytes],
    get_json_optional: Callable[[str], tuple[bytes, dict[str, Any]] | None],
    head_object: Callable[[str], dict[str, Any]],
    archive_audit: dict[str, Any],
    intervals: Iterable[tuple[dt.date, dt.date]] | None = None,
) -> dict[str, Any]:
    """Build and validate an immutable exact-object manifest.

    ``get_json_bytes`` is required for expected exact receipts and manifests;
    optional reads are used only to document aliases/collisions.  No callback
    capable of listing a prefix is accepted by this API.
    """
    prefix = prefix.strip("/") + "/"
    expected = list(intervals or expected_intervals())
    objects: list[dict[str, Any]] = []
    selected_intervals: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    native_grid = acquisition_intervals(START, END)
    native_by_expected: dict[tuple[dt.date, dt.date], list[tuple[dt.date, dt.date]]] = {}
    for source_start, source_end in native_grid:
        parents = [
            pair for pair in expected
            if pair[0] <= source_start and source_end <= pair[1]
        ]
        if len(parents) != 1:
            raise ManifestFreezeError(
                f"native segment {source_start}..{source_end} does not map to one expected interval"
            )
        native_by_expected.setdefault(parents[0], []).append((source_start, source_end))

    for start, end in expected:
        seg = segment_id(start, end)
        job_key = f"{prefix}_jobs/{seg}.json"
        try:
            job_raw = get_json_bytes(job_key)
        except Exception as exc:
            raise ManifestFreezeError(f"required exact job provenance missing for {seg}: {exc}") from exc
        job = json.loads(job_raw)
        _require_equal(job, "start", start.isoformat(), job_key)
        _require_equal(job, "end", end.isoformat(), job_key)
        job_id = str(job.get("job_id") or "")
        if not job_id:
            raise ManifestFreezeError(f"{job_key}: canonical job_id unavailable")

        interval_objects = []
        native_manifests = []
        native_parts = sorted(native_by_expected.get((start, end), []))
        cursor = start
        for source_start, source_end in native_parts:
            if source_start != cursor:
                raise ManifestFreezeError(f"native manifest coverage gap inside {seg} at {cursor}")
            cursor = source_end
        if cursor != end:
            raise ManifestFreezeError(f"native manifest coverage incomplete inside {seg}: ends {cursor}")

        for source_start, source_end in native_parts:
            source_seg = segment_id(source_start, source_end)
            manifest_key = f"{prefix}manifests/{source_seg}.json"
            try:
                manifest_raw = get_json_bytes(manifest_key)
            except Exception as exc:
                raise ManifestFreezeError(
                    f"required deterministic native manifest missing for {source_seg}: {exc}"
                ) from exc
            source_manifest = json.loads(manifest_raw)
            _require_equal(source_manifest, "start", source_start.isoformat(), manifest_key)
            _require_equal(source_manifest, "end", source_end.isoformat(), manifest_key)
            _require_equal(source_manifest, "segment", source_seg, manifest_key)
            _require_equal(source_manifest, "dataset", DATASET, manifest_key)
            _require_equal(source_manifest, "symbol", SYMBOL, manifest_key)
            _require_equal(source_manifest, "stype_in", STYPE_IN, manifest_key)
            _require_equal(source_manifest, "data_schema", SCHEMA, manifest_key)
            native_job_id = str(source_manifest.get("job_id") or "")
            if not native_job_id:
                raise ManifestFreezeError(f"{manifest_key}: native job_id unavailable")
            if len(native_parts) == 1 and native_job_id != job_id:
                raise ManifestFreezeError(
                    f"{manifest_key}: exact native job differs from canonical receipt {job_id}"
                )
            files = source_manifest.get("files")
            if not isinstance(files, list) or not files:
                raise ManifestFreezeError(f"{manifest_key}: native file list is empty")
            native_manifests.append({
                "segment": source_seg,
                "interval": {"start": source_start.isoformat(), "end": source_end.isoformat()},
                "native_job_id": native_job_id,
                "segment_manifest_key": manifest_key,
                "segment_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            })

            for entry in files:
                normalized = _normalize_file_entry(entry, prefix, source_seg)
                key = normalized["key"]
                if key in seen_keys:
                    raise ManifestFreezeError(f"canonical native key selected twice: {key}")
                head = head_object(key)
                actual_bytes = int(head.get("ContentLength", 0))
                metadata = {str(k).lower(): str(v) for k, v in (head.get("Metadata") or {}).items()}
                if actual_bytes != normalized["bytes"]:
                    raise ManifestFreezeError(
                        f"{key}: content length drift manifest={normalized['bytes']} s3={actual_bytes}"
                    )
                if metadata.get("sha256", "").lower() != normalized["sha256"]:
                    raise ManifestFreezeError(f"{key}: S3 SHA-256 metadata drift")
                for field, wanted in (
                    ("dataset", DATASET), ("schema", SCHEMA), ("symbol", SYMBOL),
                    ("stype", STYPE_IN), ("job_id", native_job_id), ("segment", source_seg),
                ):
                    if metadata.get(field) != wanted:
                        raise ManifestFreezeError(
                            f"{key}: S3 metadata {field} drift expected={wanted!r} actual={metadata.get(field)!r}"
                        )
                selection_reason = (
                    "EXACT_EXPECTED_INTERVAL_EXACT_JOB_AND_SEGMENT_MANIFEST"
                    if len(native_parts) == 1
                    else "ADJACENT_NATIVE_SEGMENTS_EXACTLY_TILE_EXPECTED_INTERVAL_WITHOUT_OVERLAP"
                )
                obj = {
                    **normalized,
                    "bucket": bucket,
                    "interval": {"start": start.isoformat(), "end": end.isoformat()},
                    "segment": source_seg,
                    "canonical_interval_job_id": job_id,
                    "native_segment_job_id": native_job_id,
                    "requested_symbol": SYMBOL,
                    "stype_in": STYPE_IN,
                    "raw_contract_resolution": "DBN_METADATA_DURING_CAUSAL_REPLAY",
                    "selection_reason": selection_reason,
                    "s3_etag": str(head.get("ETag", "")).strip('"'),
                    "s3_last_modified": _head_last_modified(head),
                }
                objects.append(obj)
                interval_objects.append(key)
                seen_keys.add(key)

        if len(native_parts) > 1:
            exclusions.append({
                "kind": "UNMATERIALIZED_FULL_MONTH_CANONICAL_JOB",
                "interval": {"start": start.isoformat(), "end": end.isoformat()},
                "excluded_job_id": job_id,
                "selected_native_job_ids": [x["native_job_id"] for x in native_manifests],
                "reason": "EXISTING_ADJACENT_NATIVE_MANIFESTS_EXACTLY_TILE_INTERVAL;_DO_NOT_REDUPLICATE_BYTES",
            })

        legacy_key = f"{prefix}_jobs/{start:%Y-%m}.json"
        legacy_result = get_json_optional(legacy_key)
        if legacy_result is not None:
            _, legacy = legacy_result
            legacy_id = str(legacy.get("job_id") or "")
            if (
                legacy.get("start") == start.isoformat()
                and legacy.get("end") == end.isoformat()
                and legacy_id
                and legacy_id != job_id
            ):
                exclusions.append({
                    "kind": "DUPLICATE_EXPECTED_INTERVAL_JOB",
                    "interval": {"start": start.isoformat(), "end": end.isoformat()},
                    "excluded_job_id": legacy_id,
                    "selected_job_id": job_id,
                    "provenance_key": legacy_key,
                    "reason": "EXACT_RECEIPT_AND_EXACT_SEGMENT_MANIFEST_TAKE_PRECEDENCE",
                })

        selected_intervals.append({
            "interval": {"start": start.isoformat(), "end": end.isoformat()},
            "segment": seg,
            "canonical_job_id": job_id,
            "job_receipt_key": job_key,
            "job_receipt_sha256": hashlib.sha256(job_raw).hexdigest(),
            "native_manifests": native_manifests,
            "canonical_object_count": len(interval_objects),
            "canonical_object_keys": interval_objects,
        })

    expected_pairs = {(a.isoformat(), b.isoformat()) for a, b in expected}
    for row in archive_audit.get("unexpected_intervals", []):
        pair = (row.get("start"), row.get("end"))
        if pair in expected_pairs:
            raise ManifestFreezeError(f"archive audit marks expected interval unexpected: {pair}")
        for job_id in sorted(str(x) for x in row.get("job_ids", []) if x):
            exclusions.append({
                "kind": "UNEXPECTED_PARTIAL_OVERLAP_JOB",
                "interval": {"start": pair[0], "end": pair[1]},
                "excluded_job_id": job_id,
                "reason": "OUTSIDE_DETERMINISTIC_61_INTERVAL_POPULATION_GRID",
            })

    if len(selected_intervals) != len(expected):
        raise ManifestFreezeError("selected interval count drift")
    result = {
        "schema": REVISION,
        "status": "CANONICAL_NATIVE_MBO_OBJECT_MANIFEST_FROZEN_AND_S3_VALIDATED",
        "region": DEFAULT_REGION,
        "bucket": bucket,
        "prefix": prefix,
        "dataset": DATASET,
        "data_schema": SCHEMA,
        "requested_symbol": SYMBOL,
        "stype_in": STYPE_IN,
        "approved_range": {"start": START.isoformat(), "end": END.isoformat()},
        "selection_policy": "EXACT_61_INTERVAL_RECEIPTS_RECONCILED_TO_DETERMINISTIC_65_NATIVE_SEGMENT_GRID",
        "prefix_wide_enumeration_used": False,
        "expected_interval_count": len(expected),
        "selected_interval_count": len(selected_intervals),
        "deterministic_native_segment_count": len(native_grid),
        "selected_intervals": selected_intervals,
        "canonical_object_count": len(objects),
        "canonical_total_bytes": sum(x["bytes"] for x in objects),
        "canonical_dbn_keys": [x["key"] for x in objects],
        "canonical_dbn_objects": objects,
        "exclusions": sorted(
            exclusions,
            key=lambda x: (x["interval"]["start"], x["kind"], x["excluded_job_id"]),
        ),
        "archive_audit_sha256": hashlib.sha256(canonical_json_bytes(archive_audit)).hexdigest(),
        "every_selected_object_s3_head_validated": True,
        "release_or_virgin_holdout_consumed": False,
        "empirical_census_launched": False,
    }
    result["manifest_sha256"] = payload_sha256(result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    ap.add_argument(
        "--archive-audit",
        default="research/kalshi/NG_MBO_5Y_COMPACT_AUDIT_20260820.json",
    )
    ap.add_argument(
        "--out",
        default="research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json",
    )
    args = ap.parse_args()

    try:
        import boto3
    except ImportError as exc:
        raise SystemExit("boto3 is required for the live canonical-manifest freeze") from exc
    s3 = boto3.client("s3", region_name=args.region)

    def raw_required(key: str) -> bytes:
        return s3.get_object(Bucket=args.bucket, Key=key)["Body"].read()

    def optional(key: str) -> tuple[bytes, dict[str, Any]] | None:
        try:
            raw = raw_required(key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise
        return raw, json.loads(raw)

    def head(key: str) -> dict[str, Any]:
        return s3.head_object(Bucket=args.bucket, Key=key)

    archive_audit = json.loads(Path(args.archive_audit).read_text())
    manifest = freeze_manifest(
        bucket=args.bucket,
        prefix=args.prefix,
        get_json_bytes=raw_required,
        get_json_optional=optional,
        head_object=head,
        archive_audit=archive_audit,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": manifest["status"],
        "manifest_sha256": manifest["manifest_sha256"],
        "selected_interval_count": manifest["selected_interval_count"],
        "canonical_object_count": manifest["canonical_object_count"],
        "canonical_total_bytes": manifest["canonical_total_bytes"],
        "exclusion_count": len(manifest["exclusions"]),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
