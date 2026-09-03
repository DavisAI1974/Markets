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
    # D83: the model-evaluation clock is the F_LAST receive of the group at which the
    # principal is staged - an event instant the driver stamps, never a time we choose.
    "clock_model_evaluation_ns": 1_633_381_200_237_256_020,
}

EVIDENCE = {
    "result_hash": "a" * 64,
    "artifact_path": "artifacts/a_memory_rt_evidence_20211004.json",
    "completion_status": "EVIDENCE_ONLY",
}


class StageSpawnRequestTest(unittest.TestCase):
    def test_it_writes_a_request_the_coordinator_can_find(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            self.assertTrue(path.exists())
            body = json.loads(path.read_text())
            self.assertEqual(body["schema"], SPAWN_REQUEST_SCHEMA)
            self.assertEqual(body["cutoff"]["session_phase"], "POST_CLOSE")
            self.assertEqual(body["arm"], "A_MEMORY")

    def test_the_path_is_deterministic_from_the_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            second = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            self.assertEqual(first, second)

    def test_it_names_the_evidence_the_findings_must_be_derived_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = stage_spawn_request(
                CUTOFF, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                evidence=EVIDENCE,
            )
            body = json.loads(path.read_text())
            self.assertEqual(body["evidence"]["result_hash"], "a" * 64)

    def test_it_refuses_a_cutoff_missing_its_lawful_availability(self):
        broken = {k: v for k, v in CUTOFF.items() if k != "first_lawful_availability_ns"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    broken, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                    evidence=EVIDENCE,
                )

    def test_it_refuses_a_cutoff_missing_its_model_evaluation_clock(self):
        """D83, S121 item one: the driver stamps `clock_model_evaluation_ns` (the F_LAST
        receive of the group the principal is staged at) on every cutoff it stages. A request
        without it names no instant at which he was invoked, so it is refused BY NAME."""
        broken = {k: v for k, v in CUTOFF.items() if k != "clock_model_evaluation_ns"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError) as caught:
                stage_spawn_request(
                    broken, out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE",
                    evidence=EVIDENCE,
                )
        self.assertIn("clock_model_evaluation_ns", str(caught.exception))

    def test_it_refuses_an_unknown_arm_or_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    CUTOFF, out_dir=Path(tmp), arm="A_SIDEWAYS",
                    role="REAL_TIME_FRANKIE", evidence=EVIDENCE,
                )
            with self.assertRaises(StagingError):
                stage_spawn_request(
                    CUTOFF, out_dir=Path(tmp), arm="A_MEMORY",
                    role="SPECIALIST_C", evidence=EVIDENCE,
                )


