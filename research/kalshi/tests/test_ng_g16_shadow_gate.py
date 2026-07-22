import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_blind_wall import G16_DATES, session_decision_cutoff_utc  # noqa: E402
from ng_g16_shadow_gate import (  # noqa: E402
    CANONICAL_DATASET,
    CANONICAL_INSTRUMENT_ID,
    CANONICAL_RAW_SYMBOL,
    G16ShadowGateError,
    _fingerprint,
    _fixture_blind_state,
    _fixture_feature,
    _fixture_forecast,
    _fixture_registry,
    authorize_feature_state,
    authorize_feature_stream,
    build_shadow_plan,
    validate_authorization_token,
    validate_shadow_plan,
)
from ng_rt_feature_state import build_feature_state, feature_fingerprint, validate_feature_state  # noqa: E402


def feature_at(day, event_time, *, instrument_id=CANONICAL_INSTRUMENT_ID,
               raw_symbol=CANONICAL_RAW_SYMBOL, sequence=1):
    operator = {
        "schema": "ng_live_operator.v2",
        "authority": "SHADOW_TELEMETRY",
        "as_of_event_s": float(event_time),
        "move_onset_pressure": {
            "value": 0.7,
            "regime": "transition",
            "activity_ratio": 1.1,
            "price_efficiency": 0.6,
        },
        "signed_flow": {"imb_level": 0.4, "imb_flow": 0.2},
        "divergence_exhaustion": {"expect": "continuation"},
        "mbo_queue": {
            "book_complete": True,
            "snapshot_complete": True,
            "maybe_bad_book": False,
            "consumed_side": "ASK",
            "far_side_recruitment": 0.5,
        },
        "data_quality": {
            "book_complete": True,
            "snapshot_active": False,
            "maybe_bad_book": False,
            "missing_order_events": 0,
            "mapping_flags": [],
            "trade_events_60s": 8,
            "trade_events_15m": 20,
            "complete_mbo_events": 1,
        },
    }
    state = build_feature_state(
        blind_prior={"up": 0.3, "flat": 0.2, "down": 0.5},
        operator_snapshot=operator,
        instrument_identity={
            "dataset": CANONICAL_DATASET,
            "publisher_id": 1,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "definition_date": "2026-03-20",
            "continuous_symbol": "NG.v.0",
            "roll_rule": "kalshi_settlement_proximity",
        },
        decision_cutoff_s=float(event_time),
        horizon="close",
        source_mode="historical_replay",
        sequence=sequence,
    )
    state["session_day"] = day
    state["feature_fingerprint"] = feature_fingerprint(state)
    validate_feature_state(state)
    return state


class G16ShadowPlanTests(unittest.TestCase):
    def setUp(self):
        self.forecast = _fixture_forecast()
        self.blind_state = _fixture_blind_state()
        self.registry = _fixture_registry()

    def test_plan_locks_all_sources_without_mutation(self):
        forecast_before = copy.deepcopy(self.forecast)
        state_before = copy.deepcopy(self.blind_state)
        registry_before = copy.deepcopy(self.registry)
        plan = build_shadow_plan(self.forecast, self.blind_state, self.registry)
        validate_shadow_plan(
            plan,
            blind_forecast=self.forecast,
            blind_safe_state=self.blind_state,
            registry_source=self.registry,
        )
        self.assertEqual(list(plan["days"]), list(G16_DATES))
        self.assertTrue(plan["gate"]["g16_shadow_refinement_authorized"])
        self.assertEqual(self.forecast, forecast_before)
        self.assertEqual(self.blind_state, state_before)
        self.assertEqual(self.registry, registry_before)

    def test_empty_registry_creates_denied_plan(self):
        registry = _fixture_registry()
        registry["candidate_count"] = 0
        registry["candidates"] = []
        registry["gate"]["g16_refinement_authorized"] = False
        registry["registry_fingerprint"] = _fingerprint(
            {key: value for key, value in registry.items() if key != "registry_fingerprint"}
        )
        plan = build_shadow_plan(self.forecast, self.blind_state, registry)
        self.assertFalse(plan["gate"]["g16_shadow_refinement_authorized"])
        with self.assertRaises(G16ShadowGateError):
            authorize_feature_state(plan, _fixture_feature())

    def test_blind_forecast_outcome_field_is_rejected(self):
        forecast = copy.deepcopy(self.forecast)
        forecast["days"][0]["actual_curve"] = [[20, 999]]
        with self.assertRaises(G16ShadowGateError):
            build_shadow_plan(forecast, self.blind_state, self.registry)

    def test_tampered_blind_safe_state_is_rejected(self):
        state = copy.deepcopy(self.blind_state)
        state["days"][G16_DATES[0]]["state"]["future"] = 99
        with self.assertRaises(G16ShadowGateError):
            build_shadow_plan(self.forecast, state, self.registry)

    def test_tampered_registry_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["candidates"][0]["may_update_ng_brain"] = True
        with self.assertRaises(G16ShadowGateError):
            build_shadow_plan(self.forecast, self.blind_state, registry)

    def test_plan_tampering_is_rejected(self):
        plan = build_shadow_plan(self.forecast, self.blind_state, self.registry)
        plan["candidate_ids"].append("unregistered")
        with self.assertRaises(G16ShadowGateError):
            validate_shadow_plan(plan)


