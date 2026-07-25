#!/usr/bin/env python3
"""Capture checksum-enabled S3 inventory from complete explicit service pagination.

The legacy inventory capture issued one ``list-object-versions`` call per corpus and
failed closed whenever that response was truncated. This stage performs explicit
service pagination with ``--no-paginate``, fingerprints every request/response page,
rejects marker cycles, duplicate rows, out-of-prefix objects, and incomplete final
pages, then delegates exact latest-object and checksum/head validation to the existing
inventory capture contract.

Trading identity is never inferred from S3 keys. No outcomes, posterior mutation,
execution authority, paid live-data assumption, or options implementation is allowed.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_inventory_capture as legacy
import ng_corpus_s3_paginated_latest_version_resolution as pagination

SPEC_SCHEMA = legacy.SPEC_SCHEMA
MATERIALIZATION_SCHEMA = legacy.MATERIALIZATION_SCHEMA
RECEIPT_SCHEMA = "ng_corpus_s3_paginated_inventory_capture_attestation.v1"
READY_STATUS = "S3_PAGINATED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"
BLOCKED_STATUS = "S3_PAGINATED_INVENTORY_CAPTURE_BLOCKED"
DEFAULT_MAX_KEYS = pagination.DEFAULT_MAX_KEYS
DEFAULT_MAX_PAGES = pagination.DEFAULT_MAX_PAGES


class CorpusS3PaginatedInventoryCaptureError(ValueError):
    """Raised when paginated inventory evidence is malformed or unsafe."""


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
        raise CorpusS3PaginatedInventoryCaptureError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3PaginatedInventoryCaptureError(
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
            raise CorpusS3PaginatedInventoryCaptureError(
                f"{label}: {field} must remain {expected!r}"
            )


def _positive_int(value: Any, *, label: str, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise CorpusS3PaginatedInventoryCaptureError(
            f"{label} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3PaginatedInventoryCaptureError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0 or (maximum is not None and number > maximum):
        suffix = f" no greater than {maximum}" if maximum is not None else ""
        raise CorpusS3PaginatedInventoryCaptureError(
            f"{label} must be a positive integer{suffix}"
        )
    return number


def build_from_paginated_evidence(
    source_spec: Mapping[str, Any],
    *,
    captured_pages: Mapping[str, Sequence[Mapping[str, Any]]],
    head_responses: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build materialization input and attestation from complete page/head evidence."""

    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusS3PaginatedInventoryCaptureError(
            f"inventory capture spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="paginated inventory capture spec")

    corpora = list(spec.get("corpora") or [])
    declared_ids = [str(corpus.get("corpus_id") or "") for corpus in corpora]
    if set(captured_pages) != set(declared_ids) or len(declared_ids) != len(
        set(declared_ids)
    ):
        raise CorpusS3PaginatedInventoryCaptureError(
            "captured page sets must exactly match unique declared corpus IDs"
        )

    declared_sources = {
        str(source.get("source_id") or "")
        for corpus in corpora
        for source in (corpus.get("sources") or [])
    }
    if "" in declared_sources or set(head_responses) != declared_sources:
        raise CorpusS3PaginatedInventoryCaptureError(
            "head-object evidence must exactly match declared source IDs"
        )

    combined_responses: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []
    for corpus in corpora:
        corpus_id = str(corpus.get("corpus_id") or "")
        prefix = str(corpus.get("prefix") or "")
        try:
            combined, summary = pagination._combine_pages(
                captured_pages[corpus_id], corpus_id=corpus_id, prefix=prefix
            )
        except Exception as error:
            raise CorpusS3PaginatedInventoryCaptureError(str(error)) from error
        combined_responses[corpus_id] = combined
        summaries.append(summary)

    materialization_spec, legacy_receipt = legacy._build_from_evidence(
        spec,
        list_responses=combined_responses,
        head_responses=head_responses,
    )
    blockers = sorted(set(legacy_receipt.get("blockers") or []))
    status = (
        READY_STATUS
        if legacy_receipt.get("status") == legacy.READY_STATUS and not blockers
        else BLOCKED_STATUS
    )
    captured = copy.deepcopy(dict(captured_pages))
    heads = copy.deepcopy(dict(head_responses))
    combined_evidence = {
        "list_object_versions": combined_responses,
        "head_objects": heads,
    }
    ordered_summaries = sorted(summaries, key=lambda row: row["corpus_id"])
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "captured_pages": captured,
        "captured_pages_fingerprint": _fp(captured),
        "pagination_summaries": ordered_summaries,
        "pagination_summaries_fingerprint": _fp(ordered_summaries),
        "captured_head_objects": heads,
        "captured_head_objects_fingerprint": _fp(heads),
        "combined_inventory_evidence": combined_evidence,
        "combined_inventory_evidence_fingerprint": _fp(combined_evidence),
        "legacy_capture_receipt": legacy_receipt,
        "legacy_capture_receipt_fingerprint": legacy_receipt.get(
            "receipt_fingerprint"
        ),
        "materialization_spec": materialization_spec,
        "materialization_spec_fingerprint": _fp(materialization_spec),
        "complete_pagination_attested": True,
        "checksum_enabled_heads_attested": True,
        "identity_from_s3_keys_inferred": False,
        "blockers": blockers,
        "next_action": (
            "RUN_S3_MATERIALIZATION_ATTESTATION"
            if not blockers
            else "RESOLVE_S3_INVENTORY_CAPTURE_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return materialization_spec, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != RECEIPT_SCHEMA or observed != _fp(checked):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="paginated inventory receipt")
    if checked.get("complete_pagination_attested") is not True:
        raise CorpusS3PaginatedInventoryCaptureError(
            "complete S3 service pagination must be attested"
        )
    if checked.get("checksum_enabled_heads_attested") is not True:
        raise CorpusS3PaginatedInventoryCaptureError(
            "checksum-enabled head-object capture must be attested"
        )
    if checked.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusS3PaginatedInventoryCaptureError(
            "trading identity may not be inferred from S3 keys"
        )

    spec = checked.get("source_spec")
    pages = checked.get("captured_pages")
    heads = checked.get("captured_head_objects")
    if not isinstance(spec, Mapping) or not isinstance(pages, Mapping) or not isinstance(
        heads, Mapping
    ):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory receipt lacks embedded source/page/head evidence"
        )
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory source-spec fingerprint mismatch"
        )
    if checked.get("captured_pages_fingerprint") != _fp(pages):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory page-evidence fingerprint mismatch"
        )
    if checked.get("captured_head_objects_fingerprint") != _fp(heads):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory head-evidence fingerprint mismatch"
        )

    materialization_spec, rebuilt = build_from_paginated_evidence(
        spec,
        captured_pages=pages,
        head_responses=heads,
    )
    if checked.get("materialization_spec_fingerprint") != _fp(materialization_spec):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory materialization-spec fingerprint mismatch"
        )
    nested = checked.get("legacy_capture_receipt")
    if not isinstance(nested, Mapping):
        raise CorpusS3PaginatedInventoryCaptureError(
            "legacy exact inventory capture receipt is missing"
        )
    legacy.validate_receipt(nested)
    if checked.get("legacy_capture_receipt_fingerprint") != nested.get(
        "receipt_fingerprint"
    ):
        raise CorpusS3PaginatedInventoryCaptureError(
            "legacy capture receipt fingerprint link mismatch"
        )
    if rebuilt != dict(value):
        raise CorpusS3PaginatedInventoryCaptureError(
            "paginated inventory receipt differs from deterministic rebuild"
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
        raise CorpusS3PaginatedInventoryCaptureError(
            f"AWS CLI command failed ({process.returncode}): {' '.join(argv)}: "
            f"{process.stderr.strip()}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CorpusS3PaginatedInventoryCaptureError(
            f"AWS CLI returned invalid JSON: {' '.join(argv)}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3PaginatedInventoryCaptureError(
            "AWS CLI response must be a JSON object"
        )
    return value


def capture_live(
    source_spec: Mapping[str, Any],
    *,
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], dict[str, Any]] = _run_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    _authority(spec, label="paginated inventory capture spec")
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
    head_responses: dict[str, Mapping[str, Any]] = {}
    for corpus in spec.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        bucket = str(corpus.get("bucket") or "")
        prefix = str(corpus.get("prefix") or "")
        pages: list[dict[str, Any]] = []
        key_marker: str | None = None
        version_marker: str | None = None
        seen_requests: set[tuple[str | None, str | None]] = set()
        for page_index in range(1, max_pages + 1):
            markers = (key_marker, version_marker)
            if markers in seen_requests:
                raise CorpusS3PaginatedInventoryCaptureError(
                    f"{corpus_id}: request-marker cycle before page {page_index}"
                )
            seen_requests.add(markers)
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
            try:
                normalized = pagination._normalize_page(
                    response,
                    corpus_id=corpus_id,
                    page_index=page_index,
                    request_key_marker=key_marker,
                    request_version_id_marker=version_marker,
                )
            except Exception as error:
                raise CorpusS3PaginatedInventoryCaptureError(str(error)) from error
            if not normalized["is_truncated"]:
                break
            key_marker = normalized["next_key_marker"]
            version_marker = normalized["next_version_id_marker"]
        else:
            raise CorpusS3PaginatedInventoryCaptureError(
                f"{corpus_id}: pagination exceeded pagination_max_pages={max_pages}"
            )
        captured_pages[corpus_id] = pages

        for source in corpus.get("sources") or []:
            source_id = str(source.get("source_id") or "")
            head_argv = [
                *global_args,
                "s3api",
                "head-object",
                "--bucket",
                bucket,
                "--key",
                str(source.get("key") or ""),
                "--version-id",
                str(source.get("version_id") or ""),
                "--checksum-mode",
                "ENABLED",
                "--output",
                "json",
            ]
            head_responses[source_id] = runner(head_argv)

    return build_from_paginated_evidence(
        spec,
        captured_pages=captured_pages,
        head_responses=head_responses,
    )


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
                        "version_id": "v1",
                        "materialized_path": f"data/{corpus_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
    return spec


