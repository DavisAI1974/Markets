"""Research holds are immutable, recoverable records, never dropped calculations."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from adaptive_locality.core import LocalityError
from adaptive_locality.research_holds import (
    ResearchHoldRegistry, preserve_level2_holds, preserve_five_step_holds)
from adaptive_locality.level2_coupling import discover_level2_balance_links
from adaptive_locality.coupling import discover_coupling
from test_adaptive_locality_level2_coupling import make_windows
from test_adaptive_locality_coupling import synthetic_series,frame


class ResearchHoldTests(unittest.TestCase):
    def test_lossless_rank_hold_recovery_and_review_without_deletion(self):
        original=list(make_windows(50))
        original=[replace(w,balance=1.) if (w.target,w.donor)==("c","d") else w
                  for w in original]
        report=discover_level2_balance_links(original,source_identity="s",
                                              calibration_identity="c")
        self.assertGreater(report["unresolved_count"],0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"holds.sqlite"
            with ResearchHoldRegistry(path,source_identity="s",contract_identity="c") as store:
                archived=preserve_level2_holds(report,store,archive_name="run1-level2")
                self.assertEqual(archived["retained_windows"],len(original))
                self.assertEqual(archived["cases"],report["unresolved_count"])
                self.assertEqual(store.counts()["cases"],report["unresolved_count"])
                self.assertTrue(store.verify())
                self.assertEqual(preserve_level2_holds(report,store,archive_name="run1-level2"),
                                 archived)
                case=archived["research_case_ids"][0]
                retrieved=store.get(case)
                self.assertEqual(len(retrieved["original_evidence"]["records"]),len(original))
                self.assertEqual(retrieved["original_evidence"]["records"][0]["source_frames"],
                                 list(original[0].source_frames))
                self.assertEqual(retrieved["original_evidence"]["records"][0]["balance"],
                                 original[0].balance)
                store.review(case,state="UNDER_REVIEW",reason="inspect rank basis",
                             reviewer="synthetic-auditor")
                store.review(case,state="RETAIN_SEPARATE",reason="unresolved artifact",
                             reviewer="synthetic-auditor")
                self.assertEqual(store.get(case)["state"],"RETAIN_SEPARATE")
                self.assertEqual(store.get(case)["scientific_jobs_eliminated"],0)
            with ResearchHoldRegistry(path,source_identity="s",contract_identity="c") as store:
                self.assertTrue(store.verify())
                self.assertEqual(store.counts()["archives"],1)
                self.assertEqual(store.get(case)["state"],"RETAIN_SEPARATE")
                self.assertEqual(store.get(case)["original_evidence"]["records"][0]["balance"],
                                 original[0].balance)
            with self.assertRaises(LocalityError):
                with ResearchHoldRegistry(path,source_identity="different",contract_identity="c"):
                    pass

    def test_archive_conflict_does_not_overwrite_original(self):
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"s.sqlite",source_identity="s",
                                      contract_identity="c") as store:
                store.archive("base",({"value":13,"outlier":True},))
                with self.assertRaises(LocalityError):
                    store.archive("base",({"value":14,"outlier":True},))
                self.assertEqual(store.read_archive("base")["records"][0]["value"],13)
                self.assertEqual(store.hold("case1","base",reason="rank-deficient",
                                            details={"original_id":"event1"}),"RETAINED_FOR_RESEARCH")
                self.assertEqual(store.hold("case1","base",reason="rank-deficient",
                                            details={"original_id":"event1"}),"ALREADY_RETAINED")
                with self.assertRaises(LocalityError):
                    store.hold("case1","base",reason="different",
                               details={"original_id":"event1"})
                self.assertTrue(store.verify())
                store.db.execute("UPDATE archives SET evidence_json='{}' WHERE archive_name='base'")
                with self.assertRaises(LocalityError):
                    store.get("case1")

    def test_original_information_rank_abstentions_are_persisted(self):
        # Collinear operators: a mathematical research hold, not an event to drop.
        frames=tuple(frame(t,1+0.01*t,1+0.01*t,0.1,0.1,0.3)
                     for t in range(150))
        report=discover_coupling(frames)
        self.assertTrue(all(r.status.startswith("ABSTAIN") for r in report["results"]))
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"r.sqlite",
                                      source_identity="source",
                                      contract_identity="fixed-calibration") as store:
                archived=preserve_five_step_holds(report,frames,store,
                                                   archive_name="level1-full-derived-input")
                self.assertEqual(archived["retained_frames"],len(frames))
                self.assertEqual(archived["rank_and_abstention_cases"],2)
                self.assertEqual(store.counts()["cases"],2)
                case=archived["research_case_ids"][0]
                self.assertEqual(len(store.get(case)["original_evidence"]["records"]),150)
                self.assertEqual(store.counts()["original_evidence_dropped"],0)
                self.assertTrue(store.verify())

    def test_bounded_archive_refuses_silent_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"r.sqlite",
                                      source_identity="s",contract_identity="c",
                                      max_archive_bytes=90) as store:
                with self.assertRaises(LocalityError):
                    store.archive("over-limit",({"payload":"x"*200},))
                self.assertEqual(store.counts()["archives"],0)


if __name__=="__main__":
    unittest.main()
