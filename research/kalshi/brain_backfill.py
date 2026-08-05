#!/usr/bin/env python3
"""
brain_backfill.py - put the reasoning, the evidence and the past instances INTO the brain, and
retract the claims that are no longer valid. (Registry S111-3 and S111-4.)

WHY THIS IS THE POINT OF THE WHOLE AUDIT (Greg, S112):
"The biggest thing with this is to get all of the reasoning and context and decision making info
linked together in one doc and to have it reachable by the agents. It hasn't been so far. And
there's no evidence or context attached to the decisions. So we also want the past instances tied
to those decisions too where there is some past instances... We didn't start that until the last
run i think so we have to reconstruct the previous ones."

THE BRAIN IS THE ONE DOC THAT IS ACTUALLY SERVED. RUN_SOP templates BLD-1, BLD-2, RFN-1 and RFN-2
all hand the specialist `knowledge/ng_brain.json` at spawn. DECISIONS.md is served to NOBODY - D25
records that an explicit instruction about the order a specialist should reason in "has never been
read by a specialist" for exactly this reason. So reasoning that lives anywhere else is unreachable
by the machine that needs it, and putting it in the brain is what "reachable by the agents" means.

WHAT GOES IN, all of it from BRAIN_AUDIT_S112.json (82 plays, 349 traced instances):
  instances[]          the past instances, each traced to a posterior or an actual
  corpus               d24_state + searched_on + scope + n_found (searched-none DECAYS, hence re-runnable)
  support              the audit class
  falsifier            for the 65 plays that have none and therefore cannot be killed by evidence
  health.can_change_state   the D28 degeneracy read
  audit                a TYPED slot carrying the argument, the falsifiability probe, the
                       recommendation and the session tag

THE TYPED-SLOT RULE (D29, governing): "every field must be queryable across ALL plays; a session
recording something new puts it in a TYPED SLOT with a session tag inside it, never in a new field
name." `audit` is a typed slot, present on every play, with the session inside.
That is why this does not add 82 bespoke keys, which is the disease D29 cured.

RETRACTION (Greg, S112): "if the old claims are no longer valid, ditch them. They're just noise if
they aren't valid." TWO DIFFERENT OBJECTS, and conflating them would break D31:
  - a refuted SIGNAL is SCOPED, never deleted - "a refutation is scoped to the cell and the
    instrument it was measured on" (D31). This tool never touches those.
  - a false CLAIM ABOUT THE EVIDENCE is just wrong, and it is the noise. Example: a forward field
    reading "calls the sign 4/4 on the walk's four scorable seams" when the same record's
    assumption_retired field concedes a reproduction of +350 against a realized -990, and the
    honest tally is 2/4.
Retraction REMOVES the claim from the brain. It is NOT parked in a graveyard slot on the play -
Greg overturned that design: "What's your reasoning for keeping false evidence? If we're going to
use them as a reason NOT to do something then it's fine. Otherwise it feels like information that
we don't need and are only setting ourselves up to have it accidentally used at a different time."
He is right, and the rules I had reached for governed different objects: DECISIONS.md is append-only
because a ledger's reversal history IS its content, and brain_schema's losslessness governed a
MIGRATION. The brain is a working document agents LOAD AND READ AS TRUE, so a false claim parked
inside it is still in the context window and still available to be picked up later. Nothing is lost
by deleting - git holds every prior version, which is D34's own split: git is the record, the brain
is the working set. Each retraction therefore carries a DISPOSITION: DELETE (guards nothing, goes),
or KEEP_AS_GUARD (it functions as a reason NOT to do something - Greg's own test - so it is
rewritten into `caveats` as a do-not-retry warning with its evidence, where a specialist reads it).

GUARDS (D8: incumbents byte-identical, never a direct edit):
  - additive by default: a non-empty incumbent field is NEVER overwritten, only filled when empty
  - retraction is opt-in per claim, from a proposal file, and requires an explicit disposition
  - every instance path must resolve, and a desktop path is refused (D34)
  - dry-run default; --write takes a backup first and re-validates the schema after

USAGE
    python brain_backfill.py plan                        # what would change, nothing written
    python brain_backfill.py plan --verbose
    python brain_backfill.py apply --write               # additive backfill only
    python brain_backfill.py apply --write --retract retractions.json
    python brain_backfill.py selftest
"""

