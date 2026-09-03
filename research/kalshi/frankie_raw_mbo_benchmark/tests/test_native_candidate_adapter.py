"""The adapter that drives 4.10, 4.11 and 4.12 - which had no test file at all.

That absence is why D-2, D-11 and the SEARCHED-duration defect all survived a full run: the
calculators below it are each well tested and each behaved correctly on the inputs they were
given, and what was wrong was that three of those inputs were never sent.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from research.kalshi.frankie_raw_mbo_benchmark.native_candidate import Candidate
from research.kalshi.frankie_raw_mbo_benchmark.native_candidate_adapter import (
    CandidateEpisodeTracker,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import DipoleCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_exhaustion import (
    SEARCHED,
    ExhaustionCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import ClockError
from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import (
    HORIZON, T0, CandidateRecognition, RecognitionCalculator,
)

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


class PhaseAttributionTest(unittest.TestCase):
    """D-12's other half. 3,454 stages across 90 paths and not ONE was REVERSAL.

    4.10 recorded 90 of 91 runways as reversed over the same episodes. 4.12 could not observe
    a REVERSAL stage at all: the stage for second S was appended and observed BEFORE the
    phase transition for that same second was evaluated, so every stage carried the previous
    second's phase, and the terminal phase was entered inside `_close`, which observes
    nothing and then drops the episode.
    """

    def _reversed_pair(self):
        track = tracker()
        # The first episode has no predecessor and so contributes no stages; the second does.
        opened(track, candidate(candidate_id="c0", polarity=1, event_second=50,
                                available_second=52))
        track.advance(51, signed_flow=10, polarity=1)
        opened(track, candidate(candidate_id="c1", polarity=1, event_second=100,
                                available_second=102))
        for second in range(101, 108):
            track.advance(second, signed_flow=-50, polarity=-1)
        return track

    def test_a_reversal_produces_a_reversal_stage(self) -> None:
        track = self._reversed_pair()
        self.assertEqual(track.episodes_reversed, 2)
        self.assertGreater(track.dipole.summary()["event_phase_counts"].get("REVERSAL", 0), 0)

    def test_a_reversed_runway_completes_rather_than_censoring(self) -> None:
        """91 runways opened, 0 completed, 91 censored - because nothing called `complete`.

        That is why `completed_runway_duration_ns` had n=0 against 91 exclusions and the
        reversal duration everyone read was a censoring artifact.
        """
        summary = self._reversed_pair().exhaustion.summary()
        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["censored"], 0)

    def test_a_boundary_censored_episode_is_not_stamped_as_a_reversal(self) -> None:
        """The prerequisite. Otherwise the fix above fabricates reversals that never happened."""
        track = tracker()
        opened(track, candidate(candidate_id="c0", polarity=1, event_second=50,
                                available_second=52))
        track.advance(51, signed_flow=10, polarity=1)
        opened(track, candidate(candidate_id="c1", polarity=1, event_second=100,
                                available_second=102))
        track.advance(101, signed_flow=10, polarity=1)
        track.close_segment(1_633_352_500 * NS_PER_SECOND)
        self.assertEqual(track.episodes_censored, 2)
        self.assertEqual(track.dipole.summary()["event_phase_counts"].get("REVERSAL", 0), 0)

    def test_a_censored_episode_does_not_complete_its_runway(self) -> None:
        """CENSORED_AT_OBSERVATION_END is deliberately not a terminal phase."""
        track = tracker()
        opened(track, candidate(candidate_id="c1", polarity=1))
        track.close_segment(1_633_352_500 * NS_PER_SECOND)
        summary = track.exhaustion.summary()
        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["still_open"], 1,
                         "the runway stays open for 4.10's own boundary handling to censor")


class RecognitionInstantOnTheOpenRowTest(unittest.TestCase):
    """S121 item one: the open row carried `recognition_outcome` and not the instant it was
    recognised at, so the member row's discovery-confirmation clock could name the call and
    not when it was knowable. Both instants and the basis of the second now ride the row."""

    def test_an_h_plus_n_call_carries_the_available_second_and_says_which_bin_it_is(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import (
            HORIZON, RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN,
        )
        cand = candidate(event_second=1_633_352_400, available_second=1_633_352_405)
        row = opened(tracker(), cand)
        self.assertEqual(row["recognition_outcome"], HORIZON)
        self.assertEqual(row["recognized_recv_ns"], 1_633_352_405 * NS_PER_SECOND)
        self.assertEqual(row["recognized_recv_ns_basis"], RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN)
        self.assertIsNone(row["precursor_recv_ns"])

    def test_a_prior_call_carries_the_precursor_instant_and_its_basis(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import (
            PRIOR, RECOGNIZED_BASIS_PRECURSOR_FINDING,
        )
        precursor_ns = 1_633_352_390 * NS_PER_SECOND
        track = CandidateEpisodeTracker(
            exhaustion=ExhaustionCalculator(), recognition=RecognitionCalculator(),
            dipole=DipoleCalculator(), source_role="A_CLEAN",
            precursor_for=lambda _cand: precursor_ns,
        )
        row = opened(track, candidate())
        self.assertEqual(row["recognition_outcome"], PRIOR)
        self.assertEqual(row["recognized_recv_ns"], precursor_ns)
        self.assertEqual(row["precursor_recv_ns"], precursor_ns)
        self.assertEqual(row["recognized_recv_ns_basis"], RECOGNIZED_BASIS_PRECURSOR_FINDING)

    def test_the_recognition_record_keeps_the_basis_beside_the_instant(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import (
            RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN,
        )
        track = tracker()
        opened(track, candidate())
        record = track._open["c1"].recognition.as_dict()
        self.assertEqual(record["recognized_recv_ns_basis"], RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN)


class RecognitionLabelCallerS122Test(unittest.TestCase):
    def test_h_plus_n_open_row_carries_the_validated_label_and_canonical_lead(self) -> None:
        cand = candidate(event_second=1_633_352_400, available_second=1_633_352_405)
        row = opened(tracker(), cand)
        validated = row["recognition_label"]
        reference = cand.event_second * NS_PER_SECOND
        observed = cand.available_second * NS_PER_SECOND
        self.assertEqual(validated["label"], HORIZON)
        self.assertEqual(validated["clock"], "ts_recv_ns")
        self.assertEqual(validated["reference_ns"], reference)
        self.assertEqual(validated["observed_ns"], observed)
        self.assertEqual(validated["lead_ns"], reference - observed)
        self.assertLess(validated["lead_ns"], 0)
        # Existing fields stay beside the validated object.
        self.assertEqual(row["recognition_outcome"], HORIZON)
        self.assertEqual(row["recognized_recv_ns"], observed)

    def test_prior_lead_is_positive_reference_minus_observed_without_wiring_a_new_precursor(self) -> None:
        precursor_ns = 1_633_352_390 * NS_PER_SECOND
        track = CandidateEpisodeTracker(
            exhaustion=ExhaustionCalculator(), recognition=RecognitionCalculator(),
            dipole=DipoleCalculator(), source_role="A_CLEAN",
            precursor_for=lambda _cand: precursor_ns,
        )
        cand = candidate(event_second=1_633_352_400)
        row = opened(track, cand)
        validated = row["recognition_label"]
        self.assertEqual(validated["lead_ns"], cand.event_second * NS_PER_SECOND - precursor_ns)
        self.assertGreater(validated["lead_ns"], 0)

    def test_t0_with_an_observed_time_off_its_reference_is_refused_by_the_adapter_caller(self) -> None:
        def impossible_t0(self, *, recv_ns: int, basis=None):
            self.outcome = T0
            self.recognized_recv_ns = self.birth_recv_ns + 1
            self.recognized_recv_ns_basis = basis
            return self.outcome

        with patch.object(CandidateRecognition, "record_call", impossible_t0):
            with self.assertRaisesRegex(ClockError, "T0 recognition must coincide"):
                opened(tracker(), candidate())

    def test_h_plus_n_with_an_observed_time_before_reference_is_refused_by_the_adapter_caller(self) -> None:
        def impossible_horizon(self, *, recv_ns: int, basis=None):
            self.outcome = HORIZON
            self.recognized_recv_ns = self.birth_recv_ns - 1
            self.recognized_recv_ns_basis = basis
            return self.outcome

        with patch.object(CandidateRecognition, "record_call", impossible_horizon):
            with self.assertRaisesRegex(ClockError, "H\+N recognition must follow"):
                opened(tracker(), candidate())

    def test_closed_recognition_output_keeps_existing_fields_and_adds_the_validated_object(self) -> None:
        track = tracker()
        cand = candidate()
        opened(track, cand)
        closed = track.close_segment((cand.available_second + 1) * NS_PER_SECOND)[0]
        recognition = closed["recognition"]
        self.assertEqual(recognition["outcome"], HORIZON)
        self.assertIn("recognized_recv_ns", recognition)
        self.assertEqual(recognition["recognition_label"]["label"], HORIZON)
        self.assertEqual(
            recognition["recognition_label"]["lead_ns"],
            recognition["birth_recv_ns"] - recognition["recognized_recv_ns"],
        )
