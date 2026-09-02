"""D57 on the delivery workflow: parse the YAML, `bash -n` every run block, compile any
embedded Python - never verify a workflow by reading it.

Two workflows in this repository produced a jobless startup-failure run on EVERY push to
EVERY branch because a heredoc dedented to column 0 broke its block scalar. This is the
mechanical check, mirrored from `test_a_arm_launch_workflows.py`.
"""
from __future__ import annotations

import ast
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github/workflows/frankie_ledger_delivery_20260902.yml"
FETCHER = "research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers"
HEREDOC = re.compile(r"python3? - <<'(?P<tag>[A-Z_]+)'\n(?P<body>.*?)\n\s*(?P=tag)(?:\n|$)", re.DOTALL)


def document() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps() -> list[dict]:
    return [step for job in document()["jobs"].values() for step in job["steps"]]


def triggers() -> dict:
    doc = document()
    return doc.get("on", doc.get(True))


class StructureTest(unittest.TestCase):
    def test_the_yaml_parses(self):
        self.assertIn("jobs", document())

    def test_every_run_block_is_valid_bash(self):
        checked = 0
        for step in steps():
            body = step.get("run")
            if not body:
                continue
            checked += 1
            with self.subTest(step=step.get("name")):
                with tempfile.NamedTemporaryFile("w", suffix=".sh") as handle:
                    handle.write(body)
                    handle.flush()
                    result = subprocess.run(["bash", "-n", handle.name], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(checked, 0)

    def test_every_embedded_python_heredoc_compiles(self):
        """The manifest logic lives in the tested module, so the count is asserted at zero:
        a heredoc appearing here would be logic that escaped the tests."""
        found = 0
        for step in steps():
            for match in HEREDOC.finditer(step.get("run") or ""):
                found += 1
                with self.subTest(step=step.get("name")):
                    ast.parse(textwrap.dedent(match.group("body")))
        self.assertEqual(found, 0, "manifest logic belongs in fetch_frankie_ledgers, not in a heredoc")


class TriggerTest(unittest.TestCase):
    def test_dispatch_defaults_to_the_pinned_sunday_run_not_the_newest(self):
        inputs = triggers()["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["run_id"]["default"], "33630348943")
        self.assertEqual(inputs["prefix"]["default"], "")

    def test_the_push_trigger_is_filtered_to_this_branch_and_its_own_path(self):
        push = triggers()["push"]
        self.assertEqual(push["branches"], ["chatgpt/frankie-raw-mbo-benchmark-20260828"])
        self.assertIn(".github/workflows/frankie_ledger_delivery_20260902.yml", push["paths"])

    def test_the_pinned_run_is_the_default_on_a_push_as_well(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("inputs.run_id || '33630348943'", text)


class DeliveryStepsTest(unittest.TestCase):
    def _step(self, fragment: str) -> dict:
        return next(s for s in steps() if fragment in (s.get("name") or ""))

    def test_the_run_is_located_by_scanning_not_by_constructing_the_key(self):
        run = self._step("Locate")["run"]
        self.assertIn("list-objects-v2", run)
        self.assertIn('grep "/${WANTED_RUN_ID}-"', run)
        self.assertIn("aws s3api head-object", run)

    def test_the_boxs_plain_receipts_are_extracted_from_small_artifacts(self):
        run = self._step("PLAIN_SIZES")["run"]
        self.assertIn("small_artifacts.tar.gz", run)
        self.assertIn("PLAIN_SIZES", run)
        self.assertIn("PLAIN_SHA256SUMS", run)
        # A run without both receipts cannot be witnessed and must FAIL, never continue.
        self.assertNotIn("exit 0", run)

    def test_every_object_is_presigned_for_seven_days_and_urls_never_reach_the_log(self):
        run = self._step("Presign")["run"]
        self.assertIn("aws s3 presign", run)
        self.assertIn("--expires-in 604800", run)
        for name in ("exact_member_rows.jsonl.gz", "exact_lifecycle_rows.jsonl.gz",
                     "legacy_observable_rows.jsonl.gz", "calculation_result.json", "small_artifacts.tar.gz"):
            self.assertIn(name, run, name)
        self.assertNotIn("echo \"$url\"", run)
        self.assertNotIn("cat presigned", run)
        self.assertIn("set +x", run)

    def test_the_manifest_is_built_by_the_tested_module_and_summarised_without_urls(self):
        run = self._step("manifest")["run"]
        self.assertIn(f"python3 -m {FETCHER} build-manifest", run)
        self.assertIn("--presign-seconds 604800", run)
        self.assertNotIn("cat delivery_manifest.json", run)
        self.assertNotIn("cat ./delivery_manifest.json", run)

    def test_the_manifest_is_published_as_an_artifact_for_seven_days(self):
        upload = next(s for s in steps() if str(s.get("uses", "")).startswith("actions/upload-artifact@"))
        self.assertIn("frankie-ledger-delivery-", upload["with"]["name"])
        self.assertIn("${{ github.run_attempt }}", upload["with"]["name"])
        self.assertEqual(upload["with"]["retention-days"], 7)
        self.assertIn("delivery_manifest.json", upload["with"]["path"])
        self.assertEqual(upload["with"]["if-no-files-found"], "error")

    def test_permissions_are_read_only(self):
        self.assertEqual(document()["permissions"], {"contents": "read"})


if __name__ == "__main__":
    unittest.main()
