"""Ticket 19: a run's line, report and kept transcript from its own transcript, on real records only.

Every check reads a real record or a real transcript. A check that needs a live transcript (this session's
own folder) skips with the reason when the file is not on the machine. Writes go to a scratch folder, never
into markets-data. Where a check needs a case the real record does not hold, it takes a real transcript and
makes exactly one named change to it; those checks stand together in the last section of this file. Expected
figures are the auditor's own measurement of run 117's transcript (AUDIT_RUN_120, made with jq), written here
as numbers and never recomputed with the code under test.
"""

import copy
import gzip
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph.run_record import main

from .realrecords import PAPER, data_root

LIVE = Path("/root/.claude/projects/-home-user/3356516d-d71a-5e13-907d-ff8d8ffcb6d4/subagents")
COMMIT_OF_THE_REVIEW = "6e234e2"


def live(agent_id):
    p = LIVE / f"agent-{agent_id}.jsonl"
    if not p.exists():
        pytest.skip(f"live transcript {p} is not on this machine")
    return p


def live_for_run(n):
    """The live transcript whose brief opens with 'agent run n' (found by reading, for the traps)."""
    if not LIVE.exists():
        pytest.skip(f"live folder {LIVE} is not on this machine")
    for p in sorted(LIVE.glob("agent-*.jsonl")):
        with p.open(encoding="utf-8") as f:
            c = json.loads(f.readline()).get("message", {}).get("content")
        m = re.search(r"agent run (\d+)", c[:200]) if isinstance(c, str) else None
        if m and int(m.group(1)) == n:
            return p
    pytest.skip(f"no live transcript for run {n} on this machine")


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
    capsys.readouterr()
    assert main(["figures", "--transcript", str(path)]) == 0
    return json.loads(capsys.readouterr().out)


def _newest(path, run):
    got = None
    for l in path.read_text().splitlines():
        if l.strip() and json.loads(l)["run"] == run:
            got = json.loads(l)
    return got


def _aid(path):
    """The agent id on the first line of a transcript, read by hand (the id the main session was given)."""
    raw = Path(path).read_bytes()
    raw = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    return json.loads(raw.decode().splitlines()[0])["agentId"]


def _append_args(scratch, t, run, *more, aid=None):
    return ["append", "--data", str(scratch), "--run", str(run), "--transcript", str(t), "--agent-id", aid or _aid(t),
            "--role", "scout", "--stage", "s", "--task", "t", "--outcome", "o", *more]


def _keep(scratch, run, t, aid=None):
    return main(["keep", "--data", str(scratch), "--run", str(run), "--transcript", str(t), "--agent-id", aid or _aid(t)])


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
    assert f["agent_id"] == "a182da9fd43370b82"


def test_figures_run_116(paper, capsys):
    f = _figs(capsys, paper / "transcripts/run-0116.jsonl.gz")
    assert f["tool_calls"] == 4 and f["models"] == ["claude-sonnet-5-5"] and f["run_named_in_brief"] == 116


def test_a_brief_that_names_a_later_run_is_still_its_own_run(capsys):
    # run 135's brief opens "agent run 135" and names runs 131 and 123 further down
    assert _figs(capsys, live("adb1142ab9df65719"))["run_named_in_brief"] == 135


def test_append_refuses_a_run_that_has_a_line_then_writes_a_correction(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    base = _append_args(scratch, t, 117)
    assert main(base) == 2 and "already has a line" in capsys.readouterr().err
    assert rec.read_text() == before
    assert main(base + ["--corrects", "figures from the transcript"]) == 0
    new = rec.read_text()[len(before):].strip().splitlines()
    assert len(new) == 1
    d = json.loads(new[0])
    assert d["corrects"] and d["run"] == 117 and d["model"] == "claude-haiku-5-5"
    assert (d["input_tokens_fresh"], d["input_tokens_cache_written"], d["input_tokens_cache_read"], d["output_tokens"]) == (20, 85089, 501509, 18234)
    assert d["input_tokens"] == 586618 and d["model_replies"] == 10 and d["tool_calls"] == 30 and d["wall_clock_ms"] == 80761
    assert d["started_at"].startswith("2026-11-24T13:10:23.61") and d["ended_at"].startswith("2026-11-24T13:11:44.3")
    assert d["hand_backs"] >= 1 and d["sub_agent_calls"] == 0
    plan = json.loads((paper / "run-plans/run-0117.json").read_text())
    assert d["plan"] == "run-plans/run-0117.json" and d["budget_tokens"] == plan["max_tokens"] == 150000


def test_a_correcting_line_keeps_the_earlier_tokens_reported_unless_given_again(scratch, paper):
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    earlier = _newest(rec, 117)
    assert earlier["tokens_reported"] is not None
    assert main(_append_args(scratch, t, 117, "--corrects", "x")) == 0
    d = _newest(rec, 117)
    assert d["tokens_reported"] == earlier["tokens_reported"] and d["tokens_note"] == earlier["tokens_note"]
    assert main(_append_args(scratch, t, 117, "--corrects", "y", "--tokens-reported", "5")) == 0
    assert _newest(rec, 117)["tokens_reported"] == 5


def test_append_refuses_another_runs_transcript_empty_outcome_and_bad_role(scratch, paper, capsys):
    t = str(paper / "transcripts/run-0117.jsonl.gz")
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    b = ["append", "--data", str(scratch), "--transcript", t, "--agent-id", "a182da9fd43370b82", "--stage", "s", "--task", "t"]
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


def test_report_keeps_both_hand_backs_of_run_121(tmp_path):
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(live("a90a42cc900cc13e5")), "--out", str(out), "--title", "Run 121"]) == 0
    text = out.read_text()
    assert "## Hand-back 1 of 2" in text and "## Hand-back 2 of 2" in text
    a, b = text.index("Ticket 03b and the ticket 12 piece are built"), text.index("Both changes are built")
    assert text.index("## Hand-back 1 of 2") < a < text.index("## Hand-back 2 of 2") < b


