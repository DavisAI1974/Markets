#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "ng_refine_coach_voxa_adapter.py"
SPEC = importlib.util.spec_from_file_location("ng_refine_coach_voxa_adapter", MODULE_PATH)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def g15_output(
    *,
    day: str = "2026-03-15",
    sequence: int = 1,
    event_time: float = 1773500000.0,
    status: str = "UPDATED",
    prior: dict | None = None,
    posterior: dict | None = None,
) -> dict:
    blind = prior or {"up": 0.4, "flat": 0.2, "down": 0.4}
    post = posterior or {"up": 0.55, "flat": 0.2, "down": 0.25}
    if status == "STAND_DOWN":
        post = copy.deepcopy(blind)
    value = {
        "schema": "ng_rt_refine_output.v1",
        "source_mode": "historical",
        "session_day": day,
        "sequence": sequence,
        "horizon": "close",
        "as_of_event_s": event_time,
        "authority": "REFINE_POSTERIOR_ONLY",
        "execution_authority": False,
        "blind_prior": copy.deepcopy(blind),
        "blind_prior_fingerprint": "blind-prior",
        "feature_fingerprint": f"feature-{day}-{sequence}",
        "anchor_fingerprint": "anchor",
        "posterior": copy.deepcopy(post),
        "status": status,
        "scores": {
            "directional_log_weight": 0.3,
            "flat_log_weight": 0.0,
            "update_strength": 0.5,
        },
        "attribution": [
            {
                "name": "signed_flow",
                "value": {"imb_level": 0.3},
                "contribution": 0.3,
                "used": status != "STAND_DOWN",
                "note": "causal flow only",
            }
        ],
        "availability": {
            "flow_update_allowed": status != "STAND_DOWN",
            "queue_update_allowed": status != "STAND_DOWN",
            "refine_update_allowed": status != "STAND_DOWN",
            "stand_down_reasons": ["MBO_SEQUENCE_GAP"] if status == "STAND_DOWN" else [],
        },
        "provenance": {
            "blind_artifact_mutated": False,
            "same_contract_for_historical_and_live": True,
        },
    }
    value["output_fingerprint"] = adapter._fp(value)
    return value


def g15_pipeline(outputs: list[dict] | None = None) -> dict:
    rows = outputs or [g15_output()]
    value = {
        "schema": "ng_g15_pipeline.v1",
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_PIPELINE_ONLY",
        "execution_authority": False,
        "refine_stream": {
            "schema": "ng_rt_refine_stream.v1",
            "market": "NG",
            "group": 15,
            "authority": "REFINE_POSTERIOR_STREAM_ONLY",
            "execution_authority": False,
            "anchor_fingerprint": "anchor",
            "n_outputs": len(rows),
            "outputs": copy.deepcopy(rows),
        },
        "daily_audit": {
            "schema": "ng_g15_daily_refine_audit.v1",
            "authority": "REFINE_AUDIT_ONLY",
            "execution_authority": False,
            "outcome_scored": False,
        },
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
    }
    value["pipeline_fingerprint"] = adapter._fp(value)
    return value


def g16_output(
    *,
    day: str = "2026-03-29",
    sequence: int = 1,
    event_time: float = 1774800000.0,
    status: str = "UPDATED",
) -> dict:
    prior = {"up": 0.35, "flat": 0.3, "down": 0.35}
    posterior = {"up": 0.5, "flat": 0.3, "down": 0.2}
    if status == "STAND_DOWN":
        posterior = copy.deepcopy(prior)
    value = {
        "schema": "ng_g16_shadow_posterior.v1",
        "market": "NG",
        "group": 16,
        "session_day": day,
        "sequence": sequence,
        "horizon": "close",
        "as_of_event_s": event_time,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "status": status,
        "blind_prior": prior,
        "posterior": posterior,
        "scores": {
            "directional_log_weight": 0.25,
            "flat_log_weight": 0.0,
            "update_strength": 0.5,
        },
        "attribution": [
            {
                "candidate_id": "g15_mbo.signed_flow",
                "implemented_handler": True,
                "used": status != "STAND_DOWN",
                "value": {"imb_level": 0.2},
                "directional_contribution": 0.25,
            }
        ],
        "authorized_candidate_ids": ["g15_mbo.signed_flow"],
        "implemented_candidate_ids": ["g15_mbo.signed_flow"],
        "unhandled_candidate_ids": [],
        "stand_down_reasons": ["QUEUE_UNAVAILABLE"] if status == "STAND_DOWN" else [],
        "provenance": {
            "plan_fingerprint": "plan",
            "authorization_fingerprint": "auth",
            "feature_fingerprint": f"feature-{day}-{sequence}",
            "blind_prior_fingerprint": "blind",
        },
    }
    value["output_fingerprint"] = adapter._fp(value)
    return value


