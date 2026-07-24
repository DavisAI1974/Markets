from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_g16_exact_counterfactual_causal_authorization as gate
import ng_historical_refinement_readiness_v11 as readiness


class ExactCounterfactualCausalAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exact = {
            "schema": gate.EXACT_SCHEMA,
            "status": gate.EXACT_READY,
            "fingerprint": "exact-auth",
            "exact_partition_gate_fingerprint": "partition",
            "prepared_replay_gate_fingerprint": "prepared-replay",
            "manifest_fingerprint": "manifest",
            "prepared_corpus_fingerprint": "corpus",
            "replay_fingerprint": "replay",
            "blind_prior_fingerprint": "blind-prior",
            "source_binding_fingerprint": "source-binding",
            "window_contract_fingerprint": "window-contract",
            "bound_replay_source_count": 22,
            "all_g16_replay_sources_bound_to_exact_partition": True,
            "all_g16_state_spans_inside_exact_common_windows": True,
            "stand_down_days": [],
        }
        self.causal = {
            "schema": gate.COUNTERFACTUAL_SCHEMA,
            "status": gate.COUNTERFACTUAL_READY,
            "prepared_replay_gate_fingerprint": "prepared-replay",
            "manifest_fingerprint": "manifest",
            "prepared_corpus_fingerprint": "corpus",
            "replay_fingerprint": "replay",
            "blind_prior_fingerprint": "blind-prior",
            "counterfactual_lineage_gate_fingerprint": "lineage",
            "prepared_causal_authorization_fingerprint": "prepared-causal",
            "g16_plan_fingerprint": "plan",
            "authorization_stream_fingerprint": "authorization-stream",
            "posterior_stream_fingerprint": "posterior-stream",
            "g16_blind_forecast_fingerprint": "blind-forecast",
            "g16_blind_safe_state_fingerprint": "blind-state",
            "candidate_ids": ["activity", "onset"],
            "candidate_evidence_fingerprints": {
                "activity": "activity-evidence",
                "onset": "onset-evidence",
            },
            "candidate_ids_observed_in_posterior_attribution": ["activity"],
            "all_stand_down_days": [],
            "next_permitted_stage": gate.COUNTERFACTUAL_NEXT_STAGE,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": False,
            "g16_scoring_authorized": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_g16_blind_prior": False,
            "may_change_g16_blind_forecast": False,
            "may_change_posterior": False,
            "may_select_lessons_from_g16_outcomes": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
        self.causal["fingerprint"] = gate.counterfactual_fingerprint(self.causal)

    def patched(self):
        return mock.patch.object(gate, "validate_exact_authorization")

    def build(self):
        with self.patched() as patched:
            patched.return_value = self.exact
            return gate.build_authorization(self.exact, self.causal)

    def validate(self, value):
        with self.patched() as patched:
            patched.return_value = self.exact
            return gate.validate_authorization(value)

    def refingerprint_causal(self) -> None:
        payload = copy.deepcopy(self.causal)
        payload.pop("fingerprint", None)
        self.causal["fingerprint"] = gate.counterfactual_fingerprint(payload)

    def test_valid_authorization_binds_both_proofs(self):
        result = self.build()
        self.assertEqual(result["status"], gate.STATUS_READY)
        self.assertEqual(
            result["exact_partition_replay_authorization_fingerprint"], "exact-auth"
        )
        self.assertEqual(
            result["counterfactual_causal_authorization_fingerprint"],
            self.causal["fingerprint"],
        )
        self.assertEqual(result["bound_replay_source_count"], 22)
        self.assertEqual(result["candidate_count"], 2)
        self.validate(result)

    def test_replay_fingerprint_substitution_is_rejected(self):
        self.causal["replay_fingerprint"] = "replacement-replay"
        self.refingerprint_causal()
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.build()

    def test_prepared_replay_gate_substitution_is_rejected(self):
        self.causal["prepared_replay_gate_fingerprint"] = "replacement-gate"
        self.refingerprint_causal()
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.build()

    def test_incomplete_candidate_evidence_is_rejected(self):
        self.causal["candidate_evidence_fingerprints"].pop("onset")
        self.refingerprint_causal()
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.build()

    def test_exact_lane_count_is_enforced(self):
        self.exact["bound_replay_source_count"] = 21
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.build()

    def test_stand_down_days_are_unionized(self):
        self.exact["status"] = gate.EXACT_STAND_DOWNS
        self.exact["stand_down_days"] = ["2026-03-20"]
        self.causal["status"] = gate.COUNTERFACTUAL_STAND_DOWNS
        self.causal["all_stand_down_days"] = ["2026-03-23"]
        self.refingerprint_causal()
        result = self.build()
        self.assertEqual(result["status"], gate.STATUS_STAND_DOWNS)
        self.assertEqual(
            result["all_stand_down_days"], ["2026-03-20", "2026-03-23"]
        )

    def test_inputs_are_not_mutated(self):
        before = copy.deepcopy((self.exact, self.causal))
        self.build()
        self.assertEqual((self.exact, self.causal), before)

    def test_refingerprinted_top_level_tampering_is_rejected(self):
        result = self.build()
        result["source_binding_fingerprint"] = "replacement-source-binding"
        payload = copy.deepcopy(result)
        payload.pop("fingerprint")
        result["fingerprint"] = gate._fp(payload)
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.validate(result)

    def test_authority_escalation_is_rejected(self):
        result = self.build()
        result["options_lane_started"] = True
        payload = copy.deepcopy(result)
        payload.pop("fingerprint")
        result["fingerprint"] = gate._fp(payload)
        with self.assertRaises(gate.G16ExactCounterfactualCausalAuthorizationError):
            self.validate(result)

    def test_deterministic_output(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)


class HistoricalReadinessV11Tests(unittest.TestCase):
    def test_exact_causal_stage_precedes_curve(self):
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(
            keys.index("g16_counterfactual_causal_authorization"),
            keys.index("g16_exact_counterfactual_causal_authorization"),
        )
        self.assertLess(
            keys.index("g16_exact_counterfactual_causal_authorization"),
            keys.index("g16_prepared_curve_authorization"),
        )
        row = next(
            spec
            for spec in readiness.STAGES
            if spec.key == "g16_exact_counterfactual_causal_authorization"
        )
        self.assertTrue(row.pre_outcome)

    def test_complete_fixture_reaches_v11_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = readiness._linked_fixture_chain()
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            for spec in readiness.STAGES:
                readiness._atomic_json(root / spec.filename, values[spec.key])
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
            self.assertEqual(
                report["status"],
                "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V11",
            )
            self.assertTrue(
                report["g16_causal_authority_bound_to_exact_replay_bytes"]
            )
            self.assertTrue(
                report["g16_causal_authority_bound_to_exact_event_windows"]
            )

    def test_missing_exact_causal_stage_blocks_curve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = readiness._linked_fixture_chain()
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            for spec in readiness.STAGES:
                if spec.key != "g16_exact_counterfactual_causal_authorization":
                    readiness._atomic_json(root / spec.filename, values[spec.key])
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
            self.assertEqual(
                report["first_blocking_stage"],
                "g16_exact_counterfactual_causal_authorization",
            )
            curve = next(
                row
                for row in report["stages"]
                if row["key"] == "g16_prepared_curve_authorization"
            )
            self.assertEqual(curve["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_link_substitution_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = readiness._linked_fixture_chain()
            values["g16_exact_counterfactual_causal_authorization"][
                "source_binding_fingerprint"
            ] = "replacement"
            replacement = values["g16_exact_counterfactual_causal_authorization"]
            replacement.pop("fingerprint")
            replacement["fingerprint"] = readiness._fingerprint(replacement)
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            for spec in readiness.STAGES:
                readiness._atomic_json(root / spec.filename, values[spec.key])
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
            row = next(
                row
                for row in report["stages"]
                if row["key"] == "g16_exact_counterfactual_causal_authorization"
            )
            self.assertEqual(row["effective_status"], "INVALID")
            self.assertFalse(
                report["g16_causal_authority_bound_to_exact_replay_bytes"]
            )


if __name__ == "__main__":
    unittest.main()
