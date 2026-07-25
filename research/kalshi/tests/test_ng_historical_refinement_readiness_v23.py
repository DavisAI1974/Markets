from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import ng_historical_refinement_readiness_v23 as readiness


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _overrides() -> dict[str, Any]:
    return {spec.key: (lambda value: None) for spec in readiness.STAGES}


def _materialize(root: Path) -> dict[str, dict[str, Any]]:
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        _write(root / spec.filename, values[spec.key])
    return values


def test_paginated_resolution_replaces_v22_first_stage() -> None:
    stage = readiness.STAGES[0]
    assert stage.key == "corpus_s3_latest_version_resolution"
    assert (
        stage.filename
        == "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    )
    assert (
        stage.schema
        == "ng_corpus_s3_paginated_latest_version_resolution_attestation.v1"
    )
    assert stage.allowed_statuses == frozenset(
        {"S3_PAGINATED_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE"}
    )
    assert stage.pre_outcome is True


def test_complete_fixture_chain_reaches_v23(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V23"
    assert report["s3_complete_pagination_attested"] is True
    assert report["pagination_marker_progression_verified"] is True
    assert report["pagination_cycles_rejected"] is True
    assert report["truncated_final_page_rejected"] is True
    readiness.validate_readiness_report(report)


def test_missing_paginated_receipt_blocks_inventory_capture(tmp_path: Path) -> None:
    values = _materialize(tmp_path)
    (tmp_path / readiness.STAGES[0].filename).unlink()
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["first_blocking_stage"] == "corpus_s3_latest_version_resolution"
    assert report["s3_complete_pagination_attested"] is False
    assert "corpus_s3_inventory_capture" not in report["ready_stages"]
    assert values["corpus_s3_inventory_capture"]


def test_legacy_v22_artifact_name_cannot_satisfy_v23(tmp_path: Path) -> None:
    values = _materialize(tmp_path)
    paginated_path = tmp_path / readiness.STAGES[0].filename
    paginated_path.unlink()
    _write(
        tmp_path / "ng_corpus_s3_latest_version_resolution_attestation.json",
        values["corpus_s3_latest_version_resolution"],
    )
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["first_blocking_stage"] == "corpus_s3_latest_version_resolution"


def test_capture_spec_substitution_blocks_downstream(tmp_path: Path) -> None:
    values = _materialize(tmp_path)
    first = copy.deepcopy(values["corpus_s3_latest_version_resolution"])
    first["capture_spec_fingerprint"] = "substituted"
    first.pop("receipt_fingerprint", None)
    first["receipt_fingerprint"] = readiness._fingerprint(first)
    _write(tmp_path / readiness.STAGES[0].filename, first)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["first_blocking_stage"] == "corpus_s3_inventory_capture"
    assert "corpus_s3_latest_version_resolution" in report["ready_stages"]
    assert "corpus_s3_inventory_capture" not in report["ready_stages"]


def test_summary_tampering_fails_after_refingerprint(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    tampered = copy.deepcopy(report)
    tampered["pagination_cycles_rejected"] = False
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(tampered)


def test_permanent_authority_wall_is_preserved(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["paid_live_data_assumed"] is False
    assert report["random_shuffle_used"] is False
    assert report["one_signal_authority_preserved"] is True
    assert report["blind_forecasts_immutable"] is True
    assert report["may_update_ng_brain"] is False
    assert report["execution_authority"] is False
    assert report["cme_event_contracts_mode"] == "SHADOW"
    assert report["brokerage_contract"] == "tastytrade_not_ibkr"
    assert report["options_lane_started"] is False
