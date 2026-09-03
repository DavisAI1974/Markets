"""Tests for sections 5 and 6: artifact layers and fail-closed acceptance gates."""
from __future__ import annotations

import json
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    ACCEPTED,
    canonical_hash,
    GATE_COVERAGE,
    GATE_DENOMINATORS,
    GATE_DETERMINISM,
    GATE_ISOLATION,
    GATE_NOT_A_MODEL_RUN,
    REJECTED,
    REQUIRED_GATES,
    REQUIRED_LAYERS,
    CalculationRunError,
    LAYER_AVERAGES,
    LAYER_FINDINGS,
    LAYER_RECONCILIATION,
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import (
    ALIAS_FORM_KEY,
    ALIAS_LEGEND_KEY,
    FORM_ALIASED,
    FORM_PLAIN,
    expand_aliases,
    read_averaged_rows,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import member_clock_row
from research.kalshi.frankie_raw_mbo_benchmark.native_discovery import (
    INCREMENTAL,
    DiscoveryCalculator,
    FeatureSchema,
)

TOTAL_RECORDS = 3


def identity(**overrides) -> RunIdentity:
    base = dict(
        run_id="run-1",
        arm="A_MEMORY",
        mission_sha256="a" * 64,
        calculation_contract_sha256="b" * 64,
        knowledge_manifest_hash="c" * 64,
        source_manifest_hash="d" * 64,
        total_mbo_records=TOTAL_RECORDS,
        code_commit="deadbeef",
    )
    base.update(overrides)
    return RunIdentity(**base)


def component(ts_event_ns, ts_recv_ns, sequence, is_last=False):
    return {
        "instrument_id": 42,
        "publisher_id": 1,
        "channel_id": 1,
        "order_id": 900,
        "action": "A",
        "side": "B",
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


def group():
    return {
        "raw_actions": [
            component(1_000, 1_100, 10),
            component(1_500, 1_700, 11),
            component(2_000, 2_500, 12, is_last=True),
        ]
    }


def make_run(**overrides) -> NativeCalculationRun:
    kwargs = dict(
        replenishment_horizon_ns=1_000,
        response_horizons_ns=(100,),
        response_horizon_version="hv1",
        response_value_names=("price_response",),
        # These runs do not exercise the session path. Opting out is explicit and visible;
        # the default is ON, so forgetting leaves the reconciliation enabled rather than off.
        session_strata=False,
    )
    kwargs.update(overrides)
    return NativeCalculationRun(identity(), **kwargs)


def drive(run: NativeCalculationRun, *, records=TOTAL_RECORDS, f_last=True, cursor=1) -> None:
    """Minimum work that satisfies coverage and clock gates."""
    run.coverage.observe_group(group_index=0, record_count=records, f_last_closed=f_last, cursor=cursor)
    row = member_clock_row(
        group(),
        group_index=0,
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="A_A_A",
        side_orientation="BID",
        session_phase="RTH",
    )
    run.clocks.observe(row)
    run.note_member_row()


class RunIdentityTest(unittest.TestCase):
    def test_arm_and_hashes_are_validated(self) -> None:
        with self.assertRaises(CalculationRunError):
            identity(arm="B0")
        with self.assertRaises(CalculationRunError):
            identity(mission_sha256="short")
        with self.assertRaises(CalculationRunError):
            identity(total_mbo_records=0)


class LayerTest(unittest.TestCase):
    def test_all_seven_layers_are_emitted(self) -> None:
        run = make_run()
        drive(run)
        layers = run.finalize()["layers"]
        self.assertEqual(set(layers), set(REQUIRED_LAYERS))

    def test_every_required_gate_is_evaluated(self) -> None:
        """Named for the set, not a count - it read "eight" while REQUIRED_GATES held nine."""
        run = make_run()
        drive(run)
        gates = {g["gate"] for g in run.finalize()["gates"]}
        self.assertEqual(gates, set(REQUIRED_GATES))

    def test_disagreeing_sections_reject_the_run_through_the_runner(self) -> None:
        """The horizontal gate, exercised where it actually runs rather than in isolation.

        Reproduces run 33605852433: 4.9 pinned to the bounds of (bid-ask)/(bid+ask), 4.12
        computing the same formula and never approaching them. Every other gate passes.
        """
        run = make_run()
        drive(run)
        pinned = [
            {"section": "4.9", "measure": "relative_imbalance",
             "declaration": {"numerator_formula": "(bid - ask) / (bid + ask)",
                             "population": "ladder transitions", "causal_cutoff": "ts_recv_ns",
                             "status": "RESOLVED", "missingness_rule": "no exclusions"},
             "value": {"n": 5000, "sum": 5000.0, "sum_of_squares": 5000.0,
                       "minimum": 1.0, "maximum": 1.0}},
            {"section": "4.12", "measure": "normalized_imbalance",
             "declaration": {"numerator_formula": "(bid - ask) / (bid + ask)",
                             "population": "ladder transitions", "causal_cutoff": "ts_recv_ns",
                             "status": "RESOLVED", "missingness_rule": "no exclusions"},
             "value": {"n": 5000, "sum": 269.0, "sum_of_squares": 19.4,
                       "minimum": 0.0116, "maximum": 0.1109}},
        ]
        run._averaged_companions = lambda _real=run._averaged_companions: _real() + pinned
        result = run.finalize()
        self.assertEqual(result["verdict"], "REJECTED")
        self.assertIn("cross_section_agreement", result["failed_gates"])
        detail = next(g["detail"] for g in result["gates"]
                      if g["gate"] == "cross_section_agreement")
        self.assertIn("relative_book_imbalance", detail)

    def test_a_tolerated_absence_reaches_the_result_as_data_not_only_as_prose(self) -> None:
        """D60. A note that lives only in a detail string is a note nobody can query."""
        run = make_run()
        drive(run)
        lone = [{"section": "4.12", "measure": "normalized_imbalance",
                 "declaration": {"numerator_formula": "(bid - ask) / (bid + ask)",
                             "population": "ladder transitions", "causal_cutoff": "ts_recv_ns",
                             "status": "RESOLVED", "missingness_rule": "no exclusions"},
                 "value": {"n": 10, "sum": 0.5, "sum_of_squares": 0.03,
                           "minimum": 0.01, "maximum": 0.11}}]
        run._averaged_companions = lambda _real=run._averaged_companions: _real() + lone
        result = run.finalize()
        self.assertEqual(result["verdict"], "ACCEPTED", result["failed_gates"])
        gate = next(g for g in result["gates"] if g["gate"] == "cross_section_agreement")
        self.assertTrue(gate["verdicts"][0]["notes"])

    def test_a_clean_run_is_accepted(self) -> None:
        run = make_run()
        drive(run)
        result = run.finalize()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(result["failed_gates"], [])

    def test_the_result_is_hashed(self) -> None:
        run = make_run()
        drive(run)
        self.assertEqual(len(run.finalize()["result_hash"]), 64)

    def test_finalize_is_single_use(self) -> None:
        run = make_run()
        drive(run)
        run.finalize()
        with self.assertRaises(CalculationRunError):
            run.finalize()


class FieldCensusLayerTest(unittest.TestCase):
    """F-10: the member layer carries a per-field census of every row it received."""

    def test_every_row_passed_to_note_member_row_is_censused(self):
        run = make_run()
        drive(run)
        run.note_member_row(row={"a": 1, "book": {"levels": [{"size": 2}, {"size": 2}]}})
        run.note_member_row(row={"a": 1, "book": {"levels": []}})
        layer = run.finalize()["layers"]["exact_member_ledger"]
        census = layer["field_census"]
        self.assertEqual(census["rows_observed"], 2)
        by_path = {f["field"]: f for f in census["fields"]}
        self.assertTrue(by_path["a"]["degenerate"])
        self.assertEqual(by_path["book.levels[].size"]["observations"], 2)
        self.assertEqual(by_path["book.levels[].size"]["rows_with_field"], 1)

    def test_a_member_counted_without_its_row_makes_the_census_partial_and_says_so(self):
        """`drive` counts one member with no row. The flag is a FACT on the layer, not a
        gate here, because count-only callers exist; the spawn emitter refuses on it."""
        run = make_run()
        drive(run)
        layer = run.finalize()["layers"]["exact_member_ledger"]
        self.assertEqual(layer["exact_member_rows"], 1)
        self.assertEqual(layer["field_census"]["rows_observed"], 0)
        self.assertFalse(layer["field_census_covers_every_member_row"])

    def test_the_flag_is_true_when_every_member_carried_its_row(self):
        run = make_run()
        run.coverage.observe_group(group_index=0, record_count=TOTAL_RECORDS, f_last_closed=True, cursor=1)
        row = member_clock_row(
            group(), group_index=0, source_day="20211004", source_role="HELD_OUT_BLIND",
            continuity_segment=0, family_id="A_A_A", side_orientation="BID", session_phase="RTH",
        )
        run.clocks.observe(row)
        run.note_member_row(row=row)
        layer = run.finalize()["layers"]["exact_member_ledger"]
        self.assertEqual(layer["exact_member_rows"], layer["field_census"]["rows_observed"])
        self.assertTrue(layer["field_census_covers_every_member_row"])


class GateTest(unittest.TestCase):
    def test_incomplete_record_coverage_rejects(self) -> None:
        run = make_run()
        drive(run, records=TOTAL_RECORDS - 1)
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertIn(GATE_COVERAGE, result["failed_gates"])

    def test_an_unclosed_group_rejects(self) -> None:
        run = make_run()
        drive(run, f_last=False)
        self.assertIn(GATE_COVERAGE, run.finalize()["failed_gates"])

    def test_a_duplicate_group_index_rejects(self) -> None:
        run = make_run()
        drive(run)
        run.coverage.observe_group(group_index=0, record_count=0, f_last_closed=True, cursor=2)
        self.assertIn(GATE_COVERAGE, run.finalize()["failed_gates"])

    def test_a_cursor_regression_rejects(self) -> None:
        run = make_run()
        drive(run, cursor=10)
        run.coverage.observe_group(group_index=1, record_count=0, f_last_closed=True, cursor=5)
        self.assertIn(GATE_COVERAGE, run.finalize()["failed_gates"])

    def test_a_fifo_reconstruction_failure_rejects(self) -> None:
        run = make_run()
        drive(run)
        run.coverage.note_fifo_failure()
        self.assertIn(GATE_COVERAGE, run.finalize()["failed_gates"])

    def test_an_other_arm_read_rejects(self) -> None:
        run = make_run()
        drive(run)
        run.isolation.note_breach("OTHER_ARM")
        self.assertIn(GATE_ISOLATION, run.finalize()["failed_gates"])

    def test_a_sealed_surface_read_rejects(self) -> None:
        run = make_run()
        drive(run)
        run.isolation.note_breach("SEALED")
        self.assertIn(GATE_ISOLATION, run.finalize()["failed_gates"])

    def test_a_later_evidence_read_rejects(self) -> None:
        run = make_run()
        drive(run)
        run.isolation.note_breach("LATER_EVIDENCE")
        self.assertIn(GATE_ISOLATION, run.finalize()["failed_gates"])

    def test_a_recorded_denial_is_a_pass_not_a_breach(self) -> None:
        """Testing the wall and being refused is evidence the wall works."""
        run = make_run()
        drive(run)
        run.isolation.note_denial(surface="step1_census", reason="sealed for A scope")
        result = run.finalize()
        self.assertEqual(result["verdict"], ACCEPTED)
        self.assertEqual(len(result["isolation"]["denied_access_attempts"]), 1)

    def test_an_unknown_breach_kind_is_refused(self) -> None:
        run = make_run()
        with self.assertRaises(CalculationRunError):
            run.isolation.note_breach("SOMETHING")

    def test_a_fifo_identity_violation_rejects_determinism(self) -> None:
        run = make_run()
        drive(run)
        run.queue.identity_violations = 1
        self.assertIn(GATE_DETERMINISM, run.finalize()["failed_gates"])

    def test_unfrozen_discovery_rejects_determinism(self) -> None:
        schema = FeatureSchema(
            version="v1",
            feature_names=("depletion",),
            scaling={"depletion": (0.0, 1.0)},
            distance="EUCLIDEAN_ON_SCALED_FEATURES",
            radius=1.0,
            seed=0,
            mode=INCREMENTAL,
        )
        run = make_run(discovery=DiscoveryCalculator(schema))
        drive(run)
        self.assertIn(GATE_DETERMINISM, run.finalize()["failed_gates"])

    def test_frozen_discovery_passes_and_publishes_clusters(self) -> None:
        schema = FeatureSchema(
            version="v1",
            feature_names=("depletion",),
            scaling={"depletion": (0.0, 1.0)},
            distance="EUCLIDEAN_ON_SCALED_FEATURES",
            radius=1.0,
            seed=0,
            mode=INCREMENTAL,
        )
        discovery = DiscoveryCalculator(schema)
        discovery.assign(member_id="m1", features={"depletion": 0.0}, recv_ns=1)
        discovery.freeze()
        run = make_run(discovery=discovery)
        drive(run)
        result = run.finalize()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertIn("clusters", result["layers"]["open_world_indexes"])

    def test_a_missing_declaration_rejects_the_denominator_gate(self) -> None:
        run = make_run()
        drive(run)
        run.clocks.formation_latency.declaration.__dict__["population"] = ""
        self.assertIn(GATE_DENOMINATORS, run.finalize()["failed_gates"])

    def test_the_model_execution_gate_states_what_this_is_not(self) -> None:
        run = make_run()
        drive(run)
        gate = next(g for g in run.finalize()["gates"] if g["gate"] == GATE_NOT_A_MODEL_RUN)
        self.assertTrue(gate["passed"])
        self.assertIn("no principal invocation", gate["detail"])

    def test_one_failed_gate_rejects_the_whole_result(self) -> None:
        """Section 6 forbids partial promotion."""
        run = make_run()
        drive(run)
        run.isolation.note_breach("SEALED")
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertFalse(result["partial_promotion_permitted"])
        self.assertEqual(len(result["failed_gates"]), 1)
        self.assertEqual(set(result["layers"]), set(REQUIRED_LAYERS), "layers still emitted for audit")


PRINCIPAL = {
    "principal": "gpt-5.6-sol",
    "arm": "A_CLEAN",
    "role": "REAL_TIME_FRANKIE",
    "artifact_path": "forecasts/a_clean_rt_findings_20211004.json",
    "artifact_sha256": "f" * 64,
    "actual_principal_invocation": True,
    "controller_only": False,
}


class AttachToFinishedResultTest(unittest.TestCase):
    """S121 slice 2: the attach path reaches a FINISHED result.

    A run object cannot be rebuilt from its result JSON (the calculators' state is not
    serialized), so `attach_principal_findings_to_result` applies the SAME attribution and
    admission checks the live route applies and re-evaluates the one gate that depends on
    attachment, returning a new result that names the original by `evidence_result_hash`.
    """

    FINDING = {
        "claim": "withdrawal precedes touch retreat",
        "support": "n=12 runways in one stratum",
        "falsifier": "a stratum where retreat precedes withdrawal",
        "exemplars": ["g0001", "g0002"],
    }

    def finished(self) -> dict:
        run = make_run()
        drive(run)
        return run.finalize()

    def test_a_finished_evidence_only_result_receives_the_findings(self) -> None:
        result = self.finished()
        self.assertEqual(result["completion_status"], "EVIDENCE_ONLY")
        updated = NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=PRINCIPAL, findings=[self.FINDING]
        )
        self.assertEqual(updated["completion_status"], "PRINCIPAL_FINDINGS_ATTACHED")
        layer = updated["layers"]["positive_findings_report"]
        self.assertEqual(layer["findings"], [self.FINDING])
        self.assertEqual(layer["authored_by"], "PRINCIPAL")
        self.assertEqual(layer["principal"], PRINCIPAL)
        self.assertEqual(updated["verdict"], "ACCEPTED", updated["failed_gates"])

    def test_the_updated_result_names_the_evidence_and_hashes_itself(self) -> None:
        result = self.finished()
        updated = NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=PRINCIPAL, findings=[self.FINDING]
        )
        self.assertEqual(updated["evidence_result_hash"], result["result_hash"])
        self.assertNotEqual(updated["result_hash"], result["result_hash"])
        body = {k: v for k, v in updated.items() if k != "result_hash"}
        self.assertEqual(updated["result_hash"], canonical_hash(body))

    def test_the_attachment_gate_is_re_evaluated_and_names_the_principal(self) -> None:
        result = self.finished()
        updated = NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=PRINCIPAL, findings=[self.FINDING]
        )
        gate = next(g for g in updated["gates"] if g["gate"] == "calculation_evidence_is_not_model_execution")
        self.assertTrue(gate["passed"])
        self.assertIn(PRINCIPAL["principal"], gate["detail"])
        self.assertIn(PRINCIPAL["artifact_path"], gate["detail"])
        # The live route writes the identical gate wording, so a reader cannot tell the two
        # apart by the gate - only by `evidence_result_hash`, which is the point.
        live = make_run()
        drive(live)
        live.attach_principal_findings(execution=PRINCIPAL, findings=[self.FINDING])
        live_gate = next(
            g for g in live.finalize()["gates"] if g["gate"] == "calculation_evidence_is_not_model_execution"
        )
        self.assertEqual(gate, live_gate)

    def test_the_original_result_is_not_mutated(self) -> None:
        result = self.finished()
        frozen = json.dumps(result, sort_keys=True)
        NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=PRINCIPAL, findings=[self.FINDING]
        )
        self.assertEqual(json.dumps(result, sort_keys=True), frozen)

    def test_a_result_whose_hash_does_not_recompute_is_refused(self) -> None:
        result = self.finished()
        result["layers"]["exact_member_ledger"]["exact_member_rows"] = 999_999
        with self.assertRaises(CalculationRunError) as caught:
            NativeCalculationRun.attach_principal_findings_to_result(
                result, execution=PRINCIPAL, findings=[self.FINDING]
            )
        self.assertIn("result_hash", str(caught.exception))

    def test_a_result_already_carrying_principal_findings_is_refused(self) -> None:
        result = self.finished()
        once = NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=PRINCIPAL, findings=[self.FINDING]
        )
        with self.assertRaises(CalculationRunError) as caught:
            NativeCalculationRun.attach_principal_findings_to_result(
                once, execution=PRINCIPAL, findings=[self.FINDING]
            )
        self.assertIn("already", str(caught.exception))

    def test_the_live_routes_refusals_hold_on_the_finished_route(self) -> None:
        result = self.finished()
        for label, execution, findings in (
            ("controller_only", dict(PRINCIPAL, controller_only=True), [self.FINDING]),
            ("unproven invocation", dict(PRINCIPAL, actual_principal_invocation=False), [self.FINDING]),
            ("no artifact hash", {k: v for k, v in PRINCIPAL.items() if k != "artifact_sha256"}, [self.FINDING]),
            ("no falsifier", PRINCIPAL, [dict(self.FINDING, falsifier="  ")]),
            ("no exemplar", PRINCIPAL, [dict(self.FINDING, exemplars=[])]),
        ):
            with self.subTest(label=label), self.assertRaises(CalculationRunError):
                NativeCalculationRun.attach_principal_findings_to_result(
                    result, execution=execution, findings=findings
                )

    def test_a_result_of_another_schema_is_refused(self) -> None:
        result = dict(self.finished(), schema="SOMETHING_ELSE")
        with self.assertRaises(CalculationRunError):
            NativeCalculationRun.attach_principal_findings_to_result(
                result, execution=PRINCIPAL, findings=[self.FINDING]
            )


