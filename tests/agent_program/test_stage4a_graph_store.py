"""Stage 4a: the graph's layout and its four write rules, checked on the real agent-run record and
on real lines of the handoff."""

import json
import subprocess

import pytest

from tools.kgraph import ingest_agent_runs, schema
from tools.kgraph.sources import link, source_node
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, WORK, data_root

HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"


@pytest.fixture()
def store(tmp_path):
    return GraphStore(data_root(), graph_dir=tmp_path / "graph")


def real_claim(store):
    """A claim lifted from a real line of handoff X, with its real line number and wording."""
    src = source_node("markets-data", store.data_root, HANDOFF)
    lines = (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()
    n = next(i for i, l in enumerate(lines, 1) if "NO PAPER RUN until they are finished" in l)
    claim = {"id": "claim:check-handoff-x", "type": "Claim", "attrs": {
        "text": "No paper run is made until the steps of the agent program are finished.",
        "statement_kind": "decision", "inference": False, "said_by": "Greg",
        "source": src["id"], "line_start": n, "line_end": n, "quote": lines[n - 1].strip()}}
    return src, claim


def test_one_agent_run_node_for_each_line_of_the_record(store):
    result = ingest_agent_runs.agent_runs(store)
    with (store.data_root / PAPER / "agent-runs.jsonl").open() as f:
        real = [json.loads(x) for x in f if x.strip()]
    runs = store.nodes("AgentRun")
    assert len(runs) == len(real) and result["new"] == 2 * len(real) + 1
    by_run = {n["attrs"]["run"]: n["attrs"] for n in runs}
    for d in real:
        a = by_run[d["run"]]
        assert (a["model"], a["role"], a["tokens_reported"]) == (d["model"], d["role"], d["tokens_reported"])
        assert a["input_tokens"] is None and a["output_tokens"] is None    # never given, so never filled in
    assert store.check_all() == []
    again = ingest_agent_runs.agent_runs(store)
    assert again["new"] == 0 and again["revised"] == 0                     # a second load adds nothing


def test_a_record_that_grows_does_not_rewrite_the_runs_already_loaded(store):
    """One file, one id. The agent-run record is added to every session: when it changes, its own
    Source line is revised and the runs loaded from it stay as they are (checked with the two real
    commits that last changed the file)."""
    ingest_agent_runs.agent_runs(store)
    src = source_node("markets-data", store.data_root, f"{PAPER}/agent-runs.jsonl")
    log = subprocess.run(["git", "-C", str(store.data_root), "log", "-2", "--format=%H", "--", f"{PAPER}/agent-runs.jsonl"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert src["attrs"]["commit"] == log[0] and len(log) == 2 and "@" not in src["id"]
    earlier = {**src, "attrs": {**src["attrs"], "commit": log[1]}}          # the file's Source as of its earlier commit
    runs_before = {n["id"]: n["rev"] for n in store.nodes("AgentRun")}
    r = store.write([earlier], written_by="code:test")
    assert r == {"new": 0, "revised": 1, "unchanged": 0}
    assert {n["id"]: n["rev"] for n in store.nodes("AgentRun")} == runs_before
    assert [h["attrs"]["commit"] for h in store.history(src["id"])] == [log[0], log[1]]


def test_rule_1_a_claim_has_a_source_or_is_marked_an_inference(store):
    src, claim = real_claim(store)
    with pytest.raises(schema.Refused, match="SUPPORTS"):
        store.write([src, claim], written_by="code:test")                  # source named but not linked
    no_source = {**claim, "attrs": {k: v for k, v in claim["attrs"].items() if k != "source"}}
    with pytest.raises(schema.Refused, match="missing source"):
        store.write([no_source], written_by="code:test")
    assert store.nodes() == []                                             # a refused batch writes nothing
    store.write([src, claim], [link("SUPPORTS", src["id"], claim["id"])], written_by="code:test")
    # a statement its document marks as a reading (a real one, from the read of handoff W) needs no source line
    read_w = store.data_root / "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json"
    if read_w.exists():
        r = next(c for c in json.loads(read_w.read_text(encoding="utf-8"))["pieces"][0]["claims"] if c["inference"])
        store.write([{"id": "claim:check-inf", "type": "Claim", "attrs": {
            "text": r["text"], "statement_kind": r["statement_kind"], "inference": True}}], written_by="code:test")
    assert store.check_all() == []


def test_rules_2_and_3_and_who_wrote_it(store):
    with pytest.raises(schema.Refused, match="authoring_run"):
        store.write([{"id": "art:x", "type": "Artifact",
                      "attrs": {"repo": "DavisAI1974/Markets", "path": "tools/exp_dag.py", "version": "abc"}}],
                    written_by="code:test")
    with pytest.raises(schema.Refused, match="rubric"):
        store.write([{"id": "eval:x", "type": "Evaluation", "attrs": {
            "what_was_checked": "a", "what_was_observed": "b", "what_remains_open": "c"}}], written_by="code:test")
    src, claim = real_claim(store)
    with pytest.raises(schema.Refused, match="names who made it"):
        store.write([src], written_by="")


def test_rule_4_a_changed_or_withdrawn_line_keeps_the_earlier_one(store):
    src, claim = real_claim(store)
    sup = link("SUPPORTS", src["id"], claim["id"])
    store.write([src, claim], [sup], written_by="code:test")
    reworded = {**claim, "attrs": {**claim["attrs"], "text": "No paper run until every step is built."}}
    assert store.write([reworded], written_by="code:test")["revised"] == 1
    hist = store.history(claim["id"])
    assert [h["rev"] for h in hist] == [1, 2] and hist[0]["attrs"]["text"] != hist[1]["attrs"]["text"]
    fresh = GraphStore(store.data_root, graph_dir=store.dir)               # read back from the files
    assert fresh.node(claim["id"])["rev"] == 2 and len(fresh.history(claim["id"])) == 2
    fresh.withdraw_edge(sup["id"], reason="check of the store only", written_by="code:test")
    assert fresh.edges("SUPPORTS") == [] and len(fresh.edges("SUPPORTS", withdrawn=True)) == 1
    assert len(fresh.history(sup["id"])) == 2
    assert any("no SUPPORTS link" in b for b in fresh.check_all())         # the breach is reported, not hidden


def test_a_link_needs_both_ends_and_a_fill_never_carries_a_mid(store):
    src, _ = real_claim(store)
    with pytest.raises(schema.Refused, match="not a node"):
        store.write([src], [link("MENTIONS", src["id"], "entity:not-there")], written_by="code:test")
    with pytest.raises(schema.Refused, match="mid"):
        schema.check_node({"id": "fill:x", "type": "Fill",
                           "attrs": {"run": "r", "fill_ref": "f", "price": 3.547, "mid": 3.5475}})


def test_networkx_view(store):
    ingest_agent_runs.agent_runs(store)
    g = store.to_networkx()
    assert g.number_of_nodes() == len(store.nodes()) and g.number_of_edges() == len(store.edges())
