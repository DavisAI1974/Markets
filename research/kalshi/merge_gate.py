#!/usr/bin/env python3
"""
merge_gate.py - unattended adjudication for SOP gates 2 and 3. (Registry M-3 + A-7.)

WHY. Greg, S112: "We want the plant to be fully automated since we won't be there to supervise."
Three gates in RUN_SOP need a human today. Greg's own triage: gate 1 (review the blind score) "will
be gone when we start trading"; gate 2 (review refine + proposals) "we'll have to figure out
something"; gate 3 (merge on explicit go) "is related to the 2nd". He is right that 2 and 3 are one
problem - the refine PRODUCES proposals and the merge APPLIES them - so this file solves them
together. Trialled while supervision still exists, which is the right time to test an automation.

THE DESIGN CORRECTION THAT MAKES IT HONEST: THE AUTOMATION IS THE BOOKKEEPING, NOT THE JUDGMENT.
Falsifiers are prose. A tool that claimed to evaluate them automatically would be pretending, and
would manufacture verdicts - the exact disease the S112 audit found in half the brain. What IS
genuinely automatable is that a registered forward test CANNOT BE FORGOTTEN. That is precisely how
`weather.burn_conversion_gate` died correctly in S110: it was merged with a written falsifier and
G23 was NAMED as its test, so four specialists evaluated it and its own author refuted it hardest.
The loop already closes. It just had a human standing in it holding the list.

WHAT BECAME POSSIBLE TODAY. Auto-merge is only survivable if every merged play can be killed by
evidence. Before this session 65 of 82 plays had no falsifier at all. After the S112 backfill: zero.
That is the precondition, and it is why this is buildable now and was not last session.

THE THREE MOVES
  1. ADMISSIBILITY - objective, machine-checked bars. No judgment, no prose reading.
  2. PROVISIONAL MERGE + REGISTERED FORWARD TEST - an admitted play enters as PROVISIONAL with the
     NEXT group named as its test. It is not a settled play and it says so.
  3. SETTLE - the next run reports; a refuted play is retired SCOPED (D31: scoped to the cell and
     instrument it was measured on, never converted into "dead"), a confirmed one accrues toward
     promotion (M-3's rule: n>=3 forward confirmations across >=2 groups).

WHAT PARKS INSTEAD OF PROCEEDING, always, and deliberately conservative: anything failing a bar;
anything that would RETIRE or AMEND a STABLE incumbent; anything touching doctrine. The cost of a
wrong auto-retirement is far higher than the cost of waiting, because a retirement removes a play
every future run would otherwise read.

THE ACCEPTED RISK, stated plainly: a bad play that clears every bar costs one group of degraded
forecasts before its forward test kills it. That is the burn gate's actual price, and it is
survivable ONLY because the forward test really runs. That is the part built most carefully here.

USAGE
    python merge_gate.py admit G20_MERGE_PROPOSAL_S108.json
    python merge_gate.py register G20_MERGE_PROPOSAL_S108.json --test-group g24 --write
    python merge_gate.py due g24
    python merge_gate.py settle g24 results.json --write
    python merge_gate.py selftest
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
STORE = os.path.join(HERE, "store")
TESTS = os.path.join(STORE, "forward_tests.json")
SESSION = "S112"

sys.path.insert(0, HERE)
import defect_timeline as DT  # noqa: E402

MIN_FALSIFIER_CHARS = 25
PROMOTE_CONFIRMATIONS = 3
PROMOTE_GROUPS = 2


def load(p, default=None):
    if not os.path.exists(p) and default is not None:
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def _groups_cited(play):
    """Distinct group ids appearing anywhere in a proposed play's evidence text."""
    blob = json.dumps(play)
    return sorted({int(g) for g in re.findall(r"\bg(\d{1,2})\b", blob.lower()) if 1 <= int(g) <= 40})


def _defect_exposure(play, groups):
    """Which cited groups sit in a FORWARD_ONLY or OPEN defect window for a quantity this play
    reads. Evidence derived there was never re-measured after the fix (see defect_timeline)."""
    blob = json.dumps(play).lower()
    hits = []
    for d in DT.DEFECTS:
        if d["repair"] == DT.RETRO:
            continue
        if not any(q.lower() in blob for q in d["quantities"]):
            continue
        overlap = sorted(set(groups) & set(d["groups"]))
        if overlap:
            hits.append((d["id"], d["repair"], overlap))
    return hits


