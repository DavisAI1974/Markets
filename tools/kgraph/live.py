"""The graph written while a run goes: a run's record branch as it stands at one commit, added to the graph.

  python3 -m tools.kgraph.live follow --data <markets-data checkout> --run <run id>
        [--at <commit>] [--ref <ref>] [--platform <paper-trading-platform checkout>]
        [--graph-dir <scratch>] [--exp-dir <scratch>]
        [--watch [--poll-s N] [--max-wall-clock-s N] [--fetch]]

During a run the platform pushes its journal to the run's own branch of markets-data, `paper-runs/<run id>`,
at most ten seconds apart. `follow` reads that branch at one commit (default: the tip of the ref) and adds
only what the graph does not hold yet: each `paper order` row, each `fill` row and each rule version, with
the ids, attrs and links `tools/kgraph/ingest_platform.py` writes for a finished run. It does this by calling
that module's own `load_run` (the same code, not a copy): `read_run` is handed the files of the chosen
commit for the length of the call, and nothing else of ingest_platform is changed.

Reads git only: `rev-parse`, `show`, `cat-file`, `rev-list`. The ref is looked up as given, else
`refs/remotes/origin/paper-runs/<run>`, else `refs/remotes/paper-runs/<run>`. The only network use is
`git fetch` of that one ref, and only with `--fetch` in `--watch` (the caller fetches otherwise).

Without a `receipt.json` on the branch the run has NO trial in the experiment record: the trial of the
pass goes to a throw-away folder, because tools/exp_dag.py has no status for "still running" and none is
added. Once `receipt.json` is there the trial is written to the real record and the whole result equals
what `ingest_platform` writes for the finished run (the check compares every (id, content_sha)).

Signals: ingest_platform writes no node for a `signal` row and schema.py has no node type that fits one
(Order and Fill are the only journal types; Entity is "a named thing"). None is invented here: a pass
counts the signal rows it read and says so. A signal is read from the journal itself, where the packet
builder (signal_packet.py) reads it.

Lines are written by `code:tools.kgraph.live@<commit>` (the content is ingest_platform's, the hand is this
one). A Source node (the run's events.jsonl at a commit) carries the commit and the byte count, so it is
written again as its next revision on each commit that changed the file; that is a changed content, the
earlier revision stays. Nothing else of a run's nodes changes between commits: the journal only grows
(checked on every commit of two runs: each commit's file begins with the one before).

One JSON line a pass: the commit, the journal sequence reached, what was new (orders, fills, signals read,
rule versions), what was unchanged, whether the receipt was there.
No model, no run of the platform, no order, no mid price, no cost, no score.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
import time

from tools.exp_dag import ExpDag
from . import ingest_platform as ipf
from .sources import code_stamp
from .store import GraphStore

WRITER = "tools.kgraph.live"


def candidate_refs(run: str, ref: str | None = None) -> list[str]:
    if ref:
        return [ref]
    return [f"refs/remotes/origin/paper-runs/{run}", ipf.run_ref(run)]


def resolve_commit(data, run: str, *, at: str | None = None, ref: str | None = None) -> str:
    """The commit to read: `at` when given, else the tip of the first ref that exists. No network."""
    if at:
        return ipf._git(data, "rev-parse", "--verify", f"{at}^{{commit}}").strip()
    for r in candidate_refs(run, ref):
        try:
            return ipf._git(data, "rev-parse", "--verify", r).strip()
        except RuntimeError:
            continue
    raise RuntimeError(f"no ref for run {run} in {data}: tried {candidate_refs(run, ref)}; "
                       "fetch it (--fetch with --watch) or pass --ref")


def commits_of(data, tip: str) -> list[str]:
    """Every commit of the branch up to `tip`, oldest first (the branch has no parent and no merge)."""
    return ipf._git(data, "rev-list", "--reverse", tip).split()


def read_at(data, run: str, commit: str) -> dict:
    """The saved files of one run as they stand at `commit`; the same dict ipf.read_run gives."""
    base = f"paper-trading/{run}"

    def raw(name):
        if not ipf._has(data, commit, f"{base}/{name}"):
            return None
        return subprocess.run(["git", "-C", str(data), "show", f"{commit}:{base}/{name}"],
                              capture_output=True, check=True).stdout
    events = raw("events.jsonl")
    if events is None:
        raise RuntimeError(f"{run} at {commit[:10]}: no events.jsonl")
    start, receipt = raw("start.json"), raw("receipt.json")
    if start is None:
        raise RuntimeError(f"{run} at {commit[:10]}: no start.json")
    return {"commit": commit, "path": f"{base}/events.jsonl", "events_raw": events,
            "rows": [json.loads(l) for l in events.decode("utf-8").splitlines() if l.strip()],
            "start": json.loads(start.decode("utf-8")),
            "receipt": json.loads(receipt.decode("utf-8")) if receipt else None}


class _LiveStore(GraphStore):
    """A store whose lines name this module as their writer (ingest_platform's content, this hand)."""

    def write(self, nodes=(), edges=(), *, written_by):
        return super().write(nodes, edges, written_by=code_stamp(WRITER))


@contextlib.contextmanager
def _reads_from(d: dict):
    saved = ipf.read_run
    ipf.read_run = lambda data, run: d
    try:
        yield
    finally:
        ipf.read_run = saved


def _run_ids(store: GraphStore, run: str) -> dict:
    orders = {n["id"] for n in store.nodes("Order") if n["attrs"].get("run") == run}
    fills = {n["id"] for n in store.nodes("Fill") if n["attrs"].get("run") == run}
    reached = [n["attrs"]["journal_sequence"] for n in store.nodes("Order") + store.nodes("Fill")
               if n["attrs"].get("run") == run]
    return {"orders": orders, "fills": fills, "reached": max(reached, default=-1)}


def pass_once(store: GraphStore, dag: ExpDag, data, run: str, commit: str, platform: str | None = None,
              scratch_dag: ExpDag | None = None) -> dict:
    """One pass over the branch at `commit`. `dag` is the real experiment record: it gets the run's trial
    only when the receipt is there. Without it the trial goes to `scratch_dag` (a throw-away folder)."""
    d = read_at(data, run, commit)
    rows = d["rows"]
    before = _run_ids(store, run)
    rv_before = {n["id"] for n in store.nodes("Entity") if n["attrs"].get("entity_kind") == "rule version"}
    finished = d["receipt"] is not None
    if not finished:
        d = dict(d, receipt={"status": "the branch has no receipt.json yet"})
        if scratch_dag is None:
            raise ValueError("a pass over a run with no receipt needs a throw-away experiment folder")
    with _reads_from(d):
        rep = ipf.load_run(store, dag if finished else scratch_dag, store.data_root, run, platform)
    after = _run_ids(store, run)
    rv_rows = {ipf.rulever_id(r["rule"], r["rule_commit"]) for r in rows
               if r["kind"] in ("paper order", "fill") and r.get("rule") and r.get("rule_commit")}
    new_orders, new_fills = after["orders"] - before["orders"], after["fills"] - before["fills"]
    signals = [r for r in rows if r["kind"] == "signal"]
    new_signals = [r for r in signals if r["sequence"] > before["reached"]]
    return {
        "commit": commit, "journal_sequence": max((r["sequence"] for r in rows), default=-1),
        "journal_rows": len(rows), "receipt": finished,
        "new": {"orders": len(new_orders), "fills": len(new_fills), "signals_read": len(new_signals),
                "rule_versions": len(rv_rows - rv_before)},
        "unchanged": {"orders": len(before["orders"]), "fills": len(before["fills"]),
                      "signals_read": len(signals) - len(new_signals),
                      "rule_versions": len(rv_rows & rv_before)},
        "graph_write": rep["graph"],
        "trial": rep["trial"] if finished else None,
    }


def follow(data, run: str, *, at: str | None = None, ref: str | None = None, platform: str | None = None,
           graph_dir=None, exp_dir=None, store: GraphStore | None = None, dag: ExpDag | None = None,
           scratch_dag: ExpDag | None = None) -> dict:
    store = store or _LiveStore(data, graph_dir=graph_dir)
    dag = dag or ExpDag(data, exp_dir=exp_dir)
    commit = resolve_commit(store.data_root, run, at=at, ref=ref)
    if scratch_dag is not None:
        return pass_once(store, dag, store.data_root, run, commit, platform, scratch_dag)
    with tempfile.TemporaryDirectory() as tmp:
        return pass_once(store, dag, store.data_root, run, commit, platform, ExpDag(store.data_root, exp_dir=tmp))


def follow_commits(data, run: str, commits: list[str], *, platform=None, graph_dir=None, exp_dir=None,
                   on_pass=None) -> list[dict]:
    """The commits in the order given, one pass each, on one store (push by push)."""
    store, out = _LiveStore(data, graph_dir=graph_dir), []
    dag = ExpDag(data, exp_dir=exp_dir)
    with tempfile.TemporaryDirectory() as tmp:
        scratch = ExpDag(store.data_root, exp_dir=tmp)
        for c in commits:
            rep = pass_once(store, dag, store.data_root, run, c, platform, scratch)
            out.append(rep)
            if on_pass:
                on_pass(rep)
    dag.rebuild() if dag.record.exists() else None
    return out


def watch(data, run: str, *, ref=None, platform=None, graph_dir=None, exp_dir=None, poll_s: float = 10.0,
          max_wall_clock_s: float | None = None, fetch: bool = False, emit=print) -> int:
    """Repeat the pass on each new tip of the ref until the receipt is in or the wall clock is spent."""
    store = _LiveStore(data, graph_dir=graph_dir)
    dag = ExpDag(data, exp_dir=exp_dir)
    t0, last = time.monotonic(), None
    with tempfile.TemporaryDirectory() as tmp:
        scratch = ExpDag(store.data_root, exp_dir=tmp)
        while True:
            if fetch:
                target = ref or candidate_refs(run)[0]
                ipf._git(store.data_root, "fetch", "--no-tags", "origin", f"+refs/heads/paper-runs/{run}:{target}")
            try:
                tip = resolve_commit(store.data_root, run, ref=ref)
            except RuntimeError as e:
                if not fetch and last is None:
                    raise
                tip = last
            if tip is not None and tip != last:
                rep = pass_once(store, dag, store.data_root, run, tip, platform, scratch)
                emit(json.dumps(rep, sort_keys=True))
                last = tip
                if rep["receipt"]:
                    if dag.record.exists():
                        dag.rebuild()
                    return 0
            if max_wall_clock_s is not None and time.monotonic() - t0 >= max_wall_clock_s:
                return 2
            time.sleep(poll_s)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    f = sub.add_parser("follow")
    f.add_argument("--data")
    f.add_argument("--run", required=True)
    f.add_argument("--at", help="a commit of the run's branch (default: the tip of the ref)")
    f.add_argument("--ref")
    f.add_argument("--platform")
    f.add_argument("--graph-dir")
    f.add_argument("--exp-dir")
    f.add_argument("--watch", action="store_true")
    f.add_argument("--poll-s", type=float, default=10.0)
    f.add_argument("--max-wall-clock-s", type=float)
    f.add_argument("--fetch", action="store_true", help="with --watch: git fetch the one ref each poll (the only network use)")
    a = ap.parse_args(argv)
    if a.fetch and not a.watch:
        ap.error("--fetch is for --watch")
    if a.watch:
        if a.at:
            ap.error("--watch follows the tip of the ref, not one commit")
        return watch(a.data, a.run, ref=a.ref, platform=a.platform, graph_dir=a.graph_dir, exp_dir=a.exp_dir,
                     poll_s=a.poll_s, max_wall_clock_s=a.max_wall_clock_s, fetch=a.fetch)
    rep = follow(a.data, a.run, at=a.at, ref=a.ref, platform=a.platform, graph_dir=a.graph_dir, exp_dir=a.exp_dir)
    print(json.dumps(rep, sort_keys=True))
    if rep["receipt"]:
        d = ExpDag(a.data, exp_dir=a.exp_dir)
        if d.record.exists():
            d.rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
