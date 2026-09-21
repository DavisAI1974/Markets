"""BR-0: the pinned producers (lineage ccode/frankie-receiver-feed-20260916 at 2ebb8ce8) are reached through an in-repo
gitignored worktree made by deploy/aws/box/producers_checkout.sh; never a scratchpad (Greg, 2026-09-21)."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _producers as P  # noqa: E402


def test_the_script_is_committed_and_pins_the_lineage_commit_and_the_driver_hash():
    text = P.CHECKOUT_SCRIPT.read_text(encoding='utf-8')
    assert P.PIN in text and P.LINEAGE in text and P.DRIVER_SHA256 in text
    assert f'.producers-{P.PIN[:8]}' in text
    assert 'git worktree add' in text and '--detach' in text
    assert 'set -euo pipefail' in text
    assert subprocess.run(['bash', '-n', str(P.CHECKOUT_SCRIPT)]).returncode == 0


def test_the_worktree_directory_is_gitignored():
    ignore = (P.REPO / '.gitignore').read_text(encoding='utf-8').splitlines()
    assert '.producers-*/' in ignore


def test_producers_root_defaults_to_the_repo_worktree(monkeypatch):
    monkeypatch.delenv('FRANKIE_BOX_PRODUCERS', raising=False)
    assert P.producers_root() == P.REPO / '.producers-2ebb8ce8'
    monkeypatch.setenv('FRANKIE_BOX_PRODUCERS', '/elsewhere/producers')
    assert P.producers_root() == Path('/elsewhere/producers')


def test_require_producers_fails_when_the_variable_names_an_absent_path(monkeypatch, tmp_path):
    monkeypatch.setenv('FRANKIE_BOX_PRODUCERS', str(tmp_path / 'absent'))
    with pytest.raises(pytest.fail.Exception) as info:
        P.require_producers()
    assert 'FRANKIE_BOX_PRODUCERS' in str(info.value) and 'producers_checkout.sh' in str(info.value)


def test_require_producers_skips_with_the_reason_when_unset_and_absent(monkeypatch, tmp_path):
    monkeypatch.delenv('FRANKIE_BOX_PRODUCERS', raising=False)
    monkeypatch.setattr(P, 'DEFAULT_ROOT', tmp_path / 'absent')
    with pytest.raises(pytest.skip.Exception) as info:
        P.require_producers()
    assert 'FRANKIE_BOX_PRODUCERS unset' in str(info.value) and 'producers_checkout.sh' in str(info.value)


def test_the_worktree_is_at_the_pin_and_the_driver_bytes_match():
    root = P.require_producers()
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    assert head == P.PIN
    assert hashlib.sha256((root / P.DRIVER).read_bytes()).hexdigest() == P.DRIVER_SHA256


def test_the_script_run_again_is_idempotent_and_leaves_one_worktree():
    root = P.require_producers()
    if root != P.DEFAULT_ROOT:
        pytest.skip('the idempotence run targets the repo default worktree only')
    before = subprocess.run(['git', 'worktree', 'list', '--porcelain'], cwd=P.REPO, capture_output=True, text=True, check=True).stdout
    run = subprocess.run(['bash', str(P.CHECKOUT_SCRIPT)], cwd=P.REPO, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert P.PIN in run.stdout and P.DRIVER_SHA256 in run.stdout
    after = subprocess.run(['git', 'worktree', 'list', '--porcelain'], cwd=P.REPO, capture_output=True, text=True, check=True).stdout
    assert after == before
    assert sum(1 for line in after.splitlines() if line.startswith('worktree ') and line.endswith(f'.producers-{P.PIN[:8]}')) == 1
