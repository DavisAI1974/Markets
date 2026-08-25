from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import inspect
import json
from pathlib import Path
import tempfile
from types import MappingProxyType, SimpleNamespace
import unittest
from contextlib import redirect_stdout

from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    LedgerKind,
)
from research.kalshi import ng_exhaustion_frankie_fullstack_october_20260824 as fullstack


MANIFEST = Path(
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"
)


class FullStackOctoberContractTest(unittest.TestCase):
    def test_causal_second_writer_appends_thousands_in_one_validated_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "causal-seconds.jsonl"
            writer = fullstack.CausalSecondJsonlWriter.create(
                path,
                run_id="linear-causal-test",
                flush_interval_records=257,
            )
            for sequence in range(5_000):
                prefix = hashlib.sha256(f"prefix:{sequence}".encode()).hexdigest()
                state = hashlib.sha256(f"state:{sequence}".encode()).hexdigest()
                binding = CausalPrefixBinding(
                    run_id="linear-causal-test",
                    causal_cutoff=float(sequence),
                    event_known_by=float(sequence),
                    causal_prefix_hash=prefix,
                    state_prefix_hash=state,
                    knowledge_manifest_hash="a" * 64,
                ).validate()
                writer.append_second(
                    binding=binding,
                    state={"source_second": sequence, "stream_hash": prefix},
                    delta={"prior_stream_hash": "0" * 64, "stream_hash": prefix},
                    integrity={"accepted": True},
                    decision={
                        "type": "NO_LOCK" if sequence % 2 == 0 else "PROSPECTIVE_MARK",
                        "owner": "CAUSAL_OBSERVATION_ONLY",
                        "primary_lock": False,
                    },
                )

            receipt = writer.close()
            validation = fullstack.validate_causal_second_jsonl(
                path, run_id="linear-causal-test"
            )

            self.assertEqual(receipt["record_count"], 5_000)
            self.assertEqual(receipt["periodic_fsync_count"], 5_000 // 257)
            self.assertTrue(receipt["final_fsync_completed"])
            self.assertEqual(validation["record_count"], 5_000)
            self.assertEqual(validation["head_hash"], receipt["head_hash"])
            with path.open(encoding="utf-8") as handle:
                self.assertEqual(sum(1 for _ in handle), 5_000)

    def test_causal_second_chain_validation_rejects_tampered_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "causal-seconds.jsonl"
            writer = fullstack.CausalSecondJsonlWriter.create(
                path, run_id="tamper-test", flush_interval_records=8
            )
            binding = CausalPrefixBinding(
                run_id="tamper-test",
                causal_cutoff=1.0,
                event_known_by=1.0,
                causal_prefix_hash="1" * 64,
                state_prefix_hash="2" * 64,
                knowledge_manifest_hash="3" * 64,
            ).validate()
            writer.append_second(
                binding=binding,
                state={"source_second": 1},
                delta={"prior_stream_hash": "0" * 64},
                integrity={"accepted": True},
                decision={
                    "type": "NO_LOCK",
                    "owner": "CAUSAL_OBSERVATION_ONLY",
                    "primary_lock": False,
                },
            )
            writer.close()
            row = json.loads(path.read_text(encoding="utf-8"))
            row["content"]["state"]["source_second"] = 2
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with self.assertRaises(fullstack.FullStackOctoberError):
                fullstack.validate_causal_second_jsonl(path, run_id="tamper-test")

    def test_selects_exact_predecessor_and_all_october_objects(self) -> None:
        manifest = json.loads(MANIFEST.read_text())

        roster = fullstack.select_october_source_roster(manifest)

        self.assertEqual(len(roster), 27)
        self.assertTrue(roster[0].key.endswith("glbx-mdp3-20210930.mbo.dbn.zst"))
        self.assertEqual(roster[0].purpose, "PREDECESSOR_BOOTSTRAP")
        self.assertEqual({item.segment for item in roster[1:]}, {"20211001_20211101"})
        self.assertEqual(len({item.key for item in roster}), len(roster))
        self.assertTrue(all(item.purpose == "OCTOBER_CAUSAL_STREAM" for item in roster[1:]))

    def test_config_is_full_month_sol_only_and_requires_fresh_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "out"
            config = fullstack.FullStackOctoberConfig(
                run_id="october-fullstack-test",
                manifest_path=MANIFEST,
                source_root=Path(temporary),
                output_root=root,
            ).validate()

            self.assertEqual(config.model, "gpt-5.6-sol")
            self.assertEqual(
                config.target_start,
                int(datetime(2021, 10, 1, tzinfo=timezone.utc).timestamp()),
            )
            self.assertEqual(
                config.target_end,
                int(datetime(2021, 11, 1, tzinfo=timezone.utc).timestamp()),
            )
            self.assertEqual(config.answer_wall_mode, "SEALED_UNTIL_PRIMARY_FREEZE")

            root.mkdir()
            (root / "existing").write_text("immutable")
            with self.assertRaises(fullstack.FullStackOctoberError):
                config.validate()

    def test_rejects_manifest_identity_drift(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        manifest["manifest_sha256"] = "0" * 64

        with self.assertRaises(fullstack.FullStackOctoberError):
            fullstack.select_october_source_roster(manifest)

    def test_staged_roster_is_byte_and_sha_verified_without_key_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = {"predecessor.dbn.zst": b"predecessor", "target.dbn.zst": b"target"}
            roster = []
            for name, data in payloads.items():
                (root / name).write_bytes(data)
                roster.append(
                    fullstack.SourceObject(
                        date="20210930" if name.startswith("pre") else "20211001",
                        segment="segment",
                        key=f"canonical/path/{name}",
                        sha256=hashlib.sha256(data).hexdigest(),
                        bytes=len(data),
                        bucket="bucket",
                        purpose="PREDECESSOR_BOOTSTRAP" if name.startswith("pre") else "OCTOBER_CAUSAL_STREAM",
                    )
                )

            verified = fullstack.verify_staged_source_roster(tuple(roster), root)
            self.assertEqual(verified, (root / "predecessor.dbn.zst", root / "target.dbn.zst"))

            (root / "target.dbn.zst").write_bytes(b"drift")
            with self.assertRaises(fullstack.FullStackOctoberError):
                fullstack.verify_staged_source_roster(tuple(roster), root)

    def test_launch_event_sink_emits_workflow_gate_names_for_both_lanes(self) -> None:
        sink = fullstack.LaunchJsonEventSink()
        stream = io.StringIO()
        with redirect_stdout(stream):
            sink.emit_launch(
                "PAIRED_PREFIX_ACCEPTED",
                control_provider_response_ids=[f"ctrl-{index}" for index in range(5)],
                combined_provider_response_ids=[f"combined-{index}" for index in range(5)],
                identical_prefix_proof_hash="a" * 64,
            )
        row = json.loads(stream.getvalue())
        self.assertEqual(row["event"], "PAIRED_PREFIX_ACCEPTED")
        self.assertEqual(len(row["control_provider_response_ids"]), 5)
        self.assertEqual(len(row["combined_provider_response_ids"]), 5)
        self.assertEqual(len(set(row["control_provider_response_ids"] + row["combined_provider_response_ids"])), 10)

    def test_json_projection_handles_immutable_causal_mappings(self) -> None:
        @dataclass(frozen=True)
        class ImmutableFixture:
            state: object

        source = MappingProxyType({"nested": MappingProxyType({"value": 7})})
        self.assertEqual(
            fullstack._jsonable(ImmutableFixture(source)),
            {"state": {"nested": {"value": 7}}},
        )

    def test_cli_requires_exact_manifest_source_output_and_run_identity(self) -> None:
        args = fullstack.parse_args(
            [
                "--manifest",
                str(MANIFEST),
                "--source-root",
                "/tmp/raw",
                "--output-root",
                "/tmp/out",
                "--run-id",
                "paired-october",
            ]
        )
        self.assertEqual(args.manifest, MANIFEST)
        self.assertEqual(args.source_root, Path("/tmp/raw"))
        self.assertEqual(args.output_root, Path("/tmp/out"))
        self.assertEqual(args.run_id, "paired-october")

    def test_provisional_paths_map_to_seven_active_components_and_deferred_meta(self) -> None:
        paths = {
            "frankie_s137_cognitive_runtime.py": "S137_COGNITIVE_RUNTIME",
            "frankie_hipporag_p0_retrieval.py": "HIPPORAG_RETRIEVAL",
            "frankie_temporal_graph_p0_adapter.py": "TEMPORAL_GRAPH",
            "frankie_lats_p0_search.py": "LATS_BOUNDED_SEARCH",
            "frankie_cognitive_p0_loops.py": "WORKING_MEMORY",
            "frankie_progress_compress_p0.py": "PROGRESS_COMPRESSION",
            "NG_EXHAUSTION_V4_PROVISIONAL_READINESS_20260821.json": "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
            "frankie_meta_loop_s138.py": "META_LOOP",
        }
        self.assertEqual(
            {fullstack.paired_component_id(f"research/kalshi/{path}") for path in paths},
            set(paths.values()),
        )
        for path, expected in paths.items():
            self.assertEqual(fullstack.paired_component_id(f"research/kalshi/{path}"), expected)

    def test_production_knowledge_plane_and_router_share_exact_enum_identity(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        specs = fullstack.production_source_specs(repo_root)
        plane = fullstack.KnowledgePlane.build(
            repo_root,
            specs,
            contract=fullstack.october_full_stack_completeness_contract(),
            manifest_version="fullstack-runner-construction-test",
        )
        router = fullstack.FrankieLaneAwareContextRouter(
            plane, fullstack.production_provisional_components(plane)
        )
        bundle = router.build_routes(run_id="construction-test", state_prefix_hash="0" * 64)
        combined = bundle.routes[fullstack.ContextVariant.FULL_PROVISIONAL_COMBINED]
        self.assertEqual(len(specs), 150)
        self.assertEqual(len(combined.base_sources), 107)
        self.assertEqual(len(combined.augmentation_sources), 20)
        self.assertEqual(len(combined.withheld_sources), 2)
        excerpts = fullstack._base_knowledge(router, bundle)
        self.assertEqual(len(excerpts), len(combined.base_sources))
        self.assertEqual(
            {item.source_id for item in excerpts},
            {item.source_id for item in combined.base_sources},
        )
        self.assertTrue(
            all(
                0 < item.byte_end - item.byte_start <= fullstack.BASE_SOURCE_EXCERPT_BYTES
                for item in excerpts
            )
        )

    def test_paired_launch_event_contains_workflow_proof_and_first_lane_receipts(self) -> None:
        def invocation(label: str):
            return SimpleNamespace(accepted_response=SimpleNamespace(provider_response_id=label))

        binding = SimpleNamespace(
            causal_prefix_hash="1" * 64,
            state_prefix_hash="2" * 64,
            knowledge_manifest_hash="3" * 64,
        )
        paired = SimpleNamespace(
            control=SimpleNamespace(
                invocation_receipts=tuple(invocation(f"control-{i}") for i in range(5)),
                final_ledger_hash="4" * 64,
            ),
            combined=SimpleNamespace(
                invocation_receipts=tuple(invocation(f"combined-{i}") for i in range(5)),
                final_ledger_hash="5" * 64,
            ),
            identical_prefix_proof=SimpleNamespace(proof_hash="6" * 64),
            component_receipt_hashes={
                component: "7" * 64 for component in fullstack.PAIRED_COMPONENTS
            },
            control_lock_authority="S135_PRIMARY",
            combined_lock_authority="SHADOW_ONLY",
            answer_revealed=False,
        )

        class FakeLedger:
            def __init__(self, path: str):
                self.path = Path(path)
                self._records = tuple(
                    SimpleNamespace(
                        binding=SimpleNamespace(causal_prefix_hash=binding.causal_prefix_hash),
                        kind=kind,
                        record_hash=str(index + 8) * 64,
                    )
                    for index, kind in enumerate(
                        (LedgerKind.HELPER_EVIDENCE, LedgerKind.REASONING, LedgerKind.PROBABILITY)
                    )
                )

            def snapshot(self):
                return self._records

        event = fullstack.make_paired_launch_event(
            binding=binding,
            paired=paired,
            control_ledger=FakeLedger("control.jsonl"),
            combined_ledger=FakeLedger("combined.jsonl"),
        )
        self.assertEqual(event["lanes"], ["S135_CONTROL", "FULL_PROVISIONAL_COMBINED"])
        self.assertEqual(len(event["control_provider_response_ids"]), 5)
        self.assertEqual(len(event["combined_provider_response_ids"]), 5)
        self.assertEqual(len(event["active_provisional_components"]), 7)
        self.assertEqual(event["deferred_meta_loop"]["status"], "DEFERRED_NOT_YET_LAWFUL")
        self.assertEqual(
            set(event["control_ledger"]["first_receipt_hashes"]),
            {"helper_evidence", "frankie_reasoning", "probability_movie"},
        )
        self.assertEqual(len(event["receipt_hash"]), 64)

    def test_production_entrypoint_uses_paired_runtime_and_never_reveals_step1(self) -> None:
        source = inspect.getsource(fullstack.run_full_october)
        for token in (
            "production_source_specs",
            "KnowledgePlane.build",
            "FrankieLaneAwareContextRouter",
            "seal_semantic_crosswalk",
            "ContinuousV4CausalStreamBuilder",
            "ProtectedProspectiveWeakeningMarker",
            "replay_dbn_files_to_causal_seconds",
            "DurableJsonlLedger.create",
            "PairedLaneOrchestrator",
            "freeze_global_experiment",
        ):
            self.assertIn(token, source)
        self.assertNotIn("read_reconciliation", source)
        self.assertNotIn("reveal_opportunity_outcome", source)

    def test_marked_prefix_executes_combined_pipeline_before_paired_provider_calls(self) -> None:
        component_source = inspect.getsource(fullstack._component_receipts)
        run_source = inspect.getsource(fullstack.run_full_october)
        self.assertIn("execute_combined_provisional_pipeline", component_source)
        self.assertIn("source_contexts=grouped", component_source)
        self.assertIn("causal_state=causal_state", component_source)
        self.assertLess(
            run_source.index("component_receipts=_component_receipts"),
            run_source.index("answer_revealed=False"),
        )


if __name__ == "__main__":
    unittest.main()
