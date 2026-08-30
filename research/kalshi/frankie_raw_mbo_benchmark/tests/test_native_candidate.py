"""The causal candidate detector: it may never see past the second it is judging.

The frozen detector is retrospective and breaks that twice - a whole-day quantile threshold
and a global prominence sort before the refractory. This is the port that fixes both, so the
tests that matter are the ones a lookahead would FAIL, not the ones that merely show a spike
being found.

The centrepiece is `test_emission_is_a_function_of_the_prefix_alone`, which is executable
rather than argued: it replays every prefix of a stream and requires what was emitted by
second k to depend on nothing after k. That is the same property `native_rt_book` proves for
the book, and it is the only form of this claim worth having.
"""
from __future__ import annotations

import math
import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_candidate as nc
from research.kalshi.frankie_raw_mbo_benchmark.native_roll20 import (
    DEFAULT_WINDOW,
    Roll20Error,
    SecondBinner,
    RECV_CLOCK,
    roll20,
)

WARMUP = 60


def flat_then(spikes: dict[int, float], *, length: int, base: float = 0.02) -> list[float]:
    """Background flow with VARYING magnitude, plus named spikes.

    The first version of this helper alternated +base/-base, so every |value| was identical -
    and the 85th percentile of a constant series IS that constant, so every second cleared the
    bar and every second tied the local maximum. The detector then fired every 45 seconds,
    exactly as a quantile threshold on degenerate data must. That was the fixture being wrong,
    not the detector, and it is recorded because a background that never varies is not a
    background: real per-second flow does.
    """
    series = []
    for i in range(length):
        magnitude = base * (1.0 + ((i * 37) % 11) / 10.0)   # deterministic, base .. 2*base
        series.append(magnitude if i % 2 else -magnitude)
    for second, value in spikes.items():
        series[second] = value
    return series


def detect(series, **kwargs):
    params = {"warmup_seconds": WARMUP, "continuity_segment": 1, "first_second": 0,
              "selection_rule": nc.CAUSAL_FIRST_COME,
              # The production floor is 600 finite observations behind the bar; these streams
              # are hundreds of seconds, so the floor is scaled to the fixture rather than the
              # guard being relaxed. `MinObservationsTest` pins the production default.
              "min_threshold_observations": 30}
    params.update(kwargs)
    first = params.pop("first_second")
    return nc.detect(series, first_second=first, **params)


