"""Stage 7d for the own paper platform: each run's orders and fills become nodes, each run one trial.

  python3 -m tools.kgraph.ingest_platform --data <markets-data checkout> --run <run id> [--run <run id> ...]
        [--platform <paper-trading-platform checkout>] [--graph-dir <scratch>] [--exp-dir <scratch>]

Reads records with git only. Each run of the platform is its own branch of markets-data with no parent,
`paper-runs/<run id>`, holding paper-trading/<run id>/{events.jsonl,start.json,receipt.json,receive-ns.u64le}.
The branch is fetched when it is not already a remote-tracking ref of the checkout (`git fetch` is the only
network use). No model, no run of the platform, no order.

Graph (ids carry the run, so two runs never share a node):
  Order         `porder:<order id>`: one for each `paper order` row of events.jsonl. Its run, its journal
                `sequence`, its line of the file, the tape message it was decided on (`reference`: the tape
                file's sha256 and the record index; `received`: the tape receive time in ns), and the row's
                own fields as stored (bid, ask, limit_price, placement, trade_data and the rest).
  Fill          `pfill:<run id>:<sequence>`: one for each `fill` row, the same, with `price` = the row's
                fill_price as stored and its bid and ask beside it. A fill_id is not unique in a run, so the
                journal sequence is the key.
  rule version  Entity `rulever:platform:<rule>@<commit10>`: one for each (rule, rule_commit) of the run,
                DERIVED_FROM the Commit of that rule file. The row's `finding` URL is a Source node
                (`src:link:<url>`) the rule version points at (DERIVED_FROM, key "finding"); it is a link to
                a document, never to a Claim.
  edges         Fill FILLS Order, Order PLACED_BY rule version, Order and Fill DERIVED_FROM the Source of
                the run's events.jsonl (a file of the run's branch at its commit).

Experiment record: one trial for each run, status `recorded`, key `platform-run:<run id>`; change = the
platform code commit; figures = counts of what was written, computed as paper_platform/trial.py
trade_lines() and figures() compute them (copied here, not imported). No result figure, no sum, no
average across trades. Greg, 2026-11-24: "Don't use score since we didn't use anything we wanted scored".

Left out of the nodes, and named on each node (`journal_keys_left_out`): open_profit and
highest_open_profit, which are result-like. No mid price and no cost is computed or stored.
Only added to: a second load writes nothing new.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess

from tools.exp_dag import ExpDag
from .sources import REPOS, code_stamp, commit_node, link
from .store import GraphStore

WRITER = "tools.kgraph.ingest_platform"
DATA_REPO = "markets-data"
PLATFORM_REPO = "paper-trading-platform"
LEFT_OUT = ("open_profit", "highest_open_profit")      # result-like: not copied
NOT_COPIED = ("kind", "run", "market")                  # said by the node itself
GREG = ("Greg, 2026-11-24: \"Don't use score since we didn't use anything we wanted scored\". "
        "Not scored: the figures of this trial are counts of what was written, nothing else.")


def run_ref(run: str) -> str:
    return f"refs/remotes/paper-runs/{run}"


def order_node_id(order_id: str) -> str:
    return f"porder:{order_id}"


def fill_node_id(run: str, sequence: int) -> str:
    return f"pfill:{run}:{sequence}"


def rulever_id(rule: str, commit: str) -> str:
    return f"rulever:platform:{rule}@{commit[:10]}"


def finding_id(url: str) -> str:
    return f"src:link:{url}"


def _git(repo, *args, text=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=text)
    if r.returncode != 0:
        err = r.stderr.strip() if text else r.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)}: {err}")
    return r.stdout


def ensure_run(data, run: str) -> str:
    """The commit of the run's branch; fetched (depth 1) when the checkout does not hold it yet."""
    ref = run_ref(run)
    try:
        return _git(data, "rev-parse", "--verify", ref).strip()
    except RuntimeError:
        _git(data, "fetch", "--depth", "1", "origin", f"+refs/heads/paper-runs/{run}:{ref}")
        return _git(data, "rev-parse", "--verify", ref).strip()


def read_run(data, run: str) -> dict:
    """The saved files of one run, as stored on its branch."""
    commit = ensure_run(data, run)
    base = f"paper-trading/{run}"

    def raw(name):
        return subprocess.run(["git", "-C", str(data), "show", f"{commit}:{base}/{name}"],
                              capture_output=True).stdout if _has(data, commit, f"{base}/{name}") else None
    events = raw("events.jsonl")
    if events is None:
        raise RuntimeError(f"paper-runs/{run}: no events.jsonl")
    receipt = raw("receipt.json")
    return {"commit": commit, "path": f"{base}/events.jsonl", "events_raw": events,
            "rows": [json.loads(l) for l in events.decode("utf-8").splitlines() if l.strip()],
            "start": json.loads(raw("start.json").decode("utf-8")),
            "receipt": json.loads(receipt.decode("utf-8")) if receipt else None}


