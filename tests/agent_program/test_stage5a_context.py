"""Stage 5a: a session starts from the graph, not from the pile of handoffs. The context builder is
checked on the real reads kept in markets-data graph/reads/. Nothing is dropped in silence: every
claim is either in the text, folded into a line that says the same words, superseded, or on the cut list."""

import json
import re

import pytest

from tools.kgraph import context, extract, grounding, ingest_agent_runs, resolve, schema
from tools.kgraph.sources import link
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READS = {
    "run:0018": "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json",
    "run:0021": "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json",
    "run:0022": "graph/reads/run-0022-ROOT_GAMEPLAN_DECISIONS_L5853-L6152.json",
}


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    root = data_root()
    store = GraphStore(root, graph_dir=tmp_path_factory.mktemp("g") / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    for run, rel in READS.items():
        if not (root / rel).exists():
            pytest.skip(f"{rel} is not in this markets-data checkout")
        extract.load_result(store, dirs, json.loads((root / rel).read_text(encoding="utf-8")), run)
    return store, dirs


def _cited(text):
    """The claim each line is: the id in the line's own bracket (a mark may name another claim)."""
    return set(re.findall(r"\[c:([0-9a-f]{12}) \|", text))


def _accounted(store, out):
    """Every claim of the graph is in exactly one place."""
    all_ids = {c["id"] for c in store.nodes("Claim")}
    placed = [set(out["included"]), set(out["folded"]), set(out["cut"]), set(out["not_reached"])]
    assert set().union(*placed) == all_ids
    assert sum(len(p) for p in placed) == len(all_ids)          # and in one place only


def test_a_session_start_fits_its_budget_and_accounts_for_every_claim(graph):
    store, dirs = graph
    out = context.build(store, None, budget_tokens=6000, dirs=dirs)
    assert out["tokens_estimated"] <= 6000 and out["tokens_estimated"] == context.estimate_tokens(out["text"])
    _accounted(store, out)
    assert out["not_reached"] == []                              # a session start looks at every claim
    assert _cited(out["text"]) == {i.split(":", 1)[1] for i in out["included"]}
    # each cited line can be followed back to its file and line
    for cid in list(out["included"])[:25]:
        a = store.node(cid)["attrs"]
        assert f"{a['source'].rsplit('/', 1)[-1]}:{a['line_start']}" in out["text"]
    # Greg's direction is there, as his, from the file it was said in
    line = next(l for l in out["text"].splitlines() if "everything for the agents" in l)
    assert "Greg" in line and re.search(r"NEXT_SESSION_HANDOFF_20261124X\.md:7|ROOT_GAMEPLAN_DECISIONS\.md:\d+", line)
    assert out["text"].index("WHAT GREG DECIDED") < out["text"].index("WHERE THINGS STAND")


def test_a_smaller_budget_cuts_more_and_says_what_it_cut(graph):
    store, dirs = graph
    big = context.build(store, None, budget_tokens=9000, dirs=dirs)
    small = context.build(store, None, budget_tokens=2500, dirs=dirs)
    assert small["tokens_estimated"] <= 2500 < big["tokens_estimated"] <= 9000
    assert len(small["included"]) < len(big["included"]) and len(small["cut"]) > len(big["cut"])
    _accounted(store, small)
    assert f"{len(small['cut'])} claims are not shown" in small["text"]          # the reader is told
    kinds = {}
    for cid in small["cut"]:
        k = store.node(cid)["attrs"]["statement_kind"]
        kinds[k] = kinds.get(k, 0) + 1
    assert small["cut_by_kind"] == kinds


def test_a_task_brings_the_claims_about_the_things_it_names(graph):
    store, dirs = graph
    out = context.build(store, "Build stage 5a, the context builder that starts a session from the graph.",
                        budget_tokens=4000, dirs=dirs)
    assert "entity:stage-5a" in out["entities"]
    text = out["text"]
    assert "convert the handoffs into graphs" in text or "converted into graphs" in text     # what Greg asked for
    # a claim about the sandbox account names none of the task's things: it is not reached at one hop
    sandbox = next(c["id"] for c in store.nodes("Claim") if "5WY79188 is short 13 lots" in c["attrs"]["quote"])
    assert sandbox in out["not_reached"] and sandbox not in out["included"]
    _accounted(store, out)
    for cid in out["included"]:                                   # everything shown was reached from the task
        assert cid in out["reached"]
    two = context.build(store, "Build stage 5a, the context builder that starts a session from the graph.",
                        budget_tokens=4000, hops=2, dirs=dirs)
    assert set(two["reached"]) > set(out["reached"])


def test_nothing_is_replaced_a_claim_with_a_later_one_over_it_is_marked_and_called_last(graph):
    """Greg, 2026-11-24: nothing gets replaced; what does not hold up is scored so it is not called. A
    claim with a later claim set over it stays in the text when the budget allows, marked, after every
    claim of its kind that has nothing against it; under a small budget it is the first to fall."""
    store, dirs = graph
    old = next(c for c in store.nodes("Claim") if "markets-data has no `graph/` folder" in c["attrs"]["quote"])
    new = next(c for c in store.nodes("Claim")
               if ("STAGES 2 AND 4a BUILT" in c["attrs"]["quote"] or "stages 2 and 4a" in c["attrs"]["text"].lower())
               and "built" in c["attrs"]["text"].lower() and c["attrs"]["source"].endswith("ROOT_GAMEPLAN_DECISIONS.md"))
    with pytest.raises(schema.Refused, match="says why"):
        resolve.supersede(store, new["id"], old["id"], why="", run="run:0018")
    with pytest.raises(schema.Refused, match="later"):                       # an earlier claim is not set over a later one
        resolve.supersede(store, old["id"], new["id"], why="the wrong way round", run="run:0018", dirs=dirs)
    edge = resolve.supersede(store, new["id"], old["id"], why="the layout was built later the same day", run="run:0018", dirs=dirs)
    big = context.build(store, None, budget_tokens=200000, dirs=dirs)
    assert old["id"] in big["included"] and old["id"] in big["called_last"]              # still there: nothing is dropped
    lines = big["text"].splitlines()
    mine = next(i for i, l in enumerate(lines) if f"c:{old['id'].split(':', 1)[1]}" in l)
    assert f"a later claim says otherwise: c:{new['id'].split(':', 1)[1]}" in lines[mine]
    # it comes after every claim of its own section that has nothing against it
    start = max(i for i in range(mine) if lines[i].startswith("## "))
    end = next((i for i in range(mine + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    after = [l for l in lines[mine + 1:end] if l.startswith("- ")]
    assert all("says otherwise" in l or "parked" in l for l in after)
    assert any(l.startswith("- ") and "says otherwise" not in l for l in lines[start:mine])
    _accounted(store, big)
    small = context.build(store, None, budget_tokens=3000, dirs=dirs)
    assert old["id"] in small["cut"] and old["id"] in small["called_last"]              # first to fall, and said so
    assert "1 claims have something against them" in small["text"]
    _accounted(store, small)
    # the grounding check of the earlier claim says a later one stands over it; the claim itself stays
    seen = grounding.check_claim(store, old["id"], dirs)
    assert any(new["id"] in o and "says otherwise" in o for o in seen["what_was_observed"])
    assert store.node(old["id"]) is not None
    store.withdraw_edge(edge, reason="check only", written_by="code:test")
    assert old["id"] not in context.build(store, None, budget_tokens=60000, dirs=dirs)["called_last"]


def test_the_same_words_said_in_two_files_make_one_line_that_cites_both(graph):
    store, dirs = graph
    words = "finish building everything for the agents"
    same = [c for c in store.nodes("Claim") if words in c["attrs"]["quote"]]
    assert len({c["attrs"]["source"] for c in same}) >= 2         # handoff X and the decisions file both quote him
    out = context.build(store, None, budget_tokens=60000, dirs=dirs)
    shown = [c["id"] for c in same if c["id"] in out["included"]]
    folded = [c["id"] for c in same if c["id"] in out["folded"]]
    assert len(shown) == 1 and len(folded) == len(same) - 1
    line = next(l for l in out["text"].splitlines() if f"c:{shown[0].split(':', 1)[1]}" in l)
    assert "also" in line and all(store.node(f)["attrs"]["source"].rsplit("/", 1)[-1] in line for f in folded)