class G16FeatureAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_shadow_plan(
            _fixture_forecast(), _fixture_blind_state(), _fixture_registry()
        )

    def test_registered_lesson_authorizes_causal_state(self):
        state = _fixture_feature()
        token = authorize_feature_state(self.plan, state, ["flow_confirmation"])
        validate_authorization_token(token, plan=self.plan, feature_state=state)
        self.assertEqual(token["authorized_candidate_ids"], ["flow_confirmation"])
        self.assertFalse(token["actual_g16_outcomes_used"])
        self.assertFalse(token["execution_authority"])

    def test_baseline_microstructure_state_is_auditable(self):
        token = authorize_feature_state(self.plan, _fixture_feature(), [])
        self.assertTrue(token["baseline_microstructure_only"])
        self.assertEqual(token["authorized_candidate_ids"], [])

    def test_unregistered_lesson_is_rejected(self):
        with self.assertRaises(G16ShadowGateError):
            authorize_feature_state(self.plan, _fixture_feature(), ["hindsight_rule"])

    def test_state_at_or_before_blind_cutoff_is_rejected(self):
        day = G16_DATES[0]
        state = feature_at(day, session_decision_cutoff_utc(day).timestamp() - 1.0)
        with self.assertRaises(G16ShadowGateError):
            authorize_feature_state(self.plan, state, ["flow_confirmation"])

    def test_wrong_contract_is_rejected(self):
        day = G16_DATES[0]
        event_time = session_decision_cutoff_utc(day).timestamp() + 60.0
        state = feature_at(day, event_time, instrument_id=1008, raw_symbol="NGJ26")
        with self.assertRaises(G16ShadowGateError):
            authorize_feature_state(self.plan, state, ["flow_confirmation"])

    def test_authorization_token_tampering_is_rejected(self):
        state = _fixture_feature()
        token = authorize_feature_state(self.plan, state, ["flow_confirmation"])
        token["authorized_candidate_ids"] = ["hindsight_rule"]
        with self.assertRaises(G16ShadowGateError):
            validate_authorization_token(token, plan=self.plan, feature_state=state)

    def test_stream_rejects_backward_sequence(self):
        first = _fixture_feature(sequence=2)
        second = _fixture_feature(sequence=1)
        with self.assertRaises(G16ShadowGateError):
            authorize_feature_stream(self.plan, [first, second])

    def test_stream_authorizes_chronological_days(self):
        first = _fixture_feature(day=G16_DATES[0], sequence=1)
        second = _fixture_feature(day=G16_DATES[1], sequence=1)
        result = authorize_feature_stream(
            self.plan,
            [first, second],
            {
                G16_DATES[0]: ["flow_confirmation"],
                G16_DATES[1]: [],
            },
        )
        self.assertEqual(result["n_authorizations"], 2)
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_g16_blind_prior"])


if __name__ == "__main__":
    unittest.main()
