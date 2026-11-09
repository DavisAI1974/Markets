"""Unverified means preserved for investigation, never dropped or promoted."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from adaptive_locality.core import LocalityError
from adaptive_locality.research_gates import (
    UNVERIFIED_GATES,preserve_unverified_gates)
from adaptive_locality.research_holds import ResearchHoldRegistry
from adaptive_locality.buildmap_trial import (
    inspection_manifest,inspection_comparison_contract)


class UnverifiedScienceReviewGateTests(unittest.TestCase):
    def test_all_unverified_requirements_durable_reload_and_non_destructive_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"unverified.sqlite"
            with ResearchHoldRegistry(path,source_identity="standalone-research",
                                      contract_identity="gate-policy-v1") as store:
                receipt=preserve_unverified_gates(
                    store,archive_name="standalone-gates-all")
                self.assertEqual(receipt["retained_gate_count"],len(UNVERIFIED_GATES))
                self.assertEqual(receipt["unverified_case_count"],len(UNVERIFIED_GATES))
                self.assertEqual(receipt["gates_dropped"],0)
                self.assertEqual(receipt["scientific_jobs_eliminated"],0)
                self.assertEqual(receipt,preserve_unverified_gates(
                    store,archive_name="standalone-gates-all"))
                self.assertEqual(store.counts()["cases"],len(UNVERIFIED_GATES))
                original=store.read_archive("standalone-gates-all")["records"]
                self.assertEqual(len(original),len(UNVERIFIED_GATES))
                self.assertEqual({v["gate_id"] for v in original},
                                 {g.gate_id for g in UNVERIFIED_GATES})
                case=receipt["research_case_ids"][0]
                store.review(case,state="UNDER_REVIEW",reviewer="independent-auditor",
                             reason="evaluate actual independent source evidence")
                self.assertEqual(store.get(case)["state"],"UNDER_REVIEW")
                self.assertEqual(len(store.get(case)["original_evidence"]["records"]),
                                 len(UNVERIFIED_GATES))
                self.assertTrue(store.verify())
            with ResearchHoldRegistry(path,source_identity="standalone-research",
                                      contract_identity="gate-policy-v1") as store:
                self.assertEqual(store.read_archive("standalone-gates-all")["records"],
                                 original)
                self.assertEqual(store.get(case)["state"],"UNDER_REVIEW")
                self.assertEqual(store.counts()["cases"],len(UNVERIFIED_GATES))
                self.assertTrue(store.verify())

    def test_no_hidden_promotion_or_implicit_dropping(self):
        altered=(replace(UNVERIFIED_GATES[0],status="VERIFIED"),)+UNVERIFIED_GATES[1:]
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"r.sqlite",
                                      source_identity="standalone-research",
                                      contract_identity="gate-policy-v1") as store:
                with self.assertRaises(LocalityError):
                    preserve_unverified_gates(store,archive_name="invalid",gates=altered)
                with self.assertRaises(LocalityError):
                    preserve_unverified_gates(store,archive_name="invalid",
                                              gates=UNVERIFIED_GATES[:1]*2)
                self.assertEqual(store.counts()["archives"],0)

    def test_buildmap_trial_retains_every_unverified_item_as_planned(self):
        manifest=inspection_manifest()
        contract=inspection_comparison_contract()
        planned=[c for c in manifest["components"]
                 if c["id"].startswith("unverified-")]
        self.assertEqual(len(planned),len(UNVERIFIED_GATES))
        self.assertEqual({c["id"] for c in planned},
                         set(contract["known_scientific_gates"]))
        self.assertTrue(all("Unresolved" in c["contributes"] for c in planned))
        self.assertTrue(all(c["dependsOn"]==["raw-research-holds"] for c in planned))
        self.assertEqual(contract["scientific_jobs_eliminated"],0)


if __name__=="__main__":
    unittest.main()
