from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_readiness_v8 as readiness


class HistoricalRefinementReadinessV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def write_chain(self, root: Path):
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(root / spec.filename, values[spec.key])
        return values

    def test_stage_order_places_window_authorization_before_refinement(self):
        order = [spec.key for spec in readiness.STAGES]
        self.assertLess(order.index("broad_corpus_exact_partition"), order.index("g15_exact_replay"))
        self.assertLess(order.index("g15_exact_replay"), order.index("g15_exact_replay_window_authorization"))
        self.assertLess(order.index("g15_exact_replay_window_authorization"), order.index("g15_exact_refinement"))

    def test_complete_chain_reports_v8_completion(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            self.assertEqual(report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V8")
            self.assertTrue(report["g15_replay_windows_authorized"])

    def test_missing_window_authorization_blocks_refinement(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_chain(root)
            (root / "g15_exact_replay_window_authorization.json").unlink()
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            self.assertEqual(report["first_blocking_stage"], "g15_exact_replay_window_authorization")
            refinement = next(row for row in report["stages"] if row["key"] == "g15_exact_refinement")
            self.assertEqual(refinement["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_replay_completion_link_substitution_is_invalid(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = self.write_chain(root)
            window = copy.deepcopy(values["g15_exact_replay_window_authorization"])
            window["exact_replay_completion_fingerprint"] = "replacement"
            window.pop("fingerprint", None)
            window["fingerprint"] = readiness._fingerprint(window)
            readiness._atomic_json(root / "g15_exact_replay_window_authorization.json", window)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            row = next(row for row in report["stages"] if row["key"] == "g15_exact_replay_window_authorization")
            self.assertEqual(row["effective_status"], "INVALID")

    def test_overlap_link_substitution_is_invalid(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = self.write_chain(root)
            window = copy.deepcopy(values["g15_exact_replay_window_authorization"])
            window["broad_exact_overlap_fingerprint"] = "replacement"
            window.pop("fingerprint", None)
            window["fingerprint"] = readiness._fingerprint(window)
            readiness._atomic_json(root / "g15_exact_replay_window_authorization.json", window)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            row = next(row for row in report["stages"] if row["key"] == "g15_exact_replay_window_authorization")
            self.assertEqual(row["effective_status"], "INVALID")

    def test_window_stage_is_pre_outcome(self):
        spec = next(spec for spec in readiness.STAGES if spec.key == "g15_exact_replay_window_authorization")
        self.assertTrue(spec.pre_outcome)
        self.assertIn("all_replay_state_spans_inside_exact_common_windows", spec.required_fields)

    def test_deterministic_report(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_chain(root)
            first = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            second = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            self.assertEqual(first, second)

    def test_authority_controls_remain_fixed(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            self.assertFalse(report["random_shuffle_used"])
            self.assertFalse(report["may_update_ng_brain"])
            self.assertFalse(report["execution_authority"])
            self.assertFalse(report["options_lane_started"])
            self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(report["brokerage_contract"], "tastytrade_not_ibkr")


if __name__ == "__main__":
    unittest.main()
