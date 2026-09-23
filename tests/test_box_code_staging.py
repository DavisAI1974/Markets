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

def test_inventory_disables_git_filters_and_fsmonitor(tmp_path, source, monkeypatch):
    import shlex
    repo, _ = source
    (repo/'.gitattributes').write_text('tracked.txt filter=tripwire\n')
    git(repo,'add','.'); git(repo,'commit','-qm','attributes')
    marker=tmp_path/'executed'
    command='sh -c '+shlex.quote('touch '+shlex.quote(str(marker))+'; cat')
    git(repo,'config','filter.tripwire.clean',command)
    git(repo,'config','filter.tripwire.process',command)
    git(repo,'config','filter.tripwire.required','true')
    git(repo,'config','core.fsmonitor',command)
    (repo/'tracked.txt').write_text('force a worktree comparison\n')
    root=tmp_path/'box'; root.mkdir(); repo.rename(root/'markets')
    monkeypatch.setattr(stage_code,'ROOT',root)
    monkeypatch.setattr(stage_code,'CODE_PARENT',root/'code')
    monkeypatch.setattr(stage_code,'service_state',lambda: [])
    result=stage_code.inventory()
    assert result['checkout']['tracked_dirty'] is True
    assert not marker.exists()

@pytest.mark.parametrize('redirect', ['gitfile','symlink','commondir','alternates','include','worktree_config'])
def test_git_metadata_redirection_refuses(tmp_path,source,redirect):
    repo,commit=source
    external=tmp_path/'external-git'
    if redirect in ('gitfile','symlink'):
        (repo/'.git').rename(external)
        if redirect=='gitfile': (repo/'.git').write_text('gitdir: '+str(external)+'\n')
        else: (repo/'.git').symlink_to(external,target_is_directory=True)
    elif redirect=='commondir':
        (repo/'.git'/'commondir').write_text(str(tmp_path)+'\n')
    elif redirect=='alternates':
        (repo/'.git'/'objects'/'info'/'alternates').write_text(str(tmp_path)+'\n')
    elif redirect=='include':
        git(repo,'config','include.path',str(tmp_path/'private-config'))
    else:
        (repo/'.git'/'config.worktree').write_text('[core]\nworktree=/outside\n')
    with pytest.raises(ValueError):
        stage_code.clean_checkout(repo,commit)

def test_stage_rejects_symlink_in_a_valid_foreign_pack_before_checkout(tmp_path,source,monkeypatch):
    repo,_=source
    (repo/'escape').symlink_to('/outside')
    git(repo,'add','.'); git(repo,'commit','-qm','symlink')
    commit=git(repo,'rev-parse','HEAD')
    objects=git(repo,'rev-list','--objects','--no-object-names',commit)
    pack=tmp_path/'foreign.pack'
    with pack.open('wb') as stream:
        subprocess.run(['git','-C',str(repo),'pack-objects','--stdout','--no-reuse-delta'],
                       input=(objects+'\n').encode(),stdout=stream,check=True)
    parent=tmp_path/'code'; monkeypatch.setattr(stage_code,'CODE_PARENT',parent)
    with pytest.raises(ValueError,match='mode'):
        stage_code.stage(pack,hashlib.sha256(pack.read_bytes()).hexdigest(),commit,'links')
    root=parent/(commit+'-links')
    assert (root/'staging-intent.json').exists()
    assert not (root/'staging-receipt.json').exists()
    assert not (root/'markets'/'escape').exists()
    assert not (root/'markets'/'escape').is_symlink()

