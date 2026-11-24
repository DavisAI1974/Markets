"""Stage 4b, merging names that mean one thing: the exact rules and the resolver's merges, checked on
the names really lifted from handoff X. Every merge can be undone and none loses a line."""

import json
import subprocess

import pytest

from tools.kgraph import extract, ingest_agent_runs, resolve, schema
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READ = "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json"
RUN = "run:0018"


@pytest.fixture()
def graph(tmp_path):
    root = data_root()
    if not (root / READ).exists():
        pytest.skip(f"{READ} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    extract.load_result(store, dirs, json.loads((root / READ).read_text(encoding="utf-8")), RUN)
    return store, dirs


def test_the_exact_rules_merge_a_name_into_the_one_thing_it_names(graph):
    store, dirs = graph
    names = {n["attrs"]["name"]: n["id"] for n in store.nodes("Entity")}
    res = resolve.apply_rules(store, dirs)
    to = {e["src"]: e for e in store.edges("RESOLVED_TO")}
    # a file under its only basename: the decisions file (git itself says one tracked file has the name)
    tracked = subprocess.run(["git", "-C", str(store.data_root), "ls-files", "*ROOT_GAMEPLAN_DECISIONS.md"],
                             capture_output=True, text=True, check=True).stdout.split()
    assert len(tracked) == 1
    assert to[names["ROOT_GAMEPLAN_DECISIONS.md"]]["dst"] == f"src:markets-data:{tracked[0]}"
    # "handoff W" is the one handoff file that carries the letter
    assert to[names["handoff W"]]["dst"] == f"src:markets-data:{WORK}/NEXT_SESSION_HANDOFF_20261124W.md"
    # a commit id one checkout knows (handoff X names the Markets commit 65f71a9)
    full = subprocess.run(["git", "-C", str(dirs["Markets"]), "rev-parse", "65f71a9"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert to[names["65f71a9"]]["dst"] == f"commit:Markets:{full[:10]}"
    assert store.node(to[names["65f71a9"]]["dst"])["attrs"]["sha"] == full
    # a name many files carry is not guessed at, and a key file is never opened
    held = {u["name"]: u["why"] for u in res["matched_but_not_placed"]}
    assert "MANIFEST.json" in held and names["MANIFEST.json"] not in to
    assert "never opened" in held["tasty-sandbox.env"] and names["tasty-sandbox.env"] not in to
    assert not any(n["attrs"]["path"].endswith(".env") for n in store.nodes("Source"))
    for e in to.values():
        assert e["attrs"]["confidence"] == 1.0 and e["attrs"]["evidence"] and e["attrs"]["alias"]
    assert resolve.canonical(store, names["handoff W"]).endswith("NEXT_SESSION_HANDOFF_20261124W.md")
    assert "handoff W" in resolve.aliases(store, to[names["handoff W"]]["dst"])
    assert store.check_all() == []
    assert resolve.apply_rules(store, dirs)["merged"] == 0                 # nothing is merged twice


def test_a_resolvers_merge_is_checked_held_under_the_cutoff_and_can_be_undone(graph):
    store, dirs = graph
    names = {n["attrs"]["name"]: n["id"] for n in store.nodes("Entity")}
    merges = [
        # two surface forms handoff X really uses for one thing
        {"from": "handoffs", "to": "handoff", "evidence": "the plural of the same word in the same file", "confidence": 0.95},
        {"from": "aws-* agent files", "to": ".claude/agents/aws-*.md", "evidence": "line 61 calls the files of line 26 by this name", "confidence": 0.93},
        {"from": "plan", "to": "graph adoption plan", "evidence": "in handoff X 'the plan' is the graph adoption plan", "confidence": 0.7},
        {"from": "handoff", "to": "handoffs", "evidence": "would close a ring with the first", "confidence": 0.99},
        {"from": "no such name", "to": "handoff", "evidence": "x", "confidence": 0.99},
        {"from": "scout", "to": "builder", "evidence": "", "confidence": 0.99},
    ]
    out = resolve.apply(store, merges, RUN, min_confidence=0.9)
    assert out["applied"] == 2 and out["under_the_cutoff"] == 1 and len(out["not_placed"]) == 3
    assert resolve.canonical(store, names["handoffs"]) == names["handoff"]
    assert resolve.aliases(store, names[".claude/agents/aws-*.md"]) == ["aws-* agent files"]
    assert resolve.canonical(store, names["plan"]) == names["plan"]        # under the cutoff: not applied
    held = [t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:merge-held:")]
    assert len(held) == 4 and sorted(h["state"] for h in held) == ["blocked", "blocked", "blocked", "open"]
    assert {json.dumps(h["returned"], sort_keys=True) for h in held} == {json.dumps(m, sort_keys=True) for m in merges[2:]}
    # undone: the link is taken back by a new line, the earlier line stays, the name stands alone again
    edge = next(e for e in store.edges("RESOLVED_TO") if e["src"] == names["handoffs"])
    resolve.undo(store, edge["id"], "check of undo only", RUN)
    assert resolve.canonical(store, names["handoffs"]) == names["handoffs"]
    assert [h["attrs"].get("withdrawn", False) for h in store.history(edge["id"])] == [False, True]
    assert store.node(names["handoffs"]) is not None and store.check_all() == []
    with pytest.raises(schema.Refused):
        resolve.apply(store, merges[:1], "run:9999")


def test_the_resolvers_brief_lists_only_what_is_still_unmerged(graph):
    store, dirs = graph
    resolve.apply_rules(store, dirs)
    brief = resolve.candidates(store)
    merged = {e["src"] for e in store.edges("RESOLVED_TO")}
    listed = [l.split(" | ")[0] for l in brief.splitlines() if l.startswith("entity:")]
    assert set(listed) == {n["id"] for n in store.nodes("Entity")} - merged and len(listed) == len(set(listed))
