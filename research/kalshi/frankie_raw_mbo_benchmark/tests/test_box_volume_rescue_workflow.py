"""Does the box get its disk back after a failure at every point of the rescue?

**Why this is a test and not a careful reading.** Between the detach and the reattach the box
has NO ROOT VOLUME. A review of the first draft found that a failure in that window left the
300 GiB root volume sitting `available` while the instance stayed stopped and rootless, with
every error swallowed - the exact condition the workflow exists to repair. Reading the script
had not found it; running it did. S113's NC-3 is the same lesson from the other side: a guard
whose firing branch never executed is not a tested guard.

**How.** The workflow's own step text is extracted from the committed YAML and run verbatim
against a stub `aws` that keeps just enough EC2/SSM state to answer one question. The stub
models the fact the review turned on: **a MOUNTED volume does not detach**, and terminating
the helper is what releases it. Failures are injected at each point and the post-condition is
always the same - the volume ends attached to the box, at its original root device.

`sleep` is stubbed to return immediately. That changes how long the script takes, never what
it does.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOW = REPO / ".github/workflows/frankie_box_volume_rescue_20260902.yml"
STUB_SOURCE = Path(__file__).parent / "rescue_aws_stub_source.txt"
BOX = "i-08cee7171c0a76a04"
VOLUME = "vol-05a0b1e56f8c16478"
ROOT_DEV = "/dev/sda1"


def _step(name_prefix: str) -> str:
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in spec["jobs"]["rescue"]["steps"]:
        if step["name"].startswith(name_prefix):
            return step["run"]
    raise AssertionError(f"no step starting {name_prefix!r}")


class RescueFailurePathTests(unittest.TestCase):
    """One post-condition, six ways in: the volume ends on the box."""

    def _run(self, fail: str):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            stub = work / "aws"
            stub.write_text(STUB_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
            stub.chmod(0o755)
            napper = work / "sleep"
            napper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            napper.chmod(0o755)

            state = work / "state.json"
            state.write_text(json.dumps({
                "attached_to": BOX, "box": "running", "helper": None,
                "helper_state": "none", "helper_terminated": False,
                "mounted": False, "last_device": ROOT_DEV,
            }), encoding="utf-8")

            env = dict(
                os.environ, PATH=f"{work}:{os.environ['PATH']}",
                SIM_STATE=str(state), SIM_FAIL_AT=("" if fail == "none" else fail),
                INSTANCE_ID=BOX, VOLUME=VOLUME, ROOT_DEV=ROOT_DEV,
                AZ="us-east-2b", SUBNET="subnet-0e68", SGS="sg-0001", CONFIRM="RESCUE",
                PROFILE_ARN="arn:aws:iam::568968024170:instance-profile/Ssm",
                ROOT_DELETE_ON_TERMINATION="True",
                CLEAR_PATH="/opt/frankie-a-arm-run",
                GITHUB_STEP_SUMMARY=str(work / "summary.md"),
            )
            proc = subprocess.run(["bash", "-c", _step("Move the disk")], cwd=work, env=env,
                                  capture_output=True, text=True, timeout=300)
            return json.loads(state.read_text(encoding="utf-8")), proc

    def _assert_disk_returned(self, fail: str):
        state, proc = self._run(fail)
        self.assertEqual(
            state["attached_to"], BOX,
            f"failure at {fail!r} left the volume on {state['attached_to']!r}; "
            f"the box would be stopped with no root device.\n{proc.stdout[-800:]}"
        )
        self.assertEqual(state["last_device"], ROOT_DEV)
        if state["helper"]:
            self.assertTrue(state["helper_terminated"], "the helper was left running")

    def test_a_clean_run_returns_the_disk(self):
        self._assert_disk_returned("none")
        state, proc = self._run("none")
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(state["box_started_again"])
        self.assertTrue(state["dot_restored"], "DeleteOnTermination was not put back")

    def test_a_failed_stop_never_detaches(self):
        self._assert_disk_returned("stop")

    def test_a_refused_run_instances_returns_the_disk(self):
        # iam:PassRole denied is the likeliest real version of this.
        self._assert_disk_returned("run_instances")

    def test_a_helper_that_never_registers_returns_the_disk(self):
        self._assert_disk_returned("helper_offline")

    def test_a_failed_attach_to_the_helper_returns_the_disk(self):
        self._assert_disk_returned("attach_helper")

    def test_a_failure_with_the_filesystem_still_mounted_returns_the_disk(self):
        """The one the review found, and the one a careful reading missed.

        The first draft tried to detach from the helper first. A mounted volume will not
        detach, the reattach then failed VolumeInUse, and the terminate that would have
        released it ran afterwards - so the volume ended up detached and the box rootless.
        """
        self._assert_disk_returned("box_script")


class ClearPathGuardTests(unittest.TestCase):
    """The path is pasted into a script that runs as root on someone else's disk."""

    def _guard(self, path: str) -> int:
        env = dict(os.environ, CONFIRM="RESCUE", CLEAR_PATH=path, VOLUME=VOLUME)
        return subprocess.run(["bash", "-c", _step("Refuse an unarmed")],
                              env=env, capture_output=True, text=True).returncode

    def test_the_intended_paths_are_accepted(self):
        for path in ("/opt/frankie-a-arm-run",
                     "/opt/frankie-a-arm-run/ledgers",
                     "/opt/frankie-a-arm-run/checkpoints/2026-09-02"):
            self.assertEqual(self._guard(path), 0, path)

    def test_command_substitution_and_separators_are_refused(self):
        for path in ("/opt/frankie-a-arm-run/x; touch /tmp/pwned; :",
                     "/opt/frankie-a-arm-run/$(touch /tmp/pwned)",
                     "/opt/frankie-a-arm-run/`id`",
                     "/opt/frankie-a-arm-run/'"):
            self.assertNotEqual(self._guard(path), 0, path)

    def test_a_newline_is_refused(self):
        """Found by running the guard, not by reading it.

        `grep -E` matches line by line, so a value carrying a newline passed on the strength
        of its first line - and `splitlines()` downstream would have made the second line its
        own SSM command. The check is `-z` now, so the whole string is one record.
        """
        self.assertNotEqual(self._guard("/opt/frankie-a-arm-run/x\ntouch /tmp/pwned"), 0)
        self.assertNotEqual(self._guard("/opt/frankie-a-arm-run\n/opt/frankie-a-arm-run"), 0)

    def test_dot_dot_is_refused(self):
        """Also found by running it: `.` is an allowed path character, so the allowlist
        admitted `/opt/frankie-a-arm-run/../../etc`, and the box-side glob does not
        normalise. An explicit refusal now sits on both sides."""
        for path in ("/opt/frankie-a-arm-run/../../etc", "/opt/frankie-a-arm-run/.."):
            self.assertNotEqual(self._guard(path), 0, path)

    def test_paths_outside_the_run_directory_are_refused(self):
        for path in ("/etc", "/opt/frankie-a-arm-runX", "", "/opt"):
            self.assertNotEqual(self._guard(path), 0, path)

    def test_the_box_side_backstop_refuses_dot_dot_on_its_own(self):
        body = re.search(r"<<'SH'\n(.*?)\nSH\n", _step("Move the disk"), re.S).group(1)
        fragment = body[body.index("target='"):body.index("if [ -d")]
        proc = subprocess.run(
            ["bash", "-c", fragment.replace("__CLEAR_PATH__", "/opt/frankie-a-arm-run/../../etc")
             + "\necho REACHED_THE_CLEAR"],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("RESCUE_FATAL=path_contains_dotdot", proc.stdout)
        self.assertNotIn("REACHED_THE_CLEAR", proc.stdout)


class PushCannotActTests(unittest.TestCase):
    """A push registers the workflow. It must not be able to stop or clear anything."""

    def test_only_the_read_only_report_runs_on_a_push(self):
        spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        for step in spec["jobs"]["rescue"]["steps"]:
            acting = step["name"] != "Report the box and its volume"
            condition = str(step.get("if", ""))
            if acting:
                self.assertIn("workflow_dispatch", condition, step["name"])
                self.assertIn("rescue", condition, step["name"])
            else:
                self.assertEqual(condition, "", "the report is the only push-reachable step")

    def test_no_builtin_waiter_survives(self):
        """`ssm wait command-executed` gives up after 100s - far less than a du plus a
        recursive clear of ~232 GB - and its expiry would send the trap in to pull the disk
        out from under a running delete. Every wait here is an explicit poll instead."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("aws ssm wait", text)
        self.assertNotIn("aws ec2 wait", text)

    def test_concurrency_is_declared_and_does_not_cancel(self):
        spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("concurrency", spec)
        self.assertFalse(spec["concurrency"]["cancel-in-progress"],
                         "cancellation inside the detached window is the dangerous state")


if __name__ == "__main__":
    unittest.main()


class DeviceSelectionTests(unittest.TestCase):
    """The box script must end up with a real device path, not lsblk's tree drawing.

    Run 33604642708 failed here on the live box: `lsblk -bnpo` draws a TREE, so the child
    row arrived as `|-/dev/nvme1n1p1`, the name was taken verbatim, and the next lsblk said
    "not a block device". The trap restored the volume correctly, which is the only reason
    this was a wasted two minutes rather than a stranded instance.
    """

    def _fragment(self) -> str:
        body = re.search(r"<<'SH'\n(.*?)\nSH\n", _step("Move the disk"), re.S).group(1)
        return body[body.index('echo "RESCUE_DISK'):body.index("root=$(findmnt")]

    def _run_with_stub_lsblk(self, fragment: str):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            # A stub that behaves like the real one: tree output unless -l is asked for.
            (work / "lsblk").write_text(
                "#!/bin/sh\n"
                'case "$*" in\n'
                "  *-blnpo*) cat <<'EOF'\n"
                "/dev/nvme1n1 322122547200 disk\n"
                "/dev/nvme1n1p1 322121498624 part\n"
                "EOF\n"
                "  ;;\n"
                "  *-bnpo*) cat <<'EOF'\n"
                "/dev/nvme1n1 322122547200 disk\n"
                "|-/dev/nvme1n1p1 322121498624 part\n"
                "EOF\n"
                "  ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n", encoding="utf-8")
            (work / "lsblk").chmod(0o755)
            env = dict(os.environ, PATH=f"{work}:{os.environ['PATH']}")
            return subprocess.run(["bash", "-c", f'disk=/dev/nvme1n1\n{fragment}\necho "PICKED=$dev"'],
                                  env=env, capture_output=True, text=True)

    def test_the_partition_is_selected_as_a_clean_device_path(self):
        proc = self._run_with_stub_lsblk(self._fragment())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PICKED=/dev/nvme1n1p1", proc.stdout)
        self.assertNotIn("|-", proc.stdout)

    def test_the_guard_refuses_a_name_that_is_not_a_path(self):
        # The same fragment with the tree-drawing flags put back: the guard must catch what
        # the missing -l lets through, rather than passing it to the next command.
        proc = self._run_with_stub_lsblk(self._fragment().replace("-blnpo", "-bnpo"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("RESCUE_FATAL=device_name_is_not_a_path", proc.stdout)
