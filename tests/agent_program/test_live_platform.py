"""The graph while a run goes (tools/kgraph/live.py) and the packet for one opening signal
(tools/kgraph/signal_packet.py). Real records only: the record branches of markets-data fetched with every
push (origin/paper-runs/<run>) and the platform checkout. Skipped with the reason when one is missing.
Every write goes to a scratch folder; markets-data is only read. Nothing is scored; no mid, no cost."""

import copy
import json
import subprocess
import time

import pytest

from tools.exp_dag import ExpDag
from tools.kgraph import ingest_platform as ipf
from tools.kgraph import live, signal_packet as sp
from tools.kgraph.store import GraphStore, markets_data_root

RUNS = {"0f33fec49f8c4905b6c212912077d439": 90, "ea4c1d2e7e0c43168c150c8b2aef3960": 143}
R0 = "0f33fec49f8c4905b6c212912077d439"


def _root():
    try:
        return markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")


def _platform(root):
    p = root.parent / "paper-trading-platform"
    if not (p / ".git").exists():
        pytest.skip(f"no paper-trading-platform checkout at {p}")
    return str(p)


def _tip(root, run):
    try:
        tip = live.resolve_commit(root, run)
    except RuntimeError as e:
        pytest.skip(f"no ref for {run}: {e}")
    return tip, live.commits_of(root, tip)


def _snap(store):
    return ({n["id"]: n["content_sha"] for n in store.nodes()},
            {e["id"]: e["content_sha"] for e in store.edges(withdrawn=True)})


@pytest.mark.parametrize("run", list(RUNS))
def test_follow_push_by_push_equals_one_load_of_the_finished_run(run, tmp_path, capsys):
    root, plat = _root(), None
    plat = _platform(root)
    tip, commits = _tip(root, run)
    assert len(commits) == RUNS[run], f"the ref holds {len(commits)} commits, the check was made on {RUNS[run]}"
    t0 = time.time()
    reps = live.follow_commits(root, run, commits, platform=plat, graph_dir=tmp_path / "gA", exp_dir=tmp_path / "eA")
    wall = time.time() - t0
    print(f"\nfollow {run[:8]}: {len(commits)} commits in {wall:.1f} s")
    assert [r["receipt"] for r in reps] == [False] * (len(commits) - 1) + [True]
    assert [r["journal_sequence"] for r in reps] == sorted(r["journal_sequence"] for r in reps)
    # no trial while the receipt is missing
    assert all(r["trial"] is None for r in reps[:-1]) and reps[-1]["trial"]
    # ingest_platform once, on the finished run, into another scratch store
    sB, dB = GraphStore(root, graph_dir=tmp_path / "gB"), ExpDag(root, exp_dir=tmp_path / "eB")
    saved = ipf.ensure_run
    ipf.ensure_run = lambda d, r: tip
    try:
        ipf.load_run(sB, dB, root, run, plat)
    finally:
        ipf.ensure_run = saved
    sA = GraphStore(root, graph_dir=tmp_path / "gA")
    assert _snap(sA) == _snap(sB)
    # nothing revised more than its content changed; only the file's own Source node is rewritten
    multi = {i: sA.history(i) for i in _snap(sA)[0] if len(sA.history(i)) > 1}
    assert list(multi) == [f"src:markets-data@paper-runs/{run}:paper-trading/{run}/events.jsonl"]
    for lines in multi.values():
        shas = [l["content_sha"] for l in lines]
        assert all(a != b for a, b in zip(shas, shas[1:]))
    for i in _snap(sA)[1]:
        assert len(sA.history(i)) == 1
    assert [t["content_sha"] for t in ExpDag(root, exp_dir=tmp_path / "eA").log()] == [t["content_sha"] for t in dB.log()]
    # a second follow of the tip writes nothing
    again = live.follow(root, run, platform=plat, graph_dir=tmp_path / "gA", exp_dir=tmp_path / "eA")
    assert again["graph_write"]["new"] == 0 and again["graph_write"]["revised"] == 0
    assert GraphStore(root, graph_dir=tmp_path / "gA").counts() == sA.counts()
    assert len(ExpDag(root, exp_dir=tmp_path / "eA").lines()) == 1
    assert sA.check_all() == []


