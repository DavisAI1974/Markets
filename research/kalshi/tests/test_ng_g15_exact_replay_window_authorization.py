from __future__ import annotations

import copy
import unittest

import ng_g15_exact_replay_window_authorization as gate


class G15ReplayWindowAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_overlap = gate.overlap.validate_gate
        self.original_completion = gate.replay_completion.validate_completion
        gate.overlap.validate_gate = lambda value: value
        gate.replay_completion.validate_completion = lambda value, **kwargs: None
        self.overlap_gate, self.completion = gate._fixture_sources()

    def tearDown(self) -> None:
        gate.overlap.validate_gate = self.original_overlap
        gate.replay_completion.validate_completion = self.original_completion

    def build(self):
        return gate.build_authorization(self.overlap_gate, self.completion)

    def test_ready_exact_window_authorization(self):
        result = self.build()
        self.assertEqual(result["status"], gate.READY_STATUS)
        self.assertTrue(result["all_replay_state_spans_inside_exact_common_windows"])
        self.assertEqual(result["blocked_days"], [])
        self.assertEqual([row["date"] for row in result["day_authorizations"]], list(gate.G15_DATES))

    def test_fragmented_common_window_blocks(self):
        first = self.overlap_gate["day_reports"][0]
        first["merged_overlap_intervals"] = [
            {"start_s": 1000.0, "end_s": 1300.0, "duration_s": 300.0},
            {"start_s": 1400.0, "end_s": 1900.0, "duration_s": 500.0},
        ]
        result = self.build()
        self.assertEqual(result["status"], gate.BLOCKED_STATUS)
        self.assertIn("COMMON_EVENT_WINDOW_NOT_SINGLE_CONTIGUOUS_INTERVAL", result["day_authorizations"][0]["blockers"])

    def test_state_span_outside_window_blocks(self):
        self.completion["days"][0]["last_event_s"] = 2500.0
        result = self.build()
        self.assertEqual(result["status"], gate.BLOCKED_STATUS)
        self.assertIn("REPLAY_STATE_SPAN_OUTSIDE_EXACT_COMMON_WINDOW", result["day_authorizations"][0]["blockers"])

    def test_contract_identity_mismatch_blocks(self):
        self.overlap_gate["day_reports"][0]["selected_identity"]["instrument_id"] = 999
        result = self.build()
        self.assertIn("BROAD_OVERLAP_CONTRACT_IDENTITY_MISMATCH", result["day_authorizations"][0]["blockers"])

    def test_missing_g15_day_blocks(self):
        self.overlap_gate["day_reports"] = self.overlap_gate["day_reports"][1:]
        result = self.build()
        self.assertIn(gate.G15_DATES[0], result["blocked_days"])
        self.assertIn("MISSING_BROAD_OVERLAP_DAY", result["day_authorizations"][0]["blockers"])

    def test_state_fingerprint_count_mismatch_blocks(self):
        self.completion["days"][0]["state_fingerprints"] = ["only-one"]
        result = self.build()
        self.assertIn("REPLAY_STATE_FINGERPRINT_COUNT_MISMATCH", result["day_authorizations"][0]["blockers"])

    def test_visible_replay_stand_down_is_preserved(self):
        self.completion["status"] = gate.replay_completion.READY_WITH_STAND_DOWNS
        self.completion["days"][2]["stand_down_reasons"] = {"collector_skipped_records": 1}
        result = self.build()
        self.assertEqual(result["status"], gate.READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], [gate.G15_DATES[2]])

    def test_sources_are_not_mutated(self):
        before = copy.deepcopy((self.overlap_gate, self.completion))
        self.build()
        self.assertEqual((self.overlap_gate, self.completion), before)

    def test_deterministic_output(self):
        self.assertEqual(self.build(), self.build())

    def test_refingerprinted_nested_tampering_fails(self):
        result = self.build()
        result["day_authorizations"][0]["common_event_window"]["end_s"] += 1.0
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.G15ReplayWindowAuthorizationError):
            gate.validate_authorization(result)

    def test_authority_escalation_fails_even_when_refingerprinted(self):
        result = self.build()
        result["options_lane_started"] = True
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.G15ReplayWindowAuthorizationError):
            gate.validate_authorization(result)

    def test_brokerage_and_cme_controls_remain_fixed(self):
        result = self.build()
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["random_shuffle_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])


if __name__ == "__main__":
    unittest.main()
