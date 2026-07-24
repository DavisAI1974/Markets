from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import ng_corpus_executor_plan_compiler as compiler
import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer
import ng_historical_refinement_executor_v2 as executor


class CorpusExecutorPlanCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.work = self.root / "research" / "kalshi"
        self.slices = self.artifacts / "slices"
        self.work.mkdir(parents=True)
        self.slices.mkdir(parents=True)
        self.plan_value, self.bundle = self._fixtures()
        self.plan_path = self.artifacts / "ng_target_day_inspection_plan.json"
        self.bundle_path = self.artifacts / "ng_target_day_slice_bundle.json"
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps(self.plan_value), encoding="utf-8")
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _fixtures(self):
        plan = inspection.plan_template(allowed_roots=[str(self.slices)])
        corpora = {row["lane"]: row for row in plan["corpora"]}
        for day in slicer._target_days():
            identity = slicer._target_identity(day)
            definition = inspection.definition_observation(
                dataset=inspection.DATASET,
                publisher_id=1,
                instrument_id=identity["instrument_id"],
                raw_symbol=identity["raw_symbol"],
                definition_date="2026-03-01",
                definition_start_s=1.0,
                definition_end_s=2_000_000_000.0,
                observed_from="s3://definitions/observed.dbn",
                observed_at="2026-07-24T04:00:00Z",
                source_sha256="a" * 64,
                source_size_bytes=100,
            )
            for lane in ("l1_trades", "mbo"):
                corpora[lane]["sources"].append(
                    {
                        "source_id": f"target:{day}:{lane}",
                        "location": f"s3://history/{day}/{lane}.dbn",
                        "materialized_path": str(self.slices / f"{day}-{lane}.jsonl"),
                        "day": day,
                        "lane": lane,
                        "definition": definition,
                        "inventory_observed_at": "2026-07-24T04:00:00Z",
                    }
                )
        for corpus in plan["corpora"]:
            corpus["expected_days"] = list(slicer._target_days())
            corpus["expected_object_count"] = len(slicer._target_days())
            corpus["inventory_observed_at"] = "2026-07-24T04:00:00Z"
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = inspection._fp(plan)
        inspection._validate_plan(plan)
        pairs = []
        for day in slicer._target_days():
            pairs.append(
                {
                    "target": slicer._target_label(day),
                    "day": day,
                    "status": "MATCHED_L1_MBO_READY",
                    "blockers": [],
                    "event_time_overlap": {"event_start_s": 1.0, "event_end_s": 2.0},
                }
            )
        bundle = {
            "schema": slicer.SCHEMA,
            "status": compiler.READY_STATUS,
            "target_days": list(slicer._target_days()),
            "pairs": pairs,
            "inspection_plan_fingerprint": plan["plan_fingerprint"],
            "inspection_plan": copy.deepcopy(plan),
            "broad_corpus_completeness_asserted": False,
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "may_update_ng_brain": False,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
        bundle["slice_bundle_fingerprint"] = compiler._fp(bundle)
        return plan, bundle

    def _build(self):
        return compiler.build_compiled_plan(
            artifact_dir=self.artifacts,
            working_directory=self.work,
            slice_bundle_path=self.bundle_path,
            inspection_plan_path=self.plan_path,
        )

    def test_compiles_only_corpus_inspection_as_enabled(self):
        plan, receipt = self._build()
        executor.validate_plan(plan)
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertTrue(rows["corpus_coverage"]["enabled"])
        self.assertFalse(rows["basis_inventory_regeneration"]["enabled"])
        self.assertFalse(rows["replay_catalog_export"]["enabled"])
        self.assertEqual(receipt["enabled_stage"], "corpus_coverage")

    def test_exact_outputs_match_readiness_filenames(self):
        plan, _ = self._build()
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertIn(str(self.artifacts / "ng_corpus_coverage_audit.json"), rows["corpus_coverage"]["argv"])
        self.assertIn(str(self.artifacts / "ng_corpus_basis_inventory_regeneration.json"), rows["basis_inventory_regeneration"]["argv"])
        self.assertIn(str(self.artifacts / "ng_exact_replay_catalog_export.json"), rows["replay_catalog_export"]["argv"])

    def test_all_three_commands_are_preconfigured_without_outcomes(self):
        plan, _ = self._build()
        rows = {row["key"]: row for row in plan["stages"]}
        for key in ("corpus_coverage", "basis_inventory_regeneration", "replay_catalog_export"):
            self.assertTrue(rows[key]["argv"])
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
        self.assertEqual(plan["outcome_paths"], [])

    def test_rejects_blocked_exact_pair(self):
        broken = copy.deepcopy(self.bundle)
        broken["pairs"][3]["status"] = "BLOCKED"
        broken["pairs"][3]["blockers"] = ["MBO_MISSING"]
        broken.pop("slice_bundle_fingerprint")
        broken["slice_bundle_fingerprint"] = compiler._fp(broken)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerError):
            compiler.validate_inputs(broken, self.plan_value)

    def test_rejects_inspection_plan_substitution(self):
        changed = copy.deepcopy(self.plan_value)
        changed["corpora"][0]["sources"][0]["day"] = "20260101"
        changed.pop("plan_fingerprint")
        changed["plan_fingerprint"] = inspection._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerError):
            compiler.validate_inputs(self.bundle, changed)

    def test_rejects_authority_escalation_after_refingerprinting(self):
        changed = copy.deepcopy(self.bundle)
        changed["options_lane_started"] = True
        changed.pop("slice_bundle_fingerprint")
        changed["slice_bundle_fingerprint"] = compiler._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerError):
            compiler.validate_inputs(changed, self.plan_value)

    def test_receipt_rejects_command_substitution(self):
        plan, receipt = self._build()
        commands = compiler._argv_paths(self.artifacts, self.bundle_path, self.plan_path)
        commands["corpus_coverage"] = ["python", "wrong.py"]
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerError):
            compiler.validate_receipt(receipt, plan=plan, commands=commands)

    def test_build_is_deterministic(self):
        first_plan, first_receipt = self._build()
        second_plan, second_receipt = self._build()
        self.assertEqual(first_plan, second_plan)
        self.assertEqual(first_receipt, second_receipt)
        self.assertFalse(first_receipt["actual_outcomes_used"])
        self.assertFalse(first_receipt["may_update_ng_brain"])
        self.assertEqual(first_receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(first_receipt["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(first_receipt["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
