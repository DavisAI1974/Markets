import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ng_coach_voxa_adapter as coach  # noqa: E402
import ng_coach_voxa_source_gate as gate  # noqa: E402


def g15_stream(rows=None):
    outputs = rows or [coach._fixture_output(1, {"up": 0.65, "flat": 0.15, "down": 0.20})]
    return {
        "schema": coach.G15_STREAM_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "anchor",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }


def g15_pipeline(stream=None):
    posterior = stream or g15_stream()
    value = {
        "schema": gate.G15_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": gate.G15_AUTHORITY,
        "execution_authority": False,
        "refine_stream": copy.deepcopy(posterior),
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
    }
    value["pipeline_fingerprint"] = gate._fp(value)
    return value


def g16_output(sequence=1, day="20260329", status="UPDATED"):
    prior = {"up": 0.35, "flat": 0.30, "down": 0.35}
    posterior = {"up": 0.55, "flat": 0.25, "down": 0.20}
    if status == "STAND_DOWN":
        posterior = copy.deepcopy(prior)
    value = {
        "schema": coach.G16_OUTPUT_SCHEMA,
        "market": "NG",
        "group": 16,
        "session_day": day,
        "sequence": sequence,
        "horizon": "close",
        "as_of_event_s": float(sequence * 100),
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "status": status,
        "blind_prior": prior,
        "posterior": posterior,
        "scores": {
            "directional_log_weight": 0.4,
            "flat_log_weight": 0.0,
            "update_strength": 0.5,
        },
        "attribution": [
            {
                "candidate_id": "g15_mbo.signed_flow",
                "implemented_handler": True,
                "used": status != "STAND_DOWN",
                "value": {"imb_level": 0.3},
                "directional_contribution": 0.4,
            }
        ],
        "authorized_candidate_ids": ["g15_mbo.signed_flow"],
        "implemented_candidate_ids": ["g15_mbo.signed_flow"],
        "unhandled_candidate_ids": [],
        "stand_down_reasons": ["QUEUE_UNAVAILABLE"] if status == "STAND_DOWN" else [],
        "provenance": {
            "plan_fingerprint": "plan",
            "day_plan_fingerprint": "day-plan",
            "authorization_fingerprint": "auth-token",
            "feature_fingerprint": f"feature-{sequence}",
            "blind_prior_fingerprint": "blind-prior",
            "blind_forecast_day_fingerprint": "blind-day",
        },
    }
    value["output_fingerprint"] = coach._output_fingerprint(value)
    return value


