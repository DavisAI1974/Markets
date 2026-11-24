"""Ticket 03b: is every run of the other agents audited, each with its own row in an auditor's report?

    python3 -m tools.kgraph.auditor_called [--data <markets-data>] [--ticket NN] [--at <commit>]

Writes nothing anywhere. Reads the run record, the auditor's reports and TICKET_RUNS.json of a
markets-data checkout (the record and the ticket file as they stand, or at --at read with git; a
report always at the commit its own `audit_report` names). Nothing is averaged or summed across runs.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

WORK = "tasks/family-research-20261022/research-union-current"
PAPER = f"{WORK}/paper-trading-20261123"
RUNS = f"{PAPER}/agent-runs.jsonl"
TICKETS = f"{PAPER}/tickets-44-20261124/TICKET_RUNS.json"
ROSTER = ("scout", "builder", "reviewer", "frankie-performance-auditor")
AUDITOR = "frankie-performance-auditor"
LIMIT_KEYS = ("max_model_calls", "max_sub_agents", "max_concurrent_workers", "max_tool_calls",
              "max_tokens", "max_wall_clock_s", "max_retries", "max_graph_writes")


def has_row(text: str, n: int) -> bool:
    """A line of the report names run n as `run N`, `Run N` or `rN`, as a whole token."""
    pat = re.compile(rf"(?<![A-Za-z0-9])(?:[Rr]un\s+|r){n}(?![0-9])")
    return any(pat.search(ln) for ln in text.splitlines())


def agent_of(d: dict) -> str:
    """agent_type when the line has it, else the first word of role (lower-cased, punctuation stripped)."""
    if d.get("agent_type"):
        return str(d["agent_type"])
    words = str(d.get("role", "")).lower().split()
    return re.sub(r"[^a-z0-9-]", "", words[0]) if words else ""


def _git(root: Path, commit: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def read(root: Path, path: str, at: str | None) -> str | None:
    if at:
        return _git(root, at, path)
    p = root / path
    return p.read_text(encoding="utf-8") if p.exists() else None


@dataclass
class Report:
    lines: dict = field(default_factory=dict)       # run -> its lines in file order
    with_row: list = field(default_factory=list)
    record_only: list = field(default_factory=list)
    not_audited: list = field(default_factory=list)
    auditors: dict = field(default_factory=dict)    # run -> the report(s) its lines name
    outside: dict = field(default_factory=dict)     # run -> agent/role
    notes: dict = field(default_factory=dict)       # run -> why a named run is not cleared
    stand: dict = field(default_factory=dict)       # run -> where it stands
    root: Path | None = None
    at: str | None = None

    def newest(self, run: int) -> dict:
        return self.lines[run][-1]


def analyse(root, at: str | None = None) -> Report:
    root = Path(root)
    text = read(root, RUNS, at)
    if text is None:
        raise FileNotFoundError(f"no {RUNS} in {root}" + (f" at {at}" if at else ""))
    rep = Report(root=root, at=at)
    for raw in text.splitlines():
        if raw.strip():
            d = json.loads(raw)
            rep.lines.setdefault(d["run"], []).append(d)
    # what each auditor run names: the UNION over all its lines
    cleared: dict[int, list] = {}      # run -> [(auditor run, in its record_only)]
    for arun, ls in rep.lines.items():
        if not any(agent_of(d) == AUDITOR for d in ls):
            continue
        reports = [d["audit_report"] for d in ls if d.get("audit_report")]
        rep.auditors[arun] = [f"{r.get('path')}@{r.get('commit')}" for r in reports]
        names = sorted({n for d in ls for n in d.get("audits", [])})
        rec_only = {n for d in ls for n in d.get("record_only", [])}
        texts, why = [], None
        if not reports:
            why = f"auditor run {arun}: no line has an audit_report"
        for r in reports:
            if not r.get("commit"):
                why = f"auditor run {arun}: audit_report names {r.get('path')} but no commit"
            else:
                t = _git(root, r["commit"], r["path"])
                if t is None:
                    why = f"auditor run {arun}: report not readable at {r['commit']}"
                else:
                    texts.append(t)
        for n in names:
            if texts and any(has_row(t, n) for t in texts):
                cleared.setdefault(n, []).append((arun, n in rec_only))
            else:
                rep.notes[n] = why or f"auditor run {arun}: its report has no row for run {n}"
    for run in sorted(rep.lines):
        agent = agent_of(rep.newest(run))
        if run in rep.auditors:
            rep.stand[run] = "an auditor's own run"
        elif run in cleared:
            if all(ro for _, ro in cleared[run]):
                rep.record_only.append(run)
                rep.stand[run] = "audited from the record alone"
            else:
                rep.with_row.append(run)
                rep.stand[run] = "audited, its own row in the report"
        else:
            rep.not_audited.append(run)
            rep.stand[run] = "NOT AUDITED" + (f" ({rep.notes[run]})" if run in rep.notes else "")
        if agent not in ROSTER:
            rep.outside[run] = str(rep.newest(run).get("role", agent))
    rep.auditors = {k: v for k, v in rep.auditors.items()}
    return rep


def _limit(rep: Report, run: int) -> str:
    d = rep.newest(run)
    for rel in (d.get("plan"), f"run-plans/run-{run:04d}.json"):
        if not rel:
            continue
        t = read(rep.root, f"{PAPER}/{rel}", rep.at)
        if t is not None:
            p = json.loads(t)
            return f"plan {rel}: " + " ".join(f"{k}={p[k]}" for k in LIMIT_KEYS if k in p)
    return f"budget_tokens={d.get('budget_tokens')} budget_note={d.get('budget_note')}"


def _row(rep: Report, run: int, extra: str = "") -> str:
    d = rep.newest(run)
    agent = rep.outside.get(run) or agent_of(d)
    return (f"run {run} | {agent} | {d.get('model')} | limit told: {_limit(rep, run)} | reached: "
            f"tokens_reported={d.get('tokens_reported')} tool_calls={d.get('tool_calls')} "
            f"wall_clock_ms={d.get('wall_clock_ms')}{extra}")


def _print_lists(rep: Report) -> None:
    print("(1) NOT AUDITED: no auditor's report has a row for the run")
    for n in rep.not_audited:
        print(_row(rep, n, f" | {rep.notes[n]}" if n in rep.notes else ""))
    print("(2) AUDITED FROM THE RECORD ALONE: only an auditor's record_only list names the run")
    for n in rep.record_only:
        print(_row(rep, n))
    print("(3) OUTSIDE THE ROSTER (scout, builder, reviewer, frankie-performance-auditor)")
    for n in sorted(rep.outside):
        print(_row(rep, n, f" | audited: {'no' if n in rep.not_audited else 'yes'}"))
    print("(4) THE AUDITOR'S OWN RUNS: no other run audits them")
    for n in sorted(rep.auditors):
        print(_row(rep, n, f" | report: {', '.join(rep.auditors[n]) or 'none named'}"))
    print(f"COUNTS runs={len(rep.lines)} not_audited={len(rep.not_audited)} "
          f"record_only={len(rep.record_only)} with_own_row={len(rep.with_row)} "
          f"outside_roster={len(rep.outside)} auditor_runs={len(rep.auditors)}")


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python3 -m tools.kgraph.auditor_called", description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", help="markets-data checkout (default: MARKETS_DATA or the checkout beside Markets)")
    ap.add_argument("--ticket", help="a ticket id from TICKET_RUNS.json, for example 03b")
    ap.add_argument("--at", help="read the record and the ticket file as they were at this markets-data commit")
    a = ap.parse_args(argv)
    from tools.kgraph.store import markets_data_root

    root = markets_data_root(a.data)
    rep = analyse(root, a.at)
    if not a.ticket:
        _print_lists(rep)
        return 1 if rep.not_audited else 0
    raw = read(root, TICKETS, a.at)
    if raw is None:
        print(f"ticket {a.ticket}: no ticket file {TICKETS}" + (f" at {a.at}" if a.at else ""))
        return 1
    tix = json.loads(raw)
    if a.ticket == "note" or a.ticket not in tix:
        print(f"ticket {a.ticket}: no entry in TICKET_RUNS.json")
        return 1
    code = 0
    print(f"ticket {a.ticket}: runs {tix[a.ticket]}")
    for n in tix[a.ticket]:
        if n not in rep.lines:
            print(f"run {n} | no line in the run record | NOT AUDITED")
            code = 1
            continue
        print(_row(rep, n, f" | stands: {rep.stand[n]}"))
        code = 1 if n in rep.not_audited else code
    return code


if __name__ == "__main__":
    raise SystemExit(main())
