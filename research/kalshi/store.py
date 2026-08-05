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
import subprocess
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
    """A markdown table row is ONE LINE. A cell carrying a literal newline silently splits the row
    into fragments that no longer parse as a decision - the render still compares equal to the file
    it just wrote, so `check` passes while the document is corrupt, and only the extract round-trip
    catches it. That happened TWICE in one session (D35, then D36), which is the definition of a
    thing that needs a guard rather than more care. Refuse at write time and name the cell."""
    for e in store["entries"]:
        for k in ("id", "session", "decision", "status", "enforced_by"):
            if "\n" in str(e.get(k, "")):
                raise SystemExit(
                    "%s.%s contains a literal newline. A table row is one line - a newline splits it "
                    "into fragments that stop parsing as a decision, and the render/compare gate "
                    "cannot see it because both sides carry the same break. Write the cell as one "
                    "continuous line; mark paragraphs with **BOLD LEADS** the way every other entry "
                    "does." % (e.get("id", "?"), k))
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
DOCS_JSON = os.path.join(HERE, "store", "documents.json")
KALSHI_INDEX = os.path.join(ROOT, "KALSHI_TRADING.md")
PLANT_MAP = os.path.join(ROOT, "PLANT_MAP.md")
INVENTORY_BEGIN = "<!-- BEGIN GENERATED FILE INVENTORY - store.py docs --write -->"
INVENTORY_END = "<!-- END GENERATED FILE INVENTORY -->"


def load_docs():
    with open(DOCS_JSON, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def _tracked_py():
    """Every tracked research/kalshi/*.py, with the first sentence of its docstring.

    Derived from git, never from a hand-kept list - a hand-kept list is the thing that failed."""
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "research/kalshi/*.py"],
                         capture_output=True, text=True).stdout.split()
    inv = []
    for rel in sorted(out):
        summary = ""
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                head = f.read(4000)
            # The FIRST NON-EMPTY line inside the docstring. Not the first line: every file here
            # opens `"""\nname.py - summary`, so a naive match captures the empty opener and the
            # summary reads as absent. That is what the 62%-coverage selftest failure caught -
            # the extractor was broken, not the files, and lowering the threshold would have
            # buried a real defect under a passing test.
            m = re.search(r'"""\s*(\S.*?)\n', head)
            if m:
                summary = " ".join(m.group(1).split()).replace("—", "-")
                base = os.path.basename(rel)
                if summary.lower().startswith(base.lower()):
                    summary = summary[len(base):].lstrip(" -:")
        except OSError:
            pass
        inv.append((rel, summary))
    return inv


def _sop_named_py():
    """The .py files the SOP itself names. Non-circular: derived from another document, so adding a
    tool to the run automatically puts it on PLANT_MAP's hook."""
    with open(SOP_MD, encoding="utf-8") as f:
        return sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*\.py)\b", f.read())))


def render_inventory():
    """The COMPLETENESS half of the file index. The curated sections above it carry the judgment -
    which file is current, which superseded - and this carries the guarantee that nothing is
    missing. One store, generated views: the part a human must decide stays hand-written, the part
    a machine can compute is computed."""
    inv = _tracked_py()
    out = [INVENTORY_BEGIN, "",
           "## COMPLETE FILE INVENTORY (generated - do not hand-edit)",
           "",
           "Every tracked `research/kalshi/*.py`, from git, with the opening line of its docstring.",
           "Regenerate with `python research/kalshi/store.py docs --write`. The curated sections",
           "above carry the judgment (current vs superseded); this carries the completeness, so a",
           "new tool cannot go unlisted. **%d files.**" % len(inv), ""]
    for rel, summary in inv:
        base = os.path.basename(rel)
        out.append("- `%s` — %s" % (base, summary if summary else "(no docstring summary)"))
    out += ["", INVENTORY_END]
    return "\n".join(out) + "\n"


def _index_gate(path, needed, label):
    """A doc must NAME every member of a computed set. Returns the missing ones."""
    if not os.path.exists(path):
        return needed
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return [n for n in needed if n not in text]