def test_shell_bootstrap_executes_only_checked_bytes_in_isolated_python():
    import base64
    code=b'import sys\nassert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode\nprint("BOOTSTRAP_OK",sys.argv[1:])\n'
    env=dict(os.environ,ACTION='inventory',MARKETS_SHA='a'*40,
             CODE_B64=base64.b64encode(code).decode(),CODE_SHA256=hashlib.sha256(code).hexdigest())
    result=subprocess.run(['sh',str(SOURCE.with_suffix('.sh'))],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert "BOOTSTRAP_OK ['inventory', '--commit', '"+'a'*40+"']" in result.stdout

def test_live_staging_workflow_requires_explicit_dispatch_and_exact_source():
    workflow=SOURCE.parents[3]/'.github/workflows/frankie_stage_code.yml'
    body=workflow.read_text()
    assert '  workflow_dispatch:' in body
    assert '\n  push:' not in body and '\n  pull_request:' not in body
    assert "options: [inventory, stage]" in body
    assert "default: inventory" in body
    assert "MARKETS_SHA=commit" in body and "CODE_SHA256=hashlib.sha256(helper).hexdigest()" in body
    assert "IfNoneMatch='*'" in body and "ChecksumSHA256=" in body
    assert "deploy/aws/ssm_run_sh.py" in body
    assert "get_parameter" not in body and "stop_instances" not in body

def test_pack_rejects_attribute_normalization_that_git_diff_calls_clean(tmp_path,source):
    repo,_=source
    (repo/'.gitattributes').write_bytes(b'*.txt text eol=crlf\n')
    git(repo,'add','.'); git(repo,'commit','-qm','newline attributes')
    commit=git(repo,'rev-parse','HEAD')
    (repo/'tracked.txt').write_bytes(b'exact source\r\n')
    assert git(repo,'diff','--exit-code','HEAD')==''
    with pytest.raises(ValueError,match='raw blob'):
        stage_code.create_pack(repo,commit,tmp_path/'source.pack')

def test_stage_refuses_checkout_attribute_transform_and_retains_intent(tmp_path,source,monkeypatch):
    repo,_=source
    (repo/'.gitattributes').write_bytes(b'*.txt text eol=crlf\n')
    git(repo,'add','.'); git(repo,'commit','-qm','newline attributes')
    commit=git(repo,'rev-parse','HEAD')
    pack,checksum,_=packed(tmp_path,(repo,commit))
    parent=tmp_path/'code'; monkeypatch.setattr(stage_code,'CODE_PARENT',parent)
    with pytest.raises(ValueError,match='raw blob'):
        stage_code.stage(pack,checksum,commit,'crlf')
    root=parent/(commit+'-crlf')
    assert (root/'staging-intent.json').exists()
    assert not (root/'staging-receipt.json').exists()

def test_pack_rejects_executable_bit_hidden_by_git_config(tmp_path,source):
    repo,commit=source
    git(repo,'config','core.filemode','false')
    (repo/'tracked.txt').chmod(0o755)
    assert git(repo,'diff','--exit-code','HEAD')==''
    with pytest.raises(ValueError,match='raw mode'):
        stage_code.create_pack(repo,commit,tmp_path/'source.pack')

def test_ssm_payload_fits_reserved_document_budget():
    import base64
    runner=SOURCE.parents[3]/'deploy/aws/ssm_run_sh.py'
    runner_spec=importlib.util.spec_from_file_location('ssm_staging_fixture',runner)
    module=importlib.util.module_from_spec(runner_spec); runner_spec.loader.exec_module(module)
    helper=SOURCE.read_bytes()
    variables=dict(ACTION='stage',MARKETS_SHA='a'*40,CODE_B64=base64.b64encode(helper).decode(),
                   CODE_SHA256=hashlib.sha256(helper).hexdigest(),RUN_ID='9'*96,
                   PACK_SHA256='b'*64,PACK_BYTES='999999999999',MAP_URL='https://example.invalid/'+'x'*4096)
    script=module.preamble([name+'='+value for name,value in variables.items()])+SOURCE.with_suffix('.sh').read_text()
    payload=json.dumps(dict(commands=[script],executionTimeout=['1800'])).encode()
    assert len(payload)<=48*1024
    workflow=(SOURCE.parents[3]/'.github/workflows/frankie_stage_code.yml').read_text()
    assert '48*1024' in workflow and 'ssm_parameter_bytes' in workflow
