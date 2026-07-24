from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v9 as arm
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v9 as compiler
import ng_historical_refinement_executor_v9 as executor_v11
import ng_historical_refinement_executor_v10 as executor
import ng_historical_refinement_preflight_v10 as preflight
import ng_historical_refinement_readiness_v13 as readiness


class ReadinessV13ExecutionChainTests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _compiled(self) -> tuple[dict, dict, dict[str, list[str]]]:
        root = self._root()
        slice_path = root / "slice.json"
        inspection_path = root / "inspection.json"
        slice_path.write_text("{}\n", encoding="utf-8")
        inspection_path.write_text("{}\n", encoding="utf-8")
        with mock.patch.object(
            compiler.v8.v7.v6.fingerprinting,
            "validate_inputs",
            return_value=(
                {"slice_bundle_fingerprint": "slice-fingerprint"},
                {"plan_fingerprint": "inspection-fingerprint"},
            ),
        ):
            plan, receipt = compiler.build_compiled_plan(
                artifact_dir=root / "artifacts",
                working_directory=root / "work",
                slice_bundle_path=slice_path,
                inspection_plan_path=inspection_path,
            )
        return (
            plan,
            receipt,
            compiler._commands(root / "artifacts", slice_path, inspection_path),
        )

    def test_executor_uses_exact_readiness_v13_stage_contract(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        self.assertEqual(
            [row["key"] for row in plan["stages"]],
            [spec.key for spec in readiness.STAGES],
        )

    def test_executor_rejects_readiness_v11_plan_without_exact_curve_and_lock(self) -> None:
        root = self._root()
        old_plan = executor_v11.build_plan(root / "artifacts", root / "work")
        with self.assertRaises(Exception):
            executor.validate_plan(old_plan)

    def test_executor_exposes_exact_curve_lock_and_publication_entrypoints(self) -> None:
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS[
                compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE
            ],
            ("python", "ng_g16_exact_counterfactual_curve_authorization.py"),
        )
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS[compiler.G16_EXACT_CURVE_LOCK_STAGE],
            (
                "python",
                "ng_g16_exact_counterfactual_publication_gate.py",
                "lock",
            ),
        )
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS[compiler.G16_EXACT_PUBLICATION_STAGE],
            (
                "python",
                "ng_g16_exact_counterfactual_publication_gate.py",
                "complete",
            ),
        )

    def test_compiler_binds_exact_curve_before_lock_and_publication(self) -> None:
        plan, receipt, _ = self._compiled()
        keys = [row["key"] for row in plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertEqual(receipt["readiness_contract"], readiness.SCHEMA)
        self.assertLess(
            keys.index("g16_counterfactual_curve_authorization"),
            keys.index(compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE),
        )
        self.assertLess(
            keys.index(compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE),
            keys.index(compiler.G16_EXACT_CURVE_LOCK_STAGE),
        )
        self.assertLess(
            keys.index(compiler.G16_EXACT_CURVE_LOCK_STAGE),
            keys.index(compiler.G16_EXACT_PUBLICATION_STAGE),
        )

    def test_compiler_uses_exact_v13_lock_and_publication_artifacts(self) -> None:
        specs = {spec.key: spec for spec in readiness.STAGES}
        lock = specs[compiler.G16_EXACT_CURVE_LOCK_STAGE]
        publication = specs[compiler.G16_EXACT_PUBLICATION_STAGE]
        self.assertEqual(lock.filename, "g16_exact_counterfactual_curve_lock.json")
        self.assertEqual(lock.schema, "ng_g16_exact_counterfactual_curve_lock.v1")
        self.assertTrue(lock.pre_outcome)
        self.assertEqual(
            publication.filename,
            "g16_exact_counterfactual_publication_completion.json",
        )
        self.assertEqual(
            publication.schema,
            "ng_g16_exact_counterfactual_publication_completion.v1",
        )
        self.assertFalse(publication.pre_outcome)

    def test_compiler_keeps_exact_final_stages_disabled(self) -> None:
        plan, receipt, _ = self._compiled()
        rows = {row["key"]: row for row in plan["stages"]}
        for key in (
            compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
            compiler.G16_EXACT_CURVE_LOCK_STAGE,
            compiler.G16_EXACT_PUBLICATION_STAGE,
        ):
            self.assertFalse(rows[key]["enabled"])
        self.assertFalse(
            rows[compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE][
                "requires_fixed_outcomes"
            ]
        )
        self.assertFalse(
            rows[compiler.G16_EXACT_CURVE_LOCK_STAGE]["requires_fixed_outcomes"]
        )
        self.assertTrue(
            rows[compiler.G16_EXACT_PUBLICATION_STAGE]["requires_fixed_outcomes"]
        )
        self.assertTrue(receipt["legacy_g16_lock_publication_route_rejected"])

    def test_compiler_rejects_removed_exact_curve_stage(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(plan)
        changed["stages"] = [
            row
            for row in changed["stages"]
            if row["key"] != compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE
        ]
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(Exception):
            compiler.validate_receipt(receipt, plan=changed, commands=commands)

    def test_compiler_rejects_refingerprinted_legacy_route(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(receipt)
        changed["legacy_g16_lock_publication_route_rejected"] = False
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV9Error):
            compiler.validate_receipt(changed, plan=plan, commands=commands)

    def test_arm_enables_only_six_corpus_stages(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
        for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertEqual(arm_receipt["stage_order_prefix"], list(arm.ARMED_STAGES))

    def test_arm_keeps_exact_curve_lock_and_publication_disabled(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in (
            arm.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
            arm.G16_EXACT_CURVE_LOCK_STAGE,
            arm.G16_EXACT_PUBLICATION_STAGE,
        ):
            self.assertFalse(rows[key]["enabled"])
        self.assertTrue(
            arm_receipt[
                "g16_exact_counterfactual_curve_authorization_required_before_lock"
            ]
        )
        self.assertTrue(arm_receipt["g16_exact_curve_lock_required_before_scoring"])
        self.assertTrue(arm_receipt["g16_exact_publication_required_after_scoring"])

    def test_arm_rejects_refingerprinted_exact_lock_activation(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(armed)
        row = next(
            row
            for row in changed["stages"]
            if row["key"] == arm.G16_EXACT_CURVE_LOCK_STAGE
        )
        row["enabled"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(Exception):
            arm.validate_arm_receipt(
                arm_receipt,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=changed,
            )

    def test_arm_is_deterministic(self) -> None:
        plan, receipt, _ = self._compiled()
        self.assertEqual(
            arm.build_armed_plan(plan, receipt),
            arm.build_armed_plan(plan, receipt),
        )

    def test_preflight_binds_executor_and_readiness_v13(self) -> None:
        self.assertEqual(
            preflight.EXECUTOR_CONTRACT,
            "ng_historical_refinement_executor_v10",
        )
        self.assertEqual(preflight.READINESS_CONTRACT, readiness.SCHEMA)
        self.assertEqual(
            preflight.STAGE_ORDER,
            [spec.key for spec in readiness.STAGES],
        )

    def test_exact_curve_lock_and_publication_cross_fixed_outcome_once(self) -> None:
        rows = {row["key"]: row for row in preflight.STAGE_CONTRACT}
        for key in (
            "g16_exact_counterfactual_causal_authorization",
            "g16_prepared_curve_authorization",
            "g16_counterfactual_curve_authorization",
            compiler.G16_EXACT_COUNTERFACTUAL_CURVE_STAGE,
            compiler.G16_EXACT_CURVE_LOCK_STAGE,
        ):
            self.assertTrue(rows[key]["pre_outcome"])
        self.assertFalse(rows[compiler.G16_EXACT_PUBLICATION_STAGE]["pre_outcome"])

    def test_permanent_authority_and_historical_first_contract(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        self.assertEqual(plan["outcome_paths"], [])
        for value in (receipt, arm_receipt):
            self.assertFalse(value["actual_outcomes_used"])
            self.assertFalse(value["paid_live_data_assumed"])
            self.assertFalse(value["random_shuffle_used"])
            self.assertTrue(value["one_signal_authority_preserved"])
            self.assertTrue(value["blind_forecasts_immutable"])
            self.assertFalse(value["may_update_ng_brain"])
            self.assertFalse(value["execution_authority"])
            self.assertEqual(value["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(value["brokerage_contract"], "tastytrade_not_ibkr")
            self.assertFalse(value["options_lane_started"])
        self.assertEqual(
            arm_receipt["armed_plan_fingerprint"], armed["fingerprint"]
        )


if __name__ == "__main__":
    unittest.main()