def test_report_adds_the_message_run_124_hand_back_points_at(tmp_path):
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(live("a7418ae8600f3ea3d")), "--out", str(out), "--title", "Run 124"]) == 0
    text = out.read_text()
    # the real hand-back is 149 characters and its message 11,210
    assert "## Hand-back 1 of 1" in text and "## The message its last hand-back points at" in text
    assert text.index("## Hand-back 1 of 1") < text.index("## The message its last hand-back points at")
    assert len(text) > 11210 + 149
    # in run 124's real transcript the agent's LAST text message before its hand-back and its longest text
    # message are the same one (11,210 characters); its opening words are read by hand here
    texts = [it["text"] for l in live("a7418ae8600f3ea3d").read_text().splitlines() for it in (json.loads(l).get("message", {}).get("content") or [])
             if isinstance(it, dict) and it.get("type") == "text"]
    pointed = [t for t in texts if len(t) == 11210]
    assert len(pointed) == 1 and texts[-1] == pointed[0] or pointed[0] in texts
    after = text[text.index("## The message its last hand-back points at"):]
    assert pointed[0][:60] in after


def test_report_of_a_stopped_run_with_no_hand_back_and_no_text_says_so(tmp_path, capsys):
    t = live("a961b9f58c36234ce")  # run 110, stopped
    f = _figs(capsys, t)
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(t), "--out", str(out), "--title", "Run 110"]) == 0
    text = out.read_text()
    assert out.exists() and f["hand_backs"] == 0
    assert "no hand-back" in text and str(f["model_replies"]) in text and str(f["tool_calls"]) in text


def test_keep_writes_the_same_bytes_as_the_real_kept_file(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    shutil.rmtree(scratch / PAPER / "transcripts", ignore_errors=True)
    assert _keep(str(scratch), "117", str(t)) == 0
    k = scratch / PAPER / "transcripts"
    assert (k / "run-0117.jsonl.gz").read_bytes() == t.read_bytes()
    mine, real = json.loads((k / "run-0117.json").read_text()), json.loads((paper / "transcripts/run-0117.json").read_text())
    assert mine["sha256"] == real["sha256"] and mine["bytes"] == real["bytes"] and mine["lines"] == real["lines"]
    assert mine["agent_id"] == real["agent_id"]
    stamp = (k / "run-0117.json").stat().st_mtime_ns
    capsys.readouterr()
    assert _keep(str(scratch), "117", str(t)) == 0
    assert "nothing new" in capsys.readouterr().out
    assert (k / "run-0117.json").stat().st_mtime_ns == stamp
    assert _keep(str(scratch), "116", str(t)) == 2


def test_keep_refuses_a_kept_file_with_another_sha(scratch, paper):
    t = paper / "transcripts/run-0117.jsonl.gz"
    k = scratch / PAPER / "transcripts"
    k.mkdir(parents=True, exist_ok=True)
    (k / "run-0117.json").write_text(json.dumps({"run": 117, "sha256": "0" * 64}))
    assert _keep(str(scratch), "117", str(t)) == 2


def test_keep_never_writes_over_a_kept_gz_that_has_no_sidecar(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    k = scratch / PAPER / "transcripts"
    k.mkdir(parents=True, exist_ok=True)
    other = paper / "transcripts/run-0116.jsonl.gz"
    shutil.copy(other, k / "run-0117.jsonl.gz")  # other bytes under run 117's name
    kept = (k / "run-0117.jsonl.gz").read_bytes()
    assert _keep(str(scratch), "117", str(t)) == 2
    assert (k / "run-0117.jsonl.gz").read_bytes() == kept and not (k / "run-0117.json").exists()
    shutil.copy(t, k / "run-0117.jsonl.gz")  # same bytes, no sidecar
    capsys.readouterr()
    assert _keep(str(scratch), "117", str(t)) == 0
    assert "sidecar" in capsys.readouterr().out
    real = json.loads((paper / "transcripts/run-0117.json").read_text())
    assert json.loads((k / "run-0117.json").read_text())["sha256"] == real["sha256"]


def _rows(out):
    return {int(l.split()[1]): l for l in out.splitlines() if re.match(r"run \d+ \|", l)}


def _record_as_of(commit, dest, paper_rel):
    """The record, the run-plans and the transcripts as they were at a markets-data commit."""
    root = data_root()
    names = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", commit, "--", f"{paper_rel}/agent-runs.jsonl",
                            f"{paper_rel}/run-plans", f"{paper_rel}/transcripts"], capture_output=True, text=True)
    if names.returncode != 0:
        pytest.skip(f"markets-data has no commit {commit}")
    for n in names.stdout.split():
        body = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{n}"], capture_output=True).stdout
        p = dest / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def test_missing_on_the_record_as_it_was_at_the_reviewers_commit(tmp_path, capsys):
    data_root()
    d = tmp_path / "d"
    _record_as_of(COMMIT_OF_THE_REVIEW, d, PAPER)
    assert main(["missing", "--data", str(d)]) == 0
    out = capsys.readouterr().out
    rows = _rows(out)
    # facts the reviewer derived with jq on this commit, independent of the code under test
    assert sorted(r for r, l in rows.items() if "input_tokens" in l.split("|")[1]) == list(range(1, 107))
    assert sorted(r for r, l in rows.items() if "output_tokens" in l.split("|")[1]) == list(range(1, 107))
    assert sum("wall_clock" in l.split("|")[1] for l in rows.values()) == 30
    assert sum("model" in l.split("|")[1] for l in rows.values()) == 84
    assert not any("outcome" in l.split("|")[1] for l in rows.values())
    assert "lacks: model, input_tokens, output_tokens |" in rows[1] and "outcome" not in rows[1].split("|")[1]
    assert "wall_clock" not in rows[1]
    assert re.search(r"lacks: (model, )?input_tokens, output_tokens, wall_clock \|", rows[15])
    assert "lacks: nothing" in rows[114]
    assert "kept transcript exists" in rows[116] and "kept transcript exists" in rows[117]
    assert "no transcript kept" in rows[1]
    counts = [l for l in out.splitlines() if l.startswith("COUNTS")][0]
    assert "lacking exact model 84;" in counts and "lacking input tokens 106;" in counts and "lacking wall clock 30;" in counts


