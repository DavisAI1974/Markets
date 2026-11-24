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


READS_OF_RUN_25 = ("run:0018", "run:0021", "run:0022", "run:0023", "run:0024")     # what was in the graph when the resolver read it
MERGES = "graph/merges/run-0025-merges.json"


def test_the_resolvers_real_merges_are_checked_held_under_the_cutoff_and_can_be_undone(tmp_path):
    """The resolver's own answer as it came back (run 25), on the reads it was made from. The counts are
    the ones written in the decisions file when it was applied: 11 at 0.9 or above, 22 held under."""
    root = data_root()
    if not (root / MERGES).exists():
        pytest.skip(f"{MERGES} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    for f in sorted((root / "graph/reads").glob("run-*.json")):
        run = "run:" + f.name.split("-")[1]
        if run in READS_OF_RUN_25:
            extract.load_result(store, dirs, json.loads(f.read_text(encoding="utf-8")), run)
    resolve.apply_rules(store, dirs)
    merges = json.loads((root / MERGES).read_text(encoding="utf-8"))["merges"]
    out = resolve.apply(store, merges, "run:0025", min_confidence=0.9)
    assert (out["applied"], out["under_the_cutoff"]) == (11, 22) and out["applied"] + out["under_the_cutoff"] + len(out["not_placed"]) == len(merges)
    held = [t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:merge-held:")]
    assert len(held) == len(merges) - 11 and all(h["returned"] in merges for h in held)       # each one kept as it came
    done = [e for e in store.edges("RESOLVED_TO") if e["attrs"]["method"] == "model"]
    assert len(done) == 11 and all(e["attrs"]["confidence"] >= 0.9 and e["attrs"]["evidence"] for e in done)
    one = done[0]
    assert resolve.canonical(store, one["src"]) == resolve.canonical(store, one["dst"])
    assert one["attrs"]["alias"] in resolve.aliases(store, one["dst"])
    # the same merge the other way round would close a ring; one with its evidence taken off is not applied
    real = next(m for m in merges if resolve._find(store, m["from"]) == one["src"])
    again = resolve.apply(store, [{**real, "from": real["to"], "to": real["from"]},
                                  {k: v for k, v in real.items() if k != "evidence"}], "run:0025")
    assert again["applied"] == 0 and len(again["not_placed"]) == 2
    # undone: the link is taken back by a new line, the earlier line stays, the name stands alone again
    resolve.undo(store, one["id"], "check of undo only", "run:0025")
    assert resolve.canonical(store, one["src"]) == one["src"]
    assert [h["attrs"].get("withdrawn", False) for h in store.history(one["id"])] == [False, True]
    assert store.node(one["src"]) is not None and store.check_all() == []
    with pytest.raises(schema.Refused):
        resolve.apply(store, merges[:1], "run:9999")


def test_the_resolvers_brief_lists_only_what_is_still_unmerged(graph):
    store, dirs = graph
    resolve.apply_rules(store, dirs)
    brief = resolve.candidates(store)
    merged = {e["src"] for e in store.edges("RESOLVED_TO")}
    listed = [l.split(" | ")[0] for l in brief.splitlines() if l.startswith("entity:")]
    surface = {n["id"] for n in store.nodes("Entity") if n["attrs"]["entity_kind"] == "named in a document"}
    assert set(listed) == surface - merged and len(listed) == len(set(listed))
    assert not any(l.startswith("scope:") or l.startswith("rulever:") for l in brief.splitlines())   # not names to merge
