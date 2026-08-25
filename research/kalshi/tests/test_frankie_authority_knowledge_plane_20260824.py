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
    EvidencePolarity,
    KnowledgeAccessDenied,
    KnowledgeCatalogError,
    KnowledgePlane,
    RetrievalContext,
    RetrievalLane,
    SourceSpec,
    TargetRelationship,
    october_full_stack_completeness_contract,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FrankieAuthorityKnowledgePlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        plays = []
        for index in range(90):
            plays.append(
                {
                    "id": f"play-{index:02d}",
                    "call": f"complete play body {index}",
                    "support": "MECHANISM_VERIFIED" if index == 0 else "PROVISIONAL",
                    "falsifier": "fails if the contrary case repeats" if index == 0 else "",
                    "instances": (
                        [
                            {"supports_or_contradicts": "supports", "fact": "queue held"},
                            {"supports_or_contradicts": "contradicts", "fact": "queue broke"},
                        ]
                        if index == 0
                        else []
                    ),
                }
            )
        self._write("knowledge/ng_brain.json", json.dumps({"meta": {"version": "s105.9"}, "plays": plays}))
        self._write("frozen/phase1.json", '{"family":"D","case":"negative retained"}')
        self._write("frozen/phase2.md", "pair triplet stopped-chain contradictory context")
        self._write("frozen/phase2-old.md", "superseded frozen source")
        self._write("carry/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md", "gap diagnosis only")
        self._write("archive/v3_d1_extratrees_results.json", '{"D1 ExtraTrees":0.999}')
        self._write(
            "generated/NG_EXHAUSTION_D1_D5_PREDICTABILITY_ALL_AGENT_RESULTS_20260819.json",
            '{"model":"ExtraTrees","stage":"D1","value":0.999}',
        )
        self._write("shadow/frankie_s137.json", '{"candidate":"HippoRAG"}')
        self._write("sealed/october_step1_crosswalk_results.json", '{"sealed_needle":"target"}')

        self.specs = [
            SourceSpec("knowledge/ng_brain.json", AuthorityClass.CURRENT_BRAIN),
            SourceSpec("frozen/phase1.json", AuthorityClass.FROZEN_LEARNED_KNOWLEDGE),
            SourceSpec(
                "frozen/phase2.md",
                AuthorityClass.FROZEN_LEARNED_KNOWLEDGE,
                supersedes=("frozen/phase2-old.md",),
            ),
            SourceSpec("frozen/phase2-old.md", AuthorityClass.FROZEN_LEARNED_KNOWLEDGE),
            SourceSpec(
                "carry/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md",
                AuthorityClass.EXTRA_AGENT_CARRYFORWARD,
            ),
            # Deliberately misclassified: the mechanical V3/D1 ExtraTrees guard must still deny it.
            SourceSpec("archive/v3_d1_extratrees_results.json", AuthorityClass.BINDING_CURRENT),
            SourceSpec(
                "generated/NG_EXHAUSTION_D1_D5_PREDICTABILITY_ALL_AGENT_RESULTS_20260819.json",
                AuthorityClass.BINDING_CURRENT,
            ),
            SourceSpec(
                "shadow/frankie_s137.json",
                AuthorityClass.PROVISIONAL_SHADOW,
                access_policy=AccessPolicy.SHADOW_ONLY,
            ),
            SourceSpec(
                "sealed/october_step1_crosswalk_results.json",
                AuthorityClass.SEALED_TARGET_ANSWER,
                target_relationship=TargetRelationship.OCTOBER_STEP1_ANSWER,
                access_policy=AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE,
            ),
        ]
        self.contract = CompletenessContract(
            brain_path="knowledge/ng_brain.json",
            brain_version="s105.9",
            expected_play_count=90,
            frozen_paths=frozenset({"frozen/phase1.json", "frozen/phase2.md"}),
        )
        self.plane = KnowledgePlane.build(
            self.root,
            self.specs,
            contract=self.contract,
            manifest_version="october-v1",
            coverage_chunk_bytes=17,
        )
        self.primary = self.plane.context(run_id="run-october", state_hash="a" * 64)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_catalog_is_content_addressed_and_receipts_lossless_coverage(self):
        entry = self.plane.entry("frozen/phase2.md")
        self.assertEqual(entry.byte_length, len((self.root / entry.path).read_bytes()))
        self.assertEqual(entry.sha256, _sha((self.root / entry.path).read_bytes()))
        self.assertEqual(entry.knowledge_manifest_version, "october-v1")
        self.assertEqual(entry.supersedes, ("frozen/phase2-old.md",))
        self.assertEqual(self.plane.entry("frozen/phase2-old.md").superseded_by, ("frozen/phase2.md",))
        self.assertTrue(entry.source_id.startswith("sha256:"))
        self.assertEqual(entry.coverage[0].start, 0)
        self.assertEqual(entry.coverage[-1].end_exclusive, entry.byte_length)
        self.assertEqual(
            sum(chunk.end_exclusive - chunk.start for chunk in entry.coverage), entry.byte_length
        )
        self.assertTrue(all(chunk.sha256 for chunk in entry.coverage))

    def test_completeness_contract_requires_all_90_plays_and_frozen_corpus(self):
        missing = CompletenessContract(
            brain_path="knowledge/ng_brain.json",
            brain_version="s105.9",
            expected_play_count=90,
            frozen_paths=frozenset({"frozen/phase1.json", "frozen/not-catalogued.md"}),
        )
        with self.assertRaisesRegex(KnowledgeCatalogError, "frozen corpus"):
            KnowledgePlane.build(self.root, self.specs, contract=missing, manifest_version="bad")

        brain = json.loads((self.root / "knowledge/ng_brain.json").read_text(encoding="utf-8"))
        brain["plays"].pop()
        self._write("knowledge/ng_brain.json", json.dumps(brain))
        with self.assertRaisesRegex(KnowledgeCatalogError, "90 complete plays"):
            KnowledgePlane.build(self.root, self.specs, contract=self.contract, manifest_version="bad")

    def test_production_contract_names_s135_and_the_frozen_exhaustion_corpus(self):
        contract = october_full_stack_completeness_contract()
        self.assertEqual(contract.expected_play_count, 90)
        self.assertEqual(contract.brain_version, "s105.9")
        self.assertIn("research/kalshi/frankie_s135_current_runtime.py", contract.s135_paths)
        self.assertIn(
            "research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json",
            contract.frozen_paths,
        )
        self.assertIn(
            "research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md",
            contract.frozen_paths,
        )
        self.assertIn(
            "research/NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md",
            contract.frozen_paths,
        )
        self.assertEqual(len(contract.carryforward_paths), 3)

    def test_typed_list_search_read_play_and_evidence_retrieval(self):
        listed = self.plane.list_sources(self.primary)
        paths = {entry.path for entry in listed}
        self.assertIn("knowledge/ng_brain.json", paths)
        self.assertIn("frozen/phase2.md", paths)
        # Supersession is explicit routing metadata, not silent destruction of exact sources.
        self.assertIn("frozen/phase2-old.md", paths)
        self.assertEqual(
            self.plane.read(self.primary, "frozen/phase2-old.md").data,
            b"superseded frozen source",
        )
        self.assertNotIn("shadow/frankie_s137.json", paths)
        self.assertNotIn("sealed/october_step1_crosswalk_results.json", paths)

        hits = self.plane.search(self.primary, "stopped-chain")
        self.assertEqual([(hit.path, hit.match) for hit in hits], [("frozen/phase2.md", b"stopped-chain")])
        read = self.plane.read(self.primary, "frozen/phase2.md", start=5, end_exclusive=16)
        self.assertEqual(read.data, b"triplet sto")
        self.assertEqual(read.receipt.run_id, "run-october")
        self.assertEqual(read.receipt.state_hash, "a" * 64)
        self.assertEqual(read.receipt.knowledge_manifest_hash, self.plane.manifest_hash)
        self.assertEqual(read.receipt.byte_range, (5, 16))

        play = self.plane.read_play(self.primary, "play-00")
        self.assertEqual(play.body["call"], "complete play body 0")
        supporting = self.plane.retrieve_play_evidence(
            self.primary, "play-00", EvidencePolarity.SUPPORTING
        )
        contradictory = self.plane.retrieve_play_evidence(
            self.primary, "play-00", EvidencePolarity.CONTRADICTORY
        )
        self.assertTrue(any(item.body.get("fact") == "queue held" for item in supporting))
        self.assertTrue(any(item.body.get("fact") == "queue broke" for item in contradictory))
        self.assertTrue(any("falsifier" in item.body for item in contradictory))

    def test_forbidden_v3_and_d1_extratrees_are_denied_despite_misclassification(self):
        with self.assertRaisesRegex(KnowledgeAccessDenied, "FORBIDDEN_V3_D1_EXTRATREES"):
            self.plane.read(self.primary, "archive/v3_d1_extratrees_results.json")
        with self.assertRaisesRegex(KnowledgeAccessDenied, "FORBIDDEN_V3_D1_EXTRATREES"):
            self.plane.read(
                self.primary,
                "generated/NG_EXHAUSTION_D1_D5_PREDICTABILITY_ALL_AGENT_RESULTS_20260819.json",
            )
        denied = self.plane.receipts[-1]
        self.assertEqual(denied.decision, "DENIED")
        self.assertFalse(denied.primary_lock_eligible)

    def test_step1_answer_wall_denies_all_retrieval_before_primary_freeze(self):
        sealed = "sealed/october_step1_crosswalk_results.json"
        with self.assertRaisesRegex(KnowledgeAccessDenied, "ANSWER_WALL_PRE_FREEZE"):
            self.plane.read(self.primary, sealed)
        self.assertEqual(self.plane.search(self.primary, "sealed_needle"), ())
        self.assertNotIn(sealed, {entry.path for entry in self.plane.list_sources(self.primary)})
        self.assertTrue(
            any(
                receipt.decision == "DENIED" and receipt.reason == "ANSWER_WALL_PRE_FREEZE"
                for receipt in self.plane.receipts
            )
        )

    def test_step1_opens_only_for_identity_bound_post_freeze_reconciliation(self):
        artifacts = {
            "candidate_discovery": "1" * 64,
            "helper_evidence": "2" * 64,
            "frankie_reasoning": "3" * 64,
            "probability_movie": "4" * 64,
            "first_lock": "5" * 64,
            "no_lock": "6" * 64,
        }
        freeze = self.plane.freeze_primary_outputs(self.primary, artifacts)
        with self.assertRaisesRegex(KnowledgeAccessDenied, "RECONCILIATION_LANE_REQUIRED"):
            self.plane.read(self.primary, "sealed/october_step1_crosswalk_results.json")
        reconcile = self.plane.context(
            run_id="run-october", state_hash="a" * 64, lane=RetrievalLane.POST_FREEZE_RECONCILIATION
        )
        result = self.plane.read(reconcile, "sealed/october_step1_crosswalk_results.json")
        self.assertIn(b"sealed_needle", result.data)
        self.assertEqual(result.receipt.primary_freeze_receipt_hash, freeze.receipt_hash)

        wrong_state = RetrievalContext(
            run_id="run-october",
            state_hash="b" * 64,
            knowledge_manifest_hash=self.plane.manifest_hash,
            lane=RetrievalLane.POST_FREEZE_RECONCILIATION,
        )
        with self.assertRaisesRegex(KnowledgeAccessDenied, "FREEZE_IDENTITY_MISMATCH"):
            self.plane.read(wrong_state, "sealed/october_step1_crosswalk_results.json")

    def test_answer_wall_cannot_freeze_without_frankie_reasoning(self):
        incomplete = {
            "candidate_discovery": "1" * 64,
            "helper_evidence": "2" * 64,
            "probability_movie": "3" * 64,
            "first_lock": "4" * 64,
            "no_lock": "5" * 64,
        }
        with self.assertRaisesRegex(KnowledgeCatalogError, "frankie_reasoning"):
            self.plane.freeze_primary_outputs(self.primary, incomplete)

    def test_provisional_sources_are_shadow_only_and_never_primary_lock_eligible(self):
        with self.assertRaisesRegex(KnowledgeAccessDenied, "PROVISIONAL_SHADOW_ONLY"):
            self.plane.read(self.primary, "shadow/frankie_s137.json")
        shadow = self.plane.context(
            run_id="run-october", state_hash="a" * 64, lane=RetrievalLane.SHADOW
        )
        result = self.plane.read(shadow, "shadow/frankie_s137.json")
        self.assertIn(b"HippoRAG", result.data)
        self.assertTrue(result.receipt.shadow_only)
        self.assertFalse(result.receipt.primary_lock_eligible)

    def test_receipts_reject_a_manifest_identity_mismatch(self):
        forged = RetrievalContext(
            run_id="run-october",
            state_hash="a" * 64,
            knowledge_manifest_hash="f" * 64,
            lane=RetrievalLane.PRIMARY,
        )
        with self.assertRaisesRegex(KnowledgeAccessDenied, "MANIFEST_IDENTITY_MISMATCH"):
            self.plane.read(forged, "frozen/phase1.json")
        receipt = self.plane.receipts[-1]
        self.assertEqual(receipt.run_id, "run-october")
        self.assertEqual(receipt.state_hash, "a" * 64)
        self.assertEqual(receipt.knowledge_manifest_hash, "f" * 64)
        with self.assertRaisesRegex(KnowledgeAccessDenied, "MANIFEST_IDENTITY_MISMATCH"):
            self.plane.search(forged, "negative")

    def test_play_reads_fail_closed_if_the_catalogued_brain_bytes_change(self):
        brain_path = self.root / "knowledge/ng_brain.json"
        brain_path.write_bytes(brain_path.read_bytes() + b" ")
        with self.assertRaisesRegex(KnowledgeAccessDenied, "SOURCE_INTEGRITY_MISMATCH"):
            self.plane.read_play(self.primary, "play-00")


if __name__ == "__main__":
    unittest.main()