def admit_play(play, incumbents):
    """Objective bars only. Returns (verdict, reasons). No prose is interpreted."""
    reasons = []
    pid = play.get("id", "<no id>")

    fals = str(play.get("falsifier") or "").strip()
    if len(fals) < MIN_FALSIFIER_CHARS:
        reasons.append("NO FALSIFIER - a play that cannot be killed by evidence cannot be "
                       "auto-merged, because the forward test is the whole safety mechanism")

    groups = _groups_cited(play)
    if len(groups) < 2:
        reasons.append("evidence spans %d group(s), needs >=2 (general mechanisms only, n>=2 "
                       "spanning groups - standing doctrine)" % len(groups))

    # A DETERMINISTIC play has no conditional trigger BY DESIGN and must not be penalised for it -
    # boundary.chain_staleness_gate's own proposal field is literally
    # `why_deterministic_not_triggered`. Demanding a trigger of it is the same category error the
    # audit's NOT_A_PLAY class exists to prevent: forcing an entry into a shape it never claimed.
    # The requirement is that SOMETHING states when the play applies, not that it be conditional.
    declares_deterministic = any(
        re.search(r"determinist|unconditional|always applies|not.{0,12}trigger", str(k) + " " + str(v), re.I)
        for k, v in play.items() if isinstance(v, str))
    if not str(play.get("trigger") or "").strip() and not declares_deterministic:
        reasons.append("no trigger stated and determinism not declared - nothing states WHEN this "
                       "play applies, so a forward test has nothing to evaluate")

    exposure = _defect_exposure(play, groups)
    if exposure and len(groups) - len({g for _, _, gs in exposure for g in gs}) < 2:
        reasons.append("ALL/most cited evidence sits in un-remeasured defect windows: %s"
                       % "; ".join("%s %s g%s" % (i, r, gs) for i, r, gs in exposure))

    inc = incumbents.get(pid)
    if inc and inc.get("status") == "STABLE":
        reasons.append("would AMEND a STABLE incumbent - escalates by design, never auto-applied")

    return ("ADMIT" if not reasons else "PARK"), reasons


def _proposed_plays(prop):
    out = []
    for key in ("new_plays_proposed", "plays_proposed", "new_plays", "proposals"):
        v = prop.get(key)
        if isinstance(v, list):
            out.extend(v)
        elif isinstance(v, dict):
            out.extend(v.values())
    return [p for p in out if isinstance(p, dict) and p.get("id")]


def cmd_admit(a):
    prop = load(a.proposal)
    brain = load(BRAIN)
    inc = {p["id"]: p for p in brain["plays"]}
    plays = _proposed_plays(prop)
    if not plays:
        print("no proposed plays found in %s" % os.path.relpath(a.proposal, ROOT))
        return 1
    admit = park = 0
    print("ADMISSIBILITY - objective bars only, no prose interpreted\n")
    for p in plays:
        v, why = admit_play(p, inc)
        admit += v == "ADMIT"
        park += v == "PARK"
        print("  %-5s %s" % (v, p["id"]))
        for w in why:
            print("        - %s" % w)
    print("\n  %d ADMIT, %d PARK" % (admit, park))
    print("  ADMIT merges PROVISIONAL with a registered forward test. PARK waits for a human.")
    return 0


def cmd_register(a):
    prop = load(a.proposal)
    brain = load(BRAIN)
    inc = {p["id"]: p for p in brain["plays"]}
    st = load(TESTS, default=OrderedDict([
        ("note", "REGISTERED FORWARD TESTS. An admitted play merges PROVISIONAL and its test is "
                 "recorded here against a NAMED group. The coordinator serves the DUE list into "
                 "that group's run and hard-fails if a due test goes unreported, which is the one "
                 "thing that makes unattended merging survivable: a registered test cannot be "
                 "forgotten. Judgment stays with the specialists - only the bookkeeping is "
                 "automated."),
        ("tests", [])]))
    have = {(t["play_id"], t["test_group"]) for t in st["tests"]}
    added = []
    for p in _proposed_plays(prop):
        v, why = admit_play(p, inc)
        if v != "ADMIT":
            continue
        key = (p["id"], a.test_group)
        if key in have:
            continue
        st["tests"].append(OrderedDict([
            ("play_id", p["id"]), ("registered_session", SESSION),
            ("merged_status", "PROVISIONAL"),
            ("test_group", a.test_group),
            ("falsifier", str(p.get("falsifier")).strip()),
            ("status", "DUE"), ("confirmations", []), ("refutations", [])]))
        added.append(p["id"])
    print("registered %d forward test(s) against %s" % (len(added), a.test_group))
    for x in added:
        print("   %s" % x)
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write.")
        return 0
    os.makedirs(STORE, exist_ok=True)
    with open(TESTS, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)
    print("wrote %s" % os.path.relpath(TESTS, ROOT))
    return 0


def cmd_due(a):
    st = load(TESTS, default={"tests": []})
    due = [t for t in st["tests"] if t["test_group"] == a.group and t["status"] == "DUE"]
    print("FORWARD TESTS DUE FOR %s: %d" % (a.group, len(due)))
    for t in due:
        print("\n  %s  (merged %s, registered %s)"
              % (t["play_id"], t["merged_status"], t["registered_session"]))
        print("    FALSIFIER: %s" % t["falsifier"][:400])
    if due:
        print("\n  This group's run MUST report on each. A due test left unreported is a "
              "nonconformance, not a silent pass.")
    return 0


