"""due_gate.py - serve the REGISTERED FORWARD TESTS into a group's run, and refuse a silent pass.

WHY THIS FILE EXISTS. `merge_gate.py`'s own docstring states the safety mechanism that makes
unattended merging survivable:

    "an admitted play enters as PROVISIONAL with the NEXT group named as its test ... The
     coordinator serves the DUE list into that group's run and hard-fails if a due test goes
     unreported, which is the one thing that makes unattended merging survivable: a registered
     test cannot be forgotten."

MEASURED S114, and the claim was FALSE: `grep -n "forward_tests|merge_gate|due"` across
`group_coordinate_blind.py` and `group_coordinate_refine.py` returns ZERO matches. Nothing served
the list; nothing hard-failed. The enforcement existed only in the sentence describing it - a
prose rule sitting apart from the machinery it claims to govern, which is this desk's signature
defect (D30, NC-2, A-7) appearing inside the safety mechanism itself. Eight forward tests were
registered against g24 at the time of writing with nothing whatsoever holding them.

WHAT IT DOES, and deliberately no more:

  serve(gid)  -> the DUE list as text, for the run directive / spawn slot. Reporting is the
                 specialists' job; this hands them the list so "I was never told" cannot happen.

  check(gid, reports) -> HARD FAIL if a play whose test_group == gid is not mentioned by any
                 posterior in the run. The check is deliberately CRUDE - a substring match on the
                 play id across the reports - because the alternative is a tool that pretends to
                 evaluate a prose falsifier, which would manufacture verdicts (merge_gate's own
                 stated design correction: "THE AUTOMATION IS THE BOOKKEEPING, NOT THE JUDGMENT").
                 An unmentioned test is a nonconformance. A MENTIONED one is not thereby confirmed
                 or refuted - a human or a settle step decides that.

THE FAILURE MODE IT ACCEPTS: a specialist could name a play without truly evaluating it, and this
gate would pass. That is a real limit and is stated rather than hidden. It catches the case that
actually happened - a registered test nobody was even shown - not the case of bad-faith reporting.
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "store", "forward_tests.json")


def due(gid):
    """The tests registered against this group and not yet settled."""
    if not os.path.exists(TESTS):
        return []
    st = json.load(open(TESTS, encoding="utf-8"))
    return [t for t in st.get("tests", [])
            if t.get("test_group") == gid and t.get("status") == "DUE"]


def serve(gid):
    """Text block for the run directive. Empty string when nothing is due (not an error)."""
    d = due(gid)
    if not d:
        return ""
    out = ["REGISTERED FORWARD TESTS DUE THIS GROUP - you MUST report on each one you can evaluate,",
           "and say explicitly when your day carries no evidence either way (that is a real result,",
           "not a gap). A due test left unreported is a nonconformance, never a silent pass.", ""]
    for t in d:
        out.append(f"  {t['play_id']}  (merged {t.get('merged_status','?')}, registered {t.get('registered_session','?')})")
        out.append(f"    FALSIFIER: {t.get('falsifier','')}")
        out.append("")
    return "\n".join(out)


def check(gid, reports):
    """reports = list of file paths OR raw strings. Returns (ok, unreported[], reported[])."""
    d = due(gid)
    if not d:
        return True, [], []
    blob = ""
    for r in reports:
        if isinstance(r, str) and os.path.exists(r):
            blob += open(r, encoding="utf-8", errors="replace").read()
        else:
            blob += str(r)
    blob = blob.lower()
    unreported = [t["play_id"] for t in d if t["play_id"].lower() not in blob]
    reported = [t["play_id"] for t in d if t["play_id"].lower() in blob]
    return (not unreported), unreported, reported


def assert_reported(gid, reports, hard=True):
    """The gate. Prints its verdict ALWAYS - a guard whose output never executes is not tested
    (NC-3, S113: a restore guard was reported 'negative-tested both directions' when its firing
    branch had never run, and it raised NameError on the next real invocation)."""
    ok, unreported, reported = check(gid, reports)
    if not due(gid):
        print(f"[due_gate] {gid}: no registered forward tests due - nothing to enforce.")
        return True
    if ok:
        print(f"[due_gate] {gid}: PASS - all {len(reported)} due forward test(s) reported: "
              + ", ".join(reported))
        return True
    msg = (f"[due_gate] {gid}: HARD FAIL - {len(unreported)} registered forward test(s) DUE this "
           f"group and reported by nobody:\n" + "\n".join("    " + u for u in unreported)
           + "\n  Registered in research/kalshi/store/forward_tests.json. A due test left "
             "unreported is a nonconformance (merge_gate design). Report on it, or settle it, "
             "before this run is accepted.")
    print(msg)
    if hard:
        raise SystemExit(1)
    return False


def selftest():
    """D11: prove the FIXED PATH EXECUTES and the guard FIRES on the original defect, and witness
    the OUTPUT of both branches (NC-3)."""
    fails = []
    real = [t["play_id"] for t in due("g24")]
    if not real:
        fails.append("no g24 tests registered - selftest needs the real store to be meaningful")
    else:
        print("--- negative test 1: a run mentioning NONE of them must HARD FAIL ---")
        ok, un, rep = check("g24", ["a posterior that discusses nothing relevant"])
        print(f"    ok={ok} unreported={len(un)} reported={len(rep)}")
        if ok or len(un) != len(real):
            fails.append("gate did NOT fire on a run reporting nothing")
        try:
            assert_reported("g24", ["nothing relevant here"], hard=True)
            fails.append("assert_reported did not raise on the failing case")
        except SystemExit:
            print("    -> SystemExit raised, as required")

        print("--- negative test 2: a run mentioning ALL of them must PASS, and print so ---")
        blob = " ".join(real)
        ok2, un2, rep2 = check("g24", [blob])
        print(f"    ok={ok2} unreported={len(un2)} reported={len(rep2)}")
        if not ok2 or un2:
            fails.append("gate wrongly failed a run that reported every due test")
        if not assert_reported("g24", [blob], hard=False):
            fails.append("assert_reported returned False on the passing case")

        print("--- negative test 3: PARTIAL reporting must fail and NAME the missing one ---")
        partial = " ".join(real[1:])
        ok3, un3, _ = check("g24", [partial])
        print(f"    ok={ok3} unreported={un3}")
        if ok3 or un3 != [real[0]]:
            fails.append("gate did not name exactly the missing test on partial reporting")

        print("--- negative test 4: an unknown group must be a clean no-op, not a crash ---")
        if not assert_reported("g99", ["anything"], hard=True):
            fails.append("unknown group did not no-op cleanly")

        print("--- serve() must actually EMIT the list (the slot the specialists receive) ---")
        s = serve("g24")
        print(f"    serve() emitted {len(s)} chars, {len(s.splitlines())} lines")
        if not s or real[0] not in s or "FALSIFIER" not in s:
            fails.append("serve() did not emit the due list with falsifiers")

    print()
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print(f"due_gate selftest PASS - {len(real)} due test(s) for g24; both branches executed and printed.")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "selftest":
        sys.exit(selftest())
    if a[0] == "serve":
        print(serve(a[1]) or f"[due_gate] no tests due for {a[1]}")
    elif a[0] == "check":
        sys.exit(0 if assert_reported(a[1], a[2:], hard=False) else 1)
    else:
        print(__doc__)
