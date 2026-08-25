from __future__ import annotations

from pathlib import Path

from research.kalshi.frankie_source_inventory_cross_reference_20260824 import (
    ACTIVE_COMPONENT_IDS,
    EXPECTED_DISPOSITIONS,
    build_source_inventory_cross_reference,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_all_138_pushed_sources_and_12_discovered_dependencies_are_accounted_for() -> None:
    report = build_source_inventory_cross_reference(REPO_ROOT)

    assert report["listed_source_count"] == 138
    assert report["catalogued_source_count"] == 150
    assert report["discovered_dependency_count"] == 12
    assert report["disposition_counts"] == EXPECTED_DISPOSITIONS
    assert report["provider_visible_base_source_count"] == 107
    assert report["combined_active_source_count"] == 20
    assert report["meta_loop_deferred_source_count"] == 2
    assert report["combined_active_components"] == list(ACTIVE_COMPONENT_IDS)
    assert report["all_listed_sources_accounted_for"] is True
    assert report["all_discovered_dependencies_accounted_for"] is True
    assert len(report["report_hash"]) == 64


def test_every_row_has_one_explicit_existing_or_new_wiring_disposition() -> None:
    report = build_source_inventory_cross_reference(REPO_ROOT)
    rows = report["rows"]

    assert len(rows) == len({item["path"] for item in rows}) == 138
    assert all(item["disposition"] in EXPECTED_DISPOSITIONS for item in rows)
    assert all(item["section"][0] in "ABCDEFGHIJKLM" for item in rows)
    executed = [item for item in rows if item["disposition"] == "PROVISIONAL_EXECUTED"]
    assert executed
    assert all(item["component_id"] in ACTIVE_COMPONENT_IDS for item in executed)
    superseded = [item for item in rows if item["disposition"] == "SUPERSEDED_BY_CURRENT"]
    assert len(superseded) == 3
    assert all(item["replacement_paths"] for item in superseded)
