"""D90/D91: Frankie's admitted findings accumulate across roster days."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed import (
    FINDING_ARTIFACT_NAME,
    FINDING_VETO_PATH,
    FINDING_VETO_SCHEMA,
    PRINCIPAL_RUNS_DIR,
    SeedBuildError,
    build_seed,
    build_finding_memory,
    seed_entry_paths,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    KNOWLEDGE_RECEIPT_SCHEMA,
    render_knowledge_block,
    served_memory_findings,
)
from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import (
    EXPECTED_ROSTER,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github/workflows/a_memory_findings_carry_20260903.yml"


def artifact(*, source_day: str, run_id: str, findings: list[dict]) -> dict:
    return {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
        "principal": "gpt-5.6-sol",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "run_id": run_id,
        "source_day": source_day,
        "evidence_result_hash": "a" * 64,
        "actual_principal_invocation": True,
        "controller_only": False,
        "findings": findings,
    }


def write_artifact(root: Path, body: dict) -> Path:
    target = root / PRINCIPAL_RUNS_DIR / body["run_id"] / FINDING_ARTIFACT_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body), encoding="utf-8")
    return target


def finding(finding_id: str, **overrides) -> dict:
    body = {
        "id": finding_id,
        "category": "new_stream_structure",
        "section": "4.10",
        "claim": f"claim for {finding_id}",
        "evidence": {"groups": [101, 102]},
        "falsifier": f"stream event that would retire {finding_id}",
        "confidence_basis": "observed on this roster day only",
        "exemplars": ["group-101"],
    }
    body.update(overrides)
    return body


def write_vetoes(root: Path, *rows: dict) -> Path:
    target = root / FINDING_VETO_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"schema": FINDING_VETO_SCHEMA, "vetoes": list(rows)}),
        encoding="utf-8",
    )
    return target


class EmptyDayContractTest(unittest.TestCase):
    def test_written_empty_day_is_distinct_from_missing_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            written_day = EXPECTED_ROSTER[0][0]
            write_artifact(root, artifact(source_day=written_day, run_id="memory-day-empty", findings=[]))

            memory = build_finding_memory(root)

        by_day = {row["source_day"]: row for row in memory["days"]}
        self.assertEqual(by_day[written_day]["artifact_status"], "PRESENT_EMPTY")
        for source_day, _role in EXPECTED_ROSTER[1:]:
            self.assertEqual(by_day[source_day]["artifact_status"], "MISSING")
        self.assertEqual(memory["findings"], [])


class HistoricalSeedFindingsTest(unittest.TestCase):
    def test_the_existing_44_findings_are_in_a_memory_seed_unchanged(self) -> None:
        historical_path = (
            REPO_ROOT
            / PRINCIPAL_RUNS_DIR
            / "33605852433"
            / FINDING_ARTIFACT_NAME
        )
        historical = json.loads(historical_path.read_text(encoding="utf-8"))

        seed = build_seed(REPO_ROOT)

        carried = seed["finding_memory"]["findings"]
        self.assertEqual(len(historical["findings"]), 44)
        self.assertEqual(len(carried), 44)
        for expected, actual in zip(historical["findings"], carried, strict=True):
            self.assertEqual({field: actual[field] for field in expected}, expected)
            self.assertEqual(actual["status"], "VERIFIED")
            self.assertTrue(actual["served"])
        self.assertEqual(
            [row["id"] for row in served_memory_findings(seed)],
            [row["id"] for row in historical["findings"]],
        )


class FindingsCarryTest(unittest.TestCase):
    def test_a_later_day_is_refused_until_every_prior_day_has_an_artifact(self) -> None:
        first_day, second_day = (row[0] for row in EXPECTED_ROSTER[:2])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, artifact(
                source_day=second_day,
                run_id="memory-day-two-too-early",
                findings=[finding("F-OUT-OF-ORDER")],
            ))
            with self.assertRaisesRegex(SeedBuildError, f"{second_day}.*{first_day}"):
                build_finding_memory(root)

            write_artifact(root, artifact(
                source_day=first_day,
                run_id="memory-day-one-empty",
                findings=[],
            ))
            memory = build_finding_memory(root)

        by_day = {row["source_day"]: row for row in memory["days"]}
        self.assertEqual(by_day[first_day]["artifact_status"], "PRESENT_EMPTY")
        self.assertEqual(by_day[second_day]["artifact_status"], "PRESENT_WITH_FINDINGS")

    def test_second_day_adds_only_ids_not_already_carried(self) -> None:
        first_day, second_day = (row[0] for row in EXPECTED_ROSTER[:2])
        shared = finding("F-GLOBAL-SHARED")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, artifact(
                source_day=first_day,
                run_id="memory-day-one",
                findings=[finding("F-GLOBAL-ONE"), shared],
            ))
            write_artifact(root, artifact(
                source_day=second_day,
                run_id="memory-day-two",
                findings=[shared, finding("F-GLOBAL-TWO")],
            ))
            memory = build_finding_memory(root)

        self.assertEqual(
            [row["id"] for row in memory["findings"]],
            ["F-GLOBAL-ONE", "F-GLOBAL-SHARED", "F-GLOBAL-TWO"],
        )
        by_day = {row["source_day"]: row for row in memory["days"]}
        self.assertEqual(by_day[first_day]["new_finding_ids"], ["F-GLOBAL-ONE", "F-GLOBAL-SHARED"])
        self.assertEqual(by_day[second_day]["new_finding_ids"], ["F-GLOBAL-TWO"])

    def test_same_id_with_different_content_is_refused(self) -> None:
        first_day, second_day = (row[0] for row in EXPECTED_ROSTER[:2])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, artifact(
                source_day=first_day, run_id="memory-day-one", findings=[finding("F-STABLE")]
            ))
            write_artifact(root, artifact(
                source_day=second_day,
                run_id="memory-day-two",
                findings=[finding("F-STABLE", claim="the id now means something else")],
            ))
            with self.assertRaisesRegex(SeedBuildError, "stable finding id"):
                build_finding_memory(root)

    def test_the_existing_admission_gate_refuses_unfalsifiable_or_unanchored_findings(self) -> None:
        source_day = EXPECTED_ROSTER[0][0]
        for bad, reason in (
            (finding("F-NO-FALSIFIER", falsifier=""), "falsifier"),
            (finding("F-NO-EXEMPLAR", exemplars=[]), "exact exemplar"),
        ):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_artifact(root, artifact(
                    source_day=source_day, run_id=f"memory-{bad['id']}", findings=[bad]
                ))
                with self.assertRaisesRegex(SeedBuildError, reason):
                    build_finding_memory(root)

    def test_the_roster_is_the_day_bound(self) -> None:
        outside_day = str(max(int(row[0]) for row in EXPECTED_ROSTER) + 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, artifact(
                source_day=outside_day,
                run_id="memory-outside-roster",
                findings=[finding("F-OUTSIDE")],
            ))
            with self.assertRaisesRegex(SeedBuildError, "manifest roster"):
                build_finding_memory(root)

        with tempfile.TemporaryDirectory() as tmp:
            memory = build_finding_memory(Path(tmp))
        self.assertEqual(memory["roster"]["source_days"], [row[0] for row in EXPECTED_ROSTER])
        self.assertEqual(memory["roster"]["day_bound"], len(EXPECTED_ROSTER))


class VetoContractTest(unittest.TestCase):
    def test_veto_is_persistent_present_and_unserved_across_rebuilds(self) -> None:
        source_day = EXPECTED_ROSTER[0][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, artifact(
                source_day=source_day,
                run_id="memory-day-veto",
                findings=[finding("F-KEEP"), finding("F-VETO")],
            ))
            write_vetoes(root, {
                "id": "F-VETO", "status": "VETOED", "reason": "Greg marked this finding off"
            })

            first = build_finding_memory(root)
            second = build_finding_memory(root)

        self.assertEqual(first, second)
        by_id = {row["id"]: row for row in second["findings"]}
        self.assertEqual(by_id["F-VETO"]["status"], "VETOED")
        self.assertFalse(by_id["F-VETO"]["served"])
        self.assertEqual(by_id["F-KEEP"]["status"], "NEW")
        self.assertTrue(by_id["F-KEEP"]["served"])
        self.assertEqual([row["id"] for row in served_memory_findings(second)], ["F-KEEP"])

    def test_a_veto_for_an_unknown_id_is_refused_as_a_probable_typo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_vetoes(root, {
                "id": "F-NOT-PRESENT", "status": "VETOED", "reason": "fixture"
            })
            with self.assertRaisesRegex(SeedBuildError, "unknown finding id"):
                build_finding_memory(root)


class SeedIntegrationTest(unittest.TestCase):
    def test_admitted_findings_are_embedded_without_replacing_historical_files(self) -> None:
        source_day = EXPECTED_ROSTER[0][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in seed_entry_paths(REPO_ROOT):
                source = REPO_ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            write_artifact(root, artifact(
                source_day=source_day,
                run_id="memory-day-integrated",
                findings=[finding("F-IN-SEED")],
            ))

            seed = build_seed(root)

        self.assertIn("finding_memory", seed)
        findings = seed["finding_memory"]["findings"]
        self.assertEqual(len(findings), 45)
        by_id = {row["id"]: row for row in findings}
        self.assertEqual(by_id["F-IN-SEED"]["status"], "NEW")
        self.assertEqual(
            sum(row["status"] == "VERIFIED" for row in findings),
            44,
        )
        historical_paths = {entry["path"] for entry in seed["entries"]}
        self.assertIn(
            PRINCIPAL_RUNS_DIR + "33605852433/" + FINDING_ARTIFACT_NAME,
            historical_paths,
        )


class KnowledgeBlockTest(unittest.TestCase):
    def test_the_block_renders_every_served_finding_and_never_a_vetoed_one(self) -> None:
        keep = {
            **finding("F-SERVED"), "status": "NEW", "served": True,
            "provenance": {"source_day": EXPECTED_ROSTER[0][0], "run_id": "memory-day"},
        }
        veto = {
            **finding("F-VETOED"), "status": "VETOED", "served": False,
            "provenance": {"source_day": EXPECTED_ROSTER[0][0], "run_id": "memory-day"},
        }
        receipt = {
            "schema": KNOWLEDGE_RECEIPT_SCHEMA,
            "receipt_sha256": "a" * 64,
            "profile_id": "RT_A_MEMORY_SECOND_PASS",
            "arm": "A_MEMORY",
            "role": "REAL_TIME_FRANKIE",
            "manifest_path": "manifest.json",
            "manifest_hash": "b" * 64,
            "manifest_file_sha256": "c" * 64,
            "spec_path": "spec.json",
            "spec_file_sha256": "d" * 64,
            "registry_sha256": "e" * 64,
            "bundle_filename": "KNOWLEDGE_BUNDLE.md",
            "model_visible_context_sha256": "f" * 64,
            "model_visible_context_bytes": 1,
            "layers": [],
            "artifacts": [],
            "memory_findings": [keep],
            "totals": {
                "delivered": 0, "layers": 0, "artifacts": 0, "always_load": 0, "retrieval": 0,
            },
        }

        block = render_knowledge_block(receipt)

        self.assertIn("F-SERVED", block)
        for field in ("claim", "evidence", "falsifier", "confidence_basis"):
            expected = (
                json.dumps(keep[field], sort_keys=True)
                if field == "evidence"
                else str(keep[field])
            )
            self.assertIn(expected, block)
        self.assertNotIn(veto["id"], block)


class AutomaticWorkflowTest(unittest.TestCase):
    def test_push_of_a_committed_findings_file_runs_the_ordered_rebuild_and_commits(self) -> None:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        triggers = document.get("on", document.get(True))
        self.assertEqual(triggers["push"]["branches"], ["chatgpt/frankie-raw-mbo-benchmark-20260828"])
        self.assertIn(
            PRINCIPAL_RUNS_DIR + "**/" + FINDING_ARTIFACT_NAME,
            triggers["push"]["paths"],
        )
        self.assertNotIn("workflow_dispatch", triggers)
        self.assertNotIn("pull_request", triggers)
        self.assertEqual(document["permissions"]["contents"], "write")
        body = "\n".join(
            step.get("run", "")
            for job in document["jobs"].values()
            for step in job["steps"]
        )
        ordered = (
            "build_a_memory_seed",
            "register_a_memory_knowledge",
            "rebind_registry_knowledge_layers",
            "refresh_native_frankie_knowledge.py",
        )
        self.assertEqual([body.index(name) for name in ordered], sorted(body.index(name) for name in ordered))
        self.assertIn("git commit", body)
        self.assertIn("git push", body)
        self.assertNotIn("gh pr", body)

    def test_the_promotion_commit_cannot_retrigger_the_carry(self) -> None:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        triggers = document.get("on", document.get(True))["push"]["paths"]
        body = WORKFLOW.read_text(encoding="utf-8")
        for generated in (
            "A_MEMORY_SEED_20260902.json",
            "KNOWLEDGE_MANIFEST_20260828.json",
            "KNOWLEDGE_SOURCES_20260828.json",
        ):
            self.assertIn(generated, body)
            self.assertNotIn(generated, triggers)


if __name__ == "__main__":
    unittest.main()
