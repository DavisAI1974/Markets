from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_executor as executor
import ng_historical_refinement_readiness as readiness


class HistoricalRefinementExecutorTests(unittest.TestCase):
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
            path.write_text(json.dumps({"path": relative}) + "\n", encoding="utf-8")
        self.plan = executor.build_plan(self.artifacts, self.work)
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
        self.ledger = self.root / "ledger.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_stage(self, spec, value=None):
        value = value or readiness._fixture_artifact(spec, sorted(spec.ready_statuses)[0])
        readiness._atomic_json(self.artifacts / spec.filename, value)
        return value

    def configure(self, key, argv=None):
        self.plan = executor.configure_stage(
            self.plan,
            key,
            argv or ["python", "worker.py"],
        )

    def fake_result(self, returncode=0, stdout="ok", stderr=""):
        return subprocess.CompletedProcess(["python", "worker.py"], returncode, stdout, stderr)

    def test_plan_is_fail_closed_and_has_exact_stage_order(self):
        executor.validate_plan(self.plan)
        self.assertEqual(
            [row["key"] for row in self.plan["stages"]],
            [spec.key for spec in readiness.STAGES],
        )
        self.assertTrue(all(not row["enabled"] for row in self.plan["stages"]))
        self.assertFalse(self.plan["random_shuffle_used"])
        self.assertEqual(self.plan["brokerage_contract"], "tastytrade_not_ibkr")

    def test_shell_and_random_shuffle_commands_are_rejected(self):
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.configure_stage(self.plan, "corpus_coverage", ["bash", "-c", "echo hi"])
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.configure_stage(self.plan, "corpus_coverage", ["python", "job.py", "--shuffle"])

    def test_missing_command_returns_configuration_required(self):
        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
        )
        self.assertEqual(result["status"], "CONFIGURATION_REQUIRED")
        self.assertEqual(result["stage"], "corpus_coverage")
        self.assertFalse(self.ledger.exists())

    def test_dry_run_does_not_execute_or_write_ledger(self):
        self.configure("corpus_coverage")
        called = []

        def runner(*args, **kwargs):
            called.append((args, kwargs))
            return self.fake_result()

        result = executor.execute_next(
            self.plan,
            self.ledger,
            dry_run=True,
            validator_overrides=self.overrides,
            command_runner=runner,
        )
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(called, [])
        self.assertFalse(self.ledger.exists())

    def test_successful_stage_advance_runs_without_shell(self):
        self.configure("corpus_coverage")
        observed = {}

        def runner(argv, **kwargs):
            observed.update(kwargs)
            self.write_stage(readiness.STAGES[0])
            return self.fake_result(stdout="advanced")

        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=runner,
        )
        self.assertEqual(result["status"], "ADVANCED")
        self.assertIs(observed["shell"], False)
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        executor.validate_ledger(ledger, self.plan)
        self.assertEqual(ledger["entries"][0]["stage"], "corpus_coverage")

    def test_truthful_zero_exit_stand_down_is_recorded(self):
        self.configure("corpus_coverage")
        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=lambda *args, **kwargs: self.fake_result(),
        )
        self.assertEqual(result["status"], "STOOD_DOWN")
        self.assertEqual(result["target_effective_status"], "MISSING")

    def test_nonzero_command_is_recorded(self):
        self.configure("corpus_coverage")
        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=lambda *args, **kwargs: self.fake_result(7, stderr="failed"),
        )
        self.assertEqual(result["status"], "COMMAND_FAILED")
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(ledger["entries"][0]["returncode"], 7)

    def test_blind_forecast_mutation_is_restored(self):
        self.configure("corpus_coverage")
        blind = self.work / "forecasts/grp15.json"
        before = blind.read_bytes()

        def runner(*args, **kwargs):
            blind.write_text("mutated\n", encoding="utf-8")
            return self.fake_result()

        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=runner,
        )
        self.assertEqual(result["status"], "PROTECTED_MUTATION_RESTORED")
        self.assertEqual(blind.read_bytes(), before)
        self.assertTrue(any(item.startswith("g15_blind_forecast:") for item in result["protected_mutations_restored"]))

    def test_ng_brain_creation_or_mutation_is_restored(self):
        self.configure("corpus_coverage")
        brain = self.work / "knowledge/ng_brain.json"
        before = brain.read_bytes()

        def runner(*args, **kwargs):
            brain.write_text("{}\nchanged", encoding="utf-8")
            return self.fake_result()

        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=runner,
        )
        self.assertEqual(result["status"], "PROTECTED_MUTATION_RESTORED")
        self.assertEqual(brain.read_bytes(), before)

    def test_ready_upstream_artifact_mutation_is_restored(self):
        first = self.write_stage(readiness.STAGES[0])
        original = (self.artifacts / readiness.STAGES[0].filename).read_bytes()
        self.configure("basis_inventory_regeneration")

        def runner(*args, **kwargs):
            path = self.artifacts / readiness.STAGES[0].filename
            path.write_text("{}\n", encoding="utf-8")
            return self.fake_result()

        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=runner,
        )
        self.assertEqual(result["status"], "PROTECTED_MUTATION_RESTORED")
        self.assertEqual((self.artifacts / readiness.STAGES[0].filename).read_bytes(), original)
        self.assertEqual(first["schema"], readiness.STAGES[0].schema)

    def test_fixed_outcome_stage_requires_explicit_runtime_flag(self):
        values = readiness._linked_fixture_chain()
        publication_index = next(i for i, spec in enumerate(readiness.STAGES) if spec.key == "g15_publication")
        for spec in readiness.STAGES[:publication_index]:
            self.write_stage(spec, values[spec.key])
        self.configure("g15_publication")
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.execute_next(
                self.plan,
                self.ledger,
                validator_overrides=self.overrides,
                command_runner=lambda *args, **kwargs: self.fake_result(),
            )

    def test_pre_outcome_stage_cannot_reference_declared_outcome_path(self):
        outcome = self.work / "actual.json"
        outcome.write_text("{}\n", encoding="utf-8")
        plan = copy.deepcopy(self.plan)
        plan.pop("fingerprint")
        plan["outcome_paths"] = ["actual.json"]
        plan["fingerprint"] = executor._fingerprint(plan)
        self.plan = executor.configure_stage(plan, "corpus_coverage", ["python", "job.py", "actual.json"])
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.execute_next(
                self.plan,
                self.ledger,
                validator_overrides=self.overrides,
                command_runner=lambda *args, **kwargs: self.fake_result(),
            )

    def test_complete_chain_is_noop(self):
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            self.write_stage(spec, values[spec.key])
        result = executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
        )
        self.assertEqual(result["status"], "CHAIN_COMPLETE")

    def test_ledger_refingerprint_tampering_is_rejected(self):
        self.configure("corpus_coverage")
        executor.execute_next(
            self.plan,
            self.ledger,
            validator_overrides=self.overrides,
            command_runner=lambda *args, **kwargs: self.fake_result(),
        )
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        ledger["execution_authority"] = True
        ledger.pop("fingerprint")
        ledger["fingerprint"] = executor._fingerprint(ledger)
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.validate_ledger(ledger, self.plan)

    def test_plan_authority_escalation_is_rejected_after_refingerprint(self):
        plan = copy.deepcopy(self.plan)
        plan["options_lane_started"] = True
        plan.pop("fingerprint")
        plan["fingerprint"] = executor._fingerprint(plan)
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            executor.validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
