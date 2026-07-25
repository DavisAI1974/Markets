#!/usr/bin/env python3
"""Resolve exact latest S3 corpus versions from complete paginated listings.

V1 failed closed when ``list-object-versions`` returned a truncated page. V2 walks
AWS continuation markers until every page for each explicitly identified corpus
prefix has been captured, attests the raw page sequence, merges it deterministically,
and then delegates exact latest-version resolution to the validated V1 identity wall.
Trading identity is never inferred from object keys.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_s3_latest_version_resolution as v1

SPEC_SCHEMA = v1.SPEC_SCHEMA
RECEIPT_SCHEMA = "ng_corpus_s3_latest_version_resolution_attestation.v2"
READY_STATUS = v1.READY_STATUS
BLOCKED_STATUS = v1.BLOCKED_STATUS
MAX_PAGES_PER_CORPUS = 10_000


class CorpusS3LatestVersionResolutionV2Error(ValueError):
    """Raised when paginated S3 listing evidence is incomplete or inconsistent."""


def _fp(value: Any) -> str:
    return v1._fp(value)


def _load(path: Path) -> dict[str, Any]:
    return v1._load(path)


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _authority_fields() -> dict[str, Any]:
    return v1._authority_fields()


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        v1._authority(value, label=label)
    except Exception as error:
        raise CorpusS3LatestVersionResolutionV2Error(str(error)) from error


def _marker_pair(page: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(page.get("NextKeyMarker") or ""),
        str(page.get("NextVersionIdMarker") or ""),
    )


def _merge_pages(
    pages_by_corpus: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for corpus_id in sorted(pages_by_corpus):
        pages = list(pages_by_corpus[corpus_id])
        if not pages:
            raise CorpusS3LatestVersionResolutionV2Error(
                f"{corpus_id}: no list-object-versions pages were captured"
            )
        versions: list[dict[str, Any]] = []
        delete_markers: list[dict[str, Any]] = []
        seen_rows: set[tuple[str, str, str]] = set()
        seen_markers: set[tuple[str, str]] = set()
        expected_request_marker = ("", "")
        for index, raw_entry in enumerate(pages):
            if not isinstance(raw_entry, Mapping):
                raise CorpusS3LatestVersionResolutionV2Error(
                    f"{corpus_id}: page entry {index} is not an object"
                )
            request = raw_entry.get("request")
            response = raw_entry.get("response")
            if not isinstance(request, Mapping) or not isinstance(response, Mapping):
                raise CorpusS3LatestVersionResolutionV2Error(
                    f"{corpus_id}: page entry {index} must contain request and response objects"
                )
            request_marker = (
                str(request.get("key_marker") or ""),
                str(request.get("version_id_marker") or ""),
            )
            if request_marker != expected_request_marker:
                raise CorpusS3LatestVersionResolutionV2Error(
                    f"{corpus_id}: page {index} request marker {request_marker!r} does not "
                    f"match prior continuation {expected_request_marker!r}"
                )
            page = copy.deepcopy(dict(response))
            truncated = page.get("IsTruncated") is True
            marker = _marker_pair(page)
            is_last = index == len(pages) - 1
            if truncated:
                if not marker[0]:
                    raise CorpusS3LatestVersionResolutionV2Error(
                        f"{corpus_id}: truncated page {index} is missing NextKeyMarker"
                    )
                if marker in seen_markers:
                    raise CorpusS3LatestVersionResolutionV2Error(
                        f"{corpus_id}: repeated pagination marker {marker!r}"
                    )
                seen_markers.add(marker)
                if is_last:
                    raise CorpusS3LatestVersionResolutionV2Error(
                        f"{corpus_id}: captured page sequence ends while truncated"
                    )
                expected_request_marker = marker
            elif not is_last:
                raise CorpusS3LatestVersionResolutionV2Error(
                    f"{corpus_id}: non-final page {index} is not truncated"
                )
            for kind, field, destination in (
                ("version", "Versions", versions),
                ("delete", "DeleteMarkers", delete_markers),
            ):
                rows = page.get(field) or []
                if not isinstance(rows, list):
                    raise CorpusS3LatestVersionResolutionV2Error(
                        f"{corpus_id}: page {index} {field} is not a list"
                    )
                for raw_row in rows:
                    if not isinstance(raw_row, Mapping):
                        raise CorpusS3LatestVersionResolutionV2Error(
                            f"{corpus_id}: page {index} {field} row is not an object"
                        )
                    row = copy.deepcopy(dict(raw_row))
                    identity = (
                        kind,
                        str(row.get("Key") or ""),
                        str(row.get("VersionId") or ""),
                    )
                    if not identity[1] or not identity[2]:
                        raise CorpusS3LatestVersionResolutionV2Error(
                            f"{corpus_id}: page {index} has an incomplete version identity"
                        )
                    if identity in seen_rows:
                        raise CorpusS3LatestVersionResolutionV2Error(
                            f"{corpus_id}: duplicate version evidence across pages {identity!r}"
                        )
                    seen_rows.add(identity)
                    destination.append(row)
        merged[corpus_id] = {
            "Versions": versions,
            "DeleteMarkers": delete_markers,
            "IsTruncated": False,
        }
    return merged


def _build_from_pages(
    source_spec: Mapping[str, Any],
    *,
    pages_by_corpus: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    merged = _merge_pages(pages_by_corpus)
    try:
        capture_spec, base_receipt = v1._build_from_evidence(
            spec, list_responses=merged
        )
    except Exception as error:
        raise CorpusS3LatestVersionResolutionV2Error(str(error)) from error
    page_evidence = {
        "list_object_version_pages": {
            corpus_id: [copy.deepcopy(dict(page)) for page in pages_by_corpus[corpus_id]]
            for corpus_id in sorted(pages_by_corpus)
        }
    }
    merged_evidence = {"list_object_versions": merged}
    page_counts = {
        corpus_id: len(page_evidence["list_object_version_pages"][corpus_id])
        for corpus_id in sorted(page_evidence["list_object_version_pages"])
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": base_receipt["status"],
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "captured_page_evidence": page_evidence,
        "captured_page_evidence_fingerprint": _fp(page_evidence),
        "merged_list_evidence": merged_evidence,
        "merged_list_evidence_fingerprint": _fp(merged_evidence),
        "page_counts": page_counts,
        "page_counts_fingerprint": _fp(page_counts),
        "all_pages_exhausted": True,
        "continuation_markers_bound": True,
        "identity_from_s3_keys_inferred": False,
        "base_v1_receipt": base_receipt,
        "base_v1_receipt_fingerprint": base_receipt["receipt_fingerprint"],
        "capture_spec": capture_spec,
        "capture_spec_fingerprint": _fp(capture_spec),
        "blockers": copy.deepcopy(list(base_receipt.get("blockers") or [])),
        "next_action": base_receipt["next_action"],
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return capture_spec, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = copy.deepcopy(dict(value))
    observed = receipt.pop("receipt_fingerprint", None)
    if receipt.get("schema") != RECEIPT_SCHEMA or observed != _fp(receipt):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution receipt schema or fingerprint mismatch"
        )
    receipt["receipt_fingerprint"] = observed
    _authority(receipt, label="paginated resolution receipt")
    if receipt.get("all_pages_exhausted") is not True:
        raise CorpusS3LatestVersionResolutionV2Error(
            "all S3 version-list pages must be exhausted"
        )
    if receipt.get("continuation_markers_bound") is not True:
        raise CorpusS3LatestVersionResolutionV2Error(
            "S3 continuation markers are not bound"
        )
    if receipt.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusS3LatestVersionResolutionV2Error(
            "trading identity may not be inferred from S3 keys"
        )
    spec = receipt.get("source_spec")
    page_evidence = receipt.get("captured_page_evidence")
    if not isinstance(spec, Mapping) or not isinstance(page_evidence, Mapping):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution receipt is missing embedded evidence"
        )
    if receipt.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution source-spec fingerprint mismatch"
        )
    if receipt.get("captured_page_evidence_fingerprint") != _fp(page_evidence):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution page-evidence fingerprint mismatch"
        )
    pages = page_evidence.get("list_object_version_pages")
    if not isinstance(pages, Mapping):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution page map is missing"
        )
    capture_spec, rebuilt = _build_from_pages(spec, pages_by_corpus=pages)
    if rebuilt != dict(value):
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated resolution receipt differs from deterministic rebuild"
        )
    if receipt.get("capture_spec") != capture_spec:
        raise CorpusS3LatestVersionResolutionV2Error(
            "paginated capture spec differs from deterministic rebuild"
        )
    return copy.deepcopy(dict(value))


def _capture_pages(
    *,
    corpus_id: str,
    bucket: str,
    prefix: str,
    global_args: Sequence[str],
    runner: Callable[[Sequence[str]], dict[str, Any]],
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    key_marker = ""
    version_marker = ""
    used_requests: set[tuple[str, str]] = set()
    for _ in range(MAX_PAGES_PER_CORPUS):
        request_marker = (key_marker, version_marker)
        if request_marker in used_requests:
            raise CorpusS3LatestVersionResolutionV2Error(
                f"{corpus_id}: repeated pagination request marker {request_marker!r}"
            )
        used_requests.add(request_marker)
        argv = [
            *global_args,
            "s3api",
            "list-object-versions",
            "--bucket",
            bucket,
            "--prefix",
            prefix,
        ]
        if key_marker:
            argv.extend(["--key-marker", key_marker])
        if version_marker:
            argv.extend(["--version-id-marker", version_marker])
        argv.extend(["--output", "json"])
        page = runner(argv)
        if not isinstance(page, dict):
            raise CorpusS3LatestVersionResolutionV2Error(
                f"{corpus_id}: AWS CLI page is not an object"
            )
        pages.append(
            {
                "request": {
                    "key_marker": key_marker,
                    "version_id_marker": version_marker,
                },
                "response": copy.deepcopy(page),
            }
        )
        if page.get("IsTruncated") is not True:
            return pages
        key_marker, version_marker = _marker_pair(page)
        if not key_marker:
            raise CorpusS3LatestVersionResolutionV2Error(
                f"{corpus_id}: truncated AWS response is missing NextKeyMarker"
            )
    raise CorpusS3LatestVersionResolutionV2Error(
        f"{corpus_id}: exceeded {MAX_PAGES_PER_CORPUS} S3 listing pages"
    )


def resolve_live(
    source_spec: Mapping[str, Any],
    *,
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], dict[str, Any]] = v1._run_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    global_args: list[str] = [aws_executable]
    profile = str(spec.get("aws_profile") or "")
    region = str(spec.get("aws_region") or "")
    if profile:
        global_args.extend(["--profile", profile])
    if region:
        global_args.extend(["--region", region])
    pages: dict[str, list[dict[str, Any]]] = {}
    for corpus in spec.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        pages[corpus_id] = _capture_pages(
            corpus_id=corpus_id,
            bucket=str(corpus.get("bucket") or ""),
            prefix=str(corpus.get("prefix") or ""),
            global_args=global_args,
            runner=runner,
        )
    return _build_from_pages(spec, pages_by_corpus=pages)


def selftest() -> int:
    spec = {
        "schema": SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **_authority_fields(),
    }
    pages: dict[str, list[dict[str, Any]]] = {}
    for corpus_id, expected in v1.coverage.EXPECTED_WINDOWS.items():
        source_id = f"{corpus_id}-source"
        key = f"ng/{corpus_id}/source.dbn"
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "selftest-bucket",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [
                    {
                        "source_id": source_id,
                        "day": "20260315",
                        "lane": expected["lane"],
                        "key": key,
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
        pages[corpus_id] = [
            {
                "request": {"key_marker": "", "version_id_marker": ""},
                "response": {
                    "Versions": [
                        {
                            "Key": key,
                            "VersionId": "old",
                            "IsLatest": False,
                            "LastModified": "2026-07-24T00:00:00Z",
                            "Size": 7,
                            "ETag": "old",
                        }
                    ],
                    "IsTruncated": True,
                    "NextKeyMarker": key,
                    "NextVersionIdMarker": "old",
                },
            },
            {
                "request": {"key_marker": key, "version_id_marker": "old"},
                "response": {
                    "Versions": [
                        {
                            "Key": key,
                            "VersionId": "latest",
                            "IsLatest": True,
                            "LastModified": "2026-07-25T00:00:00Z",
                            "Size": 8,
                            "ETag": "latest",
                        }
                    ],
                    "IsTruncated": False,
                },
            },
        ]
    capture_spec, receipt = _build_from_pages(spec, pages_by_corpus=pages)
    assert receipt["status"] == READY_STATUS
    assert all(count == 2 for count in receipt["page_counts"].values())
    assert all(
        source["version_id"] == "latest"
        for corpus in capture_spec["corpora"]
        for source in corpus["sources"]
    )
    validate_receipt(receipt)
    print("[ng_corpus_s3_latest_version_resolution_v2] selftest PASS")
    return 0


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