def test_missing_names_runs_with_a_plan_or_kept_transcript_and_no_line(scratch, paper, capsys):
    shutil.copytree(paper / "transcripts", scratch / PAPER / "transcripts")
    rec = scratch / PAPER / "agent-runs.jsonl"
    rec.write_text("".join(l + "\n" for l in rec.read_text().splitlines() if l.strip() and json.loads(l)["run"] != 117))
    assert main(["missing", "--data", str(scratch)]) == 0
    out = capsys.readouterr().out
    assert re.search(r"^NO LINE run 117 \|.*plan.*kept transcript", out, re.M)
    plans = {int(re.search(r"run-(\d+)", q.name).group(1)) for q in (scratch / PAPER / "run-plans").glob("run-*.json")}
    kept = {int(re.search(r"run-(\d+)", q.name).group(1)) for q in (scratch / PAPER / "transcripts").glob("run-*.jsonl.gz")}
    lined = {json.loads(l)["run"] for l in rec.read_text().splitlines() if l.strip()}
    n = len((plans | kept) - lined)
    assert 117 in (plans | kept) - lined
    assert f"plan or kept transcript with no line {n};" in [l for l in out.splitlines() if l.startswith("COUNTS")][0]


def _show(commit, rel):
    r = subprocess.run(["git", "-C", str(data_root()), "show", f"{commit}:{rel}"], capture_output=True)
    if r.returncode != 0:
        pytest.skip(f"markets-data has no {rel} at {commit}")
    return r.stdout


def test_missing_with_live_counts_on_the_record_as_it_was_at_5af204d1(tmp_path, capsys):
    # The record, plans and kept transcripts as they were at markets-data commit 5af204d1 (2026-11-24T17:37:07Z).
    # The live folder holds two real transcripts, each a byte-for-byte copy:
    #   run 157's, kept at 5af204d1 (its sidecar there carries tie_note "the brief names no run ...": its brief opens
    #     "You are scout run 157", which the code's reading of a brief does not take for a run), and
    #   run 162's, NOT kept at 5af204d1 (first kept by f350c321, 2026-11-24T17:40:13Z; its brief opens
    #     "You are the scout, agent run 162"), and run 162 has no line in the record at 5af204d1.
    # The expected figures are literals read with these commands (M=/home/user/markets-data, P=PAPER):
    #   git -C $M show 5af204d1:$P/transcripts/run-0157.json | jq .tie_note        -> the "names no run" note
    #   git -C $M ls-tree --name-only 5af204d1 -- $P/transcripts/run-0162.jsonl.gz | wc -l           -> 0
    #   git -C $M show 5af204d1:$P/agent-runs.jsonl | jq -c 'select(.run==162)' | wc -l               -> 0
    #   git -C $M log --diff-filter=A --format=%h -- $P/transcripts/run-0162.jsonl.gz                  -> f350c321
    #   git -C $M show f350c321:$P/transcripts/run-0162.jsonl.gz | zcat | head -1 | jq -r .message.content
    #                                                                       -> "You are the scout, agent run 162 ..."
    # so: 2 live transcripts, 1 names one run (162), 1 names none (157), 1 with no line (162), 1 not kept (162).
    data_root()
    commit, later = "5af204d1", "f350c321"
    d, live_dir = tmp_path / "d", tmp_path / "live"
    _record_as_of(commit, d, PAPER)
    live_dir.mkdir()
    rel = PAPER + "/transcripts/run-"
    assert json.loads(_show(commit, rel + "0157.json"))["tie_note"].startswith("the brief names no run")
    assert not (d / PAPER / "transcripts" / "run-0162.jsonl.gz").exists()
    (live_dir / "agent-a9e48461f5f4f0068.jsonl").write_bytes(gzip.decompress(_show(commit, rel + "0157.jsonl.gz")))
    (live_dir / "agent-run162.jsonl").write_bytes(gzip.decompress(_show(later, rel + "0162.jsonl.gz")))
    assert main(["missing", "--data", str(d), "--live", str(live_dir)]) == 0
    counts = [l for l in capsys.readouterr().out.splitlines() if l.startswith("COUNTS")][0]
    assert "live transcripts 2, of which 1 name one run and 1 name none" in counts
    assert "live transcripts with no line 1," in counts
    assert "live transcripts not kept 1;" in counts


