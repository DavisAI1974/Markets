"""The ready check of a loop: what would be true if it were started, said before it is. It starts nothing.

  python3 -m tools.ratchet.ready --program <control file> [--data <markets-data>] [--mailbox DIR] [--scratch DIR]

Prints one JSON object: each thing looked at is its own entry (what was looked at, what was found, ready or
not), then `ready` and the list of entries that are not ready. The exit code is 0 either way: it is a report.

It never runs the control file's run command and never opens a stored tape file (names and sizes only, from
the archive's MANIFEST.json). The one thing it runs is `python3 -c "import <module>"` for each module the
command names, in the repository, with a short timeout, to see that the module imports.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.ratchet.loop import guard
from tools.ratchet.program import BUDGET_KEYS, Program, ProgramError, glob_match, load

EASTERN = ZoneInfo("America/New_York")
IMPORT_TIMEOUT_S = 30
NO_DIRECTION = ("no figure is chosen for keeping or reverting: every trial is recorded, "
                "none is kept or reverted")
HAND_OFF = "this command starts nothing; starting the loop needs Greg's go"


def _git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _entry(name, looked_at, found, ready):
    return {"name": name, "looked_at": looked_at, "found": found, "ready": bool(ready)}


def trade_day_clock_days(day: dt.date):
    """-> (the UTC clock days that hold the trade day itself, the UTC clock days the engine's scratch checkout
    takes). A trade day is 6 pm Eastern the evening before to 5 pm Eastern on the named date."""
    def utc_date(d, hour):
        return dt.datetime(d.year, d.month, d.day, hour, tzinfo=EASTERN).astimezone(dt.timezone.utc).date()
    start = utc_date(day - dt.timedelta(days=1), 18)
    end = utc_date(day, 17)
    span = [start + dt.timedelta(days=k) for k in range((end - start).days + 1)]
    sunday = day - dt.timedelta(days=(day.weekday() + 1) % 7)       # the week's Sunday start-up
    last = utc_date(day, 18)
    week = [sunday + dt.timedelta(days=k) for k in range((last - sunday).days + 1)]
    return span, week


def _expand(token, env):
    return re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", lambda m: env.get(m.group(1), m.group(0)), token)


def check(program_path, data=None, mailbox=None, scratch=None) -> dict:
    entries = []
    add = lambda *a: entries.append(_entry(*a))
    out = {"program": str(program_path)}
    try:
        program: Program = load(program_path)
    except (ProgramError, OSError) as e:
        add("control file loads", str(program_path), f"refused: {e}", False)
        return _finish(out, entries, None)
    add("control file loads", str(program_path), f"loop {program.loop}", True)

    base = program.path.parent
    repo = (Path(program.repo) if Path(program.repo).is_absolute() else base / program.repo).resolve()
    head = None
    if not (repo / ".git").exists():
        add("repository exists", str(repo), "no git repository there", False)
    else:
        add("repository exists", str(repo), "a git repository", True)
        _, shallow, _ = _git(repo, "rev-parse", "--is-shallow-repository")
        add("repository is complete (not shallow)", f"git rev-parse --is-shallow-repository in {repo}",
            "complete" if shallow == "false" else f"shallow={shallow}: a shallow repository names every rule's commit wrongly",
            shallow == "false")
        rc, head, err = _git(repo, "rev-parse", "HEAD")
        add("repository HEAD", "git rev-parse HEAD", head if rc == 0 else err, rc == 0)
        head = head if rc == 0 else None

    if head:
        rc, listing, _ = _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
        files = listing.splitlines() if rc == 0 else []
        for g in program.mutable:
            hits = [f for f in files if glob_match(g, f)]
            add(f"mutable file {g}", f"committed at HEAD {head[:10]}", hits if hits else "not committed at HEAD",
                bool(hits))
            prot, outside = guard(program, hits)
            add(f"guard on mutable {g}", "guard() on the committed paths of this entry",
                {"protected": prot, "outside_mutable": outside}, bool(hits) and not prot and not outside)
        sample = next((f for f in files for g in program.protected if glob_match(g, f)), None)
        if sample:
            prot, outside = guard(program, [sample])
            add("guard reports a protected path", f"guard() on the real path {sample}", {"protected": prot},
                prot == [sample])
        else:
            add("guard reports a protected path", "no committed file matches `protected`", "nothing to test with", False)

    # the run command: variables, paths, modules
    env = dict(os.environ, **program.env)
    names = sorted(set(re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", program.command)))
    for nm in names:
        add(f"variable {nm}", "the environment of this check and the control file's run.env",
            "set" if nm in env else "not set", nm in env)
    run_dir_pattern = f"{scratch or '<scratch>'}/{program.loop}/worktree/{program.cwd}"
    try:
        tokens = shlex.split(program.command)
    except ValueError:
        tokens = program.command.split()
    run_dir = Path(os.path.normpath(run_dir_pattern))
    wt = Path(os.path.normpath(f"{scratch or '<scratch>'}/{program.loop}/worktree"))
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and "=" not in tok:
            continue
        if i > 0 and tokens[i - 1] == "-c":      # the program text of `python3 -c "..."` is code, not a path
            continue
        val = tok.split("=", 1)[1] if tok.startswith("-") else tok
        val = _expand(val, env)
        if "$" in val or not ("/" in val or val.startswith(".")):
            continue
        p = Path(os.path.normpath(val if os.path.isabs(val) else str(run_dir / val)))
        if os.path.isabs(val):
            add(f"path {val}", "an absolute path in the run command", "exists" if p.exists() else "does not exist",
                p.exists())
        elif wt == p or wt in p.parents:
            rel = p.relative_to(wt).as_posix() if p != wt else "."
            there = bool(head) and (rel == "." or _git(repo, "cat-file", "-e", f"HEAD:{rel}")[0] == 0
                                    or _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", rel)[1] != "")
            add(f"path {val}", f"from the run directory {run_dir} (inside the worktree: looked for {rel} at HEAD)",
                "committed at HEAD" if there else "not at HEAD", there)
        else:
            ex = scratch is not None and p.exists()
            add(f"path {val}", f"from the run directory {run_dir}",
                f"resolves to {p}, outside the worktree (nothing is placed there by the loop)"
                + (": it exists" if ex else ": it does not exist" if scratch else ""), ex)
    for i, tok in enumerate(tokens[:-1]):
        if tok == "-m" and i > 0 and os.path.basename(tokens[i - 1]).startswith("python"):
            mod = tokens[i + 1]
            try:
                r = subprocess.run(["python3", "-c", f"import {mod}"], cwd=repo, capture_output=True, text=True,
                                   timeout=IMPORT_TIMEOUT_S, env=env)
                add(f"module {mod}", f'python3 -c "import {mod}" in {repo}',
                    "imports" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["failed"])[-1],
                    r.returncode == 0)
            except subprocess.TimeoutExpired:
                add(f"module {mod}", f'python3 -c "import {mod}" in {repo}', f"no answer in {IMPORT_TIMEOUT_S}s", False)

    # the stored tape of the trade day in the command
    if data:
        root = Path(data).resolve()
        add("markets-data folder", str(root), "exists" if root.is_dir() else "does not exist", root.is_dir())
        m = re.search(r"--trade-day[ =](\d{4}-\d{2}-\d{2})", program.command)
        mk = re.search(r"--market[ =](\S+)", program.command)
        market = mk.group(1) if mk else "nymex-ng"
        if not m:
            add("stored tape of the trade day", "--trade-day in the run command", "none named", True)
        elif root.is_dir():
            day = dt.date.fromisoformat(m.group(1))
            mj = repo / "paper_platform" / "markets" / f"{market}.json"
            archive = json.loads(mj.read_text(encoding="utf8")).get("archive") if mj.exists() else None
            if archive is None and market == "nymex-ng":
                archive = "data/nymex_mbo/ng_v0_oct2023"
            if archive is None:
                add("stored tape of the trade day", f"market {market}", "no archive named for this market", False)
            else:
                span, week = trade_day_clock_days(day)
                man = root / archive / "MANIFEST.json"
                if not man.is_file():
                    add("stored tape of the trade day", str(man), "no MANIFEST.json there", False)
                else:
                    listed = json.loads(man.read_text(encoding="utf8"))["files"]
                    for d in sorted(set(span) | set(week)):
                        why = ("holds part of the trade day" if d in span else "") + (
                            "; " if d in span and d in week else "") + (
                            "taken by the engine's scratch checkout (the week from its Sunday)" if d in week else "")
                        hit = next((e for e in listed if d.strftime("%Y%m%d") in e.get("file", e.get("name", ""))), None)
                        if not hit:
                            add(f"tape file of UTC clock day {d}", f"{man} ({why})", "not listed in the manifest", False)
                            continue
                        f = root / archive / hit.get("file", hit.get("name"))
                        size = f.stat().st_size if f.is_file() else None
                        ok = size is not None and size == hit.get("bytes")
                        add(f"tape file of UTC clock day {d}", f"{f} ({why}); name and size only, never opened",
                            {"file": f.name, "manifest_bytes": hit.get("bytes"), "on_disk_bytes": size,
                             "is_a_file": f.is_file()}, ok)
    else:
        add("markets-data folder", "no --data given", "not checked", True)

    if mailbox:
        mb = Path(mailbox)
        old = sorted(p.name for p in mb.glob("trial-*")) if mb.is_dir() else []
        add("mailbox folder", str(mb), ("holds " + ", ".join(old) + ": a trial that finds its brief.md there is a crash"
                                        if old else "free" if mb.is_dir() else "does not exist yet (made when the loop starts)"),
            not old and (mb.is_dir() or mb.parent.is_dir()))

    # the declared budget, the metric, the runs
    bud = {k: (program.budget[k] if program.budget[k] is not None else "not declared") for k in BUDGET_KEYS}
    add("budget", "every key of budget", bud, True)
    direction = program.metric_direction
    add("metric", "metric of the control file",
        {"name": program.metric_name, "direction": direction, "unit": program.metric_unit,
         "meaning": f"direction null: {NO_DIRECTION}" if direction is None else f"kept or reverted by {program.metric_name}, {direction}"},
        True)
    mt = program.budget["max_trials"]
    runs = {"trial_0": 1, "max_trials": mt if mt is not None else "not declared",
            "engine_runs_allowed": (1 + mt) if mt is not None else "not limited by max_trials",
            "stop_after_trials": program.stop_after_trials if program.stop_after_trials is not None else "not declared"}
    if direction is None and program.stop_after_trials_without_a_keep is not None:
        runs["note"] = (f"stop.after_trials_without_a_keep is {program.stop_after_trials_without_a_keep} but the loop "
                        "applies it only when a direction is set")
    add("engine runs the budget allows", "trial 0 plus max_trials", runs, True)
    out["hand_off"] = HAND_OFF
    return _finish(out, entries, head)


def _finish(out, entries, head):
    out["head"] = head
    out["entries"] = entries
    out["not_ready"] = [e["name"] for e in entries if not e["ready"]]
    out["ready"] = not out["not_ready"]
    out.setdefault("hand_off", HAND_OFF)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--data", help="a markets-data checkout")
    ap.add_argument("--mailbox")
    ap.add_argument("--scratch", help="the scratch folder the loop will be given (to resolve paths from the worktree)")
    a = ap.parse_args(argv)
    print(json.dumps(check(a.program, a.data, a.mailbox, a.scratch), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