def docs_problems():
    """The content gates. mtime is not staleness - a document edited today can still be silently
    missing what it exists to list, which is exactly what was measured the day this was built."""
    probs = []
    missing_py = _index_gate(KALSHI_INDEX,
                             [os.path.basename(r) for r, _ in _tracked_py()], "index_py")
    if missing_py:
        probs.append(("KALSHI_TRADING.md", "index_py",
                      "%d tracked research/kalshi/*.py not named: %s"
                      % (len(missing_py), ", ".join(missing_py[:6])
                         + (" ..." if len(missing_py) > 6 else ""))))
    missing_sop = _index_gate(PLANT_MAP, _sop_named_py(), "index_sop_py")
    if missing_sop:
        probs.append(("PLANT_MAP.md", "index_sop_py",
                      "%d tools the SOP names are absent from the plant map: %s"
                      % (len(missing_sop), ", ".join(missing_sop[:6])
                         + (" ..." if len(missing_sop) > 6 else ""))))
    return probs


OPEN_ITEMS_MD = os.path.join(ROOT, "OPEN_ITEMS.md")


def render_open_items():
    """OPEN_ITEMS.json is the system of record and JSON is not readable. Greg, S112: "put those in
    the open doc please." So the registry gets a RENDER - the same architecture as DECISIONS.md, and
    for the same reason: the store carries the truth, the document carries the readability, and the
    document is never the thing you edit."""
    with open(OPEN_ITEMS, encoding="utf-8") as f:
        reg = json.load(f, object_pairs_hook=OrderedDict)
    items = reg["items"]
    live = [i for i in items if i.get("status") in ("OPEN", "IN_PROGRESS")]
    done = [i for i in items if i.get("status") == "DONE"]
    order = {"XS": 0, "S": 1, "M": 2, "L": 3, None: 4}
    L = ["# OPEN ITEMS - the tracked work registry", "",
         "GENERATED from `research/kalshi/OPEN_ITEMS.json` by `python research/kalshi/store.py docs",
         "--write`. **Do not edit this file** - edit the store. Born under D30: a finding with no",
         "home does not exist.", "",
         "| | count |", "|---|---|",
         "| open | %d |" % len([i for i in live if i.get("status") == "OPEN"]),
         "| in progress | %d |" % len([i for i in live if i.get("status") == "IN_PROGRESS"]),
         "| done | %d |" % len(done), "",
         "By size: " + ", ".join("**%s** %d" % (s, sum(1 for i in live if i.get("size") == s))
                                 for s in ("XS", "S", "M", "L")), "", "---", "",
         "## OPEN AND IN PROGRESS", "",
         "| id | size | status | raised | title | blocked by |", "|---|---|---|---|---|---|"]
    for i in sorted(live, key=lambda x: (order.get(x.get("size"), 4), x["id"])):
        L.append("| **%s** | %s | %s | %s | %s | %s |"
                 % (i["id"], i.get("size") or "?", i.get("status"),
                    (i.get("first_raised") or "?")[:28], i["title"].replace("|", "\\|"),
                    (i.get("blocked_by") or "-").replace("|", "\\|")))
    L += ["", "## DONE", "", "| id | size | title |", "|---|---|---|"]
    for i in sorted(done, key=lambda x: x["id"]):
        L.append("| %s | %s | %s |" % (i["id"], i.get("size") or "?",
                                       i["title"].replace("|", "\\|")))
    L += ["", "---", "", "## THE FULL ENTRY FOR EVERY OPEN ITEM", "",
          "Each item's `why` verbatim - the reasoning, not a summary of it.", ""]
    for i in sorted(live, key=lambda x: (order.get(x.get("size"), 4), x["id"])):
        L += ["### %s - %s" % (i["id"], i["title"]), "",
              "*size %s | %s | raised %s%s*"
              % (i.get("size") or "?", i.get("status"), i.get("first_raised") or "?",
                 " | BLOCKED BY: %s" % i["blocked_by"] if i.get("blocked_by") else ""), ""]
        if i.get("source"):
            L += ["**Source:** %s" % i["source"], ""]
        if i.get("delegated_prior"):
            L += ["**Already delegated:** %s" % i["delegated_prior"], ""]
        L += [i.get("why", "(no detail recorded)"), "", "---", ""]
    return "\n".join(L) + "\n"