class FindingsTest(unittest.TestCase):
    def test_a_finding_requires_a_falsifier_and_an_exemplar(self) -> None:
        with self.assertRaises(CalculationRunError):
            make_run().attach_principal_findings(
                execution=PRINCIPAL,
                findings=[{"claim": "x", "support": "y", "falsifier": "  ", "exemplars": ["e1"]}],
            )
        with self.assertRaises(CalculationRunError):
            make_run().attach_principal_findings(
                execution=PRINCIPAL,
                findings=[{"claim": "x", "support": "y", "falsifier": "z", "exemplars": []}],
            )

    def test_a_finding_carries_its_exemplars_and_no_status_label(self) -> None:
        run = make_run()
        drive(run)
        run.attach_principal_findings(
            execution=PRINCIPAL,
            findings=[{
                "claim": "withdrawal precedes touch retreat",
                "support": "n=12 runways in one stratum",
                "falsifier": "a stratum where retreat precedes withdrawal",
                "exemplars": ["g0001", "g0002"],
            }],
        )
        layer = run.finalize()["layers"]["positive_findings_report"]
        self.assertNotIn("status", layer["findings"][0])
        self.assertEqual(len(layer["findings"][0]["exemplars"]), 2)
        self.assertTrue(layer["every_finding_carries_a_falsifier"])


