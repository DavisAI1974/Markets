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


def _origin_and_clone(tmp_path, name):
    """A SMALL bare origin (one commit carrying the script) that also carries the pinned lineage tip, fetched shallow from
    this repo, and a --depth 1 clone of it. The pinned tree crosses the wire once, in the first scenario only."""
    origin = tmp_path / 'origin.git'
    if not origin.exists():
        seed = tmp_path / 'seed'
        (seed / 'deploy' / 'aws' / 'box').mkdir(parents=True)
        (seed / 'deploy' / 'aws' / 'box' / 'producers_checkout.sh').write_bytes(P.CHECKOUT_SCRIPT.read_bytes())
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        for cmd in (['git', 'init', '-q', '-b', 'main'], ['git', 'add', '.'], ['git', 'commit', '-q', '-m', 'seed']):
            subprocess.run(cmd, cwd=seed, check=True, capture_output=True, env=env)
        subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True, capture_output=True)
        subprocess.run(['git', 'push', '-q', origin.as_uri(), 'main'], cwd=seed, check=True, capture_output=True)
        subprocess.run(['git', '-C', str(origin), 'fetch', '-q', '--depth', '1', P.REPO.as_uri(), f'{P.PIN}:refs/heads/{P.LINEAGE}'], check=True, capture_output=True)
    clone = tmp_path / name
    subprocess.run(['git', 'clone', '-q', '--depth', '1', '--branch', 'main', origin.as_uri(), str(clone)], check=True, capture_output=True)
    return clone, clone / 'deploy' / 'aws' / 'box' / 'producers_checkout.sh'


def test_the_script_populates_a_shallow_clone_and_refuses_a_plain_directory_or_a_worktree_at_another_commit(tmp_path):
    P.require_producers()
    clone, script = _origin_and_clone(tmp_path, 'shallow')
    assert subprocess.run(['git', '-C', str(clone), 'rev-parse', '--is-shallow-repository'], capture_output=True, text=True).stdout.strip() == 'true'
    run = subprocess.run(['bash', str(script)], cwd=clone, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'producers worktree added' in run.stdout and P.PIN in run.stdout and P.DRIVER_SHA256 in run.stdout
    worktree = clone / f'.producers-{P.PIN[:8]}'
    assert subprocess.run(['git', '-C', str(worktree), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() == P.PIN
    again = subprocess.run(['bash', str(script)], cwd=clone, capture_output=True, text=True)
    assert again.returncode == 0 and 'present at the pin' in again.stdout
    plain, script2 = _origin_and_clone(tmp_path, 'plain')
    (plain / f'.producers-{P.PIN[:8]}').mkdir()
    run = subprocess.run(['bash', str(script2)], cwd=plain, capture_output=True, text=True)
    assert run.returncode == 2 and 'is not the producers worktree (nothing moved)' in run.stdout
    assert (plain / f'.producers-{P.PIN[:8]}').is_dir()
    other, script3 = _origin_and_clone(tmp_path, 'other')
    subprocess.run(['git', '-C', str(other), 'worktree', 'add', '-q', '--detach', str(other / f'.producers-{P.PIN[:8]}'), 'HEAD'], check=True, capture_output=True)
    run = subprocess.run(['bash', str(script3)], cwd=other, capture_output=True, text=True)
    assert run.returncode == 2 and 'not the pinned' in run.stdout and (other / f'.producers-{P.PIN[:8]}').is_dir()
