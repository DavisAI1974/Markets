"""Stage 5b: Frankie's packet built from the graph (the opt-in path graph_v1, beside stacked_v1; not
switched on). Checked on the real dipole events of the four trade days. The check that matters most:
nothing that could only be known after the event's own moment is in its packet."""

import json
import re

import openpyxl
import pytest

from tools.kgraph import ingest_det as det
from tools.kgraph import packet
from tools.kgraph.store import GraphStore
from tools.ratchet import program

from .realrecords import data_root

DAY = "2023-10-02"


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    store = GraphStore(data_root(), graph_dir=tmp_path_factory.mktemp("g") / "graph")
    det.tradedays(store)
    det.dipoles(store)
    return store


@pytest.fixture(scope="module")
def sheet():
    """The day's dipole sheet read by the check's own route: [(dipole id, known ns, row dict)]."""
    wb = openpyxl.load_workbook(data_root() / det.WORKBOOK, read_only=True)
    it = wb[f"dipoles {DAY}"].iter_rows(values_only=True)
    header = next(it)
    rows = [dict(zip(header, r)) for r in it]
    return [(r["dipole"], int(r["native_known_second_ns"]), r) for r in rows]


def test_a_packet_holds_the_event_and_only_what_was_known_before_it(graph, sheet):
    name, known, row = sheet[100]
    out = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    earlier = {f"dipole:{n}" for n, k, _ in sheet if k < known}
    assert out["path"] == "graph_v1" and out["anchor"] == f"dipole:{name}" and out["known_ns"] == known
    assert set(out["included"]) == earlier | {f"dipole:{name}"} and out["cut"] == []
    assert out["rows"] == len(earlier) + 1
    assert packet.leakage_check(graph, out) == []
    later = [n for n, k, _ in sheet if k >= known and n != name]
    assert later and not any(n in out["text"] for n in later)             # no later event, by name
    # the event's own cells are the workbook's, for the columns that are known at its moment
    line = next(l for l in out["text"].splitlines() if l.startswith(f"dipole:{name} "))
    for col in ("native_birth_ns", "native_magnitude", "trades_in_birth_second", "our_flow_bought_20s_before"):
        assert f"{col}={row[col]}" in line


def test_what_could_only_be_known_afterwards_is_never_in_a_packet(graph, sheet):
    name, known, row = sheet[100]
    out = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    after = [c for c in row if c.endswith("_after") or c.startswith("seconds_to_") or c == "render"]
    assert sorted(after) == sorted(out["hidden_columns"]) and len(after) == 6
    body = out["text"].split("NOT IN THIS PACKET")[0]
    assert not any(c in body for c in after)
    shown = set(re.findall(r"(\w+)=", body))
    assert shown <= set(packet.KNOWN_AT_THE_MOMENT)                         # an allow-list: a new column is hidden until listed
    assert set(row) == set(packet.KNOWN_AT_THE_MOMENT) | set(after)         # every real column is placed on one side


def test_the_packet_does_not_change_when_the_future_is_taken_away(graph, sheet, tmp_path):
    """The leakage gate, as invariance: the packet of an event built from the whole trade day equals
    the packet built from a graph that holds nothing made known at or after the event's moment."""
    name, known, _ = sheet[100]
    whole = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    past = GraphStore(graph.data_root, graph_dir=tmp_path / "graph")
    keep = [n for n in graph.nodes("DipoleEvent")
            if n["attrs"]["trade_day"] == DAY and (int(n["attrs"]["pinned"]["native_known_second_ns"]) < known or n["id"] == f"dipole:{name}")]
    src = graph.node(keep[0]["attrs"]["source"])
    past.write([{k: n[k] for k in ("id", "type", "attrs")} for n in [src, *graph.nodes("TradeDay"), *keep]],
               written_by="code:test")
    assert len(past.nodes("DipoleEvent")) < len([n for n in graph.nodes("DipoleEvent") if n["attrs"]["trade_day"] == DAY])
    assert packet.build_packet(past, f"dipole:{name}", budget_tokens=200000)["text"] == whole["text"]


def test_a_budget_cuts_the_oldest_events_first_and_says_so(graph, sheet):
    name, known, _ = sheet[100]
    big = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    small = packet.build_packet(graph, f"dipole:{name}", budget_tokens=1500)
    assert small["tokens_estimated"] <= 1500 and small["rows"] < big["rows"]
    assert set(small["included"]) | set(small["cut"]) == set(big["included"])       # nothing lost: shown or on the cut list
    order = {f"dipole:{n}": k for n, k, _ in sheet}
    assert min(order[i] for i in small["included"]) > max(order[i] for i in small["cut"])   # the newest are kept
    assert f"{len(small['cut'])} earlier events are not shown" in small["text"]


def test_the_first_event_of_a_trade_day_has_nothing_before_it(graph, sheet):
    first = min(sheet, key=lambda x: x[1])
    out = packet.build_packet(graph, f"dipole:{first[0]}", budget_tokens=4000)
    assert out["rows"] == 1 and out["included"] == [f"dipole:{first[0]}"]


def test_no_saving_is_claimed_without_a_side_by_side(graph, sheet):
    out = packet.build_packet(graph, f"dipole:{sheet[100][0]}", budget_tokens=4000)
    c = packet.compare(out)
    assert c["stacked_v1"]["input_tokens"] == 92427 and c["stacked_v1"]["rows"] == 3262      # the one figure on record
    assert c["comparable"] is False and "same moment" in c["why_not"]
    assert not any(k in json.dumps(c).lower() for k in ("saving", "saved", "percent", "ratio", "smaller by"))


def test_the_packet_loop_has_its_control_file_and_waits_for_no_figure():
    p = program.load(packet.LOOP_PROGRAM)
    assert p.metric_direction is None                    # which figure the loop goes by is Greg's; none is assumed
    assert {f.name for f in p.figures} >= {"tokens_estimated", "rows"}
    assert "tools.kgraph.packet" in p.command
