"""Tests for section 4.12 dipole and opposing-pressure runway."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import (
    FLIP,
    LONG,
    NO_DIRECTION,
    SAME,
    SHORT,
    STAGE_BIN_RULE,
    DipoleCalculator,
    DipoleError,
    DipolePath,
    DipoleStage,
    stage_bin,
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
        orientation=SAME,
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
    def path(self, flows, orientation=SAME, prices=None):
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
                stages=(stage(stage_index=0, orientation=SAME), stage(stage_index=1, orientation=FLIP)),
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

    def test_same_and_flip_never_pool(self) -> None:
        self.calc.observe_stage(stage(orientation=SAME), **CTX)
        self.calc.observe_stage(stage(orientation=FLIP), **CTX)
        orientations = {r["stratum"]["side_orientation"] for r in self.calc.signed_flow.rows()}
        self.assertEqual(orientations, {SAME, FLIP})

    def test_the_stratum_key_declares_the_stage_indices_the_row_covers(self) -> None:
        """A reader of ONE averaged row must be able to say which stages fed it.

        `stage_bin=STAGE_4_7` is stages four through seven and says so on the value. A bin
        ordinal would have needed this module open beside the row to interpret, which is the
        prose-caveat failure this contract keeps refusing.
        """
        for index in (0, 1, 5, 40):
            self.calc.observe_stage(stage(stage_index=index), **CTX)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.signed_flow.rows()}
        self.assertEqual(
            subfamilies,
            {
                "event_phase=BIRTH|stage_bin=STAGE_0_0",
                "event_phase=BIRTH|stage_bin=STAGE_1_1",
                "event_phase=BIRTH|stage_bin=STAGE_4_7",
                "event_phase=BIRTH|stage_bin=STAGE_32_63",
            },
        )

    def test_a_long_path_no_longer_makes_one_stratum_per_stage(self) -> None:
        """D-12, at the smallest size where raw and binned stratification disagree loudly.

        Sixty-four consecutive stages of one path produced sixty-four strata of n=1 under the
        raw `stage=k` key. The octaves 0 | 1 | 2-3 | 4-7 | 8-15 | 16-31 | 32-63 are seven.
        """
        for index in range(64):
            self.calc.observe_stage(stage(stage_index=index), **CTX)
        self.assertEqual(self.calc.signed_flow.stratum_count, 7)
        counts = sorted(r["value"]["n"] for r in self.calc.signed_flow.rows())
        self.assertEqual(counts, [1, 1, 2, 4, 8, 16, 32])
        self.assertEqual(sum(counts), 64)

    def test_stages_in_the_same_octave_share_a_stratum(self) -> None:
        """Under the raw key these were two strata of n=1; they are one stratum of n=2."""
        self.calc.observe_stage(stage(stage_index=4, signed_flow=10), **CTX)
        self.calc.observe_stage(stage(stage_index=7, signed_flow=-4), **CTX)
        rows = self.calc.signed_flow.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"]["n"], 2)
        self.assertEqual(rows[0]["stratum"]["subfamily_id"], "event_phase=BIRTH|stage_bin=STAGE_4_7")

    def test_binning_the_index_does_not_pool_across_event_phase(self) -> None:
        """The load-bearing half of the rule, pinned so the fix cannot quietly take it out.

        Stage 4 and stage 5 share the octave STAGE_4_7. If they were in different phases of
        the runway they are still two strata: "never average across event phase" is about
        BIRTH / PERSISTENCE / REVERSAL and was never about the ordinal position inside one.
        """
        self.calc.observe_stage(stage(stage_index=4), **{**CTX, "event_phase": "BIRTH"})
        self.calc.observe_stage(stage(stage_index=5), **{**CTX, "event_phase": "PERSISTENCE"})
        self.assertEqual(self.calc.signed_flow.stratum_count, 2)
        self.assertEqual(
            {r["stratum"]["subfamily_id"] for r in self.calc.signed_flow.rows()},
            {
                "event_phase=BIRTH|stage_bin=STAGE_4_7",
                "event_phase=PERSISTENCE|stage_bin=STAGE_4_7",
            },
        )

    def test_the_exact_stage_index_survives_on_the_member_row(self) -> None:
        """D60: binning is not dropping. The averaged key coarsens; the member row does not."""
        row = self.calc.observe_stage(stage(stage_index=37), **CTX)
        self.assertEqual(row["stage_index"], 37)
        self.assertEqual(row["stage_bin"], "STAGE_32_63")
        self.assertEqual(row["stage_bin_first_index"], 32)
        self.assertEqual(row["stage_bin_last_index"], 63)
        self.assertEqual(row["stage_bin_rule"], STAGE_BIN_RULE)

    def test_the_binning_rule_and_what_each_bin_actually_held_are_reported(self) -> None:
        for index in (0, 8, 9, 15):
            self.calc.observe_stage(stage(stage_index=index), **CTX)
        binning = self.calc.summary()["stage_binning"]
        self.assertEqual(binning["rule"], STAGE_BIN_RULE)
        self.assertTrue(binning["phase_still_raw"])
        self.assertEqual(
            binning["bins"]["STAGE_8_15"],
            {
                "covers_first_index": 8,
                "covers_last_index": 15,
                "stages_seen": 3,
                "min_stage_index_seen": 8,
                "max_stage_index_seen": 15,
            },
        )

    def test_a_stratum_filled_by_one_runway_is_counted_as_one_runway(self) -> None:
        """The failure mode binning introduces, made visible instead of assumed away.

        Two runways contribute to the STAGE_4_7 stratum; one contributes the whole of
        STAGE_8_15. An n of 4 from a single path is four consecutive seconds of one episode,
        which is not what an n of 4 usually means.
        """
        for index in (4, 5, 8, 9, 10, 11):
            self.calc.observe_stage(stage(runway_id="r1", stage_index=index), **CTX)
        for index in (4, 5):
            self.calc.observe_stage(stage(runway_id="r2", stage_index=index), **CTX)
        binning = self.calc.summary()["stage_binning"]
        self.assertEqual(binning["distinct_runways_per_stratum"], {1: 1, 2: 1})
        self.assertEqual(binning["single_runway_strata"], 1)

    def test_an_unobserved_event_phase_is_absent_from_the_counts_never_zero(self) -> None:
        """An absence is excluded and counted, never reported as a measured zero.

        Run 33605852433 emitted BIRTH 220 and PERSISTENCE 3,234 stages and no REVERSAL stage
        at all while 4.10 recorded 90 reversed runways, and 4.12's own output said nothing
        about it. It now reports the phases it saw, so the gap is readable from this section.
        """
        self.calc.observe_stage(stage(), **{**CTX, "event_phase": "BIRTH"})
        self.calc.observe_stage(stage(stage_index=1), **{**CTX, "event_phase": "PERSISTENCE"})
        counts = self.calc.summary()["event_phase_counts"]
        self.assertEqual(counts, {"BIRTH": 1, "PERSISTENCE": 1})
        self.assertNotIn("REVERSAL", counts)

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


class StageBinTest(unittest.TestCase):
    """The binning rule itself, constrained as a partition rather than described."""

    def test_bins_tile_every_index_exactly_once_and_stay_closed(self) -> None:
        """No index falls between two bins, no index falls in two, no bin is open-ended.

        An open-ended final bin would pool an unbounded stretch of one path, which is the
        averaging this measure exists to refuse; a gap would silently drop a stage.
        """
        owner: dict[int, str] = {}
        bounds: dict[str, tuple[int, int]] = {}
        for index in range(4096):
            label, first, last = stage_bin(index)
            self.assertLessEqual(first, index)
            self.assertLessEqual(index, last)
            self.assertNotIn(index, owner)
            owner[index] = label
            if label in bounds:
                self.assertEqual(bounds[label], (first, last))
            else:
                bounds[label] = (first, last)
        ordered = sorted(bounds.values())
        self.assertEqual(ordered[0], (0, 0))
        for (_, previous_last), (next_first, _) in zip(ordered, ordered[1:]):
            self.assertEqual(next_first, previous_last + 1)

    def test_the_label_carries_both_bounds(self) -> None:
        self.assertEqual(stage_bin(0)[0], "STAGE_0_0")
        self.assertEqual(stage_bin(1)[0], "STAGE_1_1")
        self.assertEqual(stage_bin(3), ("STAGE_2_3", 2, 3))
        self.assertEqual(stage_bin(190), ("STAGE_128_255", 128, 255))

    def test_the_width_doubles_rather_than_being_fixed(self) -> None:
        """A fixed width leaves the tail exactly where it was; doubling is the whole fix.

        The stratum's population at index k is the count of paths still running at k, a
        survival curve. Widths that double as survivors roughly halve keep successive bins
        within about one halving of each other instead of leaving the longest path alone in
        the last bin.
        """
        widths = []
        for index in (1, 2, 4, 8, 16, 32, 64):
            _, first, last = stage_bin(index)
            widths.append(last - first + 1)
        self.assertEqual(widths, [1, 2, 4, 8, 16, 32, 64])

    def test_a_negative_or_non_integer_index_is_refused_not_bucketed(self) -> None:
        with self.assertRaises(DipoleError):
            stage_bin(-1)
        with self.assertRaises(DipoleError):
            stage_bin(2.0)
        with self.assertRaises(DipoleError):
            stage_bin(True)


class ShatteringTest(unittest.TestCase):
    """D-12 at the size it was measured at, on a synthetic population of the same shape.

    Run 33605852433 produced 3,454 stages over 90 paths, 1,692 strata, 848 (50.1%) at n=1,
    1,307 (77.2%) at n<=2 and none at n>=30 - 6,768 averaged rows across the four measures.
    The population below is synthetic and is labelled so: 90 paths over 34 (family,
    orientation) contexts, lengths falling as a power law to a longest path of 145 stages,
    3,445 stages in total, which reproduces 1,859 raw strata with 829 at n=1 and 1,303 at
    n<=2. It is a shape match, not the tape, and it exists to size the fix.
    """

    LONGEST = 145
    PATHS = 90
    CONTEXTS = 34

    def _lengths(self) -> list[int]:
        return [
            max(1, min(self.LONGEST, int(round(self.LONGEST * ((i + 1) ** -0.4)))))
            for i in range(self.PATHS)
        ]

    def _populate(self, calc: DipoleCalculator) -> int:
        stages = 0
        for path_index, length in enumerate(self._lengths()):
            family = f"ow-{path_index % self.CONTEXTS:02d}"
            for index in range(length):
                calc.observe_stage(
                    stage(runway_id=f"p{path_index}", stage_index=index, signed_flow=1),
                    source_day="20211003",
                    source_role="HELD_OUT_BLIND",
                    continuity_segment=18904,
                    family_id=family,
                    session_phase="PRE_SETTLEMENT",
                    event_phase="BIRTH" if index < 2 else "PERSISTENCE",
                )
                stages += 1
        return stages

    def _raw_index_strata(self) -> dict[tuple, int]:
        """What the raw `stage=k` key produced, computed independently of the module."""
        counts: dict[tuple, int] = {}
        for path_index, length in enumerate(self._lengths()):
            family = f"ow-{path_index % self.CONTEXTS:02d}"
            for index in range(length):
                key = (family, "BIRTH" if index < 2 else "PERSISTENCE", index)
                counts[key] = counts.get(key, 0) + 1
        return counts

    def test_the_raw_index_key_shatters_this_population(self) -> None:
        """The baseline, so the comparison below is against a measured number not a memory."""
        counts = self._raw_index_strata()
        sizes = list(counts.values())
        self.assertEqual(sum(sizes), 3_445)
        self.assertEqual(len(sizes), 1_859)
        self.assertEqual(sum(1 for n in sizes if n == 1), 829)
        self.assertEqual(sum(1 for n in sizes if n <= 2), 1_303)
        self.assertEqual(max(sizes), 3)

    def test_binning_the_index_gives_the_same_population_a_place_to_average(self) -> None:
        calc = DipoleCalculator()
        observed = self._populate(calc)
        self.assertEqual(observed, 3_445)
        sizes = [row["value"]["n"] for row in calc.signed_flow.rows()]
        self.assertEqual(sum(sizes), 3_445)
        # Every stage is still there; 1,859 strata became 246, so the four measures emit 984
        # averaged rows where the raw key emitted 7,436 - the same shape as the run's 6,768.
        self.assertEqual(calc.signed_flow.stratum_count, 246)
        self.assertEqual(sum(m.stratum_count for m in calc.measures), 984)
        self.assertEqual(sum(1 for n in sizes if n == 1), 0)
        self.assertEqual(max(sizes), 64)
        self.assertEqual(sum(1 for n in sizes if n >= 30), 32)

    def test_the_shattering_fix_does_not_hide_single_runway_strata(self) -> None:
        """Bigger n is only progress if it came from more episodes. This says how many did."""
        calc = DipoleCalculator()
        self._populate(calc)
        histogram = calc.summary()["stage_binning"]["distinct_runways_per_stratum"]
        self.assertEqual(sum(histogram.values()), calc.signed_flow.stratum_count)
        self.assertEqual(min(histogram), 1)
        self.assertGreater(max(histogram), 1)


if __name__ == "__main__":
    unittest.main()