def _has(data, commit, path) -> bool:
    r = subprocess.run(["git", "-C", str(data), "cat-file", "-e", f"{commit}:{path}"], capture_output=True)
    return r.returncode == 0


# ---- the counts: the same as paper_platform/trial.py trade_lines() and figures() ----------------------

def trade_lines(rows):
    trades = {}
    for row in rows:
        if row["kind"] not in ("fill", "paper order", "signal") or not row.get("trade_id"):
            continue
        key = row["rule"], row["trade_id"]
        trade = trades.setdefault(key, dict(rule=key[0], trade_id=key[1], fills=[], held=0,
                                            administrative_close=False))
        if row["kind"] in ("signal", "paper order"):
            continue
        quantity = int(row["quantity"])
        signed = quantity if row["side"] == "buy" else -quantity
        trade["held"] += signed
        trade["administrative_close"] = trade["administrative_close"] or (
            row.get("action") != "open" and row.get("trade_data") is False)
        trade["fills"].append(dict(action=row["action"]))
    return [dict(contracts_held_at_end=t["held"], closed_by_an_administrative_fill=t["administrative_close"],
                 fills=t["fills"]) for t in trades.values() if t["fills"]]


def figures(rows) -> dict:
    lines = trade_lines(rows)
    return dict(
        journal_rows=len(rows),
        signals_open=sum(r["kind"] == "signal" and r.get("action") == "open" for r in rows),
        paper_orders=sum(r["kind"] == "paper order" for r in rows),
        fills=sum(r["kind"] == "fill" for r in rows),
        trades_opened=sum(any(f["action"] == "open" for f in l["fills"]) for l in lines),
        trades_holding_no_contract_at_end=sum(l["contracts_held_at_end"] == 0 for l in lines),
        trades_closed_by_an_administrative_fill=sum(l["closed_by_an_administrative_fill"] for l in lines),
    )


# ---- the graph ------------------------------------------------------------------------------------------

def _finding_node(url: str) -> dict:
    """A link to a document. A GitHub blob URL is split into its repository, commit and path."""
    m = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/blob/([0-9a-f]{40})/(.+)", url)
    attrs = {"kind": "link", "repo": m.group(1) if m else "url", "path": m.group(3) if m else url, "url": url}
    if m:
        attrs["commit"] = m.group(2)
    return {"id": finding_id(url), "type": "Source", "attrs": attrs}


def _row_attrs(row: dict, run: str, line: int, src_id: str, start: dict) -> dict:
    a = {k: v for k, v in row.items() if k not in NOT_COPIED and k not in LEFT_OUT and k != "sequence"}
    a.update({"run": run, "journal_sequence": row["sequence"], "line": line, "source": src_id,
              "journal_keys_left_out": [k for k in LEFT_OUT if k in row],
              "platform": "own paper platform"})
    ref = row.get("reference")
    if ref:
        files = [i["file"] for i in start.get("inputs") or [] if i.get("sha256") == ref[0]]
        a["tape_message"] = {"tape_file_sha256": ref[0], "record_index": ref[1],
                             "tape_file": files[0] if files else None, "received_ns": row.get("received")}
    return a