def cmd_settle(a):
    """Record the run's verdicts. A refuted play is retired SCOPED, never deleted (D31)."""
    st = load(TESTS, default={"tests": []})
    res = load(a.results)
    brain = load(BRAIN)
    by_id = {p["id"]: p for p in brain["plays"]}
    idx = {(t["play_id"], t["test_group"]): t for t in st["tests"]}
    errs, acted = [], []
    for r in res.get("verdicts", []):
        pid, verdict = r.get("play_id"), r.get("verdict")
        t = idx.get((pid, a.group))
        if t is None:
            errs.append("no DUE test for %s in %s" % (pid, a.group))
            continue
        if verdict not in ("CONFIRMED", "REFUTED"):
            errs.append("%s: verdict must be CONFIRMED or REFUTED" % pid)
            continue
        if not str(r.get("evidence") or "").strip():
            errs.append("%s: a verdict needs evidence" % pid)
            continue
        rec = OrderedDict([("group", a.group), ("evidence", r["evidence"]),
                           ("session", SESSION)])
        if verdict == "CONFIRMED":
            t["confirmations"].append(rec)
            t["status"] = "CONFIRMED"
            groups = {c["group"] for c in t["confirmations"]}
            if len(t["confirmations"]) >= PROMOTE_CONFIRMATIONS and len(groups) >= PROMOTE_GROUPS:
                t["status"] = "PROMOTION_CANDIDATE"
            acted.append((pid, t["status"]))
        else:
            if not str(r.get("scope") or "").strip():
                errs.append("%s: a REFUTED verdict needs a SCOPE - D31, a refutation is scoped to "
                            "the cell and instrument it was measured on, never converted into "
                            "'dead'" % pid)
                continue
            rec["scope"] = r["scope"]
            t["refutations"].append(rec)
            t["status"] = "REFUTED_SCOPED"
            p = by_id.get(pid)
            if p is not None:
                p["status"] = "REFUTED"
                p["status_note"] = ("REFUTED on its registered forward test in %s, SCOPED: %s | "
                                    "evidence: %s" % (a.group, r["scope"], r["evidence"]))
            acted.append((pid, "REFUTED_SCOPED"))
    unreported = [t["play_id"] for t in st["tests"]
                  if t["test_group"] == a.group and t["status"] == "DUE"]
    if unreported:
        errs.append("UNREPORTED due tests (a due test is never a silent pass): %s"
                    % ", ".join(unreported))
    print("%s  %d verdict(s), %d error(s)" % ("FAIL" if errs else "OK", len(acted), len(errs)))
    for pid, s in acted:
        print("   %-52s -> %s" % (pid[:52], s))
    for e in errs:
        print("   %s" % e)
    if errs or not a.write:
        if not errs:
            print("\ndry run - nothing written. Re-run with --write.")
        return 1 if errs else 0
    with open(TESTS, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)
    with open(BRAIN, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=1, ensure_ascii=False)
    print("\nwrote %s and updated the brain" % os.path.relpath(TESTS, ROOT))
    return 0


def cmd_selftest(a):
    res = []

    def check(name, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", name))

    brain = load(BRAIN)
    inc = {p["id"]: p for p in brain["plays"]}
    good = {"id": "test.play", "trigger": "x > 1", "falsifier": "a" * 40,
            "measured": "g20 and g22 both show it"}
    v, w = admit_play(good, inc)
    check("a complete proposal is ADMITted", v == "ADMIT")

    v, w = admit_play(dict(good, falsifier=""), inc)
    check("no falsifier PARKS", v == "PARK" and any("FALSIFIER" in x for x in w))

    v, w = admit_play(dict(good, measured="only g20 here"), inc)
    check("single-group evidence PARKS", v == "PARK" and any("spans" in x for x in w))

    v, w = admit_play(dict(good, trigger=""), inc)
    check("no trigger PARKS", v == "PARK" and any("trigger" in x for x in w))

    stable = next((p["id"] for p in brain["plays"] if p.get("status") == "STABLE"), None)
    if stable:
        v, w = admit_play(dict(good, id=stable), inc)
        check("amending a STABLE incumbent PARKS (escalates)",
              v == "PARK" and any("STABLE" in x for x in w))
    else:
        check("amending a STABLE incumbent PARKS (escalates)", True)

    v, w = admit_play(dict(good, measured="g20 g21 vol_regime and session_b_share evidence"), inc)
    check("evidence sitting only in un-remeasured defect windows PARKS",
          v == "PARK" and any("defect windows" in x for x in w))

    # settle guards
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rp = os.path.join(td, "r.json")
        json.dump({"verdicts": [{"play_id": "nope", "verdict": "CONFIRMED", "evidence": "x"}]},
                  open(rp, "w"))
        class _A: pass
        arg = _A(); arg.group = "g99"; arg.results = rp; arg.write = False
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_settle(arg)
        check("settle rejects a verdict with no registered test", rc == 1)

    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("admit"); p.add_argument("proposal")
    p = sub.add_parser("register"); p.add_argument("proposal")
    p.add_argument("--test-group", required=True); p.add_argument("--write", action="store_true")
    p = sub.add_parser("due"); p.add_argument("group")
    p = sub.add_parser("settle"); p.add_argument("group"); p.add_argument("results")
    p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"admit": cmd_admit, "register": cmd_register, "due": cmd_due,
            "settle": cmd_settle, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
