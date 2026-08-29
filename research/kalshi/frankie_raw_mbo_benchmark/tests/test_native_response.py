"""Tests for section 4.16 fixed causal future-response table."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_response import (
    CENSORED_BOUNDARY,
    CENSORED_STREAM_END,
    MATURED,
    PENDING,
    HorizonObservation,
    ResponseError,
    ResponseTableCalculator,
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
        obs.record(recv_ns=1_000, values={"price_response": 5.0})
        with self.assertRaises(ResponseError):
            obs.record(recv_ns=1_200, values={"price_response": 99.0})
        self.assertEqual(obs.values["price_response"], 5.0)

    def test_recording_before_the_horizon_is_due_is_refused(self) -> None:
        obs = HorizonObservation(horizon_ns=100, due_recv_ns=1_000)
        with self.assertRaises(ResponseError):
            obs.record(recv_ns=999, values={"price_response": 1.0})

    def test_censoring_a_matured_horizon_is_a_no_op(self) -> None:
        obs = HorizonObservation(horizon_ns=100, due_recv_ns=1_000)
        obs.record(recv_ns=1_000, values={"price_response": 5.0})
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


if __name__ == "__main__":
    unittest.main()