def test_missing_names_a_live_transcript_that_names_no_run_and_two_that_name_one(paper, tmp_path, capsys):
    t107 = live("a374a5827c8bc7cc6")  # run 107: a general agent, its brief begins "FIRST: read"
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    shutil.copy(t107, live_dir / "agent-a374a5827c8bc7cc6.jsonl")
    shutil.copy(paper / "transcripts/run-0117.jsonl.gz", live_dir / "agent-one.jsonl.gz")
    shutil.copy(paper / "transcripts/run-0117.jsonl.gz", live_dir / "agent-two.jsonl.gz")
    d = tmp_path / "d"
    sc = d / PAPER
    sc.mkdir(parents=True)
    shutil.copy(paper / "agent-runs.jsonl", sc / "agent-runs.jsonl")
    assert main(["missing", "--data", str(d), "--live", str(live_dir)]) == 0
    out = capsys.readouterr().out
    assert re.search(r"^UNNAMED live agent-a374a5827c8bc7cc6\.jsonl \| agentId a374a5827c8bc7cc6", out, re.M)
    assert re.search(r"^DUPLICATE live run 117 \| .*agent-one.*agent-two|^DUPLICATE live run 117 \| .*agent-two.*agent-one", out, re.M)


def test_missing_complete_line_that_differs_is_not_read_as_lacking_nothing(scratch, paper, capsys):
    shutil.copytree(paper / "transcripts", scratch / PAPER / "transcripts")
    rec = scratch / PAPER / "agent-runs.jsonl"
    d = _newest(rec, 117)
    d.update({"output_tokens": 18000})
    rec.write_text(rec.read_text() + json.dumps(d) + "\n")
    assert main(["missing", "--data", str(scratch)]) == 0
    out = capsys.readouterr().out
    row = [l for l in out.splitlines() if re.match(r"run 117 \|", l)][0]
    assert "lacks: nothing | differs:" in row and "output_tokens" in row
    counts = [l for l in out.splitlines() if l.startswith("COUNTS")][0]
    assert "complete and agreeing with a kept or live transcript:" in counts
    assert "complete, a figure differs:" in counts and "complete, no transcript to compare:" in counts


def test_data_without_a_record_is_refused_for_every_verb(tmp_path, paper, capsys):
    (tmp_path / "MANIFEST.json").write_text("{}")
    t = str(paper / "transcripts/run-0117.jsonl.gz")
    for argv in (["missing", "--data", str(tmp_path)],
                 ["keep", "--data", str(tmp_path), "--run", "117", "--transcript", t, "--agent-id", "a182da9fd43370b82"],
                 _append_args(tmp_path, t, 117)):
        assert main(argv) == 2
        assert "does not exist" in capsys.readouterr().err
    assert not (tmp_path / "transcripts").exists() and not (tmp_path / PAPER).exists()


