import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g16_shadow_gate as gate
from ng_rt_feature_state import feature_fingerprint
from ng_g16_shadow_runner import (
    G16ShadowRunnerError,
    run_state,
    run_stream,
    validate_output,
)


def inputs(candidate="g15_mbo.signed_flow", requested=True):
    forecast = gate._fixture_forecast()
    registry = gate._fixture_registry()
    registry["candidates"][0]["proposal_id"] = candidate
    registry["candidates"][0]["mechanism"] = candidate
    registry.pop("registry_fingerprint", None)
    registry["registry_fingerprint"] = gate._fingerprint(registry)
    plan = gate.build_shadow_plan(forecast, gate._fixture_blind_state(), registry)
    state = gate._fixture_feature()
    token = gate.authorize_feature_state(plan, state, [candidate] if requested else [])
    return forecast, plan, state, token


def stand_down(state):
    result = copy.deepcopy(state)
    result["availability"] = {
        "flow_update_allowed": False,
        "queue_update_allowed": False,
        "refine_update_allowed": False,
        "stand_down_reasons": ["fixture_stand_down"],
    }
    result["feature_fingerprint"] = feature_fingerprint(result)
    return result


class G16ShadowRunnerTests(unittest.TestCase):
    def test_signed_flow_moves_posterior_up(self):
        forecast, plan, state, token = inputs()
        output = run_state(plan, forecast, state, token)
        self.assertEqual(output["status"], "UPDATED")
        self.assertGreater(output["posterior"]["up"], output["blind_prior"]["up"])
        self.assertLess(output["posterior"]["down"], output["blind_prior"]["down"])

    def test_unhandled_registered_lesson_contributes_zero(self):
        forecast, plan, state, token = inputs("future.registered.lesson")
        output = run_state(plan, forecast, state, token)
        self.assertEqual(output["posterior"], output["blind_prior"])
        self.assertEqual(output["unhandled_candidate_ids"], ["future.registered.lesson"])
        self.assertFalse(output["attribution"][0]["implemented_handler"])

    def test_recruitment_handler_uses_complete_queue(self):
        forecast, plan, state, token = inputs("g15_mbo.far_side_recruitment")
        output = run_state(plan, forecast, state, token)
        self.assertGreater(output["posterior"]["up"], output["blind_prior"]["up"])
        self.assertTrue(output["attribution"][0]["used"])

    def test_divergence_handler_uses_continuation(self):
        forecast, plan, state, token = inputs("g15_mbo.divergence_exhaustion")
        output = run_state(plan, forecast, state, token)
        self.assertGreater(output["posterior"]["up"], output["blind_prior"]["up"])

    def test_stand_down_preserves_prior(self):
        forecast, plan, state, _ = inputs()
        state = stand_down(state)
        token = gate.authorize_feature_state(plan, state, ["g15_mbo.signed_flow"])
        output = run_state(plan, forecast, state, token)
        self.assertEqual(output["status"], "STAND_DOWN")
        self.assertEqual(output["posterior"], output["blind_prior"])
        self.assertEqual(output["scores"]["update_strength"], 0.0)

    def test_queue_lesson_contributes_zero_when_queue_unavailable(self):
        forecast, plan, state, _ = inputs("g15_mbo.far_side_recruitment")
        state = copy.deepcopy(state)
        state["availability"]["queue_update_allowed"] = False
        state["availability"]["stand_down_reasons"] = ["mbo_maybe_bad_book"]
        state["feature_fingerprint"] = feature_fingerprint(state)
        token = gate.authorize_feature_state(plan, state, ["g15_mbo.far_side_recruitment"])
        output = run_state(plan, forecast, state, token)
        self.assertFalse(output["attribution"][0]["used"])
        self.assertEqual(output["attribution"][0]["directional_contribution"], 0.0)

    def test_token_feature_mismatch_is_rejected(self):
        forecast, plan, state, token = inputs()
        other = copy.deepcopy(state)
        other["sequence"] += 1
        other["feature_fingerprint"] = feature_fingerprint(other)
        with self.assertRaises(Exception):
            run_state(plan, forecast, other, token)

    def test_plan_forecast_mismatch_is_rejected(self):
        forecast, plan, state, token = inputs()
        changed = copy.deepcopy(forecast)
        changed["days"][0]["guess_curve"][0][1] = 99
        with self.assertRaises(G16ShadowRunnerError):
            run_state(plan, changed, state, token)

    def test_sources_remain_immutable(self):
        forecast, plan, state, token = inputs()
        before = copy.deepcopy((forecast, plan, state, token))
        run_state(plan, forecast, state, token)
        self.assertEqual((forecast, plan, state, token), before)

    def test_output_tampering_is_rejected(self):
        forecast, plan, state, token = inputs()
        output = run_state(plan, forecast, state, token)
        output["posterior"]["up"] += 0.01
        with self.assertRaises(G16ShadowRunnerError):
            validate_output(output)

    def test_chronological_stream_runs(self):
        forecast, plan, first, _ = inputs()
        second = gate._fixture_feature(sequence=2)
        auth = gate.authorize_feature_stream(
            plan, [first, second],
            {first["session_day"]: ["g15_mbo.signed_flow"]},
        )
        result = run_stream(plan, forecast, [first, second], auth)
        self.assertEqual(result["n_outputs"], 2)
        self.assertFalse(result["actual_g16_outcomes_used"])

    def test_tampered_authorization_stream_is_rejected(self):
        forecast, plan, state, _ = inputs()
        auth = gate.authorize_feature_stream(plan, [state])
        auth["n_authorizations"] = 2
        with self.assertRaises(G16ShadowRunnerError):
            run_stream(plan, forecast, [state], auth)

    def test_output_never_grants_brain_or_execution_authority(self):
        forecast, plan, state, token = inputs()
        output = run_state(plan, forecast, state, token)
        self.assertFalse(output["actual_g16_outcomes_used"])
        self.assertFalse(output["may_update_ng_brain"])
        self.assertFalse(output["may_change_g16_blind_prior"])
        self.assertFalse(output["execution_authority"])


if __name__ == "__main__":
    unittest.main()
