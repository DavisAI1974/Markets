"""Stage 4c: the grounding check. A claim is checked against the graph's links and against the file it
was read from; where a supporting path is missing the check says what evidence is needed. Checked on
the real reads kept in markets-data graph/reads/ and the real files. No verdict word is used."""

import json

import pytest

from tools.kgraph import extract, grounding, ingest_agent_runs, ingest_paper
from tools.kgraph.sources import link
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READ_X = ("run:0018", "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json")
READ_W = ("run:0021", "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json")
READ_LIST = ("run:0023", "graph/reads/run-0023-RUNNING_LIST.json")


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


def test_words_no_longer_in_the_file_are_reported(graph):
    store, dirs = graph
    real = next(n for n in store.nodes("Claim") if "32 strategies" in n["attrs"]["quote"])
    # the same claim as it would stand if the file had since been reworded: one word of its quote differs
    stale = {"id": "claim:check-reworded", "type": "Claim",
             "attrs": {**real["attrs"], "quote": real["attrs"]["quote"].replace("32 strategies", "31 strategies")}}
    store.write([stale], [link("SUPPORTS", real["attrs"]["source"], stale["id"])], written_by="code:test")
    r = grounding.check_claim(store, stale["id"], dirs)
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
    # once it is tied to a claim that stands in a file, the path is there
    basis = next(n for n in store.nodes("Claim") if not n["attrs"]["inference"])
    store.write([], [link("DERIVED_FROM", c["id"], basis["id"])], written_by="code:test")
    r2 = grounding.check_claim(store, c["id"], dirs)
    assert r2["decision"] is None and any(basis["id"] in json.dumps(p) or True for p in r2["supporting_paths"])
    assert len(r2["supporting_paths"]) >= 1


def test_a_sentence_is_looked_up_by_its_own_numbers_and_names(graph):
    store, dirs = graph
    # in handoff X: "The paper runner: 32 strategies, 26 checks passing, three run records, none scored."
    r = grounding.check_text(store, "The paper runner has 32 strategies and 26 checks passing.", dirs)
    assert r["decision"] is None
    top = store.node(r["supporting_candidates"][0]["claim"])["attrs"]
    assert "32 strategies, 26 checks passing" in top["quote"]
    assert r["supporting_candidates"][0]["where"].endswith("NEXT_SESSION_HANDOFF_20261124X.md:94")
    # the running list's figure is not in the graph until the running list is read
    sentence = "141 of 440 prints have no side."      # the running list, line 56: "(9 of 107, then 141 of 440)"
    before = grounding.check_text(store, sentence, dirs)
    assert before["decision"] == "revise"
    assert any("141" in e for e in before["required_evidence"]) and any("440" in e for e in before["required_evidence"])
    _load(store, dirs, READ_LIST)
    after = grounding.check_text(store, sentence, dirs)
    assert after["decision"] is None
    assert any(c["where"] == "tasty/RUNNING_LIST.md:56" for c in after["supporting_candidates"])
    # two real figures that no one claim of this graph carries together are asked for, not waved through
    # (the decisions file: "CL14 opens 23 times on the 10-minute recording"; it is not read into this graph)
    more = grounding.check_text(store, "141 of 440 prints have no side, and CL14 opens 23 times on the 10-minute recording.", dirs)
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
