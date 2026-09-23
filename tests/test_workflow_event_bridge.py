"""Receipt-bound existing workflow events; no network, credentials or live dispatch."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"research/kalshi/frankie_boss/operations/workflow_event_bridge.py"

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def seal(event):
    event.pop("event_id",None)
    event["event_id"]=sha(canonical(event))
    return event

@pytest.fixture
def api():
    spec=importlib.util.spec_from_file_location("event_bridge_under_test",MODULE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    run="/native/run"
    wait=dict(schema="FRANKIE_WORKFLOW_WAIT_V1",state="WAIT",kind="readiness",
        run_id="fixture-run",run_directory=run,cycle_index=0,request_id="fixture-run-cycle-00",
        configuration_sha256="c"*64,boss_commit="d"*40,schedule_sha256="e"*64,job_id=None,
        artifacts={"host-identity.c15.json":dict(sha256="1"*64,bytes=10),
            "workflow-execution-scope.json":dict(sha256="2"*64,bytes=10),
            "execution/cycle-00/actual-critic-request.json":dict(sha256="3"*64,bytes=10),
            "execution/cycle-00/host-preparation.c15.json":dict(sha256="4"*64,bytes=10)})
    wait["receipt_id"]=sha(canonical(wait))
    pending=dict(status="WAIT",requested_cycles=3,gate=dict(wait_receipt=wait,
        receipt_sha256=sha(canonical(wait)),receipt_path=run+"/execution/cycle-00/workflow-wait/readiness.json",
        prepared_configuration_sha256="f"*64,requested_cycles=3,cycles_total=3,day="20211004",
        run_id="fixture-run",run_directory=run,schedule_sha256="a"*64,status="workflow_wait"))
    configuration=dict(pending_return=True,instance="i-0e90ee6110ef609aa",
        workflow_automation=dict(context=dict(tools_root="/tools/Markets",tools_commit="d"*40,
            python="/native/python",configuration_path="/native/configuration.json"),
            archive=dict(instance="i-0e90ee6110ef609aa",run_root="C:/fixture/days",
                bucket="frankie-granite42-568968024170-us-east-1",key_parameter="/markets/frankie/request-transport/test"),
            workflow_ref="codex/trading-day-readiness-20260922"),workflow_run={k:wait[k] for k in (
        "run_id","run_directory","configuration_sha256","boss_commit","schedule_sha256")},
        trading_day_schedule=dict(trading_day="20211004",step_count=3,source_record_count=17,
            schedule_sha256="a"*64,source_manifest_hash="b"*64))
    stages={
        "stage-sources":dict(gate=dict(manifest_hash="b"*64,records=17)),
        "schedule-prefixes":dict(gate=dict(configuration=dict(path="/native/configuration.json",sha256="f"*64,bytes=123),
            day="20211004",schedule_sha256="a"*64,prefix_count=3,source_records=17,prefixes_sha256="9"*64)),
    }
    directory=tmp_path/"runs/20211004"
    directory.mkdir(parents=True)
    pipeline=SimpleNamespace(c=configuration,day="20211004",directory=directory,cycle_limit=3,
        pending=lambda:pending,receipt=lambda stage:stages.get(stage))
    config_path=Path("pipeline.json")
    config_path.write_bytes(canonical(configuration))
    context=dict(configuration_path="/native/configuration.json",configuration_sha256="f"*64,
        wait_receipt_path=pending["gate"]["receipt_path"],wait_receipt_sha256=pending["gate"]["receipt_sha256"],
        tools_root="/tools/Markets",tools_commit="d"*40,python="/native/python",
        request_id=wait["request_id"],request_sha256="3"*64)
    event=seal(dict(schema="FRANKIE_WORKFLOW_EVENT_V1",action="archive",source_commit="d"*40,receipts_commit="8"*40,day="20211004",
        pipeline_configuration=dict(path="pipeline.json",sha256=sha(config_path.read_bytes())),
        runs_root="runs",go="b"*64,context=context,payload=dict(request_sha256="3"*64,cycle_index="00",
            instance="i-0e90ee6110ef609aa",day="20211004",run_root="C:/fixture/days",
            bucket="frankie-granite42-568968024170-us-east-1",key_parameter="/markets/frankie/request-transport/test")))
    return dict(tmp=tmp_path,pipeline=pipeline,pending=pending,wait=wait,event=event,configuration=configuration)

def release(fixture,**changes):
    value=dict(schema="FRANKIE_WORKFLOW_OWNER_RELEASE_V1",run_id="fixture-run",
        prepared_configuration_sha256="f"*64,source_manifest_hash="b"*64,schedule_sha256="a"*64,
        final_workflow_task=dict(id="owner-final-task",completed=True),owner_release=True,
        allowed_action="resume_existing_wait",execution_scope_sha256="2"*64)
    value.update(changes)
    path=fixture["tmp"]/"owner-release.json"
    path.write_bytes(canonical(value))
    fixture["configuration"]["owner_release"]=dict(path=str(path),sha256=sha(path.read_bytes()))
    return path

def assert_denied(call):
    try:
        result=call()
    except ValueError:
        return
    assert result is False

def test_exact_archive_event_binds_existing_wait_and_prepared_configuration(api,fixture):
    event=fixture["event"]
    assert api.validate_event(event,fixture["pipeline"])==event

@pytest.mark.parametrize("field,value",[
    ("day","20211005"),("go","0"*64),("source_commit","main"),("runs_root","../other"),
    ("action","stop"),("schema","foreign"),
])
def test_foreign_event_or_unsafe_dispatch_route_refuses(api,fixture,field,value):
    event=copy.deepcopy(fixture["event"])
    event[field]=value
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

@pytest.mark.parametrize("field,value",[
    ("wait_receipt_sha256","0"*64),("configuration_sha256","0"*64),
    ("request_id","foreign-run-cycle-00"),("request_sha256","0"*64),
    ("wait_receipt_path","/foreign/run/wait.json"),
])
def test_event_context_cannot_replace_the_exact_waiting_request(api,fixture,field,value):
    event=copy.deepcopy(fixture["event"])
    event["context"][field]=value
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

def test_changed_event_body_without_new_identity_is_rejected(api,fixture):
    event=copy.deepcopy(fixture["event"])
    event["payload"]["request_sha256"]="0"*64
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

def test_event_without_retained_wait_cannot_start_new_run(api,fixture):
    fixture["pipeline"].pending=lambda:None
    with pytest.raises(ValueError):
        api.validate_event(fixture["event"],fixture["pipeline"])

def test_attention_cannot_be_promoted_by_an_event(api,fixture):
    fixture["pending"]["status"]="ATTENTION"
    fixture["wait"]["state"]="ATTENTION"
    with pytest.raises(ValueError):
        api.validate_event(fixture["event"],fixture["pipeline"])

def test_changed_pipeline_configuration_refuses(api,fixture):
    fixture["pipeline"].c["workflow_automation"]["context"]["tools_commit"]="0"*40
    with pytest.raises(ValueError):
        api.validate_event(fixture["event"],fixture["pipeline"])

def test_readiness_action_requires_authenticated_producer_identity(api,fixture):
    event=copy.deepcopy(fixture["event"])
    event["action"]="readiness"
    event["payload"]=dict(ready_run_id="123456",ready_source_commit="d"*40,instance="i-0e90ee6110ef609aa")
    seal(event)
    assert api.validate_event(event,fixture["pipeline"])==event
    event["payload"]["ready_source_commit"]="main"
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

def test_principal_response_cannot_be_delivered_to_readiness_wait(api,fixture):
    event=copy.deepcopy(fixture["event"])
    event["action"]="principal"
    event["payload"]=dict(source_ref="d"*40,response_path="responses/answer.json",
        attestation_path="responses/attestation.json",record_path="responses/record.json",
        turn="initial",instance="i-0e90ee6110ef609aa",bucket="frankie-granite42-568968024170-us-east-1")
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

def test_missing_owner_release_keeps_existing_wait_held(api,fixture):
    assert api.verify_release(fixture["pipeline"],fixture["wait"]) is False

def test_exact_owner_release_names_completed_final_task_and_existing_scope(api,fixture):
    release(fixture)
    assert api.verify_release(fixture["pipeline"],fixture["wait"]) is True

@pytest.mark.parametrize("change",[
    {"owner_release":False},{"final_workflow_task":{"id":"owner-final-task","completed":False}},
    {"final_workflow_task":{"id":"","completed":True}},{"run_id":"foreign"},
    {"prepared_configuration_sha256":"0"*64},{"source_manifest_hash":"0"*64},
    {"schedule_sha256":"0"*64},{"allowed_action":"start_new_run"},{"execution_scope_sha256":"0"*64},
])
def test_foreign_incomplete_or_expanded_owner_release_denies(api,fixture,change):
    release(fixture,**change)
    assert_denied(lambda:api.verify_release(fixture["pipeline"],fixture["wait"]))

def test_changed_owner_release_bytes_cannot_be_reinterpreted(api,fixture):
    path=release(fixture)
    path.write_bytes(path.read_bytes()+b" ")
    assert_denied(lambda:api.verify_release(fixture["pipeline"],fixture["wait"]))

def test_missing_pinned_owner_release_is_still_held(api,fixture):
    path=release(fixture)
    path.rename(path.with_suffix(".fixture-retained"))
    assert api.verify_release(fixture["pipeline"],fixture["wait"]) is False

def test_dispatch_intent_precedes_external_dispatch_and_exact_duplicate_is_noop(api,fixture):
    directory=fixture["tmp"]/"outbox"
    seen=[]
    def dispatch(event):
        intents=list(directory.rglob("intent.json"))
        assert len(intents)==1
        assert event["event_id"] in intents[0].read_text()
        assert list(directory.rglob("accepted.json"))==[]
        seen.append(copy.deepcopy(event))
        return True
    first=api.dispatch_event(directory,fixture["event"],dispatch)
    retained={p:p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    second=api.dispatch_event(directory,fixture["event"],dispatch)
    assert first==second
    assert seen==[fixture["event"]]
    assert all(p.read_bytes()==raw for p,raw in retained.items())

def test_lost_dispatch_ack_retains_identity_and_retries_exact_same_event(api,fixture):
    directory=fixture["tmp"]/"outbox"
    seen=[]
    def lost(event):
        seen.append(copy.deepcopy(event))
        raise OSError("ambiguous remote acknowledgement")
    with pytest.raises(Exception):
        api.dispatch_event(directory,fixture["event"],lost)
    assert list(directory.rglob("intent.json"))
    assert list(directory.rglob("accepted.json"))==[]
    retained={p:p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    def accepted(event):
        seen.append(copy.deepcopy(event))
        return True
    api.dispatch_event(directory,fixture["event"],accepted)
    assert seen==[fixture["event"],fixture["event"]]
    assert all(p.read_bytes()==raw for p,raw in retained.items())

def test_changed_event_cannot_reuse_dispatch_identity(api,fixture):
    directory=fixture["tmp"]/"outbox"
    seen=[]
    def dispatch(event):
        seen.append(event)
        return True
    api.dispatch_event(directory,fixture["event"],dispatch)
    changed=copy.deepcopy(fixture["event"])
    changed["context"]["request_sha256"]="0"*64
    with pytest.raises(ValueError):
        api.dispatch_event(directory,changed,dispatch)
    assert len(seen)==1

@pytest.mark.parametrize("field,value",[
    ("tools_root","/foreign/tools"),("tools_commit","0"*40),("python","/foreign/python"),
    ("configuration_path","/foreign/configuration.json")
])
def test_event_cannot_select_different_native_tools_or_configuration(api,fixture,field,value):
    event=copy.deepcopy(fixture["event"])
    event["context"][field]=value
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])

@pytest.mark.parametrize("field,value",[
    ("instance","i-other"),("bucket","other"),("run_root","/other/days"),
    ("key_parameter","/foreign/key"),("cycle_index","01"),("request_sha256","0"*64)
])
def test_archive_event_cannot_substitute_target_or_request(api,fixture,field,value):
    event=copy.deepcopy(fixture["event"])
    event["payload"][field]=value
    seal(event)
    with pytest.raises(ValueError):
        api.validate_event(event,fixture["pipeline"])
