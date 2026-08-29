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
