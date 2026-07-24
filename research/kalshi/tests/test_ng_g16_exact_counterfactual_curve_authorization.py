from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_g16_exact_counterfactual_curve_authorization as gate
import ng_historical_refinement_readiness_v12 as readiness


class ExactCounterfactualCurveAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exact, self.curve, self.context = gate._selftest_inputs()
        self.patch_exact = mock.patch.object(
            gate, "validate_exact_causal_authorization", return_value=self.exact
        )
        self.patch_curve = mock.patch.object(
            gate, "validate_counterfactual_curve_authorization", return_value=None
        )
        self.patch_exact.start()
        self.patch_curve.start()
        self.addCleanup(self.patch_exact.stop)
        self.addCleanup(self.patch_curve.stop)

    def build(self):
        return gate.build_authorization(
            self.exact, self.curve, curve_kwargs=self.context
        )

    def validate(self, value):
        return gate.validate_authorization(
            value,
            exact_causal_authorization=self.exact,
            counterfactual_curve_authorization=self.curve,
            curve_kwargs=self.context,
        )

    def test_valid_authorization_binds_exact_curve_lineage(self):
        result = self.build()
        self.assertEqual(result["status"], gate.STATUS_READY)
        self.assertEqual(
            result["exact_counterfactual_causal_authorization_fingerprint"],
            self.exact["fingerprint"],
        )
        self.assertEqual(
            result["counterfactual_curve_authorization_fingerprint"],
            self.curve["fingerprint"],
        )
        self.assertEqual(result["bound_replay_source_count"], 22)
        self.assertFalse(result["actual_g16_outcomes_used"])

    def test_replay_fingerprint_substitution_fails(self):
        self.curve["replay_fingerprint"] = "replacement"
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_exact_source_binding_must_be_true(self):
        self.exact["all_g16_replay_sources_bound_to_exact_partition"] = False
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_exact_event_window_binding_must_be_true(self):
        self.exact["all_g16_state_spans_inside_exact_common_windows"] = False
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_exactly_twenty_two_replay_lanes_required(self):
        self.exact["bound_replay_source_count"] = 21
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_candidate_evidence_substitution_fails(self):
        self.curve["candidate_evidence_fingerprints"]["candidate-a"] = "replacement"
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_curve_candidate_must_have_exact_authorized_posterior_attribution(self):
        self.curve["candidate_ids_used_by_curve"] = ["candidate-b"]
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.build()

    def test_stand_downs_are_unionized(self):
        self.exact["status"] = gate.EXACT_CAUSAL_STAND_DOWNS
        self.exact["all_stand_down_days"] = ["2026-06-01"]
        self.curve["status"] = gate.CURVE_STAND_DOWNS
        self.curve["stand_down_days"] = ["2026-06-02"]
        result = self.build()
        self.assertEqual(result["status"], gate.STATUS_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], ["2026-06-01", "2026-06-02"])

    def test_sources_are_not_mutated(self):
        before = copy.deepcopy((self.exact, self.curve, self.context))
        self.build()
        self.assertEqual((self.exact, self.curve, self.context), before)

    def test_top_level_tampering_fails_after_refingerprinting(self):
        result = self.build()
        result["options_lane_started"] = True
        result["fingerprint"] = gate._fp(
            {key: value for key, value in result.items() if key != "fingerprint"}
        )
        with self.assertRaises(gate.G16ExactCounterfactualCurveAuthorizationError):
            self.validate(result)

    def test_deterministic_output(self):
        self.assertEqual(self.build(), self.build())

    def test_permanent_authority_wall(self):
        result = self.build()
        for field in (
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "paid_live_data_assumed",
            "random_shuffle_used",
            "may_change_g16_blind_prior",
            "may_change_g16_blind_forecast",
            "may_change_posterior",
            "may_select_lessons_from_g16_outcomes",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertIs(result[field], False)
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecasts_immutable"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")


class ReadinessV12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def write_chain(self, values=None, *, skip=()):
        values = copy.deepcopy(values or readiness._linked_fixture_chain())
        for spec in readiness.STAGES:
            if spec.key in skip:
                continue
            readiness._atomic_json(self.root / spec.filename, values[spec.key])
        return values

    def test_exact_curve_stage_is_between_curve_and_lock(self):
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(
            keys.index("g16_counterfactual_curve_authorization"),
            keys.index("g16_exact_counterfactual_curve_authorization"),
        )
        self.assertLess(
            keys.index("g16_exact_counterfactual_curve_authorization"),
            keys.index("g16_counterfactual_curve_lock"),
        )
        row = next(
            spec
            for spec in readiness.STAGES
            if spec.key == "g16_exact_counterfactual_curve_authorization"
        )
        self.assertTrue(row.pre_outcome)

    def test_complete_chain_reaches_v12_status(self):
        self.write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        self.assertEqual(
            report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V12"
        )
        self.assertTrue(report["g16_curve_authority_bound_to_exact_replay_bytes"])
        self.assertTrue(report["g16_curve_authority_bound_to_exact_event_windows"])
        self.assertTrue(report["g16_curve_authority_bound_to_counterfactual_lessons"])

    def test_missing_exact_curve_blocks_lock(self):
        self.write_chain(skip={"g16_exact_counterfactual_curve_authorization"})
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        self.assertEqual(
            report["first_blocking_stage"],
            "g16_exact_counterfactual_curve_authorization",
        )
        lock = next(
            row
            for row in report["stages"]
            if row["key"] == "g16_counterfactual_curve_lock"
        )
        self.assertEqual(lock["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_refingerprinted_exact_curve_provenance_substitution_fails(self):
        values = readiness._linked_fixture_chain()
        exact_curve = values["g16_exact_counterfactual_curve_authorization"]
        exact_curve["replay_fingerprint"] = "replacement"
        exact_curve["fingerprint"] = readiness._fingerprint(
            {key: value for key, value in exact_curve.items() if key != "fingerprint"}
        )
        self.write_chain(values)
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        row = next(
            row
            for row in report["stages"]
            if row["key"] == "g16_exact_counterfactual_curve_authorization"
        )
        self.assertEqual(row["effective_status"], "INVALID")

    def test_curve_lock_must_reference_exact_curve(self):
        values = readiness._linked_fixture_chain()
        lock = values["g16_counterfactual_curve_lock"]
        lock["exact_counterfactual_curve_authorization_fingerprint"] = "replacement"
        field = next(
            spec.fingerprint_field
            for spec in readiness.STAGES
            if spec.key == "g16_counterfactual_curve_lock"
        )
        lock[field] = readiness._fingerprint(
            {key: value for key, value in lock.items() if key != field}
        )
        self.write_chain(values)
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        row = next(
            row
            for row in report["stages"]
            if row["key"] == "g16_counterfactual_curve_lock"
        )
        self.assertEqual(row["effective_status"], "INVALID")

    def test_v11_schema_cannot_validate_as_v12(self):
        self.write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        report["schema"] = "ng_historical_refinement_readiness.v11"
        report["fingerprint"] = readiness._fingerprint(
            {key: value for key, value in report.items() if key != "fingerprint"}
        )
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_readiness_permanent_authority_wall(self):
        self.write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        for field in (
            "remote_presence_inferred",
            "actual_outcome_paths_loaded",
            "paid_live_data_assumed",
            "random_shuffle_used",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertIs(report[field], False)
        self.assertTrue(report["one_signal_authority_preserved"])
        self.assertTrue(report["blind_forecasts_immutable"])
        self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(report["brokerage_contract"], "tastytrade_not_ibkr")


if __name__ == "__main__":
    unittest.main()
