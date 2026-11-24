"""Agent runs into the graph and the paper runs into the experiment record (the first load of
stages 2 and 4, named in handoff X). No model is used: every value is read from a saved record.

  python3 -m tools.kgraph.ingest_agent_runs [--data <markets-data checkout>]

Reads, in markets-data tasks/family-research-20261022/research-union-current/paper-trading-20261123/:
  agent-runs.jsonl                one AgentRun node for each line, tied to the file and its line
  live-runs/<run>/receipt.json    one trial for each run folder, with the figures its receipt counts

The harness reports one token figure for a run (input and output together). It is stored as
`tokens_reported`; `input_tokens` and `output_tokens` stay empty because they were never given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.exp_dag import ExpDag
from .sources import code_stamp, commit_node, link, source_node
from .store import GraphStore

WORK = "tasks/family-research-20261022/research-union-current"
PAPER = f"{WORK}/paper-trading-20261123"
RUNS_FILE = f"{PAPER}/agent-runs.jsonl"


def run_id(n: int) -> str:
    return f"run:{int(n):04d}"


def agent_runs(store: GraphStore) -> dict:
    root = store.data_root
    src = source_node("markets-data", root, RUNS_FILE)
    nodes, edges = [src], []
    with (root / RUNS_FILE).open(encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            d = json.loads(raw)
            attrs = {
                "run": d["run"], "role": d["role"], "model": d["model"], "task": d["task"],
                "outcome": d["outcome"], "stage": d.get("stage"), "session": d.get("session"),
                "tokens_reported": d.get("tokens_reported"), "tokens_note": d.get("tokens_note"),
                "input_tokens": d.get("input_tokens"), "output_tokens": d.get("output_tokens"),
                "tool_calls": d.get("tool_calls"), "wall_clock_ms": d.get("wall_clock_ms"),
                "budget_tokens": d.get("budget_tokens"),
                "source": src["id"], "line_start": line_no, "line_end": line_no,
            }
            # anything else the line carries is kept as it is
            for k, v in d.items():
                attrs.setdefault(k, v)
            nid = run_id(d["run"])
            nodes.append({"id": nid, "type": "AgentRun", "attrs": attrs})
            edges.append(link("DERIVED_FROM", nid, src["id"], line=line_no))
    return store.write(nodes, edges, written_by=code_stamp("tools.kgraph.ingest_agent_runs"))


def _figures(prefix: str, obj, out: list) -> None:
    """Each counted figure of a receipt as its own line. Lists and texts are left in the receipt."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _figures(f"{prefix}.{k}" if prefix else k, v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append({"name": prefix, "value": obj, "unit": None, "note": "as counted in the run's receipt.json"})


def paper_runs(dag: ExpDag, store: GraphStore, platform_dir: str | None) -> list[str]:
    root = dag.data_root
    by = code_stamp("tools.kgraph.ingest_agent_runs")
    ids, first = [], None
    # in the order they were made: the folder name ends with its start time
    for folder in sorted((root / PAPER / "live-runs").iterdir(), key=lambda p: p.name.rsplit("-", 1)[-1]):
        receipt = folder / "receipt.json"
        rel = str(folder.relative_to(root))
        if receipt.exists():
            r = json.loads(receipt.read_text(encoding="utf-8"))
            figures: list = []
            _figures("counts", r.get("counts"), figures)
            figures.append({"name": "trades_in_ledger", "value": r.get("trades_in_ledger"), "unit": "ledger lines",
                            "note": "as counted in the run's receipt.json"})
            mode = r.get("mode") or {}
            hyp = (f"paper run {folder.name}: {r.get('what')}; orders sent to the sandbox: "
                   f"{mode.get('orders_sent_to_sandbox')}; stopped by: {r.get('stopped_by')}")
            change = {"repo": "DavisAI1974/paper-trading-platform", "commit": r["code_commit"]}
            env = {"where": "tastytrade sandbox", "arguments": {k: v for k, v in (r.get("arguments") or {}).items() if k != "out"},
                   "record": rel}
            seconds = (r.get("arguments") or {}).get("seconds")
            note = f"{r.get('not_scored')}. Seconds asked for: {seconds}."
            if platform_dir:
                try:
                    c = commit_node("paper-trading-platform", platform_dir, r["code_commit"])
                    store.write([c], written_by=by)
                except RuntimeError:
                    note += " The code commit is not in the local paper-trading-platform checkout."
        else:
            # a folder with no receipt (the close-out by hand): written down as what it is
            files = sorted(p.name for p in folder.iterdir())
            hyp = f"paper record {folder.name}: no receipt.json in the folder; files: {', '.join(files)}"
            change, figures, env = None, [], {"where": "tastytrade sandbox", "record": rel}
            note = "No figure is read from this folder: it has no receipt."
        tid = dag.push(hypothesis=hyp, status="recorded", parent=first, change=change, metrics=figures,
                       environment=env, note=note, key=f"paper-run:{folder.name}", written_by=by)
        first = first or tid   # the later folders of the evening follow the first run with orders
        ids.append(tid)
    dag.rebuild()
    return ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--platform", help="a paper-trading-platform checkout, for the runs' code commits")
    a = ap.parse_args(argv)
    store = GraphStore(a.data)
    print("agent runs:", agent_runs(store))
    print("paper runs:", paper_runs(ExpDag(a.data), store, a.platform))
    print("graph:", store.counts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