def test_the_agent_id_must_be_the_transcripts_own(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    id116 = json.loads((paper / "transcripts/run-0116.json").read_text())["agent_id"]
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    assert main(_append_args(scratch, t, 117, "--corrects", "x", aid=id116)) == 2
    assert "agentId" in capsys.readouterr().err
    assert _keep(scratch, 117, t, aid=id116) == 2 and "agentId" in capsys.readouterr().err
    assert rec.read_text() == before and not (scratch / PAPER / "transcripts").exists()
    assert _keep(scratch, 117, t, aid="a182da9fd43370b82") == 0
    side = json.loads((scratch / PAPER / "transcripts/run-0117.json").read_text())
    assert side["agent_id"] == "a182da9fd43370b82" and "tie_note" not in side
    assert main(_append_args(scratch, t, 117, "--corrects", "x")) == 0
    assert _newest(rec, 117)["agent_id"] == "a182da9fd43370b82"


def test_a_brief_that_names_no_run_is_tied_by_the_agent_id_alone(scratch, capsys):
    t = live("a374a5827c8bc7cc6")  # run 107: brief begins "FIRST: read ..."
    f = _figs(capsys, t)
    assert f["run_named_in_brief"] is None and f["agent_id"] == "a374a5827c8bc7cc6"
    assert _keep(scratch, 107, t) == 0
    side = json.loads((scratch / PAPER / "transcripts/run-0107.json").read_text())
    assert side["agent_id"] == "a374a5827c8bc7cc6" and side["tie_note"] == "the brief names no run: tied by the agent id given at launch"
    assert main(_append_args(scratch, t, 107, "--corrects", "x")) == 0
    line = _newest(scratch / PAPER / "agent-runs.jsonl", 107)
    assert line["agent_id"] == "a374a5827c8bc7cc6" and line["tie_note"] == side["tie_note"]


def test_one_transcript_is_one_runs_not_two(scratch, capsys):
    t = live("a374a5827c8bc7cc6")  # run 107's real transcript
    assert _keep(scratch, 107, t) == 0
    capsys.readouterr()
    assert _keep(scratch, 108, t) == 2 and "run 107" in capsys.readouterr().err
    assert main(_append_args(scratch, t, 108, "--corrects", "x")) == 2 and "run 107" in capsys.readouterr().err
    assert not (scratch / PAPER / "transcripts/run-0108.jsonl.gz").exists()


def test_a_transcript_that_is_run_108s_own_agrees_with_its_line_and_run_107s_does_not(scratch, capsys):
    t107, t108 = live("a374a5827c8bc7cc6"), live("ae63f020e27f3aa06")
    rec = scratch / PAPER / "agent-runs.jsonl"
    # the real line of run 108 holds an exact-looking haiku model and 604,479 input tokens (read from the record)
    line108 = _newest(rec, 108)
    before = rec.read_text()
    assert main(_append_args(scratch, t107, 108, "--corrects", "x")) == 2  # run 107's transcript is not run 108's
    assert "108" in capsys.readouterr().err and rec.read_text() == before
    assert main(_append_args(scratch, t108, 108, "--corrects", "x")) == 0
    after = _newest(rec, 108)
    assert after["input_tokens"] >= line108["input_tokens"] and after["agent_id"] == "ae63f020e27f3aa06"


def test_outside_the_roster_the_agent_type_is_the_text_given(scratch, capsys):
    t = live("a374a5827c8bc7cc6")
    what = "general-purpose, handed .claude/agents/reviewer.md as its instructions"
    rec = scratch / PAPER / "agent-runs.jsonl"
    assert main(_append_args(scratch, t, 107, "--corrects", "x", "--role", "reviewer", "--outside-roster", what)) == 0
    line = _newest(rec, 107)
    assert line["agent_type"] == what and line["role"] == "reviewer"
    assert main(_append_args(scratch, t, 107, "--corrects", "y", "--role", "reviewer", "--outside-roster", what, "--agent-type", "builder")) == 2
    assert "exactly one" in capsys.readouterr().err
    assert main(_append_args(scratch, t, 107, "--corrects", "z", "--role", "reviewer", "--agent-type", "wizard")) == 2
    assert main(_append_args(scratch, t, 107, "--corrects", "w", "--role", "reviewer")) == 0
    assert _newest(rec, 107)["agent_type"] == "reviewer"


def test_run_108s_kept_transcript_is_accepted_and_run_107s_offered_as_108_is_refused(tmp_path, paper, capsys):
    # the record as it was at 04d8a0f (run 108's line holds claude-haiku-5-5, no agent id), the kept files of runs 107, 108
    d = tmp_path / "data"
    (d / PAPER).mkdir(parents=True)
    (d / PAPER / "agent-runs.jsonl").write_bytes(subprocess.run(
        ["git", "-C", str(data_root()), "show", f"04d8a0f:{PAPER}/agent-runs.jsonl"], capture_output=True, check=True).stdout)
    rec = d / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    assert main(_append_args(d, paper / "transcripts/run-0107.jsonl.gz", 108, "--corrects", "x")) == 2
    err = capsys.readouterr().err
    assert "run 108's line holds model" in err and rec.read_text() == before
    assert main(_append_args(d, paper / "transcripts/run-0108.jsonl.gz", 108, "--corrects", "x")) == 0
    assert _newest(rec, 108)["agent_id"] == "ae63f020e27f3aa06"


def test_agent_type_and_outside_roster_together_are_refused_whatever_their_values(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    for x, y in (("builder", "builder"), ("wizard", "wizard"), ("builder", "wizard")):
        assert main(_append_args(scratch, t, 117, "--corrects", "x", "--role", "reviewer", "--agent-type", x, "--outside-roster", y)) == 2
        assert "exactly one" in capsys.readouterr().err
    assert rec.read_text() == before


def test_an_empty_outside_roster_is_refused_with_what_it_needs(scratch, paper, capsys):
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    for empty in ("", "  "):
        assert main(_append_args(scratch, t, 117, "--corrects", "x", "--role", "reviewer", "--outside-roster", empty)) == 2
        assert "needs the words for what the agent was" in capsys.readouterr().err
    assert rec.read_text() == before


# ---------------------------------------------------------------------------------------------------------
# CASES THE REAL RECORD DOES NOT HOLD: each uses a real transcript or a real line of the record with exactly
# the change named in the case's own comment
# ---------------------------------------------------------------------------------------------------------

def _changed_first_line(src, dest, sentence):
    """Run 119's real transcript with ONE sentence naming another run put in front of its brief."""
    lines = Path(src).read_text(encoding="utf-8").splitlines()
    d = json.loads(lines[0])
    d["message"]["content"] = sentence + " " + d["message"]["content"]
    lines[0] = json.dumps(d)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def test_trap_a_sentence_naming_another_run_in_front_of_the_brief(scratch, tmp_path, capsys):
    # change: run 119's real transcript with ONE short sentence, "This note is about agent run 117.", put in front
    # of its brief (so two different runs are named in its opening); nothing else
    changed = _changed_first_line(live_for_run(119), tmp_path / "t119.jsonl", "This note is about agent run 117.")
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    for run in ("117", "119"):
        assert main(_append_args(scratch, changed, run, "--corrects", "x")) == 2
        assert "names two different runs" in capsys.readouterr().err
        assert _keep(str(scratch), run, str(changed)) == 2
        assert "names two different runs" in capsys.readouterr().err
    assert rec.read_text() == before and not (scratch / PAPER / "transcripts").exists()
    # the unchanged transcript is still run 119's
    assert _figs(capsys, live_for_run(119))["run_named_in_brief"] == 119


def test_trap_a_real_hand_back_followed_by_a_short_one_drops_nothing(paper, tmp_path):
    # change: run 117's real transcript gains ONE more line at its end: a copy of its last hand-back line with a new
    # message id and tool_use id, its hand-back message replaced by "Short one." and its text item replaced by "x"
    lines = gzip.decompress((paper / "transcripts/run-0117.jsonl.gz").read_bytes()).decode().splitlines()
    last = max(i for i, l in enumerate(lines) if "SubagentHandback" in l and json.loads(l).get("message", {}).get("role") == "assistant")
    d = copy.deepcopy(json.loads(lines[last]))
    d["message"]["id"] = "msg_added_by_the_check"
    for it in d["message"]["content"]:
        if it.get("type") == "tool_use":
            it["id"] = "toolu_added_by_the_check"
            it["input"] = {"message": "Short one."}
        elif it.get("type") == "text":
            it["text"] = "x"
    lines.append(json.dumps(d))
    src = tmp_path / "t.jsonl"
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(src), "--out", str(out), "--title", "T"]) == 0
    text = out.read_text()
    assert "## Hand-back 1 of 2" in text and "## Hand-back 2 of 2" in text
    assert "SCOUT RUN 0117 REPORT." in text and "Short one." in text


