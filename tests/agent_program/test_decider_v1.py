"""decider_v1 on the real packets of run 036ed575 (the first seconds after 6:00 pm Eastern, trade day 2023-10-02).
No engine, no tape run: the journal is read from its record branch, the packets are built by the packet's own code.
Skipped with the reason when a checkout or the ref is missing."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from tools.decider.programs.decider_v1 import TAKE_WHY, decide
from tools.kgraph import packet as dp
from tools.kgraph import signal_packet as sp
from tools.kgraph.store import GraphStore

from .realrecords import data_root

RUN = "036ed57524584afdaeb0bc60be6aaa71"
REF = f"origin/paper-runs/{RUN}"
PLATFORM = Path("/home/user/paper-trading-platform")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = data_root()
    if not PLATFORM.exists():
        pytest.skip(f"no paper-trading-platform checkout at {PLATFORM}")
    r = subprocess.run(["git", "-C", str(root), "show", f"{REF}:paper-trading/{RUN}/events.jsonl"],
                       capture_output=True)
    if r.returncode != 0:
        pytest.skip(f"the ref {REF} is not in the markets-data checkout")
    path = tmp_path_factory.mktemp("j") / "events.jsonl"
    path.write_bytes(r.stdout)
    rows = sp.journal_from_file(path)
    store = GraphStore(root)
    packets = [sp.build(rows, q, 3000, store=store, platform_dir=PLATFORM) for q in sp.open_sequences(rows)]
    return {"packets": packets, "store": store}


def _valid(answer, packet):
    assert set(answer) == {"action", "why", "rests_on"}
    assert answer["action"] in ("take", "skip")
    assert isinstance(answer["why"], str) and answer["why"] and "\n" not in answer["why"]
    ids = {l["source"] for l in packet["lines"]}
    assert answer["rests_on"] and set(answer["rests_on"]) <= ids


def test_every_opening_signal_gets_a_valid_pure_answer(world):
    assert world["packets"]
    for p in world["packets"]:
        before = json.dumps(p, sort_keys=True)
        a = decide(p)
        _valid(a, p)
        assert decide(p) == a
        assert json.dumps(p, sort_keys=True) == before          # the packet is not changed
        if a["action"] == "take":
            assert a["why"] == TAKE_WHY or a["why"].startswith(TAKE_WHY)


def test_a_packet_with_its_lines_removed_is_the_plain_take(world):
    for p in world["packets"][:5]:
        q = copy.deepcopy(p)
        q["lines"] = []
        a = decide(q)
        assert a["action"] == "take" and a["why"].startswith(TAKE_WHY)


def test_unreadable_packets_never_raise(world):
    for bad in (None, {}, {"lines": None}, {"lines": [None, 3]}, {"lines": [{"text": 5, "source": "x"}]},
                {"lines": [{"section": "signal", "text": "x", "source": "s"}]}, "text", 7):
        a = decide(bad)
        assert a["action"] == "take" and a["why"].startswith(TAKE_WHY)


def test_the_divergence_read_on_real_dipole_lines(world):
    """Real dipole events of the graph put into a real packet of a with-the-move rule, to exercise the reading of
    a dipole line. The pairing is not a real moment; only the line's own numbers decide the expected answer."""
    store = world["store"]
    base = next(p for p in world["packets"] if p["rule"] == "CL03"
                and "side=buy" in next(l for l in p["lines"] if l["section"] == "signal")["text"])
    nodes = [n for n in store.nodes("DipoleEvent")
             if n["attrs"]["trade_day"] == base["trade_day"]]
    against = next(n for n in nodes if n["attrs"]["pinned"]["our_flow_sold_20s_after"] > 0
                   and n["attrs"]["pinned"]["our_flow_bought_20s_after"] == 0)
    withit = next(n for n in nodes if n["attrs"]["pinned"]["our_flow_bought_20s_after"] > 0
                  and n["attrs"]["pinned"]["our_flow_sold_20s_after"] == 0)
    for node, want in ((against, "skip"), (withit, "take")):
        q = copy.deepcopy(base)
        q["lines"] = q["lines"] + [{"section": "dipoles", "source": node["id"], "sequence": None, "run": None,
                                    "known_at_ns": dp._known_ns(node), "row_kind": "dipole",
                                    "text": dp._line(node, {}, q["moment_ns"])}]
        a = decide(q)
        _valid(a, q)
        assert a["action"] == want
        if want == "skip":
            assert a["why"].startswith("[divergence]") and node["id"] in a["rests_on"]
