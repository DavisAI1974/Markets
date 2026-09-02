"""S121 slice 4: the V2 workmode handoff machinery is re-fed from a VALIDATED output bundle.

`prior_memory/workmode-32851909748-1/` holds the handoff objects the two-Frankie workmode
coordinator wrote for the WRONG-DATA run: `ONEWAY_HANDOFF.json`, `RT_FIRST_LOCK.json`,
`RT_CONTEXT_MANIFEST.json` on the real-time side, `FORECASTER_*` on the forecaster side. The
machinery is what gets re-fed, never those files: the same schemas and key sets, built from the
bundle the staging gate validated, hashed by the coordinator module's own `sha256_json` and
checked by its own `verify_self_hash`, both imported.

Every shape assertion below reads the COMMITTED record and compares - no key set is typed here
as a spec. The one test that reaches the old surface's deeper validator pins, by execution,
exactly which check refuses the new surface and why, so the report can say so rather than guess.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi import ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825 as workmode
from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import (
    HANDOFF_FILES,
    StagingError,
    build_handoff,
    write_handoff,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.outputs_bundle_fixture import (
    build_bundle,
    write_bundle,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_staging import (
    DELIVERY,
    KNOWLEDGE,
    delivered_artifact,
)
from research.kalshi.frankie_role_context_profiles_20260824 import FrankieRole

PRIOR_RUN = (
    Path(__file__).resolve().parents[1] / "prior_memory" / "workmode-32851909748-1"
)
ARTIFACT_SHA = "a1" * 32
SOURCE_MANIFEST = "d" * 64


def committed(name: str) -> dict:
    return json.loads((PRIOR_RUN / f"{name}.json").read_text(encoding="utf-8"))


class HandoffFromBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.tmp.name) / "principal_outputs"
        cls.receipt = write_bundle(
            build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
            cls.outputs_dir,
        )
        cls.bundle = outputs.load_bundle(cls.outputs_dir)
        cls.objects = build_handoff(
            cls.outputs_dir,
            artifact_sha256=ARTIFACT_SHA,
            source_manifest_hash=SOURCE_MANIFEST,
            knowledge_receipt_sha256=KNOWLEDGE,
            delivery_receipt_sha256=DELIVERY,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_three_rt_side_objects_reuse_the_committed_schemas_and_key_sets(self):
        """Read off the wrong-data run's files, not typed: same schema string, same keys."""
        self.assertEqual(set(self.objects), set(HANDOFF_FILES))
        for name, body in self.objects.items():
            with self.subTest(name=name):
                record = committed(name)
                self.assertEqual(body["schema"], record["schema"])
                self.assertEqual(set(body), set(record))
                self.assertNotEqual(body["receipt_hash"], record["receipt_hash"])

    def test_every_object_verifies_under_the_coordinator_modules_own_check(self):
        for name, body in self.objects.items():
            with self.subTest(name=name):
                workmode.verify_self_hash(body)
                self.assertEqual(
                    body["receipt_hash"],
                    workmode.sha256_json({k: v for k, v in body.items() if k != "receipt_hash"}),
                )

    def test_the_one_way_handoff_binds_the_bundle_receipt_and_the_artifact(self):
        """The exact invariants `verify_rt_freeze` checks on ONEWAY_HANDOFF, held here."""
        handoff = self.objects["ONEWAY_HANDOFF"]
        self.assertEqual(handoff["frozen_rt_state_hash"], self.receipt["receipt_sha256"])
        self.assertEqual(handoff["full_validated_rt_output_hash"], ARTIFACT_SHA)
        self.assertIs(handoff["full_validated_rt_output_included"], True)
        self.assertEqual(handoff["from_role"], FrankieRole.REAL_TIME.value)
        self.assertEqual(handoff["to_role"], FrankieRole.FORECASTER.value)
        self.assertIs(handoff["rt_frozen_before_forecaster"], True)
        self.assertIs(handoff["forecaster_may_modify_rt_state"], False)
        self.assertIs(handoff["forecaster_may_reconstruct_competing_current_state"], False)

    def test_the_first_lock_is_the_bundles_lock_ledger_head_entry(self):
        lock = self.objects["RT_FIRST_LOCK"]
        ledger = self.bundle["ledgers"]["output_first_locks_and_no_locks"]
        self.assertEqual(lock["first_lock"], ledger["entries"][-1])
        self.assertEqual(lock["first_lock"]["body"]["lock_state"], "FIRST_LOCK")
        self.assertEqual(lock["first_lock"]["entry_hash"], ledger["head_hash"])
        self.assertEqual(lock["first_lock_owner"], FrankieRole.REAL_TIME.value)
        self.assertEqual(lock["rt_output_hash"], ARTIFACT_SHA)
        candidates = self.bundle["ledgers"]["output_candidate_discoveries"]["entries"]
        self.assertEqual(lock["exhaustion_events"], candidates)

    def test_the_context_manifest_seals_the_answer_wall_from_the_empty_ledger(self):
        context = self.objects["RT_CONTEXT_MANIFEST"]
        wall = self.bundle["ledgers"]["output_answer_wall_access_receipts"]
        self.assertEqual(wall["entries"], [])
        self.assertEqual(context["answer_wall"], "SEALED")
        self.assertIs(context["provider_api_called"], False)
        self.assertIs(context["role_is_forecasting"], False)
        self.assertEqual(context["role"], FrankieRole.REAL_TIME.value)
        self.assertEqual(context["packet_hash"], DELIVERY)
        self.assertEqual(context["source_manifest_hash"], SOURCE_MANIFEST)

    def test_building_is_deterministic(self):
        again = build_handoff(
            self.outputs_dir, artifact_sha256=ARTIFACT_SHA, source_manifest_hash=SOURCE_MANIFEST,
            knowledge_receipt_sha256=KNOWLEDGE, delivery_receipt_sha256=DELIVERY,
        )
        self.assertEqual(again, self.objects)


