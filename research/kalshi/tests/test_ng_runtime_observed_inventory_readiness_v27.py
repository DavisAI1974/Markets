from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor_v23 as executor
import ng_historical_refinement_readiness_v27 as readiness


def _plan():
    stages = []
    for spec in readiness.STAGES:
        stages.append(
            {
                "key": spec.key,
                "enabled": False,
                "requires_fixed_outcomes": not spec.pre_outcome,
                "expected_output": spec.filename,
                "suggested_entrypoint": list(
                    executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())
                ),
                "argv": [],
            }
        )
    return {"stages": stages, "outcome_paths": []}


def test_runtime_observed_capture_replaces_legacy_inventory_artifact():
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[:5] == [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
    ]
    assert readiness.STAGES[3].filename == (
        "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json"
    )
    assert readiness.STAGES[3].pre_outcome is True


def test_runtime_capture_has_direct_finalization_and_materialization_links():
    rules = set(readiness.LINK_RULES)
    assert (
        "corpus_inventory_finalization_contract",
        "receipt_fingerprint",
        "corpus_s3_inventory_capture",
        "finalization_contract_fingerprint",
    ) in rules
    assert (
        "corpus_s3_inventory_capture",
        "materialization_spec_fingerprint",
        "corpus_s3_materialization",
        "source_spec_fingerprint",
    ) in rules


def test_executor_uses_runtime_capture_entrypoint():
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v27"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_inventory_capture"] == (
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
    )


def test_executor_accepts_exact_v27_plan(monkeypatch):
    plan = _plan()
    monkeypatch.setattr(
        executor.legacy_executor,
        "validate_plan",
        lambda value: None,
    )
    executor.validate_plan(plan)


def test_executor_rejects_legacy_paginated_inventory_artifact(monkeypatch):
    plan = _plan()
    plan["stages"][3]["expected_output"] = (
        "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    )
    monkeypatch.setattr(
        executor.legacy_executor,
        "validate_plan",
        lambda value: None,
    )
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(plan)


def test_executor_rejects_materialization_before_runtime_capture(monkeypatch):
    plan = _plan()
    plan["stages"][3], plan["stages"][4] = (
        plan["stages"][4],
        plan["stages"][3],
    )
    monkeypatch.setattr(
        executor.legacy_executor,
        "validate_plan",
        lambda value: None,
    )
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(plan)


def test_readiness_selftest_fixture_chain_is_linked(tmp_path: Path):
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path,
        validator_overrides=overrides,
    )
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V27"
    assert report["actual_runtime_capture_bound_to_product_lags"] is True
    assert report["materialization_bound_to_runtime_observed_capture"] is True


def test_removed_runtime_capture_blocks_materialization(tmp_path: Path):
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key != "corpus_s3_inventory_capture":
            readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path,
        validator_overrides=overrides,
    )
    assert report["first_blocking_stage"] == "corpus_s3_inventory_capture"
    assert report["materialization_bound_to_runtime_observed_capture"] is False


def test_refingerprinted_summary_tampering_rejected(tmp_path: Path):
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path,
        validator_overrides=overrides,
    )
    changed = copy.deepcopy(report)
    changed["actual_runtime_capture_bound_to_product_lags"] = False
    changed.pop("fingerprint")
    changed["fingerprint"] = readiness._fingerprint(changed)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(changed)


def test_permanent_authority_wall():
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["corpus_s3_inventory_capture"].pre_outcome is True
    assert not any("option" in spec.key.lower() for spec in readiness.STAGES)
