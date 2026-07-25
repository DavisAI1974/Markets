from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any, Sequence

import pytest

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_paginated_inventory_capture as gate


def _spec() -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": gate.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "pagination_max_keys": 1,
        "corpora": [],
        **gate._authority_fields(),
    }
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        prefix = f"ng/{corpus_id}/"
        value["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "bucket",
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
    return value


def _page(
    key: str,
    version_id: str,
    *,
    latest: bool,
    truncated: bool,
    next_key: str | None = None,
    next_version: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "Versions": [
            {
                "Key": key,
                "VersionId": version_id,
                "IsLatest": latest,
                "LastModified": "2026-07-25T00:00:00Z",
                "Size": 8,
                "ETag": version_id,
            }
        ],
        "IsTruncated": truncated,
    }
    if next_key is not None:
        value["NextKeyMarker"] = next_key
    if next_version is not None:
        value["NextVersionIdMarker"] = next_version
    return value


def _pages(spec: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for corpus in spec["corpora"]:
        key = corpus["sources"][0]["key"]
        result[corpus["corpus_id"]] = [
            {
                "request": {
                    "page_index": 1,
                    "key_marker": None,
                    "version_id_marker": None,
                    "argv": ["aws"],
                },
                "response": _page(
                    key,
                    "old",
                    latest=False,
                    truncated=True,
                    next_key=key,
                    next_version="old",
                ),
            },
            {
                "request": {
                    "page_index": 2,
                    "key_marker": key,
                    "version_id_marker": "old",
                    "argv": ["aws", "--key-marker", key],
                },
                "response": _page(key, "v1", latest=True, truncated=False),
            },
        ]
    return result


def _heads(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checksum = base64.b64encode(hashlib.sha256(b"payload").digest()).decode("ascii")
    return {
        source["source_id"]: {
            "ContentLength": 8,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": "v1",
            "ChecksumSHA256": checksum,
            "Metadata": {},
        }
        for corpus in spec["corpora"]
        for source in corpus["sources"]
    }


def test_builds_complete_paginated_inventory() -> None:
    spec = _spec()
    materialization, receipt = gate.build_from_paginated_evidence(
        spec, captured_pages=_pages(spec), head_responses=_heads(spec)
    )
    assert receipt["status"] == gate.READY_STATUS
    assert receipt["complete_pagination_attested"] is True
    assert receipt["checksum_enabled_heads_attested"] is True
    assert all(row["page_count"] == 2 for row in receipt["pagination_summaries"])
    assert materialization["schema"] == gate.MATERIALIZATION_SCHEMA
    gate.validate_receipt(receipt)


def test_live_capture_uses_explicit_pagination_and_checksum_heads() -> None:
    spec = _spec()
    calls: list[list[str]] = []
    checksum = base64.b64encode(hashlib.sha256(b"payload").digest()).decode("ascii")

    def runner(argv: Sequence[str]) -> dict[str, Any]:
        call = list(argv)
        calls.append(call)
        if "list-object-versions" in call:
            prefix = call[call.index("--prefix") + 1]
            key = prefix + "source.dbn"
            if "--key-marker" not in call:
                return _page(
                    key,
                    "old",
                    latest=False,
                    truncated=True,
                    next_key=key,
                    next_version="old",
                )
            return _page(key, "v1", latest=True, truncated=False)
        return {
            "ContentLength": 8,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": "v1",
            "ChecksumSHA256": checksum,
            "Metadata": {},
        }

    _, receipt = gate.capture_live(spec, runner=runner)
    assert receipt["status"] == gate.READY_STATUS
    list_calls = [call for call in calls if "list-object-versions" in call]
    head_calls = [call for call in calls if "head-object" in call]
    assert all("--no-paginate" in call and "--max-keys" in call for call in list_calls)
    assert sum("--key-marker" in call for call in list_calls) == len(spec["corpora"])
    assert all("--checksum-mode" in call and "ENABLED" in call for call in head_calls)


def test_truncated_page_requires_next_marker() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id][0]["response"].pop("NextKeyMarker")
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.build_from_paginated_evidence(
            spec, captured_pages=pages, head_responses=_heads(spec)
        )


def test_continuation_cycle_is_rejected() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus = spec["corpora"][0]
    corpus_id = corpus["corpus_id"]
    key = corpus["sources"][0]["key"]
    pages[corpus_id][1]["response"] = _page(
        key,
        "v1",
        latest=True,
        truncated=True,
        next_key=key,
        next_version="old",
    )
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.build_from_paginated_evidence(
            spec, captured_pages=pages, head_responses=_heads(spec)
        )


def test_duplicate_rows_across_pages_are_rejected() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus = spec["corpora"][0]
    corpus_id = corpus["corpus_id"]
    key = corpus["sources"][0]["key"]
    pages[corpus_id][1]["response"] = _page(
        key, "old", latest=True, truncated=False
    )
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.build_from_paginated_evidence(
            spec, captured_pages=pages, head_responses=_heads(spec)
        )


def test_evidence_may_not_end_truncated() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id] = pages[corpus_id][:1]
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.build_from_paginated_evidence(
            spec, captured_pages=pages, head_responses=_heads(spec)
        )


def test_head_source_set_must_match_exactly() -> None:
    spec = _spec()
    heads = _heads(spec)
    heads.pop(next(iter(heads)))
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.build_from_paginated_evidence(
            spec, captured_pages=_pages(spec), head_responses=heads
        )


def test_head_version_mismatch_remains_visible_blocker() -> None:
    spec = _spec()
    heads = _heads(spec)
    heads[next(iter(heads))]["VersionId"] = "substituted"
    _, receipt = gate.build_from_paginated_evidence(
        spec, captured_pages=_pages(spec), head_responses=heads
    )
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("HEAD_VERSION_ID_MISMATCH" in item for item in receipt["blockers"])


def test_nested_page_tampering_fails_after_refingerprint() -> None:
    spec = _spec()
    _, receipt = gate.build_from_paginated_evidence(
        spec, captured_pages=_pages(spec), head_responses=_heads(spec)
    )
    tampered = copy.deepcopy(receipt)
    corpus_id = spec["corpora"][0]["corpus_id"]
    tampered["captured_pages"][corpus_id][1]["response"]["Versions"][0][
        "VersionId"
    ] = "substituted"
    tampered["captured_pages_fingerprint"] = gate._fp(tampered["captured_pages"])
    tampered["receipt_fingerprint"] = gate._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.validate_receipt(tampered)


def test_nested_head_tampering_fails_after_refingerprint() -> None:
    spec = _spec()
    _, receipt = gate.build_from_paginated_evidence(
        spec, captured_pages=_pages(spec), head_responses=_heads(spec)
    )
    tampered = copy.deepcopy(receipt)
    source_id = next(iter(tampered["captured_head_objects"]))
    tampered["captured_head_objects"][source_id]["VersionId"] = "substituted"
    tampered["captured_head_objects_fingerprint"] = gate._fp(
        tampered["captured_head_objects"]
    )
    tampered["receipt_fingerprint"] = gate._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.validate_receipt(tampered)


def test_authority_escalation_fails_after_refingerprint() -> None:
    spec = _spec()
    _, receipt = gate.build_from_paginated_evidence(
        spec, captured_pages=_pages(spec), head_responses=_heads(spec)
    )
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = gate._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(gate.CorpusS3PaginatedInventoryCaptureError):
        gate.validate_receipt(tampered)


def test_deterministic_and_inputs_immutable() -> None:
    spec = _spec()
    pages = _pages(spec)
    heads = _heads(spec)
    before = copy.deepcopy((spec, pages, heads))
    first = gate.build_from_paginated_evidence(
        spec, captured_pages=pages, head_responses=heads
    )
    second = gate.build_from_paginated_evidence(
        spec, captured_pages=pages, head_responses=heads
    )
    assert first == second
    assert (spec, pages, heads) == before
