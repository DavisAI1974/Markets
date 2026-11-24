"""Artifact nodes (plans, control files, decider programs, rule files, each repository's branch and head)
and Metric nodes (the measured figures of each run), so the graph can say where things are now (ticket 25).

  python3 -m tools.kgraph.ingest_artifacts [--data <markets-data>] [--graph-dir <scratch>]
                                           [--markets <dir>] [--platform <dir>]

No model is used: every value is read from git or from the saved record agent-runs.jsonl.
An Artifact's `authoring_run` is a run only when exactly one run's newest line names the artifact's
commit (its `code_commit` or one of its `data_commits`, compared by prefix); otherwise it is the plain
text "not recorded: ..." and the file is listed in the output. Nothing is guessed.

The link from a commit to an Artifact is PRODUCED ("src (a run, a commit) made dst"): PINNED_AT is worded
for a trade day, a time or a place on the tape, which does not fit a thing tied to a commit.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .extract import repo_dirs
from .ingest_agent_runs import RUNS_FILE, run_id
from .sources import REPOS, code_stamp, commit_node, git, link
from .store import GraphStore, now

PAPER_REL = RUNS_FILE.rsplit("/", 1)[0]
CODEX_REF = "origin/codex/strategy-trades-and-mbo-capture"
NO_LINE = "not recorded: no agent run's line names commit"

# set name -> (repo, folder, file filter)
SETS = {
    "control files": ("Markets", "tools/ratchet/programs", lambda n: True),
    "decider programs": ("Markets", "tools/decider/programs", lambda n: True),
    "rule files": ("paper-trading-platform", "paper_platform/rules", lambda n: n.endswith(".json")),
    "execution plans": ("paper-trading-platform", "paper_platform/execution_plans", lambda n: True),
    "run plans": ("markets-data", f"{PAPER_REL}/run-plans", lambda n: n.endswith(".json")),
    "plan files": ("markets-data", f"{PAPER_REL}/tickets-44-20261124",
                   lambda n: n.startswith("PLAN_") and n.endswith(".md")),
}

# the measured figures of a run that become Metric nodes, and the unit of each
FIGURES = {
    "tokens_reported": "tokens", "input_tokens_fresh": "tokens", "input_tokens_cache_written": "tokens",
    "input_tokens_cache_read": "tokens", "output_tokens": "tokens", "model_replies": "replies",
    "tool_calls": "calls", "wall_clock_ms": "ms",
}


def run_lines(data_root) -> dict:
    """run number -> (line number, the run's NEWEST line). The newest line of a run stands."""
    out = {}
    with (Path(data_root) / RUNS_FILE).open(encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            if raw.strip():
                d = json.loads(raw)
                out[d["run"]] = (n, d)
    return out


def authoring_run(sha: str, runs: dict) -> str:
    """`run:NNNN` when exactly one run's newest line names the commit, else the plain "not recorded" text."""
    named = []
    for n, (_, d) in sorted(runs.items()):
        tokens = [d.get("code_commit")] + list(d.get("data_commits") or [])
        if any(t and len(t) >= 7 and sha.startswith(t) for t in tokens):
            named.append(run_id(n))
    if len(named) == 1:
        return named[0]
    if not named:
        return f"{NO_LINE} {sha[:7]}"
    return f"not recorded: {len(named)} runs name commit {sha[:7]} ({', '.join(named)}), so none is its one author"


def _meta(d, rel):
    out = git(d, "log", "-1", "--format=%H%x00%cI", "--", rel)
    return out.split("\x00") if out else (None, None)


def _node(store, nid, attrs, stamp):
    """Keep the first read time while nothing else changed, so an unchanged read writes nothing new."""
    old = store.node(nid)
    if old and {k: v for k, v in old["attrs"].items() if k != "as_read_at"} == attrs:
        attrs = dict(attrs, as_read_at=old["attrs"].get("as_read_at"))
    else:
        attrs = dict(attrs, as_read_at=stamp)
    return {"id": nid, "type": "Artifact", "attrs": attrs}


def ingest(store: GraphStore, dirs: dict, runs: dict) -> dict:
    stamp = now()
    nodes, edges, commits = [], [], {}
    by_set = {k: 0 for k in SETS}
    no_run, skipped, runs_skipped = [], [], []

    def add(repo, a, sha):
        nid = a["id"]
        author = a["attrs"]["authoring_run"]
        if author.startswith("not recorded"):
            no_run.append(f"{nid} ({author})")
        elif store.node(author):
            edges.append(link("PRODUCED", author, nid))
        c = commit_node(repo, dirs[repo], sha)
        commits[c["id"]] = c
        edges.append(link("PRODUCED", c["id"], nid))
        nodes.append(a)

    for name, (repo, folder, ok) in SETS.items():
        if repo not in dirs:
            skipped.append(f"{name}: no {repo} checkout")
            continue
        d = dirs[repo]
        for f in sorted(os.listdir(Path(d) / folder)):
            rel = f"{folder}/{f}"
            if not (Path(d) / rel).is_file() or not ok(f):
                continue
            sha, date = _meta(d, rel)
            if sha is None or git(d, "status", "--porcelain", "--", rel):
                skipped.append(f"{repo}:{rel} ({'not committed' if sha is None else 'uncommitted changes'})")
                continue
            raw = (Path(d) / rel).read_bytes()
            import hashlib
            attrs = {"repo": REPOS.get(repo, repo), "path": rel, "version": sha,
                     "authoring_run": authoring_run(sha, runs), "set": name,
                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "commit_date": date}
            add(repo, _node(store, f"artifact:{repo}:{rel}", attrs, stamp), sha)
            by_set[name] += 1

    working = 0
    for repo, d in dirs.items():
        heads = [("working-branch", "(the working branch of this checkout)", "HEAD")]
        if repo == "paper-trading-platform":
            heads.append(("codex-branch", f"(the ref {CODEX_REF})", CODEX_REF))
        for tag, path, ref in heads:
            try:
                sha = git(d, "rev-parse", "--verify", "-q", ref)
            except RuntimeError:
                skipped.append(f"{repo}:{tag} (no ref {ref})")
                continue
            subject, date = git(d, "log", "-1", "--format=%s%x00%cI", sha).split("\x00")
            branch = git(d, "rev-parse", "--abbrev-ref", "HEAD") if ref == "HEAD" else ref
            attrs = {"repo": REPOS.get(repo, repo), "path": path, "version": sha, "branch": branch, "head": sha,
                     "authoring_run": authoring_run(sha, runs), "head_date": date, "head_subject": subject,
                     "read_from": Path(d).name}
            add(repo, _node(store, f"artifact:{repo}:{tag}", attrs, stamp), sha)
            working += 1

    metrics = 0
    for n, (line_no, d) in sorted(runs.items()):
        if not store.node(run_id(n)):
            runs_skipped.append(run_id(n))
            continue
        for name, unit in FIGURES.items():
            v = d.get(name)
            if v is None:
                continue
            nodes.append({"id": f"metric:{run_id(n)}:{name}", "type": "Metric",
                          "attrs": {"name": name, "value": v, "of": run_id(n), "source_line": line_no, "unit": unit}})
            metrics += 1

    written = store.write(list(commits.values()) + nodes, edges, written_by=code_stamp("tools.kgraph.ingest_artifacts"))
    return {"written": written, "by_set": by_set, "working_branches": working, "metrics": metrics,
            "no_run": no_run, "skipped": skipped, "runs_skipped": runs_skipped}


def current_versions_lines(store: GraphStore, budget_tokens: int) -> list[str]:
    """The CURRENT VERSIONS block of the session text, built from the Artifact nodes and nothing else."""
    from .context import CHARS_PER_TOKEN
    arts = store.nodes("Artifact")
    if not arts:
        return ["CURRENT VERSIONS: none on record (run tools.kgraph.ingest_artifacts)"]
    limit = int(budget_tokens * CHARS_PER_TOKEN * 0.10)
    top = ["CURRENT VERSIONS (as last read into the graph):"]
    for a in sorted(arts, key=lambda x: x["id"]):
        t = a["attrs"]
        if a["id"].endswith((":working-branch", ":codex-branch")):
            top.append(f"- {a['id'].split(':')[1]}{' codex' if a['id'].endswith('codex-branch') else ''}: "
                       f"branch {t['branch']}, head {t['head'][:7]} ({str(t.get('head_date'))[:10]}), "
                       f"as read at {t.get('as_read_at')}")
    files = []
    for a in sorted(arts, key=lambda x: x["id"]):
        t = a["attrs"]
        if t.get("set") in ("control files", "decider programs"):
            who = "authoring run not recorded" if t["authoring_run"].startswith("not recorded") else f"made by {t['authoring_run']}"
            files.append(f"- {t['path']}: version {t['version'][:7]}, {who}")
    sets: dict[str, int] = {}
    for a in arts:
        s = a["attrs"].get("set")
        if s in ("rule files", "execution plans", "run plans", "plan files"):
            sets[s] = sets.get(s, 0) + 1
    tail = ["- " + ", ".join(f"{sets.get(s, 0)} {s}" for s in ("rule files", "execution plans", "run plans", "plan files")),
            "These are the versions as last read into the graph; check each with git before trusting it."]
    shown = len(files)
    def size(fl, hidden):
        return sum(len(l) + 1 for l in top + fl + tail) + (80 if hidden else 0)
    while shown and size(files[:shown], shown < len(files)) > limit:
        shown -= 1
    hidden = len(files) - shown
    note = [f"- {hidden} control files and decider programs are not shown for want of budget"] if hidden else []
    return top + files[:shown] + note + tail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--graph-dir", help="a scratch graph folder (checks only); left out, the real graph")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dirs = repo_dirs(store.data_root, a.markets, a.platform)
    r = ingest(store, dirs, run_lines(store.data_root))
    print("artifacts by set:", r["by_set"], "| branch artifacts:", r["working_branches"])
    print("metrics written for", r["metrics"], "figures")
    print(f"no run on record ({len(r['no_run'])}):")
    for x in r["no_run"]:
        print("  ", x)
    print(f"files skipped ({len(r['skipped'])}):", *r["skipped"], sep="\n  " if r["skipped"] else " ")
    print(f"runs skipped, not an AgentRun node of the graph ({len(r['runs_skipped'])}):", ", ".join(r["runs_skipped"]) or "none")
    print("store wrote:", r["written"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