def g16_sources(outputs: list[dict] | None = None) -> tuple[dict, dict]:
    rows = outputs or [g16_output()]
    stream = {
        "schema": "ng_g16_shadow_posterior_stream.v1",
        "market": "NG",
        "group": 16,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "auth-stream",
        "n_outputs": len(rows),
        "outputs": copy.deepcopy(rows),
    }
    stream["stream_fingerprint"] = adapter._fp(stream)
    completion = {
        "schema": "ng_g16_exact_causal_pipeline.v1",
        "market": "NG",
        "group": 16,
        "status": "READY",
        "authority": "G16_EXACT_HISTORICAL_SHADOW_REFINEMENT_ONLY",
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
        "blind_prior_fingerprint": "blind",
        "blind_forecast_fingerprint": "forecast",
        "blind_safe_state_fingerprint": "safe",
        "lesson_registry_fingerprint": "registry",
        "lesson_adjudication_fingerprint": "adjudication",
        "plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "auth-stream",
        "posterior_stream_fingerprint": stream["stream_fingerprint"],
        "candidate_ids": ["g15_mbo.signed_flow"],
        "candidate_request_policy": "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS",
        "n_states": len(rows),
        "n_outputs": len(rows),
        "n_days": 1,
        "stand_down_days": [],
        "days": {},
        "next_permitted_stage": "OUTCOME_BLIND_G16_CURVE_ADAPTER",
    }
    completion["fingerprint"] = adapter._fp(completion)
    return completion, stream


class CoachVoxaAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.historical = adapter.build_lag_policy(mode="HISTORICAL_REPLAY")

    def test_historical_lag_policy_is_explicit_and_valid(self) -> None:
        value = adapter.validate_lag_policy(self.historical)
        self.assertEqual(value["mode"], "HISTORICAL_REPLAY")
        self.assertIsNone(value["max_event_lag_s"])

    def test_live_policy_requires_positive_threshold(self) -> None:
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_lag_policy(mode="LIVE")
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_lag_policy(mode="LIVE", max_event_lag_s=0)
        value = adapter.build_lag_policy(mode="LIVE", max_event_lag_s=12)
        self.assertEqual(value["max_event_lag_s"], 12.0)

    def test_g15_builds_read_only_voxa_packet(self) -> None:
        result = adapter.build_g15_stream(g15_pipeline(), self.historical)
        self.assertEqual(result["group"], 15)
        self.assertEqual(result["n_packets"], 1)
        packet = result["packets"][0]
        self.assertEqual(packet["posterior_lead"], "up")
        self.assertEqual(packet["coach_status"], "INFORMATIONAL")
        self.assertIn("Informational only", packet["voxa"]["utterance"])
        self.assertIsNone(packet["voxa"]["trade_instruction"])
        self.assertFalse(result["delivery_authority"])

    def test_g16_builds_read_only_voxa_packet(self) -> None:
        completion, stream = g16_sources()
        result = adapter.build_g16_stream(completion, stream, self.historical)
        self.assertEqual(result["group"], 16)
        self.assertEqual(result["source_kind"], adapter.SOURCE_G16)
        self.assertEqual(result["packets"][0]["top_attribution"][0]["name"], "g15_mbo.signed_flow")

    def test_source_stand_down_preserves_blind_and_hides_call(self) -> None:
        result = adapter.build_g15_stream(
            g15_pipeline([g15_output(status="STAND_DOWN")]),
            self.historical,
        )
        packet = result["packets"][0]
        self.assertEqual(packet["coach_status"], "STAND_DOWN")
        self.assertEqual(packet["posterior"], packet["blind_prior"])
        self.assertIsNone(packet["voxa"]["display"]["lead"])
        self.assertIn("standing down", packet["voxa"]["utterance"])

    def test_live_stale_packet_stands_down_and_exposes_lag(self) -> None:
        output = g15_output(event_time=1000.0)
        policy = adapter.build_lag_policy(mode="LIVE", max_event_lag_s=5)
        result = adapter.build_g15_stream(
            g15_pipeline([output]),
            policy,
            observed_at_s=1010.0,
        )
        packet = result["packets"][0]
        self.assertEqual(packet["product_lag"]["status"], "STALE")
        self.assertEqual(packet["coach_status"], "STAND_DOWN")
        self.assertIn("PRODUCT_EVENT_LAG_EXCEEDED", packet["stand_down_reasons"])
        self.assertIsNone(packet["voxa"]["display"]["lead"])

    def test_live_fresh_packet_remains_informational(self) -> None:
        output = g15_output(event_time=1000.0)
        policy = adapter.build_lag_policy(mode="LIVE", max_event_lag_s=5)
        result = adapter.build_g15_stream(
            g15_pipeline([output]),
            policy,
            observed_at_s=1004.0,
        )
        self.assertEqual(result["packets"][0]["product_lag"]["status"], "FRESH")
        self.assertEqual(result["packets"][0]["coach_status"], "INFORMATIONAL")

    def test_live_observed_time_cannot_precede_event(self) -> None:
        output = g15_output(event_time=1000.0)
        policy = adapter.build_lag_policy(mode="LIVE", max_event_lag_s=5)
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g15_stream(g15_pipeline([output]), policy, observed_at_s=999.0)

    def test_outcome_payload_is_rejected_even_when_refingerprinted(self) -> None:
        pipeline = g15_pipeline()
        pipeline["actual"] = {"2026-03-15": 500}
        pipeline["pipeline_fingerprint"] = adapter._fp({k: v for k, v in pipeline.items() if k != "pipeline_fingerprint"})
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g15_stream(pipeline, self.historical)

    def test_g15_pipeline_fingerprint_tampering_is_rejected(self) -> None:
        pipeline = g15_pipeline()
        pipeline["group"] = 99
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g15_stream(pipeline, self.historical)

    def test_g16_completion_stream_substitution_is_rejected(self) -> None:
        completion, stream = g16_sources()
        other = copy.deepcopy(stream)
        other["outputs"][0]["session_day"] = "2026-03-30"
        other["outputs"][0]["output_fingerprint"] = adapter._fp(
            {k: v for k, v in other["outputs"][0].items() if k != "output_fingerprint"}
        )
        other["stream_fingerprint"] = adapter._fp({k: v for k, v in other.items() if k != "stream_fingerprint"})
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g16_stream(completion, other, self.historical)

    def test_source_output_fingerprint_tampering_is_rejected(self) -> None:
        pipeline = g15_pipeline()
        pipeline["refine_stream"]["outputs"][0]["posterior"]["up"] = 0.9
        pipeline["pipeline_fingerprint"] = adapter._fp({k: v for k, v in pipeline.items() if k != "pipeline_fingerprint"})
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g15_stream(pipeline, self.historical)

    def test_source_artifacts_are_not_mutated(self) -> None:
        pipeline = g15_pipeline()
        policy = copy.deepcopy(self.historical)
        before = copy.deepcopy((pipeline, policy))
        adapter.build_g15_stream(pipeline, policy)
        self.assertEqual((pipeline, policy), before)

    def test_stream_tampering_is_rejected_after_refingerprint(self) -> None:
        result = adapter.build_g15_stream(g15_pipeline(), self.historical)
        result["packets"][0]["voxa"]["trade_instruction"] = "BUY"
        result["packets"][0]["packet_fingerprint"] = adapter._fp(
            {k: v for k, v in result["packets"][0].items() if k != "packet_fingerprint"}
        )
        result["stream_fingerprint"] = adapter._fp({k: v for k, v in result.items() if k != "stream_fingerprint"})
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.validate_stream(result)

    def test_authority_escalation_is_rejected(self) -> None:
        result = adapter.build_g15_stream(g15_pipeline(), self.historical)
        result["execution_authority"] = True
        result["stream_fingerprint"] = adapter._fp({k: v for k, v in result.items() if k != "stream_fingerprint"})
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.validate_stream(result)

    def test_duplicate_source_output_is_rejected(self) -> None:
        output = g15_output()
        pipeline = g15_pipeline([output, copy.deepcopy(output)])
        with self.assertRaises(adapter.CoachVoxaAdapterError):
            adapter.build_g15_stream(pipeline, self.historical)

    def test_output_is_deterministic_and_chronological(self) -> None:
        later = g15_output(day="2026-03-16", sequence=2, event_time=2000.0)
        earlier = g15_output(day="2026-03-15", sequence=1, event_time=1000.0)
        pipeline = g15_pipeline([later, earlier])
        first = adapter.build_g15_stream(pipeline, self.historical)
        second = adapter.build_g15_stream(copy.deepcopy(pipeline), copy.deepcopy(self.historical))
        self.assertEqual(first, second)
        self.assertEqual([p["session_day"] for p in first["packets"]], ["2026-03-15", "2026-03-16"])

    def test_permanent_market_controls_remain_locked(self) -> None:
        result = adapter.build_g15_stream(g15_pipeline(), self.historical)
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_issue_trade_instruction"])


if __name__ == "__main__":
    unittest.main()
