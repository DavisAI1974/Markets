"""Inactive code staging: disposable Git fixtures, no AWS or live host access."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import pytest

SOURCE = Path(__file__).resolve().parents[1]/'deploy/aws/box/frankie_box_stage_code.py'
spec = importlib.util.spec_from_file_location('stage_code', SOURCE)
stage_code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_code)

def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()

@pytest.fixture
def source(tmp_path):
    repo = tmp_path/'source'; repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    (repo/'tracked.txt').write_bytes(b'exact source\n')
    (repo/'nested').mkdir()
    (repo/'nested'/'module.py').write_bytes(b'VALUE = 1\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'fixture')
    commit = git(repo, 'rev-parse', 'HEAD')
    return repo, commit

def packed(tmp_path, source):
    repo, commit = source
    path = tmp_path/'source.pack'
    stage_code.create_pack(repo, commit, path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), commit

def test_stage_exact_tracked_commit_without_moving_source(tmp_path, source, monkeypatch):
    pack, checksum, commit = packed(tmp_path, source)
    repo, _ = source
    before = {p.relative_to(repo).as_posix(): p.read_bytes()
              for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts}
    parent = tmp_path/'code'; monkeypatch.setattr(stage_code, 'CODE_PARENT', parent)
    result = stage_code.stage(pack, checksum, commit, 'run-1')
    target = parent/(commit+'-run-1')/'markets'
    assert result['status'] == 'staged' and result['commit'] == commit
    assert git(target, 'rev-parse', 'HEAD') == commit
    assert git(target, 'status', '--porcelain', '--untracked-files=all') == ''
    assert git(target, 'ls-files', '--others') == ''
    assert (target/'tracked.txt').read_bytes() == b'exact source\n'
    assert git(repo, 'rev-parse', 'HEAD') == commit
    assert before == {p.relative_to(repo).as_posix(): p.read_bytes()
                      for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts}
    intent = target.parent/'staging-intent.json'
    receipt = json.loads((target.parent/'staging-receipt.json').read_bytes())
    assert receipt['intent_sha256'] == hashlib.sha256(intent.read_bytes()).hexdigest()
    assert receipt['pack_sha256'] == checksum
    assert receipt['code_root'] == str(target)
    with pytest.raises(FileExistsError):
        stage_code.stage(pack, checksum, commit, 'run-1')

def test_pack_contains_only_target_commit_tree_not_ancestor_history(tmp_path, source, monkeypatch):
    repo, first = source
    (repo/'tracked.txt').write_bytes(b'advanced\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'advanced')
    commit = git(repo, 'rev-parse', 'HEAD')
    pack, checksum, _ = packed(tmp_path, (repo, commit))
    monkeypatch.setattr(stage_code, 'CODE_PARENT', tmp_path/'code')
    result = stage_code.stage(pack, checksum, commit, 'run-2')
    target = Path(result['code_root'])
    assert git(target, 'rev-list', '--count', 'HEAD') == '1'
    assert subprocess.run(['git','-C',str(target),'cat-file','-e',first],
                          capture_output=True).returncode != 0
    git(target, 'fsck', '--full')

@pytest.mark.parametrize('kind', ['dirty', 'untracked', 'ignored', 'wrong_commit'])
def test_pack_requires_exact_clean_checkout(tmp_path, source, kind):
    repo, commit = source
    if kind == 'dirty':
        (repo/'tracked.txt').write_bytes(b'changed')
    elif kind == 'untracked':
        (repo/'injected.py').write_bytes(b'raise SystemExit()')
    elif kind == 'ignored':
        (repo/'.git'/'info'/'exclude').write_text('ignored.py\n')
        (repo/'ignored.py').write_text('VALUE=1\n')
    else:
        commit = '0'*40
    with pytest.raises(ValueError):
        stage_code.create_pack(repo, commit, tmp_path/'source.pack')

def test_pack_refuses_tracked_symlink(tmp_path, source):
    repo, commit = source
    (repo/'link').symlink_to('tracked.txt')
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'link')
    with pytest.raises(ValueError, match='mode'):
        stage_code.create_pack(repo, git(repo,'rev-parse','HEAD'), tmp_path/'source.pack')

@pytest.mark.parametrize('change', ['hash','commit','run_id','parent_symlink'])
def test_stage_refuses_bad_inputs_before_intent(tmp_path, source, monkeypatch, change):
    pack, checksum, commit = packed(tmp_path, source)
    parent = tmp_path/'code'
    run_id = 'run-1'
    if change == 'hash': checksum = '0'*64
    elif change == 'commit': commit = 'main'
    elif change == 'run_id': run_id = '../escape'
    else:
        outside = tmp_path/'outside'; outside.mkdir()
        parent.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(stage_code,'CODE_PARENT',parent)
    with pytest.raises(ValueError):
        stage_code.stage(pack, checksum, commit, run_id)
    assert not list(tmp_path.rglob('staging-intent.json'))

def test_interruption_preserves_intent_and_refuses_reuse(tmp_path, source, monkeypatch):
    pack, checksum, commit = packed(tmp_path, source)
    parent = tmp_path/'code'; monkeypatch.setattr(stage_code,'CODE_PARENT',parent)
    original = stage_code.import_pack
    def fail(*args):
        root = parent/(commit+'-run-1')
        assert (root/'staging-intent.json').is_file()
        raise RuntimeError('injected interruption')
    monkeypatch.setattr(stage_code,'import_pack',fail)
    with pytest.raises(RuntimeError):
        stage_code.stage(pack,checksum,commit,'run-1')
    root = parent/(commit+'-run-1')
    intent = (root/'staging-intent.json').read_bytes()
    assert not (root/'staging-receipt.json').exists()
    monkeypatch.setattr(stage_code,'import_pack',original)
    with pytest.raises(FileExistsError):
        stage_code.stage(pack,checksum,commit,'run-1')
    assert (root/'staging-intent.json').read_bytes() == intent

def test_inventory_does_not_create_paths_or_import_target_code(tmp_path, source, monkeypatch):
    repo, commit = source
    root = tmp_path/'box'; root.mkdir()
    repo.rename(root/'markets')
    (root/'markets'/'sitecustomize.py').write_text('raise AssertionError("must not import")\n')
    monkeypatch.setattr(stage_code,'ROOT',root)
    monkeypatch.setattr(stage_code,'CODE_PARENT',root/'code')
    monkeypatch.setattr(stage_code,'service_state',lambda: [])
    before = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    report = stage_code.inventory()
    assert report['checkout']['commit'] == commit
    assert report['checkout']['untracked'] is True
    assert not (root/'code').exists()
    assert before == {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert not list(root.rglob('__pycache__'))

@pytest.mark.parametrize('url', [
    'http://frankie-granite42-568968024170-us-east-1.s3.us-east-1.amazonaws.com/code/a',
    'https://evil.example/code/a',
    'https://frankie-granite42-568968024170-us-east-1.s3.us-east-1.amazonaws.com/code/../a',
    'https://frankie-granite42-568968024170-us-east-1.s3.us-east-1.amazonaws.com/code/%2e%2e/a',
])
def test_capability_validation_refuses_unexpected_origins_and_paths(url):
    with pytest.raises(ValueError):
        stage_code.checked_url(url)

def test_download_is_hash_bound_and_retains_failed_bytes(tmp_path, monkeypatch):
    body = b'wrong pack'
    monkeypatch.setattr(stage_code,'open_url',lambda url: io.BytesIO(body))
    destination = tmp_path/'download.pack'
    url='https://'+stage_code.BUCKET+'.s3.us-east-1.amazonaws.com/code/source.pack'
    with pytest.raises(ValueError,match='hash'):
        stage_code.download(url,destination,len(body),'0'*64)
    assert destination.read_bytes() == body
    with pytest.raises(FileExistsError):
        stage_code.download(url,destination,len(body),'0'*64)

def test_launcher_inventory_checks_reviewed_helper_hash(tmp_path):
    script = SOURCE.with_suffix('.sh')
    subprocess.run(['sh','-n',str(script)],check=True)
    env = dict(os.environ,MARKETS_SHA='a'*40,ACTION='inventory',CODE_B64='eA==',CODE_SHA256='0'*64)
    result = subprocess.run(['sh',str(script)],env=env,capture_output=True,text=True)
    assert result.returncode != 0
    assert 'helper hash' in result.stderr
