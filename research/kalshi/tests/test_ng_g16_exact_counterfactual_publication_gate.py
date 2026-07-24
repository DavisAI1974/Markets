from __future__ import annotations

import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import ng_g16_exact_counterfactual_publication_gate as gate
import ng_historical_refinement_readiness_v13 as readiness


def _exact(*, stand_downs: list[str] | None = None) -> dict:
    value = {
        "schema": gate.EXACT_CURVE_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": gate.EXACT_CURVE_STAND_DOWNS if stand_downs else gate.EXACT_CURVE_READY,
        "authority": gate.EXACT_CURVE_AUTHORITY,
        "exact_counterfactual_causal_authorization_fingerprint": "exact-causal",
        "counterfactual_curve_authorization_fingerprint": "counterfactual-curve",
        "exact_partition_replay_authorization_fingerprint": "exact-replay",
        "counterfactual_causal_authorization_fingerprint": "counterfactual-causal",
        "exact_partition_gate_fingerprint": "partition",
        "source_binding_fingerprint": "source-binding",
        "window_contract_fingerprint": "window-contract",
        "prepared_curve_authorization_fingerprint": "prepared-curve",
        "prepared_causal_authorization_fingerprint": "prepared-causal",
        "prepared_replay_gate_fingerprint": "prepared-replay",
        "replay_fingerprint": "replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "blind_prior_fingerprint": "blind-prior",
        "refined_curve_fingerprint": "refined-curve",
        "candidate_count": 1,
        "candidate_ids": ["candidate-a"],
        "candidate_evidence_fingerprints": {"candidate-a": "evidence-a"},
        "candidate_ids_used_by_curve": ["candidate-a"],
        "bound_replay_source_count": 22,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "stand_down_days": list(stand_downs or []),
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": gate.EXACT_CURVE_NEXT_STAGE,
    }
    value["fingerprint"] = gate._fp(value)
    return value


def _legacy_lock() -> dict:
    return {
        "lock_fingerprint": "legacy-lock",
        "counterfactual_curve_authorization_fingerprint": "counterfactual-curve",
        "counterfactual_causal_authorization_fingerprint": "counterfactual-causal",
        "prepared_curve_authorization_fingerprint": "prepared-curve",
        "prepared_curve_lock_fingerprint": "prepared-lock",
        "replay_fingerprint": "replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "blind_prior_fingerprint": "blind-prior",
        "refined_curve_fingerprint": "refined-curve",
        "candidate_ids": ["candidate-a"],
        "candidate_evidence_fingerprints": {"candidate-a": "evidence-a"},
        "candidate_ids_used_by_curve": ["candidate-a"],
        "stand_down_days": [],
    }


def _legacy_completion(inner: dict) -> dict:
    return {
        "completion_fingerprint": "legacy-completion",
        "counterfactual_curve_lock_fingerprint": inner["lock_fingerprint"],
        "counterfactual_curve_authorization_fingerprint": "counterfactual-curve",
        "counterfactual_causal_authorization_fingerprint": "counterfactual-causal",
        "prepared_curve_authorization_fingerprint": "prepared-curve",
        "prepared_curve_lock_fingerprint": "prepared-lock",
        "prepared_publication_completion_fingerprint": "prepared-publication",
        "replay_fingerprint": "replay",
        "refined_curve_fingerprint": "refined-curve",
        "actual_sha256": "actual-sha",
        "blind_score_fingerprint": "blind-score",
        "refined_score_fingerprint": "refined-score",
        "comparison_fingerprint": "comparison",
        "chronological_validation_fingerprint": "chronological",
        "renders": {"blind": "blind.png", "refined": "refined.png"},
        "stand_down_days": [],
    }


def _lock_kwargs(exact: dict) -> dict:
    return {
        "exact_curve_authorization": exact,
        "exact_causal_authorization": {"fingerprint": "exact-causal"},
        "counterfactual_curve_authorization": {"fingerprint": "counterfactual-curve"},
        "curve_kwargs": {},
        "legacy_lock_kwargs": {},
    }


