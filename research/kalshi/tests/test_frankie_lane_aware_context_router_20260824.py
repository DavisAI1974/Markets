from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_authority_knowledge_plane_20260824 import (  # noqa: E402
    AccessPolicy,
    AuthorityClass,
    CompletenessContract,
    KnowledgeAccessDenied,
    KnowledgeCatalogError,
    KnowledgePlane,
    SourceSpec,
    TargetRelationship,
)
from frankie_lane_aware_context_router_20260824 import (  # noqa: E402
    ComponentAvailability,
    ContextVariant,
    FrankieLaneAwareContextRouter,
    ProvisionalComponent,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FrankieLaneAwareContextRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._write(
            "knowledge/ng_brain.json",
            json.dumps(
                {
                    "meta": {"version": "s105.9"},
                    "plays": [{"id": "play-00", "call": "complete source fallback"}],
                }
            ),
        )
        self._write("s135/runtime.py", "S135_BINDING = True\n")
        self._write("frozen/findings.md", "frozen exhaustion findings")
        self._write("carry/findings.md", "authorized carryforward")
        self._write("shadow/s137.json", '{"cognitive":"candidate graph"}')
        self._write("shadow/hipporag.json", '{"retrieval":"candidate index"}')
        self._write("shadow/v4.json", '{"engineering":"candidate runtime"}')
        self._write("shadow/meta_loop_s138.json", '{"post_evidence":"candidate loop"}')
        self._write("sealed/october_step1_results.json", '{"sealed_needle":"target answer"}')
        specs = [
            SourceSpec("knowledge/ng_brain.json", AuthorityClass.CURRENT_BRAIN),
            SourceSpec("s135/runtime.py", AuthorityClass.BINDING_CURRENT),
            SourceSpec("frozen/findings.md", AuthorityClass.FROZEN_LEARNED_KNOWLEDGE),
            SourceSpec("carry/findings.md", AuthorityClass.EXTRA_AGENT_CARRYFORWARD),
            *[
                SourceSpec(
                    path,
                    AuthorityClass.PROVISIONAL_SHADOW,
                    access_policy=AccessPolicy.SHADOW_ONLY,
                )
                for path in (
                    "shadow/s137.json",
                    "shadow/hipporag.json",
                    "shadow/v4.json",
                    "shadow/meta_loop_s138.json",
                )
            ],
            SourceSpec(
                "sealed/october_step1_results.json",
                AuthorityClass.SEALED_TARGET_ANSWER,
                target_relationship=TargetRelationship.OCTOBER_STEP1_ANSWER,
                access_policy=AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE,
            ),
        ]
        contract = CompletenessContract(
            brain_path="knowledge/ng_brain.json",
            expected_play_count=1,
            s135_paths=frozenset({"s135/runtime.py"}),
            frozen_paths=frozenset({"frozen/findings.md"}),
            carryforward_paths=frozenset({"carry/findings.md"}),
        )
        self.plane = KnowledgePlane.build(
            self.root, specs, contract=contract, manifest_version="october-two-lane-v1"
        )
        self.components = (
            ProvisionalComponent(
                "shadow/s137.json", "S137_COGNITIVE", ComponentAvailability.PRE_FREEZE_AUGMENTATION
            ),
            ProvisionalComponent(
                "shadow/hipporag.json",
                "HIPPORAG_RETRIEVAL",
                ComponentAvailability.PRE_FREEZE_AUGMENTATION,
            ),
            ProvisionalComponent(
                "shadow/v4.json",
                "V4_PROVISIONAL_ENGINEERING",
                ComponentAvailability.PRE_FREEZE_AUGMENTATION,
            ),
            ProvisionalComponent(
                "shadow/meta_loop_s138.json",
                "S138_META_LOOP_POST_EVIDENCE",
                ComponentAvailability.POST_GLOBAL_FREEZE_ONLY,
            ),
        )
        self.router = FrankieLaneAwareContextRouter(self.plane, self.components)
        self.bundle = self.router.build_routes(run_id="october-run", state_prefix_hash="a" * 64)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _artifacts(seed: int) -> dict[str, str]:
        return {
            "candidate_discovery": f"{seed}" * 64,
            "helper_evidence": f"{seed + 1}" * 64,
            "frankie_reasoning": f"{seed + 2}" * 64,
            "probability_movie": f"{seed + 3}" * 64,
            "first_lock": f"{seed + 4}" * 64,
            "no_lock": f"{seed + 5}" * 64,
        }

    def test_bundle_is_exactly_control_vs_one_full_combined_shadow(self):
        self.assertEqual(
            set(self.bundle.routes),
            {ContextVariant.S135_CONTROL, ContextVariant.FULL_PROVISIONAL_COMBINED},
        )
        control = self.bundle.routes[ContextVariant.S135_CONTROL]
        combined = self.bundle.routes[ContextVariant.FULL_PROVISIONAL_COMBINED]
        self.assertEqual(control.state_prefix_hash, combined.state_prefix_hash)
        self.assertEqual(control.knowledge_manifest_hash, combined.knowledge_manifest_hash)
        self.assertEqual(control.base_corpus_hash, combined.base_corpus_hash)
        self.assertEqual(
            [(item.path, item.sha256, item.byte_length) for item in control.base_sources],
            [(item.path, item.sha256, item.byte_length) for item in combined.base_sources],
        )
        self.assertEqual(control.augmentation_sources, ())
        self.assertEqual(
            {item.component_label for item in combined.augmentation_sources},
            {"S137_COGNITIVE", "HIPPORAG_RETRIEVAL", "V4_PROVISIONAL_ENGINEERING"},
        )
        self.assertEqual(
            {item.component_label for item in combined.withheld_sources},
            {"S138_META_LOOP_POST_EVIDENCE"},
        )
        self.assertEqual(len({item.sha256 for item in combined.augmentation_sources}), 3)
        self.assertNotEqual(control.augmentation_hash, combined.augmentation_hash)
        self.assertTrue(control.complete_source_fallback)
        self.assertTrue(combined.complete_source_fallback)
        self.assertTrue(control.primary_lock_eligible)
        self.assertFalse(combined.primary_lock_eligible)

    def test_combined_augmentation_actively_serves_and_receipts_every_component(self):
        for component in self.components[:-1]:
            result = self.router.read_source(
                self.bundle, ContextVariant.FULL_PROVISIONAL_COMBINED, component.path
            )
            self.assertTrue(result.data)
        attached = [r for r in self.router.receipts if r.event == "PROVISIONAL_COMPONENT_ATTACHED"]
        self.assertEqual({r.component_label for r in attached}, {c.label for c in self.components[:-1]})
        last = self.router.receipts[-1]
        source = self.plane.entry(self.components[-2].path)
        self.assertEqual(last.variant, ContextVariant.FULL_PROVISIONAL_COMBINED.value)
        self.assertEqual(last.state_prefix_hash, "a" * 64)
        self.assertEqual(last.knowledge_manifest_hash, self.plane.manifest_hash)
        self.assertEqual(last.source_sha256, source.sha256)
        self.assertEqual(last.returned_sha256, source.sha256)
        self.assertIsNotNone(last.underlying_receipt_sequence)

    def test_primary_excludes_provisional_and_combined_preserves_complete_base_fallback(self):
        with self.assertRaisesRegex(KnowledgeAccessDenied, "PROVISIONAL_EXCLUDED_FROM_CONTROL"):
            self.router.read_source(
                self.bundle, ContextVariant.S135_CONTROL, "shadow/s137.json"
            )
        base = self.router.read_source(
            self.bundle, ContextVariant.FULL_PROVISIONAL_COMBINED, "knowledge/ng_brain.json"
        )
        self.assertIn(b"complete source fallback", base.data)
        self.assertFalse(self.router.receipts[-1].primary_lock_eligible)

    def test_context_routing_and_reads_do_not_mutate_the_brain(self):
        brain_path = self.root / "knowledge/ng_brain.json"
        before = brain_path.read_bytes()
        self.router.read_source(
            self.bundle, ContextVariant.FULL_PROVISIONAL_COMBINED, "shadow/hipporag.json"
        )
        self.router.read_source(
            self.bundle, ContextVariant.S135_CONTROL, "knowledge/ng_brain.json"
        )
        after = brain_path.read_bytes()
        self.assertEqual(after, before)
        self.assertEqual(_sha(after), self.bundle.routes[ContextVariant.S135_CONTROL].brain_sha256)

    def test_answer_wall_denies_both_lanes_until_both_artifact_sets_freeze(self):
        sealed = "sealed/october_step1_results.json"
        for variant in ContextVariant:
            with self.assertRaisesRegex(KnowledgeAccessDenied, "ANSWER_WALL_PRE_GLOBAL_FREEZE"):
                self.router.read_source(self.bundle, variant, sealed)
        with self.assertRaisesRegex(KnowledgeCatalogError, "both experiment variants"):
            self.router.freeze_global_experiment(
                self.bundle, {ContextVariant.S135_CONTROL: self._artifacts(1)}
            )
        incomplete_combined = self._artifacts(2)
        incomplete_combined.pop("no_lock")
        with self.assertRaisesRegex(KnowledgeCatalogError, "incomplete immutable artifacts"):
            self.router.freeze_global_experiment(
                self.bundle,
                {
                    ContextVariant.S135_CONTROL: self._artifacts(1),
                    ContextVariant.FULL_PROVISIONAL_COMBINED: incomplete_combined,
                },
            )
        for variant in ContextVariant:
            with self.assertRaisesRegex(KnowledgeAccessDenied, "ANSWER_WALL_PRE_GLOBAL_FREEZE"):
                self.router.read_source(self.bundle, variant, sealed)

    def test_post_evidence_is_catalogued_but_cannot_leak_into_prefreeze_context(self):
        path = "shadow/meta_loop_s138.json"
        self.assertEqual(self.plane.entry(path).authority, AuthorityClass.PROVISIONAL_SHADOW)
        with self.assertRaisesRegex(KnowledgeAccessDenied, "POST_EVIDENCE_PRE_FREEZE_WITHHELD"):
            self.router.read_source(
                self.bundle, ContextVariant.FULL_PROVISIONAL_COMBINED, path
            )
        denied = self.router.receipts[-1]
        self.assertEqual(denied.decision, "DENIED")
        self.assertIsNone(denied.returned_sha256)

    def test_complete_two_lane_freeze_is_immutable_and_only_then_opens_reconciliation(self):
        artifacts = {
            ContextVariant.S135_CONTROL: self._artifacts(1),
            ContextVariant.FULL_PROVISIONAL_COMBINED: self._artifacts(2),
        }
        freeze = self.router.freeze_global_experiment(self.bundle, artifacts)
        self.assertEqual(set(freeze.variant_artifact_hashes), set(ContextVariant))
        self.assertEqual(
            self.router.read_source(
                self.bundle,
                ContextVariant.FULL_PROVISIONAL_COMBINED,
                "shadow/meta_loop_s138.json",
            ).data,
            b'{"post_evidence":"candidate loop"}',
        )
        for variant in ContextVariant:
            with self.assertRaisesRegex(KnowledgeAccessDenied, "ANSWER_SOURCE_RECONCILIATION_ONLY"):
                self.router.read_source(self.bundle, variant, "sealed/october_step1_results.json")
        reconciled = self.router.read_reconciliation(
            self.bundle, "sealed/october_step1_results.json"
        )
        self.assertIn(b"sealed_needle", reconciled.data)
        self.assertEqual(self.router.receipts[-1].global_freeze_receipt_hash, freeze.receipt_hash)
        self.assertEqual(self.router.freeze_global_experiment(self.bundle, artifacts), freeze)
        changed = {**artifacts, ContextVariant.FULL_PROVISIONAL_COMBINED: self._artifacts(3)}
        with self.assertRaisesRegex(KnowledgeAccessDenied, "GLOBAL_EXPERIMENT_FREEZE_IMMUTABLE"):
            self.router.freeze_global_experiment(self.bundle, changed)

    def test_every_provisional_source_requires_one_explicit_unique_component(self):
        with self.assertRaisesRegex(KnowledgeCatalogError, "component coverage"):
            FrankieLaneAwareContextRouter(self.plane, self.components[:-1])
        duplicate = self.components + (
            ProvisionalComponent(
                "shadow/s137.json", "DUPLICATE", ComponentAvailability.PRE_FREEZE_AUGMENTATION
            ),
        )
        with self.assertRaisesRegex(KnowledgeCatalogError, "component coverage"):
            FrankieLaneAwareContextRouter(self.plane, duplicate)


if __name__ == "__main__":
    unittest.main()
