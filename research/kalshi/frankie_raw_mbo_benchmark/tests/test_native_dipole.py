"""Tests for section 4.12 dipole and opposing-pressure runway."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import (
    CANONICAL,
    LONG,
    MIRROR,
    NO_DIRECTION,
    SHORT,
    DipoleCalculator,
    DipoleError,
    DipolePath,
    DipoleStage,
)

CTX = dict(
    source_day="20211004",
    source_role="HELD_OUT_BLIND",
    continuity_segment=0,
    family_id="TFCN",
    session_phase="RTH",
    event_phase="BIRTH",
)


def stage(**overrides) -> DipoleStage:
    base = dict(
        runway_id="r1",
        stage_index=0,
        recv_ns=1_000,
        orientation=CANONICAL,
        signed_flow=10,
        bid_depth=100,
        ask_depth=50,
        bid_order_count=5,
        ask_order_count=3,
        bid_level_count=4,
        ask_level_count=2,
        price_raw=1000,
    )
    base.update(overrides)
    return DipoleStage(**base)


class DipoleStageTest(unittest.TestCase):
    def test_direction_comes_from_the_sign_of_flow(self) -> None:
        self.assertEqual(stage(signed_flow=10).direction, LONG)
        self.assertEqual(stage(signed_flow=-10).direction, SHORT)

    def test_zero_flow_reports_no_direction_rather_than_a_default(self) -> None:
        self.assertEqual(stage(signed_flow=0).direction, NO_DIRECTION)

    def test_magnitude_is_unsigned_and_cannot_distinguish_direction(self) -> None:
        """The reason section 4.12 forbids taking direction from magnitude."""
        up = stage(signed_flow=10)
        down = stage(signed_flow=-10)
        self.assertEqual(up.magnitude, down.magnitude)
        self.assertNotEqual(up.direction, down.direction)

    def test_normalized_imbalance(self) -> None:
        self.assertAlmostEqual(stage(bid_depth=75, ask_depth=25).normalized_imbalance, 0.5)

    def test_empty_book_imbalance_is_none_not_zero(self) -> None:
        self.assertIsNone(stage(bid_depth=0, ask_depth=0).normalized_imbalance)

    def test_invalid_orientation_or_negative_depth_is_refused(self) -> None:
        with self.assertRaises(DipoleError):
            stage(orientation="MAYBE")
        with self.assertRaises(DipoleError):
            stage(bid_depth=-1)
        with self.assertRaises(DipoleError):
            stage(stage_index=-1)


class DipolePathTest(unittest.TestCase):
    def path(self, flows, orientation=CANONICAL, prices=None):
        prices = prices or [1000] * len(flows)
        return DipolePath(
            runway_id="r1",
            stages=tuple(
                stage(stage_index=i, signed_flow=f, recv_ns=1_000 + i * 100, price_raw=p)
                for i, (f, p) in enumerate(zip(flows, prices))
            ),
        )

    def test_sign_reversals_are_exact_and_timed(self) -> None:
        reversals = self.path([5, 3, -2, -4, 6]).sign_reversals
        self.assertEqual(len(reversals), 2)
        self.assertEqual(reversals[0]["from_direction"], LONG)
        self.assertEqual(reversals[0]["to_direction"], SHORT)
        self.assertEqual(reversals[0]["stage_index"], 2)
        self.assertEqual(reversals[1]["to_direction"], LONG)

    def test_a_persisting_path_has_no_reversals(self) -> None:
        p = self.path([5, 3, 1])
        self.assertTrue(p.persisted)
        self.assertIsNone(p.inflection_recv_ns)

    def test_zero_flow_stages_do_not_create_a_reversal(self) -> None:
        """A gap in direction is not a change of direction."""
        p = self.path([5, 0, 3])
        self.assertEqual(p.sign_reversals, [])
        self.assertTrue(p.persisted)

    def test_inflection_is_the_first_reversal(self) -> None:
        p = self.path([5, -1, 4])
        self.assertEqual(p.inflection_recv_ns, 1_100)

    def test_price_coupling_spans_the_path(self) -> None:
        self.assertEqual(self.path([1, 1], prices=[1000, 1007]).price_coupling, 7)

    def test_a_path_cannot_mix_orientations(self) -> None:
        with self.assertRaises(DipoleError):
            DipolePath(
                runway_id="r1",
                stages=(stage(stage_index=0, orientation=CANONICAL), stage(stage_index=1, orientation=MIRROR)),
            )

    def test_stages_must_be_strictly_ordered(self) -> None:
        with self.assertRaises(DipoleError):
            DipolePath(runway_id="r1", stages=(stage(stage_index=1), stage(stage_index=0)))
        with self.assertRaises(DipoleError):
            DipolePath(runway_id="r1", stages=(stage(stage_index=0), stage(stage_index=0)))

    def test_an_empty_path_is_refused(self) -> None:
        with self.assertRaises(DipoleError):
            DipolePath(runway_id="r1", stages=())


class DipoleCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DipoleCalculator()

    def test_canonical_and_mirror_never_pool(self) -> None:
        self.calc.observe_stage(stage(orientation=CANONICAL), **CTX)
        self.calc.observe_stage(stage(orientation=MIRROR), **CTX)
        orientations = {r["stratum"]["side_orientation"] for r in self.calc.signed_flow.rows()}
        self.assertEqual(orientations, {CANONICAL, MIRROR})

    def test_stage_index_separates_strata_so_paths_are_stage_relative(self) -> None:
        self.calc.observe_stage(stage(stage_index=0), **CTX)
        self.calc.observe_stage(stage(stage_index=1), **CTX)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.signed_flow.rows()}
        self.assertEqual(subfamilies, {"event_phase=BIRTH|stage=0", "event_phase=BIRTH|stage=1"})

    def test_event_phase_separates_strata(self) -> None:
        self.calc.observe_stage(stage(), **{**CTX, "event_phase": "BIRTH"})
        self.calc.observe_stage(stage(), **{**CTX, "event_phase": "PERSISTENCE"})
        self.assertEqual(self.calc.signed_flow.stratum_count, 2)

    def test_signed_flow_and_magnitude_are_both_retained(self) -> None:
        self.calc.observe_stage(stage(signed_flow=-40), **CTX)
        self.assertEqual(self.calc.signed_flow.rows()[0]["value"]["minimum"], -40.0)
        self.assertEqual(self.calc.magnitude.rows()[0]["value"]["maximum"], 40.0)

    def test_opposite_signed_flows_do_not_cancel_in_the_magnitude_view(self) -> None:
        self.calc.observe_stage(stage(signed_flow=10), **CTX)
        self.calc.observe_stage(stage(signed_flow=-10), **CTX)
        self.assertEqual(self.calc.signed_flow.rows()[0]["value"]["sum"], 0.0)
        self.assertEqual(self.calc.magnitude.rows()[0]["value"]["sum"], 20.0)

    def test_empty_book_stage_is_excluded_from_imbalance_and_counted(self) -> None:
        self.calc.observe_stage(stage(bid_depth=0, ask_depth=0), **CTX)
        row = self.calc.normalized_imbalance.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_mirror_difference_is_recorded_when_a_pair_exists(self) -> None:
        self.calc.observe_stage(stage(signed_flow=10), mirror_signed_flow=4, **CTX)
        self.assertEqual(self.calc.mirror_difference.rows()[0]["value"]["maximum"], 6.0)

    def test_unpaired_stages_are_excluded_and_counted(self) -> None:
        self.calc.observe_stage(stage(), **CTX)
        row = self.calc.mirror_difference.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_days_do_not_pool(self) -> None:
        self.calc.observe_stage(stage(), **{**CTX, "source_day": "20211004"})
        self.calc.observe_stage(stage(), **{**CTX, "source_day": "20211005"})
        self.assertEqual(self.calc.signed_flow.stratum_count, 2)

    def test_summary_records_the_direction_source(self) -> None:
        self.calc.observe_stage(stage(signed_flow=0), **CTX)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.12")
        self.assertEqual(summary["direction_source"], "SIGNED_FLOW_AND_CAUSAL_MECHANICS")
        self.assertEqual(summary["direction_counts"][NO_DIRECTION], 1)

    def test_paths_contribute_their_reversals_to_the_summary(self) -> None:
        path = DipolePath(
            runway_id="r1",
            stages=tuple(
                stage(stage_index=i, signed_flow=f) for i, f in enumerate([5, -3, 2])
            ),
        )
        self.calc.observe_path(path)
        self.assertEqual(self.calc.summary()["sign_reversals"], 2)
        self.assertEqual(self.calc.summary()["paths_seen"], 1)


if __name__ == "__main__":
    unittest.main()
