import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_g16_counterfactual_lineage_gate as mod  # noqa: E402


class CounterfactualLineageGateTests(unittest.TestCase):
    def setUp(self):
        self.fx = mod._fixture()

    def args(self, **overrides):
        values = {
            "counterfactual_gate": self.fx["counterfactual_gate"],
            "g15_publication": self.fx["publication"],
            "g16_plan": self.fx["g16_plan"],
            "replay": self.fx["replay"],
            "anchor": self.fx["anchor"],
            "refine_stream": self.fx["refine_stream"],
            "attribution": self.fx["attribution"],
            "audit": self.fx["audit"],
            "comparison": self.fx["comparison"],
            "g16_blind_forecast": self.fx["g16_blind_forecast"],
            "g16_blind_safe_state": self.fx["g16_blind_safe_state"],
        }
        values.update(overrides)
        return values

    def build(self, **overrides):
        return mod.build_lineage(**self.args(**overrides))

    @staticmethod
    def refingerprint(value, field="fingerprint"):
        value.pop(field, None)
        value[field] = mod._fingerprint(value)

    def test_exact_counterfactual_lineage_is_bound(self):
        result = self.build()
        self.assertEqual(result["status"], mod.READY)
        self.assertEqual(
            result["counterfactual_lesson_gate_fingerprint"],
            self.fx["counterfactual_gate"]["fingerprint"],
        )
        self.assertGreater(result["candidate_count"], 0)

    def test_sources_are_immutable(self):
        before = copy.deepcopy(tuple(self.args().values()))
        self.build()
        self.assertEqual(before, tuple(self.args().values()))

    def test_legacy_publication_adjudication_is_rejected(self):
        publication = copy.deepcopy(self.fx["publication"])
        publication["lesson_adjudication_fingerprint"] = "legacy-adjudication"
        self.refingerprint(publication, "completion_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g15_publication=publication)

    def test_publication_registry_substitution_is_rejected(self):
        publication = copy.deepcopy(self.fx["publication"])
        publication["g16_shadow_registry"]["registry_fingerprint"] = "other"
        self.refingerprint(publication, "completion_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g15_publication=publication)

    def test_plan_adjudication_substitution_is_rejected(self):
        plan = copy.deepcopy(self.fx["g16_plan"])
        plan["lesson_adjudication_fingerprint"] = "other"
        self.refingerprint(plan, "plan_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_plan=plan)

    def test_plan_registry_substitution_is_rejected(self):
        plan = copy.deepcopy(self.fx["g16_plan"])
        plan["lesson_registry_fingerprint"] = "other"
        self.refingerprint(plan, "plan_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_plan=plan)

    def test_publication_candidate_set_substitution_is_rejected(self):
        publication = copy.deepcopy(self.fx["publication"])
        publication["g16_shadow_registry"]["candidate_ids"] = ["legacy-candidate"]
        publication["g16_shadow_registry"]["candidate_count"] = 1
        self.refingerprint(publication, "completion_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g15_publication=publication)

    def test_counterfactual_gate_refingerprinted_tampering_is_rejected(self):
        gate = copy.deepcopy(self.fx["counterfactual_gate"])
        gate["source"]["adjudication_fingerprint"] = "other"
        self.refingerprint(gate)
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(counterfactual_gate=gate)

    def test_counterfactual_comparison_substitution_is_rejected(self):
        gate = copy.deepcopy(self.fx["counterfactual_gate"])
        gate["source"]["comparison_fingerprint"] = "other"
        self.refingerprint(gate)
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(counterfactual_gate=gate)

    def test_g16_blind_forecast_substitution_is_rejected(self):
        forecast = copy.deepcopy(self.fx["g16_blind_forecast"])
        forecast["days"][0]["guess_curve"][0][1] += 1
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_blind_forecast=forecast)

    def test_g16_blind_safe_state_substitution_is_rejected(self):
        state = copy.deepcopy(self.fx["g16_blind_safe_state"])
        state["artifact_fingerprint"] = "other"
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_blind_safe_state=state)

    def test_plan_candidate_evidence_substitution_is_rejected(self):
        plan = copy.deepcopy(self.fx["g16_plan"])
        for row in plan["days"].values():
            row["candidate_evidence_fingerprints"] = {
                identifier: "other" for identifier in plan["candidate_ids"]
            }
            self.refingerprint(row, "day_plan_fingerprint")
        self.refingerprint(plan, "plan_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_plan=plan)

    def test_publication_stand_downs_remain_visible(self):
        publication = copy.deepcopy(self.fx["publication"])
        publication["status"] = "EXACT_G15_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
        publication["stand_down_days"] = ["20260315"]
        self.refingerprint(publication, "completion_fingerprint")
        result = self.build(g15_publication=publication)
        self.assertEqual(result["status"], mod.READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], ["20260315"])

    def test_g16_outcome_escalation_is_rejected(self):
        plan = copy.deepcopy(self.fx["g16_plan"])
        plan["actual_g16_outcomes_used"] = True
        self.refingerprint(plan, "plan_fingerprint")
        with self.assertRaises(mod.CounterfactualLineageError):
            self.build(g16_plan=plan)

    def test_result_authority_escalation_is_rejected(self):
        result = self.build()
        result["execution_authority"] = True
        self.refingerprint(result)
        with self.assertRaises(mod.CounterfactualLineageError):
            mod.validate_lineage(result, **self.args())

    def test_permanent_controls_remain_locked(self):
        result = self.build()
        self.assertFalse(result["actual_g16_outcomes_used"])
        self.assertFalse(result["g16_scoring_authorized"])
        self.assertFalse(result["random_shuffle_used"])
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecasts_immutable"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])

    def test_output_is_deterministic(self):
        self.assertEqual(self.build(), self.build())


if __name__ == "__main__":
    unittest.main()
