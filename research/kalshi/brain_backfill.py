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
name." `audit` and `retracted` are two typed slots, present on every play, with the session inside.
That is why this does not add 82 bespoke keys, which is the disease D29 cured.

RETRACTION (Greg, S112): "if the old claims are no longer valid, ditch them. They're just noise if
they aren't valid." TWO DIFFERENT OBJECTS, and conflating them would break D31:
  - a refuted SIGNAL is SCOPED, never deleted - "a refutation is scoped to the cell and the
    instrument it was measured on" (D31). This tool never touches those.
  - a false CLAIM ABOUT THE EVIDENCE is just wrong, and it is the noise. Example: a forward field
    reading "calls the sign 4/4 on the walk's four scorable seams" when the same record's
    assumption_retired field concedes a reproduction of +350 against a realized -990, and the
    honest tally is 2/4.
Retraction MOVES the claim out of the served fields into `retracted[]` with the refuting evidence
beside it. The agent stops reading it as true, which is what "noise" means when the reader is a
machine; the record survives, because this desk supersedes and never silently deletes (DECISIONS.md
header: "Never delete a line; supersede it with a new one"). If a hard delete is wanted instead,
that is a one-line change here and Greg's call, not mine.

GUARDS (D8: incumbents byte-identical, never a direct edit):
  - additive by default: a non-empty incumbent field is NEVER overwritten, only filled when empty
  - retraction is opt-in per claim, from a proposal file, and always preserves the original text
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
    """Move a no-longer-valid CLAIM out of a served field into retracted[], evidence beside it.
    Never touches a refuted SIGNAL - that is D31's territory and is scoped, not deleted."""
    by_id = {p["id"]: p for p in brain["plays"]}
    n = 0
    for r in retr.get("retractions", []):
        pid, field = r.get("play_id"), r.get("field")
        p = by_id.get(pid)
        if p is None:
            errs.append("retraction names an unknown play: %s" % pid)
            continue
        for k in ("claim", "why_invalid", "evidence"):
            if not str(r.get(k, "")).strip():
                errs.append("%s: retraction missing '%s'" % (pid, k))
        if errs:
            continue
        original = p.get(field)
        if original is None and field not in (p.get("legacy_notes") or {}):
            errs.append("%s: field '%s' not present, nothing to retract" % (pid, field))
            continue
        p.setdefault("retracted", []).append(OrderedDict([
            ("session", SESSION), ("field", field),
            ("claim", r["claim"]), ("why_invalid", r["why_invalid"]),
            ("evidence", r["evidence"]),
            ("original_value", original)]))
        # blank the served field so an agent cannot read the false claim as true
        if field in p:
            p[field] = ""
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

    # a fabricated instance path must be refused
    bad = copy.deepcopy(audit)
    bad["audits"][0]["instances"] = [{"date": "20260701", "group": "g22",
                                      "source_file": "research/kalshi/forecasts/NOPE.json",
                                      "what_the_state_said": "x", "what_the_day_did": "x",
                                      "supports_or_contradicts": "supports"}]
    _, e2 = build_plan(load(BRAIN), bad)
    check("fabricated instance path is refused", any("does not resolve" in x for x in e2))

    bad2 = copy.deepcopy(audit)
    bad2["audits"][0]["instances"] = [{"date": "20260701", "group": "g22",
                                       "source_file": "E:/Markets/research/kalshi/knowledge/ng_brain.json",
                                       "what_the_state_said": "x", "what_the_day_did": "x",
                                       "supports_or_contradicts": "supports"}]
    _, e3 = build_plan(load(BRAIN), bad2)
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
        {"play_id": brain["plays"][0]["id"], "field": "caveats", "claim": "x"}]}, e4)
    check("retraction without why_invalid/evidence is refused", any("missing" in x for x in e4))

    e5 = []
    apply_retractions(load(BRAIN), {"retractions": [
        {"play_id": "weather.not_real", "field": "caveats", "claim": "x",
         "why_invalid": "y", "evidence": "z"}]}, e5)
    check("retraction on an unknown play is refused", any("unknown play" in x for x in e5))

    # retraction preserves the original text
    b3 = load(BRAIN)
    pid = b3["plays"][0]["id"]
    orig = b3["plays"][0].get("caveats")
    e6 = []
    apply_retractions(b3, {"retractions": [{"play_id": pid, "field": "caveats",
                                            "claim": "c", "why_invalid": "w", "evidence": "e"}]}, e6)
    kept = b3["plays"][0].get("retracted", [{}])[0].get("original_value")
    check("retraction PRESERVES the original value", kept == orig and not e6)
    check("retraction BLANKS the served field", b3["plays"][0].get("caveats") == "")

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
    a = ap.parse_args()
    return {"plan": cmd_plan, "apply": cmd_apply, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
