"""Stage 6, the swarm: what a worker reads, the reducer, the refute wave, the plan and the command line.

Real records only, no made-up request string, figure, model id or answer. The expected values are counted
here by another route than the code's: openpyxl on the saved workbook ROOT_dipoles_pinned.xlsx. No model is
called. The AgentRun is the real run:0029, loaded into the scratch graph by tools.kgraph.ingest_agent_runs
from the real agent-runs.jsonl. The reads are the real records, read ONLY from markets-data graph/reads/
(SWARM_READS_DIR points a developer's run at another folder; nothing sets it for the saved checks):
  swarm-worker-v2-dip-19632-1696206142.json   one worker reading the real brief of the real event, under
                                              the column=value contract (read by hand, not a run of the swarm)
  swarm-refute-v2-dip-19632-1696206142.json   one refuter reading the claims that answer sent to review
  swarm-worker-dip-19632-1696206142.json      the first worker read, written before the contract: the real
                                              record of the old contract, which the loader now refuses in part
A check never alters a real answer: refusals are checked by setting real things against each other (a real
answer against another real event's cells). Where no real record exists the check is skipped, with the reason.
Writes go to pytest tmp folders, never into markets-data.
"""

import io
import json
import os
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import openpyxl
import pytest

from tools.kgraph import ingest_agent_runs
from tools.kgraph.store import GraphStore, markets_data_root
from tools.swarm import layers as L
from tools.swarm import model as M
from tools.swarm import plan as P
from tools.swarm import reduce as R
from tools.swarm import refute as F
from tools.swarm import run as RUN

DAYS = ("2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18")
DAY = "2023-10-02"
XLSX = ("tasks/family-research-20261022/research-union-current/root-redesign-20261116/"
        "ROOT_dipoles_pinned.xlsx")
SRC = "src:markets-data:" + XLSX
EVENT = "dipole:dip-19632-1696206142"
WORKER_FILE = "swarm-worker-v2-dip-19632-1696206142.json"
REFUTE_FILE = "swarm-refute-v2-dip-19632-1696206142.json"
OLD_WORKER_FILE = "swarm-worker-dip-19632-1696206142.json"
RUN_ID = "run:0029"                 # a real line of the real agent-runs.jsonl (the builder run that wrote the loaders)


@pytest.fixture(scope="module")
def root():
    try:
        r = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    if not (r / XLSX).exists() or not (r / "graph" / "nodes" / "DipoleEvent.jsonl").exists():
        pytest.skip("this markets-data checkout has no saved workbook or no saved graph of the dipoles")
    return r


@pytest.fixture(scope="module")
def real(root):
    return GraphStore(root)                      # read only: nothing in this module writes to it


@pytest.fixture(scope="module")
def book(root):
    """The workbook as stored: {sheet: (header, rows)} for the dipole and peak sheets."""
    wb = openpyxl.load_workbook(root / XLSX, read_only=True)
    out = {}
    for name in wb.sheetnames:
        if name.startswith(("dipoles ", "peaks ")):
            rows = list(wb[name].iter_rows(values_only=True))
            out[name] = (rows[0], rows[1:])
    return out


def _read(root, name, committed_only=False):
    folder = None if committed_only else os.environ.get("SWARM_READS_DIR")
    folder = Path(folder) if folder else root / "graph" / "reads"
    p = folder / name
    if not p.exists():
        pytest.skip(f"{name} is not in {folder}: the real read is not there yet, and none is made up")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def worker_read(root):
    return _read(root, WORKER_FILE)


@pytest.fixture(scope="module")
def refute_read(root):
    return _read(root, REFUTE_FILE)


@pytest.fixture(scope="module")
def old_worker_read(root):
    return _read(root, OLD_WORKER_FILE, committed_only=True)


def _slim(n):
    return {"id": n["id"], "type": n["type"], "attrs": n["attrs"]}


def scratch(real, root, tmp_path, day="2023-10-02", name="g"):
    """A scratch graph (in a pytest tmp folder) holding the real nodes of one trade day (a copy of what the
    saved graph holds: the TradeDay, the workbook Source, every dipole and peak) and the real AgentRuns."""
    sc = GraphStore(root, graph_dir=tmp_path / name)
    nodes = [_slim(real.node("tradeday:" + day)), _slim(real.node(SRC))]
    nodes += [_slim(n) for n in real.nodes("DipoleEvent") if n["attrs"]["trade_day"] == day]
    nodes += [_slim(n) for n in real.nodes("Peak") if n["attrs"]["trade_day"] == day]
    sc.write(nodes, [], written_by="code:test_stage6_swarm")
    ingest_agent_runs.agent_runs(sc)               # the real agent-runs.jsonl, so run:0029 is the real node
    assert sc.node(RUN_ID)["type"] == "AgentRun"
    return sc


def _sheet_dipoles(book, day):
    h, rows = book[f"dipoles {day}"]
    return [dict(zip(h, r)) for r in rows]


def _sheet_peaks(book, day):
    h, rows = book[f"peaks {day}"]
    return [dict(zip(h, r)) for r in rows]


# ---- what a worker reads ---------------------------------------------------------------------------

