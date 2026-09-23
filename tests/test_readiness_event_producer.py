"""Isolated producer contract checks; no network, runtime, or model imports."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / ".github/workflows/frankie_retained_granite.yml"
COMPOSITE = ROOT / ".github/actions/frankie-workflow-event/action.yml"


def document(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def composite_steps():
    return document(COMPOSITE)["runs"]["steps"]


def test_readiness_hook_is_optional_prepare_only_and_after_successful_upload():
    workflow = document(PRODUCER)
    trigger = workflow.get("on", workflow.get(True))
    field = trigger["workflow_dispatch"]["inputs"]["continuation_event"]
    assert field["required"] is False and field["type"] == "string"
    job = workflow["jobs"]["retained"]
    steps = job["steps"]
    hooks = [(index, step) for index, step in enumerate(steps)
             if step.get("uses") == "./.github/actions/frankie-workflow-event"]
    assert len(hooks) == 1
    index, hook = hooks[0]
    assert hook["continue-on-error"] is True
    assert "matrix.role == 'prepare'" in hook["if"]
    assert "inputs.continuation_event != ''" in hook["if"]
    assert "always()" not in hook["if"]
    upload = steps[index-1]
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == "retained-granite-ready-${{ github.run_id }}"
    assert upload["with"]["if-no-files-found"] == "error"
    assert "continue-on-error" not in upload
    assert steps[index+1]["run"].endswith("granite_retained_host hold")
    assert hook["with"] == {
        "event_json": "${{ inputs.continuation_event }}",
        "ready_run_id": "${{ github.run_id }}",
        "ready_source_commit": "${{ github.sha }}",
        "request_sha256": "${{ inputs.request_sha256 }}",
    }
    assert job["permissions"] == {"contents": "read", "actions": "write"}


def test_producer_preserves_existing_runtime_and_recovery_commands():
    steps = document(PRODUCER)["jobs"]["retained"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert commands == [
        "python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu\n"
        "python -m pip install numpy==2.4.3 boto3==1.42.23 transformers==5.8.0 tokenizers==0.22.2 cryptography==46.0.3\n",
        "python -m research.kalshi.frankie_boss.granite_retained_host ${{ matrix.role }}",
        "python -m research.kalshi.frankie_boss.granite_retained_host hold",
        "python -m research.kalshi.frankie_boss.granite_retained_host cleanup",
    ]
    cleanup = next(step for step in steps if step.get("run", "").endswith("granite_retained_host cleanup"))
    assert cleanup["if"] == "always()"


def test_composite_preserves_separate_checkout_and_upload_before_dispatch():
    steps = composite_steps()
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["path"] == "workflow-event-transport"
    assert checkout["with"]["ref"] == "${{ fromJSON(inputs.event_json).source_commit }}"
    prepare = next(i for i, step in enumerate(steps) if " prepare-outbox " in step.get("run", ""))
    dispatch = next(i for i, step in enumerate(steps) if " dispatch " in step.get("run", ""))
    uploads = [(i, step) for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert any(prepare < i < dispatch and step["with"].get("if-no-files-found") == "error"
               and step["with"]["path"] == "workflow-event-transport/workflow-event-outbox/"
               for i, step in uploads)
    for step in steps[prepare:dispatch+1]:
        assert step.get("continue-on-error") is not True
    assert "always()" not in steps[dispatch].get("if", "")
    assert steps[dispatch]["env"]["WORKFLOW_OUTBOX_ARTIFACT_CONFIRMED"] == "true"
    assert steps[dispatch]["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert steps[dispatch]["working-directory"] == "workflow-event-transport"
    assert any(i > dispatch and step.get("if") == "always()" for i, step in uploads)
    for step in steps:
        assert "${{ inputs.event_json }}" not in step.get("run", "")


def derivation_ast():
    step = next(step for step in composite_steps() if " prepare-outbox " in step.get("run", ""))
    source = step["run"].split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    tree = ast.parse(source)
    # Execute the actual embedded derivation after the independent source preflight.
    start = next(i for i, node in enumerate(tree.body)
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "event" for target in node.targets))
    return compile(ast.Module(body=tree.body[start:], type_ignores=[]), "<embedded-producer>", "exec")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def seal(value):
    body = {key: item for key, item in value.items() if key != "event_id"}
    return dict(body, event_id=hashlib.sha256(canonical(body)).hexdigest())


@pytest.fixture
def template():
    return seal(dict(schema="FRANKIE_WORKFLOW_EVENT_V1", action="archive", source_commit="a"*40,
        receipts_commit="b"*40, day="20260923", go="c"*64,
        pipeline_configuration={"path": "config/pipeline.json", "sha256": "d"*64},
        runs_root="runs", context={"request_sha256": "e"*64, "wait_receipt_sha256": "f"*64},
        payload={"instance": "i-original", "request_sha256": "e"*64, "cycle_index": "00"}))


def derive(tmp_path, monkeypatch, template, *, run_id="12345", request=None):
    monkeypatch.chdir(tmp_path)
    env = dict(EVENT_JSON=json.dumps(template), READY_RUN_ID=run_id,
               READY_SOURCE_COMMIT="9"*40, REQUEST_SHA256=request or "e"*64)
    calls = []
    def validate(value):
        calls.append(value)
        assert value == seal(value)
        return value
    module = SimpleNamespace(validate_shape=validate, seal=seal, canonical=canonical)
    exec(derivation_ast(), dict(module=module, os=SimpleNamespace(environ=env), json=json, Path=Path))
    assert calls == [template]
    return json.loads((tmp_path/"continuation-event.json").read_bytes())


def test_actual_embedded_derivation_binds_current_producer_and_keeps_wait(tmp_path, monkeypatch, template):
    output = derive(tmp_path, monkeypatch, template)
    assert output["action"] == "readiness"
    assert output["payload"] == {"ready_run_id": "12345", "ready_source_commit": "9"*40, "instance": "i-original"}
    assert output["event_id"] != template["event_id"]
    assert output == seal(output)
    assert {key: value for key, value in output.items() if key not in ("event_id", "action", "payload")} == {
        key: value for key, value in template.items() if key not in ("event_id", "action", "payload")}


def test_actual_embedded_derivation_refuses_wrong_request_before_outbox(tmp_path, monkeypatch, template):
    with pytest.raises((ValueError, SystemExit), match="request"):
        derive(tmp_path, monkeypatch, template, request="0"*64)
    assert not (tmp_path/"continuation-event.json").exists()


def test_ordinary_exact_event_is_preserved_without_readiness_derivation(tmp_path, monkeypatch, template):
    assert derive(tmp_path, monkeypatch, template, run_id="") == template


def test_composite_source_authority_is_checked_before_bridge_import():
    steps = composite_steps()
    runs = "\n".join(step.get("run", "") for step in steps)
    assert "git" in runs and "diff" in runs and "source_commit" in runs
    assert "GITHUB_SHA" in runs or "CALLER_COMMIT" in runs
    import_at = runs.index("spec.loader.exec_module(module)")
    # The caller/source comparison must happen before code from event-selected source executes.
    diff_at = runs.index("diff")
    assert diff_at < import_at
