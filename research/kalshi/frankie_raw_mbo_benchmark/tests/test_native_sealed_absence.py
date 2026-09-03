"""The sealed-absence proof (F-23): the one function the S121 search found nowhere.

The forbidden set is DERIVED: the registry's SEALED_FOR_A_SCOPE layer ids, the source
inventory's section-K objects (classified SEALED), and the Step-1 product identifiers read out
of the section-K files themselves (schema strings, S3 prefixes). `prove_sealed_absent` scans
the emitted prompt and every delivered and knowledge path, modelled on
`brain_view.context_leak`, and produces the four-key FRANKIE_SEALED_ABSENCE_PROOF_V1 the
crosswalk consumes; a hit is a hard failure naming the surface.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    SEALED_LAYER_IDS,
    canonical_hash,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    REPO_ROOT,
    SEALED,
    build_knowledge_delivery,
    classify_inventory,
    render_knowledge_block,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    SEALED_PROOF_SCHEMA,
    crosswalk,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_sealed_absence import (
    PROOF_SCHEMA,
    SealedAbsenceError,
    prove_sealed_absent,
    sealed_object_set,
    surfaces_from_delivery,
)


class SealedObjectSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.inventory = classify_inventory(REPO_ROOT)
        cls.sealed = sealed_object_set(cls.registry, cls.inventory, repo_root=REPO_ROOT)
        cls.tokens = set(cls.sealed["tokens"])

    def test_the_nine_sealed_layer_ids_are_tokens_derived_from_the_registry(self) -> None:
        derived = {
            e["layer_id"] for g in self.registry["groups"] if g["policy"] == "SEALED_FOR_A_SCOPE" for e in g["entries"]
        }
        self.assertEqual(derived, set(SEALED_LAYER_IDS))
        self.assertTrue(derived <= self.tokens)
        self.assertEqual(set(self.sealed["by_class"]["SEALED_LAYER_ID"]), derived)

    def test_every_section_k_object_with_a_path_is_a_token(self) -> None:
        k_paths = {row.path for row in self.inventory if row.classification == SEALED and row.path}
        self.assertTrue(k_paths)
        self.assertTrue(k_paths <= self.tokens)
        self.assertEqual(set(self.sealed["by_class"]["SECTION_K_PATH"]), k_paths)

    def test_the_step1_schema_strings_are_read_out_of_the_section_k_files_not_typed(self) -> None:
        strings = set(self.sealed["by_class"]["STEP1_IDENTIFIER"])
        self.assertTrue(strings)
        # One known member, as a check on the reader, not as a spec of the set.
        self.assertIn("NG_EXHAUSTION_STEP1_OCTOBER_SHARD_RECEIPT_V2_20260824", strings)
        for value in strings:
            with self.subTest(value=value):
                self.assertTrue(len(value) >= 12, "an identifier shorter than that would match prose")

    def test_tokens_are_unique_sorted_and_no_token_is_a_bare_common_word(self) -> None:
        tokens = self.sealed["tokens"]
        self.assertEqual(tokens, sorted(set(tokens)))
        self.assertEqual(self.sealed["token_count"], len(tokens))
        for token in tokens:
            self.assertNotIn(token.lower(), {"step1", "step-1", "sealed", "october", "seconds"})

    def test_the_set_is_deterministic(self) -> None:
        again = sealed_object_set(self.registry, self.inventory, repo_root=REPO_ROOT)
        self.assertEqual(again, self.sealed)


class ProveSealedAbsentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.sealed = sealed_object_set(cls.registry, classify_inventory(REPO_ROOT), repo_root=REPO_ROOT)
        cls.delivery = build_knowledge_delivery(arm="A_MEMORY", role="REAL_TIME_FRANKIE")

    def _clean_surfaces(self) -> dict[str, str]:
        prompt = "# prompt\n" + render_knowledge_block(self.delivery.receipt)
        surfaces = {"prompt": prompt}
        surfaces.update(surfaces_from_delivery(
            knowledge_receipt=self.delivery.receipt, model_visible_context=self.delivery.model_visible_context,
            delivery_receipt=None,
        ))
        return surfaces

    def test_it_passes_on_the_clean_fixture_and_produces_the_four_keys_the_crosswalk_consumes(self) -> None:
        surfaces = self._clean_surfaces()
        proof = prove_sealed_absent(self.sealed, surfaces)
        for key in ("schema", "all_absent", "tokens_checked", "receipt_sha256"):
            self.assertIn(key, proof)
        self.assertEqual(proof["schema"], PROOF_SCHEMA)
        self.assertEqual(PROOF_SCHEMA, SEALED_PROOF_SCHEMA)
        self.assertTrue(proof["all_absent"])
        self.assertEqual(proof["tokens_checked"], self.sealed["token_count"])
        self.assertEqual(proof["receipt_sha256"], canonical_hash(proof, omit="receipt_sha256"))
        self.assertEqual(proof["hits"], [])
        self.assertEqual(set(proof["surfaces_scanned"]), set(surfaces))
        self.assertEqual(proof["sealed_set_sha256"], self.sealed["sealed_set_sha256"])

    def test_the_proof_never_carries_a_sealed_token_in_clear(self) -> None:
        proof = prove_sealed_absent(self.sealed, self._clean_surfaces())
        blob = json.dumps(proof)
        for token in self.sealed["tokens"]:
            with self.subTest(token=token[:24]):
                self.assertNotIn(token, blob)
        self.assertEqual(len(proof["token_digests"]), proof["tokens_checked"])
        self.assertEqual(
            proof["token_digests"][0], hashlib.sha256(self.sealed["tokens"][0].encode("utf-8")).hexdigest()
        )

    def test_an_injected_sealed_path_in_the_prompt_is_a_hard_failure_naming_the_surface(self) -> None:
        surfaces = self._clean_surfaces()
        surfaces["prompt"] += "\nsee research/ng_exhaustion_step1_october_shards_20260824.py for the answer\n"
        with self.assertRaisesRegex(SealedAbsenceError, "prompt"):
            prove_sealed_absent(self.sealed, surfaces)

    def test_an_injected_sealed_layer_id_in_a_delivered_path_list_is_a_hard_failure(self) -> None:
        surfaces = self._clean_surfaces()
        surfaces["delivered_paths"] = surfaces.get("delivered_paths", "") + "\ndata/x/step1_populations.json\n"
        with self.assertRaisesRegex(SealedAbsenceError, "delivered_paths"):
            prove_sealed_absent(self.sealed, surfaces)

    def test_with_hard_off_a_hit_is_reported_as_all_absent_false_and_the_crosswalk_reads_unproven(self) -> None:
        surfaces = self._clean_surfaces()
        surfaces["prompt"] += "\ntarget_ground_truth_onset_time\n"
        proof = prove_sealed_absent(self.sealed, surfaces, hard=False)
        self.assertFalse(proof["all_absent"])
        self.assertEqual(len(proof["hits"]), 1)
        self.assertEqual(proof["hits"][0]["surface"], "prompt")
        self.assertNotIn("target_ground_truth_onset_time", json.dumps(proof["hits"]))
        rows = {r["layer_id"]: r for r in crosswalk(self.registry, arm="A_MEMORY", sealed_proof=proof)["layers"]}
        self.assertEqual(rows["step1_populations"]["status"], "SEALED_UNPROVEN")

    def test_a_clean_proof_makes_the_crosswalk_read_every_sealed_layer_proven(self) -> None:
        proof = prove_sealed_absent(self.sealed, self._clean_surfaces())
        body = crosswalk(self.registry, arm="A_MEMORY", sealed_proof=proof)
        sealed_rows = [r for r in body["layers"] if r["policy"] == "SEALED_FOR_A_SCOPE"]
        self.assertTrue(sealed_rows)
        for row in sealed_rows:
            with self.subTest(layer=row["layer_id"]):
                self.assertEqual(row["status"], "SEALED_PROVEN")
                self.assertEqual(row["evidence"]["receipt_sha256"], proof["receipt_sha256"])

    def test_matching_is_exact_and_case_sensitive_so_keep_paths_naming_step1_in_caps_are_not_hits(self) -> None:
        surfaces = {"prompt": "research/NG_EXHAUSTION_CHAIN_STEP1_ORIGINAL_FILE_MAP_20260820.md STEP1_POPULATIONS Step-1"}
        proof = prove_sealed_absent(self.sealed, surfaces)
        self.assertTrue(proof["all_absent"])

    def test_surfaces_from_delivery_cover_bundle_knowledge_paths_and_delivered_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            member = Path(tmp) / "exact_member_rows.jsonl"
            member.write_text("{}\n", encoding="utf-8")
            delivery_receipt = {
                "schema": "FRANKIE_LEDGER_DELIVERY_RECEIPT_V1",
                "ledgers": {"exact_member_ledger": {"local_path": str(member), "object": "ledgers/exact_member_rows.jsonl.gz"}},
                "objects": {"calculation_result.json": {"key": "run/calculation_result.json"}},
                "run_prefix": "nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/abc/1-1",
            }
            surfaces = surfaces_from_delivery(
                knowledge_receipt=self.delivery.receipt, model_visible_context=self.delivery.model_visible_context,
                delivery_receipt=delivery_receipt,
            )
        self.assertEqual(set(surfaces), {"knowledge_bundle", "knowledge_paths", "delivered_paths"})
        self.assertIn(str(member), surfaces["delivered_paths"])
        self.assertIn("ledgers/exact_member_rows.jsonl.gz", surfaces["delivered_paths"])
        self.assertIn(delivery_receipt["run_prefix"], surfaces["delivered_paths"])
        self.assertIn("A_MEMORY_SEED_20260902.json", surfaces["knowledge_paths"])
        self.assertIn("FRANKIE_A_MEMORY_SEED_V1", surfaces["knowledge_bundle"])

    def test_no_surface_is_a_refusal_not_a_vacuous_proof(self) -> None:
        with self.assertRaisesRegex(SealedAbsenceError, "surface"):
            prove_sealed_absent(self.sealed, {})
        with self.assertRaisesRegex(SealedAbsenceError, "token"):
            prove_sealed_absent({**self.sealed, "tokens": [], "token_count": 0}, {"prompt": "x"})


if __name__ == "__main__":
    unittest.main()
