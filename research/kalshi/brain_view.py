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

THE SECTION FILTER IS A RELEVANCE FILTER. THE WINDOW REDACTION IS A BLIND WALL, and it exists
because the docstring here used to say "the brain carries no price" - which was FALSE and was
caught by a specialist mid-rehearsal, not by any test of mine.

MEASURED S114: `plays[].instances[]` carry DATED REALIZED OUTCOMES in dollars for the exact days
being forecast - "20260622 (Mon): day_move +650 USD - gap +1210 + session net -560". The g22 window
draws 455 date-string hits across its ten days, g23 draws 411. Specialist B, forecasting 20260622
from a view built by this module, hit its own answer at step 4 of the decision order and emitted
+650 - the leaked actual. It declared the leak instead of using it quietly, and its pre-influence
sign read (step 3a, taken before the hit) is the only part of that run that is evidence.

S112 stamped 624 dated instances into the brain and every merge since has added realized outcomes,
so this grows on its own. The section filter could never have caught it: sections were the wrong
axis - the leak is on the TIME axis.

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


def window_tokens(days):
    """Every string form a block's days appear in on this desk: 20260622, 2026-06-22, 0622, 06/22."""
    toks = set()
    for d in days:
        y, m, dd = d[:4], d[4:6], d[6:8]
        toks.update({d, "%s-%s-%s" % (y, m, dd), "%s%s" % (m, dd), "%s/%s" % (m, dd)})
    return toks


def redact_window(obj, toks, counter):
    """Strip any leaf string that names an in-window day, and SAY SO in its place.

    Aggressive on purpose. A prose sentence mentioning a block day's realized move is the leak just
    as much as a structured field is, and the MMDD form ("0622") is this desk's own shorthand - it
    appears 100 times for one day. A false positive costs a specialist one sentence of history; a
    false negative hands it the answer.

    The replacement is a VISIBLE marker, never a silent drop: holes #7 and #8 were both silent
    absences that read downstream like a deliberate mask, and the standing lesson is that an
    absence has to announce itself.
    """
    if isinstance(obj, dict):
        return OrderedDict((k, redact_window(v, toks, counter)) for k, v in obj.items())
    if isinstance(obj, list):
        return [redact_window(v, toks, counter) for v in obj]
    if isinstance(obj, str) and any(t in obj for t in toks):
        counter[0] += 1
        return ("[REDACTED - in-window date. This text named a day inside the block you are "
                "forecasting and the brain records realized outcomes against those days. Withheld "
                "by the blind wall, not missing.]")
    return obj


# NO BLANKET OUTCOME STRIP - REVERTED S114, and the reason is the correction itself.
# Specialist E proposed dropping `what_the_day_did` from every instance to cut size and leak
# together. I applied it to ALL instances, which was wrong. Greg: "Why did you strip outcomes out?
# He should have those just not real price curve."
# He is right and it is the sharper rule. A PAST day's outcome is the EVIDENCE - it is what makes
# an instance worth carrying, it is what the falsifier fields rest on (the thing both specialists
# called the most useful content in the brain), and it is the library D32 is built to accumulate.
# What must not be served is the outcome of a day the specialist is FORECASTING. That is a window
# question, not a field question, and `redact_window` already answers it: any leaf naming an
# in-window day goes, including that instance's own `what_the_day_did`.
# The blanket strip was therefore both harmful and redundant - it destroyed 938 historical
# evidence fields to remove leaks the window wall had already removed.

# Files the harness AUTO-LOADS into every agent before it reads any instruction. CLAUDE.md is the
# one that matters and it is the THIRD leak channel specialist E found (A-50): it states walked
# blocks' blind and refine scores outright and names 0629's mechanism and its actual.
AUTOLOADED = ("CLAUDE.md",)


def context_leak(days, root=None):
    """-> [(file, token, excerpt)] for any in-window day named in an auto-loaded file.

    THE SIMPLEST FIX THAT ENFORCES SOMETHING (Greg, S114: "do the simplest fix because we're only
    going to need it for 2 more runs"). Rewriting CLAUDE.md or maintaining a blind-safe variant
    would both be larger and would need maintaining past the point of use. A GATE costs nothing
    when clean and stops the line when not.

    It is clean for a FRESH block by construction - nothing can record the outcome of a day nobody
    has forecast - so this passes silently on G24 and fires only if someone re-runs a walked block
    blind, which is exactly the case that should stop.

    A date match is not automatically a leak: CLAUDE.md is full of SESSION dates
    (SESSION_HANDOFF_2026-07-20_S99.md) and dataset span endpoints. The excerpt is returned so the
    caller can see which it is rather than trusting the count.
    """
    root = root or os.path.dirname(os.path.dirname(HERE))
    # SCAN THE MMDD FORM ONLY, and that is the whole discriminator. This desk writes a TRADING DAY
    # as MMDD ("0624", "0709", "0629") and a SESSION date as ISO ("SESSION_HANDOFF_2026-07-20_S99",
    # "cost us an hour on 2026-07-20"). Measured on all three live blocks: every true leak is MMDD,
    # every false positive was ISO. An outcome-word regex was tried first and kept firing on "S100"
    # and a "$500/mo" price - it would have blocked the one clean block we actually need to run,
    # and a gate that cries wolf is a gate people route around (D33).
    # LIMIT, STATED: an outcome written in ISO form would slip through. Accepted deliberately -
    # Greg, S114: "do the simplest fix because we're only going to need it for 2 more runs."
    toks = {d[4:8] for d in days}
    out = []
    for fn in AUTOLOADED:
        path = os.path.join(root, fn)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for t in sorted(toks):
            i = text.find(t)
            while i >= 0:
                ex = text[max(0, i - 90):i + len(t) + 70].replace("\n", " ")
                out.append({"file": fn, "token": t, "excerpt": ex, "leak": True})
                i = text.find(t, i + 1)
    return out


