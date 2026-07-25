#!/usr/bin/env python3
"""Resolve exact latest S3 corpus versions from explicit, complete page evidence.

The legacy latest-version resolver accepted one ``list-object-versions`` response per
corpus. AWS CLI normally auto-paginates, but that hides the service-page boundary and
cannot prove that every page marker advanced monotonically. This wrapper performs
service pagination explicitly with ``--no-paginate``, preserves every request/response
page, rejects cycles, duplicate rows, out-of-prefix objects, and incomplete final pages,
then delegates the exact latest-version decision to the existing resolver.

Trading identity is never inferred from S3 keys. Day, lane, publisher, materialization
path, and observed definition remain explicit inputs. No outcomes, posterior mutation,
execution authority, paid live-data assumption, or options implementation is permitted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_latest_version_resolution as legacy

SPEC_SCHEMA = legacy.SPEC_SCHEMA
RECEIPT_SCHEMA = "ng_corpus_s3_paginated_latest_version_resolution_attestation.v1"
READY_STATUS = "S3_PAGINATED_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE"
BLOCKED_STATUS = "S3_PAGINATED_LATEST_VERSION_RESOLUTION_BLOCKED"
DEFAULT_MAX_KEYS = 1000
DEFAULT_MAX_PAGES = 10000


class CorpusS3PaginatedLatestVersionResolutionError(ValueError):
    """Raised when S3 page evidence is malformed, incomplete, or unsafe."""


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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _authority_fields() -> dict[str, Any]:
    return copy.deepcopy(legacy._authority_fields())


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field, expected in _authority_fields().items():
        if value.get(field) != expected:
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{label}: {field} must remain {expected!r}"
            )


def _positive_int(value: Any, *, label: str, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{label} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0 or (maximum is not None and number > maximum):
        suffix = f" no greater than {maximum}" if maximum is not None else ""
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{label} must be a positive integer{suffix}"
        )
    return number


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _page_rows(
    response: Mapping[str, Any], *, field: str, corpus_id: str, page_index: int
) -> list[dict[str, Any]]:
    raw_rows = response.get(field) or []
    if not isinstance(raw_rows, list):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: page {page_index} {field} must be a list"
        )
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: page {page_index} {field} entry is not an object"
            )
        row = copy.deepcopy(dict(raw))
        key = _optional_text(row.get("Key"))
        version_id = _optional_text(row.get("VersionId"))
        if key is None or version_id is None:
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: page {page_index} {field} row requires Key and VersionId"
            )
        rows.append(row)
    return rows


def _normalize_page(
    response: Mapping[str, Any],
    *,
    corpus_id: str,
    page_index: int,
    request_key_marker: str | None,
    request_version_id_marker: str | None,
) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: page {page_index} response is not an object"
        )
    versions = _page_rows(
        response, field="Versions", corpus_id=corpus_id, page_index=page_index
    )
    delete_markers = _page_rows(
        response, field="DeleteMarkers", corpus_id=corpus_id, page_index=page_index
    )
    is_truncated = response.get("IsTruncated") is True
    next_key_marker = _optional_text(response.get("NextKeyMarker"))
    next_version_id_marker = _optional_text(response.get("NextVersionIdMarker"))
    if is_truncated and next_key_marker is None:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: page {page_index} is truncated without NextKeyMarker"
        )
    if not is_truncated and (
        next_key_marker is not None or next_version_id_marker is not None
    ):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: final page {page_index} carries unexpected continuation markers"
        )
    if is_truncated and (
        next_key_marker,
        next_version_id_marker,
    ) == (request_key_marker, request_version_id_marker):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: page {page_index} continuation markers did not advance"
        )
    return {
        "page_index": page_index,
        "request_key_marker": request_key_marker,
        "request_version_id_marker": request_version_id_marker,
        "response": copy.deepcopy(dict(response)),
        "versions": versions,
        "delete_markers": delete_markers,
        "is_truncated": is_truncated,
        "next_key_marker": next_key_marker,
        "next_version_id_marker": next_version_id_marker,
    }


def _combine_pages(
    page_records: Sequence[Mapping[str, Any]], *, corpus_id: str, prefix: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not page_records:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: at least one S3 version page is required"
        )
    expected_request: tuple[str | None, str | None] = (None, None)
    seen_continuations: set[tuple[str | None, str | None]] = set()
    seen_rows: set[tuple[str, str, str]] = set()
    versions: list[dict[str, Any]] = []
    delete_markers: list[dict[str, Any]] = []
    normalized_pages: list[dict[str, Any]] = []

    for page_index, raw_record in enumerate(page_records, start=1):
        if not isinstance(raw_record, Mapping):
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: page record {page_index} is not an object"
            )
        request = raw_record.get("request") or {}
        response = raw_record.get("response")
        if not isinstance(request, Mapping) or not isinstance(response, Mapping):
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: page record {page_index} lacks request/response evidence"
            )
        request_key = _optional_text(request.get("key_marker"))
        request_version = _optional_text(request.get("version_id_marker"))
        if (request_key, request_version) != expected_request:
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: page {page_index} request markers do not follow prior page"
            )
        normalized = _normalize_page(
            response,
            corpus_id=corpus_id,
            page_index=page_index,
            request_key_marker=request_key,
            request_version_id_marker=request_version,
        )
        for kind, rows, target in (
            ("version", normalized["versions"], versions),
            ("delete_marker", normalized["delete_markers"], delete_markers),
        ):
            for row in rows:
                key = str(row["Key"])
                version_id = str(row["VersionId"])
                if not key.startswith(prefix):
                    raise CorpusS3PaginatedLatestVersionResolutionError(
                        f"{corpus_id}: page {page_index} returned out-of-prefix key {key!r}"
                    )
                identity = (kind, key, version_id)
                if identity in seen_rows:
                    raise CorpusS3PaginatedLatestVersionResolutionError(
                        f"{corpus_id}: duplicate {kind} across pages for {key!r} {version_id!r}"
                    )
                seen_rows.add(identity)
                target.append(copy.deepcopy(row))
        normalized_pages.append(
            {
                "page_index": page_index,
                "request_key_marker": request_key,
                "request_version_id_marker": request_version,
                "is_truncated": normalized["is_truncated"],
                "next_key_marker": normalized["next_key_marker"],
                "next_version_id_marker": normalized["next_version_id_marker"],
                "version_count": len(normalized["versions"]),
                "delete_marker_count": len(normalized["delete_markers"]),
                "response_fingerprint": _fp(response),
            }
        )
        if normalized["is_truncated"]:
            continuation = (
                normalized["next_key_marker"],
                normalized["next_version_id_marker"],
            )
            if continuation in seen_continuations:
                raise CorpusS3PaginatedLatestVersionResolutionError(
                    f"{corpus_id}: continuation-marker cycle detected at page {page_index}"
                )
            seen_continuations.add(continuation)
            expected_request = continuation
        else:
            if page_index != len(page_records):
                raise CorpusS3PaginatedLatestVersionResolutionError(
                    f"{corpus_id}: evidence continues after final page {page_index}"
                )
            expected_request = (None, None)

    if normalized_pages[-1]["is_truncated"]:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"{corpus_id}: pagination evidence ended on a truncated page"
        )
    combined = {
        "Versions": sorted(
            versions, key=lambda row: (str(row.get("Key")), str(row.get("VersionId")))
        ),
        "DeleteMarkers": sorted(
            delete_markers,
            key=lambda row: (str(row.get("Key")), str(row.get("VersionId"))),
        ),
        "IsTruncated": False,
    }
    summary = {
        "corpus_id": corpus_id,
        "page_count": len(normalized_pages),
        "version_count": len(versions),
        "delete_marker_count": len(delete_markers),
        "complete_pagination_attested": True,
        "pages": normalized_pages,
        "pages_fingerprint": _fp(normalized_pages),
        "combined_response_fingerprint": _fp(combined),
    }
    return combined, summary


def build_from_paginated_evidence(
    source_spec: Mapping[str, Any],
    *,
    captured_pages: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"resolution spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="paginated resolution spec")
    corpora = list(spec.get("corpora") or [])
    declared_ids = [str(corpus.get("corpus_id") or "") for corpus in corpora]
    if set(captured_pages) != set(declared_ids) or len(declared_ids) != len(
        set(declared_ids)
    ):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "captured page sets must exactly match unique declared corpus IDs"
        )

    combined_responses: dict[str, dict[str, Any]] = {}
    pagination_summaries: list[dict[str, Any]] = []
    for corpus in corpora:
        corpus_id = str(corpus.get("corpus_id") or "")
        prefix = str(corpus.get("prefix") or "")
        combined, summary = _combine_pages(
            captured_pages[corpus_id], corpus_id=corpus_id, prefix=prefix
        )
        combined_responses[corpus_id] = combined
        pagination_summaries.append(summary)

    capture_spec, legacy_receipt = legacy._build_from_evidence(
        spec, list_responses=combined_responses
    )
    blockers = sorted(set(legacy_receipt.get("blockers") or []))
    status = READY_STATUS if legacy_receipt.get("status") == legacy.READY_STATUS else BLOCKED_STATUS
    captured = copy.deepcopy(dict(captured_pages))
    combined_evidence = {"list_object_versions": combined_responses}
    summaries = sorted(pagination_summaries, key=lambda row: row["corpus_id"])
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "captured_pages": captured,
        "captured_pages_fingerprint": _fp(captured),
        "pagination_summaries": summaries,
        "pagination_summaries_fingerprint": _fp(summaries),
        "combined_list_evidence": combined_evidence,
        "combined_list_evidence_fingerprint": _fp(combined_evidence),
        "legacy_resolution_receipt": legacy_receipt,
        "legacy_resolution_receipt_fingerprint": legacy_receipt.get(
            "receipt_fingerprint"
        ),
        "capture_spec": capture_spec,
        "capture_spec_fingerprint": _fp(capture_spec),
        "complete_pagination_attested": True,
        "identity_from_s3_keys_inferred": False,
        "blockers": blockers,
        "next_action": (
            "RUN_EXACT_S3_INVENTORY_CAPTURE"
            if not blockers
            else "RESOLVE_S3_LATEST_VERSION_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return capture_spec, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != RECEIPT_SCHEMA or observed != _fp(checked):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated resolution receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="paginated resolution receipt")
    if checked.get("complete_pagination_attested") is not True:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "complete S3 service pagination must be attested"
        )
    if checked.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "trading identity may not be inferred from S3 keys"
        )
    spec = checked.get("source_spec")
    pages = checked.get("captured_pages")
    if not isinstance(spec, Mapping) or not isinstance(pages, Mapping):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated resolution receipt lacks embedded source/page evidence"
        )
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated resolution source-spec fingerprint mismatch"
        )
    if checked.get("captured_pages_fingerprint") != _fp(pages):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated resolution page-evidence fingerprint mismatch"
        )
    capture_spec, rebuilt = build_from_paginated_evidence(
        spec, captured_pages=pages
    )
    if checked.get("capture_spec_fingerprint") != _fp(capture_spec):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated capture-spec fingerprint mismatch"
        )
    nested = checked.get("legacy_resolution_receipt")
    if not isinstance(nested, Mapping):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "legacy exact-resolution receipt is missing"
        )
    legacy.validate_receipt(nested)
    if rebuilt != dict(value):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "paginated resolution receipt differs from deterministic rebuild"
        )
    return copy.deepcopy(dict(value))


def _run_json(argv: Sequence[str]) -> dict[str, Any]:
    process = subprocess.run(
        list(argv),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"AWS CLI command failed ({process.returncode}): {' '.join(argv)}: "
            f"{process.stderr.strip()}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CorpusS3PaginatedLatestVersionResolutionError(
            f"AWS CLI returned invalid JSON: {' '.join(argv)}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3PaginatedLatestVersionResolutionError(
            "AWS CLI response must be a JSON object"
        )
    return value


def resolve_live(
    source_spec: Mapping[str, Any],
    *,
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], dict[str, Any]] = _run_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    _authority(spec, label="paginated resolution spec")
    max_keys = _positive_int(
        spec.get("pagination_max_keys", DEFAULT_MAX_KEYS),
        label="pagination_max_keys",
        maximum=DEFAULT_MAX_KEYS,
    )
    max_pages = _positive_int(
        spec.get("pagination_max_pages", DEFAULT_MAX_PAGES),
        label="pagination_max_pages",
    )
    global_args: list[str] = [aws_executable]
    profile = str(spec.get("aws_profile") or "")
    region = str(spec.get("aws_region") or "")
    if profile:
        global_args.extend(["--profile", profile])
    if region:
        global_args.extend(["--region", region])

    captured_pages: dict[str, list[dict[str, Any]]] = {}
    for corpus in spec.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        bucket = str(corpus.get("bucket") or "")
        prefix = str(corpus.get("prefix") or "")
        pages: list[dict[str, Any]] = []
        key_marker: str | None = None
        version_marker: str | None = None
        seen_requests: set[tuple[str | None, str | None]] = set()
        for page_index in range(1, max_pages + 1):
            request_markers = (key_marker, version_marker)
            if request_markers in seen_requests:
                raise CorpusS3PaginatedLatestVersionResolutionError(
                    f"{corpus_id}: request-marker cycle before page {page_index}"
                )
            seen_requests.add(request_markers)
            argv = [
                *global_args,
                "s3api",
                "list-object-versions",
                "--bucket",
                bucket,
                "--prefix",
                prefix,
                "--max-keys",
                str(max_keys),
                "--no-paginate",
                "--output",
                "json",
            ]
            if key_marker is not None:
                argv.extend(["--key-marker", key_marker])
            if version_marker is not None:
                argv.extend(["--version-id-marker", version_marker])
            response = runner(argv)
            pages.append(
                {
                    "request": {
                        "page_index": page_index,
                        "key_marker": key_marker,
                        "version_id_marker": version_marker,
                        "argv": argv,
                    },
                    "response": copy.deepcopy(response),
                }
            )
            normalized = _normalize_page(
                response,
                corpus_id=corpus_id,
                page_index=page_index,
                request_key_marker=key_marker,
                request_version_id_marker=version_marker,
            )
            if not normalized["is_truncated"]:
                break
            key_marker = normalized["next_key_marker"]
            version_marker = normalized["next_version_id_marker"]
        else:
            raise CorpusS3PaginatedLatestVersionResolutionError(
                f"{corpus_id}: pagination exceeded pagination_max_pages={max_pages}"
            )
        captured_pages[corpus_id] = pages
    return build_from_paginated_evidence(spec, captured_pages=captured_pages)


def _selftest_spec() -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "pagination_max_keys": 1,
        "corpora": [],
        **_authority_fields(),
    }
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        prefix = f"ng/{corpus_id}/"
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "selftest-bucket",
                "prefix": prefix,
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [
                    {
                        "source_id": f"{corpus_id}-source",
                        "day": "20260315",
                        "lane": expected["lane"],
                        "key": f"{prefix}source.dbn",
                        "materialized_path": f"data/{corpus_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
    return spec


def selftest() -> int:
    spec = _selftest_spec()
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> dict[str, Any]:
        call = list(argv)
        calls.append(call)
        prefix = call[call.index("--prefix") + 1]
        source_id = prefix.rstrip("/").split("/")[-1] + "-source"
        key = prefix + "source.dbn"
        if "--key-marker" not in call:
            return {
                "Versions": [
                    {
                        "Key": key,
                        "VersionId": "old",
                        "IsLatest": False,
                        "LastModified": "2026-07-24T00:00:00Z",
                        "Size": 8,
                        "ETag": source_id + "-old",
                    }
                ],
                "IsTruncated": True,
                "NextKeyMarker": key,
                "NextVersionIdMarker": "old",
            }
        return {
            "Versions": [
                {
                    "Key": key,
                    "VersionId": "v1",
                    "IsLatest": True,
                    "LastModified": "2026-07-25T00:00:00Z",
                    "Size": 8,
                    "ETag": source_id,
                }
            ],
            "IsTruncated": False,
        }

    capture_spec, receipt = resolve_live(spec, runner=runner)
    assert receipt["status"] == READY_STATUS
    assert all(summary["page_count"] == 2 for summary in receipt["pagination_summaries"])
    assert all("--no-paginate" in call for call in calls)
    assert any("--key-marker" in call for call in calls)
    assert all(
        source["version_id"] == "v1"
        for corpus in capture_spec["corpora"]
        for source in corpus["sources"]
    )
    validate_receipt(receipt)
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = _fp(
        {key: item for key, item in tampered.items() if key != "receipt_fingerprint"}
    )
    try:
        validate_receipt(tampered)
    except CorpusS3PaginatedLatestVersionResolutionError:
        print("[ng_corpus_s3_paginated_latest_version_resolution] selftest PASS")
        return 0
    raise AssertionError("authority escalation was accepted")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--spec", type=Path, required=True)
    resolve_parser.add_argument("--capture-spec-out", type=Path, required=True)
    resolve_parser.add_argument("--receipt-out", type=Path, required=True)
    resolve_parser.add_argument("--aws-executable", default="aws")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--receipt", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    if args.command == "validate":
        receipt = validate_receipt(_load(args.receipt))
        print(json.dumps({"status": receipt["status"]}, sort_keys=True))
        return 0
    capture_spec, receipt = resolve_live(
        _load(args.spec), aws_executable=args.aws_executable
    )
    _write(args.receipt_out, receipt)
    if receipt["status"] != READY_STATUS:
        print(
            json.dumps(
                {"status": receipt["status"], "blockers": receipt["blockers"]},
                sort_keys=True,
            )
        )
        return 2
    _write(args.capture_spec_out, capture_spec)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "capture_spec": str(args.capture_spec_out),
                "receipt": str(args.receipt_out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
