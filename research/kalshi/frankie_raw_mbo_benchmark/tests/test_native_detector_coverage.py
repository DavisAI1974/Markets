"""Section 4.0b: the accounting for the search that creates the candidate population.

Frankie, on run 33605852433: 91 promoted of 4,462 considered, and the 4,371 rejected sat in
a traversal counter block outside the contract, which is what made 4.11's
`detection_share = 1.0` unfalsifiable. These tests drive a REAL `CausalPeakDetector` through
the section - it never sees a flow value, so a fake detector could only prove that the
section reads dicts - and the refusals are exercised by PRODUCING the refusal, not by
asserting that a clean input passes.
"""
from __future__ import annotations

import math
import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_candidate as nc
from research.kalshi.frankie_raw_mbo_benchmark.native_detector_coverage import (
    COVERAGE_COUNTERS,
    FED,
    NOT_FED,
    PENDING_GAUGE,
    PROMOTED,
    REJECTION_REASONS,
    SEARCH_FAMILY,
    SEARCH_SIDE,
    TERMINAL_OUTCOMES,
    WINDOW_INCOMPLETE,
    DetectorCoverageCalculator,
    DetectorCoverageError,
    derive,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_candidate import (
    WARMUP,
    flat_then,
)

CTX = dict(source_day="20211004", source_role="A_CLEAN", session_phase="RTH")


def detector(segment: int = 1, **overrides) -> nc.CausalPeakDetector:
    params = dict(
        continuity_segment=segment,
        warmup_seconds=WARMUP,
        min_threshold_observations=30,
        selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE,
    )
    params.update(overrides)
    return nc.CausalPeakDetector(**params)


def drive(calc: DetectorCoverageCalculator, det: nc.CausalPeakDetector, series, *, phase_at=None):
    """Feed every second through the detector AND the section, the way the traversal does."""
    calc.open_segment(det)
    last = 0
    for second, value in enumerate(series):
        det.observe(second, value)
        phase = phase_at(second) if phase_at else CTX["session_phase"]
        calc.observe_second(
            det, second=second, source_day=CTX["source_day"], source_role=CTX["source_role"],
            continuity_segment=det.continuity_segment, session_phase=phase,
        )
        last = second
    det.finish(last)
    return calc.close_segment(
        det, source_day=CTX["source_day"], source_role=CTX["source_role"],
        continuity_segment=det.continuity_segment, session_phase=CTX["session_phase"],
        recv_ns=last * 1_000_000_000, occasion="STREAM_END",
    )


def three_peaks(length: int = 300):
    """Promotes, rejects at the bar, suppresses by prominence, and exits one peak at release."""
    return flat_then({120: 0.5, 134: 0.9, 165: 0.7}, length=length)


class PartitionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DetectorCoverageCalculator()
        self.det = detector()
        self.row = drive(self.calc, self.det, three_peaks())
        self.summary = self.calc.summary()

    def test_the_fixture_both_promotes_and_rejects_so_nothing_below_is_vacuous(self) -> None:
        self.assertGreater(self.summary["promoted"], 0)
        self.assertGreater(self.summary["rejected_total"], 0)
        self.assertGreater(self.summary["rejected_by_reason"]["rejected_below_threshold"], 0)
        self.assertGreater(self.summary["rejected_by_reason"]["suppressed_by_prominence"], 0)
        self.assertGreater(
            self.summary["rejected_by_reason"]["rejected_in_refractory_at_release"], 0,
            "the release-time exit is the one that used to go uncounted; the fixture must hit it",
        )

    def test_every_judged_second_ends_in_exactly_one_named_outcome(self) -> None:
        counters = self.det.counters()
        accounted = sum(counters[name] for name in TERMINAL_OUTCOMES) + counters[PENDING_GAUGE]
        self.assertEqual(counters["seconds_judged"], accounted)
        self.assertTrue(self.row["partition_identity_holds"])
        self.assertEqual(counters[PENDING_GAUGE], 0, "finish() leaves nothing pending")

    def test_the_section_totals_are_the_detectors_counters_key_for_key(self) -> None:
        for name in COVERAGE_COUNTERS + TERMINAL_OUTCOMES:
            with self.subTest(counter=name):
                self.assertEqual(self.row["section_totals"][name], self.det.counters()[name])
        self.assertTrue(self.row["reconciled_with_detector"])

    def test_every_rate_carries_its_numerator_and_denominator(self) -> None:
        rate = self.summary["promotion_rate"]
        self.assertEqual(rate["numerator"], self.summary["promoted"])
        self.assertEqual(rate["denominator"], self.summary["considered"])
        self.assertEqual(rate["basis"], "RATIO_OF_EXACT_COUNTS")
        self.assertAlmostEqual(rate["value"], rate["numerator"] / rate["denominator"])
        self.assertEqual(
            self.summary["considered"],
            self.summary["promoted"] + self.summary["rejected_total"]
            + self.summary["candidates_pending_in_window"],
            "considered is a sum of named outcomes, never a residual",
        )
        self.assertEqual(
            self.summary["searched_seconds"],
            self.summary["considered"] + self.summary["seconds_without_finite_flow"],
        )
        self.assertEqual(
            self.summary["seconds_judged"],
            self.summary["searched_seconds"] + self.summary["seconds_in_warmup"],
        )

    def test_rejected_by_reason_uses_the_detectors_names_verbatim(self) -> None:
        self.assertEqual(tuple(self.summary["rejected_by_reason"]), REJECTION_REASONS)
        for name in REJECTION_REASONS:
            with self.subTest(reason=name):
                self.assertIn(name, self.det.counters())
                self.assertIn(name, self.det.summary())

    def test_the_window_building_seconds_are_named_not_lost(self) -> None:
        """Observed minus judged is the first and last local radius; it is stated, not implied."""
        self.assertEqual(
            self.summary["seconds_window_never_completed"], 2 * self.det.local_radius,
        )
        self.assertEqual(self.summary["seconds_observed"], 300)

    def test_the_coverage_row_partitions_seconds_fed_so_its_n_is_a_population(self) -> None:
        """A row whose n summed two overlapping counts would feed the receipt as a population."""
        rows = [r for r in self.calc.companion_rows() if r["measure"] == "detector_seconds_coverage"]
        self.assertEqual(len(rows), 1)
        value = rows[0]["value"]
        self.assertEqual(value["n"], self.summary["seconds_observed"])
        self.assertEqual(value["counts"]["seconds_judged"], self.summary["seconds_judged"])
        self.assertEqual(value["counts"][WINDOW_INCOMPLETE], 2 * self.det.local_radius)

    def test_the_parameters_ride_on_every_row_and_change_the_signature(self) -> None:
        rows = self.calc.companion_rows()
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(measure=row["measure"]):
                params = row["value"]["detector_parameters"]
                self.assertEqual(params["peak_quantile"], nc.PEAK_QUANTILE)
                self.assertEqual(params["refractory_seconds"], nc.REFRACTORY)
                self.assertEqual(params["local_radius_seconds"], nc.LOCAL_RADIUS)
                self.assertEqual(params["warmup_seconds"], WARMUP)
                self.assertEqual(params["min_threshold_observations"], 30)
                self.assertEqual(params["selection_rule"], nc.CAUSAL_WINDOWED_PROMINENCE)
                self.assertEqual(params["threshold_rule"], nc.TRAILING_QUANTILE)
                self.assertIn("prominence_rule", params)
                self.assertIn("zero_flow_epsilon", params)
                self.assertTrue(row["value"]["parameter_signature"])
                self.assertEqual(row["kind"], "COUNT_PARTITION")
                self.assertEqual(row["stratum"]["family_id"], SEARCH_FAMILY)
                self.assertEqual(row["stratum"]["side_orientation"], SEARCH_SIDE)
                for field_name in ("numerator_formula", "population", "causal_cutoff",
                                   "status", "missingness_rule"):
                    self.assertTrue(row["declaration"][field_name])
        other = DetectorCoverageCalculator()
        drive(other, detector(refractory=30), three_peaks())
        self.assertNotEqual(
            other.summary()["parameter_signatures_seen"],
            self.summary["parameter_signatures_seen"],
            "a different refractory is a different population and must read as one",
        )
        self.assertTrue(self.summary["parameters_uniform_across_segments"])
        self.assertEqual(self.summary["parameters"]["refractory_seconds"], nc.REFRACTORY)

    def test_no_arithmetic_mean_is_formed_anywhere(self) -> None:
        for row in self.calc.companion_rows():
            with self.subTest(measure=row["measure"]):
                self.assertNotIn("arithmetic_mean", row["value"])
                self.assertIn("arithmetic_mean_forbidden", row["value"])

    def test_the_outcome_row_rates_are_ratios_of_that_rows_own_counts(self) -> None:
        rows = [r for r in self.calc.companion_rows() if r["measure"] == "detector_second_outcome"]
        self.assertEqual(len(rows), 1)
        counts = rows[0]["value"]["counts"]
        rates = rows[0]["value"]["rates"]
        self.assertEqual(rates["promotion_rate"]["numerator"], counts[PROMOTED])
        self.assertEqual(rates["considered"], derive(counts)["considered"])
        self.assertEqual(rates["promotion_rate"]["denominator"], rates["considered"])

    def test_the_summary_declares_it_was_fed(self) -> None:
        self.assertEqual(self.summary["status"], FED)
        self.assertEqual(self.summary["segments_closed"], 1)
        self.assertEqual(self.summary["seconds_accounted"], 300)
        self.assertEqual(self.summary["partition_identity"]["segments_verified"], 1)


class StratificationTest(unittest.TestCase):
    def test_outcomes_land_in_the_phase_the_traversal_was_in_when_they_became_known(self) -> None:
        calc = DetectorCoverageCalculator()
        drive(calc, detector(), three_peaks(), phase_at=lambda s: "ETH" if s < 150 else "RTH")
        rows = [r for r in calc.companion_rows() if r["measure"] == "detector_second_outcome"]
        phases = {r["stratum"]["session_phase"] for r in rows}
        self.assertEqual(phases, {"ETH", "RTH"})
        total = sum(r["value"]["n"] for r in rows)
        self.assertEqual(total, calc.summary()["seconds_judged"],
                         "per-phase rows partition the segment; nothing pools and nothing is lost")

    def test_nan_seconds_past_warmup_are_counted_not_derived(self) -> None:
        series = three_peaks()
        for second in range(200, 260):
            series[second] = math.nan
        calc = DetectorCoverageCalculator()
        drive(calc, detector(), series)
        summary = calc.summary()
        self.assertGreaterEqual(summary["seconds_without_finite_flow"], 60)
        self.assertEqual(
            summary["searched_seconds"],
            summary["considered"] + summary["seconds_without_finite_flow"],
        )

    def test_a_segment_that_searched_nothing_is_still_a_row(self) -> None:
        calc = DetectorCoverageCalculator()
        det = detector()
        calc.open_segment(det)
        row = calc.close_segment(det, continuity_segment=1, recv_ns=0, occasion="SEGMENT_CLOSE",
                                 **CTX)
        self.assertTrue(row["partition_identity_holds"])
        self.assertEqual(row["detector_counters"]["seconds_judged"], 0)
        self.assertEqual(calc.summary()["segments_closed"], 1)

    def test_unfed_it_declares_itself_rather_than_reporting_a_bare_zero(self) -> None:
        summary = DetectorCoverageCalculator().summary()
        self.assertEqual(summary["status"], NOT_FED)
        self.assertEqual(summary["promoted"], 0)
        self.assertIsNone(summary["promotion_rate"]["value"])
        self.assertEqual(summary["promotion_rate"]["denominator"], 0)


class RefusalTest(unittest.TestCase):
    """Each refusal is produced, because a guard whose firing branch never ran is untested."""

    def test_an_unnamed_rejection_counter_is_refused_at_open(self) -> None:
        class Widened(nc.CausalPeakDetector):
            def counters(self):
                return {**super().counters(), "rejected_by_a_new_rule": 0}

        with self.assertRaises(DetectorCoverageError) as caught:
            DetectorCoverageCalculator().open_segment(
                Widened(continuity_segment=1, warmup_seconds=WARMUP))
        self.assertIn("rejected_by_a_new_rule", str(caught.exception))

    def test_a_stray_rejection_in_the_summary_alone_is_refused(self) -> None:
        class Prose(nc.CausalPeakDetector):
            def summary(self):
                return {**super().summary(), "suppressed_by_something_else": 0}

        with self.assertRaises(DetectorCoverageError) as caught:
            DetectorCoverageCalculator().open_segment(
                Prose(continuity_segment=1, warmup_seconds=WARMUP))
        self.assertIn("suppressed_by_something_else", str(caught.exception))

    def test_a_counter_the_detector_stopped_exposing_is_refused(self) -> None:
        class Narrowed(nc.CausalPeakDetector):
            def counters(self):
                out = super().counters()
                del out["suppressed_by_prominence"]
                return out

        with self.assertRaises(DetectorCoverageError) as caught:
            DetectorCoverageCalculator().open_segment(
                Narrowed(continuity_segment=1, warmup_seconds=WARMUP))
        self.assertIn("suppressed_by_prominence", str(caught.exception))

    def test_a_judged_second_with_no_named_outcome_is_refused_not_binned(self) -> None:
        """The defect class itself: a second judged and binned nowhere, exactly as the
        release-time refractory exit used to be. It passes every per-second check - one fed,
        one judged, counters monotone, totals reconciled - and only the partition catches it."""

        class Leaky(nc.CausalPeakDetector):
            def _judge(self, idx):
                second, _value = self._flow[idx]
                if second == 150:
                    self.seconds_judged += 1        # judged, and left by no door
                    return None
                return super()._judge(idx)

        calc = DetectorCoverageCalculator()
        det = Leaky(continuity_segment=1, warmup_seconds=WARMUP, min_threshold_observations=30,
                    selection_rule=nc.CAUSAL_WINDOWED_PROMINENCE)
        calc.open_segment(det)
        for second, value in enumerate(three_peaks()):
            det.observe(second, value)
            calc.observe_second(det, second=second, continuity_segment=1, **CTX)
        det.finish(299)
        with self.assertRaises(DetectorCoverageError) as caught:
            calc.close_segment(det, continuity_segment=1, recv_ns=0, occasion="STREAM_END", **CTX)
        self.assertIn("does not name", str(caught.exception))
        self.assertIn("1 judged second", str(caught.exception))

    def test_a_section_total_that_disagrees_with_the_detector_is_refused(self) -> None:
        calc = DetectorCoverageCalculator()
        det = detector()
        calc.open_segment(det)
        for second, value in enumerate(three_peaks()):
            det.observe(second, value)
            calc.observe_second(det, second=second, continuity_segment=1, **CTX)
        det.finish(299)
        calc._ledgers[1].totals["candidates_emitted"] -= 1
        with self.assertRaises(DetectorCoverageError) as caught:
            calc.close_segment(det, continuity_segment=1, recv_ns=0, occasion="STREAM_END", **CTX)
        self.assertIn("disagree", str(caught.exception))

    def test_a_counter_moving_backwards_is_refused(self) -> None:
        calc = DetectorCoverageCalculator()
        det = detector()
        calc.open_segment(det)
        for second, value in enumerate(flat_then({120: 0.9}, length=150)):
            det.observe(second, value)
            calc.observe_second(det, second=second, continuity_segment=1, **CTX)
        self.assertGreater(det.rejected_below_threshold, 0, "nothing to move backwards")
        det.rejected_below_threshold -= 1
        with self.assertRaises(DetectorCoverageError) as caught:
            calc.observe_second(det, second=150, continuity_segment=1, **CTX)
        self.assertIn("backwards", str(caught.exception))

    def test_a_detector_never_opened_is_refused(self) -> None:
        with self.assertRaises(DetectorCoverageError):
            DetectorCoverageCalculator().observe_second(
                detector(), second=0, continuity_segment=1, **CTX)

    def test_a_closed_segment_does_not_reopen(self) -> None:
        calc = DetectorCoverageCalculator()
        det = detector()
        drive(calc, det, flat_then({100: 0.9}, length=120))
        with self.assertRaises(DetectorCoverageError):
            calc.observe_second(det, second=120, continuity_segment=1, **CTX)
        with self.assertRaises(DetectorCoverageError):
            calc.open_segment(detector())

    def test_the_traversals_segment_must_be_the_detectors(self) -> None:
        calc = DetectorCoverageCalculator()
        det = detector(segment=5)
        calc.open_segment(det)
        det.observe(0, 0.01)
        with self.assertRaises(DetectorCoverageError) as caught:
            calc.observe_second(det, second=0, continuity_segment=6, **CTX)
        self.assertIn("segment", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
