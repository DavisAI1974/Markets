import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ng_g15_counterfactual_score_gate as gate
import ng_g15_counterfactual_scoring_wall as wall
import ng_g15_path_score as scorer


class TestCounterfactualScoreGate(unittest.TestCase):
    def setUp(self):
        self.blind, self.refined, self.actual, self.blind_bytes = scorer._fixture()
        self.refined_bytes = (json.dumps(self.refined, indent=2) + "\n").encode("utf-8")
        self.lock = wall._selftest_lock()
        self.lock.update(
            {
                "blind_forecast_sha256": gate._sha(self.blind_bytes),
                "refined_forecast_sha256": gate._sha(self.refined_bytes),
                "refined_curve_fingerprint": self.refined["artifact_fingerprint"],
                "counterfactual_attribution_fingerprint": "attribution-fp",
                "lesson_candidate_ids_fixed_before_scoring": [
                    "g15_counterfactual.signed_flow"
                ],
            }
        )
        self._refingerprint(self.lock, "lock_fingerprint")

    def build(self):
        return gate.build_scores(
            lock=self.lock,
            blind=self.blind,
            refined=self.refined,
            actual=self.actual,
            blind_bytes=self.blind_bytes,
            refined_bytes=self.refined_bytes,
        )

    def test_scores_blind_and_refined_after_lock(self):
        receipt, blind_score, refined_score, comparison = self.build()
        self.assertEqual(receipt["status"], gate.READY)
        self.assertEqual(blind_score["forecast_kind"], "blind")
        self.assertEqual(refined_score["forecast_kind"], "refined")
        self.assertEqual(
            comparison["blind_score_fingerprint"],
            blind_score["artifact_fingerprint"],
        )
        self.assertEqual(
            comparison["refined_score_fingerprint"],
            refined_score["artifact_fingerprint"],
        )

    def test_receipt_binds_pre_outcome_lock(self):
        receipt, *_ = self.build()
        self.assertEqual(
            receipt["counterfactual_scoring_lock_fingerprint"],
            self.lock["lock_fingerprint"],
        )
        self.assertTrue(receipt["lock_validated_before_actual_file_open"])
        self.assertTrue(receipt["blind_and_refined_scores_separate"])

    def test_rejects_blind_byte_substitution(self):
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_locked_forecasts(
                self.lock,
                blind_bytes=self.blind_bytes + b"x",
                refined_bytes=self.refined_bytes,
            )

    def test_rejects_refined_byte_substitution(self):
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_locked_forecasts(
                self.lock,
                blind_bytes=self.blind_bytes,
                refined_bytes=self.refined_bytes + b"x",
            )

    def test_rejects_outcome_tainted_lock(self):
        self.lock["actual_g15_outcomes_used"] = True
        self._refingerprint(self.lock, "lock_fingerprint")
        with self.assertRaises(gate.CounterfactualScoreGateError):
            self.build()

    def test_rejects_score_selected_support_escalation(self):
        receipt, *_ = self.build()
        receipt["may_select_lesson_support_from_scores"] = True
        self._refingerprint(receipt, "fingerprint")
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_receipt(receipt)

    def test_rejects_g16_outcome_escalation(self):
        receipt, *_ = self.build()
        receipt["actual_g16_outcomes_used"] = True
        self._refingerprint(receipt, "fingerprint")
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_receipt(receipt)

    def test_rejects_comparison_substitution(self):
        receipt, blind_score, refined_score, comparison = self.build()
        altered = copy.deepcopy(comparison)
        altered["note"] = "changed"
        altered["artifact_fingerprint"] = scorer._fingerprint(
            {key: value for key, value in altered.items() if key != "artifact_fingerprint"}
        )
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_receipt(
                receipt,
                lock=self.lock,
                blind_score=blind_score,
                refined_score=refined_score,
                comparison=altered,
            )

    def test_rejects_refingerprinted_receipt_lock_substitution(self):
        receipt, *_ = self.build()
        receipt["counterfactual_scoring_lock_fingerprint"] = "other"
        self._refingerprint(receipt, "fingerprint")
        with self.assertRaises(gate.CounterfactualScoreGateError):
            gate.validate_receipt(receipt, lock=self.lock)

    def test_stand_downs_remain_visible(self):
        self.lock["status"] = wall.LOCK_READY_SD
        self.lock["stand_down_days"] = ["20260315"]
        self._refingerprint(self.lock, "lock_fingerprint")
        receipt, *_ = self.build()
        self.assertEqual(receipt["status"], gate.READY_SD)
        self.assertEqual(receipt["stand_down_days"], ["20260315"])

    def test_inputs_are_immutable(self):
        before = copy.deepcopy((self.lock, self.blind, self.refined, self.actual))
        self.build()
        self.assertEqual(before, (self.lock, self.blind, self.refined, self.actual))

    def test_deterministic_output(self):
        self.assertEqual(self.build(), self.build())

    def test_cli_never_opens_actual_when_forecast_hash_fails(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            lock_path = root / "lock.json"
            blind_path = root / "blind.json"
            refined_path = root / "refined.json"
            missing_actual = root / "actual-must-not-open.json"
            lock = copy.deepcopy(self.lock)
            lock["blind_forecast_sha256"] = "wrong"
            self._refingerprint(lock, "lock_fingerprint")
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            blind_path.write_bytes(self.blind_bytes)
            refined_path.write_bytes(self.refined_bytes)
            argv = [
                "ng_g15_counterfactual_score_gate.py",
                "--lock", str(lock_path),
                "--blind", str(blind_path),
                "--refined", str(refined_path),
                "--actual", str(missing_actual),
                "--receipt-out", str(root / "receipt.json"),
                "--blind-score-out", str(root / "blind-score.json"),
                "--refined-score-out", str(root / "refined-score.json"),
                "--comparison-out", str(root / "comparison.json"),
            ]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(gate.CounterfactualScoreGateError) as raised:
                    gate.main()
            self.assertNotIsInstance(raised.exception.__cause__, FileNotFoundError)
            self.assertFalse(missing_actual.exists())

    def test_authority_contract(self):
        receipt, *_ = self.build()
        self.assertFalse(receipt["random_shuffle_used"])
        self.assertTrue(receipt["blind_forecast_immutable"])
        self.assertFalse(receipt["may_update_ng_brain"])
        self.assertFalse(receipt["execution_authority"])
        self.assertEqual(receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(receipt["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(receipt["options_lane_started"])

    @staticmethod
    def _refingerprint(value, field):
        value[field] = gate._fp({key: item for key, item in value.items() if key != field})


if __name__ == "__main__":
    unittest.main()
