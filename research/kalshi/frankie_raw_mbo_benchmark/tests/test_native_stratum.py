"""Tests for the parallel-view rule as enforced structure."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    COMPLEMENTARY,
    QUANTILE_BASIS_EXACT,
    QUANTILE_BASIS_RESERVOIR,
    Declaration,
    RatioPair,
    StratifiedMeasure,
    CLUSTERING_NOT_RUN,
    StratumError,
    StratumKey,
    StreamingDistribution,
    SurvivalAccumulator,
    cross_day_synthesis,
)


def key(**overrides) -> StratumKey:
    base = dict(
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="AN_TFMN_TFCN",
        side_orientation="BID",
        session_phase="RTH",
        clock="ts_recv_ns",
    )
    base.update(overrides)
    return StratumKey(**base)


def declaration(**overrides) -> Declaration:
    base = dict(
        numerator_formula="sum(event_to_receive_latency_ns)",
        population="F_LAST-closed groups in the stratum",
        causal_cutoff="F_LAST receive time",
        status="RESOLVED",
        missingness_rule="components without a receive timestamp are excluded and counted",
    )
    base.update(overrides)
    return Declaration(**base)


class StratumKeyTest(unittest.TestCase):
    def test_keys_differing_in_any_forbidden_dimension_do_not_collide(self) -> None:
        for field_name, value in (
            ("source_day", "20211005"),
            ("family_id", "OTHER"),
            ("side_orientation", "ASK"),
            ("session_phase", "ETH"),
            ("clock", "ts_event_ns"),
            ("continuity_segment", 1),
            ("subfamily_id", "sub"),
            ("cluster_version", "v2"),
            ("chain_signature", "D3"),
        ):
            with self.subTest(field=field_name):
                self.assertNotEqual(key(), key(**{field_name: value}))

    def test_identical_keys_collide(self) -> None:
        self.assertEqual(key(), key())
        self.assertEqual(hash(key()), hash(key()))

    def test_empty_or_wrong_typed_identity_is_refused(self) -> None:
        with self.assertRaises(StratumError):
            key(family_id="")
        with self.assertRaises(StratumError):
            key(continuity_segment=-1)
        with self.assertRaises(StratumError):
            key(continuity_segment="0")


class ClusterVersionTest(unittest.TestCase):
    """D-14. 16,209 of 16,293 averaged rows declared nothing, and every gate passed.

    Contract section 3 requires every average to declare family, subfamily AND cluster
    version. The field defaulted to the empty string and only 4.16's 84 rows ever set it.
    """

    def test_the_empty_string_is_refused(self) -> None:
        """It is the ABSENCE of a declaration, not a declaration that clustering was absent."""
        with self.assertRaises(StratumError):
            key(cluster_version="")

    def test_the_default_is_a_declaration_not_a_blank(self) -> None:
        self.assertEqual(key().cluster_version, CLUSTERING_NOT_RUN)
        self.assertTrue(CLUSTERING_NOT_RUN)

    def test_the_declaration_reaches_the_emitted_row(self) -> None:
        """A field that never leaves the key cannot be read by anyone auditing the artifact."""
        self.assertEqual(key().as_dict()["cluster_version"], CLUSTERING_NOT_RUN)

    def test_a_real_cluster_version_still_keys_apart_from_the_default(self) -> None:
        self.assertNotEqual(key(cluster_version="disc-v3"), key())


class DeclarationTest(unittest.TestCase):
    def test_every_declaration_field_is_mandatory(self) -> None:
        for field_name in ("numerator_formula", "population", "causal_cutoff", "missingness_rule"):
            with self.subTest(field=field_name):
                with self.assertRaises(StratumError):
                    declaration(**{field_name: "  "})

    def test_status_is_constrained(self) -> None:
        with self.assertRaises(StratumError):
            declaration(status="PROBABLY_FINE")
        for status in ("RESOLVED", "CENSORED", "STILL_OPEN"):
            self.assertEqual(declaration(status=status).status, status)


class StreamingDistributionTest(unittest.TestCase):
    def test_exact_statistics_on_a_known_sample(self) -> None:
        dist = StreamingDistribution()
        for value in (1.0, 2.0, 3.0, 4.0, 100.0):
            dist.add(value)
        row = dist.as_dict()
        self.assertEqual(row["n"], 5)
        self.assertEqual(row["sum"], 110.0)
        self.assertEqual(row["arithmetic_mean"], 22.0)
        self.assertEqual(row["minimum"], 1.0)
        self.assertEqual(row["maximum"], 100.0)
        self.assertEqual(row["p50"], 3.0)
        self.assertEqual(row["quantile_basis"], QUANTILE_BASIS_EXACT)

    def test_maximum_stays_exact_after_the_reservoir_bound(self) -> None:
        """The maximum is the heavy-tail evidence; it must never be sampled away."""
        dist = StreamingDistribution(exact_cap=10)
        for value in range(1, 1001):
            dist.add(float(value))
        row = dist.as_dict()
        self.assertEqual(row["n"], 1000)
        self.assertEqual(row["maximum"], 1000.0)
        self.assertEqual(row["minimum"], 1.0)
        self.assertEqual(row["sum"], sum(float(v) for v in range(1, 1001)))
        self.assertEqual(row["quantile_basis"], QUANTILE_BASIS_RESERVOIR)
        self.assertEqual(row["quantile_sample_size"], 10)
        self.assertIsNotNone(row["quantile_reservoir_seed"])

    def test_approximation_is_declared_not_silent(self) -> None:
        dist = StreamingDistribution(exact_cap=3)
        for value in (1.0, 2.0, 3.0):
            dist.add(value)
        self.assertEqual(dist.as_dict()["quantile_basis"], QUANTILE_BASIS_EXACT)
        dist.add(4.0)
        self.assertEqual(dist.as_dict()["quantile_basis"], QUANTILE_BASIS_RESERVOIR)

    def test_nan_is_refused_rather_than_averaged(self) -> None:
        dist = StreamingDistribution()
        with self.assertRaises(StratumError):
            dist.add(float("nan"))

    def test_empty_distribution_reports_none_not_zero(self) -> None:
        row = StreamingDistribution().as_dict()
        self.assertIsNone(row["arithmetic_mean"])
        self.assertIsNone(row["maximum"])
        self.assertEqual(row["n"], 0)


class RatioPairTest(unittest.TestCase):
    def test_both_ratios_are_retained_and_can_disagree(self) -> None:
        """Simpson-style divergence is the reason section 4.8 keeps both."""
        pair = RatioPair()
        pair.add(1.0, 1.0)     # member ratio 1.0
        pair.add(1.0, 99.0)    # member ratio ~0.0101
        row = pair.as_dict()
        self.assertAlmostEqual(row["mean_of_member_ratios"], (1.0 + 1.0 / 99.0) / 2)
        self.assertAlmostEqual(row["ratio_of_aggregate_sums"], 2.0 / 100.0)
        self.assertNotAlmostEqual(row["mean_of_member_ratios"], row["ratio_of_aggregate_sums"])
        self.assertEqual(row["difference_label"], COMPLEMENTARY)
        self.assertTrue(row["coequal"])

    def test_zero_denominator_members_are_counted_not_dropped(self) -> None:
        pair = RatioPair()
        pair.add(5.0, 0.0)
        pair.add(2.0, 4.0)
        row = pair.as_dict()
        self.assertEqual(row["zero_denominator_members"], 1)
        self.assertEqual(row["member_ratio_distribution"]["n"], 1)
        self.assertEqual(row["numerator_total"], 7.0)

    def test_indeterminate_members_stay_explicit(self) -> None:
        pair = RatioPair()
        pair.add_indeterminate()
        self.assertEqual(pair.as_dict()["indeterminate_members"], 1)


class SurvivalAccumulatorTest(unittest.TestCase):
    def test_kaplan_meier_matches_a_worked_example(self) -> None:
        """n=5: events at t=1 and t=4, censored at t=2. S = 0.8 then 0.8*(1-1/3)."""
        survival = SurvivalAccumulator()
        survival.add(1.0, event_observed=True)
        survival.add(2.0, event_observed=False)
        survival.add(4.0, event_observed=True)
        survival.add(5.0, event_observed=False)
        survival.add(5.0, event_observed=False)
        curve = {row["time"]: row for row in survival.curve()}
        self.assertEqual(curve[1.0]["at_risk"], 5)
        self.assertAlmostEqual(curve[1.0]["survival"], 0.8)
        self.assertEqual(curve[2.0]["at_risk"], 4)
        self.assertAlmostEqual(curve[2.0]["survival"], 0.8)
        self.assertEqual(curve[4.0]["at_risk"], 3)
        self.assertAlmostEqual(curve[4.0]["survival"], 0.8 * (2.0 / 3.0))
        self.assertEqual(curve[5.0]["at_risk"], 2)

    def test_at_risk_counts_are_present_at_every_time(self) -> None:
        survival = SurvivalAccumulator()
        for t in (1.0, 2.0, 3.0):
            survival.add(t, event_observed=True)
        self.assertTrue(all("at_risk" in row for row in survival.curve()))

    def test_censored_observations_are_reported_separately(self) -> None:
        survival = SurvivalAccumulator()
        survival.add(1.0, event_observed=True)
        survival.add(2.0, event_observed=False)
        row = survival.as_dict()
        self.assertEqual(row["observed_events"], 1)
        self.assertEqual(row["censored_observations"], 1)
        self.assertEqual(row["estimator"], "KAPLAN_MEIER_PRODUCT_LIMIT")

    def test_negative_time_is_refused(self) -> None:
        with self.assertRaises(StratumError):
            SurvivalAccumulator().add(-1.0, event_observed=True)


class StratifiedMeasureTest(unittest.TestCase):
    def test_distinct_strata_accumulate_independently(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        measure.observe(key(), 10.0)
        measure.observe(key(source_day="20211005"), 1000.0)
        self.assertEqual(measure.stratum_count, 2)
        by_day = {row["stratum"]["source_day"]: row for row in measure.rows()}
        self.assertEqual(by_day["20211004"]["value"]["maximum"], 10.0)
        self.assertEqual(by_day["20211005"]["value"]["maximum"], 1000.0)

    def test_every_row_carries_identity_and_declarations(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        measure.observe(key(), 10.0)
        row = measure.rows()[0]
        for field_name in ("source_day", "family_id", "side_orientation", "session_phase", "clock"):
            self.assertIn(field_name, row["stratum"])
        for field_name in ("numerator_formula", "population", "causal_cutoff", "status", "missingness_rule"):
            self.assertIn(field_name, row["declaration"])

    def test_a_raw_tuple_key_is_refused(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        with self.assertRaises(StratumError):
            measure.observe(("20211004", "BID"), 10.0)

    def test_excluded_members_are_reported_per_stratum(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        measure.observe(key(), 10.0)
        measure.exclude_missing(key(), 3)
        self.assertEqual(measure.rows()[0]["excluded_missing_members"], 3)

    def test_ratio_and_survival_kinds_route_correctly(self) -> None:
        ratios = StratifiedMeasure(name="absorption", declaration=declaration(), kind="RATIO_PAIR")
        ratios.observe(key(), 1.0, 2.0)
        self.assertEqual(ratios.rows()[0]["value"]["ratio_of_aggregate_sums"], 0.5)

        survival = StratifiedMeasure(name="time_to_exit", declaration=declaration(status="CENSORED"), kind="SURVIVAL")
        survival.observe(key(), 3.0, event_observed=True)
        self.assertEqual(survival.rows()[0]["value"]["estimator"], "KAPLAN_MEIER_PRODUCT_LIMIT")

    def test_indeterminate_is_only_valid_for_a_ratio_measure(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        with self.assertRaises(StratumError):
            measure.observe_indeterminate(key())

    def test_unknown_kind_is_refused(self) -> None:
        with self.assertRaises(StratumError):
            StratifiedMeasure(name="x", declaration=declaration(), kind="MEAN")


class CrossDaySynthesisTest(unittest.TestCase):
    def test_synthesis_retains_every_day_level_row_and_reports_no_pooled_scalar(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        measure.observe(key(), 10.0)
        measure.observe(key(source_day="20211005"), 20.0)
        synthesis = cross_day_synthesis(measure, justification="same instrument, same session, same family")
        self.assertFalse(synthesis["primary"])
        self.assertEqual(synthesis["source_days"], ["20211004", "20211005"])
        self.assertEqual(len(synthesis["per_day_rows_retained"]), 2)
        self.assertIsNone(synthesis["pooled_scalar"])

    def test_synthesis_without_a_commensurability_argument_is_refused(self) -> None:
        measure = StratifiedMeasure(name="latency_ns", declaration=declaration())
        measure.observe(key(), 10.0)
        with self.assertRaises(StratumError):
            cross_day_synthesis(measure, justification="   ")


if __name__ == "__main__":
    unittest.main()
