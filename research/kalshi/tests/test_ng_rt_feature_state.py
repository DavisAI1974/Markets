import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_rt_feature_state import (  # noqa: E402
    FeatureStateError,
    assert_transport_parity,
    build_feature_state,
    validate_chronological,
)


class FeatureStateContractTests(unittest.TestCase):
    def setUp(self):
        self.prior = {"up": 0.3, "flat": 0.2, "down": 0.5}
        self.identity = {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 123,
            "raw_symbol": "NGQ6",
            "definition_date": "2026-07-21",
            "continuous_symbol": "NG.v.0",
            "roll_rule": "volume",
        }
        self.operator = {
            "schema": "ng_live_operator.v2",
            "authority": "SHADOW_TELEMETRY",
            "as_of_event_s": 100.0,
            "move_onset_pressure": {
                "value": 0.71,
                "regime": "transition",
                "activity_ratio": 1.4,
                "price_efficiency": 0.42,
            },
            "signed_flow": {"imb_level": -0.31, "imb_flow": -0.18},
            "divergence_exhaustion": {"expect": "continuation"},
            "mbo_queue": {
                "book_complete": True,
                "snapshot_complete": True,
                "maybe_bad_book": False,
                "consumed_side": "BID",
                "far_side_recruitment": -0.22,
                "bbo": {"best_bid": {"price": 3.0}, "best_ask": {"price": 3.001}},
                "recent_book_deltas": {},
            },
            "data_quality": {
                "trade_events_60s": 20,
                "trade_events_15m": 200,
                "complete_mbo_events": 500,
                "missing_order_events": 0,
                "mapping_flags": [],
                "book_complete": True,
                "snapshot_active": False,
                "snapshot_complete": True,
                "maybe_bad_book": False,
            },
        }

    def build(self, *, mode="historical_replay", sequence=1, operator=None, cutoff=100.0):
        return build_feature_state(
            blind_prior=self.prior,
            operator_snapshot=operator or self.operator,
            instrument_identity=self.identity,
            decision_cutoff_s=cutoff,
            horizon="close",
            source_mode=mode,
            sequence=sequence,
        )

    def test_historical_and_live_transport_parity(self):
        historical = self.build(mode="historical_replay")
        live = self.build(mode="live")
        assert_transport_parity(historical, live)
        self.assertEqual(historical["feature_fingerprint"], live["feature_fingerprint"])

    def test_bad_book_stands_down_queue_but_not_trade_flow(self):
        operator = copy.deepcopy(self.operator)
        operator["data_quality"]["maybe_bad_book"] = True
        operator["mbo_queue"]["maybe_bad_book"] = True
        state = self.build(operator=operator)
        self.assertFalse(state["availability"]["queue_update_allowed"])
        self.assertTrue(state["availability"]["flow_update_allowed"])
        self.assertIn("mbo_maybe_bad_book", state["availability"]["stand_down_reasons"])

    def test_future_snapshot_is_rejected(self):
        operator = copy.deepcopy(self.operator)
        operator["as_of_event_s"] = 100.001
        with self.assertRaises(FeatureStateError):
            self.build(operator=operator, cutoff=100.0)

    def test_chronological_replay_rejects_reordering(self):
        first = self.build(sequence=1)
        operator = copy.deepcopy(self.operator)
        operator["as_of_event_s"] = 99.0
        second = self.build(sequence=2, operator=operator)
        with self.assertRaises(FeatureStateError):
            validate_chronological([first, second])

    def test_builder_does_not_mutate_blind_prior(self):
        original = copy.deepcopy(self.prior)
        state = self.build()
        self.assertEqual(self.prior, original)
        state["blind_prior"]["down"] = 0.0
        self.assertEqual(self.prior, original)

    def test_definition_change_cannot_share_one_replay_stream(self):
        first = self.build(sequence=1)
        changed_identity = dict(self.identity)
        changed_identity["definition_date"] = "2026-07-22"
        second = build_feature_state(
            blind_prior=self.prior,
            operator_snapshot=self.operator,
            instrument_identity=changed_identity,
            decision_cutoff_s=100.0,
            horizon="close",
            source_mode="historical_replay",
            sequence=2,
        )
        with self.assertRaises(FeatureStateError):
            validate_chronological([first, second])


if __name__ == "__main__":
    unittest.main()
