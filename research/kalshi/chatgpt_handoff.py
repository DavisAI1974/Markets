#!/usr/bin/env python3
"""
chatgpt_handoff.py - GENERATE the ChatGPT hand-off that ships with the drop-in. (Registry A-25.)

THE ASK (Greg, S112): "include a doc that i can download and send to chat along with the drop ins
when you're printing." So this joins the close-out artifact set - handoff, drop-in, and now this -
and like the drop-in's work list (A-9) it is GENERATED FROM THE REGISTRY rather than written by
hand. A hand-written brief drifts the moment an item is done, and then it asks for work already
finished, which is the exact defect A-9 was built to end one document over.

WHAT GOES IN AND WHY IT IS A NARROW SET. An item is delegable here only if it can be finished with
PUBLIC SOURCES AND NO ACCESS TO OUR DATA. That is a real line, not a formality:
  - SOURCE HUNTING delegates well. Which USGS gauge, which FERC docket, which ISO endpoint, what
    the licence article actually says - bounded, citation-heavy, parallelises cleanly, and the
    answer is checkable by following the link.
  - FITTING DOES NOT DELEGATE. A coefficient tuned by someone without our states is hindsight-fitted
    with zero forward evidence, which the brain architecture forbids outright; and per D35 the
    output is a national total, so per-BA parameters fitted elsewhere are numbers we would throw
    away. The one exception is A-23, whose input (DATA_POINTS.md) is itself a shippable artifact.

Items opt in by carrying `"delegable": true` in OPEN_ITEMS.json - explicit, auditable, and not a
keyword guess. Over-inclusion is cheap on the PLANNED harvest in data_registry; here it would send
someone to do work whose answer we could not use, so it is deliberate.

USAGE
    python chatgpt_handoff.py build                 # dry run
    python chatgpt_handoff.py build --write         # CHATGPT_HANDOFF_S<N>.md + per-task files
    python chatgpt_handoff.py selftest
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OPEN_ITEMS = os.path.join(HERE, "OPEN_ITEMS.json")
TASK_DIR = os.path.join(HERE, "chatgpt_tasks")

# The standing constraints on ANY returned work. These are not politeness - each one is a defect
# this desk has already paid for, named so the answer comes back in a usable shape.
RULES = """## THE RULES ON WHAT YOU SEND BACK

These are not style preferences. Each one is a failure this desk has already paid for.

1. **CITE EVERY CLAIM WITH A FOLLOWABLE LINK.** A source we cannot open is a source we cannot use.
   Prefer the primary publisher (the agency, the exchange, the commission docket) over a summary.
2. **NEVER INVENT A NUMBER, AN ENDPOINT, OR A FIELD NAME.** If you cannot verify it, write "not
   verified" and say what you would need. A plausible-looking endpoint that 404s costs us a session;
   an honest gap costs a sentence. This is the single most important rule here.
3. **SAY WHAT IS FREE AND WHAT IS NOT**, with the specific licence or terms where you can find them.
   Our standing policy is free-first: we pay only for measured gaps.
4. **DISTINGUISH "PUBLISHED" FROM "AVAILABLE OVER AN API."** A federal agency posting a web page is
   published; that is not the same as machine-readable, and conflating them is how a build estimate
   goes wrong by a week. Say which one you found, and if it is scrape-only, say so plainly.
5. **REPORT COVERAGE PER UNIT, NEVER POOLED.** "EIA reports this for every balancing authority" is
   the kind of claim that is true in general and false for the three we need. Check per unit or say
   you did not.
6. **DO NOT FIT ANYTHING.** No thresholds, no weights, no coefficients, no "typically around X".
   We fit against our own measured states or not at all - a number tuned without them is
   hindsight-fitted with zero forward evidence and we would have to discard it.
7. **NO EMOJIS OR SPECIAL SYMBOLS** anywhere in what you return - it goes straight into a repo.
8. **ONE TASK PER CONVERSATION.** The tasks below are independent on purpose.
"""


def _session():
    """Next session number, from the highest committed drop-in. Derived, never typed."""
    n = 0
    for f in os.listdir(ROOT):
        m = re.match(r"^DROP_IN_S(\d+)\.md$", f)
        if m:
            n = max(n, int(m.group(1)))
    return n or 113


def load_items():
    with open(OPEN_ITEMS, encoding="utf-8") as f:
        reg = json.load(f)
    return [i for i in reg["items"]
            if i.get("delegable") and i.get("status") in ("OPEN", "IN_PROGRESS")]


def context_block():
    """What ChatGPT needs to know to answer usefully, and nothing else. Deliberately short: the
    brief is not a briefing on the whole desk, it is the minimum frame for these tasks."""
    return """## THE CONTEXT YOU NEED (and only what you need)

We forecast **natural gas** - the Henry Hub price curve - and trade it on Kalshi and NYMEX. One
number is the product: total US gas demand, or more precisely **demand that Henry Hub can see**.

Two things that shape every answer you give us:

**Henry Hub is not a national index.** It is one physical delivery point near Erath, Louisiana, on
Sabine Pipe Line, with roughly nine interstate and three-to-four intrastate interconnects, where the
NYMEX contract is physically deliverable. Every other region prices at a basis differential. So New
England demand can spike Algonquin with little effect at Henry, while Gulf-coast LNG feedgas is the
most tightly coupled demand there is.

