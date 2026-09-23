"""Existing registered workflow routes events without host startup, ingest or cleanup."""
import json
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
REGISTERED=ROOT/".github/workflows/frankie_journal_stack.yml"
CONTINUATION=ROOT/".github/workflows/frankie_workflow_continuation.yml"

def workflow(path):
    return yaml.safe_load(path.read_text())

@pytest.mark.parametrize("job",["sources","journal","host","cleanup","checks"])
def test_existing_operational_jobs_are_explicitly_excluded_for_continuation(job):
    value=workflow(REGISTERED)["jobs"][job]
    assert "inputs.continuation_event == ''" in value["if"]

def test_registered_route_forwards_exact_event_into_existing_workflow_call():
    value=workflow(REGISTERED)["jobs"]["continuation"]
    assert value["uses"]=="./.github/workflows/frankie_workflow_continuation.yml"
    assert value["with"]=={"continuation_event":"${{ inputs.continuation_event }}"}
    assert "inputs.continuation_event != ''" in value["if"]
    assert "workflow_dispatch" in value["if"]

def source_guard():
    steps=workflow(CONTINUATION)["jobs"]["validate"]["steps"]
    index=next(i for i,step in enumerate(steps) if "unchanged executable caller" in step.get("name",""))
    assert index<next(i for i,step in enumerate(steps) if step.get("id")=="bound")
    run=steps[index]["run"]
    return run.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]

@pytest.mark.parametrize("changes",[
    "",
    "A\truns/20211004/04-cycles-wait-"+("a"*64)+".json\n",
    "A\tresearch/kalshi/frankie_boss/runs/request-archives/request/artifact.json\n",
])
def test_actual_embedded_caller_guard_checks_diff_before_exact_source_checkout(tmp_path,monkeypatch,changes):
    monkeypatch.chdir(tmp_path)
    event=dict(source_commit="d"*40,runs_root="runs",day="20211004")
    monkeypatch.setenv("EVENT_JSON",json.dumps(event))
    monkeypatch.setenv("CALLER_COMMIT","e"*40)
    calls=[]
    monkeypatch.setattr(subprocess,"run",lambda argv,**kw:calls.append(argv))
    monkeypatch.setattr(subprocess,"check_output",lambda argv,**kw:calls.append(argv) or changes)
    exec(compile(source_guard(),"<actual workflow caller guard>","exec"),{})
    assert calls==[
        ["git","fetch","--no-tags","--depth=1","origin","d"*40],
        ["git","diff","--name-status","d"*40,"e"*40],
        ["git","checkout","--detach","d"*40],
    ]
    assert json.loads(Path("continuation-event.json").read_bytes())==event

@pytest.mark.parametrize("changes",[
    "M\truns/20211004/03-schedule-prefixes.json\n",
    "D\truns/20211004/00-stage-sources.json\n",
    "A\t.github/workflows/frankie_deliver_readiness.yml\n",
    "A\tresearch/kalshi/frankie_boss/operations/workflow_event_bridge.py\n",
    "A\truns/20211005/04-cycles.json\n",
])
def test_actual_embedded_caller_guard_refuses_changed_executable_or_foreign_evidence(tmp_path,monkeypatch,changes):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVENT_JSON",json.dumps(dict(source_commit="d"*40,runs_root="runs",day="20211004")))
    monkeypatch.setenv("CALLER_COMMIT","e"*40)
    calls=[]
    monkeypatch.setattr(subprocess,"run",lambda argv,**kw:calls.append(argv))
    monkeypatch.setattr(subprocess,"check_output",lambda argv,**kw:changes)
    with pytest.raises(SystemExit):
        exec(compile(source_guard(),"<actual workflow caller guard>","exec"),{})
    assert not any("checkout" in argv for argv in calls)
    assert not Path("continuation-event.json").exists()

@pytest.mark.parametrize("job",["archive","readiness","principal"])
def test_delivery_requires_owner_release_and_unconsumed_event(job):
    guard=workflow(CONTINUATION)["jobs"][job]["if"]
    assert "needs.validate.outputs.released == 'true'" in guard
    assert "needs.validate.outputs.consumed != 'true'" in guard

def test_resume_requires_successful_verified_delivery_and_does_not_run_whole_pipeline():
    value=workflow(CONTINUATION)["jobs"]["resume"]
    assert set(value["needs"])=={"validate","readiness","principal"}
    assert "needs.readiness.result == 'success' || needs.principal.result == 'success'" in value["if"]
    assert "needs.validate.outputs.released == 'true'" in value["if"]
    commands="\n".join(step.get("run","") for step in value["steps"])
    assert '"$BRIDGE" resume --event continuation-event.json' in commands
    assert "--ensure-host-online" not in commands and "--stop-compute" not in commands
    assert "--until" not in commands

def test_finalization_requires_retained_result_and_successful_or_unneeded_next_archive():
    value=workflow(CONTINUATION)["jobs"]["finalize"]
    assert set(value["needs"])=={"validate","resume","next_archive"}
    assert "needs.resume.result == 'success'" in value["if"]
    assert "needs.resume.outputs.resumed == 'true'" in value["if"]
    assert "needs.next_archive.result == 'success' || needs.next_archive.result == 'skipped'" in value["if"]
    steps=value["steps"]
    download=next(i for i,step in enumerate(steps) if step.get("uses","").startswith("actions/download-artifact@"))
    finalize=next(i for i,step in enumerate(steps) if " finalize " in step.get("run",""))
    assert download<finalize
    assert steps[download]["with"]["name"]=="continuation-resume-${{ github.run_id }}-${{ github.run_attempt }}"
