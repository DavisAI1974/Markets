from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v12 as arm
import ng_corpus_executor_plan_compiler_v12 as compiler
import ng_historical_refinement_executor_v13 as executor
import ng_historical_refinement_readiness_v16 as readiness


class DualInspectionReadinessV16Tests(unittest.TestCase):
    def _commands(self) -> dict[str, list[str]]:
        return compiler._commands(
            artifact_dir=Path("renders/ng_refine_s95"),
            inventory_receipt_path=Path(
                "renders/ng_refine_s95/ng_corpus_inventory_plan_compiler.json"
            ),
            broad_plan_path=Path(
                "renders/ng_refine_s95/ng_corpus_inspection_plan.json"
            ),
            slice_bundle_path=Path(
                "renders/ng_refine_s95/ng_target_day_slice_bundle.json"
            ),
            target_plan_path=Path(
                "renders/ng_refine_s95/ng_target_day_inspection_plan.json"
            ),
        )

    def _minimal_plan(self, *, compiled: bool = True) -> dict:
        commands = self._commands()
        rows = []
        for spec in readiness.STAGES:
            index = (
                compiler.CONFIGURED_STAGES.index(spec.key)
                if spec.key in compiler.CONFIGURED_STAGES
                else None
            )
            rows.append(
                {
                    "key": spec.key,
                    "enabled": bool(index == 0) if compiled else index is not None,
                    "requires_fixed_outcomes": not spec.pre_outcome,
                    "argv": list(commands.get(spec.key) or []),
                }
            )
        return {"stages": rows}

    @staticmethod
    def _joined(argv: list[str]) -> str:
        return " ".join(argv)

    def test_readiness_inserts_target_slice_inspection_before_basis(self) -> None:
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(
            keys.index("corpus_coverage"),
            keys.index("corpus_definition_byte_binding"),
        )
        self.assertLess(
            keys.index("corpus_definition_byte_binding"),
            keys.index("target_slice_coverage"),
        )
        self.assertLess(
            keys.index("target_slice_coverage"),
            keys.index("basis_inventory_regeneration"),
        )
        self.assertLess(
            keys.index("basis_inventory_regeneration"),
            keys.index("broad_corpus_scope"),
        )

    def test_target_slice_stage_contract_is_canonical(self) -> None:
        spec = next(
            spec for spec in readiness.STAGES if spec.key == "target_slice_coverage"
        )
        self.assertEqual(spec.filename, "ng_target_slice_inspection_receipt.json")
        self.assertEqual(spec.schema, "ng_corpus_inspection_receipt.v1")
        self.assertEqual(spec.fingerprint_field, "receipt_fingerprint")
        self.assertTrue(spec.pre_outcome)
        self.assertEqual(spec.ready_statuses, frozenset({"INSPECTION_COMPLETE"}))

    def test_readiness_selftest(self) -> None:
        self.assertEqual(readiness.selftest(), 0)

    def test_executor_uses_readiness_v16(self) -> None:
        with executor._v16_context():
            self.assertIs(executor.legacy_executor.readiness, readiness)
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS["target_slice_coverage"],
            ("python", "ng_corpus_inspection.py", "inspect"),
        )

    def test_compiler_prefix_contains_both_inspection_lanes(self) -> None:
        expected = (
            "corpus_coverage",
            "corpus_definition_byte_binding",
            "target_slice_coverage",
            "basis_inventory_regeneration",
            "replay_catalog_export",
            "broad_corpus_scope",
            "broad_corpus_exact_overlap",
            "broad_corpus_exact_partition",
        )
        self.assertEqual(compiler.CONFIGURED_STAGES, expected)
        self.assertEqual(list(expected), [spec.key for spec in readiness.STAGES][:8])

    def test_compiler_routes_artifacts_to_distinct_receipts(self) -> None:
        commands = self._commands()
        broad = self._joined(commands["corpus_coverage"])
        binding = self._joined(commands["corpus_definition_byte_binding"])
        target = self._joined(commands["target_slice_coverage"])
        basis = self._joined(commands["basis_inventory_regeneration"])
        replay = self._joined(commands["replay_catalog_export"])
        scope = self._joined(commands["broad_corpus_scope"])
        self.assertIn("ng_corpus_inspection_receipt.json", broad)
        self.assertIn("ng_corpus_inspection_receipt.json", binding)
        self.assertNotIn("ng_target_slice_inspection_receipt.json", binding)
        self.assertIn("ng_target_slice_inspection_receipt.json", target)
        self.assertIn("ng_target_slice_inspection_receipt.json", basis)
        self.assertNotIn("ng_corpus_inspection_receipt.json", basis)
        self.assertIn("ng_target_slice_catalog.json", replay)
        self.assertIn("ng_target_slice_coverage_audit.json", replay)
        self.assertIn("ng_corpus_inspection_receipt.json", scope)
        self.assertNotIn("ng_target_slice_inspection_receipt.json", scope)

    def test_compiler_accepts_exact_compiled_boundary(self) -> None:
        plan = self._minimal_plan(compiled=True)
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            rows = compiler._validate_plan(plan, self._commands(), compiled=True)
        self.assertIn("target_slice_coverage", rows)

    def test_compiler_rejects_missing_target_slice_stage(self) -> None:
        plan = self._minimal_plan(compiled=True)
        plan["stages"] = [
            row for row in plan["stages"] if row["key"] != "target_slice_coverage"
        ]
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV12Error):
                compiler._validate_plan(plan, self._commands(), compiled=True)

    def test_compiler_rejects_premature_target_activation(self) -> None:
        plan = self._minimal_plan(compiled=True)
        for row in plan["stages"]:
            if row["key"] == "target_slice_coverage":
                row["enabled"] = True
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV12Error):
                compiler._validate_plan(plan, self._commands(), compiled=True)

    def test_arm_enables_only_dual_inspection_corpus_prefix(self) -> None:
        self.assertEqual(arm.ARMED_STAGES, compiler.CONFIGURED_STAGES)
        plan = self._minimal_plan(compiled=False)
        rows = {row["key"]: row for row in plan["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
        for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
            self.assertFalse(rows[spec.key]["enabled"])

    def test_target_slice_linkage_is_bound_to_basis(self) -> None:
        values = readiness._linked_fixture_chain()
        target = values["target_slice_coverage"]
        basis = values["basis_inventory_regeneration"]
        self.assertEqual(
            target["receipt_fingerprint"],
            basis["inspection_receipt_fingerprint"],
        )
        self.assertEqual(
            target["plan_fingerprint"],
            basis["inspection_plan_fingerprint"],
        )
        self.assertEqual(
            target["catalog_fingerprint"],
            basis["coverage_catalog_fingerprint"],
        )
        self.assertEqual(
            target["audit_fingerprint"],
            basis["coverage_audit_fingerprint"],
        )

    def test_permanent_authority_wall(self) -> None:
        target = readiness._linked_fixture_chain()["target_slice_coverage"]
        for field in (
            "actual_outcomes_used",
            "paid_live_data_assumed",
            "random_shuffle_used",
            "may_change_blind_forecast",
            "may_change_posterior",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertFalse(target[field])
        self.assertTrue(target["one_signal_authority_preserved"])
        self.assertTrue(target["blind_forecasts_immutable"])
        self.assertEqual(target["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(target["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(
            any("option" in key.lower() for key in executor.SUGGESTED_ENTRYPOINTS)
        )


if __name__ == "__main__":
    unittest.main()
