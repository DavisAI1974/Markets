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
