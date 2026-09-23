"""Execute the actual credential-free workflow validator and Git publication block."""
import json
import os
from pathlib import Path
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/frankie_host_stage_critic_request.yml'


def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def python_block(name):
    steps = [step for job in workflow()['jobs'].values() for step in job.get('steps', [])]
    shell = next(step['run'] for step in steps if step.get('name') == name)
    return shell.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


def bindings():
    return dict(REQUEST_SHA256='a'*64, CYCLE_INDEX='01', INSTANCE='i-0e90ee6110ef609aa',
                DAY='20211004', RUN_ROOT='C:/Codex/Frankie-BOSS-20260919/days',
                BUCKET='frankie-granite42-568968024170-us-east-1',
                KEY_PARAMETER='/markets/frankie/request-transport/test',
                SOURCE_REF='refs/heads/codex/test')


def validate(monkeypatch, changes=None):
    values = bindings()
    values.update(changes or {})
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    exec(compile(python_block('Validate explicit archive bindings before credentials'), '<validator>', 'exec'), {})


def test_call_contract_is_explicit_and_credentials_follow_validation():
    w = workflow()
    triggers = w.get('on', w.get(True))
    expected = {k.lower() for k in bindings()} - {'source_ref'}
    for trigger in ('workflow_dispatch', 'workflow_call'):
        assert set(triggers[trigger]['inputs']) == expected
        assert all(v['required'] is True and v['type'] == 'string' and 'default' not in v
                   for v in triggers[trigger]['inputs'].values())
    assert w['jobs']['stage']['needs'] == 'validate'
    assert w['jobs']['validate']['permissions'] == {}
    assert 'secrets.' not in json.dumps(w['jobs']['validate'])
    assert w['concurrency']['cancel-in-progress'] is False
    assert 'github.ref' in w['concurrency']['group']
    assert set(triggers['workflow_call']['outputs']) == {'archive_commit', 'source_commit', 'request_sha256'}
    assert 'push' not in triggers


def test_valid_explicit_bindings(monkeypatch):
    validate(monkeypatch)


@pytest.mark.parametrize('key,value', [
    ('REQUEST_SHA256', 'A'*64), ('REQUEST_SHA256', '../archive'),
    ('CYCLE_INDEX', '0'), ('DAY', '20210230'), ('DAY', '20211004\n'),
    ('INSTANCE', 'i-other'), ('BUCKET', 'public-other'),
    ('KEY_PARAMETER', '/unrelated/key'), ('RUN_ROOT', 'C:/days/../secret'),
    ('RUN_ROOT', 'C:/days;echo leak'), ('RUN_ROOT', 'C:/days//more'),
    ('SOURCE_REF', 'refs/tags/release'),
])
def test_invalid_bindings_refuse_before_aws(monkeypatch, key, value):
    with pytest.raises(SystemExit):
        validate(monkeypatch, {key: value})


def test_workflow_uses_durable_writer_exact_export_and_retains_only_safe_evidence():
    w = workflow()
    text = WORKFLOW.read_text()
    assert 'write_request_archive(directory, body, expected' in text
    assert 'read_request_archive(directory, expected, ssm)' in text
    assert '--set "ExpectedRequestSha256=$EXPECTED_SHA256"' in text
    assert 'AESGCM(' not in text
    assert 'git rebase' not in text
    retention = next(s for s in w['jobs']['stage']['steps'] if s.get('name') == 'Retain encrypted archive and publication evidence')
    assert retention['if'] == 'always()'
    assert 'request_sha256' in retention['with']['path']
    assert 'archive-publication' in retention['with']['path']
    assert 'request.url' not in retention['with']['path']
    assert 'stage.log' not in retention['with']['path']


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def publication(tmp_path, monkeypatch):
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'codex/test')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'source.txt').write_text('reviewed source\n')
    git(repo, 'add', 'source.txt')
    git(repo, 'commit', '-m', 'baseline')
    git(repo, 'remote', 'add', 'origin', str(remote))
    git(repo, 'push', '-u', 'origin', 'codex/test')
    source = git(repo, 'rev-parse', 'HEAD')
    archive = repo / 'research/kalshi/frankie_boss/runs/request-archives' / ('a'*64)
    archive.mkdir(parents=True)
    (archive / 'envelope.json').write_text('{"verified":"by preceding archive step"}\n')
    (archive / 'request.enc').write_bytes(b'encrypted fixture')
    temporary = tmp_path / 'attempt-1'
    temporary.mkdir()
    output = tmp_path / 'output'
    monkeypatch.chdir(repo)
    for key, value in dict(EXPECTED_SHA256='a'*64, SOURCE_COMMIT=source, BRANCH='codex/test',
                           RUNNER_TEMP=str(temporary), GITHUB_OUTPUT=str(output)).items():
        monkeypatch.setenv(key, value)
    def execute():
        exec(compile(python_block('Publish exact archive or reuse unchanged publication'), '<publication>', 'exec'), {})
    return repo, remote, archive, temporary, output, source, execute


