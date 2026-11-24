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
        pk = sp.build(world["rows"], s, BUDGET, store=world["store"], platform_dir=world["plat"])
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

    def breaching(rows, sequence, budget, store, platform_dir):
        pk = sp.build(rows, sequence, budget, store=store, platform_dir=platform_dir)
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
        "wall_ms_question_to_decision", "answered_by", "skip_reason"}


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
