"""Stage 6, the swarm: what a worker reads, the reducer, the refute wave, the plan and the command line.

Real records only. The expected values are counted here by another route than the code's: openpyxl on the
saved workbook ROOT_dipoles_pinned.xlsx. No model is called: the two real reads (one worker's answer and one
refuter's answer for the real event dipole:dip-19632-1696206142, written by hand by the builder session to
check the loaders on real output) are read from markets-data graph/reads/ (until the main session copies them
there, from the builder's scratch folder). Writes go to pytest tmp folders, never into markets-data.
"""

import copy
import io
import json
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import openpyxl
import pytest

from tools.kgraph.store import GraphStore, markets_data_root
from tools.swarm import layers as L
from tools.swarm import model as M
from tools.swarm import plan as P
from tools.swarm import reduce as R
from tools.swarm import refute as F
from tools.swarm import run as RUN

DAYS = ("2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18")
XLSX = ("tasks/family-research-20261022/research-union-current/root-redesign-20261116/"
        "ROOT_dipoles_pinned.xlsx")
SRC = "src:markets-data:" + XLSX
EVENT = "dipole:dip-19632-1696206142"
WORKER_FILE = "swarm-worker-dip-19632-1696206142.json"
REFUTE_FILE = "swarm-refute-dip-19632-1696206142.json"
SCRATCH_READS = Path("/tmp/claude-0/-home-user/0512b4e2-4481-5302-b8a2-d9cee9a3e96b/scratchpad/reads")
RUN_ID = "run:0029"
RUN_NODE = {"id": RUN_ID, "type": "AgentRun", "attrs": {
    "role": "builder", "model": "sonnet",
    "task": "one real worker read and one real refute read of dip-19632-1696206142, to check the swarm's loaders",
    "outcome": "returned"}}


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


def _read(root, name):
    for p in (root / "graph" / "reads" / name, SCRATCH_READS / name):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    pytest.skip(f"{name} is in neither markets-data graph/reads/ nor the builder's scratch folder")


@pytest.fixture(scope="module")
def worker_read(root):
    return _read(root, WORKER_FILE)


@pytest.fixture(scope="module")
def refute_read(root):
    return _read(root, REFUTE_FILE)


def _slim(n):
    return {"id": n["id"], "type": n["type"], "attrs": n["attrs"]}


def scratch(real, root, tmp_path, day="2023-10-02", name="g"):
    """A scratch graph (in a pytest tmp folder) holding the real nodes of one trade day (a copy of what the
    saved graph holds: the TradeDay, the workbook Source, every dipole and peak) and the check's AgentRun."""
    sc = GraphStore(root, graph_dir=tmp_path / name)
    nodes = [_slim(real.node("tradeday:" + day)), _slim(real.node(SRC))]
    nodes += [_slim(n) for n in real.nodes("DipoleEvent") if n["attrs"]["trade_day"] == day]
    nodes += [_slim(n) for n in real.nodes("Peak") if n["attrs"]["trade_day"] == day]
    sc.write(nodes, [], written_by="code:test_stage6_swarm")
    sc.write([RUN_NODE], [], written_by="code:test_stage6_swarm")
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


def test_what_is_sent_to_the_model(root):
    kw = M.request_kwargs("claude-haiku-5-5", "s", "u", 100, "low", L.ANSWER_SCHEMA)
    assert "betas" not in kw and "fallbacks" not in kw and kw["output_config"]["effort"] == "low"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    kw = M.request_kwargs("claude-sonnet-5-5", "s", "u", 100, "medium")
    assert kw["betas"] == [M.FALLBACK_BETA] and kw["fallbacks"] == "default"
    for k in ("temperature", "top_p", "thinking", "tool_choice"):
        assert k not in kw
    assert kw["messages"] == [{"role": "user", "content": "u"}]      # no prefill
    with pytest.raises(ValueError):
        M.request_kwargs("claude-haiku-5-5-20260101", "s", "u", 1, "low")      # exact ids, no date suffix
    with pytest.raises(ValueError):
        M.request_kwargs("claude-haiku-5-5", "s", "u", 1, "fast")
    import inspect
    assert not [n for n in dir(M) if "fake" in n.lower() or "mock" in n.lower()]      # no caller makes up an answer
    assert {"AnthropicCaller", "FileCaller"} <= {n for n, o in vars(M).items() if inspect.isclass(o)}


