"""Ticket 46, consolidation as a standing step of every read: the brief of candidate pairs for one read's
claims, the pairs applied one link each, the count of what has been through the step, the take-back of a
later-over-earlier link, and the date fault that must not return.

Every check works on a scratch copy of the REAL graph of the markets-data checkout (the nodes and links
only, copied to a scratch folder); nothing is written into markets-data and no claim is made up. The one
case the real graph does not hold sits apart at the foot of the file."""

import json
import shutil

import pytest

from tools.kgraph import consolidate, resolve, schema
from tools.kgraph.store import GraphStore

from .realrecords import data_root

# THE DATE FAULT (ticket 46, second box). Both claims sit in a folder named family-research-20261022/
# and carry no said_on, so the date comes from the FILE's own name.
NEW_1124 = "claim:eeeda142ddb2"      # NEXT_SESSION_HANDOFF_20261124X.md line 4: file date 2026-11-24, folder date 2022-10-22
OLD_1123 = "claim:69e43c1bcaf7"      # NEXT_SESSION_HANDOFF_20261123U.md line 3: file date 2026-11-23, same folder
FOLDER_DATE, FILE_DATES = "20261022", ("20261124", "20261123")
READ = "run:0022"                   # a real read of the graph (256 claims); 9 of the 32 hand-made links of run 96 rest on it
APPLIER = "run:0096"                # a real AgentRun of the graph


@pytest.fixture()
def scratch(tmp_path):
    root = data_root()
    g = tmp_path / "graph"
    shutil.copytree(root / "graph", g, ignore=shutil.ignore_patterns("reads", "reviews", "merges", "evaluations", "MANIFEST.json"))
    return root, g


def run_cmd(mod, root, g, *argv):
    return mod.main(["--data", str(root), "--graph-dir", str(g), *argv])


def test_undo_takes_back_a_later_over_earlier_link_and_it_stays_on_record_as_withdrawn(scratch, capsys):
    root, g = scratch
    before = {e["id"] for e in GraphStore(root, graph_dir=g).edges("SUPERSEDES")}
    run_cmd(resolve, root, g, "supersede", "--new", NEW_1124, "--old", OLD_1123, "--why", "check of the take-back", "--run", "code:test")
    eid = capsys.readouterr().out.strip().splitlines()[-1]
    store = GraphStore(root, graph_dir=g)
    assert eid.startswith("e:") and eid not in before and eid in {e["id"] for e in store.edges("SUPERSEDES")}
    run_cmd(resolve, root, g, "undo", "--edge", eid, "--reason", "the check takes it back", "--run", "run:0096")
    store = GraphStore(root, graph_dir=g)
    assert eid not in {e["id"] for e in store.edges("SUPERSEDES")}
    on_record = {e["id"]: e for e in store.edges("SUPERSEDES", withdrawn=True)}[eid]
    assert on_record["attrs"]["withdrawn"] is True and "the check takes it back" in on_record["attrs"]["withdrawn_reason"]
    assert "run:0096" in on_record["attrs"]["withdrawn_reason"]
    assert on_record["attrs"]["why"] == "check of the take-back" and on_record["attrs"]["made_by"] == "code:test"
    assert len(store.history(eid)) == 2                                       # the first line stays
    # any other kind of link is still refused
    mention = store.edges("MENTIONS")[0]["id"]
    with pytest.raises(schema.Refused):
        resolve.undo(store, mention, "no", "run:0096")


def test_the_date_fault_cannot_return_supersede_reads_the_files_date_not_the_folders(scratch, capsys):
    root, g = scratch
    store = GraphStore(root, graph_dir=g)
    for cid, fdate in ((NEW_1124, FILE_DATES[0]), (OLD_1123, FILE_DATES[1])):
        a = store.node(cid)["attrs"]
        assert not a.get("said_on")
        folder, name = a["source"].rsplit("/", 1)
        assert FOLDER_DATE in folder and fdate in name and FOLDER_DATE not in name
    assert resolve._when(store, store.node(NEW_1124), None)[0] == "2026-11-24"
    assert resolve._when(store, store.node(OLD_1123), None)[0] == "2026-11-23"
    # the true pair (2026-11-24 over 2026-11-23) is taken; read by the folder it would have been refused (2026-10-22)
    assert run_cmd(resolve, root, g, "supersede", "--new", NEW_1124, "--old", OLD_1123, "--why", "date check", "--run", "code:test") == 0
    # and the wrong way round is refused for its dates, so the dates really are compared
    with pytest.raises(schema.Refused, match="2026-11-23 against 2026-11-24"):
        resolve.supersede(store, OLD_1123, NEW_1124, "date check", "code:test")