class LoadPrincipalArtifactTest(unittest.TestCase):
    """The coordinator side. A missing or malformed artifact is a HARD failure."""

    GOOD = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
        "principal": "gpt-5.6-sol",
        "arm": "A_MEMORY",
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

    def test_a_written_artifact_with_no_findings_is_an_empty_success(self):
        """The committed artifact proves the spawn ran; no novelty is a valid outcome."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {**self.GOOD, "findings": []})
            execution, findings = load_principal_artifact(path, expected_evidence_hash="a" * 64)
        self.assertEqual(findings, [])
        self.assertEqual(execution["artifact_path"], str(path))

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
                out_dir=Path(tmp), arm="A_MEMORY", role="REAL_TIME_FRANKIE", evidence=EVIDENCE
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


class DeliveredLedgersMustBeReadTest(unittest.TestCase):
    """D81 at the coordinator side: a delivered ledger he did not read is a failed spawn.

    NOT_READ was the honest answer while the ledgers stayed on the box. Once an artifact
    cites a `delivery_receipt_sha256` - which only exists when `fetch_frankie_ledgers`
    verified every exact ledger into the session - NOT_READ on any of them is refused.
    Without the citation the old rule stands, so an artifact from a pre-delivery run still
    validates exactly as before.
    """

    READ_ALL = {name: "READ" for name in (
        "exact_member_ledger", "exact_lifecycle_and_runway_ledger", "legacy_observable_rows",
    )}

    def _body(self, **overrides):
        body = dict(LoadPrincipalArtifactTest.GOOD)
        body["evidence_read"] = dict(self.READ_ALL)
        body["delivery_receipt_sha256"] = "d" * 64
        body["stream_receipt_sha256"] = "5" * 64
        body.update(overrides)
        return body

    def _load(self, tmp, body, **kwargs):
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(body))
        return load_principal_artifact(
            path, expected_evidence_hash="a" * 64, render_report=False, **kwargs
        )

    def test_read_everywhere_with_a_delivery_receipt_loads_and_carries_both_hashes(self):
        # S121 slice 1: a delivered artifact also cites the output bundle it wrote and staging
        # is handed that bundle, so this test now supplies both; the two hashes it always
        # asserted are still carried through.
        with tempfile.TemporaryDirectory() as tmp:
            outputs_dir = Path(tmp) / "outputs"
            receipt = write_bundle(
                build_bundle(
                    delivery_receipt_sha256="d" * 64, knowledge_receipt_sha256="e" * 64,
                ),
                outputs_dir,
            )
            execution, _ = self._load(
                tmp, self._body(outputs_receipt_sha256=receipt["receipt_sha256"]),
                outputs_dir=outputs_dir, knowledge_receipt_sha256="e" * 64,
            )
        self.assertEqual(execution["delivery_receipt_sha256"], "d" * 64)
        self.assertEqual(execution["stream_receipt_sha256"], "5" * 64)
        self.assertTrue(execution["principal_read_any_exact_rows"])

    def test_not_read_on_a_delivered_ledger_is_refused_by_name(self):
        body = self._body(evidence_read=dict(self.READ_ALL, legacy_observable_rows="NOT_READ"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError) as caught:
                self._load(tmp, body)
        self.assertIn("legacy_observable_rows", str(caught.exception))
        self.assertIn("delivered", str(caught.exception))

    def test_without_a_delivery_receipt_the_old_rule_stands(self):
        body = self._body(evidence_read=dict(self.READ_ALL, exact_member_ledger="NOT_READ"))
        body.pop("delivery_receipt_sha256")
        body.pop("stream_receipt_sha256")
        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = self._load(tmp, body)
        self.assertEqual(execution["evidence_read"]["exact_member_ledger"], "NOT_READ")
        self.assertIsNone(execution["delivery_receipt_sha256"])
        self.assertIsNone(execution["stream_receipt_sha256"])

    def test_a_malformed_receipt_hash_is_refused(self):
        for field in ("delivery_receipt_sha256", "stream_receipt_sha256"):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(StagingError) as caught:
                        self._load(tmp, self._body(**{field: "not-a-sha"}))
                self.assertIn(field, str(caught.exception))


# ------------------------------------------------------------------------------------------
# Slice 1 (S121): the staging gate is wired to the output validator.
# ------------------------------------------------------------------------------------------

from research.kalshi.frankie_raw_mbo_benchmark.tests.outputs_bundle_fixture import (  # noqa: E402
    build_bundle,
    write_bundle,
)

DELIVERY = "d" * 64
KNOWLEDGE = "e" * 64
STREAM = "5" * 64


def delivered_artifact(**overrides) -> dict:
    """An artifact from a DELIVERED run on the arm every spawn targets (A_MEMORY, D86).

    Its finding carries what a real one does - `id`, `section`, claim, falsifier, exemplars -
    so the report beside it renders; the renderer refuses a finding it cannot render honestly.
    """
    body = dict(LoadPrincipalArtifactTest.GOOD)
    body["arm"] = "A_MEMORY"
    body["evidence_read"] = {name: "READ" for name in (
        "exact_member_ledger", "exact_lifecycle_and_runway_ledger", "legacy_observable_rows",
    )}
    body["delivery_receipt_sha256"] = DELIVERY
    body["stream_receipt_sha256"] = STREAM
    body["findings"] = [
        {
            "id": "F-01",
            "section": "4.6",
            "claim": "cancels cluster at the close",
            "support": "group 2654677",
            "falsifier": "a close with no cancel cluster",
            "exemplars": ["2654677"],
        }
    ]
    body.update(overrides)
    return body


def write_knowledge_gate_inputs(root: Path) -> dict:
    """Write the three exact files the default knowledge-use adapter validates."""
    from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
        build_knowledge_delivery,
        complete_knowledge_use,
        render_knowledge_block,
        write_knowledge_delivery,
    )

    delivery = build_knowledge_delivery(arm="A_MEMORY", role="REAL_TIME_FRANKIE")
    written = write_knowledge_delivery(delivery, root)
    prompt = root / "FRANKIE_SPAWN_PROMPT.md"
    prompt.write_bytes(
        ("# prompt\n" + render_knowledge_block(delivery.receipt)).encode("utf-8")
    )
    return {
        "delivery": delivery,
        "knowledge_use": complete_knowledge_use(delivery.receipt),
        "receipt": written["receipt"],
        "bundle": written["bundle"],
        "prompt": prompt,
    }


class CanonicalArmTest(unittest.TestCase):
    """One arm, A_MEMORY (D86). Staging re-exports the outputs module's `CANONICAL_ARM` so
    the two cannot drift; A_CLEAN stays in ALLOWED_ARMS as an inert record (D60)."""

    def test_staging_and_outputs_agree_on_the_one_arm(self):
        from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs, native_staging

        self.assertEqual(native_staging.CANONICAL_ARM, "A_MEMORY")
        self.assertIs(native_staging.CANONICAL_ARM, native_principal_outputs.CANONICAL_ARM)
        self.assertIn(native_staging.CANONICAL_ARM, native_staging.ALLOWED_ARMS)
        self.assertIn("A_CLEAN", native_staging.ALLOWED_ARMS)

    def test_the_fixtures_run_on_the_one_arm(self):
        from research.kalshi.frankie_raw_mbo_benchmark.native_staging import CANONICAL_ARM

        self.assertEqual(delivered_artifact()["arm"], CANONICAL_ARM)
        self.assertEqual(LoadPrincipalArtifactTest.GOOD["arm"], CANONICAL_ARM)
        self.assertEqual(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE).arm,
            CANONICAL_ARM,
        )


class OutputsBundleGateTest(unittest.TestCase):
    """The outputs ARE the deliverable of a delivered run, and the gate now asks for them.

    `native_principal_outputs.validate_output_bundle_dir` was complete, tested and had no
    production caller - the S119 shape again: a correct validator nothing ever reached. An
    artifact that cites a delivery receipt was produced with every exact ledger in hand, so it
    must also cite the receipt of the output bundle it wrote, and staging must be handed that
    bundle to validate; the artifact's `outputs_receipt_sha256` must equal what the validator
    computes. An artifact without a delivery receipt keeps the old rule untouched.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
            cls.outputs_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _load(self, body, **kwargs):
        args = dict(
            expected_evidence_hash="a" * 64, render_report=False,
            outputs_dir=self.outputs_dir, knowledge_receipt_sha256=KNOWLEDGE,
        )
        args.update(kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "findings.json"
            path.write_text(json.dumps(body))
            return load_principal_artifact(path, **args)

    def _refused(self, body, needle, **kwargs):
        with self.assertRaises(StagingError) as caught:
            self._load(body, **kwargs)
        self.assertIn(needle, str(caught.exception))
        return caught.exception

    def test_a_delivered_artifact_with_its_validated_bundle_loads_and_carries_the_receipt(self):
        execution, findings = self._load(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"])
        )
        self.assertEqual(execution["outputs_receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertEqual(execution["outputs_receipt"]["schema"], self.receipt["schema"])
        self.assertEqual(execution["outputs_receipt"]["missing_ledger_ids"], [])
        self.assertEqual(execution["outputs_receipt"]["arm"], "A_MEMORY")
        self.assertEqual(execution["delivery_receipt_sha256"], DELIVERY)
        self.assertEqual(len(findings), 1)

    def test_a_delivered_artifact_that_cites_no_outputs_receipt_is_refused_by_name(self):
        """The firing branch for the emitter's CURRENT return shape, which carries no
        `outputs_receipt_sha256`: an artifact following it verbatim is refused here."""
        self._refused(delivered_artifact(), "outputs_receipt_sha256")

    def test_an_outputs_citation_nothing_can_verify_is_refused(self):
        self._refused(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"]),
            "outputs_dir", outputs_dir=None,
        )

    def test_an_outputs_dir_the_artifact_does_not_bind_to_is_refused(self):
        """A bundle handed to staging that the artifact never cites is a bundle from nowhere."""
        body = dict(LoadPrincipalArtifactTest.GOOD)
        self._refused(body, "outputs_receipt_sha256", knowledge_receipt_sha256=None)

    def test_a_bundle_receipt_that_disagrees_with_the_citation_is_refused(self):
        exc = self._refused(delivered_artifact(outputs_receipt_sha256="e" * 64), "e" * 64)
        self.assertIn(self.receipt["receipt_sha256"], str(exc))

    def test_a_malformed_outputs_receipt_sha256_is_refused(self):
        self._refused(delivered_artifact(outputs_receipt_sha256="not-a-sha"), "outputs_receipt_sha256")

    def test_a_bundle_produced_against_another_delivery_is_refused(self):
        """The bundle binds the delivery it was written against; the artifact cites another."""
        self._refused(
            delivered_artifact(
                outputs_receipt_sha256=self.receipt["receipt_sha256"],
                delivery_receipt_sha256="c" * 64,
            ),
            "delivery",
        )

    def test_a_knowledge_receipt_the_verdicts_do_not_cite_is_refused(self):
        self._refused(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"]),
            "knowledge", knowledge_receipt_sha256="f" * 64,
        )

    def test_a_bundle_for_another_arm_is_refused(self):
        """A_CLEAN stays a valid arm (an inert record, D86); it is not THIS artifact's arm."""
        with tempfile.TemporaryDirectory() as other:
            receipt = write_bundle(
                build_bundle(
                    arm="A_CLEAN", delivery_receipt_sha256=DELIVERY,
                    knowledge_receipt_sha256=KNOWLEDGE,
                ),
                Path(other) / "outputs",
            )
            exc = self._refused(
                delivered_artifact(outputs_receipt_sha256=receipt["receipt_sha256"]),
                "arm", outputs_dir=Path(other) / "outputs",
            )
        self.assertIn("A_CLEAN", str(exc))
        self.assertIn("A_MEMORY", str(exc))

    def test_a_ledger_edited_on_disk_is_refused(self):
        """Produced, not asserted: the validator's chain check reaches the gate."""
        with tempfile.TemporaryDirectory() as other:
            root = Path(other) / "outputs"
            receipt = write_bundle(
                build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
                root,
            )
            ledger_path = root / "ledgers" / "contract_section_4.10.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["entries"][-1]["body"]["member_group_indices"] = [9999]
            ledger_path.write_text(json.dumps(ledger))
            self._refused(
                delivered_artifact(outputs_receipt_sha256=receipt["receipt_sha256"]),
                "rewritten", outputs_dir=root,
            )

    def test_the_coordinators_delivery_receipt_must_be_the_one_the_artifact_cites(self):
        self._refused(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"]),
            "delivery_receipt_sha256", delivery_receipt_sha256="c" * 64,
        )

    def test_the_coordinators_delivery_receipt_passes_through_when_it_matches(self):
        execution, _ = self._load(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"]),
            delivery_receipt_sha256=DELIVERY,
        )
        self.assertEqual(execution["delivery_receipt_sha256"], DELIVERY)

    def test_without_a_delivery_receipt_and_without_outputs_the_old_rule_stands(self):
        execution, _ = self._load(
            dict(LoadPrincipalArtifactTest.GOOD), outputs_dir=None, knowledge_receipt_sha256=None,
        )
        self.assertIsNone(execution["outputs_receipt_sha256"])
        self.assertIsNone(execution["outputs_receipt"])

    def test_the_round_trip_with_outputs_satisfies_the_runner(self):
        """The execution dict, receipt included, is what the runner attaches."""
        from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_calculation_runner import (
            drive,
            make_run,
        )
        execution, findings = self._load(
            delivered_artifact(outputs_receipt_sha256=self.receipt["receipt_sha256"])
        )
        run = make_run()
        drive(run)
        run.attach_principal_findings(execution=execution, findings=findings)
        result = run.finalize()
        self.assertEqual(result["verdict"], "ACCEPTED", result["failed_gates"])
        principal = result["layers"]["positive_findings_report"]["principal"]
        self.assertEqual(principal["outputs_receipt_sha256"], self.receipt["receipt_sha256"])


# ------------------------------------------------------------------------------------------
# Slice 2 (S121): the read-back loop closes on a FINISHED calculation_result.json.
# ------------------------------------------------------------------------------------------

import io  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402

from research.kalshi.frankie_raw_mbo_benchmark.native_staging import (  # noqa: E402
    READ_BACK_SUFFIX,
    main as staging_main,
    read_back,
)


def finished_result(arm: str = "A_MEMORY") -> dict:
    """A finalized EVIDENCE_ONLY result, exactly what the launch writes to calculation_result.json.

    Run on the one arm (D86): the read-back binds the arm and the source manifest hash off
    the result's identity receipt, so the fixture result is stamped the way the A_MEMORY
    launch stamps it. (The runner test's own `identity()` fixture predates D86 and names
    A_CLEAN; it is another persona's file and is set here rather than edited there.)
    """
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_calculation_runner import (
        drive,
        identity,
        make_run,
    )
    run = make_run()
    run.identity = identity(arm=arm)
    drive(run)
    return run.finalize()


class ReadBackTest(unittest.TestCase):
    """A finished result cannot be reconstituted into a live NativeCalculationRun - the
    calculators' state is not serialized - so the findings layer is written INTO the result
    JSON through the runner's own attach route, and the updated result is written BESIDE the
    original. The original is never touched: it is the evidence the artifact cites, by hash.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
            cls.outputs_dir,
        )
        cls.result = finished_result()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _stage(self, tmp: str, *, artifact_overrides=None, result=None) -> tuple[Path, Path]:
        result_path = Path(tmp) / "calculation_result.json"
        result_path.write_text(json.dumps(result or self.result, indent=2, sort_keys=True) + "\n")
        body = delivered_artifact(
            evidence_result_hash=(result or self.result)["result_hash"],
            outputs_receipt_sha256=self.receipt["receipt_sha256"],
        )
        body.update(artifact_overrides or {})
        artifact_path = Path(tmp) / "frankie_principal_findings.json"
        artifact_path.write_text(json.dumps(body, indent=2))
        return artifact_path, result_path

    def _read_back(self, artifact_path, result_path, **kwargs):
        args = dict(
            result_path=result_path, outputs_dir=self.outputs_dir,
            knowledge_receipt_sha256=KNOWLEDGE, render_report=False,
        )
        args.update(kwargs)
        return read_back(artifact_path, **args)

    def test_it_writes_the_result_with_findings_beside_the_original_and_never_over_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            before = result_path.read_bytes()
            summary = self._read_back(artifact_path, result_path)
            written = Path(summary["result_path"])
            self.assertEqual(written.parent, result_path.parent)
            self.assertNotEqual(written, result_path)
            self.assertEqual(written.name, f"calculation_result{READ_BACK_SUFFIX}.json")
            self.assertEqual(result_path.read_bytes(), before, "the original was rewritten")
            updated = json.loads(written.read_text())
        self.assertEqual(updated["completion_status"], "PRINCIPAL_FINDINGS_ATTACHED")
        self.assertEqual(updated["verdict"], "ACCEPTED", updated["failed_gates"])
        layer = updated["layers"]["positive_findings_report"]
        self.assertEqual(len(layer["findings"]), 1)
        self.assertEqual(layer["authored_by"], "PRINCIPAL")
        self.assertEqual(layer["principal"]["outputs_receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertEqual(updated["evidence_result_hash"], self.result["result_hash"])
        self.assertNotEqual(updated["result_hash"], self.result["result_hash"])
        self.assertEqual(summary["findings_attached"], 1)
        self.assertEqual(summary["evidence_result_hash"], self.result["result_hash"])

    def test_an_artifact_citing_other_evidence_than_the_result_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(
                tmp, artifact_overrides={"evidence_result_hash": "b" * 64}
            )
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
        self.assertIn("evidence", str(caught.exception))

    def test_a_result_whose_hash_does_not_recompute_is_refused(self):
        """A tampered evidence file cannot receive findings; the artifact cites the hash."""
        tampered = json.loads(json.dumps(self.result))
        tampered["layers"]["exact_member_ledger"]["exact_member_rows"] = 999_999
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp, result=tampered)
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
        self.assertIn("result_hash", str(caught.exception))

    def test_a_result_that_already_carries_principal_findings_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            first = self._read_back(artifact_path, result_path)
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, Path(first["result_path"]))
        self.assertIn("already", str(caught.exception))

    def test_it_refuses_to_overwrite_an_earlier_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            self._read_back(artifact_path, result_path)
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
        self.assertIn("exists", str(caught.exception))

    def test_it_refuses_an_out_path_equal_to_the_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            with self.assertRaises(StagingError):
                self._read_back(artifact_path, result_path, out_path=result_path)

    def test_the_staging_refusals_still_fire_through_the_read_back(self):
        """The read-back runs load_principal_artifact; its gate is not bypassed."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(
                tmp, artifact_overrides={"outputs_receipt_sha256": "e" * 64}
            )
            with self.assertRaises(StagingError):
                self._read_back(artifact_path, result_path)
            self.assertFalse(
                (result_path.parent / f"calculation_result{READ_BACK_SUFFIX}.json").exists(),
                "a refused read-back must write nothing",
            )


class ReadBackCliTest(unittest.TestCase):
    """`python3 -m ...native_staging read-back ...`, following the sibling modules' pattern:
    a JSON summary on success, `REFUSED: <why>` and exit 1 otherwise."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.knowledge = write_knowledge_gate_inputs(root / "knowledge")
        knowledge_sha = cls.knowledge["delivery"].receipt["receipt_sha256"]
        cls.outputs_dir = root / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=knowledge_sha),
            cls.outputs_dir,
        )
        cls.result = finished_result()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _stage(self, tmp: str, **artifact_overrides) -> tuple[Path, Path]:
        result_path = Path(tmp) / "calculation_result.json"
        result_path.write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
        body = delivered_artifact(
            evidence_result_hash=self.result["result_hash"],
            outputs_receipt_sha256=self.receipt["receipt_sha256"],
            knowledge_receipt_sha256=self.knowledge["delivery"].receipt["receipt_sha256"],
            knowledge_use=self.knowledge["knowledge_use"],
        )
        body.update(artifact_overrides)
        artifact_path = Path(tmp) / "frankie_principal_findings.json"
        artifact_path.write_text(json.dumps(body, indent=2))
        return artifact_path, result_path

    def _argv(self, artifact_path, result_path, *extra):
        return [
            "read-back", "--artifact", str(artifact_path), "--result", str(result_path),
            "--outputs-dir", str(self.outputs_dir),
            "--knowledge-receipt", str(self.knowledge["receipt"]),
            "--knowledge-bundle", str(self.knowledge["bundle"]),
            "--prompt", str(self.knowledge["prompt"]),
            *extra,
        ]

    def test_read_back_prints_a_summary_and_writes_the_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                code = staging_main(self._argv(artifact_path, result_path))
            self.assertEqual(code, 0, out.getvalue())
            summary = json.loads(out.getvalue())
            self.assertEqual(summary["findings_attached"], 1)
            self.assertEqual(summary["outputs_receipt_sha256"], self.receipt["receipt_sha256"])
            self.assertTrue(Path(summary["result_path"]).exists())
            self.assertEqual(
                json.loads(Path(summary["result_path"]).read_text())["completion_status"],
                "PRINCIPAL_FINDINGS_ATTACHED",
            )

    def test_a_refusal_prints_refused_and_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp, outputs_receipt_sha256="e" * 64)
            out = io.StringIO()
            with redirect_stdout(out):
                code = staging_main(self._argv(artifact_path, result_path))
            self.assertEqual(code, 1)
            self.assertTrue(out.getvalue().startswith("REFUSED"), out.getvalue())

    def test_the_module_runs_as_a_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            proc = subprocess.run(
                [sys.executable, "-m", "research.kalshi.frankie_raw_mbo_benchmark.native_staging",
                 *self._argv(artifact_path, result_path, "--no-report")],
                capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[4]),
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["findings_attached"], 1)


# ------------------------------------------------------------------------------------------
# Slice 3 (S121): the report at the choke point carries the 99-layer crosswalk.
# ------------------------------------------------------------------------------------------


def fixture_delivery_receipt() -> dict:
    """A FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 that passes the crosswalk's own hash check."""
    from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import RECEIPT_SCHEMA
    from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
        canonical_hash,
    )
    body = {
        "schema": RECEIPT_SCHEMA, "run_id": "readback-fixture", "run_prefix": "fixture/prefix",
        "bucket": "fixture-bucket", "manifest_sha256": "f" * 64,
        "fetched_at": "2026-09-02T00:00:00Z", "out_dir": "fixture", "ledgers": {}, "objects": {},
        "all_ledgers_verified": True, "receipt_sha256": "",
    }
    body["receipt_sha256"] = canonical_hash(body, omit="receipt_sha256")
    return body


def fixture_knowledge_receipt(sha256: str) -> dict:
    """A FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1 shape as the crosswalk reads it (hash unverified
    there); its receipt_sha256 is what the bundle's verdicts cite."""
    from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
        KNOWLEDGE_RECEIPT_SCHEMA,
    )
    return {"schema": KNOWLEDGE_RECEIPT_SCHEMA, "layers": [], "receipt_sha256": sha256}