import argparse
import copy
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
AUDIT = os.path.join(HERE, "BRAIN_AUDIT_S112.json")
SESSION = "S112"

sys.path.insert(0, HERE)
import brain_audit as BA  # noqa: E402  - reuse the traceability wall and the desktop-path guard


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def _empty(v):
    return v is None or v == "" or v == [] or v == {} or v == "UNAUDITED"


def build_plan(brain, audit):
    """Returns (plan, errors). Never mutates its inputs."""
    by_id = {p["id"]: p for p in brain["plays"]}
    plan, errs = [], []
    for rec in audit["audits"]:
        pid = rec["play_id"]
        p = by_id.get(pid)
        if p is None:
            errs.append("audit names a play not in the brain: %s" % pid)
            continue
        ch = OrderedDict()

        # --- instances: additive, and every one must trace (D32 s3 / D34)
        if not p.get("instances") and rec.get("instances"):
            keep = []
            for ins in rec["instances"]:
                sf = ins.get("source_file", "")
                if any(BA._is_machine_path(t) for t in BA._split_citation(sf)):
                    errs.append("%s: instance carries a DESKTOP PATH: %s" % (pid, sf))
                    continue
                if not BA._traces(sf):
                    errs.append("%s: instance source_file does not resolve: %s" % (pid, sf))
                    continue
                keep.append(OrderedDict([
                    ("date", ins.get("date")), ("group", ins.get("group")),
                    ("source_file", sf),
                    ("what_the_state_said", ins.get("what_the_state_said")),
                    ("what_the_day_did", ins.get("what_the_day_did")),
                    ("supports_or_contradicts", ins.get("supports_or_contradicts")),
                    ("added_by", "audit_%s" % SESSION)]))
            if keep:
                ch["instances"] = keep

        # --- corpus state. searched_on matters because searched-none DECAYS as the corpus grows.
        cur = p.get("corpus") or {}
        if cur.get("d24_state") in (None, "not_searched") and rec.get("d24_state"):
            ch["corpus"] = OrderedDict([
                ("d24_state", rec["d24_state"]),
                ("searched_on", SESSION),
                ("searched_scope", "committed corpus: forecasts/ + renders/ng_refine_s95/ "
                                   "(g6-g23 posteriors, actuals, mbo_evidence)"),
                ("n_found", len(rec.get("instances") or []))])

        # --- support class
        if p.get("support", "UNAUDITED") == "UNAUDITED":
            ch["support"] = rec["support_class"]

        # --- falsifier: 65 plays have none and so cannot be killed by evidence (S111-4)
        if _empty(p.get("falsifier")) and str(rec.get("falsifier", "")).strip():
            ch["falsifier"] = rec["falsifier"]

        # --- D28 degeneracy read
        h = p.get("health") or {}
        if h.get("can_change_state") is None and rec.get("condition_can_change_state"):
            ch["health.can_change_state"] = rec["condition_can_change_state"]

        # --- the typed audit slot: the REASONING, which is the thing that was never reachable
        if not p.get("audit"):
            ch["audit"] = OrderedDict([
                ("session", SESSION),
                ("support_class", rec["support_class"]),
                ("argument", rec.get("the_argument")),
                ("could_evidence_have_come_out_otherwise",
                 rec.get("could_evidence_have_come_out_otherwise")),
                ("recommendation", rec.get("recommendation")),
                ("confidence", rec.get("confidence")),
                ("source", "BRAIN_AUDIT_S112.json")])

        if ch:
            plan.append((pid, ch))
    return plan, errs