class CausalityTest(unittest.TestCase):
    def test_emission_is_a_function_of_the_prefix_alone(self):
        """No lookahead, proved by replay rather than asserted.

        For every k, a detector fed only seconds[:k] must have emitted exactly what the
        full-stream detector had emitted by the time it had consumed k seconds. If any
        decision consulted a later second, the two diverge.
        """
        series = flat_then({120: 0.9, 200: -0.8, 320: 0.7, 340: 0.95}, length=400)
        full = nc.CausalPeakDetector(continuity_segment=1, warmup_seconds=WARMUP)
        running: list[list[str]] = []
        seen: list[str] = []
        for offset, value in enumerate(series):
            for candidate in full.observe(offset, value):
                seen.append(candidate.candidate_id)
            running.append(list(seen))

        for k in (100, 150, 250, 330, 400):
            with self.subTest(prefix=k):
                partial = nc.CausalPeakDetector(continuity_segment=1, warmup_seconds=WARMUP)
                got: list[str] = []
                for offset, value in enumerate(series[:k]):
                    got.extend(c.candidate_id for c in partial.observe(offset, value))
                self.assertEqual(got, running[k - 1])

    def test_availability_is_never_the_event_second(self):
        """A spike at t needs t +/- radius to be a local max, so it is not knowable at t."""
        found, _ = detect(flat_then({120: 0.9}, length=200))
        self.assertIn(120, [c.event_second for c in found])
        for candidate in found:
            with self.subTest(second=candidate.event_second):
                self.assertEqual(candidate.detection_lag_seconds, nc.LOCAL_RADIUS)
                self.assertEqual(
                    candidate.available_second, candidate.event_second + nc.LOCAL_RADIUS
                )

    def test_a_percentile_bar_admits_background_by_construction_and_prominence_separates(self):
        """Recorded because expecting otherwise is the easy mistake, and it was mine.

        An 85th-percentile threshold admits roughly 15% of seconds BY DEFINITION - the bar is
        a quantile of the very series it is filtering. What makes the frozen program's 3,429
        events rare is not the bar; it is prominence ranking under a 45-second refractory
        across a whole week, on flow that is heavy-tailed in reality. So a test asserting
        "only the injected spike fires" is testing a property the frozen detector never had,
        and a detector that produced it would be doing something else.
        """
        found, _ = detect(flat_then({120: 0.9}, length=200))
        self.assertGreater(len(found), 1, "a percentile bar that admits nothing else is not one")
        spike = next(c for c in found if c.event_second == 120)
        background = [c for c in found if c.event_second != 120]
        self.assertTrue(background)
        self.assertGreater(spike.prominence, 10 * max(c.prominence for c in background))

    def test_the_windowed_rule_stamps_the_instant_its_window_actually_closed(self):
        """The release instant, measured by replay - not a constant asserted into existence.

        The first version asserted `detection_lag == REFRACTORY`, which the code made true by
        construction for every windowed candidate regardless of when the window really closed;
        it could not have failed. Availability is a property of the WINDOW, not the winner, so
        the lag varies with where in its window the winner sat. What must hold is that the
        stamp equals the second the traversal was actually on when the row came out.
        """
        detector = nc.CausalPeakDetector(
            continuity_segment=1, warmup_seconds=WARMUP, min_threshold_observations=30,
            selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE,
        )
        released_at: list[tuple[int, int]] = []
        for second, value in enumerate(flat_then({120: 0.5, 140: 0.9}, length=300)):
            for candidate in detector.observe(second, value):
                released_at.append((candidate.available_second, second))
        self.assertTrue(released_at)
        for stamped, actual in released_at:
            with self.subTest(stamped=stamped):
                self.assertEqual(stamped, actual)

    def test_a_gap_in_the_feed_is_refused_rather_than_stamped_as_a_short_wait(self):
        """The local window is sliced positionally; availability is computed temporally.

        Skip a stretch and the two disagree: a candidate at second 200 on a feed that jumped
        to 5000 was stamped available at 205 after a 4,800-second wait - a 4,800-second
        lookahead recorded as a five-second one. A quiet second is NaN, not absent.
        """
        detector = nc.CausalPeakDetector(
            continuity_segment=1, warmup_seconds=WARMUP, min_threshold_observations=30
        )
        for second in range(0, 100):
            detector.observe(second, 0.01)
        with self.assertRaises(nc.CandidateError):
            detector.observe(5000, 0.9)

    def test_the_threshold_is_trailing_so_history_changes_the_verdict(self):
        """The frozen whole-day bar would judge these two identically. A causal bar cannot.

        The same spike, same magnitude, same local shape. After a quiet stretch it clears a low
        trailing bar; after a loud stretch it does not. That difference IS what RT-legality
        buys, so it is asserted directly rather than described in the module docstring.
        """
        quiet_found, _ = detect(flat_then({120: 0.55}, length=200, base=0.01))
        loud_found, _ = detect(flat_then({120: 0.55}, length=200, base=0.50))
        self.assertIn(120, [c.event_second for c in quiet_found])
        self.assertNotIn(120, [c.event_second for c in loud_found])

    def test_no_candidate_is_available_before_the_warmup_has_elapsed(self):
        """A quantile over a handful of observations is noise wearing a threshold's name."""
        found, detector = detect(flat_then({20: 0.99}, length=200))
        self.assertGreater(detector.seconds_in_warmup, 0)
        self.assertNotIn(20, [c.event_second for c in found])
        for candidate in found:
            with self.subTest(second=candidate.event_second):
                self.assertGreaterEqual(candidate.available_second, WARMUP)

    def test_a_warmup_shorter_than_the_baseline_lookback_is_refused(self):
        with self.assertRaises(nc.CandidateError):
            nc.CausalPeakDetector(continuity_segment=1, warmup_seconds=5)

    def test_an_unknown_selection_rule_is_refused_never_defaulted(self):
        """It decides which member of a cluster survives; a silent default would hide that."""
        with self.assertRaises(nc.CandidateError):
            nc.CausalPeakDetector(continuity_segment=1, selection_rule="BEST")


