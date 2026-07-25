from __future__ import annotations

import copy
from typing import Any

import pytest

import ng_corpus_s3_latest_version_resolution as resolver


def _spec() -> dict[str, Any]:
    value = {
        "schema": resolver.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **resolver._authority_fields(),
    }
    for corpus_id, expected in resolver.coverage.EXPECTED_WINDOWS.items():
        source_id = f"{corpus_id}-source"
        value["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "bucket",
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
                        "key": f"ng/{corpus_id}/source.dbn",
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition": {"publisher_id": 1},
                    }
                ],
            }
        )
    return value


def _responses(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for corpus in spec["corpora"]:
        source = corpus["sources"][0]
        result[corpus["corpus_id"]] = {
            "Versions": [
                {
                    "Key": source["key"],
                    "VersionId": f"v-{corpus['corpus_id']}",
                    "IsLatest": True,
                    "LastModified": "2026-07-25T00:00:00Z",
                    "Size": 10,
                    "ETag": corpus["corpus_id"],
                }
            ]
        }
    return result


def test_resolves_exact_latest_versions_without_inferring_identity() -> None:
    spec = _spec()
    capture_spec, receipt = resolver._build_from_evidence(
        spec, list_responses=_responses(spec)
    )
    assert receipt["status"] == resolver.READY_STATUS
    assert receipt["identity_from_s3_keys_inferred"] is False
    assert all(
        source["version_id"].startswith("v-")
        for corpus in capture_spec["corpora"]
        for source in corpus["sources"]
    )
    assert all(
        row["identity_from_key_inferred"] is False
        for row in receipt["resolutions"]
    )
    resolver.validate_receipt(receipt)


def test_latest_delete_marker_blocks_resolution() -> None:
    spec = _spec()
    evidence = _responses(spec)
    corpus = spec["corpora"][0]
    key = corpus["sources"][0]["key"]
    evidence[corpus["corpus_id"]]["Versions"][0]["IsLatest"] = False
    evidence[corpus["corpus_id"]]["DeleteMarkers"] = [
        {
            "Key": key,
            "VersionId": "delete-v1",
            "IsLatest": True,
            "LastModified": "2026-07-25T00:00:00Z",
        }
    ]
    _, receipt = resolver._build_from_evidence(spec, list_responses=evidence)
    assert receipt["status"] == resolver.BLOCKED_STATUS
    assert any("LATEST_OBJECT_IS_DELETE_MARKER" in item for item in receipt["blockers"])


def test_missing_latest_version_blocks_resolution() -> None:
    spec = _spec()
    evidence = _responses(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    evidence[corpus_id]["Versions"] = []
    _, receipt = resolver._build_from_evidence(spec, list_responses=evidence)
    assert any("LATEST_VERSION_NOT_FOUND" in item for item in receipt["blockers"])


def test_ambiguous_latest_versions_block_resolution() -> None:
    spec = _spec()
    evidence = _responses(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    duplicate = copy.deepcopy(evidence[corpus_id]["Versions"][0])
    duplicate["VersionId"] = "v-other"
    evidence[corpus_id]["Versions"].append(duplicate)
    _, receipt = resolver._build_from_evidence(spec, list_responses=evidence)
    assert any("LATEST_VERSION_AMBIGUOUS" in item for item in receipt["blockers"])


def test_undeclared_latest_object_blocks_dedicated_prefix() -> None:
    spec = _spec()
    evidence = _responses(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    evidence[corpus_id]["Versions"].append(
        {
            "Key": f"ng/{corpus_id}/undeclared.dbn",
            "VersionId": "v-extra",
            "IsLatest": True,
            "LastModified": "2026-07-25T00:00:00Z",
            "Size": 5,
            "ETag": "extra",
        }
    )
    _, receipt = resolver._build_from_evidence(spec, list_responses=evidence)
    assert any("UNDECLARED_LATEST_OBJECT" in item for item in receipt["blockers"])


def test_truncated_version_listing_blocks_resolution() -> None:
    spec = _spec()
    evidence = _responses(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    evidence[corpus_id]["IsTruncated"] = True
    _, receipt = resolver._build_from_evidence(spec, list_responses=evidence)
    assert f"{corpus_id}:S3_VERSION_LIST_TRUNCATED" in receipt["blockers"]


def test_predeclared_version_id_is_rejected() -> None:
    spec = _spec()
    spec["corpora"][0]["sources"][0]["version_id"] = "operator-guessed"
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionError):
        resolver._build_from_evidence(spec, list_responses=_responses(spec))


def test_capture_spec_preserves_explicit_identity_fields() -> None:
    spec = _spec()
    capture_spec, _ = resolver._build_from_evidence(
        spec, list_responses=_responses(spec)
    )
    original = spec["corpora"][0]["sources"][0]
    resolved = capture_spec["corpora"][0]["sources"][0]
    for field in (
        "source_id",
        "day",
        "lane",
        "key",
        "materialized_path",
        "definition",
    ):
        assert resolved[field] == original[field]


def test_refingerprinted_nested_tampering_is_rejected() -> None:
    spec = _spec()
    _, receipt = resolver._build_from_evidence(spec, list_responses=_responses(spec))
    tampered = copy.deepcopy(receipt)
    tampered["capture_spec"]["corpora"][0]["sources"][0]["version_id"] = "v-tampered"
    tampered["capture_spec_fingerprint"] = resolver._fp(tampered["capture_spec"])
    tampered["receipt_fingerprint"] = resolver._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionError):
        resolver.validate_receipt(tampered)


def test_authority_escalation_and_source_mutation_are_rejected() -> None:
    spec = _spec()
    original = copy.deepcopy(spec)
    _, receipt = resolver._build_from_evidence(spec, list_responses=_responses(spec))
    assert spec == original
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = resolver._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionError):
        resolver.validate_receipt(tampered)


def test_live_command_lists_each_prefix_and_never_heads_objects() -> None:
    spec = _spec()
    calls: list[list[str]] = []
    responses = _responses(spec)

    def runner(argv: list[str]) -> dict[str, Any]:
        calls.append(list(argv))
        prefix = argv[argv.index("--prefix") + 1]
        corpus_id = next(
            corpus["corpus_id"]
            for corpus in spec["corpora"]
            if corpus["prefix"] == prefix
        )
        return responses[corpus_id]

    _, receipt = resolver.resolve_live(spec, runner=runner)
    assert receipt["status"] == resolver.READY_STATUS
    assert len(calls) == 2
    assert all("list-object-versions" in call for call in calls)
    assert all("head-object" not in call for call in calls)
