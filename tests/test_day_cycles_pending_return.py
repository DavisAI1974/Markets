"""Run actual day_cycles PowerShell with a fake runner, real config and WAIT receipts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"deploy/aws/host/day_cycles.ps1"

def quote(value):
    return "'"+str(value).replace("'","''")+"'"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

@pytest.fixture
def state(tmp_path):
    pwsh=shutil.which("pwsh")
    assert pwsh,"PowerShell required for isolated wrapper verification"
    run=tmp_path/"run"
    cycle=run/"execution/cycle-00"
    cycle.mkdir(parents=True)
    (run/"native-host-runtime.json").write_text("{}")
    (run/"host-identity.c15.json").write_bytes(b"identity")
    (cycle/"host-preparation.c15.json").write_bytes(b"prepared")
    (cycle/"actual-critic-request.json").write_bytes(b'{"ts_recv":1633302000123456789}')
    day=tmp_path/"days/20211004"
    day.mkdir(parents=True)
    schedule=tmp_path/"schedule.json"
    schedule.write_text(json.dumps(dict(schema="BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1",
        trading_day="20211004",schedule_sha256="b"*64,steps=[{},{}])))
    prefixes=tmp_path/"prefixes.json"
    prefixes.write_text(json.dumps(dict(witnesses=[{},{}])))
    config=dict(run_id="fixture-run",run_directory=str(run),trading_day="20211004",
        trading_day_schedule=dict(schedule_sha256="b"*64),
        host_runtime=dict(repository=str(ROOT),boss_commit="a"*40,
            pod_credential_ssm=dict(name="/fixture/secret",region="us-east-1",trigger_directory=str(tmp_path/"trigger")),
            prefixes_directory=str(tmp_path),prefix_manifest=dict(path=str(prefixes)),
            schedule=dict(path=str(schedule),sha256=sha(schedule.read_bytes()))))
    configuration=day/"prepared.json"
    configuration.write_text(json.dumps(config))
    spec=importlib.util.spec_from_file_location("ps_wait_fixture",ROOT/"research/kalshi/frankie_boss/operations/workflow_wait.py")
    helper=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=helper
    spec.loader.exec_module(helper)
    outcome=helper.write_wait_receipt(config,cycle,"readiness")
    return dict(tmp=tmp_path,pwsh=pwsh,run=run,day=day,config=config,
        configuration=configuration,outcome=outcome,helper=helper,cycle=cycle)

def invoke(state, *, code=3, outcome=None, pending=True, resume=None):
    marker=state["tmp"]/("command-"+uuid.uuid4().hex+".txt")
    wrapper=state["tmp"]/("wrapper-"+uuid.uuid4().hex+".ps1")
    value=state["outcome"] if outcome is None else outcome
    status=json.dumps(value)
    wrapper.write_text(f"""