def apply_retractions(brain, retr, errs):
    """Remove a no-longer-valid CLAIM from the brain. Two dispositions, and the choice between them
    is the whole design.

    GREG, S112, and he overturned my first design: "What's your reasoning for keeping false
    evidence? If we're going to use them as a reason NOT to do something then it's fine. Otherwise
    it feels like information that we don't need and are only setting ourselves up to have it
    accidentally used at a different time."

    He is right. My first version parked retracted claims in a `retracted[]` slot ON THE PLAY, on
    the reasoning that this desk supersedes rather than deletes. But that rule comes from
    DECISIONS.md, an append-only LEDGER where the history of a reversal IS the content, and from
    brain_schema's losslessness, which governed a MIGRATION - reshaping fields without dropping
    values. The brain is neither. It is a working document that agents LOAD AND READ AS TRUE at
    every spawn, so a false claim parked inside it is still in the context window, still readable,
    still available to be picked up later. That is the accidental-reuse hazard, built in by hand.

    Nothing is lost by deleting: git holds every prior version of this file, which is D34's own
    split - git is the record, the brain is the working set.

    DISPOSITION, required per retraction:
      DELETE         the claim guards nothing. A play claiming 4/4 when the record says 2/4 does
                     not help anyone by being remembered. Removed from the served field outright;
                     the proposal file and git history are the record.
      KEEP_AS_GUARD  the claim functions as a reason NOT to do something - Greg's own test. This is
                     D31's scoped refutation: tried in this cell, failed in this cell, do not
                     re-try it here. It is rewritten into `caveats` as a warning WITH its evidence,
                     where a specialist will actually read it, rather than filed in a graveyard.
    """
    by_id = {p["id"]: p for p in brain["plays"]}
    n = 0
    for r in retr.get("retractions", []):
        pid, field = r.get("play_id"), r.get("field")
        disp = r.get("disposition")
        p = by_id.get(pid)
        if p is None:
            errs.append("retraction names an unknown play: %s" % pid)
            continue
        for k in ("claim", "why_invalid", "evidence"):
            if not str(r.get(k, "")).strip():
                errs.append("%s: retraction missing '%s'" % (pid, k))
        if disp not in ("DELETE", "KEEP_AS_GUARD"):
            errs.append("%s: disposition must be DELETE or KEEP_AS_GUARD, got %r "
                        "(Greg's test: does this claim function as a reason NOT to do something?)"
                        % (pid, disp))
        if errs:
            continue
        if field not in p:
            errs.append("%s: field '%s' not present, nothing to retract" % (pid, field))
            continue

        # SURGICAL, NOT BLUNT. A field often carries a false claim AND a valid one in the same
        # run of sentences. selector.midblock_right_the_ship's forward field credits a run "with
        # ZERO DIRECTION CHANGES - the mid-block re-derivation working", which is false because
        # this play's only action IS a direction change, so a run with none is a run where it
        # never fired - and the very next clause records a real G18 result, "RTS fired 0506 UP but
        # the turn did not deliver". Blanking the field would delete the honest half with the
        # false half. So a retraction MAY carry a `replacement`: the corrected value of the field.
        # Omitting it clears the field, which is right only when the whole field was the claim.
        replacement = r.get("replacement")
        if replacement is not None and not str(replacement).strip():
            errs.append("%s: replacement given but empty - omit it to clear the field, or supply "
                        "the corrected text" % pid)
            continue

        if disp == "KEEP_AS_GUARD":
            guard = ("DO NOT RE-TRY (retracted %s): %s | why it fails: %s | evidence: %s"
                     % (SESSION, r["claim"], r["why_invalid"], r["evidence"]))
            existing = str(p.get("caveats") or "").strip()
            p["caveats"] = (existing + " " + guard).strip() if existing else guard
        # in every case the false claim leaves the served field. It is not parked anywhere in the
        # brain - the retraction proposal file and git history carry the record.
        p[field] = replacement if replacement is not None else ""
        n += 1
    return n


