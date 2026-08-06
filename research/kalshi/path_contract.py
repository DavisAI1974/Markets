"""path_contract.py - is the emitted curve actually a full-session curve? (S114)

WHY. The output contract in BLD-1/RFN-1 is explicit: `path_p50_curve` runs "on the 2-HOURLY CLOCK
FROM THE 20:00 REOPEN through the close - the FULL session, never daytime-hours-only", the first
point is 0, and the last equals (day-move minus gap). Nothing checked it.

MEASURED ON THE COMMITTED g22 BLIND, which is the record of a scored run:
    first point == 0 .................. 4 of 10 FAIL
    last  == (move - gap) ............. 0 of 10 fail   <- the one arithmetic rule that held
    path starts at the 20:00 reopen ... 10 of 10 FAIL  <- every single day started at hour 8
    >= 11 points (the full clock) ..... 8 of 10 FAIL
So every day's curve was missing its overnight leg. Day-to-day ATTACHMENT was clean (0 of 10
unattached), which is why this never surfaced as a continuity bug: the day-move arithmetic was
right and only the SHAPE was truncated. It reads downstream as a session that did not trade
between the reopen and 08:00, and it is half the reason a drawn line looks disconnected.

WHY IT MATTERS BEYOND THE RENDER. The walk is a LIBRARY BUILD (D32) and retrieval matches on
SHAPE. A curve missing its first six hours has a shape no session ever traded, so it cannot match
and the library entry is wrong furniture. It also silently drops the leg where the weekend seam
and the overnight gap reaction live - the E->A->B chain's whole subject.

THE CLOCK IS DERIVED, NOT DECREED. Read off the committed refine posteriors that were accepted as
good rather than from the prose (which gives no point count):
    [20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16]        n=7   <- canonical
    [20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 17]    n=5   <- canonical + the 17:00 close
Both are accepted. Anything ending early (...12, 13) or running past 17 into 18/20 is not, because
past 17:00 is the NEXT session.

    python path_contract.py check g22 --blind
    python path_contract.py check g22 --dir forecasts/g22_perday
    python path_contract.py selftest
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RN = os.path.join(HERE, "renders", "ng_refine_s95")

CLOCK = [20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16]
CLOSE_HOUR = 17                      # the 17:00 ET settle; an optional final point


def check_path(path, day_move=None, gap=None):
    """-> list of violation strings. Empty means the curve satisfies the contract.

    Deliberately reports EVERY violation rather than the first, because a truncated path usually
    breaks three rules at once and a first-failure message would send the repair at one of them.
    """
    v = []
    if not isinstance(path, list) or not path:
        # ABSENT, not malformed - and the distinction is D31 discipline. Every blind through g16
        # emitted no path at all (the field is []), because the curve was not yet the product.
        # Reporting those as contract violations would manufacture 100+ defects out of an era
        # difference and bury the two real ones (g20 overrunning the close, g22 daytime-only).
        return ["ABSENT: no path emitted"]
    try:
        hrs = [int(p[0]) for p in path]
        cum = [float(p[1]) for p in path]
    except Exception:
        return ["path_p50_curve is not a list of [hour, cum] pairs"]

    if hrs[0] != CLOCK[0]:
        v.append("starts at hour %d, not the %d:00 REOPEN - the overnight leg is missing, which "
                 "is the g22 defect (10 of 10 days started at 08)" % (hrs[0], CLOCK[0]))
    bad_late = [h for h in hrs if h > CLOSE_HOUR and h not in CLOCK]
    if bad_late:
        v.append("hour(s) %s run past the %d:00 close - that is the NEXT session"
                 % (bad_late, CLOSE_HOUR))
    allowed = CLOCK + [CLOSE_HOUR]
    off = sorted({h for h in hrs if h not in allowed})
    if off:
        v.append("hour(s) %s are not on the 2-hourly clock %s (+ optional %d close)"
                 % (off, CLOCK, CLOSE_HOUR))
    # coverage: every canonical hour from the first present one onward must be there
    missing = [h for h in CLOCK if h not in hrs]
    if missing:
        v.append("missing clock hour(s) %s - %d of %d points, the FULL session is required"
                 % (missing, len(hrs), len(CLOCK)))
    if len(set(hrs)) != len(hrs):
        v.append("duplicate hour(s) in the path")
    if abs(cum[0]) > 1e-9:
        v.append("first point is %g, must be 0 - cum is measured from the day's OPEN, and a "
                 "non-zero first point is how cum-from-prior-close double-counts the gap" % cum[0])
    if day_move is not None and gap is not None:
        want = day_move - gap
        if abs(cum[-1] - want) > 1e-6:
            v.append("last point %g != (day_move %g - gap %g) = %g"
                     % (cum[-1], day_move, gap, want))
    return v


def assert_rows(rows, hard=False, label="path_contract"):
    """Check every assembled row's curve. Returns the list of offending dates.

    A FUNCTION, not inline coordinator code, and that is the point: the first version of this guard
    lived inline in each coordinator's __main__, where it could not be executed in a test because
    both coordinators refuse to run on a group that already has a committed record (correctly - see
    NC-4). A guard whose firing branch cannot be executed has not been tested (NC-3), and this desk
    has shipped that exact mistake before.
    """
    bad = []
    for r in rows:
        v = check_path(r.get("path_p50") or r.get("path_p50_curve"),
                       r.get("guess_day_move_usd", r.get("guessed_net_usd")),
                       r.get("overnight_gap_usd"))
        if v and not v[0].startswith("ABSENT"):
            print("[%s] %s: %s" % (label, r.get("date"), "; ".join(v)))
            bad.append(r.get("date"))
    if not bad:
        print("[%s] all %d emitted paths satisfy the curve contract." % (label, len(rows)))
        return bad
    print("[%s] %d of %d day(s) violate the curve contract: %s"
          % (label, len(bad), len(rows), ", ".join(str(d) for d in bad)))
    if hard:
        raise SystemExit("%s: the curve is the product - refusing to assemble a posterior from "
                         "truncated paths. A path missing its overnight leg has a shape no session "
                         "traded, so it can never be matched on shape (D32)." % label)
    print("[%s] ANNOUNCE only - a path can only be repaired by re-running the specialist, and a "
          "SystemExit here would discard a completed run. Announce in the blind, hard in the "
          "refine, exactly as due_gate does." % label)
    return bad


def _posteriors(gid, blind, dirpath):
    """-> [(label, path, day_move, gap)]"""
    out = []
    if blind:
        p = os.path.join(HERE, "forecasts", "grp%s.json" % gid.lstrip("g"))
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for r in d["days"]:
            out.append((r["date"], r.get("path_p50") or r.get("path_p50_curve"),
                        r.get("guess_day_move_usd"), r.get("overnight_gap_usd")))
        return out
    for f in sorted(glob.glob(os.path.join(HERE, dirpath, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        p = d.get("path_p50_curve") or d.get("path_p50")
        if p is None:
            continue
        out.append((os.path.basename(f), p,
                    d.get("guessed_net_usd", d.get("expected_magnitude_usd")),
                    d.get("overnight_gap_usd")))
    return out


def cmd_check(gid, blind, dirpath, hard):
    rows = _posteriors(gid, blind, dirpath)
    if not rows:
        print("path_contract: nothing to check for %s" % gid)
        return 0
    bad = absent = 0
    print("PATH CONTRACT - %s (%d posterior(s))" % (gid, len(rows)))
    for label, path, mv, gap in rows:
        v = check_path(path, mv, gap)
        if v and v[0].startswith("ABSENT"):
            absent += 1
            print("  --   %s  no path emitted (pre-curve era, not a violation)" % label)
        elif v:
            bad += 1
            print("  FAIL %s" % label)
            for x in v:
                print("        %s" % x)
        else:
            print("  ok   %s (%d pts)" % (label, len(path)))
    print("\n%d of %d emitted paths violate the contract%s"
          % (bad, len(rows) - absent,
             " (%d emitted no path at all - era, not defect)" % absent if absent else ""))
    if bad and hard:
        print("HARD: the curve is the product. A truncated path is a shape no session traded, so "
              "it cannot serve as a library entry (D32) and the render cannot draw it.")
        return 1
    if bad:
        print("ANNOUNCE only - not failing the run here, because a path can only be repaired by "
              "re-running the specialist and a SystemExit would discard completed work. Same "
              "reasoning as due_gate: announce in the blind, hard in the refine.")
    return 0


def cmd_selftest():
    """Every negative branch PRINTS the guard's output - a test that never produced the guard's
    output did not test the guard (NC-3)."""
    fails = []

    def check(name, cond, detail=""):
        print("  %-56s %s%s" % (name, "PASS" if cond else "FAIL", ("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    good = [[h, 0 if i == 0 else -100 * i] for i, h in enumerate(CLOCK)]
    good[-1][1] = -440
    print("path_contract selftest")
    v = check_path(good, -420, 20)
    check("canonical 11-point clock passes", not v, str(v))

    withclose = [list(p) for p in good] + [[CLOSE_HOUR, -440]]
    check("canonical + the 17:00 close passes", not check_path(withclose, -420, 20))

    def neg(name, path, mv=-420, gap=20, expect=None):
        v = check_path(path, mv, gap)
        print("     guard output: %s" % (v[0][:96] if v else "<none>"))
        ok = bool(v) and (expect is None or any(expect in x for x in v))
        check(name, ok)
        return ok

    # THE ACTUAL g22 DEFECT, verbatim in shape: starts at 08, six points
    g22 = [[8, -60], [9, -130], [10, -190], [12, -270], [14, -360], [16, -440]]
    neg("NEG the real g22 shape (starts at 08) is caught", g22, expect="REOPEN")
    neg("NEG first point non-zero is caught",
        [[h, (5 if i == 0 else -100 * i)] for i, h in enumerate(CLOCK)], expect="must be 0")
    short = [list(p) for p in good][:-2]
    neg("NEG truncated before the close is caught", short, expect="missing clock hour")
    over = [list(p) for p in good] + [[18, -500], [20, -520]]
    neg("NEG running past 17:00 into the next session is caught", over, expect="NEXT session")
    odd = [list(p) for p in good]; odd[5][0] = 7
    neg("NEG an off-clock hour is caught", odd, expect="not on the 2-hourly clock")
    neg("NEG last != (move - gap) is caught", good, -999, 20, expect="last point")
    neg("NEG empty path is reported as ABSENT, not malformed", [], expect="ABSENT")

    # assert_rows - the branch the coordinators actually call. Exercised on the REAL committed g22
    # rows, because both coordinators refuse to run on a group that has a committed record (NC-4),
    # so this function is the only way its firing branch can ever execute.
    import json as _json
    rows = _json.load(open(os.path.join(HERE, "forecasts", "grp22.json"),
                           encoding="utf-8"))["days"]
    bad = assert_rows(rows, hard=False, label="selftest-announce")
    check("assert_rows ANNOUNCE returns offenders and does not raise", len(bad) == 10,
          "%d of 10 g22 days" % len(bad))
    try:
        assert_rows(rows, hard=True, label="selftest-hard")
        check("assert_rows HARD raises on the g22 rows", False)
    except SystemExit as e:
        print("     guard output: %s" % str(e)[:96])
        check("assert_rows HARD raises on the g22 rows", True)
    clean = []
    for r in rows:
        want = r["guess_day_move_usd"] - r["overnight_gap_usd"]
        pth = [[h, 0 if k == 0 else round(want * k / (len(CLOCK) - 1))]
               for k, h in enumerate(CLOCK)]
        pth[-1][1] = want
        clean.append(dict(r, path_p50=pth))
    try:
        assert_rows(clean, hard=True, label="selftest-clean")
        check("POSITIVE a contract-clean block passes the HARD branch", True)
    except SystemExit:
        check("POSITIVE a contract-clean block passes the HARD branch", False)

    print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % fails))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("gid")
    c.add_argument("--blind", action="store_true", help="check the committed blind of record")
    c.add_argument("--dir", dest="dirpath", default="", help="a per-day posterior directory")
    c.add_argument("--hard", action="store_true", help="exit non-zero on any violation")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return cmd_selftest()
    return cmd_check(a.gid, a.blind, a.dirpath, a.hard)


if __name__ == "__main__":
    sys.exit(main())