$ErrorActionPreference='Stop'
$Day='20211004'
$ToolsRoot={quote(ROOT)}
$Python={quote(sys.executable)}
$RunRoot={quote(state["day"].parent)}
$RequirePreparedConfiguration='1'
$PreparedConfigurationPath={quote(state["configuration"])}
$PreparedConfigurationSha256={quote(sha(state["configuration"].read_bytes()))}
$ExpectedTradingDayScheduleSha256={'"b"*64' if False else quote("b"*64)}
$CycleLimit=2
{"$PendingReturn='1'" if pending else ""}
{"$ResumeWaitSha256="+quote(resume) if resume is not None else ""}
function cmd.exe {{
    $line=$args -join ' '
    [IO.File]::WriteAllText({quote(marker)},$line)
    $match=[regex]::Match($line,'> "([^"]+)"')
    if(-not $match.Success){{throw 'test requires runner log destination'}}
    [IO.File]::WriteAllText($match.Groups[1].Value,{quote(status)}+[Environment]::NewLine)
    $global:LASTEXITCODE={code}
}}
. {quote(SCRIPT)}
""",encoding="utf-8")
    result=subprocess.run([state["pwsh"],"-NoLogo","-NoProfile","-NonInteractive","-File",str(wrapper)],
        capture_output=True,text=True,timeout=30)
    lines=[line[len("PIPELINE_RECEIPT "):] for line in result.stdout.splitlines() if line.startswith("PIPELINE_RECEIPT ")]
    return dict(result=result,marker=marker,receipt=json.loads(lines[-1]) if lines else None)

def test_valid_pending_return_emits_bound_wait_without_claiming_completion(state):
    got=invoke(state)
    assert got["result"].returncode==0,got["result"].stdout+got["result"].stderr
    receipt=got["receipt"]
    assert receipt["status"]=="workflow_wait"
    assert receipt["wait_receipt"]==state["outcome"]["wait_receipt"]
    assert receipt["receipt_sha256"]==state["outcome"]["receipt_sha256"]
    assert receipt["prepared_configuration_sha256"]==sha(state["configuration"].read_bytes())
    assert receipt["day"]=="20211004" and receipt["run_id"]=="fixture-run"
    assert receipt["run_directory"]==str(state["run"])
    assert receipt["schedule_sha256"]=="b"*64
    assert receipt["requested_cycles"]==receipt["cycles_total"]==2
    assert "cycles_completed" not in receipt
    assert "--pending-return" in got["marker"].read_text()

def test_resume_passes_exact_wait_pin_to_same_existing_native_run(state):
    got=invoke(state,resume=state["outcome"]["receipt_sha256"])
    assert got["result"].returncode==0,got["result"].stderr
    command=got["marker"].read_text()
    assert "--ec2-resume" in command
    assert "--resume-wait-sha256 "+state["outcome"]["receipt_sha256"] in command
    assert str(state["configuration"]) in command

@pytest.mark.parametrize("code",[1,2,5])
def test_nonpending_exit_codes_cannot_be_relabelled_as_lawful_wait(state,code):
    got=invoke(state,code=code)
    assert got["result"].returncode!=0
    assert got["receipt"] is None

def test_pending_requires_opt_in(state):
    got=invoke(state,pending=False)
    assert got["result"].returncode!=0 and got["receipt"] is None

def test_exit_code_and_wait_state_must_agree(state):
    got=invoke(state,code=4)
    assert got["result"].returncode!=0 and got["receipt"] is None

def test_attention_remains_attention_and_keeps_exact_job(state):
    outcome=state["helper"].write_wait_receipt(state["config"],state["cycle"],"same_job",state="ATTENTION",job_id="c"*64)
    got=invoke(state,code=4,outcome=outcome)
    assert got["result"].returncode==0,got["result"].stderr
    assert got["receipt"]["status"]=="workflow_attention"
    assert got["receipt"]["wait_receipt"]["job_id"]=="c"*64
    assert "cycles_completed" not in got["receipt"]

def test_changed_retained_request_refuses_receipt_before_pipeline_admission(state):
    (state["cycle"]/"actual-critic-request.json").write_bytes(b"other request")
    got=invoke(state)
    assert got["result"].returncode!=0 and got["receipt"] is None

def test_missing_wait_file_refuses_pending_status(state):
    path=Path(state["outcome"]["receipt_path"])
    path.rename(path.with_name("fixture-retained.json"))
    got=invoke(state)
    assert got["result"].returncode!=0 and got["receipt"] is None

@pytest.mark.parametrize("pin",["bad","0"*63,"A"*64])
def test_bad_resume_pin_refuses_before_runner(state,pin):
    got=invoke(state,resume=pin)
    assert got["result"].returncode!=0
    assert not got["marker"].exists()

def test_pending_status_cannot_claim_unverified_embedded_receipt(state):
    value=dict(state["outcome"])
    value["wait_receipt"]=dict(value["wait_receipt"],run_id="foreign")
    got=invoke(state,outcome=value)
    assert got["result"].returncode!=0 and got["receipt"] is None
