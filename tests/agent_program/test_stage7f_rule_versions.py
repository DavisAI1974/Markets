"""Stage 7f: the loop and the grounding check on rule versions, using the paper record. Each edit of
the paper runner's rules is a trial of the experiment record (plan 7a), each paper run is tied to the
rule version it ran under, and a rule version with no finding under it is reported. Real commits and
the real run folders only; nothing is scored."""

import subprocess

import pytest

from tools.exp_dag import ExpDag
from tools.kgraph import extract, grounding, ingest_agent_runs, ingest_paper, rule_versions
from tools.kgraph.store import GraphStore
from tools.ratchet import program

from .realrecords import data_root


def _git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = data_root()
    dirs = extract.repo_dirs(root, None, None)
    if "paper-trading-platform" not in dirs:
        pytest.skip("no paper-trading-platform checkout beside Markets")
    tmp = tmp_path_factory.mktemp("g")
    store = GraphStore(root, graph_dir=tmp / "graph")
    dag = ExpDag(root, exp_dir=tmp / "experiments")
    plat = dirs["paper-trading-platform"]
    ingest_agent_runs.paper_runs(dag, store, str(plat))
    ingest_paper.paper(store, str(plat))
    report = rule_versions.load(dag, store, plat)
    return store, dag, plat, report


def test_each_edit_of_the_rules_is_a_trial_in_the_order_it_was_made(made):
    store, dag, plat, report = made
    commits = _git(plat, "log", "--reverse", "--format=%H", "--", *rule_versions.RULE_FILES).split()
    assert len(commits) >= 5 and report["rule_versions"] == commits
    trials = [t for t in dag.log() if (t.get("key") or "").startswith("rule-version:")]
    assert [t["change"]["commit"] for t in trials] == commits
    assert trials[0]["parent"] is None
    assert [t["parent"] for t in trials[1:]] == [t["id"] for t in trials[:-1]]          # each on the one before
    for t, c in zip(trials, commits):
        assert t["hypothesis"] == _git(plat, "log", "-1", "--format=%s", c) and t["status"] == "recorded"
        assert t["metrics"] == []                         # no figure: the feed is not scored
    assert store.node(f"commit:paper-trading-platform:{commits[-1][:10]}")["attrs"]["sha"] == commits[-1]


def test_each_paper_run_is_tied_to_the_rule_version_it_ran_under(made):
    store, dag, plat, report = made
    runs = [t for t in dag.log() if (t.get("key") or "").startswith("paper-run:") and t["change"]]
    assert len(runs) == 2
    by_commit = {t["change"]["commit"]: t for t in dag.log() if (t.get("key") or "").startswith("rule-version:")}
    for run in runs:
        in_force = _git(plat, "log", "-1", "--format=%H", run["change"]["commit"], "--", *rule_versions.RULE_FILES)
        assert run["id"] in by_commit[in_force]["links"]
        assert report["in_force"][run["change"]["commit"]] == in_force
        # in the graph: every rule version of that run points at the commit that last changed the rules
        mine = [e for e in store.nodes("Entity") if e["attrs"].get("entity_kind") == "rule version"
                and e["attrs"]["commit"] == run["change"]["commit"]]
        assert mine
        for rv in mine:
            ends = {e["dst"] for e in store.edges("DERIVED_FROM") if e["src"] == rv["id"]}
            assert f"commit:paper-trading-platform:{in_force[:10]}" in ends
    again = rule_versions.load(dag, store, plat)
    assert again["written"] == {"trials_new_or_revised": 0, "graph": {"new": 0, "revised": 0, "unchanged": again["written"]["graph"]["unchanged"]}}


def test_a_rule_version_rests_on_no_finding_yet_and_the_check_says_so(made):
    store, dag, plat, _ = made
    out = rule_versions.check(store, None, reviewer="code:test", run=None)
    rvs = [e for e in store.nodes("Entity") if e["attrs"].get("entity_kind") == "rule version"]
    assert out["checked"] == len(rvs) == 30 and out["need_evidence"] == 30
    evals = store.nodes("Evaluation")
    assert len(evals) == 30 and {e["dst"] for e in store.edges("EVALUATES")} == {r["id"] for r in rvs}
    one = evals[0]["attrs"]
    assert one["decision"] == "revise" and any("DERIVED_FROM" in x for x in one["required_evidence"])
    assert rule_versions.check(store, None, reviewer="code:test", run=None)["evaluations_written"] == 0   # one line a check
    assert store.check_all() == []


def test_the_rules_loop_has_its_control_file_guards_the_right_files_and_waits_for_no_figure(made):
    _, _, plat, _ = made
    p = program.load(rule_versions.LOOP_PROGRAM)
    assert p.metric_direction is None
    tracked = _git(plat, "ls-files").splitlines()
    rules = [f for f in tracked if any(program.glob_match(g, f) for g in p.mutable)]
    assert set(rules) >= set(_git(plat, "ls-files", *rule_versions.RULE_FILES).splitlines())
    # everything outside our folders (Codex's platform, the shared line code) is protected, never mutable
    others = [f for f in tracked if not f.startswith(("tasty/", "tests/tasty_runner/"))]
    assert others and all(any(program.glob_match(g, f) for g in p.protected) for f in others)
    assert not any(any(program.glob_match(g, f) for g in p.mutable) for f in others)
    assert all(any(program.glob_match(g, f) for g in p.protected) for f in ("tasty/paper/broker_tasty.py", "tasty/paper/runner.py"))
