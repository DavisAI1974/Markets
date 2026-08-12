import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
KALSHI = HERE.parent
sys.path.insert(0, str(KALSHI))

import frankie_progress_lock_s122 as lock


class FrankieProgressLockS122Test(unittest.TestCase):
    def test_current_measurement_is_1914_truth(self):
        doc = lock.load_lock()
        self.assertEqual(doc["measurement"]["served"], 1914)
        self.assertEqual(doc["measurement"]["decision_state_blocks"], 44)
        self.assertEqual(doc["measurement"]["served_unread"], 1222)
        self.assertEqual(doc["measurement"]["status"], "CURRENT_ACCEPTED_MEASUREMENT")

    def test_unread_is_not_frankie_inaccessibility(self):
        doc = lock.load_lock()
        self.assertTrue(doc["rules"]["unread_does_not_mean_unavailable_to_frankie"])
        self.assertIn("regardless of ng_brain reader count", doc["rules"]["frankie_access_rule"])

    def test_known_completed_items_cannot_reopen(self):
        for iid in ("A-1", "A-16", "G-5", "G-19", "A-51", "A-52"):
            self.assertEqual(lock.effective_item_state(iid, "OPEN")["state"], "DONE")

    def test_s115_mechanisms_are_not_rebuilt_while_evidence_remains(self):
        for iid in ("A-42", "A-50", "A-59", "A-61", "A-62", "A-65", "A-66", "A-67", "A-68", "A-69"):
            self.assertEqual(
                lock.effective_item_state(iid, "OPEN")["state"],
                "IMPLEMENTED_EVIDENCE_PENDING",
            )

    def test_lock_runs_against_historical_registry(self):
        status = lock.assert_lock()
        self.assertEqual(status["status"], "LOCKED")
        self.assertGreaterEqual(status["fully_done_locked"], 13)
        self.assertGreaterEqual(status["implemented_evidence_pending_locked"], 10)

    def test_future_mask_and_spawn_protection_remain(self):
        doc = lock.load_lock()
        self.assertTrue(doc["rules"]["future_target_curve_masked"])
        self.assertTrue(doc["rules"]["spawn_py_protected"])


if __name__ == "__main__":
    unittest.main()
