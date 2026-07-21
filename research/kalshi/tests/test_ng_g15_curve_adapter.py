import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_curve_adapter import (  # noqa: E402
    CurveConfig,
    CurveError,
    GRID_HOURS,
    SCHEMA,
    _session_grid,
    build_refined_forecast,
    validate_refined_forecast,
)
from ng_historical_manifest import G15_DATES  # noqa: E402
from ng_rt_refiner import output_fingerprint  # noqa: E402


def blind_forecast():
    return {
        "group": 15,
        "tag": "g15",
        "brain_version": "s102.1",
        "days": [
            {
                "date": day,
                "dow": "X",
                "overnight_gap_usd": 25,
                "guess_curve": [[hour, -25 * index] for index, hour in enumerate(GRID_HOURS)],
                "guessed_net_usd": -300,
            }
            for day in G15_DATES
        ],
    }


def refine_output(day, *, posterior=None, status="UPDATED", event_index=7, sequence=1, allowed=True):
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    output = {
        "schema": "ng_rt_refine_output.v1",
        "source_mode": "historical_replay",
        "session_day": day,
        "sequence": sequence,
        "horizon": "close",
        "as_of_event_s": _session_grid(day)[event_index] - 60,
        "authority": "REFINE_POSTERIOR_ONLY",
        "execution_authority": False,
        "blind_prior": prior,
        "blind_prior_fingerprint": "blind",
        "feature_fingerprint": f"feature-{day}-{sequence}",
        "anchor_fingerprint": "anchor",
        "posterior": posterior or {"up": 0.7, "flat": 0.1, "down": 0.2},
        "status": status,
        "scores": {
            "directional_log_weight": 0.2,
            "flat_log_weight": 0.0,
            "update_strength": 1.0,
        },
        "attribution": [],
        "availability": {
            "flow_update_allowed": allowed,
            "queue_update_allowed": allowed,
            "refine_update_allowed": allowed,
            "stand_down_reasons": [] if allowed else ["fixture_stand_down"],
        },
        "provenance": {
            "feature_schema": "ng_rt_feature_state.v1",
            "anchor_schema": "ng_g15_anchor.v1",
            "blind_artifact_mutated": False,
            "same_contract_for_historical_and_live": True,
            "threshold_status": "SHADOW_UNTIL_WALK_FORWARD_CALIBRATION",
        },
    }
    output["output_fingerprint"] = output_fingerprint(output)
    return output


def stream(outputs):
    return {
        "schema": "ng_rt_refine_stream.v1",
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "anchor",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }


class CurveAdapterTests(unittest.TestCase):
    def test_positive_posterior_lifts_only_future_curve_points(self):
        blind = blind_forecast()
        result = build_refined_forecast(blind, stream([refine_output(G15_DATES[0], event_index=7)]))
        source = blind["days"][0]
        refined = result["days"][0]
        self.assertEqual(refined["guess_curve"][:7], source["guess_curve"][:7])
        self.assertGreater(refined["guessed_net_usd"], source["guessed_net_usd"])
        self.assertEqual(refined["overnight_gap_usd"], source["overnight_gap_usd"])
        self.assertEqual(refined["guess_curve"][0][1], 0)

    def test_negative_posterior_lowers_future_curve(self):
        blind = blind_forecast()
        output = refine_output(
            G15_DATES[0], posterior={"up": 0.15, "flat": 0.1, "down": 0.75}
        )
        result = build_refined_forecast(blind, stream([output]))
        self.assertLess(result["days"][0]["guessed_net_usd"], blind["days"][0]["guessed_net_usd"])

    def test_stand_down_does_not_change_curve(self):
        blind = blind_forecast()
        output = refine_output(G15_DATES[0], status="STAND_DOWN", allowed=False)
        result = build_refined_forecast(blind, stream([output]))
        self.assertEqual(result["days"][0]["guess_curve"], blind["days"][0]["guess_curve"])
        self.assertEqual(result["days"][0]["refinement_audit"]["outputs_used"], 0)

    def test_blind_object_remains_immutable(self):
        blind = blind_forecast()
        before = copy.deepcopy(blind)
        build_refined_forecast(blind, stream([refine_output(G15_DATES[0])]))
        self.assertEqual(blind, before)

    def test_adjustment_is_capped_by_explicit_fraction(self):
        blind = blind_forecast()
        output = refine_output(
            G15_DATES[0], posterior={"up": 1.0, "flat": 0.0, "down": 0.0}
        )
        result = build_refined_forecast(
            blind,
            stream([output]),
            config=CurveConfig(max_adjustment_fraction=0.10),
        )
        audit = result["days"][0]["refinement_audit"]
        self.assertLessEqual(
            abs(audit["endpoint_adjustment_usd"]),
            audit["blind_scale_usd"] * 0.10 + 1,
        )

    def test_event_outside_session_is_rejected(self):
        output = refine_output(G15_DATES[0])
        output["as_of_event_s"] = _session_grid(G15_DATES[0])[-1] + 3 * 3600
        output["output_fingerprint"] = output_fingerprint(output)
        with self.assertRaises(CurveError):
            build_refined_forecast(blind_forecast(), stream([output]))

    def test_stream_must_be_chronological(self):
        later = refine_output(G15_DATES[1], sequence=1)
        earlier = refine_output(G15_DATES[0], sequence=2)
        with self.assertRaises(CurveError):
            build_refined_forecast(blind_forecast(), stream([later, earlier]))

    def test_missing_or_reordered_g15_day_is_rejected(self):
        blind = blind_forecast()
        blind["days"] = blind["days"][:-1]
        with self.assertRaises(CurveError):
            build_refined_forecast(blind, stream([]))

    def test_fingerprint_detects_tampering(self):
        result = build_refined_forecast(
            blind_forecast(), stream([refine_output(G15_DATES[0])])
        )
        self.assertEqual(result["schema"], SCHEMA)
        result["days"][0]["guessed_net_usd"] += 1
        with self.assertRaises(CurveError):
            validate_refined_forecast(result)

    def test_same_inputs_are_deterministic(self):
        blind = blind_forecast()
        updates = stream([refine_output(G15_DATES[0])])
        first = build_refined_forecast(blind, updates)
        second = build_refined_forecast(blind, updates)
        self.assertEqual(first["artifact_fingerprint"], second["artifact_fingerprint"])
        self.assertEqual(first, second)

    def test_no_actual_outcomes_or_execution_authority(self):
        result = build_refined_forecast(blind_forecast(), stream([]))
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["may_update_ng_brain"])

    def test_invalid_config_is_rejected(self):
        with self.assertRaises(CurveError):
            build_refined_forecast(
                blind_forecast(), stream([]), config=CurveConfig(max_adjustment_fraction=1.1)
            )


if __name__ == "__main__":
    unittest.main()
