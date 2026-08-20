from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_temporal_p0_controls import (  # noqa: E402
    TemporalP0ControlError,
    assess_frozen_pool_current_risk,
    audit_planted_null_first_locks,
    calibrate_accumulated_accuracy_gap,
    run_delayed_label_aci,
)


def _null_trial(trial_id: str, p_values: list[float], recorded=None):
    return {
        "trial_id": trial_id,
        "planted_null": True,
        "looks": [
            {"look_index": index, "observed_at": index, "p_value": value}
            for index, value in enumerate(p_values, start=1)
        ],
        "recorded_spending_first_lock_look": recorded,
    }


def test_planted_null_alpha_spending_is_anytime_and_has_naive_control():
    trials = [_null_trial(f"n{index}", [0.5, 0.04, 0.5]) for index in range(20)]
    receipt = audit_planted_null_first_locks(
        trials,
        alpha=0.05,
        spending_policy="TELESCOPING",
        planned_horizon=3,
    )
    assert receipt["total_planned_spend_upper_bound"] == 0.05
    assert receipt["spending_result"]["false_locks"] == 0
    assert receipt["finite_bonferroni_control"]["false_locks"] == 0
    assert receipt["naive_pointwise_control"]["false_locks"] == 20
    assert receipt["confidence_sequence_implementation"] is False
    assert receipt["authority"]["v4_launch_authority"] is False


def test_planted_null_audit_recomputes_first_lock_and_rejects_bad_record():
    receipt = audit_planted_null_first_locks(
        [_null_trial("false-lock", [0.001, 0.9], recorded=1)],
        alpha=0.05,
    )
    assert receipt["trial_receipts"][0]["spending_first_lock_look"] == 1
    tampered = _null_trial("tampered", [0.001, 0.9], recorded=2)
    with pytest.raises(TemporalP0ControlError, match="disagrees with recomputation"):
        audit_planted_null_first_locks([tampered], alpha=0.05)
    non_null = _null_trial("not-null", [0.5])
    non_null["planted_null"] = False
    with pytest.raises(TemporalP0ControlError, match="planted_null"):
        audit_planted_null_first_locks([non_null], alpha=0.05)


def _early_case(case_id: str, start: float, wrong_early: bool):
    truth = "UP"
    return {
        "case_id": case_id,
        "truth_label": truth,
        "full_prediction": truth,
        "case_start_at": start,
        "label_reveal_at": start + 3,
        "prefixes": [
            {
                "look_index": 1,
                "observed_at": start + 1,
                "prediction": "DOWN" if wrong_early else truth,
                "confidence": 0.7,
            },
            {
                "look_index": 2,
                "observed_at": start + 2,
                "prediction": truth,
                "confidence": 0.95,
            },
        ],
    }


def test_accumulated_gap_calibrates_only_on_calibration_then_scores_test():
    calibration = [
        _early_case(f"cal-{index}", index * 4.0, wrong_early=index % 2 == 0)
        for index in range(80)
    ]
    test_start = max(case["label_reveal_at"] for case in calibration) + 1
    test = [
        _early_case(f"test-{index}", test_start + index * 4.0, wrong_early=True)
        for index in range(20)
    ]
    receipt = calibrate_accumulated_accuracy_gap(
        calibration,
        test,
        candidate_thresholds=[0.6, 0.9],
        max_accuracy_gap=0.25,
        confidence_delta=0.2,
        min_calibration_halts_per_slice=10,
        calibration_iid_assumption_declared=True,
    )
    assert receipt["selected_threshold"] == 0.9
    assert receipt["test_partition_used_for_selection"] is False
    assert receipt["truth_relative_timing_optimization"] is False
    assert receipt["test_summary"]["marginal_accuracy_gap"] == 0.0
    assert receipt["test_summary"]["mean_normalized_halt_time"] == 1.0
    by_threshold = {row["threshold"]: row for row in receipt["candidate_summaries"]}
    assert by_threshold[0.6]["calibration_passed"] is False
    assert by_threshold[0.9]["calibration_passed"] is True


def test_accumulated_gap_rejects_partition_overlap_and_reveal_leakage():
    calibration = [_early_case("same", 0.0, False)]
    test = [_early_case("same", 10.0, False)]
    with pytest.raises(TemporalP0ControlError, match="overlap"):
        calibrate_accumulated_accuracy_gap(
            calibration,
            test,
            candidate_thresholds=[0.9],
            max_accuracy_gap=0.5,
            confidence_delta=0.2,
            min_calibration_halts_per_slice=1,
        )
    test[0]["case_id"] = "test"
    test[0]["case_start_at"] = 2.0
    test[0]["prefixes"][0]["observed_at"] = 2.2
    test[0]["prefixes"][1]["observed_at"] = 2.5
    test[0]["label_reveal_at"] = 4.0
    with pytest.raises(TemporalP0ControlError, match="mature before"):
        calibrate_accumulated_accuracy_gap(
            calibration,
            test,
            candidate_thresholds=[0.9],
            max_accuracy_gap=0.5,
            confidence_delta=0.2,
            min_calibration_halts_per_slice=1,
        )


