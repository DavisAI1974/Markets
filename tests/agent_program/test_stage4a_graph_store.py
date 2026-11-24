"""Stage 4a: the graph's layout and its four write rules, checked on the real agent-run record and
on real lines of the handoff."""

import json
import subprocess

import pytest

from tools.kgraph import extract, ingest_agent_runs, schema
from tools.kgraph.sources import link, source_node
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, WORK, data_root

HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"


@pytest.fixture()
def store(tmp_path):
    return GraphStore(data_root(), graph_dir=tmp_path / "graph")


READ = "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json"


def real_pair(store):
    """Two claims the reader really returned for handoff X, both on the same lines and both standing by the
    extract check as it is now: (source node, the first as a Claim node whole, the second's attrs). Nothing
    is written by the check: the first is the claim, the second is the real other wording of those lines."""
    read = store.data_root / READ
    if not read.exists():
        pytest.skip(f"{READ} is not in this markets-data checkout")
    src = source_node("markets-data", store.data_root, HANDOFF)
    lines = (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()
    cs = [c for p in json.loads(read.read_text(encoding="utf-8"))["pieces"] for c in p["claims"]
          if extract.check_claim(c, lines, 1, len(lines)) is None]
    by = {}
    for c in cs:
        by.setdefault((c["line_start"], c["line_end"]), []).append(c)
    pair = next((v for v in by.values() if len(v) > 1), None)
    if pair is None:
        pytest.skip("the real read of handoff X holds no two claims on the same lines")

    def attrs(c):
        return {"text": c["text"], "statement_kind": c["statement_kind"], "inference": c["inference"],
                "said_by": c["said_by"], "source": src["id"], "line_start": c["line_start"],
                "line_end": c["line_end"], "quote": c["quote"]}
    first, second = pair[0], pair[1]
    return src, {"id": extract.claim_id(src["id"], first["quote"]), "type": "Claim", "attrs": attrs(first)}, attrs(second)


def real_claim(store):
    """A claim taken whole from the real read of handoff X: its own text, quote and lines."""
    src, claim, _ = real_pair(store)
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
        r = next((c for c in json.loads(read_w.read_text(encoding="utf-8"))["pieces"][0]["claims"] if c["inference"]), None)
        if r is None:
            pytest.skip("the real read of handoff W holds no claim marked as an inference")
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
    _, _, other = real_pair(store)         # the real other wording of the same lines
    reworded = {**claim, "attrs": {**claim["attrs"], "text": other["text"]}}
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


# ---- the store's own safety (review tickets F6.1 to F6.4, F11.2) --------------------------------------
# Every case below is built from real lines (the real agent-run record, real Source lines); where the
# case is a failure part way, it is made by stopping the real writer, not by writing made-up lines.
import os

from tools.kgraph import sources, store as store_mod


def test_a_write_that_stops_part_way_leaves_a_pending_file_and_the_check_says_which_lines_are_missing(store, monkeypatch):
    calls = {"n": 0}
    real_fsync = os.fsync

    def stop_on_the_second_file(fd):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full (the check stops the writer here)")
        return real_fsync(fd)
    monkeypatch.setattr(store_mod.os, "fsync", stop_on_the_second_file)
    with pytest.raises(OSError):
        ingest_agent_runs.agent_runs(store)
    monkeypatch.undo()
    assert (store.dir / ".pending-write.json").exists()
    assert store.nodes("AgentRun") == []                                 # the writer's own tables are not advanced
    fresh = GraphStore(store.data_root, graph_dir=store.dir)
    out = fresh.check_all()
    assert any(b.startswith(".pending-write.json: left over from a write by") for b in out)
    missing = [b for b in out if "lines are missing from the file" in b and ": 0 of its" not in b]
    assert missing                                                       # the file the writer never reached lacks its lines
    assert any(b.startswith("MANIFEST.json") for b in out)               # the manifest was not written for them
    with pytest.raises(schema.Refused, match="left over from a write that did not finish"):
        fresh.write([source_node("markets-data", fresh.data_root, HANDOFF)], written_by="code:test@x")


def test_a_finished_write_leaves_no_pending_file_and_the_manifest_agrees(store):
    ingest_agent_runs.agent_runs(store)
    assert not (store.dir / ".pending-write.json").exists()
    assert store.check_all() == []


def test_a_line_cut_part_way_stops_a_plain_load_and_a_tolerant_load_reports_it(store):
    ingest_agent_runs.agent_runs(store)
    path = next(store.dir.glob("nodes/AgentRun.jsonl"))
    raw = path.read_bytes()
    path.write_bytes(raw[:-40])                                          # the last real line cut part way
    n = raw[:-40].count(b"\n") + 1
    with pytest.raises(ValueError, match=rf"AgentRun.jsonl:{n}: not a JSON line"):
        GraphStore(store.data_root, graph_dir=store.dir).nodes()
    tol = GraphStore(store.data_root, graph_dir=store.dir, tolerant=True)
    out = tol.check_all()                                                # the check can run
    assert any(f"AgentRun.jsonl:{n}: not a JSON line" in b for b in out)
    assert any("AgentRun.jsonl sha256 differs" in b for b in out)        # and the manifest no longer agrees with the file


def test_the_check_reports_each_difference_between_the_manifest_and_the_files(store):
    import json as _json
    ingest_agent_runs.agent_runs(store)
    mf = store.dir / "MANIFEST.json"
    m = _json.loads(mf.read_text(encoding="utf-8"))
    m["files"][0]["sha256"] = "0" * 64
    m["files"][0]["lines"] += 1
    mf.write_text(_json.dumps(m), encoding="utf-8")
    out = GraphStore(store.data_root, graph_dir=store.dir).check_all()
    assert any("sha256 differs" in b for b in out) and any("the manifest says" in b for b in out)


def test_two_lines_of_one_id_with_the_same_rev_stop_a_further_revision(store):
    """Two writers' union-merged lines: the same real line twice in the file. `write` will not add a
    further revision of that id; the check lists it; nothing is deleted."""
    src = source_node("markets-data", store.data_root, HANDOFF)
    store.write([src], written_by="code:test@x")
    path = store.dir / "nodes" / "Source.jsonl"
    line = path.read_text(encoding="utf-8")
    path.write_text(line + line, encoding="utf-8")
    again = GraphStore(store.data_root, graph_dir=store.dir)
    changed = {**src, "attrs": {**src["attrs"], "commit": "0" * 40}}
    with pytest.raises(schema.Refused, match="same rev"):
        again.write([changed], written_by="code:test@x")
    assert path.read_text(encoding="utf-8") == line + line               # nothing deleted, nothing added
    assert any("revisions are not 1..2" in b for b in again.check_all())


def test_the_real_graph_is_not_written_by_code_with_uncommitted_changes_but_a_scratch_graph_is(store):
    src = source_node("markets-data", store.data_root, HANDOFF)
    real = GraphStore(store.data_root)
    assert real.is_real_graph() and not store.is_real_graph()
    before = real.counts()
    with pytest.raises(schema.Refused, match="commit the code first"):
        real.write([src], written_by="code:tools.kgraph.extract@abc1234567+uncommitted")
    assert GraphStore(store.data_root).counts() == before
    store.write([src], written_by="code:tools.kgraph.extract@abc1234567+uncommitted")      # a scratch graph is not restricted
    assert store.node(src["id"]) is not None


def test_one_function_decides_a_sources_kind_from_its_path():
    from tools.kgraph import ingest_det
    for rel, _ in ingest_det.MANIFESTS:
        assert sources.kind_of(rel) == "manifest", rel
    assert sources.kind_of(ingest_det.WORKBOOK) == "workbook"
    assert sources.kind_of(HANDOFF) == "file"
    assert sources.kind_of("x/y.json", in_checkout=False) == "listed_file_not_in_checkout"
    assert "kind" not in sources.source_node.__code__.co_varnames[:sources.source_node.__code__.co_argcount + sources.source_node.__code__.co_kwonlyargcount]


def test_the_real_graph_loads_tolerantly_and_the_checks_run(store):
    real = GraphStore(store.data_root, tolerant=True)
    assert real.skipped_lines == [] or real.check_all()
    assert not any(b.startswith("MANIFEST.json") for b in real.check_all())
