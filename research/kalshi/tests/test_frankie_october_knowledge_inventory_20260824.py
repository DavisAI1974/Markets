#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AccessPolicy,
    AuthorityClass,
    TargetRelationship,
)
from research.kalshi.frankie_october_knowledge_inventory_20260824 import (
    PROVISIONAL_SOURCE_DISPOSITIONS,
    ProvisionalSourceDisposition,
    production_source_specs,
    sealed_step1_external_descriptors,
)


ROOT = Path(__file__).resolve().parents[3]


class ProductionKnowledgeInventoryTests(unittest.TestCase):
    def test_curated_inventory_is_exhaustively_classified(self) -> None:
        specs = production_source_specs(ROOT)
        by_path = {item.path: item for item in specs}

        self.assertEqual(len(specs), 161)
        self.assertEqual(len(by_path), len(specs))
        self.assertTrue(all((ROOT / path).is_file() for path in by_path))
        for path in (
            "research/kalshi/FRANKIE_ROLE_CONTEXT_PROFILES_20260824.json",
            "research/kalshi/FRANKIE_STEP1_STRUCTURAL_CENSUS_METHOD_V1_20260824.md",
            "research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json",
            "research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json",
        ):
            self.assertEqual(by_path[path].access_policy, AccessPolicy.SERVE)
        self.assertEqual(
            {item.authority for item in specs},
            set(AuthorityClass),
        )
        for path in (
            "research/kalshi/frankie_cognitive_p0_loops.py",
            "research/kalshi/frankie_progress_compress_p0.py",
            "research/kalshi/frankie_p0_registry.py",
        ):
            self.assertEqual(by_path[path].authority, AuthorityClass.PROVISIONAL_SHADOW)
            self.assertEqual(by_path[path].access_policy, AccessPolicy.SHADOW_ONLY)

    def test_current_brain_shadow_answer_and_forbidden_substitute_are_gated(self) -> None:
        by_path = {item.path: item for item in production_source_specs(ROOT)}

        brain = by_path["research/kalshi/knowledge/ng_brain.json"]
        self.assertEqual(brain.authority, AuthorityClass.CURRENT_BRAIN)
        self.assertEqual(brain.access_policy, AccessPolicy.SERVE)

        shadow = by_path["research/kalshi/frankie_hipporag_p0_retrieval.py"]
        self.assertEqual(shadow.authority, AuthorityClass.PROVISIONAL_SHADOW)
        self.assertEqual(shadow.access_policy, AccessPolicy.SHADOW_ONLY)

        answer = by_path["research/ng_exhaustion_step1_october_shards_20260824.py"]
        self.assertEqual(answer.authority, AuthorityClass.SEALED_TARGET_ANSWER)
        self.assertEqual(answer.access_policy, AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE)
        self.assertEqual(answer.target_relationship, TargetRelationship.OCTOBER_STEP1_ANSWER)

        forbidden = by_path["research/kalshi/frankie_bounded_3mo_parallel.py"]
        self.assertEqual(forbidden.authority, AuthorityClass.ARCHIVE_NOT_SERVABLE)
        self.assertEqual(forbidden.access_policy, AccessPolicy.DENY)

    def test_corrected_sources_record_supersession(self) -> None:
        by_path = {item.path: item for item in production_source_specs(ROOT)}
        corrected = by_path[
            "research/kalshi/NG_EXHAUSTION_FRANKIE_FULL_STACK_OCTOBER_NEXT_CHAT_HANDOFF_20260824.md"
        ]
        self.assertIn(
            "research/kalshi/NG_EXHAUSTION_OCTOBER_SHARDED_HANDOFF_20260824.md",
            corrected.supersedes,
        )

    def test_step1_runtime_manifest_expands_exact_external_descriptors_without_fetching(self) -> None:
        descriptors = sealed_step1_external_descriptors(ROOT)

        self.assertEqual(len(descriptors), 13)
        self.assertEqual(
            {item.object_kind for item in descriptors},
            {"RESULT_PREFIX", "RECEIPT", "RECONCILIATION", "GOVERNED_FINAL_OUTPUT"},
        )
        self.assertIn(
            "step1:LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz",
            {item.descriptor_id for item in descriptors},
        )
        self.assertIn(
            "step1:V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz",
            {item.descriptor_id for item in descriptors},
        )
        self.assertTrue(all(item.authority is AuthorityClass.SEALED_TARGET_ANSWER for item in descriptors))
        self.assertTrue(all(item.access_policy is AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE for item in descriptors))
        self.assertTrue(all(item.target_relationship is TargetRelationship.OCTOBER_STEP1_ANSWER for item in descriptors))
        self.assertTrue(all(item.external_uri.startswith("s3://") for item in descriptors))
        self.assertTrue(all(len(item.descriptor_sha256) == 64 for item in descriptors))
        self.assertTrue(all(item.content_accessed is False for item in descriptors))
        self.assertTrue(all(item.local_path is None for item in descriptors))

    def test_every_provisional_source_has_one_explicit_disposition(self) -> None:
        specs = production_source_specs(ROOT)
        provisional = {
            item.path for item in specs if item.authority is AuthorityClass.PROVISIONAL_SHADOW
        }

        self.assertEqual(set(PROVISIONAL_SOURCE_DISPOSITIONS), provisional)
        self.assertEqual(len(PROVISIONAL_SOURCE_DISPOSITIONS), 22)
        self.assertEqual(
            {
                row.disposition
                for row in PROVISIONAL_SOURCE_DISPOSITIONS.values()
            },
            {
                ProvisionalSourceDisposition.EXECUTABLE_MODULE_BINDING,
                ProvisionalSourceDisposition.CONTEXT_ONLY_GOVERNANCE,
                ProvisionalSourceDisposition.DEFERRED_POST_EVIDENCE,
            },
        )
        for path, row in PROVISIONAL_SOURCE_DISPOSITIONS.items():
            if row.disposition is ProvisionalSourceDisposition.EXECUTABLE_MODULE_BINDING:
                self.assertTrue(path.endswith(".py"))
                self.assertTrue(row.module_name)
                self.assertTrue(row.required_symbol)
            elif row.disposition is ProvisionalSourceDisposition.CONTEXT_ONLY_GOVERNANCE:
                self.assertFalse(path.endswith(".py"))
                self.assertIsNone(row.module_name)
                self.assertIsNone(row.required_symbol)
            else:
                self.assertEqual(row.component_id, "META_LOOP")


if __name__ == "__main__":
    unittest.main()
