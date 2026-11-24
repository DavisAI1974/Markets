"""Stage 7d for the own paper platform: each run's orders and fills in the graph, each run one trial.
Real records only: the platform's run branches of markets-data (paper-runs/<id>), read with git; a run that
cannot be fetched is skipped with the reason. Writes go to a scratch graph and a scratch experiment record.
Nothing is scored: no result figure, no mid, no cost."""

import json

import pytest

from tools.exp_dag import ExpDag
from tools.kgraph import ingest_platform as ipf
from tools.kgraph.store import GraphStore

from .realrecords import data_root

RUNS = ("036ed57524584afdaeb0bc60be6aaa71", "06ce6b90c0384057997e17a22d7a4624",
        "064df1c2b58f46999f0276304c10d49e", "058313bbf2304bb0bb14aaed3315ab0e")
BANNED_WORDS = ("mid", "cost", "fee", "slippage", "profit", "result", "pnl", "score", "win", "loss")


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = data_root()
    runs = {}
    for r in RUNS:
        try:
            runs[r] = ipf.read_run(root, r)
        except RuntimeError as e:
            pytest.skip(f"paper-runs/{r} cannot be fetched: {e}")
    tmp = tmp_path_factory.mktemp("platform")
    store = GraphStore(root, graph_dir=tmp / "graph")
    dag = ExpDag(root, exp_dir=tmp / "experiments")
    reports = {r: ipf.load_run(store, dag, root, r) for r in RUNS}
    return root, store, dag, runs, reports, tmp


def _keys(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(o, list):
        for v in o:
            _keys(v, out)
    return out


def test_every_paper_order_and_fill_row_has_its_node(made):
    root, store, dag, runs, reports, tmp = made
    for r, d in runs.items():
        orders = [x for x in d["rows"] if x["kind"] == "paper order"]
        fills = [x for x in d["rows"] if x["kind"] == "fill"]
        for x in orders:
            n = store.node(ipf.order_node_id(x["order_id"]))
            assert n and n["type"] == "Order" and n["attrs"]["run"] == r
            assert n["attrs"]["journal_sequence"] == x["sequence"]
            assert n["attrs"]["reference"] == x["reference"] and n["attrs"]["received"] == x["received"]
            for k in ("bid", "ask", "limit_price", "trade_data"):
                assert n["attrs"].get(k) == x.get(k)
        for x in fills:
            n = store.node(ipf.fill_node_id(r, x["sequence"]))
            assert n and n["type"] == "Fill" and n["attrs"]["run"] == r
            assert n["attrs"]["price"] == x["fill_price"] and n["attrs"]["journal_sequence"] == x["sequence"]
            assert n["attrs"]["bid"] == x["bid"] and n["attrs"]["ask"] == x["ask"]
            assert n["attrs"]["trade_data"] == x.get("trade_data")
            assert store.node(n["attrs"]["source"])["type"] == "Source"
        assert len([n for n in store.nodes("Order") if n["attrs"]["run"] == r]) == len(orders)
        assert len([n for n in store.nodes("Fill") if n["attrs"]["run"] == r]) == len(fills)


def test_each_fill_fills_one_order_and_each_order_has_a_rule_version(made):
    root, store, dag, runs, reports, tmp = made
    fills_of = {}
    for e in store.edges("FILLS"):
        fills_of.setdefault(e["src"], []).append(e["dst"])
    for f in store.nodes("Fill"):
        assert len(fills_of[f["id"]]) == 1 and store.node(fills_of[f["id"]][0])["type"] == "Order"
    placed = {}
    for e in store.edges("PLACED_BY"):
        placed.setdefault(e["src"], []).append(e["dst"])
    for o in store.nodes("Order"):
        (rv,) = placed[o["id"]]
        n = store.node(rv)
        assert n["attrs"]["entity_kind"] == "rule version"
        assert rv == ipf.rulever_id(o["attrs"]["rule"], o["attrs"]["rule_commit"])
        targets = [store.node(e["dst"])["type"] for e in store.edges("DERIVED_FROM") if e["src"] == rv]
        assert "Commit" in targets and set(targets) <= {"Commit", "Source"}
    for e in store.edges():       # a finding is a link to a document, never to a Claim
        if store.node(e["src"])["type"] == "Entity":
            assert store.node(e["dst"])["type"] != "Claim"


def test_the_trial_counts_equal_counts_made_from_the_journal(made):
    root, store, dag, runs, reports, tmp = made
    for r, d in runs.items():
        rows = d["rows"]
        (t,) = [x for x in dag.log() if x["key"] == f"platform-run:{r}"]
        got = {m["name"]: m["value"] for m in t["metrics"]}
        # counts made directly: a trade is one (rule, trade_id) with a fill
        trades = {}
        for x in rows:
            if x["kind"] == "fill":
                trades.setdefault((x["rule"], x["trade_id"]), []).append(x)
        held = {k: sum(f["quantity"] if f["side"] == "buy" else -f["quantity"] for f in v) for k, v in trades.items()}
        want = {
            "journal_rows": len(rows),
            "signals_open": len([x for x in rows if x["kind"] == "signal" and x.get("action") == "open"]),
            "paper_orders": len([x for x in rows if x["kind"] == "paper order"]),
            "fills": len([x for x in rows if x["kind"] == "fill"]),
            "trades_opened": len([k for k, v in trades.items() if any(f["action"] == "open" for f in v)]),
            "trades_holding_no_contract_at_end": len([k for k in trades if held[k] == 0]),
            "trades_closed_by_an_administrative_fill": len(
                [k for k, v in trades.items() if any(f["action"] != "open" and f.get("trade_data") is False for f in v)]),
        }
        assert got == want
        assert list(got) == list(want)
        assert t["status"] == "recorded" and t["change"]["commit"] == d["start"]["code_commit"]
        assert t["environment"]["receipt_status"] == d["receipt"]["status"]
        assert t["environment"]["trade_day"] == "2023-10-02"
        assert "Don't use score since we didn't use anything we wanted scored" in t["note"] and "Not scored" in t["note"]


def test_a_second_load_writes_nothing_new(made):
    root, store, dag, runs, reports, tmp = made
    before, lines = store.counts(), len(dag.lines())
    again = GraphStore(root, graph_dir=store.dir)
    for r in RUNS:
        rep = ipf.load_run(again, dag, root, r)
        assert rep["graph"]["new"] == 0 and rep["graph"]["revised"] == 0, (r, rep["graph"])
    assert GraphStore(root, graph_dir=store.dir).counts() == before and len(dag.lines()) == lines


def test_no_mid_no_cost_no_result_figure(made):
    root, store, dag, runs, reports, tmp = made
    keys = set()
    for n in store.nodes("Order") + store.nodes("Fill"):
        _keys(n["attrs"], keys)
    keys |= {m["name"] for t in dag.log() for m in t["metrics"]}
    low = {k.lower() for k in keys}
    bad = sorted(k for k in low if any(w in k.split("_") or k.startswith(w + "_") for w in BANNED_WORDS))
    assert bad == [], bad
    assert "open_profit" not in keys and "highest_open_profit" not in keys
    assert store.check_all() == []