class ReadBackReportTest(unittest.TestCase):
    """The read-back has the result and every receipt in hand, so it computes the crosswalk
    (`native_layer_crosswalk.crosswalk`) and the report carries `render_crosswalk_table`. A
    receipt FILE handed to the read-back is bound by hash to the artifact's citation - that is
    a refusal - while a crosswalk that cannot be computed stays non-fatal and is STATED in the
    report rather than lost on stderr."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.delivery = fixture_delivery_receipt()
        cls.delivery_path = root / "FRANKIE_LEDGER_DELIVERY_RECEIPT.json"
        cls.delivery_path.write_text(json.dumps(cls.delivery, indent=2))
        cls.knowledge = fixture_knowledge_receipt(KNOWLEDGE)
        cls.knowledge_path = root / "FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT.json"
        cls.knowledge_path.write_text(json.dumps(cls.knowledge, indent=2))
        cls.outputs_dir = root / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(
                delivery_receipt_sha256=cls.delivery["receipt_sha256"],
                knowledge_receipt_sha256=KNOWLEDGE,
            ),
            cls.outputs_dir,
        )
        cls.result = finished_result()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _stage(self, tmp: str, **artifact_overrides) -> tuple[Path, Path]:
        result_path = Path(tmp) / "calculation_result.json"
        result_path.write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
        body = delivered_artifact(
            evidence_result_hash=self.result["result_hash"],
            delivery_receipt_sha256=self.delivery["receipt_sha256"],
            outputs_receipt_sha256=self.receipt["receipt_sha256"],
        )
        body.update(artifact_overrides)
        artifact_path = Path(tmp) / "frankie_principal_findings.json"
        artifact_path.write_text(json.dumps(body, indent=2))
        return artifact_path, result_path

    def test_the_read_back_report_carries_the_crosswalk_totals_and_files_the_outputs(self):
        from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
            load_registry,
        )
        from research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs import (
            registry_output_layer_ids,
        )
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            summary = read_back(
                artifact_path, result_path=result_path, outputs_dir=self.outputs_dir,
                delivery_receipt=self.delivery_path, knowledge_receipt=self.knowledge_path,
            )
            report = Path(summary["report_path"])
            self.assertTrue(report.exists())
            text = report.read_text()
        self.assertIn("## Layer crosswalk", text)
        self.assertIn("| registered |", text)
        self.assertIn("| inputs_applicable |", text)
        # Every output ledger the registry names is in the validated bundle, so the crosswalk
        # files all of them off the outputs receipt - the count derived, not typed.
        expected = len(registry_output_layer_ids(load_registry()))
        self.assertIn(f"| outputs_filed | {expected} |", text)
        self.assertIn(f"| outputs_pending | 0 |", text)
        self.assertIn(self.receipt["receipt_sha256"], text)
        self.assertIn(self.delivery["receipt_sha256"], text)
        self.assertEqual(summary["knowledge_receipt_sha256"], KNOWLEDGE)

    def test_a_delivery_receipt_file_that_is_not_the_cited_one_is_refused(self):
        other = dict(self.delivery, run_id="another-run", receipt_sha256="")
        from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
            canonical_hash,
        )
        other["receipt_sha256"] = canonical_hash(other, omit="receipt_sha256")
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            other_path = Path(tmp) / "other_receipt.json"
            other_path.write_text(json.dumps(other))
            with self.assertRaises(StagingError) as caught:
                read_back(
                    artifact_path, result_path=result_path, outputs_dir=self.outputs_dir,
                    delivery_receipt=other_path, knowledge_receipt=self.knowledge_path,
                    render_report=False,
                )
        self.assertIn("delivery", str(caught.exception))

    def test_a_knowledge_receipt_file_and_a_stated_sha_must_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            with self.assertRaises(StagingError) as caught:
                read_back(
                    artifact_path, result_path=result_path, outputs_dir=self.outputs_dir,
                    knowledge_receipt=self.knowledge_path, knowledge_receipt_sha256="f" * 64,
                    render_report=False,
                )
        self.assertIn("knowledge", str(caught.exception))

    def test_a_crosswalk_that_cannot_be_computed_is_non_fatal_and_stated_in_the_report(self):
        """The receipt file binds to the citation (same sha) and is still not a delivery
        receipt the crosswalk can read; the findings are the deliverable, so the read-back
        completes and the report says what happened to the crosswalk."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            broken_path = Path(tmp) / "broken_receipt.json"
            broken_path.write_text(json.dumps({
                "schema": "NOT_A_DELIVERY_RECEIPT", "receipt_sha256": self.delivery["receipt_sha256"],
            }))
            summary = read_back(
                artifact_path, result_path=result_path, outputs_dir=self.outputs_dir,
                delivery_receipt=broken_path, knowledge_receipt=self.knowledge_path,
            )
            self.assertTrue(Path(summary["result_path"]).exists())
            text = Path(summary["report_path"]).read_text()
        self.assertIn("## Layer crosswalk", text)
        self.assertIn("could not be computed", text)
        self.assertIn("NOT_A_DELIVERY_RECEIPT", text)

    def test_the_cli_accepts_the_receipt_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge = write_knowledge_gate_inputs(Path(tmp) / "knowledge")
            knowledge_sha = knowledge["delivery"].receipt["receipt_sha256"]
            outputs_dir = Path(tmp) / "principal_outputs"
            outputs_receipt = write_bundle(
                build_bundle(
                    delivery_receipt_sha256=self.delivery["receipt_sha256"],
                    knowledge_receipt_sha256=knowledge_sha,
                ),
                outputs_dir,
            )
            artifact_path, result_path = self._stage(
                tmp,
                knowledge_receipt_sha256=knowledge_sha,
                knowledge_use=knowledge["knowledge_use"],
                outputs_receipt_sha256=outputs_receipt["receipt_sha256"],
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = staging_main([
                    "read-back", "--artifact", str(artifact_path), "--result", str(result_path),
                    "--outputs-dir", str(outputs_dir),
                    "--delivery-receipt", str(self.delivery_path),
                    "--knowledge-receipt", str(knowledge["receipt"]),
                    "--knowledge-bundle", str(knowledge["bundle"]),
                    "--prompt", str(knowledge["prompt"]),
                ])
            self.assertEqual(code, 0, out.getvalue())
            summary = json.loads(out.getvalue())
            text = Path(summary["report_path"]).read_text()
        self.assertIn("## Layer crosswalk", text)
        self.assertEqual(summary["delivery_receipt_sha256"], self.delivery["receipt_sha256"])


# ------------------------------------------------------------------------------------------
# Slice 6 (S122): the read-back builds and writes the RT handoff trio from the validated bundle.
# ------------------------------------------------------------------------------------------

from research.kalshi import ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825 as workmode  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (  # noqa: E402
    LAYER_IDENTITY,
    canonical_hash,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import HANDOFF_FILES  # noqa: E402


class ReadBackHandoffTest(unittest.TestCase):
    """After a successful attach the read-back calls `build_handoff` and `write_handoff`:
    ONEWAY_HANDOFF, RT_FIRST_LOCK and RT_CONTEXT_MANIFEST are written BESIDE the read-back
    output, exclusive-create, never over an earlier trio, and the summary names their paths
    and hashes. `source_manifest_hash` and the arm are bound from the result's identity
    receipt (`layers.identity_receipt`, what the launch stamped from `RunIdentity`) - never
    from a CLI string. A bundle with no FIRST_LOCK entry yields a null first lock, stated,
    never a fabricated one; an artifact with no bundle has no handoff and says so."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
            cls.outputs_dir,
        )
        cls.result = finished_result()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _stage(self, tmp: str, *, result=None, receipt=None, **artifact_overrides) -> tuple[Path, Path]:
        result = result or self.result
        result_path = Path(tmp) / "calculation_result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        body = delivered_artifact(
            evidence_result_hash=result["result_hash"],
            outputs_receipt_sha256=(receipt or self.receipt)["receipt_sha256"],
        )
        body.update(artifact_overrides)
        artifact_path = Path(tmp) / "frankie_principal_findings.json"
        artifact_path.write_text(json.dumps(body, indent=2))
        return artifact_path, result_path

    def _read_back(self, artifact_path, result_path, **kwargs):
        args = dict(
            result_path=result_path, outputs_dir=self.outputs_dir,
            knowledge_receipt_sha256=KNOWLEDGE, render_report=False,
        )
        args.update(kwargs)
        return read_back(artifact_path, **args)

    def test_the_handoff_trio_is_written_beside_the_read_back_output_and_named_in_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            summary = self._read_back(artifact_path, result_path)
            written = Path(summary["result_path"])
            self.assertEqual(summary["handoff_dir"], str(written.parent))
            self.assertEqual(set(summary["handoff"]), set(HANDOFF_FILES))
            files = {}
            for name in HANDOFF_FILES:
                path = Path(summary["handoff"][name]["path"])
                self.assertEqual(path, written.parent / f"{name}.json", "written beside the read-back output")
                self.assertTrue(path.exists())
                body = json.loads(path.read_text())
                workmode.verify_self_hash(body)
                self.assertEqual(summary["handoff"][name]["receipt_hash"], body["receipt_hash"])
                files[name] = body
            lock_ledger = json.loads((self.outputs_dir / "ledgers" / "output_first_locks_and_no_locks.json").read_text())
        identity = self.result["layers"][LAYER_IDENTITY]
        self.assertEqual(files["ONEWAY_HANDOFF"]["full_validated_rt_output_hash"], summary["artifact_sha256"])
        self.assertEqual(files["ONEWAY_HANDOFF"]["frozen_rt_state_hash"], self.receipt["receipt_sha256"])
        self.assertEqual(files["RT_CONTEXT_MANIFEST"]["source_manifest_hash"], identity["source_manifest_hash"])
        self.assertEqual(summary["source_manifest_hash"], identity["source_manifest_hash"])
        self.assertEqual(files["RT_CONTEXT_MANIFEST"]["packet_hash"], DELIVERY)
        first = [e for e in lock_ledger["entries"] if e["body"]["lock_state"] == "FIRST_LOCK"][0]
        self.assertEqual(files["RT_FIRST_LOCK"]["first_lock"], first)
        self.assertEqual(summary["first_lock"]["entry_hash"], first["entry_hash"])
        self.assertEqual(summary["first_lock"]["candidate_id"], first["body"]["candidate_id"])
        self.assertIsNone(summary["first_lock_note"])
        self.assertIsNone(summary["handoff_note"])

    def test_source_manifest_hash_is_bound_from_the_identity_receipt_and_nothing_else_may_supply_it(self):
        """No CLI flag exists for it; a result whose identity receipt lacks it is refused."""
        from research.kalshi.frankie_raw_mbo_benchmark.native_staging import main as cli
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                cli(["read-back", "--artifact", "x", "--result", "y", "--source-manifest-hash", "f" * 64])
        stripped = json.loads(json.dumps(self.result))
        stripped["layers"][LAYER_IDENTITY].pop("source_manifest_hash")
        stripped.pop("result_hash")
        stripped["result_hash"] = canonical_hash(stripped)
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp, result=stripped)
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
            self.assertFalse((result_path.parent / f"calculation_result{READ_BACK_SUFFIX}.json").exists())
        self.assertIn("source_manifest_hash", str(caught.exception))

    def test_an_artifact_on_another_arm_than_the_result_is_refused_by_name(self):
        """The arm is bound off the identity receipt too: an A_MEMORY artifact against a
        result stamped A_CLEAN (the inert record) attaches to nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp, result=finished_result(arm="A_CLEAN"))
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
        message = str(caught.exception)
        self.assertIn("A_CLEAN", message)
        self.assertIn("A_MEMORY", message)

    def test_an_earlier_handoff_is_never_written_over_and_the_refusal_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            earlier = result_path.parent / "RT_FIRST_LOCK.json"
            earlier.write_text("{}")
            with self.assertRaises(StagingError) as caught:
                self._read_back(artifact_path, result_path)
            self.assertEqual(earlier.read_text(), "{}", "the earlier file was written over")
            self.assertFalse((result_path.parent / f"calculation_result{READ_BACK_SUFFIX}.json").exists())
            self.assertFalse((result_path.parent / "ONEWAY_HANDOFF.json").exists())
        self.assertIn("RT_FIRST_LOCK", str(caught.exception))
        self.assertIn("exists", str(caught.exception))

    def test_a_handoff_dir_of_its_own_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path, result_path = self._stage(tmp)
            handoff_dir = Path(tmp) / "handoff"
            summary = self._read_back(artifact_path, result_path, handoff_dir=handoff_dir)
            self.assertEqual(summary["handoff_dir"], str(handoff_dir))
            for name in HANDOFF_FILES:
                self.assertTrue((handoff_dir / f"{name}.json").exists())
                self.assertFalse((result_path.parent / f"{name}.json").exists())

    def test_a_bundle_with_no_first_lock_says_so_rather_than_fabricating_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs_dir = Path(tmp) / "principal_outputs"
            receipt = write_bundle(
                build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE, first_lock=False),
                outputs_dir,
            )
            artifact_path, result_path = self._stage(tmp, receipt=receipt)
            summary = self._read_back(artifact_path, result_path, outputs_dir=outputs_dir)
            lock = json.loads(Path(summary["handoff"]["RT_FIRST_LOCK"]["path"]).read_text())
        self.assertIsNone(lock["first_lock"])
        self.assertIsNone(summary["first_lock"])
        self.assertIn("no FIRST_LOCK", summary["first_lock_note"])

    def test_an_artifact_without_a_bundle_has_no_handoff_and_the_summary_says_so(self):
        """A pre-delivery artifact (no delivery receipt, no outputs) still reads back; there
        is no bundle to build a handoff from, and the summary states that instead of omitting
        the keys."""
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "calculation_result.json"
            result_path.write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
            body = dict(LoadPrincipalArtifactTest.GOOD, evidence_result_hash=self.result["result_hash"])
            artifact_path = Path(tmp) / "frankie_principal_findings.json"
            artifact_path.write_text(json.dumps(body))
            summary = read_back(artifact_path, result_path=result_path, render_report=False)
            self.assertEqual(summary["findings_attached"], 1)
            for name in HANDOFF_FILES:
                self.assertFalse((result_path.parent / f"{name}.json").exists())
        self.assertIsNone(summary["handoff"])
        self.assertIsNone(summary["handoff_dir"])
        self.assertIn("no output bundle", summary["handoff_note"])
        self.assertIsNone(summary["first_lock"])

    def test_a_forecaster_artifact_hands_nothing_off_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs_dir = Path(tmp) / "principal_outputs"
            receipt = write_bundle(
                build_bundle(role="FORECASTER_FRANKIE", delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
                outputs_dir,
            )
            artifact_path, result_path = self._stage(tmp, receipt=receipt, role="FORECASTER_FRANKIE")
            summary = self._read_back(artifact_path, result_path, outputs_dir=outputs_dir)
            for name in HANDOFF_FILES:
                self.assertFalse((result_path.parent / f"{name}.json").exists())
        self.assertIsNone(summary["handoff"])
        self.assertIn("FORECASTER_FRANKIE", summary["handoff_note"])

    def test_the_cli_names_the_handoff_paths_and_accepts_a_handoff_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge = write_knowledge_gate_inputs(Path(tmp) / "knowledge")
            knowledge_sha = knowledge["delivery"].receipt["receipt_sha256"]
            outputs_dir = Path(tmp) / "principal_outputs"
            outputs_receipt = write_bundle(
                build_bundle(
                    delivery_receipt_sha256=DELIVERY,
                    knowledge_receipt_sha256=knowledge_sha,
                ),
                outputs_dir,
            )
            artifact_path, result_path = self._stage(
                tmp,
                receipt=outputs_receipt,
                knowledge_receipt_sha256=knowledge_sha,
                knowledge_use=knowledge["knowledge_use"],
            )
            handoff_dir = Path(tmp) / "handoff"
            proc = subprocess.run(
                [sys.executable, "-m", "research.kalshi.frankie_raw_mbo_benchmark.native_staging",
                 "read-back", "--artifact", str(artifact_path), "--result", str(result_path),
                 "--outputs-dir", str(outputs_dir),
                 "--knowledge-receipt", str(knowledge["receipt"]),
                 "--knowledge-bundle", str(knowledge["bundle"]),
                 "--prompt", str(knowledge["prompt"]),
                 "--handoff-dir", str(handoff_dir), "--no-report"],
                capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[4]),
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            summary = json.loads(proc.stdout)
            for name in HANDOFF_FILES:
                path = Path(summary["handoff"][name]["path"])
                self.assertEqual(path.parent, handoff_dir)
                workmode.verify_self_hash(json.loads(path.read_text()))
            self.assertEqual(summary["source_manifest_hash"], self.result["layers"][LAYER_IDENTITY]["source_manifest_hash"])


# ------------------------------------------------------------------------------------------
# Slice 7 (S122): the canonical read-back surface, and the knowledge read gate's seam.
# ------------------------------------------------------------------------------------------

import shlex  # noqa: E402

from research.kalshi.frankie_raw_mbo_benchmark import native_staging  # noqa: E402


def canonical_usage_argv() -> list[str]:
    """The `read-back` command as the module docstring states it, split into argv.

    Read off `native_staging.__doc__`, never typed here: the usage IS the spec of the single
    entry, and a docstring that drifted from the parser would fail this instead of a reader.
    """
    lines = native_staging.__doc__.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("python3 -m ") and "native_staging" in line)
    command = []
    for line in lines[start:]:
        stripped = line.strip()
        command.append(stripped.rstrip("\\").strip())
        if not stripped.endswith("\\"):
            break
    return shlex.split(" ".join(command))


