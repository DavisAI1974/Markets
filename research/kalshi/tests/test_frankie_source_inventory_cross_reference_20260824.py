from __future__ import annotations

from pathlib import Path

from research.kalshi.frankie_source_inventory_cross_reference_20260824 import (
    ACTIVE_COMPONENT_IDS,
    EXPECTED_DISPOSITIONS,
    build_source_inventory_cross_reference,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_all_curated_local_discovered_and_external_identities_are_accounted_for() -> None:
    report = build_source_inventory_cross_reference(REPO_ROOT)

    assert report["listed_source_count"] == 148
    assert report["catalogued_source_count"] == 161
    assert report["discovered_dependency_count"] == 12
    assert report["additional_local_sealed_governing_identity_count"] == 1
    assert report["external_sealed_descriptor_count"] == 13
    assert report["total_manifest_identity_count"] == 174
    assert report["disposition_counts"] == EXPECTED_DISPOSITIONS
    assert report["provider_visible_base_source_count"] == 117
    assert report["combined_active_source_count"] == 20
    assert report["meta_loop_deferred_source_count"] == 2
    assert report["combined_active_components"] == list(ACTIVE_COMPONENT_IDS)
    assert report["all_listed_sources_accounted_for"] is True
    assert report["all_discovered_dependencies_accounted_for"] is True
    assert report["all_external_sealed_descriptors_accounted_for"] is True
    assert len(report["report_hash"]) == 64

    governors = report["additional_local_sealed_governing_identities"]
    assert list(governors) == [
        "research/kalshi/NG_EXHAUSTION_MBO_5Y_STEP1_LAUNCH_20260822.json"
    ]
    assert len(governors[next(iter(governors))]["source_sha256"]) == 64

    descriptors = report["external_sealed_descriptors"]
    assert len(descriptors) == 13
    assert len({item["descriptor_id"] for item in descriptors}) == 13
    assert all(item["authority"] == "SEALED_TARGET_ANSWER" for item in descriptors)
    assert all(item["content_accessed"] is False for item in descriptors)
    assert all(item["content_sha256"] is None for item in descriptors)
    assert all(item["local_path"] is None for item in descriptors)
    assert all(len(item["descriptor_sha256"]) == 64 for item in descriptors)


def test_every_row_has_one_explicit_existing_or_new_wiring_disposition() -> None:
    report = build_source_inventory_cross_reference(REPO_ROOT)
    rows = report["rows"]

    assert len(rows) == len({item["path"] for item in rows}) == 148
    assert all(item["disposition"] in EXPECTED_DISPOSITIONS for item in rows)
    assert all(item["section"][0] in "ABCDEFGHIJKLM" for item in rows)
    executed = [item for item in rows if item["disposition"] == "PROVISIONAL_EXECUTED"]
    assert executed
    assert all(item["component_id"] in ACTIVE_COMPONENT_IDS for item in executed)
    superseded = [item for item in rows if item["disposition"] == "SUPERSEDED_BY_CURRENT"]
    assert len(superseded) == 3
    assert all(item["replacement_paths"] for item in superseded)
