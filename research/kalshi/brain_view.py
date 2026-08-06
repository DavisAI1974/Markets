"""brain_view.py - serve the brain to a ROLE, and DECLARE what was withheld.

ONE BRAIN DOC, MANY VIEWS (Greg, S114). Two of his instructions meet here:

    "All behavior related docs should be merged with schema. We can have separate sections for
     things but there should only be one brain doc."
    "We don't want the agents seeing nonsense when they are making a forecast."

Both hold at once only if the brain is one file and the SERVING is scoped. Before this, the spawn
template said `Brain: knowledge/ng_brain.json` and handed every specialist the whole thing - so a
forecaster mid-day was reading post-outcome failure-localization doctrine and `doctrine_legacy`,
which is explicitly superseded and read_by nobody.

THE SCOPING IS DECLARED, NEVER SILENT. `meta.sections[<name>].roles` says which roles a section is
served to; a withheld section is PRINTED with the reason. That matters on this desk specifically:
holes #7 and #8 were both silent absences that read downstream exactly like a deliberate mask, and
the lesson was that an absence has to announce itself. A view that quietly dropped a section would
be the same defect wearing a different hat.

Not a security boundary and not a blind wall - D2's one deliberate mask is the PRICE CURVE, and the
brain carries no price. This is a RELEVANCE filter: fewer wrong things in front of a forecaster.

    python brain_view.py --role specialist
    python brain_view.py --role specialist --out /path/brain_specialist.json
    python brain_view.py --roles          # what each role gets, and what it does not
    python brain_view.py --selftest
"""
import argparse
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")


def load(path=BRAIN):
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def sections_index(brain):
    idx = (brain.get("meta") or {}).get("sections") or {}
    return OrderedDict((k, v) for k, v in idx.items() if not k.startswith("_"))


def known_roles(brain):
    out = []
    for e in sections_index(brain).values():
        for r in (e.get("roles") or []):
            if r not in out:
                out.append(r)
    return sorted(out)


def build(brain, role, phase="working"):
    """-> (view, served[], withheld[(name, why)]).

    PHASE is Greg's distinction, S114: "they should get instructions on what their reason for being
    is before they launch but that shouldn't touch them when making a curve. They should always be
    aware of how to make good decisions while they are making the curve."

    So a section is served by ROLE *and* PHASE:
      briefing     - the mission. Rendered into the SPAWN PROMPT, then out of the way.
      working      - reasoning_method, plays, doctrine. In view the whole time the curve is drawn.
      post_outcome - failure_localization. Never during a forecast.
    `--phase all` exists for a human reading the brain, and is never what a specialist is served.

    Raises on an UNDECLARED section rather than guessing: an undeclared section is exactly the
    silent-addition case the section gate exists to stop, and guessing here would route around it.
    """
    idx = sections_index(brain)
    undeclared = [k for k in brain if k != "meta" and k not in idx]
    if undeclared:
        raise SystemExit("brain_view: UNDECLARED section(s) %s - declare them in meta.sections "
                         "(see brain_schema.py validate) before serving a view." % undeclared)
    if role not in known_roles(brain):
        raise SystemExit("brain_view: unknown role %r. Known: %s" % (role, known_roles(brain)))

    served, withheld = [], []
    view = OrderedDict()
    meta = OrderedDict(brain.get("meta") or {})
    meta["view_role"] = role
    meta["view_phase"] = phase
    meta["view_note"] = ("This is a ROLE-SCOPED, PHASE-SCOPED view of knowledge/ng_brain.json, not a "
                         "different brain. Sections withheld from you are listed in "
                         "meta.view_withheld with the reason. If you believe you need a withheld "
                         "section, say so in your report - do not open the raw file to route around "
                         "the scoping.")
    if phase == "working":
        meta["view_note"] += (" Your MISSION brief (why you exist, what success looks like, where "
                              "your day sits) was delivered in your spawn prompt and is deliberately "
                              "not repeated here - it is orientation, not something to consult "
                              "mid-curve.")
    view["meta"] = meta
    for name, entry in idx.items():
        ph = entry.get("phase") or "working"
        role_ok = role in (entry.get("roles") or [])
        phase_ok = (phase == "all") or (ph == phase)
        if role_ok and phase_ok:
            if name in brain:
                view[name] = brain[name]
                served.append(name)
        elif not role_ok:
            withheld.append((name, entry.get("withheld_why")
                             or "not served to role %r (meta.sections[%r].roles)" % (role, name)))
        else:
            withheld.append((name, "phase %r, and this view is phase %r - %s"
                             % (ph, phase, entry.get("phase_why") or "")))
    meta["view_served"] = served
    meta["view_withheld"] = [OrderedDict([("section", n), ("why", w)]) for n, w in withheld]
    # the index itself is trimmed to what this role is served, so the view does not advertise a
    # section it cannot see and then withhold it - that reads as a mask rather than a scoping
    meta["sections"] = OrderedDict((k, v) for k, v in idx.items() if k in served)
    return view, served, withheld


