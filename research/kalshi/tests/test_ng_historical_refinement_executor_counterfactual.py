from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_executor as executor
import ng_historical_refinement_readiness as readiness


class CounterfactualExecutorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.artifacts = self.root / "artifacts"
        self.work.mkdir()
        self.artifacts.mkdir()
        for relative in (
            "forecasts/grp15.json",
            "forecasts/grp16.json",
            "knowledge/ng_brain.json",
        ):
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        self.plan = executor.build_plan(self.artifacts, self.work)
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def tearDown(self):
        self.temp.cleanup()

    def test_executor_plan_uses_counterfactual_v3_stage_order(self):
        executor.validate_plan(self.plan)
        keys = [row["key"] for row in self.plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertIn("g15_counterfactual_attribution", keys)
        self.assertIn("g15_counterfactual_lesson_gate", keys)
        self.assertIn("g15_g16_counterfactual_lineage", keys)
        self.assertEqual(
            keys[-5:],
            [
                "g16_counterfactual_causal_authorization",
                "g16_prepared_curve_authorization",
                "g16_counterfactual_curve_authorization",
                "g16_counterfactual_curve_lock",
                "g16_counterfactual_publication",
            ],
        )
        self.assertNotIn("g16_prepared_curve_lock", keys)
        self.assertNotIn("g16_prepared_publication", keys)

    def test_expected_outputs_follow_v3_filenames(self):
        rows = {row["key"]: row for row in self.plan["stages"]}
        self.assertEqual(
            rows["g16_counterfactual_curve_lock"]["expected_output"],
            "g16_counterfactual_curve_lock.json",
        )
        self.assertEqual(
            rows["g16_counterfactual_publication"]["expected_output"],
            "g16_counterfactual_publication_completion.json",
        )

    def test_only_scored_publication_crosses_g16_fixed_outcome_boundary(self):
        rows = {row["key"]: row for row in self.plan["stages"]}
        self.assertFalse(rows["g16_counterfactual_curve_lock"]["requires_fixed_outcomes"])
        self.assertTrue(rows["g16_counterfactual_publication"]["requires_fixed_outcomes"])
        self.assertFalse(rows["g16_counterfactual_curve_authorization"]["requires_fixed_outcomes"])

    def test_new_counterfactual_stages_can_be_configured(self):
        for key in (
            "g15_counterfactual_attribution",
            "g15_counterfactual_lesson_gate",
            "g15_g16_counterfactual_lineage",
            "g16_counterfactual_causal_authorization",
            "g16_counterfactual_curve_authorization",
            "g16_counterfactual_curve_lock",
            "g16_counterfactual_publication",
        ):
            configured = executor.configure_stage(
                self.plan,
                key,
                ["python", f"{key}.py"],
            )
            executor.validate_plan(configured)
            row = next(item for item in configured["stages"] if item["key"] == key)
            self.assertTrue(row["enabled"])

    def test_refingerprinted_legacy_stage_plan_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan.pop("fingerprint")
        plan["stages"][-2]["key"] = "g16_prepared_curve_lock"
        plan["stages"][-1]["key"] = "g16_prepared_publication"
        plan["fingerprint"] = executor._fingerprint(plan)
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.validate_plan(plan)

    def test_executor_stops_at_missing_counterfactual_attribution(self):
        values = readiness._linked_fixture_chain()
        attribution = next(
            spec for spec in readiness.STAGES
            if spec.key == "g15_counterfactual_attribution"
        )
        for spec in readiness.STAGES[:readiness.STAGES.index(attribution)]:
            readiness._atomic_json(self.artifacts / spec.filename, values[spec.key])
        result = executor.execute_next(
            self.plan,
            self.root / "ledger.json",
            validator_overrides=self.overrides,
        )
        self.assertEqual(result["status"], "CONFIGURATION_REQUIRED")
        self.assertEqual(result["stage"], "g15_counterfactual_attribution")

    def test_complete_v3_chain_is_executor_noop(self):
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(self.artifacts / spec.filename, values[spec.key])
        result = executor.execute_next(
            self.plan,
            self.root / "ledger.json",
            validator_overrides=self.overrides,
        )
        self.assertEqual(result["status"], "CHAIN_COMPLETE")

    def test_plan_authority_contract_remains_permanent(self):
        self.assertFalse(self.plan["random_shuffle_used"])
        self.assertFalse(self.plan["may_update_ng_brain"])
        self.assertFalse(self.plan["execution_authority"])
        self.assertFalse(self.plan["options_lane_started"])
        self.assertTrue(self.plan["blind_forecasts_immutable"])
        self.assertEqual(self.plan["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(self.plan["brokerage_contract"], "tastytrade_not_ibkr")


if __name__ == "__main__":
    unittest.main()