def cmd_plan(a):
    brain, audit = load(BRAIN), load(AUDIT)
    plan, errs = build_plan(brain, audit)
    fields = {}
    for _, ch in plan:
        for k in ch:
            fields[k] = fields.get(k, 0) + 1
    print("brain %s | audit %d plays | %d plays would change\n"
          % (brain["meta"]["version"], len(audit["audits"]), len(plan)))
    print("  field                       plays filled")
    for k, v in sorted(fields.items(), key=lambda kv: -kv[1]):
        print("    %-26s %3d" % (k, v))
    n_inst = sum(len(ch.get("instances", [])) for _, ch in plan)
    print("\n  instances added: %d" % n_inst)
    print("  incumbents overwritten: 0 (additive by construction - a non-empty field is never touched)")
    if errs:
        print("\n  ERRORS (%d) - apply would REFUSE:" % len(errs))
        for e in errs[:20]:
            print("    " + e)
    if a.verbose:
        print()
        for pid, ch in plan[:12]:
            print("  %-54s %s" % (pid[:54], ",".join(ch)))
    return 1 if errs else 0


def cmd_apply(a):
    brain, audit = load(BRAIN), load(AUDIT)
    before = json.dumps(brain, sort_keys=True)
    plan, errs = build_plan(brain, audit)
    if errs:
        print("REFUSED - %d errors; run plan to see them." % len(errs))
        for e in errs[:20]:
            print("   " + e)
        return 1

    by_id = {p["id"]: p for p in brain["plays"]}
    incumbent_snapshot = {p["id"]: copy.deepcopy(p) for p in brain["plays"]}
    for pid, ch in plan:
        p = by_id[pid]
        for k, v in ch.items():
            if k == "health.can_change_state":
                p.setdefault("health", OrderedDict())["can_change_state"] = v
            else:
                p[k] = v

    n_retr = 0
    if a.retract:
        n_retr = apply_retractions(brain, load(a.retract), errs)
        if errs:
            print("REFUSED - retraction errors:")
            for e in errs[:20]:
                print("   " + e)
            return 1

    # D8 WALL: every incumbent field that existed and was non-empty must be byte-identical.
    touched = set()
    for pid, ch in plan:
        touched |= set(ch)
    for pid, old in incumbent_snapshot.items():
        new = by_id[pid]
        for k, ov in old.items():
            if _empty(ov) or k in ("instances", "corpus", "support", "falsifier", "health", "audit"):
                continue
            if k == "retracted":
                continue
            if json.dumps(new.get(k), sort_keys=True) != json.dumps(ov, sort_keys=True):
                if a.retract and any(r.get("play_id") == pid and r.get("field") == k
                                     for r in load(a.retract).get("retractions", [])):
                    continue      # a declared retraction is the one licensed change
                errs.append("INCUMBENT CHANGED: %s.%s" % (pid, k))
    if errs:
        print("REFUSED - the D8 incumbent wall fired:")
        for e in errs[:20]:
            print("   " + e)
        return 1

    if not a.write:
        print("dry run OK: %d plays would be filled, %d claims retracted, 0 incumbents changed."
              % (len(plan), n_retr))
        print("re-run with --write to apply.")
        return 0

    bak = os.path.join(HERE, "knowledge",
                       "ng_brain_%s_prebackfill_backup.json" % brain["meta"]["version"])
    if not os.path.exists(bak):
        with open(bak, "w", encoding="utf-8") as f:
            f.write(before)
        print("backup: %s" % os.path.relpath(bak, ROOT))
    with open(BRAIN, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=1, ensure_ascii=False)
    print("APPLIED: %d plays filled, %d claims retracted -> %s"
          % (len(plan), n_retr, os.path.relpath(BRAIN, ROOT)))
    return 0


