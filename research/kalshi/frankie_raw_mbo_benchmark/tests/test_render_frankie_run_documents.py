"""The two run documents are renders of two chain-hashed ledgers; nothing in them is authored.

Greg, 2026-09-16: "we want him printing 2 for right now so we can see what he learned along
with his words about it."
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark import render_frankie_run_documents as docs

C1 = 1_633_298_400_000_000_000


def learned(**overrides) -> dict:
    body = {
        "learning_id": "L-001",
        "statement": "the bid touch drained by cancellation before the first trade on all three closed groups",
        "kind": "REVISED",
        "prior_lesson_id": "served-lesson-7",
        "sections": ["4.5"],
        "evidence": {"member_group_indices": [4562, 4563], "cutoff_recv_ns": C1},
    }
    body.update(overrides)
    return body


def words(topic: str, statement: str) -> dict:
    return {"topic": topic, "statement": statement, "refers_to": ["contract_section_4.5"]}


def bundle_with(learned_rows: list[dict], words_rows: list[dict]) -> dict:
    ledgers = {}
    for lid, rows in ((outputs.WHAT_HE_LEARNED_LEDGER, learned_rows), (outputs.IN_HIS_OWN_WORDS_LEDGER, words_rows)):
        ledger = outputs.AppendOnlyLedger(lid)
        for row in rows:
            ledger.append(C1, row)
        ledgers[lid] = ledger.to_dict()
    return {
        "schema": outputs.OUTPUT_BUNDLE_SCHEMA, "run_id": "run-doc-1", "arm": "A_MEMORY", "role": "REAL_TIME_FRANKIE",
        "registry_sha256": "1" * 64, "contract_sha256": "2" * 64,
        "delivery_receipt_sha256": "3" * 64, "knowledge_receipt_sha256": "4" * 64,
        "ledgers": ledgers,
    }


FOUR = [
    words("FINDINGS", "what I found: the drain preceded every first trade"),
    words("BUILD", "my opinion of the build: the causal stream is sound, the finalize step is manual"),
    words("DATA", "my opinion of the data: three ledgers, whole and verified, one Sunday"),
    words("SUGGESTION", "what I suggest: feed the block as one stream"),
]


class RenderTest(unittest.TestCase):
    def test_what_he_learned_carries_every_entry_its_standing_and_its_evidence(self):
        text = docs.render_what_he_learned(bundle_with([learned(), learned(learning_id="L-002", kind="NEW", evidence={"member_group_indices": [], "basis": "no member of the stratum closed"})], FOUR))
        self.assertTrue(text.startswith("# What I learned\n"))
        self.assertIn("## L-001 (REVISED against served lesson `served-lesson-7`)", text)
        self.assertIn("## L-002 (NEW)", text)
        self.assertIn("exact member groups (2): 4562, 4563", text)
        self.assertIn("basis (rests on absence): no member of the stratum closed", text)
        self.assertIn("contract sections: `4.5`", text)
        self.assertIn("run: `run-doc-1`", text)

    def test_in_his_own_words_is_ordered_by_the_four_topics(self):
        text = docs.render_in_his_own_words(bundle_with([learned()], FOUR))
        self.assertTrue(text.startswith("# In my own words\n"))
        positions = [text.index(docs.TOPIC_HEADINGS[t]) for t in outputs.OWN_WORDS_TOPICS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("feed the block as one stream", text)
        self.assertIn("about: `contract_section_4.5`", text)

    def test_an_empty_ledger_or_a_missing_ledger_refuses_the_document(self):
        with self.assertRaisesRegex(docs.RenderError, "empty"):
            docs.render_what_he_learned(bundle_with([], FOUR))
        body = bundle_with([learned()], FOUR)
        del body["ledgers"][outputs.IN_HIS_OWN_WORDS_LEDGER]
        with self.assertRaisesRegex(docs.RenderError, "no ledger"):
            docs.render_in_his_own_words(body)

    def test_a_tampered_entry_breaks_the_chain_and_refuses_the_render(self):
        body = bundle_with([learned()], FOUR)
        body["ledgers"][outputs.WHAT_HE_LEARNED_LEDGER]["entries"][0]["body"]["statement"] = "edited after the fact"
        with self.assertRaises(docs.RenderError):
            docs.render_what_he_learned(body)

    def test_render_documents_names_the_two_files(self):
        rendered = docs.render_documents(bundle_with([learned()], FOUR))
        self.assertEqual(set(rendered), {docs.WHAT_HE_LEARNED_FILENAME, docs.IN_HIS_OWN_WORDS_FILENAME})


class WriteTest(unittest.TestCase):
    def test_write_documents_is_idempotent_over_a_written_bundle(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        body = bundle_with([learned()], FOUR)
        outputs_dir = root / "principal_outputs"
        (outputs_dir / outputs.LEDGERS_DIRNAME).mkdir(parents=True)
        for lid, ledger in body["ledgers"].items():
            (outputs_dir / outputs.LEDGERS_DIRNAME / f"{lid}.json").write_text(json.dumps(ledger), encoding="utf-8")
        receipt = outputs.bundle_receipt(body, required_ledger_ids=list(body["ledgers"]))
        (outputs_dir / outputs.RECEIPT_FILENAME).write_text(json.dumps(receipt), encoding="utf-8")
        first = docs.write_documents(outputs_dir, root)
        self.assertEqual(set(first.values()), {"WRITTEN"})
        second = docs.write_documents(outputs_dir, root)
        self.assertEqual(set(second.values()), {"CURRENT"})
        self.assertEqual(docs.main(["--outputs-dir", str(outputs_dir), "--out-dir", str(root)]), 0)


if __name__ == "__main__":
    unittest.main()
