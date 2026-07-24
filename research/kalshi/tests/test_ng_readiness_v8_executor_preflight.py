from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_historical_refinement_executor_v5 as executor_v5
import ng_historical_refinement_executor_v6 as executor
import ng_historical_refinement_preflight as legacy_preflight
import ng_historical_refinement_preflight_v6 as preflight
import ng_historical_refinement_readiness_v8 as readiness


class ReadinessV8ExecutorPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plan(self) -> dict:
        return executor.build_plan(self.root / "artifacts", self.root)

    def base_receipt(self, plan: dict) -> dict:
        value = {
            "schema": legacy_preflight.SCHEMA,
            "status": "PREFLIGHT_PASSED",
            "plan_fingerprint": plan["fingerprint"],
            "executor_result": {
                "status": "DRY_RUN",
                "stage": "corpus_coverage",
            },
            "blockers": [],
            "stand_downs": [],
        }
        value["fingerprint"] = legacy_preflight._fingerprint(value)
        return value

    def finalize(self, plan: dict) -> dict:
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            return preflight._finalize(plan, self.base_receipt(plan))

    def test_executor_uses_exact_readiness_v8_order(self) -> None:
        plan = self.plan()
        keys = [row["key"] for row in plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertLess(keys.index("g15_exact_replay"), keys.index("g15_exact_replay_window_authorization"))
        self.assertLess(keys.index("g15_exact_replay_window_authorization"), keys.index("g15_exact_refinement"))

    def test_executor_exposes_exact_window_entrypoint(self) -> None:
        plan = self.plan()
        row = next(
            row
            for row in plan["stages"]
            if row["key"] == "g15_exact_replay_window_authorization"
        )
        self.assertEqual(
            row["suggested_entrypoint"],
            ["python", "ng_g15_exact_replay_window_authorization.py"],
        )
        self.assertFalse(row["requires_fixed_outcomes"])
        self.assertFalse(row["enabled"])

    def test_executor_rejects_readiness_v7_plan(self) -> None:
        plan = executor_v5.build_plan(self.root / "artifacts", self.root)
        with self.assertRaises(Exception):
            executor.validate_plan(plan)

    def test_preflight_receipt_binds_v8_contract(self) -> None:
        receipt = self.finalize(self.plan())
        self.assertEqual(receipt["readiness_contract"], readiness.SCHEMA)
        self.assertEqual(
            receipt["executor_contract"],
            "ng_historical_refinement_executor_v6",
        )
        self.assertTrue(receipt["execution_plan_v8_validated"])
        self.assertTrue(receipt["g15_exact_replay_window_authorization_required"])
        self.assertTrue(receipt["g15_refinement_blocked_until_replay_window_authorized"])

    def test_preflight_rejects_refingerprinted_window_bypass(self) -> None:
        receipt = self.finalize(self.plan())
        receipt["g15_refinement_blocked_until_replay_window_authorized"] = False
        unsigned = {key: value for key, value in receipt.items() if key != "fingerprint"}
        receipt["fingerprint"] = legacy_preflight._fingerprint(unsigned)
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            with self.assertRaises(preflight.HistoricalRefinementPreflightV6Error):
                preflight.validate_receipt(receipt)

    def test_preflight_rejects_stage_contract_substitution(self) -> None:
        receipt = self.finalize(self.plan())
        receipt["readiness_stage_contract"] = [
            row
            for row in receipt["readiness_stage_contract"]
            if row["key"] != "g15_exact_replay_window_authorization"
        ]
        receipt["readiness_stage_contract_fingerprint"] = legacy_preflight._fingerprint(
            receipt["readiness_stage_contract"]
        )
        unsigned = {key: value for key, value in receipt.items() if key != "fingerprint"}
        receipt["fingerprint"] = legacy_preflight._fingerprint(unsigned)
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            with self.assertRaises(preflight.HistoricalRefinementPreflightV6Error):
                preflight.validate_receipt(receipt)

    def test_replay_window_and_refinement_remain_pre_outcome(self) -> None:
        receipt = self.finalize(self.plan())
        rows = {
            row["key"]: row
            for row in receipt["execution_plan_snapshot"]["stages"]
        }
        for key in (
            "g15_exact_replay",
            "g15_exact_replay_window_authorization",
            "g15_exact_refinement",
        ):
            self.assertFalse(rows[key]["requires_fixed_outcomes"])

    def test_executor_rejects_random_shuffle_escalation(self) -> None:
        plan = self.plan()
        plan["random_shuffle_used"] = True
        unsigned = {key: value for key, value in plan.items() if key != "fingerprint"}
        plan["fingerprint"] = legacy_preflight._fingerprint(unsigned)
        with self.assertRaises(Exception):
            executor.validate_plan(plan)

    def test_plan_is_deterministic(self) -> None:
        self.assertEqual(self.plan(), self.plan())

    def test_permanent_authority_controls(self) -> None:
        plan = self.plan()
        self.assertFalse(plan["random_shuffle_used"])
        self.assertTrue(plan["one_signal_authority_preserved"])
        self.assertTrue(plan["blind_forecasts_immutable"])
        self.assertFalse(plan["may_update_ng_brain"])
        self.assertFalse(plan["execution_authority"])
        self.assertEqual(plan["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(plan["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(plan["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
