import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ng_chronological_validation import (  # noqa: E402
    ChronologicalValidationError,
    G15_DATES,
    G16_DATES,
    _fingerprint,
    _fixture,
    build_chronological_validation,
    validate_chronological_validation,
)


def refresh_output(output):
    output.pop("output_fingerprint", None)
    output["output_fingerprint"] = _fingerprint(output)


def refresh_stream(stream):
    stream.pop("stream_fingerprint", None)
    stream["n_outputs"] = len(stream.get("outputs") or [])
    stream["stream_fingerprint"] = _fingerprint(stream)


def refresh_comparison(comparison):
    for row in comparison["days"]:
        row.pop("comparison_day_fingerprint", None)
        row["comparison_day_fingerprint"] = _fingerprint(row)
    comparison.pop("comparison_fingerprint", None)
    comparison["comparison_fingerprint"] = _fingerprint(comparison)


def refresh_plan(plan):
    for row in plan["days"].values():
        row.pop("day_plan_fingerprint", None)
        row["day_plan_fingerprint"] = _fingerprint(row)
    plan.pop("plan_fingerprint", None)
    plan["plan_fingerprint"] = _fingerprint(plan)


class ChronologicalValidationTests(unittest.TestCase):
    def setUp(self):
        self.adjudication, self.plan, self.stream, self.comparison = _fixture()

    def build(self):
        return build_chronological_validation(
            self.adjudication, self.plan, self.stream, self.comparison
        )

    def test_supported_candidate_advances_only_to_next_shadow_holdout(self):
        result = self.build()
        self.assertEqual(result["block"]["status"], "G16_FORWARD_HOLDOUT_SUPPORTED")
        self.assertEqual(
            result["candidate_results"][0]["status"],
            "G16_FORWARD_HOLDOUT_SUPPORTED",
        )
        self.assertEqual(result["post_g16_shadow_registry"]["candidate_count"], 1)
        self.assertFalse(result["adoption_gate"]["brain_adoption_authorized"])

    def test_fixed_chronology_and_random_shuffle_forbidden(self):
        result = self.build()
        self.assertEqual(result["partition"]["discovery"]["dates"], list(G15_DATES))
        self.assertEqual(result["partition"]["forward_holdout"]["dates"], list(G16_DATES))
        self.assertLess(max(G15_DATES), min(G16_DATES))
        self.assertFalse(result["random_shuffle_used"])
        self.assertFalse(result["random_shuffle_allowed"])
        self.assertFalse(result["block"]["g16_reusable_as_untouched_holdout"])

    def test_counterexamples_block_candidate_and_block(self):
        for row in self.comparison["days"]:
            row["path_mae_improvement_usd"] = -20.0
            row["endpoint_abs_error_improvement_usd"] = -20.0
            row["direction_gain"] = -1
            row["regime_gain"] = -1
        self.comparison["aggregate"].update(
            days_path_mae_improved=0,
            days_path_mae_worsened=len(G16_DATES),
            mean_path_mae_improvement_usd=-20.0,
            mean_net_abs_error_improvement_usd=-20.0,
            net_direction_gain=-len(G16_DATES),
            regime_gain=-len(G16_DATES),
        )
        refresh_comparison(self.comparison)
        result = self.build()
        self.assertEqual(result["block"]["status"], "G16_FORWARD_HOLDOUT_CONTRADICTED")
        self.assertEqual(
            result["candidate_results"][0]["status"],
            "G16_FORWARD_HOLDOUT_CONTRADICTED",
        )
        self.assertEqual(result["post_g16_shadow_registry"]["candidate_count"], 0)

    def test_candidate_not_exercised_cannot_advance(self):
        self.stream["outputs"] = []
        refresh_stream(self.stream)
        result = self.build()
        row = result["candidate_results"][0]
        self.assertEqual(row["status"], "NOT_EXERCISED_G16")
        self.assertEqual(row["sample_size_days"], 0)
        self.assertEqual(result["post_g16_shadow_registry"]["candidate_count"], 0)

    def test_plan_candidate_set_must_equal_g15_registry(self):
        self.plan["candidate_ids"] = ["unregistered"]
        self.plan["candidate_count"] = 1
        for row in self.plan["days"].values():
            row["allowed_candidate_ids"] = ["unregistered"]
        refresh_plan(self.plan)
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_posterior_stream_must_reference_exact_plan(self):
        self.stream["plan_fingerprint"] = "wrong"
        refresh_stream(self.stream)
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_unregistered_attribution_is_rejected(self):
        output = self.stream["outputs"][0]
        output["authorized_candidate_ids"].append("unregistered")
        output["implemented_candidate_ids"].append("unregistered")
        output["attribution"].append(
            {
                "candidate_id": "unregistered",
                "implemented_handler": True,
                "used": True,
                "value": 1,
                "directional_contribution": 0.1,
            }
        )
        refresh_output(output)
        refresh_stream(self.stream)
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_backward_posterior_stream_is_rejected(self):
        self.stream["outputs"][0], self.stream["outputs"][1] = (
            self.stream["outputs"][1],
            self.stream["outputs"][0],
        )
        refresh_stream(self.stream)
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_comparison_tamper_is_rejected(self):
        self.comparison["days"][0]["path_mae_improvement_usd"] = 999
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_adjudication_tamper_is_rejected(self):
        self.adjudication["adjudications"][0]["status"] = "CHANGED"
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_stand_down_cannot_change_prior(self):
        output = self.stream["outputs"][0]
        output["status"] = "STAND_DOWN"
        output["posterior"] = {"up": 0.9, "flat": 0.05, "down": 0.05}
        refresh_output(output)
        refresh_stream(self.stream)
        with self.assertRaises(ChronologicalValidationError):
            self.build()

    def test_sources_remain_immutable(self):
        before = copy.deepcopy(
            (self.adjudication, self.plan, self.stream, self.comparison)
        )
        self.build()
        self.assertEqual(
            (self.adjudication, self.plan, self.stream, self.comparison), before
        )

    def test_validation_artifact_tamper_is_rejected(self):
        result = self.build()
        result["block"]["status"] = "CHANGED"
        with self.assertRaises(ChronologicalValidationError):
            validate_chronological_validation(result)

    def test_candidate_day_sample_counts_unique_days(self):
        duplicate = copy.deepcopy(self.stream["outputs"][0])
        duplicate["sequence"] = 99
        duplicate["as_of_event_s"] = 99.0
        refresh_output(duplicate)
        self.stream["outputs"].insert(1, duplicate)
        refresh_stream(self.stream)
        result = self.build()
        row = result["candidate_results"][0]
        self.assertEqual(row["sample_size_days"], 3)
        self.assertEqual(row["days"][0]["used_outputs"], 2)

    def test_all_authority_gates_remain_disabled(self):
        result = self.build()
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_any_blind_prior"])
        registry = result["post_g16_shadow_registry"]
        self.assertFalse(registry["execution_authority"])
        self.assertFalse(registry["may_update_ng_brain"])
        self.assertFalse(registry["gate"]["brain_adoption_authorized"])


if __name__ == "__main__":
    unittest.main()
