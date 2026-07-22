import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_corpus_basis_gate import (  # noqa: E402
    CANONICAL_DATES,
    G16CorpusBasisError,
    _fixture_rows,
    evaluate_manifest,
    expected_inventory_template,
    validate_report,
)


class G16CorpusBasisGateTests(unittest.TestCase):
    def test_unknown_template_never_claims_remote_presence(self):
        template = expected_inventory_template(publisher_id=1)
        self.assertFalse(template["remote_inventory_verified"])
        self.assertFalse(template["paid_live_data_assumed"])
        self.assertEqual([row["status"] for row in template["rows"]], ["UNKNOWN"] * len(CANONICAL_DATES))

    def test_exact_ngk26_block_is_ready(self):
        report = evaluate_manifest(_fixture_rows())
        validate_report(report)
        self.assertEqual(report["status"], "MATCHED_L1_MBO_READY")
        self.assertTrue(report["matched_l1_mbo_ready"])
        self.assertEqual(len(report["day_reports"]), len(CANONICAL_DATES))

    def test_wrong_l1_contract_is_blocked_without_relabeling(self):
        day = CANONICAL_DATES[0]
        report = evaluate_manifest(_fixture_rows(wrong_l1_day=day))
        self.assertEqual(report["status"], "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED")
        self.assertEqual(report["l1_wrong_basis_days"], [day])
        self.assertFalse(report["may_relabel_wrong_leg_l1"])

    def test_nonoverlapping_event_ranges_are_blocked(self):
        day = CANONICAL_DATES[-1]
        report = evaluate_manifest(_fixture_rows(no_overlap_day=day))
        self.assertEqual(report["event_overlap_blocked_days"], [day])
        self.assertFalse(report["matched_l1_mbo_ready"])

    def test_missing_day_is_structurally_blocked(self):
        rows = _fixture_rows()
        rows.pop()
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("missing G16 inventory dates" in value for value in report["errors"]))

    def test_duplicate_day_is_structurally_blocked(self):
        rows = _fixture_rows()
        rows.append(copy.deepcopy(rows[0]))
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("duplicate G16 inventory date" in value for value in report["errors"]))

    def test_wrong_mbo_instrument_blocks_specific_leg(self):
        rows = _fixture_rows()
        rows[0]["instrument_id"] = 1008
        rows[0]["raw_symbol"] = "NGJ26"
        rows[0]["mbo_basis_correct"] = False
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["mbo_blocked_days"], [CANONICAL_DATES[0]])

    def test_definition_period_must_contain_both_lanes(self):
        rows = _fixture_rows()
        rows[1]["l1_definition_end_s"] = rows[1]["l1_first_event_utc"] - 1
        report = evaluate_manifest(rows)
        self.assertIn(CANONICAL_DATES[1], report["definition_blocked_days"])
        self.assertIn(CANONICAL_DATES[1], report["l1_blocked_days"])

    def test_queue_stand_down_is_visible_but_not_false_absence(self):
        rows = _fixture_rows()
        rows[2]["queue_usable"] = False
        report = evaluate_manifest(rows)
        self.assertEqual(report["status"], "MATCHED_L1_MBO_READY")
        self.assertEqual(report["queue_stand_down_days"], [CANONICAL_DATES[2]])
        day = report["day_reports"][2]
        self.assertTrue(day["matched_l1_mbo_ready"])
        self.assertFalse(day["queue_usable"])

    def test_publisher_is_required(self):
        rows = _fixture_rows()
        rows[3]["publisher_id"] = None
        report = evaluate_manifest(rows)
        day = report["day_reports"][3]
        self.assertIn("publisher_id is missing", day["errors"])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn(CANONICAL_DATES[3], report["mbo_blocked_days"])
        self.assertIn(CANONICAL_DATES[3], report["l1_blocked_days"])

    def test_input_is_not_mutated(self):
        rows = _fixture_rows()
        original = copy.deepcopy(rows)
        evaluate_manifest(rows)
        self.assertEqual(rows, original)

    def test_report_tampering_is_rejected(self):
        report = evaluate_manifest(_fixture_rows())
        report["matched_l1_mbo_ready"] = False
        with self.assertRaises(G16CorpusBasisError):
            validate_report(report)

    def test_authority_is_permanently_disabled(self):
        report = evaluate_manifest(_fixture_rows())
        self.assertFalse(report["actual_outcomes_used"])
        self.assertFalse(report["paid_live_data_assumed"])
        self.assertFalse(report["may_change_g16_blind_prior"])
        self.assertFalse(report["may_update_ng_brain"])
        self.assertFalse(report["execution_authority"])

    def test_mapping_input_rows_and_entries_are_supported(self):
        rows = _fixture_rows()
        first = evaluate_manifest({"rows": rows})
        second = evaluate_manifest({"entries": rows})
        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_invalid_input_shape_is_rejected(self):
        with self.assertRaises(G16CorpusBasisError):
            evaluate_manifest({"unexpected": []})


if __name__ == "__main__":
    unittest.main()
