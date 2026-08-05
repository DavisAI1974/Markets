#!/usr/bin/env python3
"""
store.py - ONE STORE, GENERATED VIEWS. (Registry A-7.)

THE DISEASE, in Greg's words (S112): "get this and the sop's and all that under one roof so we can
stop having things falling through the cracks" - and, on the ledger specifically: "Definitely
generated. We want the plant to be fully automated since we won't be there to supervise."

The architecture doc s8 names it as one disease in three costumes: A DOCUMENT THAT DESCRIBES WHAT
SHOULD HAPPEN, SITTING APART FROM THE MACHINERY THAT MAKES IT HAPPEN. Four measured instances:
  - SOP v1.6 pinned the cum convention and it reached the agents only because someone hand-copied
    it into the BLD-1 template.
  - D25, an explicit instruction about the ORDER a specialist should reason in, HAS NEVER BEEN READ
    BY A SPECIALIST, because DECISIONS.md is served to nobody.
  - The S110 memo's two FIX items never became decision lines and were therefore never done.
  - RUN_SOP.md carries 13 slot placeholders across 36 occurrences, every one filled BY HAND, which
    is exactly how NC-1 happened: a directive asserted "first post-roll session" from prose while
    flow_calendar said bcom_roll_day_n 5. A specialist caught it.
And a fifth, from this session: the committed DROP_IN_S112 listed two ALREADY-DONE items as live
instructions, because the work list was restated in prose instead of generated from the registry.

THE PATTERN IS ALREADY PROVEN HERE THREE TIMES, which is why this is a generalisation and not a
bet: brain_audit.py fills prompt slots by lookup from the brain (nobody types a play id);
standdown_ledger.py audit-prompt does the same from the ledger; chatgpt_brief_split.py generates
six hand-offs from one brief. Each replaced a hand-copied artifact.

THE SAFETY DISCIPLINE, and it is the same one brain_schema used to earn the right to migrate the
brain: EXTRACT to a store, RENDER back, and PROVE the render reproduces the committed file before
anything becomes the source of truth. A generator that cannot reproduce today's file is a generator
that would silently rewrite the record. `check` is that proof and it is what CI runs.

WHAT IS IN SCOPE HERE: the plant documents - DECISIONS.md first. `knowledge/ng_brain.json` and
`OPEN_ITEMS.json` are ALREADY stores and are left alone. The gold-vaulted agents/*.md reasoning
files are deliberately OUT of scope: a change there is a versioned vault event, not an edit.

USAGE
    python store.py extract decisions        # DECISIONS.md -> store/decisions.json
    python store.py render decisions         # store/decisions.json -> DECISIONS.md (stdout)
    python store.py check                    # do the committed renders match the store? CI gate
    python store.py check --write            # regenerate any render that has drifted
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(HERE, "store")
DECISIONS_MD = os.path.join(ROOT, "DECISIONS.md")
DECISIONS_JSON = os.path.join(STORE, "decisions.json")

ROW = re.compile(r"^\|\s*(D\d+(?:\.\d+)?|NC-\d+)\s*\|")


def _cells(line):
    """Split a decision row into its five columns: id | session | decision | status | enforced_by.

    Parsed BY POSITION FROM BOTH ENDS, never by naive split, because three decisions carry literal
    pipes inside their text: D21 and D28 escape theirs (`sha256(group\\|date\\|owner\\|number)`,
    `\\|dip_imb_level\\| >= 0.15`) and NC-2 does NOT - it contains a bare `git ls-files | grep
    brain-play-audit`. A naive split gives that row 6 cells, D28 7 and D21 8. The first version
    refused to guess and stopped the line, which is what it should do; this is the fix rather than
    a loosened check.

    NOTE, and it is a real if cosmetic defect the extraction surfaced: NC-2's unescaped pipe means
    that row currently renders as extra columns in any markdown viewer. The store preserves the
    text byte-for-byte so the round-trip still proves out; escaping it is a content edit and
    therefore a store edit, not something a parser should do silently."""
    # Split on UNESCAPED pipes only. Splitting on every pipe put D21's boundary in the wrong place
    # entirely: its escaped pipes sit in the ENFORCED_BY column, not the decision, so counting three
    # cells in from the right landed mid-sha256 and the round-trip came back with
    # "sha256(group\|date\ | owner\ | number)". Escaping is what the column separator is escaped
    # FROM, so it is the only correct thing to split on.
    parts = re.split(r"(?<!\\)\|", line)
    if len(parts) < 7:
        return [c.strip() for c in parts[1:-1]]
    # a genuinely unescaped pipe inside the text (NC-2's `git ls-files | grep ...`) lands in the
    # decision column, so the middle is rejoined rather than truncated
    return [parts[1].strip(), parts[2].strip(),
            "|".join(parts[3:-3]).strip(),
            parts[-3].strip(), parts[-2].strip()]


def extract_decisions():
    with open(DECISIONS_MD, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    hdr = next(i for i, l in enumerate(lines) if l.startswith("| # |"))
    preamble = "\n".join(lines[:hdr]).rstrip("\n")
    header = lines[hdr]
    sep = lines[hdr + 1]
    entries, trailing = [], []
    for i, l in enumerate(lines[hdr + 2:], start=hdr + 2):
        if ROW.match(l):
            c = _cells(l)
            if len(c) != 5:
                raise SystemExit("row %d does not have 5 cells (%d) - refusing to guess" % (i, len(c)))
            entries.append(OrderedDict([
                ("id", c[0]), ("session", c[1]), ("decision", c[2]),
                ("status", c[3]), ("enforced_by", c[4])]))
        elif l.strip():
            trailing.append(l)
    return OrderedDict([
        ("note", "THE DECISIONS STORE. Source of truth for DECISIONS.md, which is now a RENDER "
                 "(A-7, Greg S112: 'Definitely generated'). Append a decision HERE, then run "
                 "`store.py check --write`. Never edit DECISIONS.md directly - it is regenerated "
                 "and your edit would be silently overwritten, which is the exact drift this store "
                 "exists to end."),
        ("renders_to", "DECISIONS.md"),
        ("preamble", preamble),
        ("table_header", header),
        ("table_separator", sep),
        ("trailing", trailing),
        ("entries", entries)])


def render_decisions(store):
    out = [store["preamble"], "", store["table_header"], store["table_separator"]]
    for e in store["entries"]:
        out.append("| %s | %s | %s | %s | %s |"
                   % (e["id"], e["session"], e["decision"], e["status"], e["enforced_by"]))
    out.extend(store.get("trailing") or [])
    return "\n".join(out) + "\n"




SOP_MD = os.path.join(HERE, "agents", "RUN_SOP.md")
SOP_JSON = os.path.join(STORE, "sop_templates.json")
APPENDIX_HEAD = "## APPENDIX — VERBATIM SPAWN TEMPLATES"


def extract_sop():
    """The spawn templates, verbatim, out of RUN_SOP.md's appendix.

    SCOPE, deliberately: only the APPENDIX becomes a render, not the whole SOP. The appendix is
    39% of the file and is the only part a MACHINE consumes - spawn.py fills these templates and
    nothing else. The prose above it (change control, the version log, the step list) is written
    for people, is genuinely append-only history, and turning it into a generated view would buy
    nothing and risk rewriting the record. One store per thing that is actually consumed."""
    with open(SOP_MD, encoding="utf-8") as f:
        text = f.read()
    i = text.index(APPENDIX_HEAD)
    head, appendix = text[:i], text[i:]
    blocks = re.findall(r"^### (\S+) — ([^\n]*)\n```\n(.*?)\n```", appendix, re.M | re.S)
    if not blocks:
        raise SystemExit("no templates found in the appendix - refusing to write an empty store")
    return OrderedDict([
        ("note", "THE SPAWN TEMPLATE STORE. Extracted VERBATIM from RUN_SOP.md's appendix, which "
                 "stays as the human-readable render. spawn.py fills these BY LOOKUP - nobody "
                 "types a slot value. Edit a template HERE and regenerate; editing the SOP "
                 "directly makes the two diverge, which is the A-7 disease this store exists to "
                 "end."),
        ("renders_to", "research/kalshi/agents/RUN_SOP.md (appendix section only)"),
        ("appendix_header", APPENDIX_HEAD),
        ("preamble_sha_note", "the SOP prose above the appendix is NOT generated - see extract_sop"),
        ("templates", [OrderedDict([
            ("name", n), ("title", t), ("body", b),
            ("slots", sorted(set(re.findall(r"\{([A-Za-z_0-9]+)\}", b))))]) for n, t, b in blocks])])


def render_sop(store):
    """Rebuild the appendix section from the store, byte-for-byte."""
    out = [store["appendix_header"], ""]
    for i, t in enumerate(store["templates"]):
        if i:
            out.append("")          # the committed appendix separates blocks with a blank line
        out.append("### %s — %s" % (t["name"], t["title"]))
        out.append("```")
        out.append(t["body"])
        out.append("```")
    return "\n".join(out) + "\n"


def sop_target_read():
    """The committed appendix, for comparison."""
    with open(SOP_MD, encoding="utf-8") as f:
        text = f.read()
    return text[text.index(APPENDIX_HEAD):]


def sop_target_write(new_appendix):
    with open(SOP_MD, encoding="utf-8") as f:
        text = f.read()
    i = text.index(APPENDIX_HEAD)
    with open(SOP_MD, "w", encoding="utf-8") as f:
        f.write(text[:i] + new_appendix)

RENDERS = {
    "decisions": dict(store=DECISIONS_JSON, target=DECISIONS_MD,
                      extract=extract_decisions, render=render_decisions),
    "sop": dict(store=SOP_JSON, target=SOP_MD, extract=extract_sop, render=render_sop,
                read=sop_target_read, write=sop_target_write),
}



OPEN_ITEMS = os.path.join(HERE, "OPEN_ITEMS.json")


def work_list(limit=12):
    """GENERATE the next session's work list from the registry. (Registry A-9.)

    THE INSTANCE THAT CREATED THIS: the committed DROP_IN_S112 listed `brain_schema.py sections
    --write` and the condition_audit false-claim fix as work to do when BOTH WERE ALREADY DONE.
    The drop-in restated the work in prose instead of pointing at the registry, so a completed item
    could still appear as a live instruction. Generated from OPEN_ITEMS.json, only OPEN and
    IN_PROGRESS entries can ever appear - a DONE item becoming a live instruction is structurally
    impossible rather than something a careful reader has to catch.

    ORDER: irreversible first (work whose value is permanently lost by waiting), then XS, then
    everything else by size. `blocked_by` items sort last and say what blocks them."""
    with open(OPEN_ITEMS, encoding="utf-8") as f:
        items = json.load(f)["items"]
    live = [i for i in items if i.get("status") in ("OPEN", "IN_PROGRESS")]
    IRREVERSIBLE = {"G-11"}          # accrual that cannot be backfilled - every week waited is lost
    order = {"XS": 0, "S": 1, "M": 2, "L": 3}

    # RE-RAISED SORTS SECOND, ABOVE SIZE. Greg, S112: "It scares me that things we talk about and
    # decide on don't get implemented. We actually just had to revisit the nuke discussion for the
    # 2nd time a few sessions ago and we still haven't addressed it." He is right, and sorting by
    # size buried it: the nuclear schedule is an S, so a generated list ordered on effort alone put
    # it below five XS items. THE COST OF A RE-RAISED ITEM IS NOT THE WORK, IT IS THE REPETITION -
    # so having been asked for twice is itself a priority signal and now outranks how cheap the
    # item is. Only IRREVERSIBLE (permanent data loss) sorts above it.
    def rank(i):
        if i["id"] in IRREVERSIBLE:
            return 0
        if i.get("reraised"):
            return 1
        return 2

    def key(i):
        return (rank(i),
                1 if i.get("blocked_by") else 0,
                order.get(i.get("size"), 9), i["id"])
    out = []
    for i in sorted(live, key=key)[:limit]:
        tag = ""
        if i["id"] in IRREVERSIBLE:
            tag = "  [IRREVERSIBLE - value is permanently lost by waiting]"
        elif i.get("reraised"):
            tag = "  [RE-RAISED - Greg has had to ask for this %s]" % i.get("reraised")
        elif i.get("blocked_by"):
            tag = "  [BLOCKED: %s]" % i["blocked_by"]
        out.append("- **%s** (%s) %s%s" % (i["id"], i.get("size", "?"), i["title"], tag))
    return "\n".join(out), len(live)


def cmd_worklist(a):
    body, n = work_list(a.limit)
    print("GENERATED FROM research/kalshi/OPEN_ITEMS.json - %d live items, showing %d.\n"
          "Only OPEN and IN_PROGRESS can appear here, so a DONE item cannot be a live "
          "instruction.\n" % (n, min(a.limit, n)))
    print(body)
    return 0


def cmd_extract(a):
    name = a.what
    spec = RENDERS[name]
    st = spec["extract"]()
    os.makedirs(STORE, exist_ok=True)
    with open(spec["store"], "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)
    # PROVE IT ROUND-TRIPS before anyone trusts it
    original = spec["read"]() if "read" in spec else open(spec["target"], encoding="utf-8").read()
    rendered = spec["render"](st)
    ok = rendered == original
    n_items = len(st.get("entries") or st.get("templates") or [])
    print("extracted %d entries -> %s" % (n_items, os.path.relpath(spec["store"], ROOT)))
    print("round-trip reproduces %s: %s" % (os.path.relpath(spec["target"], ROOT),
                                            "YES, byte-identical" if ok else "NO"))
    if not ok:
        a_, b_ = original.split("\n"), rendered.split("\n")
        for i in range(max(len(a_), len(b_))):
            x = a_[i] if i < len(a_) else "<missing>"
            y = b_[i] if i < len(b_) else "<missing>"
            if x != y:
                print("  first difference at line %d:" % (i + 1))
                print("    committed: %s" % x[:160])
                print("    rendered : %s" % y[:160])
                break
        return 1
    return 0


def cmd_render(a):
    spec = RENDERS[a.what]
    with open(spec["store"], encoding="utf-8") as f:
        st = json.load(f, object_pairs_hook=OrderedDict)
    sys.stdout.write(spec["render"](st))
    return 0


def cmd_check(a):
    """THE CI GATE. Every committed render must equal what its store currently generates. A render
    that has drifted from its store is a document describing what should happen while the machinery
    does something else - the disease itself."""
    bad = 0
    for name, spec in RENDERS.items():
        if not os.path.exists(spec["store"]):
            print("SKIP  %-12s no store yet (%s)" % (name, os.path.relpath(spec["store"], ROOT)))
            continue
        with open(spec["store"], encoding="utf-8") as f:
            st = json.load(f, object_pairs_hook=OrderedDict)
        rendered = spec["render"](st)
        committed = (spec["read"]() if "read" in spec
                     else open(spec["target"], encoding="utf-8").read())
        if rendered == committed:
            print("PASS  %-12s %s matches its store (%d entries)"
                  % (name, os.path.relpath(spec["target"], ROOT),
                     len(st.get("entries") or st.get("templates") or [])))
        elif a.write:
            if "write" in spec:
                spec["write"](rendered)
            else:
                with open(spec["target"], "w", encoding="utf-8") as f:
                    f.write(rendered)
            print("REGEN %-12s %s regenerated from its store"
                  % (name, os.path.relpath(spec["target"], ROOT)))
        else:
            bad += 1
            print("FAIL  %-12s %s has DRIFTED from its store - run check --write"
                  % (name, os.path.relpath(spec["target"], ROOT)))
    if bad:
        print("\n%d render(s) drifted. The render is generated; edit the STORE, not the document."
              % bad)
    return 1 if bad else 0


def cmd_selftest(a):
    """The gate must FAIL on drift and PASS on a clean tree (D11)."""
    import tempfile, shutil
    res = []

    def check(name, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", name))

    st = extract_decisions()
    check("extract finds every decision row", len(st["entries"]) >= 30)
    check("round-trip is byte-identical to the committed file",
          render_decisions(st) == open(DECISIONS_MD, encoding="utf-8").read())

    # a store edit must change the render
    st2 = json.loads(json.dumps(st))
    st2["entries"][0]["status"] = "RETIRED"
    check("a store edit changes the render", render_decisions(st2) != render_decisions(st))

    # the gate must FAIL when the document is edited behind the store's back
    with tempfile.TemporaryDirectory() as td:
        tgt = os.path.join(td, "D.md")
        stp = os.path.join(td, "d.json")
        with open(tgt, "w", encoding="utf-8") as f:
            f.write(render_decisions(st) + "\nAN EDIT MADE DIRECTLY IN THE DOCUMENT\n")
        with open(stp, "w", encoding="utf-8") as f:
            json.dump(st, f)
        saved = dict(RENDERS["decisions"])
        RENDERS["decisions"] = dict(saved, store=stp, target=tgt)
        class _A: write = False
        rc = cmd_check(_A())
        RENDERS["decisions"] = saved
        check("gate FAILS when the document is edited behind the store", rc == 1)

    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract"); p.add_argument("what", choices=list(RENDERS))
    p = sub.add_parser("render"); p.add_argument("what", choices=list(RENDERS))
    p = sub.add_parser("check"); p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    p = sub.add_parser("worklist"); p.add_argument("--limit", type=int, default=12)
    a = ap.parse_args()
    return {"extract": cmd_extract, "render": cmd_render,
            "check": cmd_check, "selftest": cmd_selftest,
            "worklist": cmd_worklist}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
