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

@pytest.fixture
def retained_pipeline(api,fixture):
    module=api.load_module("real_event_pipeline_fixture",ROOT/"research/kalshi/frankie_boss/operations/day_pipeline.py")
    p=module.DayPipeline(fixture["configuration"],"20211004",runs_root="runs")
    p.write("stage-sources",dict(manifest="manifest.json",manifest_hash="b"*64,records=17),command=[])
    p.write("host-start",dict(ssm_online=True),command=[])
    p.write("ingest",dict(journal_count=17,journal_hash="5"*64,compact_sha256="6"*64),command=[])
    prepared=fixture["pipeline"].receipt("schedule-prefixes")["gate"]
    p.write("schedule-prefixes",prepared,command=[])
    p._write_wait(fixture["pending"]["gate"],3,None)
    fixture["pipeline"]=p
    return fixture

def fake_git(api,monkeypatch,files=None,head="d"*40,modes=None):
    files={} if files is None else files
    modes={} if modes is None else modes
    calls=[]
    def run(argv,**kwargs):
        calls.append(list(argv))
        assert argv[0]=="git" and "fetch" in argv,"only isolated Git metadata may run"
        return SimpleNamespace(returncode=0)
    def output(argv,**kwargs):
        calls.append(list(argv))
        assert argv[0]=="git","test cannot invoke a host runner"
        if "rev-parse" in argv:
            result=head+"\n"
        elif "ls-tree" in argv:
            names=sorted(files)
            if "--name-only" in argv:
                result="\n".join(names)+("\n" if names else "")
            else:
                separator="\0" if "-z" in argv or "-rz" in argv else "\n"
                result=separator.join(modes.get(name,"100644")+" blob "+"9"*40+"\t"+name for name in names)
                if names:result+=separator
        elif "show" in argv:
            name=argv[-1].split(":",1)[1]
            result=Path(name).read_bytes() if argv[-1].startswith("HEAD:") else files[name]
        else:
            raise AssertionError("unexpected metadata request "+repr(argv))
        if kwargs.get("text"):
            return result.decode() if isinstance(result,bytes) else result
        return result.encode() if isinstance(result,str) else result
    monkeypatch.setattr(api.subprocess,"run",run)
    monkeypatch.setattr(api.subprocess,"check_output",output)
    return calls

