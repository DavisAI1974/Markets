"""The adapter that drives 4.10, 4.11 and 4.12 - which had no test file at all.

That absence is why D-2, D-11 and the SEARCHED-duration defect all survived a full run: the
calculators below it are each well tested and each behaved correctly on the inputs they were
given, and what was wrong was that three of those inputs were never sent.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_candidate import Candidate
from research.kalshi.frankie_raw_mbo_benchmark.native_candidate_adapter import (
    CandidateEpisodeTracker,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import DipoleCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_exhaustion import (
    SEARCHED,
    ExhaustionCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import RecognitionCalculator

NS_PER_SECOND = 1_000_000_000


def candidate(**overrides) -> Candidate:
    base = dict(
        candidate_id="c1",
        event_second=1_633_352_400,
        available_second=1_633_352_402,
        polarity=1,
        magnitude=500.0,
        prominence=120.0,
        threshold=300.0,
        threshold_rule="p95_trailing",
        selection_rule="max_prominence",
        continuity_segment=0,
        baseline=10.0,
        observations_behind_threshold=41,
        searched_span_seconds=64,
    )
    base.update(overrides)
    return Candidate(**base)


def tracker() -> CandidateEpisodeTracker:
    return CandidateEpisodeTracker(
        exhaustion=ExhaustionCalculator(),
        recognition=RecognitionCalculator(),
        dipole=DipoleCalculator(),
        source_role="A_CLEAN",
    )


def opened(track: CandidateEpisodeTracker, cand: Candidate, **overrides):
    kwargs = dict(source_day="20211003", family_id="TFCN", session_phase="RTH",
                  instrument_id=42)
    kwargs.update(overrides)
    return track.open(cand, **kwargs)


class SearchedDurationTest(unittest.TestCase):
    """D-11. SEARCHED had min = max = 0.0 for all 91 candidates."""

    def test_the_searched_phase_spans_the_interval_that_was_searched(self) -> None:
        track = tracker()
        cand = candidate(searched_span_seconds=64)
        opened(track, cand)
        runway = track.exhaustion._open["c1"]
        searched = next(p for p in runway.phases if p.phase == SEARCHED)
        self.assertEqual(searched.duration_ns, 64 * NS_PER_SECOND)

    def test_it_uses_the_wall_clock_span_not_the_observation_count(self) -> None:
        """41 finite observations spanning 64 seconds: reading the count understates by 36%."""
        track = tracker()
        opened(track, candidate(observations_behind_threshold=41, searched_span_seconds=64))
        runway = track.exhaustion._open["c1"]
        searched = next(p for p in runway.phases if p.phase == SEARCHED)
        self.assertNotEqual(searched.duration_ns, 41 * NS_PER_SECOND)
        self.assertEqual(searched.duration_ns, 64 * NS_PER_SECOND)

    def test_the_searched_window_ends_at_the_birth_and_so_precedes_it(self) -> None:
        """The runway opens at the birth; the evidence for it was gathered beforehand."""
        track = tracker()
        cand = candidate()
        opened(track, cand)
        runway = track.exhaustion._open["c1"]
        searched = next(p for p in runway.phases if p.phase == SEARCHED)
        self.assertEqual(searched.exited_recv_ns, cand.event_second * NS_PER_SECOND)
        self.assertLess(searched.entered_recv_ns, runway.opened_recv_ns)


class LiquidityAttributionTest(unittest.TestCase):
    """D-2. phase_depletion and phase_refill were 0.0 in all 109 strata."""

    def test_a_group_on_the_same_side_feeds_the_runway(self) -> None:
        track = tracker()
        opened(track, candidate(polarity=1))
        attributed = track.note_group_liquidity(side="B", depletion=40, refill=15)
        self.assertEqual(attributed, 1)
        phase = track.exhaustion._open["c1"].current_phase
        self.assertEqual((phase.depletion, phase.refill), (40, 15))

    def test_the_opposite_side_is_not_attributed(self) -> None:
        """A bid runway's consumption is not measured by asks being pulled."""
        track = tracker()
        opened(track, candidate(polarity=1))
        self.assertEqual(track.note_group_liquidity(side="A", depletion=40, refill=15), 0)
        self.assertEqual(track.exhaustion._open["c1"].current_phase.depletion, 0)

    def test_an_unsided_group_is_attributed_to_nothing(self) -> None:
        """Same rule as the ladder: assigning "N" to a side fabricates one."""
        track = tracker()
        opened(track, candidate(polarity=1))
        self.assertEqual(track.note_group_liquidity(side="N", depletion=40, refill=15), 0)

    def test_overlapping_runways_each_receive_it_and_the_count_says_so(self) -> None:
        track = tracker()
        opened(track, candidate(candidate_id="c1", polarity=1))
        opened(track, candidate(candidate_id="c2", polarity=1))
        self.assertEqual(track.note_group_liquidity(side="B", depletion=9, refill=3), 2)


class StructureRecurrenceTest(unittest.TestCase):
    """D-11. recurrence_count was min = max = 0.0 in all 28 strata."""

    def test_a_recurring_family_notifies_its_open_runways(self) -> None:
        track = tracker()
        opened(track, candidate(), family_id="TFCN")
        self.assertEqual(track.note_structure_recurrence("TFCN"), 1)
        self.assertEqual(track.exhaustion._open["c1"].recurrences, 1)

    def test_a_different_family_recurring_is_not_this_runway_recurring(self) -> None:
        track = tracker()
        opened(track, candidate(), family_id="TFCN")
        self.assertEqual(track.note_structure_recurrence("OTHER"), 0)
        self.assertEqual(track.exhaustion._open["c1"].recurrences, 0)


if __name__ == "__main__":
    unittest.main()