def test_trap_a_line_whose_figures_differ_from_its_kept_transcript_is_named(scratch, paper, capsys):
    # change: run 117's real line in the record copy gets output_tokens 18000 (real 18234), its wall clock raised by
    # 500 ms (then by 5,500 ms in all) and its model_replies removed; its kept transcript is not touched
    shutil.copytree(paper / "transcripts", scratch / PAPER / "transcripts")
    rec = scratch / PAPER / "agent-runs.jsonl"
    d = _newest(rec, 117)
    d.update({"output_tokens": 18000, "wall_clock_ms": d["wall_clock_ms"] + 500})  # 500 ms is not named
    d.pop("model_replies", None)
    rec.write_text("".join(l + "\n" for l in rec.read_text().splitlines() if l.strip() and json.loads(l)["run"] != 117) + json.dumps(d) + "\n")
    assert main(["missing", "--data", str(scratch)]) == 0
    out = capsys.readouterr().out
    mine = [l for l in out.splitlines() if l.startswith("DIFFERS run 117")]
    assert any("output_tokens" in l and "18000" in l and "18234" in l for l in mine)
    assert any("model_replies" in l for l in mine)
    assert not any("wall_clock" in l for l in mine)
    d["wall_clock_ms"] += 5000
    rec.write_text(rec.read_text() + json.dumps(d) + "\n")
    capsys.readouterr()
    assert main(["missing", "--data", str(scratch)]) == 0
    assert any("wall_clock_ms" in l for l in capsys.readouterr().out.splitlines() if l.startswith("DIFFERS run 117"))


def test_trap_a_long_sentence_in_front_of_run_119s_brief_is_tied_only_by_the_agent_id(scratch, tmp_path, capsys):
    # change: run 119's real transcript with ONE sentence of over 200 characters, naming no run, in front of its brief;
    # and, in one part, run 136's real plan in the record copy gains an agent_id of another agent
    sentence = ("This sentence is longer than two hundred characters and says nothing about which run follows, " * 3).strip()
    assert len(sentence) > 200
    changed = _changed_first_line(live_for_run(119), tmp_path / "t.jsonl", sentence)
    id119 = _aid(changed)
    f = _figs(capsys, changed)
    assert f["run_named_in_brief"] is None
    # given another run with another agent id on record (change: run 136's real plan gains an agent_id), refused
    plan = scratch / PAPER / "run-plans/run-0136.json"
    if not plan.exists():
        pytest.skip("this record has no plan for run 136")
    d = json.loads(plan.read_text())
    assert "agent_id" not in d
    d["agent_id"] = "a0000000000000000"
    plan.write_text(json.dumps(d))
    assert _keep(scratch, 136, changed, aid=id119) == 2
    assert "another agent id" in capsys.readouterr().err
    assert main(_append_args(scratch, changed, 136, "--corrects", "x", aid=id119)) == 2
    assert "another agent id" in capsys.readouterr().err
    assert not (scratch / PAPER / "transcripts").exists()
    # with nothing on record naming run 136's agent id the tie rests on the id given: accepted (the stated limit) ...
    del d["agent_id"]
    plan.write_text(json.dumps(d))
    assert _keep(scratch, 119, changed, aid=id119) == 0  # run 119's own
    capsys.readouterr()
    # ... but one transcript is one run's: the same transcript as run 136 is refused, naming run 119
    assert _keep(scratch, 136, changed, aid=id119) == 2
    assert "run 119" in capsys.readouterr().err