def cmd_mark_actions(a):
    """Give fires and declines EQUAL FOOTING in the brain (Greg, S112: "I just want to give them
    equal footing so one isn't ignored over the other", and "there should be no difference in how
    they are listed in the schema for the brain except one is a do and the other a don't").

    So there is ONE instances[] list and ONE field that distinguishes them: action = do | dont.
    No separate section, no second structure, no subordinate category - because a category filed
    somewhere else is a category that gets read second, and the whole reason the declines were
    invisible for 23 sessions is that nothing recorded them at all.

    This stamps `action` onto instances that predate the field. A fire and a decline then differ by
    exactly one token, and any consumer counting evidence counts both by default.
    """
    brain = load(BRAIN)
    led_path = os.path.join(HERE, "STANDDOWN_LEDGER_S112.json")
    declined = set()
    if os.path.exists(led_path):
        for r in load(led_path)["entries"]:
            if r["action"] == "stood_down":
                declined.add((r["play_id"], r["date"]))
    n_do = n_dont = 0
    for p in brain["plays"]:
        for ins in p.get("instances") or []:
            if "action" in ins:
                continue
            key = (p["id"], ins.get("date"))
            said = str(ins.get("what_the_state_said") or "")
            is_dont = key in declined or "stood_down" in said or "plays_stood_down" in said
            ins["action"] = "dont" if is_dont else "do"
            n_dont += is_dont
            n_do += not is_dont
    print("stamped action on instances: do=%d  dont=%d" % (n_do, n_dont))
    if not a.write:
        print("dry run - nothing written. Re-run with --write.")
        return 0
    with open(BRAIN, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=1, ensure_ascii=False)
    print("written to %s" % os.path.relpath(BRAIN, ROOT))
    return 0