def test_layers_of_the_second_dipole_of_2023_10_02(real, book):
    dips = _sheet_dipoles(book, "2023-10-02")
    peaks = _sheet_peaks(book, "2023-10-02")
    ly = L.event_layers(real, EVENT)
    me, before, after = dips[1], dips[0], dips[2]
    assert me["dipole"] == "dip-19632-1696206142"
    # the event's cells equal the workbook row's cells (every column, as stored)
    assert ly["event"]["attrs"]["pinned"] == me
    assert ly["event"]["attrs"]["row"] == 3 and ly["event"]["attrs"]["sheet"] == "dipoles 2023-10-02"
    # its neighbours are the first and the third rows of the sheet
    assert ly["before"]["attrs"]["pinned"] == before and ly["after"]["attrs"]["pinned"] == after
    # its peaks are exactly the peaks of the sheet between the neighbours' born_eastern, ends included
    lo, hi = before["born_eastern"], after["born_eastern"]
    expect = {p["peak_high_position"] for p in peaks if lo <= p["high_eastern"] <= hi}
    got = [p["attrs"]["position_on_tape"] for p in ly["peaks"]]
    assert len(expect) == 8 and set(got) == expect and len(got) == len(set(got))
    assert [p["attrs"]["pinned"]["high_eastern"] for p in ly["peaks"]] == sorted(
        p["attrs"]["pinned"]["high_eastern"] for p in ly["peaks"])
    # the cells: numbered 1..n in a fixed order, the event first, then before, after, then the peaks
    cl = L.cells(ly)
    assert [c["n"] for c in cl] == list(range(1, len(cl) + 1))
    assert {(c["column"], c["value"]) for c in cl if c["node"] == EVENT} == set(me.items())
    assert [c["node"] for c in cl if c["column"] == "dipole" and c["node"].startswith("dipole:")] == [
        EVENT, "dipole:" + before["dipole"], "dipole:" + after["dipole"]]
    assert L.cells(L.event_layers(real, EVENT)) == cl                    # the same every time
    assert len(cl) == 25 * 3 + 5 * 8
    # the brief carries one line for each cell, as `n| node | column = value`
    brief = L.build_brief(ly)
    for c in cl:
        assert f"{c['n']}| {c['node']} | {c['column']} = {json.dumps(c['value'], ensure_ascii=False)}\n" in brief + "\n"
    assert L.estimate_tokens("x" * 9) == 3 and L.estimate_tokens("x" * 8) == 2


def test_first_and_last_dipole_of_each_trade_day_and_no_peak_of_another_day(real, book):
    for day in DAYS:
        dips, peaks = _sheet_dipoles(book, day), _sheet_peaks(book, day)
        ids = L.event_ids(real, day)
        assert ids == ["dipole:" + d["dipole"] for d in dips]           # the sheet's order is birth order
        first = L.event_layers(real, ids[0])
        last = L.event_layers(real, ids[-1])
        assert first["before"] is None and last["after"] is None
        by_pos = {p["peak_high_position"]: p for p in peaks}
        t_first = min(p["high_eastern"] for p in peaks)
        t_last = max(p["high_eastern"] for p in peaks)
        # the span runs to the trade day's first peak and last peak
        assert min(p["attrs"]["pinned"]["high_eastern"] for p in first["peaks"]) == t_first
        assert max(p["attrs"]["pinned"]["high_eastern"] for p in last["peaks"]) == t_last
        hi = dips[1]["born_eastern"]
        assert {p["attrs"]["position_on_tape"] for p in first["peaks"]} == {
            p["peak_high_position"] for p in peaks if p["high_eastern"] <= hi}
        lo = dips[-2]["born_eastern"]
        assert {p["attrs"]["position_on_tape"] for p in last["peaks"]} == {
            p["peak_high_position"] for p in peaks if p["high_eastern"] >= lo}
        # no peak of another trade day, for every event of the day
        for ev in ids:
            ly = L.event_layers(real, ev)
            assert all(p["attrs"]["trade_day"] == day and p["id"].startswith(f"peak:{day}:") for p in ly["peaks"])
            assert ly["before"] is None or ly["before"]["attrs"]["trade_day"] == day
            assert ly["after"] is None or ly["after"]["attrs"]["trade_day"] == day
            assert all(p["attrs"]["position_on_tape"] in by_pos for p in ly["peaks"])
        # the whole day's dipoles are all there
        assert len(ids) == len(dips)


# ---- the plan and the command line ----------------------------------------------------------------

