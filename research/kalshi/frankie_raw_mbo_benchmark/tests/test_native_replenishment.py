"""Tests for section 4.7 replenishment and liquidity resilience."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_replenishment import (
    ARRIVAL_ATTRIBUTION_RULE,
    CENSORED_SEGMENT_END,
    CENSORED_STREAM_END,
    NEIGHBORING_PRICE,
    NEVER_RESTORED,
    NEW_LIQUIDITY,
    RESHAPED_RESIDUAL,
    NEIGHBORHOOD_ARRIVAL_FORMULA,
    RESTORED,
    SAME_PRICE,
    ReplenishmentCalculator,
    ReplenishmentError,
)

HORIZON = 1_000


def open_kwargs(**overrides):
    base = dict(
        instrument_id=42,
        side="B",
        price_raw=1000,
        recv_ns=10_000,
        continuity_segment=0,
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        family_id="TFCN",
        session_phase="RTH",
        touch_state_at_open="AT_TOUCH",
        removed_quantity=10,
        removed_order_count=2,
        depth_at_open=100,
        touch_price_at_open=1000,
    )
    base.update(overrides)
    return base


class ReplenishmentCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = ReplenishmentCalculator(horizon_ns=HORIZON)

    def test_a_zero_removal_is_not_a_contact(self) -> None:
        with self.assertRaises(ReplenishmentError):
            self.calc.open_episode(**open_kwargs(removed_quantity=0))

    def test_nonpositive_horizon_is_refused(self) -> None:
        with self.assertRaises(ReplenishmentError):
            ReplenishmentCalculator(horizon_ns=0)

    def test_nothing_is_emitted_before_the_horizon_elapses(self) -> None:
        """Deferred emission: an outcome is not available until stream time reaches it."""
        self.calc.open_episode(**open_kwargs())
        self.assertEqual(self.calc.advance(10_500), [])
        self.assertEqual(self.calc.pending_count, 1)

    def test_the_episode_emits_once_the_horizon_is_reached(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=6, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_400)
        rows = self.calc.advance(11_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], RESTORED)
        self.assertEqual(rows[0]["time_to_restoration_ns"], 400)
        self.assertEqual(self.calc.pending_count, 0)

    def test_emission_time_is_the_horizon_not_the_observation_that_triggered_it(self) -> None:
        """A late advance must not backdate or postdate the causal cutoff."""
        self.calc.open_episode(**open_kwargs())
        rows = self.calc.advance(999_999)
        self.assertEqual(rows[0]["closed_recv_ns"], 10_000 + HORIZON)

    def test_never_restored_is_resolved_not_censored(self) -> None:
        self.calc.open_episode(**open_kwargs())
        rows = self.calc.advance(11_000)
        self.assertEqual(rows[0]["outcome"], NEVER_RESTORED)
        self.assertTrue(rows[0]["resolved"])
        self.assertFalse(rows[0]["censored"])
        self.assertEqual(self.calc.never_restored_count, 1)

    def test_never_restored_is_distinct_from_not_yet_observed(self) -> None:
        """The whole point of deferring: an unfinished episode is not a negative result."""
        self.calc.open_episode(**open_kwargs())
        self.calc.open_episode(**open_kwargs(recv_ns=999_000))
        resolved = self.calc.advance(11_000)
        censored = self.calc.finalize(recv_ns=999_500)
        self.assertEqual(resolved[0]["outcome"], NEVER_RESTORED)
        self.assertEqual(censored[0]["outcome"], CENSORED_STREAM_END)
        self.assertTrue(censored[0]["censored"])
        self.assertFalse(censored[0]["resolved"])

    def test_new_liquidity_and_reshaped_residual_are_never_summed_into_one_figure(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=4, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        episode.add_refill(quantity=3, liquidity_kind=RESHAPED_RESIDUAL, price_relation=SAME_PRICE, recv_ns=10_200)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["new_id_add_quantity"], 4)
        self.assertEqual(row["same_id_modify_quantity"], 3)
        self.assertEqual(row["new_id_add_count"], 1)
        self.assertEqual(row["same_id_modify_count"], 1)
        self.assertEqual(row["replaced_quantity"], 7)

    def test_same_and_neighboring_price_refills_are_separated(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=4, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        episode.add_refill(
            quantity=5, liquidity_kind=NEW_LIQUIDITY, price_relation=NEIGHBORING_PRICE, recv_ns=10_200
        )
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["same_price_refill_quantity"], 4)
        self.assertEqual(row["neighboring_price_refill_quantity"], 5)

    def test_overshoot_is_measured_above_the_removal(self) -> None:
        episode = self.calc.open_episode(**open_kwargs(removed_quantity=10))
        episode.add_refill(quantity=14, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["overshoot_quantity"], 4)
        self.assertEqual(row["neighborhood_arrival_ratio"], 1.4)

    def test_no_overshoot_reports_zero_which_is_an_observation(self) -> None:
        episode = self.calc.open_episode(**open_kwargs(removed_quantity=10))
        episode.add_refill(quantity=3, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["overshoot_quantity"], 0)
        self.assertEqual(row["neighborhood_arrival_ratio"], 0.3)

    def test_touch_restoration_is_tracked_separately_from_quantity(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.restore_touch(10_600)
        episode.restore_touch(10_900)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["touch_restoration_ns"], 600, "first restoration wins, not the latest")

    def test_a_refill_before_the_removal_is_refused(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        with self.assertRaises(ReplenishmentError):
            episode.add_refill(
                quantity=1, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=9_999
            )

    def test_unknown_liquidity_kind_or_price_relation_is_refused(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        with self.assertRaises(ReplenishmentError):
            episode.add_refill(quantity=1, liquidity_kind="GUESS", price_relation=SAME_PRICE, recv_ns=10_100)
        with self.assertRaises(ReplenishmentError):
            episode.add_refill(quantity=1, liquidity_kind=NEW_LIQUIDITY, price_relation="NEARBY", recv_ns=10_100)

    def test_segment_end_censors_rather_than_letting_a_horizon_span_a_boundary(self) -> None:
        self.calc.open_episode(**open_kwargs())
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=10_300)
        self.assertEqual(rows[0]["outcome"], CENSORED_SEGMENT_END)
        self.assertTrue(rows[0]["censored"])
        self.assertEqual(self.calc.pending_count, 0)

    def test_segment_end_only_touches_its_own_segment(self) -> None:
        self.calc.open_episode(**open_kwargs(continuity_segment=0))
        self.calc.open_episode(**open_kwargs(continuity_segment=1))
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=10_300)
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.calc.pending_count, 1)

    def test_a_censored_episode_still_contributes_its_restoration_if_one_occurred(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=2, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        self.calc.close_continuity_segment(segment=0, recv_ns=10_300)
        survival = self.calc.time_to_restoration.rows()[0]["value"]
        self.assertEqual(survival["observed_events"], 1)
        self.assertEqual(survival["censored_observations"], 0)

    def test_censored_episodes_are_excluded_from_replaced_quantity_and_counted(self) -> None:
        self.calc.open_episode(**open_kwargs())
        self.calc.close_continuity_segment(segment=0, recv_ns=10_300)
        row = self.calc.replaced_quantity.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_neighborhood_arrival_ratio_keeps_both_coequal_forms(self) -> None:
        for quantity, removed in ((1, 1), (1, 99)):
            episode = self.calc.open_episode(**open_kwargs(removed_quantity=removed))
            episode.add_refill(
                quantity=quantity, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100
            )
        self.calc.advance(11_000)
        value = self.calc.neighborhood_arrival_ratio.rows()[0]["value"]
        self.assertAlmostEqual(value["mean_of_member_ratios"], (1.0 + 1.0 / 99.0) / 2)
        self.assertAlmostEqual(value["ratio_of_aggregate_sums"], 2.0 / 100.0)
        self.assertEqual(value["difference_label"], "COMPLEMENTARY_SCOPE_DIFFERENCE")

    def test_every_episode_reaches_the_survival_estimator_exactly_once(self) -> None:
        for index in range(3):
            self.calc.open_episode(**open_kwargs(recv_ns=10_000 + index))
        self.calc.advance(20_000)
        survival = self.calc.time_to_restoration.rows()[0]["value"]
        self.assertEqual(survival["total_observations"], 3)

    def test_touch_state_separates_strata(self) -> None:
        self.calc.open_episode(**open_kwargs(touch_state_at_open="AT_TOUCH"))
        self.calc.open_episode(**open_kwargs(touch_state_at_open="DEEP"))
        self.calc.advance(20_000)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.removed_quantity.rows()}
        self.assertEqual(subfamilies, {"touch=AT_TOUCH", "touch=DEEP"})

    def test_days_do_not_pool(self) -> None:
        self.calc.open_episode(**open_kwargs(source_day="20211004"))
        self.calc.open_episode(**open_kwargs(source_day="20211005"))
        self.calc.advance(20_000)
        days = {r["stratum"]["source_day"] for r in self.calc.removed_quantity.rows()}
        self.assertEqual(days, {"20211004", "20211005"})

    def test_pending_set_is_bounded_by_the_horizon_not_the_stream(self) -> None:
        for index in range(500):
            self.calc.open_episode(**open_kwargs(recv_ns=10_000 + index))
            self.calc.advance(10_000 + index)
        self.assertLessEqual(self.calc.pending_count, HORIZON + 1)
        self.calc.advance(10_000 + 500 + HORIZON)
        self.assertEqual(self.calc.pending_count, 0)
        self.assertEqual(self.calc.opened, 500)

    def test_pending_lookup_by_level(self) -> None:
        self.calc.open_episode(**open_kwargs(price_raw=1000))
        self.calc.open_episode(**open_kwargs(price_raw=1001))
        self.assertEqual(len(self.calc.pending_at(42, "B", 1000)), 1)
        self.assertEqual(len(self.calc.pending_at(42, "A", 1000)), 0)

    def test_summary_declares_the_emission_policy(self) -> None:
        self.calc.open_episode(**open_kwargs())
        self.calc.advance(11_000)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.7")
        self.assertEqual(summary["emission"], "DEFERRED_UNTIL_HORIZON_ELAPSED_IN_STREAM_TIME")
        self.assertEqual(summary["episodes_opened"], 1)


class ArrivalDensityNamingTest(unittest.TestCase):
    """D-3: the name was the defect, so these tests are about what the name claims.

    The delivered run reported an aggregate 14.24 under the name `restoration_ratio`, built
    from 441,404 arrivals credited across 24,283 episodes - 18.18 attributions each - against
    a median removed quantity of 1 to 2 lots. Nothing about the arithmetic is wrong. Every
    assertion below is about whether a reader can tell what they are holding.
    """

    def setUp(self) -> None:
        self.calc = ReplenishmentCalculator(horizon_ns=HORIZON)

    def test_no_number_goes_out_under_a_name_that_claims_replacement(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=6, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        row = self.calc.advance(11_000)[0]
        self.assertNotIn("restoration_ratio", row)
        self.assertIn("neighborhood_arrival_ratio", row)
        self.assertNotIn(
            "restoration_ratio",
            {r["measure"] for r in self.calc.companion_rows()},
        )

    def test_the_old_name_is_refused_loudly_rather_than_quietly_still_working(self) -> None:
        """D60's third option. A caller asking for a replacement ratio must not be handed
        an arrival density under the name it asked for."""
        episode = self.calc.open_episode(**open_kwargs())
        with self.assertRaises(ReplenishmentError):
            episode.restoration_ratio
        with self.assertRaises(ReplenishmentError):
            self.calc.restoration_ratio

    def test_the_formula_travels_on_the_episode_row(self) -> None:
        """A caveat that lives only in a docstring expires the first time a row is read alone."""
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=6, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["neighborhood_arrival_ratio_formula"], NEIGHBORHOOD_ARRIVAL_FORMULA)
        self.assertIn("NOT the share", row["neighborhood_arrival_ratio_formula"])
        self.assertEqual(row["attribution_rule"], ARRIVAL_ATTRIBUTION_RULE)

    def test_the_stratified_measure_declares_the_same_formula(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        episode.add_refill(quantity=6, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        self.calc.advance(11_000)
        (row,) = [
            r for r in self.calc.companion_rows() if r["measure"] == "neighborhood_arrival_ratio"
        ]
        self.assertIn("arrival density", row["declaration"]["numerator_formula"])
        self.assertIn("every pending episode", row["declaration"]["numerator_formula"])

    def test_the_multiplicity_is_a_number_in_the_artifact_not_a_division_to_do_later(self) -> None:
        """441,404 / 24,283 lived in two different documents. It lives on the value now."""
        first = self.calc.open_episode(**open_kwargs())
        second = self.calc.open_episode(**open_kwargs(recv_ns=10_001))
        for recv_ns in (10_100, 10_200, 10_300):
            # One arrival, credited to both pending episodes - the rule under test.
            for episode in (first, second):
                episode.add_refill(
                    quantity=2,
                    liquidity_kind=NEW_LIQUIDITY,
                    price_relation=SAME_PRICE,
                    recv_ns=recv_ns,
                )
        rows = self.calc.advance(12_000)
        summary = self.calc.summary()
        self.assertEqual([row["refill_attributions"] for row in rows], [3, 3])
        self.assertEqual(summary["refill_attributions"], 6)
        self.assertEqual(summary["episodes_closed"], 2)
        self.assertEqual(summary["attributions_per_episode"], 3.0)
        self.assertEqual(summary["attribution_rule"], ARRIVAL_ATTRIBUTION_RULE)

    def test_the_multiplicity_is_visible_per_stratum_not_only_in_the_traversal(self) -> None:
        episode = self.calc.open_episode(**open_kwargs())
        for recv_ns in (10_100, 10_200):
            episode.add_refill(
                quantity=1, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=recv_ns
            )
        self.calc.advance(11_000)
        (row,) = [
            r
            for r in self.calc.companion_rows()
            if r["measure"] == "refill_attributions_per_episode"
        ]
        self.assertEqual(row["value"]["n"], 1)
        self.assertEqual(row["value"]["maximum"], 2.0)

    def test_a_censored_episode_is_excluded_from_the_multiplicity_and_counted(self) -> None:
        """Its exposure to arrivals was cut short, so its count is not a comparable one."""
        self.calc.open_episode(**open_kwargs())
        self.calc.close_continuity_segment(segment=0, recv_ns=10_300)
        (row,) = [
            r
            for r in self.calc.companion_rows()
            if r["measure"] == "refill_attributions_per_episode"
        ]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_the_multiplicity_before_anything_closes_is_absent_not_zero(self) -> None:
        """Zero would say each arrival was credited to no episode, which is a false claim."""
        self.calc.open_episode(**open_kwargs())
        self.assertIsNone(self.calc.summary()["attributions_per_episode"])
        self.assertEqual(self.calc.summary()["episodes_closed"], 0)

    def test_the_summary_names_the_measure_it_replaced(self) -> None:
        """The rename must be joinable to run 33605852433, or the comparison is lost."""
        summary = self.calc.summary()
        self.assertEqual(
            summary["renamed_measures"], {"restoration_ratio": "neighborhood_arrival_ratio"}
        )
        self.assertIn("D-3", summary["rename_reason"])

    def test_the_relabel_left_the_arithmetic_alone(self) -> None:
        """A regression pin, deliberately. Changing the attribution here would silently
        invalidate every comparison with the delivered run, which is why D-3 was prescribed
        as a relabel."""
        episode = self.calc.open_episode(**open_kwargs(removed_quantity=10))
        episode.add_refill(quantity=4, liquidity_kind=NEW_LIQUIDITY, price_relation=SAME_PRICE, recv_ns=10_100)
        episode.add_refill(quantity=3, liquidity_kind=RESHAPED_RESIDUAL, price_relation=SAME_PRICE, recv_ns=10_200)
        row = self.calc.advance(11_000)[0]
        self.assertEqual(row["replaced_quantity"], 7)
        self.assertEqual(row["neighborhood_arrival_ratio"], 0.7)
        value = self.calc.neighborhood_arrival_ratio.rows()[0]["value"]
        self.assertEqual(value["numerator_total"], 7.0)
        self.assertEqual(value["denominator_total"], 10.0)

    def test_a_zero_removal_ratio_is_none_rather_than_zero(self) -> None:
        """Unchanged from before the relabel, and restated because it is the same discipline:
        no denominator is not a ratio of zero."""
        episode = self.calc.open_episode(**open_kwargs())
        episode.removed_quantity = 0
        self.assertIsNone(episode.neighborhood_arrival_ratio)

if __name__ == "__main__":
    unittest.main()
