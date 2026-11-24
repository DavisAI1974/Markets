"""A run's eight limits, written in a plan file before it starts and checked after it ends (ticket 18).

    python3 -m tools.kgraph.run_plan write --data <markets-data> --run N --agent A --model M --task "..." \
        --max-model-calls .. --max-sub-agents .. --max-concurrent-workers .. --max-tool-calls .. \
        --max-tokens .. --max-wall-clock-s .. --max-retries .. --max-graph-writes .. [--session S] \
        [--tickets 18,19] [--note ".."]
    python3 -m tools.kgraph.run_plan brief --data <markets-data> --run N
    python3 -m tools.kgraph.run_plan check --data <markets-data> --run N [--transcript F] [--plan F]

WHAT CODE CANNOT HOLD: nothing in code can stop an agent started from a chat in the middle of its run.
The agent is told its limits in its brief, counts for itself and stops (runs 117, 126 and 127 stopped
exactly at their tool-call limit); `check` shows afterwards whether it did. `write` and `brief` only write
the plan and the words; `check` writes nothing.

The graph-writes count holds the lines of graph/nodes/*.jsonl and graph/edges/*.jsonl whose `written_by` is
`run:NNNN` (the run). It does not hold lines a code stamp wrote for a run (`made_by`), and not the files of
graph/reads, graph/merges and graph/evaluations.

PAIRED CHECKS: whenever `check` is given `--plan`, the plan read is one given by hand, not the run's own plan in
git. The first line printed says so, the git state and the git order are not measured, and the exit code is 3,
so it can never be read as the run's own check ending well. The limit lines are printed as always.

Git order: it rests on the committer time of the commit that added the plan file (found with `git log
--diff-merges=first-parent --diff-filter=A`, so a plan added inside a merge commit is found), and a rebase
moves that time. A plan that was renamed or moved has the rename's time as its add time, which is right for the
rule: a plan is written once under its own name and never moved.

A plan counts as written before the run only if it is in git: `check` compares the file it reads with the file's
bytes at the commit that added it, and a plan that is not in git, was changed after it was added, or was
committed after the run's first line fails (exit 1).

`--data` is used exactly as given or refused; it never falls through to another checkout. Exit codes:
0 done, 1 `check` found a PASSED limit / a late plan / no plan, 2 refused.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.swarm.plan import BUDGET_KEYS

PAPER_REL = "tasks/family-research-20261022/research-union-current/paper-trading-20261123"
ROSTER = ("scout", "builder", "reviewer", "frankie-performance-auditor")
IS_GRAPH = "writes into the real graph of markets-data; a write into a scratch copy is not counted"
IS_TOKENS = ("the harness's total for the run when it ends (input and output together); "
             "the transcript's sum is recorded beside it")
MIN_ONE = ("max_model_calls", "max_tokens", "max_wall_clock_s", "max_concurrent_workers")
ON_LIMIT = "the run stops and returns what is done, what is open and why it stopped"
UNITS = {"max_model_calls": "model calls", "max_sub_agents": "sub-agents",
         "max_concurrent_workers": "concurrent workers", "max_tool_calls": "tool calls",
         "max_tokens": "tokens", "max_wall_clock_s": "seconds of wall clock", "max_retries": "retries",
         "max_graph_writes": "writes into the real graph"}


class Refused(Exception):
    pass


def _paper(data):
    root = Path(data)
    paper = root / PAPER_REL
    if not (paper / "run-plans").is_dir():
        raise Refused(f"{root} has no {PAPER_REL}/run-plans folder; used exactly as given, no other checkout tried")
    return root, paper


def _lines(paper):
    f = paper / "agent-runs.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _newest(paper, run):
    mine = _of_run(paper, run)
    return mine[-1] if mine else None


def _of_run(paper, run):
    # a line belongs to a run by its `run` number; what `corrects` holds (a sentence in the real record) is not read
    return [d for d in _lines(paper) if _num(d.get("run")) == run]


def _plan_path(paper, run):
    return paper / "run-plans" / f"run-{run:04d}.json"


# ---- write ------------------------------------------------------------------------------------------
def _write(a):
    root, paper = _paper(a.data)
    if a.run < 1:
        raise Refused(f"run number {a.run} is below 1")
    missing = [k for k in BUDGET_KEYS if getattr(a, k) is None]
    if missing:
        raise Refused("missing limit(s): " + ", ".join(missing))
    neg = [k for k in BUDGET_KEYS if getattr(a, k) < 0]
    if neg:
        raise Refused("negative limit(s): " + ", ".join(neg))
    zero = [k for k in MIN_ONE if getattr(a, k) < 1]
    if zero:
        raise Refused("limit(s) below 1 (a run makes at least one model call, and has tokens, time and a worker): "
                      + ", ".join(zero))
    if a.agent not in ROSTER:
        raise Refused(f"agent {a.agent!r} is not in the roster {ROSTER}")
    path = _plan_path(paper, a.run)
    if path.exists():
        raise Refused(f"a plan file already exists for run {a.run}: {path}; a plan is never rewritten")
    if not _is_repo(root):
        raise Refused(f"{root} is not a git repository: a plan is written only where it can be committed")
    if _git_history(root, path):
        raise Refused(f"the plan path of run {a.run} is in git history ({path}) though the file is gone; "
                      "a plan is never written twice")
    if any(_num(d.get("run")) == a.run or _num(d.get("corrects")) == a.run for d in _lines(paper)):
        raise Refused(f"run {a.run} already has a line in the record; the plan comes before the run")
    session = a.session
    if session is None:
        olds = sorted((paper / "run-plans").glob("run-*.json"))
        session = json.loads(olds[-1].read_text()).get("session") if olds else None
    if not session:
        raise Refused("no --session given and no earlier plan to take it from")
    doc = {"run": a.run, "session": session, "agent": a.agent, "model": a.model, "task": a.task,
           "written_before_the_run_started": True}
    doc.update({k: getattr(a, k) for k in BUDGET_KEYS})
    doc.update({"max_graph_writes_is": IS_GRAPH, "max_tokens_is": IS_TOKENS, "on_reaching_a_limit": ON_LIMIT})
    if a.note:
        doc["note"] = a.note
    if a.tickets:
        doc["tickets"] = [t.strip() for t in a.tickets.split(",") if t.strip()]
    with open(path, "x") as f:
        f.write(json.dumps(doc, indent=1) + "\n")
    print(f"reading: {root}\nwrote: {path}")
    return 0


# ---- brief ------------------------------------------------------------------------------------------
def _load_plan(paper, a):
    path = Path(a.plan) if getattr(a, "plan", None) else _plan_path(paper, a.run)
    if not path.exists():
        return None, path
    return json.loads(path.read_text()), path


def _brief(a):
    root, paper = _paper(a.data)
    plan, path = _load_plan(paper, a)
    if plan is None:
        raise Refused(f"run {a.run} has no plan file at {path}")
    figs = ", ".join(f"{plan[k]} {UNITS[k]}" for k in BUDGET_KEYS)
    print(f"YOUR LIMITS, written before you started in {path}: {figs}. "
          f"Tokens are {plan.get('max_tokens_is', 'the total for the run')}; graph writes are "
          f"{plan.get('max_graph_writes_is', 'writes into the real graph')}. "
          f"COUNT your own tool calls as you go and report the true count. "
          f"On reaching any limit: {plan.get('on_reaching_a_limit', ON_LIMIT)}.")
    return 0


# ---- check ------------------------------------------------------------------------------------------
def _read_transcript(path):
    op = gzip.open if str(path).endswith(".gz") else open
    ts, replies, tools, subs, usage = [], {}, {}, 0, {}
    with op(path, "rt") as f:
        for l in f:
            if not l.strip():
                continue
            d = json.loads(l)
            if d.get("timestamp"):
                ts.append(datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")))
            m = d.get("message") or {}
            if m.get("role") != "assistant":
                continue
            mid = m.get("id") or f"line{len(replies)}"
            replies[mid] = True
            if m.get("usage"):
                usage[mid] = m["usage"]
            c = m.get("content")
            for it in c if isinstance(c, list) else []:
                if isinstance(it, dict) and it.get("type") == "tool_use":
                    tools[it.get("id") or f"{mid}:{len(tools)}"] = it.get("name")
    names = list(tools.values())
    u = lambda k: sum(x.get(k) or 0 for x in usage.values())
    return {"first": ts[0] if ts else None,
            "wall": (ts[-1] - ts[0]).total_seconds() if len(ts) > 1 else None,
            "replies": len(replies),
            "tools": sum(1 for n in names if n != "SubagentHandback"),
            "subs": sum(1 for n in names if n in ("Agent", "Task")),
            "tokens": (u("input_tokens"), u("cache_creation_input_tokens"), u("cache_read_input_tokens"),
                       u("output_tokens"))}


def _graph_writes(root, run):
    g = root / "graph"
    files = list(g.glob("nodes/*.jsonl")) + list(g.glob("edges/*.jsonl"))
    if not files:
        return None
    tag, n = f"run:{run:04d}", 0
    for f in files:
        for l in f.read_text().splitlines():
            if l.strip() and json.loads(l).get("written_by") == tag:
                n += 1
    return n


def _rel(root, path):
    try:
        return Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        return None


def _is_repo(root):
    r = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def _git_history(root, path):
    rel = _rel(root, path)
    if rel is None:
        return False
    r = subprocess.run(["git", "-C", str(root), "log", "--oneline", "--", str(rel)], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def _git_state(root, path):
    """('outside'|'tracked_no_add'|'not_in_git'|'changed'|'unchanged', commit time, sha256 now, sha256 at the add commit)."""
    rel = _rel(root, path)
    if rel is None:
        return "outside", None, None, None
    r = subprocess.run(["git", "-C", str(root), "log", "--diff-merges=first-parent", "--diff-filter=A",
                        "--name-only", "--format=COMMIT %H %cI", "--", str(rel)], capture_output=True, text=True)
    rows = [x.split()[1:] for x in r.stdout.splitlines() if x.startswith("COMMIT ")] if r.returncode == 0 else []
    if not rows:
        t = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", str(rel)], capture_output=True)
        return ("tracked_no_add" if t.returncode == 0 else "not_in_git"), None, None, None
    h, when = min(rows, key=lambda x: datetime.fromisoformat(x[1]))
    then = subprocess.run(["git", "-C", str(root), "show", f"{h}:{rel}"], capture_output=True).stdout
    now = Path(path).read_bytes()
    sn, st = hashlib.sha256(now).hexdigest(), hashlib.sha256(then).hexdigest()
    return ("unchanged" if sn == st else "changed"), datetime.fromisoformat(when), sn, st


def _check(a):
    root, paper = _paper(a.data)
    if a.plan:
        print(f"PAIRED CHECK: the plan read is {a.plan}, given by hand; "
              f"this is not a check of run {a.run} against its own plan in git")
    print(f"reading: {root}")
    plan, path = _load_plan(paper, a)
    tpath = Path(a.transcript) if a.transcript else paper / "transcripts" / f"run-{a.run:04d}.jsonl.gz"
    tr = _read_transcript(tpath) if tpath.exists() else None
    line = _newest(paper, a.run)
    fig, why = {}, {}
    if tr:
        print(f"figures: the transcript {tpath}")
        fig.update(max_model_calls=tr["replies"], max_tool_calls=tr["tools"], max_sub_agents=tr["subs"],
                   max_wall_clock_s=tr["wall"])
    elif line:
        print("figures: the run's own newest line in the record (no transcript)")
        fig.update(max_model_calls=line.get("model_replies"), max_tool_calls=line.get("tool_calls"),
                   max_wall_clock_s=None if line.get("wall_clock_ms") is None else line["wall_clock_ms"] / 1000)
        why["max_sub_agents"] = "the record's line does not count sub-agents and there is no transcript"
    else:
        print("figures: none, the run has no line and no transcript")
    for k in ("max_model_calls", "max_tool_calls", "max_wall_clock_s"):
        if fig.get(k) is None:
            why[k] = "no figure on the line and no transcript"
    if line and line.get("tokens_reported") is not None:
        fig["max_tokens"] = line["tokens_reported"]
    else:
        why["max_tokens"] = "no harness total on the run's line: this limit cannot be shown kept"
    why["max_concurrent_workers"] = "not in a transcript"
    why["max_retries"] = "not in a transcript"
    gw = _graph_writes(root, a.run)
    if gw is None:
        why["max_graph_writes"] = "no graph/nodes or graph/edges here"
    else:
        fig["max_graph_writes"] = gw
    bad, unmeasured = False, 0
    for k in BUDGET_KEYS:
        lim = plan[k] if plan else None
        f = fig.get(k)
        lead = f"{k}: plan {lim}, " if plan else f"{k}: no plan, "
        if f is None:
            unmeasured += 1
            print(f"{lead}reached -, cannot be measured here ({why.get(k, 'no figure')})")
        else:
            f = round(f, 1) if isinstance(f, float) else f
            if not plan:
                print(f"{lead}reached {f}")
            elif f > lim:
                bad = True
                print(f"{lead}reached {f}, PASSED")
            else:
                print(f"{lead}reached {f}, kept" + (" (at the limit, not passed)" if f == lim else ""))
        if k == "max_tokens" and plan:
            print("max_tokens is: " + plan.get("max_tokens_is", "the plan holds no max_tokens_is"))
        if k == "max_tokens" and f is None:
            earlier = [d["tokens_reported"] for d in _of_run(paper, a.run)[:-1] if d.get("tokens_reported") is not None]
            if earlier:
                print(f"an earlier line of this run holds a harness total of {earlier[-1]}; "
                      "the newest line holds none")
    if tr:
        i, cw, cr, o = tr["tokens"]
        print(f"transcript tokens: input fresh {i}, cache written {cw}, cache read {cr}, output {o}")
    print(f"limits that could not be measured: {unmeasured} of {len(BUDGET_KEYS)}")
    if plan is None:
        print(f"run {a.run} has no plan file at {path}: its limits were not written before it started")
        return 1
    print(f"plan: {path}")
    if a.plan:
        print("plan in git: not measured: a paired plan is not the run's own plan in git")
        print("git order: not measured: a paired plan")
        return 3
    state, when, sn, st = _git_state(root, path)
    start, start_msg, start_note = _start(tr, line)
    if state == "not_in_git":
        bad = True
        print("plan in git: the plan file is not in git: a limit that is not in git before the run is not a "
              "written limit")
    elif state == "tracked_no_add":
        bad = True
        print("plan in git: tracked, and the commit that added it could not be found")
    else:
        if state == "changed":
            bad = True
            print(f"plan in git: the plan was changed after it was written: sha256 of the file read {sn}, "
                  f"sha256 at the add commit {st}")
        else:
            print(f"plan in git: unchanged since it was added (sha256 {sn})")
        if start_note:
            print(f"git order: {start_note}")
        if start is None:
            print("git order: " + (start_msg or "not measured: the run's line holds no start time and no "
                                   "transcript is kept"))
        elif when.astimezone(start.tzinfo) <= start:
            print(f"git order: committed {when.isoformat()} before the run began {start.isoformat()}")
        else:
            bad = True
            print(f"git order: committed {when.isoformat()} AFTER the run began {start.isoformat()}")
    return 1 if bad else 0


def _start(tr, line):
    """(start, message, note): the transcript's first line, else the line's started_at read as ISO time."""
    if tr and tr["first"]:
        return tr["first"], None, None
    v = line.get("started_at") if line else None
    if v is None or v == "":
        return None, None, None
    try:
        if not isinstance(v, str):
            raise ValueError
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None, f"not measured: the run's line holds a start time that cannot be read ({v})", None
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc), None, "read as UTC: the line names no zone"
    return t, None, None


def main(argv=None):
    p = argparse.ArgumentParser(prog="run_plan")
    sub = p.add_subparsers(dest="verb", required=True)
    for v in ("write", "brief", "check"):
        s = sub.add_parser(v)
        s.add_argument("--data", required=True)
        s.add_argument("--run", type=int, required=True)
        if v == "write":
            s.add_argument("--agent", required=True)
            s.add_argument("--model", required=True)
            s.add_argument("--task", required=True)
            s.add_argument("--session")
            s.add_argument("--tickets")
            s.add_argument("--note")
            for k in BUDGET_KEYS:
                s.add_argument("--" + k.replace("_", "-"), dest=k, type=int)
        else:
            s.add_argument("--plan")
        if v == "check":
            s.add_argument("--transcript")
    a = p.parse_args(argv)
    try:
        return {"write": _write, "brief": _brief, "check": _check}[a.verb](a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
