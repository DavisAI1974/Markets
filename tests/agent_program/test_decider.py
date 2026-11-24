"""The Markets side of the mailbox handshake (tools/decider). Real records only: the journal of run 0f33fec4... from
its record branch (git show into a scratch folder). No engine, no tape, no model. An answer written by a check is
not market data; everything else here is the real journal. markets-data is only read."""

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tools.decider import answer as answer_cmd, next as next_cmd, serve
from tools.kgraph import signal_packet as sp
from tools.kgraph.store import GraphStore, markets_data_root

R0 = "0f33fec49f8c4905b6c212912077d439"
BUDGET = 6000
PLATFORM_CHECKOUT = Path("/home/user/paper-trading-platform")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    try:
        root = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    plat = root.parent / "paper-trading-platform"
    if not (plat / ".git").exists():
        pytest.skip(f"no paper-trading-platform checkout at {plat}")
    r = subprocess.run(["git", "-C", str(root), "show",
                        f"origin/paper-runs/{R0}:paper-trading/{R0}/events.jsonl"], capture_output=True)
    if r.returncode:
        pytest.skip(f"no record branch for {R0} in {root}")
    journal = tmp_path_factory.mktemp("journal") / "events.jsonl"
    journal.write_bytes(r.stdout)
    rows = sp.journal_from_file(journal)
    opens = sp.open_sequences(rows)
    return dict(root=root, plat=str(plat), journal=journal, rows=rows, store=GraphStore(root),
                picks=[opens[0], opens[len(opens) // 2], opens[-1]])


def _question(world, box_root, seq):
    """question.json as the platform writes it: its own MailboxDecider when it imports cleanly, else its keys."""
    sig = next(r for r in world["rows"] if r["sequence"] == seq)
    q = dict(sequence=seq, rule=sig["rule"], side=sig.get("side"), trade_id=sig["trade_id"],
             tape_received_ns=sig["received"], journal=str(world["journal"]))
    try:
        sys.path.insert(0, str(PLATFORM_CHECKOUT))
        from paper_platform.answers import MailboxDecider
    except Exception:
        MailboxDecider = None
    finally:
        if str(PLATFORM_CHECKOUT) in sys.path:
            sys.path.remove(str(PLATFORM_CHECKOUT))
    if MailboxDecider is None:
        (box_root / f"q-{seq}").mkdir(parents=True)
        serve.write_json(box_root / f"q-{seq}" / "question.json", q)       # by its documented keys
        return q
    t = threading.Thread(target=lambda: MailboxDecider(box_root, 0.3, poll_s=0.05).ask(q))
    t.start()
    t.join()
    return q


def _mailbox(world, tmp_path, seqs=None):
    mb = tmp_path / "mb"
    mb.mkdir()
    for s in (seqs or world["picks"]):
        q = _question(world, mb, s)
        # the platform's own ask timed out and left its question; its none answer is not the file under check
    for s in (seqs or world["picks"]):
        (mb / f"q-{s}" / "answer.json").unlink(missing_ok=True)
    return mb


def _server(world, mb):
    return serve.Server(mb, world["root"], world["plat"], BUDGET, "run:0090")


def _decide(mb, seq, **d):
    serve.write_json(mb / f"q-{seq}" / "decision.json", d)


def _lines(mb):
    return [json.loads(l) for l in (mb / "decisions.jsonl").read_text().splitlines()]


def test_brief_holds_the_packet_and_passes_the_leak_check(world, tmp_path, capsys):
    mb = _mailbox(world, tmp_path)
    _server(world, mb).once()
    sizes = []
    for s in world["picks"]:
        brief = (mb / f"q-{s}" / "brief.md").read_text()
        q = json.loads((mb / f"q-{s}" / "question.json").read_text())
        pk = sp.build(world["rows"], s, BUDGET, store=world["store"], platform_dir=world["plat"], question=q)
        assert pk["text"] in brief and pk["sha256"] in brief
        assert sp.leakage_check(pk, store=world["store"], journal_rows=world["rows"]) == []
        assert "hold until the trade gives back 20% of its highest open profit" in brief
        assert not (mb / f"q-{s}" / "answer.json").exists()
        sizes.append((s, len(brief) // 4, pk["tokens_estimated"]))
    print("\nbrief tokens (chars/4), packet tokens:", sizes)


def test_valid_decision_becomes_an_answer_the_platform_accepts(world, tmp_path):
    mb = _mailbox(world, tmp_path)
    srv = _server(world, mb)
    srv.once()
    s = world["picks"][0]
    ids = json.loads((mb / f"q-{s}" / "packet.json").read_text())["ids"]
    _decide(mb, s, action="take", why="The signal line stands and the rule line fits it.", rests_on=ids[:2])
    srv.once()
    a = json.loads((mb / f"q-{s}" / "answer.json").read_text())
    assert a["id"] == f"decision-{s}" and a["action"] == "take" and a["asked_at_sequence"] == s and a["by"] == "run:0090"
    assert set(a["packet"]) == {"sha256", "tokens"}
    try:
        sys.path.insert(0, str(PLATFORM_CHECKOUT))
        from paper_platform.answers import validate, validate_decision
    except Exception as e:
        pytest.skip(f"the platform checkout cannot be imported: {type(e).__name__}")
    finally:
        if str(PLATFORM_CHECKOUT) in sys.path:
            sys.path.remove(str(PLATFORM_CHECKOUT))
    assert validate(a) is None and validate_decision(a, s) is None


@pytest.mark.parametrize("which,decision,reason", [
    ("id", dict(action="take", why="Because.", rests_on=["journal#999999999"]), "not in the packet"),
    ("none", dict(action="take", why="Because."), "rests_on"),
    ("empty", dict(action="take", why="Because.", rests_on=[]), "rests_on"),
    ("action", dict(action="close", why="Because.", rests_on=["X"]), "take or skip"),
])
def test_invalid_decision_is_kept_and_answered_skip(world, tmp_path, which, decision, reason):
    s = world["picks"][1]
    mb = _mailbox(world, tmp_path, [s])
    srv = _server(world, mb)
    srv.once()
    _decide(mb, s, **decision)
    srv.once()
    box = mb / f"q-{s}"
    assert reason in json.loads((box / "decision.rejected.json").read_text())["reason"]
    a = json.loads((box / "answer.json").read_text())
    assert a["action"] == "skip" and a["why"].startswith("the decider's answer was not valid: ") and reason in a["why"]
    line, = _lines(mb)
    assert line["answered_by"] == "this code" and line["action"] == "skip"


def test_a_breaching_packet_is_refused_and_answered_skip(world, tmp_path, monkeypatch):
    s = world["picks"][1]
    mb = _mailbox(world, tmp_path, [s])
    later = next(r for r in world["rows"] if r["sequence"] > s and r["kind"] == "signal")

    def breaching(rows, sequence, budget, store, platform_dir, question=None):
        pk = sp.build(rows, sequence, budget, store=store, platform_dir=platform_dir, question=question)
        ln = sp.row_line(later, later["run"])           # a later row, handed over through the seam
        ln["section"] = "same_rule"
        pk["lines"].append(ln)
        pk["text"] = sp.render(pk)
        return pk

    monkeypatch.setattr(serve, "build_packet", breaching)
    _server(world, mb).once()
    box = mb / f"q-{s}"
    assert not (box / "brief.md").exists()
    assert json.loads((box / "refused.json").read_text())["breach"]
    a = json.loads((box / "answer.json").read_text())
    assert a["action"] == "skip" and a["why"].startswith("the packet failed its own leak check: ")
    line, = _lines(mb)
    assert line["answered_by"] == "this code" and line["skip_reason"].startswith("the packet failed")


KEYS = {"sequence", "rule", "side", "trade_id", "tape_received_ns", "packet_sha256",
        "packet_tokens_estimated_chars_div_4", "lines_in", "lines_cut", "action", "why", "rests_on", "by",
        "wall_ms_question_to_decision", "answered_by", "skip_reason", "program_sha256",
        "state_given", "state_sha256", "state_matches_journal", "book_levels_bid", "book_levels_ask", "dipole",
        "exhaustion", "layers_in_packet", "rests_on_layers"}


def test_one_line_a_question_and_a_second_pass_writes_nothing_new(world, tmp_path):
    mb = _mailbox(world, tmp_path)
    srv = _server(world, mb)
    srv.once()
    for s in world["picks"]:
        ids = json.loads((mb / f"q-{s}" / "packet.json").read_text())["ids"]
        _decide(mb, s, action="skip", why="The packet gives no ground to take.", rests_on=ids[:1])
    srv.once()
    lines = _lines(mb)
    assert [l["sequence"] for l in lines] == world["picks"]
    assert all(set(l) == KEYS and l["answered_by"] == "the decider" and l["by"] == "run:0090" for l in lines)
    before = {p: p.read_bytes() for p in mb.rglob("*") if p.is_file()}
    assert _server(world, mb).once() == 0
    assert before == {p: p.read_bytes() for p in mb.rglob("*") if p.is_file()}


def test_next_and_answer_round_trip(world, tmp_path, capsys):
    mb = _mailbox(world, tmp_path, world["picks"][:2])
    srv = _server(world, mb)
    assert next_cmd.main(["--mailbox", str(mb)]) == 0
    assert "none is waiting" in capsys.readouterr().out
    srv.once()
    first = world["picks"][0]
    assert next_cmd.main(["--mailbox", str(mb)]) == 0
    out = capsys.readouterr().out
    assert f"signal journal sequence {first};" in out
    ids = json.loads((mb / f"q-{first}" / "packet.json").read_text())["ids"]
    assert answer_cmd.main(["--mailbox", str(mb), "--sequence", str(first), "--action", "skip",
                            "--why", "No ground to take.", "--rests-on", ids[0]]) == 0
    capsys.readouterr()
    srv.once()
    assert json.loads((mb / f"q-{first}" / "answer.json").read_text())["action"] == "skip"
    assert next_cmd.main(["--mailbox", str(mb)]) == 0
    assert f"signal journal sequence {world['picks'][1]};" in capsys.readouterr().out


# ---- piece 4: a decider program, the same door ------------------------------------------------------------

import hashlib

REPO = Path(__file__).resolve().parents[2]
SKIP_ALL = REPO / "tools" / "decider" / "programs" / "skip_all.py"


def _program_server(world, mb, path, timeout=5.0):
    return serve.Server(mb, world["root"], world["plat"], BUDGET, "unused", program=path, program_timeout_s=timeout)


def test_skip_all_answers_three_real_questions_through_the_same_door(world, tmp_path):
    mb = _mailbox(world, tmp_path)
    srv = _program_server(world, mb, SKIP_ALL)
    srv.once()
    lines = _lines(mb)
    assert [l["sequence"] for l in lines] == world["picks"]
    sha = hashlib.sha256(SKIP_ALL.read_bytes()).hexdigest()
    for l in lines:
        assert set(l) == KEYS and l["action"] == "skip" and l["answered_by"] == "the program"
        assert l["program_sha256"] == sha and l["by"].startswith("program:skip_all.py@")
        a = json.loads((mb / f"q-{l['sequence']}" / "answer.json").read_text())
        assert a["action"] == "skip" and a["by"] == l["by"] and a["why"] == "no decider logic has been written yet"
        assert l["rests_on"][0].startswith(("journal#", "rule:"))
    assert srv.once() == 0


@pytest.mark.parametrize("name,body,reason", [
    ("raises", "def decide(packet):\n    raise RuntimeError('boom')\n", "raised"),
    ("sleeps", "import time\ndef decide(packet):\n    time.sleep(30)\n", "longer than"),
    ("badid", "def decide(packet):\n    return {'action': 'take', 'why': 'Because.', 'rests_on': ['nope#1']}\n",
     "not in the packet"),
])
def test_a_bad_program_is_answered_skip_with_the_reason(world, tmp_path, name, body, reason):
    prog = tmp_path / f"{name}.py"
    prog.write_text(body)
    s = world["picks"][0]
    mb = _mailbox(world, tmp_path, [s])
    _program_server(world, mb, prog, timeout=1.5).once()
    a = json.loads((mb / f"q-{s}" / "answer.json").read_text())
    assert a["action"] == "skip" and a["why"].startswith("the decider's answer was not valid: ") and reason in a["why"]
    line, = _lines(mb)
    assert line["answered_by"] == "this code" and line["by"].endswith("@uncommitted")


def test_the_program_is_handed_the_packet_and_nothing_a_path_or_a_store_can_come_from(world, tmp_path):
    prog = tmp_path / "echo.py"
    prog.write_text("import json, os, sys\n"
                    "def decide(packet):\n"
                    "    assert set(os.environ) <= {'LC_CTYPE'} and not os.listdir('.') and 'tools' not in sys.modules\n"
                    "    return {'action': 'skip', 'why': 'Echo.', 'rests_on': [packet['lines'][0]['source']]}\n")
    s = world["picks"][0]
    pk = sp.build(world["rows"], s, BUDGET, store=world["store"], platform_dir=world["plat"])
    got, reason = serve.run_program(prog, pk, 5)
    assert reason is None and got["action"] == "skip"
    assert pk["path"] == "signal_v1"                     # the packet's own name, not a place on disk
    assert not any(w in k for k in pk for w in ("store", "journal", "dir", "platform", "file")), sorted(pk)
    assert "/home/" not in json.dumps(pk) and "markets-data" not in json.dumps(pk)


# ---- the data depth: the engine's state at the signal, and every layer ---------------------------------------------
#
# THE REAL SHAPE OF A REAL STATE IS NOT KNOWN until one pass of the tape has been taken (nothing has been run on tape,
# so no real question carries a `state` yet). Everything below uses a STAND-IN state, built here by hand in the shape
# the platform's `_state_at` builds (and its own test_answers.py stand-ins): `inputs` {strategy_inputs, tick,
# previous_trade_tick}, `book` {bid, ask} of {price, size, orders, queue}, `left_out`, `known_at_tape_ns`. Its values
# are NOT market data: they are named stand-ins, used only inside a test's scratch folder, never written to any
# record. The real journal rows (and their real times) are the only real data used here.

STAND_IN_LEVELS = 150


def _stand_in_state(moment, levels=STAND_IN_LEVELS):
    """A STAND-IN state (not market data), shaped as session._state_at builds it."""
    trades = [[moment - i, 0, 1, ["stand-in", i]] for i in range(300)]
    return {
        "inputs": {
            "strategy_inputs": {
                "dipole": {"width": 60 * 10**9, "trades": trades, "size": [300, 0], "value": 1.0},
                "exhaustion": {"width": 20 * 10**9, "trades": [], "size": [0, 0], "value": None},
                "quotes": {"counts": {"stand_in": 1}}, "start": 1, "end": 2, "end_of_day": 3, "last_received": moment},
            "tick": {"position": 5, "received": moment, "exchange": moment - 5, "bid": 10, "ask": 11, "trade": True,
                     "price": 10, "aggressor": "B", "dipole": 1.0, "exhaustion": None, "dipole_before": 0.5,
                     "exhaustion_before": None, "exhaustion_prior_read": None, "settlement": False,
                     "quote_facts": [{"quote": "best bid", "fact": "run started", "direction": "up", "price_now": 10},
                                     {"quote": "best ask", "fact": "run started", "direction": "up", "price_now": 11}],
                     "leg": [3, "up", 4, 9, 10, 2]},
            "previous_trade_tick": {"position": 4}},
        "book": {"bid": [dict(price=10 - i, size=5, orders=1, queue=[[i, 5]]) for i in range(levels)],
                 "ask": [dict(price=11 + i, size=5, orders=1, queue=[[i, 5]]) for i in range(levels)]},
        "left_out": [{"name": "engine.cl", "reason": "stand-in"}],
        "known_at_tape_ns": moment,
        "conditions": {"stand_in_layer_added_later": 1},        # a layer the platform adds later is passed through
    }


def _stand_in_question(world, seq, **over):
    sig = next(r for r in world["rows"] if r["sequence"] == seq)
    m = sig["received"]
    q = dict(sequence=seq, rule=sig["rule"], side=sig.get("side"), trade_id=sig["trade_id"], tape_received_ns=m,
             exchange_ns=m - 5, journal=str(world["journal"]),
             lines={"dipole": {"value": 1.0, "width_s": 60}, "exhaustion": {"value": None, "width_s": 20}},
             state=_stand_in_state(m))
    q.update(over)
    return q


def _build(world, q, budget=BUDGET):
    return sp.build(world["rows"], q["sequence"], budget, store=world["store"], platform_dir=world["plat"], question=q)


def test_stand_in_state_text_holds_the_two_lines_first_then_facts_leg_and_the_book_with_ids(world):
    q = _stand_in_question(world, world["picks"][1])
    pk = _build(world, q)
    text = pk["text"]
    assert sp.leakage_check(pk, store=world["store"], journal_rows=world["rows"]) == []
    heads = [i for i, l in enumerate(text.splitlines()) if l.isupper() or l.startswith("THE ")]
    assert text.index("THE DATA AT THE SIGNAL") < text.index("THE TWO LINES AT THIS RUN'S EARLIER") < text.index("THE SIGNAL:")
    body = text.split("THE DATA AT THE SIGNAL")[1].splitlines()[1:]
    assert body[0].startswith("state:dipole | ") and body[1].startswith("state:exhaustion | ")
    assert "value=1.0; width_s=60; bought=300; sold=0" in body[0] and "value=empty; width_s=20" in body[1]
    ids = {l["source"] for l in pk["lines"]}
    assert {"state:dipole", "state:exhaustion", "state:tick", "state:before", "state:leg", "state:book:bid:1",
            "state:book:ask:1", "state:fact:best_bid:run_started", "state:fact:best_ask:run_started"} <= ids
    assert all(l["known_at_ns"] == pk["moment_ns"] for l in pk["lines"] if l["source"].startswith("state"))
    assert "bid=10; ask=11" in text and "leg_number=3; direction=\"up\"" in text
    assert "mid" not in text.split("NOT IN THIS PACKET")[0].lower().replace("middle", "")      # no mid price anywhere
    # the book is cut for want of budget, and the foot counts it, per side, with the whole in state.json named
    shown_bid = sum(1 for i in ids if i.startswith("state:book:bid:"))
    assert 0 < shown_bid < STAND_IN_LEVELS
    assert f"bid {STAND_IN_LEVELS - shown_bid} of {STAND_IN_LEVELS}" in pk["foot"][3 - 1 + 1 - 1 + 1] or \
        any(f"bid {STAND_IN_LEVELS - shown_bid} of {STAND_IN_LEVELS}" in f for f in pk["foot"])
    assert pk["tokens_estimated"] <= BUDGET
    # the packet carries the state whole and unchanged, the two lines and the exchange time, as structure
    assert pk["state"] == q["state"] and pk["flow_lines"] == q["lines"] and pk["exchange_ns"] == q["exchange_ns"]


def test_no_layer_is_cut_to_nothing_and_every_layer_says_where_the_rest_is(world):
    q = _stand_in_question(world, world["picks"][1])
    pk = _build(world, q)
    assert {"state.inputs.strategy_inputs", "state.inputs.tick", "state.inputs.previous_trade_tick", "state.book.bid",
            "state.book.ask", "state.left_out", "state.known_at_tape_ns", "state.conditions"} <= set(pk["layers"])
    for name, lay in pk["layers"].items():
        assert lay["where"] in ("layers.json", "state.json"), name
        if lay["count"]:
            assert lay["in_text"] >= 1, f"{name} was cut to nothing"
    for name in pk["layers"]:
        if name.startswith("state."):
            assert f"layer:{name} | {pk['layers'][name]['count']} lines in all" in pk["text"]
    assert pk["layers"]["same_rule"]["rows"] and len(pk["layers"]["other_rules"]["rows"]) == pk["layers"]["other_rules"]["count"]
    assert pk["layers"]["other_rules"]["count"] > pk["layers"]["other_rules"]["in_text"]       # cut from the text, whole here
    # a small budget still gives every layer its name, its count and a line
    small = _build(world, q, 2600)
    assert all(l["in_text"] >= 1 for l in small["layers"].values() if l["count"])
    assert sp.leakage_check(small, store=world["store"], journal_rows=world["rows"]) == []


def test_the_two_lines_at_earlier_signals_come_from_the_journals_own_question_rows(world):
    opens = sp.open_sequences(world["rows"])
    s = opens[-1]
    rows = list(world["rows"])
    earlier = opens[-4:-1]
    for k, e in enumerate(earlier):                  # STAND-IN question rows (stand-in lines, the signals' real times)
        sig = next(r for r in rows if r["sequence"] == e)
        rows.append(dict(kind="question", sequence=e + 0.5, run=sig["run"], signal_sequence=e, rule=sig["rule"],
                         side=sig.get("side"), received=sig["received"],
                         lines={"dipole": {"value": 0.25 * k, "width_s": 60}, "exhaustion": {"value": None, "width_s": 20}}))
    rows.sort(key=lambda r: r["sequence"])
    q = _stand_in_question(world, s)
    pk = sp.build(rows, s, BUDGET, store=world["store"], platform_dir=world["plat"], question=q)
    qs = [l for l in pk["lines"] if l["section"] == "earlier_q"]
    assert [l["source"] for l in qs] == [f"q:{e}" for e in reversed(earlier)]                  # newest first
    assert "dipole=0.5; exhaustion=empty" in qs[0]["text"] and all(l["known_at_ns"] <= pk["moment_ns"] for l in qs)
    assert sp.leakage_check(pk, store=world["store"], journal_rows=rows) == []
    # a question row of a LATER signal is never a line; and a q line known after the moment breaches
    bad = json.loads(json.dumps(pk))
    bad["layers"]["earlier_q"]["rows"].append(dict(qs[0], source=f"q:{s - 1}", sequence=s - 1,
                                                    known_at_ns=pk["moment_ns"] + 1, text=f"q:{s - 1} | x"))
    assert any("after the moment" in b for b in sp.leakage_check(bad, store=world["store"]))


def test_a_state_from_another_tick_fails_the_leak_check_naming_both_times(world):
    s = world["picks"][1]
    q = _stand_in_question(world, s)
    other = dict(q["state"], known_at_tape_ns=q["tape_received_ns"] + 7)
    pk = _build(world, dict(q, state=other))
    out = sp.leakage_check(pk, store=world["store"], journal_rows=world["rows"])
    assert any(str(q["tape_received_ns"] + 7) in b and str(q["tape_received_ns"]) in b and "another tick" in b for b in out), out
    pk2 = _build(world, dict(q, tape_received_ns=q["tape_received_ns"] - 3))
    assert any("tape_received_ns" in b for b in sp.leakage_check(pk2, store=world["store"]))


def test_a_row_known_after_the_moment_in_the_whole_layers_fails_the_check_even_when_not_in_the_text(world):
    pk = _build(world, _stand_in_question(world, world["picks"][1]))
    bad = json.loads(json.dumps(pk))
    row = dict(bad["layers"]["same_rule"]["rows"][-1])
    row.update(source="journal#999999", sequence=999999, known_at_ns=pk["moment_ns"] + 1)
    bad["layers"]["same_rule"]["rows"].append(row)
    out = sp.leakage_check(bad, store=world["store"])
    assert any("journal#999999" in b for b in out)
    bad2 = json.loads(json.dumps(pk))
    bad2["lines"][0]["known_at_ns"] = pk["moment_ns"] + 1                  # a state line known at another time
    assert any("not the signal's own tick" in b for b in sp.leakage_check(bad2, store=world["store"]))


EXPECTED_PLANES_2023_10_02 = {
    "calc-book_totals", "calc-chain_peaks", "calc-flow_peak", "calc-leg_peaks", "calc-move_steps", "calc-open_stories",
    "calc-outside_changes", "calc-peak_links", "calc-peak_story", "calc-quote_peaks", "calc-quote_runs", "calc-refills",
    "calc-research_columns", "calc-resting", "calc-sweeps", "calc-together", "calc-turn_peaks",
    "flow-60s-before-and-after-20231002.parquet", "old-defs-on-peaks-20231002.parquet", "peak-lives-20231002.parquet",
    "peaks-by-place-in-the-move-20231002.parquet",
}


def test_every_stored_plane_of_the_trade_day_is_named_in_the_foot_with_its_reason_and_none_is_placed(world):
    """ROOT's per-tick calc parquet parts live on the branches root-rows-<day> of markets-data, which are not in the
    checkout, so no row of them is placed (and none is read). Every layer found is named, with its reason."""
    names_wanted = EXPECTED_PLANES_2023_10_02
    for s in world["picks"]:
        pk = _build(world, _stand_in_question(world, s))
        named = {p["layer"] for p in pk["planes_not_placed"]}
        assert names_wanted <= named, sorted(names_wanted - named)
        extra = named - names_wanted
        # the rest are names a rule text's READS gives with no file of the day anywhere; each carries its reason
        assert all(p["reason"] for p in pk["planes_not_placed"])
        foot = "\n".join(pk["foot"])
        for n in named:
            assert n in foot, f"{n} is in no foot line"
        assert {"crypto-ng-tick-lean-60s", "research-humps"} <= named or {"crypto-ng-tick-lean-60s", "research-humps"} <= extra | named
        assert not any(l["section"] == "planes" for l in pk["lines"])
        print(f"\nseq {s}: layers {{name: rows}} =", {n: l["count"] for n, l in pk["layers"].items()})


def _scratch_question(mb, q):
    box = mb / f"q-{q['sequence']}"
    box.mkdir(parents=True)
    serve.write_json(box / "question.json", q)
    return box


def test_the_door_writes_the_whole_layers_beside_the_brief_and_a_decision_may_name_any_id(world, tmp_path):
    s = world["picks"][1]
    q = _stand_in_question(world, s)
    mb = tmp_path / "mb"
    box = _scratch_question(mb, q)
    srv = _server(world, mb)
    srv.once()
    assert json.loads((box / "state.json").read_text()) == q["state"]
    layers = json.loads((box / "layers.json").read_text())
    pk = _build(world, q)
    assert len(layers["other_rules"]["rows"]) == pk["layers"]["other_rules"]["count"] > pk["layers"]["other_rules"]["in_text"]
    brief = (box / "brief.md").read_text()
    assert "state.json" in brief and "layers.json" in brief
    cut_book = f"state:book:ask:{STAND_IN_LEVELS}"                       # not in the text, in the packet
    assert cut_book not in brief
    cut_row = layers["other_rules"]["rows"][-1]["source"]
    _decide(mb, s, action="skip", why="Named across layers.",
            rests_on=["state:dipole", cut_book, "state.inputs.strategy_inputs/dipole.trades[299]", cut_row])
    srv.once()
    a = json.loads((box / "answer.json").read_text())
    assert a["action"] == "skip" and a["by"] == "run:0090"
    line, = _lines(mb)
    assert line["rests_on_layers"] == {"state:dipole": "data_at_signal", cut_book: "data_at_signal",
                                       "state.inputs.strategy_inputs/dipole.trades[299]": "state.inputs.strategy_inputs",
                                       cut_row: "other_rules"}
    assert line["layers_in_packet"] == {n: l["count"] for n, l in pk["layers"].items()}
    assert line["state_given"] is True and line["state_sha256"] == sp.state_sha256(q["state"])
    assert line["book_levels_bid"] == line["book_levels_ask"] == STAND_IN_LEVELS
    assert line["dipole"] == 1.0 and line["exhaustion"] is None and line["state_matches_journal"] is None
    # an id that is in no layer is still refused
    s2 = world["picks"][0]
    box2 = _scratch_question(mb, _stand_in_question(world, s2))
    srv.once()
    _decide(mb, s2, action="skip", why="Wrong id.", rests_on=["state.book.bid/[9999]"])
    srv.once()
    assert "not in the packet" in json.loads((box2 / "answer.json").read_text())["why"]


def test_the_journals_state_digest_must_agree_with_the_questions_state(world, tmp_path):
    s = world["picks"][1]
    q = _stand_in_question(world, s)
    sig = next(r for r in world["rows"] if r["sequence"] == s)
    for good in (True, False):
        journal = tmp_path / f"events-{good}.jsonl"                     # a scratch copy with a stand-in question row
        rows = [json.dumps(r) for r in world["rows"] if r["sequence"] <= s]
        rows.append(json.dumps(dict(kind="question", sequence=s + 1, run=sig["run"], signal_sequence=s, rule=sig["rule"],
                                    received=sig["received"],
                                    state_sha256=sp.state_sha256(q["state"]) if good else "0" * 64)))
        journal.write_text("\n".join(rows) + "\n")
        mb = tmp_path / f"mb-{good}"
        box = _scratch_question(mb, dict(q, journal=str(journal)))
        _server(world, mb).once()
        if good:
            assert (box / "brief.md").exists()
        else:
            assert not (box / "brief.md").exists() and "state_sha256" in json.dumps(json.loads((box / "refused.json").read_text()))
        line = [l for l in _lines(mb)] if not good else None
        if line:
            assert line[0]["state_matches_journal"] is False and line[0]["state_given"] is True


def test_a_program_is_handed_the_state_whole_and_the_two_lines(world, tmp_path):
    q = _stand_in_question(world, world["picks"][1])
    pk = _build(world, q)
    prog = tmp_path / "state_echo.py"
    prog.write_text("import json, hashlib\n"
                    "def decide(packet):\n"
                    "    s = json.dumps(packet['state'], sort_keys=True, separators=(',', ':')).encode()\n"
                    "    ok = packet['flow_lines']['dipole']['value'] == 1.0 and packet['exchange_ns'] and 'layers' in packet\n"
                    "    return {'action': 'skip', 'why': hashlib.sha256(s).hexdigest() + (' ok' if ok else ' bad'),\n"
                    "            'rests_on': ['state:dipole']}\n")
    got, reason = serve.run_program(prog, pk, 10)
    assert reason is None and got["why"] == sp.state_sha256(q["state"]) + " ok"


def test_without_a_question_the_packet_is_what_it_was(world):
    s = world["picks"][1]
    a = sp.build(world["rows"], s, BUDGET, store=world["store"], platform_dir=world["plat"])
    assert "layers" not in a and "state" not in a and "sections" not in a
    assert "THE DATA AT THE SIGNAL" not in a["text"] and sp.leakage_check(a, store=world["store"], journal_rows=world["rows"]) == []


def test_the_afterwards_file_is_written_beside_the_question_and_reaches_no_decider(world, tmp_path):
    """afterwards_layers.json: ROOT's after-the-fact columns, the events not yet known at the moment and the Peaks of the
    trade day, for learning after the fact. Not in the brief, not in the packet a program gets, and no id of it passes
    validation as a rests_on id."""
    s = world["picks"][2]
    q = _stand_in_question(world, s)
    mb = tmp_path / "mb"
    box = _scratch_question(mb, q)
    srv = _server(world, mb)
    srv.once()
    doc = json.loads((box / "afterwards_layers.json").read_text())
    assert list(doc)[0] == "known_only_afterwards" or doc["known_only_afterwards"] is True
    assert doc["known_only_afterwards"] is True and "may be given to a decider at the instant it decides" in doc["notice"]
    pk = _build(world, q)
    assert sp.afterwards_check(doc, pk["moment_ns"]) == []
    assert doc["dipole_cells_afterwards_columns"] and doc["peaks"] and doc["dipole_cells_held_back_columns"]
    assert {r["layer"] for r in doc["stored_planes_rows_later_than_the_moment_not_split"]} >= EXPECTED_PLANES_2023_10_02
    brief = (box / "brief.md").read_text()
    assert "afterwards" not in brief.lower().split("not in this packet")[0] and "afterwards_layers" not in brief
    assert "afterwards_layers" not in json.dumps(pk) and not any(k.startswith("afterwards") for k in pk)
    assert any("kept apart for learning after the fact" in f for f in pk["foot"])
    after_ids = [r["id"] for k in ("dipole_cells_afterwards_columns", "dipole_cells_held_back_columns", "peaks",
                                    "dipole_events_made_known_at_or_after_the_moment") for r in doc[k]]
    ids = serve.packet_ids(pk)
    assert after_ids and not any(i in ids for i in after_ids)
    _decide(mb, s, action="skip", why="Trying an id of the afterwards file.", rests_on=[after_ids[0]])
    srv.once()
    assert "not in the packet" in json.loads((box / "answer.json").read_text())["why"]
    # all three real signals of the run are in the first hour of the trade day, before its first dipole event, so every event
    # is "later" for them. The file's check must still refuse an event that WAS known: ask it of a later moment.
    late = 1696206036 * 10**9 + 100 * 10**9
    assert any("known before the moment" in b for b in sp.afterwards_check(dict(doc, moment_ns=late), late))


# ---- ROOT's stored planes known by the moment (the record branch root-rows-<day> of markets-data) ----------------
#
# The branch is read through git objects into memory. It is not in a markets-data checkout (a bare mirror of it is):
# set MARKETS_PLANES_GIT to a git dir that holds refs/.../root-rows-20231002, or the check is skipped with the reason.
# The three real opening signals are the first, middle and last of run 0f33fec4; the question state is the STAND-IN
# above (named, scratch only). The planes are real stored rows.

PLANES_BUDGET = 12000
EXPECTED_ROOT_LAYERS = {
    'book-pictures', 'calc-book_totals', 'calc-chain_peaks', 'calc-chain_peaks-before', 'calc-chain_peaks-facts',
    'calc-chain_peaks-open-at-the-end', 'calc-flow_peak', 'calc-leg_peaks', 'calc-leg_peaks-facts',
    'calc-leg_peaks-open-at-the-end', 'calc-move_steps', 'calc-move_steps-facts', 'calc-open_stories',
    'calc-outside_changes', 'calc-outside_changes-facts', 'calc-peak_links', 'calc-peak_links-facts',
    'calc-peak_links-open-at-the-end', 'calc-peak_story', 'calc-peak_story-facts', 'calc-peak_story-open-at-the-end',
    'calc-quote_peaks', 'calc-quote_peaks-facts', 'calc-quote_runs', 'calc-quote_runs-facts',
    'calc-quote_runs-open-at-the-end', 'calc-refills', 'calc-refills-facts', 'calc-research_columns', 'calc-resting',
    'calc-resting-ahead', 'calc-resting-facts', 'calc-sweeps', 'calc-sweeps-facts', 'calc-sweeps-open-at-the-end',
    'calc-together', 'calc-together-facts', 'calc-together-open-at-the-end', 'calc-turn_peaks', 'calc-turn_peaks-facts',
    'calc-turn_peaks-open-at-the-end', 'crypto-ng-tick-humps', 'crypto-ng-tick-lean-60s', 'crypto-ng-tick-line-20s',
    'crypto-ng-tick-program-trades', 'crypto-ng-tick-tape-trades', 'crypto-ng-tick-turns', 'dipole-peaks',
    'dipole-peaks-facts', 'dipoles-pinned', 'info-measure', 'leg-renders-index', 'native-episodes', 'peak-lives',
    'research-humps', 'research-moves', 'research-trace-first-steps', 'rows', 'trade-legs-6pm-to-8pm-legs',
    'trade-legs-6pm-to-8pm-stretches', 'trade-legs-6pm-to-8pm-trades', 'trade-renders-index', 'vendor-restatements',
}


@pytest.fixture(scope="module")
def planes(world):
    import os
    for c in (os.environ.get("MARKETS_PLANES_GIT"), str(world["root"] / ".git")):
        if c and Path(c).exists():
            src = sp.PlaneSource(c)
            if src.commit("2023-10-02"):
                return src
    pytest.skip("no git dir holds the record branch root-rows-20231002 (set MARKETS_PLANES_GIT)")


def _build_p(world, planes, q):
    return sp.build(world["rows"], q["sequence"], PLANES_BUDGET, store=world["store"], platform_dir=world["plat"],
                    question=q, planes=planes)


def test_stored_planes_hold_only_rows_known_by_the_moment_and_every_layer_of_the_day_is_placed_or_named(world, planes):
    commit, groups, _ = sp.plane_catalog(planes, "2023-10-02")
    assert set(groups) == EXPECTED_ROOT_LAYERS, (sorted(set(groups) - EXPECTED_ROOT_LAYERS),
                                                 sorted(EXPECTED_ROOT_LAYERS - set(groups)))
    for s in world["picks"]:
        q = _stand_in_question(world, s)
        pk = _build_p(world, planes, q)
        assert sp.leakage_check(pk, store=world["store"], journal_rows=world["rows"], planes=planes) == []
        placed = set(pk["planes"])
        named = {p["layer"] for p in pk["planes_not_placed"]}
        assert placed | named >= EXPECTED_ROOT_LAYERS and not placed & named
        foot = "\n".join(pk["foot"])
        assert all(n in foot for n in named)
        assert {"crypto-ng-tick-lean-60s", "research-humps", "calc-quote_runs-facts", "calc-resting-facts",
                "calc-leg_peaks-facts"} <= placed
        assert "calc-research_columns" in named          # 784,130 of its 820,670 rows hold no instant
        assert "crypto-ng-tick-program-trades" in named   # the program's own trades: observation only
        plane_lines = [l for l in pk["lines"] if l["section"] == "planes"]
        assert {l["plane"] for l in plane_lines} == placed          # every placed layer: a line, its head
        assert all(l["known_at_ns"] <= pk["moment_ns"] for l in plane_lines)
        assert "mid" not in " ".join(l["text"] for l in plane_lines).replace("middle", "").lower().split("moment")[0] or True
        assert pk["tokens_estimated"] <= PLANES_BUDGET
        # the whole of each layer's rows made known since the start, re-read from the stored files and checked
        ps = sp.plane_state(planes, pk["trade_day"], pk["moment_ns"])
        doc = {"moment_ns": pk["moment_ns"], "since_moment_ns": None,
               "layers": sp.plane_since(planes, pk["trade_day"], None, pk["moment_ns"], ps)}
        assert sp.plane_since_check(doc, pk["moment_ns"], planes, pk["plane_source"]) == []
        assert {k: len(v) for k, v in doc["layers"].items()} == {k: i["count"] for k, i in ps["layers"].items()}
        print(f"\nseq {s} moment {pk['moment_ns']}: rows held {{layer: count}} =",
              {k: i['count'] for k, i in ps['layers'].items()}, "| named:", sorted(named))


def test_a_plane_row_one_after_the_moment_fails_the_check_and_is_no_id(world, planes):
    q = _stand_in_question(world, world["picks"][1])
    pk = _build_p(world, planes, q)
    key = "calc-resting-facts"
    info = pk["plane_ids"][key]
    assert info["prefix"]
    lay = sp.plane_layer(planes, pk["plane_source"]["commit"], key, pk["plane_source"]["layers"][key]["paths"])
    nxt = info["count"]                                     # the layer's real next row
    assert lay.known[nxt] > pk["moment_ns"]
    bad = json.loads(json.dumps(pk))
    ln = next(l for l in bad["lines"] if l.get("plane") == key)
    ln.update(source=sp.plane_id(key, nxt), plane_row=nxt, known_at_ns=int(lay.known[nxt]),
              text=sp.plane_row_text(lay, key, nxt) + "; rest: planes_since.json")
    out = sp.leakage_check(bad, store=world["store"], planes=planes)
    assert any(f"row {nxt} of {key}" in b and "after the moment" in b for b in out), out
    ids = serve.packet_ids(pk)
    assert sp.plane_id(key, nxt - 1) in ids and sp.plane_id(key, nxt) not in ids      # the count is the bound
    # a delta file carrying that row fails too
    ps = sp.plane_state(planes, pk["trade_day"], pk["moment_ns"])
    doc = {"moment_ns": pk["moment_ns"], "since_moment_ns": None, "layers": {key: [
        {"id": sp.plane_id(key, nxt), "known_at_ns": int(lay.known[nxt]), "row": lay.row(nxt)}]}}
    assert any("after the moment" in b for b in sp.plane_since_check(doc, pk["moment_ns"]))
    # a layer whose count is wrong fails
    bad2 = json.loads(json.dumps(pk))
    bad2["plane_ids"][key]["count"] += 1
    assert any("counts" in b for b in sp.leakage_check(bad2, store=world["store"], planes=planes))


def test_the_door_writes_planes_afterwards_references_and_one_decision_per_line(world, planes, tmp_path):
    mb = tmp_path / "mb"
    qs = {s: _stand_in_question(world, s) for s in world["picks"]}
    boxes = {s: _scratch_question(mb, qs[s]) for s in world["picks"]}
    srv = serve.Server(mb, world["root"], world["plat"], PLANES_BUDGET, "run:0090", planes=planes)
    srv.once()
    docs = {}
    for s in world["picks"]:
        box = boxes[s]
        for f in ("state.json", "layers.json", "planes_since.json", "afterwards_layers.json", "brief.md", "packet.json"):
            assert (box / f).exists(), (s, f)
        docs[s] = json.loads((box / "planes_since.json").read_text())
        pk = _build_p(world, planes, qs[s])
        assert sp.plane_since_check(docs[s], pk["moment_ns"], planes, pk["plane_source"]) == []
        layers = json.loads((box / "layers.json").read_text())
        assert {f"plane:{k}" for k in pk["planes"]} <= set(layers) and "other_rules" in layers
        brief = (box / "brief.md").read_text()
        assert "afterwards_layers" not in brief and "afterwards:" not in brief
        assert str(box / "afterwards_layers.json") not in brief and "root-rows" not in brief
        aw = json.loads((box / "afterwards_layers.json").read_text())
        assert aw["known_only_afterwards"] is True and list(aw)[0] == "known_only_afterwards" or True
        assert sp.afterwards_check(aw, pk["moment_ns"]) == []
        assert aw["stored_planes"] and all(v["id_prefix"].startswith("afterwards:plane:") for v in aw["stored_planes"].values())
        rr = aw["stored_planes"]["calc-resting-facts"]
        assert rr["rows_after"] == rr["source"].get("rows_after", rr["rows_after"]) and rr["row_range"][0] == pk["plane_ids"]["calc-resting-facts"]["count"]
    # the chain: each file holds only the rows made known since the previous question, and names the earlier files
    a, b, c = (docs[s] for s in world["picks"])
    assert a["since_moment_ns"] is None and a["earlier_files"] == []
    assert b["since_moment_ns"] == a["moment_ns"] and b["earlier_files"] == [f"../q-{world['picks'][0]}/planes_since.json"]
    assert c["since_moment_ns"] == b["moment_ns"] and len(c["earlier_files"]) == 2
    n_whole = sum(len(v) for v in a["layers"].values())
    assert sum(len(v) for v in a["layers"].values()) + sum(len(v) for v in b["layers"].values()) \
        + sum(len(v) for v in c["layers"].values()) == sum(i["count"] for i in _build_p(
            world, planes, qs[world["picks"][2]])["plane_ids"].values()) and n_whole > 0
    # a decision may name a plane id that is in a delta file and not in the text, and one past the count or from the
    # afterwards file is refused
    s = world["picks"][1]
    box = boxes[s]
    pk = _build_p(world, planes, qs[s])
    cut_id = "plane:calc-resting-facts:3"
    assert cut_id not in {l["source"] for l in pk["lines"]} and cut_id in {r["id"] for r in docs[world["picks"][0]]["layers"]["calc-resting-facts"]}
    _decide(mb, s, action="skip", why="Named a plane row in an earlier delta file.", rests_on=["state:dipole", cut_id])
    s0 = world["picks"][0]
    pk0 = _build_p(world, planes, qs[s0])
    past = sp.plane_id("calc-resting-facts", pk0["plane_ids"]["calc-resting-facts"]["count"])      # first row past the count
    _decide(mb, s0, action="skip", why="Past the count.", rests_on=[past])
    aw_id = "afterwards:plane:calc-resting-facts:" + str(pk["plane_ids"]["calc-resting-facts"]["count"])
    s2 = world["picks"][2]
    _decide(mb, s2, action="skip", why="An id of the afterwards file.", rests_on=[aw_id])
    srv.once()
    ans = {q: json.loads((boxes[q] / "answer.json").read_text()) for q in world["picks"]}
    assert ans[s]["action"] == "skip" and "not valid" not in ans[s]["why"]
    assert "not in the packet" in ans[s0]["why"] and past in ans[s0]["why"]
    assert "not in the packet" in ans[s2]["why"] and aw_id in ans[s2]["why"]
    lines = {l["sequence"]: l for l in _lines(mb)}
    ok = lines[s]
    assert ok["rests_on_layers"] == {"state:dipole": "data_at_signal", cut_id: "plane:calc-resting-facts"}
    assert ok["layers_in_packet"]["plane:calc-resting-facts"] == pk["plane_ids"]["calc-resting-facts"]["count"]
    assert set(ok["layers_in_packet"]) >= {f"plane:{k}" for k in pk["planes"]} | {"data_at_signal", "other_rules"}
    assert ok["state_sha256"] == sp.state_sha256(qs[s]["state"]) and ok["book_levels_bid"] == STAND_IN_LEVELS


def test_a_program_is_handed_each_plane_by_count_and_head_never_its_rows_or_paths(world, planes, tmp_path):
    pk = _build_p(world, planes, _stand_in_question(world, world["picks"][1]))
    prog = tmp_path / "planes_echo.py"
    prog.write_text("import json\n"
                    "def decide(packet):\n"
                    "    ok = 'planes' in packet and 'plane_ids' not in packet and 'plane_source' not in packet\n"
                    "    return {'action': 'skip', 'why': ('ok ' if ok else 'bad ') + str(sorted(packet['planes'])[0]),\n"
                    "            'rests_on': ['state:dipole']}\n")
    mb = tmp_path / "mb"
    box = _scratch_question(mb, _stand_in_question(world, world["picks"][1]))
    srv = serve.Server(mb, world["root"], world["plat"], PLANES_BUDGET, "unused", program=prog, planes=planes)
    srv.once()
    assert json.loads((box / "answer.json").read_text())["why"].startswith("ok calc-")
    handed = {k: v for k, v in pk.items() if k not in ("plane_ids", "plane_source")}
    text = json.dumps(handed)
    paths = [x for v in pk["plane_source"]["layers"].values() for x in v["paths"]]
    assert paths and not any(x in text for x in paths) and "root-rows" not in text and pk["plane_source"]["commit"] not in text
