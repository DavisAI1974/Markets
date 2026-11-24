"""Stage 4c: the grounding check. A claim is checked against the graph's links and against the file it
was read from; where a supporting path is missing the check says what evidence is needed. Checked on
the real reads kept in markets-data graph/reads/ and the real files. No verdict word is used."""

import json
import re

import pytest

from tools.kgraph import extract, grounding, ingest_agent_runs, ingest_paper, platform_scope, resolve, schema
from tools.kgraph.sources import link
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READ_X = ("run:0018", "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json")
READ_W = ("run:0021", "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json")
READ_LIST = ("run:0023", "graph/reads/run-0023-RUNNING_LIST.json")
READ_DECISIONS = ("run:0022", "graph/reads/run-0022-ROOT_GAMEPLAN_DECISIONS_L5853-L6152.json")


def _load(store, dirs, read):
    run, rel = read
    if not (store.data_root / rel).exists():
        pytest.skip(f"{rel} is not in this markets-data checkout")
    return extract.load_result(store, dirs, json.loads((store.data_root / rel).read_text(encoding="utf-8")), run)


@pytest.fixture()
def graph(tmp_path):
    root = data_root()
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    _load(store, dirs, READ_X)
    return store, dirs


def test_a_claim_read_from_a_file_has_its_path_and_its_words_still_stand(graph):
    store, dirs = graph
    claims = store.nodes("Claim")
    for c in claims:
        r = grounding.check_claim(store, c["id"], dirs)
        assert r["decision"] is None and r["required_evidence"] == []
        assert len(r["supporting_paths"]) == 1
        sup = store.history(r["supporting_paths"][0][0])[-1]
        assert sup["type"] == "SUPPORTS" and sup["dst"] == c["id"]
        assert any("stand" in o for o in r["what_was_observed"])
    assert not any(k in json.dumps(grounding.check_claim(store, claims[0]["id"], dirs)).lower()
                   for k in ("verdict", "pass", "fail", "refuted", "supported_within"))


def test_a_missing_path_says_what_evidence_is_needed(graph):
    store, dirs = graph
    c = next(n for n in store.nodes("Claim") if "32 strategies" in n["attrs"]["quote"])
    sup = next(e for e in store.edges("SUPPORTS") if e["dst"] == c["id"])
    store.withdraw_edge(sup["id"], reason="check of the grounding code only", written_by="code:test")
    r = grounding.check_claim(store, c["id"], dirs)
    assert r["decision"] == "revise" and r["claim"]["id"] == c["id"] and r["reason"]
    assert any("SUPPORTS" in e and "NEXT_SESSION_HANDOFF_20261124X.md" in e for e in r["required_evidence"])
    assert set(r) >= {"decision", "claim", "reason", "required_evidence"}        # the plan's own shape