def cmd_selftest(a):
    """The guards must fire on their own defects (D11)."""
    brain, audit = load(BRAIN), load(AUDIT)
    res = []

    def check(name, ok, why=""):
        res.append(ok)
        print("  %-4s | %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  " + why))

    plan, errs = build_plan(brain, audit)
    check("clean plan builds with no errors", not errs, str(errs[:2]))
    check("plan is non-empty", len(plan) > 0)

    # The instance guards must be tested INDEPENDENTLY OF WHETHER THE BACKFILL HAS RUN. Once it
    # has, every play carries instances and build_plan correctly skips instance-filling, so an
    # injected bad instance is never reached and the test passes for the wrong reason. Clearing
    # the target play's instances first tests the guard rather than the current brain state.
    def _brain_with_cleared_instances(pid):
        b = load(BRAIN)
        for pl in b["plays"]:
            if pl["id"] == pid:
                pl["instances"] = []
        return b

    target = audit["audits"][0]["play_id"]

    bad = copy.deepcopy(audit)
    bad["audits"][0]["instances"] = [{"date": "20260701", "group": "g22",
                                      "source_file": "research/kalshi/forecasts/NOPE.json",
                                      "what_the_state_said": "x", "what_the_day_did": "x",
                                      "supports_or_contradicts": "supports"}]
    _, e2 = build_plan(_brain_with_cleared_instances(target), bad)
    check("fabricated instance path is refused", any("does not resolve" in x for x in e2))

    bad2 = copy.deepcopy(audit)
    bad2["audits"][0]["instances"] = [{"date": "20260701", "group": "g22",
                                       "source_file": "E:/Markets/research/kalshi/knowledge/ng_brain.json",
                                       "what_the_state_said": "x", "what_the_day_did": "x",
                                       "supports_or_contradicts": "supports"}]
    _, e3 = build_plan(_brain_with_cleared_instances(target), bad2)
    check("desktop path in an instance is refused (D34)", any("DESKTOP PATH" in x for x in e3))

    # additive: a play that already has a falsifier must not have it replaced
    b2 = load(BRAIN)
    have = [p for p in b2["plays"] if str(p.get("falsifier", "")).strip()]
    if have:
        pid = have[0]["id"]
        orig = have[0]["falsifier"]
        pl, _ = build_plan(b2, audit)
        ch = dict(pl).get(pid, {})
        check("existing falsifier is NOT overwritten", "falsifier" not in ch)
    else:
        check("existing falsifier is NOT overwritten", True, "(no play has one)")

    # retraction requires evidence
    e4 = []
    apply_retractions(load(BRAIN), {"retractions": [
        {"play_id": brain["plays"][0]["id"], "field": "caveats", "claim": "x",
         "disposition": "DELETE"}]}, e4)
    check("retraction without why_invalid/evidence is refused", any("missing" in x for x in e4))

    e4b = []
    apply_retractions(load(BRAIN), {"retractions": [
        {"play_id": brain["plays"][0]["id"], "field": "caveats", "claim": "x",
         "why_invalid": "y", "evidence": "z"}]}, e4b)
    check("retraction without a disposition is refused", any("disposition must be" in x for x in e4b))

    e5 = []
    apply_retractions(load(BRAIN), {"retractions": [
        {"play_id": "weather.not_real", "field": "caveats", "claim": "x",
         "why_invalid": "y", "evidence": "z"}]}, e5)
    check("retraction on an unknown play is refused", any("unknown play" in x for x in e5))

    # DELETE leaves NO residue anywhere in the brain (Greg S112)
    b3 = load(BRAIN)
    pid = next(p["id"] for p in b3["plays"] if p.get("trigger"))
    e6 = []
    apply_retractions(b3, {"retractions": [{"play_id": pid, "field": "trigger",
                                            "claim": "c", "why_invalid": "w", "evidence": "e",
                                            "disposition": "DELETE"}]}, e6)
    tgt = next(p for p in b3["plays"] if p["id"] == pid)
    check("DELETE clears the served field", tgt.get("trigger") == "" and not e6)
    check("DELETE leaves NO retracted[] graveyard in the brain", "retracted" not in tgt)
    check("DELETE does not smuggle the claim into caveats",
          "c" not in str(tgt.get("caveats") or "") or "DO NOT RE-TRY" not in str(tgt.get("caveats") or ""))

    # KEEP_AS_GUARD writes a do-not-retry warning where a specialist will read it
    b4 = load(BRAIN)
    pid4 = next(p["id"] for p in b4["plays"] if p.get("trigger"))
    e7 = []
    apply_retractions(b4, {"retractions": [{"play_id": pid4, "field": "trigger",
                                            "claim": "the 4/4 tally", "why_invalid": "record says 2/4",
                                            "evidence": "grp21 posterior",
                                            "disposition": "KEEP_AS_GUARD"}]}, e7)
    t4 = next(p for p in b4["plays"] if p["id"] == pid4)
    check("KEEP_AS_GUARD puts the warning in caveats",
          "DO NOT RE-TRY" in str(t4.get("caveats")) and "record says 2/4" in str(t4.get("caveats")))
    check("KEEP_AS_GUARD still clears the served field", t4.get("trigger") == "")

    # surgical replacement keeps the honest half of a mixed field
    b5 = load(BRAIN)
    pid5 = next(p["id"] for p in b5["plays"] if p.get("trigger"))
    e8 = []
    apply_retractions(b5, {"retractions": [{"play_id": pid5, "field": "trigger",
                                            "claim": "the false half", "why_invalid": "w",
                                            "evidence": "e", "disposition": "DELETE",
                                            "replacement": "the corrected text only"}]}, e8)
    t5 = next(p for p in b5["plays"] if p["id"] == pid5)
    check("replacement REPLACES rather than blanks", t5.get("trigger") == "the corrected text only")

    e9 = []
    apply_retractions(load(BRAIN), {"retractions": [{"play_id": pid5, "field": "trigger",
                                                     "claim": "c", "why_invalid": "w",
                                                     "evidence": "e", "disposition": "DELETE",
                                                     "replacement": "   "}]}, e9)
    check("an empty replacement is refused", any("replacement given but empty" in x for x in e9))

    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--verbose", action="store_true")
    p = sub.add_parser("apply"); p.add_argument("--write", action="store_true")
    p.add_argument("--retract")
    sub.add_parser("selftest")
    p = sub.add_parser("mark-actions"); p.add_argument("--write", action="store_true")
    a = ap.parse_args()
    return {"plan": cmd_plan, "apply": cmd_apply, "selftest": cmd_selftest,
            "mark-actions": cmd_mark_actions}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
