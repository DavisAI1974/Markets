"""Stage 7d: the orders and fills of the saved paper runs in the graph, checked against the records
and against the counts RUNNING_LIST.md section D gives. Real records only; writes go to a scratch graph.
Nothing is scored: no result, no right/wrong tally, no profit figure."""

import json

import pytest

from tools.kgraph import ingest_paper as ip
from tools.kgraph.store import GraphStore

from .realrecords import data_root

PLATFORM = "/home/user/paper-trading-platform"
RUN1, CLOSE, RUN2 = "orders-20261124T010517Z", "closeout-20261124T011335Z", "feed-only-20261124T011440Z"


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = data_root()
    store = GraphStore(root, graph_dir=tmp_path_factory.mktemp("graph"))
    for f in (RUN1, CLOSE, RUN2):
        if not (root / ip.LIVE / f).is_dir():
            pytest.skip(f"{f} is not in this markets-data checkout")
    return root, store, ip.paper(store, PLATFORM)


def _jl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_counts_of_run_1_as_the_ledger_and_receipt_hold_them(made):
    root, store, rep = made
    d = root / ip.LIVE / RUN1
    ledger = _jl(d / "ledger.jsonl")
    receipt = json.loads((d / "receipt.json").read_text(encoding="utf-8"))
    orders = [o for t in ledger for o in t["orders"]] + receipt["flatten_orders"]
    r = rep[RUN1]
    assert len(ledger) == 62 and r["intended_orders"] == len(orders) == 120
    assert r["sent"] == sum(o["sent"] for o in orders) == 19
    ns = [o for o in orders if not o["sent"]]
    assert len(ns) == 101
    assert sum(r["not_sent"].values()) == 101
    assert r["not_sent"]["refused at the dry run"] + r["not_sent"]["flatten refused at the dry run"] == \
        sum(o["reason"].startswith("before the submit") for o in ns) == 44      # 43 buys + the flatten
    assert r["not_sent"]["close held back: its open was not confirmed by fills"] == 34
    assert r["not_sent"]["cut off by the order budget stop"] == 23
    filled = [o for o in orders if o["sent"] and o["outcome"]["fills"]]
    assert r["fills"] == len(filled) == 13
    errs = [o for o in orders if o["sent"] and o["outcome"]["order_id"] is None]
    assert len(errs) == 6
    assert len(r["unplaced"]["sent, answered with an error, no broker order id (counted as sent)"]) == 6
    assert r["rule_versions"] == len({t["strategy"] for t in ledger}) == 13
    assert receipt["counts"]["intents"] and receipt["trades_in_ledger"] == 62


def test_counts_of_run_2_and_the_closeout(made):
    root, store, rep = made
    ledger = _jl(root / ip.LIVE / RUN2 / "ledger.jsonl")
    n = sum(len(t["orders"]) for t in ledger)
    assert len(ledger) == 183 and n == 364
    assert rep[RUN2]["intended_orders"] == 364 and rep[RUN2]["sent"] == 0 and rep[RUN2]["fills"] == 0
    c = rep[CLOSE]
    assert c["intended_orders"] == 1 and c["sent"] == 0       # the buy of 13, refused
    revised = c["orders_revised_by_cancel"]
    assert len(revised) == 5                                   # six cancels sent, five accepted
    assert len(c["unplaced"]["cancel that could not be put on an order"]) == 1
    for oid in revised:
        n_ = store.node(oid)
        assert n_["rev"] == 1          # built across all the run folders first: written once, in its final wording
        assert n_["attrs"]["statuses_seen"][-1]["status"] == "Cancel Requested"
        assert len(n_["attrs"]["statuses_seen"]) > 1


def test_every_fill_has_one_fills_link_to_a_sent_order(made):
    root, store, rep = made
    fills = store.nodes("Fill")
    assert len(fills) == 13
    links = store.edges("FILLS")
    for f in fills:
        mine = [e for e in links if e["src"] == f["id"]]
        assert len(mine) == 1
        o = store.node(mine[0]["dst"])
        assert o["type"] == "Order" and o["attrs"]["sent"] is True and o["id"] == f["attrs"]["order"]
        assert f["attrs"]["price_is"].startswith("what the sandbox reported; not a result")


