import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_anchor import (  # noqa: E402
    ANCHOR_DAY,
    AnchorError,
    anchor_fingerprint,
    build_anchor,
    validate_anchor,
)
from ng_historical_replay import NORMALIZED_SCHEMA  # noqa: E402
from ng_live_operator import F_LAST  # noqa: E402
from ng_rt_feature_state import build_feature_state  # noqa: E402
from ng_rt_refiner import (  # noqa: E402
    RefineError,
    refine_feature_state,
    refine_stream,
    validate_refine_output,
)


def identity(day=ANCHOR_DAY):
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 1008,
        "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01",
        "session_day": day,
    }


def event(event_type, ts, seq, **kwargs):
    return {
        **identity(),
        "schema": NORMALIZED_SCHEMA,
        "event_type": event_type,
        "ts_event_s": float(ts),
        "source_sequence": int(seq),
        **kwargs,
    }


def anchor_events():
    rows = [event("definition", 1, 1)]
    prices = [3.140, 3.138, 3.136, 3.134, 3.133, 3.132]
    sides = ["A", "A", "B", "A", "A", "B"]
    for index, (price, side) in enumerate(zip(prices, sides), 1):
        rows.append(event("trade", 100 + index * 10, index, price=price, size=2, side=side))
    rows.append(
        event(
            "mbo",
            159,
            1,
            action="A",
            side="B",
            size=10,
            order_id=1,
            price=3.131,
            flags=F_LAST,
        )
    )
    return sorted(
        rows,
        key=lambda row: (
            row["ts_event_s"],
            {"definition": 0, "trade": 1, "mbo": 2}[row["event_type"]],
        ),
    )


def operator_snapshot(*, imb=0.35, imb_flow=0.15, bad_queue=False, no_flow=False, as_of=200.0):
    return {
        "schema": "ng_live_operator.v2",
        "authority": "SHADOW_TELEMETRY",
        "as_of_event_s": as_of,
        "move_onset_pressure": {
            "value": 0.72,
            "regime": "transition",
            "activity_ratio": 1.4,
            "price_efficiency": 0.45,
        },
        "signed_flow": None if no_flow else {"imb_level": imb, "imb_flow": imb_flow},
        "divergence_exhaustion": {"expect": "continuation"},
        "mbo_queue": {
            "book_complete": not bad_queue,
            "snapshot_complete": True,
            "maybe_bad_book": bad_queue,
            "consumed_side": "ASK" if imb >= 0 else "BID",
            "far_side_recruitment": 0.25,
            "bbo": {"best_bid": {"price": 3.131}, "best_ask": {"price": 3.132}},
            "recent_book_deltas": {},
        },
        "data_quality": {
            "trade_events_60s": 20 if not no_flow else 0,
            "trade_events_15m": 200 if not no_flow else 0,
            "complete_mbo_events": 10,
            "missing_order_events": 0,
            "mapping_flags": [],
            "book_complete": not bad_queue,
            "snapshot_active": False,
            "snapshot_complete": True,
            "maybe_bad_book": bad_queue,
        },
    }


def feature_state(*, imb=0.35, bad_queue=False, no_flow=False, as_of=200.0, sequence=1):
    return build_feature_state(
        blind_prior={"up": 0.35, "flat": 0.30, "down": 0.35},
        operator_snapshot=operator_snapshot(
            imb=imb,
            imb_flow=0.15 if imb >= 0 else -0.15,
            bad_queue=bad_queue,
            no_flow=no_flow,
            as_of=as_of,
        ),
        instrument_identity={
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
            "continuous_symbol": "NG.v.0",
            "roll_rule": "kalshi_settlement_proximity",
        },
        decision_cutoff_s=as_of,
        horizon="close",
        source_mode="historical_replay",
        sequence=sequence,
    )


class G15AnchorTests(unittest.TestCase):
    def test_anchor_is_deterministic_and_summarizes_last_hour(self):
        first = build_anchor(anchor_events())
        second = build_anchor(anchor_events())
        validate_anchor(first)
        self.assertEqual(first["anchor_fingerprint"], second["anchor_fingerprint"])
        self.assertEqual(first["prices"]["last"], 3.132)
        self.assertEqual(first["direction"], "down")
        self.assertEqual(first["trade_count"], 6)
        self.assertEqual(first["anchor_fingerprint"], anchor_fingerprint(first))
        self.assertFalse(first["execution_authority"])

    def test_anchor_rejects_non_friday_records(self):
        rows = anchor_events()
        rows[0]["session_day"] = "20260312"
        with self.assertRaises(AnchorError):
            build_anchor(rows)

    def test_anchor_rejects_post_cutoff_evidence(self):
        with self.assertRaises(AnchorError):
            build_anchor(anchor_events(), cutoff_event_s=150.0)


class RTRefinerTests(unittest.TestCase):
    def setUp(self):
        self.anchor = build_anchor(anchor_events())

    def test_buy_flow_shifts_posterior_up_without_mutating_prior(self):
        state = feature_state(imb=0.40)
        original = copy.deepcopy(state["blind_prior"])
        output = refine_feature_state(state, self.anchor)
        validate_refine_output(output)
        self.assertGreater(output["posterior"]["up"], original["up"])
        self.assertEqual(state["blind_prior"], original)
        self.assertEqual(output["status"], "UPDATED")

    def test_sell_flow_shifts_posterior_down(self):
        output = refine_feature_state(feature_state(imb=-0.40), self.anchor)
        self.assertGreater(output["posterior"]["down"], output["blind_prior"]["down"])

    def test_bad_queue_still_allows_valid_trade_flow(self):
        output = refine_feature_state(feature_state(imb=0.40, bad_queue=True), self.anchor)
        self.assertFalse(output["availability"]["queue_update_allowed"])
        self.assertTrue(output["availability"]["flow_update_allowed"])
        self.assertGreater(output["posterior"]["up"], output["blind_prior"]["up"])

    def test_total_stand_down_preserves_blind_prior(self):
        output = refine_feature_state(feature_state(no_flow=True, bad_queue=True), self.anchor)
        self.assertEqual(output["status"], "STAND_DOWN")
        self.assertEqual(output["posterior"], output["blind_prior"])

    def test_state_at_or_before_anchor_is_rejected(self):
        state = feature_state(as_of=float(self.anchor["cutoff_event_s"]))
        with self.assertRaises(AnchorError):
            refine_feature_state(state, self.anchor)

    def test_stream_rejects_backwards_event_time(self):
        later = feature_state(as_of=220.0, sequence=1)
        earlier = feature_state(as_of=210.0, sequence=2)
        with self.assertRaises(RefineError):
            refine_stream([later, earlier], self.anchor)

    def test_output_tampering_is_detected(self):
        output = refine_feature_state(feature_state(), self.anchor)
        output["posterior"]["up"] = 0.99
        with self.assertRaises(RefineError):
            validate_refine_output(output)


if __name__ == "__main__":
    unittest.main()
