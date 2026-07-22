import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ng_coach_voxa_adapter as c  # noqa: E402


def out(seq, probs, status="UPDATED", reasons=()):
    row = c._fixture_output(seq, probs, status=status)
    row["availability"]["stand_down_reasons"] = list(reasons)
    row["output_fingerprint"] = c._output_fingerprint(row)
    return row


def stream(rows):
    return {
        "schema": c.G15_STREAM_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": "a",
        "n_outputs": len(rows),
        "outputs": rows,
    }


def lag(status=c.MEASURED, as_of=99.0):
    key = {
        "venue": "kalshi", "product": "NG event contract", "series": "KXNG",
        "contract": "KXNG-X", "strike": "3.25", "liquidity_bucket": "medium",
        "move_size_bucket": "small", "time_of_day_bucket": "us_morning",
        "regime": "shoulder",
    }
    row = {
        "schema": c.LAG_SCHEMA, "authority": c.LAG_AUTHORITY, "status": status,
        "key": key, "key_fingerprint": c._fp(key), "as_of_s": as_of,
        "strictly_pre_cutoff": True, "minimum_samples": 5,
        "exact_key_observations": 6,
        "eligible_pre_cutoff_observations": 6 if status == c.MEASURED else 0,
        "first_reprice_window": (
            {"min_ms": 80, "p25_ms": 90, "p50_ms": 110, "p75_ms": 130, "p90_ms": 150, "max_ms": 180}
            if status == c.MEASURED else None
        ),
        "completion_window": None,
        "reasons": [] if status == c.MEASURED else ["NO_EXACT_KEY_HISTORY"],
        "observation_fingerprints": ["o"] if status == c.MEASURED else [],
        "registry_fingerprint": "r", "fallback_used": False,
        "execution_authority": False, "may_update_ng_brain": False,
    }
    row["fingerprint"] = c._fp(row)
    return row


def attach(output, lookup):
    return {"attachments": [{"posterior_output_fingerprint": output["output_fingerprint"], "lookup": lookup}]}


class CoachTests(unittest.TestCase):
    def test_material_only_and_direction_change(self):
        rows = [
            out(1, {"up": .66, "flat": .14, "down": .20}),
            out(2, {"up": .67, "flat": .13, "down": .20}),
            out(3, {"up": .20, "flat": .13, "down": .67}),
        ]
        result = c.build_coach_stream(stream(rows))
        self.assertEqual([m["event_type"] for m in result["messages"]], ["INITIAL_UPDATE", "DIRECTION_CHANGE"])
        self.assertEqual(result["n_suppressed"], 1)
        self.assertEqual(result["messages"][1]["invalidates_message_fingerprint"], result["messages"][0]["message_fingerprint"])

    def test_invalidation_without_flip(self):
        result = c.build_coach_stream(stream([
            out(1, {"up": .70, "flat": .10, "down": .20}),
            out(2, {"up": .53, "flat": .20, "down": .27}),
        ]))
        self.assertEqual(result["messages"][1]["event_type"], "INVALIDATION")

    def test_stand_down_reason_change_and_recovery(self):
        prior = {"up": .4, "flat": .2, "down": .4}
        result = c.build_coach_stream(stream([
            out(1, prior, "STAND_DOWN", ["gap"]),
            out(2, prior, "STAND_DOWN", ["book"]),
            out(3, {"up": .61, "flat": .14, "down": .25}),
        ]))
        self.assertEqual([m["event_type"] for m in result["messages"]], ["STAND_DOWN", "STAND_DOWN", "RECOVERY"])

    def test_exact_lag_and_no_window_are_truthful(self):
        first = out(1, {"up": .66, "flat": .14, "down": .20})
        measured = c.build_coach_stream(stream([first]), lag_attachments=attach(first, lag()))
        self.assertTrue(measured["messages"][0]["lag"]["timing_claim_allowed"])
        second = out(1, {"up": .66, "flat": .14, "down": .20})
        missing = c.build_coach_stream(stream([second]), lag_attachments=attach(second, lag(c.NO_WINDOW)))
        self.assertFalse(missing["messages"][0]["lag"]["timing_claim_allowed"])
        self.assertIn("no follower timing claim", missing["messages"][0]["speech_text"])

    def test_lag_after_posterior_and_unknown_attachment_rejected(self):
        row = out(1, {"up": .66, "flat": .14, "down": .20})
        with self.assertRaises(c.CoachAdapterError):
            c.build_coach_stream(stream([row]), lag_attachments=attach(row, lag(as_of=101)))
        bad = attach(row, lag())
        bad["attachments"][0]["posterior_output_fingerprint"] = "unknown"
        with self.assertRaises(c.CoachAdapterError):
            c.build_coach_stream(stream([row]), lag_attachments=bad)

    def test_incremental_dedupe_uses_suppressed_terminal_state(self):
        first = [
            out(1, {"up": .65, "flat": .15, "down": .20}),
            out(2, {"up": .66, "flat": .14, "down": .20}),
        ]
        previous = c.build_coach_stream(stream(first))
        result = c.build_coach_stream(
            stream(first + [out(3, {"up": .67, "flat": .13, "down": .20})]),
            previous_stream=previous,
        )
        self.assertEqual(result["n_messages"], 0)
        self.assertEqual(result["terminal_state_by_day"]["20260318"]["sequence"], 3)

    def test_sources_immutable_and_tampering_detected(self):
        row = out(1, {"up": .66, "flat": .14, "down": .20})
        source = stream([row])
        original = copy.deepcopy(source)
        result = c.build_coach_stream(source)
        self.assertEqual(source, original)
        bad = copy.deepcopy(result["messages"][0])
        bad["speech_text"] = "changed"
        with self.assertRaises(c.CoachAdapterError):
            c.validate_message(bad)
        result["n_messages"] = 7
        with self.assertRaises(c.CoachAdapterError):
            c.validate_coach_stream(result)

    def test_chronology_enforced(self):
        rows = [
            out(2, {"up": .66, "flat": .14, "down": .20}),
            out(1, {"up": .67, "flat": .13, "down": .20}),
        ]
        rows[0]["as_of_event_s"] = 200
        rows[0]["output_fingerprint"] = c._output_fingerprint(rows[0])
        rows[1]["as_of_event_s"] = 100
        rows[1]["output_fingerprint"] = c._output_fingerprint(rows[1])
        with self.assertRaises(c.CoachAdapterError):
            c.build_coach_stream(stream(rows))

    def test_no_delivery_execution_or_signal_authority(self):
        result = c.build_coach_stream(stream([out(1, {"up": .66, "flat": .14, "down": .20})]))
        self.assertTrue(result["one_signal_authority_preserved"])
        for field in ("delivery_authority", "execution_authority", "may_update_ng_brain", "may_change_posterior", "may_change_blind_prior"):
            self.assertFalse(result[field])
        self.assertEqual(result["messages"][0]["voxa_payload"]["transport_status"], "ADAPTER_ONLY_NOT_SENT")


if __name__ == "__main__":
    unittest.main()