class ReconciliationTest(unittest.TestCase):
    def test_reconciliation_does_not_demand_equal_counts(self) -> None:
        """A granularity difference is COMPLEMENTARY_SCOPE_DIFFERENCE, not a discrepancy."""
        run = make_run()
        drive(run)
        reconciliation = run.finalize()["layers"]["reconciliation_receipt"]
        self.assertNotEqual(
            reconciliation["summarized_observations"], reconciliation["exact_member_rows"]
        )
        self.assertIn("COMPLEMENTARY_SCOPE_DIFFERENCE", reconciliation["granularity_note"])

    def test_averaged_rows_are_tagged_with_their_section(self) -> None:
        run = make_run()
        drive(run)
        rows = run.finalize()["layers"]["averaged_companions"]["rows"]
        self.assertTrue(rows)
        self.assertTrue(all("section" in row for row in rows))


if __name__ == "__main__":
    unittest.main()


class SessionAssignmentGateTest(unittest.TestCase):
    """A traversal that supplies a constant session_phase must be REJECTED.

    This is the failure the D6 derivation exists to prevent and the one a field-level check
    cannot see: a constant phase is present, non-empty, correctly typed and plausible, and
    it collapses every phase stratum with a fully green suite. Only reconciliation against
    an independent derivation catches it.
    """

    @staticmethod
    def _instant(iso: str) -> int:
        from datetime import datetime, timezone
        return int(
            datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()
        ) * 1_000_000_000

    # Three instants inside one CME trade date that the exchange puts in three phases.
    SPAN = (
        "2021-10-04T13:00:00",  # PRE_SETTLEMENT
        "2021-10-04T18:29:00",  # SETTLEMENT   (14:29 ET)
        "2021-10-04T21:30:00",  # POST_CLOSE   (16:30 CT)
    )

    def _observe(self, run, *, phase_supplier, segment_supplier=None) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
            segment_of,
            trade_day,
        )
        for iso in self.SPAN:
            at = self._instant(iso)
            day = trade_day(at)
            run.note_session_assignment(
                ts_event_ns=at,
                continuity_segment=(
                    segment_supplier(at) if segment_supplier else segment_of(day)
                ),
                session_phase=phase_supplier(at),
            )

    def test_a_constant_phase_across_three_phases_is_rejected(self) -> None:
        run = make_run(session_strata=True)
        drive(run)
        self._observe(run, phase_supplier=lambda at: "RTH")
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertIn(GATE_DENOMINATORS, result["failed_gates"])

    def test_the_derived_assignment_is_accepted(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
            phase_within,
            trade_day,
        )
        run = make_run(session_strata=True)
        drive(run)
        self._observe(run, phase_supplier=lambda at: phase_within(at, trade_day(at)))
        result = run.finalize()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])

    def test_a_wrong_segment_is_rejected(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
            phase_within,
            segment_of,
            trade_day,
        )
        run = make_run(session_strata=True)
        drive(run)
        self._observe(
            run,
            phase_supplier=lambda at: phase_within(at, trade_day(at)),
            segment_supplier=lambda at: segment_of(trade_day(at)) + 1,
        )
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertIn(GATE_DENOMINATORS, result["failed_gates"])

    def test_writing_members_without_reporting_any_assignment_is_rejected(self) -> None:
        """The other way to defeat the check: never call it at all."""
        run = make_run(session_strata=True)
        drive(run)
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertIn(GATE_DENOMINATORS, result["failed_gates"])

    def test_the_reconciliation_layer_reports_the_basis(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
            phase_within,
            trade_day,
        )
        run = make_run(session_strata=True)
        drive(run)
        self._observe(run, phase_supplier=lambda at: phase_within(at, trade_day(at)))
        sessions = run.finalize()["layers"][LAYER_RECONCILIATION]["session_assignment"]
        self.assertEqual(sessions["assignments_observed"], 3)
        self.assertEqual(sessions["phase_mismatches"], 0)
        self.assertIn("CME session rule", sessions["basis"])