def test_actual_loader_reconstructs_real_pipeline_from_exact_retained_receipts(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    calls=fake_git(api,monkeypatch)
    loaded=api.load_pipeline(f["event"],overlay=False)
    assert loaded.pending()["gate"]["receipt_sha256"]==f["event"]["context"]["wait_receipt_sha256"]
    assert loaded.receipt("cycles") is None
    assert all(command[0]=="git" for command in calls)

def test_actual_loader_rejects_source_checkout_drift_before_receipt_overlay(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    calls=fake_git(api,monkeypatch,head="0"*40)
    with pytest.raises(ValueError):
        api.load_pipeline(f["event"])
    assert not any("fetch" in command for command in calls)

def test_receipt_commit_cannot_supply_missing_pipeline_configuration_authority(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    event=copy.deepcopy(f["event"])
    malicious="runs/20211004/injected-configuration.json"
    raw=canonical(f["configuration"])
    event["pipeline_configuration"]=dict(path=malicious,sha256=sha(raw))
    seal(event)
    fake_git(api,monkeypatch,files={malicious:raw})
    with pytest.raises((ValueError,FileNotFoundError)):
        api.load_pipeline(event)
    assert not Path(malicious).exists()

def test_receipt_commit_cannot_supply_owner_release_authority(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    release_path=release(f)
    raw=release_path.read_bytes()
    target="runs/20211004/owner-release.json"
    f["configuration"]["owner_release"]=dict(path=target,sha256=sha(raw))
    Path("pipeline.json").write_bytes(canonical(f["configuration"]))
    event=copy.deepcopy(f["event"])
    event["pipeline_configuration"]["sha256"]=sha(Path("pipeline.json").read_bytes())
    seal(event)
    fake_git(api,monkeypatch,files={target:raw})
    try:
        api.load_pipeline(event)
    except (ValueError,RuntimeError):
        pass
    assert not Path(target).exists(),"receipt transport must never manufacture owner release authority"

def test_symlink_git_object_is_not_admitted_as_regular_receipt_bytes(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    path=next(Path("runs/20211004").glob("04-cycles-wait-*.json"))
    name=path.as_posix()
    fake_git(api,monkeypatch,files={name:path.read_bytes()},modes={name:"120000"})
    with pytest.raises(ValueError):
        api.load_pipeline(f["event"])

@pytest.mark.parametrize("stage,field,value",[
    ("stage-sources","records",18),("ingest","journal_count",18),
    ("ingest","compact_sha256","0"*64),
])
def test_actual_loader_refuses_changed_earlier_receipt_chain(api,retained_pipeline,monkeypatch,stage,field,value):
    f=retained_pipeline
    path=f["pipeline"].path(stage)
    record=json.loads(path.read_bytes())
    record["gate"][field]=value
    path.write_bytes(canonical(record))
    fake_git(api,monkeypatch)
    with pytest.raises((ValueError,RuntimeError)):
        api.load_pipeline(f["event"],overlay=False)

@pytest.mark.parametrize("stage",["stage-sources","host-start","ingest"])
def test_actual_loader_refuses_missing_earlier_receipt(api,retained_pipeline,monkeypatch,stage):
    f=retained_pipeline
    path=f["pipeline"].path(stage)
    path.rename(path.with_suffix(".fixture-retained"))
    fake_git(api,monkeypatch)
    with pytest.raises((ValueError,RuntimeError)):
        api.load_pipeline(f["event"],overlay=False)

def test_actual_resume_cli_keeps_missing_owner_release_held_without_ssm(api,retained_pipeline,monkeypatch,capsys):
    f=retained_pipeline
    event_path=Path("event.json")
    event_path.write_bytes(canonical(f["event"]))
    calls=fake_git(api,monkeypatch)
    monkeypatch.setattr(api.sys,"argv",["bridge","resume","--event",str(event_path)])
    api.main()
    result=json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["status"]=="HELD"
    assert all(command[0]=="git" for command in calls)
    assert f["pipeline"].receipt("cycles") is None

def test_actual_dispatch_cli_requires_uploaded_outbox_before_external_api(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    event_path=Path("event.json")
    event_path.write_bytes(canonical(f["event"]))
    directory=Path("outbox")
    api.WAIT._publish(directory/"intent.json",dict(schema="FRANKIE_WORKFLOW_EVENT_OUTBOX_V1",event=f["event"]))
    calls=fake_git(api,monkeypatch)
    monkeypatch.delenv("WORKFLOW_OUTBOX_ARTIFACT_CONFIRMED",raising=False)
    monkeypatch.setattr(api.sys,"argv",["bridge","dispatch","--event",str(event_path),"--directory",str(directory)])
    with pytest.raises(ValueError):
        api.main()
    assert all(command[0]=="git" for command in calls)
    assert not (directory/"accepted.json").exists()

def test_actual_dispatch_cli_targets_registered_route_with_exact_event_once(api,retained_pipeline,monkeypatch):
    f=retained_pipeline
    event_path=Path("event.json")
    event_path.write_bytes(canonical(f["event"]))
    directory=Path("outbox")
    api.WAIT._publish(directory/"intent.json",dict(schema="FRANKIE_WORKFLOW_EVENT_OUTBOX_V1",event=f["event"]))
    calls=fake_git(api,monkeypatch)
    git_run=api.subprocess.run
    sent=[]
    def external(argv,**kwargs):
        if argv[0]=="git":
            return git_run(argv,**kwargs)
        assert argv[:4]==["gh","workflow","run","frankie_journal_stack.yml"]
        assert (directory/"intent.json").is_file()
        sent.append(argv)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(api.subprocess,"run",external)
    monkeypatch.setenv("WORKFLOW_OUTBOX_ARTIFACT_CONFIRMED","true")
    monkeypatch.setattr(api.sys,"argv",["bridge","dispatch","--event",str(event_path),"--directory",str(directory)])
    api.main()
    api.main()
    assert len(sent)==1
    value=next(part.split("=",1)[1] for part in sent[0] if part.startswith("continuation_event="))
    assert json.loads(value)==f["event"]
    assert "checks_only=true" in sent[0] and "keep_compute=true" in sent[0]
    assert (directory/"accepted.json").is_file()


@pytest.mark.parametrize("diff",[
    "",
    "A\truns/20211004/04-cycles-wait-"+("a"*64)+".json\n",
    "A\tresearch/kalshi/frankie_boss/runs/request-archives/exact/archive.json\n",
])
def test_caller_revision_accepts_only_new_immutable_evidence(api,fixture,monkeypatch,diff):
    calls=[]
    def git(*args,**kwargs):
        calls.append(args)
        return diff.encode()
    monkeypatch.setattr(api,"git",git)
    assert api.validate_caller_revision(fixture["event"],"9"*40) is True
    assert calls==[("diff","--name-status","d"*40,"9"*40)]

@pytest.mark.parametrize("diff",[
    "M\truns/20211004/04-cycles-wait-"+("a"*64)+".json\n",
    "D\truns/20211004/00-stage-sources.json\n",
    "R100\truns/20211004/old.json\truns/20211004/new.json\n",
    "A\t.github/workflows/frankie_workflow_continuation.yml\n",
    "A\tresearch/kalshi/frankie_boss/operations/foreign.py\n",
    "A\truns/20211005/04-cycles.json\n",
    "A\truns/202110040/04-cycles.json\n",
    "A\tresearch/kalshi/frankie_boss/runs/request-archives-foreign/archive.json\n",
])
def test_caller_revision_rejects_changed_code_receipts_or_foreign_day(api,fixture,monkeypatch,diff):
    monkeypatch.setattr(api,"git",lambda *args,**kw:diff.encode())
    with pytest.raises(ValueError):
        api.validate_caller_revision(fixture["event"],"9"*40)

@pytest.fixture
def publication_repo(api,retained_pipeline,tmp_path):
    """Real Git objects and a temporary local bare remote, never a network repository."""
    import subprocess
    f=retained_pipeline
    def git(*args,cwd=None):
        return subprocess.check_output(["git",*args],cwd=cwd).decode().strip()
    git("init","-q")
    git("config","user.name","isolated-ci")
    git("config","user.email","isolated-ci@example.invalid")
    ref=f["configuration"]["workflow_automation"]["workflow_ref"]
    git("checkout","-qb",ref)
    git("add","pipeline.json","runs")
    git("commit","-qm","synthetic source and retained WAIT")
    source=git("rev-parse","HEAD")
    remote=tmp_path.parent/(tmp_path.name+"-synthetic-origin.git")
    git("init","--bare","-q",str(remote))
    git("remote","add","origin",str(remote))
    git("push","-q","origin",ref)
    event=copy.deepcopy(f["event"])
    event["source_commit"]=source
    event["receipts_commit"]=source
    seal(event)
    f.update(event=event,git=git,remote=remote,ref=ref,source=source)
    return f

def test_publication_keeps_source_checkout_and_confirms_exact_cas_commit(api,publication_repo):
    f=publication_repo
    commit=api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert f["git"]("rev-parse","HEAD")==f["source"]
    assert f["git"]("ls-remote","--heads","origin","refs/heads/"+f["ref"]).split()[0]==commit
    retained=json.loads(Path("workflow-event-outbox/receipt-publication-intent.json").read_bytes())
    assert retained["parent_commit"]==f["source"]
    assert retained["receipts_commit"]==commit
    marker=api.consumer_marker(f["pipeline"],f["event"]).as_posix()
    remote_marker=json.loads(f["git"]("show",commit+":"+marker))
    assert remote_marker["input_wait_sha256"]==f["event"]["context"]["wait_receipt_sha256"]
    assert remote_marker["event_sha256"]==sha(canonical(f["event"]))
    assert "Co-Authored-By: Codex <noreply@openai.com>" in f["git"]("show","-s","--format=%B",commit)

def test_lost_push_ack_is_recovered_only_by_exact_remote_commit_readback(api,publication_repo,monkeypatch):
    f=publication_repo
    real_run=api.subprocess.run
    attempts=[]
    def lose_ack(argv,**kwargs):
        result=real_run(argv,**kwargs)
        if argv[:2]==["git","push"]:
            attempts.append(argv)
            assert result.returncode==0
            return SimpleNamespace(returncode=1,stdout=b"",stderr=b"synthetic lost acknowledgment")
        return result
    monkeypatch.setattr(api.subprocess,"run",lose_ack)
    commit=api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert len(attempts)==1
    assert json.loads(Path("workflow-event-outbox/receipt-publication.json").read_bytes())["receipts_commit"]==commit

def test_failed_push_without_matching_remote_head_remains_unconfirmed(api,publication_repo,monkeypatch):
    f=publication_repo
    real_run=api.subprocess.run
    def reject_push(argv,**kwargs):
        if argv[:2]==["git","push"]:
            return SimpleNamespace(returncode=1,stdout=b"",stderr=b"synthetic rejected CAS")
        return real_run(argv,**kwargs)
    monkeypatch.setattr(api.subprocess,"run",reject_push)
    with pytest.raises(ValueError):
        api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert Path("workflow-event-outbox/receipt-publication-intent.json").is_file()
    assert not Path("workflow-event-outbox/receipt-publication.json").exists()
    assert f["git"]("ls-remote","--heads","origin","refs/heads/"+f["ref"]).split()[0]==f["source"]

def test_publication_refuses_remote_cycle_evidence_missing_from_local_chain(api,publication_repo,tmp_path):
    f=publication_repo
    other=tmp_path.parent/(tmp_path.name+"-concurrent-writer")
    f["git"]("clone","-q","--branch",f["ref"],str(f["remote"]),str(other))
    f["git"]("config","user.name","other-isolated-ci",cwd=other)
    f["git"]("config","user.email","other-isolated-ci@example.invalid",cwd=other)
    foreign=other/"runs/20211004"/("04-cycles-wait-"+("0"*64)+".json")
    foreign.write_bytes(canonical(dict(schema="FRANKIE_DAY_PIPELINE_RECEIPT_V1",day="20211004",stage="cycles",
                                      status="WAIT",previous_wait_sha256=f["event"]["context"]["wait_receipt_sha256"])))
    f["git"]("add","runs",cwd=other)
    f["git"]("commit","-qm","synthetic competing WAIT",cwd=other)
    f["git"]("push","-q","origin",f["ref"],cwd=other)
    competing=f["git"]("rev-parse","HEAD",cwd=other)
    with pytest.raises(ValueError):
        api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert f["git"]("ls-remote","--heads","origin","refs/heads/"+f["ref"]).split()[0]==competing
    assert not Path("workflow-event-outbox/receipt-publication.json").exists()

def test_retained_consumed_event_prevents_second_resume(api,publication_repo):
    f=publication_repo
    assert api.consumed(f["pipeline"],f["event"]) is False
    api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert api.consumed(f["pipeline"],f["event"]) is True

def resume_record(fixture,result):
    event=fixture["event"]
    return dict(schema="FRANKIE_WORKFLOW_EVENT_RESUME_RESULT_V1",event_id=event["event_id"],
        event_sha256=sha(canonical(event)),input_wait_sha256=event["context"]["wait_receipt_sha256"],
        result=result)

def test_finalize_accepts_unchanged_wait_as_exact_idempotent_resume(api,retained_pipeline):
    f=retained_pipeline
    prior=copy.deepcopy(f["pipeline"].pending())
    result=api.validate_resume_result(f["pipeline"],f["event"],resume_record(f,"wait"),prior)
    assert result["gate"]["receipt_sha256"]==prior["gate"]["receipt_sha256"]
    assert f["pipeline"].receipt("cycles") is None

@pytest.mark.parametrize("field,value",[
    ("event_id","0"*64),("event_sha256","0"*64),("input_wait_sha256","0"*64),
    ("schema","foreign"),("result","cleanup"),
])
def test_finalize_rejects_foreign_resume_result_identity(api,retained_pipeline,field,value):
    f=retained_pipeline
    record=resume_record(f,"wait");record[field]=value
    with pytest.raises(ValueError):
        api.validate_resume_result(f["pipeline"],f["event"],record,copy.deepcopy(f["pipeline"].pending()))

@pytest.mark.parametrize("result",["done","present"])
def test_finalize_cannot_promote_wait_without_exact_completed_gate(api,retained_pipeline,result):
    f=retained_pipeline
    prior=copy.deepcopy(f["pipeline"].pending())
    f["pipeline"].write("cycles",dict(day="20211004",cycles_completed=1,cycles_total=3),command=[])
    with pytest.raises(ValueError):
        api.validate_resume_result(f["pipeline"],f["event"],resume_record(f,result),prior)

def test_finalize_cannot_use_unrelated_preexisting_batch_as_new_partial_progress(api,retained_pipeline):
    f=retained_pipeline
    prior=copy.deepcopy(f["pipeline"].pending())
    path=f["pipeline"].directory/"04-cycles-batch-99.json"
    path.write_bytes(canonical(dict(schema="FRANKIE_DAY_PIPELINE_RECEIPT_V1",day="20211004",stage="cycles",
        status="PARTIAL",gate=dict(status="requested_cycles_complete",day="20211004",
        cycles_completed=99,requested_cycles=99,cycles_total=3))))
    with pytest.raises((ValueError,FileNotFoundError)):
        api.validate_resume_result(f["pipeline"],f["event"],resume_record(f,"partial"),prior)


def test_publication_retry_reconciles_retained_intent_after_post_push_crash(api,publication_repo,monkeypatch):
    f=publication_repo
    publish=api.WAIT._publish
    def crash_after_push(path,value):
        if Path(path).name=="receipt-publication.json":
            raise OSError("synthetic crash after remote CAS, before local acknowledgment")
        return publish(path,value)
    monkeypatch.setattr(api.WAIT,"_publish",crash_after_push)
    with pytest.raises(OSError):
        api.publish_receipts(f["pipeline"],f["event"],"wait")
    intent=json.loads(Path("workflow-event-outbox/receipt-publication-intent.json").read_bytes())
    assert f["git"]("ls-remote","--heads","origin","refs/heads/"+f["ref"]).split()[0]==intent["receipts_commit"]
    assert not Path("workflow-event-outbox/receipt-publication.json").exists()
    monkeypatch.setattr(api.WAIT,"_publish",publish)
    commit=api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert commit==intent["receipts_commit"]
    assert json.loads(Path("workflow-event-outbox/receipt-publication.json").read_bytes())["receipts_commit"]==commit


def test_completed_pipeline_cannot_emit_archive_for_its_historical_wait(api,retained_pipeline):
    f=retained_pipeline
    f["pipeline"].write("cycles",dict(status="all_scheduled_cycles_complete",
        day="20211004",cycles_completed=3,cycles_total=3),command=[])
    event=f["event"]
    assert api.archive_event(f["pipeline"],source_commit=event["source_commit"],
        receipts_commit=event["receipts_commit"],configuration_path=event["pipeline_configuration"]["path"],
        runs_root=event["runs_root"],go=event["go"]) is None


def test_completed_requested_batch_cannot_emit_archive_for_historical_wait(api,retained_pipeline):
    f=retained_pipeline
    original=f["pipeline"]
    module=api.load_module("partial_event_pipeline_fixture",ROOT/"research/kalshi/frankie_boss/operations/day_pipeline.py")
    pipeline=module.DayPipeline(f["configuration"],"20211004",runs_root="partial-runs",cycle_limit=2)
    for stage in ("stage-sources","host-start","ingest","schedule-prefixes"):
        pipeline.write(stage,original.receipt(stage)["gate"],command=[])
    gate=copy.deepcopy(f["pending"]["gate"])
    gate["requested_cycles"]=2
    pipeline._write_wait(gate,2,None)
    batch=dict(schema="FRANKIE_DAY_PIPELINE_RECEIPT_V1",day="20211004",stage="cycles",status="PARTIAL",
        gate=dict(status="requested_cycles_complete",day="20211004",cycles_completed=2,
                  requested_cycles=2,cycles_total=3),
        previous_receipt_sha256=sha(canonical(pipeline.receipt("schedule-prefixes"))))
    (pipeline.directory/"04-cycles-batch-02.json").write_bytes(canonical(batch))
    event=f["event"]
    assert api.archive_event(pipeline,source_commit=event["source_commit"],
        receipts_commit=event["receipts_commit"],configuration_path=event["pipeline_configuration"]["path"],
        runs_root="partial-runs",go=event["go"]) is None


def test_publication_retry_without_local_intent_reuses_exact_remote_consumption(api,publication_repo):
    f=publication_repo
    original=api.publish_receipts(f["pipeline"],f["event"],"wait")
    Path("workflow-event-outbox").rename("retained-first-attempt-outbox")
    confirmed=api.publish_receipts(f["pipeline"],f["event"],"wait")
    assert confirmed==original
    assert f["git"]("ls-remote","--heads","origin","refs/heads/"+f["ref"]).split()[0]==original
    assert Path("retained-first-attempt-outbox/receipt-publication-intent.json").is_file()
