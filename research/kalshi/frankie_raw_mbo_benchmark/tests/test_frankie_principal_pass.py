"""The principal's own pass: knowledge is READ, not merely delivered.

Four sessions in a row found the knowledge built, delivered, receipted and gated - and consumed
by no run. These pin the mechanical half: every delivered artifact is read and verified before
the pass runs, the dispositions are written from what loaded, and a mismatch refuses the pass.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import frankie_principal_pass as fpp
from research.kalshi.frankie_raw_mbo_benchmark import native_knowledge_delivery as K


class KnowledgeIsReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delivery = K.build_knowledge_delivery(arm="A_MEMORY", role="REAL_TIME_FRANKIE")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = K.write_knowledge_delivery(cls.delivery, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_delivered_artifact_is_read_verified_and_disposed_inspected(self):
        loaded = fpp.load_knowledge(self.delivery.receipt, bundle_path=self.paths["bundle"])
        ids = {a["id"] for a in self.delivery.receipt["artifacts"]}
        self.assertEqual(set(loaded["artifacts"]), ids)
        self.assertEqual({v["disposition"] for v in loaded["knowledge_use"]["dispositions"].values()}, {"INSPECTED"})
        self.assertEqual(set(loaded["knowledge_use"]["dispositions"]), ids)
        self.assertIsNotNone(loaded["brain"], "the brain is parsed in full, not listed")
        self.assertGreater(len(loaded["brain"]["plays"]), 0)
        # the knowledge_use the pass writes is the one the staging read gate accepts
        use = loaded["knowledge_use"]
        bundle = self.paths["bundle"].read_bytes()
        prompt = b"prompt bytes for the test\n"
        result = K.validate_knowledge_use(use, knowledge_receipt=self.delivery.receipt, model_visible_context=bundle,
                                          serialized_principal_input=K.serialized_principal_input(prompt, bundle))
        self.assertEqual(result["knowledge_receipt_sha256"], self.delivery.receipt["receipt_sha256"])

    def test_an_artifact_that_does_not_hash_as_receipted_refuses_the_pass(self):
        receipt = json.loads(json.dumps(self.delivery.receipt))
        receipt["artifacts"][0]["sha256"] = hashlib.sha256(b"not the bytes on disk").hexdigest()
        with self.assertRaises(fpp.PassError) as caught:
            fpp.load_knowledge(receipt, bundle_path=self.paths["bundle"])
        self.assertIn("knowledge-blind", str(caught.exception))
        self.assertIn(receipt["artifacts"][0]["id"], str(caught.exception))

    def test_a_bundle_that_is_not_the_receipted_context_refuses_the_pass(self):
        other = Path(self.tmp.name) / "other.md"
        other.write_bytes(b"a different bundle\n")
        with self.assertRaises(fpp.PassError):
            fpp.load_knowledge(self.delivery.receipt, bundle_path=other)


class VerdictVocabularyTest(unittest.TestCase):
    def test_the_middle_verdict_is_not_unverified(self):
        from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as O
        self.assertNotIn("UNVERIFIED", O.KNOWLEDGE_VERDICTS)
        self.assertIn("NOT_TESTED_ON_THIS_SLICE", O.KNOWLEDGE_VERDICTS)


if __name__ == "__main__":
    unittest.main()
