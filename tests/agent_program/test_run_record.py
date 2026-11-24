"""Ticket 19: a run's line, report and kept transcript from its own transcript, on real records only.

Expected figures are the auditor's own measurement of run 117's transcript (AUDIT_RUN_120, made with jq),
written here as numbers, not recomputed with the code under test.
"""

import gzip
import hashlib
import json
import shutil

import pytest

from tools.kgraph.run_record import main

from .realrecords import PAPER, data_root


@pytest.fixture
def paper():
    return data_root() / PAPER


@pytest.fixture
def scratch(tmp_path, paper):
    d = tmp_path / "data" / PAPER
    d.mkdir(parents=True)
    shutil.copy(paper / "agent-runs.jsonl", d / "agent-runs.jsonl")
    shutil.copytree(paper / "run-plans", d / "run-plans")
    return tmp_path / "data"


def _figs(capsys, path):
    assert main(["figures", "--transcript", str(path)]) == 0
    return json.loads(capsys.readouterr().out)


def test_figures_run_117_match_the_auditors_measure(paper, capsys):
    f = _figs(capsys, paper / "transcripts/run-0117.jsonl.gz")
    assert f["run_named_in_brief"] == 117
    assert f["models"] == ["claude-haiku-5-5"]
    assert (f["input_tokens_fresh"], f["input_tokens_cache_written"], f["input_tokens_cache_read"]) == (20, 85089, 501509)
    assert f["input_tokens"] == 20 + 85089 + 501509
    assert f["output_tokens"] == 18234
    assert f["model_replies"] == 10
    assert f["tool_calls"] == 30
    assert f["sub_agent_calls"] == 0 and f["hand_backs"] >= 1
    assert f["first"].startswith("2026-11-24T13:10:23.61")
    assert f["wall_clock_ms"] == 80761


def test_figures_run_116(paper, capsys):
    f = _figs(capsys, paper / "transcripts/run-0116.jsonl.gz")
    assert f["tool_calls"] == 4 and f["models"] == ["claude-sonnet-5-5"] and f["run_named_in_brief"] == 116


def test_append_refuses_a_run_that_has_a_line_then_writes_a_correction(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    base = ["append", "--data", str(scratch), "--run", "117", "--transcript", str(t), "--role", "scout",
            "--stage", "s", "--task", "t", "--outcome", "o"]
    assert main(base) == 2 and "already has a line" in capsys.readouterr().err
    assert rec.read_text() == before
    assert main(base + ["--corrects", "figures from the transcript"]) == 0
    new = rec.read_text()[len(before):].strip().splitlines()
    assert len(new) == 1
    d = json.loads(new[0])
    assert d["corrects"] and d["run"] == 117 and d["model"] == "claude-haiku-5-5"
    assert (d["input_tokens_fresh"], d["input_tokens_cache_written"], d["input_tokens_cache_read"], d["output_tokens"]) == (20, 85089, 501509, 18234)
    assert d["input_tokens"] == 586618 and d["model_replies"] == 10 and d["tool_calls"] == 30 and d["wall_clock_ms"] == 80761
    plan = json.loads((paper / "run-plans/run-0117.json").read_text())
    assert d["plan"] == "run-plans/run-0117.json" and d["budget_tokens"] == plan["max_tokens"] == 150000


def test_append_refuses_another_runs_transcript_empty_outcome_and_bad_role(scratch, paper, capsys):
    t = str(paper / "transcripts/run-0117.jsonl.gz")
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    b = ["append", "--data", str(scratch), "--transcript", t, "--stage", "s", "--task", "t"]
    assert main(b + ["--run", "116", "--role", "scout", "--outcome", "o"]) == 2
    assert "names agent run 117" in capsys.readouterr().err
    assert main(b + ["--run", "117", "--role", "scout", "--outcome", " ", "--corrects", "x"]) == 2
    assert "outcome is empty" in capsys.readouterr().err
    assert main(b + ["--run", "117", "--role", "wizard", "--outcome", "o", "--corrects", "x"]) == 2
    assert "wizard" in capsys.readouterr().err
    assert rec.read_text() == before


def test_report_run_117_holds_the_scouts_own_words(paper, tmp_path):
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(paper / "transcripts/run-0117.jsonl.gz"), "--out", str(out), "--title", "Scout run 117"]) == 0
    text = out.read_text()
    assert text.startswith("# Scout run 117")
    assert "nothing below it is the main session's" in text
    assert "SCOUT RUN 0117 REPORT." in text


def test_keep_writes_the_same_bytes_as_the_real_kept_file(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    shutil.rmtree(scratch / PAPER / "transcripts", ignore_errors=True)
    assert main(["keep", "--data", str(scratch), "--run", "117", "--transcript", str(t)]) == 0
    k = scratch / PAPER / "transcripts"
    assert (k / "run-0117.jsonl.gz").read_bytes() == t.read_bytes()
    mine, real = json.loads((k / "run-0117.json").read_text()), json.loads((paper / "transcripts/run-0117.json").read_text())
    assert mine["sha256"] == real["sha256"] and mine["bytes"] == real["bytes"] and mine["lines"] == real["lines"]
    assert mine["agent_id"] == real["agent_id"]
    stamp = (k / "run-0117.json").stat().st_mtime_ns
    capsys.readouterr()
    assert main(["keep", "--data", str(scratch), "--run", "117", "--transcript", str(t)]) == 0
    assert "nothing new" in capsys.readouterr().out
    assert (k / "run-0117.json").stat().st_mtime_ns == stamp
    # another run's transcript is refused
    assert main(["keep", "--data", str(scratch), "--run", "116", "--transcript", str(t)]) == 2


def test_keep_refuses_a_kept_file_with_another_sha(scratch, paper, tmp_path):
    t = paper / "transcripts/run-0117.jsonl.gz"
    k = scratch / PAPER / "transcripts"
    k.mkdir(parents=True, exist_ok=True)
    (k / "run-0117.json").write_text(json.dumps({"run": 117, "sha256": "0" * 64}))
    assert main(["keep", "--data", str(scratch), "--run", "117", "--transcript", str(t)]) == 2


def test_missing_on_the_real_record(paper, capsys):
    assert main(["missing", "--data", str(data_root())]) == 0
    out = capsys.readouterr().out.splitlines()
    row = {int(l.split()[1]): l for l in out if l.startswith("run ")}
    assert "lacks: model, input_tokens, output_tokens |" in row[1]
    assert "wall_clock" not in row[1] and "outcome" not in row[1].split("|")[1]
    assert "lacks: model, input_tokens, output_tokens, wall_clock |" in row[15] or "lacks: input_tokens, output_tokens, wall_clock |" in row[15]
    assert "lacks: nothing" in row[114]
    assert "could fill" in row[116] or "kept transcript exists" in row[116]
    assert "kept transcript exists" in row[117] or "could fill" in row[117]
    assert "no transcript kept" in row[1]
    newest = {}
    for l in (paper / "agent-runs.jsonl").read_text().splitlines():
        if l.strip():
            newest[json.loads(l)["run"]] = json.loads(l)
    n_model = sum(1 for r in newest.values() if not str(r.get("model", "")).startswith("claude-"))
    counts = [l for l in out if l.startswith("COUNTS")][0]
    assert f"runs {len(newest)};" in counts and f"lacking exact model {n_model};" in counts
    print(counts)


def test_data_without_a_record_is_refused(tmp_path, capsys):
    (tmp_path / "MANIFEST.json").write_text("{}")
    assert main(["missing", "--data", str(tmp_path)]) == 2
    assert "does not exist" in capsys.readouterr().err