def test_a_branch_with_no_receipt_has_no_trial(tmp_path):
    root = _root()
    tip, commits = _tip(root, R0)
    rep = live.follow(root, R0, at=commits[40], platform=_platform(root), graph_dir=tmp_path / "g", exp_dir=tmp_path / "e")
    assert rep["receipt"] is False and rep["trial"] is None
    assert not (tmp_path / "e" / "trials.jsonl").exists() or ExpDag(root, exp_dir=tmp_path / "e").lines() == []
    assert rep["new"]["orders"] > 0 and rep["unchanged"]["orders"] == 0


# ---- the packet ------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pk_env():
    root = _root()
    plat = _platform(root)
    tip, commits = _tip(root, R0)
    rows = sp.journal_from_branch(root, R0)
    return root, plat, tip, commits, rows, GraphStore(root)      # read only: nothing is written to it


def test_first_middle_last_packets_pass_and_a_later_row_fails_naming_it(pk_env):
    root, plat, tip, commits, rows, store = pk_env
    opens = sp.open_sequences(rows)
    assert len(opens) == 217
    for s in (opens[0], opens[len(opens) // 2], opens[-1]):
        p = sp.build(rows, s, 6000, store=store, platform_dir=plat)
        assert sp.leakage_check(p, store=store, journal_rows=rows) == []
        assert p["tokens_estimated"] <= 6000 and "mid" not in p["text"].split("NOT IN THIS PACKET")[0].lower().replace("middle", "")
        assert "open_profit" not in p["text"].split("NOT IN THIS PACKET")[0]
        print(f"\npacket seq {s}: {p['tokens_estimated']} tokens, lines {len(p['lines'])}, cut {p['cut']}")
    p = sp.build(rows, opens[len(opens) // 2], 6000, store=store, platform_dir=plat)
    later = next(r for r in rows if r["sequence"] > p["sequence"] and r["kind"] == "paper order"
                 and r["received"] > p["moment_ns"])
    bad = copy.deepcopy(p)
    ln = sp.row_line(later, R0)
    ln["section"] = "other_rules"
    bad["lines"].append(ln)
    bad["text"] = sp.render(bad)
    breaches = sp.leakage_check(bad, store=store, journal_rows=rows)
    assert any(ln["source"] in b for b in breaches), breaches
    assert any("after the moment" in b for b in breaches) and any("not below the signal" in b for b in breaches)
    other = copy.deepcopy(p)
    x = sp.row_line(later, R0)
    x.update(section="other_rules", run="another-run", known_at_ns=p["moment_ns"], sequence=1)
    other["lines"].append(x)
    other["text"] = sp.render(other)
    assert any("another-run" in b for b in sp.leakage_check(other))
    edited = copy.deepcopy(p)
    edited["text"] += "an extra line\n"
    assert sp.leakage_check(edited)


def test_all_opens_gives_a_line_for_each_with_no_breach(pk_env, tmp_path):
    root, plat, tip, commits, rows, store = pk_env
    out = tmp_path / "opens.jsonl"
    assert sp.main(["--data", str(root), "--run", R0, "--budget", "6000", "--all-opens", "--out", str(out),
                    "--platform", plat]) == 0
    got = [json.loads(l) for l in out.read_text().splitlines()]
    assert [g["sequence"] for g in got] == sp.open_sequences(rows) and len(got) == 217
    assert all(g["leakage_breaches"] == 0 for g in got)
    assert set(got[0]) == {"sequence", "rule", "tokens_estimated", "lines_in", "lines_cut", "leakage_breaches"}


def test_a_packet_built_at_an_early_commit_equals_the_one_at_the_tip(pk_env):
    root, plat, tip, commits, rows, store = pk_env
    opens = sp.open_sequences(rows)
    s = opens[len(opens) // 2]
    early = next(c for c in commits if max(r["sequence"] for r in live.read_at(root, R0, c)["rows"]) > s)
    assert early != tip
    a = sp.build(sp.journal_from_branch(root, R0, at=early), s, 6000, store=store, platform_dir=plat)
    b = sp.build(rows, s, 6000, store=store, platform_dir=plat)
    assert a["text"] == b["text"] and a["sha256"] == b["sha256"] and a["lines"] == b["lines"]


def test_a_packet_from_a_local_journal_file_equals_the_one_from_the_branch(pk_env, tmp_path):
    root, plat, tip, commits, rows, store = pk_env
    path = tmp_path / "events.jsonl"
    path.write_bytes(subprocess.run(["git", "-C", str(root), "show", f"{tip}:paper-trading/{R0}/events.jsonl"],
                                    capture_output=True, check=True).stdout)
    from_file = sp.journal_from_file(path)
    opens = sp.open_sequences(rows)
    for s in (opens[0], opens[len(opens) // 2], opens[-1]):
        a = sp.build(from_file, s, 6000, store=store, platform_dir=plat)
        b = sp.build(rows, s, 6000, store=store, platform_dir=plat)
        assert a["text"] == b["text"] and a["sha256"] == b["sha256"]
        # the file holding only the rows below the signal gives the same packet: later rows are never read
        c = sp.build([r for r in from_file if r["sequence"] <= s], s, 6000, store=store, platform_dir=plat)
        assert c["sha256"] == a["sha256"]
    # the command line, both sources
    import io, contextlib
    outs = []
    for extra in (["--run", R0], ["--journal", str(path)]):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert sp.main(["--data", str(root), *extra, "--sequence", str(opens[5]), "--budget", "4000",
                            "--platform", plat]) == 0
        outs.append(buf.getvalue())
    assert outs[0] == outs[1] and outs[0]


# ---- what a decider is given, against the Excel daily sheets (Greg, 2026-11-24) ------------------------------------
#
# "We should compare that against the excel daily sheets or just one day. They should have same columns on each day."
# The daily sheets in the checkout: ROOT_dipoles_pinned.xlsx (one sheet a trade day for each of three kinds, the four
# trade days) and ROOT_short_stretch_20231002_0900.xlsx (one day of the stored rows, 408 columns, "COLUMNS" sheet beside
# it). Headers only are read. Every column of the 2023-10-02 sheets is in exactly one place: (a) in the packet at the
# signal's moment, (b) in afterwards_layers.json, (c) not placed, with the reason. A column added to a workbook later
# fails the check until someone places it.

WORK = "tasks/family-research-20261022/research-union-current/root-redesign-20261116"
PINNED = f"{WORK}/ROOT_dipoles_pinned.xlsx"
STRETCH = f"{WORK}/ROOT_short_stretch_20231002_0900.xlsx"
DAYS = ("2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18")


def _headers(path, sheet):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return list(next(wb[sheet].iter_rows(min_row=1, max_row=1, values_only=True)))
    finally:
        wb.close()


def _workbook(root, rel):
    p = root / rel
    if not p.exists():
        pytest.skip(f"the workbook {rel} is not in the checkout {root}")
    return p


def test_the_four_days_carry_the_same_columns_in_the_same_order_on_every_kind_of_sheet():
    root = _root()
    p = _workbook(root, PINNED)
    for kind in ("dipoles", "peaks", "crypto and ng"):
        first = _headers(p, f"{kind} {DAYS[0]}")
        for day in DAYS[1:]:
            assert _headers(p, f"{kind} {day}") == first, f"{kind}: {day} differs from {DAYS[0]}"


def _crypto_ng_reason():
    from tools.kgraph import signal_packet as sp
    return next(r for k, r in sp.PLANE_NOT_PLACED if k == "crypto-ng-tick-program-trades")


def test_every_column_of_the_2023_10_02_daily_sheets_is_placed_in_one_of_three_places():
    from tools.kgraph import packet as dp, signal_packet as sp
    root = _root()
    pinned, stretch = _workbook(root, PINNED), _workbook(root, STRETCH)
    store = GraphStore(root)
    placed = {}                                                    # (sheet, column) -> (place, reason)

    def put(sheet, col, place, why):
        assert (sheet, col) not in placed, f"{sheet}.{col} is placed twice"
        placed[(sheet, col)] = (place, why)

    # dipoles: packet.py's own groups. SHOWN is in the packet (dipoles section, known at the event's known second);
    # HELD_BACK and AFTERWARDS are in afterwards_layers.json (dipole_cells_held_back_columns / _afterwards_columns).
    for c in _headers(pinned, "dipoles 2023-10-02"):
        if c in dp.SHOWN:
            put("dipoles", c, "a", "dipoles section, known at the event's native known second")
        elif c in dp.HELD_BACK:
            put("dipoles", c, "b", "held back: " + dp.HELD_BACK[c])
        elif c in dp.AFTERWARDS:
            put("dipoles", c, "b", "after the event: " + dp.AFTERWARDS[c])
        else:
            put("dipoles", c, "c", "a column the code has no group for")
    # peaks: every Peak is after-the-fact (the graph holds the time of a peak's high, not when it became known); the
    # five columns are the cells of the Peak nodes' `pinned`, which the afterwards file carries whole.
    peak_cells = set()
    for n in store.nodes("Peak"):
        if n["attrs"].get("trade_day") == "2023-10-02":
            peak_cells |= set(n["attrs"]["pinned"])
    for c in _headers(pinned, "peaks 2023-10-02"):
        if c in peak_cells:
            put("peaks", c, "b", "a Peak: the graph holds the time of a peak's high, not when it became known")
        else:
            put("peaks", c, "c", "not a cell of any Peak node of the trade day")
    # the crypto and ng program's own trades: observation and verification only (CLAUDE.md), kept out of both
    for c in _headers(pinned, "crypto and ng 2023-10-02"):
        put("crypto and ng", c, "c", _crypto_ng_reason())
    # the stored rows of the day: the packet's `rows` layer is read through PLANE_PROJECT (the tape's own fields, each
    # row placed by its own latest instant); the other columns are NOT copied (size), named in the foot
    sheet_cols = _headers(stretch, "2023-10-02")
    mine = set(sp.PLANE_PROJECT["rows"])
    assert mine <= set(sheet_cols), sorted(mine - set(sheet_cols))
    for c in sheet_cols:
        if c in mine:
            put("rows", c, "a", "plane:rows:<n>, placed by the row's own latest instant (received_time_ns)")
        else:
            put("rows", c, "c", "stored per tick and known at the tick, but not copied into a question's files: 408 fields "
                                "by 820,670 ticks (about 1 GB held in memory for the 85 fields of sections A to E, 323 "
                                "outside-data fields beside); named in the foot, kept in git pinned by sha256")
    # the equality that makes a new column fail: the day's columns as sets, against the placed list
    day_columns = ({("dipoles", c) for c in _headers(pinned, "dipoles 2023-10-02")}
                   | {("peaks", c) for c in _headers(pinned, "peaks 2023-10-02")}
                   | {("crypto and ng", c) for c in _headers(pinned, "crypto and ng 2023-10-02")}
                   | {("rows", c) for c in sheet_cols})
    assert set(placed) == day_columns
    # the dipole sheet's columns: every one has a group, none falls to "no group"
    assert not [k for k, (pl, w) in placed.items() if k[0] in ("dipoles", "peaks") and pl == "c"]
    counts = {pl: sum(1 for v in placed.values() if v[0] == pl) for pl in "abc"}
    per_sheet = {s: {pl: sum(1 for k, v in placed.items() if k[0] == s and v[0] == pl) for pl in "abc"}
                 for s in ("dipoles", "peaks", "crypto and ng", "rows")}
    print("\ncolumn placement of the 2023-10-02 daily sheets:", counts, per_sheet)
    assert counts["a"] + counts["b"] + counts["c"] == len(day_columns)
