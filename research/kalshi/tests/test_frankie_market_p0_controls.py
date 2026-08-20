from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_cognition import CognitiveContractError  # noqa: E402
from frankie_market_p0_controls import (  # noqa: E402
    AdaptiveNullPolicy,
    CalibrationPolicy,
    PairedEvidencePolicy,
    RetentionPolicy,
    evaluate_calibration_selective_gate,
    evaluate_paired_repeated_seed_gate,
    evaluate_planted_null_contamination_gate,
    evaluate_retention_matrix,
    score_open_stream_events,
    validate_byte_exact_rollback,
    validate_first_lock_movie,
    validate_reveal_time_purged_splits,
)


class FrankieMarketP0ControlTests(unittest.TestCase):
    def test_open_stream_event_matching_scores_delay_misses_and_false_alarms(self):
        result = score_open_stream_events(
            events=[
                {"event_id": "e1", "stream_id": "s1", "timestamp": 20},
                {"event_id": "e2", "stream_id": "s1", "timestamp": 70},
                {"event_id": "e3", "stream_id": "s2", "timestamp": 50},
            ],
            alarms=[
                {"alarm_id": "a0", "stream_id": "s1", "timestamp": 10},
                {"alarm_id": "a1", "stream_id": "s1", "timestamp": 22},
                {"alarm_id": "a2", "stream_id": "s1", "timestamp": 71},
                {"alarm_id": "a3", "stream_id": "s1", "timestamp": 90},
                {"alarm_id": "a4", "stream_id": "s2", "timestamp": 48},
            ],
            observation_windows=[
                {"stream_id": "s1", "start_timestamp": 0, "end_timestamp": 100},
                {"stream_id": "s2", "start_timestamp": 0, "end_timestamp": 100},
            ],
            max_early_seconds=5,
            max_late_seconds=5,
        )
        self.assertEqual(result["metrics"]["matched_count"], 3)
        self.assertEqual(result["metrics"]["false_alarm_count"], 2)
        self.assertEqual(result["metrics"]["missed_event_count"], 0)
        self.assertEqual(result["metrics"]["mean_delay_seconds"], 1 / 3)
        self.assertEqual(result["metrics"]["early_match_fraction"], 1 / 3)
        self.assertEqual(result["false_alarm_ids"], ["a0", "a3"])

    def test_open_stream_matching_is_stream_local_and_fail_closed(self):
        with self.assertRaises(CognitiveContractError):
            score_open_stream_events(
                events=[{"event_id": "e1", "stream_id": "missing", "timestamp": 1}],
                alarms=[],
                observation_windows=[
                    {"stream_id": "s1", "start_timestamp": 0, "end_timestamp": 10}
                ],
                max_late_seconds=5,
            )

    @staticmethod
    def clean_split_rows():
        return [
            {
                "case_id": "d1",
                "group_id": "g1",
                "split": "DISCOVERY",
                "start_timestamp": 0,
                "end_timestamp": 5,
                "reveal_timestamp": 10,
            },
            {
                "case_id": "t1",
                "group_id": "g2",
                "split": "TUNE",
                "start_timestamp": 15,
                "end_timestamp": 18,
                "reveal_timestamp": 20,
            },
            {
                "case_id": "o1",
                "group_id": "g3",
                "split": "OOT",
                "start_timestamp": 25,
                "end_timestamp": 28,
                "reveal_timestamp": 30,
            },
        ]

    def test_reveal_time_purged_split_accepts_clean_chronology(self):
        result = validate_reveal_time_purged_splits(
            self.clean_split_rows(), ["DISCOVERY", "TUNE", "OOT"], embargo_seconds=5
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual([row["clearance_seconds"] for row in result["boundaries"]], [5.0, 5.0])

    def test_reveal_time_purged_split_rejects_overlap_post_reveal_and_group_reuse(self):
        overlap = self.clean_split_rows()
        overlap[1] = {**overlap[1], "start_timestamp": 9}
        with self.assertRaises(CognitiveContractError):
            validate_reveal_time_purged_splits(overlap, ["DISCOVERY", "TUNE", "OOT"])

        post_reveal = self.clean_split_rows()
        post_reveal[0] = {**post_reveal[0], "end_timestamp": 10}
        with self.assertRaises(CognitiveContractError):
            validate_reveal_time_purged_splits(post_reveal, ["DISCOVERY", "TUNE", "OOT"])

        reused_group = self.clean_split_rows()
        reused_group[1] = {**reused_group[1], "group_id": "g1"}
        with self.assertRaises(CognitiveContractError):
            validate_reveal_time_purged_splits(reused_group, ["DISCOVERY", "TUNE", "OOT"])

    @staticmethod
    def lock_movie():
        return [
            {"timestamp": 10, "probabilities": {"DOWN": 0.60, "UP": 0.40}},
            {"timestamp": 11, "probabilities": {"DOWN": 0.70, "UP": 0.30}},
            {"timestamp": 12, "probabilities": {"DOWN": 0.75, "UP": 0.25}},
            {"timestamp": 13, "probabilities": {"DOWN": 0.80, "UP": 0.20}},
        ]

    def test_first_lock_recomputed_at_current_second_never_backdated(self):
        lock = {
            "decision_timestamp": 12,
            "predicted_label": "DOWN",
            "winning_probability": 0.75,
            "winning_margin": 0.50,
            "persistence_observed_seconds": 2,
            "probabilities": {"DOWN": 0.75, "UP": 0.25},
        }
        result = validate_first_lock_movie(
            self.lock_movie(),
            ["DOWN", "UP"],
            {"minimum_probability": 0.70, "minimum_margin": 0.30, "persistence_seconds": 2},
            lock,
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["computed_first_lock"]["decision_timestamp"], 12.0)

    def test_first_lock_rejects_backdating_and_probability_tamper(self):
        backdated = {
            "decision_timestamp": 11,
            "predicted_label": "DOWN",
            "winning_probability": 0.70,
            "winning_margin": 0.40,
            "persistence_observed_seconds": 2,
            "probabilities": {"DOWN": 0.70, "UP": 0.30},
        }
        rule = {"minimum_probability": 0.70, "minimum_margin": 0.30, "persistence_seconds": 2}
        with self.assertRaises(CognitiveContractError):
            validate_first_lock_movie(self.lock_movie(), ["DOWN", "UP"], rule, backdated)
        tampered = self.lock_movie()
        tampered[0] = {"timestamp": 10, "probabilities": {"DOWN": 0.6, "UP": 0.5}}
        with self.assertRaises(CognitiveContractError):
            validate_first_lock_movie(tampered, ["DOWN", "UP"], rule, None)

    @staticmethod
    def calibration_policy():
        return CalibrationPolicy(
            ece_bins=5,
            min_rows_per_stratum=2,
            min_selected_per_stratum=1,
            max_brier=0.10,
            max_log_loss=0.40,
            max_ece=0.25,
            max_selective_risk=0.0,
            max_wrong_lock_rate=0.0,
            min_coverage=0.5,
        )

    @staticmethod
    def calibration_rows():
        return [
            {"case_id": "a1", "stratum": "A", "truth": 1, "probability": 0.9, "selected": True, "lock_label": 1},
            {"case_id": "a2", "stratum": "A", "truth": 0, "probability": 0.1, "selected": False},
            {"case_id": "b1", "stratum": "B", "truth": 1, "probability": 0.8, "selected": True, "lock_label": 1},
            {"case_id": "b2", "stratum": "B", "truth": 0, "probability": 0.2, "selected": False},
        ]

    def test_calibration_selective_gate_reports_all_declared_metrics(self):
        result = evaluate_calibration_selective_gate(
            self.calibration_rows(), ["A", "B"], self.calibration_policy()
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(set(result["metrics"]), {"ALL", "A", "B"})
        self.assertEqual(result["metrics"]["A"]["coverage"], 0.5)
        self.assertEqual(result["metrics"]["A"]["selective_risk"], 0.0)

    def test_calibration_gate_fails_wrong_lock_and_rejects_missing_stratum(self):
        wrong = self.calibration_rows()
        wrong[0] = {**wrong[0], "lock_label": 0}
        result = evaluate_calibration_selective_gate(wrong, ["A", "B"], self.calibration_policy())
        self.assertEqual(result["verdict"], "FAIL")
        self.assertGreater(result["metrics"]["A"]["wrong_lock_rate"], 0.0)

        with self.assertRaises(CognitiveContractError):
            evaluate_calibration_selective_gate(
                self.calibration_rows(), ["A", "B", "MISSING"], self.calibration_policy()
            )

    @staticmethod
    def paired_policy():
        return PairedEvidencePolicy(
            min_cases=5,
            min_seeds_per_case=3,
            min_effect=0.0,
            confidence_z=1.96,
            min_case_win_rate=1.0,
            max_seed_loss_rate=0.0,
        )

    @staticmethod
    def paired_rows():
        return [
            {
                "case_id": f"case-{case}",
                "seed": seed,
                "candidate_metric": 1.0 + 0.01 * case,
                "control_metric": 0.5,
            }
            for case in range(5)
            for seed in (11, 22, 33)
        ]

    def test_paired_repeated_seed_gate_clusters_by_case(self):
        result = evaluate_paired_repeated_seed_gate(
            self.paired_rows(), [11, 22, 33], self.paired_policy()
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["case_count"], 5)
        self.assertGreater(result["lower_confidence_bound"], 0.0)

    def test_paired_gate_rejects_missing_seed_and_fails_uncertain_effect(self):
        with self.assertRaises(CognitiveContractError):
            evaluate_paired_repeated_seed_gate(
                self.paired_rows()[:-1], [11, 22, 33], self.paired_policy()
            )
        no_effect = [
            {**row, "candidate_metric": row["control_metric"]}
            for row in self.paired_rows()
        ]
        result = evaluate_paired_repeated_seed_gate(
            no_effect, [11, 22, 33], self.paired_policy()
        )
        self.assertEqual(result["verdict"], "FAIL")

    @staticmethod
    def retention_rows():
        return [
            {
                "suite_id": suite,
                "stratum": stratum,
                "row_count": 20,
                "baseline_metric": 0.70,
                "candidate_metric": 0.71,
                "higher_is_better": True,
            }
            for suite in ("NO_LOCK", "WRONG_LOCK")
            for stratum in ("D0", "POX")
        ]

    def test_retention_matrix_requires_complete_cells_and_gates_regression(self):
        policy = RetentionPolicy(min_rows_per_cell=10, max_regression=0.01)
        result = evaluate_retention_matrix(
            self.retention_rows(), ["NO_LOCK", "WRONG_LOCK"], ["D0", "POX"], policy
        )
        self.assertEqual(result["verdict"], "PASS")

        bad = self.retention_rows()
        bad[0] = {**bad[0], "candidate_metric": 0.60}
        self.assertEqual(
            evaluate_retention_matrix(
                bad, ["NO_LOCK", "WRONG_LOCK"], ["D0", "POX"], policy
            )["verdict"],
            "FAIL",
        )
        with self.assertRaises(CognitiveContractError):
            evaluate_retention_matrix(
                self.retention_rows()[:-1],
                ["NO_LOCK", "WRONG_LOCK"],
                ["D0", "POX"],
                policy,
            )

    def test_byte_exact_rollback_recomputes_hashes_and_refuses_vacuous_test(self):
        before = {"model": b"old-model", "config": b"old-config"}
        candidate = {"model": b"new-model", "config": b"old-config"}
        expected = {key: hashlib.sha256(value).hexdigest() for key, value in before.items()}
        result = validate_byte_exact_rollback(before, candidate, dict(before), expected)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["changed_artifact_count"], 1)

        with self.assertRaises(CognitiveContractError):
            validate_byte_exact_rollback(before, candidate, {**before, "model": b"wrong"}, expected)
        with self.assertRaises(CognitiveContractError):
            validate_byte_exact_rollback(before, dict(before), dict(before), expected)

    @staticmethod
    def null_bindings():
        return {
            "precommit_hash": "1" * 64,
            "adaptive_search_manifest_hash": "2" * 64,
            "planted_null_manifest_hash": "3" * 64,
            "locked_evaluator_hash": "4" * 64,
        }

    @classmethod
    def null_rows(cls, selected_count=0):
        bindings = cls.null_bindings()
        evaluator = bindings["locked_evaluator_hash"]
        search = bindings["adaptive_search_manifest_hash"]
        precommit = bindings["precommit_hash"]
        null_manifest = bindings["planted_null_manifest_hash"]
        rows = []
        for index in range(100):
            null_hash = hashlib.sha256(f"null-{index}".encode()).hexdigest()
            candidate_hash = hashlib.sha256(f"candidate-{index}".encode()).hexdigest()
            rows.append(
                {
                    "trial_id": f"null-{index:03d}",
                    "seed": index,
                    "planted_effect": 0.0,
                    "selected": index < selected_count,
                    "observed_delta": 0.01 if index < selected_count else 0.0,
                    "null_draw_hash": null_hash,
                    "candidate_hash": candidate_hash,
                    "adaptation_parent_hashes": [precommit, search],
                    "evaluation_parent_hashes": [
                        candidate_hash, null_hash, precommit, null_manifest, evaluator,
                    ],
                }
            )
        return rows

    def test_planted_null_gate_binds_parents_and_false_selection_uncertainty(self):
        result = evaluate_planted_null_contamination_gate(
            self.null_rows(),
            AdaptiveNullPolicy(min_trials=100, max_false_selection_rate=0.05),
            **self.null_bindings(),
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["false_selection_count"], 0)
        self.assertLess(result["false_selection_wilson_upper"], 0.05)

        failed = evaluate_planted_null_contamination_gate(
            self.null_rows(selected_count=10),
            AdaptiveNullPolicy(min_trials=100, max_false_selection_rate=0.05),
            **self.null_bindings(),
        )
        self.assertEqual(failed["verdict"], "FAIL")

    def test_planted_null_gate_rejects_declared_parent_contamination(self):
        rows = self.null_rows()
        rows[0] = {
            **rows[0],
            "adaptation_parent_hashes": [rows[0]["null_draw_hash"]],
        }
        with self.assertRaises(CognitiveContractError):
            evaluate_planted_null_contamination_gate(
                rows,
                AdaptiveNullPolicy(min_trials=100, max_false_selection_rate=0.05),
                **self.null_bindings(),
            )


if __name__ == "__main__":
    unittest.main()
