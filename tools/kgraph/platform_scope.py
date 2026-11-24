"""No new claim is tied to a tastytrade platform issue.

Greg, 2026-11-24: "Make sure any nee claims aren't tied to tasty platdorm issues". What the tastytrade
sandbox does and what its thin feed lacks are parked by him ("The sandbox specific issues won't be a
problem soon so don't spend time on them"; "we don't need to make system around thin data"). So the
claims about them are kept, marked, and closed: nothing new may rest on one.

How a claim is tied (one MEMBER_OF link from the claim to the scope node, with the rule and the words
that tied it; nothing about the claim itself is changed):
  "the running list"  the claim was read from a line of the paper runner's list of gaps and misses
                      that the list itself parks: the lines its own entry "SANDBOX-ONLY ISSUES ARE
                      PARKED" names, its section on the feed, and its entry "RICHER DATA IS COMING"
                      (what exists only because the feed is thin). The line numbers are read from the
                      list as it stands, not written here.
  "its own words"     the claim's text or quote names the sandbox, tastytrade, the thin feed, a
                      stand-in for it, or a print with no side.
Greg's own decisions and rules are never tied: his word to park the issues is not itself an issue.

What being tied does:
  - the store refuses a link by which a new claim or a rule version would rest on a tied claim
    (`GraphStore.write`: a DERIVED_FROM, DEPENDS_ON or claim-to-claim SUPPORTS link whose rested-on end
    is in a closed scope);
  - the grounding check does not take a tied claim as evidence, and says so;
  - the session context leaves out the claims tied by the running list and marks the others.
A tie made by mistake is taken back with `untie` (the link's earlier line stays, with the reason), and
is not made again.

  python3 -m tools.kgraph.platform_scope mark
  python3 -m tools.kgraph.platform_scope list
  python3 -m tools.kgraph.platform_scope untie --claim claim:... --reason "..." --by run:00NN
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .sources import code_stamp, link
from .store import GraphStore, edge_id

SCOPE_ID = "scope:tastytrade-platform-issue"
SCOPE_NAME = "a tastytrade platform issue (the sandbox or its thin feed)"
LIST_REPO, LIST_PATH = "paper-trading-platform", "tasty/RUNNING_LIST.md"
LIST_SOURCE = f"src:{LIST_REPO}:{LIST_PATH}"
WORDS = re.compile(r"(?i)\b(sandbox(?:'s|-only)?|tastytrade(?:'s)?|thin feed|thin data|thinness|stand-ins?|"
                   r"no[- ]side|900[- ]seconds?|15-minute-old)(?!\w)")


def scope_node() -> dict:
    return {"id": SCOPE_ID, "type": "Entity", "attrs": {
        "name": SCOPE_NAME, "entity_kind": "scope", "closed": True,
        "closed_means": "nothing new may rest on a claim in this scope; the claims themselves are kept",
        "by": "Greg, 2026-11-24: \"Make sure any nee claims aren't tied to tasty platdorm issues\"; "
              "\"The sandbox specific issues won't be a problem soon so don't spend time on them\"; "
              "\"we don't need to make system around thin data\""}}


def parked_items(list_text: str) -> set[str]:
    """The lines the list's own entry parks: the item names between "dropped when the sandbox is left
    behind:" and "STILL OURS" (read from the list, so the list stays the one place they are named)."""
    m = re.search(r"dropped when the sandbox\s+is left behind:(.*?)STILL OURS", list_text, re.S)
    return set(re.findall(r"\b([A-D]\d+)\b", m.group(1))) if m else set()


