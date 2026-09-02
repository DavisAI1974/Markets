"""Tests for section 4.16 fixed causal future-response table."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_response import (
    CENSORED_BOUNDARY,
    CENSORED_STREAM_END,
    COMPLETION_RESPONSE,
    CONTRACT_CHANNELS,
    DEPTH_SCOPE_FULL_BOOK,
    EXACT_AT_HORIZON,
    FLOW_RESPONSE,
    FULL_BOOK_RESPONSE,
    HORIZON_SETS,
    LATE_BEYOND_HORIZON,
    LATE_WITHIN_HORIZON,
    MATURED,
    NS_PER_MS,
    NS_PER_S,
    PENDING,
    PRICE_RESPONSE,
    QUEUE_RESPONSE,
    REGIME_BASIS_UNDECLARED,
    REGIME_CONSTANT,
    REGIME_CONDITIONS,
    SURVIVAL_RESPONSE,
    TRANSITION_RESPONSE,
    ChannelReading,
    HorizonObservation,
    ResponseError,
    ResponseTableCalculator,
    channel_values,
    horizons_for_version,
)

HORIZONS = (100, 1_000)


def track_kwargs(**overrides):
    base = dict(
        structure_id="s1",
        first_lawful_recv_ns=10_000,
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="TFCN",
        side_orientation="B",
        session_phase="RTH",
        cluster_version="v1",
        starting_liquidity_regime="THIN",
    )
    base.update(overrides)
    return base


def values_for(_track, horizon):
    return {"price_response": float(horizon)}


class HorizonObservationTest(unittest.TestCase):
    def test_a_horizon_is_written_once(self) -> None:
        """Section 4.16: preserve the earliest observation, never substitute a later one."""
        obs = HorizonObservation(horizon_ns=100, due_recv_ns=1_000)
        obs.record(read_recv_ns=1_000, values={"price_response": 5.0})
        with self.assertRaises(ResponseError):
            obs.record(read_recv_ns=1_200, values={"price_response": 99.0})
        self.assertEqual(obs.values["price_response"], 5.0)

    def test_recording_before_the_horizon_is_due_is_refused(self) -> None:
        obs = HorizonObservation(horizon_ns=100, due_recv_ns=1_000)
        with self.assertRaises(ResponseError):
            obs.record(read_recv_ns=999, values={"price_response": 1.0})

    def test_censoring_a_matured_horizon_is_a_no_op(self) -> None:
        obs = HorizonObservation(horizon_ns=100, due_recv_ns=1_000)
        obs.record(read_recv_ns=1_000, values={"price_response": 5.0})
        obs.censor(status=CENSORED_BOUNDARY, recv_ns=1_500)
        self.assertEqual(obs.status, MATURED)


class ResponseTableCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=("price_response",)
        )

    def test_invalid_construction_is_refused(self) -> None:
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(horizons_ns=(), horizon_version="v", value_names=("x",))
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(horizons_ns=(100, 100), horizon_version="v", value_names=("x",))
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(horizons_ns=(0,), horizon_version="v", value_names=("x",))
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(horizons_ns=(100,), horizon_version="v", value_names=())

    def test_nothing_matures_before_its_horizon(self) -> None:
        self.calc.open_track(**track_kwargs())
        self.assertEqual(self.calc.advance(10_050, values_for=values_for), [])

    def test_horizons_mature_in_order_as_stream_time_advances(self) -> None:
        self.calc.open_track(**track_kwargs())
        first = self.calc.advance(10_100, values_for=values_for)
        self.assertEqual([r["horizon_ns"] for r in first], [100])
        second = self.calc.advance(11_000, values_for=values_for)
        self.assertEqual([r["horizon_ns"] for r in second], [1_000])

    def test_observation_time_is_the_due_time_not_the_advance_time(self) -> None:
        """A late advance must not postdate the causal cutoff."""
        self.calc.open_track(**track_kwargs())
        rows = self.calc.advance(999_999, values_for=values_for)
        self.assertEqual(rows[0]["observation"]["observed_recv_ns"], 10_100)

    def test_a_second_advance_does_not_rewrite_a_matured_horizon(self) -> None:
        self.calc.open_track(**track_kwargs())
        self.calc.advance(10_100, values_for=values_for)
        again = self.calc.advance(10_200, values_for=lambda t, h: {"price_response": 999.0})
        self.assertEqual(again, [])
        measure = self.calc.response[(100, "price_response")]
        self.assertEqual(measure.rows()[0]["value"]["maximum"], 100.0)

    def test_each_horizon_has_its_own_at_risk_denominator(self) -> None:
        """A structure censored early was at risk at H+100 and not at H+1000."""
        self.calc.open_track(**track_kwargs(structure_id="a"))
        self.calc.open_track(**track_kwargs(structure_id="b"))
        self.calc.advance(10_100, values_for=values_for)
        self.calc.close_continuity_segment(segment=0, recv_ns=10_500)
        table = {row["horizon_ns"]: row for row in self.calc.at_risk_table()}
        self.assertEqual(table[100]["observed"], 2)
        self.assertEqual(table[100]["censored_before_horizon"], 0)
        self.assertEqual(table[1_000]["observed"], 0)
        self.assertEqual(table[1_000]["censored_before_horizon"], 2)
        self.assertTrue(table[100]["denominator_is_horizon_specific"])

    def test_horizons_are_separate_strata(self) -> None:
        self.calc.open_track(**track_kwargs())
        self.calc.advance(11_000, values_for=values_for)
        subfamilies = set()
        for horizon in HORIZONS:
            subfamilies |= {
                r["stratum"]["subfamily_id"]
                for r in self.calc.response[(horizon, "price_response")].rows()
            }
        self.assertEqual(len(subfamilies), 2)
        self.assertTrue(all("horizon_version=hv1" in s for s in subfamilies))

    def test_boundary_censoring_stops_the_track(self) -> None:
        self.calc.open_track(**track_kwargs())
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=10_050)
        self.assertTrue(rows[0]["closed"])
        statuses = {h["status"] for h in rows[0]["horizons"]}
        self.assertEqual(statuses, {CENSORED_BOUNDARY})
        self.assertEqual(self.calc.summary()["tracks_open"], 0)

    def test_segment_close_only_touches_its_own_segment(self) -> None:
        self.calc.open_track(**track_kwargs(structure_id="a", continuity_segment=0))
        self.calc.open_track(**track_kwargs(structure_id="b", continuity_segment=1))
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=10_050)
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.calc.summary()["tracks_open"], 1)

    def test_stream_end_censors_the_remainder(self) -> None:
        self.calc.open_track(**track_kwargs())
        rows = self.calc.finalize(recv_ns=10_050)
        self.assertEqual({h["status"] for h in rows[0]["horizons"]}, {CENSORED_STREAM_END})

    def test_partially_matured_tracks_keep_their_matured_horizons(self) -> None:
        self.calc.open_track(**track_kwargs())
        self.calc.advance(10_100, values_for=values_for)
        rows = self.calc.finalize(recv_ns=10_500)
        statuses = {h["horizon_ns"]: h["status"] for h in rows[0]["horizons"]}
        self.assertEqual(statuses[100], MATURED)
        self.assertEqual(statuses[1_000], CENSORED_STREAM_END)

    def test_change_points_are_kept_beside_the_fixed_horizons(self) -> None:
        track = self.calc.open_track(**track_kwargs())
        track.add_change_point(recv_ns=10_020, values={"price_response": 2.0})
        rows = self.calc.finalize(recv_ns=10_050)
        self.assertEqual(rows[0]["change_point_count"], 1)

    def test_a_change_point_before_first_lawful_availability_is_refused(self) -> None:
        track = self.calc.open_track(**track_kwargs())
        with self.assertRaises(ResponseError):
            track.add_change_point(recv_ns=9_999, values={"price_response": 1.0})

    def test_a_missing_value_is_excluded_and_counted(self) -> None:
        self.calc.open_track(**track_kwargs())
        self.calc.advance(10_100, values_for=lambda t, h: {})
        row = self.calc.response[(100, "price_response")].rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_duplicate_track_is_refused(self) -> None:
        self.calc.open_track(**track_kwargs())
        with self.assertRaises(ResponseError):
            self.calc.open_track(**track_kwargs())

    def test_days_and_regimes_do_not_pool(self) -> None:
        self.calc.open_track(**track_kwargs(structure_id="a", source_day="20211004"))
        self.calc.open_track(**track_kwargs(structure_id="b", source_day="20211005"))
        self.calc.open_track(**track_kwargs(structure_id="c", starting_liquidity_regime="DEEP"))
        self.calc.advance(11_000, values_for=values_for)
        self.assertEqual(self.calc.response[(100, "price_response")].stratum_count, 3)

    def test_summary_declares_both_rules(self) -> None:
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.16")
        self.assertEqual(summary["emission"], "DEFERRED_UNTIL_HORIZON_ELAPSED_IN_STREAM_TIME")
        self.assertIn("may not substitute", summary["earliest_observation_rule"])
        self.assertIn("own at-risk denominator", summary["denominator_rule"])


def two_channel_calc(**overrides):
    kwargs = dict(
        horizons_ns=HORIZONS,
        horizon_version="hv1",
        value_names=(PRICE_RESPONSE, FLOW_RESPONSE),
    )
    kwargs.update(overrides)
    return ResponseTableCalculator(**kwargs)


def both_channels(_track, horizon):
    return {PRICE_RESPONSE: float(horizon), FLOW_RESPONSE: float(-horizon)}


class ResponseChannelVocabularyTest(unittest.TestCase):
    """D-10: one of seven channels, and an absent channel looked like a measured null."""

    def test_the_contract_names_seven_channels_and_all_seven_are_declared(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_response import (
            FEEDABLE_CHANNELS,
            REFUSED_CHANNELS,
        )

        self.assertEqual(len(CONTRACT_CHANNELS), 7)
        self.assertEqual(
            set(CONTRACT_CHANNELS), set(FEEDABLE_CHANNELS) | set(REFUSED_CHANNELS)
        )
        self.assertEqual(set(FEEDABLE_CHANNELS) & set(REFUSED_CHANNELS), set())

    def test_a_channel_we_cannot_feed_is_refused_by_name_with_its_reason(self) -> None:
        """Never emitted as an absent or zero-valued channel - refused at construction."""
        for name in (SURVIVAL_RESPONSE, TRANSITION_RESPONSE, COMPLETION_RESPONSE):
            with self.assertRaises(ResponseError) as caught:
                ResponseTableCalculator(
                    horizons_ns=HORIZONS, horizon_version="hv1", value_names=(name,)
                )
            self.assertIn("REFUSED_", str(caught.exception))

    def test_a_name_outside_the_contract_vocabulary_is_refused(self) -> None:
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(
                horizons_ns=HORIZONS, horizon_version="hv1", value_names=("made_up",)
            )

    def test_a_repeated_channel_is_refused(self) -> None:
        with self.assertRaises(ResponseError):
            ResponseTableCalculator(
                horizons_ns=HORIZONS,
                horizon_version="hv1",
                value_names=(PRICE_RESPONSE, PRICE_RESPONSE),
            )

    def test_the_flow_and_queue_channels_are_constructible(self) -> None:
        calc = ResponseTableCalculator(
            horizons_ns=HORIZONS,
            horizon_version="hv1",
            value_names=(PRICE_RESPONSE, FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE),
        )
        self.assertEqual(len(calc.response), len(HORIZONS) * 4)
        self.assertEqual(calc.summary()["channels"]["omitted_feedable"], [])

    def test_a_declared_channel_the_feed_omits_is_refused_on_the_first_maturation(self) -> None:
        """An omission means NOT WIRED, and it used to accumulate silently as exclusions."""
        calc = two_channel_calc()
        calc.open_track(**track_kwargs())
        with self.assertRaises(ResponseError) as caught:
            calc.advance(10_100, values_for=values_for)
        self.assertIn(FLOW_RESPONSE, str(caught.exception))

    def test_a_channel_the_table_was_not_told_to_emit_is_refused(self) -> None:
        """D60: a value that reaches the calculator is emitted or refused, never dropped."""
        calc = ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=(PRICE_RESPONSE,)
        )
        calc.open_track(**track_kwargs())
        with self.assertRaises(ResponseError) as caught:
            calc.advance(10_100, values_for=both_channels)
        self.assertIn(FLOW_RESPONSE, str(caught.exception))

    def test_an_unmeasurable_channel_is_declared_none_excluded_and_counted(self) -> None:
        """None is an absence; 0.0 would be a measurement that the structure moved nothing."""
        calc = two_channel_calc()
        calc.open_track(**track_kwargs())
        rows = calc.advance(10_100, values_for=lambda t, h: {
            PRICE_RESPONSE: 5.0, FLOW_RESPONSE: None
        })
        self.assertEqual(rows[0]["observation"]["absent_channels"], [FLOW_RESPONSE])
        flow_rows = calc.response[(100, FLOW_RESPONSE)].rows()
        self.assertEqual(flow_rows[0]["value"]["n"], 0)
        self.assertEqual(flow_rows[0]["excluded_missing_members"], 1)
        self.assertEqual(calc.response[(100, PRICE_RESPONSE)].rows()[0]["value"]["n"], 1)
        report = calc.summary()["channels"]
        self.assertEqual(report["declared_absences_per_channel"][FLOW_RESPONSE], 1)
        self.assertEqual(report["channels_never_fed"], [FLOW_RESPONSE])

    def test_censoring_excludes_every_channel_not_only_the_first(self) -> None:
        """Two channels of one horizon must agree about how many structures were at risk."""
        calc = two_channel_calc()
        calc.open_track(**track_kwargs())
        calc.finalize(recv_ns=10_050)
        for name in (PRICE_RESPONSE, FLOW_RESPONSE):
            rows = calc.response[(100, name)].rows()
            self.assertEqual(len(rows), 1, f"{name} has no stratum row for the censoring")
            self.assertEqual(rows[0]["excluded_missing_members"], 1)

    def test_the_summary_names_what_was_refused_and_what_was_merely_omitted(self) -> None:
        report = ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=(PRICE_RESPONSE,)
        ).summary()["channels"]
        self.assertEqual(report["emitted"], [PRICE_RESPONSE])
        self.assertEqual(
            sorted(report["omitted_feedable"]),
            sorted([FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE]),
        )
        self.assertEqual(
            sorted(report["refused"]),
            sorted([SURVIVAL_RESPONSE, TRANSITION_RESPONSE, COMPLETION_RESPONSE]),
        )


class ChannelValuesTest(unittest.TestCase):
    """The channel arithmetic lives beside the channel declarations, not in the traversal."""

    def baseline(self, **overrides) -> ChannelReading:
        kwargs = dict(
            price_raw=100,
            signed_flow_lots=5,
            resting_depth_total=40,
            same_side_touch_depth=12,
            depth_scope=DEPTH_SCOPE_FULL_BOOK,
        )
        kwargs.update(overrides)
        return ChannelReading(**kwargs)

    def test_every_requested_channel_is_differenced_from_the_baseline(self) -> None:
        values = channel_values(
            self.baseline(),
            self.baseline(
                price_raw=103, signed_flow_lots=-2, resting_depth_total=31,
                same_side_touch_depth=12,
            ),
            channels=(PRICE_RESPONSE, FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE),
        )
        self.assertEqual(values[PRICE_RESPONSE], 3.0)
        self.assertEqual(values[FLOW_RESPONSE], -7.0)
        self.assertEqual(values[FULL_BOOK_RESPONSE], -9.0)
        self.assertEqual(values[QUEUE_RESPONSE], 0.0)

    def test_an_absent_input_becomes_none_and_never_zero(self) -> None:
        values = channel_values(
            self.baseline(),
            self.baseline(signed_flow_lots=None),
            channels=(PRICE_RESPONSE, FLOW_RESPONSE),
        )
        self.assertIn(FLOW_RESPONSE, values)
        self.assertIsNone(values[FLOW_RESPONSE])

    def test_a_depth_channel_off_the_ten_level_projection_is_refused(self) -> None:
        """D-5 again: a truncated book presented as the book reads as present and in range."""
        with self.assertRaises(ResponseError) as caught:
            channel_values(
                self.baseline(depth_scope="TOP_TEN_PROJECTION"),
                self.baseline(depth_scope="TOP_TEN_PROJECTION"),
                channels=(FULL_BOOK_RESPONSE,),
            )
        self.assertIn("TOP_TEN_PROJECTION", str(caught.exception))

    def test_a_price_channel_survives_a_projection_scope(self) -> None:
        """Only the depth-derived channels need the full book; price does not."""
        values = channel_values(
            self.baseline(depth_scope="TOP_TEN_PROJECTION"),
            self.baseline(price_raw=101, depth_scope="TOP_TEN_PROJECTION"),
            channels=(PRICE_RESPONSE,),
        )
        self.assertEqual(values[PRICE_RESPONSE], 1.0)

    def test_differencing_two_different_scopes_is_refused(self) -> None:
        with self.assertRaises(ResponseError):
            channel_values(
                self.baseline(),
                self.baseline(depth_scope="TOP_TEN_PROJECTION"),
                channels=(PRICE_RESPONSE,),
            )


class HorizonVersioningTest(unittest.TestCase):
    """The horizon set is versioned; a version whose contents move identifies nothing."""

    def test_the_run_33605852433_horizon_set_is_frozen(self) -> None:
        self.assertEqual(
            HORIZON_SETS["a-arm-h1"], (1 * NS_PER_S, 10 * NS_PER_S, 60 * NS_PER_S)
        )

    def test_the_sub_second_ladder_is_a_new_version_that_keeps_the_old_horizons(self) -> None:
        h1, h2 = HORIZON_SETS["a-arm-h1"], HORIZON_SETS["a-arm-h2"]
        self.assertTrue(set(h1) < set(h2))
        below_one_second = [h for h in h2 if h < NS_PER_S]
        self.assertTrue(below_one_second)
        self.assertEqual(min(below_one_second), 1 * NS_PER_MS)

    def test_a_registered_version_may_not_be_handed_other_horizons(self) -> None:
        with self.assertRaises(ResponseError) as caught:
            ResponseTableCalculator(
                horizons_ns=(1 * NS_PER_S,),
                horizon_version="a-arm-h1",
                value_names=(PRICE_RESPONSE,),
            )
        self.assertIn("a-arm-h1", str(caught.exception))

    def test_a_registered_version_constructs_from_its_own_horizons(self) -> None:
        calc = ResponseTableCalculator(
            horizons_ns=horizons_for_version("a-arm-h2"),
            horizon_version="a-arm-h2",
            value_names=(PRICE_RESPONSE,),
        )
        self.assertTrue(calc.summary()["horizon_version_registered"])

    def test_an_unregistered_version_is_allowed_and_says_so(self) -> None:
        calc = ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=(PRICE_RESPONSE,)
        )
        self.assertFalse(calc.summary()["horizon_version_registered"])
        with self.assertRaises(ResponseError):
            horizons_for_version("hv1")


class ReadingLatenessTest(unittest.TestCase):
    """A sub-second horizon read on a whole-second advance is not a sub-second reading."""

    def setUp(self) -> None:
        self.calc = ResponseTableCalculator(
            horizons_ns=(1 * NS_PER_MS, 1 * NS_PER_S),
            horizon_version="hv-sub",
            value_names=(PRICE_RESPONSE,),
        )

    def test_the_read_instant_is_carried_beside_the_unmoved_causal_cutoff(self) -> None:
        self.calc.open_track(**track_kwargs(first_lawful_recv_ns=0))
        rows = self.calc.advance(1 * NS_PER_S, values_for=values_for)
        observation = rows[0]["observation"]
        self.assertEqual(observation["due_recv_ns"], 1 * NS_PER_MS)
        self.assertEqual(observation["observed_recv_ns"], 1 * NS_PER_MS)
        self.assertEqual(observation["read_recv_ns"], 1 * NS_PER_S)
        self.assertEqual(observation["read_lateness_ns"], 1 * NS_PER_S - 1 * NS_PER_MS)

    def test_a_reading_later_than_its_own_horizon_is_classed_and_counted(self) -> None:
        self.calc.open_track(**track_kwargs(first_lawful_recv_ns=0))
        rows = {r["horizon_ns"]: r["observation"] for r in
                self.calc.advance(1 * NS_PER_S, values_for=values_for)}
        self.assertEqual(rows[1 * NS_PER_MS]["reading_resolution"], LATE_BEYOND_HORIZON)
        self.assertEqual(rows[1 * NS_PER_S]["reading_resolution"], EXACT_AT_HORIZON)
        report = self.calc.summary()["horizon_resolution"]
        self.assertFalse(report[str(1 * NS_PER_MS)]["resolved_at_its_own_length"])
        self.assertEqual(report[str(1 * NS_PER_MS)][LATE_BEYOND_HORIZON], 1)
        self.assertTrue(report[str(1 * NS_PER_S)]["resolved_at_its_own_length"])

    def test_lateness_inside_the_horizon_is_not_called_beyond_it(self) -> None:
        self.calc.open_track(**track_kwargs(first_lawful_recv_ns=0))
        rows = {r["horizon_ns"]: r["observation"] for r in
                self.calc.advance(1_500_000, values_for=values_for)}
        self.assertEqual(rows[1 * NS_PER_MS]["reading_resolution"], LATE_WITHIN_HORIZON)

    def test_a_horizon_still_cannot_be_read_before_it_is_due(self) -> None:
        """Causal integrity is not weakened by carrying the read instant."""
        self.calc.open_track(**track_kwargs(first_lawful_recv_ns=0))
        self.assertEqual(self.calc.advance(999_999, values_for=values_for), [])
        observation = HorizonObservation(horizon_ns=1 * NS_PER_MS, due_recv_ns=1 * NS_PER_MS)
        with self.assertRaises(ResponseError):
            observation.record(read_recv_ns=999_999, values={PRICE_RESPONSE: 1.0})


class StartingLiquidityRegimeTest(unittest.TestCase):
    """D-10: DEPTH_SKEW_BID on all 84 at-risk rows, and nothing counted the distinct values."""

    def calc(self):
        return ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=(PRICE_RESPONSE,)
        )

    def test_a_single_valued_regime_is_reported_as_conditioning_on_a_constant(self) -> None:
        calc = self.calc()
        for i in range(3):
            calc.open_track(
                **track_kwargs(structure_id=f"s{i}", starting_liquidity_regime="DEPTH_SKEW_BID")
            )
        conditioning = calc.summary()["starting_liquidity_regime_conditioning"]
        self.assertEqual(conditioning["status"], REGIME_CONSTANT)
        self.assertEqual(conditioning["distinct_values"], 1)
        self.assertEqual(conditioning["counts"], {"DEPTH_SKEW_BID": 3})

    def test_the_conditioning_verdict_travels_on_every_at_risk_row(self) -> None:
        """A caveat that lives only in prose expires; this one rides on the value."""
        calc = self.calc()
        calc.open_track(**track_kwargs(starting_liquidity_regime="DEPTH_SKEW_BID"))
        rows = calc.at_risk_table()
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["starting_liquidity_regime_conditioning"], REGIME_CONSTANT)
            self.assertEqual(row["starting_liquidity_regime_distinct_values"], 1)

    def test_more_than_one_regime_is_reported_as_conditioning(self) -> None:
        calc = self.calc()
        calc.open_track(**track_kwargs(structure_id="a", starting_liquidity_regime="DEPTH_SKEW_BID"))
        calc.open_track(**track_kwargs(structure_id="b", starting_liquidity_regime="DEPTH_SKEW_ASK"))
        rows = calc.at_risk_table()
        self.assertEqual(
            {r["starting_liquidity_regime_conditioning"] for r in rows}, {REGIME_CONDITIONS}
        )
        self.assertEqual(
            calc.summary()["starting_liquidity_regime_conditioning"]["distinct_values"], 2
        )

    def test_the_regime_basis_travels_with_the_regime(self) -> None:
        """The principal could not prove the derivation from the artifact. Now it is on it."""
        calc = self.calc()
        track = calc.open_track(
            **track_kwargs(starting_liquidity_regime_basis="FULL_BOOK_DEPTH_SIGN")
        )
        self.assertEqual(track.as_dict()["starting_liquidity_regime_basis"], "FULL_BOOK_DEPTH_SIGN")
        self.assertEqual(
            calc.summary()["starting_liquidity_regime_conditioning"]["basis_counts"],
            {"FULL_BOOK_DEPTH_SIGN": 1},
        )

    def test_an_undeclared_basis_declares_itself(self) -> None:
        calc = self.calc()
        track = calc.open_track(**track_kwargs())
        self.assertEqual(
            track.as_dict()["starting_liquidity_regime_basis"], REGIME_BASIS_UNDECLARED
        )

    def test_an_empty_regime_is_refused_rather_than_keyed_on(self) -> None:
        with self.assertRaises(ResponseError):
            self.calc().open_track(**track_kwargs(starting_liquidity_regime=""))


class EventDrivenChangePointTest(unittest.TestCase):
    """The contract requires change points AND fixed horizons; run 33605852433 had one half."""

    def setUp(self) -> None:
        self.calc = ResponseTableCalculator(
            horizons_ns=HORIZONS, horizon_version="hv1", value_names=(PRICE_RESPONSE,)
        )

    def test_an_unfed_change_point_channel_declares_itself(self) -> None:
        self.calc.open_track(**track_kwargs())
        block = self.calc.summary()["event_driven_change_points"]
        self.assertEqual(block["observed"], 0)
        self.assertEqual(block["status"], "NOT_FED_BY_THE_TRAVERSAL")

    def test_a_change_point_reaches_every_open_track_and_is_counted(self) -> None:
        self.calc.open_track(**track_kwargs(structure_id="a"))
        self.calc.open_track(**track_kwargs(structure_id="b"))
        written = self.calc.observe_change_point(
            10_020, values_for=lambda t: {PRICE_RESPONSE: 2.0}
        )
        self.assertEqual(written, 2)
        block = self.calc.summary()["event_driven_change_points"]
        self.assertEqual(block["observed"], 2)
        self.assertEqual(block["status"], "FED_BY_THE_TRAVERSAL")

    def test_a_change_point_obeys_the_same_channel_contract_as_a_horizon(self) -> None:
        calc = two_channel_calc()
        calc.open_track(**track_kwargs())
        with self.assertRaises(ResponseError):
            calc.observe_change_point(10_020, values_for=lambda t: {PRICE_RESPONSE: 1.0})

    def test_a_change_point_before_a_track_is_lawful_skips_that_track(self) -> None:
        self.calc.open_track(**track_kwargs(structure_id="early", first_lawful_recv_ns=10_000))
        self.calc.open_track(**track_kwargs(structure_id="late", first_lawful_recv_ns=90_000))
        written = self.calc.observe_change_point(
            20_000, values_for=lambda t: {PRICE_RESPONSE: 1.0}
        )
        self.assertEqual(written, 1)


if __name__ == "__main__":
    unittest.main()
