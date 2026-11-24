"""ONE command for a trial with a written decider program.

  python3 -m tools.decider.trial_with_decider --program <file> --platform <checkout> --data <markets-data>
        --trade-day D --plan <plan file> --from-minute M --minutes N --budget <packet tokens>
        [--keep <folder>] [--decider-timeout-s N] [--dry]

It makes a fresh mailbox folder, starts `tools.decider.serve --program <file>` on it, runs the platform's
`python3 -m paper_platform.trial ... --decider-mailbox <mailbox> [--keep ...]` in the platform checkout, waits for
it, stops the door, copies `decisions.jsonl` beside the trial's kept files, and prints as its LAST line one JSON
object: the trial's own last line unchanged under `trial`, and under `figures` the trial's own `figures` plus four
counts read from `decisions.jsonl` (decider_asked, decider_take, decider_skip, decider_skip_by_code: the skips
this code answered, not the program). Each is a count of what was written; none is a result.
If the trial or the door fails it exits non-zero and says why.

A real trial runs the engine on the stored tape. It is started by the ratchet loop or by Greg's go, never by a check.
`--dry` starts nothing: it prints the two commands it would run and the checks it made (the program compiles and
defines `decide`; the platform checkout is not shallow; the plan file exists; the tape files of the trade day's UTC
clock days are real files, named and sized as the archive's MANIFEST.json says). Nothing is opened but names, sizes
and the program's own text.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tools.ratchet.ready import trade_day_clock_days

HERE = Path(__file__).resolve().parents[2]            # the Markets checkout this file is in (the loop's worktree)
DEFAULT_ARCHIVE = "data/nymex_mbo/ng_v0_oct2023"


def commands(a, mailbox: str):
    door = [sys.executable, "-m", "tools.decider.serve", "--mailbox", mailbox, "--data", str(a.data),
            "--platform", str(a.platform), "--budget", str(a.budget), "--by", "trial-with-decider",
            "--program", str(a.program), "--poll-s", "0.2"]
    trial = [sys.executable, "-m", "paper_platform.trial", "--data", str(a.data), "--trade-day", a.trade_day,
             "--plan", str(a.plan), "--from-minute", f"{a.from_minute:g}", "--minutes", f"{a.minutes:g}",
             "--decider-mailbox", mailbox, "--decider-timeout-s", str(a.decider_timeout_s)]
    if a.keep:
        trial += ["--keep", str(a.keep)]
    return door, trial


def checks(a) -> list:
    out = []
    add = lambda name, found, ok: out.append({"check": name, "found": found, "ok": bool(ok)})
    prog = Path(a.program)
    try:
        tree = ast.parse(prog.read_text(encoding="utf8"), str(prog))
        has = any(isinstance(n, ast.FunctionDef) and n.name == "decide" for n in tree.body)
        add("the program file compiles and defines decide", "compiles; decide " + ("defined" if has else "not defined"), has)
    except (OSError, SyntaxError, ValueError) as e:
        add("the program file compiles and defines decide", f"{type(e).__name__}: {e}", False)
    plat = Path(a.platform)
    r = subprocess.run(["git", "-C", str(plat), "rev-parse", "--is-shallow-repository"], capture_output=True, text=True)
    add("the platform checkout is not shallow", r.stdout.strip() or r.stderr.strip(), r.stdout.strip() == "false")
    add("the plan file exists", str(a.plan), Path(a.plan).is_file())
    try:
        day = dt.date.fromisoformat(a.trade_day)
    except ValueError:
        add("the trade day is a date", a.trade_day, False)
        return out
    mj = plat / "paper_platform" / "markets" / "nymex-ng.json"
    archive = DEFAULT_ARCHIVE
    if mj.exists():
        try:
            archive = json.loads(mj.read_text(encoding="utf8")).get("archive") or DEFAULT_ARCHIVE
        except ValueError:
            pass
    root = Path(a.data) / archive
    man = root / "MANIFEST.json"
    if not man.is_file():
        add("the archive's MANIFEST.json", str(man), False)
        return out
    listed = json.loads(man.read_text(encoding="utf8"))["files"]
    span, week = trade_day_clock_days(day)
    for d in sorted(set(span) | set(week)):
        hit = next((e for e in listed if d.strftime("%Y%m%d") in e.get("file", e.get("name", ""))), None)
        if not hit:
            add(f"tape file of UTC clock day {d}", "not listed in the manifest", False)
            continue
        name = hit.get("file", hit.get("name"))
        f = root / name
        size = f.stat().st_size if f.is_file() else None
        add(f"tape file of UTC clock day {d}",
            {"file": name, "manifest_bytes": hit.get("bytes"), "on_disk_bytes": size, "is_a_file": f.is_file()},
            size is not None and size == hit.get("bytes"))
    return out


def decision_counts(path: Path) -> dict:
    lines = [json.loads(l) for l in path.read_text(encoding="utf8").splitlines() if l.strip()] if path.exists() else []
    return {"decider_asked": len(lines),
            "decider_take": sum(l["action"] == "take" for l in lines),
            "decider_skip": sum(l["action"] == "skip" for l in lines),
            "decider_skip_by_code": sum(l["action"] == "skip" and l["answered_by"] == "this code" for l in lines)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--trade-day", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--from-minute", type=float, required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--budget", type=int, required=True, help="packet tokens")
    ap.add_argument("--keep")
    ap.add_argument("--decider-timeout-s", type=float, default=600)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    for k in ("program", "platform", "data", "plan", "keep"):
        if getattr(a, k):
            setattr(a, k, str(Path(getattr(a, k)).resolve()))

    if a.dry:
        door, trial = commands(a, "<a fresh mailbox folder, made when the trial starts>")
        done = checks(a)
        print(f"door  (in {HERE}): {shlex.join(door)}")
        print(f"trial (in {a.platform}): {shlex.join(trial)}")
        for c in done:
            print(f"check: {c['check']}: {json.dumps(c['found'])}: {'ok' if c['ok'] else 'NOT OK'}")
        print(json.dumps({"dry": True, "started": "nothing", "door_command": door, "door_cwd": str(HERE),
                          "trial_command": trial, "trial_cwd": a.platform, "checks": done}))
        return 0 if all(c["ok"] for c in done) else 1

    bad = [c for c in checks(a) if not c["ok"]]
    if bad:
        print("not started: " + "; ".join(f"{c['check']}: {c['found']}" for c in bad), file=sys.stderr)
        return 2
    mailbox = Path(tempfile.mkdtemp(prefix="decider-mailbox-"))
    door_cmd, trial_cmd = commands(a, str(mailbox))
    door = subprocess.Popen(door_cmd, cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        r = subprocess.run(trial_cmd, cwd=a.platform, capture_output=True, text=True)
        # the door writes the answer first and its log line a moment after: wait for the log to catch up
        t_end = time.monotonic() + 15
        while time.monotonic() < t_end and door.poll() is None:
            answered = len(list(mailbox.glob("q-*/answer.json")))
            log = mailbox / "decisions.jsonl"
            n = len(log.read_text(encoding="utf8").splitlines()) if log.exists() else 0
            if n >= answered:
                break
            time.sleep(0.1)
        died = door.poll()
    finally:
        if door.poll() is None:
            door.terminate()
            try:
                door.wait(timeout=10)
            except subprocess.TimeoutExpired:
                door.kill()
    door_err = (door.stderr.read() or "").strip()[-500:] if door.stderr else ""
    if died is not None:
        print(f"the door (tools.decider.serve) stopped by itself with exit code {died}: {door_err}", file=sys.stderr)
        return 3
    if r.returncode != 0:
        print(f"the trial failed with exit code {r.returncode}: {(r.stderr.strip().splitlines() or ['no message'])[-1]}",
              file=sys.stderr)
        return 4
    last = next((l for l in reversed(r.stdout.splitlines()) if l.strip()), "")
    try:
        doc = json.loads(last)
    except ValueError:
        print(f"the trial's last line is not JSON: {last[:300]}", file=sys.stderr)
        return 5
    log = mailbox / "decisions.jsonl"
    if doc.get("kept") and log.exists():
        shutil.copyfile(log, Path(doc["kept"]) / "decisions.jsonl")
    figs = dict(doc.get("figures", {}), **decision_counts(log))
    shutil.rmtree(mailbox, ignore_errors=True)
    print(json.dumps({"trial": doc, "figures": figs}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