def test_delayed_aci_updates_only_matured_labels_and_batches_same_time():
    events = [
        {
            "case_id": "a",
            "prediction_at": 0.0,
            "reveal_at": 10.0,
            "aci_miscovered": True,
            "static_miscovered": True,
        },
        {
            "case_id": "b",
            "prediction_at": 5.0,
            "reveal_at": 20.0,
            "aci_miscovered": False,
            "static_miscovered": True,
        },
        {
            "case_id": "c",
            "prediction_at": 15.0,
            "reveal_at": 30.0,
            "aci_miscovered": False,
            "static_miscovered": False,
        },
        {
            "case_id": "d",
            "prediction_at": 15.0,
            "reveal_at": 40.0,
            "aci_miscovered": False,
            "static_miscovered": False,
        },
    ]
    receipt = run_delayed_label_aci(
        events,
        target_miscoverage=0.1,
        gamma=0.2,
        audit_until=25.0,
    )
    decisions = {row["case_id"]: row for row in receipt["decision_ledger"]}
    assert decisions["a"]["alpha_used"] == 0.1
    assert decisions["b"]["alpha_used"] == 0.1
    assert decisions["c"]["alpha_used"] == 0.0
    assert decisions["d"]["alpha_used"] == 0.0
    assert [row["case_id"] for row in receipt["update_ledger"]] == ["a", "b"]
    assert receipt["pending_case_ids"] == ["c", "d"]
    assert receipt["final_alpha"] == pytest.approx(0.02)
    assert receipt["paper_faithful_end_to_end_conformal_system"] is False


def test_delayed_aci_rejects_an_already_known_label():
    with pytest.raises(TemporalP0ControlError, match="must follow"):
        run_delayed_label_aci(
            [
                {
                    "case_id": "bad",
                    "prediction_at": 2.0,
                    "reveal_at": 2.0,
                    "aci_miscovered": False,
                    "static_miscovered": False,
                }
            ],
            target_miscoverage=0.1,
            gamma=0.05,
        )


def _shift_rows():
    result = []
    for period in range(1, 9):
        early = period <= 4
        result.append(
            {
                "case_id": f"p{period}",
                "period_index": period,
                "observed_at": float(period),
                "reveal_at": period + 0.1,
                "losses": {
                    "A": 0.1 if early else 0.9,
                    "B": 0.8 if early else 0.1,
                },
            }
        )
    return result


def test_hhw_inspired_current_risk_has_matched_controls_and_switch_report():
    receipt = assess_frozen_pool_current_risk(
        _shift_rows(),
        {"A": "a" * 64, "B": "b" * 64},
        [
            {"assessment_id": "early", "assessment_at": 4.5},
            {"assessment_id": "shift", "assessment_at": 6.5},
            {"assessment_id": "late", "assessment_at": 8.5},
        ],
        loss_upper_bound=1.0,
        delta=0.05,
        adaptive_window_periods=[2, 4],
        fixed_window_periods=4,
        recent_window_periods=2,
        min_samples_per_window=2,
    )
    assert receipt["switch_report"]["adaptive"]["selection_path"] == ["A", "B", "B"]
    assert receipt["switch_report"]["adaptive"]["switch_count"] == 1
    assert receipt["switch_counts_operational_only"] is True
    assert receipt["cumulative_loss_guarantee"] is False
    assert receipt["best_fixed_candidate_guarantee"] is False
    for result in receipt["assessment_results"]:
        assert "fixed_window_control" in result
        assert "expanding_window_control" in result
        assert "recent_window_control" in result
    assert receipt["authority"]["model_promotion_authority"] is False


def test_hhw_inspired_current_risk_fails_closed_on_sparse_window():
    with pytest.raises(TemporalP0ControlError, match="sparse adaptive window"):
        assess_frozen_pool_current_risk(
            _shift_rows()[:2],
            {"A": "a" * 64, "B": "b" * 64},
            [{"assessment_id": "sparse", "assessment_at": 2.5}],
            loss_upper_bound=1.0,
            delta=0.05,
            adaptive_window_periods=[1, 2],
            fixed_window_periods=2,
            recent_window_periods=1,
            min_samples_per_window=2,
        )


def test_receipts_are_hash_bound_and_inputs_are_not_mutated():
    events = [
        {
            "case_id": "immutable",
            "prediction_at": 0.0,
            "reveal_at": 1.0,
            "aci_miscovered": False,
            "static_miscovered": False,
        }
    ]
    before = copy.deepcopy(events)
    receipt = run_delayed_label_aci(
        events,
        target_miscoverage=0.1,
        gamma=0.05,
        audit_until=1.0,
    )
    assert events == before
    assert len(receipt["receipt_hash"]) == 64
    assert set(receipt["authority"].values()) == {False}
