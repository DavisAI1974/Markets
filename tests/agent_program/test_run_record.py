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


def test_missing_with_live_counts_on_the_record_as_it_was_at_7de89a4(tmp_path, capsys):
    data_root()
    d, live_dir = tmp_path / "d", tmp_path / "live"
    _record_as_of("7de89a4", d, PAPER)
    live_dir.mkdir()
    gzs = sorted((d / PAPER / "transcripts").glob("run-*.jsonl.gz"))
    assert gzs
    for g in gzs:
        (live_dir / g.name[:-3]).write_bytes(gzip.decompress(g.read_bytes()))
    lined = {json.loads(l)["run"] for l in (d / PAPER / "agent-runs.jsonl").read_text().splitlines() if l.strip()}
    named = []
    for g in live_dir.glob("*.jsonl"):
        brief = json.loads(g.read_text().splitlines()[0])["message"]["content"]
        own = re.match(r"\s*You are the [^,.\n]{1,60}, agent run (\d+)", brief, re.I)
        nums = {int(own.group(1))} if own else {int(x) for x in re.findall(r"agent run (\d+)", brief[:200], re.I)}
        named.append(next(iter(nums)) if len(nums) == 1 else None)
    runs = [r for r in named if r is not None]
    kept = {int(re.search(r"run-(\d+)", g.name).group(1)) for g in gzs}
    assert main(["missing", "--data", str(d), "--live", str(live_dir)]) == 0
    counts = [l for l in capsys.readouterr().out.splitlines() if l.startswith("COUNTS")][0]
    assert f"live transcripts {len(runs)} (naming no single run {named.count(None)})" in counts
    assert f"live transcripts with no line {len(set(runs) - lined)}," in counts
    assert f"live transcripts not kept {len(set(runs) - kept)};" in counts


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
    # change: run 119's real transcript with ONE sentence of over 200 characters, naming no run, in front of its brief
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
    assert _keep(scratch, 136, changed, aid=id119) == 0  # nothing on record names run 136's agent id: accepted, the limit
    shutil.rmtree(scratch / PAPER / "transcripts")
    d["agent_id"] = "a0000000000000000"
    plan.write_text(json.dumps(d))
    assert _keep(scratch, 136, changed, aid=id119) == 2
    assert "another agent id" in capsys.readouterr().err
    assert main(_append_args(scratch, changed, 136, "--corrects", "x", aid=id119)) == 2
    assert "another agent id" in capsys.readouterr().err
    assert not (scratch / PAPER / "transcripts").exists()


def test_trap_a_run_whose_line_holds_another_agent_id_refuses_this_one(scratch, tmp_path, capsys):
    # change: run 107's real transcript with every agentId replaced by another id
    t = live("a374a5827c8bc7cc6")
    assert main(_append_args(scratch, t, 107, "--corrects", "x")) == 0  # the line now holds the real id
    other = tmp_path / "other.jsonl"
    other.write_text(t.read_text().replace("a374a5827c8bc7cc6", "aother0000000000"), encoding="utf-8")
    assert main(_append_args(scratch, other, 107, "--corrects", "y")) == 2
    assert "another agent id" in capsys.readouterr().err
