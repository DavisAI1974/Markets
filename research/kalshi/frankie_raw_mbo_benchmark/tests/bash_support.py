"""Run workflow text without Windows command-line or WSL path reinterpretation."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


def bash_executable() -> str:
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            bash = Path(git).resolve().parent.parent / "bin" / "bash.exe"
            if bash.is_file():
                return str(bash)
        raise RuntimeError("Workflow tests on Windows require Git for Windows Bash")
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("Workflow tests require Bash")
    return bash


def run_bash(script: str, *, syntax_only: bool = False, **kwargs):
    # stdin avoids a shared/open temporary file and the platform's -c quoting rules.
    return subprocess.run(
        [bash_executable(), "--noprofile", "--norc", "-n" if syntax_only else "-s"],
        input=script, capture_output=True, text=True, **kwargs,
    )
