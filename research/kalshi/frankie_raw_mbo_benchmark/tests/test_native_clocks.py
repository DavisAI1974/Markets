"""Tests for section 4.5 formation, serialization, and observation clocks."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (
    CAUSAL_CLOCK,
    HORIZON,
    INTERPRETATION_DOMAIN,
    PRIOR,
    T0,
    ClockCalculator,
    ClockError,
    RecognitionLabel,
    clock_subfamily,
    member_clock_row,
)


def component(
    *,
    ts_event_ns: int,
    ts_recv_ns: int,
    sequence: int,
    channel_id: int = 1,
    is_last: bool = False,
    action: str = "A",
    side: str = "B",
) -> dict:
    return {
        "instrument_id": 42,
        "publisher_id": 1,
        "channel_id": channel_id,
        "order_id": 900,
        "action": action,
        "side": side,
        "price_raw": 1000,
        "size": 1,
        "flags": 128 if is_last else 0,
        "sequence": sequence,
        "ts_event_ns": ts_event_ns,
        "ts_recv_ns": ts_recv_ns,
        "ts_in_delta_ns": 0,
        "is_last": is_last,
        "is_snapshot": False,
    }


def group(components) -> dict:
    return {"raw_actions": components, "causal_availability_clock": CAUSAL_CLOCK}


def three_component_group() -> dict:
    return group(
        [
            component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10),
            component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=11),
            component(ts_event_ns=2_000, ts_recv_ns=2_500, sequence=12, is_last=True),
        ]
    )


def row_for(g: dict, **overrides) -> dict:
    base = dict(
        group_index=0,
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="A_A_A",
        side_orientation="BID",
        session_phase="RTH",
    )
    base.update(overrides)
    return member_clock_row(g, **base)


class MemberClockRowTest(unittest.TestCase):
    def test_exact_clocks_on_a_worked_group(self) -> None:
        row = row_for(three_component_group())
        self.assertEqual(row["component_count"], 3)
        self.assertEqual(row["event_to_receive_latency_ns"], [100, 200, 500])
        self.assertEqual(row["formation_latency_ns"], 2_500 - 1_100)
        self.assertEqual(row["within_group_receive_gaps_ns"], [600, 800])
        self.assertEqual(row["max_within_group_receive_gap_ns"], 800)
        self.assertEqual(row["sequence_span"], 2)
        self.assertTrue(row["sequence_contiguous"])
        self.assertTrue(row["single_channel_group"])

    def test_first_lawful_availability_is_the_f_last_receive_time(self) -> None:
        """Section 2: the first lawful knowledge time for a completed group is F_LAST recv."""
        row = row_for(three_component_group())
        self.assertEqual(row["clocks"]["first_lawful_availability_ns"], 2_500)
        self.assertEqual(row["clocks"]["f_last_ts_recv_ns"], 2_500)

    def test_the_four_clocks_stay_distinct(self) -> None:
        row = row_for(three_component_group(), decision_ts_recv_ns=9_000)
        clocks = row["clocks"]
        self.assertEqual(clocks["first_component_ts_event_ns"], 1_000)
        self.assertEqual(clocks["first_component_ts_recv_ns"], 1_100)
        self.assertEqual(clocks["f_last_ts_recv_ns"], 2_500)
        self.assertEqual(clocks["decision_ts_recv_ns"], 9_000)
        self.assertEqual(len({v for v in clocks.values() if v is not None}), 4)

    def test_f_last_to_decision_delay(self) -> None:
        row = row_for(three_component_group(), decision_ts_recv_ns=9_000)
        self.assertEqual(row["f_last_to_decision_delay_ns"], 6_500)

    def test_a_decision_before_availability_is_refused(self) -> None:
        """A decision cannot be taken before the group is knowable."""
        with self.assertRaises(ClockError):
            row_for(three_component_group(), decision_ts_recv_ns=2_499)

    def test_an_unclosed_group_is_refused_not_degraded(self) -> None:
        unclosed = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10),
                component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=11),
            ]
        )
        with self.assertRaises(ClockError):
            row_for(unclosed)

    def test_nonmonotonic_receive_times_are_refused(self) -> None:
        broken = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=2_000, sequence=10),
                component(ts_event_ns=1_500, ts_recv_ns=1_100, sequence=11, is_last=True),
            ]
        )
        with self.assertRaises(ClockError):
            row_for(broken)

    def test_empty_group_is_refused(self) -> None:
        with self.assertRaises(ClockError):
            row_for(group([]))

    def test_noncontiguous_sequence_is_recorded_not_repaired(self) -> None:
        gapped = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10),
                component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=19, is_last=True),
            ]
        )
        row = row_for(gapped)
        self.assertFalse(row["sequence_contiguous"])
        self.assertEqual(row["sequence_span"], 9)

    def test_multi_channel_group_is_flagged(self) -> None:
        mixed = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10, channel_id=1),
                component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=11, channel_id=4, is_last=True),
            ]
        )
        row = row_for(mixed)
        self.assertFalse(row["single_channel_group"])
        self.assertEqual(row["channels"], [1, 4])

    def test_rows_are_stamped_as_serialization_not_economic(self) -> None:
        self.assertEqual(row_for(three_component_group())["interpretation_domain"], INTERPRETATION_DOMAIN)


class RecognitionLabelTest(unittest.TestCase):
    def test_prior_must_precede_and_reports_positive_lead(self) -> None:
        label = RecognitionLabel(label=PRIOR, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=400)
        self.assertEqual(label.lead_ns, 600)
        with self.assertRaises(ClockError):
            RecognitionLabel(label=PRIOR, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=1_000)

    def test_t0_must_coincide(self) -> None:
        RecognitionLabel(label=T0, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=1_000)
        with self.assertRaises(ClockError):
            RecognitionLabel(label=T0, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=1_001)

    def test_horizon_must_follow(self) -> None:
        label = RecognitionLabel(label=HORIZON, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=1_600)
        self.assertEqual(label.lead_ns, -600)
        with self.assertRaises(ClockError):
            RecognitionLabel(label=HORIZON, clock=CAUSAL_CLOCK, reference_ns=1_000, observed_ns=1_000)

    def test_recognition_must_be_on_the_named_clock(self) -> None:
        with self.assertRaises(ClockError):
            RecognitionLabel(label=T0, clock="ts_event_ns", reference_ns=1, observed_ns=1)

    def test_unknown_label_is_refused(self) -> None:
        with self.assertRaises(ClockError):
            RecognitionLabel(label="MAYBE", clock=CAUSAL_CLOCK, reference_ns=1, observed_ns=1)


class ClockCalculatorTest(unittest.TestCase):
    def test_observations_land_in_the_declared_strata(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        rows = {r["measure"]: r for r in calc.companion_rows()}
        self.assertEqual(rows["event_to_receive_latency_ns"]["value"]["n"], 3)
        self.assertEqual(rows["event_to_receive_latency_ns"]["value"]["maximum"], 500.0)
        self.assertEqual(rows["formation_latency_ns"]["value"]["n"], 1)
        self.assertEqual(rows["within_group_receive_gap_ns"]["value"]["maximum"], 800.0)

    def test_days_do_not_pool(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        calc.observe(row_for(three_component_group(), source_day="20211005"))
        days = {r["stratum"]["source_day"] for r in calc.formation_latency.rows()}
        self.assertEqual(days, {"20211004", "20211005"})
        self.assertEqual(calc.formation_latency.stratum_count, 2)

    def test_component_count_and_channel_separate_strata(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        two = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10),
                component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=11, is_last=True),
            ]
        )
        calc.observe(row_for(two))
        subfamilies = {r["stratum"]["subfamily_id"] for r in calc.formation_latency.rows()}
        self.assertEqual(subfamilies, {clock_subfamily(1, 3), clock_subfamily(1, 2)})

    def test_single_component_group_is_excluded_from_gaps_not_counted_as_zero(self) -> None:
        """A zero gap and no gap are different facts."""
        calc = ClockCalculator()
        single = group([component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10, is_last=True)])
        calc.observe(row_for(single))
        row = calc.within_group_gap.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_missing_decision_time_is_excluded_and_counted(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        row = calc.f_last_to_decision.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_multi_channel_member_is_attributed_to_each_channel_it_spans(self) -> None:
        calc = ClockCalculator()
        mixed = group(
            [
                component(ts_event_ns=1_000, ts_recv_ns=1_100, sequence=10, channel_id=1),
                component(ts_event_ns=1_500, ts_recv_ns=1_700, sequence=11, channel_id=4, is_last=True),
            ]
        )
        calc.observe(row_for(mixed))
        subfamilies = {r["stratum"]["subfamily_id"] for r in calc.formation_latency.rows()}
        self.assertEqual(subfamilies, {clock_subfamily(1, 2), clock_subfamily(4, 2)})
        self.assertEqual(calc.multi_channel_members, 1)

    def test_summary_declares_the_interpretation_boundary(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        summary = calc.summary()
        self.assertEqual(summary["section"], "4.5")
        self.assertEqual(summary["interpretation_domain"], INTERPRETATION_DOMAIN)
        self.assertEqual(summary["causal_clock"], CAUSAL_CLOCK)
        self.assertEqual(summary["members_seen"], 1)

    def test_every_companion_row_carries_its_declaration(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        for row in calc.companion_rows():
            for field in ("numerator_formula", "population", "causal_cutoff", "status", "missingness_rule"):
                self.assertTrue(row["declaration"][field])

    def test_a_foreign_row_is_refused(self) -> None:
        calc = ClockCalculator()
        row = row_for(three_component_group())
        row["interpretation_domain"] = "ECONOMIC"
        with self.assertRaises(ClockError):
            calc.observe(row)

    def test_memory_is_bounded_by_strata_not_group_count(self) -> None:
        calc = ClockCalculator(exact_cap=16)
        for index in range(500):
            calc.observe(row_for(three_component_group(), group_index=index))
        self.assertEqual(calc.members_seen, 500)
        self.assertEqual(calc.formation_latency.stratum_count, 1)
        value = calc.formation_latency.rows()[0]["value"]
        self.assertEqual(value["n"], 500)
        self.assertEqual(value["quantile_sample_size"], 16)
        self.assertEqual(value["maximum"], 1400.0)


if __name__ == "__main__":
    unittest.main()
