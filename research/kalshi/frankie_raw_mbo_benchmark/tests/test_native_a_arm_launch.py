"""T2/T3/T5: the launch path gates, traverses, checkpoints and finalizes.

Everything under test here was built before this module existed and none of it was on a path
that runs: the execution gate was referenced by its own test alone, the checkpointer was
imported by a driver no workflow dispatched, and both launch workflows staged a packet and
stopped. An unreferenced gate is not a gate, and a checkpointer with no path is not a save
point - so these tests assert the CALL, not the capability.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (
    CheckpointError,
    build_checkpoint,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.corrected_a_arm_execution_gate_20260828 import (
    CorrectedExecutionGateError,
    SURFACE_IDS,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import ACCEPTED
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import read_averaged_rows
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    IngestionLayerGateError,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_session import NS_PER_SECOND

SOURCE = "s3://bucket/nymex/ng_mbo_5y_v0/native/20211004/part-0.dbn.zst"
F_LAST = 128


def at(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()) * NS_PER_SECOND


def slice_records(groups: int = 40):
    """A bounded native record stream: four-action groups, forward only, in tape order."""
    base = at("2021-10-04T13:00:00")
    plan = (("T", "A"), ("F", "A"), ("C", "A"), ("A", "B"))
    seq = 0
    for group_index in range(groups):
        for offset, (action, side) in enumerate(plan):
            event_ns = base + (group_index * 4 + offset) * NS_PER_SECOND
            yield {
                "instrument_id": 42,
                "publisher_id": 1,
                "channel_id": 0,
                "order_id": 900 + group_index * 4 + offset,
                "action": action,
                "side": side,
                "price": 3_500_000_000,
                "size": 5,
                "flags": F_LAST if offset == len(plan) - 1 else 0,
                "sequence": seq,
                "ts_event": event_ns,
                "ts_recv": event_ns + 150_000,
                "ts_in_delta": 0,
                "source_dbn_object": SOURCE,
                "source_dbn_sha256": "0" * 64,
                "raw_symbol": "NGX1",
            }
            seq += 1


class PreTraversalGateTest(unittest.TestCase):
    """T2: the gate now runs on the launch path, on real evidence, before any data is read."""

    def test_both_arms_pass_all_three_gates(self):
        for arm, required in (("A_CLEAN", 75), ("A_MEMORY", 77)):
            with self.subTest(arm=arm):
                gates = launcher.run_pre_traversal_gates(arm=arm, run_id=f"gate-{arm}")
                self.assertEqual(gates["pre_call_layer_gate"]["registered_layer_count"], 99)
                self.assertEqual(gates["pre_call_layer_gate"]["required_input_count"], required)
                self.assertTrue(gates["pre_call_layer_gate"]["answer_wall_sealed"])
                self.assertEqual(gates["rt_surface_gate"]["surface_count"], len(SURFACE_IDS))
                self.assertTrue(gates["rt_surface_gate"]["step1_sealed"])

    def test_a_memory_sees_more_required_input_than_a_clean(self):
        """The asymmetry IS the experiment (D2), so it must be visible in the gate receipts."""
        clean = launcher.run_pre_traversal_gates(arm="A_CLEAN", run_id="g1")
        memory = launcher.run_pre_traversal_gates(arm="A_MEMORY", run_id="g2")
        self.assertGreater(
            memory["pre_call_layer_gate"]["required_input_count"],
            clean["pre_call_layer_gate"]["required_input_count"],
        )

    def test_every_sealed_surface_is_sealed_in_both_objects(self):
        """The answer wall has to hold in the registry receipt AND the surface inventory."""
        registry = load_registry()
        sealed = {
            entry["layer_id"]
            for group in registry["groups"]
            if group["policy"] == "SEALED_FOR_A_SCOPE"
            for entry in group["entries"]
        }
        self.assertEqual(len(sealed), 9)
        inventory = launcher.build_rt_surface_inventory(arm="A_CLEAN", registry=registry)
        rows = {row["surface_id"]: row for row in inventory["surfaces"]}
        for surface_id in sealed:
            with self.subTest(surface_id=surface_id):
                row = rows[surface_id]
                self.assertEqual(row["route"], "SEALED")
                self.assertEqual(row["availability"], "SEALED")
                self.assertFalse(row["model_visible"])
                self.assertIsNone(row["evidence_receipt_sha256"])

    def test_a_tampered_inventory_is_refused(self):
        """Proves the gate is doing work rather than accepting whatever it is handed."""
        registry = load_registry()
        inventory = launcher.build_rt_surface_inventory(arm="A_CLEAN", registry=registry)
        for row in inventory["surfaces"]:
            if row["route"] == "SEALED":
                row["availability"] = "AVAILABLE"
                row["model_visible"] = True
                break
        with self.assertRaises(CorrectedExecutionGateError):
            launcher.execution_gate.validate_rt_surface_inventory(inventory, arm="A_CLEAN")

    def test_opening_a_sealed_layer_is_refused_even_with_the_hash_recomputed(self):
        """The dangerous tamper is the answer wall, and re-hashing must not get past it.

        The first version of this test flipped `layers[0]` to AVAILABLE and asserted a
        refusal. It did not raise - `layers[0]` is the mission, which is AVAILABLE already,
        so the mutation changed nothing and the test would have passed against a gate that
        checked nothing at all. Mutating a SEALED layer and recomputing `receipt_sha256`
        tests the POLICY rather than the hash, which is the check worth having.
        """
        registry = load_registry()
        receipt = launcher.build_pre_call_receipt(
            arm="A_CLEAN", run_id="tamper", registry=registry
        )
        sealed = next(row for row in receipt["layers"] if row["status"] == "SEALED")
        sealed["status"] = "AVAILABLE"
        sealed["model_visible"] = True
        receipt["receipt_sha256"] = launcher.registry_gate.canonical_hash(
            receipt, omit="receipt_sha256"
        )
        with self.assertRaises(IngestionLayerGateError):
            launcher.registry_gate.validate_pre_call_receipt(receipt, registry=registry)

    def test_evidence_hashes_are_computed_from_bytes_not_asserted(self):
        """A receipt cannot be produced for a source that is not there."""
        with self.assertRaises(launcher.LaunchError):
            launcher.evidence_receipt_sha256(
                ["research/kalshi/this_file_does_not_exist.md"], repo_root=launcher.REPO_ROOT
            )

    def test_the_two_external_identities_are_the_pinned_ones(self):
        """Section 9: do not re-derive, do not guess. The substitution is explicit."""
        self.assertEqual(
            launcher.EXTERNAL_SOURCE_IDENTITIES["external:a_memory_prior_lessons_package"],
            "b487acfbbea8ac8a82f42ceb555e8334057e4004740af91b9127cd2ba71e1cf8",
        )
        self.assertEqual(
            launcher.EXTERNAL_SOURCE_IDENTITIES["external:a_memory_prior_lessons_package_proof"],
            "d54c61915c0d85c8b2630eb79d5e1b8911481c80883c56d75ba815fcfab20c05",
        )


class LaunchSliceTest(unittest.TestCase):
    """T3 and T5: a bounded slice runs the whole path and the eight gates pass."""

    GROUPS = 40

    def _launch(self, out_dir: Path, **kwargs):
        manifest = {"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689}
        params = dict(
            arm="A_CLEAN",
            run_id="slice-1",
            sources=[],
            source_manifest=manifest,
            out_dir=out_dir,
            code_commit="cafebabe",
            limit_records=self.GROUPS * 4,
            checkpoint_every_records=50,
            cadence_groups=10,
            records=slice_records(self.GROUPS),
        )
        params.update(kwargs)
        return launcher.launch(**params)

    def test_the_slice_is_accepted_with_no_failed_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(result["failed_gates"], [])

    def test_the_launched_result_hashes_to_itself_as_written(self):
        """F-feed-6, found by the feeding persona on the REAL Sunday result: the launcher added
        ledger_retention, gates, evidence_identity and slice AFTER the runner's finalize had
        hashed the result, so every launcher-written result declared a result_hash that did
        not recompute and native_staging.read_back refused it ("declares d2ab3feb... and
        recomputes to ceaca066..."). The tests never saw it because they build results through
        the runner, never the launcher. The launched result must hash to itself; the runner's
        own hash is kept beside it under its own name (D60: nothing dropped)."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        recomputed = canonical_hash({k: v for k, v in result.items() if k != "result_hash"})
        self.assertEqual(result["result_hash"], recomputed)
        self.assertRegex(result["runner_result_hash"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(result["runner_result_hash"], result["result_hash"])
        for key in ("ledger_retention", "gates", "evidence_identity", "slice"):
            self.assertIn(key, result, key)

    def test_the_gate_receipts_travel_with_the_result(self):
        """A calculation that cannot say what gated it is not evidence anyone can audit."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        self.assertEqual(
            sorted(result["gates"]),
            ["pre_call_layer_gate", "registry_gate", "rt_surface_gate"],
        )
        self.assertTrue(result["gates"]["rt_surface_gate"]["step1_sealed"])

    def test_a_save_point_is_written_during_the_slice(self):
        """T3's acceptance. Before this the checkpointer had no path that executes."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self._launch(out)
            written = sorted((out / "checkpoints").glob("checkpoint-*.json"))
            self.assertGreater(len(written), 0)
            body = json.loads(written[-1].read_text(encoding="utf-8"))
        self.assertGreater(result["traversal"]["save_points"], 0)
        self.assertEqual(body["phase"], "RT_NATIVE_TRAVERSAL")
        self.assertFalse(body["event_group_open"], "a save point mid-group is not resumable")

    def test_a_memory_slice_reaches_a_canonical_memory_assisted_checkpoint(self):
        """A_MEMORY is the arm id; MEMORY_ASSISTED is the checkpoint-mode token."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self._launch(out, arm="A_MEMORY", run_id="slice-a-memory")
            written = sorted((out / "checkpoints").glob("checkpoint-*.json"))
            body = json.loads(written[-1].read_text(encoding="utf-8"))
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(body["memory_mode"], "MEMORY_ASSISTED")

    def test_checkpoint_contract_still_refuses_an_unknown_memory_mode_by_name(self):
        with self.assertRaisesRegex(CheckpointError, "unknown benchmark memory mode"):
            build_checkpoint(
                run_id="unknown-mode",
                controller="A_CHATGPT",
                memory_mode="MEMORY",
                sequence=0,
                source_manifest_hash="e" * 64,
                completed_mbo_records=0,
                total_mbo_records=1,
                event_group_open=False,
                adapter_state_hash="a" * 64,
                controller_state_hash=None,
                previous_checkpoint_hash=None,
                phase="RT_NATIVE_TRAVERSAL",
                locked=False,
            )

    def test_every_section_the_traversal_feeds_reports_a_real_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        fed = result["traversal"]["sections_fed"]
        self.assertEqual(fed["4.14_recurrence_sequences"], self.GROUPS)
        self.assertEqual(fed["4.8_absorption_runways"], self.GROUPS)
        self.assertGreater(fed["4.9_ladder_transitions"], 0)
        self.assertGreater(fed["4.13_lineage_nodes_observed"], 0)

    def test_the_run_stages_spawn_requests_and_calls_nothing(self):
        """The corrected procedure: at a cutoff the traversal STAGES, it never invokes."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self._launch(out)
            staged = sorted((out / "spawn_requests").glob("*.json"))
            self.assertGreater(len(staged), 0)
            request = json.loads(staged[0].read_text(encoding="utf-8"))
        self.assertEqual(len(staged), result["traversal"]["invocation_cutoff_count"])
        self.assertEqual(request["role"], "REAL_TIME_FRANKIE")

    def test_evidence_only_until_a_principal_artifact_is_attached(self):
        """The calculation layer produces evidence; findings are Frankie's and are absent."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        self.assertEqual(result["completion_status"], "EVIDENCE_ONLY")

    def test_a_bounded_slice_declares_itself_against_the_full_roster(self):
        """A slice reporting the roster's record count would make coverage meaningless."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._launch(Path(tmp))
        self.assertTrue(result["slice"]["is_bounded_slice"])
        self.assertEqual(result["slice"]["records_requested"], self.GROUPS * 4)
        self.assertEqual(result["slice"]["roster_total_mbo_records"], 5_667_689)
        self.assertEqual(result["slice"]["record_source"], "SUPPLIED_ITERABLE")


if __name__ == "__main__":
    unittest.main()


class SliceBoundaryTest(unittest.TestCase):
    """The defect that made the first real canary REJECT, pinned.

    Run 33300298768: 50,000 records, 40,241 groups, every fed section reporting real data -
    and `failed_gates: ["exact_once_coverage"]`. That gate requires
    `coverage.records_seen == identity.total_mbo_records`, and the left side counts records
    assigned to CLOSED groups while the identity carried the records FED. A slice cutting
    mid-group leaves its tail consumed but never assigned, so the two can never agree. The
    gate was right; the launcher was wrong.
    """

    F_LAST_BIT = 128

    def test_a_slice_does_not_stop_before_its_limit(self):
        self.assertFalse(launcher.slice_ends_here(emitted=10, limit=50, flags=self.F_LAST_BIT))

    def test_a_slice_does_not_stop_mid_group_even_at_the_limit(self):
        """The whole bug in one assertion."""
        self.assertFalse(launcher.slice_ends_here(emitted=50, limit=50, flags=0))
        self.assertFalse(launcher.slice_ends_here(emitted=999, limit=50, flags=0))

    def test_a_slice_stops_on_the_first_closing_group_at_or_after_the_limit(self):
        self.assertTrue(launcher.slice_ends_here(emitted=50, limit=50, flags=self.F_LAST_BIT))
        self.assertTrue(launcher.slice_ends_here(emitted=51, limit=50, flags=self.F_LAST_BIT))

    def test_an_unbounded_run_never_stops_early(self):
        self.assertFalse(launcher.slice_ends_here(emitted=10**9, limit=None, flags=self.F_LAST_BIT))

    def test_a_missing_or_unusable_flag_is_not_read_as_a_group_close(self):
        """A closing group is a flag that is SET, never one that is absent."""
        for flags in (None, 0, "", 1, 64):
            with self.subTest(flags=flags):
                self.assertFalse(launcher.slice_ends_here(emitted=50, limit=50, flags=flags))


class AliasCompanionKeysThroughTheLaunchPathTest(unittest.TestCase):
    """The flag must survive the real launch path, not just the runner in isolation.

    S119's own dominant finding was a correct calculator nothing ever called, and its own
    recorded mistake was a finalize wired into the wrong loop whose unit tests passed
    because they called the calculator directly. So this exercises `launch()`.
    """

    GROUPS = 40

    def _launch(self, out_dir: Path, *, alias: bool):
        return launcher.launch(
            arm="A_CLEAN",
            run_id=f"alias-{alias}",
            sources=[],
            source_manifest={"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689},
            out_dir=out_dir,
            code_commit="cafebabe",
            limit_records=self.GROUPS * 4,
            checkpoint_every_records=50,
            cadence_groups=10,
            records=slice_records(self.GROUPS),
            alias_companion_keys=alias,
        )

    def test_both_forms_decode_to_the_same_rows_and_the_same_verdict(self):
        with tempfile.TemporaryDirectory() as raw:
            plain = self._launch(Path(raw) / "plain", alias=False)
            aliased = self._launch(Path(raw) / "aliased", alias=True)
        self.assertEqual(plain["verdict"], aliased["verdict"])
        self.assertEqual(plain["failed_gates"], aliased["failed_gates"])
        self.assertEqual(read_averaged_rows(plain), read_averaged_rows(aliased))

    def test_the_aliased_layer_is_smaller_on_the_wire(self):
        """If it is not smaller it is doing nothing, and the flag is a lie."""
        with tempfile.TemporaryDirectory() as raw:
            plain = self._launch(Path(raw) / "plain", alias=False)
            aliased = self._launch(Path(raw) / "aliased", alias=True)

        def wire(result):
            return len(json.dumps(
                result["layers"]["averaged_companions"]["rows"],
                separators=(",", ":"),
                sort_keys=True,
            ))

        self.assertLess(wire(aliased), wire(plain))


class ChangePointDefaultCliS122Test(unittest.TestCase):
    @staticmethod
    def _base_args():
        return [
            "--arm", "A_MEMORY", "--run-id", "task-b", "--code-commit", "cafebabe",
            "--source", "source.dbn.zst", "--source-manifest", "manifest.json",
            "--out-dir", "out",
        ]

    def test_launch_function_defaults_change_points_on(self):
        import inspect
        self.assertIs(inspect.signature(launcher.launch).parameters["emit_change_points"].default, True)

    def test_cli_no_flag_keeps_change_points_on(self):
        args = launcher.parse_args(self._base_args())
        self.assertIs(args.emit_change_points, True)

    def test_cli_flag_is_an_explicit_opt_out(self):
        args = launcher.parse_args(self._base_args() + ["--no-change-points"])
        self.assertIs(args.emit_change_points, False)
