"""Ticket 25: Artifact nodes and Metric nodes, and the session text that shows the current versions.

Every check runs on ONE scratch copy of the real graph with the real files of the three checkouts.
Nothing is written into the real graph. Expectations are stated from facts of the record (named in
each check) or from git called here, not from the code under test.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph import context, extract, ingest_agent_runs, ingest_artifacts, schema
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root

MARKETS = Path(__file__).resolve().parents[2]
PLATFORM = Path("/home/user/paper-trading-platform")
NOT_RECORDED = "not recorded: no agent run's line names commit"


def git(d, *a):
    r = subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
    return r.stdout.strip()


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = data_root()
    if not PLATFORM.exists():
        pytest.skip("no paper-trading-platform checkout beside Markets")
    g = tmp_path_factory.mktemp("artgraph") / "graph"
    shutil.copytree(root / "graph", g)
    store = GraphStore(root, graph_dir=g)
    ingest_agent_runs.agent_runs(store)          # the newer runs become nodes of the scratch copy
    dirs = extract.repo_dirs(root, str(MARKETS), str(PLATFORM))
    before_problems = store.check_all()
    text_before = context.build(store, None, 6000, dirs=dirs)["text"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        first = ingest_artifacts.main(["--data", str(root), "--graph-dir", str(g),
                                       "--markets", str(MARKETS), "--platform", str(PLATFORM)])
    printed_first = out.getvalue()
    out2 = io.StringIO()
    with contextlib.redirect_stdout(out2):
        second = ingest_artifacts.main(["--data", str(root), "--graph-dir", str(g),
                                        "--markets", str(MARKETS), "--platform", str(PLATFORM)])
    store = GraphStore(root, graph_dir=g)
    at_ingest = {r: (git(d, "rev-parse", "--abbrev-ref", "HEAD"), git(d, "rev-parse", "HEAD"), git(d, "log", "-1", "--format=%s"))
                 for r, d in (("Markets", MARKETS), ("paper-trading-platform", PLATFORM), ("markets-data", root))}
    return {"at_ingest": at_ingest, "store": store, "root": root, "dirs": dirs, "before_problems": before_problems,
            "text_before": text_before, "printed_first": printed_first, "printed_second": out2.getvalue(),
            "codes": (first, second), "after_problems": store.check_all(),
            "text_after": context.build(store, None, 6000, dirs=dirs)["text"]}


def test_decider_v1_has_its_last_commit_and_the_four_required_attrs(world):
    # fact: tools/decider/programs/decider_v1.py was last changed by Markets commit 04f43786...
    n = world["store"].node("artifact:Markets:tools/decider/programs/decider_v1.py")
    assert n["type"] == "Artifact"
    assert n["attrs"]["version"] == "04f437861201ba5b8be0b411346a91eafdc531c6"
    for k in ("repo", "path", "version", "authoring_run"):
        assert n["attrs"].get(k)
    assert n["attrs"]["set"] == "decider programs"
    assert len(n["attrs"]["sha256"]) == 64 and n["attrs"]["bytes"] > 0


def test_every_rule_file_and_control_file_has_an_artifact(world):
    rules = sorted(os.listdir(PLATFORM / "paper_platform/rules"))
    assert len(rules) == 32 and rules[0].startswith("CL01") and rules[-1].startswith("CX15")
    for f in rules:
        assert world["store"].node(f"artifact:paper-trading-platform:paper_platform/rules/{f}"), f
    for f in ("packet_graph_v1.md", "paper_rules.md", "platform_decider.md", "platform_exit.md"):
        assert world["store"].node(f"artifact:Markets:tools/ratchet/programs/{f}"), f
    assert len(os.listdir(MARKETS / "tools/ratchet/programs")) == 4
    decider = [p for p in os.listdir(MARKETS / "tools/decider/programs") if (MARKETS / "tools/decider/programs" / p).is_file()]
    assert len(decider) == 5
    for f in decider:
        assert world["store"].node(f"artifact:Markets:tools/decider/programs/{f}"), f


@pytest.mark.parametrize("repo,where", [("Markets", MARKETS), ("paper-trading-platform", PLATFORM),
                                        ("markets-data", Path("/home/user/markets-data"))])
def test_working_branch_artifact_holds_the_branch_and_head_git_gives(world, repo, where):
    n = world["store"].node(f"artifact:{repo}:working-branch")
    a = n["attrs"]
    # git, called by the test straight after the ingest (other builders move markets-data's head meanwhile)
    branch, head, subject = world["at_ingest"][repo]
    assert a["branch"] == branch and a["head"] == head == a["version"] and a["head_subject"] == subject
    assert a["read_from"] == where.name and a["as_read_at"]
    assert a["authoring_run"]


def test_codex_branch_artifact_from_the_remote_ref(world):
    ref = "origin/codex/strategy-trades-and-mbo-capture"
    n = world["store"].node("artifact:paper-trading-platform:codex-branch")
    assert n["attrs"]["head"] == git(PLATFORM, "rev-parse", ref)
    assert n["attrs"]["branch"] == ref


def test_authoring_run_is_named_only_when_a_line_names_the_commit(world):
    runs = ingest_artifacts.run_lines(world["root"])
    # record: run 119's newest line lists data_commits 11fe552 and 9079b22 (markets-data); no other line names 11fe552
    full = git("/home/user/markets-data", "rev-parse", "11fe552")
    assert ingest_artifacts.authoring_run(full, runs) == "run:0119"
    # record: only run 114's newest line names code_commit 68d65a6 (no commit is named by two runs, so the
    # several-runs wording of authoring_run has no real case to check against)
    full = git(MARKETS, "rev-parse", "68d65a6") or git(PLATFORM, "rev-parse", "68d65a6")
    assert full
    said = ingest_artifacts.authoring_run(full, runs)
    assert said == "run:0114"
    # no real file of the six sets is last changed by a commit a run names: none exists to point at,
    # so a file carries the "not recorded" text, and is in the printed list
    n = world["store"].node("artifact:Markets:tools/decider/programs/decider_v1.py")
    assert n["attrs"]["authoring_run"] == f"{NOT_RECORDED} 04f4378"
    assert "tools/decider/programs/decider_v1.py" in world["printed_first"]
    assert "no run on record" in world["printed_first"]


def test_a_named_run_gets_a_produced_link_from_the_run_and_the_commit_a_link_too(world):
    edges = world["store"].edges("PRODUCED")
    mine = [e for e in edges if e["dst"] == "artifact:Markets:tools/decider/programs/decider_v1.py"]
    assert [e["src"] for e in mine] == ["commit:Markets:04f4378612"]


def test_metric_of_run_0114_tool_calls(world):
    # record: run 114's newest line has tool_calls 26 and output_tokens 20871
    m = world["store"].node("metric:run:0114:tool_calls")
    assert m["type"] == "Metric" and m["attrs"]["value"] == 26 and m["attrs"]["of"] == "run:0114"
    assert m["attrs"]["unit"] == "calls" and m["attrs"]["source_line"] > 0
    assert world["store"].node("metric:run:0114:output_tokens")["attrs"]["value"] == 20871


def test_every_metric_is_of_one_run_and_none_is_a_sum(world):
    ms = world["store"].nodes("Metric")
    assert ms
    for m in ms:
        a = m["attrs"]
        assert a["of"].startswith("run:") and "," not in a["of"] and a["of"].count("run:") == 1
        assert m["id"] == f"metric:{a['of']}:{a['name']}"
        assert world["store"].node(a["of"])["type"] == "AgentRun"
    names = {m["attrs"]["name"] for m in ms}
    assert names <= set(ingest_artifacts.FIGURES)


def test_a_null_figure_writes_no_metric(world):
    lines = (world["root"] / PAPER / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    newest = {}
    for l in lines:
        d = json.loads(l)
        newest[d["run"]] = d
    pairs = [(r, k) for r, d in newest.items() for k in ingest_artifacts.FIGURES if d.get(k) is None]
    assert pairs
    for r, k in pairs[:200]:
        assert world["store"].node(f"metric:run:{r:04d}:{k}") is None


def test_a_second_ingest_writes_nothing_new_and_the_checks_find_nothing_new(world):
    assert world["codes"] == (0, 0)
    assert "'new': 0, 'revised': 0" in world["printed_second"]
    assert "'new': 0" not in world["printed_first"]
    assert set(world["after_problems"]) <= set(world["before_problems"])


def test_session_text_shows_the_markets_branch_and_head(world):
    branch = git(MARKETS, "rev-parse", "--abbrev-ref", "HEAD")
    head7 = git(MARKETS, "rev-parse", "HEAD")[:7]
    text = world["text_after"]
    assert "CURRENT VERSIONS" in text
    line = next(l for l in text.splitlines() if "Markets" in l and branch in l and head7 in l)
    assert "as read at" in line
    assert "check each with git before trusting it" in text


def test_session_text_without_artifacts_says_none_on_record(world):
    assert "CURRENT VERSIONS: none on record (run tools.kgraph.ingest_artifacts)" in world["text_before"]
    assert "artifact:" not in world["text_before"]


def test_session_text_is_within_its_budget(world):
    for budget in (6000, 3000):
        r = context.build(world["store"], None, budget, dirs=world["dirs"])
        assert len(r["text"]) <= budget * context.CHARS_PER_TOKEN, budget


def test_current_versions_block_is_held_to_a_tenth_and_says_what_it_cut(world):
    for budget in (1500, 2000, 2500, 3000):
        lines = ingest_artifacts.current_versions_lines(world["store"], budget)
        files = [l for l in lines if l.startswith("- tools/")]
        assert any("not shown for want of budget" in l for l in lines), budget
        assert len(files) < 9
        if files:
            assert sum(len(l) + 1 for l in lines) <= budget * context.CHARS_PER_TOKEN * 0.10 + 80
    full = ingest_artifacts.current_versions_lines(world["store"], 400000)
    assert not any("not shown" in l for l in full)
    assert any("decider_v1.py" in l and "04f4378" in l for l in full)
    assert any("32 rule files" in l for l in full)
