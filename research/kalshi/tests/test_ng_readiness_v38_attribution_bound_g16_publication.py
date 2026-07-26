from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g16_attribution_bound_publication_gate as gate
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_readiness_v38 as readiness


def _keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _rehash(plan: dict) -> None:
    plan.pop("fingerprint", None)
    plan["fingerprint"] = readiness._fingerprint(plan)


def test_bound_publication_directly_follows_fixed_g16_publication() -> None:
    assert _keys()[-4:] == [
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        "g16_attribution_bound_publication",
    ]
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["g16_attribution_bound_publication"].schema == gate.SCHEMA
    assert by_key["g16_attribution_bound_publication"].pre_outcome is False


def test_bound_publication_links_lock_publication_and_separate_scores() -> None:
    links = set(readiness.LINK_RULES)
    assert (
        "g16_attribution_bound_curve_lock",
        "fingerprint",
        "g16_attribution_bound_publication",
        "attribution_bound_curve_lock_fingerprint",
    ) in links
    assert (
        "g16_counterfactual_publication",
        "completion_fingerprint",
        "g16_attribution_bound_publication",
        "counterfactual_publication_fingerprint",
    ) in links
    for field in ("blind_score_fingerprint", "refined_score_fingerprint", "comparison_fingerprint"):
        assert (
            "g16_counterfactual_publication",
            field,
            "g16_attribution_bound_publication",
            field,
        ) in links


def test_missing_bound_publication_reports_incomplete_binding(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "g16_attribution_bound_publication":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_publication"
    assert report["status"] == (
        "G16_COUNTERFACTUAL_PUBLICATION_READY_ATTRIBUTION_BINDING_INCOMPLETE"
    )


def test_complete_fixture_preserves_controls(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    bound = values["g16_attribution_bound_publication"]
    assert bound["g15_blind_score_fingerprint"] != bound["g15_refined_score_fingerprint"]
    assert bound["blind_score_fingerprint"] != bound["refined_score_fingerprint"]
    assert bound["actual_g16_outcomes_used"] is True
    assert bound["random_shuffle_used"] is False
    assert bound["blind_forecasts_immutable"] is True
    assert bound["may_update_ng_brain"] is False
    assert bound["execution_authority"] is False
    assert bound["cme_event_contracts_mode"] == "SHADOW"
    assert bound["brokerage_contract"] == "tastytrade_not_ibkr"
    assert bound["options_lane_started"] is False

    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V38"
    assert report["g16_scoring_bound_to_attribution_scored_g15_lessons"] is True


def test_link_substitution_blocks_bound_publication(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    target = copy.deepcopy(values["g16_attribution_bound_publication"])
    target["blind_score_fingerprint"] = "x" * 64
    target.pop("fingerprint", None)
    target["fingerprint"] = readiness._fingerprint(target)
    values["g16_attribution_bound_publication"] = target
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_publication"
    row = next(item for item in report["stages"] if item["key"] == "g16_attribution_bound_publication")
    assert any("provenance link mismatch" in blocker for blocker in row["blockers"])


def test_executor_builds_attribution_bound_publication(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    row = rows["g16_attribution_bound_publication"]
    assert row["expected_output"] == "g16_attribution_bound_publication_gate.json"
    assert row["suggested_entrypoint"] == [
        "python",
        "ng_g16_attribution_bound_publication_gate.py",
    ]
    assert row["requires_fixed_outcomes"] is True


def test_executor_rejects_removed_bound_publication(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row for row in tampered["stages"] if row["key"] != "g16_attribution_bound_publication"
    ]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_entrypoint_substitution(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(item for item in tampered["stages"] if item["key"] == "g16_attribution_bound_publication")
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_bound_publication(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(item for item in tampered["stages"] if item["key"] == "g16_attribution_bound_publication")
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