def selftest() -> int:
    spec = _selftest_spec()
    checksum = base64.b64encode(hashlib.sha256(b"selftest").digest()).decode(
        "ascii"
    )
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> dict[str, Any]:
        call = list(argv)
        calls.append(call)
        if "list-object-versions" in call:
            prefix = call[call.index("--prefix") + 1]
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
                            "ETag": "old",
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
                        "ETag": "v1",
                    }
                ],
                "IsTruncated": False,
            }
        return {
            "ContentLength": 8,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": "v1",
            "ChecksumSHA256": checksum,
            "Metadata": {},
        }

    materialization, receipt = capture_live(spec, runner=runner)
    assert materialization["schema"] == MATERIALIZATION_SCHEMA
    assert receipt["status"] == READY_STATUS
    assert receipt["complete_pagination_attested"] is True
    assert all("--no-paginate" in call for call in calls if "list-object-versions" in call)
    assert any("--key-marker" in call for call in calls)
    assert all(
        "--checksum-mode" in call and "ENABLED" in call
        for call in calls
        if "head-object" in call
    )
    validate_receipt(receipt)
    print("[ng_corpus_s3_paginated_inventory_capture] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--spec", type=Path, required=True)
    capture_parser.add_argument("--materialization-spec-out", type=Path, required=True)
    capture_parser.add_argument("--receipt-out", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    spec = _load(args.spec)
    materialization, receipt = capture_live(spec)
    _write(args.materialization_spec_out, materialization)
    _write(args.receipt_out, receipt)
    print(
        json.dumps(
            {
                "materialization_spec_out": str(args.materialization_spec_out),
                "receipt_out": str(args.receipt_out),
                "status": receipt["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
