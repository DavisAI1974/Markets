"""Stage 7f: the loop and the grounding check on rule versions, using the paper record.

  python3 -m tools.kgraph.rule_versions load  [--data <markets-data>] [--platform <paper-trading-platform>]
  python3 -m tools.kgraph.rule_versions check [--record] [--reviewer run:00NN]

load   Each edit of the paper runner's rules is one git commit of DavisAI1974/paper-trading-platform that
       changed a rule file. Each becomes a trial of the experiment record (plan 7a: "each version is a
       node in the stage-2 DAG"), in the order it was made, each on the one before. It carries no
       figure: the feed is not scored. Each paper run is tied to the rule version it ran under (the
       last rule commit that is in the history of the run's own code commit), in the record (the
       version's `links`) and in the graph (each `rulever:` node of that run points at that commit).
check  The grounding check of stage 4c on every rule version: which claim or finding does the rule
       rest on? With --record each check is kept as an Evaluation node. No link from a rule to a
       claim is ever made here: a missing one is what the check reports.

The loop itself is tools/ratchet with the control file LOOP_PROGRAM. It is not run from here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.exp_dag import ExpDag
from . import grounding
from .extract import repo_dirs
from .sources import REPOS, code_stamp, commit_node, git, link
from .store import GraphStore, sha

RULE_FILES = ("tasty/paper/rules_cl.py", "tasty/paper/rules_cx.py")
REPO = "paper-trading-platform"
LOOP_PROGRAM = Path(__file__).resolve().parents[1] / "ratchet" / "programs" / "paper_rules.md"


def load(dag: ExpDag, store: GraphStore, platform_dir) -> dict:
    by = code_stamp("tools.kgraph.rule_versions")
    commits = git(platform_dir, "log", "--reverse", "--format=%H", "--", *RULE_FILES).split()
    runs = [t for t in dag.log() if (t.get("key") or "").startswith("paper-run:") and t.get("change")]
    in_force = {}
    for run in runs:
        c = run["change"]["commit"]
        try:
            in_force[c] = git(platform_dir, "log", "-1", "--format=%H", c, "--", *RULE_FILES) or None
        except RuntimeError:
            in_force[c] = None          # the run's commit is not in this checkout: said in the report
    before, parent, ids = len(dag.lines()), None, {}
    for c in commits:
        files = git(platform_dir, "show", "--format=", "--name-only", c).split()
        under = sorted(r["id"] for r in runs if in_force.get(r["change"]["commit"]) == c)
        parent = dag.push(
            hypothesis=git(platform_dir, "log", "-1", "--format=%s", c), status="recorded", parent=parent,
            change={"repo": REPOS[REPO], "commit": c}, metrics=[], links=under,
            environment={"what": "one edit of the paper runner's rules", "rule_files_changed": [f for f in files if f in RULE_FILES],
                         "files_changed": len(files)},
            note="A rule version. It carries no figure: nothing from the sandbox feed is scored. "
                 "Linked: the paper runs that ran under it.",
            key=f"rule-version:{c}", written_by=by)
        ids[c] = parent
    nodes = {n["id"]: n for n in (commit_node(REPO, platform_dir, c) for c in commits)}
    edges = []
    for rv in store.nodes("Entity"):
        if rv["attrs"].get("entity_kind") != "rule version":
            continue
        version = in_force.get(rv["attrs"]["commit"])
        if version:
            edges.append(link("DERIVED_FROM", rv["id"], f"commit:{REPO}:{version[:10]}", key="rule version in force",
                              what="the commit that last changed the rule files before the run's own code commit",
                              found_by="git log -1 <run commit> -- " + " ".join(RULE_FILES)))
    # What could not be placed is kept in the graph too (open, with the reason), not only in the report.
    for run in runs:
        c = run["change"]["commit"]
        if in_force.get(c) is None:
            reason = (f"the code commit {c} of the paper run {run['id']} is not in this checkout of "
                      f"{REPOS[REPO]}, so the rule version it ran under cannot be found and its rule versions "
                      "are not tied to a commit")
            nodes[f"task:run-commit-not-in-checkout:{sha([run['id'], c])}"] = {
                "id": f"task:run-commit-not-in-checkout:{sha([run['id'], c])}", "type": "Task",
                "attrs": {"text": reason, "state": "open", "reason": reason, "trial": run["id"],
                          "code_commit": c, "left_out_by": "tools.kgraph.rule_versions"}}
    graph = store.write(list(nodes.values()), edges, written_by=by)
    if len(dag.lines()) != before:
        dag.rebuild()
    return {"rule_versions": commits, "trial_ids": ids, "in_force": in_force,
            "runs_whose_commit_is_not_in_the_checkout": sorted(c for c, v in in_force.items() if v is None),
            "written": {"trials_new_or_revised": len(dag.lines()) - before, "graph": graph}}


def check(store: GraphStore, dirs: dict | None, reviewer: str, run: str | None, record: bool = True) -> dict:
    rvs = [e for e in store.nodes("Entity") if e["attrs"].get("entity_kind") == "rule version"]
    have = {e["id"] for e in store.nodes("Evaluation")}
    out = {"checked": len(rvs), "need_evidence": 0, "evaluations_written": 0, "each": []}
    for rv in sorted(rvs, key=lambda n: n["id"]):
        r = grounding.check_node(store, rv["id"], dirs)
        out["need_evidence"] += r["decision"] == "revise"
        out["each"].append({"rule_version": rv["id"], "decision": r["decision"], "reason": r["reason"],
                            "required_evidence": r["required_evidence"]})
        if record:
            eid = grounding.record(store, r, reviewer=reviewer, run=run)
            out["evaluations_written"] += eid not in have
            have.add(eid)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("load")
    p = sub.add_parser("check")
    p.add_argument("--record", action="store_true")
    p.add_argument("--reviewer", default=None)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dirs = repo_dirs(store.data_root, a.markets, a.platform)
    if a.verb == "load":
        if REPO not in dirs:
            print("no paper-trading-platform checkout: pass --platform", file=sys.stderr)
            return 2
        out = load(ExpDag(a.data), store, dirs[REPO])
        print(json.dumps({k: v for k, v in out.items() if k != "trial_ids"}, indent=1))
    else:
        reviewer = a.reviewer or code_stamp("tools.kgraph.rule_versions")
        out = check(store, dirs, reviewer, reviewer if reviewer.startswith("run:") else None, record=a.record)
        print(json.dumps({k: v for k, v in out.items() if k != "each"}, indent=1))
        for e in out["each"]:
            print(f"{e['rule_version']}: {e['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
