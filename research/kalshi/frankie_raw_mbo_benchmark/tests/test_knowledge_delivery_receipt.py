"""The knowledge delivery receipt, produced FROM the existing pipeline, consumed by the crosswalk.

F-22 slice 3. `build_context_bundle` -> `build_model_visible_context` (the existing, tested
pipeline in native_frankie_knowledge_registry) run for arm A_MEMORY / role REAL_TIME_FRANKIE
over the committed manifest, translated into the per-layer FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1
that native_layer_crosswalk consumes: every applicable knowledge layer DELIVERED with its files
and hashes from the registry's source_paths. The read gate is the EXISTING
`bind_principal_knowledge_use`; `validate_knowledge_use` is the artifact's door to it.

No number here is a spec: layer sets and artifact sets are read off the registry and the
manifest at test time.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    PRECALL_SCHEMA,
    USE_SCHEMA,
    KnowledgeRegistryError,
    load_and_validate_manifest,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_hash,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    A_MEMORY_SEED_PATH,
    BINDING_DOCUMENT,
    KNOWLEDGE_BUNDLE_FILENAME,
    KNOWLEDGE_INPUT_POLICIES,
    KNOWLEDGE_RECEIPT_FILENAME,
    KNOWLEDGE_RECEIPT_SCHEMA,
    KNOWLEDGE_USE_SCHEMA,
    MANIFEST_ARTIFACT,
    MANIFEST_PATH,
    REPO_ROOT,
    SPEC_PATH,
    KnowledgeDelivery,
    KnowledgeDeliveryError,
    build_knowledge_delivery,
    complete_knowledge_use,
    render_knowledge_block,
    serialized_principal_input,
    validate_knowledge_use,
    validate_knowledge_use_files,
    write_knowledge_delivery,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    INPUT_POLICIES,
    crosswalk,
)

ARM = "A_MEMORY"
ROLE = "REAL_TIME_FRANKIE"
#: D34 markers, spelled so the pre-commit grep for local paths stays mechanically clean.
LOCAL_PATH_MARKERS = ("/" + "tmp/", "scratch" + "pad")


def sha256_of(relative: str) -> str:
    return hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


def applicable_knowledge_layers(registry: dict, arm: str) -> dict[str, dict]:
    return {
        entry["layer_id"]: {"group": group, "entry": entry}
        for group in registry["groups"]
        if group["policy"] in KNOWLEDGE_INPUT_POLICIES and arm in group["arms"]
        for entry in group["entries"]
    }


class BuildKnowledgeDeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.delivery = build_knowledge_delivery(arm=ARM, role=ROLE)
        cls.receipt = cls.delivery.receipt
        cls.rows = {row["layer_id"]: row for row in cls.receipt["layers"]}
        cls.manifest = load_and_validate_manifest(REPO_ROOT / MANIFEST_PATH, REPO_ROOT)

    def test_the_receipt_is_the_schema_the_crosswalk_consumes_and_hashes_to_itself(self) -> None:
        self.assertIsInstance(self.delivery, KnowledgeDelivery)
        self.assertEqual(self.receipt["schema"], KNOWLEDGE_RECEIPT_SCHEMA)
        self.assertEqual(self.receipt["schema"], "FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1")
        self.assertEqual(self.receipt["receipt_sha256"], canonical_hash(self.receipt, omit="receipt_sha256"))
        self.assertEqual(self.receipt["arm"], ARM)
        self.assertEqual(self.receipt["role"], ROLE)
        self.assertEqual(self.receipt["registry_sha256"], self.registry["registry_sha256"])
        self.assertEqual(self.receipt["manifest_hash"], self.manifest["manifest_hash"])

    def test_the_profile_is_derived_from_arm_and_role_never_typed(self) -> None:
        expected = [pid for pid, p in self.manifest["profiles"].items() if p["arm"] == ARM and p["role"] == ROLE]
        self.assertEqual([self.receipt["profile_id"]], expected)
        self.assertEqual(self.delivery.pre_call["profile_id"], self.receipt["profile_id"])

    def test_it_is_the_existing_pipeline_context_receipt_and_pre_call_are_bound(self) -> None:
        pre_call = self.delivery.pre_call
        self.assertEqual(pre_call["schema"], PRECALL_SCHEMA)
        self.assertEqual(pre_call["pre_call_receipt_hash"], canonical_hash(pre_call, omit="pre_call_receipt_hash"))
        self.assertEqual(self.receipt["pre_call_receipt_hash"], pre_call["pre_call_receipt_hash"])
        self.assertEqual(self.receipt["context_receipt_hash"], pre_call["context_receipt"]["receipt_hash"])
        self.assertEqual(self.receipt["context_bundle_sha256"], pre_call["context_receipt"]["context_bundle_sha256"])
        self.assertEqual(
            hashlib.sha256(self.delivery.model_visible_context).hexdigest(), pre_call["model_visible_context_sha256"]
        )
        self.assertEqual(self.receipt["model_visible_context_sha256"], pre_call["model_visible_context_sha256"])
        self.assertEqual(self.receipt["pre_call"], pre_call, "the receipt carries the pre-call receipt whole")

    def test_the_receipt_covers_exactly_the_applicable_knowledge_layers(self) -> None:
        expected = applicable_knowledge_layers(self.registry, ARM)
        self.assertEqual(set(self.rows), set(expected))
        for layer_id, binding in expected.items():
            with self.subTest(layer=layer_id):
                self.assertEqual(self.rows[layer_id]["group_id"], binding["group"]["group_id"])
                self.assertEqual(self.rows[layer_id]["policy"], binding["group"]["policy"])
        for row in self.receipt["layers"]:
            self.assertIn(row["policy"], KNOWLEDGE_INPUT_POLICIES)

    def test_every_applicable_knowledge_layer_is_delivered_with_its_files_and_hashes(self) -> None:
        expected = applicable_knowledge_layers(self.registry, ARM)
        for layer_id, binding in expected.items():
            row = self.rows[layer_id]
            with self.subTest(layer=layer_id):
                self.assertEqual(row["status"], "DELIVERED", row.get("missing"))
                self.assertEqual(row["missing"], [])
                self.assertEqual([f["path"] for f in row["files"]], list(binding["entry"]["source_paths"]))
                for file in row["files"]:
                    self.assertEqual(file["sha256"], sha256_of(file["path"]))
                    self.assertEqual(file["bytes"], (REPO_ROOT / file["path"]).stat().st_size)
                    self.assertIn(file["delivery"], (MANIFEST_ARTIFACT, BINDING_DOCUMENT))

    def test_manifest_artifacts_are_delivered_by_the_manifest_and_the_two_binding_documents_by_hash(self) -> None:
        by_path = {row["path"]: row for row in self.manifest["artifacts"]}
        for row in self.receipt["layers"]:
            for file in row["files"]:
                with self.subTest(layer=row["layer_id"], path=file["path"]):
                    if file["path"] in (MANIFEST_PATH, SPEC_PATH):
                        self.assertEqual(file["delivery"], BINDING_DOCUMENT)
                        self.assertIsNone(file["artifact_id"])
                    else:
                        self.assertEqual(file["delivery"], MANIFEST_ARTIFACT)
                        self.assertEqual(file["artifact_id"], by_path[file["path"]]["id"])
                        self.assertEqual(file["sha256"], by_path[file["path"]]["sha256"])
                        self.assertIn(file["load_mode"], ("ALWAYS_LOAD", "RETRIEVAL"))
        self.assertEqual(self.receipt["manifest_file_sha256"], sha256_of(MANIFEST_PATH))
        self.assertEqual(self.receipt["spec_file_sha256"], sha256_of(SPEC_PATH))

    def test_the_seed_is_delivered_inline_as_memory_for_the_overlay_layers(self) -> None:
        for layer_id in ("a_memory_prior_lessons_package", "a_memory_prior_package_proof"):
            with self.subTest(layer=layer_id):
                files = self.rows[layer_id]["files"]
                self.assertEqual([f["path"] for f in files], [A_MEMORY_SEED_PATH])
                self.assertEqual(files[0]["load_mode"], "ALWAYS_LOAD")
        self.assertIn(b"FRANKIE_A_MEMORY_SEED_V1", self.delivery.model_visible_context)

    def test_the_delivered_artifact_set_is_the_profiles_whole_set_in_profile_order(self) -> None:
        profile = self.manifest["profiles"][self.receipt["profile_id"]]
        self.assertEqual(
            [a["id"] for a in self.receipt["artifacts"]], profile["always_load"] + profile["retrieval_catalog"]
        )
        for artifact in self.receipt["artifacts"]:
            with self.subTest(artifact=artifact["id"]):
                self.assertEqual(artifact["sha256"], sha256_of(artifact["path"]))

    def test_totals_are_derived_from_the_rows(self) -> None:
        totals = self.receipt["totals"]
        self.assertEqual(totals["layers"], len(self.receipt["layers"]))
        self.assertEqual(totals["delivered"], sum(1 for r in self.receipt["layers"] if r["status"] == "DELIVERED"))
        self.assertEqual(totals["not_delivered"], sum(1 for r in self.receipt["layers"] if r["status"] != "DELIVERED"))
        self.assertEqual(totals["artifacts"], len(self.receipt["artifacts"]))
        self.assertEqual(totals["files"], sum(len(r["files"]) for r in self.receipt["layers"]))

    def test_the_crosswalk_delivers_static_inputs_but_declares_the_seed_self_proof(self) -> None:
        """A delivered file is not independent proof when subject and proof bind the same bytes."""
        body = crosswalk(self.registry, arm=ARM, knowledge_receipt=self.receipt)
        rows = {row["layer_id"]: row for row in body["layers"]}
        static = [
            row for row in body["layers"]
            if row["arm_applicable"] and row["policy"] in KNOWLEDGE_INPUT_POLICIES
        ]
        self.assertTrue(static)
        for row in static:
            with self.subTest(layer=row["layer_id"]):
                if row["layer_id"] == "a_memory_prior_package_proof":
                    self.assertEqual(row["status"], "DEGENERATE_PROOF_SAME_AS_SUBJECT")
                    self.assertIn("bind the same file", row["evidence"]["detail"])
                else:
                    self.assertEqual(row["status"], "DELIVERED")
                self.assertEqual(row["evidence"]["kind"], "KNOWLEDGE_RECEIPT")
                self.assertEqual(row["evidence"]["receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertEqual(body["totals"]["degenerate_proof_same_as_subject"], 1)
        self.assertEqual(rows["a_clean_promoted_positive_capsule"]["status"], "NOT_APPLICABLE")
        self.assertEqual(body["knowledge_receipt_sha256"], self.receipt["receipt_sha256"])
        # Stream inputs are untouched by a knowledge receipt: still not delivered without a run.
        self.assertNotEqual(rows["fifo_queues"]["status"], "DELIVERED")
        self.assertTrue(any(r["policy"] in INPUT_POLICIES for r in body["layers"]))

    def test_a_manifest_whose_artifact_bytes_drifted_is_refused(self) -> None:
        drifted = json.loads(json.dumps(self.manifest))
        drifted["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(KnowledgeDeliveryError, "sha256"):
            build_knowledge_delivery(arm=ARM, role=ROLE, manifest=drifted)

    def test_an_arm_and_role_with_no_profile_is_refused(self) -> None:
        with self.assertRaisesRegex(KnowledgeDeliveryError, "profile"):
            build_knowledge_delivery(arm=ARM, role="NO_SUCH_ROLE")

    def test_write_puts_the_bundle_pre_call_and_receipt_beside_a_prompt_and_names_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            written = write_knowledge_delivery(self.delivery, out)
            self.assertEqual(set(written), {"bundle", "receipt", "pre_call"})
            self.assertEqual(written["bundle"].name, KNOWLEDGE_BUNDLE_FILENAME)
            self.assertEqual(written["receipt"].name, KNOWLEDGE_RECEIPT_FILENAME)
            self.assertEqual(written["bundle"].read_bytes(), self.delivery.model_visible_context)
            body = json.loads(written["receipt"].read_text(encoding="utf-8"))
            self.assertEqual(body["receipt_sha256"], self.receipt["receipt_sha256"])
            pre_call = json.loads(written["pre_call"].read_text(encoding="utf-8"))
            self.assertEqual(pre_call["pre_call_receipt_hash"], self.delivery.pre_call["pre_call_receipt_hash"])


class RenderKnowledgeBlockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = build_knowledge_delivery(arm=ARM, role=ROLE)
        cls.text = render_knowledge_block(cls.delivery.receipt)

    def test_the_block_names_every_delivered_file_with_its_sha256_and_the_receipt_hash(self) -> None:
        receipt = self.delivery.receipt
        self.assertIn(receipt["receipt_sha256"], self.text)
        self.assertIn(KNOWLEDGE_RECEIPT_SCHEMA, self.text)
        for artifact in receipt["artifacts"]:
            with self.subTest(artifact=artifact["id"]):
                self.assertIn(artifact["path"], self.text)
                self.assertIn(artifact["sha256"], self.text)
        for row in receipt["layers"]:
            with self.subTest(layer=row["layer_id"]):
                self.assertIn(row["layer_id"], self.text)
                for file in row["files"]:
                    self.assertIn(file["sha256"], self.text)

    def test_the_block_names_the_bundle_file_and_its_hash_and_the_disposition_rule(self) -> None:
        receipt = self.delivery.receipt
        self.assertIn(KNOWLEDGE_BUNDLE_FILENAME, self.text)
        self.assertIn(receipt["model_visible_context_sha256"], self.text)
        self.assertIn("INSPECTED", self.text)
        self.assertIn("UNINSPECTED", self.text)
        self.assertIn("knowledge_use", self.text)
        self.assertIn("knowledge_receipt_sha256", self.text)
        self.assertIn("UNVERIFIED", self.text)
        for marker in LOCAL_PATH_MARKERS:
            self.assertNotIn(marker, self.text)


class ValidateKnowledgeUseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = build_knowledge_delivery(arm=ARM, role=ROLE)
        cls.receipt = cls.delivery.receipt
        cls.prompt = b"# prompt\n" + render_knowledge_block(cls.receipt).encode("utf-8")
        cls.serialized = serialized_principal_input(cls.prompt, cls.delivery.model_visible_context)

    def _use(self, **overrides) -> dict:
        use = complete_knowledge_use(self.receipt, disposition="INSPECTED", reason="read in full")
        use.update(overrides)
        return use

    def _validate(self, use: dict, *, serialized: bytes | None = None) -> dict:
        return validate_knowledge_use(
            use,
            knowledge_receipt=self.receipt,
            model_visible_context=self.delivery.model_visible_context,
            serialized_principal_input=self.serialized if serialized is None else serialized,
        )

    def test_a_complete_disposition_inventory_passes_through_the_existing_read_gate(self) -> None:
        use = self._use()
        self.assertEqual(use["schema"], KNOWLEDGE_USE_SCHEMA)
        self.assertEqual(set(use["dispositions"]), {a["id"] for a in self.receipt["artifacts"]})
        result = self._validate(use)
        self.assertEqual(result["schema"], USE_SCHEMA, "the EXISTING bind_principal_knowledge_use receipt")
        self.assertEqual(result["knowledge_use_receipt_hash"], canonical_hash(result, omit="knowledge_use_receipt_hash"))
        self.assertEqual(result["knowledge_receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertEqual(result["missing_retrieval_dispositions"], [])
        retrieval_ids = {row["id"] for row in result["retrieval_inventory"]}
        always_ids = {row["id"] for row in result["loaded_artifacts"]}
        self.assertEqual(retrieval_ids | always_ids, set(use["dispositions"]))
        self.assertEqual(set(result["always_load_dispositions"]), always_ids)

    def test_uninspected_with_a_reason_is_accepted_and_recorded(self) -> None:
        use = self._use()
        some_id = self.receipt["artifacts"][-1]["id"]
        use["dispositions"][some_id] = {"disposition": "UNINSPECTED", "reason": "ran out of budget before this one"}
        result = self._validate(use)
        inventory = {row["id"]: row for row in result["retrieval_inventory"]}
        self.assertEqual(inventory[some_id]["disposition"], "UNINSPECTED")

    def test_a_missing_artifact_disposition_is_refused_by_name(self) -> None:
        use = self._use()
        dropped = self.receipt["artifacts"][3]["id"]
        del use["dispositions"][dropped]
        with self.assertRaisesRegex(KnowledgeDeliveryError, dropped):
            self._validate(use)

    def test_an_extra_artifact_nobody_delivered_is_refused(self) -> None:
        use = self._use()
        use["dispositions"]["not_a_delivered_artifact"] = {"disposition": "INSPECTED", "reason": "x"}
        with self.assertRaisesRegex(KnowledgeDeliveryError, "not_a_delivered_artifact"):
            self._validate(use)

    def test_any_disposition_other_than_inspected_or_uninspected_is_refused(self) -> None:
        use = self._use()
        some_id = self.receipt["artifacts"][0]["id"]
        use["dispositions"][some_id] = {"disposition": "SKIMMED", "reason": "x"}
        with self.assertRaisesRegex(KnowledgeDeliveryError, "SKIMMED"):
            self._validate(use)

    def test_a_disposition_without_a_reason_is_refused(self) -> None:
        use = self._use()
        some_id = self.receipt["artifacts"][0]["id"]
        use["dispositions"][some_id] = {"disposition": "UNINSPECTED", "reason": ""}
        with self.assertRaisesRegex(KnowledgeDeliveryError, "reason"):
            self._validate(use)

    def test_a_knowledge_use_citing_another_receipt_is_refused(self) -> None:
        with self.assertRaisesRegex(KnowledgeDeliveryError, "knowledge_receipt_sha256"):
            self._validate(self._use(knowledge_receipt_sha256="0" * 64))

    def test_a_prompt_that_does_not_carry_the_bundle_bytes_is_refused_by_the_existing_gate(self) -> None:
        with self.assertRaises((KnowledgeDeliveryError, KnowledgeRegistryError)):
            self._validate(self._use(), serialized=self.prompt)

    def test_a_tampered_receipt_is_refused(self) -> None:
        tampered = dict(self.receipt, receipt_sha256="0" * 64)
        with self.assertRaisesRegex(KnowledgeDeliveryError, "receipt_sha256"):
            validate_knowledge_use(
                self._use(), knowledge_receipt=tampered,
                model_visible_context=self.delivery.model_visible_context, serialized_principal_input=self.serialized,
            )

    def test_the_file_form_reads_the_receipt_bundle_and_prompt_beside_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            written = write_knowledge_delivery(self.delivery, out)
            prompt_path = out / "FRANKIE_SPAWN_PROMPT.md"
            prompt_path.write_bytes(self.prompt)
            result = validate_knowledge_use_files(
                self._use(), knowledge_receipt_path=written["receipt"], bundle_path=written["bundle"], prompt_path=prompt_path,
            )
            self.assertEqual(result["schema"], USE_SCHEMA)
            with self.assertRaises(KnowledgeDeliveryError):
                validate_knowledge_use_files(
                    self._use(), knowledge_receipt_path=written["receipt"], bundle_path=written["bundle"],
                    prompt_path=out / "does_not_exist.md",
                )


if __name__ == "__main__":
    unittest.main()