class CanonicalReadBackSurfaceTest(unittest.TestCase):
    """Greg (S122, D88): "there is supposed to be a canonical file or a runner, launcher file
    with everything." The launcher is native_a_arm_launch; the read-back is THIS module's CLI,
    the single entry that, given an artifact, its outputs dir, the result and the two receipts,
    validates, attaches, renders the report with the crosswalk and builds the handoff - on the
    one arm, with nothing to remember. The docstring's own command is run end to end."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.tmp.name) / "run"
        cls.run_dir.mkdir()
        cls.delivery = fixture_delivery_receipt()
        (cls.run_dir / "FRANKIE_LEDGER_DELIVERY_RECEIPT.json").write_text(json.dumps(cls.delivery, indent=2))
        cls.knowledge = write_knowledge_gate_inputs(cls.run_dir)
        knowledge_sha = cls.knowledge["delivery"].receipt["receipt_sha256"]
        cls.receipt = write_bundle(
            build_bundle(
                delivery_receipt_sha256=cls.delivery["receipt_sha256"],
                knowledge_receipt_sha256=knowledge_sha,
            ),
            cls.run_dir / "principal_outputs",
        )
        cls.result = finished_result()
        (cls.run_dir / "calculation_result.json").write_text(json.dumps(cls.result, indent=2, sort_keys=True) + "\n")
        body = delivered_artifact(
            evidence_result_hash=cls.result["result_hash"],
            delivery_receipt_sha256=cls.delivery["receipt_sha256"],
            outputs_receipt_sha256=cls.receipt["receipt_sha256"],
            knowledge_receipt_sha256=knowledge_sha,
            knowledge_use=cls.knowledge["knowledge_use"],
        )
        (cls.run_dir / "frankie_principal_findings.json").write_text(json.dumps(body, indent=2))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_docstring_states_the_command_and_it_carries_no_arm_to_remember(self):
        argv = canonical_usage_argv()
        self.assertEqual(argv[:3], ["python3", "-m", "research.kalshi.frankie_raw_mbo_benchmark.native_staging"])
        self.assertEqual(argv[3], "read-back")
        flags = {a for a in argv if a.startswith("--")}
        self.assertEqual(
            flags,
            {
                "--artifact", "--result", "--outputs-dir", "--delivery-receipt",
                "--knowledge-receipt", "--knowledge-bundle", "--prompt",
            },
        )
        self.assertNotIn("--arm", flags, "the arm is bound off the run, not remembered")
        self.assertIn("<run>", " ".join(argv))

    def test_the_docstrings_command_runs_end_to_end_on_the_fixtures(self):
        argv = [a.replace("<run>", str(self.run_dir)) for a in canonical_usage_argv()]
        argv[0] = sys.executable
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[4]))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["arm"], "A_MEMORY")
        # validated and attached
        updated = json.loads(Path(summary["result_path"]).read_text())
        self.assertEqual(updated["completion_status"], "PRINCIPAL_FINDINGS_ATTACHED")
        self.assertEqual(updated["verdict"], "ACCEPTED", updated["failed_gates"])
        self.assertEqual(summary["outputs_receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertEqual(summary["delivery_receipt_sha256"], self.delivery["receipt_sha256"])
        self.assertEqual(
            summary["knowledge_receipt_sha256"],
            self.knowledge["delivery"].receipt["receipt_sha256"],
        )
        # the report with the crosswalk
        report = Path(summary["report_path"]).read_text()
        self.assertIn("## Layer crosswalk", report)
        self.assertIn(self.receipt["receipt_sha256"], report)
        self.assertEqual(len(summary["crosswalk_sha256"]), 64)
        # the handoff, beside the read-back output
        for name in HANDOFF_FILES:
            path = Path(summary["handoff"][name]["path"])
            self.assertEqual(path.parent, self.run_dir)
            workmode.verify_self_hash(json.loads(path.read_text()))
        self.assertEqual(summary["source_manifest_hash"], self.result["layers"][LAYER_IDENTITY]["source_manifest_hash"])
        self.assertIsNotNone(summary["first_lock"])
        # the original evidence is untouched
        self.assertEqual(
            json.loads((self.run_dir / "calculation_result.json").read_text())["result_hash"],
            self.result["result_hash"],
        )


class KnowledgeReadGateSeamTest(unittest.TestCase):
    """The knowledge persona exposes `validate_knowledge_use`; the coordinator adapter is
    wired to it. The seam is `load_principal_artifact(knowledge_use_gate=)`, threaded through
    `read_back(knowledge_use_gate=)`, and the CLI reads the module hook
    `native_staging.KNOWLEDGE_USE_GATE`. The gate is
    called with the artifact body and the knowledge receipt sha the coordinator delivered
    under, BEFORE the bundle is validated; what it raises is a refusal that writes nothing;
    what it returns is carried on the execution as `knowledge_use_receipt`."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
            cls.outputs_dir,
        )
        cls.result = finished_result()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _artifact(self, tmp: str) -> Path:
        body = delivered_artifact(
            outputs_receipt_sha256=self.receipt["receipt_sha256"],
            knowledge_receipt_sha256=KNOWLEDGE,
            knowledge_use={"lessons": {"lesson-1": "INSPECTED"}},
        )
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(body))
        return path

    def test_the_hook_is_wired_to_the_file_bound_adapter(self):
        self.assertIs(
            native_staging.KNOWLEDGE_USE_GATE,
            native_staging.validate_staged_knowledge_use,
        )

    def test_the_gate_receives_the_artifact_body_and_the_delivered_receipt_sha_and_its_receipt_is_carried(self):
        calls = []

        def gate(body, *, knowledge_receipt_sha256):
            calls.append((dict(body), knowledge_receipt_sha256))
            return {"schema": "TEST_KNOWLEDGE_USE_RECEIPT", "inspected": 1}

        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = load_principal_artifact(
                self._artifact(tmp), expected_evidence_hash="a" * 64, render_report=False,
                outputs_dir=self.outputs_dir, knowledge_receipt_sha256=KNOWLEDGE,
                knowledge_use_gate=gate,
            )
        self.assertEqual(len(calls), 1)
        body, sha = calls[0]
        self.assertEqual(body["knowledge_use"], {"lessons": {"lesson-1": "INSPECTED"}})
        self.assertEqual(body["knowledge_receipt_sha256"], KNOWLEDGE)
        self.assertEqual(sha, KNOWLEDGE)
        self.assertEqual(execution["knowledge_use_receipt"], {"schema": "TEST_KNOWLEDGE_USE_RECEIPT", "inspected": 1})

    def test_a_gate_that_refuses_refuses_the_artifact_by_name_before_the_bundle_is_validated(self):
        seen = []

        def gate(body, *, knowledge_receipt_sha256):
            seen.append("gate")
            raise ValueError("lesson-1 was delivered and its disposition is missing")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StagingError) as caught:
                load_principal_artifact(
                    self._artifact(tmp), expected_evidence_hash="a" * 64, render_report=False,
                    outputs_dir=Path(tmp) / "no-such-bundle", knowledge_receipt_sha256=KNOWLEDGE,
                    knowledge_use_gate=gate,
                )
        self.assertEqual(seen, ["gate"])
        message = str(caught.exception)
        self.assertIn("knowledge read gate", message)
        self.assertIn("lesson-1", message)
        self.assertNotIn("no-such-bundle", message, "the gate fired before the bundle was looked at")

    def test_without_a_gate_nothing_is_carried_and_nothing_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            execution, _ = load_principal_artifact(
                self._artifact(tmp), expected_evidence_hash="a" * 64, render_report=False,
                outputs_dir=self.outputs_dir, knowledge_receipt_sha256=KNOWLEDGE,
            )
        self.assertNotIn("knowledge_use_receipt", execution)

    def test_the_read_back_threads_the_gate_and_a_refusal_writes_nothing(self):
        def gate(body, *, knowledge_receipt_sha256):
            raise ValueError("refused by the knowledge read gate")

        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "calculation_result.json"
            result_path.write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
            body = delivered_artifact(
                evidence_result_hash=self.result["result_hash"],
                outputs_receipt_sha256=self.receipt["receipt_sha256"],
            )
            artifact_path = Path(tmp) / "frankie_principal_findings.json"
            artifact_path.write_text(json.dumps(body))
            with self.assertRaises(StagingError) as caught:
                read_back(
                    artifact_path, result_path=result_path, outputs_dir=self.outputs_dir,
                    knowledge_receipt_sha256=KNOWLEDGE, render_report=False, knowledge_use_gate=gate,
                )
            self.assertFalse((result_path.parent / f"calculation_result{READ_BACK_SUFFIX}.json").exists())
            for name in HANDOFF_FILES:
                self.assertFalse((result_path.parent / f"{name}.json").exists())
        self.assertIn("knowledge read gate", str(caught.exception))

    def test_the_cli_reads_the_module_hook(self):
        calls = []

        def gate(body, *, knowledge_receipt_sha256):
            calls.append(knowledge_receipt_sha256)
            return None

        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "calculation_result.json"
            result_path.write_text(json.dumps(self.result, indent=2, sort_keys=True) + "\n")
            body = delivered_artifact(
                evidence_result_hash=self.result["result_hash"],
                outputs_receipt_sha256=self.receipt["receipt_sha256"],
            )
            artifact_path = Path(tmp) / "frankie_principal_findings.json"
            artifact_path.write_text(json.dumps(body))
            previous = native_staging.KNOWLEDGE_USE_GATE
            native_staging.KNOWLEDGE_USE_GATE = gate
            try:
                out = io.StringIO()
                with redirect_stdout(out):
                    code = staging_main([
                        "read-back", "--artifact", str(artifact_path), "--result", str(result_path),
                        "--outputs-dir", str(self.outputs_dir), "--knowledge-receipt-sha256", KNOWLEDGE,
                        "--no-report",
                    ])
            finally:
                native_staging.KNOWLEDGE_USE_GATE = previous
            self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(calls, [KNOWLEDGE])


