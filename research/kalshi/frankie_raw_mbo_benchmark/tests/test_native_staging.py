"""The spawn contract: how Frankie is actually called.

On the first run Frankie was never called. The mechanism that calls it is the walk's own:
stage a committed request file at the cutoff, spawn an agent session that reads it, read
back the committed artifact, hard-fail if it is missing or malformed. No API call.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_staging import (
    SPAWN_REQUEST_SCHEMA,
    StagingError,
    load_principal_artifact,
    stage_spawn_request,
)

CUTOFF = {
    "group_index": 2_654_677,
    "recv_ns": 1_633_381_200_237_256_020,
    "first_lawful_availability_ns": 1_633_381_200_237_256_020,
    "session_phase": "POST_CLOSE",
    "continuity_segment": 18_904,
    "source_day": "20211004",
}

EVIDENCE = {
    "result_hash": "a" * 64,
    "artifact_path": "artifacts/a_clean_rt_evidence_20211004.json",
    "completion_status": "EVIDENCE_ONLY",
}


class StageSpawnRequestTest(unittest.TestCase):
    def test_it_writes_a_request_the_coordinator_can_find(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            self.assertTrue(path.exists())
            body = json.loads(path.read_text())
            self.assertEqual(body["schema"], SPAWN_REQUEST_SCHEMA)
            self.assertEqual(body["cutoff"]["session_phase"], "POST_CLOSE")
            self.assertEqual(body["arm"], "A_CLEAN")

    def test_the_path_is_deterministic_from_the_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            second = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            self.assertEqual(first, second)

    def test_it_names_the_evidence_the_findings_must_be_derived_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            body = json.loads(path.read_text())
            self.assertEqual(body["evidence"]["result_hash"], "a" * 64)

    def test_it_refuses_a_cutoff_missing_its_lawful_availability(self):
        broken = {k: v for k, v in CUTOFF.items() if k != "first_lawful_availability_ns"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    broken, out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE",
                    evidence=EVIDENCE,
                )

    def test_it_refuses_an_unknown_arm_or_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    CUTOFF, out_dir=Path(tmp), arm="A_SIDEWAYS",
                    role="REAL_TIME_FRANKIE", evidence=EVIDENCE,
                )
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    CUTOFF, out_dir=Path(tmp), arm="A_CLEAN",
                    role="SPECIALIST_C", evidence=EVIDENCE,
                )


class LoadPrincipalArtifactTest(unittest.TestCase):
    """The coordinator side. A missing or malformed artifact is a HARD failure."""

    GOOD = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
        "principal": "gpt-5.6-sol",
        "arm": "A_CLEAN",
        "role": "REAL_TIME_FRANKIE",
        "evidence_result_hash": "a" * 64,
        "actual_principal_invocation": True,
        "controller_only": False,
        # F-14: every exact ledger's read status is declared. NOT_READ is the honest
        # default while delivery is unsolved; leaving it out is what the gate refuses.
        "evidence_read": {
            "exact_member_ledger": "NOT_READ",
            "exact_lifecycle_and_runway_ledger": "NOT_READ",
            "legacy_observable_rows": "NOT_READ",
        },
        "findings": [
            {
                "claim": "cancels cluster at the close",
                "support": "group 2654677",
                "falsifier": "a close with no cancel cluster",
                "exemplars": ["2654677"],
            }
        ],
    }

    def _write(self, tmp: str, body) -> Path:
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(body))
        return path

    def test_a_good_artifact_yields_execution_and_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, self.GOOD)
            execution, findings = load_principal_artifact(path, expected_evidence_hash="a" * 64)
            self.assertEqual(execution["principal"], "gpt-5.6-sol")
            self.assertEqual(execution["artifact_path"], str(path))
            self.assertEqual(len(execution["artifact_sha256"]), 64)
            self.assertEqual(len(findings), 1)

    def test_a_missing_artifact_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                load_principal_artifact(Path(tmp) / "absent.json", expected_evidence_hash="a" * 64)

    def test_malformed_json_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "findings.json"
            path.write_text("{not json")
            with self.assertRaises(StagingError):
                load_principal_artifact(path, expected_evidence_hash="a" * 64)

    def test_findings_derived_from_other_evidence_are_refused(self):
        """Findings must cite the evidence they were produced against."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {**self.GOOD, "evidence_result_hash": "b" * 64})
            with self.assertRaises(StagingError):
                load_principal_artifact(path, expected_evidence_hash="a" * 64)

    def test_controller_only_output_is_refused_at_the_door(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {**self.GOOD, "controller_only": True})
            with self.assertRaises(StagingError):
                load_principal_artifact(path, expected_evidence_hash="a" * 64)

    def test_an_artifact_with_no_findings_is_refused(self):
        """A spawn that produced nothing is a failed spawn, not an empty success."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {**self.GOOD, "findings": []})
            with self.assertRaises(StagingError):
                load_principal_artifact(path, expected_evidence_hash="a" * 64)

    def test_the_round_trip_satisfies_the_runner(self):
        """What load_principal_artifact returns must be what the runner accepts."""
        from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_calculation_runner import (
            drive,
            make_run,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, self.GOOD)
            execution, findings = load_principal_artifact(path, expected_evidence_hash="a" * 64)
            run = make_run()
            drive(run)
            run.attach_principal_findings(execution=execution, findings=findings)
            result = run.finalize()
            self.assertEqual(result["completion_status"], "PRINCIPAL_FINDINGS_ATTACHED")
            self.assertEqual(result["verdict"], "ACCEPTED", result["failed_gates"])


if __name__ == "__main__":
    unittest.main()


class DriverStagesRatherThanInvokesTest(unittest.TestCase):
    """The traversal leaves a request behind at a cutoff. It calls nothing."""

    def test_a_cutoff_stages_a_committed_request(self):
        from research.kalshi.frankie_raw_mbo_benchmark.native_staging import SpawnStager
        from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_replay_driver import (
            at,
            make_driver,
            record,
        )

        class Always:
            def should_invoke(self, **_kwargs) -> bool:
                return True

        with tempfile.TemporaryDirectory() as tmp:
            stager = SpawnStager(
                out_dir=Path(tmp), arm="A_CLEAN", role="REAL_TIME_FRANKIE", evidence=EVIDENCE
            )
            driver = make_driver(cadence=Always(), total_mbo_records=1)
            driver.stage_spawn = stager.stage
            driver.consume([record(seq=0, event_ns=at("2021-10-04T18:29:00"), order_id=700)])

            self.assertEqual(len(stager.staged), 1)
            body = json.loads(stager.staged[0].read_text())
            self.assertEqual(body["schema"], SPAWN_REQUEST_SCHEMA)
            self.assertEqual(body["cutoff"]["session_phase"], "SETTLEMENT")
            self.assertIn("No API call", body["invocation_note"])

    def test_the_driver_no_longer_carries_an_on_invoke_callback(self):
        from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_replay_driver import (
            make_driver,
        )
        driver = make_driver()
        self.assertFalse(hasattr(driver, "on_invoke"))
        self.assertTrue(hasattr(driver, "stage_spawn"))


class EvidenceReadDeclarationTest(unittest.TestCase):
    """The non-replacement rule, enforced at the DELIVERY boundary.

    The contract preamble already says, verbatim, "Exact evidence is never discarded or
    replaced by an average." It is honoured in STORAGE - the exact ledgers are written,
    retained, counted and witnessed - and broken in DELIVERY: they stay on the box while the
    principal receives the result JSON. The one guard, `member_rows_written > 0`, proves rows
    were written somewhere and cannot prove anyone read one. Outcome on run 33605852433:
    16,293 averaged rows read, zero member rows read, and every exact-member claim resting
    on counters.

    So the artifact must DECLARE, per exact ledger, whether the principal read it. Not
    reading is allowed and expected while delivery is unsolved; not SAYING is refused,
    because an undeclared read status is what lets an average stand in for the exact.
    """

    GOOD = dict(LoadPrincipalArtifactTest.GOOD)
    GOOD["evidence_read"] = {
        "exact_member_ledger": "NOT_READ",
        "exact_lifecycle_and_runway_ledger": "NOT_READ",
        "legacy_observable_rows": "NOT_READ",
    }

    def _write(self, tmp, body):
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(body))
        return path

    def test_an_artifact_that_declares_read_status_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = load_principal_artifact(
                self._write(tmp, self.GOOD), expected_evidence_hash="a" * 64,
                render_report=False,
            )
        self.assertEqual(execution["evidence_read"]["exact_member_ledger"], "NOT_READ")

    def test_an_artifact_that_does_not_declare_is_refused(self):
        """The firing branch. This is the exact artifact shape run 33605852433 produced."""
        body = dict(self.GOOD)
        body.pop("evidence_read")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError) as caught:
                load_principal_artifact(
                    self._write(tmp, body), expected_evidence_hash="a" * 64,
                    render_report=False,
                )
        self.assertIn("evidence_read", str(caught.exception))

    def test_a_ledger_left_undeclared_is_refused_by_name(self):
        """Declaring two of three is the silent version of declaring none."""
        body = dict(self.GOOD)
        body["evidence_read"] = {"exact_member_ledger": "NOT_READ"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError) as caught:
                load_principal_artifact(
                    self._write(tmp, body), expected_evidence_hash="a" * 64,
                    render_report=False,
                )
        self.assertIn("exact_lifecycle_and_runway_ledger", str(caught.exception))

    def test_an_unknown_status_word_is_refused(self):
        """READ, PARTIAL and NOT_READ are the vocabulary. 'skimmed' is not a fact."""
        body = dict(self.GOOD)
        body["evidence_read"] = dict(self.GOOD["evidence_read"], exact_member_ledger="skimmed")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                load_principal_artifact(
                    self._write(tmp, body), expected_evidence_hash="a" * 64,
                    render_report=False,
                )

    def test_not_read_is_accepted_not_penalised(self):
        """NOT_READ is the honest answer while delivery is unsolved. A gate that only
        accepted READ would push the principal toward claiming reads he did not make."""
        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = load_principal_artifact(
                self._write(tmp, self.GOOD), expected_evidence_hash="a" * 64,
                render_report=False,
            )
        self.assertFalse(execution["principal_read_any_exact_rows"])

    def test_read_on_any_ledger_flips_the_summary_flag(self):
        body = dict(self.GOOD)
        body["evidence_read"] = dict(self.GOOD["evidence_read"], legacy_observable_rows="READ")
        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = load_principal_artifact(
                self._write(tmp, body), expected_evidence_hash="a" * 64,
                render_report=False,
            )
        self.assertTrue(execution["principal_read_any_exact_rows"])