def g16_stream(rows=None):
    outputs = rows or [g16_output()]
    value = {
        "schema": coach.G16_STREAM_SCHEMA,
        "market": "NG",
        "group": 16,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "auth-stream",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    value["stream_fingerprint"] = coach._stream_fingerprint(value)
    return value


def g16_completion(stream=None):
    posterior = stream or g16_stream()
    value = {
        "schema": gate.G16_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "READY",
        "authority": gate.G16_AUTHORITY,
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_select_lessons_from_g16_outcomes": False,
        "replay_fingerprint": "replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "prepared",
        "blind_prior_fingerprint": "blind-prior",
        "blind_forecast_fingerprint": "blind-forecast",
        "blind_safe_state_fingerprint": "blind-safe",
        "lesson_registry_fingerprint": "registry",
        "lesson_adjudication_fingerprint": "adjudication",
        "plan_fingerprint": posterior["plan_fingerprint"],
        "authorization_stream_fingerprint": posterior["authorization_stream_fingerprint"],
        "posterior_stream_fingerprint": posterior["stream_fingerprint"],
        "candidate_ids": ["g15_mbo.signed_flow"],
        "candidate_request_policy": "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS",
        "n_states": len(posterior["outputs"]),
        "n_outputs": len(posterior["outputs"]),
        "n_days": 1,
        "stand_down_days": [],
        "days": {},
        "next_permitted_stage": "OUTCOME_BLIND_G16_CURVE_ADAPTER",
    }
    value["fingerprint"] = gate._fp(value)
    return value


class CoachVoxaSourceGateTests(unittest.TestCase):
    def test_g15_pipeline_binds_exact_embedded_stream(self):
        stream = g15_stream()
        source = g15_pipeline(stream)
        result = gate.build_source_gate(source, stream)
        self.assertEqual(result["group"], 15)
        self.assertEqual(result["source_authorization_fingerprint"], source["pipeline_fingerprint"])
        self.assertEqual(result["status"], gate.STATUS)

    def test_g16_completion_binds_exact_posterior_stream(self):
        stream = g16_stream()
        source = g16_completion(stream)
        result = gate.build_source_gate(source, stream)
        self.assertEqual(result["group"], 16)
        self.assertEqual(result["posterior_stream_fingerprint"], stream["stream_fingerprint"])

    def test_authorized_g15_stream_uses_existing_single_adapter(self):
        stream = g15_stream()
        result = gate.build_authorized_coach_stream(g15_pipeline(stream), stream)
        self.assertEqual(result["schema"], coach.STREAM_SCHEMA)
        self.assertEqual(result["authority"], coach.STREAM_AUTHORITY)
        self.assertEqual(result["source_authorization_status"], gate.STATUS)
        self.assertEqual(result["next_permitted_stage"], gate.NEXT_STAGE)
        self.assertFalse(result["delivery_authority"])

    def test_authorized_g16_stream_is_pre_cutoff_and_outcome_blind(self):
        stream = g16_stream()
        result = gate.build_authorized_coach_stream(g16_completion(stream), stream)
        self.assertEqual(result["group"], 16)
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["paid_live_data_assumed"])
        self.assertFalse(result["may_change_blind_forecast"])

    def test_g15_stream_substitution_rejected_even_after_pipeline_refingerprint(self):
        original = g15_stream()
        source = g15_pipeline(original)
        replacement = g15_stream([coach._fixture_output(2, {"up": 0.20, "flat": 0.15, "down": 0.65})])
        source["pipeline_fingerprint"] = gate._fp(gate._without(source, "pipeline_fingerprint"))
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, replacement)

    def test_g16_stream_substitution_rejected(self):
        original = g16_stream()
        source = g16_completion(original)
        replacement = g16_stream([g16_output(sequence=2, day="20260330")])
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, replacement)

    def test_g16_plan_or_authorization_substitution_rejected(self):
        stream = g16_stream()
        source = g16_completion(stream)
        source["plan_fingerprint"] = "other-plan"
        source["fingerprint"] = gate._fp(gate._without(source, "fingerprint"))
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, stream)

    def test_outcome_payload_rejected_even_after_refingerprint(self):
        stream = g15_stream()
        source = g15_pipeline(stream)
        source["actual"] = {"20260318": 123.0}
        source["pipeline_fingerprint"] = gate._fp(gate._without(source, "pipeline_fingerprint"))
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, stream)

    def test_g16_scoring_flag_rejected(self):
        stream = g16_stream()
        source = g16_completion(stream)
        source["g16_scoring_authorized"] = True
        source["fingerprint"] = gate._fp(gate._without(source, "fingerprint"))
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, stream)

    def test_source_fingerprint_tampering_rejected(self):
        stream = g15_stream()
        source = g15_pipeline(stream)
        source["group"] = 16
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.build_source_gate(source, stream)

    def test_source_inputs_remain_immutable(self):
        stream = g15_stream()
        source = g15_pipeline(stream)
        original = copy.deepcopy((source, stream))
        gate.build_authorized_coach_stream(source, stream)
        self.assertEqual((source, stream), original)

    def test_gate_tampering_rejected_after_refingerprint(self):
        stream = g15_stream()
        value = gate.build_source_gate(g15_pipeline(stream), stream)
        value["brokerage_contract"] = "ibkr"
        value["gate_fingerprint"] = gate._fp(gate._without(value, "gate_fingerprint"))
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.validate_source_gate(value, posterior_stream=stream)

    def test_authorized_stream_tampering_rejected_after_refingerprint(self):
        stream = g15_stream()
        source = g15_pipeline(stream)
        source_gate = gate.build_source_gate(source, stream)
        value = gate.build_authorized_coach_stream(source, stream)
        value["options_lane_started"] = True
        value["stream_fingerprint"] = coach._stream_payload_fingerprint(value)
        with self.assertRaises(gate.CoachVoxaSourceGateError):
            gate.validate_authorized_coach_stream(value, gate=source_gate, posterior_stream=stream)

    def test_stand_down_is_preserved_by_existing_adapter(self):
        output = coach._fixture_output(1, {"up": 0.4, "flat": 0.2, "down": 0.4}, status="STAND_DOWN")
        stream = g15_stream([output])
        result = gate.build_authorized_coach_stream(g15_pipeline(stream), stream)
        self.assertEqual(result["messages"][0]["event_type"], "STAND_DOWN")
        self.assertEqual(result["messages"][0]["posterior"], result["messages"][0]["blind_prior"])

    def test_permanent_controls_remain_locked(self):
        stream = g15_stream()
        result = gate.build_authorized_coach_stream(g15_pipeline(stream), stream)
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecast_immutable"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])
        for field in (
            "execution_authority",
            "delivery_authority",
            "may_update_ng_brain",
            "may_change_posterior",
            "may_change_blind_prior",
            "may_change_blind_forecast",
        ):
            self.assertFalse(result[field])


if __name__ == "__main__":
    unittest.main()