def test_trap_a_run_whose_line_holds_another_agent_id_refuses_this_one(scratch, tmp_path, capsys):
    # change: run 107's real transcript with every agentId replaced by another id ("aother0000000000"); nothing else
    t = live("a374a5827c8bc7cc6")
    assert main(_append_args(scratch, t, 107, "--corrects", "x")) == 0  # the line now holds the real id
    other = tmp_path / "other.jsonl"
    other.write_text(t.read_text().replace("a374a5827c8bc7cc6", "aother0000000000"), encoding="utf-8")
    assert main(_append_args(scratch, other, 107, "--corrects", "y")) == 2
    assert "another agent id" in capsys.readouterr().err


def test_trap_a_line_already_on_record_is_compared_with_the_transcript(scratch, tmp_path, capsys):
    # change: run 107's real transcript with every agentId replaced by a fresh id ("afresh0000000000"), given as run 108,
    # whose own real line holds another model and fewer tokens
    t = live("a374a5827c8bc7cc6")
    fresh = tmp_path / "fresh.jsonl"
    fresh.write_text(t.read_text().replace("a374a5827c8bc7cc6", "afresh0000000000"), encoding="utf-8")
    rec = scratch / PAPER / "agent-runs.jsonl"
    before = rec.read_text()
    assert main(_append_args(scratch, fresh, 108, "--corrects", "x")) == 2
    err = capsys.readouterr().err
    assert "model" in err or "input_tokens" in err
    assert rec.read_text() == before
    assert _keep(scratch, 108, fresh) == 2 and not (scratch / PAPER / "transcripts").exists()


def test_trap_a_line_with_more_tokens_than_its_transcript_refuses_a_correction(scratch, paper, capsys):
    # change: run 117's real line in the record copy gets input_tokens raised by 1 (a run that was sent back has grown,
    # it never shrinks, so the transcript's lower figure is refused); a second change raises output_tokens by 1 instead
    t = paper / "transcripts/run-0117.jsonl.gz"
    rec = scratch / PAPER / "agent-runs.jsonl"
    for key in ("input_tokens", "output_tokens"):
        d = _newest(rec, 117)
        d[key] += 1
        rec.write_text(rec.read_text() + json.dumps(d) + "\n")
        before = rec.read_text()
        assert main(_append_args(scratch, t, 117, "--corrects", "x")) == 2
        err = capsys.readouterr().err
        assert key in err and str(d[key]) in err and str(d[key] - 1) in err
        assert rec.read_text() == before
        d[key] -= 2  # a line BELOW the transcript's figure is fine
        rec.write_text(rec.read_text() + json.dumps(d) + "\n")
        assert main(_append_args(scratch, t, 117, "--corrects", "ok")) == 0
        assert _newest(rec, 117)[key] == d[key] + 1


def _add_before_the_long_message(src, dest, hand_back_inner_text=None, earlier_longer=None):
    lines = Path(src).read_text(encoding="utf-8").splitlines()
    if earlier_longer:
        i = next(k for k, l in enumerate(lines) if '"text"' in l and len(l) > 11210 and json.loads(l).get("message", {}).get("role") == "assistant")
        d = copy.deepcopy(json.loads(lines[i]))
        d["message"]["id"] = "msg_earlier_longer_added_by_the_check"
        d["message"]["content"] = [{"type": "text", "text": earlier_longer}]
        lines.insert(i, json.dumps(d))
    if hand_back_inner_text:
        i = max(k for k, l in enumerate(lines) if "SubagentHandback" in l and json.loads(l).get("message", {}).get("role") == "assistant")
        d = json.loads(lines[i])
        d["message"]["content"].insert(0, {"type": "text", "text": hand_back_inner_text})
        lines[i] = json.dumps(d)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def _real_pointed_at_opening():
    texts = [it["text"] for l in live("a7418ae8600f3ea3d").read_text().splitlines() for it in (json.loads(l).get("message", {}).get("content") or [])
             if isinstance(it, dict) and it.get("type") == "text"]
    return next(t for t in texts if len(t) == 11210)[:60]


def test_trap_the_pointed_at_message_is_the_last_one_not_the_longest(tmp_path):
    # change: run 124's real transcript gains ONE more assistant line, with a new message id, holding a text item of
    # 12,000 characters (LONGER than the real 11,210-character message), put in an earlier reply before it
    src = live("a7418ae8600f3ea3d")
    changed = _add_before_the_long_message(src, tmp_path / "t.jsonl", earlier_longer="EARLIER AND LONGER. " * 600)
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(changed), "--out", str(out), "--title", "T"]) == 0
    after = out.read_text()
    after = after[after.index("## The message its last hand-back points at"):]
    assert _real_pointed_at_opening() in after and "EARLIER AND LONGER." not in after


