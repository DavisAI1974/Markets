from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_g15_g16_attribution_bound_lineage_gate as gate
import ng_historical_refinement_executor_v30 as executor
import ng_historical_refinement_readiness_v34 as readiness


def _keys() -> list[str]:
    return [spec.key for spec in readiness.STAGES]


def _rehash(plan: dict) -> None:
    plan.pop("fingerprint", None)
    plan["fingerprint"] = readiness._fingerprint(plan)


def test_bound_lineage_is_between_legacy_lineage_and_g16_basis() -> None:
    keys = _keys()
    index = keys.index("g15_g16_counterfactual_lineage")
    assert keys[index : index + 3] == [
        "g15_g16_counterfactual_lineage",
        "g15_g16_attribution_bound_lineage",
        "g16_corpus_basis",
    ]
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["g15_g16_counterfactual_lineage"].pre_outcome is False
    assert by_key["g15_g16_attribution_bound_lineage"].pre_outcome is False
    assert by_key["g16_corpus_basis"].pre_outcome is True
    assert by_key["g15_g16_attribution_bound_lineage"].schema == gate.SCHEMA


def test_bound_lineage_links_publication_lessons_scores_and_plan() -> None:
    links = set(readiness.LINK_RULES)
    expected = {
        (
            "g15_attribution_bound_publication",
            "fingerprint",
            "g15_g16_attribution_bound_lineage",
            "attribution_bound_publication_fingerprint",
        ),
        (
            "g15_counterfactual_lesson_gate",
            "fingerprint",
            "g15_g16_attribution_bound_lineage",
            "counterfactual_lesson_gate_fingerprint",
        ),
        (
            "g15_g16_counterfactual_lineage",
            "fingerprint",
            "g15_g16_attribution_bound_lineage",
            "legacy_lineage_fingerprint",
        ),
        (
            "g15_attribution_bound_publication",
            "blind_score_fingerprint",
            "g15_g16_attribution_bound_lineage",
            "blind_score_fingerprint",
        ),
        (
            "g15_attribution_bound_publication",
            "refined_score_fingerprint",
            "g15_g16_attribution_bound_lineage",
            "refined_score_fingerprint",
        ),
        (
            "g15_g16_counterfactual_lineage",
            "g16_plan_fingerprint",
            "g15_g16_attribution_bound_lineage",
            "g16_plan_fingerprint",
        ),
    }
    assert expected.issubset(links)


def test_missing_bound_lineage_blocks_g16_corpus_basis(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key == "g15_g16_attribution_bound_lineage":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g15_g16_attribution_bound_lineage"
    assert report["status"] == (
        "G15_G16_LEGACY_LINEAGE_READY_ATTRIBUTION_BOUND_LINEAGE_INCOMPLETE"
    )
    assert report["g16_corpus_basis_opened_after_attribution_bound_lineage"] is False


def test_link_substitution_blocks_bound_lineage(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    target = copy.deepcopy(values["g15_g16_attribution_bound_lineage"])
    target["legacy_lineage_fingerprint"] = "x" * 64
    target.pop("fingerprint", None)
    target["fingerprint"] = readiness._fingerprint(target)
    values["g15_g16_attribution_bound_lineage"] = target
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "g15_g16_attribution_bound_lineage"
    row = next(
        item
        for item in report["stages"]
        if item["key"] == "g15_g16_attribution_bound_lineage"
    )
    assert any("provenance link mismatch" in blocker for blocker in row["blockers"])


def test_complete_fixture_preserves_g16_blind_wall(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    bound = values["g15_g16_attribution_bound_lineage"]
    assert bound["all_six_factors_authorized_before_scoring"] is True
    assert bound["separate_blind_refined_scores_verified"] is True
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
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V34"
    assert report["g15_scored_lessons_recursively_bound_to_g16_plan"] is True
    assert report["g16_outcomes_unavailable_during_lesson_lineage"] is True


def test_executor_builds_fixed_g15_outcome_lineage_then_blind_g16_basis(
    tmp_path: Path,
) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    executor.validate_plan(plan)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["g15_g16_counterfactual_lineage"]["requires_fixed_outcomes"] is True
    bound = rows["g15_g16_attribution_bound_lineage"]
    assert bound["expected_output"] == "g15_g16_attribution_bound_lineage_gate.json"
    assert bound["suggested_entrypoint"] == [
        "python",
        "ng_g15_g16_attribution_bound_lineage_gate.py",
    ]
    assert bound["requires_fixed_outcomes"] is True
    assert rows["g16_corpus_basis"]["requires_fixed_outcomes"] is False


def test_executor_rejects_removed_bound_lineage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row
        for row in tampered["stages"]
        if row["key"] != "g15_g16_attribution_bound_lineage"
    ]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_bound_lineage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_g16_attribution_bound_lineage"
    )
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_pre_outcome_legacy_scored_lineage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        item
        for item in tampered["stages"]
        if item["key"] == "g15_g16_counterfactual_lineage"
    )
    row["requires_fixed_outcomes"] = False
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_executor_rejects_fixed_outcome_g16_basis(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(item for item in tampered["stages"] if item["key"] == "g16_corpus_basis")
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
        if item["key"] == "g15_g16_attribution_bound_lineage"
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
        if item["key"] == "g15_g16_attribution_bound_lineage"
    )
    row["suggested_entrypoint"] = ["python", "wrong.py"]
    _rehash(tampered)
    with pytest.raises(Exception):
        executor.validate_plan(tampered)