class RunnerMustNotReplaceFrankieTest(unittest.TestCase):
    """The first run's procedural failure: Frankie was never called and the runner stood in.

    The calculation layer produces EVIDENCE. The positive findings report is Frankie's
    output, read from a committed artifact an agent session emitted. Nothing here may author
    findings, and an evidence-only result must not present itself as a completed run.
    """

    PRINCIPAL = {
        "principal": "gpt-5.6-sol",
        "arm": "A_CLEAN",
        "role": "REAL_TIME_FRANKIE",
        "artifact_path": "forecasts/a_clean_rt_findings_20211004.json",
        "artifact_sha256": "f" * 64,
        "actual_principal_invocation": True,
        "controller_only": False,
    }

    FINDING = {
        "claim": "queue position decays fastest in the settlement window",
        "support": "group 2654677",
        "falsifier": "a settlement-window stratum with slower decay than its own pre-leg",
        "exemplars": ["2654677"],
    }

    def test_the_runner_cannot_author_findings(self) -> None:
        run = make_run()
        drive(run)
        with self.assertRaises(CalculationRunError):
            run.add_finding(
                claim="x", support="y", falsifier="z", exemplars=["e1"]
            )

    def test_evidence_without_findings_is_labelled_evidence_only(self) -> None:
        run = make_run()
        drive(run)
        result = run.finalize()
        self.assertEqual(result["completion_status"], "EVIDENCE_ONLY")
        self.assertFalse(result["layers"][LAYER_FINDINGS]["findings"])

    def test_attached_principal_findings_complete_the_run(self) -> None:
        run = make_run()
        drive(run)
        run.attach_principal_findings(execution=self.PRINCIPAL, findings=[self.FINDING])
        result = run.finalize()
        self.assertEqual(result["completion_status"], "PRINCIPAL_FINDINGS_ATTACHED")
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(
            result["layers"][LAYER_FINDINGS]["principal"]["principal"], "gpt-5.6-sol"
        )

    def test_controller_only_work_is_refused(self) -> None:
        """The exact shape of the first run: a controller produced the output."""
        run = make_run()
        drive(run)
        controller = {**self.PRINCIPAL, "controller_only": True}
        with self.assertRaises(CalculationRunError):
            run.attach_principal_findings(execution=controller, findings=[self.FINDING])

    def test_an_unproven_invocation_is_refused(self) -> None:
        run = make_run()
        drive(run)
        unproven = {**self.PRINCIPAL, "actual_principal_invocation": False}
        with self.assertRaises(CalculationRunError):
            run.attach_principal_findings(execution=unproven, findings=[self.FINDING])

    def test_findings_must_name_the_committed_artifact_they_came_from(self) -> None:
        """Proof is the file contract, not a provider receipt: no path, no attribution."""
        run = make_run()
        drive(run)
        for missing in ("artifact_path", "artifact_sha256", "principal"):
            with self.subTest(missing=missing):
                execution = {k: v for k, v in self.PRINCIPAL.items() if k != missing}
                with self.assertRaises(CalculationRunError):
                    make_run().attach_principal_findings(
                        execution=execution, findings=[self.FINDING]
                    )

    def test_a_finding_still_requires_a_falsifier_and_an_exemplar(self) -> None:
        run = make_run()
        drive(run)
        with self.assertRaises(CalculationRunError):
            run.attach_principal_findings(
                execution=self.PRINCIPAL, findings=[{**self.FINDING, "falsifier": "  "}]
            )
        with self.assertRaises(CalculationRunError):
            make_run().attach_principal_findings(
                execution=self.PRINCIPAL, findings=[{**self.FINDING, "exemplars": []}]
            )

    def test_the_not_a_model_run_gate_is_a_check_not_a_label(self) -> None:
        """It used to always return True. Findings present with no principal must FAIL."""
        run = make_run()
        drive(run)
        run._findings = [dict(self.FINDING)]  # simulate the first run's shape
        result = run.finalize()
        self.assertEqual(result["verdict"], REJECTED)
        self.assertIn(GATE_NOT_A_MODEL_RUN, result["failed_gates"])