def test_trap_a_short_text_inside_the_hand_backs_own_message_does_not_displace_the_real_one(tmp_path):
    # change: run 124's real transcript, the line holding its hand-back gets ONE text item, "Handing back now.", put in
    # front of the hand-back's tool_use inside the same message (the same message id)
    changed = _add_before_the_long_message(live("a7418ae8600f3ea3d"), tmp_path / "t.jsonl", hand_back_inner_text="Handing back now.")
    out = tmp_path / "r.md"
    assert main(["report", "--transcript", str(changed), "--out", str(out), "--title", "T"]) == 0
    after = out.read_text()
    after = after[after.index("## The message its last hand-back points at"):]
    assert _real_pointed_at_opening() in after


def _agent_id_scratch(tmp_path, paper):
    """The record at 04d8a0f (no line holds run 157's agent id), no plans, and run 157's real kept sidecar and bytes."""
    d = tmp_path / "data"
    (d / PAPER / "transcripts").mkdir(parents=True)
    (d / PAPER / "agent-runs.jsonl").write_bytes(subprocess.run(
        ["git", "-C", str(data_root()), "show", f"04d8a0f:{PAPER}/agent-runs.jsonl"], capture_output=True, check=True).stdout)
    side = json.loads((paper / "transcripts/run-0157.json").read_text())
    assert side["tie_note"] and not any(side["agent_id"] in l for l in (d / PAPER / "agent-runs.jsonl").read_text().splitlines())
    return d, side


def test_trap_the_same_bytes_under_another_run_are_refused_on_the_sha_alone(tmp_path, paper, capsys):
    # change: run 157's real kept sidecar (its brief names no run) has its agent_id removed, so the agent-id refusals do
    # not fire and the sha refusal is the only one left; the same real bytes are offered as run 9001, which has no line
    d, side = _agent_id_scratch(tmp_path, paper)
    del side["agent_id"]
    (d / PAPER / "transcripts/run-0157.json").write_text(json.dumps(side))
    t = paper / "transcripts/run-0157.jsonl.gz"
    aid = json.loads((paper / "transcripts/run-0157.json").read_text())["agent_id"]
    assert _keep(d, 9001, t, aid=aid) == 2
    err = capsys.readouterr().err
    assert f"these bytes (sha256 {side['sha256']}) are already kept as run 157, not run 9001" in err
    assert not (d / PAPER / "transcripts/run-9001.jsonl.gz").exists()


def test_the_same_agent_id_under_another_run_is_refused_on_its_kept_sidecar_alone(tmp_path, paper, capsys):
    # real sidecar, no change: run 157's own kept sidecar holds the agent id; the bytes offered as run 9001
    d, side = _agent_id_scratch(tmp_path, paper)
    shutil.copy(paper / "transcripts/run-0157.json", d / PAPER / "transcripts")
    assert _keep(d, 9001, paper / "transcripts/run-0157.jsonl.gz", aid=side["agent_id"]) == 2
    err = capsys.readouterr().err
    assert f"agent id {side['agent_id']} is already on record for run 157 (its kept sidecar), not run 9001" in err
    assert "these bytes" not in err


def test_trap_the_same_agent_id_under_another_run_is_refused_on_its_line_alone(tmp_path, paper, capsys):
    # change: run 116's real line in the record at 04d8a0f gains agent_id = run 157's real agent id; nothing else
    d, side = _agent_id_scratch(tmp_path, paper)
    rec = d / PAPER / "agent-runs.jsonl"
    lines = [json.loads(l) for l in rec.read_text().splitlines() if l.strip()]
    mine = [x for x in lines if x["run"] == 116][-1]
    mine["agent_id"] = side["agent_id"]
    rec.write_text("".join(json.dumps(x) + "\n" for x in lines if x is not mine) + json.dumps(mine) + "\n")
    assert _keep(d, 9001, paper / "transcripts/run-0157.jsonl.gz", aid=side["agent_id"]) == 2
    assert f"agent id {side['agent_id']} is already on record for run 116 (its line), not run 9001" in capsys.readouterr().err


def test_trap_a_line_whose_model_replies_differs_from_its_kept_transcript_is_named(scratch, paper, capsys):
    # change: run 154's real newest line (model_replies 10, the same as its kept transcript: unchanged, `missing` names no
    # difference for it, asserted first) has its model_replies raised by one to 11; nothing else is touched
    shutil.copytree(paper / "transcripts", scratch / PAPER / "transcripts")
    rec = scratch / PAPER / "agent-runs.jsonl"
    d = _newest(rec, 154)
    assert d["model_replies"] == 10
    assert main(["missing", "--data", str(scratch)]) == 0
    assert not [l for l in capsys.readouterr().out.splitlines() if l.startswith("DIFFERS run 154") and "model_replies" in l]
    d["model_replies"] = 11
    rec.write_text("".join(l + "\n" for l in rec.read_text().splitlines() if l.strip() and json.loads(l)["run"] != 154) + json.dumps(d) + "\n")
    assert main(["missing", "--data", str(scratch)]) == 0
    mine = [l for l in capsys.readouterr().out.splitlines() if l.startswith("DIFFERS run 154")]
    assert any("model_replies: line 11, transcript 10" in l for l in mine)