def assert_no_context_leak(gid, hard=True):
    """Gate a BLIND run on the auto-loaded files. Prints both counts; fires only on outcomes."""
    import group_config as gc
    hits = context_leak(gc.GROUPS[gid]["days"])
    leaks = [h for h in hits if h["leak"]]
    print("[context_leak] %s: %d in-window date mention(s) in %s, %d carrying an OUTCOME"
          % (gid, len(hits), "/".join(AUTOLOADED), len(leaks)))
    for h in leaks[:6]:
        print("    LEAK [%s] ...%s..." % (h["token"], h["excerpt"][:120]))
    if leaks and hard:
        raise SystemExit(
            "context_leak: %s has %d outcome mention(s) in auto-loaded context (A-50). Every agent "
            "in this repo loads those files before it reads any instruction, so a blind run on this "
            "block starts with its own answer. A FRESH block is clean by construction - this fires "
            "only when re-running a walked one, which is exactly what should stop." % (gid, len(leaks)))
    if not leaks:
        print("    clean - the matches are session dates and handoff filenames, not outcomes.")
    return leaks


def build(brain, role, phase="working", window_days=None):
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
    if window_days:
        # BLIND LEGALITY (A-53). A window means a blind run, so annotate every play with whether it
        # CAN fire on a blind slice. Specialist D wrote a stand-down paragraph for each of four
        # plays that were never going to be available; this lets that be one line. The
        # CONTRADICTION verdict is the one that matters - a play asserting blind-legality while
        # naming a price-derived quantity is worse than a silently unavailable one, because the
        # assertion is what a specialist trusts.
        try:
            import blind_legality
            verdicts = blind_legality.sweep(brain, verbose=False)
            for pl in view.get("plays", []):
                v = verdicts.get(pl.get("id"))
                if v:
                    pl["blind_legality"] = v
        except Exception as e:
            print("[brain_view] blind_legality annotation skipped: %s" % e)
        toks = window_tokens(window_days)
        counter = [0]
        for k in list(view):
            if k == "meta":
                continue
            view[k] = redact_window(view[k], toks, counter)
        meta["window_redaction"] = OrderedDict([
            ("days", sorted(window_days)),
            ("leaves_redacted", counter[0]),
            ("historical_outcomes", "KEPT. A past day's outcome is evidence; only in-window "
                                    "days are withheld (Greg, S114)."),
            ("why", "The brain carries DATED REALIZED OUTCOMES in dollars against block days "
                    "(S112 stamped 624 instances; every merge since adds more). A blind specialist "
                    "reading them gets its own answer - measured S114, specialist B on 20260622."),
            ("what_you_still_have", "Every play, mechanism and falsifier. Only the sentences naming "
                                    "in-window days are gone, and each one says so where it stood."),
        ])
    meta["view_served"] = served
    meta["view_withheld"] = [OrderedDict([("section", n), ("why", w)]) for n, w in withheld]
    # the index itself is trimmed to what this role is served, so the view does not advertise a
    # section it cannot see and then withhold it - that reads as a mask rather than a scoping
    meta["sections"] = OrderedDict((k, v) for k, v in idx.items() if k in served)
    return view, served, withheld


def cmd_view(role, out, phase="working", gid=None):
    brain = load()
    days = None
    if gid:
        sys.path.insert(0, HERE)
        import group_config as gc
        if gid not in gc.GROUPS:
            raise SystemExit("brain_view: unknown group %r" % gid)
        days = gc.GROUPS[gid]["days"]
    view, served, withheld = build(brain, role, phase, days)
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
    wr = view["meta"].get("window_redaction")
    if wr:
        print("  BLIND WALL : %d leaf string(s) redacted for the %s window (%s..%s)"
              % (wr["leaves_redacted"], gid, wr["days"][0], wr["days"][-1]))
    elif gid is None:
        print("  BLIND WALL : NOT APPLIED - no --gid given. A blind specialist MUST be served with "
              "--gid, or the brain hands it dated realized outcomes for its own day.")
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

    # THE BLIND WALL - the leak two specialists found mid-rehearsal, and the branch that closes it.
    import group_config as gc
    days = gc.GROUPS["g22"]["days"]
    raw_hits = sum(json.dumps(brain).count(d) for d in days)
    walled, _, _ = build(brain, "specialist", "working", days)
    txt = json.dumps({k: v for k, v in walled.items() if k != "meta"})
    wall_hits = sum(txt.count(d) for d in days)
    wr = walled["meta"]["window_redaction"]
    print("     guard output: %d leaf string(s) redacted; in-window date hits %d -> %d"
          % (wr["leaves_redacted"], raw_hits, wall_hits))
    check("BLIND WALL removes every in-window date from the served body", wall_hits == 0,
          "%d redacted" % wr["leaves_redacted"])
    check("the wall REPORTS itself rather than dropping silently",
          wr["leaves_redacted"] > 0 and wr["why"])
    check("NEGATIVE without a window the leak is present (the wall is doing the work)",
          raw_hits > 400, "%d raw hits" % raw_hits)
    unwalled, _, _ = build(brain, "specialist", "working", None)
    check("NEGATIVE no window -> no redaction record, so it cannot look applied",
          "window_redaction" not in unwalled["meta"])

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
    ap.add_argument("--gid", help="group id - REDACT every in-window date from the view (the blind "
                                  "wall). Required for any blind specialist.")
    ap.add_argument("--roles", action="store_true", help="the section x role matrix")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return cmd_selftest()
    if a.roles:
        return cmd_roles()
    if a.role:
        return cmd_view(a.role, a.out, a.phase, a.gid)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
