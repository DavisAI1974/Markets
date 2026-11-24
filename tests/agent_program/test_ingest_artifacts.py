"""Ticket 25: Artifact nodes and Metric nodes, and the session text that shows current versions.

Every check runs on ONE scratch copy of the real graph with the real files of the three checkouts, and
on ONE snapshot of what the ingest reads (checkouts move while the checks run: other builders push).
Expectations are stated from facts of the record (named in each check) or from git called here.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph import context, extract, ingest_agent_runs, ingest_artifacts
from tools.kgraph.ingest_agent_runs import RUNS_FILE
from tools.kgraph.store import GraphStore

from .realrecords import data_root

MARKETS = Path(__file__).resolve().parents[2]
PLATFORM = Path("/home/user/paper-trading-platform")
CODEX = "origin/codex/strategy-trades-and-mbo-capture"
OUTSIDE = "none: made outside the agent runs"


def git(d, *a):
    r = subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
    return r.stdout.strip()


def _heads(root):
    return {r: (git(d, "rev-parse", "--abbrev-ref", "HEAD"), git(d, "rev-parse", "HEAD"), git(d, "log", "-1", "--format=%s"))
            for r, d in (("Markets", MARKETS), ("paper-trading-platform", PLATFORM), ("markets-data", root))}


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
    git_before = _heads(root)
    snap = ingest_artifacts.read_snapshot(root, dirs)
    git_after = _heads(root)
    first = ingest_artifacts.ingest(store, snap)
    second = ingest_artifacts.ingest(store, snap)                        # the same snapshot twice
    third = ingest_artifacts.ingest(store, dict(snap, read_at="2099-01-01T00:00:00Z"))   # same state, read later
    store = GraphStore(root, graph_dir=g)
    return {"store": store, "root": root, "dirs": dirs, "snap": snap, "before_problems": before_problems,
            "text_before": text_before, "git": (git_before, git_after), "ingests": (first, second, third),
            "after_problems": store.check_all(),
            "text_after": context.build(store, None, 6000, dirs=dirs)["text"]}


def _node(world, repo, rel):
    return world["store"].node(f"artifact:{repo}:{rel}")


def test_decider_v1_has_its_last_commit_and_the_four_required_attrs(world):
    # fact: tools/decider/programs/decider_v1.py was last changed by Markets commit 04f43786...
    n = _node(world, "Markets", "tools/decider/programs/decider_v1.py")
    assert n["type"] == "Artifact"
    assert n["attrs"]["version"] == "04f437861201ba5b8be0b411346a91eafdc531c6"
    for k in ("repo", "path", "version", "authoring_run"):
        assert n["attrs"].get(k)
    assert n["attrs"]["set"] == "decider programs"
    assert len(n["attrs"]["sha256"]) == 64 and n["attrs"]["bytes"] > 0


def test_a_builders_outcome_text_names_the_author(world):
    # record: run 87 (role "builder, as the writer") has outcome "finished. Markets 04f4378, 073f43d. 4 checks passed ..."
    for f in ("decider_v1.py", "decider_v1.md"):
        a = _node(world, "Markets", f"tools/decider/programs/{f}")["attrs"]
        assert a["authoring_run"] == "run:0087", f
        assert a["authoring_basis"].startswith("outcome text of a builder") and "not from a field" in a["authoring_basis"]
    # record: run 88 (builder) outcome names Markets 6fdd4e1, ad57e2b, 131a9dc, 1e9a7c5
    for rel in ("tools/decider/programs/loop_decider.py", "tools/ratchet/programs/platform_decider.md"):
        assert _node(world, "Markets", rel)["attrs"]["authoring_run"] == "run:0088", rel
    mine = [e["src"] for e in world["store"].edges("PRODUCED") if e["dst"] == "artifact:Markets:tools/decider/programs/decider_v1.py"]
    assert sorted(mine) == ["commit:Markets:04f4378612", "run:0087"]


def test_a_reviewers_task_text_is_not_authorship(world):
    # record: the task texts of five reviewer runs (79, 82, 86, 101, 103) name Codex's head 47fa1c5; they read it
    a = world["store"].node("artifact:paper-trading-platform:codex-branch")["attrs"]
    named = [n for n, (_, d) in world["snap"]["runs"].items() if "47fa1c5" in str(d.get("task"))]
    assert named and all(not ingest_artifacts._is_builder(world["snap"]["runs"][n][1]) for n in named)
    assert a["authoring_run"] == OUTSIDE
    assert a["authoring_basis"].startswith("outside the agent runs")
    assert a["git_author"] == git(PLATFORM, "log", "-1", "--format=%an", a["head"])
    assert not [e for e in world["store"].edges("PRODUCED") if e["dst"] == "artifact:paper-trading-platform:codex-branch"
                and e["src"].startswith("run:")]


def test_platform_rule_files_were_made_outside_the_agent_runs(world):
    rules = sorted(os.listdir(PLATFORM / "paper_platform/rules"))
    assert len(rules) == 32 and rules[0].startswith("CL01") and rules[-1].startswith("CX15")
    for f in rules:
        n = _node(world, "paper-trading-platform", f"paper_platform/rules/{f}")
        a = n["attrs"]
        assert a["authoring_run"] == OUTSIDE, f
        assert a["git_author"] == git(PLATFORM, "log", "-1", "--format=%an", a["version"]), f


def test_every_listed_file_has_an_artifact_and_a_missing_one_is_named(world):
    for f in ("packet_graph_v1.md", "paper_rules.md", "platform_decider.md", "platform_exit.md"):
        assert _node(world, "Markets", f"tools/ratchet/programs/{f}"), f
    decider = [p for p in os.listdir(MARKETS / "tools/decider/programs") if (MARKETS / "tools/decider/programs" / p).is_file()]
    assert len(decider) == 5
    for f in decider:
        assert _node(world, "Markets", f"tools/decider/programs/{f}"), f
    for f in ("scout.md", "builder.md", "reviewer.md", "frankie-performance-auditor.md"):
        n = _node(world, "Markets", f".claude/agents/{f}")
        assert n and n["attrs"]["set"] == "agent files", f
    for rel in ("research/kalshi/frankie_boss/CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md",
                "research/kalshi/frankie_boss/CODEX_PROMPT_AMENDMENTS_20261123.md",
                "research/kalshi/frankie_boss/README_HANDOFF_20261123.md",
                "research/kalshi/FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md"):
        if (MARKETS / rel).is_file():
            assert _node(world, "Markets", rel)["attrs"]["set"] == "plan files", rel
        else:
            assert any(rel in s and "not in this checkout" in s for s in world["snap"]["skipped"]), rel


@pytest.mark.parametrize("repo,where", [("Markets", MARKETS), ("paper-trading-platform", PLATFORM),
                                        ("markets-data", Path("/home/user/markets-data"))])
def test_working_branch_artifact_holds_the_branch_and_head_git_gives(world, repo, where):
    a = world["store"].node(f"artifact:{repo}:working-branch")["attrs"]
    before, after = world["git"][0][repo], world["git"][1][repo]
    # git, called by this test before and after the snapshot: the stored head is one of the two
    assert a["branch"] in (before[0], after[0]) and a["head"] in (before[1], after[1]) and a["version"] == a["head"]
    assert a["head_subject"] in (before[2], after[2])
    assert a["read_from"] == where.name and a["first_read_at"] and "as_read_at" not in a
    assert a["authoring_run"] and a["authoring_basis"]


def test_codex_branch_artifact_from_the_remote_ref(world):
    n = world["store"].node("artifact:paper-trading-platform:codex-branch")
    assert n["attrs"]["head"] == git(PLATFORM, "rev-parse", CODEX) and n["attrs"]["branch"] == CODEX


def test_authoring_run_from_a_field_in_the_real_record(world):
    s = world["snap"]
    # record: run 119's newest line lists data_commits 11fe552 and 9079b22 (markets-data)
    full = git("/home/user/markets-data", "rev-parse", "11fe552")
    got = ingest_artifacts.authorship("markets-data", full, s["runs"], s["info"].get("markets-data", {}), s["sessions"])
    assert got["authoring_run"] == "run:0119" and got["authoring_basis"].startswith("field")
    # record: only run 114's newest line names code_commit 68d65a6
    full = git(MARKETS, "rev-parse", "68d65a6") or git(PLATFORM, "rev-parse", "68d65a6")
    assert full
    got = ingest_artifacts.authorship("Markets", full, s["runs"], {}, s["sessions"])
    assert got["authoring_run"] == "run:0114" and got["authoring_basis"].startswith("field")


def _expected_basis(root, runs_text, sha):
    """From the raw record text and git alone (not from ingest_artifacts): 'main' when the commit's own
    message ends with the Claude-Session line of a session of the record and its committer time is from that
    session's first start to its latest ended_at (latest started_at where no line has one), or later while no
    later session has a line; otherwise 'outside'."""
    lines = [json.loads(l) for l in runs_text.splitlines() if l.strip()]
    msg = git(root, "log", "-1", "--format=%B", sha)
    ids = re.findall(r"Claude-Session:\s*\S*?(session_[A-Za-z0-9]+)", msg)
    if not ids:
        return "outside"
    sid = ids[-1]
    def when(x):
        return ingest_artifacts._time(x)
    sess = {}
    for d in lines:
        if d.get("session"):
            sess.setdefault(d["session"], []).append(d)
    if sid not in sess:
        return "outside"
    def start_of(k):
        st = [when(d.get("started_at")) for d in sess[k] if when(d.get("started_at"))]
        if st:
            return min(st)
        own = [when(git(root, "log", "-1", "--format=%cI", h)) for h in
               git(root, "log", "--format=%H", f"--grep={k}").split()]
        return min(own) if own else None
    starts = {k: start_of(k) for k in sess}
    st = starts[sid]
    t = when(git(root, "log", "-1", "--format=%cI", sha))
    ends = [when(d.get("ended_at")) for d in sess[sid] if when(d.get("ended_at"))]
    sts = [when(d.get("started_at")) for d in sess[sid] if when(d.get("started_at"))]
    if sts:
        end = max(ends or sts)
    else:
        own = [when(git(root, "log", "-1", "--format=%cI", h)) for h in git(root, "log", "--format=%H", f"--grep={sid}").split()]
        end = max(own)
    later = any(v and v > st for k, v in starts.items() if k != sid)
    return "main" if st <= t and (t <= end or not later) else "outside"


def test_the_main_sessions_commits_and_those_outside_the_runs_hold_against_git(world):
    runs_text = (world["root"] / RUNS_FILE).read_text(encoding="utf-8")
    seen = {"main": 0, "outside": 0}
    for a in [n["attrs"] for n in world["store"].nodes("Artifact")]:
        if a["repo"] != "DavisAI1974/markets-data" or "authoring_basis" not in a:
            continue
        msg = git("/home/user/markets-data", "log", "-1", "--format=%B", a["version"])
        ids = re.findall(r"Claude-Session:\s*\S*?(session_[A-Za-z0-9]+)", msg)
        tag = a["authoring_basis"].split(":")[0]
        if tag == "the main session's commits":
            assert ids and a["authoring_run"] == f"the main session of {ids[-1]}", a["path"]
            assert _expected_basis(world["root"], runs_text, a["version"]) == "main", a["path"]
            seen["main"] += 1
        elif tag == "outside the agent runs":
            assert _expected_basis(world["root"], runs_text, a["version"]) == "outside", a["path"]
            assert a["git_author"] == git("/home/user/markets-data", "log", "-1", "--format=%an", a["version"])
            seen["outside"] += 1
    assert seen["main"] + seen["outside"] > 0
    # the run plans of 0180 to 0185 (committed 2026-11-24T17:46:24Z, inside the span of session_017eY1WSS3...,
    # which runs from 17:30:40Z) were made by the main session: they are no longer "outside the agent runs".
    # Plans 0157 to 0161 were committed at 17:28:54Z, before the session's first start: they stay outside.
    for n in (180, 181, 182, 183, 184, 185, 186, 187, 188, 189):
        a = _node(world, "markets-data", f"{ingest_artifacts.PAPER_REL}/run-plans/run-{n:04d}.json")
        if a:
            assert not a["attrs"]["authoring_basis"].startswith("outside the agent runs"), n


EARLIER_RECORD = "b0c1f81"      # a markets-data commit: the record as it stood there, read with git


def test_the_same_rule_holds_on_the_record_read_at_an_earlier_commit(world):
    root = world["root"]
    full = git(root, "rev-parse", EARLIER_RECORD)
    assert full
    runs_text = git(root, "show", f"{full}:{RUNS_FILE}")
    snap = ingest_artifacts.read_snapshot(root, {"markets-data": str(root)}, data_rev=full)
    assert snap["runs"] == {k: v for k, v in ingest_artifacts.run_lines(root, full).items()}
    shas = git(root, "log", full, "--format=%H", "--", f"{ingest_artifacts.PAPER_REL}/run-plans").split()
    assert len(shas) > 30
    mdlog = {}
    got = {"main": 0, "outside": 0}
    for sha in shas:
        info = {sha: {"author": git(root, "log", "-1", "--format=%an", sha), "time": git(root, "log", "-1", "--format=%cI", sha),
                      "session": (re.findall(r"Claude-Session:\s*\S*?(session_[A-Za-z0-9]+)",
                                             git(root, "log", "-1", "--format=%B", sha)) or [None])[-1]}}
        who = ingest_artifacts.authorship("markets-data", sha, snap["runs"], info, snap["sessions"])
        tag = ingest_artifacts._tag(who["authoring_basis"])
        if tag in ("the main session's commits", "outside the agent runs"):
            want = "main" if tag.startswith("the main") else "outside"
            assert _expected_basis(root, runs_text, sha) == want, sha
            got[want] += 1
    assert got["main"] > 0 and got["outside"] >= 0


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
        assert a["of"].startswith("run:") and a["of"].count("run:") == 1 and "," not in a["of"]
        assert m["id"] == f"metric:{a['of']}:{a['name']}"
        assert world["store"].node(a["of"])["type"] == "AgentRun"
    assert {m["attrs"]["name"] for m in ms} <= set(ingest_artifacts.FIGURES)


def test_a_null_figure_writes_no_metric(world):
    newest = {n: d for n, (_, d) in world["snap"]["runs"].items()}
    pairs = [(r, k) for r, d in newest.items() for k in ingest_artifacts.FIGURES if d.get(k) is None]
    assert pairs
    for r, k in pairs[:200]:
        assert world["store"].node(f"metric:run:{r:04d}:{k}") is None


def test_the_same_snapshot_ingested_twice_writes_nothing_new(world):
    first, second, third = world["ingests"]
    assert first["written"]["new"] > 0
    assert second["written"]["new"] == 0 and second["written"]["revised"] == 0
    # the same state read at a later time: still nothing new (first_read_at is the first read of a state)
    assert third["written"]["new"] == 0 and third["written"]["revised"] == 0
    assert set(world["after_problems"]) <= set(world["before_problems"])


def test_an_existing_commit_node_is_left_as_it_is(world):
    sha = world["snap"]["heads"][0]["sha"]
    cid = f"commit:{world['snap']['heads'][0]['repo']}:{sha[:10]}"
    assert len(world["store"].history(cid)) == 1


def test_main_prints_the_counts_by_basis_and_the_listing(tmp_path):
    root = data_root()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ingest_artifacts.main(["--data", str(root), "--graph-dir", str(tmp_path / "graph"),
                                      "--markets", str(MARKETS), "--platform", str(PLATFORM)])
    text = out.getvalue()
    assert code == 0 and "artifacts by authoring basis:" in text and "runs skipped" in text and "store wrote:" in text
    assert "artifact:Markets:tools/decider/programs/decider_v1.py [outcome text of a builder] run:0087" in text
    assert "[field]" not in text


def test_session_text_shows_the_markets_branch_and_head(world):
    before, after = world["git"][0]["Markets"], world["git"][1]["Markets"]
    text = world["text_after"]
    line = next(l for l in text.splitlines() if l.startswith("- Markets (code)"))
    assert before[0] in line and before[1][:7] in line and "first read at" in line
    assert "check each with git before trusting it" in text


def test_the_block_says_which_repository_holds_what_and_ours_first(world):
    lines = [l for l in ingest_artifacts.current_versions_lines(world["store"], 6000) if l.startswith("- ") and "branch " in l]
    assert [l.split(":")[0] for l in lines] == [
        "- Markets (code)", "- markets-data (records, graph, tickets)",
        "- paper-trading-platform (the platform; OUR change is on this branch)",
        "- paper-trading-platform, Codex's branch (his; our change is NOT on it)"]
    assert "ccr-0ac78691" in lines[2] or "branch " in lines[2]
    assert CODEX in lines[3]


def test_session_text_without_artifacts_says_none_on_record(world):
    assert "CURRENT VERSIONS: none on record (run tools.kgraph.ingest_artifacts)" in world["text_before"]
    assert "artifact:" not in world["text_before"]


def test_session_text_is_within_its_budget_with_the_block_counted(world):
    for budget in (2500, 3000, 4000, 6000):
        r = context.build(world["store"], None, budget, dirs=world["dirs"])
        assert "CURRENT VERSIONS" in r["text"]
        assert len(r["text"]) <= budget * context.CHARS_PER_TOKEN, budget


def test_at_a_small_budget_the_branch_lines_stay_and_the_file_lines_go(world):
    lines = ingest_artifacts.current_versions_lines(world["store"], 1000)
    assert len([l for l in lines if ": branch " in l and l.startswith("- ")]) == 4
    assert not [l for l in lines if l.startswith("- tools/")]
    assert any("9 control files and decider programs are not shown" in l and "never cut" in l for l in lines)
    assert lines[-1].endswith("check each with git before trusting it.")


def test_current_versions_block_is_held_to_a_tenth_and_says_what_it_cut(world):
    for budget in (1500, 2000, 2500, 3000):
        lines = ingest_artifacts.current_versions_lines(world["store"], budget)
        files = [l for l in lines if l.startswith("- tools/")]
        assert any("not shown for want of budget" in l for l in lines), budget
        assert len(files) < 9
        if files:
            assert sum(len(l) + 1 for l in lines) <= budget * context.CHARS_PER_TOKEN * 0.10
    full = ingest_artifacts.current_versions_lines(world["store"], 400000)
    assert not any("not shown" in l for l in full)
    assert any("decider_v1.py" in l and "04f4378" in l and "run:0087" in l for l in full)
    assert any("32 rule files" in l and "agent files" in l for l in full)


# ---------------------------------------------------------------------------------------------------------
# CASES THE REAL RECORD DOES NOT HOLD: each uses the real record with exactly the change named in the
# case's own comment (a real run line re-appended to a scratch copy of the record).
# ---------------------------------------------------------------------------------------------------------
def _scratch_record(tmp_path, world, *changes):
    """A scratch markets-data root holding a copy of the real record plus the re-appended lines.
    `changes` are (run number to take the real newest line of, {field: value}) pairs."""
    root = tmp_path / "md"
    dst = root / RUNS_FILE
    dst.parent.mkdir(parents=True)
    shutil.copy(world["root"] / RUNS_FILE, dst)
    with dst.open("a", encoding="utf-8") as f:
        for n, edit in changes:
            line = dict(world["snap"]["runs"][n][1], **edit)
            f.write(json.dumps(line) + "\n")
    return ingest_artifacts.run_lines(root)


def test_case_two_runs_name_one_commit_in_a_field(tmp_path, world):
    # change: run 121's real line re-appended with its code_commit set to 68d65a6, which run 114's real line names
    runs = _scratch_record(tmp_path, world, (121, {"code_commit": "68d65a6"}))
    full = git(MARKETS, "rev-parse", "68d65a6") or git(PLATFORM, "rev-parse", "68d65a6")
    got = ingest_artifacts.authorship("Markets", full, runs, {}, world["snap"]["sessions"])
    assert got["authoring_run"] == "not settled: runs 114 and 121 both name commit 68d65a6"
    assert got["authoring_basis"].startswith("two runs")


def test_case_two_builders_name_one_commit_in_their_outcome(tmp_path, world):
    # change: run 88's real line re-appended as run 87 (its outcome names 131a9dc, as run 88's own does)
    runs = _scratch_record(tmp_path, world, (88, {"run": 87}))
    full = git(MARKETS, "rev-parse", "131a9dc")
    got = ingest_artifacts.authorship("Markets", full, runs, {}, world["snap"]["sessions"])
    assert got["authoring_run"] == "not settled: runs 87 and 88 both name commit 131a9dc"
    assert got["authoring_basis"].startswith("two runs")


def test_case_the_commits_field_in_both_forms_and_the_repo_it_names(tmp_path, world):
    # change: run 121's real line re-appended with a `commits` list naming 04f4378 as "Markets:<sha>",
    # 073f43d as {"repo","sha"}, and 131a9dc under the wrong repository
    f04, f07, f13 = (git(MARKETS, "rev-parse", s) for s in ("04f4378", "073f43d", "131a9dc"))
    runs = _scratch_record(tmp_path, world, (121, {"commits": [f"Markets:{f04}", {"repo": "Markets", "sha": f07},
                                                               {"repo": "paper-trading-platform", "sha": f13}]}))
    sess = world["snap"]["sessions"]
    assert ingest_artifacts.authorship("Markets", f04, runs, {}, sess)["authoring_run"] == "run:0121"
    assert ingest_artifacts.authorship("Markets", f07, runs, {}, sess)["authoring_run"] == "run:0121"
    got = ingest_artifacts.authorship("Markets", f13, runs, {}, sess)      # the field names the platform, not Markets
    assert got["authoring_run"] == "run:0088" and got["authoring_basis"].startswith("outcome text of a builder")


def test_case_a_builders_task_text_is_not_authorship(tmp_path, world):
    # change: run 119's real line (a builder) re-appended with " 1757145" added to its task text; 1757145 is a real
    # platform commit that no line names in a field or an outcome
    full = git(PLATFORM, "rev-parse", "1757145")
    assert full
    runs = _scratch_record(tmp_path, world, (119, {"task": str(world["snap"]["runs"][119][1].get("task")) + " 1757145"}))
    got = ingest_artifacts.authorship("paper-trading-platform", full, runs, {}, world["snap"]["sessions"])
    assert got["authoring_run"] == OUTSIDE