def test_file_caller_hands_back_what_a_session_agent_put_there(worker_read, tmp_path):
    fc = M.FileCaller(tmp_path / "f", poll_s=0.01, timeout_s=0.3)
    cid = M.FileCaller.call_id("claude-haiku-5-5", "sys", "usr")
    with pytest.raises(M.ModelCallFailed):                    # nothing there: it waits, then says so
        fc.call("claude-haiku-5-5", "sys", "usr", 100, "low")
    assert (tmp_path / "f" / f"{cid}.brief.txt").exists()
    (tmp_path / "f" / f"{cid}.result.json").write_text(json.dumps(worker_read), encoding="utf-8")
    r = fc.call("claude-haiku-5-5", "sys", "usr", 100, "low")
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
        # one node only: the cited cells all belong to one sheet row
        assert len({x["n"] for x in a["cited_cells"]}) == len(a["cited_cells"])
    # inferences have no source of their own, and rest on claims of the answer
    infer = [c for c in claims if c["attrs"]["inference"]]
    assert infer and all("source" not in c["attrs"] for c in infer)
    derived = [e for e in sc.edges("DERIVED_FROM")]
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


def test_a_real_claim_set_against_the_wrong_real_cells_is_thrown_out(real, root, worker_read, tmp_path):
    """Real words and real cells only; no figure is invented. The text of one real claim is set against the
    cells another real claim cites, so the figure it states is not the value of a cell it cites."""
    sc = scratch(real, root, tmp_path)
    alt = copy.deepcopy(worker_read)
    c2 = next(c for c in alt["claims"] if "0.1461538461538462" in c["text"])
    other = next(c for c in alt["claims"] if not c.get("inference") and c is not c2
                 and set(c["cells"]) != set(c2["cells"]) and "0.1461538461538462" not in c["text"])
    c2["cells"] = list(other["cells"])
    rep = R.load_worker_result(sc, alt, RUN_ID, cutoff=0.7)
    assert rep["thrown_out"] >= 1 and any("0.1461538461538462" in t["reason"] for t in rep["thrown"])
    assert all(c["attrs"]["text"] != c2["text"] for c in sc.nodes("Claim"))
    assert rep["thrown_out"] + rep["claims_written"] == len(alt["claims"])           # none lost
    # a claim that cites cells of two nodes is thrown out as a non-inference
    alt = copy.deepcopy(worker_read)
    alt["claims"][0]["cells"] = [1, 26]
    rep = R.load_worker_result(scratch(real, root, tmp_path, name="g3"), alt, RUN_ID)
    assert rep["thrown_out"] >= 1 and "one node only" in rep["thrown"][0]["reason"]
    # a claim resting on a claim that was thrown out is thrown out too (it rests on nothing written)
    assert any("not an earlier claim of this answer that was written" in t["reason"] for t in rep["thrown"])
    # a cell number one past the last cell of the event's own brief
    alt = copy.deepcopy(worker_read)
    alt["claims"][1]["cells"] = [len(L.cells(L.event_layers(sc, EVENT))) + 1]
    rep = R.load_worker_result(scratch(real, root, tmp_path, name="g4"), alt, RUN_ID)
    assert "not a cell of this event's brief" in rep["thrown"][0]["reason"]
    # a run that is not an AgentRun of the graph is refused
    with pytest.raises(Exception, match="AgentRun"):
        R.load_worker_result(scratch(real, root, tmp_path, name="g6"), worker_read, "run:nothing")


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
    rep = F.load_refute_result(sc, refute_read, RUN_ID)
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
    rep = F.load_refute_result(sc, refute_read, RUN_ID)
    cx = sc.edges("CONTRADICTS")
    assert len(cx) == rep["counter_statements_written"] <= len(real_ones)
    for e in cx:
        assert sc.node(e["src"])["type"] == "Claim" and sc.node(e["dst"]) is not None      # both claims stay
    assert sc.check_all() == []


def test_synthesis_names_only_that_events_claims(real, root, worker_read, refute_read, tmp_path):
    sc = _loaded(real, root, worker_read, tmp_path)
    F.load_refute_result(sc, refute_read, RUN_ID)
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
    F.load_refute_result(sc, refute_read, RUN_ID)
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
    runs = [n for n in sc.nodes("AgentRun") if n["id"] != RUN_ID]
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
