"""Durable code-bound host-state preservation in isolated CI directories.

No host, SSM, ingestion, model, or Classroom execution. PowerShell is required:
a missing interpreter fails the fixture instead of silently skipping coverage.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/aws/host/frankie_host_supersede_code_bound_state.ps1"
JOURNAL_ROOT = ROOT / "research/kalshi/frankie_boss"
OLD = "a" * 40
INTENT_SCHEMA = "FRANKIE_CODE_BOUND_STATE_INTENT_V1"
RECEIPT_SCHEMA = "FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1"


def digest(body):
    return hashlib.sha256(body).hexdigest()


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_files(day, schema):
    result = {}
    for path in day.glob("superseded-code-bound-state-*.json"):
        value = read_json(path)
        if value.get("schema") == schema:
            result[path] = value
    return result


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def command(*args):
    return subprocess.run(
        args, check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()


@pytest.fixture
def state(tmp_path, monkeypatch):
    pwsh = shutil.which("pwsh")
    assert pwsh, "These behavioral tests require PowerShell; install pwsh in CI."

    # Load the real stdlib-only modules without the package's torch import.
    monkeypatch.syspath_prepend(str(JOURNAL_ROOT))
    journal = importlib.import_module("c15_journal")

    tools = tmp_path / "tools"
    for relative in ("research", "research/kalshi", "research/kalshi/frankie_boss"):
        directory = tools / relative
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    for name in ("c15_journal.py", "causal_packet.py"):
        shutil.copyfile(JOURNAL_ROOT / name, tools / "research/kalshi/frankie_boss" / name)
    command("git", "init", "--quiet", str(tools))
    command(
        "git", "-C", str(tools),
        "-c", "user.name=Preservation fixture",
        "-c", "user.email=preservation@example.invalid",
        "-c", "core.hooksPath=/dev/null",
        "commit", "--allow-empty", "--no-gpg-sign", "--quiet", "-m", "fixture",
    )
    head = command("git", "-C", str(tools), "rev-parse", "HEAD")
    run_root = tmp_path / "runs"
    day = run_root / "20211003"
    run = day / "run"
    run.mkdir(parents=True)

    def packed(value):
        return json.dumps(journal.pack(value), separators=(",", ":")).encode()

    moved = {
        "initialization.c15.json": packed({"boss_commit": OLD}),
        "training.sqlite": b"retained checkpoint bytes\x00\xff",
        "host-identity.c15.json": packed({
            "configuration": {"host_runtime": {"boss_commit": OLD}},
        }),
        "execution/execution-identity.c15.json": packed({"boss_commit": OLD}),
        "root-extra.c15.json": packed({"boss_commit": OLD}),
        "execution/extra.c15.json": packed({"boss_commit": OLD}),
        "execution/cycle-00/extra.c15.json": packed({"boss_commit": OLD}),
        "training-witnesses/state-a.c15.json": packed({"checkpoint": "alpha"}),
        "training-witnesses/nested/state-b.c15.json": b"\x00\x80\xff\n",
        "training-witnesses/.hidden": b"hidden retained evidence",
    }
    for name in (
        "host-preparation.c15.json", "host-service.c15.json",
        "host-context-cache.c15.json", "request-plan.c15.json",
        "actual-critic-request.json", "host-ready-instance.c15.json",
    ):
        moved[f"execution/cycle-00/{name}"] = packed({"boss_commit": OLD})

    kept = {
        "host-instance.c15.json": packed({"instance": "retained", "boss_commit": OLD}),
        "native-host-runtime.json": b'{"resume":"retained"}',
        "cycles.sqlite": b"cycle ledger",
        "lessons.sqlite": b"lesson ledger",
        "verified-root.c15.json": packed({"boss_commit": OLD}),
        "genesis.c15.json": packed({"boss_commit": OLD}),
        "append-0001.c15.json": packed({"boss_commit": OLD}),
        "execution/genesis.c15.json": packed({"boss_commit": OLD}),
        "execution/cycle-00/append-0001.c15.json": packed({"boss_commit": OLD}),
        "execution/cycle-01/completion.c15.json": packed({"boss_commit": OLD}),
        "execution/cycle-01/host-preparation.c15.json": packed({"boss_commit": OLD}),
    }
    for relative, body in {**moved, **kept}.items():
        write(run / relative, body)
    (run / "training-witnesses/nested/empty").mkdir()

    config = {
        "run_directory": str(run),
        "run_id": "isolated-preservation-fixture",
        "host_runtime": {"boss_commit": head},
    }
    write(day / "actual-host-configuration.json", json.dumps(config).encode())
    expected_items = {
        relative for relative in moved if not relative.startswith("training-witnesses/")
    } | {"training-witnesses"}
    return SimpleNamespace(
        tmp=tmp_path, tools=tools, run_root=run_root, day=day, run=run,
        head=head, pwsh=pwsh, moved=moved, kept=kept, expected_items=expected_items,
    )


def invoke(state, *, before=False, after=0):
    capture = state.tmp / f"move-observation-{uuid.uuid4().hex}.json"
    prelude = f"""
