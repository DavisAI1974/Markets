"""Checks of tools/kgraph/run_plan.py through its public verbs, on real records only.

Real: the plan files, the agent-runs record and the two kept transcripts (runs 116 and 117) of
markets-data. Facts stated from the auditor's reports, not recomputed here: run 117's plan allows 30 tool
calls and it made exactly 30; it allows 20 model calls and it made 10 replies; run 116's plan allows 25
tool calls and it made 4; run 109 has a line in the record and no plan file; runs 114, 115 and 117 had
their plan files committed before their first transcript line.
Scratch: the `write` checks run on copies of the real run-plans folder and record under tmp_path.
Paired (not one run's own): the PASSED check points `check` at run 117's real transcript with run 116's
real plan file (25 tool calls), because the record holds no run from 114 on that went over its own plan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess

from tools.kgraph import run_plan
from tools.swarm.plan import BUDGET_KEYS

from .realrecords import PAPER, data_root

def _real_rc():
    """0, or 3 where the real markets-data checkout is itself shallow: `check` then says the order is not measured."""
    r = subprocess.run(["git", "-C", str(data_root()), "rev-parse", "--is-shallow-repository"],
                       capture_output=True, text=True)
    return 3 if r.stdout.strip() == "true" else 0


LINE = re.compile(r"^(max_\w+): plan (\S+), reached (\S+), (.*)$")


def _limits(out):
    return {m.group(1): (m.group(2), m.group(3), m.group(4)) for l in out.splitlines() if (m := LINE.match(l))}


def _scratch(tmp_path):
    root = data_root()
    dst = tmp_path / "md"
    (dst / PAPER).mkdir(parents=True)
    shutil.copytree(root / PAPER / "run-plans", dst / PAPER / "run-plans")
    shutil.copy(root / PAPER / "agent-runs.jsonl", dst / PAPER / "agent-runs.jsonl")
    subprocess.run(["git", "-C", str(dst), "init", "-q"], check=True)
    return dst


def _next_unused(d):
    nums = [int(re.search(r"(\d+)", p.name).group(1)) for p in (d / PAPER / "run-plans").glob("run-*.json")]
    nums += [int(json.loads(l)["run"]) for l in (d / PAPER / "agent-runs.jsonl").read_text().splitlines()]
    return max(nums) + 1


def _base(run, agent="builder"):
    args = ["--run", str(run), "--agent", agent, "--model", "claude-sonnet-5-5", "--task", "a check"]
    for k in BUDGET_KEYS:
        args += ["--" + k.replace("_", "-"), "3"]
    return args


def test_check_117_kept_at_the_limit(capsys):
    root = data_root()
    rc = run_plan.main(["check", "--data", str(root), "--run", "117"])
    out = capsys.readouterr().out
    lim = _limits(out)
    assert lim["max_tool_calls"][:2] == ("30", "30") and lim["max_tool_calls"][2].startswith("kept")
    assert lim["max_model_calls"][:2] == ("20", "10") and lim["max_model_calls"][2].startswith("kept")
    assert lim["max_sub_agents"][:2] == ("0", "0") and lim["max_sub_agents"][2].startswith("kept")
    assert lim["max_graph_writes"][:2] == ("0", "0") and lim["max_graph_writes"][2].startswith("kept")
    assert lim["max_retries"][2].startswith("cannot be measured")
    assert lim["max_concurrent_workers"][2].startswith("cannot be measured")
    assert "PASSED" not in out
    assert str(root) in out
    if _real_rc() == 0:
        assert "before the run began" in out
    else:
        assert "is shallow, so the time the plan was added is not known" in out
    assert rc == _real_rc()


def test_check_116_four_of_25(capsys):
    rc = run_plan.main(["check", "--data", str(data_root()), "--run", "116"])
    lim = _limits(capsys.readouterr().out)
    assert lim["max_tool_calls"][:2] == ("25", "4")
    assert rc == _real_rc()


def test_check_109_has_no_plan(capsys):
    rc = run_plan.main(["check", "--data", str(data_root()), "--run", "109"])
    assert "no plan file" in capsys.readouterr().out
    assert rc == 1


def test_check_passed_branch_paired_plan(capsys):
    # real pair: run 117's real transcript with run 116's real plan file (25 tool calls), given by hand
    root = data_root()
    plan116 = root / PAPER / "run-plans" / "run-0116.json"
    rc = run_plan.main(["check", "--data", str(root), "--run", "117", "--plan", str(plan116)])
    out = capsys.readouterr().out
    assert out.splitlines()[0] == (f"PAIRED CHECK: the plan read is {plan116}, given by hand; "
                                   "this is not a check of run 117 against its own plan in git")
    assert _limits(out)["max_tool_calls"][:3] == ("25", "30", "PASSED")
    assert "git order: not measured" in out and "plan in git: not measured" in out
    assert rc == 3


def test_write_refusals_and_a_new_plan(tmp_path, capsys):
    d = _scratch(tmp_path)
    plans = d / PAPER / "run-plans"
    before = sorted(p.name for p in plans.iterdir())
    record = (d / PAPER / "agent-runs.jsonl").read_bytes()

    assert run_plan.main(["write", "--data", str(d)] + _base(114)) == 2
    assert "already exists" in capsys.readouterr().err
    assert run_plan.main(["write", "--data", str(d)] + _base(109)) == 2
    assert "line in the record" in capsys.readouterr().err
    assert run_plan.main(["write", "--data", str(d)] + _base(132, agent="general-purpose")) == 2
    assert "roster" in capsys.readouterr().err
    short = _base(132)
    i = short.index("--max-retries")
    assert run_plan.main(["write", "--data", str(d)] + short[:i] + short[i + 2:]) == 2
    assert "max_retries" in capsys.readouterr().err
    neg = _base(132)
    neg[neg.index("--max-tokens") + 1] = "-1"
    assert run_plan.main(["write", "--data", str(d)] + neg) == 2
    assert "max_tokens" in capsys.readouterr().err
    assert sorted(p.name for p in plans.iterdir()) == before

    nums = [int(re.search(r"(\d+)", n).group(1)) for n in before]
    for line in record.decode().splitlines():
        nums.append(int(json.loads(line)["run"]))
    nxt = max(nums) + 1
    assert run_plan.main(["write", "--data", str(d), "--tickets", "18,19", "--note", "n"] + _base(nxt)) == 0
    capsys.readouterr()
    new = plans / f"run-{nxt:04d}.json"
    doc = json.loads(new.read_text())
    assert all(k in doc for k in BUDGET_KEYS)
    assert doc["run"] == nxt and doc["written_before_the_run_started"] is True
    assert sorted(p.name for p in plans.iterdir()) == sorted(before + [new.name])
    assert (d / PAPER / "agent-runs.jsonl").read_bytes() == record
    assert run_plan.main(["write", "--data", str(d)] + _base(nxt)) == 2
    assert "already exists" in capsys.readouterr().err


def test_brief_122(capsys):
    root = data_root()
    plan = json.loads((root / PAPER / "run-plans" / "run-0122.json").read_text())
    assert run_plan.main(["brief", "--data", str(root), "--run", "122"]) == 0
    out = capsys.readouterr().out
    for want in ("60 model calls", "0 sub-agents", "1 concurrent workers", "70 tool calls", "500000 tokens",
                 "2400 seconds", "1 retries", "0 writes into the real graph"):
        assert want in out
    assert "COUNT your own tool calls" in out
    assert plan["on_reaching_a_limit"] in out
    assert run_plan.main(["brief", "--data", str(root), "--run", "122"]) == 0
    assert capsys.readouterr().out == out


def test_data_without_run_plans_is_refused(tmp_path, capsys):
    (tmp_path / "MANIFEST.json").write_text("{}")
    for verb in ("check", "brief"):
        assert run_plan.main([verb, "--data", str(tmp_path), "--run", "117"]) == 2
        err = capsys.readouterr().err
        assert str(tmp_path) in err and "run-plans" in err


# ---- the second read (points 1 to 8) on the real record ---------------------------------------------
def test_check_117_tokens_and_wall_clock_lines(capsys):
    run_plan.main(["check", "--data", str(data_root()), "--run", "117"])
    out = capsys.readouterr().out
    assert "max_tokens: plan 150000, reached 91604, kept" in out
    assert "max_wall_clock_s: plan 900, reached 80.8, kept" in out
    assert "limits that could not be measured: 2 of 8" in out


def test_check_116_no_harness_total_is_said_and_the_plans_own_sentence_is_read(capsys):
    root = data_root()
    plan = json.loads((root / PAPER / "run-plans" / "run-0116.json").read_text())
    rc = run_plan.main(["check", "--data", str(root), "--run", "116"])
    out = capsys.readouterr().out
    assert "no harness total on the run's line: this limit cannot be shown kept" in out
    assert plan["max_tokens_is"] in out
    assert "transcript tokens: input fresh" in out
    assert "limits that could not be measured: 3 of 8" in out
    assert rc == _real_rc()


def test_every_real_plan_is_unchanged_since_it_was_added(capsys):
    root = data_root()
    nums = sorted(int(re.search(r"(\d+)", p.name).group(1)) for p in (root / PAPER / "run-plans").glob("run-*.json"))
    nums = [n for n in nums if n >= 114]
    assert nums[0] == 114
    for n in nums:
        run_plan.main(["check", "--data", str(root), "--run", str(n)])
        assert "unchanged since it was added" in capsys.readouterr().out, n


def test_check_96_with_no_plan_still_counts_its_graph_writes(capsys):
    rc = run_plan.main(["check", "--data", str(data_root()), "--run", "96"])
    out = capsys.readouterr().out
    assert "max_graph_writes: no plan, reached 32" in out  # the reviewer counted 32 lines with written_by run:0096
    assert "no plan file" in out
    assert rc == 1


def test_brief_says_the_stop_sentence_once(capsys):
    run_plan.main(["brief", "--data", str(data_root()), "--run", "122"])
    assert capsys.readouterr().out.count("what is open") == 1


def test_write_refuses_run_below_one_and_limits_below_one(tmp_path, capsys):
    d = _scratch(tmp_path)
    n = _next_unused(d)
    assert run_plan.main(["write", "--data", str(d)] + _base(0)) == 2
    assert "run number" in capsys.readouterr().err
    for key in ("max_model_calls", "max_tokens", "max_wall_clock_s", "max_concurrent_workers"):
        args = _base(n)
        args[args.index("--" + key.replace("_", "-")) + 1] = "0"
        assert run_plan.main(["write", "--data", str(d)] + args) == 2, key
        assert key in capsys.readouterr().err
    args = _base(n)
    for key in ("max_sub_agents", "max_tool_calls", "max_retries", "max_graph_writes"):
        args[args.index("--" + key.replace("_", "-")) + 1] = "0"
    assert run_plan.main(["write", "--data", str(d)] + args) == 0


# ---- CASES THE REAL RECORD DOES NOT HOLD: each uses real files of the record in a scratch git repository;
# ---- only what is named here is the scratch's own
# Scratch's own: the git repository and its commit dates; the merge commit that adds a plan; the one edited copy
# of a plan (max_tool_calls 999); the plan copy with max_tokens_is deleted; the one uncommitted plan; the copy of
# run 117's real line with a start time added or left off (and the two bad start times); the record emptied in the
# git-history case; the plan given through --plan (a copy of run 117's own plan, edited, or run 116's real plan);
# the folder that is not a git repository; the files other.txt and main.txt (the two commits that make the merge
# commit's two sides) and the scratch's copy of run 128's real plan, run-0128.json (the one real file copied into a
# folder with no git); the scratch repositories of the earliest-add case (side branch and merge), the staged and never
# committed plan, the shallow clone and the grafted copy, and the date-only start time. Real: run-0117.json, run 117's kept transcript and line, run-0116.json,
# and for run 128 the record as it was at markets-data 04d8a0f (read with git).
FIRST = "2026-11-24T13:10:23.610000+00:00"  # the first line of run 117's real kept transcript


def _git(d, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="s", GIT_AUTHOR_EMAIL="s@s", GIT_COMMITTER_NAME="s",
               GIT_COMMITTER_EMAIL="s@s")
    if when:
        env.update(GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    subprocess.run(["git", "-C", str(d), *args], check=True, capture_output=True, env=env)


def _repo(tmp_path, transcript=True):
    root = data_root()
    d = tmp_path / "g"
    (d / PAPER / "run-plans").mkdir(parents=True)
    (d / PAPER / "transcripts").mkdir()
    shutil.copy(root / PAPER / "run-plans" / "run-0117.json", d / PAPER / "run-plans")
    shutil.copy(root / PAPER / "agent-runs.jsonl", d / PAPER)
    if transcript:
        shutil.copy(root / PAPER / "transcripts" / "run-0117.jsonl.gz", d / PAPER / "transcripts")
    _git(d, "init", "-q")
    return d


def test_plan_committed_after_its_run_began_is_exit_1(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "late", when="2026-11-24T13:20:00+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    assert "AFTER the run began" in capsys.readouterr().out
    assert rc == 1


def test_plan_committed_before_its_run_began_is_exit_0(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "early", when="2026-11-24T13:08:54+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "unchanged since it was added" in out and "before the run began" in out
    assert rc == 0


def test_plan_edited_after_its_add_commit_is_exit_1(tmp_path, capsys):
    d = _repo(tmp_path)
    f = d / PAPER / "run-plans" / "run-0117.json"
    first = f.read_bytes()
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "add", when="2026-11-24T13:08:54+00:00")
    plan = json.loads(first)
    plan["max_tool_calls"] = 999
    f.write_text(json.dumps(plan, indent=1) + "\n")
    _git(d, "commit", "-q", "-am", "edit", when="2026-11-24T13:20:00+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "changed after it was written" in out
    assert hashlib.sha256(first).hexdigest() in out and hashlib.sha256(f.read_bytes()).hexdigest() in out
    assert rc == 1


def test_plan_not_in_git_is_exit_1(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", str(PAPER + "/agent-runs.jsonl"))
    _git(d, "commit", "-q", "-m", "only the record", when="2026-11-24T13:08:54+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    assert "the plan file is not in git" in capsys.readouterr().out
    assert rc == 1


def _line_117(extra):
    root = data_root()
    last = [json.loads(l) for l in (root / PAPER / "agent-runs.jsonl").read_text().splitlines()
            if json.loads(l).get("run") == 117][-1]
    last.update(extra)
    return last


def test_git_order_from_the_lines_start_time_without_a_transcript(tmp_path, capsys):
    d = _repo(tmp_path, transcript=False)
    (d / PAPER / "agent-runs.jsonl").write_text(json.dumps(_line_117({"started_at": FIRST})) + "\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "early", when="2026-11-24T13:08:54+00:00")
    run_plan.main(["check", "--data", str(d), "--run", "117"])
    assert "before the run began" in capsys.readouterr().out
    _git(d, "commit", "-q", "--amend", "-m", "late", "--date", "2026-11-24T13:20:00+00:00",
         when="2026-11-24T13:20:00+00:00")
    assert run_plan.main(["check", "--data", str(d), "--run", "117"]) == 1


def test_git_order_without_start_time_and_without_transcript_says_so(tmp_path, capsys):
    d = _repo(tmp_path, transcript=False)
    (d / PAPER / "agent-runs.jsonl").write_text(json.dumps(_line_117({})) + "\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "early", when="2026-11-24T13:08:54+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    assert "not measured: the run's line holds no start time and no transcript is kept" in capsys.readouterr().out
    assert rc == 0


def test_write_refuses_a_run_whose_plan_is_in_git_history_though_the_file_is_gone(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "add", when="2026-11-24T13:08:54+00:00")
    (d / PAPER / "run-plans" / "run-0117.json").unlink()
    (d / PAPER / "agent-runs.jsonl").write_text("")  # the record has no line, so only git can say it was written
    rc = run_plan.main(["write", "--data", str(d)] + _base(117))
    assert rc == 2 and "git history" in capsys.readouterr().err


def test_plan_without_max_tokens_is_says_so(tmp_path, capsys):
    # every real plan from 114 on holds max_tokens_is, so the scratch's own copy of run 117's plan drops it
    d = _repo(tmp_path)
    f = d / PAPER / "run-plans" / "run-0117.json"
    plan = json.loads(f.read_text())
    del plan["max_tokens_is"]
    f.write_text(json.dumps(plan, indent=1) + "\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "add", when="2026-11-24T13:08:54+00:00")
    run_plan.main(["check", "--data", str(d), "--run", "117"])
    assert "the plan holds no max_tokens_is" in capsys.readouterr().out


def test_paired_check_of_an_edited_copy_of_the_runs_own_plan_is_exit_3_not_0(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "x", when="2026-11-24T13:08:54+00:00")
    plan = json.loads((data_root() / PAPER / "run-plans" / "run-0117.json").read_text())
    plan["max_tool_calls"] = 999
    out_plan = tmp_path / "edited.json"
    out_plan.write_text(json.dumps(plan))
    rc = run_plan.main(["check", "--data", str(d), "--run", "117", "--plan", str(out_plan)])
    out = capsys.readouterr().out
    assert out.startswith("PAIRED CHECK: the plan read is ")
    assert _limits(out)["max_tool_calls"][:3] == ("999", "30", "kept")
    assert rc == 3


def test_plan_added_inside_a_merge_commit_is_found(tmp_path, capsys):
    d = _repo(tmp_path)
    _git(d, "add", PAPER + "/agent-runs.jsonl", PAPER + "/transcripts")
    _git(d, "commit", "-q", "-m", "base", when="2026-11-24T13:00:00+00:00")
    _git(d, "checkout", "-q", "-b", "side")
    (d / "other.txt").write_text("side")
    _git(d, "add", "other.txt")
    _git(d, "commit", "-q", "-m", "side", when="2026-11-24T13:01:00+00:00")
    _git(d, "checkout", "-q", "-")
    (d / "main.txt").write_text("main")
    _git(d, "add", "main.txt")
    _git(d, "commit", "-q", "-m", "main", when="2026-11-24T13:02:00+00:00")
    _git(d, "merge", "-q", "--no-commit", "--no-ff", "side")
    _git(d, "add", PAPER + "/run-plans/run-0117.json")
    _git(d, "commit", "-q", "-m", "merge that adds the plan", when="2026-11-24T13:08:54+00:00")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "the plan file is not in git" not in out
    assert "unchanged since it was added" in out and "before the run began" in out
    assert rc == 0


def test_start_time_forms_without_a_transcript(tmp_path, capsys):
    d = _repo(tmp_path, transcript=False)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "early", when="2026-11-24T13:08:54+00:00")
    rec = d / PAPER / "agent-runs.jsonl"
    for value, want, rc_want in (
            ("2026-11-24T13:10:23.610000Z", "before the run began", 0),
            ("2026-11-24T13:10:23.610000", "read as UTC: the line names no zone", 0),
            (1795000000, "not measured: the run's line holds a start time that cannot be read (1795000000)", 0),
            ("yesterday", "not measured: the run's line holds a start time that cannot be read (yesterday)", 0)):
        rec.write_text(json.dumps(_line_117({"started_at": value})) + "\n")
        assert run_plan.main(["check", "--data", str(d), "--run", "117"]) == rc_want
        out = capsys.readouterr().out
        assert want in out, value
    rec.write_text(json.dumps(_line_117({"started_at": "2026-11-24T13:00:00"})) + "\n")
    assert run_plan.main(["check", "--data", str(d), "--run", "117"]) == 1  # no zone, read as UTC: committed after


def test_an_earlier_line_with_a_harness_total_is_named(tmp_path, capsys):
    # real: run 128's two lines as the record was at markets-data 04d8a0f (first line 52,854, correcting line none)
    root = data_root()
    d = tmp_path / "m"
    (d / PAPER / "run-plans").mkdir(parents=True)
    shutil.copy(root / PAPER / "run-plans" / "run-0128.json", d / PAPER / "run-plans")
    rec = subprocess.run(["git", "-C", str(root), "show", f"04d8a0f:{PAPER}/agent-runs.jsonl"],
                         capture_output=True, text=True, check=True).stdout
    (d / PAPER / "agent-runs.jsonl").write_text(rec)
    run_plan.main(["check", "--data", str(d), "--run", "128"])
    out = capsys.readouterr().out
    assert "an earlier line of this run holds a harness total of 52854; the newest line holds none" in out
    assert "no harness total on the run's line: this limit cannot be shown kept" in out


def test_write_into_a_folder_that_is_not_a_git_repository_is_refused(tmp_path, capsys):
    d = tmp_path / "plain"
    (d / PAPER / "run-plans").mkdir(parents=True)
    shutil.copy(data_root() / PAPER / "agent-runs.jsonl", d / PAPER)
    rc = run_plan.main(["write", "--data", str(d), "--session", "s"] + _base(900))
    assert rc == 2 and "not a git repository" in capsys.readouterr().err
    assert not list((d / PAPER / "run-plans").iterdir())


def _plan_line_and_transcript_repo(tmp_path):
    d = _repo(tmp_path)
    _git(d, "add", PAPER + "/agent-runs.jsonl", PAPER + "/transcripts")
    _git(d, "commit", "-q", "-m", "base", when="2026-11-24T13:00:00+00:00")
    return d


def test_a_plan_file_given_with_plan_that_does_not_exist_is_refused_with_its_name(tmp_path, capsys):
    d = _repo(tmp_path)
    nope = tmp_path / "nope.json"
    rc = run_plan.main(["check", "--data", str(d), "--run", "117", "--plan", str(nope)])
    cap = capsys.readouterr()
    assert rc == 2
    assert str(nope) in cap.err and "does not exist" in cap.err
    assert "limits were not written" not in cap.err + cap.out


def test_two_commits_that_add_the_plan_the_earliest_is_the_add(tmp_path, capsys):
    # change: the plan is added on a side branch (13:05) and again, as far as first-parent history shows, by the
    # merge (13:20); the run began 13:10:23, so the earliest add is before it and the newest would be after it
    d = _plan_line_and_transcript_repo(tmp_path)
    _git(d, "checkout", "-q", "-b", "side")
    _git(d, "add", PAPER + "/run-plans/run-0117.json")
    _git(d, "commit", "-q", "-m", "side adds the plan", when="2026-11-24T13:05:00+00:00")
    _git(d, "checkout", "-q", "-")
    (d / "main.txt").write_text("main")
    _git(d, "add", "main.txt")
    _git(d, "commit", "-q", "-m", "main", when="2026-11-24T13:06:00+00:00")
    _git(d, "merge", "-q", "--no-ff", "-m", "merge", "side", when="2026-11-24T13:20:00+00:00")
    log = subprocess.run(["git", "-C", str(d), "log", "--diff-merges=first-parent", "--diff-filter=A", "--name-only",
                          "--format=COMMIT %cI", "--", PAPER + "/run-plans/run-0117.json"],
                         capture_output=True, text=True, check=True).stdout
    assert log.count("COMMIT ") == 2  # git itself lists both as adds
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "committed 2026-11-24T13:05:00+00:00 before the run began" in out
    assert rc == 0


def test_a_plan_staged_and_never_committed_is_tracked_without_an_add(tmp_path, capsys):
    # change: git add with no commit that holds the plan
    d = _repo(tmp_path)
    _git(d, "add", "-A")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "plan in git: the file is in the index and no commit has added it" in out
    assert "the plan file is not in git" not in out
    assert rc == 1


def _three_commits(tmp_path):
    d = _plan_line_and_transcript_repo(tmp_path)
    _git(d, "add", PAPER + "/run-plans/run-0117.json")
    _git(d, "commit", "-q", "-m", "plan", when="2026-11-24T13:08:54+00:00")
    (d / "other.txt").write_text("later")
    _git(d, "add", "other.txt")
    _git(d, "commit", "-q", "-m", "later", when="2026-11-24T14:00:00+00:00")
    return d


def test_a_shallow_clone_says_the_add_time_is_not_measured_and_is_exit_3(tmp_path, capsys):
    # change: a real shallow clone (depth 1) of a repository whose plan was added at 13:08:54, before the run
    src = _three_commits(tmp_path)
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{src}", str(clone)], check=True,
                   capture_output=True)
    rc = run_plan.main(["check", "--data", str(clone), "--run", "117"])
    out = capsys.readouterr().out
    assert "is shallow, so the time the plan was added is not known" in out
    assert "AFTER the run began" not in out
    assert rc == 3
    f = clone / PAPER / "run-plans" / "run-0117.json"
    plan = json.loads(f.read_text())
    plan["max_tool_calls"] = 999  # something else already exit 1
    f.write_text(json.dumps(plan, indent=1) + "\n")
    assert run_plan.main(["check", "--data", str(clone), "--run", "117"]) == 1


def test_a_grafted_history_says_the_add_time_is_not_measured_and_is_exit_3(tmp_path, capsys):
    # change: git replace --graft makes the newest commit (14:00) a root commit, so it reads as the plan's add
    d = _three_commits(tmp_path)
    _git(d, "replace", "--graft", "HEAD")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "is grafted, so the time the plan was added is not known" in out
    assert "AFTER the run began" not in out
    assert rc == 3


def test_a_started_at_that_is_a_date_with_no_time_is_not_measured_and_is_exit_3(tmp_path, capsys):
    # change: the copy of run 117's real line has started_at "2026-11-24" (a date, no time of day)
    d = _repo(tmp_path, transcript=False)
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "early", when="2026-11-24T13:08:54+00:00")
    (d / PAPER / "agent-runs.jsonl").write_text(json.dumps(_line_117({"started_at": "2026-11-24"})) + "\n")
    rc = run_plan.main(["check", "--data", str(d), "--run", "117"])
    out = capsys.readouterr().out
    assert "a date with no time of day (2026-11-24)" in out
    assert "AFTER the run began" not in out
    assert rc == 3
