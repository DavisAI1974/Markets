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
    # the event's own cells are the workbook's, for the columns that are shown
    line = next(l for l in out["text"].splitlines() if l.startswith(f"dipole:{name} "))
    for col in ("native_birth_ns", "trades_in_birth_second", "our_flow_bought_20s_before", "our_flow_bought_20s_after"):
        assert f"{col}={row[col]}" in line
    assert "native_magnitude" not in line and "native_polarity" not in line


def test_every_real_column_is_in_exactly_one_group_and_only_the_shown_ones_are_shown(graph, sheet):
    name, known, row = sheet[100]
    out = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    groups = (set(packet.SHOWN), set(packet.HELD_BACK), set(packet.AFTERWARDS))
    assert set(row) == groups[0] | groups[1] | groups[2]                    # every real column is placed
    assert not (groups[0] & groups[1]) and not (groups[0] & groups[2]) and not (groups[1] & groups[2])
    assert out["unplaced_columns"] == []
    # held back until Greg says: Native's five values written on the closing line, and the column made from the polarity
    assert set(out["held_back_columns"]) == {"native_polarity", "native_magnitude", "native_threshold",
                                             "native_baseline", "native_prominence", "our_flow_on_native_side_after"}
    assert set(out["after_columns"]) == {"seconds_to_dipole_after", "render"}
    body, foot = out["text"].split("NOT IN THIS PACKET")
    assert not any(c in body for c in out["hidden_columns"])
    assert set(re.findall(r"(\w+)=", body)) <= set(packet.SHOWN)             # an allow-list
    assert "held back until Greg says which reading governs" in foot
    assert all(c in foot for c in out["hidden_columns"])                    # each hidden column is named, none silently


def test_the_birth_second_has_ended_before_an_event_is_made_known_on_all_four_trade_days(graph):
    """What the birth-second columns and the flow at the end of the birth second rest on: the birth second is
    over before the event's moment. Read from the birth time, a different column from the moment."""
    events = graph.nodes("DipoleEvent")
    assert {n["attrs"]["trade_day"] for n in events} == {"2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18"}
    gaps = [int(n["attrs"]["pinned"]["native_known_second_ns"]) - int(n["attrs"]["pinned"]["native_birth_ns"]) for n in events]
    assert len(gaps) == 3178 and min(gaps) >= packet.NS_PER_SECOND
    # the gap column: on these four trade days the dipole before by birth was always made known first, so the
    # guard that withholds the column has no real case to show; the count that says so is asserted here
    late = 0
    for day in {n["attrs"]["trade_day"] for n in events}:
        before = packet._before_by_birth([n for n in events if n["attrs"]["trade_day"] == day])
        late += sum(1 for n in events if n["attrs"]["trade_day"] == day
                    and not packet._gap_is_known(n, before, int(n["attrs"]["pinned"]["native_known_second_ns"])))
    assert late == 0


def test_the_packet_does_not_change_when_the_future_is_taken_away(graph, sheet, tmp_path):
    """The leakage gate, as invariance, with the future taken away by another route than the packet's own:
    the second graph has lost every event BORN at or after the anchor's moment (birth time, not the moment
    column the packet filters on) and every column that is not shown. Events born before the moment and made
    known after it are still in that graph; the packet must leave them out by itself."""
    name, known = next((n, k) for n, k, r in sheet[100:]
                       if any(int(r2["native_birth_ns"]) < k <= k2 and n2 != n for n2, k2, r2 in sheet))
    whole = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    past = GraphStore(graph.data_root, graph_dir=tmp_path / "graph")
    keep = [n for n in graph.nodes("DipoleEvent")
            if n["attrs"]["trade_day"] == DAY and int(n["attrs"]["pinned"]["native_birth_ns"]) < known]
    born_before_known_after = [n["id"] for n in keep
                               if int(n["attrs"]["pinned"]["native_known_second_ns"]) >= known and n["id"] != f"dipole:{name}"]
    assert born_before_known_after                       # a real case of the detection lag stays in the cut graph
    stripped = []
    for n in keep:
        attrs = dict(n["attrs"], pinned={c: v for c, v in n["attrs"]["pinned"].items() if c in packet.SHOWN})
        stripped.append({"id": n["id"], "type": n["type"], "attrs": attrs})
    src = graph.node(keep[0]["attrs"]["source"])
    past.write([{k: n[k] for k in ("id", "type", "attrs")} for n in [src, *graph.nodes("TradeDay")]] + stripped,
               written_by="code:test")
    assert len(past.nodes("DipoleEvent")) < len([n for n in graph.nodes("DipoleEvent") if n["attrs"]["trade_day"] == DAY])
    cut = packet.build_packet(past, f"dipole:{name}", budget_tokens=200000)
    body = lambda t: t.split("NOT IN THIS PACKET")[0]
    assert body(cut["text"]) == body(whole["text"])      # the same events and the same cells; the foot names columns the cut graph never held
    assert not any(i.split(":", 1)[1] in whole["text"] for i in born_before_known_after)


def test_the_check_catches_a_later_cell_put_under_a_shown_name(graph, sheet):
    """leakage_check reads the packet's text against the graph. Here the check itself changes one built
    packet's text, putting the event's real `seconds_to_dipole_after` cell under the shown name
    `seconds_since_dipole_before`; nothing of the record is changed."""
    name, known, row = next(x for x in sheet[100:] if x[2]["seconds_to_dipole_after"] != x[2]["seconds_since_dipole_before"])
    out = packet.build_packet(graph, f"dipole:{name}", budget_tokens=200000)
    real, later = f"seconds_since_dipole_before={row['seconds_since_dipole_before']}", f"seconds_since_dipole_before={row['seconds_to_dipole_after']}"
    line = next(l for l in out["text"].splitlines() if l.startswith(f"dipole:{name} "))
    assert real in line
    tampered = dict(out, text=out["text"].replace(line, line.replace(real, later), 1))
    found = packet.leakage_check(graph, tampered)
    assert len(found) == 1 and "is not that event's stored cell" in found[0] and f"dipole:{name}" in found[0]
    # a held-back column written onto a line is caught by its name
    extra = dict(out, text=out["text"].replace(line, line + f"; native_polarity={row['native_polarity']}", 1))
    assert any("native_polarity" in b for b in packet.leakage_check(graph, extra))


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