class CompanionKeyAliasingTest(unittest.TestCase):
    """The aliaser is wired into the artifact, and it must change bytes and nothing else."""

    def _finalized(self, *, alias: bool):
        run = make_run(alias_companion_keys=alias)
        drive(run)
        return run.finalize()

    def test_the_layer_declares_its_form_even_when_plain(self):
        """A field present in only one form makes its absence ambiguous.

        Absent, a reader cannot tell a plain artifact from one written before the field
        existed - so PLAIN is stamped as positively as ALIASED.
        """
        plain = self._finalized(alias=False)["layers"][LAYER_AVERAGES]
        self.assertEqual(plain[ALIAS_FORM_KEY], FORM_PLAIN)
        self.assertEqual(plain[ALIAS_LEGEND_KEY], {})

        aliased = self._finalized(alias=True)["layers"][LAYER_AVERAGES]
        self.assertEqual(aliased[ALIAS_FORM_KEY], FORM_ALIASED)

    def test_default_is_plain_so_a_rerun_carries_no_second_change(self):
        self.assertEqual(
            make_run().finalize.__self__.alias_companion_keys, False
        )

    def test_the_two_forms_carry_identical_rows(self):
        """The whole claim. Aliasing is a renaming; decoded, the rows must be the same object."""
        plain = self._finalized(alias=False)["layers"][LAYER_AVERAGES]["rows"]
        aliased_layer = self._finalized(alias=True)["layers"][LAYER_AVERAGES]
        decoded = expand_aliases(aliased_layer["rows"], aliased_layer[ALIAS_LEGEND_KEY])
        self.assertEqual(decoded, plain)

    def test_read_averaged_rows_returns_plain_rows_from_either_form(self):
        for alias in (False, True):
            with self.subTest(alias=alias):
                result = self._finalized(alias=alias)
                rows = read_averaged_rows(result)
                self.assertTrue(all("section" in row for row in rows))

    def test_the_gates_run_on_unaliased_rows_so_the_verdict_is_unchanged(self):
        """Aliasing must not be able to change whether a run is accepted.

        The gates read `_averaged_companions()` directly, which never aliases. If that ever
        stopped being true, a gate keyed on `row["value"]` would silently see nothing and
        pass on an empty population - the exact defect class the ninth gate exists for.
        """
        plain = self._finalized(alias=False)
        aliased = self._finalized(alias=True)
        self.assertEqual(plain["verdict"], aliased["verdict"])
        self.assertEqual(plain["failed_gates"], aliased["failed_gates"])
        self.assertEqual(plain["gates"], aliased["gates"])

    def test_reconciliation_is_unchanged_by_the_form(self):
        """`summarized_observations` walks `row["value"]`, so an aliased row would read 0."""
        plain = self._finalized(alias=False)["layers"][LAYER_RECONCILIATION]
        aliased = self._finalized(alias=True)["layers"][LAYER_RECONCILIATION]
        self.assertEqual(plain, aliased)
