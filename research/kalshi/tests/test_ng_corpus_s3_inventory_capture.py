from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any

import pytest

import ng_corpus_s3_inventory_capture as capture


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    checksum = hashlib.sha256(b"fixture").hexdigest()
    checksum_b64 = base64.b64encode(bytes.fromhex(checksum)).decode("ascii")
    spec: dict[str, Any] = {
        "schema": capture.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T01:00:00Z",
        "corpora": [],
        **capture._authority_fields(),
    }
    lists: dict[str, Any] = {}
    heads: dict[str, Any] = {}
    for corpus_id, expected in capture.coverage.EXPECTED_WINDOWS.items():
        lane = expected["lane"]
        source_id = f"{corpus_id}-source"
        key = f"ng/{corpus_id}/20260315.dbn"
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "publisher_id": 1,
                "bucket": f"fixture-{corpus_id}",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [
                    {
                        "source_id": source_id,
                        "day": "20260315",
                        "lane": lane,
                        "key": key,
                        "version_id": "v1",
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition_path": f"definitions/{source_id}.json",
                        "expected_checksum_sha256": checksum,
                    }
                ],
            }
        )
        lists[corpus_id] = {
            "Versions": [
                {
                    "Key": key,
                    "VersionId": "v1",
                    "IsLatest": True,
                    "LastModified": "2026-07-25T00:00:00Z",
                    "Size": 7,
                    "ETag": source_id,
                }
            ]
        }
        heads[source_id] = {
            "ContentLength": 7,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": source_id,
            "ChecksumSHA256": checksum_b64,
        }
    return spec, lists, heads


def test_ready_capture_builds_exact_materialization_spec() -> None:
    spec, lists, heads = _fixture()
    materialization, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert receipt["status"] == capture.READY_STATUS
    assert receipt["blockers"] == []
    assert materialization["schema"] == capture.MATERIALIZATION_SCHEMA
    sources = [
        source
        for corpus in materialization["corpora"]
        for source in corpus["sources"]
    ]
    assert all(source["s3_object"]["version_id"] == "v1" for source in sources)
    assert all(
        source["s3_object"]["checksum_source"] == "s3.ChecksumSHA256"
        for source in sources
    )
    capture.validate_receipt(receipt)


def test_metadata_sha256_is_accepted_without_native_checksum() -> None:
    spec, lists, heads = _fixture()
    checksum = spec["corpora"][0]["sources"][0]["expected_checksum_sha256"]
    for head in heads.values():
        head.pop("ChecksumSHA256")
        head["Metadata"] = {"sha256": checksum}
    materialization, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert receipt["status"] == capture.READY_STATUS
    assert all(
        source["s3_object"]["checksum_source"] == "s3.Metadata.sha256"
        for corpus in materialization["corpora"]
        for source in corpus["sources"]
    )


def test_missing_sha256_is_visible_blocker() -> None:
    spec, lists, heads = _fixture()
    first = next(iter(heads))
    heads[first].pop("ChecksumSHA256")
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert receipt["status"] == capture.BLOCKED_STATUS
    assert f"{first}:S3_SHA256_MISSING" in receipt["blockers"]


def test_native_and_metadata_checksum_conflict_is_blocked() -> None:
    spec, lists, heads = _fixture()
    first = next(iter(heads))
    heads[first]["Metadata"] = {"sha256": "0" * 64}
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert f"{first}:S3_SHA256_CONFLICT" in receipt["blockers"]


def test_undeclared_latest_object_is_blocked() -> None:
    spec, lists, heads = _fixture()
    corpus_id = spec["corpora"][0]["corpus_id"]
    lists[corpus_id]["Versions"].append(
        {
            "Key": f"ng/{corpus_id}/unexpected.dbn",
            "VersionId": "v2",
            "IsLatest": True,
            "LastModified": "2026-07-25T00:00:00Z",
            "Size": 1,
            "ETag": "unexpected",
        }
    )
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert any(
        "UNDECLARED_LATEST_OBJECT" in blocker for blocker in receipt["blockers"]
    )


def test_latest_delete_marker_is_blocked() -> None:
    spec, lists, heads = _fixture()
    corpus_id = spec["corpora"][0]["corpus_id"]
    lists[corpus_id]["DeleteMarkers"] = [
        {
            "Key": f"ng/{corpus_id}/deleted.dbn",
            "VersionId": "delete-v1",
            "IsLatest": True,
            "LastModified": "2026-07-25T00:00:00Z",
        }
    ]
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert any("LATEST_DELETE_MARKER" in blocker for blocker in receipt["blockers"])


def test_version_or_size_substitution_is_blocked() -> None:
    spec, lists, heads = _fixture()
    first = next(iter(heads))
    heads[first]["VersionId"] = "substituted"
    heads[first]["ContentLength"] = 8
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert f"{first}:HEAD_VERSION_ID_MISMATCH" in receipt["blockers"]
    assert f"{first}:LIST_HEAD_SIZE_MISMATCH" in receipt["blockers"]


def test_capture_live_uses_list_versions_and_checksum_enabled_head() -> None:
    spec, lists, heads = _fixture()
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> dict[str, Any]:
        calls.append(list(argv))
        if "list-object-versions" in argv:
            corpus = next(
                row
                for row in spec["corpora"]
                if row["bucket"] == argv[argv.index("--bucket") + 1]
            )
            return lists[corpus["corpus_id"]]
        key = argv[argv.index("--key") + 1]
        source = next(
            source
            for corpus in spec["corpora"]
            for source in corpus["sources"]
            if source["key"] == key
        )
        return heads[source["source_id"]]

    _, receipt = capture.capture_live(spec, runner=runner)
    assert receipt["status"] == capture.READY_STATUS
    assert sum("list-object-versions" in call for call in calls) == 2
    assert sum("head-object" in call for call in calls) == 2
    assert all(
        call[call.index("--checksum-mode") + 1] == "ENABLED"
        for call in calls
        if "head-object" in call
    )


def test_capture_never_infers_day_lane_or_identity_from_key() -> None:
    spec, lists, heads = _fixture()
    del spec["corpora"][0]["sources"][0]["day"]
    with pytest.raises(capture.CorpusS3InventoryCaptureError):
        capture._build_from_evidence(
            spec, list_responses=lists, head_responses=heads
        )


def test_nested_refingerprinted_tampering_fails_deterministic_validation() -> None:
    spec, lists, heads = _fixture()
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    tampered = copy.deepcopy(receipt)
    first = next(iter(heads))
    tampered["captured_inventory"]["head_objects"][first][
        "ContentLength"
    ] = 99
    tampered["captured_inventory_fingerprint"] = capture._fp(
        tampered["captured_inventory"]
    )
    tampered["receipt_fingerprint"] = capture._fp(
        {
            key: value
            for key, value in tampered.items()
            if key != "receipt_fingerprint"
        }
    )
    with pytest.raises(capture.CorpusS3InventoryCaptureError):
        capture.validate_receipt(tampered)


def test_authority_escalation_is_rejected() -> None:
    spec, lists, heads = _fixture()
    _, receipt = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = capture._fp(
        {
            key: value
            for key, value in tampered.items()
            if key != "receipt_fingerprint"
        }
    )
    with pytest.raises(capture.CorpusS3InventoryCaptureError):
        capture.validate_receipt(tampered)


def test_deterministic_output_and_source_immutability() -> None:
    spec, lists, heads = _fixture()
    before = copy.deepcopy((spec, lists, heads))
    first = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    second = capture._build_from_evidence(
        spec, list_responses=lists, head_responses=heads
    )
    assert first == second
    assert (spec, lists, heads) == before