def cmd_docs(a):
    """THE DOCUMENT REGISTRY (Greg, S112: 'so one doesn't get forgotten about')."""
    store = load_docs()
    if a.write:
        with open(KALSHI_INDEX, encoding="utf-8") as f:
            text = f.read()
        block = render_inventory()
        if INVENTORY_BEGIN in text:
            i, j = text.index(INVENTORY_BEGIN), text.index(INVENTORY_END) + len(INVENTORY_END)
            text = text[:i] + block.rstrip("\n") + text[j:]
        else:
            text = text.rstrip("\n") + "\n\n" + block
        with open(KALSHI_INDEX, "w", encoding="utf-8") as f:
            f.write(text)
        print("regenerated the file inventory in KALSHI_TRADING.md")
        with open(OPEN_ITEMS_MD, "w", encoding="utf-8") as f:
            f.write(render_open_items())
        print("regenerated OPEN_ITEMS.md from the registry")
    by_class = OrderedDict()
    for d in store["documents"]:
        by_class.setdefault(d["class"], []).append(d)
    print("THE DOCUMENT REGISTRY - %d entries\n" % len(store["documents"]))
    for cls, docs in by_class.items():
        print("%s  (%s)" % (cls, store["classes"][cls]))
        for d in docs:
            print("   %-46s gate=%s" % (d["path"], d.get("gate") or "-"))
        print()
    print("CLOSE-OUT TRIO (excluded from mid-session sweeps by design): %s"
          % ", ".join(store["close_out_trio"]["docs"]))
    probs = docs_problems()
    print()
    if not probs:
        print("PASS  docs        every content gate satisfied")
        return 0
    for path, gate, msg in probs:
        print("FAIL  %-14s [%s] %s" % (path, gate, msg))
    print("\n%d document gate(s) failed. mtime is not staleness - CONTENT is." % len(probs))
    return 1


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
    # THE DOCUMENT CONTENT GATES (S112). A render gate catches a generated document drifting from
    # its store; it cannot catch a HAND-KEPT index that quietly stopped listing things. Measured the
    # day this was added: 55 of 151 tracked research/kalshi/*.py were absent from KALSHI_TRADING.md,
    # and PLANT_MAP.md had been edited that same session while naming none of the SOP's own tools.
    for path, gate, msg in docs_problems():
        bad += 1
        print("FAIL  %-12s [%s] %s" % ("docs", gate, path + ": " + msg))
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

    # the newline guard must FIRE - this defect landed twice before it was guarded
    st_nl = json.loads(json.dumps(st))
    st_nl["entries"][0]["decision"] = "line one\nline two"
    try:
        render_decisions(st_nl)
        check("render REFUSES a cell containing a literal newline", False)
    except SystemExit:
        check("render REFUSES a cell containing a literal newline", True)
    check("the clean store still renders", isinstance(render_decisions(st), str))

    # --- the DOCUMENT registry gates (S112) ---
    docs = load_docs()
    om = render_open_items()
    check("OPEN_ITEMS.md render carries every open item",
          all(i["id"] in om for i in json.load(open(OPEN_ITEMS, encoding="utf-8"))["items"]
              if i.get("status") in ("OPEN", "IN_PROGRESS")))
    check("the open-items render carries each item's reasoning verbatim, not a summary",
          "THE FULL ENTRY FOR EVERY OPEN ITEM" in om)
    check("document registry loads and classifies every entry",
          all(d["class"] in docs["classes"] for d in docs["documents"]))
    check("the close-out trio is declared and excluded from sweeps",
          len(docs["close_out_trio"]["docs"]) == 3)
    inv = _tracked_py()
    check("file inventory is derived from git, not a hand list", len(inv) > 100)
    check("inventory carries a docstring summary for most files",
          sum(1 for _, sm in inv if sm) > 0.8 * len(inv))
    # the gate must FIRE on a document that stopped listing what it exists to list
    with tempfile.TemporaryDirectory() as td:
        empty = os.path.join(td, "EMPTY.md")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("# an index that lists nothing\n")
        miss = _index_gate(empty, [b for b, _ in [(os.path.basename(r), s) for r, s in inv]], "x")
        check("index gate FIRES on a document naming none of its members", len(miss) == len(inv))
        full = os.path.join(td, "FULL.md")
        with open(full, "w", encoding="utf-8") as f:
            f.write("\n".join(os.path.basename(r) for r, _ in inv))
        check("index gate PASSES when every member is named",
              _index_gate(full, [os.path.basename(r) for r, _ in inv], "x") == [])
    check("PLANT_MAP's needed set is derived from the SOP, not hand-kept", len(_sop_named_py()) > 5)

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
    p = sub.add_parser("docs"); p.add_argument("--write", action="store_true",
                                               help="regenerate the file inventory in KALSHI_TRADING.md")
    a = ap.parse_args()
    return {"extract": cmd_extract, "render": cmd_render,
            "check": cmd_check, "selftest": cmd_selftest,
            "worklist": cmd_worklist, "docs": cmd_docs}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
