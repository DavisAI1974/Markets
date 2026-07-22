from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_readiness as readiness


class HistoricalRefinementReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def tearDown(self):
        self.temp.cleanup()

    def write_stage(self, spec, status=None, *, stand_down=False, mutate=None):
        if status is None:
            status = sorted(spec.ready_statuses)[0]
        value = readiness._fixture_artifact(spec, status, stand_down=stand_down)
        if mutate:
            mutate(value)
            value.pop(spec.fingerprint_field, None)
            value[spec.fingerprint_field] = readiness._fingerprint(value)
        readiness._atomic_json(self.root / spec.filename, value)
        return value

    def write_all(self):
        for spec in readiness.STAGES:
            self.write_stage(spec)

    def build(self):
        return readiness.build_readiness_report(
            self.root,
            validator_overrides=self.overrides,
        )

    def test_missing_chain_fails_closed_at_corpus(self):
        report = self.build()
        self.assertEqual(report["status"], "BLOCKED_OR_UNVERIFIED")
        self.assertEqual(report["first_blocking_stage"], "corpus_coverage")
        self.assertFalse(report["remote_presence_inferred"])

    def test_complete_chain_is_ready(self):
        self.write_all()
        report = self.build()
        self.assertEqual(report["status"], "G15_G16_EXACT_PUBLICATION_COMPLETE")
        self.assertIsNone(report["first_blocking_stage"])
        self.assertEqual(report["ready_stage_count"], len(readiness.STAGES))

    def test_downstream_ready_artifact_cannot_bypass_missing_upstream(self):
        self.write_stage(readiness.STAGES[1])
        report = self.build()
        row = report["stages"][1]
        self.assertEqual(row["validation"], "PASS")
        self.assertEqual(row["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_tampered_artifact_is_invalid(self):
        spec = readiness.STAGES[0]
        value = self.write_stage(spec)
        value["status"] = "BLOCKED"
        (self.root / spec.filename).write_text(json.dumps(value), encoding="utf-8")
        report = self.build()
        self.assertEqual(report["stages"][0]["effective_status"], "INVALID")
        self.assertIn("fingerprint", report["stages"][0]["blockers"][0])

    def test_wrong_schema_is_invalid_even_when_refingerprinted(self):
        spec = readiness.STAGES[0]
        value = self.write_stage(spec)
        value["schema"] = "wrong.v1"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        readiness._atomic_json(self.root / spec.filename, value)
        report = self.build()
        self.assertEqual(report["stages"][0]["effective_status"], "INVALID")

    def test_canonical_validator_failure_is_visible(self):
        spec = readiness.STAGES[0]
        self.write_stage(spec)
        overrides = dict(self.overrides)

        def fail(value):
            raise ValueError("canonical validator rejected artifact")

        overrides[spec.key] = fail
        report = readiness.build_readiness_report(self.root, validator_overrides=overrides)
        self.assertEqual(report["stages"][0]["validation"], "FAIL")
        self.assertEqual(report["stages"][0]["blockers"], ["canonical validator rejected artifact"])

    def test_stand_downs_are_preserved(self):
        for index, spec in enumerate(readiness.STAGES):
            self.write_stage(spec, stand_down=index == 2)
        report = self.build()
        self.assertIn("20260315", report["stand_down_days"])
        self.assertEqual(report["stages"][2]["effective_status"], "READY_WITH_STAND_DOWNS")

    def test_blocked_artifact_reports_embedded_blockers(self):
        spec = readiness.STAGES[0]
        self.write_stage(
            spec,
            status="BLOCKED",
            mutate=lambda value: value.update({"l1_wrong_basis_days": ["20260315"]}),
        )
        report = self.build()
        row = report["stages"][0]
        self.assertEqual(row["effective_status"], "BLOCKED")
        self.assertIn("l1_wrong_basis_days:20260315", row["blockers"])

    def test_exact_ready_broad_unverified_is_not_claimed_full(self):
        spec = readiness.STAGES[0]
        self.write_stage(spec, status="G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED")
        report = self.build()
        self.assertTrue(report["exact_replay_intersections_ready"])
        self.assertFalse(report["broad_corpus_verified"])

    def test_full_corpus_status_marks_broad_verified(self):
        spec = readiness.STAGES[0]
        self.write_stage(spec, status="FULL_CORPUS_AND_G15_G16_EXACT_READY")
        report = self.build()
        self.assertTrue(report["broad_corpus_verified"])

    def test_g15_publication_status_is_separate_from_g16(self):
        for spec in readiness.STAGES[:5]:
            self.write_stage(spec)
        report = self.build()
        self.assertEqual(report["status"], "G15_EXACT_PUBLICATION_COMPLETE_G16_INCOMPLETE")
        self.assertTrue(report["g15_exact_publication_complete"])
        self.assertFalse(report["g16_exact_publication_complete"])

    def test_stage_path_override_is_honored(self):
        spec = readiness.STAGES[0]
        custom = self.root / "custom.json"
        readiness._atomic_json(custom, readiness._fixture_artifact(spec, sorted(spec.ready_statuses)[0]))
        report = readiness.build_readiness_report(
            self.root,
            stage_paths={spec.key: custom},
            validator_overrides=self.overrides,
        )
        self.assertEqual(report["stages"][0]["path"], str(custom))
        self.assertEqual(report["stages"][0]["effective_status"], "READY")

    def test_report_tampering_is_rejected(self):
        report = self.build()
        report["execution_authority"] = True
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_report_security_controls_are_permanent(self):
        report = self.build()
        for field in (
            "remote_presence_inferred", "actual_outcome_paths_loaded", "paid_live_data_assumed",
            "random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started",
        ):
            self.assertFalse(report[field])
        self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(report["brokerage_contract"], "tastytrade_not_ibkr")

    def test_inputs_are_not_mutated(self):
        spec = readiness.STAGES[0]
        value = self.write_stage(spec)
        before = copy.deepcopy(value)
        self.build()
        observed = json.loads((self.root / spec.filename).read_text(encoding="utf-8"))
        self.assertEqual(observed, before)

    def test_parse_stage_paths_rejects_unknown_keys(self):
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness._parse_stage_paths(["unknown=/tmp/file.json"])


if __name__ == "__main__":
    unittest.main()
