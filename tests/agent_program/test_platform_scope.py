"""Greg, 2026-11-24: "Make sure any nee claims aren't tied to tasty platdorm issues". What the tastytrade
sandbox does and what its thin feed lacks are parked, so nothing new may rest on a claim about them.
Checked on the real reads of handoff X and the running list."""

import json
import re
import subprocess

import pytest

from tools.kgraph import context, extract, grounding, ingest_agent_runs, ingest_paper, platform_scope, schema
from tools.kgraph.sources import link
from tools.kgraph.store import GraphStore

from .realrecords import data_root

READS = {"run:0018": "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json",
         "run:0023": "graph/reads/run-0023-RUNNING_LIST.json"}
LIST = "tasty/RUNNING_LIST.md"


@pytest.fixture()
def graph(tmp_path):
    root = data_root()
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    if "paper-trading-platform" not in dirs:
        pytest.skip("no paper-trading-platform checkout beside Markets")
    for run, rel in READS.items():
        if not (root / rel).exists():
            pytest.skip(f"{rel} is not in this markets-data checkout")
        extract.load_result(store, dirs, json.loads((root / rel).read_text(encoding="utf-8")), run)
    return store, dirs


def _claim(store, words):
    return next(c for c in store.nodes("Claim") if words in c["attrs"]["quote"])


def test_a_claim_read_from_a_document_is_tied_as_it_is_loaded(graph):
    store, dirs = graph
    tied = platform_scope.members(store)
    assert tied                                             # the loader ties them: no separate step to forget
    # the feed's own fault (running list, section B): "A THIRD OF THE PRINTS HAVE NO SIDE (9 of 107, then 141 of 440)"
    assert _claim(store, "141 of 440")["id"] in tied
    # the sandbox account left short (handoff X line 96)
    assert _claim(store, "5WY79188 is short 13 lots")["id"] in tied
    # Greg's own decision to park them is his decision, not a platform issue
    parked = _claim(store, "sandbox-only issues are parked")
    assert parked["attrs"]["said_by"] == "Greg" and parked["id"] not in tied
    # a rule that has nothing to do with the platform
    assert _claim(store, "A trade day is 6 pm Eastern")["id"] not in tied
    # every tie says why, in words a person can check against the claim
    for e in store.edges("MEMBER_OF"):
        if e["dst"] == platform_scope.SCOPE_ID:
            assert e["attrs"]["why"] and e["attrs"]["rule"] in ("its own words", "the running list")
    assert platform_scope.mark(store, dirs)["new"] == 0       # marking twice ties nothing twice


def test_the_parked_lines_are_read_from_the_running_list_itself(graph):
    store, dirs = graph
    # the list as it stood at the commit the read was made from (the list is added to; a claim's line
    # numbers are that wording's)
    read_at = next(c["attrs"]["source_commit"] for c in store.nodes("Claim") if c["attrs"]["source"].endswith(LIST))
    text = subprocess.run(["git", "-C", str(dirs["paper-trading-platform"]), "show", f"{read_at}:{LIST}"],
                          capture_output=True, text=True, check=True).stdout
    # the list's own words (C22): "... dropped when the sandbox is left behind: C5 (...), C8 ..., C20 ..."
    assert platform_scope.parked_items(text) == {"C5", "C8", "C9", "C19", "C10", "C18", "C11", "C13", "C14", "C15", "C20"}
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines, 1) if l.startswith("14. ") and "STUCK SHORT 13 LOTS" in l)
    end = next(i for i, l in enumerate(lines, 1) if i > start and re.match(r"\d+\. ", l)) - 1
    tied = platform_scope.members(store)
    in_c14 = [c for c in store.nodes("Claim") if c["attrs"]["source"].endswith(LIST) and start <= c["attrs"]["line_start"] <= end]
    assert in_c14 and all(c["id"] in tied for c in in_c14)
    # a line that is "still ours, whatever the feed or the broker" (C2) is not tied by the list
    c2 = [c for c in store.nodes("Claim") if "worked out again from all the trades at every print" in c["attrs"]["quote"]]
    assert c2 and not any(e["attrs"]["rule"] == "the running list" for e in store.edges("MEMBER_OF")
                          if e["src"] == c2[0]["id"] and e["dst"] == platform_scope.SCOPE_ID)


