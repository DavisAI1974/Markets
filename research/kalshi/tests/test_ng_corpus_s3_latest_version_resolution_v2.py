from __future__ import annotations

import copy
from typing import Any

import pytest

import ng_corpus_s3_latest_version_resolution_v2 as resolver


def _spec() -> dict[str, Any]:
    value = {
        "schema": resolver.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **resolver._authority_fields(),
    }
    for corpus_id, expected in resolver.v1.coverage.EXPECTED_WINDOWS.items():
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


def _pages(spec: dict[str, Any], *, paginated: bool = True) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for corpus in spec["corpora"]:
        key = corpus["sources"][0]["key"]
        latest = {
            "Key": key,
            "VersionId": f"latest-{corpus['corpus_id']}",
            "IsLatest": True,
            "LastModified": "2026-07-25T00:00:00Z",
            "Size": 10,
            "ETag": corpus["corpus_id"],
        }
        if paginated:
            result[corpus["corpus_id"]] = [
                {
                    "request": {"key_marker": "", "version_id_marker": ""},
                    "response": {
                        "Versions": [
                            {
                                **latest,
                                "VersionId": "old",
                                "IsLatest": False,
                                "LastModified": "2026-07-24T00:00:00Z",
                            }
                        ],
                        "IsTruncated": True,
                        "NextKeyMarker": key,
                        "NextVersionIdMarker": "old",
                    },
                },
                {
                    "request": {"key_marker": key, "version_id_marker": "old"},
                    "response": {"Versions": [latest], "IsTruncated": False},
                },
            ]
        else:
            result[corpus["corpus_id"]] = [
                {
                    "request": {"key_marker": "", "version_id_marker": ""},
                    "response": {"Versions": [latest], "IsTruncated": False},
                }
            ]
    return result


def test_merges_all_pages_before_exact_latest_version_resolution() -> None:
    spec = _spec()
    capture_spec, receipt = resolver._build_from_pages(spec, pages_by_corpus=_pages(spec))
    assert receipt["status"] == resolver.READY_STATUS
    assert receipt["all_pages_exhausted"] is True
    assert receipt["continuation_markers_bound"] is True
    assert all(count == 2 for count in receipt["page_counts"].values())
    assert all(
        source["version_id"].startswith("latest-")
        for corpus in capture_spec["corpora"]
        for source in corpus["sources"]
    )
    resolver.validate_receipt(receipt)


def test_live_resolution_uses_exact_aws_continuation_markers() -> None:
    spec = _spec()
    queued = _pages(spec)
    calls: list[list[str]] = []
    offsets = {corpus["corpus_id"]: 0 for corpus in spec["corpora"]}

    def runner(argv: list[str]) -> dict[str, Any]:
        calls.append(list(argv))
        prefix = argv[argv.index("--prefix") + 1]
        corpus_id = next(
            corpus["corpus_id"] for corpus in spec["corpora"] if corpus["prefix"] == prefix
        )
        index = offsets[corpus_id]
        offsets[corpus_id] += 1
        return queued[corpus_id][index]["response"]

    _, receipt = resolver.resolve_live(spec, runner=runner)
    assert receipt["status"] == resolver.READY_STATUS
    assert len(calls) == 4
    continuation_calls = [call for call in calls if "--key-marker" in call]
    assert len(continuation_calls) == 2
    assert all("--version-id-marker" in call for call in continuation_calls)
    assert all("head-object" not in call for call in calls)


def test_request_marker_must_equal_prior_response_continuation() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id][1]["request"]["key_marker"] = "wrong"
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver._build_from_pages(spec, pages_by_corpus=pages)


def test_truncated_final_page_is_rejected() -> None:
    spec = _spec()
    pages = _pages(spec, paginated=False)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id][0]["response"].update(
        {"IsTruncated": True, "NextKeyMarker": "next", "NextVersionIdMarker": "v"}
    )
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver._build_from_pages(spec, pages_by_corpus=pages)


def test_truncated_page_without_next_key_marker_is_rejected() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id][0]["response"].pop("NextKeyMarker")
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver._build_from_pages(spec, pages_by_corpus=pages)


def test_duplicate_version_evidence_across_pages_is_rejected() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    duplicate = copy.deepcopy(pages[corpus_id][0]["response"]["Versions"][0])
    pages[corpus_id][1]["response"]["Versions"].append(duplicate)
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver._build_from_pages(spec, pages_by_corpus=pages)


def test_non_final_untruncated_page_is_rejected() -> None:
    spec = _spec()
    pages = _pages(spec)
    corpus_id = spec["corpora"][0]["corpus_id"]
    pages[corpus_id][0]["response"]["IsTruncated"] = False
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver._build_from_pages(spec, pages_by_corpus=pages)


def test_page_evidence_tampering_is_rejected_after_refingerprinting() -> None:
    spec = _spec()
    _, receipt = resolver._build_from_pages(spec, pages_by_corpus=_pages(spec))
    tampered = copy.deepcopy(receipt)
    corpus_id = spec["corpora"][0]["corpus_id"]
    tampered["captured_page_evidence"]["list_object_version_pages"][corpus_id][1][
        "response"
    ]["Versions"][0]["VersionId"] = "tampered"
    tampered["captured_page_evidence_fingerprint"] = resolver._fp(
        tampered["captured_page_evidence"]
    )
    tampered["receipt_fingerprint"] = resolver._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver.validate_receipt(tampered)


def test_authority_escalation_is_rejected() -> None:
    spec = _spec()
    _, receipt = resolver._build_from_pages(spec, pages_by_corpus=_pages(spec))
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = resolver._fp(
        {key: value for key, value in tampered.items() if key != "receipt_fingerprint"}
    )
    with pytest.raises(resolver.CorpusS3LatestVersionResolutionV2Error):
        resolver.validate_receipt(tampered)


def test_resolution_is_deterministic_and_does_not_mutate_inputs() -> None:
    spec = _spec()
    pages = _pages(spec)
    original_spec = copy.deepcopy(spec)
    original_pages = copy.deepcopy(pages)
    first = resolver._build_from_pages(spec, pages_by_corpus=pages)
    second = resolver._build_from_pages(spec, pages_by_corpus=pages)
    assert first == second
    assert spec == original_spec
    assert pages == original_pages
