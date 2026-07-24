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

    def write_value(self, spec, value):
        readiness._atomic_json(self.root / spec.filename, value)

    def write_stage(self, spec, status=None, *, stand_down=False, mutate=None):
        status = status or sorted(spec.ready_statuses)[0]
        value = readiness._fixture_artifact(spec, status, stand_down=stand_down)
        if mutate:
            mutate(value)
            value.pop(spec.fingerprint_field, None)
            value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        return value

    def write_all(self):
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            self.write_value(spec, values[spec.key])
        return values

    def build(self):
        return readiness.build_readiness_report(
            self.root,
            validator_overrides=self.overrides,
        )

    def test_missing_chain_fails_closed_at_corpus(self):
        report = self.build()
        self.assertEqual(report["status"], "BLOCKED_OR_UNVERIFIED")
        self.assertEqual(report["first_blocking_stage"], "corpus_coverage")

    def test_complete_counterfactual_chain_is_ready(self):
        self.write_all()
        report = self.build()
        self.assertEqual(report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE")
        self.assertTrue(report["hardened_g16_chain_complete"])
        self.assertTrue(report["g15_counterfactual_lessons_complete"])
        self.assertTrue(report["g15_g16_counterfactual_lineage_complete"])
        self.assertEqual(report["ready_stage_count"], len(readiness.STAGES))

    def test_legacy_prepared_lock_and_publication_cannot_complete_v3(self):
        self.write_all()
        lock_spec = next(spec for spec in readiness.STAGES if spec.key == "g16_counterfactual_curve_lock")
        publication_spec = next(spec for spec in readiness.STAGES if spec.key == "g16_counterfactual_publication")
        (self.root / lock_spec.filename).unlink()
        (self.root / publication_spec.filename).unlink()
        (self.root / "g16_prepared_curve_lock.json").write_text("{}\n", encoding="utf-8")
        (self.root / "g16_prepared_publication_completion.json").write_text("{}\n", encoding="utf-8")
        report = self.build()
        self.assertEqual(report["first_blocking_stage"], "g16_counterfactual_curve_lock")
        self.assertFalse(report["g16_exact_publication_complete"])

    def test_counterfactual_attribution_is_required_before_g15_scoring(self):
        values = readiness._linked_fixture_chain()
        attribution_index = next(i for i, spec in enumerate(readiness.STAGES) if spec.key == "g15_counterfactual_attribution")
        for spec in readiness.STAGES[:attribution_index]:
            self.write_value(spec, values[spec.key])
        publication = next(spec for spec in readiness.STAGES if spec.key == "g15_publication")
        self.write_value(publication, values[publication.key])
        report = self.build()
        self.assertEqual(report["first_blocking_stage"], "g15_counterfactual_attribution")
        publication_row = report["stages"][readiness.STAGES.index(publication)]
        self.assertEqual(publication_row["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_counterfactual_lesson_gate_is_required_after_g15_publication(self):
        values = readiness._linked_fixture_chain()
        lesson_index = next(i for i, spec in enumerate(readiness.STAGES) if spec.key == "g15_counterfactual_lesson_gate")
        for spec in readiness.STAGES[:lesson_index]:
            self.write_value(spec, values[spec.key])
        report = self.build()
        self.assertEqual(report["first_blocking_stage"], "g15_counterfactual_lesson_gate")
        self.assertEqual(report["status"], "G15_EXACT_PUBLICATION_COMPLETE_COUNTERFACTUAL_LESSONS_INCOMPLETE")

    def test_g15_g16_lineage_is_required_before_g16_basis_and_replay(self):
        values = readiness._linked_fixture_chain()
        lineage = next(spec for spec in readiness.STAGES if spec.key == "g15_g16_counterfactual_lineage")
        for spec in readiness.STAGES[:readiness.STAGES.index(lineage)]:
            self.write_value(spec, values[spec.key])
        later = next(spec for spec in readiness.STAGES if spec.key == "g16_corpus_basis")
        self.write_value(later, values[later.key])
        report = self.build()
        self.assertEqual(report["first_blocking_stage"], lineage.key)
        self.assertEqual(report["stages"][readiness.STAGES.index(later)]["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_basis_regeneration_is_required_before_catalog_export(self):
        corpus, basis, export = readiness.STAGES[:3]
        self.write_stage(corpus)
        self.write_stage(export)
        report = self.build()
        self.assertEqual(report["first_blocking_stage"], basis.key)
        self.assertEqual(report["stages"][2]["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_downstream_ready_artifact_cannot_bypass_missing_upstream(self):
        self.write_stage(readiness.STAGES[1])
        report = self.build()
        self.assertEqual(report["stages"][1]["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_tampered_artifact_is_invalid(self):
        spec = readiness.STAGES[0]
        value = self.write_stage(spec)
        value["status"] = "BLOCKED"
        (self.root / spec.filename).write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(self.build()["stages"][0]["effective_status"], "INVALID")

    def test_wrong_schema_is_invalid_even_when_refingerprinted(self):
        spec = readiness.STAGES[0]
        value = self.write_stage(spec)
        value["schema"] = "wrong.v1"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        self.assertEqual(self.build()["stages"][0]["effective_status"], "INVALID")

    def test_nested_required_provenance_is_mandatory(self):
        spec = next(item for item in readiness.STAGES if item.key == "g15_counterfactual_lesson_gate")
        value = readiness._fixture_artifact(spec, sorted(spec.ready_statuses)[0])
        value["source"].pop("counterfactual_fingerprint")
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertEqual(row["effective_status"], "INVALID")
        self.assertTrue(any("required provenance" in blocker for blocker in row["blockers"]))

    def test_pre_g16_outcome_stage_may_disclose_g15_but_not_g16_outcomes(self):
        spec = next(item for item in readiness.STAGES if item.key == "g16_counterfactual_curve_authorization")
        self.write_stage(spec, mutate=lambda value: value.update({"actual_g15_outcomes_used": True, "actual_g16_outcomes_used": False}))
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertNotEqual(row["effective_status"], "INVALID")
        value = json.loads((self.root / spec.filename).read_text(encoding="utf-8"))
        value["actual_g16_outcomes_used"] = True
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertEqual(row["effective_status"], "INVALID")

    def test_final_publication_may_record_fixed_g16_outcome_scoring(self):
        values = self.write_all()
        spec = next(item for item in readiness.STAGES if item.key == "g16_counterfactual_publication")
        value = values[spec.key]
        value["actual_g16_outcomes_used"] = True
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        self.assertEqual(self.build()["stages"][-1]["effective_status"], "READY")

    def test_nested_attribution_link_substitution_is_rejected(self):
        values = self.write_all()
        spec = next(item for item in readiness.STAGES if item.key == "g15_counterfactual_lesson_gate")
        value = values[spec.key]
        value["source"]["counterfactual_fingerprint"] = "replacement-attribution"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertEqual(row["effective_status"], "INVALID")
        self.assertTrue(any("provenance link mismatch" in blocker for blocker in row["blockers"]))

    def test_lineage_substitution_is_rejected_after_refingerprint(self):
        values = self.write_all()
        spec = next(item for item in readiness.STAGES if item.key == "g16_counterfactual_causal_authorization")
        value = values[spec.key]
        value["counterfactual_lineage_gate_fingerprint"] = "other-lineage"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertEqual(row["effective_status"], "INVALID")

    def test_curve_lock_substitution_is_rejected(self):
        values = self.write_all()
        spec = next(item for item in readiness.STAGES if item.key == "g16_counterfactual_publication")
        value = values[spec.key]
        value["counterfactual_curve_lock_fingerprint"] = "other-lock"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        self.assertEqual(self.build()["stages"][-1]["effective_status"], "INVALID")

    def test_required_prepared_provenance_is_mandatory(self):
        spec = next(item for item in readiness.STAGES if item.key == "g16_prepared_replay")
        value = readiness._fixture_artifact(spec, sorted(spec.ready_statuses)[0])
        value.pop("prepared_corpus_fingerprint")
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        self.write_value(spec, value)
        row = self.build()["stages"][readiness.STAGES.index(spec)]
        self.assertEqual(row["effective_status"], "INVALID")

    def test_canonical_validator_failure_is_visible(self):
        spec = readiness.STAGES[0]
        self.write_stage(spec)
        overrides = dict(self.overrides)
        def fail(value):
            raise ValueError("canonical validator rejected artifact")
        overrides[spec.key] = fail
        report = readiness.build_readiness_report(self.root, validator_overrides=overrides)
        self.assertEqual(report["stages"][0]["blockers"], ["canonical validator rejected artifact"])

    def test_stand_downs_are_preserved_across_counterfactual_chain(self):
        values = readiness._linked_fixture_chain()
        spec = next(item for item in readiness.STAGES if item.key == "g16_counterfactual_causal_authorization")
        values[spec.key]["all_stand_down_days"] = ["20260401"]
        values[spec.key].pop(spec.fingerprint_field)
        values[spec.key][spec.fingerprint_field] = readiness._fingerprint(values[spec.key])
        for target in readiness.STAGES[readiness.STAGES.index(spec) + 1:]:
            for source_key, source_path, target_key, target_path in readiness.LINK_RULES:
                if target_key == target.key:
                    readiness._path_set(values[target.key], target_path, readiness._path_get(values[source_key], source_path))
            values[target.key].pop(target.fingerprint_field, None)
            values[target.key][target.fingerprint_field] = readiness._fingerprint(values[target.key])
        for stage in readiness.STAGES:
            self.write_value(stage, values[stage.key])
        report = self.build()
        self.assertIn("20260401", report["stand_down_days"])

    def test_exact_ready_broad_unverified_is_not_claimed_full(self):
        spec = readiness.STAGES[0]
        self.write_stage(spec, status="G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED")
        report = self.build()
        self.assertTrue(report["exact_replay_intersections_ready"])
        self.assertFalse(report["broad_corpus_verified"])

    def test_stage_path_override_is_honored(self):
        spec = readiness.STAGES[0]
        custom = self.root / "custom.json"
        readiness._atomic_json(custom, readiness._fixture_artifact(spec, sorted(spec.ready_statuses)[0]))
        report = readiness.build_readiness_report(self.root, stage_paths={spec.key: custom}, validator_overrides=self.overrides)
        self.assertEqual(report["stages"][0]["path"], str(custom))

    def test_report_tampering_is_rejected(self):
        report = self.build()
        report["execution_authority"] = True
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_report_security_controls_are_permanent(self):
        report = self.build()
        for field in ("remote_presence_inferred", "actual_outcome_paths_loaded", "paid_live_data_assumed", "random_shuffle_used", "may_update_ng_brain", "execution_authority", "options_lane_started"):
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
