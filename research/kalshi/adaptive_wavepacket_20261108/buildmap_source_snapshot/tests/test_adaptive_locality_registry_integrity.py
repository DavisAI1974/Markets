"""Research-hold archival integrity: preserving all cases across restarts."""
import tempfile
import unittest
from pathlib import Path

from adaptive_locality.core import LocalityError
from adaptive_locality.research_holds import ResearchHoldRegistry


class RegistryIntegrityTests(unittest.TestCase):
    def test_foreign_key_enforced_and_all_cases_preserved_after_state_review(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"integrity.sqlite"
            with ResearchHoldRegistry(db,source_identity="source-v1",
                                      contract_identity="frozen-v1") as store:
                self.assertEqual(store.db.execute("PRAGMA foreign_keys").fetchone(),(1,))
                store.archive("original",({"original_id":"e1","value":1.0},))
                store.hold("case1","original",reason="RANK_UNVERIFIED",
                           details={"direction":"AB","clock":1})
                store.hold("case2","original",reason="CONFLICTING_FINDING",
                           details={"direction":"BA","clock":2})
                with self.assertRaises(Exception):
                    store.db.execute("DELETE FROM archives WHERE archive_name='original'")
                store.review("case1",state="UNDER_REVIEW",
                             reason="inspect rank with independent estimator",
                             reviewer="review-a")
                self.assertTrue(store.verify())
                self.assertEqual(store.counts()["cases"],2)
                self.assertEqual(store.get("case2")["state"],"RESEARCH_HOLD")
            with ResearchHoldRegistry(db,source_identity="source-v1",
                                      contract_identity="frozen-v1") as store:
                self.assertEqual(store.get("case1")["state"],"UNDER_REVIEW")
                self.assertEqual(store.get("case2")["original_evidence"]["records"][0]["original_id"],
                                 "e1")
                self.assertTrue(store.verify())

    def test_tampered_case_state_rejected_even_if_archive_and_history_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"state.sqlite",
                                      source_identity="s",contract_identity="c") as store:
                store.archive("raw",({"id":"e1"},))
                store.hold("rank","raw",reason="UNVERIFIED",
                           details={"source":"original"})
                store.db.execute("UPDATE cases SET state='REVIEWED_NO_SUPPRESSION' "
                                 "WHERE case_id='rank'")
                with self.assertRaisesRegex(LocalityError,"diverges"):
                    store.verify()

    def test_tampered_initial_reason_and_missing_case_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"reason.sqlite",
                                      source_identity="s",contract_identity="c") as store:
                store.archive("raw",({"id":"e1"},))
                store.hold("case","raw",reason="UNRESOLVED",
                           details={"source":"original"})
                store.db.execute("UPDATE cases SET reason='FALSE_ACCEPTED' "
                                 "WHERE case_id='case'")
                with self.assertRaisesRegex(LocalityError,"creation history"):
                    store.verify()
                store.db.execute("UPDATE cases SET reason='UNRESOLVED' "
                                 "WHERE case_id='case'")
                store.db.execute("DELETE FROM cases WHERE case_id='case'")
                with self.assertRaisesRegex(LocalityError,"missing research case"):
                    store.verify()


if __name__=="__main__":
    unittest.main()
