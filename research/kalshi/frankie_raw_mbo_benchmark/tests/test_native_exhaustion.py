"""Tests for section 4.10 exhaustion runways."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_exhaustion import (
    ENDPOINT_CONFIRMATION,
    ENDPOINT_ONSET,
    T0,
    UNMARKED,
    ExhaustionCalculator,
    ExhaustionError,
    open_world_state_id,
    resolve_state_id,
)


def open_kwargs(**overrides):
    base = dict(
        candidate_id="c1",
        instrument_id=42,
        side="B",
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="TFCN",
        session_phase="RTH",
        searched_coverage_ns=10_000,
        opened_recv_ns=1_000,
        seed_state="P",
    )
    base.update(overrides)
    return base


class StateIdentityTest(unittest.TestCase):
    def test_seeds_pass_through(self) -> None:
        self.assertEqual(resolve_state_id("P", []), "P")

    def test_unmatched_states_get_a_deterministic_open_world_id(self) -> None:
        first = resolve_state_id(None, ["AN", "TFM", "TFCN"])
        second = resolve_state_id(None, ["AN", "TFM", "TFCN"])
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("OW_"))

    def test_different_shapes_get_different_ids(self) -> None:
        self.assertNotEqual(open_world_state_id(["AN"]), open_world_state_id(["AN", "TFM"]))

    def test_a_non_seed_label_is_refused_rather_than_silently_accepted(self) -> None:
        with self.assertRaises(ExhaustionError):
            resolve_state_id("Q", ["AN"])

    def test_an_empty_shape_cannot_make_an_id(self) -> None:
        with self.assertRaises(ExhaustionError):
            open_world_state_id([])


class RunwayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = ExhaustionCalculator()

    def test_landmarks_advance_and_cannot_go_backwards(self) -> None:
        self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_100)
        self.calc.mark_landmark("c1", ENDPOINT_ONSET, 1_500)
        with self.assertRaises(ExhaustionError):
            self.calc.mark_landmark("c1", T0, 1_600)

    def test_remarking_the_same_landmark_is_refused(self) -> None:
        self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_500)
        with self.assertRaises(ExhaustionError):
            self.calc.mark_landmark("c1", T0, 1_600)

    def test_unknown_landmark_is_refused(self) -> None:
        self.calc.open_runway(**open_kwargs())
        with self.assertRaises(ExhaustionError):
            self.calc.mark_landmark("c1", "VIBES", 1_100)

    def test_the_eleven_invented_phase_names_are_gone(self) -> None:
        """Four of them were reused for a different referent, which reads as continuity."""
        from research.kalshi.frankie_raw_mbo_benchmark import native_exhaustion as ex

        for name in (
            "SEARCHED", "PRECURSOR", "PREBIRTH", "FIRST_DEVIATION", "BIRTH", "TRANSITION",
            "INFLECTION", "PERSISTENCE", "EXTENSION", "COMPLETION", "REVERSAL",
            "PHASE_ORDER", "PHASE_INDEX", "RunwayPhase", "register_discovered_phase",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ex, name))

    def test_birth_is_the_onset_and_is_absent_when_never_marked(self) -> None:
        """The negative case - a boundary with no birth - has to be representable."""
        runway = self.calc.open_runway(**open_kwargs())
        self.assertIsNone(runway.birth_recv_ns)
        self.calc.mark_landmark("c1", T0, 1_400)
        self.assertEqual(runway.birth_recv_ns, 1_400)
        self.calc.mark_landmark("c1", ENDPOINT_ONSET, 1_800)
        self.assertEqual(runway.birth_recv_ns, 1_400, "confirmation never overwrites onset")

    def test_a_runway_with_no_birth_still_closes_and_says_so(self) -> None:
        self.calc.open_runway(**open_kwargs())
        row = self.calc.finalize(recv_ns=9_000)[0]
        self.assertFalse(row["birth_marked"])
        self.assertIsNone(row["birth_recv_ns"])

    def test_completed_duration_is_not_readable_before_completion(self) -> None:
        """Section 4.10 forbids a completed duration at an earlier causal cutoff."""
        runway = self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_500)
        with self.assertRaises(ExhaustionError):
            _ = runway.completed_duration_ns
        self.assertEqual(runway.causal_age_ns(2_000), 1_000, "elapsed age is always lawful")

    def test_completed_duration_becomes_readable_after_completion(self) -> None:
        runway = self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_500)
        self.calc.complete("c1", recv_ns=4_000)
        self.assertEqual(runway.completed_duration_ns, 3_000)

    def test_a_censored_runway_never_exposes_a_completed_duration(self) -> None:
        runway = self.calc.open_runway(**open_kwargs())
        self.calc.finalize(recv_ns=9_000)
        with self.assertRaises(ExhaustionError):
            _ = runway.completed_duration_ns

    def test_the_landmark_is_part_of_the_stratum_so_segments_never_pool(self) -> None:
        self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_100)
        self.calc.mark_landmark("c1", ENDPOINT_ONSET, 1_500)
        self.calc.complete("c1", recv_ns=3_000)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.segment_duration.rows()}
        self.assertIn("state=P|landmark=T0", subfamilies)
        self.assertIn("state=P|landmark=ENDPOINT_ONSET", subfamilies)

    def test_segment_durations_are_exact(self) -> None:
        self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_100)
        self.calc.mark_landmark("c1", ENDPOINT_ONSET, 1_700)
        rows = {r["stratum"]["subfamily_id"]: r["value"] for r in self.calc.segment_duration.rows()}
        self.assertEqual(rows["state=P|landmark=T0"]["maximum"], 600.0)

    def test_the_onset_and_the_confirmation_are_both_kept(self) -> None:
        """`PERSIST - 1` apart: the structural answer and the causal one are different."""
        self.calc.open_runway(**open_kwargs())
        self.calc.mark_landmark("c1", T0, 1_000)
        self.calc.mark_landmark("c1", ENDPOINT_ONSET, 4_000)
        row = self.calc.complete("c1", recv_ns=6_000)
        marks = {seg["landmark"]: seg["entered_recv_ns"] for seg in row["segments"]}
        self.assertEqual(marks[ENDPOINT_ONSET], 4_000)
        self.assertEqual(marks[ENDPOINT_CONFIRMATION], 6_000)

    def test_only_the_confirmation_is_terminal(self) -> None:
        self.calc.open_runway(**open_kwargs(candidate_id="a"))
        row = self.calc.complete("a", recv_ns=2_000, terminal_landmark=ENDPOINT_CONFIRMATION)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["segments"][-1]["landmark"], ENDPOINT_CONFIRMATION)

    def test_a_nonterminal_completion_landmark_is_refused(self) -> None:
        self.calc.open_runway(**open_kwargs())
        with self.assertRaises(ExhaustionError):
            self.calc.complete("c1", recv_ns=2_000, terminal_landmark=ENDPOINT_ONSET)

    def test_segment_end_censors_and_excludes_from_completed_duration(self) -> None:
        self.calc.open_runway(**open_kwargs())
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=5_000)
        self.assertEqual(rows[0]["status"], "CENSORED_SEGMENT_END")
        self.assertTrue(rows[0]["censored"])
        completed = self.calc.completed_duration.rows()[0]
        self.assertEqual(completed["value"]["n"], 0)
        self.assertEqual(completed["excluded_missing_members"], 1)
        self.assertEqual(self.calc.censored_age.rows()[0]["value"]["maximum"], 4_000.0)

    def test_completed_and_censored_runways_never_pool(self) -> None:
        """Each lands in its own terminal-landmark stratum, and in its own measure."""
        self.calc.open_runway(**open_kwargs(candidate_id="a"))
        self.calc.complete("a", recv_ns=2_000)
        self.calc.open_runway(**open_kwargs(candidate_id="b"))
        self.calc.finalize(recv_ns=90_000)

        completed = {r["stratum"]["subfamily_id"]: r for r in self.calc.completed_duration.rows()}
        censored = {r["stratum"]["subfamily_id"]: r for r in self.calc.censored_age.rows()}
        self.assertEqual(completed["state=P|landmark=ENDPOINT_CONFIRMATION"]["value"]["n"], 1)
        self.assertEqual(censored["state=P|landmark=UNMARKED"]["value"]["n"], 1)

        # The cross terms are excluded rather than zero-filled, and never merged.
        self.assertEqual(completed["state=P|landmark=UNMARKED"]["value"]["n"], 0)
        self.assertEqual(completed["state=P|landmark=UNMARKED"]["excluded_missing_members"], 1)
        self.assertEqual(censored["state=P|landmark=ENDPOINT_CONFIRMATION"]["value"]["n"], 0)
        self.assertEqual(censored["state=P|landmark=ENDPOINT_CONFIRMATION"]["excluded_missing_members"], 1)

        self.assertEqual(sum(r["value"]["n"] for r in completed.values()), 1)
        self.assertEqual(sum(r["value"]["n"] for r in censored.values()), 1)

    def test_falsifiers_and_alternatives_are_preserved(self) -> None:
        runway = self.calc.open_runway(**open_kwargs())
        runway.falsifiers.append("refill exceeded removal within 200ms")
        runway.alternative_hypotheses.append("maker rotation, not exhaustion")
        row = self.calc.complete("c1", recv_ns=2_000)
        self.assertEqual(len(row["falsifiers"]), 1)
        self.assertEqual(len(row["alternative_hypotheses"]), 1)

    def test_recurrences_are_counted(self) -> None:
        self.calc.open_runway(**open_kwargs())
        self.calc.note_recurrence("c1")
        self.calc.note_recurrence("c1")
        row = self.calc.complete("c1", recv_ns=2_000)
        self.assertEqual(row["recurrences"], 2)

    def test_open_world_states_are_tracked_and_flagged(self) -> None:
        self.calc.open_runway(**open_kwargs(seed_state=None, observed_shape=["AN", "TFM"]))
        row = self.calc.complete("c1", recv_ns=2_000)
        self.assertTrue(row["state_is_open_world"])
        self.assertEqual(self.calc.summary()["open_world_state_count"], 1)

    def test_duplicate_open_is_refused(self) -> None:
        self.calc.open_runway(**open_kwargs())
        with self.assertRaises(ExhaustionError):
            self.calc.open_runway(**open_kwargs())

    def test_acting_on_an_unopened_runway_is_refused(self) -> None:
        with self.assertRaises(ExhaustionError):
            self.calc.mark_landmark("nope", T0, 1)
        with self.assertRaises(ExhaustionError):
            self.calc.note_recurrence("nope")

    def test_days_do_not_pool(self) -> None:
        self.calc.open_runway(**open_kwargs(candidate_id="a", source_day="20211004"))
        self.calc.complete("a", recv_ns=2_000)
        self.calc.open_runway(**open_kwargs(candidate_id="b", source_day="20211005"))
        self.calc.complete("b", recv_ns=2_000)
        days = {r["stratum"]["source_day"] for r in self.calc.completed_duration.rows()}
        self.assertEqual(days, {"20211004", "20211005"})

    def test_summary_reports_the_split(self) -> None:
        self.calc.open_runway(**open_kwargs(candidate_id="a"))
        self.calc.complete("a", recv_ns=2_000)
        self.calc.open_runway(**open_kwargs(candidate_id="b"))
        self.calc.finalize(recv_ns=9_000)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.10")
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["censored"], 1)
        self.assertEqual(summary["still_open"], 0)
        self.assertTrue(summary["seed_states_are_a_crosswalk_not_an_allowlist"])


if __name__ == "__main__":
    unittest.main()
