from __future__ import annotations

import copy
import unittest
from unittest import mock

import ng_g16_counterfactual_causal_authorization as subject


class CounterfactualCausalAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = subject._fixture()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture["_temporary"].cleanup()

    def kwargs(self) -> dict:
        return {
            key: copy.deepcopy(value)
            for key, value in self.fixture.items()
            if not key.startswith("_") and key != "lineage_fixture"
        }

    @staticmethod
    def refingerprint(value: dict) -> None:
        value.pop("fingerprint", None)
        value["fingerprint"] = subject._fp(value)

    def test_valid_exact_lineage_authorization(self) -> None:
        result = subject.build_authorization(**self.kwargs())
        self.assertEqual(result["status"], subject.STATUS_READY)
        self.assertGreater(result["candidate_count"], 0)
        self.assertEqual(
            result["g16_plan_fingerprint"], self.fixture["g16_plan"]["plan_fingerprint"]
        )
        self.assertFalse(result["actual_g16_outcomes_used"])

    def test_sources_are_immutable(self) -> None:
        kwargs = self.kwargs()
        before = copy.deepcopy(kwargs)
        subject.build_authorization(**kwargs)
        self.assertEqual(kwargs, before)

    def test_exact_candidate_and_evidence_lineage_is_carried(self) -> None:
        result = subject.build_authorization(**self.kwargs())
        self.assertEqual(result["candidate_ids"], self.fixture["lineage_gate"]["candidate_ids"])
        self.assertEqual(
            result["candidate_evidence_fingerprints"],
            self.fixture["lineage_gate"]["candidate_evidence_fingerprints"],
        )

    def test_refingerprinted_lineage_tampering_is_rejected(self) -> None:
        kwargs = self.kwargs()
        kwargs["lineage_gate"]["candidate_ids"].append("manual.after_score")
        kwargs["lineage_gate"]["candidate_ids"].sort()
        kwargs["lineage_gate"]["candidate_count"] += 1
        self.refingerprint(kwargs["lineage_gate"])
        with self.assertRaises(subject.G16CounterfactualCausalAuthorizationError):
            subject.build_authorization(**kwargs)

    def test_refingerprinted_prepared_authorization_tampering_is_rejected(self) -> None:
        kwargs = self.kwargs()
        kwargs["prepared_authorization"]["candidate_ids"] = ["legacy.manual.lesson"]
        self.refingerprint(kwargs["prepared_authorization"])
        with self.assertRaises(subject.G16CounterfactualCausalAuthorizationError):
            subject.build_authorization(**kwargs)

    def test_different_causal_plan_is_rejected(self) -> None:
        kwargs = self.kwargs()
        kwargs["causal_artifacts"]["plan"]["plan_fingerprint"] = "different-plan"
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "different G16 plan",
            ):
                subject.build_authorization(**kwargs)

    def test_registry_bypass_is_rejected(self) -> None:
        kwargs = self.kwargs()
        kwargs["prepared_authorization"]["lesson_registry_fingerprint"] = "legacy-registry"
        kwargs["causal_artifacts"]["completion"]["lesson_registry_fingerprint"] = "legacy-registry"
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "bypasses counterfactual lineage",
            ):
                subject.build_authorization(**kwargs)

    def test_candidate_set_substitution_is_rejected(self) -> None:
        kwargs = self.kwargs()
        kwargs["prepared_authorization"]["candidate_ids"] = ["manual.candidate"]
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "candidate set differs",
            ):
                subject.build_authorization(**kwargs)

    def test_candidate_evidence_substitution_is_rejected(self) -> None:
        kwargs = self.kwargs()
        first_day = next(iter(kwargs["causal_artifacts"]["plan"]["days"]))
        kwargs["causal_artifacts"]["plan"]["days"][first_day][
            "candidate_evidence_fingerprints"
        ] = {candidate: "after-outcome" for candidate in kwargs["lineage_gate"]["candidate_ids"]}
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "candidate evidence differs",
            ):
                subject.build_authorization(**kwargs)

    def test_authorization_token_must_request_all_counterfactual_candidates(self) -> None:
        kwargs = self.kwargs()
        kwargs["causal_artifacts"]["authorization_stream"]["authorizations"][0][
            "authorized_candidate_ids"
        ] = kwargs["lineage_gate"]["candidate_ids"][:-1]
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "exact counterfactual candidate set",
            ):
                subject.build_authorization(**kwargs)

    def test_unknown_posterior_attribution_candidate_is_rejected(self) -> None:
        kwargs = self.kwargs()
        output = kwargs["causal_artifacts"]["posterior_stream"]["outputs"][0]
        output.setdefault("attribution", []).append(
            {"candidate_id": "post.outcome.injected", "directional_contribution": 0.1}
        )
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            with self.assertRaisesRegex(
                subject.G16CounterfactualCausalAuthorizationError,
                "unregistered candidate",
            ):
                subject.build_authorization(**kwargs)

    def test_lineage_and_prepared_stand_downs_are_unionized(self) -> None:
        kwargs = self.kwargs()
        kwargs["lineage_gate"]["status"] = subject.LINEAGE_STAND_DOWNS
        kwargs["lineage_gate"]["stand_down_days"] = ["2026-03-30"]
        kwargs["prepared_authorization"]["status"] = subject.PREPARED_STAND_DOWNS
        kwargs["prepared_authorization"]["all_stand_down_days"] = ["2026-04-01"]
        with mock.patch.object(subject, "_validate_upstream", return_value=None):
            result = subject.build_authorization(**kwargs)
        self.assertEqual(result["status"], subject.STATUS_STAND_DOWNS)
        self.assertEqual(result["all_stand_down_days"], ["2026-03-30", "2026-04-01"])

    def test_refingerprinted_result_tampering_is_rejected(self) -> None:
        kwargs = self.kwargs()
        result = subject.build_authorization(**kwargs)
        result["g16_registry_fingerprint"] = "replacement-registry"
        self.refingerprint(result)
        with self.assertRaisesRegex(
            subject.G16CounterfactualCausalAuthorizationError,
            "deterministic reconstruction",
        ):
            subject.validate_authorization_artifact(result, **kwargs)

    def test_authority_escalation_is_rejected(self) -> None:
        kwargs = self.kwargs()
        result = subject.build_authorization(**kwargs)
        for field in (
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "random_shuffle_used",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            tampered = copy.deepcopy(result)
            tampered[field] = True
            self.refingerprint(tampered)
            with self.assertRaises(subject.G16CounterfactualCausalAuthorizationError):
                subject.validate_authorization_artifact(tampered, **kwargs)

    def test_shadow_and_tastytrade_controls_are_permanent(self) -> None:
        kwargs = self.kwargs()
        result = subject.build_authorization(**kwargs)
        for field, value in (
            ("cme_event_contracts_mode", "LIVE"),
            ("brokerage_contract", "ibkr"),
        ):
            tampered = copy.deepcopy(result)
            tampered[field] = value
            self.refingerprint(tampered)
            with self.assertRaises(subject.G16CounterfactualCausalAuthorizationError):
                subject.validate_authorization_artifact(tampered, **kwargs)

    def test_output_is_deterministic(self) -> None:
        first = subject.build_authorization(**self.kwargs())
        second = subject.build_authorization(**self.kwargs())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