class SelectionTest(unittest.TestCase):
    """Which member of a cluster survives, and what that costs in availability.

    Assertions are scoped to the two INJECTED spikes rather than to the whole emitted set,
    because a percentile bar admits background by construction (see CausalityTest) and a test
    that demanded a clean set would be testing the fixture, not the rule.
    """

    SPIKES = (120, 140)

    def _injected(self, found):
        return [c.event_second for c in found if c.event_second in self.SPIKES]

    def test_first_come_keeps_the_earlier_spike_even_when_a_later_one_is_larger(self):
        """The frozen global sort would keep the larger. In RT the earlier one already happened."""
        found, _ = detect(flat_then({120: 0.6, 140: 0.95}, length=300))
        self.assertEqual(self._injected(found), [120])

    def test_the_default_rule_is_the_one_that_does_not_lose_signal(self):
        detector = nc.CausalPeakDetector(continuity_segment=1)
        self.assertEqual(detector.selection_rule, nc.CAUSAL_WINDOWED_PROMINENCE)

    def test_no_two_accepted_candidates_fall_inside_one_refractory_window(self):
        """The invariant the rule exists to hold, asserted over everything emitted."""
        found, _ = detect(flat_then({120: 0.9, 400: 0.9}, length=500))
        seconds = [c.event_second for c in found]
        for earlier, later in zip(seconds, seconds[1:]):
            with self.subTest(pair=(earlier, later)):
                self.assertGreaterEqual(later - earlier, nc.REFRACTORY)

    def test_windowed_prominence_keeps_the_larger_spike_in_its_window(self):
        found, detector = detect(
            flat_then({120: 0.6, 140: 0.95}, length=300),
            selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE,
        )
        self.assertEqual(self._injected(found), [140])
        self.assertGreater(detector.suppressed_by_prominence, 0)

    def test_the_two_rules_disagree_on_the_same_stream(self):
        """If they agreed, the choice would not need declaring - and it does."""
        series = flat_then({120: 0.6, 140: 0.95}, length=300)
        self.assertNotEqual(
            self._injected(detect(series)[0]),
            self._injected(detect(series, selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE)[0]),
        )

    def test_the_selection_rule_travels_on_every_candidate(self):
        """A caveat that lives only in prose expires."""
        found, _ = detect(flat_then({120: 0.9}, length=200))
        for candidate in found:
            self.assertEqual(candidate.selection_rule, nc.CAUSAL_FIRST_COME)
            self.assertEqual(candidate.threshold_rule, nc.TRAILING_QUANTILE)
            self.assertIn("observations_behind_threshold", candidate.as_dict())


class DirectionAndMissingnessTest(unittest.TestCase):
    def test_polarity_comes_from_the_sign_and_magnitude_is_reported_beside_it(self):
        up, _ = detect(flat_then({120: 0.9}, length=200))
        down, _ = detect(flat_then({120: -0.9}, length=200))
        up_spike = next(c for c in up if c.event_second == 120)
        down_spike = next(c for c in down if c.event_second == 120)
        self.assertEqual(up_spike.polarity, 1)
        self.assertEqual(down_spike.polarity, -1)
        self.assertEqual(up_spike.magnitude, down_spike.magnitude)

    def test_a_nan_second_is_not_read_as_balanced(self):
        """A second with no trades is undefined, not 0.0. Treating it as 0 invents a reading."""
        series = flat_then({120: 0.9}, length=200)
        series[121] = float("nan")
        series[119] = float("nan")
        found, _ = detect(series)
        spike = next(c for c in found if c.event_second == 120)
        self.assertTrue(math.isfinite(spike.magnitude))
        self.assertEqual(spike.polarity, 1)

    def test_an_all_nan_stream_emits_nothing_rather_than_a_zero_peak(self):
        found, _ = detect([float("nan")] * 300)
        self.assertEqual(found, [])

    def test_an_empty_stream_emits_nothing(self):
        """Proves the assertions above discriminate rather than passing on anything."""
        found, detector = detect([])
        self.assertEqual(found, [])
        self.assertEqual(detector.emitted, 0)


