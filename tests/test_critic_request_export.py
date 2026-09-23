"""Disposable Linux PowerShell export tests: HTTP is mocked; files are real."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import uuid
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'deploy/aws/host/frankie_host_stage_critic_request.ps1'
CAPABILITY='https://private.example.invalid/request?X-Amz-Signature=SECRET_CAPABILITY_SENTINEL'

def quote(value):
    return "'"+str(value).replace("'","''")+"'"

def sha(body):
    return hashlib.sha256(body).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

@pytest.fixture
def state(tmp_path):
    pwsh=shutil.which('pwsh')
    assert pwsh,'PowerShell is required for isolated source tests'
    day=tmp_path/'days/20211004'
    run=tmp_path/'run'
    request=run/'execution/cycle-00/actual-critic-request.json'
    request.parent.mkdir(parents=True)
    body=b'{"ts_recv":9223372036854775807,"price":-0.0,"label":"exact"}\r\n'
    request.write_bytes(body)
    day.mkdir(parents=True)
    config=day/'actual-host-configuration.json'
    config.write_text(json.dumps(dict(run_directory=str(run),run_id='fixture-run')))
    return SimpleNamespace(tmp=tmp_path,pwsh=pwsh,day=day,run=run,request=request,
                           body=body,expected=sha(body),config=config)

def invoke(state,mode='success',expected=None,url=CAPABILITY):
    marker=state.tmp/('upload-'+uuid.uuid4().hex+'.json')
    capture=state.tmp/('before-upload-'+uuid.uuid4().hex+'.json')
    wrapper=state.tmp/('wrapper-'+uuid.uuid4().hex+'.ps1')
    action={
        'success':'',
        'failure': "throw ('REMOTE_BODY_SECRET_SENTINEL '+$Uri)",
        'interrupt': "[Environment]::Exit(77)",
        'mutate': "[IO.File]::WriteAllBytes($InFile,[Text.Encoding]::UTF8.GetBytes('changed after upload'))",
    }[mode]
    wrapper.write_text(f"""
$ErrorActionPreference = 'Stop'
$Day='20211004'
$RunRoot={quote(state.day.parent)}
$CycleIndex='00'
$ExpectedRequestSha256={quote(state.expected if expected is None else expected)}
$RequestUrl={quote(url)}
function Get-Date {{
    return [DateTime]::Parse('2026-09-23T12:00:00Z').ToUniversalTime()
}}
function Invoke-WebRequest {{
    param([string]$Uri,[string]$Method,[string]$InFile,[switch]$UseBasicParsing)
    $before=@(Get-ChildItem -LiteralPath {quote(state.day)} -Filter 'critic-request-staged-*.intent.json')
    [IO.File]::WriteAllText({quote(capture)},(ConvertTo-Json -InputObject @($before.FullName) -Compress))
    [IO.File]::WriteAllText({quote(marker)},(ConvertTo-Json -InputObject ([ordered]@{{method=$Method;path=$InFile}}) -Compress))
    {action}
}}
. {quote(SCRIPT)}
""",encoding='utf-8')
    result=subprocess.run([state.pwsh,'-NoLogo','-NoProfile','-NonInteractive','-File',str(wrapper)],
                          capture_output=True,text=True,timeout=30)
    return SimpleNamespace(result=result,marker=marker,capture=capture)

def intents(state):
    return sorted(state.day.glob('critic-request-staged-*.intent.json'))

def completions(state):
    return sorted(path for path in state.day.glob('critic-request-staged-*.json')
                  if not path.name.endswith('.intent.json'))

def test_export_records_complete_intent_before_http_and_binds_completion(state):
    got=invoke(state)
    assert got.result.returncode==0,got.result.stdout+got.result.stderr
    before=read(got.capture)
    assert len(before)==1
    intent_path=Path(before[0])
    intent=read(intent_path)
    assert intent['schema']=='FRANKIE_CRITIC_REQUEST_STAGE_INTENT_V1'
    assert intent['day']=='20211004' and intent['run_id']=='fixture-run' and intent['cycle_index']==0
    assert intent['path']==str(state.request)
    assert intent['sha256']==state.expected and intent['bytes']==len(state.body)
    assert intent['configuration_sha256']==sha(state.config.read_bytes())
    done=completions(state)
    assert len(done)==1
    receipt=read(done[0])
    assert receipt['schema']=='FRANKIE_CRITIC_REQUEST_STAGED_V1'
    assert receipt['intent_path']==str(intent_path)
    assert receipt['intent_sha256']==sha(intent_path.read_bytes())
    assert receipt['sha256']==state.expected and receipt['bytes']==len(state.body)
    assert 'EXPORTED actual-critic-request.json bytes='+str(len(state.body))+' sha256='+state.expected in got.result.stdout
    assert state.request.read_bytes()==state.body
    for path in intents(state)+done:
        assert CAPABILITY not in path.read_text() and 'SECRET_CAPABILITY_SENTINEL' not in path.read_text()

def test_same_second_exports_retain_distinct_receipts_and_all_prior_bytes(state):
    first=invoke(state)
    assert first.result.returncode==0,first.result.stderr
    retained={p:p.read_bytes() for p in intents(state)+completions(state)}
    second=invoke(state)
    assert second.result.returncode==0,second.result.stderr
    assert len(intents(state))==2 and len(completions(state))==2
    assert all(path.read_bytes()==body for path,body in retained.items())

@pytest.mark.parametrize('expected',['0'*64,'not-a-hash'])
def test_wrong_expected_hash_refuses_before_upload_or_intent(state,expected):
    got=invoke(state,expected=expected)
    assert got.result.returncode!=0
    assert not got.marker.exists()
    assert not intents(state) and not completions(state)
    assert state.request.read_bytes()==state.body

def test_upload_failure_never_logs_capability_or_remote_error_body(state):
    got=invoke(state,mode='failure')
    combined=got.result.stdout+got.result.stderr
    assert got.result.returncode!=0
    assert 'SECRET_CAPABILITY_SENTINEL' not in combined
    assert 'REMOTE_BODY_SECRET_SENTINEL' not in combined
    assert 'private.example.invalid' not in combined
    assert len(intents(state))==1 and not completions(state)
    assert 'EXPORTED ' not in got.result.stdout

def test_missing_capability_validation_never_echoes_its_value(state):
    got=invoke(state,url='HOST_SECRET_CAPABILITY_SENTINEL')
    assert got.result.returncode!=0
    assert 'SECRET_CAPABILITY_SENTINEL' not in got.result.stdout+got.result.stderr
    assert not got.marker.exists()

def test_interrupted_upload_retains_intent_without_completion(state):
    got=invoke(state,mode='interrupt')
    assert got.result.returncode!=0 and got.marker.exists()
    before=read(got.capture)
    assert len(before)==1 and Path(before[0]).is_file()
    assert not completions(state)
    assert state.request.read_bytes()==state.body

def test_request_changed_during_upload_cannot_receive_completion(state):
    got=invoke(state,mode='mutate')
    assert got.result.returncode!=0 and got.marker.exists()
    assert len(intents(state))==1 and not completions(state)
    assert 'EXPORTED ' not in got.result.stdout
    assert read(intents(state)[0])['sha256']==state.expected
