from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_render_s115 import (  # noqa: E402
    FrankieAgentObject,
    RenderContractError,
    TypedPosterior,
    assert_byte_identical,
)
from frankie_s115 import (  # noqa: E402
    LensBookEntry,
    S115Stop,
    SpecialistOutcome,
    append_lens_book,
    assert_future_absent,
    assert_no_narrative_leak,
    assert_ownership_clean,
    build_specialist_track_records,
    causal_lens_view,
    pin_snapshot,
    validate_compaction,
    verify_snapshot,
)
from frankie_validation_s115 import (  # noqa: E402
    EventScore,
    TrainingSplit,
    ValidationStop,
    compare_arms,
    grade_fj1,
    training_release_gate,
)


class S115Tests(unittest.TestCase):
    def test_a66_ownership_has_no_same_part_collision(self):
        assert_ownership_clean()

    def test_a61_snapshot_detects_tree_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            s = Path(tmp) / "snapshot.json"
            p.write_text('{"a":1}\n', encoding="utf-8")
            pin_snapshot([p], s)
            verify_snapshot(s)
            p.write_text('{"a":2}\n', encoding="utf-8")
            with self.assertRaises(S115Stop):
                verify_snapshot(s)

    def test_a50_known_outcome_language_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "CLAUDE.md"
            p.write_text("held-out head result is already known", encoding="utf-8")
            with self.assertRaises(S115Stop):
                assert_no_narrative_leak([p])

    def test_a68_future_is_absent_not_discouraged(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "E.jsonl"
            append_lens_book(
                book,
                LensBookEntry("E", "2026-08-01", "2026-08-01T20:00:00Z", "e1", {}, {}, ("h1",)),
            )
            append_lens_book(
                book,
                LensBookEntry("E", "2026-08-03", "2026-08-03T20:00:00Z", "e2", {}, {}, ("h2",)),
            )
            view = causal_lens_view(book, lens="E", current_day="2026-08-03")
            self.assertEqual([r["event_id"] for r in view], ["e1"])
            assert_future_absent(view, "2026-08-03")

    def test_a62_is_generated_and_serves_mechanism(self):
        payload = build_specialist_track_records(
            [
                SpecialistOutcome(
                    "B", "e1", "2026-08-01", {"x": 1}, {"x": 2},
                    "weekend_chain_misread", "inherit Friday bridge state", True,
                )
            ]
        )
        self.assertTrue(payload["generated"])
        self.assertFalse(payload["authored"])
        self.assertEqual(
            payload["lenses"]["B"][0]["correction_mechanism"], "inherit Friday bridge state"
        )

    def test_a65_compaction_rejects_load_bearing_change(self):
        full = {"direction": "UP", "magnitude": 100, "fired": ["p1"], "stood_down": []}
        changed = {"direction": "DOWN", "magnitude": 100, "fired": ["p1"], "stood_down": []}
        result = validate_compaction(full=full, changed=changed)
        self.assertEqual(result["verdict"], "REJECT_VIEW_CHANGE")

    def test_a59_render_is_byte_identical_to_canonical_semantics(self):
        templates = {"BLD-1": {"body": "day={DAY}\nrole={X}\n{IF B}: preserve conditional"}}
        slots = {"DAY": ("20260801", "test"), "X": ("B", "test")}
        with mock.patch("spawn.templates", return_value=templates), mock.patch("spawn.slots", return_value=slots):
            agent = FrankieAgentObject("BLD-1", "g99", "20260801", "B")
            assert_byte_identical(agent)
            self.assertIn("{IF B}", agent.render_prompt())

    def test_a59_malformed_posterior_fails_at_write_boundary(self):
        with self.assertRaises(RenderContractError):
            TypedPosterior.from_mapping({"group": "g1"})
        with self.assertRaises(RenderContractError):
            TypedPosterior.from_mapping(
                {
                    "group": "g1", "day": "20260801", "specialist": "B", "direction": "UP",
                    "fired": [], "stood_down": [], "reasoning": "x", "source_hashes": ["h"],
                    "execution_enabled": True,
                }
            )

    @staticmethod
    def score(event_id: str, guess: float) -> EventScore:
        return EventScore(
            event_id, "B", "Mon", guess, 10.0, 0.0, 5.0, 8.0, True,
            5.0, 15.0, False, True, "DERIVED",
        )

    def test_a67_requires_identical_events_and_stays_per_event(self):
        report = compare_arms([self.score("e1", 8)], [self.score("e1", 9)])
        self.assertIsNone(report["pooled_scalar"])
        self.assertEqual(len(report["pairs"]), 1)
        with self.assertRaises(ValidationStop):
            compare_arms([self.score("e1", 8)], [self.score("e2", 9)])

    def test_a69_train_and_head_must_be_disjoint(self):
        with self.assertRaises(ValidationStop):
            TrainingSplit(("e1",), ("e1",), True).validate()

    def test_a69_corpus_only_gain_is_scrapped(self):
        split = TrainingSplit(("e1", "e2"), ("h1",), True)
        label = grade_fj1(edge="model-context", fault_side="context", mode="Context Delivery Failure")
        result = training_release_gate(
            split=split,
            corpus_improved=True,
            heldout_improved=False,
            fj1_labels=[label],
        )
        self.assertEqual(result["verdict"], "SCRAP_RECALL_OR_OVERFIT")


if __name__ == "__main__":
    unittest.main()
