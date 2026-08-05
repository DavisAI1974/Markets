#!/usr/bin/env python3
"""
brain_conditions.py - the CONDITIONS slot: vocabulary, verification, and curation harness.

THE DIRECTIVE. D29 left a visible work list, and this is its largest open number: **74 of 82 plays
have `conditions` unparsed**. D29 also says why the slot matters more than its size suggests -
`conditions[].state_path` "is the slot doing the most work: it makes the D28 degeneracy check run
automatically at every merge instead of by hand-curated registry, which would have caught the burn
gate's constant limb before the merge rather than on a forward test a session later."

THE CONSTRAINT THAT SHAPES THIS FILE. D29, verbatim: `conditions[]` is populated "ONLY from a
hand-curated map, 8 of 82 - regex-parsing prose triggers is the fuzzy-matching error that produced
holes #8 and #9, so the other 74 are marked `unparsed`, an open task and never a guess."

So this tool does NOT parse prose. It does the two things that make hand curation safe:

  1. It publishes the VOCABULARY - every quantity actually served, with the groups it exists in.
     A curator picks from what exists instead of writing down what they expect to exist. Hole #8
     was an off-instrument field and hole #9 a wrong encoding; both are "the name looked right".
  2. It VERIFIES every state_path against the committed states and refuses to write one that does
     not resolve. Same wall as brain_audit.py's instance traceability, for the same reason: a
     condition naming a field that is not there is worse than no condition, because it reads as
     evaluated and silently never fires.

COVERAGE IS PART OF THE ANSWER, NOT A FOOTNOTE. A path resolves in a SPAN of groups, not
universally - `tape_conditions.*` starts at g15/g18 because the block did not exist earlier, and
`weather.gw_hdd` is missing in g16/g18/g19. A condition keyed to a path its own block does not
serve cannot fire there, which is D28's discrimination failure arriving by a different road. So
verify reports the span and names the gaps rather than answering yes/no.

USAGE
    python brain_conditions.py vocab                 # served quantities + the groups carrying them
    python brain_conditions.py vocab --grep b_share  # filter
    python brain_conditions.py verify                # gate: every state_path must resolve
    python brain_conditions.py unparsed              # the 74, with their prose, batched for curation
    python brain_conditions.py unparsed --batch 3
    python brain_conditions.py apply prop.json       # additive curation, dry-run; --write to commit
    python brain_conditions.py selftest              # negative tests on the guards

Report-only unless `apply --write`. Never edits a play's incumbent fields; only fills `conditions`
and `conditions_state`, per D8 (incumbents byte-identical).
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
STATE_GLOB = os.path.join(HERE, "renders", "ng_refine_s95", "grp*_state.json")

COMPARATORS = ["<", "<=", ">", ">=", "==", "!="]
REFERENCES = ["absolute", "percentile_3y", "percentile_block", "ratio", "delta", "rank"]
N_BATCHES = 8


def _gnum(p):
    m = re.search(r"grp(\d+)_state", p)
    return int(m.group(1)) if m else -1


def state_files():
    """Chronological, NOT alphabetical. Sorting these as strings puts grp9 after grp23 and makes a
    modern path look unresolvable - which is exactly the false alarm this note exists to prevent."""
    return sorted(glob.glob(STATE_GLOB), key=_gnum)


def days_of(path):
    d = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in d.items() if isinstance(v, dict) and re.fullmatch(r"\d{8}", k)}


def resolve(day, state_path):
    """Walk a dotted path with optional [i] indexing. Returns (ok, value)."""
    cur = day
    for tok in state_path.split("."):
        m = re.match(r"([^\[\]]+)(?:\[(\d+)\])?$", tok)
        if not m:
            return False, None
        key, idx = m.group(1), m.group(2)
        if not isinstance(cur, dict) or key not in cur:
            return False, None
        cur = cur[key]
        if idx is not None:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return False, None
            cur = cur[int(idx)]
    return True, cur


def groups_carrying(state_path):
    """Which groups serve this path on EVERY scored day. Partial coverage inside a group is itself
    a defect signature (the S107 empty-block family), so it is reported separately."""
    full, partial = [], []
    for sf in state_files():
        dd = days_of(sf)
        if not dd:
            continue
        hits = sum(1 for v in dd.values() if resolve(v, state_path)[0])
        if hits == len(dd):
            full.append(_gnum(sf))
        elif hits:
            partial.append((_gnum(sf), hits, len(dd)))
    return full, partial


def _walk(obj, prefix, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue          # _mask_note and friends are annotations, not quantities
            _walk(v, "%s.%s" % (prefix, k) if prefix else str(k), out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix] = out.get(prefix, 0) + 1


def vocabulary():
    """Every NUMERIC leaf served anywhere, with the groups carrying it. Numeric because a condition
    is a bar on a quantity; a string field cannot carry one."""
    seen = {}
    for sf in state_files():
        g = _gnum(sf)
        for day in days_of(sf).values():
            out = {}
            _walk(day, "", out)
            for p in out:
                seen.setdefault(p, set()).add(g)
    return {p: sorted(gs) for p, gs in seen.items()}


def load_brain():
    with open(BRAIN, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def cmd_vocab(a):
    v = vocabulary()
    items = sorted(v.items())
    if a.grep:
        items = [(p, g) for p, g in items if a.grep.lower() in p.lower()]
    print("%d numeric quantities served across %d committed state files"
          % (len(v), len(state_files())))
    if a.grep:
        print("filter %r -> %d" % (a.grep, len(items)))
    print()
    modern = [g for g in (18, 19, 20, 21, 22, 23)]
    for p, gs in items:
        tag = "all-modern" if all(g in gs for g in modern) else "g" + ",".join(str(g) for g in gs[-6:])
        print("  %-58s %s" % (p, tag))
    return 0


def cmd_verify(a):
    b = load_brain()
    rows, bad = [], 0
    for play in b["plays"]:
        for c in play.get("conditions", []):
            sp = c.get("state_path", "")
            full, partial = groups_carrying(sp)
            ok = bool(full or partial)
            if not ok:
                bad += 1
            rows.append((play["id"], sp, full, partial, ok))
    print("brain %s | %d conditions across %d plays"
          % (b["meta"]["version"], len(rows), sum(1 for p in b["plays"] if p.get("conditions"))))
    print()
    for pid, sp, full, partial, ok in rows:
        if not ok:
            print("  UNRESOLVED  %-46s  %s" % (sp, pid))
        elif partial:
            # partial coverage inside a group is the S107 empty-block signature, not a pass
            print("  PARTIAL     %-46s  %s  full=%s partial=%s" % (sp, pid, full, partial))
    span = {}
    for _, sp, full, _, ok in rows:
        if ok:
            span.setdefault(sp, full)
    print()
    print("  unique paths: %d | unresolved: %d" % (len(span) + bad, bad))
    for sp, full in sorted(span.items()):
        print("     %-46s groups %s" % (sp, full))
    if bad:
        print("\nFAIL - a condition naming a field that is not served reads as evaluated and "
              "silently never fires.")
    return 1 if bad else 0


def unparsed_plays(b=None):
    b = b or load_brain()
    return [p for p in b["plays"] if not p.get("conditions")]


def cmd_unparsed(a):
    b = load_brain()
    ps = unparsed_plays(b)
    if a.batch:
        base, extra = divmod(len(ps), N_BATCHES)
        n = a.batch
        start = (n - 1) * base + min(n - 1, extra)
        ps = ps[start:start + base + (1 if n <= extra else 0)]
    print("%d plays with conditions UNPARSED%s\n"
          % (len(ps), " (batch %d of %d)" % (a.batch, N_BATCHES) if a.batch else ""))
    for p in ps:
        print("-" * 92)
        print("id      : %s" % p["id"])
        print("status  : %s   support: %s   confidence: %s"
              % (p.get("status"), p.get("support"), p.get("confidence")))
        for f in ("trigger", "read", "call", "requires", "scope", "caveats"):
            if p.get(f):
                print("%-8s: %s" % (f, str(p[f])[:400]))
    return 0


def cmd_apply(a):
    """Apply a curated proposal. Additive and verified: a condition whose state_path does not
    resolve is REFUSED, and no incumbent field is touched (D8)."""
    with open(a.path, encoding="utf-8") as f:
        prop = json.load(f)
    b = load_brain()
    by_id = {p["id"]: p for p in b["plays"]}
    errs, staged = [], []
    for ent in prop.get("conditions", []):
        pid = ent.get("play_id")
        if pid not in by_id:
            errs.append("unknown play_id %s" % pid)
            continue
        if by_id[pid].get("conditions"):
            errs.append("%s already has conditions - additive only, refusing to overwrite" % pid)
            continue
        for c in ent.get("conditions", []):
            for f in ("quantity", "state_path", "reference", "comparator", "threshold", "units"):
                if f not in c:
                    errs.append("%s: condition missing '%s'" % (pid, f))
            if c.get("comparator") not in COMPARATORS:
                errs.append("%s: comparator %r not in %s" % (pid, c.get("comparator"), COMPARATORS))
            if c.get("reference") not in REFERENCES:
                errs.append("%s: reference %r not in %s" % (pid, c.get("reference"), REFERENCES))
            sp = c.get("state_path", "")
            full, partial = groups_carrying(sp)
            if not (full or partial):
                errs.append("%s: state_path does not resolve in ANY committed state: %s" % (pid, sp))
        staged.append((pid, ent))
    # a play may legitimately have NO numeric condition; that is declared, not silently skipped
    for ent in prop.get("no_condition", []):
        pid = ent.get("play_id")
        if pid not in by_id:
            errs.append("unknown play_id %s" % pid)
        elif not ent.get("why"):
            errs.append("%s: no_condition needs a 'why'" % pid)
        else:
            staged.append((pid, ent))

    print("proposal %s: %d entries, %d errors" % (os.path.relpath(a.path, ROOT), len(staged), len(errs)))
    for e in errs[:40]:
        print("   " + e)
    if errs:
        print("\nREFUSED - the line stops on a gap.")
        return 1
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write to apply.")
        return 0

    bak = os.path.join(HERE, "knowledge",
                       "ng_brain_%s_preconditions_backup.json" % b["meta"]["version"])
    if not os.path.exists(bak):
        with open(bak, "w", encoding="utf-8") as f:
            json.dump(b, f, indent=1, ensure_ascii=False)
        print("backup: %s" % os.path.relpath(bak, ROOT))
    n = 0
    for pid, ent in staged:
        p = by_id[pid]
        if "conditions" in ent:
            p["conditions"] = ent["conditions"]
            p["conditions_state"] = "parsed"
        else:
            p["conditions_state"] = "no_numeric_condition"
            p.setdefault("legacy_notes", OrderedDict())["conditions_note"] = ent["why"]
        n += 1
    with open(BRAIN, "w", encoding="utf-8") as f:
        json.dump(b, f, indent=1, ensure_ascii=False)
    print("applied %d entries to %s" % (n, os.path.relpath(BRAIN, ROOT)))
    return 0


def cmd_selftest(a):
    """The guards must fire on their own defects (D11)."""
    import tempfile
    b = load_brain()
    real = None
    for p in b["plays"]:
        if p.get("conditions"):
            real = p["conditions"][0]["state_path"]
            break
    target = unparsed_plays(b)[0]["id"]
    already = next(p["id"] for p in b["plays"] if p.get("conditions"))

    def cond(**over):
        c = {"quantity": "q", "state_path": real, "reference": "absolute",
             "comparator": ">=", "threshold": 1, "units": "u"}
        c.update(over)
        return c

    cases = [
        ("positive control: verified condition on an unparsed play",
         {"conditions": [{"play_id": target, "conditions": [cond()]}]}, None),
        ("state_path that resolves nowhere is REFUSED",
         {"conditions": [{"play_id": target, "conditions": [cond(state_path="tape_conditions.not_a_field")]}]},
         "does not resolve"),
        ("overwriting an existing conditions[] is REFUSED (additive only, D8)",
         {"conditions": [{"play_id": already, "conditions": [cond()]}]}, "already has conditions"),
        ("unknown play_id is caught",
         {"conditions": [{"play_id": "weather.invented", "conditions": [cond()]}]}, "unknown play_id"),
        ("off-enum comparator is caught",
         {"conditions": [{"play_id": target, "conditions": [cond(comparator="=>")]}]}, "comparator"),
        ("off-enum reference is caught",
         {"conditions": [{"play_id": target, "conditions": [cond(reference="vibes")]}]}, "reference"),
        ("missing field is caught",
         {"conditions": [{"play_id": target,
                          "conditions": [{k: v for k, v in cond().items() if k != "units"}]}]},
         "missing 'units'"),
        ("no_condition without a 'why' is caught",
         {"no_condition": [{"play_id": target}]}, "needs a 'why'"),
        ("no_condition WITH a why is accepted",
         {"no_condition": [{"play_id": target, "why": "qualitative tape read, no numeric bar"}]}, None),
    ]

    class _A:
        write = False

    res = []
    import io, contextlib
    with tempfile.TemporaryDirectory() as td:
        pth = os.path.join(td, "p.json")
        for name, doc, expect in cases:
            with open(pth, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            arg = _A(); arg.path = pth; arg.write = False
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cmd_apply(arg)
            out = buf.getvalue()
            passed = (rc == 0) if expect is None else (rc == 1 and expect in out)
            res.append(passed)
            print("  %-4s | %s%s" % ("PASS" if passed else "FAIL", name,
                                     "" if passed else "  (rc=%d %s)" % (rc, out.strip()[:120])))
    print("\n  %d/%d negative tests passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("vocab"); p.add_argument("--grep")
    sub.add_parser("verify")
    p = sub.add_parser("unparsed"); p.add_argument("--batch", type=int)
    p = sub.add_parser("apply"); p.add_argument("path"); p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"vocab": cmd_vocab, "verify": cmd_verify, "unparsed": cmd_unparsed,
            "apply": cmd_apply, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
