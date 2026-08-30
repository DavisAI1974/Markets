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
              "selection_rule": nc.CAUSAL_FIRST_COME}
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

    def test_the_windowed_rule_pays_for_prominence_with_a_longer_lag(self):
        """It looks across a refractory window, so it cannot claim radius-only availability."""
        found, _ = detect(
            flat_then({120: 0.5, 140: 0.9}, length=300),
            selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE,
        )
        self.assertTrue(found)
        for candidate in found:
            with self.subTest(second=candidate.event_second):
                self.assertEqual(candidate.detection_lag_seconds, nc.REFRACTORY)

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

    def test_windowed_prominence_keeps_the_larger_spike_in_the_same_window(self):
        found, detector = detect(
            flat_then({120: 0.6, 140: 0.95}, length=300),
            selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE,
        )
        self.assertEqual(self._injected(found), [140])
        self.assertGreater(detector.suppressed_by_prominence, 0)

    def test_the_two_rules_disagree_on_the_same_stream(self):
        """If they agreed, the choice would not need declaring - and it does."""
        series = flat_then({120: 0.6, 140: 0.95}, length=300)
        first_come, _ = detect(series)
        windowed, _ = detect(series, selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE)
        self.assertNotEqual(self._injected(first_come), self._injected(windowed))

    def test_first_come_lets_trivial_noise_shadow_a_real_spike(self):
        """The measurement that made windowed prominence the default. Kept as the instance.

        Background peak at 393, magnitude 0.04. Real spike at 400, magnitude 0.9 - twenty-two
        times larger. Under first-come the noise arrived seven seconds earlier, took the
        refractory window, and the spike was never emitted at all. This is not a fixture
        artifact: an 85th-percentile bar admits ~15% of seconds by construction, so trivial
        peaks are always competing for the window, and under first-come arrival order decides.
        """
        found, _ = detect(flat_then({120: 0.9, 400: 0.9}, length=500))
        kept = [c.event_second for c in found]
        self.assertIn(393, kept)
        self.assertNotIn(400, kept, "first-come no longer shadows; re-check the default")

    def test_windowed_prominence_keeps_both_real_spikes_where_first_come_loses_one(self):
        """Why the default is windowed. Same stream, both rules, side by side."""
        series = flat_then({120: 0.9, 400: 0.9}, length=500)
        windowed, _ = detect(series, selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE)
        first_come, _ = detect(series, selection_rule=nc.CAUSAL_FIRST_COME)
        self.assertTrue({120, 400}.issubset({c.event_second for c in windowed}))
        self.assertFalse({120, 400}.issubset({c.event_second for c in first_come}))

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