def test_publish_then_verified_replay_creates_no_new_commit(publication, monkeypatch, tmp_path):
    repo, remote, archive, temporary, output, source, execute = publication
    execute()
    first = git(repo, 'rev-parse', 'HEAD')
    assert first != source
    assert git(remote, 'rev-parse', 'refs/heads/codex/test') == first
    assert json.loads((temporary / 'archive-publication.json').read_bytes())['archive_commit'] == first
    assert 'Co-Authored-By: Codex <noreply@openai.com>' in git(repo, 'log', '-1', '--format=%B')
    retained = {p.name: p.read_bytes() for p in archive.iterdir()}
    second = tmp_path / 'attempt-2'
    second.mkdir()
    monkeypatch.setenv('RUNNER_TEMP', str(second))
    monkeypatch.setenv('SOURCE_COMMIT', first)
    execute()
    assert git(repo, 'rev-parse', 'HEAD') == first
    assert json.loads((second / 'archive-publication.json').read_bytes())['changed'] is False
    assert retained == {p.name: p.read_bytes() for p in archive.iterdir()}


def test_stale_source_refuses_without_rebase_or_commit(publication):
    repo, remote, archive, temporary, output, source, execute = publication
    (repo / 'source.txt').write_text('unreviewed advance\n')
    git(repo, 'add', 'source.txt')
    git(repo, 'commit', '-m', 'advanced')
    git(repo, 'push', 'origin', 'codex/test')
    advanced = git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(SystemExit, match='source branch advanced'):
        execute()
    assert git(repo, 'rev-parse', 'HEAD') == advanced
    assert (temporary / 'archive-publication-intent.json').exists()
    assert not output.exists()
    assert (archive / 'request.enc').exists()


def test_unrelated_staged_paths_are_not_published(publication):
    repo, remote, archive, temporary, output, source, execute = publication
    (repo / 'unexpected.txt').write_text('do not publish')
    git(repo, 'add', 'unexpected.txt')
    with pytest.raises(SystemExit, match='unexpected staged path'):
        execute()
    assert git(repo, 'rev-parse', 'HEAD') == source
    assert git(remote, 'rev-parse', 'refs/heads/codex/test') == source


@pytest.mark.parametrize('accepted', [True, False])
def test_ambiguous_push_reconciles_exact_remote_or_retains_failure(publication, monkeypatch, accepted):
    repo, remote, archive, temporary, output, source, execute = publication
    original = subprocess.run
    def uncertain(args, *a, **kw):
        if args[:2] == ['git', 'push']:
            if accepted:
                original(args, *a, **kw)
            return subprocess.CompletedProcess(args, 1, b'', b'uncertain transport')
        return original(args, *a, **kw)
    monkeypatch.setattr(subprocess, 'run', uncertain)
    if accepted:
        execute()
        assert git(remote, 'rev-parse', 'refs/heads/codex/test') == git(repo, 'rev-parse', 'HEAD')
        assert (temporary / 'archive-publication.json').exists()
    else:
        with pytest.raises(SystemExit, match='publication not confirmed'):
            execute()
        assert (temporary / 'archive-publication-intent.json').exists()
        assert not (temporary / 'archive-publication.json').exists()
        assert git(remote, 'rev-parse', 'refs/heads/codex/test') == source
        assert not output.exists()
    assert (archive / 'request.enc').exists()
