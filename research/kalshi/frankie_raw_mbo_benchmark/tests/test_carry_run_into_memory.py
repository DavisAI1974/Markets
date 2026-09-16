"""The carry is gated, rendered, rebuilt, verified and receipted - one tool, idempotent, fail-closed.

Greg, 2026-09-16: "we have to make all of that automated because we won't be able to watch for
jsons 24/7 for him." The gate tests copy a committed run into a temporary root and break one
thing at a time; the committed-tree tests run --check against what --write left behind.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import carry_run_into_memory as carry
from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed import (
    FINDING_ARTIFACT_NAME,
    PRINCIPAL_RUNS_DIR,
    REPO_ROOT,
    own_a_memory_runs,
)


def a_committed_run() -> tuple[str, str]:
    runs = own_a_memory_runs(REPO_ROOT)
    assert runs, "a committed A_MEMORY run of his own"
    return runs[0]


class GateTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory, self.run_id = a_committed_run()
        shutil.copytree(REPO_ROOT / self.directory, self.root / self.directory)
        self.artifact = self.root / self.directory / FINDING_ARTIFACT_NAME

    def _rewrite_artifact(self, **changes):
        body = json.loads(self.artifact.read_text(encoding="utf-8"))
        body.update(changes)
        self.artifact.write_text(json.dumps(body), encoding="utf-8")

    def test_the_committed_run_passes_the_gate_and_states_its_standing(self):
        verdict = carry.gate_output_bundle(self.root, self.directory)
        self.assertIn(verdict["status"], (carry.GATE_FULLY_VALIDATED, carry.GATE_PRIOR))
        self.assertEqual(verdict["outputs_receipt_sha256"], json.loads(self.artifact.read_text(encoding="utf-8"))["outputs_receipt_sha256"])
        self.assertTrue(verdict["required_ledger_ids_at_filing"])
        if verdict["status"] == carry.GATE_PRIOR:
            delta = verdict["required_set_delta_since_filing"]
            self.assertTrue(delta["added"] or delta["removed"] or verdict["filed_against"] != verdict["current"])

    def test_a_cited_receipt_the_bundle_does_not_have_is_refused(self):
        self._rewrite_artifact(outputs_receipt_sha256="f" * 64)
        with self.assertRaisesRegex(carry.CarryError, "different set of outputs"):
            carry.gate_output_bundle(self.root, self.directory)

    def test_an_artifact_citing_no_outputs_is_refused(self):
        self._rewrite_artifact(outputs_receipt_sha256=None)
        with self.assertRaisesRegex(carry.CarryError, "taught nothing"):
            carry.gate_output_bundle(self.root, self.directory)

    def test_a_tampered_ledger_is_refused_by_the_chain(self):
        ledgers = self.root / self.directory / carry.OUTPUT_BUNDLE_DIRNAME / outputs.LEDGERS_DIRNAME
        target = next(ledgers.glob("contract_section_*.json"))
        body = json.loads(target.read_text(encoding="utf-8"))
        body["entries"][0]["body"]["section"] = "4.99"
        target.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaises(carry.CarryError):
            carry.gate_output_bundle(self.root, self.directory)

    def test_a_run_that_is_not_committed_does_not_exist(self):
        with self.assertRaisesRegex(carry.CarryError, "not committed"):
            carry.run_directory(self.root, "no-such-run")

    def test_documents_are_rendered_or_recorded_as_not_filed_never_invented(self):
        docs = carry.render_run_documents(self.root, self.directory, write=False)
        bundle = outputs.load_bundle(self.root / self.directory / carry.OUTPUT_BUNDLE_DIRNAME)
        filed = all(lid in bundle["ledgers"] for lid in outputs.RUN_DOCUMENT_LEDGERS)
        if filed:
            self.assertEqual(docs["status"], "RENDERED")
            self.assertEqual(set(docs["files"]), {"FRANKIE_WHAT_HE_LEARNED.md", "FRANKIE_IN_HIS_OWN_WORDS.md"})
        else:
            self.assertEqual(docs, {"status": carry.DOCUMENTS_NOT_FILED, "files": {}})


class CommittedTreeTest(unittest.TestCase):
    """--write left a receipt per run; --check recomputes it from disk and the four tools pass."""

    def test_every_committed_run_checks_against_its_carry_receipt(self):
        self.assertEqual(carry.main(["--check", "--all", "--repo-root", str(REPO_ROOT)]), 0)

    def test_a_receipt_names_the_memory_it_left_by_hash_and_no_desktop_path(self):
        for _directory, run_id in own_a_memory_runs(REPO_ROOT):
            with self.subTest(run=run_id):
                path = REPO_ROOT / carry.CARRY_RECEIPTS_DIR / f"{run_id}.json"
                receipt = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(receipt["schema"], carry.CARRY_RECEIPT_SCHEMA)
                for key in ("seed", "mission", "knowledge_sources", "knowledge_manifest", "registry"):
                    self.assertRegex(receipt["memory"][key]["sha256"], r"^[0-9a-f]{64}$")
                blob = path.read_text(encoding="utf-8")
                self.assertNotRegex(blob, r"[A-Za-z]:[\\/]")
                self.assertNotIn("/tmp/", blob)

    def test_the_carry_tools_refuse_another_checkout(self):
        with self.assertRaisesRegex(carry.CarryError, "this checkout"):
            carry.rebuild_memory(Path(tempfile.gettempdir()), write=False)

    def test_the_receipts_directory_is_not_a_run(self):
        self.assertNotIn(carry.CARRY_RECEIPTS_DIR, [d for d, _ in own_a_memory_runs(REPO_ROOT)])
        self.assertTrue(carry.CARRY_RECEIPTS_DIR.startswith(PRINCIPAL_RUNS_DIR))


if __name__ == "__main__":
    unittest.main()
