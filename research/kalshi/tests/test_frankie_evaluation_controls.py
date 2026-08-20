from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_cognition import CognitiveContractError  # noqa: E402
from frankie_evaluation_controls import (  # noqa: E402
    HoldoutExposureLedger,
    MIN_JUDGE_CANARY_CASES,
    evaluate_judge_independence_canary,
    validate_release_exposure_audit,
)


class FrankieEvaluationControlTests(unittest.TestCase):
    SPLIT_HASH = "a" * 64

    @classmethod
    def release_ledger(cls):
        return HoldoutExposureLedger("release-1", cls.SPLIT_HASH, "RELEASE")

    @staticmethod
    def judge_rows(*, order_flip=False, length_flip=False, truth_error=False):
        rows = []
        for index in range(MIN_JUDGE_CANARY_CASES):
            truth = "candidate-a"
            rows.append(
                {
                    "case_id": f"judge-{index:03d}",
                    "truth_choice": truth,
                    "forward_choice": "candidate-b" if truth_error and index == 0 else truth,
                    "reversed_choice": "candidate-b" if order_flip and index == 0 else truth,
                    "length_control_choice": "candidate-b" if length_flip and index == 0 else truth,
                }
            )
        return rows

    def test_release_ledger_allows_one_aggregate_final_score(self):
        ledger = self.release_ledger().record(
            query_id="final",
            consumer="locked-evaluator",
            purpose="FINAL_RELEASE_SCORE",
            output_level="AGGREGATE_ONLY",
        )
        audit = ledger.release_audit()
        self.assertEqual(
            validate_release_exposure_audit(
                audit,
                split_id="release-1",
                split_hash=self.SPLIT_HASH,
            ),
            audit["audit_hash"],
        )

    def test_release_ledger_refuses_row_level_and_second_query(self):
        with self.assertRaises(CognitiveContractError):
            self.release_ledger().record(
                query_id="rows",
                consumer="developer",
                purpose="FINAL_RELEASE_SCORE",
                output_level="ROW_LEVEL",
            )
        consumed = self.release_ledger().record(
            query_id="final",
            consumer="locked-evaluator",
            purpose="FINAL_RELEASE_SCORE",
            output_level="AGGREGATE_ONLY",
        )
        with self.assertRaises(CognitiveContractError):
            consumed.record(
                query_id="again",
                consumer="locked-evaluator",
                purpose="FINAL_RELEASE_SCORE",
                output_level="AGGREGATE_ONLY",
            )

    def test_release_audit_is_bound_to_precommitted_split_hash(self):
        audit = self.release_ledger().record(
            query_id="final",
            consumer="locked-evaluator",
            purpose="FINAL_RELEASE_SCORE",
            output_level="AGGREGATE_ONLY",
        ).release_audit()
        with self.assertRaises(CognitiveContractError):
            validate_release_exposure_audit(
                audit,
                split_id="release-1",
                split_hash="b" * 64,
            )

    def test_clean_judge_canary_retains_only_grading_authority(self):
        result = evaluate_judge_independence_canary(self.judge_rows())
        self.assertEqual(result["verdict"], "JUDGE_AUTHORITY_RETAINED")
        self.assertEqual(result["promotion_authority"], "NONE")

    def test_order_or_length_bias_revokes_judge_authority(self):
        for control in ({"order_flip": True}, {"length_flip": True}):
            with self.subTest(control=control):
                result = evaluate_judge_independence_canary(
                    self.judge_rows(**control),
                    max_order_flip_rate=0.0,
                    max_length_control_flip_rate=0.0,
                )
                self.assertEqual(result["verdict"], "JUDGE_AUTHORITY_REVOKED")


if __name__ == "__main__":
    unittest.main()