class ExactPublicationGateTests(unittest.TestCase):
    def upstream(self, *, legacy_lock: dict | None = None, legacy_completion=None):
        stack = ExitStack()
        lock = copy.deepcopy(legacy_lock or _legacy_lock())
        stack.enter_context(
            mock.patch.object(gate, "validate_exact_curve_authorization", return_value=None)
        )
        stack.enter_context(
            mock.patch.object(gate, "build_legacy_curve_lock", return_value=lock)
        )
        stack.enter_context(
            mock.patch.object(gate, "validate_legacy_curve_lock", return_value=None)
        )
        completion_builder = legacy_completion or (
            lambda *, counterfactual_curve_lock, **kwargs: _legacy_completion(
                counterfactual_curve_lock
            )
        )
        stack.enter_context(
            mock.patch.object(gate, "build_legacy_completion", side_effect=completion_builder)
        )
        stack.enter_context(
            mock.patch.object(gate, "validate_legacy_completion", return_value=None)
        )
        return stack

    def test_exact_lock_binds_source_windows_and_lessons(self):
        exact = _exact()
        with self.upstream():
            lock = gate.build_curve_lock(**_lock_kwargs(exact))
        self.assertEqual(
            lock["exact_counterfactual_curve_authorization_fingerprint"],
            exact["fingerprint"],
        )
        self.assertEqual(lock["source_binding_fingerprint"], "source-binding")
        self.assertEqual(lock["window_contract_fingerprint"], "window-contract")
        self.assertTrue(lock["fixed_scoring_may_begin"])
        self.assertFalse(lock["actual_g16_outcomes_used"])

    def test_exact_lock_rejects_incomplete_replay_binding(self):
        exact = _exact()
        exact["bound_replay_source_count"] = 21
        exact["fingerprint"] = gate._fp(
            {k: v for k, v in exact.items() if k != "fingerprint"}
        )
        with self.upstream(), self.assertRaises(
            gate.G16ExactCounterfactualPublicationError
        ):
            gate.build_curve_lock(**_lock_kwargs(exact))

    def test_exact_lock_rejects_false_window_contract(self):
        exact = _exact()
        exact["all_g16_state_spans_inside_exact_common_windows"] = False
        exact["fingerprint"] = gate._fp(
            {k: v for k, v in exact.items() if k != "fingerprint"}
        )
        with self.upstream(), self.assertRaises(
            gate.G16ExactCounterfactualPublicationError
        ):
            gate.build_curve_lock(**_lock_kwargs(exact))

    def test_exact_lock_rejects_legacy_replay_substitution(self):
        bad = _legacy_lock()
        bad["replay_fingerprint"] = "other-replay"
        with self.upstream(legacy_lock=bad), self.assertRaises(
            gate.G16ExactCounterfactualPublicationError
        ):
            gate.build_curve_lock(**_lock_kwargs(_exact()))

    def test_exact_lock_rejects_candidate_evidence_substitution(self):
        bad = _legacy_lock()
        bad["candidate_evidence_fingerprints"] = {"candidate-a": "other-evidence"}
        with self.upstream(legacy_lock=bad), self.assertRaises(
            gate.G16ExactCounterfactualPublicationError
        ):
            gate.build_curve_lock(**_lock_kwargs(_exact()))

    def test_exact_lock_is_deterministic_and_does_not_mutate_inputs(self):
        exact = _exact()
        kwargs = _lock_kwargs(exact)
        original = copy.deepcopy(kwargs)
        with self.upstream():
            first = gate.build_curve_lock(**kwargs)
            second = gate.build_curve_lock(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(kwargs, original)

    def test_refingerprinted_exact_lock_tampering_is_rejected(self):
        kwargs = _lock_kwargs(_exact())
        with self.upstream():
            lock = gate.build_curve_lock(**kwargs)
            lock["source_binding_fingerprint"] = "other-source"
            lock["lock_fingerprint"] = gate._fp(
                {k: v for k, v in lock.items() if k != "lock_fingerprint"}
            )
            with self.assertRaises(gate.G16ExactCounterfactualPublicationError):
                gate.validate_curve_lock(lock, **kwargs)

    def test_completion_preserves_exact_provenance(self):
        kwargs = _lock_kwargs(_exact())
        with self.upstream():
            lock = gate.build_curve_lock(**kwargs)
            completion = gate.build_completion(
                exact_curve_lock=lock,
                exact_lock_kwargs=kwargs,
                legacy_completion_kwargs={},
            )
        self.assertEqual(
            completion["exact_counterfactual_curve_lock_fingerprint"],
            lock["lock_fingerprint"],
        )
        self.assertTrue(completion["actual_g16_outcomes_used"])
        self.assertTrue(
            completion["exact_corpus_provenance_preserved_through_fixed_scoring"]
        )
        self.assertNotEqual(
            completion["blind_score_fingerprint"],
            completion["refined_score_fingerprint"],
        )

    def test_completion_rejects_legacy_lock_bypass(self):
        kwargs = _lock_kwargs(_exact())

        def bad_completion(*, counterfactual_curve_lock, **unused):
            value = _legacy_completion(counterfactual_curve_lock)
            value["counterfactual_curve_lock_fingerprint"] = "other-lock"
            return value

        with self.upstream(legacy_completion=bad_completion):
            lock = gate.build_curve_lock(**kwargs)
            with self.assertRaises(gate.G16ExactCounterfactualPublicationError):
                gate.build_completion(
                    exact_curve_lock=lock,
                    exact_lock_kwargs=kwargs,
                    legacy_completion_kwargs={},
                )

    def test_completion_unionizes_visible_stand_downs(self):
        exact = _exact(stand_downs=["2026-03-20"])
        kwargs = _lock_kwargs(exact)

        def stood_down(*, counterfactual_curve_lock, **unused):
            return {
                **_legacy_completion(counterfactual_curve_lock),
                "stand_down_days": ["2026-03-24"],
            }

        with self.upstream(legacy_completion=stood_down):
            lock = gate.build_curve_lock(**kwargs)
            completion = gate.build_completion(
                exact_curve_lock=lock,
                exact_lock_kwargs=kwargs,
                legacy_completion_kwargs={},
            )
        self.assertEqual(completion["status"], gate.READY_WITH_STAND_DOWNS)
        self.assertEqual(
            completion["stand_down_days"], ["2026-03-20", "2026-03-24"]
        )

    def test_refingerprinted_completion_authority_escalation_is_rejected(self):
        kwargs = _lock_kwargs(_exact())
        with self.upstream():
            lock = gate.build_curve_lock(**kwargs)
            completion = gate.build_completion(
                exact_curve_lock=lock,
                exact_lock_kwargs=kwargs,
                legacy_completion_kwargs={},
            )
            completion["options_lane_started"] = True
            completion["completion_fingerprint"] = gate._fp(
                {
                    k: v
                    for k, v in completion.items()
                    if k != "completion_fingerprint"
                }
            )
            with self.assertRaises(gate.G16ExactCounterfactualPublicationError):
                gate.validate_completion(
                    completion,
                    exact_curve_lock=lock,
                    exact_lock_kwargs=kwargs,
                    legacy_completion_kwargs={},
                )


class ReadinessV13Tests(unittest.TestCase):
    def test_replaces_legacy_lock_and_publication_contracts(self):
        rows = {spec.key: spec for spec in readiness.STAGES}
        lock = rows["g16_counterfactual_curve_lock"]
        publication = rows["g16_counterfactual_publication"]
        self.assertEqual(lock.schema, gate.LOCK_SCHEMA)
        self.assertEqual(lock.filename, "g16_exact_counterfactual_curve_lock.json")
        self.assertTrue(lock.pre_outcome)
        self.assertEqual(publication.schema, gate.SCHEMA)
        self.assertEqual(
            publication.filename,
            "g16_exact_counterfactual_publication_completion.json",
        )
        self.assertFalse(publication.pre_outcome)

    def test_exact_curve_lock_precedes_publication(self):
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(
            keys.index("g16_exact_counterfactual_curve_authorization"),
            keys.index("g16_counterfactual_curve_lock"),
        )
        self.assertLess(
            keys.index("g16_counterfactual_curve_lock"),
            keys.index("g16_counterfactual_publication"),
        )

    def _write_chain(self, root: Path, values: dict, *, skip: str | None = None):
        for spec in readiness.STAGES:
            if spec.key != skip:
                readiness._atomic_json(root / spec.filename, values[spec.key])

    def test_complete_fixture(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = readiness._linked_fixture_chain()
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            self._write_chain(root, values)
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
        self.assertEqual(
            report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V13"
        )
        self.assertTrue(
            report["g16_exact_corpus_provenance_locked_before_fixed_scoring"]
        )
        self.assertTrue(
            report["g16_exact_corpus_provenance_preserved_through_publication"]
        )

    def test_missing_exact_lock_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = readiness._linked_fixture_chain()
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            self._write_chain(root, values, skip="g16_counterfactual_curve_lock")
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
        self.assertEqual(
            report["first_blocking_stage"], "g16_counterfactual_curve_lock"
        )
        row = next(
            item
            for item in report["stages"]
            if item["key"] == "g16_counterfactual_publication"
        )
        self.assertEqual(row["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_rejects_legacy_lock_schema(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = readiness._linked_fixture_chain()
            lock = values["g16_counterfactual_curve_lock"]
            lock["schema"] = "ng_g16_counterfactual_curve_lock.v1"
            lock["lock_fingerprint"] = readiness._fingerprint(
                {k: v for k, v in lock.items() if k != "lock_fingerprint"}
            )
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            self._write_chain(root, values)
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
        row = next(
            item
            for item in report["stages"]
            if item["key"] == "g16_counterfactual_curve_lock"
        )
        self.assertEqual(row["effective_status"], "INVALID")

    def test_refingerprinted_exact_authorization_substitution_blocks_lock(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = readiness._linked_fixture_chain()
            lock = values["g16_counterfactual_curve_lock"]
            lock[
                "exact_counterfactual_curve_authorization_fingerprint"
            ] = "other-exact-curve"
            lock["lock_fingerprint"] = readiness._fingerprint(
                {k: v for k, v in lock.items() if k != "lock_fingerprint"}
            )
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            self._write_chain(root, values)
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
        row = next(
            item
            for item in report["stages"]
            if item["key"] == "g16_counterfactual_curve_lock"
        )
        self.assertEqual(row["effective_status"], "INVALID")

    def test_summary_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = readiness._linked_fixture_chain()
            overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
            self._write_chain(root, values)
            report = readiness.build_readiness_report(
                root, validator_overrides=overrides
            )
        report[
            "g16_exact_corpus_provenance_preserved_through_publication"
        ] = False
        report["fingerprint"] = readiness._fingerprint(
            {k: v for k, v in report.items() if k != "fingerprint"}
        )
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)


if __name__ == "__main__":
    unittest.main()