def parked_lines(list_text: str) -> dict[int, str]:
    """line number -> why, for every line of the list that is parked."""
    lines = list_text.splitlines()
    items, section, cur = {}, None, None       # "C14" -> [first line, last line]
    section_span = {}
    for n, l in enumerate(lines, 1):
        s = re.match(r"## ([A-D])\. ", l)
        if s:
            section, cur = s.group(1), None
            section_span[section] = [n, n]
        elif section:
            section_span[section][1] = n
            m = re.match(r"(\d+)\. ", l)
            if m:
                cur = f"{section}{m.group(1)}"
                items[cur] = [n, n]
            elif cur and not l.startswith("("):
                items[cur][1] = n
    out: dict[int, str] = {}
    for name in sorted(parked_items(list_text)):
        if name in items:
            for n in range(items[name][0], items[name][1] + 1):
                out[n] = f"the running list parks its line {name} (its entry SANDBOX-ONLY ISSUES ARE PARKED)"
    if "B" in section_span:
        for n in range(section_span["B"][0], section_span["B"][1] + 1):
            out.setdefault(n, "the running list's section B: the tastytrade feed")
    for name, (a, b) in items.items():
        if "RICHER DATA IS COMING" in lines[a - 1]:
            for n in range(a, b + 1):
                out.setdefault(n, f"the running list's line {name}: what exists only because the feed is thin")
    return out


def members(store: GraphStore) -> set[str]:
    return {e["src"] for e in store.edges("MEMBER_OF") if e["dst"] == SCOPE_ID}


def ties(store: GraphStore) -> dict[str, dict]:
    """claim id -> the link's attrs (rule, why) for every claim that is tied now."""
    return {e["src"]: e["attrs"] for e in store.edges("MEMBER_OF") if e["dst"] == SCOPE_ID}


def _exempt(claim: dict) -> bool:
    a = claim["attrs"]
    return a.get("said_by") == "Greg" and a["statement_kind"] in ("decision", "rule")


def mark(store: GraphStore, dirs: dict | None) -> dict:
    """Tie every claim that should be tied and is not. A tie a person took back is not made again."""
    by = code_stamp("tools.kgraph.platform_scope")
    by_line: dict[int, str] = {}
    if dirs and LIST_REPO in dirs and (Path(dirs[LIST_REPO]) / LIST_PATH).is_file():
        by_line = parked_lines((Path(dirs[LIST_REPO]) / LIST_PATH).read_text(encoding="utf-8"))
    edges, counts = [], {"the running list": 0, "its own words": 0}
    for c in store.nodes("Claim"):
        if _exempt(c):
            continue
        eid = edge_id("MEMBER_OF", c["id"], SCOPE_ID, "")
        if store.history(eid):                   # tied already, or tied and taken back by a person
            continue
        a = c["attrs"]
        rule = why = None
        if a.get("source") == LIST_SOURCE and a.get("line_start") in by_line:
            rule, why = "the running list", by_line[a["line_start"]]
        else:
            found = sorted({m.group(1).lower() for m in WORDS.finditer(a["text"] + " " + (a.get("quote") or ""))})
            if found:
                rule, why = "its own words", "it names: " + ", ".join(found)
        if rule:
            counts[rule] += 1
            edges.append(link("MEMBER_OF", c["id"], SCOPE_ID, rule=rule, why=why))
    res = store.write([scope_node()], edges, written_by=by)
    return {"new": len(edges), "by_rule": counts, "tied_now": len(members(store)), "written": res,
            "running_list_read": bool(by_line)}


def untie(store: GraphStore, claim_id: str, reason: str, by: str) -> dict:
    eid = edge_id("MEMBER_OF", claim_id, SCOPE_ID, "")
    return store.withdraw_edge(eid, reason=f"{reason} (taken back by {by})",
                               written_by=by if by.startswith("run:") else code_stamp("tools.kgraph.platform_scope"))


def main(argv=None) -> int:
    from .extract import repo_dirs
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("mark")
    sub.add_parser("list")
    p = sub.add_parser("untie")
    p.add_argument("--claim", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    if a.verb == "mark":
        print(json.dumps(mark(store, repo_dirs(store.data_root, a.markets, a.platform)), indent=1))
    elif a.verb == "list":
        for cid, t in sorted(ties(store).items()):
            print(f"{cid} | {t['rule']} | {t['why']} | {store.node(cid)['attrs']['text'][:110]}")
    else:
        print(json.dumps(untie(store, a.claim, a.reason, a.by)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