def test_nothing_new_may_rest_on_a_tied_claim(graph):
    """The links tried here are relations the record itself states, not invented ones: CL16 was written
    for the print with no side (decisions file, 2026-11-24), and the list's own reading "if many are
    unmarked buys ..." rests on its count of prints with no side."""
    store, dirs = graph
    no_side = _claim(store, "141 of 440")                                  # the feed's fault, tied
    ingest_paper.paper(store, str(dirs["paper-trading-platform"]))
    cl16 = next(n for n in store.nodes("Entity") if n["attrs"].get("entity_kind") == "rule version" and n["attrs"]["strategy"] == "CL16")
    with pytest.raises(schema.Refused, match="tastytrade platform"):       # a rule version may not rest on it
        store.write([], [link("DERIVED_FROM", cl16["id"], no_side["id"])], written_by="code:test")
    reading = next(c for c in store.nodes("Claim") if c["attrs"]["inference"] and c["attrs"]["source"].endswith(LIST)
                   and 56 <= c["attrs"]["line_start"] <= 61)
    with pytest.raises(schema.Refused, match="tastytrade platform"):       # nor may a reading
        store.write([], [link("DERIVED_FROM", reading["id"], no_side["id"])], written_by="code:test")
    assert not [e for e in store.edges("DERIVED_FROM") if e["dst"] == no_side["id"]] and store.check_all() == []
    # a tie can be taken back by a person, with the reason kept; then the link is allowed
    platform_scope.untie(store, no_side["id"], reason="check of untie only", by="code:test")
    assert no_side["id"] not in platform_scope.members(store)
    store.write([], [link("DERIVED_FROM", cl16["id"], no_side["id"])], written_by="code:test")
    assert platform_scope.mark(store, dirs)["new"] == 0                    # a tie a person took back is not made again


def test_the_grounding_check_does_not_take_a_tied_claim_as_evidence(graph):
    store, dirs = graph
    r = grounding.check_text(store, "141 of 440 prints have no side.", dirs)
    assert r["decision"] == "revise" and "tastytrade platform" in r["reason"]
    assert any("does not come from the tastytrade" in e for e in r["required_evidence"])
    assert r["supporting_candidates"] and all(c["platform_issue"] for c in r["supporting_candidates"])   # shown, and said to be tied
    one = grounding.check_claim(store, _claim(store, "141 of 440")["id"], dirs)
    assert any("tastytrade platform" in o for o in one["what_was_observed"])
    # a sentence the list carries that is not about the platform is still found (list A2)
    ok = grounding.check_text(store, "CL14, CL17, CL05, CL06 and CL16 made 235 of the 327 trades.", dirs)
    assert ok["decision"] is None and any(not c["platform_issue"] for c in ok["supporting_candidates"])


def test_the_session_context_drops_nothing_it_marks_tied_claims_and_calls_the_parked_ones_last(graph):
    """Greg, 2026-11-24: nothing gets replaced; what does not work is scored so it is not called."""
    store, dirs = graph
    ties = platform_scope.ties(store)
    by_list = {c for c, t in ties.items() if t["rule"] == "the running list"}
    by_words = set(ties) - by_list
    assert by_list and by_words
    out = context.build(store, None, budget_tokens=400000, dirs=dirs)
    allc = {c["id"] for c in store.nodes("Claim")}
    assert set().union(out["included"], out["folded"], out["cut"], out["not_reached"]) == allc and out["cut"] == []
    assert by_list <= set(out["called_last"])
    text = out["text"].splitlines()
    for cid in list(by_list & set(out["included"]))[:10]:
        line = next(l for l in text if f"c:{cid.split(':', 1)[1]}" in l)
        assert "(parked: a tastytrade platform issue)" in line
    for cid in list(by_words & set(out["included"]))[:10]:
        line = next(l for l in text if f"c:{cid.split(':', 1)[1]}" in l)
        assert "(names the tastytrade platform: nothing new may rest on it)" in line
    assert "Sandbox-only issues are parked" in out["text"]                    # Greg's own decision is shown, unmarked
    # under a real budget the parked lines are the first to fall: none is shown while an unmarked claim of its kind is cut
    small = context.build(store, None, budget_tokens=6000, dirs=dirs)
    kind = lambda c: store.node(c)["attrs"]["statement_kind"]
    cut_plain = {kind(c) for c in small["cut"] if c not in small["called_last"]}
    assert not [c for c in small["included"] if c in by_list and kind(c) in cut_plain]
    assert f"{len(small['called_last'])} claims have something against them" in small["text"]
