import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_corpus_basis_gate import (  # noqa: E402
    CANONICAL_DATES,
    EXPECTED,
    CorpusBasisError,
    _fixture_rows,
    evaluate_manifest,
    validate_report,
)


class G15CorpusBasisGateTests(unittest.TestCase):
    def test_exact_specific_leg_l1_and_mbo_are_ready(self):
        report = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=False))
        self.assertEqual(report["status"], "MATCHED_L1_MBO_READY")
        self.assertTrue(report["mbo_specific_leg_ready"])
        self.assertTrue(report["matched_l1_mbo_ready"])
        self.assertEqual(report["l1_wrong_basis_days"], [])
        validate_report(report)

    def test_wrong_pre_roll_continuation_l1_is_truthfully_blocked(self):
        report = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=True))
        self.assertEqual(report["status"], "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED")
        self.assertTrue(report["mbo_specific_leg_ready"])
        self.assertFalse(report["matched_l1_mbo_ready"])
        self.assertEqual(
            report["l1_wrong_basis_days"],
            [day for day in CANONICAL_DATES if day <= "20260319"],
        )

    def test_readable_wrong_leg_is_not_matching_l1(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[0]["l1_instrument_id"] = [996]
        rows[0]["l1_basis_correct"] = True
        report = evaluate_manifest(rows)
        self.assertIn("20260313", report["l1_wrong_basis_days"])
        self.assertFalse(report["matched_l1_mbo_ready"])

    def test_false_basis_flag_blocks_even_when_id_matches(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[1]["l1_basis_correct"] = False
        report = evaluate_manifest(rows)
        self.assertIn("20260315", report["l1_wrong_basis_days"])
        self.assertFalse(report["matched_l1_mbo_ready"])

    def test_wrong_mbo_contract_blocks_specific_leg_replay(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[1]["instrument_id"] = 996
        rows[1]["raw_symbol"] = "NGK26"
        rows[1]["mbo_basis_correct"] = False
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["mbo_specific_leg_ready"])
        self.assertIn("20260315", report["mbo_blocked_days"])

    def test_missing_canonical_day_blocks(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)[:-1]
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("missing G15 inventory dates" in error for error in report["errors"]))

    def test_duplicate_day_blocks(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows.append(copy.deepcopy(rows[0]))
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("duplicate G15 inventory date" in error for error in report["errors"]))

    def test_backward_event_time_blocks_mbo(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[2]["first_event_utc"] = "2026-03-16T23:00:00+00:00"
        rows[2]["last_event_utc"] = "2026-03-16T00:00:00+00:00"
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("20260316", report["mbo_blocked_days"])

    def test_queue_stand_down_does_not_invent_failure_of_trade_flow(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[3]["queue_usable"] = False
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "MATCHED_L1_MBO_READY")
        self.assertIn("20260317", report["queue_stand_down_days"])
        day = next(row for row in report["day_reports"] if row["date"] == "20260317")
        self.assertTrue(day["mbo_specific_leg_ready"])
        self.assertFalse(day["queue_usable"])

    def test_flow_unusable_blocks_specific_leg_mbo_readiness(self):
        rows = _fixture_rows(wrong_pre_roll_l1=False)
        rows[3]["flow_usable"] = False
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("20260317", report["mbo_blocked_days"])

    def test_report_tampering_is_rejected(self):
        report = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=False))
        report["matched_l1_mbo_ready"] = False
        with self.assertRaises(CorpusBasisError):
            validate_report(report)

    def test_authority_is_permanently_disabled(self):
        report = evaluate_manifest(_fixture_rows(wrong_pre_roll_l1=False))
        self.assertFalse(report["actual_outcomes_used"])
        self.assertFalse(report["may_relabel_wrong_leg_l1"])
        self.assertFalse(report["may_update_ng_brain"])
        self.assertFalse(report["execution_authority"])

    def test_inputs_are_not_mutated(self):
        rows = _fixture_rows(wrong_pre_roll_l1=True)
        before = copy.deepcopy(rows)
        evaluate_manifest(rows)
        self.assertEqual(rows, before)

    def test_contract_map_is_exact_at_the_seam(self):
        self.assertEqual(EXPECTED["20260319"], {"contract": "NGJ26", "instrument_id": 1008})
        self.assertEqual(EXPECTED["20260320"], {"contract": "NGK26", "instrument_id": 996})


if __name__ == "__main__":
    unittest.main()