class HandoffRefusalTest(unittest.TestCase):
    def test_a_forecaster_bundle_has_nothing_to_hand_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            write_bundle(
                build_bundle(
                    role="FORECASTER_FRANKIE", delivery_receipt_sha256=DELIVERY,
                    knowledge_receipt_sha256=KNOWLEDGE,
                ),
                root,
            )
            with self.assertRaises(StagingError) as caught:
                build_handoff(
                    root, artifact_sha256=ARTIFACT_SHA, source_manifest_hash=SOURCE_MANIFEST,
                    knowledge_receipt_sha256=KNOWLEDGE, delivery_receipt_sha256=DELIVERY,
                )
        self.assertIn("FORECASTER", str(caught.exception))

    def test_a_bundle_the_validator_refuses_builds_no_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            write_bundle(
                build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
                root,
            )
            path = root / "ledgers" / "output_first_locks_and_no_locks.json"
            ledger = json.loads(path.read_text())
            ledger["entries"][-1]["body"]["candidate_id"] = "cand-9999"
            path.write_text(json.dumps(ledger))
            with self.assertRaises(StagingError) as caught:
                build_handoff(
                    root, artifact_sha256=ARTIFACT_SHA, source_manifest_hash=SOURCE_MANIFEST,
                    knowledge_receipt_sha256=KNOWLEDGE, delivery_receipt_sha256=DELIVERY,
                )
        self.assertIn("rewritten", str(caught.exception))

    def test_a_malformed_artifact_or_source_manifest_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            write_bundle(
                build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
                root,
            )
            for kwargs in (
                dict(artifact_sha256="not-a-sha", source_manifest_hash=SOURCE_MANIFEST),
                dict(artifact_sha256=ARTIFACT_SHA, source_manifest_hash="not-a-sha"),
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(StagingError):
                    build_handoff(
                        root, knowledge_receipt_sha256=KNOWLEDGE,
                        delivery_receipt_sha256=DELIVERY, **kwargs,
                    )


class WriteHandoffTest(unittest.TestCase):
    def test_it_writes_the_three_files_once_and_never_over_them(self):
        """Written with the coordinator module's own exclusive-create `write_json`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            write_bundle(
                build_bundle(delivery_receipt_sha256=DELIVERY, knowledge_receipt_sha256=KNOWLEDGE),
                root,
            )
            objects = build_handoff(
                root, artifact_sha256=ARTIFACT_SHA, source_manifest_hash=SOURCE_MANIFEST,
                knowledge_receipt_sha256=KNOWLEDGE, delivery_receipt_sha256=DELIVERY,
            )
            out = Path(tmp) / "handoff"
            written = write_handoff(objects, out)
            self.assertEqual(sorted(p.name for p in written), sorted(f"{n}.json" for n in HANDOFF_FILES))
            for path in written:
                workmode.verify_self_hash(json.loads(path.read_text()))
            with self.assertRaises(StagingError) as caught:
                write_handoff(objects, out)
        self.assertIn("exists", str(caught.exception))


class OldSurfaceValidatorsTest(unittest.TestCase):
    """What could NOT be reused, pinned by execution so the report names the check."""

    def test_validate_rt_refuses_the_findings_artifact_at_its_first_check(self):
        """`verify_rt_freeze` (the deeper handoff validator) reads `RT_OUTPUT.json` from a run
        root and runs `validate_rt` on it; its FIRST check is `RT_REQUIRED - set(value)`, the
        old two-day-surface output contract, which the findings artifact does not carry."""
        manifest = {"first_event_second": 0, "last_event_second": 1, "manifest_hash": "0" * 64}
        with self.assertRaises(workmode.prior.TwoFrankieBlindError) as caught:
            workmode.validate_rt(delivered_artifact(), manifest)
        message = str(caught.exception)
        self.assertIn("RT output missing fields", message)
        for field in ("exhaustion_events", "frozen_rt_state", "state_summary", "as_of"):
            self.assertIn(field, message)


if __name__ == "__main__":
    unittest.main()
