from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_historical_refinement_executor_v3 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v3 as preflight
import ng_historical_refinement_readiness_v5 as readiness


class HistoricalRefinementPreflightV3Tests(unittest.TestCase):
    def _plan(self) -> dict:
        root = Path(tempfile.mkdtemp())
        return executor.build_plan(root / "artifacts", root / "work")

    def _base(self, plan: dict, *, stage: str = "broad_corpus_scope") -> dict:
        value = {
            "schema": legacy.SCHEMA,
            "status": "PREFLIGHT_PASSED",
            "plan_fingerprint": plan["fingerprint"],
            "executor_result": {"status": "CONFIGURATION_REQUIRED", "stage": stage},
            "pre_alignment_gate": {"status": "ALIGNED"},
            "post_alignment_gate": {"status": "ALIGNED"},
            "blockers": [],
            "stand_downs": [],
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
        value["fingerprint"] = legacy._fingerprint(value)
        return value

    def test_stage_contract_requires_broad_scope_before_g15(self) -> None:
        self.assertEqual(preflight.READINESS_CONTRACT, "ng_historical_refinement_readiness.v5")
        self.assertEqual(preflight.EXECUTOR_CONTRACT, "ng_historical_refinement_executor_v3")
        self.assertLess(
            preflight.STAGE_ORDER.index("broad_corpus_scope"),
            preflight.STAGE_ORDER.index("g15_exact_replay"),
        )
        broad = next(row for row in preflight.STAGE_CONTRACT if row["key"] == "broad_corpus_scope")
        self.assertTrue(broad["pre_outcome"])

    def test_finalize_embeds_exact_v5_plan(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
        self.assertEqual(result["execution_plan_snapshot"], plan)
        self.assertTrue(result["execution_plan_v5_validated"])
        self.assertTrue(result["broad_corpus_scope_required"])
        self.assertTrue(result["lock_first_g15_scoring_required"])
        self.assertTrue(result["counterfactual_g16_lineage_required"])

    def test_v4_plan_is_rejected(self) -> None:
        plan = self._plan()
        plan["stages"] = [row for row in plan["stages"] if row["key"] != "broad_corpus_scope"]
        plan.pop("fingerprint")
        plan["fingerprint"] = executor.legacy_executor._fingerprint(plan)
        with self.assertRaises(Exception):
            executor.validate_plan(plan)

    def test_refingerprinted_broad_requirement_removal_is_rejected(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
            result["broad_corpus_scope_required"] = False
            result.pop("fingerprint")
            result["fingerprint"] = legacy._fingerprint(result)
            with self.assertRaises(preflight.HistoricalRefinementPreflightV3Error):
                preflight.validate_receipt(result)

    def test_stage_contract_substitution_is_rejected(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
            result["readiness_stage_contract"] = copy.deepcopy(result["readiness_stage_contract"])
            result["readiness_stage_contract"].pop(3)
            result.pop("fingerprint")
            result["fingerprint"] = legacy._fingerprint(result)
            with self.assertRaises(preflight.HistoricalRefinementPreflightV3Error):
                preflight.validate_receipt(result)

    def test_unknown_executor_stage_is_rejected(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
            result["executor_result"]["stage"] = "options_implementation"
            result.pop("fingerprint")
            result["fingerprint"] = legacy._fingerprint(result)
            with self.assertRaises(preflight.HistoricalRefinementPreflightV3Error):
                preflight.validate_receipt(result)

    def test_plan_snapshot_substitution_is_rejected(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
            result["execution_plan_snapshot"] = copy.deepcopy(plan)
            result["execution_plan_snapshot"]["stages"][3]["requires_fixed_outcomes"] = True
            result.pop("fingerprint")
            result["fingerprint"] = legacy._fingerprint(result)
            with self.assertRaises(Exception):
                preflight.validate_receipt(result)

    def test_receipt_is_deterministic(self) -> None:
        plan = self._plan()
        base = self._base(plan)
        with mock.patch.object(legacy, "validate_receipt", return_value=None):
            first = preflight._finalize(plan, base)
            second = preflight._finalize(plan, base)
        self.assertEqual(first, second)

    def test_permanent_contract_metadata(self) -> None:
        self.assertEqual(preflight.READINESS_CONTRACT, readiness.SCHEMA)
        self.assertIn("g15_counterfactual_scoring_lock", preflight.STAGE_ORDER)
        self.assertIn("g16_counterfactual_curve_lock", preflight.STAGE_ORDER)
        self.assertNotIn("g16_prepared_curve_lock", preflight.STAGE_ORDER)
        self.assertNotIn("g16_prepared_publication", preflight.STAGE_ORDER)


if __name__ == "__main__":
    unittest.main()
