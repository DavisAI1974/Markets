"""Stage 3 of the graph adoption plan: the keep-if-better loop (ratchet), one control file per loop.

One trial: a proposer changes a worktree on the branch `ratchet/<loop>`; the guard checks which files
changed; the change is committed; the run command is run; every declared figure is parsed; the trial is
kept (the branch stays at its commit) or reverted / crashed (the branch goes back to the last kept
commit and the trial's commit stays addressable as `refs/ratchet/<loop>/trial-<n>`); the trial is pushed
to the experiment record (tools/exp_dag.py) with its status. Nothing is averaged, ranked or dropped.
Trial 0 is the baseline run of the repository's own HEAD, without any change.

It runs only where it is called: no workflow is dispatched, no pod or cloud service is touched.

WHAT THE GUARD COVERS, AND WHAT IT DOES NOT. The guard covers what a PROPOSER changes inside the worktree:
every file git lists as changed or new, and every file git IGNORES that is new or changed since the proposer
was called (an ignored file is read by the run command like any other, so it counts as a change outside
`mutable`: the trial is not run and is recorded as crash, "touched <file>"). Ignored files are cleaned from
the worktree between trials too. The guard does NOT cover what the RUN COMMAND itself does elsewhere: a command
that writes outside the worktree (through an environment variable, an absolute path, `gh workflow run`) is
neither checked nor undone. A control file's command must therefore only read and print. Each trial records the
command and the NAMES of the environment variables the control file sets (never their values) so the claim can
be checked.
A proposer that raises (any exception) ends that trial as a recorded crash with the exception's text, the
worktree goes back to the last kept commit, and the report is always returned (and written to `escalate_file`
when one is named and there is an escalation).

  python3 -m tools.ratchet.loop --program program.md --replay <commit> [<commit> ...] --scratch DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from tools.exp_dag import ExpDag
from tools.kgraph.sources import code_stamp
from tools.ratchet.program import Program, glob_match, load

USAGE_KEYS = ("model_calls", "tokens", "tool_calls", "sub_agents")
USAGE_BUDGET = {"model_calls": "max_model_calls", "tokens": "max_tokens", "tool_calls": "max_tool_calls",
                "sub_agents": "max_sub_agents"}
NOT_REPORTED = "not reported"
IDENTITY = ["-c", "user.name=ratchet loop", "-c", "user.email=ratchet-loop@localhost",
            "-c", "commit.gpgsign=false"]


class ProposalFailed(RuntimeError):
    def __init__(self, message, hypothesis=None):
        super().__init__(message)
        self.hypothesis = hypothesis


def git(cwd, *args, check=True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


class ReplayCommits:
    """Applies, one per trial, the real change of each given existing commit (a proposer for checking
    the harness on real history without inventing a change)."""

    def __init__(self, repo, commits):
        self.repo = str(repo)
        self.commits = [git(self.repo, "rev-parse", "--verify", c + "^{commit}").strip() for c in commits]
        self.next = 0

    def unresolved(self):
        return self.commits[self.next:]

    def __call__(self, worktree, trial_no, history):
        if self.next >= len(self.commits):
            return None
        sha = self.commits[self.next]
        self.next += 1
        subject = git(self.repo, "log", "-1", "--format=%s", sha).strip()
        r = subprocess.run(["git", "cherry-pick", "--no-commit", sha], cwd=worktree,
                           capture_output=True, text=True)
        if r.returncode != 0:
            detail = (r.stderr.strip() or r.stdout.strip()).splitlines()
            git(worktree, "cherry-pick", "--quit", check=False)
            git(worktree, "reset", "-q", "--hard", "HEAD")
            git(worktree, "clean", "-fdqx")
            raise ProposalFailed(f"commit {sha[:10]} did not apply here: {detail[0] if detail else ''}",
                                 hypothesis=f"replay of {sha[:10]}: {subject}")
        return {"hypothesis": f"replay of {sha[:10]}: {subject}", "agent_run": None, "usage": None}


# ---- pieces -------------------------------------------------------------------------------------
def changed_files(worktree) -> list[str]:
    out = git(worktree, "status", "--porcelain", "-z", "-uall")
    parts, files, i = out.split("\0"), [], 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        files.append(e[3:])
        if e[0] in "RC":          # a rename carries its old path as the next field
            files.append(parts[i])
            i += 1
    return files


def ignored_state(worktree) -> dict:
    """Every file git ignores in the worktree -> the hash of its content (the guard's view of ignored files)."""
    out = git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    state = {}
    for rel in filter(None, out.split("\0")):
        f = Path(worktree) / rel
        try:
            state[rel] = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "not a file"
        except OSError as e:
            state[rel] = f"unreadable: {e}"
    return state


def ignored_changes(before: dict, after: dict) -> list[str]:
    """The ignored files that are new or changed since `before` (a file that was removed is a change too)."""
    return sorted(f for f in set(before) | set(after) if before.get(f) != after.get(f))


def guard(program: Program, files: list[str], ignored: list[str] = ()):
    """-> (protected files touched, files outside mutable). A new or changed ignored file is outside
    `mutable` whatever its name, unless it is protected (then it is reported as protected)."""
    prot = [f for f in list(files) + list(ignored) if any(glob_match(g, f) for g in program.protected)]
    outside = [f for f in files if f not in prot and not any(glob_match(g, f) for g in program.mutable)]
    outside += [f for f in ignored if f not in prot and f not in outside]
    return prot, outside


def _number(s):
    s = str(s).strip().replace(",", "")
    try:
        return int(s)
    except ValueError:
        return float(s)


def parse_figures(program: Program, stdout: str, stderr: str):
    """-> (figures {name: value}, unparsed [name]). Regex: the last match in stdout then stderr."""
    figs, bad = {}, []
    last = next((l for l in reversed(stdout.splitlines()) if l.strip()), "")
    doc = None
    try:
        doc = json.loads(last)
    except (json.JSONDecodeError, ValueError):
        pass
    for f in program.figures:
        try:
            if f.kind == "regex":
                hits = list(re.finditer(f.pattern, stdout)) or list(re.finditer(f.pattern, stderr))
                figs[f.name] = _number(hits[-1].group(f.group))
            else:
                v = doc
                for k in f.key.split("."):
                    v = v[k]
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError
                figs[f.name] = v
        except (IndexError, KeyError, TypeError, ValueError, AttributeError):
            bad.append(f.name)
    return figs, bad


def _run_once(program: Program, worktree: Path, log):
    cwd = (worktree / program.cwd).resolve()
    env = dict(os.environ, **program.env)
    t0 = time.monotonic()
    p = subprocess.Popen(program.command, shell=True, cwd=cwd, env=env, text=True, start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=program.timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        timed_out = True
    dt = time.monotonic() - t0
    log.write(f"--- exit {p.returncode}{' TIMEOUT' if timed_out else ''} after {dt:.2f}s\n"
              f"--- stdout\n{out}\n--- stderr\n{err}\n")
    return p.returncode, timed_out, out or "", err or "", dt


def _better(program: Program, value, best) -> bool:
    if program.metric_direction == "higher":
        return value > best if program.keep == "strictly_better" else value >= best
    return value < best if program.keep == "strictly_better" else value <= best


# ---- the loop -----------------------------------------------------------------------------------
def run_loop(program_path, proposer, *, scratch, data_root=None, exp_dir=None) -> dict:
    program = program_path if isinstance(program_path, Program) else load(program_path)
    base_dir = program.path.parent if program.path else Path.cwd()
    repo = Path(program.repo) if Path(program.repo).is_absolute() else (base_dir / program.repo)
    repo = repo.resolve()
    dag = ExpDag(data_root or program.data_root, exp_dir=exp_dir)
    stamp = code_stamp("tools.ratchet.loop")
    scratch = Path(scratch).resolve()
    work = scratch / program.loop
    wt, logs = work / "worktree", work / "logs"
    if wt.exists():
        raise RuntimeError(f"{wt} already exists: a loop works in a fresh scratch folder")
    logs.mkdir(parents=True, exist_ok=True)
    branch = f"ratchet/{program.loop}"
    head = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "worktree", "add", "-q", "-b", branch, str(wt), head)
    ref = lambda n: f"refs/ratchet/{program.loop}/trial-{n}"
    bud = program.budget
    env_base = {"run_command": program.command, "repo": repo.name, "python": platform.python_version(),
                "cwd": program.cwd, "env_names": sorted(program.env),
                "guard": "covers what a proposer changes in the worktree (ignored files too), not what the run command does elsewhere"}

    trials, kept, reverted, crashed, recorded = [], [], [], [], []
    history, escalations = [], []
    state = {"graph_writes": 0, "retries": 0}
    usage = {k: None for k in USAGE_KEYS}
    usage_from = 0
    t_start = time.monotonic()
    anchor = {"id": None, "commit": head, "value": None}   # the last kept trial (the best kept)
    streak = no_keep = proposed = 0
    stopped = None

    def push(n, hypothesis, status, parent, commit, figs, runtime, note, agent_run, attempts=()):
        metrics = [{"name": f.name, "value": figs[f.name], "unit": f.unit, "note": None}
                   for f in program.figures if f.name in figs]
        tid = dag.push(hypothesis=hypothesis, status=status, parent=parent, agent_run=agent_run,
                       change={"repo": repo.name, "commit": commit}, metrics=metrics, runtime_s=runtime,
                       environment=dict(env_base, attempts=list(attempts)), loop=program.loop, note=note,
                       written_by=stamp)
        state["graph_writes"] += 1
        row = {"n": n, "id": tid, "commit": commit, "status": status, "figures": dict(figs),
               "note": note, "hypothesis": hypothesis, "parent": parent, "runtime_s": runtime}
        history.append(row)
        trials.append(tid)
        {"kept": kept, "reverted": reverted, "crash": crashed, "recorded": recorded}[status].append(tid)
        return tid

    def execute(n):
        """Run the command (with retries on a crash) -> (figs, note, runtime, attempts). attempts is a list,
        one entry an attempt: its exit code, whether it timed out, what was parsed (and what was not) and
        its own note. note set = crash; a crashed trial keeps the figures that were parsed (the last
        attempt's) and the note of every attempt."""
        left = int(bud["max_retries"] or 0)
        attempts, figs, dt = [], {}, 0.0
        with (logs / f"trial-{n}.log").open("w", encoding="utf-8") as log:
            while True:
                log.write(f"=== attempt {len(attempts) + 1}: {program.command}\n")
                code, timed_out, out, err, dt = _run_once(program, wt, log)
                figs, bad = parse_figures(program, out, err)
                if timed_out:
                    one = f"crash: timeout after {program.timeout_s}s"
                elif code != 0:
                    one = f"crash: exit code {code}"
                elif bad:
                    one = f"crash: could not parse figure {', '.join(bad)}"
                else:
                    one = None
                attempts.append({"attempt": len(attempts) + 1, "exit_code": code, "timed_out": timed_out,
                                 "parsed": dict(figs), "not_parsed": list(bad), "note": one,
                                 "runtime_s": round(dt, 3)})
                if one is None or left <= 0:
                    break
                left -= 1
                state["retries"] += 1
        notes = [x["note"] for x in attempts if x["note"]]
        if not attempts[-1]["note"]:
            notes = []                                  # the last attempt ran well: no crash
        if not notes:
            return figs, None, dt, attempts
        text = notes[0] if len(attempts) == 1 else "; ".join(
            f"{x['note']} (attempt {x['attempt']})" if x["note"] else f"attempt {x['attempt']} ran" for x in attempts)
        return figs, text + f" (log {logs / f'trial-{n}.log'})", dt, attempts

    def add_usage(u):
        nonlocal usage_from
        if not u:
            return
        usage_from += 1
        for k, v in u.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                usage[k] = (usage[k] or 0) + v

    def settle(n, hypothesis, commit, figs, note, dt, agent_run, attempts, parent_for_record):
        """Decide and push a trial that was run; moves the branch. Returns the status."""
        nonlocal anchor, no_keep
        metric = program.metric_name
        if note:
            status = "crash"
        elif program.metric_direction is None:
            status = "recorded"
        elif anchor["value"] is None or _better(program, figs[metric], anchor["value"]):
            status = "kept"
        else:
            status = "reverted"
            note = (f"figure {metric} was {figs[metric]}, the best kept is {anchor['value']} "
                    f"(trial {anchor['n']}, {anchor['id']})")
        parent = parent_for_record
        tid = push(n, hypothesis, status, parent, commit, figs, dt, note, agent_run, attempts)
        if status in ("kept", "recorded"):
            anchor = {"id": tid, "n": n, "commit": commit, "value": figs.get(metric)}
            no_keep = 0
        else:
            git(wt, "update-ref", ref(n), commit)
            git(wt, "reset", "-q", "--hard", anchor["commit"])
            no_keep += 1
        return status

    def _restore():
        """The worktree back to the last kept commit, ignored files cleaned too."""
        git(wt, "reset", "-q", "--hard", anchor["commit"], check=False)
        git(wt, "clean", "-fdqx", check=False)

    try:
        # trial 0: the baseline, the repository's own HEAD
        figs, note, dt, attempts = execute(0)
        git(wt, "reset", "-q", "--hard", "HEAD")
        git(wt, "clean", "-fdqx")
        anchor["n"] = 0
        st = settle(0, f"baseline: {repo.name} at {head[:10]}, no change", head, figs, note, dt, None, attempts, None)
        git(wt, "update-ref", ref(0), head)
        streak = 1 if st == "crash" else 0
        if st == "crash":
            stopped = "baseline run crashed: no figure to compare trials against"
            escalations.append({"condition": "baseline crashed", "detail": note})
        no_keep = 0

        while stopped is None:
            # stop and budget checks, before a trial is started
            if program.stop_after_trials is not None and proposed >= program.stop_after_trials:
                stopped = f"stop.after_trials reached ({proposed})"
                break
            if program.stop_after_trials_without_a_keep is not None and program.metric_direction \
                    and no_keep >= program.stop_after_trials_without_a_keep:
                stopped = f"stop.after_trials_without_a_keep reached ({no_keep})"
                break
            over = None
            if bud["max_trials"] is not None and proposed >= bud["max_trials"]:
                over = f"max_trials ({bud['max_trials']}) used"
            elif bud["max_wall_clock_s"] is not None and time.monotonic() - t_start >= bud["max_wall_clock_s"]:
                over = f"max_wall_clock_s ({bud['max_wall_clock_s']}) used"
            elif bud["max_graph_writes"] is not None and state["graph_writes"] >= bud["max_graph_writes"]:
                over = f"max_graph_writes ({bud['max_graph_writes']}) used"
            else:
                for k, bk in USAGE_BUDGET.items():
                    if bud[bk] is not None and usage[k] is not None and usage[k] >= bud[bk]:
                        over = f"{bk} ({bud[bk]}) used, as the proposer reported"
            if over:
                stopped = f"budget exhausted: {over}"
                escalations.append({"condition": "budget exhausted", "detail": over})
                break

            n = proposed + 1
            ign_before = ignored_state(wt)
            try:
                prop = proposer(wt, n, [dict(h) for h in history])
            except ProposalFailed as e:
                prop = {"hypothesis": e.hypothesis or f"proposal {n}", "agent_run": None, "usage": None}
                failed = str(e)
            except Exception as e:                    # any other exception ends THIS trial as a recorded crash
                prop = {"hypothesis": f"proposal {n}", "agent_run": None, "usage": None}
                failed = f"the proposer raised {type(e).__name__}: {e}"
                _restore()
            else:
                failed = None
            if prop is None:
                stopped = "the proposer has nothing more to try"
                break
            proposed += 1
            add_usage(prop.get("usage"))
            hyp, agent_run = prop["hypothesis"], prop.get("agent_run")
            parent = anchor["id"]

            if failed:
                streak += 1
                push(n, hyp, "crash", parent, anchor["commit"], {}, None, f"crash: {failed}", agent_run)
                _restore()
            else:
                files = changed_files(wt)
                ign = ignored_changes(ign_before, ignored_state(wt))
                if not files and not ign:
                    streak += 1
                    push(n, hyp, "crash", parent, anchor["commit"], {}, None,
                         "crash: the proposer made no change", agent_run)
                else:
                    if files:
                        git(wt, "add", "-A")
                        git(wt, *IDENTITY, "commit", "-q", "--no-verify", "-m", hyp)
                        commit = git(wt, "rev-parse", "HEAD").strip()
                        git(wt, "update-ref", ref(n), commit)
                    else:
                        commit = anchor["commit"]           # only ignored files changed: nothing to commit
                    prot, outside = guard(program, files, ign)
                    if prot or outside:
                        touched = prot + outside
                        streak += 1
                        push(n, hyp, "crash", parent, commit, {}, None, "touched " + ", ".join(touched), agent_run)
                        _restore()
                        no_keep += 1
                        if prot:
                            escalations.append({"condition": "a protected file was touched",
                                                "detail": f"trial {n} touched {', '.join(prot)}"})
                            stopped = f"escalated: a protected file was touched ({', '.join(prot)})"
                    else:
                        figs, note, dt, attempts = execute(n)
                        git(wt, "reset", "-q", "--hard", "HEAD")
                        git(wt, "clean", "-fdqx")
                        st = settle(n, hyp, commit, figs, note, dt, agent_run, attempts, parent)
                        streak = streak + 1 if st == "crash" else 0
            if stopped is None and streak >= program.max_consecutive_crashes:
                stopped = f"escalated: {streak} crashed trials in a row (max_consecutive_crashes)"
                escalations.append({"condition": "max_consecutive_crashes reached", "detail": f"{streak} in a row"})


    except Exception as e:                             # the report is always returned
        stopped = f"the loop itself stopped: {type(e).__name__}: {e}"
        escalations.append({"condition": "the loop stopped on an exception", "detail": f"{type(e).__name__}: {e}"})
        _restore()

    unresolved = list(proposer.unresolved()) if hasattr(proposer, "unresolved") else []
    used = {"trials": proposed, "wall_clock_s": round(time.monotonic() - t_start, 3),
            "retries": state["retries"], "graph_writes": state["graph_writes"], "workers": 1}
    for k in USAGE_KEYS:
        used[k] = usage[k] if usage[k] is not None else NOT_REPORTED
    used["usage_reported_by_trials"] = usage_from
    report = {
        "loop": program.loop, "branch": branch, "worktree": str(wt), "logs": str(logs),
        "trials": trials, "kept": kept, "reverted": reverted, "crashed": crashed, "recorded": recorded,
        "best": (anchor["id"] if program.metric_direction else None),
        "stopped_because": stopped, "unresolved": unresolved, "escalations": escalations,
        "declared_escalation_conditions": program.escalate, "budget_used": used,
        "summary": [{k: h[k] for k in ("n", "id", "commit", "status", "figures", "parent", "note")}
                    for h in history],
    }
    if program.escalate_file and escalations:
        p = Path(program.escalate_file)
        p = p if p.is_absolute() else base_dir / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"loop": program.loop, "escalations": escalations,
                                 "stopped_because": stopped}, indent=1) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--replay", nargs="+", required=True, help="existing commits to apply, one per trial")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--data", help="markets-data checkout")
    ap.add_argument("--exp-dir", help="a folder for the experiment record (checks only)")
    a = ap.parse_args(argv)
    program = load(a.program)
    repo = Path(program.repo) if Path(program.repo).is_absolute() else Path(a.program).resolve().parent / program.repo
    rep = run_loop(program, ReplayCommits(repo, a.replay), scratch=a.scratch, data_root=a.data, exp_dir=a.exp_dir)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
