from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_packet_compact_s120 as compact  # noqa: E402


class S120PacketCompactionTests(unittest.TestCase):
    @staticmethod
    def packet() -> dict:
        plays = {
            f"play_{i:02d}": {
                "id": f"play_{i:02d}",
                "call": "preserve this complete canonical argument",
                "trigger": {"field_name_that_must_not_be_truncated": i, "operator": ">="},
                "falsifier": "do not silently remove or rename me",
            }
            for i in range(90)
        }
        return {
            "packet_version": "s120.canary-boundary.1",
            "group": "g18",
            "day": "20260427",
            "specialist": "B",
            "realized_outcome_in_packet": False,
            "brain_view_served": {
                "plays": plays,
                "play_index": {name: {"evaluability": "EVALUABLE"} for name in plays},
                "_frankie_serving": {
                    "canonical_plays_total": 90,
                    "full_plays_served": 90,
                },
            },
            "causal_slice": {
                "long_canonical_field_name": [1, 2, 3],
                "nested": {"another_field_that_must_survive_exactly": "value"},
            },
        }

    def test_compact_round_trip_is_structurally_identical(self):
        packet = self.packet()
        text = compact.compact_packet_json(packet)
        self.assertEqual(json.loads(text), packet)

    def test_compaction_does_not_rename_or_truncate_keys(self):
        packet = self.packet()
        text = compact.compact_packet_json(packet)
        decoded = json.loads(text)
        self.assertIn("long_canonical_field_name", decoded["causal_slice"])
        self.assertIn(
            "another_field_that_must_survive_exactly",
            decoded["causal_slice"]["nested"],
        )
        self.assertIn(
            "field_name_that_must_not_be_truncated",
            decoded["brain_view_served"]["plays"]["play_00"]["trigger"],
        )

    def test_compact_form_is_smaller_than_legacy_pretty_form(self):
        packet = self.packet()
        stats = compact.compaction_stats(packet)
        self.assertTrue(stats["semantic_round_trip_equal"])
        self.assertLess(stats["after_bytes"], stats["before_bytes"])
        self.assertGreater(stats["bytes_saved"], 0)

    def test_full_90_90_brain_invariant_survives(self):
        packet = self.packet()
        text = compact.compact_packet_json(packet)
        proof = compact.assert_frankie_invariants(packet, text)
        self.assertEqual(proof["canonical_plays_total"], 90)
        self.assertEqual(proof["full_play_bodies_served"], 90)
        self.assertTrue(proof["play_index_present"])
        self.assertFalse(proof["realized_outcome_in_packet"])

    def test_invariant_fails_closed_if_a_play_is_dropped(self):
        packet = self.packet()
        packet["brain_view_served"]["plays"].pop("play_89")
        text = compact.compact_packet_json(packet)
        with self.assertRaisesRegex(compact.PacketCompactionError, "full-brain invariant"):
            compact.assert_frankie_invariants(packet, text)


if __name__ == "__main__":
    unittest.main()