$ErrorActionPreference = 'Stop'
$Day = '20211003'
$RunRoot = {ps_quote(state.run_root)}
$ToolsRoot = {ps_quote(state.tools)}
$Python = {ps_quote(sys.executable)}
$CycleIndex = '00'
$global:hostMoves = 0
$global:observationPath = {ps_quote(capture)}
$global:intentDirectory = {ps_quote(state.day)}
$global:failBeforeMove = ${str(before).lower()}
$global:failAfterMove = {after}
function Get-Date {{
    [DateTime]::Parse('2026-09-22T12:00:00Z').ToUniversalTime()
}}
function Move-Item {{
    param([string]$LiteralPath, [string]$Destination)
    $global:hostMoves += 1
    if ($global:hostMoves -eq 1) {{
        $intents = @(Get-ChildItem -LiteralPath $global:intentDirectory -Filter '*.intent.json' |
            ForEach-Object {{
                [ordered]@{{
                    path = $_.FullName
                    content = [IO.File]::ReadAllText($_.FullName)
                }}
            }})
        $observation = [ordered]@{{
            source = $LiteralPath
            destination = $Destination
            intents = $intents
        }}
        [IO.File]::WriteAllText(
            $global:observationPath, ($observation | ConvertTo-Json -Depth 100))
    }}
    if ($global:failBeforeMove) {{ throw 'TEST_INTERRUPT_BEFORE_MOVE' }}
    Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath -Destination $Destination
    if ($global:failAfterMove -eq $global:hostMoves) {{
        throw 'TEST_INTERRUPT_AFTER_MOVE'
    }}
}}
try {{
    & {ps_quote(SCRIPT)}
}} catch {{
    [Console]::Error.WriteLine($_.ToString())
    exit 37
}}
"""
    result = subprocess.run(
        [state.pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", prelude],
        capture_output=True, text=True, timeout=60,
    )
    return result, capture


def assert_success(result):
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def assert_kept(state):
    for relative, body in state.kept.items():
        assert (state.run / relative).read_bytes() == body, relative


def assert_preserved(state, receipt):
    target = Path(receipt["superseded_root"])
    assert {item["relative"] for item in receipt["moved"]} == state.expected_items
    for relative, body in state.moved.items():
        assert not (state.run / relative).exists(), relative
        assert (target / relative).read_bytes() == body, relative
    assert (target / "training-witnesses/nested/empty").is_dir()
    assert_kept(state)


def test_complete_parseable_intent_exists_before_first_move(state):
    result, capture = invoke(state, before=True)
    assert result.returncode != 0
    assert "TEST_INTERRUPT_BEFORE_MOVE" in result.stderr
    observed = read_json(capture)
    assert len(observed["intents"]) == 1
    record = observed["intents"][0]
    intent = json.loads(record["content"])
    assert Path(record["path"]).read_text(encoding="utf-8-sig") == record["content"]
    assert intent["schema"] == INTENT_SCHEMA
    assert intent["stored_boss_commit"] == OLD
    assert intent["current_boss_commit"] == state.head
    assert intent["cycle_index"] == "00"
    assert intent["run_directory"] == str(state.run)
    assert intent["run_id"] == "isolated-preservation-fixture"
    assert {item["relative"] for item in intent["items"]} == state.expected_items
    for item in intent["items"]:
        assert item["destination"] == str(Path(intent["superseded_root"]) / item["relative"])
        assert item["manifest"]
        if item["relative"] in state.moved:
            body = state.moved[item["relative"]]
            assert item["sha256"] == digest(body)
            assert item["bytes"] == len(body)
    for relative, body in state.moved.items():
        assert (state.run / relative).read_bytes() == body
    assert not json_files(state.day, RECEIPT_SCHEMA)
    assert_kept(state)


@pytest.mark.parametrize("after", [1, 5])
def test_interruption_after_real_move_reconciles_same_intent_without_loss(state, after):
    result, _ = invoke(state, after=after)
    assert result.returncode != 0
    assert "TEST_INTERRUPT_AFTER_MOVE" in result.stderr
    intents = json_files(state.day, INTENT_SCHEMA)
    assert len(intents) == 1
    intent_path, intent = next(iter(intents.items()))
    intent_bytes = intent_path.read_bytes()
    gone = sum(not (state.run / item["relative"]).exists() for item in intent["items"])
    assert gone == after
    if after == 5:
        assert not (state.run / "host-identity.c15.json").exists()
        assert not (state.run / "execution/execution-identity.c15.json").exists()
    assert not json_files(state.day, RECEIPT_SCHEMA)

    result, _ = invoke(state)
    assert_success(result)
    assert set(json_files(state.day, INTENT_SCHEMA)) == {intent_path}
    assert intent_path.read_bytes() == intent_bytes
    receipts = json_files(state.day, RECEIPT_SCHEMA)
    assert len(receipts) == 1
    receipt = next(iter(receipts.values()))
    assert receipt["intent_path"] == str(intent_path)
    assert receipt["intent_sha256"] == digest(intent_bytes)
    assert receipt["superseded_root"] == intent["superseded_root"]
    assert_preserved(state, receipt)


def test_directory_manifest_witnesses_every_file_and_empty_directory(state):
    result, _ = invoke(state)
    assert_success(result)
    intent = next(iter(json_files(state.day, INTENT_SCHEMA).values()))
    witness = next(item for item in intent["items"] if item["relative"] == "training-witnesses")
    entries = {entry["relative"]: entry for entry in witness["manifest"]}
    assert len(entries) == len(witness["manifest"]), "Manifest contains duplicate paths"
    expected_files = {
        relative.removeprefix("training-witnesses/"): body
        for relative, body in state.moved.items()
        if relative.startswith("training-witnesses/")
    }
    assert set(entries) == {".", "nested", "nested/empty"} | set(expected_files)
    for relative in (".", "nested", "nested/empty"):
        assert entries[relative]["kind"] == "directory"
    for relative, body in expected_files.items():
        assert entries[relative]["kind"] == "file"
        assert entries[relative]["sha256"] == digest(body)
        assert entries[relative]["bytes"] == len(body)
    receipt = next(iter(json_files(state.day, RECEIPT_SCHEMA).values()))
    assert_preserved(state, receipt)


@pytest.mark.parametrize(
    "relative", ["execution", "training.sqlite", "training-witnesses/nested/state-b.c15.json"]
)
def test_symlink_sources_ancestors_and_manifest_children_refuse_before_moves(state, relative):
    source = state.run / relative
    external = state.tmp / "outside" / source.name
    external.parent.mkdir(parents=True)
    source.rename(external)
    source.symlink_to(external, target_is_directory=external.is_dir())
    external_bytes = {
        p.relative_to(external): p.read_bytes()
        for p in external.rglob("*") if p.is_file()
    } if external.is_dir() else {Path("."): external.read_bytes()}

    result, capture = invoke(state)
    assert result.returncode != 0, result.stdout
    assert not capture.exists(), "Refusal must precede the first move"
    assert source.is_symlink()
    for relative_path, body in external_bytes.items():
        path = external if relative_path == Path(".") else external / relative_path
        assert path.read_bytes() == body
    assert not json_files(state.day, RECEIPT_SCHEMA)
    assert (state.run / "initialization.c15.json").read_bytes() == state.moved["initialization.c15.json"]
    assert_kept(state)


@pytest.mark.parametrize("escape", ["source", "destination"])
def test_unfinished_intent_cannot_escape_into_a_sibling_with_the_same_prefix(state, escape):
    result, _ = invoke(state, before=True)
    assert result.returncode != 0
    assert "TEST_INTERRUPT_BEFORE_MOVE" in result.stderr
    path, intent = next(iter(json_files(state.day, INTENT_SCHEMA).items()))
    item = intent["items"][0]
    if escape == "source":
        outside = state.run.with_name(state.run.name + "-escape")
        victim = outside / "victim"
        item["relative"] = "../" + outside.name + "/victim"
    else:
        outside = Path(intent["superseded_root"] + "-escape")
        victim = outside / "victim"
        item["destination"] = str(victim)
    write(victim, b"outside evidence must survive")
    path.write_text(json.dumps(intent), encoding="utf-8")

    result, capture = invoke(state)
    assert result.returncode != 0, result.stdout
    assert not capture.exists(), "Untrusted intent must be rejected before any move"
    assert victim.read_bytes() == b"outside evidence must survive"
    assert not json_files(state.day, RECEIPT_SCHEMA)
    for relative, body in state.moved.items():
        assert (state.run / relative).read_bytes() == body
    assert_kept(state)


def test_same_second_generations_never_overwrite_receipts_or_preserved_bytes(state):
    result, _ = invoke(state)
    assert_success(result)
    original = {
        path: path.read_bytes()
        for path in state.day.glob("superseded-code-bound-state-*.json")
    }
    first = next(iter(json_files(state.day, RECEIPT_SCHEMA).values()))
    assert_preserved(state, first)

    # A second genuine stale generation in the same frozen wall-clock second.
    for relative, body in state.moved.items():
        write(state.run / relative, body)
    (state.run / "training-witnesses/nested/empty").mkdir()
    result, _ = invoke(state)
    assert_success(result)

    for path, body in original.items():
        assert path.read_bytes() == body, f"Overwritten evidence: {path.name}"
    receipts = json_files(state.day, RECEIPT_SCHEMA)
    assert len(receipts) == 2
    assert len(json_files(state.day, INTENT_SCHEMA)) == 2
    assert len({value["superseded_root"] for value in receipts.values()}) == 2
    assert len({value["intent_path"] for value in receipts.values()}) == 2
    for receipt in receipts.values():
        assert_preserved(state, receipt)
        intent_path = Path(receipt["intent_path"])
        assert receipt["intent_sha256"] == digest(intent_path.read_bytes())
