from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    KnowledgeRegistryError,
    bind_principal_knowledge_use,
    build_context_bundle,
    build_model_visible_context,
    canonical_hash,
    load_and_validate_manifest,
)


class NativeFrankieKnowledgeRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "mission.md").write_text("mission\n", encoding="utf-8")
        (self.root / "capsule.md").write_text("capsule\n", encoding="utf-8")
        (self.root / "evidence.md").write_text("evidence\n", encoding="utf-8")
        artifacts = []
        for artifact_id, path, load_mode in (
            ("mission", "mission.md", "ALWAYS_LOAD"),
            ("capsule", "capsule.md", "ALWAYS_LOAD"),
            ("evidence", "evidence.md", "RETRIEVAL"),
        ):
            raw = (self.root / path).read_bytes()
            artifacts.append(
                {
                    "id": artifact_id,
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "kind": "MARKDOWN",
                    "authority": "POSITIVE_NATIVE_KNOWLEDGE",
                    "arms": ["A_CLEAN"],
                    "roles": ["REAL_TIME_FRANKIE"],
                    "load_mode": load_mode,
                }
            )
        body = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_KNOWLEDGE_MANIFEST_V1",
            "version": "test-v1",
            "artifacts": artifacts,
            "external_bindings": [],
            "profiles": {
                "RT_A_CLEAN": {
                    "arm": "A_CLEAN",
                    "role": "REAL_TIME_FRANKIE",
                    "always_load": ["mission", "capsule"],
                    "retrieval_catalog": ["evidence"],
                    "external_bindings": [],
                }
            },
            "manifest_hash": "",
        }
        body["manifest_hash"] = canonical_hash(body, omit="manifest_hash")
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_text(json.dumps(body), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_builds_deterministic_always_load_bundle_and_inventory(self) -> None:
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        bundle, receipt = build_context_bundle(manifest, "RT_A_CLEAN", self.root)
        self.assertIn(b"mission\n", bundle)
        self.assertIn(b"capsule\n", bundle)
        self.assertNotIn(b"evidence\n", bundle)
        self.assertEqual(
            [row["id"] for row in receipt["loaded_artifacts"]],
            ["mission", "capsule"],
        )
        self.assertEqual(
            [row["id"] for row in receipt["retrieval_catalog"]], ["evidence"]
        )
        self.assertEqual(receipt["unregistered_required_artifacts"], [])
        self.assertEqual(receipt["missing_required_artifacts"], [])

    def test_fails_closed_when_registered_bytes_drift(self) -> None:
        (self.root / "capsule.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(KnowledgeRegistryError, "SHA-256 drift"):
            load_and_validate_manifest(self.manifest_path, self.root)

    def test_fails_closed_when_profile_omits_always_load_artifact(self) -> None:
        body = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        body["profiles"]["RT_A_CLEAN"]["always_load"] = ["mission"]
        body["manifest_hash"] = canonical_hash(body, omit="manifest_hash")
        self.manifest_path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(KnowledgeRegistryError, "unrouted ALWAYS_LOAD"):
            load_and_validate_manifest(self.manifest_path, self.root)

    def test_fails_closed_on_cross_arm_profile_route(self) -> None:
        body = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        body["profiles"]["RT_A_CLEAN"]["arm"] = "A_MEMORY"
        body["manifest_hash"] = canonical_hash(body, omit="manifest_hash")
        self.manifest_path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(KnowledgeRegistryError, "arm route violation"):
            load_and_validate_manifest(self.manifest_path, self.root)

    def _principal_binding(self, context_receipt: dict[str, object]) -> dict[str, object]:
        return {
            "profile_id": context_receipt["profile_id"],
            "arm": context_receipt["arm"],
            "role": context_receipt["role"],
            "manifest_hash": context_receipt["manifest_hash"],
            "context_bundle_sha256": context_receipt["context_bundle_sha256"],
            "retrieval_dispositions": {"evidence": "INSPECTED"},
        }

    def test_binds_model_visible_context_and_complete_retrieval_inventory(self) -> None:
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        context, pre_call = build_model_visible_context(
            manifest, "RT_A_CLEAN", self.root, external_proofs={}
        )
        self.assertIn(b'"id":"evidence"', context)
        self.assertNotIn(b"evidence\n", context)
        serialized = b'{"principal_context":' + context + b"}"
        receipt = bind_principal_knowledge_use(
            pre_call,
            model_visible_context=context,
            serialized_principal_input=serialized,
            response_binding=self._principal_binding(pre_call["context_receipt"]),
        )
        self.assertEqual(receipt["retrieval_inventory"][0]["disposition"], "INSPECTED")
        self.assertEqual(receipt["missing_retrieval_dispositions"], [])

    def test_rejects_one_byte_model_context_omission(self) -> None:
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        context, pre_call = build_model_visible_context(
            manifest, "RT_A_CLEAN", self.root, external_proofs={}
        )
        with self.assertRaisesRegex(KnowledgeRegistryError, "exact model-visible context"):
            bind_principal_knowledge_use(
                pre_call,
                model_visible_context=context,
                serialized_principal_input=context[:-1],
                response_binding=self._principal_binding(pre_call["context_receipt"]),
            )

    def test_rejects_wrong_response_profile(self) -> None:
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        context, pre_call = build_model_visible_context(
            manifest, "RT_A_CLEAN", self.root, external_proofs={}
        )
        binding = self._principal_binding(pre_call["context_receipt"])
        binding["profile_id"] = "WRONG"
        with self.assertRaisesRegex(KnowledgeRegistryError, "response binding mismatch"):
            bind_principal_knowledge_use(
                pre_call,
                model_visible_context=context,
                serialized_principal_input=b"prefix" + context,
                response_binding=binding,
            )

    def test_rejects_incomplete_retrieval_disposition_inventory(self) -> None:
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        context, pre_call = build_model_visible_context(
            manifest, "RT_A_CLEAN", self.root, external_proofs={}
        )
        binding = self._principal_binding(pre_call["context_receipt"])
        binding["retrieval_dispositions"] = {}
        with self.assertRaisesRegex(KnowledgeRegistryError, "retrieval disposition inventory"):
            bind_principal_knowledge_use(
                pre_call,
                model_visible_context=context,
                serialized_principal_input=b"prefix" + context,
                response_binding=binding,
            )

    def test_rejects_external_proof_mismatch(self) -> None:
        body = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        body["external_bindings"] = [
            {
                "id": "prior_memory",
                "description": "verified prior lessons",
                "sha256": "e" * 64,
                "arms": ["A_CLEAN"],
                "roles": ["REAL_TIME_FRANKIE"],
                "required_proof_sha256": "f" * 64,
            }
        ]
        body["profiles"]["RT_A_CLEAN"]["external_bindings"] = ["prior_memory"]
        body["manifest_hash"] = canonical_hash(body, omit="manifest_hash")
        self.manifest_path.write_text(json.dumps(body), encoding="utf-8")
        manifest = load_and_validate_manifest(self.manifest_path, self.root)
        with self.assertRaisesRegex(KnowledgeRegistryError, "external-proof hash mismatch"):
            build_model_visible_context(
                manifest,
                "RT_A_CLEAN",
                self.root,
                external_proofs={
                    "prior_memory": {"sha256": "e" * 64, "proof_sha256": "0" * 64}
                },
            )


if __name__ == "__main__":
    unittest.main()
