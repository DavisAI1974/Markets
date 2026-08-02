#!/usr/bin/env python3
"""plant_status.py - THE ANDON BOARD (S110, turnaround memo 2.4). One command, no arguments.

Prints the state of the plant: branch, gold vault, per-group line position, state_health on the
active groups, canonical-name occupancy vs blind archives, uncommitted files, and the DECISIONS.md
staleness sweep. READ-ONLY - this tool never fixes anything. Exit 0 = no FAIL lines; exit 1 = at
least one FAIL. WARN never changes the exit code.

Designed to be wrapped by agents/QC_CHECKLIST.md (the small-model QC shift): every line is
mechanical PASS/WARN/FAIL with the evidence inline, zero judgment required of the reader.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RD = os.path.join(HERE, "renders", "ng_refine_s95")
FC = os.path.join(HERE, "forecasts")
EXPECTED_BRANCH = "claude/kalshi-agents-coordinator-guard-1175nr"
TAGS = ("A", "B", "C", "D", "E")

lines, nfail = [], 0


def say(level: str, area: str, msg: str) -> None:
    global nfail
    if level == "FAIL":
        nfail += 1
    lines.append(f"{level:4} | {area:14} | {msg}")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> int:
    # 1. branch
    br = git("rev-parse", "--abbrev-ref", "HEAD")
    tip = git("log", "--oneline", "-1")
    say("PASS" if br == EXPECTED_BRANCH else "FAIL", "branch",
        f"{br} @ {tip[:60]}" + ("" if br == EXPECTED_BRANCH else f" - EXPECTED {EXPECTED_BRANCH}"))

    # 2. gold vault
    sys.path.insert(0, HERE)
    import verify_gold
    ok, problems = verify_gold.check_gold_integrity()
    in_sync, drifted = verify_gold.check_runtime_drift()
    if ok and in_sync:
        say("PASS", "gold", "vault intact; runtime reasoning == gold")
    elif ok:
        say("WARN", "gold", f"vault intact; runtime DRIFTED from gold: {', '.join(drifted)}")
    else:
        say("FAIL", "gold", f"VAULT VIOLATED: {problems[0]}" + (f" (+{len(problems)-1} more)" if len(problems) > 1 else ""))

    # 3. per-group line position
    active = []
    for sp in sorted(glob.glob(os.path.join(RD, "grp*_state.json")),
                     key=lambda x: int(re.sub(r"\D", "", os.path.basename(x)))):
        n = re.sub(r"\D", "", os.path.basename(sp))
        gid = f"g{n}"
        pos = ["staged"]
        if os.path.exists(os.path.join(FC, f"grp{n}_state_audit.json")):
            pos.append("audited")
        blind = os.path.exists(os.path.join(FC, f"grp{n}.json"))
        if blind:
            pos.append("blind-scored")
        if os.path.isdir(os.path.join(FC, f"g{n}_blind_round1")):
            pos.append("archived")
        r1 = os.path.exists(os.path.join(FC, f"grp{n}_mbo_refined.json"))
        if r1:
            pos.append("refined-r1")
        if os.path.exists(os.path.join(FC, f"grp{n}_mbo_refined_r2.json")):
            pos.append("refined-r2")
        staged_s108 = os.path.exists(os.path.join(RD, f"{gid}_exit_states.json"))
        if staged_s108 and (not blind or not r1):
            active.append((gid, sp))
        say("PASS", "line", f"{gid}: {' -> '.join(pos)}" + ("  [ACTIVE]" if (gid, sp) in active else ""))

    # 4. state_health on the active groups only (legacy states carry known-era true positives)
    import state_health as sh
    for gid, sp in active:
        st = json.load(open(sp, encoding="utf-8"))
        r = sh.audit(st)
        say("PASS" if not r["hard"] else "FAIL", "state_health",
            f"{gid}: {len(r['hard'])} hard, {len(r['soft'])} soft (declared)"
            + ("" if not r["hard"] else f" - first: {r['hard'][0][:80]}"))

    # 5. canonical-name occupancy vs blind archives (the collision guard, standing)
    for arch_dir in sorted(glob.glob(os.path.join(FC, "g*_blind_round1"))):
        n = re.sub(r"\D", "", os.path.basename(arch_dir))
        for t in TAGS:
            canon = os.path.join(FC, f"grp{n}_mbo_specialist_{t}.json")
            arch = os.path.join(arch_dir, f"grp{n}_mbo_specialist_{t}.json")
            if os.path.exists(canon) and os.path.exists(arch) and sha(canon) == sha(arch):
                say("FAIL", "collision", f"g{n} {t}: canonical file is BYTE-IDENTICAL to its blind "
                                          f"archive - a blind posterior sitting at the refine's name")

    # 6. uncommitted files
    porcelain = [l for l in git("status", "--porcelain").splitlines() if l.strip()]
    tracked = [l for l in porcelain if not l.startswith("??")]
    say("PASS" if not tracked else "WARN", "git",
        f"{len(tracked)} modified tracked file(s), {len(porcelain) - len(tracked)} untracked"
        + ("" if not tracked else f" - first: {tracked[0]}"))

    # 7. DECISIONS.md staleness sweep: DECIDED enforced by doc-only, older than 2 sessions
    dpath = os.path.join(ROOT, "DECISIONS.md")
    if not os.path.exists(dpath):
        say("FAIL", "decisions", "DECISIONS.md missing")
    else:
        cur = 0
        for h in glob.glob(os.path.join(ROOT, "SESSION_HANDOFF_*_S*.md")):
            m = re.search(r"_S(\d+)\.md$", h)
            if m:
                cur = max(cur, int(m.group(1)))
        stale = []
        for row in open(dpath, encoding="utf-8"):
            cells = [c.strip() for c in row.split("|")]
            if len(cells) < 7 or not cells[1].startswith("D"):
                continue
            m = re.search(r"S(\d+)", cells[2])
            ses = int(m.group(1)) if m else 0
            status, enforced = cells[4], cells[5].lower()
            if status.startswith("DECIDED") and "doc" in enforced.split("(")[0] and cur - ses >= 2:
                stale.append(cells[1])
        say("PASS" if not stale else "WARN", "decisions",
            f"session S{cur}; DECIDED/doc-only older than 2 sessions: {stale or 'none'}"
            + ("" if not stale else " - wire an enforcement or re-affirm"))

    # 8. data plane + key files (presence only, never values)
    plane = os.path.isdir(os.path.join(ROOT, "data")) and bool(os.listdir(os.path.join(ROOT, "data")))
    keys = os.path.exists(os.path.join(HERE, "scratchpad", "aws.env")) or os.path.exists(
        os.path.join(ROOT, "scratchpad", "aws.env"))
    say("WARN" if not plane else "PASS", "data-plane",
        ("data/ populated" if plane else "data/ EMPTY (expected without keys; staged S108+ groups run anyway)"))
    say("WARN" if not keys else "PASS", "keys",
        ("aws.env present" if keys else "no aws.env (expected fresh session; needed only for staging/restore)"))

    print("=" * 78)
    print("PLANT STATUS (andon) - read-only; this tool never fixes anything")
    print("=" * 78)
    for l in lines:
        print(l)
    print("=" * 78)
    print(f"{'ALL CLEAR' if nfail == 0 else f'{nfail} FAIL LINE(S) - STOP THE LINE, report, fix under SOP'}")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
