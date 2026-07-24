from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_readiness_v14 as readiness


class HistoricalRefinementReadinessV14Tests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _overrides(self) -> dict:
        return {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def _write_chain(self, root: Path) -> dict:
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(root / spec.filename, values[spec.key])
        return values

    def test_stage_order_places_lock_attestation_before_publication(self) -> None:
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(
            keys.index("g16_counterfactual_curve_lock"),
            keys.index("g16_exact_lock_context_compilation"),
        )
        self.assertLess(
            keys.index("g16_exact_lock_context_compilation"),
            keys.index("g16_counterfactual_publication"),
        )
        self.assertLess(
            keys.index("g16_counterfactual_publication"),
            keys.index("g16_exact_publication_context_compilation"),
        )

    def test_complete_chain_requires_both_compiler_attestations(self) -> None:
        root = self._root()
        self._write_chain(root)
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        self.assertEqual(
            report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V14"
        )
        self.assertTrue(report["g16_exact_lock_built_through_context_compiler"])
        self.assertTrue(
            report["g16_exact_publication_built_through_context_compiler"]
        )

    def test_missing_lock_attestation_blocks_fixed_publication(self) -> None:
        root = self._root()
        self._write_chain(root)
        (root / readiness._LOCK_ATTESTATION.filename).unlink()
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        self.assertEqual(
            report["first_blocking_stage"],
            "g16_exact_lock_context_compilation",
        )
        publication = next(
            row
            for row in report["stages"]
            if row["key"] == "g16_counterfactual_publication"
        )
        self.assertEqual(publication["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_missing_publication_attestation_prevents_v14_completion(self) -> None:
        root = self._root()
        self._write_chain(root)
        (root / readiness._PUBLICATION_ATTESTATION.filename).unlink()
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        self.assertEqual(
            report["status"],
            "G16_EXACT_PUBLICATION_COMPLETE_COMPILER_ATTESTATION_INCOMPLETE",
        )
        self.assertEqual(
            report["first_blocking_stage"],
            "g16_exact_publication_context_compilation",
        )

    def test_lock_artifact_substitution_invalidates_lock_attestation_link(self) -> None:
        root = self._root()
        values = self._write_chain(root)
        lock = copy.deepcopy(values["g16_counterfactual_curve_lock"])
        lock["candidate_count"] += 1
        lock.pop("lock_fingerprint")
        lock["lock_fingerprint"] = readiness._fingerprint(lock)
        readiness._atomic_json(root / readiness.v13._G16_EXACT_LOCK.filename, lock)
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        attestation = next(
            row
            for row in report["stages"]
            if row["key"] == "g16_exact_lock_context_compilation"
        )
        self.assertEqual(attestation["effective_status"], "INVALID")

    def test_publication_attestation_must_bind_lock_attestation(self) -> None:
        root = self._root()
        values = self._write_chain(root)
        publication_attestation = copy.deepcopy(
            values["g16_exact_publication_context_compilation"]
        )
        publication_attestation[
            "lock_context_compilation_attestation_fingerprint"
        ] = "substituted"
        publication_attestation.pop("fingerprint")
        publication_attestation["fingerprint"] = readiness._fingerprint(
            publication_attestation
        )
        readiness._atomic_json(
            root / readiness._PUBLICATION_ATTESTATION.filename,
            publication_attestation,
        )
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        row = next(
            item
            for item in report["stages"]
            if item["key"] == "g16_exact_publication_context_compilation"
        )
        self.assertEqual(row["effective_status"], "INVALID")

    def test_lock_attestation_is_pre_outcome_and_publication_attestation_is_post_outcome(self) -> None:
        specs = {spec.key: spec for spec in readiness.STAGES}
        self.assertTrue(specs["g16_exact_lock_context_compilation"].pre_outcome)
        self.assertFalse(
            specs["g16_exact_publication_context_compilation"].pre_outcome
        )

    def test_refingerprinted_summary_tampering_fails(self) -> None:
        root = self._root()
        self._write_chain(root)
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        changed = copy.deepcopy(report)
        changed["g16_exact_lock_built_through_context_compiler"] = False
        changed.pop("fingerprint")
        changed["fingerprint"] = readiness._fingerprint(changed)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(changed)

    def test_permanent_authority_wall(self) -> None:
        root = self._root()
        self._write_chain(root)
        report = readiness.build_readiness_report(
            root, validator_overrides=self._overrides()
        )
        self.assertFalse(report["paid_live_data_assumed"])
        self.assertFalse(report["random_shuffle_used"])
        self.assertTrue(report["one_signal_authority_preserved"])
        self.assertTrue(report["blind_forecasts_immutable"])
        self.assertFalse(report["may_update_ng_brain"])
        self.assertFalse(report["execution_authority"])
        self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(report["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(report["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
