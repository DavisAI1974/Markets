"""Durable WAIT receipt tests: all evidence lives in disposable CI directories."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "research/kalshi/frankie_boss/operations/workflow_wait.py"

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

@pytest.fixture
def api():
    spec = importlib.util.spec_from_file_location("wait_receipt_under_test",MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def state(tmp_path):
    run = tmp_path/"retained-run"
    cycle = run/"execution/cycle-00"
    cycle.mkdir(parents=True)
    files = {
        "host-identity.c15.json": b'{"fixture":"identity","value":9223372036854775807}\r\n',
        "execution/cycle-00/host-preparation.c15.json": b'{"fixture":"prepared","checkpoint":"exact"}\r\n',
        "execution/cycle-00/actual-critic-request.json": b'{"request":"full exact content","as_of":1633302000123456789}\r\n',
    }
    for name,raw in files.items():
        (run/name).write_bytes(raw)
    configuration = dict(run_id="fixture-run",run_directory=str(run),host_runtime=dict(
        boss_commit="a"*40,schedule=dict(path=str(tmp_path/"schedule.json"),sha256="b"*64)))
    return dict(run=run,cycle=cycle,files=files,configuration=configuration)

def write(api,state,kind="readiness",**kw):
    return api.write_wait_receipt(state["configuration"],state["cycle"],kind,**kw)

def test_receipt_binds_same_run_exact_artifact_bytes_without_copying_context(api,state):
    result = write(api,state)
    assert result["status"] == "workflow_wait"
    path = Path(result["receipt_path"])
    assert path.is_relative_to(state["run"])
    raw = path.read_bytes()
    assert sha(raw) == result["receipt_sha256"]
    receipt = api.read_wait_receipt(path,expected_sha256=result["receipt_sha256"],configuration=state["configuration"])
    assert receipt == result["wait_receipt"]
    assert receipt["schema"] == "FRANKIE_WORKFLOW_WAIT_V1"
    assert receipt["state"] == "WAIT" and receipt["kind"] == "readiness"
    assert receipt["request_id"] == "fixture-run-cycle-00" and receipt["cycle_index"] == 0
    assert receipt["run_id"] == "fixture-run"
    assert receipt["configuration_sha256"] == sha(canonical(state["configuration"]))
    assert receipt["boss_commit"] == "a"*40 and receipt["schedule_sha256"] == "b"*64
    identity = dict(receipt)
    identity.pop("receipt_id")
    assert receipt["receipt_id"] == sha(canonical(identity))
    for name,body in state["files"].items():
        assert receipt["artifacts"][name] == dict(sha256=sha(body),bytes=len(body))
        assert (state["run"]/name).read_bytes() == body
        assert body not in raw

def test_unchanged_wait_replay_returns_same_receipt_and_keeps_every_byte(api,state):
    first = write(api,state)
    retained = {p:p.read_bytes() for p in state["run"].rglob("*") if p.is_file()}
    second = write(api,state)
    assert second == first
    assert all(p.read_bytes()==raw for p,raw in retained.items())

@pytest.mark.parametrize("name",[
    "host-identity.c15.json","execution/cycle-00/host-preparation.c15.json",
    "execution/cycle-00/actual-critic-request.json"])
def test_missing_required_context_refuses_wait_creation(api,state,name):
    # Disposable fixture manipulation only; no canonical evidence is touched.
    (state["run"]/name).rename(state["run"]/(name+".fixture-retained"))
    with pytest.raises((ValueError,OSError)):
        write(api,state)

@pytest.mark.parametrize("name",[
    "host-identity.c15.json","execution/cycle-00/host-preparation.c15.json",
    "execution/cycle-00/actual-critic-request.json"])
def test_changed_retained_context_refuses_reentry(api,state,name):
    result = write(api,state)
    (state["run"]/name).write_bytes(b"changed")
    with pytest.raises((ValueError,OSError)):
        api.read_wait_receipt(result["receipt_path"],expected_sha256=result["receipt_sha256"],configuration=state["configuration"])

@pytest.mark.parametrize("change",[
    {"run_id":"other-run"},{"host_runtime":{"boss_commit":"c"*40,"schedule":{"sha256":"b"*64}}},
    {"seed":123},{"source_manifest":{"sha256":"d"*64}}
])
def test_changed_configuration_never_reuses_wait(api,state,change):
    result = write(api,state)
    altered = copy.deepcopy(state["configuration"])
    altered.update(change)
    with pytest.raises((ValueError,OSError)):
        api.read_wait_receipt(result["receipt_path"],expected_sha256=result["receipt_sha256"],configuration=altered)

def test_foreign_receipt_hash_is_refused(api,state):
    result = write(api,state)
    with pytest.raises((ValueError,OSError)):
        api.read_wait_receipt(result["receipt_path"],expected_sha256="0"*64,configuration=state["configuration"])

def test_tampered_receipt_cannot_be_admitted_even_with_new_file_hash(api,state):
    result = write(api,state)
    path = Path(result["receipt_path"])
    changed = json.loads(path.read_bytes())
    changed["request_id"] = "foreign-cycle-00"
    raw = canonical(changed)+b"\n"
    path.write_bytes(raw)
    with pytest.raises((ValueError,OSError)):
        api.read_wait_receipt(path,expected_sha256=sha(raw),configuration=state["configuration"])

def test_principal_wait_requires_retained_plan_and_request(api,state):
    with pytest.raises((ValueError,OSError)):
        write(api,state,"principal")
    (state["cycle"]/"request-plan.c15.json").write_bytes(b"exact retained controller plan")
    with pytest.raises((ValueError,OSError)):
        write(api,state,"principal")
    principal = state["cycle"]/"principal"
    principal.mkdir()
    (principal/"session-request.json").write_bytes(b"exact principal session")
    result = write(api,state,"principal")
    assert result["wait_receipt"]["artifacts"]["execution/cycle-00/request-plan.c15.json"]["sha256"] == sha(b"exact retained controller plan")
    assert result["wait_receipt"]["artifacts"]["execution/cycle-00/principal/session-request.json"]["sha256"] == sha(b"exact principal session")

def test_existing_dispatch_and_correction_requests_are_retained_under_same_identity(api,state):
    spool = state["cycle"]/"critic-spool"/("d"*64)
    spool.mkdir(parents=True)
    (spool/"dispatch.json").write_bytes(b'{"same_job":"retained"}')
    principal = state["cycle"]/"principal"
    principal.mkdir()
    (principal/"session-request.json").write_bytes(b"original")
    (principal/"session-correction-request.json").write_bytes(b"correction")
    (state["cycle"]/"request-plan.c15.json").write_bytes(b"plan")
    result = write(api,state,"principal")
    artifacts = result["wait_receipt"]["artifacts"]
    assert "execution/cycle-00/critic-spool/"+("d"*64)+"/dispatch.json" in artifacts
    assert "execution/cycle-00/principal/session-correction-request.json" in artifacts

@pytest.mark.parametrize("job",[None,"bad","A"*64])
def test_same_job_attention_requires_an_exact_job_id(api,state,job):
    with pytest.raises((ValueError,OSError)):
        write(api,state,"same_job",state="ATTENTION",job_id=job)

def test_attention_retains_exact_job_and_never_becomes_readiness(api,state):
    result = write(api,state,"same_job",state="ATTENTION",job_id="c"*64)
    assert result["status"] == "workflow_attention"
    assert result["wait_receipt"]["state"] == "ATTENTION"
    assert result["wait_receipt"]["job_id"] == "c"*64
    assert result["wait_receipt"]["kind"] == "same_job"

def test_symlinked_artifact_cannot_bind_outside_context(api,state,tmp_path):
    artifact = state["cycle"]/"actual-critic-request.json"
    outside = tmp_path/"outside.json"
    outside.write_bytes(artifact.read_bytes())
    artifact.rename(artifact.with_name("retained-fixture-request.json"))
    artifact.symlink_to(outside)
    with pytest.raises((ValueError,OSError)):
        write(api,state)

def test_foreign_cycle_directory_cannot_produce_wait(api,state,tmp_path):
    foreign = tmp_path/"foreign/execution/cycle-00"
    foreign.mkdir(parents=True)
    with pytest.raises((ValueError,OSError)):
        api.write_wait_receipt(state["configuration"],foreign,"readiness")

def test_wait_cannot_succeed_when_durable_flush_fails(api,state,monkeypatch):
    def fail(fd):
        raise OSError("injected durable flush failure")
    monkeypatch.setattr(api.os,"fsync",fail)
    with pytest.raises(OSError):
        write(api,state)
    for name,raw in state["files"].items():
        assert (state["run"]/name).read_bytes()==raw

def test_unpinned_reentry_returns_same_pending_without_advancing(api,state):
    result = write(api,state)
    with pytest.raises(api.WorkflowPending) as caught:
        api.resume_admission(state["configuration"])
    assert caught.value.result == result
    assert caught.value.exit_code == 3

def test_exact_wait_receipt_admits_only_its_existing_cycle(api,state):
    result = write(api,state)
    assert api.resume_admission(state["configuration"],result["receipt_sha256"]) == 1

@pytest.mark.parametrize("pin",["0"*64,"invalid",""])
def test_invalid_resume_event_never_admits_a_new_cycle(api,state,pin):
    write(api,state)
    with pytest.raises(ValueError):
        api.resume_admission(state["configuration"],pin)

def test_resume_event_without_any_retained_wait_refuses_new_run(api,state):
    with pytest.raises(ValueError):
        api.resume_admission(state["configuration"],"0"*64)

def test_attention_cannot_be_used_as_automatic_resume_authority(api,state):
    result = write(api,state,"same_job",state="ATTENTION",job_id="c"*64)
    with pytest.raises(api.WorkflowPending) as caught:
        api.resume_admission(state["configuration"])
    assert caught.value.exit_code == 4
    with pytest.raises(ValueError):
        api.resume_admission(state["configuration"],result["receipt_sha256"])

def test_resolution_requires_actual_admitted_artifact_and_keeps_wait_evidence(api,state):
    result = write(api,state)
    raw = Path(result["receipt_path"]).read_bytes()
    with pytest.raises(ValueError):
        api.resolve_wait(result,[])
    response = state["cycle"]/"verified-response.json"
    response.write_bytes(b"admitted response")
    api.resolve_wait(result,[response])
    assert Path(result["receipt_path"]).read_bytes()==raw
    assert api.pending_receipts(state["configuration"],state["cycle"]) == []
    assert api.resume_admission(state["configuration"],result["receipt_sha256"]) == 1
    assert api.resume_admission(state["configuration"]) is None

def test_changed_admitted_response_cannot_resolve_a_retained_wait(api,state):
    result = write(api,state)
    response = state["cycle"]/"verified-response.json"
    response.write_bytes(b"admitted response")
    api.resolve_wait(result,[response])
    response.write_bytes(b"changed")
    with pytest.raises(ValueError):
        api.pending_receipts(state["configuration"],state["cycle"])

def test_newer_boundary_cannot_be_bypassed_by_duplicate_old_event(api,state):
    first = write(api,state)
    admitted = state["cycle"]/"verified-response.json"
    admitted.write_bytes(b"admitted service")
    api.resolve_wait(first,[admitted])
    (state["cycle"]/"request-plan.c15.json").write_bytes(b"plan")
    principal=state["cycle"]/"principal"
    principal.mkdir()
    (principal/"session-request.json").write_bytes(b"principal exact request")
    second = write(api,state,"principal")
    with pytest.raises(api.WorkflowPending) as caught:
        api.resume_admission(state["configuration"],first["receipt_sha256"])
    assert caught.value.result == second

def test_changed_artifact_after_durable_wait_cannot_be_rewritten_as_new_identity(api,state):
    first = write(api,state)
    raw=Path(first["receipt_path"]).read_bytes()
    (state["cycle"]/"actual-critic-request.json").write_bytes(b"other request")
    with pytest.raises(ValueError):
        write(api,state)
    assert Path(first["receipt_path"]).read_bytes()==raw
