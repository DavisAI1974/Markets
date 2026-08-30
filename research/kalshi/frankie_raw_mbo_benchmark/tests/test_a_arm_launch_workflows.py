"""T4: the A-arm launch workflows dispatch compute, and neither can fire the box by push.

Both workflows used to fetch the roster, seal a packet, push it to S3 and stop - measured:
zero references to `ssm`, `ec2`, `send-command` or `INSTANCE_ID` in either file. They
reported `RUNNING_PRE_CALL` at 0 records because no compute ran at all.

The structural checks here are D57's rule, and they are not ceremony. Two workflows in this
repository produced a jobless startup-failure run on EVERY push to EVERY branch, ignoring
their own branch filters, because a heredoc dedented to column 0 and broke its enclosing
block scalar. Writing THIS file caught the mirror image an hour after reading that decision:
a heredoc terminator indented so bash never saw it. `bash -n` found it before a push did.
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
WORKFLOWS = {
    "A_CLEAN": REPO_ROOT / ".github/workflows/frankie_a_clean_rt_native_launch_20260828.yml",
    "A_MEMORY": REPO_ROOT / ".github/workflows/frankie_a_memory_rt_native_launch_20260828.yml",
}
LAUNCHER = "research.kalshi.frankie_raw_mbo_benchmark.native_a_arm_launch"


def steps_of(path: Path) -> list[dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step for job in document["jobs"].values() for step in job["steps"]]


class LaunchWorkflowStructureTest(unittest.TestCase):
    def test_every_run_block_is_valid_bash(self):
        """D57: an unparseable step is reported by GitHub as a jobless failed run."""
        for arm, path in WORKFLOWS.items():
            for step in steps_of(path):
                body = step.get("run")
                if not body:
                    continue
                with self.subTest(arm=arm, step=step.get("name")):
                    with tempfile.NamedTemporaryFile("w", suffix=".sh") as handle:
                        handle.write(body)
                        handle.flush()
                        result = subprocess.run(
                            ["bash", "-n", handle.name], capture_output=True, text=True
                        )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_embedded_python_heredoc_compiles(self):
        """A workflow that ships broken Python fails at the far end of a long fetch."""
        pattern = re.compile(r"python3? - <<'PY'\n(.*?)\n\s*PY(?:\n|$)", re.DOTALL)
        found = 0
        for arm, path in WORKFLOWS.items():
            for step in steps_of(path):
                body = step.get("run") or ""
                for block in pattern.findall(body):
                    found += 1
                    with self.subTest(arm=arm, step=step.get("name")):
                        ast.parse(textwrap.dedent(block))
        self.assertGreater(found, 0, "the heredoc pattern stopped matching anything")


class LaunchWorkflowDispatchTest(unittest.TestCase):
    def test_both_workflows_invoke_the_launcher(self):
        """The whole of T4: before this, neither file dispatched any compute at all."""
        for arm, path in WORKFLOWS.items():
            with self.subTest(arm=arm):
                self.assertIn(LAUNCHER, path.read_text(encoding="utf-8"))

    def test_the_canary_runs_the_arm_it_belongs_to(self):
        for arm, path in WORKFLOWS.items():
            with self.subTest(arm=arm):
                self.assertIn(f"ARM_ID: {arm}", path.read_text(encoding="utf-8"))

    def test_the_canary_is_bounded_and_is_the_default_mode(self):
        """Prelaunch section 0 item 9: a small slice BEFORE anything touches the roster."""
        for arm, path in WORKFLOWS.items():
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            # PyYAML resolves the bare `on:` key to boolean True. Accept either.
            triggers = document.get("on", document.get(True))
            with self.subTest(arm=arm):
                self.assertEqual(triggers["workflow_dispatch"]["inputs"]["mode"]["default"], "canary")
                canary = next(
                    s for s in steps_of(path) if "canary traversal" in (s.get("name") or "")
                )
                self.assertIn("--limit-records", canary["run"])

    def test_the_full_roster_step_cannot_be_reached_by_a_push(self):
        """Starting the box is a spend, and D58 leaves the sizing decision with Greg.

        The guard is asserted on BOTH limbs. `inputs.mode == 'full'` alone would be true on a
        push, where `inputs` is empty and the comparison is against an unset value - which is
        exactly the kind of condition that looks like a guard and is not one.
        """
        for arm, path in WORKFLOWS.items():
            dispatch = next(
                s for s in steps_of(path) if "full-roster" in (s.get("name") or "")
            )
            condition = dispatch["if"]
            with self.subTest(arm=arm):
                self.assertIn("github.event_name == 'workflow_dispatch'", condition)
                self.assertIn("inputs.mode == 'full'", condition)
                self.assertIn("&&", condition)

    def test_the_full_roster_step_drives_the_box_over_ssm(self):
        for arm, path in WORKFLOWS.items():
            dispatch = next(
                s for s in steps_of(path) if "full-roster" in (s.get("name") or "")
            )
            with self.subTest(arm=arm):
                self.assertRegex(dispatch["env"]["INSTANCE_ID"], r"^i-[0-9a-f]+$")
                self.assertIn("aws ssm send-command", dispatch["run"])
                self.assertIn("AWS-RunShellScript", dispatch["run"])
                self.assertIn("get-command-invocation", dispatch["run"])
                # FIRE AND RETURN. It used to wait, with a one-hour SSM timeout and a
                # three-hour poll, against a run measured at four to five hours - and a
                # GitHub job is hard capped at 360 minutes anyway, so waiting could never
                # work. It now confirms the box ACCEPTED the command and exits.
                self.assertIn("--timeout-seconds 43200", dispatch["run"])
                self.assertIn("InProgress", dispatch["run"])
                # The remote command still ECHOES a completion marker - that is the box's
                # own log line. What must not come back is the workflow GREPPING for it,
                # which is the waiting this replaced.
                self.assertNotIn(
                    'grep -F "A_ARM_TRAVERSAL_COMPLETE', dispatch["run"],
                    "the step is waiting for completion again",
                )

    def test_the_remote_command_reads_the_arm_from_its_own_env_var(self):
        """It read `os.environ["A_CLEAN"]` - the VALUE as a key - and would KeyError on
        dispatch. Never fired, so it was never seen."""
        for arm, path in WORKFLOWS.items():
            with self.subTest(arm=arm):
                body = path.read_text(encoding="utf-8")
                self.assertIn('os.environ["ARM_ID"]', body)
                self.assertNotIn(f'os.environ["{arm}"]', body)

    def test_the_canary_summary_reads_the_artifact_rather_than_restating_it(self):
        """A summary that says a run passed without reading what it wrote attests nothing."""
        for arm, path in WORKFLOWS.items():
            report = next(
                s for s in steps_of(path) if "canary verdict" in (s.get("name") or "")
            )
            with self.subTest(arm=arm):
                self.assertIn("calculation_result.json", report["run"])
                self.assertIn("failed_gates", report["run"])


if __name__ == "__main__":
    unittest.main()