def _cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = RUN.main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_plan_for_each_trade_day_and_the_refusals(root, real, book, tmp_path):
    for day in DAYS:
        out = tmp_path / f"plan-{day}.json"
        rc, so, se = _cli(["--data-root", str(root), "plan", "--trade-day", day, "--cutoff", "0.7",
                           "--budget-tokens", "100000000", "--out", str(out)])
        assert rc == 0, se
        plan = json.loads(out.read_text(encoding="utf-8"))
        dips = _sheet_dipoles(book, day)
        assert plan["events"] == ["dipole:" + d["dipole"] for d in dips]       # one brief for each dipole of the sheet
        assert len(plan["estimate_per_event"]) == len(dips)
        assert plan["estimate_total_input_tokens"] == sum(e["estimated_input_tokens"] for e in plan["estimate_per_event"])
        assert plan["greg_go"] == "" and plan["cutoff"] == 0.7
        for k in P.BUDGET_KEYS:
            assert k in plan["budget"]
        assert "estimate" in plan["estimate_note"]                              # said to be an estimate
        # the estimate of one event is the brief's characters over four, rounded up
        e0 = plan["estimate_per_event"][0]
        assert e0["estimated_input_tokens"] == -(-e0["brief_chars"] // 4)
    # a budget under the estimate is refused, and the figure is named
    plan2 = json.loads((tmp_path / "plan-2023-10-02.json").read_text(encoding="utf-8"))
    total = plan2["estimate_total_input_tokens"]
    out = tmp_path / "small.json"
    rc, so, se = _cli(["--data-root", str(root), "plan", "--trade-day", "2023-10-02", "--cutoff", "0.7",
                       "--budget-tokens", str(total - 1), "--out", str(out)])
    assert rc == 2 and str(total) in se and str(total - 1) in se and not out.exists()
    # one named event of a trade day is a plan of one brief
    rc, so, se = _cli(["--data-root", str(root), "plan", "--trade-day", "2023-10-02", "--events", EVENT,
                       "--cutoff", "0.7", "--budget-tokens", "100000", "--out", str(tmp_path / "one.json")])
    assert rc == 0
    one = json.loads((tmp_path / "one.json").read_text(encoding="utf-8"))
    assert one["events"] == [EVENT] and one["estimate_total_input_tokens"] == one["estimate_per_event"][0]["estimated_input_tokens"]
    # an event of another trade day is refused
    rc, so, se = _cli(["--data-root", str(root), "plan", "--trade-day", "2023-10-03", "--events", EVENT,
                       "--cutoff", "0.7", "--budget-tokens", "100000", "--out", str(tmp_path / "bad.json")])
    assert rc == 2


def test_go_refuses_without_gregs_go_and_without_a_plan_that_passes(root, tmp_path):
    out = tmp_path / "p.json"
    rc, _, _ = _cli(["--data-root", str(root), "plan", "--trade-day", "2023-10-02", "--events", EVENT,
                     "--cutoff", "0.7", "--budget-tokens", "100000", "--out", str(out)])
    assert rc == 0
    # no --greg-go: refused before anything is built or called
    rc, so, se = _cli(["--data-root", str(root), "go", "--plan", str(out), "--caller", "files",
                       "--files-dir", str(tmp_path / "f")])
    assert rc == 2 and "Greg's go" in se
    rc, so, se = _cli(["--data-root", str(root), "go", "--plan", str(out), "--caller", "files",
                       "--greg-go", "   ", "--files-dir", str(tmp_path / "f")])
    assert rc == 2 and "Greg's go" in se
    assert not (tmp_path / "f").exists()
    # his words given, but the plan is over its own budget: refused, the figure named
    j = json.loads(out.read_text(encoding="utf-8"))
    j["budget"]["max_tokens"] = j["estimate_total_input_tokens"] - 1
    out.write_text(json.dumps(j), encoding="utf-8")
    rc, so, se = _cli(["--data-root", str(root), "go", "--plan", str(out), "--caller", "files",
                       "--greg-go", "go", "--files-dir", str(tmp_path / "f")])
    assert rc == 2 and str(j["estimate_total_input_tokens"]) in se and not (tmp_path / "f").exists()
    # the plan check also names the other figures
    base = P.RunPlan.load(out)
    base.budget["max_tokens"] = base.estimate_total_input_tokens
    base.budget["max_model_calls"] = 0
    with pytest.raises(P.PlanRefused, match="max_model_calls of 0"):
        P.check(base)


def _real_plan(root, tmp_path):
    out = tmp_path / "real-plan.json"
    rc, so, se = _cli(["--data-root", str(root), "plan", "--trade-day", DAY, "--events", EVENT,
                       "--cutoff", "0.7", "--budget-tokens", "100000", "--out", str(out)])
    assert rc == 0, se
    return json.loads(out.read_text(encoding="utf-8"))


def test_what_is_sent_to_the_model(real, root, tmp_path):
    """The real worker brief of the real event, the real model ids of model.py, the efforts and the output
    ceilings of a real plan."""
    plan = _real_plan(root, tmp_path)
    ws, wu = L.build_brief_parts(L.event_layers(real, EVENT))
    mt, ef = plan["max_output_tokens"]["worker"], plan["efforts"]["worker"]
    kw = M.request_kwargs(M.WORKER_MODEL, ws, wu, mt, ef, L.ANSWER_SCHEMA)
    assert kw["model"] == M.WORKER_MODEL and kw["system"] == ws and kw["max_tokens"] == mt
    assert "betas" not in kw and "fallbacks" not in kw and kw["output_config"]["effort"] == ef
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": L.ANSWER_SCHEMA}
    assert kw["messages"] == [{"role": "user", "content": wu}]                    # no prefill
    for model in M.MODELS:
        kw = M.request_kwargs(model, ws, wu, mt, plan["efforts"]["refute"])
        assert kw["model"] == model and kw["messages"] == [{"role": "user", "content": wu}]
        for k in ("temperature", "top_p", "thinking", "tool_choice"):
            assert k not in kw
        if model != M.WORKER_MODEL:
            assert kw["betas"] == [M.FALLBACK_BETA] and kw["fallbacks"] == "default"
    # the model that run:0029 is recorded with is the alias "sonnet", not an exact id: refused
    alias = real.node(RUN_ID)["attrs"]["model"]
    assert alias not in M.MODELS
    with pytest.raises(ValueError):
        M.request_kwargs(alias, ws, wu, mt, ef)
    with pytest.raises(ValueError):
        M.request_kwargs(M.WORKER_MODEL, ws, wu, mt, M.REFUTE_MODEL)           # a model id is not an effort
    import inspect
    assert not [n for n in dir(M) if "fake" in n.lower() or "mock" in n.lower()]      # no caller makes up an answer
    assert {"AnthropicCaller", "FileCaller"} <= {n for n, o in vars(M).items() if inspect.isclass(o)}


def test_file_caller_hands_back_what_a_session_agent_put_there(real, root, worker_read, tmp_path):
    plan = _real_plan(root, tmp_path)
    ws, wu = L.build_brief_parts(L.event_layers(real, EVENT))
    mt, ef = plan["max_output_tokens"]["worker"], plan["efforts"]["worker"]
    fc = M.FileCaller(tmp_path / "f", poll_s=0.01, timeout_s=0.3)
    cid = M.FileCaller.call_id(M.WORKER_MODEL, ws, wu)
    assert cid != M.FileCaller.call_id(M.REFUTE_MODEL, ws, wu)                  # the model is part of the id
    with pytest.raises(M.ModelCallFailed):                    # nothing there: it waits, then says so
        fc.call(M.WORKER_MODEL, ws, wu, mt, ef)
    brief = (tmp_path / "f" / f"{cid}.brief.txt").read_text(encoding="utf-8")
    assert ws in brief and wu in brief and M.WORKER_MODEL in brief
    (tmp_path / "f" / f"{cid}.result.json").write_text(json.dumps(worker_read), encoding="utf-8")
    r = fc.call(M.WORKER_MODEL, ws, wu, mt, ef)
    assert json.loads(r["text"]) == worker_read and r["stop_reason"] == "end_turn"
    assert set(r["usage"]) == set(M.USAGE_KEYS) and r["usage"]["input_tokens"] is None     # a session agent reports none


# ---- the reducer, on the real read -----------------------------------------------------------------

def _cell_values_from_sheet(book, node):
    """The cited cells of a claim's node, read from the workbook by another route than the graph."""
    sheet, row = node["attrs"]["sheet"], node["attrs"]["row"]
    h, rows = book[sheet]
    return dict(zip(h, rows[row - 2]))


def test_every_returned_claim_is_written_or_kept_as_thrown_out(real, root, book, worker_read, tmp_path):
    sc = scratch(real, root, tmp_path)
    returned = worker_read["claims"]
    assert 6 <= len(returned) <= 12 and any(c["inference"] for c in returned) and any(c["confidence"] < 0.7 for c in returned)
    rep = R.load_worker_result(sc, worker_read, RUN_ID, cutoff=0.7)
    claims = sc.nodes("Claim")
    tasks = [t for t in sc.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert rep["returned"] == len(returned) and rep["claims_written"] + rep["thrown_out"] == len(returned)
    assert len(claims) == rep["claims_written"] and len(tasks) == rep["thrown_out"]
    assert rep["thrown_out"] == 0                              # the real answer was written by hand against the rules
    # a non-inference claim's quote is its cited cells as stored (read here from the workbook)
    plain = [c for c in claims if not c["attrs"]["inference"]]
    assert plain
    for c in plain:
        a = c["attrs"]
        node = sc.node(a["cited_node"])
        sheet_vals = _cell_values_from_sheet(book, node)
        quote = "; ".join(f"{x['column']}={json.dumps(sheet_vals[x['column']], ensure_ascii=False)}" for x in a["cited_cells"])
        assert a["quote"] == quote
        assert a["sheet"] == node["attrs"]["sheet"] and a["line_start"] == a["line_end"] == node["attrs"]["row"]
        assert a["source"] == SRC and a["extracted_by"] == RUN_ID and a["about"] == EVENT
        # which wording of the workbook it was read from
        assert a["source_commit"] == sc.node(SRC)["attrs"]["commit"] and a["source_commit"]
        assert a["cited_node_rev"] == node["rev"] == 1
        # one node only: the cited cells all belong to one sheet row
        assert len({x["n"] for x in a["cited_cells"]}) == len(a["cited_cells"])
    # inferences have no source of their own, and rest on claims of the answer
    infer = [c for c in claims if c["attrs"]["inference"]]
    assert infer and all("source" not in c["attrs"] for c in infer)
    assert all(c["attrs"]["source_commit"] == sc.node(SRC)["attrs"]["commit"] and c["attrs"]["cited_node_rev"] is None
               for c in infer)
    derived = [e for e in sc.edges("DERIVED_FROM") if e["src"].startswith("claim:")]   # the runs' own links are not claims'
    assert {e["src"] for e in derived} == {c["id"] for c in infer}
    assert all(sc.node(e["dst"])["type"] == "Claim" for e in derived)
    # links: SUPPORTS from the workbook for each plain claim, MENTIONS the event, PRODUCED from the run
    sup = sc.edges("SUPPORTS")
    assert {e["dst"] for e in sup} == {c["id"] for c in plain} and all(e["src"] == SRC for e in sup)
    assert {e["dst"] for e in sc.edges("MENTIONS")} == {EVENT} and len(sc.edges("MENTIONS")) == len(claims)
    assert {e["dst"] for e in sc.edges("PRODUCED") if e["src"] == RUN_ID} == {c["id"] for c in claims}
    assert sc.check_all() == []
    # the same answer loaded again is the same lines (nothing doubled)
    again = R.load_worker_result(sc, worker_read, RUN_ID, cutoff=0.7)
    assert again["claims_written"] == rep["claims_written"] and len(sc.nodes("Claim")) == len(claims)


def test_the_cutoff_splits_sent_to_review_and_held_with_none_lost(real, root, worker_read, tmp_path):
    sc = scratch(real, root, tmp_path)
    for cutoff in (0.7, 0.5, 0.99, 1.0):
        d = tmp_path / f"c{cutoff}"
        s2 = scratch(real, root, d)
        rep = R.load_worker_result(s2, worker_read, RUN_ID, cutoff=cutoff)
        sent = R.review_set(s2, [EVENT], cutoff)
        mine_sent = {c["id"] for c in s2.nodes("Claim") if c["attrs"]["review"] == "sent to review"}
        mine_held = {c["id"] for c in s2.nodes("Claim") if c["attrs"]["review"] == f"held under the cutoff {cutoff}"}
        assert set(sent) == mine_sent and mine_sent.isdisjoint(mine_held)
        assert len(mine_sent) + len(mine_held) == rep["claims_written"] == len(worker_read["claims"])
        assert rep["sent_to_review"] == len(mine_sent) and rep["held_under_the_cutoff"] == len(mine_held)
        expect_sent = [c for c in worker_read["claims"] if c["confidence"] >= cutoff]
        assert len(mine_sent) == len(expect_sent)
        # a held claim stays in the graph, with its confidence
        for c in s2.nodes("Claim"):
            if c["id"] in mine_held:
                assert c["attrs"]["confidence"] < cutoff
    # at 0.7 the one claim the worker was less sure of is held, and it is still a Claim of the graph
    s7 = scratch(real, root, tmp_path / "c7")
    R.load_worker_result(s7, worker_read, RUN_ID, cutoff=0.7)
    held = [c for c in s7.nodes("Claim") if c["attrs"]["review"].startswith("held")]
    assert len(held) == sum(1 for c in worker_read["claims"] if c["confidence"] < 0.7) >= 1


def test_a_real_answer_set_against_another_real_events_cells_is_thrown_out_whole(real, root, worker_read, tmp_path):
    """Two real things set against each other, neither altered: the real answer for EVENT (only its `event`
    field names the other event) against the cells of the last dipole of the same trade day. Its claims cite
    cells whose values are not its figures, so every claim is kept as thrown out with a reason, none written."""
    other = L.event_ids(real, DAY)[-1]
    assert other != EVENT
    sc = scratch(real, root, tmp_path)
    ctx = R.event_context(sc, other)
    # the per-claim check, directly: each claim of the answer, a pair or a cell that is not the other event's
    for c in worker_read["claims"]:
        why, prep = R.prepare_claim(ctx, c, {})
        assert why and prep is None, c["k"]
    rep = R.load_worker_result(sc, {**worker_read, "event": other}, RUN_ID, cutoff=0.7)
    n = len(worker_read["claims"])
    assert rep["returned"] == n and rep["thrown_out"] == n and rep["claims_written"] == 0
    assert all(t["reason"] for t in rep["thrown"]) and not sc.nodes("Claim")
    # nothing returned is lost: each thrown claim is a Task line holding the claim as it came, with its reason
    tasks = [t for t in sc.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert len(tasks) == n
    assert sorted(json.dumps(t["attrs"]["returned"], sort_keys=True) for t in tasks) == \
        sorted(json.dumps(c, sort_keys=True) for c in worker_read["claims"])
    assert all(t["attrs"]["reason"] and t["attrs"]["about"] == other for t in tasks)
    # a run that is not an AgentRun of the graph is refused
    with pytest.raises(Exception, match="AgentRun"):
        R.load_worker_result(scratch(real, root, tmp_path, name="g6"), worker_read, "run:nothing")


def test_the_first_real_read_of_the_old_contract_is_refused_where_it_holds_a_bare_number(real, root, old_worker_read, tmp_path):
    """The saved worker read of the first run was written before the column=value contract. It is the real
    record of the old contract; the loader now throws out the claims that hold a number outside a pair."""
    sc = scratch(real, root, tmp_path)
    returned = old_worker_read["claims"]
    rep = R.load_worker_result(sc, old_worker_read, RUN_ID, cutoff=0.7)
    assert rep["returned"] == len(returned) and rep["claims_written"] + rep["thrown_out"] == len(returned)
    assert rep["thrown_out"] >= 1
    for t in rep["thrown"]:
        assert t["reason"]
    outside = [t for t in rep["thrown"] if "outside a column=value pair" in t["reason"]]
    assert outside, "no claim of the old read was refused for a number outside a pair"
    # a claim of the old read that holds no figure at all is still taken
    written_ks = {c["k"] for c in rep["claims"]}
    for c in returned:
        if c["k"] in written_ks:
            assert not re.search(r"\d", re.sub(r"[\w:]*dipole[\w:\-]*|[a-z]+_[a-z0-9_]+", "", c["text"]))
    tasks = [t for t in sc.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert len(tasks) == rep["thrown_out"] and len(sc.nodes("Claim")) == rep["claims_written"]


def test_the_refused_words_and_the_number_words_are_in_the_lists_greg_decided(root):
    """The lists as decided (2026-11-24), checked as code constants, not on a made-up sentence."""
    banned = ("total sum sums mean average averaged median most least largest smallest highest lowest biggest best "
              "worst better worse good bad strong stronger strongest weak weaker weakest winner loser win loss rank "
              "ranked top bottom mid midpoint middle net profit fee fees cost costs correct incorrect right wrong "
              "accurate inaccurate agrees pass fail refuted confirmed proven proves").split()
    for w in banned:
        assert R.banned_word(w) == w and R.banned_word(w.upper()) == w.upper(), w
    for w in "first last before after earlier later".split():       # order in time stays allowed
        assert R.banned_word(w) is None, w
    numwords = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred "
                "thousand million half double twice thrice dozen none").split()
    for w in numwords:
        assert R.number_word(w) == w and R.number_word(w.title()) == w.title(), w
    # a name that holds a word is not the word
    assert R.number_word("our_flow_fully_one_sided_after") is None
    assert R.banned_word("bought_minus_sold_at_high") is None
    # "1,000" is one number with its separator, never split
    assert R.parse_text("1,000", [])["strays"] == ["1,000"]
    assert R.value_matches("1,000", 1000) and not R.value_matches("1,000", 1)


def test_a_label_in_a_real_answer_is_thrown_out(worker_read):
    pytest.skip("no real worker answer on record carries a label or a statistic, so the refusal of one has no real "
                "record to be checked on; no sentence is made up for it")


# ---- the refute wave, on the real read -------------------------------------------------------------

def _loaded(real, root, worker_read, tmp_path, name="g"):
    sc = scratch(real, root, tmp_path, name=name)
    R.load_worker_result(sc, worker_read, RUN_ID, cutoff=0.7)
    return sc


def test_refute_brief_has_each_claim_with_its_events_numbered_cells(real, root, worker_read, tmp_path):
    sc = _loaded(real, root, worker_read, tmp_path)
    ids = R.review_set(sc, [EVENT], 0.7)
    brief = F.build_refute_brief(sc, ids)
    for cid in ids:
        assert f"claim {cid} |" in brief
    held = [c["id"] for c in sc.nodes("Claim") if c["attrs"]["review"].startswith("held")]
    assert all(h not in brief for h in held)
    for c in L.cells(L.event_layers(real, EVENT)):
        assert f"{c['n']}| {c['node']} | {c['column']} = " in brief
    with pytest.raises(Exception):
        F.build_refute_brief(sc, ["claim:nothing"])


def test_refute_loader_one_evaluation_for_each_check(real, root, worker_read, refute_read, tmp_path):
    sc = _loaded(real, root, worker_read, tmp_path)
    ids = set(R.review_set(sc, [EVENT], 0.7))
    checks = refute_read["checks"]
    assert {c["claim"] for c in checks} == ids                      # the refuter looked at each claim sent to review
    rep = F.load_refute_result(sc, refute_read, RUN_ID, R.review_set(sc, [EVENT], 0.7))
    evs = sc.nodes("Evaluation")
    assert rep["returned"] == len(checks) and rep["evaluations_written"] + rep["thrown_out"] == len(checks)
    assert rep["thrown_out"] == 0 and len(evs) == len(checks)
    ev_edges = sc.edges("EVALUATES")
    assert len(ev_edges) == len(checks) and {e["dst"] for e in ev_edges} == ids
    assert {e["src"] for e in ev_edges} == {e["id"] for e in evs}
    # a CONTRADICTS link only where the returned check says contradicted and its cells verify
    expect = [c for c in checks if c["contradicted"]]
    assert len(sc.edges("CONTRADICTS")) == len(expect)
    for e in evs:
        a = e["attrs"]
        assert a["rubric"] == F.RUBRIC and a["check_type"] == "model-assisted" and a["reviewer"] == RUN_ID
        assert a["method"] == "tools.swarm.refute" and a["claim_revision"] == 1
        assert a["what_was_checked"] and a["what_was_observed"] and a["what_remains_open"]
        assert a["cells"] and all("column" in c for c in a["cells"])
    assert sc.check_all() == []
    # the claims stay as they were
    assert len([c for c in sc.nodes("Claim")]) == len(worker_read["claims"])


def test_a_contradiction_is_a_claim_of_its_own_with_a_contradicts_link(real, root, worker_read, refute_read, tmp_path):
    """Checked only on a real refute answer that says contradicted. The one on record contradicts nothing,
    and none is made up: until a real one exists this path has no check."""
    real_ones = [c for c in refute_read["checks"] if c.get("contradicted")]
    if not real_ones:
        pytest.skip("the one real refute answer on record contradicts nothing, so the CONTRADICTS path has no real "
                    "record to be checked on; no answer is made up for it")
    sc = _loaded(real, root, worker_read, tmp_path)
    rep = F.load_refute_result(sc, refute_read, RUN_ID, R.review_set(sc, [EVENT], 0.7))
    cx = sc.edges("CONTRADICTS")
    assert len(cx) == rep["counter_statements_written"] <= len(real_ones)
    for e in cx:
        assert sc.node(e["src"])["type"] == "Claim" and sc.node(e["dst"]) is not None      # both claims stay
    assert sc.check_all() == []


def test_a_check_for_a_claim_not_in_the_brief_is_kept_as_a_task_and_the_others_go_on(real, root, worker_read, refute_read, tmp_path):
    """Real things set against each other: the real refute answer, loaded with a brief that holds all its claims
    but one. The check of the claim that was not in the brief is kept with its reason; the rest are written."""
    sc = _loaded(real, root, worker_read, tmp_path)
    ids = R.review_set(sc, [EVENT], 0.7)
    left_out = ids[0]
    rep = F.load_refute_result(sc, refute_read, RUN_ID, [i for i in ids if i != left_out])
    assert rep["thrown_out"] == 1 and rep["evaluations_written"] == len(refute_read["checks"]) - 1
    assert "not in the brief" in rep["thrown"][0]
    assert not [e for e in sc.edges("EVALUATES") if e["dst"] == left_out]
    task = [t for t in sc.nodes("Task") if t["attrs"]["state"] == "blocked" and t["attrs"]["returned"]["claim"] == left_out]
    assert len(task) == 1 and "not in the brief" in task[0]["attrs"]["reason"]
    assert sc.node(left_out)["type"] == "Claim"                       # the claim stays


def test_one_check_that_raises_does_not_stop_the_others(real, root, worker_read, refute_read, tmp_path, monkeypatch):
    """The real refute answer, loaded while the event's cells fail to load for the first check only."""
    sc = _loaded(real, root, worker_read, tmp_path)
    ids = R.review_set(sc, [EVENT], 0.7)
    orig, calls = R.event_context, []

    def flaky(store, event_id):
        calls.append(event_id)
        if len(calls) == 1:
            raise RuntimeError("the cells of this event could not be read")
        return orig(store, event_id)
    monkeypatch.setattr(R, "event_context", flaky)
    rep = F.load_refute_result(sc, refute_read, RUN_ID, ids)
    assert rep["thrown_out"] == 1 and rep["evaluations_written"] == len(refute_read["checks"]) - 1
    assert "RuntimeError" in rep["thrown"][0] and "could not be read" in rep["thrown"][0]


def test_a_check_for_a_document_claim_is_kept_as_a_task():
    pytest.skip("no real refute answer names a document claim (a claim without `about`), so the refusal has no real "
                "record to be checked on; no check is made up for it")


def test_synthesis_names_only_that_events_claims(real, root, worker_read, refute_read, tmp_path):
    sc = _loaded(real, root, worker_read, tmp_path)
    F.load_refute_result(sc, refute_read, RUN_ID, R.review_set(sc, [EVENT], 0.7))
    other = "dipole:dip-19632-1696206187"
    text = R.synthesis(sc, [EVENT, other])
    blocks = text.split("== ")
    assert len(blocks) == 3 and blocks[1].startswith(EVENT) and blocks[2].startswith(other)
    mine = {c["id"]: c for c in sc.nodes("Claim") if c["attrs"]["about"] == EVENT}
    sent = set(R.review_set(sc, [EVENT], 0.7))
    listed = re.findall(r"^claim (claim:[0-9a-f]+) \|", blocks[1], re.M)
    assert set(listed) == sent and len(listed) == len(sent)
    for cid in sent:
        links = [e["id"] for e in sc.edges("SUPPORTS") if e["dst"] == cid] + \
                [e["id"] for e in sc.edges("DERIVED_FROM") if e["src"] == cid]
        evs = [e["src"] for e in sc.edges("EVALUATES") if e["dst"] == cid]
        assert links and evs
        i = blocks[1].index(f"claim {cid} |")
        line2 = blocks[1][i:].splitlines()[1]
        assert all(l in line2 for l in links) and all(e in line2 for e in evs)
    held = [c for c in mine if c not in sent]
    assert held and all(h in blocks[1] for h in held)              # named as held, not as sent
    assert not re.search(r"^claim ", blocks[2], re.M)              # the other event has no claim: nothing is borrowed
    # no figure over several events or claims: no total, count or mean is written
    for word in ("total", "average", "mean ", "median", "rate", "% "):
        assert word not in text.lower()


def test_no_verdict_word_and_no_pooled_figure_on_any_node_or_link(real, root, worker_read, refute_read, tmp_path):
    sc = _loaded(real, root, worker_read, tmp_path)
    F.load_refute_result(sc, refute_read, RUN_ID, R.review_set(sc, [EVENT], 0.7))
    assert sc.check_all() == []
    verdict = re.compile(r"\b(pass|passed|fail|failed|refuted|confirmed|verdict|winner|loser|strong|weak|best|worst)\b", re.I)
    pooled = re.compile(r"\b(average|averaged|mean|median|total|pooled|rank|ranked|rate)\b", re.I)
    for n in sc.nodes("Claim") + sc.nodes("Evaluation"):
        a = {k: v for k, v in n["attrs"].items() if k != "returned"}      # `returned` is the refuter's object as it came
        assert not {"verdict", "decision", "status", "grade", "score"} & set(a)
        blob = json.dumps(a, ensure_ascii=False)
        assert not verdict.search(blob), (n["id"], verdict.search(blob).group(0))
        assert not pooled.search(blob), (n["id"], pooled.search(blob).group(0))
    for e in sc.edges():
        assert not verdict.search(json.dumps(e["attrs"])) and not pooled.search(json.dumps(e["attrs"]))


# ---- the run, with answers put in files by hand (no model is called) ---------------------------------

def test_a_run_over_files_holds_its_budget_and_records_each_call(real, root, worker_read, refute_read, tmp_path):
    """The `go` machinery with the FileCaller and the two real reads put where it waits. No model is called,
    no API key is read. This is the only check that runs the fan-out code; the command `go` itself is
    exercised only for its refusals."""
    sc = scratch(real, root, tmp_path, name="run")
    # what the run will ask: the worker's brief, and (from the claims the worker's answer writes) the refuter's
    probe = _loaded(real, root, worker_read, tmp_path, name="probe")
    ids = R.review_set(probe, [EVENT], 0.7)
    ws, wu = L.build_brief_parts(L.event_layers(sc, EVENT))
    rs, ru = F.build_refute_brief_parts(probe, ids)
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / (M.FileCaller.call_id(M.WORKER_MODEL, ws, wu) + ".result.json")).write_text(json.dumps(worker_read))
    (folder / (M.FileCaller.call_id(M.REFUTE_MODEL, rs, ru) + ".result.json")).write_text(json.dumps(refute_read))
    budget = {"max_model_calls": 2, "max_sub_agents": 2, "max_concurrent_workers": 1, "max_tool_calls": 0,
              "max_tokens": 200000, "max_wall_clock_s": 300, "max_retries": 0, "max_graph_writes": 1000}
    plan = P.make_plan(sc, name="check-run", workload="one real event, from files", events=[EVENT], cutoff=0.7, budget=budget)
    plan.greg_go = "the check's own words, not Greg's: nothing is dispatched"
    res = RUN.run_plan(plan, M.FileCaller(folder, poll_s=0.01, timeout_s=2), sc)
    assert res["completed_events"] == [EVENT] and res["unresolved"] == {} and res["stopped_because"] is None
    assert res["refute_wave_events"] == [EVENT] and len(sc.nodes("Evaluation")) == len(refute_read["checks"])
    runs = [n for n in sc.nodes("AgentRun") if n["attrs"].get("plan")]      # the real runs of the record carry no plan
    assert {r["attrs"]["role"] for r in runs} == {"swarm worker", "swarm refuter"} and len(runs) == 2
    for r in runs:
        a = r["attrs"]
        assert a["plan"] == "check-run" and a["outcome"] == "returned" and a["wall_clock_ms"] >= 0
        assert a["model"] in M.MODELS and "input_tokens" in a and "output_tokens" in a
    assert sc.check_all() == []
    assert res["synthesis"].count("== ") == 1 and res["budget_used"]["model_calls"] == 2

    # the budget stops the run: one call allowed, so the refute wave is not started, and it says why
    sc2 = scratch(real, root, tmp_path, name="run2")
    b2 = dict(budget, max_model_calls=1)
    plan2 = P.make_plan(sc2, name="check-run-2", workload="w", events=[EVENT], cutoff=0.7, budget=b2)
    plan2.greg_go = "the check's own words"
    res2 = RUN.run_plan(plan2, M.FileCaller(folder, poll_s=0.01, timeout_s=2), sc2)
    assert res2["completed_events"] == [EVENT] and res2["refute_wave_events"] == []
    assert "max_model_calls of 1" in res2["unresolved"]["refute:" + EVENT]
    # and with no wall clock allowed, the event is returned as unresolved, with the reason
    sc3 = scratch(real, root, tmp_path, name="run3")
    plan3 = P.make_plan(sc3, name="check-run-3", workload="w", events=[EVENT], cutoff=0.7, budget=dict(budget, max_wall_clock_s=0))
    plan3.greg_go = "the check's own words"
    res3 = RUN.run_plan(plan3, M.FileCaller(folder, poll_s=0.01, timeout_s=2), sc3)
    assert res3["completed_events"] == [] and EVENT in res3["unresolved"] and "max_wall_clock_s of 0" in res3["stopped_because"]
    assert "not started" in res3["unresolved"][EVENT]
    # a plan without Greg's go does not run at all
    plan3.greg_go = ""
    with pytest.raises(P.PlanRefused):
        RUN.run_plan(plan3, M.FileCaller(folder), sc3)


def test_one_events_reduce_or_refute_failure_is_recorded_for_that_event_and_the_run_goes_on(
        real, root, worker_read, refute_read, tmp_path, monkeypatch):
    """The real answers in files; the reducer or the refute loader made to raise (the code, not the answers,
    is changed). The event is recorded as unresolved with the reason, and the run returns its result."""
    sc = scratch(real, root, tmp_path, name="run")
    probe = _loaded(real, root, worker_read, tmp_path, name="probe")
    ids = R.review_set(probe, [EVENT], 0.7)
    ws, wu = L.build_brief_parts(L.event_layers(sc, EVENT))
    rs, ru = F.build_refute_brief_parts(probe, ids)
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / (M.FileCaller.call_id(M.WORKER_MODEL, ws, wu) + ".result.json")).write_text(json.dumps(worker_read))
    (folder / (M.FileCaller.call_id(M.REFUTE_MODEL, rs, ru) + ".result.json")).write_text(json.dumps(refute_read))
    budget = {"max_model_calls": 2, "max_sub_agents": 2, "max_concurrent_workers": 1, "max_tool_calls": 0,
              "max_tokens": 200000, "max_wall_clock_s": 300, "max_retries": 0, "max_graph_writes": 1000}
    plan = P.make_plan(sc, name="check-fail", workload="one real event, from files", events=[EVENT], cutoff=0.7, budget=budget)
    plan.greg_go = "the check's own words, not Greg's: nothing is dispatched"
    # the refute step raises
    orig = F.load_refute_result

    def boom(*a, **k):
        raise RuntimeError("the refute step fell over")
    monkeypatch.setattr(F, "load_refute_result", boom)
    res = RUN.run_plan(plan, M.FileCaller(folder, poll_s=0.01, timeout_s=2), sc)
    assert res["completed_events"] == [EVENT] and res["refute_wave_events"] == []
    assert "RuntimeError" in res["unresolved"]["refute:" + EVENT] and "fell over" in res["unresolved"]["refute:" + EVENT]
    monkeypatch.setattr(F, "load_refute_result", orig)
    # the reduce step raises
    sc2 = scratch(real, root, tmp_path, name="run2")

    def boom2(*a, **k):
        raise RuntimeError("the reduce step fell over")
    monkeypatch.setattr(R, "load_worker_result", boom2)
    plan2 = P.make_plan(sc2, name="check-fail-2", workload="w", events=[EVENT], cutoff=0.7, budget=budget)
    plan2.greg_go = plan.greg_go
    res2 = RUN.run_plan(plan2, M.FileCaller(folder, poll_s=0.01, timeout_s=2), sc2)
    assert res2["completed_events"] == [] and "RuntimeError" in res2["unresolved"][EVENT]
