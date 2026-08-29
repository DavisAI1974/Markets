"""Tests for sections 5 and 6: artifact layers and fail-closed acceptance gates."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    ACCEPTED,
    GATE_COVERAGE,
    GATE_DENOMINATORS,
    GATE_DETERMINISM,
    GATE_ISOLATION,
    GATE_NOT_A_MODEL_RUN,
    REJECTED,
    REQUIRED_GATES,
    REQUIRED_LAYERS,
    CalculationRunError,
    LAYER_FINDINGS,
    LAYER_RECONCILIATION,
    NativeCalculationRun,
    RunIdentity,
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
        arm="A_CLEAN",
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

    def test_all_eight_gates_are_evaluated(self) -> None:
        run = make_run()
        drive(run)
        gates = {g["gate"] for g in run.finalize()["gates"]}
        self.assertEqual(gates, set(REQUIRED_GATES))

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

    def test_a_finding_is_provisional_and_carries_its_exemplars(self) -> None:
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
        self.assertEqual(layer["findings"][0]["status"], "PROVISIONAL")
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
