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
    production_source_specs,
)


ROOT = Path(__file__).resolve().parents[3]


class ProductionKnowledgeInventoryTests(unittest.TestCase):
    def test_curated_inventory_is_exhaustively_classified(self) -> None:
        specs = production_source_specs(ROOT)
        by_path = {item.path: item for item in specs}

        self.assertEqual(len(specs), 150)
        self.assertEqual(len(by_path), len(specs))
        self.assertTrue(all((ROOT / path).is_file() for path in by_path))
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


if __name__ == "__main__":
    unittest.main()
