"""The real shell checkout helper must use the dispatched immutable revision."""
import os
from pathlib import Path
import subprocess
import sys
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'deploy/aws/box/frankie_box_session.sh'


def shell(root,sha,*,active=False):
    text=SCRIPT.read_text(encoding='utf-8')
    begin=text.index('checkout_markets() {')
    end=text.index('\n}\n',begin)+3
    command=text[begin:end]+'\ncheckout_markets\n'
    env=dict(os.environ,ROOT=str(root),MARKETS_SHA=sha,MARKETS_REF='moving-branch',
        ACTIVE='yes' if active else 'no',PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
    return subprocess.run(['bash','-c',command],env=env,capture_output=True,text=True)


@pytest.fixture
def repo(tmp_path):
    origin=tmp_path/'origin'
    origin.mkdir()
    def git(*args,cwd=origin):
        return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
    git('init','-q')
    git('config','user.email','test@example.invalid')
    git('config','user.name','Offline fixture')
    (origin/'source.txt').write_text('old')
    git('add','source.txt');git('commit','-qm','old')
    old=git('rev-parse','HEAD')
    (origin/'source.txt').write_text('new')
    git('commit','-qam','new')
    new=git('rev-parse','HEAD')
    git('branch','moving-branch',new)
    root=tmp_path/'box';root.mkdir()
    git('clone','-q',str(origin),str(root/'markets'))
    (root/'venv'/'bin').mkdir(parents=True)
    (root/'venv'/'bin'/'python').symlink_to(sys.executable)
    (root/'receipts').mkdir()
    (root/'bin').mkdir()
    ctl=root/'bin'/'systemctl'
    ctl.write_text('#!/bin/sh\nif [ "$ACTIVE" = yes ]; then echo "frankie-cycle-00.service loaded active running"; fi\nexit 0\n')
    ctl.chmod(0o755)
    return root,old,new


def head(root):
    return subprocess.check_output(['git','-C',str(root/'markets'),'rev-parse','HEAD'],text=True).strip()


def test_exact_sha_wins_over_a_moving_branch_and_has_a_prior_intent(repo):
    import json
    root,old,new=repo
    result=shell(root,old)
    assert result.returncode==0,result.stdout+result.stderr
    assert head(root)==old
    intents=list((root/'receipts').glob('markets-checkout-intent-*.json'))
    receipts=list((root/'receipts').glob('markets-checkout-receipt-*.json'))
    assert len(intents)==len(receipts)==1
    intent=json.loads(intents[0].read_bytes());receipt=json.loads(receipts[0].read_bytes())
    assert intent['from_commit']==new and intent['to_commit']==old
    assert receipt['intent_sha256']
    assert receipt['actual_commit']==old


@pytest.mark.parametrize('pin',['','moving-branch','a'*39,'A'*40,'bad;command'])
def test_missing_or_nonimmutable_pin_refuses_without_moving(repo,pin):
    root,old,new=repo
    result=shell(root,pin)
    assert result.returncode!=0
    assert head(root)==new
    assert list((root/'receipts').iterdir())==[]


def test_running_session_prevents_checkout_change(repo):
    root,old,new=repo
    result=shell(root,old,active=True)
    assert result.returncode!=0
    assert head(root)==new


def test_dirty_source_is_not_overwritten(repo):
    root,old,new=repo
    path=root/'markets'/'source.txt';path.write_text('uncommitted evidence')
    result=shell(root,old)
    assert result.returncode!=0
    assert path.read_text()=='uncommitted evidence'
    assert head(root)==new


def test_unknown_pin_refuses_without_running_old_code(repo):
    root,old,new=repo
    result=shell(root,'f'*40)
    assert result.returncode!=0
    assert head(root)==new


def test_script_is_valid_shell_and_checkout_callers_fail_closed():
    subprocess.run(['bash','-n',str(SCRIPT)],check=True)
    text=SCRIPT.read_text(encoding='utf-8')
    assert text.count('checkout_markets || return 2')==5
    assert 'origin -- "$MARKETS_REF"' not in text
