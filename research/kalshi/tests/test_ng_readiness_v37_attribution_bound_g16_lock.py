from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g16_attribution_bound_curve_lock_gate as gate
import ng_historical_refinement_executor_v33 as executor
import ng_historical_refinement_readiness_v37 as readiness


def _keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _rehash(plan: dict) -> None:
    plan.pop("fingerprint", None)
    plan["fingerprint"] = readiness._fingerprint(plan)


def test_bound_lock_is_between_legacy_lock_and_publication() -> None:
    keys = _keys()
    index = keys.index("g16_attribution_bound_curve_authorization")
    assert keys[index : index + 4] == [
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
    ]
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["g16_attribution_bound_curve_lock"].schema == gate.SCHEMA
    assert by_key["g16_attribution_bound_curve_lock"].pre_outcome is False
    assert (
        "attribution_bound_curve_authorization_fingerprint"
        not in by_key["g16_counterfactual_curve_lock"].required_fields
    )


def test_bound_lock_links_exact_curve_and_legacy_lock() -> None:
    links = set(readiness.LINK_RULES)
    assert (
        "g16_attribution_bound_curve_authorization",
        "fingerprint",
        "g16_attribution_bound_curve_lock",
        "attribution_bound_curve_authorization_fingerprint",
    ) in links
    assert (
        "g16_counterfactual_curve_lock",
        "lock_fingerprint",
        "g16_attribution_bound_curve_lock",
        "counterfactual_curve_lock_fingerprint",
    ) in links
    assert (
        "g16_attribution_bound_curve_authorization",
        "fingerprint",
        "g16_counterfactual_curve_lock",
        "attribution_bound_curve_authorization_fingerprint",
    ) not in links


def test_missing_bound_lock_blocks_fixed_publication(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key in {
            "g16_attribution_bound_curve_lock",
            "g16_counterfactual_publication",
        }:
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_curve_lock"
    assert report["status"] == (
        "G16_LEGACY_CURVE_LOCK_READY_ATTRIBUTION_BOUND_LOCK_INCOMPLETE"
    )
    assert report["g16_fixed_scoring_opened_after_attribution_bound_lock"] is False


def test_complete_fixture_preserves_blind_wall(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    bound_lock = values["g16_attribution_bound_curve_lock"]
    assert bound_lock["blind_score_fingerprint"] != bound_lock["refined_score_fingerprint"]
    assert bound_lock["actual_g15_outcomes_used"] is True
    assert bound_lock["actual_g16_outcomes_used"] is False
    assert bound_lock["random_shuffle_used"] is False
    assert bound_lock["blind_forecasts_immutable"] is True
    assert bound_lock["may_update_ng_brain"] is False
    assert bound_lock["execution_authority"] is False
    assert bound_lock["cme_event_contracts_mode"] == "SHADOW"
    assert bound_lock["brokerage_contract"] == "tastytrade_not_ibkr"
    assert bound_lock["options_lane_started"] is False

    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V37"
    assert report["g16_curve_lock_bound_to_attribution_scored_g15_lessons"] is True
    assert report["g16_legacy_curve_lock_no_longer_requires_unemitted_bound_field"] is True


def test_link_substitution_blocks_bound_lock(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    target = copy.deepcopy(values["g16_attribution_bound_curve_lock"])
    target["counterfactual_curve_lock_fingerprint"] = "x" * 64
    target.pop("fingerprint", None)
    target["fingerprint"] = readiness._fingerprint(target)
    values["g16_attribution_bound_curve_lock"] = target
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_curve_lock"
    row = next(
        item
        for item in report["stages"]
        if item["key"] == "g16_attribution_bound_curve_lock"
    )
    assert any("provenance link mismatch" in blocker for blocker in row["blockers"])


def test_executor_builds_attribution_bound_lock(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    row = rows["g16_attribution_bound_curve_lock"]
    assert row["expected_output"] == "g16_attribution_bound_curve_lock.json"
    assert row["suggested_entrypoint"] == [
        "python",
        "ng_g16_attribution_bound_curve_lock_gate.py",
    ]
    assert row["requires_fixed_outcomes"] is True
    assert rows["g16_counterfactual_curve_lock"]["requires_fixed_outcomes"] is True
    assert rows["g16_counterfactual_publication"]["requires_fixed_outcomes"] is True


def test_executor_rejects_removed_bound_lock(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row for row in tampered["stages"] if row["key"] != "g16_attribution_bound_curve_lock"
    ]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_entrypoint_substitution(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item for item in tampered["stages"] if item["key"] == "g16_attribution_bound_curve_lock"
    )
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_bound_lock(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item for item in tampered["stages"] if item["key"] == "g16_attribution_bound_curve_lock"
    )
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