def test_words_that_are_not_in_the_file_are_reported(graph):
    """What the check says when a claim's quoted words are not in its file (as after a rewording). Real
    words only: a claim really read from handoff W is set against handoff X, which does not hold them."""
    store, dirs = graph
    lines = (store.data_root / f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md").read_text(encoding="utf-8").splitlines()
    whole = " ".join(" ".join(lines).split())
    of_w = json.loads((store.data_root / READ_W[1]).read_text(encoding="utf-8"))["pieces"][0]["claims"]
    w = next(c for c in of_w if c["line_end"] <= len(lines) and " ".join(c["quote"].split()) not in whole)
    real = next(n for n in store.nodes("Claim") if "32 strategies" in n["attrs"]["quote"])
    elsewhere = {"id": "claim:check-words-not-in-this-file", "type": "Claim", "attrs": {
        **real["attrs"], "text": w["text"], "quote": w["quote"], "line_start": w["line_start"], "line_end": w["line_end"]}}
    store.write([elsewhere], [link("SUPPORTS", real["attrs"]["source"], elsewhere["id"])], written_by="code:test")
    r = grounding.check_claim(store, elsewhere["id"], dirs)
    assert r["decision"] == "revise" and "no longer" in r["reason"]
    assert any("current wording" in e for e in r["required_evidence"])


def test_a_reading_needs_something_it_rests_on(graph):
    store, dirs = graph
    _load(store, dirs, READ_W)
    readings = [n for n in store.nodes("Claim") if n["attrs"]["inference"]]
    assert readings                                         # handoff W marks several statements as Claude's readings
    c = readings[0]
    r = grounding.check_claim(store, c["id"], dirs)
    assert r["decision"] == "revise" and "reading" in r["reason"]
    assert any("DERIVED_FROM" in e for e in r["required_evidence"])
    # a link to something that does not hold a reading up (an AgentRun that read it) does not give it a path
    store.write([], [link("DERIVED_FROM", c["id"], "run:0018")], written_by="code:test")
    r_run = grounding.check_claim(store, c["id"], dirs)
    assert r_run["decision"] == "revise" and any("does not hold a reading up" in o for o in r_run["what_was_observed"])


def test_a_reading_rests_on_a_claim_it_really_rests_on(graph):
    """F12.1. The reading and the measurement it rests on are taken from the same entry of the same real read
    (the decisions file, lines 5923 to 5925: the measured ledger lines, then Claude's reading of what the
    changed line says). The running list's entry at lines 56 to 61 (unmarked buys) cannot be used: every claim of
    it is marked as a tastytrade platform issue and the store refuses a new link onto a marked claim."""
    store, dirs = graph
    _load(store, dirs, READ_DECISIONS)
    tied = platform_scope.members(store)
    at = lambda n: [c for c in store.nodes("Claim") if c["attrs"].get("source", "").endswith("ROOT_GAMEPLAN_DECISIONS.md")
                    and c["attrs"]["line_start"] == n and c["id"] not in tied]
    readings = [c for c in at(5925) if c["attrs"]["inference"]]
    basis = [c for n in (5923, 5924) for c in at(n) if not c["attrs"]["inference"] and c["attrs"]["statement_kind"] == "measurement"]
    if not readings or not basis:
        pytest.skip("no unmarked reading and measurement of one entry of the real reads")
    c, b = readings[0], basis[0]
    before = grounding.check_claim(store, c["id"], dirs)
    assert before["decision"] == "revise" and "reading" in before["reason"]
    store.write([], [link("DERIVED_FROM", c["id"], b["id"])], written_by="code:test")
    after = grounding.check_claim(store, c["id"], dirs)
    assert after["decision"] is None
    link_id = next(e["id"] for e in store.edges("DERIVED_FROM") if e["src"] == c["id"] and e["dst"] == b["id"])
    assert any(p[0] == link_id for p in after["supporting_paths"])         # the path runs through THAT claim
    # a claim that is marked as a tastytrade platform issue is refused by the store, and so is not taken as a basis
    marked = next((m for m in store.nodes("Claim") if m["id"] in tied), None)
    if marked:
        with pytest.raises(schema.Refused):
            store.write([], [link("DERIVED_FROM", c["id"], marked["id"])], written_by="code:test")


def test_a_claim_not_read_again_here_is_unread_and_a_moved_one_says_where(graph):
    """F8.3: the link is there but the words cannot be read again (no local checkout) -> "unread", not null;
    the same words at another line of their file -> null, with the new line given."""
    store, dirs = graph
    c = next(n for n in store.nodes("Claim") if "32 strategies" in n["attrs"]["quote"])
    r = grounding.check_claim(store, c["id"], {})
    assert r["decision"] == "unread" and r["required_evidence"] == [] and "could not be read again" in r["reason"]
    assert r["supporting_paths"]                                    # the link is there
    assert all(grounding.check_claim(store, n["id"], {})["decision"] == "unread" for n in store.nodes("Claim"))
    # moved: a real claim of handoff X set at the place of another real claim of the same file
    others = [n for n in store.nodes("Claim") if n["id"] != c["id"] and n["attrs"]["source"] == c["attrs"]["source"]
              and n["attrs"]["line_start"] != c["attrs"]["line_start"] and n["attrs"]["line_start"] == n["attrs"]["line_end"]]
    place = others[0]["attrs"]
    there = {"id": "claim:check-words-elsewhere-in-the-file", "type": "Claim", "attrs": {
        **c["attrs"], "line_start": place["line_start"], "line_end": place["line_end"]}}
    store.write([there], [link("SUPPORTS", c["attrs"]["source"], there["id"])], written_by="code:test")
    moved = grounding.check_claim(store, there["id"], dirs)
    assert moved["decision"] is None
    assert any(f"now at line {c['attrs']['line_start']}" in o for o in moved["what_was_observed"]), moved["what_was_observed"]


def test_a_sentence_is_looked_up_by_its_own_numbers_and_names(graph):
    store, dirs = graph
    # in handoff X: "The paper runner: 32 strategies, 26 checks passing, three run records, none scored."
    r = grounding.check_text(store, "The paper runner has 32 strategies and 26 checks passing.", dirs)
    assert r["decision"] == "read" and "reviewer must read" in r["reason"]
    top = store.node(r["supporting_candidates"][0]["claim"])["attrs"]
    assert "32 strategies, 26 checks passing" in top["quote"]
    assert r["supporting_candidates"][0]["where"].endswith("NEXT_SESSION_HANDOFF_20261124X.md:94")
    # a figure of the running list (its line A2) is not in the graph until the running list is read
    sentence = "CL14, CL17, CL05, CL06 and CL16 made 235 of the 327 trades."
    before = grounding.check_text(store, sentence, dirs)
    assert before["decision"] == "revise"
    assert any("235" in e for e in before["required_evidence"]) and any("327" in e for e in before["required_evidence"])
    _load(store, dirs, READ_LIST)
    after = grounding.check_text(store, sentence, dirs)
    assert after["decision"] == "read"
    assert any(c["where"].startswith("tasty/RUNNING_LIST.md:") and not c["platform_issue"] for c in after["supporting_candidates"])
    # two real figures that no one claim of this graph carries together are asked for, not waved through
    # (the decisions file: "CL14 opens 23 times on the 10-minute recording"; it is not read into this graph)
    more = grounding.check_text(store, "CL14, CL17, CL05, CL06 and CL16 made 235 of the 327 trades, and CL14 opens 23 times.", dirs)
    assert more["decision"] == "revise" and any("23" in e for e in more["required_evidence"])


def test_a_rule_version_with_no_finding_under_it_is_reported_and_the_check_is_kept(graph):
    store, dirs = graph
    if "paper-trading-platform" not in dirs:
        pytest.skip("no paper-trading-platform checkout beside Markets")
    ingest_paper.paper(store, str(dirs["paper-trading-platform"]))
    rv = next(n for n in store.nodes("Entity") if n["attrs"]["entity_kind"] == "rule version")
    r = grounding.check_node(store, rv["id"], dirs)
    assert r["decision"] == "revise"
    assert any("DERIVED_FROM" in e and "claim" in e.lower() for e in r["required_evidence"])
    ev = grounding.record(store, r, reviewer="code:test", run=None)
    node = store.node(ev)
    assert node["type"] == "Evaluation" and node["attrs"]["rubric"].startswith("grounding check")
    assert node["attrs"]["required_evidence"] == r["required_evidence"] and node["attrs"]["check_type"] == "deterministic"
    assert node["attrs"]["claim_revision"] == rv["rev"]
    assert [e["dst"] for e in store.edges("EVALUATES") if e["src"] == ev] == [rv["id"]]
    assert grounding.record(store, r, reviewer="code:test", run=None) == ev      # the same check is one line
    assert store.check_all() == []


def test_a_sentence_never_gets_null_and_words_are_whole_words(graph):
    """F8.1 / F8.4, on the real saved graph (read only): a sentence whose figure and half its words an unrelated
    claim carries is "read" (a reviewer reads whether it means it), never null; words are whole words."""
    store, dirs = graph
    saved = GraphStore(store.data_root)
    if not saved.nodes("Claim"):
        pytest.skip("no saved graph in this markets-data checkout")
    for sentence in ("The four trade days hold 741 losing trades of the paper runner.",
                     "Frankie's packet holds 3,262 rows and 92,427 tokens on the four trade days.",
                     "A third of the prints have no side."):
        r = grounding.check_text(saved, sentence, dirs)
        assert r["decision"] in ("read", "revise")
        if r["decision"] == "read":
            assert "reviewer must read" in r["reason"] and r["supporting_candidates"]
        for cand in r["supporting_candidates"]:
            body = (cand["text"] + " " + (cand["quote"] or "")).lower()
            tokens = {w.strip(".-/") for w in re.findall(r"[a-z][a-z0-9_/.\-]{3,}", body)}
            assert all(w in tokens for w in cand["words_carried"])        # whole words, never part of a longer one
    assert grounding._word_set("the holidays glossary") == {"holidays", "glossary"}


def test_a_sentence_carried_only_by_a_claim_with_a_later_one_over_it_is_revise(graph):
    """F8.4. A real claim with a real later claim set over it: its own words are carried by the later one too
    (usable, so "read"); and the superseded one is listed after it, marked."""
    store, dirs = graph
    old = next(c for c in store.nodes("Claim") if "markets-data has no `graph/` folder" in c["attrs"]["quote"])
    _load(store, dirs, ("run:0022", READ_DECISIONS[1]))
    new = next((c for c in store.nodes("Claim")
                if "stages 2 and 4a" in c["attrs"]["text"].lower() and "built" in c["attrs"]["text"].lower()
                and c["attrs"]["source"].endswith("ROOT_GAMEPLAN_DECISIONS.md")), None)
    if new is None:
        pytest.skip("the later claim is not in the real reads of this checkout")
    resolve.supersede(store, new["id"], old["id"], why="the layout was built later the same day", run="run:0018", dirs=dirs)
    r = grounding.check_text(store, old["attrs"]["text"], dirs)
    mine = [c for c in r["supporting_candidates"] if c["claim"] == old["id"]]
    assert mine and mine[0]["superseded"]
    if r["decision"] == "read":
        usable = [c for c in r["supporting_candidates"] if not c["superseded"] and not c["platform_issue"]]
        assert usable and r["supporting_candidates"].index(mine[0]) > r["supporting_candidates"].index(usable[0])
    else:
        assert r["decision"] == "revise" and any("later claim" in x or "no later claim" in x for x in r["required_evidence"] + [r["reason"]])


def test_a_swarm_claim_is_read_again_from_the_pinned_cells_of_its_node(graph, tmp_path):
    """F8.2, on the real swarm read: the quote 'column=value' is compared with the node's pinned cells in the
    graph, never with the workbook opened as text."""
    store, dirs = graph
    read = store.data_root / "graph/reads/swarm-worker-dip-19632-1696206142.json"
    if not read.exists():
        pytest.skip("the real swarm worker read is not in this markets-data checkout")
    try:
        from tools.swarm import reduce as R
    except Exception as e:                                           # the swarm loader is under change
        pytest.skip(f"tools.swarm.reduce does not load now: {e}")
    saved = GraphStore(store.data_root)
    event = "dipole:dip-19632-1696206142"
    day = saved.node(event)
    if day is None:
        pytest.skip("the saved graph holds no such dipole")
    d = day["attrs"]["trade_day"]
    sc = GraphStore(store.data_root, graph_dir=tmp_path / "swarm")
    nodes = [saved.node("tradeday:" + d)] + [n for n in saved.nodes("DipoleEvent") if n["attrs"]["trade_day"] == d] \
        + [n for n in saved.nodes("Peak") if n["attrs"]["trade_day"] == d] + [saved.node(day["attrs"]["source"])]
    sc.write([{"id": n["id"], "type": n["type"], "attrs": n["attrs"]} for n in nodes], [], written_by="code:test")
    ingest_agent_runs.agent_runs(sc)
    try:
        R.load_worker_result(sc, json.loads(read.read_text(encoding="utf-8")), "run:0018", cutoff=0.7)
    except Exception as e:
        pytest.skip(f"the swarm loader refuses the real read now: {e}")
    cells = [c for c in sc.nodes("Claim") if c["attrs"].get("cited_node")]
    assert cells
    for c in cells:
        r = grounding.check_claim(sc, c["id"], dirs)
        assert r["decision"] is None and any("pinned cells" in o for o in r["what_was_observed"])
    # set against another real node: the same quote against the pinned cells of a different dipole
    c = cells[0]
    same = lambda n: all(n["attrs"]["pinned"].get(x["column"]) == x["value"] for x in c["attrs"]["cited_cells"])
    other = next((n for n in sc.nodes("DipoleEvent") if n["id"] != c["attrs"]["cited_node"] and not same(n)), None)
    if other is None:
        pytest.skip("every other dipole of the trade day has the same cited cells")
    there = {"id": "claim:check-cells-of-another-node", "type": "Claim", "attrs": {**c["attrs"], "cited_node": other["id"]}}
    sc.write([there], [link("SUPPORTS", c["attrs"]["source"], there["id"])], written_by="code:test")
    r = grounding.check_claim(sc, there["id"], dirs)
    assert r["decision"] == "revise" and "pinned cells" in r["reason"]


def test_two_reviewers_checks_of_one_thing_are_two_nodes(graph):
    """F6.3 / F9.2: the reviewer and the method are in the id of an Evaluation, so neither revises the other."""
    store, dirs = graph
    c = next(n for n in store.nodes("Claim") if "32 strategies" in n["attrs"]["quote"])
    sup = next(e for e in store.edges("SUPPORTS") if e["dst"] == c["id"])
    store.withdraw_edge(sup["id"], reason="check of the grounding code only", written_by="code:test")
    r = grounding.check_claim(store, c["id"], dirs)
    one = grounding.record(store, r, reviewer="code:test-one", run=None)
    two = grounding.record(store, r, reviewer="code:test-two", run=None)
    assert one != two and store.node(one) and store.node(two)
    assert grounding.record(store, r, reviewer="code:test-one", run=None) == one
    assert {store.node(one)["attrs"]["reviewer"], store.node(two)["attrs"]["reviewer"]} == {"code:test-one", "code:test-two"}
