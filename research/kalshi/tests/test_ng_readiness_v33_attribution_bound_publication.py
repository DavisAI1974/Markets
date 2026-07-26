from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g15_attribution_bound_publication_gate as gate
import ng_historical_refinement_executor_v29 as executor
import ng_historical_refinement_readiness_v33 as readiness


def _keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def test_binding_stage_is_between_publication_and_lesson_gate() -> None:
    keys = _keys()
    index = keys.index("g15_publication")
    assert keys[index : index + 3] == [
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]
    spec = readiness.STAGES[index + 1]
    assert spec.filename == "g15_attribution_bound_publication_gate.json"
    assert spec.schema == gate.SCHEMA
    assert spec.pre_outcome is False
    lesson = readiness.STAGES[index + 2]
    assert lesson.pre_outcome is False


def test_binding_links_authorization_and_publication() -> None:
    links = set(readiness.LINK_RULES)
    assert (
        "g15_counterfactual_attribution_authorization",
        "authorization_fingerprint",
        "g15_attribution_bound_publication",
        "attribution_authorization_fingerprint",
    ) in links
    assert (
        "g15_publication",
        "completion_fingerprint",
        "g15_attribution_bound_publication",
        "publication_completion_fingerprint",
    ) in links


def test_missing_binding_blocks_lesson_adjudication(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "g15_attribution_bound_publication":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g15_attribution_bound_publication"
    assert report["status"] == "G15_PUBLICATION_COMPLETE_ATTRIBUTION_BINDING_INCOMPLETE"
    assert report["g15_lesson_adjudication_bound_to_verified_publication"] is False


def test_complete_fixture_preserves_separate_scores_and_authority(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    bound = values["g15_attribution_bound_publication"]
    assert bound["separate_blind_refined_scores_verified"] is True
    assert bound["lesson_proposals_brain_write_forbidden"] is True
    assert bound["actual_g15_outcomes_used"] is True
    assert bound["actual_g16_outcomes_used"] is False
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
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V33"
    assert report["g15_separate_blind_refined_scores_recursively_verified"] is True
    assert report["g15_lesson_adjudication_fixed_outcome_only"] is True


def test_executor_builds_post_outcome_binding_contract(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    bound = rows["g15_attribution_bound_publication"]
    assert bound["expected_output"] == "g15_attribution_bound_publication_gate.json"
    assert bound["suggested_entrypoint"] == [
        "python",
        "ng_g15_attribution_bound_publication_gate.py",
    ]
    assert bound["requires_fixed_outcomes"] is True
    assert rows["g15_counterfactual_lesson_gate"]["requires_fixed_outcomes"] is True


def test_executor_rejects_removed_binding_stage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row
        for row in tampered["stages"]
        if row["key"] != "g15_attribution_bound_publication"
    ]
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_binding_stage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_attribution_bound_publication"
    )
    row["requires_fixed_outcomes"] = False
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_scored_lesson_gate(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_counterfactual_lesson_gate"
    )
    row["requires_fixed_outcomes"] = False
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_entrypoint_substitution(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_attribution_bound_publication"
    )
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
