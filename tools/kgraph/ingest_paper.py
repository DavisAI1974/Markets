"""Stage 7d: each order and each fill of the paper runs becomes a node, linked to its rule version.

  python3 -m tools.kgraph.ingest_paper --data <markets-data checkout> --platform <paper-trading-platform checkout>
        [--graph-dir <scratch>]

Reads only the saved records in markets-data paper-trading-20261123/live-runs/<folder>/ (no run is made,
no sign-in, no network, no order). Every node says where it came from on its own line: `source` (the
Source id of the file), `line` (the 1-based line numbers of that file it was put together from), `run`
(the folder name) and `trial` (the experiment trial id of the folder, the same id tools/exp_dag.py makes).

  Order        one for each INTENDED order the runner wrote, sent or not (orders.jsonl `intent` line),
               tied by its `trade` attr to the paper trade of the ledger (no node for the trade).
               The quote the rule acted on is two fields, quote_bid and quote_offer, as stored.
  Fill         one for each fill the broker reported (orders.jsonl `fill` line), with the feed's own
               prints before and after it from fills-beside-the-market.json where that file has the fill.
  rule version Entity `rulever:<strategy>@<commit10>`, DERIVED_FROM the Commit of the run's code.
               It is not linked to any Claim: no such link is in the record.

Nothing is scored, averaged, ranked or labelled. No mid price and no cost is computed or stored; the
ledger's own "right"/"wrong" word is not copied. The broker answers' fee and buying-power figures are
not read at all. Only added to: a second run writes nothing new.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ingest_agent_runs import PAPER
from .sources import REPOS, code_stamp, commit_node, link, source_id, source_node
from .store import GraphStore, sha

WRITER = "tools.kgraph.ingest_paper"
LIVE = f"{PAPER}/live-runs"
FILLS_FILE = "fills-beside-the-market.json"
PLATFORM_REPO = "paper-trading-platform"
PRICE_IS = ("what the sandbox reported; not a result (the sandbox fills at the market as it is now, "
            "its own feed is 900 seconds old)")


def trial_id(folder: str) -> str:
    """The id tools/exp_dag.py gives the trial of this key."""
    return "exp-" + sha(["key", f"paper-run:{folder}"])


def order_id(folder: str, ext: str) -> str:
    return f"order:{folder}:{ext}"


def fill_id(folder: str, broker_order_id, n: int) -> str:
    return f"fill:{folder}:{broker_order_id}:{n}"


def rulever_id(strategy: str, commit: str) -> str:
    return f"rulever:{strategy}@{commit[:10]}"


def _lines(path: Path) -> list:
    """[(1-based line number, object)] of a JSON-lines file; the numbers are the file's own."""
    out = []
    with path.open(encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            if raw.strip():
                out.append((n, json.loads(raw)))
    return out


def why_not_sent(role: str, reason: str) -> str:
    """The name of the group a reason belongs to (the reason itself stays on the Order as stored)."""
    if reason.startswith("before the submit"):
        return "flatten refused at the dry run" if role == "flatten" else "refused at the dry run"
    if reason.startswith("its open was not confirmed"):
        return "close held back: its open was not confirmed by fills"
    if reason.startswith("run stopping"):
        return "cut off by the order budget stop"
    if reason.startswith("no --orders flag"):
        return "written, none sent: no --orders flag"
    return reason


def _answer(x: dict) -> dict:
    """What a response said about itself, for an error; nothing of a successful answer but its warnings."""
    body = x.get("body")
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        e = body["error"]
        return {"error_code": e.get("code"), "error_message": e.get("message"),
                "errors": [{"code": s.get("code"), "message": s.get("message")} for s in e.get("errors") or []]}
    if isinstance(body, dict) and isinstance(body.get("data"), dict) and "warnings" in body["data"]:
        return {"warnings": body["data"]["warnings"]}
    if x.get("status", 200) >= 300:
        return {"answer_text": (x.get("body_text") or "")[:300]}
    return {}


def _scan(lines: list) -> dict:
    """Walk orders.jsonl once, in order, and give each external identifier the lines that belong to it.

    The runner works one order at a time: its dry-run requests come just BEFORE its intent line; for a
    sent order, its submit, reads, fills and outcome follow the intent line up to the outcome line."""
    by, pending, cur, loose = {}, [], None, {"dry_run_without_intent": []}
    for n, x in lines:
        k, path = x["kind"], x.get("path") or ""
        if k in ("request", "response") and path.endswith("/orders/dry-run"):
            pending.append((n, x))
        elif k == "intent":
            rec = {"intent": (n, x), "dry": pending, "post": [], "get": [], "lookup": [], "fills": [],
                   "outcome": None, "notes": []}
            pending = []
            by[x["external_identifier"]] = rec
            cur = rec if x["sent"] else None
        elif cur is not None:
            if k in ("request", "response") and x["method"] == "POST" and path.endswith("/orders"):
                cur["post"].append((n, x))
            elif k in ("request", "response") and x["method"] == "GET" and path.rsplit("/", 1)[-1].isdigit():
                cur["get"].append((n, x))
            elif k in ("request", "response") and x["method"] == "GET":
                cur["lookup"].append((n, x))
            elif k == "note":
                cur["notes"].append((n, x))
            elif k == "fill" and x["external_identifier"] == cur["intent"][1]["external_identifier"]:
                cur["fills"].append((n, x))
            elif k == "outcome" and x["external_identifier"] == cur["intent"][1]["external_identifier"]:
                cur["outcome"] = (n, x)
                cur = None
    loose["dry_run_without_intent"] = [n for n, _ in pending]
    by["__loose__"] = loose
    return by


def _dry_run(pairs: list) -> list:
    out, req = [], None
    for n, x in pairs:
        if x["kind"] == "request":
            req = (n, x)
        else:
            e = {"attempt": x.get("attempt"), "request_line": req[0] if req else None, "response_line": n,
                 "http_status": x["status"]}
            e.update(_answer(x))
            out.append(e)
    return out


def _http(pairs: list, what: str) -> tuple[list, list]:
    """(statuses the broker said, answers that were not 2xx), each with its line."""
    said, errors = [], []
    for n, x in pairs:
        if x["kind"] != "response":
            continue
        if 200 <= x["status"] < 300:
            d = (x.get("body") or {}).get("data") or {}
            st = (d.get("order") or {}).get("status") if "order" in d else d.get("status")
            if st is not None:
                said.append({"status": st, "via": what(x), "line": n})
        else:
            errors.append({"line": n, "http_status": x["status"], "what": what(x), **_answer(x)})
    return said, errors


def _build_orders(folder: str, src: dict, lines: list, ledger: list, rule_commit: str | None) -> tuple[dict, dict]:
    """(orders by id, what could not be placed)."""
    scan = _scan(lines)
    loose = scan.pop("__loose__")
    led = {}
    for ln, t in ledger:
        for o in t["orders"]:
            led[o["external_identifier"]] = (ln, t, o)
    orders, unplaced = {}, {"dry_run_lines_without_an_intent": loose["dry_run_without_intent"],
                            "ledger_orders_without_an_intent": [e for e in led if e not in scan]}
    for ext, rec in scan.items():
        iln, it = rec["intent"]
        lines_used = [iln] + [n for n, _ in rec["dry"] + rec["post"] + rec["get"] + rec["lookup"] + rec["fills"]]
        a = {"run": folder, "trial": trial_id(folder), "order_ref": ext, "strategy": it.get("strategy"),
             "trade": it.get("trade_id"), "leg": it["role"], "action": it["action"], "quantity": it["quantity"],
             "symbol": it.get("symbol"), "sent": it["sent"], "reason_in_intent": it["reason"],
             "intent_t_ns": it["t_ns"], "dry_run": _dry_run(rec["dry"]), "intent_line": iln,
             "source": src["orders.jsonl"]}
        if it.get("note"):
            a["note"] = it["note"]
        if not it["sent"]:
            a["not_sent_reason"] = it["reason"]
            a["not_sent_group"] = why_not_sent(it["role"], it["reason"])
        ea = it.get("event_at")
        a["quote_bid"] = ea["bid"] if ea else None
        a["quote_offer"] = ea["offer"] if ea else None
        a["signal_feed_time_ns"] = ea["feed_time_ns"] if ea else None
        a["signal_place"] = ea["place"] if ea else None
        a["signal_sequence"] = ea["sequence"] if ea else None
        if ext in led:
            ln, t, lo = led[ext]
            a["ledger_source"], a["ledger_line"], a["reason_in_ledger"] = src["ledger.jsonl"], ln, lo["reason"]
        if rec["post"]:
            reqs = [(n, x) for n, x in rec["post"] if x["kind"] == "request"]
            a["send_t_ns"] = reqs[0][1]["t_ns"] if reqs else None
            a["submit_request_lines"] = [n for n, _ in reqs]
        statuses = []
        post_said, post_err = _http(rec["post"], lambda x: "answer to the submit")
        get_said, get_err = _http(rec["get"], lambda x: "read of the order")
        statuses = sorted(post_said + get_said, key=lambda s: s["line"])
        if rec["outcome"]:
            oln, ox = rec["outcome"]
            o = ox["outcome"]
            lines_used.append(oln)
            a.update({"broker_order_id": o.get("order_id"), "outcome_line": oln, "outcome_confirmed": o.get("confirmed"),
                      "filled_quantity": o.get("filled_quantity"), "polls": o.get("polls"), "lookup": o.get("lookup")})
            if o.get("status_as_said") is not None:
                statuses.append({"status": o["status_as_said"], "via": "outcome the runner wrote", "line": oln})
        a["statuses_seen"] = statuses
        a["http_errors"] = sorted(post_err + get_err, key=lambda s: s["line"])
        if it["sent"] and a.get("broker_order_id") is None:
            a["broker_order_id"] = None
        if rule_commit and it.get("strategy"):
            a["rule_version"] = rulever_id(it["strategy"], rule_commit)
        a["line"] = sorted(lines_used)
        orders[order_id(folder, ext)] = {"attrs": a, "fills": rec["fills"], "ext": ext}
    return orders, unplaced


def _order_node(oid: str, attrs: dict) -> dict:
    return {"id": oid, "type": "Order", "attrs": attrs}


def _fill_nodes(folder: str, src: dict, orders: dict, market: dict, market_src: str | None) -> tuple[list, list, dict]:
    nodes, edges, miss = [], [], {"fills_not_in_the_market_file": []}
    for oid, o in orders.items():
        for n, (ln, x) in enumerate(o["fills"], 1):
            f = x["fill"]
            fid = fill_id(folder, x["order_id"], n)
            a = {"run": folder, "trial": trial_id(folder), "fill_ref": f["fill_id"], "price": f["fill_price"],
                 "quantity": f["quantity"], "filled_at": f["filled_at"], "leg_action": f["leg_action"],
                 "symbol": f.get("symbol"), "venue": f.get("venue"), "order": oid, "broker_order_id": x["order_id"],
                 "print_acted_on_bid": x.get("bid_at_print"), "print_acted_on_offer": x.get("offer_at_print"),
                 "price_is": PRICE_IS, "source": src["orders.jsonl"], "line": [ln]}
            m = market.get(x["order_id"])
            if m is not None and market_src:
                b, af = m["feed_print_before_the_fill"], m["feed_print_after_the_fill"]
                a.update({"market_before_time_utc": b["market_time_utc"], "market_before_price": b["price"],
                          "market_before_bid": b["bid"], "market_before_offer": b["offer"], "market_before_side": b["side"],
                          "market_after_time_utc": af["market_time_utc"], "market_after_price": af["price"],
                          "market_after_bid": af["bid"], "market_after_offer": af["offer"], "market_after_side": af["side"],
                          "market_source": market_src, "market_entry": m["_index"]})
            else:
                miss["fills_not_in_the_market_file"].append(fid)
            nodes.append({"id": fid, "type": "Fill", "attrs": a})
            edges.append(link("FILLS", fid, oid))
            edges.append(link("DERIVED_FROM", fid, src["orders.jsonl"], key=f"line {ln}", line=ln))
            if m is not None and market_src:
                edges.append(link("DERIVED_FROM", fid, market_src, key=f"entry {m['_index']}", entry=m["_index"]))
    return nodes, edges, miss


def _cancel_requests(lines: list, broker_id) -> list:
    """The DELETE calls of the close-out aimed at one order, as stored."""
    out, req = [], None
    for n, x in lines:
        if x["kind"] in ("request", "response") and x.get("method") == "DELETE" \
                and (x.get("path") or "").rsplit("/", 1)[-1] == str(broker_id):
            if x["kind"] == "request":
                req = n
            else:
                out.append({"attempt": x.get("attempt"), "request_line": req, "response_line": n,
                            "http_status": x["status"]})
    return out


def _probes(folder: Path) -> dict:
    p = folder / "dry-run-probe.jsonl"
    if not p.exists():
        return {}
    ls = _lines(p)
    asked = [x["body"]["legs"][0] for _, x in ls if x["kind"] == "request" and (x.get("path") or "").endswith("/dry-run")]
    answered = [x["status"] for _, x in ls if x["kind"] == "response" and (x.get("path") or "").endswith("/dry-run")]
    return {"dry-run-probe.jsonl: no node (no external identifier, no order intended or sent; dry runs only)":
            [{"legs": a, "http_status": s} for a, s in zip(asked, answered)]}


def paper(store: GraphStore, platform_dir: str | None = None) -> dict:
    """Every folder of live-runs, in the order they were made; one store.write for each folder.
    Returns, per folder, the counts it made and what it could not place."""
    root, by = store.data_root, code_stamp(WRITER)
    folders = sorted((p for p in (root / LIVE).iterdir() if p.is_dir()), key=lambda p: p.name.rsplit("-", 1)[-1])
    # the fills file sits beside the feed-only recording but holds the fills of the run with orders
    market, market_src, market_rel = {}, None, None
    for p in folders:
        if (p / FILLS_FILE).exists():
            market_rel = str((p / FILLS_FILE).relative_to(root))
            for i, m in enumerate(json.loads((p / FILLS_FILE).read_text(encoding="utf-8"))):
                market[m["order_id"]] = dict(m, _index=i)
            market_src = source_id("markets-data", market_rel)
    built: dict = {}      # broker order id -> (order id, attrs): what a later cancel revises
    report: dict = {}
    # Every folder is built first (a close-out's cancels are added to the orders of an EARLIER run), then
    # each node is written once, in its final wording: a second call writes nothing, and a real change,
    # a return to an earlier wording included, is the next revision.
    batches: list = []    # (folder name, rep, nodes, edges)
    order_node_of: dict = {}
    for folder in folders:
        name = folder.name
        sources = {f.name: source_node("markets-data", root, str(f.relative_to(root)))
                   for f in sorted(folder.iterdir()) if f.is_file()}
        src = {k: v["id"] for k, v in sources.items()}
        nodes, edges = list(sources.values()), []
        rep = {"intended_orders": 0, "sent": 0, "not_sent": {}, "fills": 0, "rule_versions": 0, "unplaced": {}}
        report[name] = rep
        if "orders.jsonl" not in src:
            rep["unplaced"]["no orders.jsonl in the folder"] = sorted(src)
            batches.append((name, rep, nodes, edges))
            continue
        commit = None
        if (folder / "receipt.json").exists():
            commit = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))["code_commit"]
        cnode = None
        if commit and platform_dir:
            try:
                cnode = commit_node(PLATFORM_REPO, platform_dir, commit)
            except RuntimeError:
                rep["unplaced"]["code commit not in the local paper-trading-platform checkout"] = [commit]
        elif commit:
            rep["unplaced"]["no paper-trading-platform checkout given"] = [commit]
        lines = _lines(folder / "orders.jsonl")
        ledger = _lines(folder / "ledger.jsonl") if (folder / "ledger.jsonl").exists() else []
        orders, unplaced = _build_orders(name, src, lines, ledger, commit if cnode else None)
        rep["unplaced"].update({k: v for k, v in unplaced.items() if v})
        if cnode:
            nodes.append(cnode)
        versions = {o["attrs"]["rule_version"]: o["attrs"]["strategy"] for o in orders.values() if o["attrs"].get("rule_version")}
        for rv, strat in sorted(versions.items()):
            nodes.append({"id": rv, "type": "Entity", "attrs": {
                "name": f"{strat} at {commit[:10]}", "entity_kind": "rule version", "strategy": strat,
                "commit": commit, "repo": REPOS[PLATFORM_REPO], "run": name, "trial": trial_id(name)}})
            edges.append(link("DERIVED_FROM", rv, cnode["id"]))
        rep["rule_versions"] = len(versions)
        order_nodes = []
        for oid, o in orders.items():
            a = o["attrs"]
            order_nodes.append(_order_node(oid, a))
            order_node_of[oid] = order_nodes[-1]
            edges.append(link("DERIVED_FROM", oid, src["orders.jsonl"], key=f"line {a['intent_line']}", line=a["intent_line"]))
            if a.get("rule_version"):
                edges.append(link("PLACED_BY", oid, a["rule_version"]))
            else:
                why = ("no rule: the runner's own flatten" if a["leg"] == "flatten"
                       else "no code commit for the run" if not cnode else "no strategy on the intent")
                rep["unplaced"].setdefault(f"order with no PLACED_BY link ({why})", []).append(oid)
            rep["intended_orders"] += 1
            if a["sent"]:
                rep["sent"] += 1
                if a.get("broker_order_id") is None:
                    rep["unplaced"].setdefault("sent, answered with an error, no broker order id (counted as sent)", []).append(oid)
            else:
                rep["not_sent"][a["not_sent_group"]] = rep["not_sent"].get(a["not_sent_group"], 0) + 1
            if a.get("broker_order_id") is not None:
                built[a["broker_order_id"]] = (oid, a)
        if commit:
            r = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
            for fo in r.get("flatten_orders") or []:
                if order_id(name, fo["external_identifier"]) not in orders:
                    rep["unplaced"].setdefault("receipt flatten order with no intent line in orders.jsonl", []).append(fo["external_identifier"])
        fnodes, fedges, miss = _fill_nodes(name, src, orders, market, market_src)
        rep["fills"] = len(fnodes)
        if miss["fills_not_in_the_market_file"]:
            rep["unplaced"]["fill with no entry in the market file"] = miss["fills_not_in_the_market_file"]
        if fnodes and market_rel:
            nodes.append(source_node("markets-data", root, market_rel))
        # the cancels of the close-out: a new revision of the order each one cancels
        for n, x in [(n, x) for n, x in lines if x["kind"] == "cancel"]:
            bid = x["order"]["order_id"]
            hit = built.get(bid)
            if hit is None or x["answer"] is None:
                rep["unplaced"].setdefault("cancel that could not be put on an order", []).append(
                    {"line": n, "broker_order_id": bid, "answered": x["answer"] is not None,
                     "in_the_graph": hit is not None, "cancel_http": _cancel_requests(lines, bid)})
                continue
            oid, a = hit
            a2 = dict(a, statuses_seen=a["statuses_seen"] + [
                {"status": x["answer"]["data"]["status"], "via": "answer to the cancel (close-out)", "line": n,
                 "source": src["orders.jsonl"], "run": name}],
                cancel_http=_cancel_requests(lines, bid), cancel_line=n, cancel_source=src["orders.jsonl"])
            order_node_of[oid]["attrs"] = a2          # the same node, in the batch of the run that made it
            built[bid] = (oid, a2)
            rep.setdefault("orders_revised_by_cancel", []).append(oid)
        rep["unplaced"].update(_probes(folder))
        nodes += order_nodes + fnodes
        edges += fedges
        batches.append((name, rep, nodes, edges))
    for name, rep, nodes, edges in batches:
        rep["write"] = store.write(nodes, edges, written_by=by)
    # Greg, 2026-11-24: nothing new is tied to a tastytrade platform issue. The runs' own orders, fills and
    # files were made on the sandbox and its feed: they are marked, so that nothing new can rest on them.
    from . import platform_scope
    platform_scope.mark(store, None)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--platform", help="a paper-trading-platform checkout, for the runs' code commits")
    ap.add_argument("--graph-dir", help="a scratch folder to write the graph to (checks)")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    for folder, rep in paper(store, a.platform).items():
        print(folder, json.dumps(rep, indent=1, ensure_ascii=False))
    print("graph:", store.counts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