class Roll20StreamingReconciliationTest(unittest.TestCase):
    """`rolling_value` and `roll20()` are two ways to compute one number, so they are checked.

    Two computations of one quantity that are never compared are two quantities - the
    `_family_id` defect of 2026-08-29 in a different costume.
    """

    def _binner(self) -> SecondBinner:
        binner = SecondBinner(clock=RECV_CLOCK)
        for second in range(0, 60):
            row = {
                "action": "T",
                "price": 3_500_000_000 + (100 if second % 3 else -100),
                "size": 1 + (second % 5),
                "bid_px_00": 3_499_000_000,
                "ask_px_00": 3_501_000_000,
                "ts_recv": second,  # SECONDS: observe() keys on floor(clock)
            }
            binner.observe(row)
        return binner

    def test_the_streaming_value_equals_the_materialised_series_at_every_index(self):
        binner = self._binner()
        buys, sells, first = binner.series()
        materialised = roll20(buys, sells, window=DEFAULT_WINDOW)
        for offset, expected in enumerate(materialised):
            with self.subTest(second=first + offset):
                got = binner.rolling_value(first + offset, window=DEFAULT_WINDOW)
                if math.isnan(expected):
                    self.assertTrue(math.isnan(got))
                else:
                    self.assertAlmostEqual(got, expected, places=12)

    def test_a_window_with_no_volume_is_nan_not_zero(self):
        binner = SecondBinner(clock=RECV_CLOCK)
        self.assertTrue(math.isnan(binner.rolling_value(10_000)))

    def test_a_non_positive_window_is_refused(self):
        with self.assertRaises(Roll20Error):
            self._binner().rolling_value(10, window=0)

    def test_a_nanosecond_clock_is_refused_rather_than_hanging(self):
        """The trap this test file walked into. A hang reads as a slow run, not a defect."""
        binner = SecondBinner(clock=RECV_CLOCK)
        for stamp in (1_000_000_000, 5_000_000_000):
            binner.observe({
                "action": "T", "price": 3_500_100_000, "size": 2,
                "bid_px_00": 3_499_000_000, "ask_px_00": 3_501_000_000,
                "ts_recv": stamp,              # nanoseconds, not seconds
            })
        with self.assertRaises(Roll20Error):
            binner.series()


if __name__ == "__main__":
    unittest.main()


