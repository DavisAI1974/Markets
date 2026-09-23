"""Actual DayPipeline continuation behavior with an isolated SSM process boundary."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("continuation_day_pipeline", ROOT / "research/kalshi/frankie_boss/operations/day_pipeline.py")
dp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dp)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

@pytest.fixture
def state(tmp_path):
    config = dict(python="py", ssm_run="ssm.py", ec2_host="ec2.py", instance="i-fixture", region="us-east-1",
        stage_block_sources="stage.py", upload_restore_set="upload.py", block="fixture", archive="archive",
        bucket="fixture", blocks_dir="blocks", restore_prefix="fixture", pending_return=True,
        host_scripts=dict(ingest="ingest.ps1", schedule_prefixes="prefix.ps1", cycles="cycles.ps1"),
        workflow_run=dict(run_id="retained-run", run_directory="/retained/run", boss_commit="f"*40,
            configuration_sha256="e"*64,schedule_sha256="b"*64),
        trading_day_schedule=dict(trading_day="20211004", step_count=3, source_record_count=17,
            source_manifest_hash="a"*64, schedule_sha256="b"*64))
    prepared = dict(prefix_count=3, prefixes_sha256="c"*64, day="20211004", source_records=17,
        schedule_sha256="b"*64, configuration=dict(path="/retained/configuration.json", sha256="d"*64, bytes=123))
    wait = dict(schema="FRANKIE_WORKFLOW_WAIT_V1", state="WAIT", kind="readiness",
        run_id="retained-run", run_directory="/retained/run", cycle_index=2, request_id="retained-run-cycle-02",
        configuration_sha256="e"*64, boss_commit="f"*40, schedule_sha256="b"*64, job_id=None,
        artifacts={"host-identity.c15.json":dict(sha256="1"*64, bytes=10),
            "execution/cycle-02/host-preparation.c15.json":dict(sha256="2"*64, bytes=20),
            "execution/cycle-02/actual-critic-request.json":dict(sha256="3"*64, bytes=30)})
    wait["receipt_id"] = digest(wait)
    envelope = dict(status="workflow_wait", day="20211004", requested_cycles=3, cycles_total=3,
        run_id="retained-run", run_directory="/retained/run", prepared_configuration_sha256="d"*64,
        schedule_sha256="b"*64,wait_receipt=wait,
        receipt_path="/retained/run/execution/cycle-02/workflow-wait/readiness.json",
        receipt_sha256=hashlib.sha256(canonical(wait)).hexdigest())
    calls = []
    output = [envelope]
    def runner(argv, *, timeout):
        calls.append(argv)
        if "cycles.ps1" not in argv:
            raise AssertionError("pending continuation invoked a different stage")
        return 0, "PIPELINE_RECEIPT " + json.dumps(output[0])
    pipeline = dp.DayPipeline(config, "20211004", runner=runner, runs_root=tmp_path)
    pipeline.write("stage-sources",dict(manifest="manifest.json",manifest_hash="a"*64,records=17),command=[])
    pipeline.write("host-start",dict(ssm_online=True),command=[])
    pipeline.write("ingest",dict(journal_count=17,journal_hash="1"*64,compact_sha256="2"*64),command=[])
    pipeline.write("schedule-prefixes",prepared,command=[])
    return dict(config=config,prepared=prepared,pipeline=pipeline,output=output,calls=calls,tmp=tmp_path,envelope=envelope)

def reopen(state, **changes):
    config = copy.deepcopy(state["config"])
    config.update(changes)
    return dp.DayPipeline(config,"20211004",runner=state["pipeline"].run,runs_root=state["tmp"])

def complete():
    return dict(status="all_scheduled_cycles_complete", day="20211004",
        cycles_completed=3,cycles_total=3,requested_cycles=3)

def test_wait_keeps_prior_receipts_and_never_completes_or_runs_cleanup(state):
    p = state["pipeline"]
    prior = {p.path(s):p.path(s).read_bytes() for s in dp.STAGES[:4]}
    result = p.resume(go="a"*64)
    assert result == {s:"present" for s in dp.STAGES[:4]} | {"cycles":"wait"}
    assert p.receipt("cycles") is None
    assert len(state["calls"]) == 1
    assert "PendingReturn=1" in state["calls"][0]
    assert all(path.read_bytes()==body for path,body in prior.items())
    assert not (p.directory/"host-stop.json").exists()
    with pytest.raises(dp.StageRefused):
        p.run_stage("package-upload")
    assert len(state["calls"]) == 1

def test_reopening_wait_without_exact_resume_pin_does_not_dispatch(state):
    assert state["pipeline"].run_stage("cycles",go="a"*64) == "wait"
    retained = {p:p.read_bytes() for p in state["pipeline"].directory.rglob("*.json")}
    assert reopen(state).resume(go="a"*64)["cycles"] == "wait"
    assert len(state["calls"]) == 1
    assert all(p.read_bytes()==raw for p,raw in retained.items())

def test_correct_wait_pin_resumes_same_command_and_completion_is_idempotent(state):
    p = state["pipeline"]
    assert p.run_stage("cycles",go="a"*64) == "wait"
    state["output"][0] = complete()
    resumed = reopen(state)
    assert resumed.run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"]) == "done"
    assert len(state["calls"]) == 2
    before, after = state["calls"]
    extra = ["--set","ResumeWaitSha256="+state["envelope"]["receipt_sha256"]]
    assert after == before + extra
    assert resumed.receipt("cycles")["gate"]["cycles_completed"] == 3
    assert resumed.run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"]) == "present"
    assert len(state["calls"]) == 2

@pytest.mark.parametrize("pin",["0"*64,"not-a-hash",""])
def test_wrong_or_empty_explicit_resume_pin_refuses_without_dispatch(state,pin):
    assert state["pipeline"].run_stage("cycles",go="a"*64) == "wait"
    with pytest.raises((dp.StageRefused,ValueError)):
        reopen(state).run_stage("cycles",go="a"*64,resume_wait=pin)
    assert len(state["calls"]) == 1

@pytest.mark.parametrize("go",[None,"0"*64])
def test_hold_dominates_valid_wait_resume_pin(state,go):
    assert state["pipeline"].run_stage("cycles",go="a"*64) == "wait"
    assert reopen(state).run_stage("cycles",go=go,resume_wait=state["envelope"]["receipt_sha256"]) == "hold"
    assert len(state["calls"]) == 1
    assert state["pipeline"].receipt("cycles") is None

def test_resume_pin_without_retained_wait_cannot_start_a_new_run(state):
    with pytest.raises((dp.StageRefused,ValueError)):
        state["pipeline"].run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"])
    assert state["calls"] == []

def test_attention_is_retained_and_never_automatically_resumed(state):
    value = state["envelope"]
    value["status"] = "workflow_attention"
    value["wait_receipt"]["state"] = "ATTENTION"
    value["wait_receipt"]["kind"] = "same_job"
    value["wait_receipt"]["job_id"] = "4"*64
    value["wait_receipt"].pop("receipt_id")
    value["wait_receipt"]["receipt_id"] = digest(value["wait_receipt"])
    value["receipt_sha256"] = hashlib.sha256(canonical(value["wait_receipt"])).hexdigest()
    assert state["pipeline"].resume(go="a"*64)["cycles"] == "attention"
    assert reopen(state).resume(go="a"*64)["cycles"] == "attention"
    with pytest.raises((dp.StageRefused,ValueError)):
        reopen(state).run_stage("cycles",go="a"*64,resume_wait=value["receipt_sha256"])
    assert len(state["calls"]) == 1

@pytest.mark.parametrize("field,value",[
    ("day","20211005"),("run_id","foreign"),("run_directory","/another/run"),
    ("cycles_total",19),("requested_cycles",2),("receipt_sha256","0"*64)])
def test_foreign_or_unbound_wait_status_is_not_admitted(state,field,value):
    state["output"][0][field] = value
    with pytest.raises((dp.StageRefused,ValueError)):
        state["pipeline"].run_stage("cycles",go="a"*64)
    assert state["pipeline"].receipt("cycles") is None

@pytest.mark.parametrize("change",[
    {"instance":"i-other"},
    {"workflow_run":{"run_id":"foreign","run_directory":"/retained/run"}},
    {"workflow_run":{"run_id":"retained-run","run_directory":"/other/run"}},
])
def test_changed_dispatch_configuration_refuses_existing_wait(state,change):
    assert state["pipeline"].run_stage("cycles",go="a"*64) == "wait"
    with pytest.raises((dp.StageRefused,ValueError)):
        reopen(state,**change).run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"])
    assert len(state["calls"]) == 1

def test_missing_opt_in_never_accepts_pending_status(state):
    p = reopen(state,pending_return=False)
    with pytest.raises((dp.StageRefused,ValueError)):
        p.run_stage("cycles",go="a"*64)
    assert p.receipt("cycles") is None

def test_changed_previous_preparation_receipt_refuses_resume_before_dispatch(state):
    p = state["pipeline"]
    assert p.run_stage("cycles",go="a"*64) == "wait"
    path = p.path("schedule-prefixes")
    prior = json.loads(path.read_bytes())
    prior["gate"]["configuration"]["sha256"] = "9"*64
    path.write_bytes(canonical(prior)+b"\n")
    with pytest.raises((dp.StageRefused,ValueError)):
        reopen(state).run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"])
    assert len(state["calls"]) == 1

def test_repeated_same_wait_preserves_receipts_without_duplicate_completion(state):
    p = state["pipeline"]
    assert p.run_stage("cycles",go="a"*64) == "wait"
    retained = {path:path.read_bytes() for path in p.directory.rglob("*.json")}
    assert reopen(state).run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"]) == "wait"
    assert all(path.read_bytes()==raw for path,raw in retained.items())
    assert p.receipt("cycles") is None

def test_resume_is_capped_to_waiting_cycle_and_cannot_package_or_start_next_cycle(state):
    value=state["envelope"]
    wait=value["wait_receipt"]
    wait["cycle_index"]=0
    wait["request_id"]="retained-run-cycle-00"
    wait["artifacts"]={name.replace("cycle-02","cycle-00"):pin for name,pin in wait["artifacts"].items()}
    wait.pop("receipt_id")
    wait["receipt_id"]=digest(wait)
    value["receipt_path"]=value["receipt_path"].replace("cycle-02","cycle-00")
    value["receipt_sha256"]=hashlib.sha256(canonical(wait)).hexdigest()
    assert state["pipeline"].run_stage("cycles",go="a"*64) == "wait"
    state["output"][0]=dict(status="requested_cycles_complete",day="20211004",
        cycles_completed=1,requested_cycles=1,cycles_total=3)
    result=reopen(state).resume(go="a"*64,resume_wait=value["receipt_sha256"])
    assert result["cycles"]=="partial"
    assert "package-upload" not in result
    assert "CycleLimit=1" in state["calls"][-1]
    assert "CycleLimit=3" not in state["calls"][-1]
    assert state["pipeline"].receipt("cycles") is None
    assert len(state["calls"])==2

def test_corrupt_retained_wait_refuses_before_resumed_process(state):
    p=state["pipeline"]
    assert p.run_stage("cycles",go="a"*64)=="wait"
    waits=list(p.directory.glob("04-cycles-wait-*.json"))
    assert len(waits)==1
    record=json.loads(waits[0].read_bytes())
    record["gate"]["wait_receipt"]["request_id"]="foreign-cycle-02"
    waits[0].write_bytes(canonical(record))
    with pytest.raises((dp.StageRefused,ValueError)):
        reopen(state).run_stage("cycles",go="a"*64,resume_wait=state["envelope"]["receipt_sha256"])
    assert len(state["calls"])==1

def test_pending_return_requires_explicit_trading_schedule_and_native_run_pins(state):
    for key in ("trading_day_schedule","workflow_run"):
        config=copy.deepcopy(state["config"])
        config.pop(key)
        with pytest.raises((dp.StageRefused,ValueError)):
            dp.DayPipeline(config,"20211004",runner=state["pipeline"].run,runs_root=state["tmp"])
    assert state["calls"]==[]
