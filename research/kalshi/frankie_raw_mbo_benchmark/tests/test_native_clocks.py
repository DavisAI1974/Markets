"""Tests for section 4.5 formation, serialization, and observation clocks."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (
    BASIS_F_LAST_RECEIVE_OF_THE_GROUP,
    BASIS_OBSERVED_ON_THE_RECORD,
    CAUSAL_CLOCK,
    DECISION_BASIS_UNDECLARED_ON_ROW,
    EVALUATION_BASIS_LEGACY_DECISION_TS,
    NOT_ON_THIS_ROW,
    CAUSAL_CLOCK_LAYER_IDS,
    CLOCK_EVENT_KNOWN_BY,
    CLOCK_EVENT_TIME,
    CLOCK_FEATURE_AVAILABILITY,
    CLOCK_LOCK_TIME,
    CLOCK_MODEL_EVALUATION,
    CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION,
    CLOCK_RECEIVE_TIME,
    DECISION_BASIS_ABSENT,
    DECISION_BASIS_OBSERVED,
    DECISION_BASIS_REPLAY_EARLIEST,
    DISCOVERY_BASIS_EMITTED,
    DISCOVERY_BASIS_NONE,
    EVALUATION_BASIS_NONE,
    EVALUATION_BASIS_STAGED,
    EVENT_CLOCK,
    FEATURE_BASIS_OBSERVED,
    FEATURE_BASIS_REPLAY_EARLIEST,
    FEATURE_SCOPE_MEMBER_ROW,
    HORIZON,
    INTERPRETATION_DOMAIN,
    LOCK_BASIS_PRINCIPAL,
    PRIOR,
    T0,
    ClockCalculator,
    ClockError,
    RecognitionLabel,
    clock_subfamily,
    member_clock_row,
    causal_clock_layers_from_legacy_clocks,
    check_causal_clock_order,
    stamp_discovery_confirmations,
    stamp_model_evaluation,
    validate_causal_clock_layers,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry


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

    def test_a_declared_absence_is_excluded_and_counted(self) -> None:
        """Still the rule - but it now takes a DECLARATION, not a forgotten argument."""
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group(),
                             decision_basis=DECISION_BASIS_ABSENT))
        row = calc.f_last_to_decision.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_the_replay_basis_populates_the_clock_that_was_empty_on_every_member(self) -> None:
        """D-1. 43,569 of 43,569 excluded, because nobody ever passed a decision time.

        A replay takes its decision at the first lawfully knowable instant, so the delay is
        zero - a measurement, not an absence - and the basis says which of the two it is.
        """
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        row = calc.f_last_to_decision.rows()[0]
        self.assertEqual(row["value"]["n"], 1)
        self.assertEqual(row["value"]["maximum"], 0.0)
        self.assertEqual(row["excluded_missing_members"], 0)

    def test_the_basis_travels_on_the_exact_record(self) -> None:
        """A zero delay and an unknown delay must never be indistinguishable downstream."""
        replayed = row_for(three_component_group())
        absent = row_for(three_component_group(), decision_basis=DECISION_BASIS_ABSENT)
        self.assertEqual(replayed["decision_basis"], DECISION_BASIS_REPLAY_EARLIEST)
        self.assertEqual(replayed["f_last_to_decision_delay_ns"], 0)
        self.assertEqual(absent["decision_basis"], DECISION_BASIS_ABSENT)
        self.assertIsNone(absent["f_last_to_decision_delay_ns"])
        self.assertIsNone(absent["clocks"]["decision_ts_recv_ns"])

    def test_an_observed_decision_time_overrides_the_replay_convention(self) -> None:
        """Passing a real time alongside a replay basis must not silently discard it."""
        g = three_component_group()
        f_last = max(int(c["ts_recv_ns"]) for c in g["raw_actions"])
        row = row_for(g, decision_ts_recv_ns=f_last + 500,
                      decision_basis=DECISION_BASIS_REPLAY_EARLIEST)
        self.assertEqual(row["decision_basis"], DECISION_BASIS_OBSERVED)
        self.assertEqual(row["f_last_to_decision_delay_ns"], 500)

    def test_an_unknown_basis_is_refused(self) -> None:
        with self.assertRaises(ClockError):
            row_for(three_component_group(), decision_basis="ASSUMED")

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


class CausalClockLayersTest(unittest.TestCase):
    """S121 item one: the registry's seven causal clocks, produced BY NAME on every member row.

    The delivery receipt already named all seven layer ids as delivered with the member line's
    hash as evidence, while no field on the row was keyed by any of them (packet section 2).
    Delivered-by-hash and findable-by-name are different facts; these pin the second.
    """

    def test_the_seven_ids_are_exactly_the_registrys_causal_clocks_group(self) -> None:
        registry = load_registry()
        group = next(g for g in registry["groups"] if g["group_id"] == "causal_clocks")
        self.assertEqual([e["layer_id"] for e in group["entries"]], list(CAUSAL_CLOCK_LAYER_IDS))

    def test_every_member_row_carries_the_seven_by_id_each_with_a_clock_and_a_basis(self) -> None:
        layers = row_for(three_component_group())["causal_clocks"]
        self.assertEqual(set(layers), set(CAUSAL_CLOCK_LAYER_IDS))
        for layer_id, entry in layers.items():
            with self.subTest(layer=layer_id):
                self.assertIn(entry["clock"], (CAUSAL_CLOCK, EVENT_CLOCK))
                self.assertTrue(entry["basis"])

    def test_the_stream_clocks_carry_the_groups_own_instants(self) -> None:
        layers = row_for(three_component_group())["causal_clocks"]
        self.assertEqual(
            layers[CLOCK_EVENT_TIME],
            {"clock": EVENT_CLOCK, "first_component_ns": 1_000, "f_last_ns": 2_000,
             "basis": BASIS_OBSERVED_ON_THE_RECORD},
        )
        self.assertEqual(
            layers[CLOCK_RECEIVE_TIME],
            {"clock": CAUSAL_CLOCK, "first_component_ns": 1_100, "f_last_ns": 2_500,
             "basis": BASIS_OBSERVED_ON_THE_RECORD},
        )
        self.assertEqual(
            layers[CLOCK_EVENT_KNOWN_BY],
            {"clock": CAUSAL_CLOCK, "value_ns": 2_500, "basis": BASIS_F_LAST_RECEIVE_OF_THE_GROUP},
        )
        feature = layers[CLOCK_FEATURE_AVAILABILITY]
        self.assertEqual(feature["value_ns"], 2_500)
        self.assertEqual(feature["basis"], FEATURE_BASIS_REPLAY_EARLIEST)
        self.assertEqual(feature["scope"], FEATURE_SCOPE_MEMBER_ROW)

    def test_event_known_by_is_the_first_lawful_availability_under_its_registry_name(self) -> None:
        row = row_for(three_component_group())
        self.assertEqual(
            row["causal_clocks"][CLOCK_EVENT_KNOWN_BY]["value_ns"],
            row["clocks"]["first_lawful_availability_ns"],
        )

    def test_an_observed_feature_computation_instant_is_carried_with_its_basis(self) -> None:
        entry = row_for(three_component_group(), feature_computed_at_ns=2_900)["causal_clocks"][
            CLOCK_FEATURE_AVAILABILITY]
        self.assertEqual(entry["value_ns"], 2_900)
        self.assertEqual(entry["basis"], FEATURE_BASIS_OBSERVED)

    def test_a_feature_cannot_be_available_before_the_group_is_knowable(self) -> None:
        with self.assertRaises(ClockError):
            row_for(three_component_group(), feature_computed_at_ns=2_499)

    def test_the_two_downstream_clocks_are_declared_not_fabricated(self) -> None:
        layers = row_for(three_component_group())["causal_clocks"]
        self.assertIsNone(layers[CLOCK_MODEL_EVALUATION]["value_ns"])
        self.assertEqual(layers[CLOCK_MODEL_EVALUATION]["basis"], EVALUATION_BASIS_NONE)
        self.assertIsNone(layers[CLOCK_LOCK_TIME]["value_ns"])
        self.assertEqual(layers[CLOCK_LOCK_TIME]["basis"], LOCK_BASIS_PRINCIPAL)
        discovery = layers[CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION]
        self.assertEqual(discovery["confirmed_at_this_cutoff"], [])
        self.assertEqual(discovery["basis"], DISCOVERY_BASIS_NONE)

    def test_stamping_an_invocation_puts_the_cutoff_on_the_row(self) -> None:
        row = row_for(three_component_group())
        stamp_model_evaluation(row, staged_at_recv_ns=2_500)
        entry = row["causal_clocks"][CLOCK_MODEL_EVALUATION]
        self.assertEqual(entry["value_ns"], 2_500)
        self.assertEqual(entry["basis"], EVALUATION_BASIS_STAGED)

    def test_an_invocation_cannot_be_staged_before_the_group_is_knowable(self) -> None:
        with self.assertRaises(ClockError):
            stamp_model_evaluation(row_for(three_component_group()), staged_at_recv_ns=2_499)

    def test_stamping_no_invocation_leaves_the_declared_null(self) -> None:
        row = row_for(three_component_group())
        stamp_model_evaluation(row, staged_at_recv_ns=None)
        entry = row["causal_clocks"][CLOCK_MODEL_EVALUATION]
        self.assertIsNone(entry["value_ns"])
        self.assertEqual(entry["basis"], EVALUATION_BASIS_NONE)

    def test_stamping_confirmations_records_each_call_at_this_cutoff(self) -> None:
        row = row_for(three_component_group())
        stamp_discovery_confirmations(row, [{
            "candidate_id": "c1", "outcome": HORIZON, "birth_recv_ns": 1_000,
            "recognized_recv_ns": 2_000, "recognized_recv_ns_basis": "AVAILABLE_SECOND_BIN",
        }])
        entry = row["causal_clocks"][CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION]
        self.assertEqual(entry["basis"], DISCOVERY_BASIS_EMITTED)
        self.assertEqual(len(entry["confirmed_at_this_cutoff"]), 1)
        confirmed = entry["confirmed_at_this_cutoff"][0]
        self.assertEqual(confirmed["candidate_id"], "c1")
        self.assertEqual(confirmed["confirmed_at_cutoff_ns"], 2_500)
        self.assertEqual(confirmed["recognized_recv_ns"], 2_000)

    def test_a_confirmation_without_its_identity_is_refused(self) -> None:
        with self.assertRaises(ClockError):
            stamp_discovery_confirmations(row_for(three_component_group()), [{"outcome": HORIZON}])

    def test_the_five_field_clocks_object_is_unchanged(self) -> None:
        """The stream reads `clocks.first_lawful_availability_ns` and the registry validator
        checks the receipt's four keys; the seven ride BESIDE, never inside."""
        row = row_for(three_component_group())
        self.assertEqual(
            set(row["clocks"]),
            {"first_component_ts_event_ns", "first_component_ts_recv_ns", "f_last_ts_recv_ns",
             "first_lawful_availability_ns", "decision_ts_recv_ns"},
        )

    def test_the_summary_declares_the_carrier_and_every_layer_once(self) -> None:
        calc = ClockCalculator()
        calc.observe(row_for(three_component_group()))
        declared = calc.summary()["causal_clock_layers"]
        self.assertEqual(declared["carrier"], "member_row.causal_clocks")
        self.assertEqual(declared["layer_ids"], list(CAUSAL_CLOCK_LAYER_IDS))
        self.assertEqual(set(declared["declarations"]), set(CAUSAL_CLOCK_LAYER_IDS))
        for text in declared["declarations"].values():
            self.assertTrue(text.strip())

    def test_feature_availability_carries_the_latest_input_it_consumed_and_its_cutoff(self) -> None:
        """The Step-1 module's idea, not its code: every derived block on the row consumed the
        group's components and nothing later, so the latest contributing receive instant and
        the cutoff the features were computed at travel together, and the first can never
        exceed the second (`max_contributing_ts_recv_ns > feature_cutoff_ts_recv_ns` is the
        ordering failure Step-1 refuses on)."""
        feature = row_for(three_component_group())["causal_clocks"][CLOCK_FEATURE_AVAILABILITY]
        self.assertEqual(feature["max_contributing_ts_recv_ns"], 2_500)
        self.assertEqual(feature["feature_cutoff_ts_recv_ns"], 2_500)
        self.assertLessEqual(feature["max_contributing_ts_recv_ns"], feature["feature_cutoff_ts_recv_ns"])
        observed = row_for(three_component_group(), feature_computed_at_ns=2_900)["causal_clocks"][
            CLOCK_FEATURE_AVAILABILITY]
        self.assertEqual(observed["max_contributing_ts_recv_ns"], 2_500)
        self.assertEqual(observed["feature_cutoff_ts_recv_ns"], 2_900)

    def test_the_availability_chain_holds_and_is_returned_as_three_named_instants(self) -> None:
        """event_known_by <= feature_availability <= model_evaluation, the order the V4
        `validate_availability_chain` enforces, checked here with three comparisons and no
        import from that universe."""
        row = row_for(three_component_group())
        stamp_model_evaluation(row, staged_at_recv_ns=2_600)
        chain = check_causal_clock_order(row["causal_clocks"])
        self.assertEqual(chain, {"event_known_by_ns": 2_500, "feature_availability_ns": 2_500,
                                 "model_evaluation_ns": 2_600})

    def test_a_disordered_chain_is_refused_with_the_clocks_named(self) -> None:
        """PRODUCED, not asserted: the refusal fires on a row whose feature clock was moved
        before the group was knowable."""
        row = row_for(three_component_group())
        row["causal_clocks"][CLOCK_FEATURE_AVAILABILITY]["value_ns"] = 2_499
        with self.assertRaisesRegex(ClockError, "clock_event_known_by"):
            check_causal_clock_order(row["causal_clocks"])
        row = row_for(three_component_group())
        stamp_model_evaluation(row, staged_at_recv_ns=2_600)
        row["causal_clocks"][CLOCK_FEATURE_AVAILABILITY]["value_ns"] = 2_700
        with self.assertRaisesRegex(ClockError, "clock_model_evaluation"):
            check_causal_clock_order(row["causal_clocks"])

    def test_an_unstamped_evaluation_clock_does_not_break_the_chain(self) -> None:
        chain = check_causal_clock_order(row_for(three_component_group())["causal_clocks"])
        self.assertIsNone(chain["model_evaluation_ns"])

    def test_the_validator_refuses_a_partial_or_misshapen_object(self) -> None:
        good = row_for(three_component_group())["causal_clocks"]
        self.assertEqual(validate_causal_clock_layers(good), good)
        partial = {CLOCK_EVENT_TIME: dict(good[CLOCK_EVENT_TIME])}
        with self.assertRaisesRegex(ClockError, "causal_clocks"):
            validate_causal_clock_layers(partial)
        no_basis = {k: dict(v) for k, v in good.items()}
        del no_basis[CLOCK_LOCK_TIME]["basis"]
        with self.assertRaisesRegex(ClockError, "basis"):
            validate_causal_clock_layers(no_basis)

    def test_a_pre_s121_clocks_object_yields_three_clocks_and_four_declared_absences(self) -> None:
        """The delivered Sunday ledger carries the five-field object and nothing keyed by a
        registry id. What it can support is derived; what it cannot is said, never patched."""
        legacy = {
            "first_component_ts_event_ns": 1_000, "first_component_ts_recv_ns": 1_100,
            "f_last_ts_recv_ns": 2_500, "first_lawful_availability_ns": 2_500,
            "decision_ts_recv_ns": 2_500,
        }
        layers = causal_clock_layers_from_legacy_clocks(legacy, ts_event_ns=2_000)
        self.assertEqual(set(layers), set(CAUSAL_CLOCK_LAYER_IDS))
        self.assertEqual(layers[CLOCK_EVENT_TIME],
                         {"clock": EVENT_CLOCK, "first_component_ns": 1_000, "f_last_ns": 2_000,
                          "basis": BASIS_OBSERVED_ON_THE_RECORD})
        self.assertEqual(layers[CLOCK_RECEIVE_TIME],
                         {"clock": CAUSAL_CLOCK, "first_component_ns": 1_100, "f_last_ns": 2_500,
                          "basis": BASIS_OBSERVED_ON_THE_RECORD})
        self.assertEqual(layers[CLOCK_EVENT_KNOWN_BY],
                         {"clock": CAUSAL_CLOCK, "value_ns": 2_500, "basis": BASIS_F_LAST_RECEIVE_OF_THE_GROUP})
        for layer_id in (CLOCK_FEATURE_AVAILABILITY, CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION,
                         CLOCK_LOCK_TIME):
            with self.subTest(layer=layer_id):
                self.assertIsNone(layers[layer_id]["value_ns"])
                self.assertEqual(layers[layer_id]["basis"], NOT_ON_THIS_ROW)
        # F-feed-5 (S122, measured on the real Sunday ledgers): the old row DOES carry a
        # decision instant - clocks.decision_ts_recv_ns under decision_basis - so the model-
        # evaluation clock derives from it, with the convention it was adopted under named.
        self.assertEqual(layers[CLOCK_MODEL_EVALUATION], {
            "clock": CAUSAL_CLOCK, "value_ns": 2_500,
            "basis": EVALUATION_BASIS_LEGACY_DECISION_TS,
            "decision_basis": DECISION_BASIS_UNDECLARED_ON_ROW,
        })
        self.assertEqual(validate_causal_clock_layers(layers), layers)

    def test_the_legacy_decision_instant_carries_the_rows_own_decision_basis(self) -> None:
        legacy = {
            "first_component_ts_event_ns": 1_000, "first_component_ts_recv_ns": 1_100,
            "f_last_ts_recv_ns": 2_500, "first_lawful_availability_ns": 2_500,
            "decision_ts_recv_ns": 2_600,
        }
        layers = causal_clock_layers_from_legacy_clocks(
            legacy, ts_event_ns=2_000, decision_basis="REPLAY_EARLIEST_LAWFUL_AVAILABILITY")
        entry = layers[CLOCK_MODEL_EVALUATION]
        self.assertEqual(entry["value_ns"], 2_600)
        self.assertEqual(entry["basis"], EVALUATION_BASIS_LEGACY_DECISION_TS)
        self.assertEqual(entry["decision_basis"], "REPLAY_EARLIEST_LAWFUL_AVAILABILITY")
        self.assertEqual(check_causal_clock_order(layers)["model_evaluation_ns"], 2_600)

    def test_a_legacy_row_without_a_decision_instant_still_says_not_on_this_row(self) -> None:
        legacy = {
            "first_component_ts_event_ns": 1_000, "first_component_ts_recv_ns": 1_100,
            "f_last_ts_recv_ns": 2_500, "first_lawful_availability_ns": 2_500,
            "decision_ts_recv_ns": None,
        }
        layers = causal_clock_layers_from_legacy_clocks(legacy, ts_event_ns=2_000)
        self.assertEqual(layers[CLOCK_MODEL_EVALUATION],
                         {"clock": CAUSAL_CLOCK, "value_ns": None, "basis": NOT_ON_THIS_ROW})

    def test_the_declaration_prose_is_not_repeated_on_every_row(self) -> None:
        """Bytes: the producer prose lives once in the summary; a row carries short bases."""
        for entry in row_for(three_component_group())["causal_clocks"].values():
            for value in entry.values():
                if isinstance(value, str):
                    self.assertLess(len(value), 64)


if __name__ == "__main__":
    unittest.main()