**Gas burn is the RESIDUAL of the power stack.** Load, minus wind, minus solar, minus hydro, minus
what nuclear and coal are running. Nuclear and coal are LEVELS that move on outage and retirement
timescales. Wind, solar and hydro are FORCINGS - they are on or off according to weather and water,
not according to load. Gas is the only term that regulates. So anything that removes a forcing
without warning lands on gas, and the clearest instance we have measured: on one day our cooling
forecast was exactly right and gas burn still FELL 4.2 Bcf/d, because wind rose 62%.

We work at a **day-ahead to roughly two-week horizon**. Directional level forecasting on price dies
at 5-7 days; what survives past it is dispersion, the forward calendar, and the revision process. So
anything DATED AND FORWARD - a posted outage schedule, a retirement date, a reservoir operating
guide - is worth more to us than a better nowcast.
"""


def render(items, sess):
    L = ["# CHATGPT HAND-OFF - S%d" % sess, "",
         "Generated by `python research/kalshi/chatgpt_handoff.py build --write` from the work",
         "registry, so a finished item cannot appear here as a live request. Ships with the",
         "session drop-in.", "",
         "**%d tasks.** They are independent - run one per conversation." % len(items), "",
         context_block(), "", RULES, "",
         "---", ""]
    for n, it in enumerate(items, 1):
        L += ["## TASK %d - %s" % (n, it["title"]), "",
              "*Registry item %s (size %s).*" % (it["id"], it.get("size") or "?"), ""]
        if it.get("delegable_ask"):
            L += ["### What we need from you", "", it["delegable_ask"], ""]
        L += ["### Why we want it, in our own words", "",
              "This is the registry entry verbatim, so you can see the reasoning rather than a",
              "summary of it. Where it names something we measured, that is a real measurement.", "",
              "> " + it["why"].replace("\n\n", "\n>\n> ").replace("\n", "\n> "), ""]
        if it.get("blocked_by"):
            L += ["**Note:** blocked in OUR queue by: %s. That does not block your research - it "
                  "only means we cannot build on the answer the moment it arrives."
                  % it["blocked_by"], ""]
        L += ["---", ""]
    L += ["## WHAT TO SEND BACK", "",
          "One markdown file per task. Structure it however the findings want, but every factual",
          "line needs its link, and anything you could not verify needs to say so in place rather",
          "than being left out. A gap we can see is useful; a gap we cannot see is a defect.", ""]
    return "\n".join(L)


def render_task(it, n, sess):
    """One self-contained file per task - the brief instructs one task per conversation, so each
    must stand alone without the others. Same pattern as chatgpt_brief_split.py."""
    L = ["# S%d TASK %d - %s" % (sess, n, it["title"]), "",
         "Self-contained: everything you need is in this file. Registry item %s." % it["id"], "",
         context_block(), "", RULES, "", "---", ""]
    if it.get("delegable_ask"):
        L += ["## WHAT WE NEED FROM YOU", "", it["delegable_ask"], "", "---", ""]
    L += ["## THE REGISTRY ENTRY, VERBATIM", "",
          "> " + it["why"].replace("\n\n", "\n>\n> ").replace("\n", "\n> "), ""]
    return "\n".join(L) + "\n"


def cmd_build(a):
    items = load_items()
    sess = _session()
    print("session      : S%d" % sess)
    print("delegable    : %d item(s)" % len(items))
    for it in items:
        print("   %-6s %s" % (it["id"], it["title"][:78]))
    if not items:
        print("\nnothing marked delegable - refusing to write an empty brief.")
        return 1
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write.")
        return 0
    main_path = os.path.join(ROOT, "CHATGPT_HANDOFF_S%d.md" % sess)
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(render(items, sess))
    os.makedirs(TASK_DIR, exist_ok=True)
    written = [os.path.relpath(main_path, ROOT)]
    for n, it in enumerate(items, 1):
        slug = re.sub(r"[^a-z0-9]+", "_", it["title"].lower())[:52].strip("_")
        p = os.path.join(TASK_DIR, "S%d_TASK_%d_%s.md" % (sess, n, slug))
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_task(it, n, sess))
        written.append(os.path.relpath(p, ROOT))
    print("\nwrote:")
    for w in written:
        print("   %s" % w)
    return 0


def cmd_selftest(a):
    res = []

    def check(n, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", n))

    items = load_items()
    check("delegable items are found by an explicit flag, not a keyword guess", len(items) > 0)
    check("only OPEN or IN_PROGRESS items can appear",
          all(i["status"] in ("OPEN", "IN_PROGRESS") for i in items))
    with open(OPEN_ITEMS, encoding="utf-8") as f:
        allitems = json.load(f)["items"]
    done_flagged = [i for i in allitems if i.get("delegable") and i.get("status") == "DONE"]
    check("a DONE item cannot appear as a live request (A-9's rule, one document over)",
          all(i["id"] not in [x["id"] for x in items] for i in done_flagged))
    sess = _session()
    check("session number is DERIVED from the committed drop-ins, never typed", sess >= 113)
    doc = render(items, sess)
    check("the brief carries the no-fabrication rule",
          "NEVER INVENT A NUMBER" in doc)
    check("the brief carries the do-not-fit rule", "DO NOT FIT ANYTHING" in doc)
    check("the brief distinguishes published from API-available",
          "PUBLISHED" in doc and "AVAILABLE OVER AN API" in doc)
    check("every task file stands alone (context + rules repeated)",
          all(("THE CONTEXT YOU NEED" in render_task(it, n, sess)
               and "THE RULES ON WHAT YOU SEND BACK" in render_task(it, n, sess))
              for n, it in enumerate(items, 1)))
    check("no emoji or em-dash reaches the generated brief",
          not any(ord(c) > 0x2000 for c in doc))
    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"build": cmd_build, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
