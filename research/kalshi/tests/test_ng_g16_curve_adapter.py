import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g16_curve_adapter as adapter
from ng_g16_shadow_gate import (
    G16_DATES,
    _fixture_blind_state,
    _fixture_registry,
    build_shadow_plan,
)
from ng_g16_shadow_runner import STREAM_AUTHORITY, STREAM_SCHEMA


def inputs():
    forecast = adapter._fixture_forecast()
    forecast["days"][0]["overnight_gap_usd"] = 125
    plan = build_shadow_plan(forecast, _fixture_blind_state(), _fixture_registry())
    output = adapter._fixture_output(G16_DATES[0], forecast, plan)
    stream = {
        "schema": STREAM_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": STREAM_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan["plan_fingerprint"],
        "authorization_stream_fingerprint": "auth-stream",
        "n_outputs": 1,
        "outputs": [output],
    }
    stream["stream_fingerprint"] = adapter._fingerprint(stream)
    return forecast, plan, stream


def refingerprint_output(output):
    output.pop("output_fingerprint", None)
    output["output_fingerprint"] = adapter._fingerprint(output)


def refingerprint_stream(stream):
    stream.pop("stream_fingerprint", None)
    stream["stream_fingerprint"] = adapter._fingerprint(stream)


class G16CurveAdapterTests(unittest.TestCase):
    def test_positive_posterior_moves_endpoint_up(self):
        forecast, plan, stream = inputs()
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertGreater(result["days"][0]["guessed_net_usd"], forecast["days"][0]["guessed_net_usd"])

    def test_negative_posterior_moves_endpoint_down(self):
        forecast, plan, stream = inputs()
        output = stream["outputs"][0]
        output["posterior"] = {"up": 0.1, "flat": 0.1, "down": 0.8}
        refingerprint_output(output)
        refingerprint_stream(stream)
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertLess(result["days"][0]["guessed_net_usd"], forecast["days"][0]["guessed_net_usd"])

    def test_evidence_changes_only_future_grid_points(self):
        forecast, plan, stream = inputs()
        output = stream["outputs"][0]
        output["as_of_event_s"] = adapter._session_grid(G16_DATES[0])[7] - 1
        refingerprint_output(output)
        refingerprint_stream(stream)
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertEqual(result["days"][0]["guess_curve"][:7], forecast["days"][0]["guess_curve"][:7])

    def test_stand_down_preserves_blind_curve(self):
        forecast, plan, stream = inputs()
        output = stream["outputs"][0]
        output["status"] = "STAND_DOWN"
        output["posterior"] = copy.deepcopy(output["blind_prior"])
        refingerprint_output(output)
        refingerprint_stream(stream)
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertEqual(result["days"][0]["guess_curve"], forecast["days"][0]["guess_curve"])

    def test_overnight_gap_and_open_are_immutable(self):
        forecast, plan, stream = inputs()
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertEqual(result["days"][0]["overnight_gap_usd"], 125)
        self.assertEqual(result["days"][0]["guess_curve"][0][1], 0)

    def test_source_forecast_is_immutable(self):
        forecast, plan, stream = inputs()
        before = copy.deepcopy(forecast)
        adapter.build_refined_forecast(forecast, plan, stream)
        self.assertEqual(forecast, before)

    def test_plan_forecast_mismatch_is_rejected(self):
        forecast, plan, stream = inputs()
        plan["blind_forecast_fingerprint"] = "wrong"
        plan.pop("plan_fingerprint", None)
        plan["plan_fingerprint"] = adapter._fingerprint(plan)
        stream["plan_fingerprint"] = plan["plan_fingerprint"]
        refingerprint_stream(stream)
        with self.assertRaises(adapter.G16CurveError):
            adapter.build_refined_forecast(forecast, plan, stream)

    def test_stream_tampering_is_rejected(self):
        forecast, plan, stream = inputs()
        stream["n_outputs"] = 2
        with self.assertRaises(adapter.G16CurveError):
            adapter.build_refined_forecast(forecast, plan, stream)

    def test_output_tampering_is_rejected(self):
        forecast, plan, stream = inputs()
        stream["outputs"][0]["posterior"]["up"] = 0.99
        refingerprint_stream(stream)
        with self.assertRaises(adapter.G16CurveError):
            adapter.build_refined_forecast(forecast, plan, stream)

    def test_day_plan_provenance_mismatch_is_rejected(self):
        forecast, plan, stream = inputs()
        output = stream["outputs"][0]
        output["provenance"]["day_plan_fingerprint"] = "wrong"
        refingerprint_output(output)
        refingerprint_stream(stream)
        with self.assertRaises(adapter.G16CurveError):
            adapter.build_refined_forecast(forecast, plan, stream)

    def test_backward_stream_is_rejected(self):
        forecast, plan, stream = inputs()
        first = stream["outputs"][0]
        second = copy.deepcopy(first)
        second["sequence"] = 2
        second["as_of_event_s"] = first["as_of_event_s"] - 60
        refingerprint_output(second)
        stream["outputs"].append(second)
        stream["n_outputs"] = 2
        refingerprint_stream(stream)
        with self.assertRaises(adapter.G16CurveError):
            adapter.build_refined_forecast(forecast, plan, stream)

    def test_adjustment_cap_is_enforced(self):
        forecast, plan, stream = inputs()
        output = stream["outputs"][0]
        output["posterior"] = {"up": 1.0, "flat": 0.0, "down": 0.0}
        refingerprint_output(output)
        refingerprint_stream(stream)
        config = adapter.CurveConfig(max_adjustment_fraction=0.10)
        result = adapter.build_refined_forecast(forecast, plan, stream, config=config)
        audit = result["days"][0]["refinement_audit"]
        self.assertLessEqual(audit["max_abs_curve_adjustment_usd"], 30)

    def test_artifact_tampering_is_rejected(self):
        forecast, plan, stream = inputs()
        result = adapter.build_refined_forecast(forecast, plan, stream)
        result["days"][0]["guess_curve"][-1][1] += 1
        with self.assertRaises(adapter.G16CurveError):
            adapter.validate_refined_forecast(result, blind_forecast=forecast)

    def test_days_without_outputs_are_unchanged(self):
        forecast, plan, stream = inputs()
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertEqual(result["days"][1]["guess_curve"], forecast["days"][1]["guess_curve"])

    def test_authority_gates_remain_disabled(self):
        forecast, plan, stream = inputs()
        result = adapter.build_refined_forecast(forecast, plan, stream)
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["actual_g16_outcomes_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_g16_blind_prior"])


if __name__ == "__main__":
    unittest.main()