def cmd_view(role, out, phase="working"):
    brain = load()
    view, served, withheld = build(brain, role, phase)
    if out:
        d = os.path.dirname(os.path.abspath(out))
        if d and not os.path.isdir(d):
            os.makedirs(d)          # data/ is disposable (D34) and will not exist on a fresh session
        with open(out, "w", encoding="utf-8") as f:
            json.dump(view, f, indent=1, ensure_ascii=False)
    print("brain %s -> role %s, phase %s"
          % (brain["meta"].get("version"), role, phase))
    print("  SERVED  : %s" % ", ".join(served))
    for n, w in withheld:
        print("  WITHHELD: %-22s %s" % (n, w.split(".")[0][:88]))
    if out:
        print("  written -> %s  (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))
    return 0


def cmd_roles():
    brain = load()
    idx = sections_index(brain)
    roles = known_roles(brain)
    print("brain %s | %d sections | roles: %s"
          % (brain["meta"].get("version"), len(idx), ", ".join(roles)))
    w = max(len(k) for k in idx)
    print("\n%-*s  %-12s  %s" % (w, "section", "phase", "  ".join("%-13s" % r for r in roles)))
    for k, e in idx.items():
        cells = ["%-13s" % ("SERVED" if r in (e.get("roles") or []) else ".") for r in roles]
        print("%-*s  %-12s  %s" % (w, k, e.get("phase") or "working", "  ".join(cells)))
    dead = [k for k, e in idx.items() if not (e.get("roles") or [])]
    if dead:
        print("\nserved to NO role (in the brain for provenance/losslessness only): %s"
              % ", ".join(dead))
    return 0


def cmd_selftest():
    """Negative tests included, and each one PRINTS the guard's output - a test that never produced
    the guard's output did not test the guard (NC-3)."""
    brain = load()
    fails = []

    def check(name, cond, detail=""):
        print("  %-58s %s%s" % (name, "PASS" if cond else "FAIL", ("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    print("brain_view selftest (brain %s)" % brain["meta"].get("version"))

    spec, served, withheld = build(brain, "specialist")
    wnames = [n for n, _ in withheld]
    check("specialist is served plays + reasoning_method",
          "plays" in served and "reasoning_method" in served)
    check("specialist does NOT see doctrine_legacy (superseded)",
          "doctrine_legacy" not in spec and "doctrine_legacy" in wnames)
    check("withholding is DECLARED, not silent",
          all(w.get("why") for w in spec["meta"]["view_withheld"]) and
          len(spec["meta"]["view_withheld"]) == len(withheld),
          "%d declared" % len(withheld))
    check("view index advertises only what is served",
          set(spec["meta"]["sections"]) == set(served))

    # PHASE - Greg's split: the brief lands before launch, the how-to-decide stays in view
    brief, bserved, _ = build(brain, "specialist", "briefing")
    check("BRIEFING phase carries the mission", "mission" in brief)
    check("mission is NOT in the working view (it is a spawn-prompt brief)",
          "mission" not in spec, "working: %s" % ", ".join(served))
    check("WORKING view keeps reasoning_method (how to decide, always on)",
          "reasoning_method" in spec)
    check("reasoning_method is NOT in the briefing (it is not a one-time read)",
          "reasoning_method" not in brief)
    check("working view tells the agent where its brief went",
          "spawn prompt" in spec["meta"]["view_note"])
    check("phase withholding states the phase and the reason",
          any("phase" in w["why"] for w in spec["meta"]["view_withheld"]))

    # THE JUDGE'S DOCTRINE IS NO LONGER A BRAIN SECTION (S114). It moved to
    # store/failure_judge.json -> agents/failure_judge.md because it caused a contradiction with
    # the FROZEN gold mbo_refine_shared.md, which orders specialists to read knowledge/ng_brain.json
    # in full. The rule that settled it: SHARED behaviour in the brain, single-role doctrine in that
    # role's own file. These tests hold the line that it did not creep back.
    check("failure_localization is NOT a brain section any more",
          "failure_localization" not in brain,
          "it lives in store/failure_judge.json -> agents/failure_judge.md")
    import os as _os
    check("and its file exists where it moved to",
          _os.path.exists(_os.path.join(HERE, "store", "failure_judge.json")) and
          _os.path.exists(_os.path.join(HERE, "agents", "failure_judge.md")))
    fj, fserved, _ = build(brain, "failure_judge", "working")
    check("failure_judge still gets the SHARED sections it needs",
          "plays" in fj and "reasoning_method" in fj)
    check("failure_judge is NOT served fingerprints/mechanisms",
          "fingerprints" not in fj and "mechanisms" not in fj)

    # NEGATIVE 1 - an undeclared section must stop the view, not be served or dropped
    import copy
    tampered = copy.deepcopy(brain)
    tampered["a_new_section_nobody_declared"] = {"x": 1}
    try:
        build(tampered, "specialist")
        check("NEGATIVE undeclared section refuses to serve", False)
    except SystemExit as e:
        print("     guard output: %s" % str(e)[:96])
        check("NEGATIVE undeclared section refuses to serve", True)

    # NEGATIVE 2 - an unknown role must not silently return an empty view
    try:
        build(brain, "trader")
        check("NEGATIVE unknown role refuses", False)
    except SystemExit as e:
        print("     guard output: %s" % str(e)[:96])
        check("NEGATIVE unknown role refuses", True)

    # NEGATIVE 3 - no view may carry every section by accident
    check("NEGATIVE specialist view is strictly smaller than the brain",
          len([k for k in spec if k != "meta"]) < len([k for k in brain if k != "meta"]),
          "%d of %d sections" % (len(served), len(sections_index(brain))))

    # losslessness: every section reaches at least one role, or is declared dead on purpose
    idx = sections_index(brain)
    orphan = [k for k, e in idx.items()
              if not (e.get("roles") or []) and not e.get("withheld_why")]
    check("no section is orphaned without a stated reason", not orphan, str(orphan))

    print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % fails))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", help="serve the brain scoped to this role")
    ap.add_argument("--out", help="write the view here (default: print the summary only)")
    ap.add_argument("--phase", default="working",
                    choices=["working", "briefing", "post_outcome", "all"],
                    help="working (default) = what stays in view while the curve is drawn; "
                         "briefing = the pre-launch mission; all = a human reading the brain")
    ap.add_argument("--roles", action="store_true", help="the section x role matrix")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return cmd_selftest()
    if a.roles:
        return cmd_roles()
    if a.role:
        return cmd_view(a.role, a.out, a.phase)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