class AdversarialReviewRegressionTest(unittest.TestCase):
    """One test per finding from the adversarial review, numbered as it reported them.

    All ten were present while the suite was green at 24 tests, and eight of them changed
    which events the detector emits. They are pinned here by number so a future change that
    reintroduces one is named rather than merely red.
    """

    def _spread(self, spikes, *, length=500, rule=None):
        found, _ = detect(
            flat_then(spikes, length=length),
            **({"selection_rule": rule} if rule else {}),
        )
        return [c.event_second for c in found]

    def test_f1_no_two_emitted_events_are_closer_than_the_refractory(self):
        """The invariant the frozen greedy loop guarantees and the first port did not.

        It partitioned on the window's left edge instead of on what was PICKED, and it only
        filtered candidates already buffered - one judged after the window closed opened a
        fresh window inside the winner's shadow. Measured before the fix: 7 seconds, then 33.
        """
        cases = (
            {120: 0.6, 140: 0.95},
            {120: 0.9, 400: 0.9},
            {100: 0.30, 164: 0.95, 165: 0.90},
            {100: 0.30, 142: 0.99},
        )
        for rule in (nc.CAUSAL_FIRST_COME, nc.CAUSAL_WINDOWED_PROMINENCE):
            for spikes in cases:
                seconds = self._spread(spikes, rule=rule)
                with self.subTest(rule=rule, spikes=sorted(spikes)):
                    gaps = [b - a for a, b in zip(seconds, seconds[1:])]
                    if gaps:
                        self.assertGreaterEqual(min(gaps), nc.REFRACTORY)

    def test_f2_a_window_includes_the_members_judged_in_its_last_seconds(self):
        """The window closed `local_radius` early, so its last five seconds never competed.

        Review's case: a spike at 142 is inside the window opened at 100 and 3.5x more
        prominent, so exactly one event must come out of that window. It emitted both.
        """
        seconds = self._spread({100: 0.30, 142: 0.99}, rule=nc.CAUSAL_WINDOWED_PROMINENCE)
        in_window = [s for s in seconds if 100 <= s < 145]
        self.assertEqual(len(in_window), 1, f"one window emitted {in_window}")

    def test_f4_a_balanced_tape_produces_no_direction_less_events(self):
        """roll20 is exactly 0.0 on a balanced window, and the frozen drops those marks.

        Unguarded, the bar is 0.0 too, `abs(0) < 0` is False, and every such second became a
        qualifying peak with polarity 0 - which then consumed refractory windows. On the
        review's series the frozen emits exactly one event; so does this now.
        """
        series = [0.0] * 300
        series[120] = 0.9
        for rule in (nc.CAUSAL_FIRST_COME, nc.CAUSAL_WINDOWED_PROMINENCE):
            found, _ = detect(series, selection_rule=rule)
            with self.subTest(rule=rule):
                self.assertEqual([c.event_second for c in found], [120])
                self.assertEqual(found[0].polarity, 1)
                self.assertNotIn(0, [c.polarity for c in found])

    def test_f6_a_bar_is_never_built_from_a_handful_of_observations(self):
        """The warmup gated on observe CALLS, and NaN seconds count there.

        905 NaN seconds then one finite 0.42: the bar was that single observation, which then
        cleared itself. Overnight NG has stretches of exactly that shape.
        """
        detector = nc.CausalPeakDetector(
            continuity_segment=1, warmup_seconds=900, min_threshold_observations=600
        )
        emitted = []
        for second in range(905):
            emitted.extend(detector.observe(second, float("nan")))
        emitted.extend(detector.observe(905, 0.42))
        for second in range(906, 920):
            emitted.extend(detector.observe(second, float("nan")))
        self.assertEqual(emitted, [])
        self.assertGreater(detector.seconds_in_warmup, 0)

    def test_f7_the_baseline_uses_the_frozen_twenty_one_points(self):
        """`range(t-30, t-9)` is t-30..t-10. The port used an inclusive t-9: 22 points.

        Prominence differed on 63 of 63 candidates in the review's comparison, and prominence
        is the windowed rule's sort key - it decides which member of a cluster survives.
        """
        self.assertEqual(nc.BASELINE_POINTS, 21)
        self.assertEqual(nc.BASELINE_START - nc.BASELINE_LAG, 21)

    def test_f8_the_threshold_buffer_is_named_as_the_count_it_is(self):
        """It caps FINITE observations, not wall-clock seconds; NaN never enters it."""
        summary = nc.CausalPeakDetector(continuity_segment=1).summary()
        self.assertIn("threshold_observation_cap", summary)
        self.assertNotIn("threshold_window_seconds", summary)

    def test_f9_a_window_cut_short_by_the_stream_end_says_so(self):
        """`finish()` forces the last window open, so its winner is a partial-window maximum
        stamped with an availability the segment never reaches. A consumer measuring H+N
        against it would index past the data if a complete and a truncated window looked the
        same."""
        series = flat_then({192: 0.95}, length=200)   # inside the final, never-closing window
        found, _ = detect(series, selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE)
        truncated = [c for c in found if c.window_truncated]
        self.assertTrue(truncated, "the last window closed cleanly; the fixture no longer truncates")
        for candidate in truncated:
            self.assertIn("window_truncated", candidate.as_dict())