class DefaultKnowledgeReadGateTest(unittest.TestCase):
    """The default seam validates the exact knowledge files staged for this artifact."""

    @classmethod
    def setUpClass(cls):
        from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
            build_knowledge_delivery,
            complete_knowledge_use,
            render_knowledge_block,
            serialized_principal_input,
        )

        cls.tmp = tempfile.TemporaryDirectory()
        cls.delivery = build_knowledge_delivery(arm="A_MEMORY", role="REAL_TIME_FRANKIE")
        cls.knowledge_use = complete_knowledge_use(cls.delivery.receipt)
        cls.prompt = (
            "# prompt\n" + render_knowledge_block(cls.delivery.receipt)
        ).encode("utf-8")
        cls.principal_input = serialized_principal_input(
            cls.prompt, cls.delivery.model_visible_context
        )
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.outputs_receipt = write_bundle(
            build_bundle(
                delivery_receipt_sha256=DELIVERY,
                knowledge_receipt_sha256=cls.delivery.receipt["receipt_sha256"],
            ),
            cls.outputs_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _artifact(self, directory: str, knowledge_use: dict) -> Path:
        body = delivered_artifact(
            knowledge_receipt_sha256=self.delivery.receipt["receipt_sha256"],
            outputs_receipt_sha256=self.outputs_receipt["receipt_sha256"],
            knowledge_use=knowledge_use,
        )
        path = Path(directory) / "frankie_principal_findings.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def _load(self, directory: str, knowledge_use: dict):
        return load_principal_artifact(
            self._artifact(directory, knowledge_use),
            expected_evidence_hash="a" * 64,
            render_report=False,
            outputs_dir=self.outputs_dir,
            knowledge_receipt_sha256=self.delivery.receipt["receipt_sha256"],
            knowledge_use_gate=native_staging.KNOWLEDGE_USE_GATE,
            knowledge_receipt=self.delivery.receipt,
            model_visible_context=self.delivery.model_visible_context,
            serialized_principal_input=self.principal_input,
        )

    def test_a_well_formed_knowledge_use_passes_and_carries_the_gate_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            execution, _ = self._load(directory, self.knowledge_use)
        self.assertEqual(
            execution["knowledge_use_receipt"]["knowledge_receipt_sha256"],
            self.delivery.receipt["receipt_sha256"],
        )

    def test_an_undelivered_knowledge_id_is_refused_by_name_through_staging(self):
        knowledge_use = json.loads(json.dumps(self.knowledge_use))
        undelivered = "not_a_delivered_knowledge_id"
        knowledge_use["dispositions"][undelivered] = {
            "disposition": "INSPECTED",
            "reason": "not actually delivered",
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StagingError) as caught:
                self._load(directory, knowledge_use)
        self.assertIn(undelivered, str(caught.exception))
