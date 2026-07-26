from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g16_attribution_bound_causal_authorization_gate as gate
import ng_historical_refinement_executor_v31 as executor
import ng_historical_refinement_readiness_v35 as readiness


def _keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _rehash(plan: dict) -> None:
    plan.pop("fingerprint", None)
    plan["fingerprint"] = readiness._fingerprint(plan)


def test_bound_causal_is_between_legacy_causal_and_prepared_curve() -> None:
    keys = _keys()
    index = keys.index("g16_counterfactual_causal_authorization")
    assert keys[index : index + 3] == [
        "g16_counterfactual_causal_authorization",
        "g16_attribution_bound_causal_authorization",
        "g16_prepared_curve_authorization",
    ]
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["g16_counterfactual_causal_authorization"].pre_outcome is False
    assert by_key["g16_attribution_bound_causal_authorization"].pre_outcome is False
    assert by_key["g16_prepared_curve_authorization"].pre_outcome is True
    assert by_key["g16_attribution_bound_causal_authorization"].schema == gate.SCHEMA


def test_bound_causal_links_g15_lineage_and_g16_posterior() -> None:
    links = set(readiness.LINK_RULES)
    expected = {
        (
            "g15_g16_attribution_bound_lineage",
            "fingerprint",
            "g16_attribution_bound_causal_authorization",
            "attribution_bound_lineage_fingerprint",
        ),
        (
            "g16_counterfactual_causal_authorization",
            "fingerprint",
            "g16_attribution_bound_causal_authorization",
            "legacy_counterfactual_causal_authorization_fingerprint",
        ),
        (
            "g16_prepared_causal_authorization",
            "fingerprint",
            "g16_attribution_bound_causal_authorization",
            "prepared_causal_authorization_fingerprint",
        ),
        (
            "g16_prepared_replay",
            "fingerprint",
            "g16_attribution_bound_causal_authorization",
            "prepared_replay_gate_fingerprint",
        ),
        (
            "g16_historical_replay",
            "fingerprint",
            "g16_attribution_bound_causal_authorization",
            "replay_fingerprint",
        ),
        (
            "g15_g16_attribution_bound_lineage",
            "blind_score_fingerprint",
            "g16_attribution_bound_causal_authorization",
            "blind_score_fingerprint",
        ),
        (
            "g15_g16_attribution_bound_lineage",
            "refined_score_fingerprint",
            "g16_attribution_bound_causal_authorization",
            "refined_score_fingerprint",
        ),
    }
    assert expected.issubset(links)


def test_missing_bound_causal_blocks_prepared_curve(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "g16_attribution_bound_causal_authorization":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_causal_authorization"
    assert report["status"] == (
        "G16_LEGACY_CAUSAL_READY_ATTRIBUTION_BOUND_CAUSAL_INCOMPLETE"
    )
    assert report["g16_prepared_curve_opened_after_attribution_bound_causal"] is False


def test_link_substitution_blocks_bound_causal(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    target = copy.deepcopy(values["g16_attribution_bound_causal_authorization"])
    target["attribution_bound_lineage_fingerprint"] = "x" * 64
    target.pop("fingerprint", None)
    target["fingerprint"] = readiness._fingerprint(target)
    values["g16_attribution_bound_causal_authorization"] = target
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g16_attribution_bound_causal_authorization"
    row = next(
        item
        for item in report["stages"]
        if item["key"] == "g16_attribution_bound_causal_authorization"
    )
    assert any("provenance link mismatch" in blocker for blocker in row["blockers"])


def test_complete_fixture_preserves_g16_blind_wall(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    bound = values["g16_attribution_bound_causal_authorization"]
    assert bound["g16_posterior_bound_to_attribution_scored_g15_lessons"] is True
    assert bound["blind_score_fingerprint"] != bound["refined_score_fingerprint"]
    assert bound["actual_g15_outcomes_used"] is True
    assert bound["actual_g16_outcomes_used"] is False
    assert bound["g16_scoring_authorized"] is False
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
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V35"
    assert report["g16_posterior_bound_to_attribution_scored_g15_lessons"] is True
    assert report["g16_outcomes_unavailable_during_causal_authorization"] is True


def test_executor_builds_fixed_g15_causal_binding_then_blind_curve(
    tmp_path: Path,
) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["g16_counterfactual_causal_authorization"][
        "requires_fixed_outcomes"
    ] is True
    bound = rows["g16_attribution_bound_causal_authorization"]
    assert bound["expected_output"] == "g16_attribution_bound_causal_authorization.json"
    assert bound["suggested_entrypoint"] == [
        "python",
        "ng_g16_attribution_bound_causal_authorization_gate.py",
    ]
    assert bound["requires_fixed_outcomes"] is True
    assert rows["g16_prepared_curve_authorization"][
        "requires_fixed_outcomes"
    ] is False


def test_executor_rejects_removed_bound_causal(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row
        for row in tampered["stages"]
        if row["key"] != "g16_attribution_bound_causal_authorization"
    ]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_bound_causal(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g16_attribution_bound_causal_authorization"
    )
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_legacy_causal(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g16_counterfactual_causal_authorization"
    )
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_fixed_g16_outcome_curve(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g16_prepared_curve_authorization"
    )
    row["requires_fixed_outcomes"] = True
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_artifact_substitution(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g16_attribution_bound_causal_authorization"
    )
    row["expected_output"] = "substituted.json"
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_entrypoint_substitution(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g16_attribution_bound_causal_authorization"
    )
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
