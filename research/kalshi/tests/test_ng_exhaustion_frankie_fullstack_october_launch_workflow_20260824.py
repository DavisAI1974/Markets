from __future__ import annotations

import ast
import json
import re
import subprocess
import textwrap
import unittest
from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml"
)
MANIFEST = Path(
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"
)
MARKER = Path(
    "research/kalshi/NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_LAUNCH_20260824.json"
)
TARGET_BRANCH = "chatgpt/ng-exhaustion-october-sharded-20260824"
WORKFLOW_TEST = Path(
    "research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py"
)


class FullStackOctoberLaunchWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_trigger_is_explicit_new_marker_or_confirmed_dispatch_on_target_branch(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertIn("confirm_full_october:", self.source)
        self.assertIn("type: boolean", self.source)
        self.assertIn(f"- {TARGET_BRANCH}", self.source)
        self.assertIn(str(MARKER), self.source)
        self.assertIn(f"refs/heads/{TARGET_BRANCH}", self.source)
        self.assertFalse(MARKER.exists(), "implementation must not create or fire the launch marker")

    def test_staging_is_manifest_driven_for_predecessor_plus_all_26_october_objects(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = manifest["canonical_dbn_objects"]
        predecessor = [
            row
            for row in rows
            if row["segment"] == "20210901_20211001"
            and row["key"].endswith("glbx-mdp3-20210930.mbo.dbn.zst")
        ]
        october = [row for row in rows if row["segment"] == "20211001_20211101"]
        self.assertEqual(len(predecessor), 1)
        self.assertEqual(len(october), 26)
        self.assertEqual(len(predecessor) + len(october), 27)

        for token in (
            'manifest["canonical_dbn_objects"]',
            'row.get("segment") == predecessor_segment',
            'row.get("segment") == october_segment',
            "len(targets) != 26",
            "len(roster) != 27",
            "for index, row in enumerate(roster)",
            'row["bytes"]',
            'row["sha256"]',
            "sha256_file(destination)",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("target_key =", self.source)

    def test_packages_exact_sha_and_invokes_only_the_full_month_runner(self):
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', self.source)
        self.assertIn('git archive --format=tar.gz --output="$package" "$GITHUB_SHA"', self.source)
        self.assertIn(
            "python research/kalshi/ng_exhaustion_frankie_fullstack_october_20260824.py",
            self.source,
        )
        for flag in ("--manifest", "--source-root", "--output-root", "--run-id"):
            self.assertIn(flag, self.source)
        self.assertNotIn("ng_exhaustion_october_frankie_v4_bridge_20260824.py", self.source)
        self.assertNotIn("frankie_bounded_3mo_parallel.py", self.source)
        self.assertNotIn("canary", self.source.lower())

    def test_identity_is_unique_and_keyed_by_sha_run_and_attempt(self):
        for token in (
            "ng-exhaustion-frankie-fullstack-october-",
            "/mnt/markets/ng_exhaustion_frankie_fullstack_october_20260824/",
            "${GITHUB_SHA}",
            "${GITHUB_RUN_ID}",
            "${GITHUB_RUN_ATTEMPT}",
            "frankie/fullstack-october-2021/launches/",
            "systemd-run --collect --unit",
            '--property=Restart=no',
        ):
            self.assertIn(token, self.source)

    def test_permanent_services_are_observed_but_never_mutated_or_required_inactive(self):
        for service in (
            "markets-frankie.service",
            "markets-frankie-reflect.service",
            "markets-frankie-reflect.timer",
            "markets-frankie-bounded-3mo.service",
        ):
            self.assertIn(service, self.source)
        self.assertIn('systemctl show "$service"', self.source)
        self.assertNotRegex(
            self.source,
            re.compile(
                r"systemctl\s+(?:start|stop|restart|try-restart|reload|enable|disable|mask|unmask|reset-failed)"
                r"[^\n]*(?:markets-frankie|permanent)",
                re.IGNORECASE,
            ),
        )
        self.assertNotIn("require inactive", self.source.lower())
        self.assertNotIn("is-active --quiet markets-frankie", self.source)

    def test_rollback_sync_dependencies_and_focused_tests_are_explicit(self):
        self.assertIn('FULLSTACK_STOP_COMMAND=systemctl stop $unit', self.source)
        self.assertIn('aws s3 sync "$output"', self.source)
        self.assertIn('aws s3 cp "$run_log"', self.source)
        self.assertIn("databento==0.81.0", self.source)
        self.assertIn("deploy/aws/requirements-frankie.txt", self.source)
        self.assertIn(
            "python research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_20260824.py",
            self.source,
        )
        self.assertIn(f"python {WORKFLOW_TEST}", self.source)
        self.assertNotIn("python -m pytest", self.source)

    def test_launch_waits_for_every_evidence_gate_and_fails_closed(self):
        for event in (
            "KNOWLEDGE_MANIFEST_READY",
            "ANSWER_WALL_PREFREEZE_VERIFIED",
            "FORBIDDEN_V3_DENIED",
            "CAUSAL_STATE_APPENDED",
            "HELPER_EVIDENCE_APPENDED",
            "FRANKIE_REASONING_APPENDED",
            "PROBABILITY_MOVIE_APPENDED",
            "SOL_RESPONSE_ACCEPTED",
        ):
            self.assertIn(event, self.source)
        for token in (
            '"gpt-5.6-sol"',
            "provider_response_id",
            "knowledge_manifest_hash",
            "receipt_hash",
            "Traceback",
            "MODEL_DRIFT",
            "RUN_FAILED",
            "FULLSTACK_LAUNCH_GATES=PASS",
        ):
            self.assertIn(token, self.source)
        self.assertIn('ActiveState --value "$unit"', self.source)
        self.assertIn('test "$status" = Success', self.source)

    def test_embedded_python_generator_and_remote_python_scripts_compile(self):
        match = re.search(
            r"          python - <<'PY'\n(.*?)\n          PY", self.source, re.DOTALL
        )
        self.assertIsNotNone(match)
        generator = textwrap.dedent(match.group(1))
        tree = ast.parse(generator, filename=str(WORKFLOW))
        scripts = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "stage_script",
                    "gate_script",
                    "runner_script",
                }:
                    scripts[target.id] = node.value.value
        self.assertEqual(set(scripts), {"stage_script", "gate_script", "runner_script"})
        for name in ("stage_script", "gate_script"):
            source = scripts[name]
            compile(textwrap.dedent(source), f"<{name}>", "exec")
        subprocess.run(
            ["bash", "-n"],
            input=textwrap.dedent(scripts["runner_script"]),
            text=True,
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
