"""Stage 2: the experiment record, checked on the real paper run folders."""

import json
import sqlite3

import pytest

from tools.exp_dag import ExpDag, Refused
from tools.kgraph import ingest_agent_runs
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root


@pytest.fixture()
def loaded(tmp_path):
    root = data_root()
    dag = ExpDag(root, exp_dir=tmp_path / "experiments")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ids = ingest_agent_runs.paper_runs(dag, store, None)
    return root, dag, ids


def test_one_trial_for_each_run_folder_and_each_figure_is_the_receipts(loaded):
    root, dag, ids = loaded
    folders = sorted(p for p in (root / PAPER / "live-runs").iterdir() if p.is_dir())
    assert len(ids) == len(folders) == len(dag.latest())
    for folder in folders:
        receipt = folder / "receipt.json"
        trial = [t for t in dag.latest().values() if t["key"] == f"paper-run:{folder.name}"]
        assert len(trial) == 1
        if receipt.exists():
            r = json.loads(receipt.read_text())
            fig = {m["name"]: m["value"] for m in trial[0]["metrics"]}
            assert fig["trades_in_ledger"] == r["trades_in_ledger"]
            assert fig["counts.engine.prints"] == r["counts"]["engine"]["prints"]
            assert trial[0]["change"]["commit"] == r["code_commit"]
            assert trial[0]["status"] == "recorded"   # not scored: no keep or revert was decided
        else:
            assert trial[0]["metrics"] == []          # no receipt, so no figure is claimed


def test_loading_twice_adds_nothing(loaded):
    root, dag, ids = loaded
    before = dag.record.read_bytes()
    again = ingest_agent_runs.paper_runs(dag, GraphStore(root, graph_dir=dag.dir.parent / "graph"), None)
    assert again == ids and dag.record.read_bytes() == before


def test_the_verbs(loaded):
    _, dag, ids = loaded
    first = ids[0]
    kids = dag.children(first)
    assert {k["id"] for k in kids} == set(ids[1:])
    assert {l["id"] for l in dag.leaves()} == set(ids[1:])
    assert [l["id"] for l in dag.lineage(ids[-1])] == [ids[-1], first]
    assert dag.fetch(first)[0]["rev"] == 1
    d = dag.diff(ids[0], ids[-1])
    assert any(m["name"] == "trades_in_ledger" and m["a"] != m["b"] for m in d["metrics"])


def test_a_reverted_and_a_crashed_trial_stay_in_the_record(loaded):
    _, dag, ids = loaded
    lines_before = len(dag.lines())
    dag.set_status(ids[1], "reverted", note="check of the record only: status put back below", written_by="code:test")
    dag.set_status(ids[1], "crash", note="check of the record only", written_by="code:test")
    hist = dag.fetch(ids[1])
    assert [h["status"] for h in hist] == ["recorded", "reverted", "crash"]
    assert len(dag.lines()) == lines_before + 2        # nothing was rewritten or removed
    out = dag.rebuild()
    db = sqlite3.connect(out)
    assert db.execute("select count(*) from trial").fetchone()[0] == len(dag.lines())
    assert db.execute("select status from trial where id=? and is_latest=1", (ids[1],)).fetchone()[0] == "crash"
    assert db.execute("select count(*) from metric").fetchone()[0] == sum(len(l["metrics"]) for l in dag.lines())


def test_what_is_refused(loaded):
    _, dag, ids = loaded
    with pytest.raises(Refused):
        dag.push(hypothesis="x", status="winner", written_by="code:test")          # no such status
    with pytest.raises(Refused):
        dag.push(hypothesis="x", status="kept", parent="exp-notthere", written_by="code:test")
    with pytest.raises(Refused):
        dag.push(hypothesis="", status="kept", written_by="code:test")
