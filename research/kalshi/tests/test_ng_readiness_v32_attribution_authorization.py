from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g15_counterfactual_attribution_gate as gate
import ng_historical_refinement_executor_v28 as executor
import ng_historical_refinement_readiness_v32 as readiness


def _stage_keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def test_authorization_stage_is_directly_before_publication() -> None:
    keys = _stage_keys()
    index = keys.index("g15_counterfactual_attribution")
    assert keys[index : index + 3] == [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
    ]
    spec = readiness.STAGES[index + 1]
    assert spec.filename == "g15_counterfactual_attribution_authorization.json"
    assert spec.schema == gate.SCHEMA
    assert spec.pre_outcome is True
    assert spec.ready_statuses == {gate.READY, gate.READY_WITH_STAND_DOWNS}


def test_authorization_links_exact_replay_refinement_and_attribution() -> None:
    links = set(readiness.LINK_RULES)
    assert (
        "g15_exact_replay",
        "completion_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "exact_replay_completion_fingerprint",
    ) in links
    assert (
        "g15_exact_refinement",
        "pipeline_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "pipeline_fingerprint",
    ) in links
    assert (
        "g15_exact_refinement",
        "authorization_fingerprint",
        "g15_counterfactual_attribution_authorization",
        "refinement_authorization_fingerprint",
    ) in links
    assert (
        "g15_counterfactual_attribution",
        "fingerprint",
        "g15_counterfactual_attribution_authorization",
        "attribution_fingerprint",
    ) in links


def test_missing_authorization_blocks_publication(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "g15_counterfactual_attribution_authorization":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g15_counterfactual_attribution_authorization"
    assert report["g15_publication_bound_to_attribution_authorization"] is False
    assert report["status"] == "G15_COUNTERFACTUAL_ATTRIBUTION_READY_AUTHORIZATION_INCOMPLETE"


def test_complete_fixture_preserves_authority_wall(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    authorization = values["g15_counterfactual_attribution_authorization"]
    assert authorization["all_six_factors_quantified"] is True
    assert authorization["lesson_proposals_brain_write_forbidden"] is True
    assert authorization["actual_outcomes_used"] is False
    assert authorization["random_shuffle_used"] is False
    assert authorization["blind_forecasts_immutable"] is True
    assert authorization["may_update_ng_brain"] is False
    assert authorization["execution_authority"] is False
    assert authorization["g16_authorized"] is False
    assert authorization["cme_event_contracts_mode"] == "SHADOW"
    assert authorization["brokerage_contract"] == "tastytrade_not_ibkr"
    assert authorization["options_lane_started"] is False

    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V32"
    assert report["g15_all_six_factors_authorized_before_scoring"] is True


def test_executor_builds_v32_authorization_contract(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    row = rows["g15_counterfactual_attribution_authorization"]
    assert row["expected_output"] == "g15_counterfactual_attribution_authorization.json"
    assert row["suggested_entrypoint"] == [
        "python",
        "ng_g15_counterfactual_attribution_gate.py",
    ]
    assert row["requires_fixed_outcomes"] is False


def test_executor_rejects_removed_authorization_stage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row
        for row in tampered["stages"]
        if row["key"] != "g15_counterfactual_attribution_authorization"
    ]
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_post_outcome_authorization(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_counterfactual_attribution_authorization"
    )
    row["requires_fixed_outcomes"] = True
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
        if item["key"] == "g15_counterfactual_attribution_authorization"
    )
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