def test_every_order_is_placed_or_reported(made):
    root, store, rep = made
    placed = {e["src"] for e in store.edges("PLACED_BY")}
    reported = {o for r in rep.values() for k, v in r["unplaced"].items() if k.startswith("order with no PLACED_BY") for o in v}
    for o in store.nodes("Order"):
        assert o["id"] in placed or o["id"] in reported
        assert (o["id"] in placed) == bool(o["attrs"].get("rule_version"))
    assert len(reported) == 2 and all(store.node(o)["attrs"]["leg"] == "flatten" for o in reported)
    for e in store.edges("PLACED_BY"):
        rv = store.node(e["dst"])
        assert rv["attrs"]["entity_kind"] == "rule version"
        assert {x["type"] for x in store.edges("DERIVED_FROM") if x["src"] == rv["id"] for _ in [0]} == {"DERIVED_FROM"}
        assert not [x for x in store.edges() if x["dst"] == rv["id"] and store.node(x["src"])["type"] == "Claim"]


def test_nothing_carries_a_mid_a_verdict_or_a_cost(made):
    root, store, rep = made
    for n in store.nodes():
        assert not [k for k in n["attrs"] if "mid" in k.lower()], n["id"]
    text = json.dumps([n["attrs"] for n in store.nodes("Order") + store.nodes("Fill")])
    for word in ('"verdict"', '"right"', '"wrong"', "fee-calculation", "buying-power"):
        assert word not in text


def test_the_13_fills_beside_the_market(made):
    root, store, rep = made
    mf = _jl_all(root / ip.LIVE / RUN2 / ip.FILLS_FILE)
    assert len(mf) == 13
    for f in store.nodes("Fill"):
        a = f["attrs"]
        for k in ("before", "after"):
            assert a[f"market_{k}_bid"] is not None and a[f"market_{k}_offer"] is not None
        assert a["market_source"].endswith(ip.FILLS_FILE)
        m = mf[a["market_entry"]]
        assert m["order_id"] == a["broker_order_id"] and m["fill_price"] == a["price"]
        px = float(a["price"])
        sides = {a["market_before_bid"], a["market_before_offer"], a["market_after_bid"], a["market_after_offer"]}
        # reported as the record measured it; a fill that does not sit on one of the four is not adjusted
        assert px in sides, (f["id"], px, sides)
        assert px in (a["market_before_bid"], a["market_before_offer"]) or px in (a["market_after_bid"], a["market_after_offer"])


def _jl_all(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_each_node_names_its_line_and_the_graph_is_whole(made):
    root, store, rep = made
    for n in store.nodes("Order") + store.nodes("Fill"):
        a = n["attrs"]
        assert store.node(a["source"])["type"] == "Source"
        assert a["run"] in a["source"] and a["trial"] == ip.trial_id(a["run"])
        assert isinstance(a["line"], list) and a["line"]
    assert store.check_all() == []


def test_a_second_run_adds_nothing(made):
    root, store, rep = made
    before = store.counts()
    again = ip.paper(GraphStore(root, graph_dir=store.dir), PLATFORM)
    for f, r in again.items():
        assert r["write"]["new"] == 0 and r["write"]["revised"] == 0, (f, r["write"])
    after = GraphStore(root, graph_dir=store.dir)
    assert after.counts() == before and after.check_all() == []


def test_a_return_to_an_earlier_wording_is_the_next_revision(tmp_path):
    """The real graph holds Orders that went from one wording to another (a close-out's cancel, rev 1 then
    rev 2). Their real lines are copied into a scratch graph, and the real first wording is written again:
    the store (no `_fresh` any more) keeps it as rev 3, and all three lines stay. Built from real lines;
    nothing is invented."""
    root = data_root()
    real = GraphStore(root)
    two = next((h for h in (real.history(n["id"]) for n in real.nodes("Order"))
                if len(h) == 2 and h[0]["attrs"] != h[1]["attrs"]), None)
    if two is None:
        pytest.skip("no Order of the real graph has two different wordings")
    scratch = GraphStore(root, graph_dir=tmp_path / "graph")
    (scratch.dir / "nodes").mkdir(parents=True)
    for name, lines in (("Order", two), ("Source", real.history(two[0]["attrs"]["source"]))):
        (scratch.dir / "nodes" / f"{name}.jsonl").write_text(
            "".join(json.dumps(l, ensure_ascii=False, sort_keys=True) + "\n" for l in lines), encoding="utf-8")
    scratch = GraphStore(root, graph_dir=tmp_path / "graph")
    res = scratch.write([{"id": two[0]["id"], "type": "Order", "attrs": two[0]["attrs"]}],
                        written_by="code:test@checked")
    assert res["revised"] == 1
    h = scratch.history(two[0]["id"])
    assert [l["rev"] for l in h] == [1, 2, 3] and h[2]["attrs"] == two[0]["attrs"] and h[1]["attrs"] == two[1]["attrs"]
