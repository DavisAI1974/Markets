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
    # S112 caught this as a weak guard: it PASSED on a non-empty data/ while the SessionStart hook
    # printed "NG DATA PLANE NOT RESTORED" - both true, because the hook had materialized crypto
    # realbins. Present, non-empty, right owner, wrong content: exactly the family this desk hunts.
    # Now checks for the NG stores by name rather than for any bytes at all.
    NG_STORES = ["nymex_cont", "weather", "flow_calendar", "cot", "storage_vintage", "grid_stack"]
    ddir = os.path.join(ROOT, "data")
    have_ng = [d for d in NG_STORES if os.path.isdir(os.path.join(ddir, d))]
    plane = len(have_ng) >= 4
    keys = os.path.exists(os.path.join(HERE, "scratchpad", "aws.env")) or os.path.exists(
        os.path.join(ROOT, "scratchpad", "aws.env"))
    say("WARN" if not plane else "PASS", "data-plane",
        ("NG stores present: %s" % ",".join(have_ng)) if plane else
        ("NG DATA PLANE ABSENT - %d/%d NG stores (%s). data/ may still be non-empty from other "
         "feeds; that is NOT the NG plane. Expected without keys; staged S108+ groups run anyway"
         % (len(have_ng), len(NG_STORES), ",".join(have_ng) or "none")))
    say("WARN" if not keys else "PASS", "keys",
        ("aws.env present" if keys else "no aws.env (expected fresh session; needed only for staging/restore)"))

    # 9. THE TRACKED WORK REGISTRY (S111, D30 - a finding with no home does not exist).
    # Seven S110 turnaround-memo items were found undone in S111 because they lived only in prose.
    # This row makes an open item impossible to overlook at bring-up: it is printed every session,
    # and staleness (sessions_open) is what surfaces the decided-then-dropped pattern.
    oi = os.path.join(HERE, "OPEN_ITEMS.json")
    if not os.path.exists(oi):
        say("WARN", "open-items", "OPEN_ITEMS.json ABSENT - the tracked work registry is the D30 "
                                  "enforcement; without it findings live in prose and get dropped")
    else:
        try:
            reg = json.load(open(oi, encoding="utf-8"))
            items = reg.get("items", [])
            cur_s = int(re.search(r"\d+", reg.get("current_session", "S0")).group())
            openish = [i for i in items if i.get("status") in ("OPEN", "IN_PROGRESS", "BLOCKED")]
            done = [i for i in items if i.get("status") == "DONE"]
            stale2 = []
            for i in openish:
                m2 = re.search(r"\d+", str(i.get("first_raised", "")))
                if m2 and cur_s - int(m2.group()) >= 2:
                    stale2.append("%s(S%s)" % (i["id"], m2.group()))
            xs = [i["id"] for i in openish if i.get("size") in ("XS",)]
            say("WARN" if stale2 else "PASS", "open-items",
                "%d open / %d done | carried 2+ sessions: %s | quickest first: %s"
                % (len(openish), len(done), ",".join(stale2) or "none", ",".join(xs) or "-"))
        except Exception as e:                                   # a corrupt registry is a finding
            say("FAIL", "open-items", "OPEN_ITEMS.json unreadable: %s" % e)

    # 10. THE SCRATCHPAD GATE (S111, D33 - Greg: "fix in whatever doc you need to that things
    # don't go on scratchpads anymore. this was in the audit file!"). A-7's disease keeps recurring
    # because it was only ever a sentence. INSTANCE (NC-2): the S111 drop-in pointed S112 at an audit
    # harness under ~/.claude/projects/ - session scratchpad - which does not exist on a fresh
    # container, so the next session had to re-author it. This row makes it mechanical: any FILE THE
    # NEXT SESSION IS TOLD TO RUN must be tracked in git. FAIL, not WARN - a handoff that names a
    # file nobody else can open is a broken handoff.
    import subprocess as _sp
    tracked = set(_sp.run(["git", "ls-files"], capture_output=True, text=True,
                          cwd=ROOT).stdout.split())
    # SCOPE: only the LIVE instructions - the newest drop-in, the newest handoff, and the SOP.
    # Historical drop-ins are RECORDS, not instructions; scanning them yields permanent noise
    # (DROP_IN_S104 references agents/blind_shared.md, deleted in S105 by design) and a gate that
    # always shows red is a gate people learn to ignore. What matters is what the NEXT session is
    # told to run.
    def _newest(pat):
        f = sorted(glob.glob(os.path.join(ROOT, pat)),
                   key=lambda x: int(re.search(r"S(\d+)", os.path.basename(x)).group(1))
                   if re.search(r"S(\d+)", os.path.basename(x)) else -1)
        return f[-1:] if f else []
    handoff_docs = (_newest("DROP_IN_*.md") + _newest("SESSION_HANDOFF_*.md")
                    + [os.path.join(HERE, "agents", "RUN_SOP.md")])
    # NO REGEX for the marker check. The first version of this guard used a character class
    # containing a backslash, was mangled by shell escaping, compiled WITHOUT ERROR, and silently
    # matched nothing - it "passed" its negative test by failing to fire at all. Plain substring
    # matching on a slash-normalized, lowercased line cannot be broken that way. That is the D11
    # lesson in miniature: a guard that cannot be SHOWN firing on the defect is not a guard.
    SCRATCH_MARKERS = (".claude/projects", "appdata/local/temp", "workflows/scripts/", " /tmp/")
    PATHY = re.compile(r"((?:research/kalshi/|odcore/|deploy/|dashboard/)[\w./-]*"
                       r"\.(?:py|json|md|sh|yml))")
    scratch_hits, missing = [], []
    for doc in handoff_docs:
        if not os.path.exists(doc):
            continue
        txt = open(doc, encoding="utf-8", errors="replace").read()
        norm = txt.replace("\\", "/").lower()
        base = os.path.basename(doc)
        for mk in SCRATCH_MARKERS:
            if mk in norm:
                scratch_hits.append("%s -> %s" % (base, mk.strip()))
        for m in PATHY.finditer(txt):
            rel = m.group(1)
            if rel not in tracked and rel.rstrip("/") not in tracked:
                missing.append("%s -> %s" % (base, rel))
    bad = scratch_hits + missing
    say("PASS" if not bad else "FAIL", "scratchpad-gate",
        ("no session-scratchpad paths in the handoff docs; every referenced file is tracked"
         if not bad else
         "%d BROKEN REFERENCE(S) - a handoff naming a file nobody else can open is a broken handoff: %s"
         % (len(bad), "; ".join(bad[:4]))))

    # 10. THE ARCHITECTURE DOC - the target itself. Greg, S111: "how do we make sure the arch doc
    # isn't overlooked?" Answer: the andon board names it every session, because the alternative is
    # hoping someone remembers to read it, which is the exact failure this board exists to catch.
    arch = os.path.join(HERE, "FORECAST_ARCHITECTURE_S111.md")
    say("PASS" if os.path.exists(arch) else "FAIL", "architecture",
        "FORECAST_ARCHITECTURE_S111.md - READ THIS FIRST; the product is a CURVE, the walk is a "
        "LIBRARY BUILD (D32)" if os.path.exists(arch) else "ARCHITECTURE DOC MISSING")

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
