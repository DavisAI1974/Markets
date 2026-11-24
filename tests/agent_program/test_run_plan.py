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

import json
import re
import shutil

from tools.kgraph import run_plan
from tools.swarm.plan import BUDGET_KEYS

from .realrecords import PAPER, data_root

LINE = re.compile(r"^(max_\w+): plan (\S+), reached (\S+), (.*)$")


def _limits(out):
    return {m.group(1): (m.group(2), m.group(3), m.group(4)) for l in out.splitlines() if (m := LINE.match(l))}


def _scratch(tmp_path):
    root = data_root()
    dst = tmp_path / "md"
    (dst / PAPER).mkdir(parents=True)
    shutil.copytree(root / PAPER / "run-plans", dst / PAPER / "run-plans")
    shutil.copy(root / PAPER / "agent-runs.jsonl", dst / PAPER / "agent-runs.jsonl")
    return dst


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
    assert "before the run began" in out
    assert rc == 0


def test_check_116_four_of_25(capsys):
    rc = run_plan.main(["check", "--data", str(data_root()), "--run", "116"])
    lim = _limits(capsys.readouterr().out)
    assert lim["max_tool_calls"][:2] == ("25", "4")
    assert rc == 0


def test_check_109_has_no_plan(capsys):
    rc = run_plan.main(["check", "--data", str(data_root()), "--run", "109"])
    assert "no plan file" in capsys.readouterr().out
    assert rc == 1


def test_check_passed_branch_paired_plan(capsys):
    root = data_root()
    plan116 = root / PAPER / "run-plans" / "run-0116.json"
    rc = run_plan.main(["check", "--data", str(root), "--run", "117", "--plan", str(plan116)])
    lim = _limits(capsys.readouterr().out)
    assert lim["max_tool_calls"][:3] == ("25", "30", "PASSED")
    assert rc == 1


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
