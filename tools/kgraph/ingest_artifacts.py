"""Artifact nodes (plans, control files, decider programs, rule files, agent files, each repository's
branch and head) and Metric nodes (the measured figures of each run), so the graph can say where
things are now (ticket 25).

  python3 -m tools.kgraph.ingest_artifacts [--data <markets-data>] [--graph-dir <scratch>]
                                           [--markets <dir>] [--platform <dir>]

No model is used: every value is read from git or from the saved record agent-runs.jsonl.
Everything is read ONCE into a snapshot (`read_snapshot`) and `ingest(store, snapshot)` writes from
that snapshot alone, so the same snapshot ingested twice writes nothing new whatever the checkouts do.

WHO MADE AN ARTIFACT (`authorship`): the first of these four that holds, never guessed.
  field              exactly one run's newest line names the commit in `code_commit`, `data_commits`
                     or `commits` (items "repo:sha" or {"repo","sha"})
  outcome text of a builder   exactly one run whose agent is the builder names the commit's first 7
                     characters as a whole token in its `outcome` text. A commit named in a `task`
                     text, or by a reviewer, scout or auditor, is not authorship: they read it.
  the main session's commits  the commit is in markets-data, carries a Claude-Session line of a
                     session of the record, and its committer time lies inside that session's span
  outside the agent runs      none of the above; `git_author` holds the author's name as git gives it
Two runs naming one commit by the same step: "not settled: runs N and M both name commit <sha7>".
PRODUCED from the run to the Artifact is written only for the first two.

The link from a commit to an Artifact is PRODUCED ("src (a run, a commit) made dst"); settled by the plans.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .extract import repo_dirs
from .ingest_agent_runs import RUNS_FILE, run_id
from .sources import REPOS, code_stamp, commit_node, git, link
from .store import GraphStore, now

PAPER_REL = RUNS_FILE.rsplit("/", 1)[0]
CODEX_REF = "origin/codex/strategy-trades-and-mbo-capture"
FRANKIE = "research/kalshi/frankie_boss"


def _names(*n):
    return lambda f: f in n


# set name -> [(repo, folder, file filter)]
SETS = {
    "control files": [("Markets", "tools/ratchet/programs", lambda n: True)],
    "decider programs": [("Markets", "tools/decider/programs", lambda n: True)],
    "rule files": [("paper-trading-platform", "paper_platform/rules", lambda n: n.endswith(".json"))],
    "execution plans": [("paper-trading-platform", "paper_platform/execution_plans", lambda n: True)],
    "run plans": [("markets-data", f"{PAPER_REL}/run-plans", lambda n: n.endswith(".json"))],
    "plan files": [
        ("markets-data", f"{PAPER_REL}/tickets-44-20261124", lambda n: n.startswith("PLAN_") and n.endswith(".md")),
        ("Markets", FRANKIE, _names("CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md",
                                    "CODEX_PROMPT_AMENDMENTS_20261123.md", "README_HANDOFF_20261123.md")),
        ("Markets", "research/kalshi", _names("FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md")),
    ],
    "agent files": [("Markets", ".claude/agents", _names("scout.md", "builder.md", "reviewer.md",
                                                         "frankie-performance-auditor.md"))],
}
# files an explicit list names, so a missing one is said, not silently absent
LISTED = {"plan files": {("Markets", FRANKIE): ["CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md",
                                                  "CODEX_PROMPT_AMENDMENTS_20261123.md", "README_HANDOFF_20261123.md"],
                         ("Markets", "research/kalshi"): ["FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md"]},
          "agent files": {("Markets", ".claude/agents"): ["scout.md", "builder.md", "reviewer.md",
                                                           "frankie-performance-auditor.md"]}}

# the measured figures of a run that become Metric nodes, and the unit of each
FIGURES = {
    "tokens_reported": "tokens", "input_tokens_fresh": "tokens", "input_tokens_cache_written": "tokens",
    "input_tokens_cache_read": "tokens", "output_tokens": "tokens", "model_replies": "replies",
    "tool_calls": "calls", "wall_clock_ms": "ms",
}

# What each repository holds, in the order the session text shows them: (repo, tag, words before the branch)
LABELS = [
    ("Markets", "working-branch", "Markets (code)"),
    ("markets-data", "working-branch", "markets-data (records, graph, tickets)"),
    ("paper-trading-platform", "working-branch", "paper-trading-platform (the platform; OUR change is on this branch)"),
    ("paper-trading-platform", "codex-branch", "paper-trading-platform, Codex's branch (his; our change is NOT on it)"),
]

TAGS = ("field", "outcome text of a builder", "the main session's commits", "outside the agent runs", "two runs")
SESSION_RE = re.compile(r"Claude-Session:\s*\S*?(session_[A-Za-z0-9]+)")
HEX_RE = re.compile(r"(?<![0-9A-Za-z])([0-9a-f]{7,40})(?![0-9A-Za-z])")


def run_lines(data_root, rev=None) -> dict:
    """run number -> (line number, the run's NEWEST line). The newest line of a run stands.
    With `rev`, the record as markets-data held it at that commit, read with git."""
    out = {}
    if rev:
        text = subprocess.run(["git", "-C", str(data_root), "show", f"{rev}:{RUNS_FILE}"],
                              capture_output=True, text=True, check=True).stdout
        lines = text.splitlines()
    else:
        with (Path(data_root) / RUNS_FILE).open(encoding="utf-8") as f:
            lines = f.read().splitlines()
    for n, raw in enumerate(lines, 1):
        if raw.strip():
            d = json.loads(raw)
            out[d["run"]] = (n, d)
    return out


def _time(s):
    try:
        t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def _repo_name(s: str) -> str:
    return str(s).rsplit("/", 1)[-1].lower()


def _field_tokens(d: dict) -> list:
    """(repo or None, sha) for each commit the run's newest line names in a field."""
    out = [(None, d.get("code_commit"))] + [(None, c) for c in (d.get("data_commits") or [])]
    for c in d.get("commits") or []:
        if isinstance(c, dict):
            out.append((c.get("repo"), c.get("sha")))
        elif isinstance(c, str) and ":" in c:
            r, s = c.split(":", 1)
            out.append((r, s))
    return [(r, s) for r, s in out if s]


def _is_builder(d: dict) -> bool:
    agent = d.get("agent_type") or re.sub(r"[^A-Za-z0-9]", "", str(d.get("role") or "").split(" ")[0].split(",")[0])
    return str(agent).lower() == "builder"


def _two(named: list, sha: str) -> dict:
    return {"authoring_run": f"not settled: runs {' and '.join(str(int(r.split(':')[1])) for r in named)} "
                             f"both name commit {sha[:7]}",
            "authoring_basis": "two runs: each of these runs' newest lines names the commit in the same way"}


def authorship(repo: str, sha: str, runs: dict, info: dict, sessions: dict) -> dict:
    """authoring_run, authoring_basis (and git_author when it is outside the runs) of one commit."""
    # (a) a field
    named = []
    for n, (_, d) in sorted(runs.items()):
        for r, s in _field_tokens(d):
            if len(s) >= 7 and sha.startswith(s) and (r is None or _repo_name(r) == repo.lower()):
                named.append(run_id(n))
                break
    if len(named) == 1:
        return {"authoring_run": named[0], "authoring_basis": "field: the run's newest line names the commit in "
                                                               "code_commit, data_commits or commits"}
    if len(named) > 1:
        return _two(named, sha)
    # (b) the outcome text of a builder
    named = [run_id(n) for n, (_, d) in sorted(runs.items())
             if _is_builder(d) and any(sha.startswith(t) for t in HEX_RE.findall(str(d.get("outcome") or "")))]
    if len(named) == 1:
        return {"authoring_run": named[0], "authoring_basis": "outcome text of a builder: read from the run's "
                                                               "outcome text, not from a field"}
    if len(named) > 1:
        return _two(named, sha)
    # (c) the main session's commits
    c = info.get(sha) or {}
    sid, span = c.get("session"), sessions.get(c.get("session"))
    when = _time(c.get("time"))
    if (repo == "markets-data" and sid and span and when
            and span["start"] <= when and (when <= span["end"] or span["open"])):
        return {"authoring_run": f"the main session of {sid}",
                "authoring_basis": f"the main session's commits: no run names the commit; its message carries that "
                                   f"session's Claude-Session line and its committer time {c['time']} lies inside the "
                                   f"session's span, found from {span['how']}"}
    # (d) outside the agent runs
    return {"authoring_run": "none: made outside the agent runs",
            "authoring_basis": "outside the agent runs: no run names the commit and it is not the main session's",
            "git_author": c.get("author")}


def _tag(basis: str) -> str:
    return basis.split(":", 1)[0]


def read_snapshot(data_root, dirs: dict, data_rev=None) -> dict:
    """Everything the ingest reads, read once: the run record, each checkout's branch and head, the
    files' last commits and the commits' details. `ingest` writes from this and from nothing else.
    With `data_rev` (a markets-data commit) the run record and the commit messages the sessions are
    found from are those at that commit, read with git, so the result does not move as lines are added."""
    runs = run_lines(data_root, data_rev)
    snap = {"read_at": now(), "runs": runs, "files": [], "heads": [], "skipped": [], "info": {}, "commits": {}}
    mdlog = {}
    if "markets-data" in dirs:
        for chunk in git(dirs["markets-data"], "log", data_rev or "HEAD", "--format=%H%x00%cI%x00%B%x01").split("\x01"):
            if chunk.strip():
                h, t, m = chunk.strip().split("\x00", 2)
                found = SESSION_RE.findall(m)
                mdlog[h] = (t, found[-1] if found else None)
    groups: dict = {}
    for _, d in runs.values():
        if d.get("session"):
            groups.setdefault(d["session"], []).append(d)
    sessions = {}
    for sid, lines in groups.items():
        starts = [t for t in (_time(d.get("started_at")) for d in lines) if t]
        ends = [t for t in (_time(d.get("ended_at")) for d in lines) if t]
        how = ("the earliest started_at to the latest ended_at (the latest started_at where no line carries an "
               "ended_at) of the session's lines in agent-runs.jsonl")
        if starts:
            ts = starts + (ends or [])
        else:
            ts = [t for t in (_time(v[0]) for v in mdlog.values() if v[1] == sid) if t]
            how = "the first and last markets-data commits whose message ends with the session's Claude-Session line"
        if ts:
            sessions[sid] = {"start": min(ts), "end": max(ts), "how": how}
    for sid, sp in sessions.items():      # a session whose span no later session's start follows stays open
        sp["open"] = not any(o["start"] > sp["start"] for k, o in sessions.items() if k != sid)
        if sp["open"]:
            sp["how"] += "; no later session has a line, so a commit of its own after the span is still its own"
    snap["sessions"] = sessions

    def info(repo, sha):
        d = dirs[repo]
        an, ct = git(d, "log", "-1", "--format=%an%x00%cI", sha).split("\x00")
        sess = mdlog[sha][1] if repo == "markets-data" and sha in mdlog else None
        snap["info"].setdefault(repo, {})[sha] = {"author": an, "time": ct, "session": sess}
        c = commit_node(repo, d, sha)
        snap["commits"][c["id"]] = c

    for name, sources in SETS.items():
        for repo, folder, ok in sources:
            if repo not in dirs:
                snap["skipped"].append(f"{name}: no {repo} checkout")
                continue
            d = Path(dirs[repo])
            listed = LISTED.get(name, {}).get((repo, folder))
            names = listed if listed is not None else sorted(os.listdir(d / folder))
            for f in names:
                rel = f"{folder}/{f}"
                if not (d / rel).is_file():
                    if listed is not None:
                        snap["skipped"].append(f"{repo}:{rel} (listed for {name}, not in this checkout)")
                    continue
                if not ok(f):
                    continue
                out = git(d, "log", "-1", "--format=%H%x00%cI", "--", rel)
                if not out or git(d, "status", "--porcelain", "--", rel):
                    snap["skipped"].append(f"{repo}:{rel} ({'uncommitted changes' if out else 'not committed'})")
                    continue
                sha, date = out.split("\x00")
                raw = (d / rel).read_bytes()
                if sha not in snap["info"].get(repo, {}):
                    info(repo, sha)
                snap["files"].append({"id": f"artifact:{repo}:{rel}", "repo": repo, "sha": sha, "set": name,
                                      "attrs": {"repo": REPOS.get(repo, repo), "path": rel, "version": sha, "set": name,
                                                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                                                "commit_date": date}})
    for repo, d in dirs.items():
        heads = [("working-branch", "(the working branch of this checkout)", "HEAD")]
        if repo == "paper-trading-platform":
            heads.append(("codex-branch", f"(the ref {CODEX_REF})", CODEX_REF))
        for tag, path, ref in heads:
            try:
                sha = git(d, "rev-parse", "--verify", "-q", ref)
            except RuntimeError:
                snap["skipped"].append(f"{repo}:{tag} (no ref {ref})")
                continue
            subject, date = git(d, "log", "-1", "--format=%s%x00%cI", sha).split("\x00")
            branch = git(d, "rev-parse", "--abbrev-ref", "HEAD") if ref == "HEAD" else ref
            if sha not in snap["info"].get(repo, {}):
                info(repo, sha)
            snap["heads"].append({"id": f"artifact:{repo}:{tag}", "repo": repo, "sha": sha,
                                  "attrs": {"repo": REPOS.get(repo, repo), "path": path, "version": sha, "branch": branch,
                                            "head": sha, "head_date": date, "head_subject": subject,
                                            "read_from": Path(d).name}})
    return snap


def _node(store, nid, attrs, stamp):
    """The state read, with `first_read_at`: the time this state was first read. While nothing else has
    changed the standing line is kept as it is (its old key too), so a second read writes nothing new."""
    strip = lambda a: {k: v for k, v in a.items() if k not in ("as_read_at", "first_read_at")}
    old = store.node(nid)
    if old and strip(old["attrs"]) == attrs:
        return {"id": nid, "type": "Artifact", "attrs": old["attrs"]}
    return {"id": nid, "type": "Artifact", "attrs": dict(attrs, first_read_at=stamp)}


def ingest(store: GraphStore, snap: dict) -> dict:
    nodes, edges = [], []
    by_set = {k: 0 for k in SETS}
    by_basis = {k: 0 for k in TAGS}
    listed, no_run = [], []
    runs, sessions = snap["runs"], snap["sessions"]
    for entry in snap["files"] + snap["heads"]:
        repo, sha = entry["repo"], entry["sha"]
        who = authorship(repo, sha, runs, snap["info"][repo], sessions)
        attrs = dict(entry["attrs"], **{k: v for k, v in who.items() if v is not None})
        nid = entry["id"]
        nodes.append(_node(store, nid, attrs, snap["read_at"]))
        c = commit_node_id = f"commit:{repo}:{sha[:10]}"
        edges.append(link("PRODUCED", c, nid))
        tag = _tag(who["authoring_basis"])
        by_basis[tag] += 1
        if "set" in entry:
            by_set[entry["set"]] += 1
        if tag in ("field", "outcome text of a builder") and store.node(who["authoring_run"]):
            edges.append(link("PRODUCED", who["authoring_run"], nid))
        if tag != "field":
            listed.append(f"{nid} [{tag}] {who['authoring_run']}" + (f" (git author {who['git_author']})" if who.get("git_author") else ""))
    runs_skipped = []
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
    # a Commit node another module already wrote is left as it is
    commits = [c for cid, c in snap["commits"].items() if not store.node(cid)]
    written = store.write(commits + nodes, edges, written_by=code_stamp("tools.kgraph.ingest_artifacts"))
    return {"written": written, "by_set": by_set, "by_basis": by_basis, "branch_artifacts": len(snap["heads"]),
            "metrics": metrics, "listed": listed, "skipped": snap["skipped"], "runs_skipped": runs_skipped}


def current_versions_lines(store: GraphStore, budget_tokens: int) -> list[str]:
    """The CURRENT VERSIONS block of the session text, built from the Artifact nodes and nothing else.
    The four branch lines and the closing sentence are NEVER cut. The block is held to 10 per cent of the
    budget by cutting file lines (control files, decider programs) from the end; when any are cut, a line
    says how many are not shown."""
    from .context import CHARS_PER_TOKEN
    arts = {a["id"]: a for a in store.nodes("Artifact")}
    if not arts:
        return ["CURRENT VERSIONS: none on record (run tools.kgraph.ingest_artifacts)"]
    limit = int(budget_tokens * CHARS_PER_TOKEN * 0.10)
    top = ["CURRENT VERSIONS (as last read into the graph):"]
    for repo, tag, label in LABELS:
        a = arts.get(f"artifact:{repo}:{tag}")
        if a:
            t = a["attrs"]
            top.append(f"- {label}: branch {t['branch']}, head {t['head'][:7]} ({str(t.get('head_date'))[:10]}), "
                       f"first read at {t.get('first_read_at') or t.get('as_read_at')}")
    files = []
    for a in sorted(arts.values(), key=lambda x: x["id"]):
        t = a["attrs"]
        if t.get("set") in ("control files", "decider programs"):
            basis = t.get("authoring_basis")
            files.append(f"- {t['path']}: version {t['version'][:7]}, authored by {t['authoring_run']}"
                         + (f" [{_tag(basis)}]" if basis else ""))
    sets: dict[str, int] = {}
    for a in arts.values():
        s = a["attrs"].get("set")
        if s in ("rule files", "execution plans", "run plans", "plan files", "agent files"):
            sets[s] = sets.get(s, 0) + 1
    order = ("rule files", "execution plans", "run plans", "plan files", "agent files")
    tail = ["- " + ", ".join(f"{sets.get(s, 0)} {s}" for s in order),
            "These are the versions as last read into the graph; check each with git before trusting it."]
    shown = len(files)

    def size(fl, hidden):
        return sum(len(l) + 1 for l in top + fl + tail) + (160 if hidden else 0)
    while shown and size(files[:shown], shown < len(files)) > limit:
        shown -= 1
    hidden = len(files) - shown
    note = [f"- {hidden} control files and decider programs are not shown for want of budget "
            "(the branch lines and the closing sentence are never cut)"] if hidden else []
    # where the lines that are never cut (the branch lines, the note on what is not shown, the closing lines)
    # are over a tenth of the budget by themselves, the block says so, with the two figures
    kept_chars = sum(len(l) + 1 for l in top + files[:shown] + note + tail)
    if kept_chars > limit:
        note.append(f"- the branch lines are kept whole and, with the closing lines, take {kept_chars} characters, "
                    f"more than their share of {limit} characters (a tenth of the budget of {budget_tokens} tokens)")
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
    r = ingest(store, read_snapshot(store.data_root, dirs))
    print("artifacts by set:", r["by_set"], "| branch artifacts:", r["branch_artifacts"])
    print("artifacts by authoring basis:", r["by_basis"])
    print("metrics written for", r["metrics"], "figures")
    print(f"artifacts whose basis is not a field ({len(r['listed'])}):")
    for x in r["listed"]:
        print("  ", x)
    print(f"files skipped ({len(r['skipped'])}):", *r["skipped"], sep="\n  " if r["skipped"] else " ")
    print(f"runs skipped, not an AgentRun node of the graph ({len(r['runs_skipped'])}):", ", ".join(r["runs_skipped"]) or "none")
    print("store wrote:", r["written"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
