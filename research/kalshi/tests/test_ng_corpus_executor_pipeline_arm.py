from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_corpus_executor_pipeline_arm as arm
import ng_corpus_executor_plan_compiler as compiler
import ng_historical_refinement_executor_v2 as executor
import ng_historical_refinement_readiness_v4 as readiness


class CorpusExecutorPipelineArmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.work = self.root / "research" / "kalshi"
        self.artifacts.mkdir(parents=True)
        self.work.mkdir(parents=True)
        self.plan, self.receipt, self.commands = self._compiled_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _compiled_fixture(self):
        plan = executor.build_plan(self.artifacts, self.work)
        commands = {
            "corpus_coverage": [
                "python",
                "ng_corpus_inspection.py",
                "inspect",
                "--plan",
                str(self.artifacts / "inspection-plan.json"),
                "--catalog-out",
                str(self.artifacts / "ng_corpus_catalog.json"),
                "--audit-out",
                str(self.artifacts / "ng_corpus_coverage_audit.json"),
                "--receipt-out",
                str(self.artifacts / "ng_corpus_inspection_receipt.json"),
            ],
            "basis_inventory_regeneration": [
                "python",
                "ng_corpus_basis_inventory_regeneration.py",
                "--slice-bundle",
                str(self.artifacts / "slice-bundle.json"),
                "--inspection-receipt",
                str(self.artifacts / "ng_corpus_inspection_receipt.json"),
                "--g15-out",
                str(self.artifacts / "g15_mbo_l1_manifest.json"),
                "--g16-out",
                str(self.artifacts / "g16_mbo_l1_inventory.json"),
                "--bundle-out",
                str(self.artifacts / "ng_corpus_basis_inventory_regeneration.json"),
            ],
            "replay_catalog_export": [
                "python",
                "ng_corpus_replay_catalog_export.py",
                "--catalog",
                str(self.artifacts / "ng_corpus_catalog.json"),
                "--audit",
                str(self.artifacts / "ng_corpus_coverage_audit.json"),
                "--g15-inventory",
                str(self.artifacts / "g15_mbo_l1_manifest.json"),
                "--g16-inventory",
                str(self.artifacts / "g16_mbo_l1_inventory.json"),
                "--g15-out",
                str(self.artifacts / "g15_exact_replay_catalog.json"),
                "--g16-out",
                str(self.artifacts / "g16_exact_replay_catalog.json"),
                "--bundle-out",
                str(self.artifacts / "ng_exact_replay_catalog_export.json"),
            ],
        }
        plan = executor.configure_stage(plan, "corpus_coverage", commands["corpus_coverage"], enabled=True)
        plan = executor.configure_stage(
            plan,
            "basis_inventory_regeneration",
            commands["basis_inventory_regeneration"],
            enabled=False,
        )
        plan = executor.configure_stage(
            plan,
            "replay_catalog_export",
            commands["replay_catalog_export"],
            enabled=False,
        )
        receipt = {
            "schema": compiler.SCHEMA,
            "status": "CORPUS_EXECUTOR_PLAN_COMPILED",
            "slice_bundle_fingerprint": "fixture-slice",
            "inspection_plan_fingerprint": "fixture-inspection",
            "execution_plan_fingerprint": plan["fingerprint"],
            "configured_stages": list(commands),
            "enabled_stage": "corpus_coverage",
            "commands_fingerprint": compiler._fp(commands),
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": "RUN_BRANCH_GUARDED_CORPUS_INSPECTION",
        }
        receipt["fingerprint"] = compiler._fp(receipt)
        compiler.validate_receipt(receipt, plan=plan, commands=commands)
        return plan, receipt, commands

    def _build(self):
        return arm.build_armed_plan(self.plan, self.receipt)

    def test_arms_all_three_pre_outcome_corpus_stages(self):
        plan, receipt = self._build()
        rows = {row["key"]: row for row in plan["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
        self.assertEqual(receipt["armed_stages"], list(arm.ARMED_STAGES))

    def test_keeps_every_downstream_stage_disabled(self):
        plan, receipt = self._build()
        rows = {row["key"]: row for row in plan["stages"]}
        for spec in readiness.STAGES[len(arm.ARMED_STAGES):]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertFalse(receipt["downstream_stages_enabled"])

    def test_uses_one_stable_plan_and_ledger_contract(self):
        plan, receipt = self._build()
        executor.validate_plan(plan)
        self.assertTrue(receipt["single_stable_plan_for_all_corpus_stages"])
        self.assertTrue(receipt["single_stable_ledger_supported"])
        self.assertEqual(receipt["armed_plan_fingerprint"], plan["fingerprint"])
        self.assertEqual(
            receipt["selection_rule"],
            "GUARDED_EXECUTOR_RUNS_FIRST_BLOCKING_READINESS_STAGE_ONLY",
        )

    def test_keeps_broad_scope_verification_explicit_before_g15(self):
        _, receipt = self._build()
        self.assertTrue(receipt["broad_corpus_verification_required_before_g15_replay"])
        self.assertEqual(receipt["required_broad_scope"]["l1_dense_trades"], "ONE_YEAR")
        self.assertEqual(receipt["required_broad_scope"]["mbo"], "SPRING_SUMMER")
        self.assertEqual(
            receipt["after_replay_catalog_export"],
            "VERIFY_BROAD_CORPUS_SCOPE_BEFORE_CONFIGURING_G15_REPLAY",
        )

    def test_never_references_outcomes(self):
        plan, receipt = self._build()
        self.assertEqual(plan["outcome_paths"], [])
        self.assertFalse(receipt["actual_outcomes_used"])
        self.assertFalse(receipt["paid_live_data_assumed"])

    def test_build_does_not_mutate_compiled_inputs(self):
        plan_before = copy.deepcopy(self.plan)
        receipt_before = copy.deepcopy(self.receipt)
        self._build()
        self.assertEqual(self.plan, plan_before)
        self.assertEqual(self.receipt, receipt_before)

    def test_rejects_compiler_receipt_command_substitution(self):
        changed = copy.deepcopy(self.receipt)
        changed["commands_fingerprint"] = "0" * 64
        changed.pop("fingerprint")
        changed["fingerprint"] = compiler._fp(changed)
        with self.assertRaises(arm.CorpusExecutorPipelineArmError):
            arm.build_armed_plan(self.plan, changed)

    def test_rejects_compiled_plan_with_downstream_stage_enabled(self):
        changed_plan = executor.configure_stage(
            self.plan,
            "g15_exact_replay",
            ["python", "ng_g15_exact_replay_completion.py"],
            enabled=True,
        )
        changed_receipt = copy.deepcopy(self.receipt)
        changed_receipt["execution_plan_fingerprint"] = changed_plan["fingerprint"]
        changed_receipt.pop("fingerprint")
        changed_receipt["fingerprint"] = compiler._fp(changed_receipt)
        with self.assertRaises(arm.CorpusExecutorPipelineArmError):
            arm.build_armed_plan(changed_plan, changed_receipt)

    def test_rejects_refingerprinted_arm_authority_escalation(self):
        plan, receipt = self._build()
        changed = copy.deepcopy(receipt)
        changed["options_lane_started"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = arm._fp(changed)
        with self.assertRaises(arm.CorpusExecutorPipelineArmError):
            arm.validate_arm_receipt(
                changed,
                compiled_plan=self.plan,
                compiler_receipt=self.receipt,
                armed_plan=plan,
            )

    def test_rejects_armed_plan_command_change(self):
        plan, receipt = self._build()
        changed = executor.configure_stage(
            plan,
            "replay_catalog_export",
            ["python", "wrong_exporter.py"],
            enabled=True,
        )
        with self.assertRaises(arm.CorpusExecutorPipelineArmError):
            arm.validate_arm_receipt(
                receipt,
                compiled_plan=self.plan,
                compiler_receipt=self.receipt,
                armed_plan=changed,
            )

    def test_build_is_deterministic(self):
        first_plan, first_receipt = self._build()
        second_plan, second_receipt = self._build()
        self.assertEqual(first_plan, second_plan)
        self.assertEqual(first_receipt, second_receipt)
        self.assertFalse(first_receipt["random_shuffle_used"])
        self.assertTrue(first_receipt["blind_forecasts_immutable"])
        self.assertFalse(first_receipt["may_update_ng_brain"])
        self.assertEqual(first_receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(first_receipt["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(first_receipt["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