def load_run(store: GraphStore, dag: ExpDag, data, run: str, platform_dir: str | None = None) -> dict:
    d = read_run(data, run)
    if d["receipt"] is None:
        raise RuntimeError(f"paper-runs/{run} has no receipt.json: the run has not ended; not loaded")
    rows, start, receipt = d["rows"], d["start"], d["receipt"]
    by = code_stamp(WRITER)
    src = {"id": f"src:{DATA_REPO}@paper-runs/{run}:{d['path']}", "type": "Source", "attrs": {
        "kind": "file", "repo": REPOS[DATA_REPO], "path": d["path"], "branch": f"paper-runs/{run}",
        "commit": d["commit"], "bytes": len(d["events_raw"]), "sha256": hashlib.sha256(d["events_raw"]).hexdigest(),
        "lines": d["events_raw"].count(b"\n")}}
    nodes, edges = [src], []
    lines_of = {}
    n = 0
    for raw_line in d["events_raw"].decode("utf-8").splitlines():
        n += 1
        if raw_line.strip():
            lines_of[json.loads(raw_line)["sequence"]] = n
    versions, order_nodes, missing = {}, 0, {"rows_without_a_rule_commit": []}
    for row in rows:
        if row["kind"] not in ("paper order", "fill"):
            continue
        a = _row_attrs(row, run, lines_of[row["sequence"]], src["id"], start)
        if row["kind"] == "paper order":
            nid = order_node_id(row["order_id"])
            a["order_ref"] = row["order_id"]
            nodes.append({"id": nid, "type": "Order", "attrs": a})
            order_nodes += 1
        else:
            nid = fill_node_id(run, row["sequence"])
            a.update({"fill_ref": row["fill_id"], "price": row["fill_price"]})
            nodes.append({"id": nid, "type": "Fill", "attrs": a})
            edges.append(link("FILLS", nid, order_node_id(row["order_id"])))
        edges.append(link("DERIVED_FROM", nid, src["id"], key=f"line {a['line']}", line=a["line"]))
        if row["kind"] == "paper order":
            if row.get("rule") and row.get("rule_commit"):
                rv = rulever_id(row["rule"], row["rule_commit"])
                edges.append(link("PLACED_BY", nid, rv))
            else:
                missing["rows_without_a_rule_commit"].append(row["sequence"])
        if row.get("rule") and row.get("rule_commit"):
            versions.setdefault((row["rule"], row["rule_commit"]), set())
            if row.get("finding"):
                versions[(row["rule"], row["rule_commit"])].add(row["finding"])
    for (rule, commit), findings in sorted(versions.items()):
        rv = rulever_id(rule, commit)
        if platform_dir:
            try:
                cnode = commit_node(PLATFORM_REPO, platform_dir, commit)
            except RuntimeError:
                cnode = None
        else:
            cnode = None
        if cnode is None:
            # the commit is not in a local checkout: only what the run's own records say of it
            cnode = {"id": f"commit:{PLATFORM_REPO}:{commit[:10]}", "type": "Commit",
                     "attrs": {"repo": REPOS[PLATFORM_REPO], "sha": commit,
                               "note": "from the run's rule_commit; its subject and date are not read here"}}
        nodes.append(cnode)
        nodes.append({"id": rv, "type": "Entity", "attrs": {
            "name": f"{rule} at {commit[:10]}", "entity_kind": "rule version", "rule": rule, "commit": commit,
            "repo": REPOS[PLATFORM_REPO], "platform": "own paper platform"}})
        edges.append(link("DERIVED_FROM", rv, cnode["id"]))
        for url in sorted(findings):
            fn = _finding_node(url)
            nodes.append(fn)
            edges.append(link("DERIVED_FROM", rv, fn["id"], key="finding",
                              what="the document the rule's journal rows name as its finding (a link, not a claim)"))
    written = store.write(nodes, edges, written_by=by)

    last_received = max((r["received"] for r in rows if r.get("received") is not None), default=None)
    plan = start.get("execution_plan") or {}
    figs = figures(rows)
    metrics = [{"name": k, "value": v, "unit": None,
                "note": "a count of what the run wrote, computed as paper_platform/trial.py figures() does"}
               for k, v in figs.items()]
    consts = start.get("constants") or {}
    env = {"where": "own paper platform", "record": f"paper-runs/{run}", "record_commit": d["commit"],
           "trade_day": start.get("trade_day"), "market": start.get("market"),
           "execution_plan_source": start.get("execution_plan_source") or receipt.get("execution_plan_source"),
           "execution_plan_sha256": receipt.get("execution_plan_sha256"),
           "exit": plan.get("exit"), "paced_from_tape_ns": consts.get("paced_from_tape_ns"),
           "last_received_ns": last_received, "receipt_status": receipt.get("status"),
           "rule_commits_of_the_run": sorted({c for c in (receipt.get("rule_commits") or {}).values()}),
           "orders_in_graph": order_nodes}
    status = receipt.get("status")
    hyp = (f"platform run {run}: plan {env['execution_plan_source']}"
           + (f", exit {json.dumps(env['exit'])}" if env["exit"] else ", the rules' own closes")
           + f"; trade day {env['trade_day']}; ended: {status}")
    tid = dag.push(hypothesis=hyp, status="recorded", change={"repo": REPOS[PLATFORM_REPO], "commit": start["code_commit"]},
                   metrics=metrics, environment=env, note=GREG, key=f"platform-run:{run}", written_by=by)
    return {"run": run, "trial": tid, "figures": figs, "graph": written, "orders": order_nodes,
            "fills": figs["fills"], "rule_versions": len(versions), "left_unplaced": missing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--run", action="append", required=True, help="a platform run id (branch paper-runs/<id>)")
    ap.add_argument("--platform", help="a paper-trading-platform checkout, for the subjects of rule commits")
    ap.add_argument("--graph-dir", help="a scratch folder to write the graph to (checks)")
    ap.add_argument("--exp-dir", help="a scratch folder to write the experiment record to (checks)")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dag = ExpDag(a.data, exp_dir=a.exp_dir)
    for run in a.run:
        print(json.dumps(load_run(store, dag, store.data_root, run, a.platform), indent=1))
    dag.rebuild()
    print("graph:", store.counts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
