"""No new claim is tied to a tastytrade platform issue.

Greg, 2026-11-24: "Make sure any nee claims aren't tied to tasty platdorm issues". What the tastytrade
sandbox does and what its thin feed lacks are parked by him ("The sandbox specific issues won't be a
problem soon so don't spend time on them"; "we don't need to make system around thin data"). And, same
day: "nothing gets replaced ... stuff that doesn't work just gets scored so it doesn't get called".

So nothing about the platform is removed or replaced. Each thing that belongs to it is MARKED (one
MEMBER_OF link to the scope node, with the rule that marked it and why), and a marked thing is not
called: nothing new may rest on it, the grounding check does not take it as evidence, and the session
context calls it last.

Who marks (each link says which):
  "the running list"            a claim read from a line of the paper runner's list of gaps and misses
                                that the list itself parks: the lines its entry "SANDBOX-ONLY ISSUES
                                ARE PARKED" names, its section on the feed, and its entry "RICHER DATA
                                IS COMING". Read from the list as it stood when the claim was read.
  "a record of a sandbox run"   every Order and Fill of a paper run, and the run folders' own files:
                                they were made on the sandbox and its feed, and nothing of them is scored.
  "the evaluator"               a model that read the claim against the rubric in EVALUATOR_BRIEF and
                                said it is about the platform's behaviour or exists only because of it.
  "its own words"               PROVISIONAL: the claim's words name the sandbox, tastytrade, the thin
                                feed, a stand-in, a print with no side, a refusal or a server error.
                                It is the cheap signal that holds until an evaluator has read the
                                claim; the evaluator can confirm it or lift it, with its reason.
Never marked: anything Greg said (his decisions about the platform are not platform issues). A standing
rule is not marked by its words or by an evaluator; only a line the running list itself parks is.

Lifting a mark: a provisional one is lifted by an evaluator's answer (`apply`). Any other is lifted
only with Greg's own words (`untie --greg "<his words>"`), which are kept on the line. A mark that was
lifted is not made again.

  python3 -m tools.kgraph.platform_scope mark
  python3 -m tools.kgraph.platform_scope list
  python3 -m tools.kgraph.platform_scope brief --out brief.txt          # for the evaluator
  python3 -m tools.kgraph.platform_scope apply --result answer.json --run run:00NN
  python3 -m tools.kgraph.platform_scope untie --node claim:... --greg "<his words>" --by run:00NN
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import schema
from .sources import code_stamp, link
from .store import GraphStore, edge_id

_ws = re.compile(r"\s+")
SCOPE_ID = "scope:tastytrade-platform-issue"
SCOPE_NAME = "the tastytrade platform (an issue of its sandbox or its thin feed, or a record made on them)"
LIST_REPO, LIST_PATH = "paper-trading-platform", "tasty/RUNNING_LIST.md"
LIST_SOURCE = f"src:{LIST_REPO}:{LIST_PATH}"
RULE_LIST, RULE_RECORD, RULE_EVAL, RULE_WORDS = ("the running list", "a record of a sandbox run",
                                                 "the evaluator", "its own words")
PROVISIONAL = (RULE_WORDS,)
RUN_RECORDS = ("/paper-trading-20261123/live-runs/", "/paper-trading-20261123/7e/")
WORDS = re.compile(r"(?i)(?<![\w/])(sandbox(?:'s|-only)?|tastytrade(?:'s)?|thin feed|thin data|thinness|stand-ins?|"
                   r"no[- ]side|900[- ]seconds?|15-minute-old|this feed|feed-only|refused|server errors?|"
                   r"dry[- ]runs?|cancel requested|5WY79188|/NGF7|/NGF27)(?![\w/])")


def scope_node() -> dict:
    return {"id": SCOPE_ID, "type": "Entity", "attrs": {
        "name": SCOPE_NAME, "entity_kind": "scope", "closed": True,
        "closed_means": "nothing is removed or replaced: what is in this scope is kept and marked, and is not "
                        "called: nothing new may rest on it",
        "by": "Greg, 2026-11-24: \"Make sure any nee claims aren't tied to tasty platdorm issues\"; "
              "\"The sandbox specific issues won't be a problem soon so don't spend time on them\"; "
              "\"we don't need to make system around thin data\"; \"nothing gets replaced ... stuff that doesn't "
              "work just gets scored so it doesn't get called\""}}


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


def ties(store: GraphStore) -> dict[str, dict]:
    """node id -> the link's attrs (rule, why) for everything that is marked now."""
    return {e["src"]: e["attrs"] for e in store.edges("MEMBER_OF") if e["dst"] == SCOPE_ID}


def members(store: GraphStore) -> set[str]:
    return set(ties(store))


def exempt(claim: dict) -> bool:
    """Greg's own words are never marked, whatever their kind, and no standing rule is."""
    a = claim["attrs"]
    return a.get("said_by") == "Greg" or a.get("statement_kind") == "rule"


def _due(store: GraphStore, dirs: dict | None) -> list[tuple[dict, str, str]]:
    """(node, rule, why) for everything the rules mark that is not marked and was never lifted."""
    repo_dir = Path(dirs[LIST_REPO]) if dirs and LIST_REPO in dirs else None
    at_commit: dict[str, dict[int, str]] = {}

    def by_line_at(commit: str | None) -> dict[int, str]:
        # the list AS IT STOOD at the commit the claim was read from: a claim's line numbers are that wording's
        if repo_dir is None or not commit:
            return {}
        if commit not in at_commit:
            try:
                from .extract import git_text
                at_commit[commit] = parked_lines(git_text(repo_dir, commit, LIST_PATH))
            except RuntimeError:
                at_commit[commit] = {}
        return at_commit[commit]

    out = []
    for n in store.nodes():
        if n["type"] not in ("Claim", "Order", "Fill", "Source"):
            continue
        if store.history(edge_id("MEMBER_OF", n["id"], SCOPE_ID, "")):     # marked already, or marked and lifted
            continue
        a = n["attrs"]
        if n["type"] in ("Order", "Fill"):
            out.append((n, RULE_RECORD, f"an {n['type'].lower()} of the paper run {a.get('run')} on the tastytrade "
                                         "sandbox; nothing of it is scored"))
        elif n["type"] == "Source":
            if any(part in "/" + a.get("path", "") for part in RUN_RECORDS):
                out.append((n, RULE_RECORD, "a file of a run on the tastytrade sandbox"))
        elif a.get("said_by") != "Greg":
            # A line the running list itself parks is marked whatever kind of sentence the reader called it
            # (the list is Greg's own parking of it). Beyond the list, a standing rule is never marked.
            by_line = by_line_at(a.get("source_commit")) if a.get("source") == LIST_SOURCE else {}
            if a.get("line_start") in by_line:
                out.append((n, RULE_LIST, by_line[a["line_start"]]))
            elif not exempt(n):
                found = sorted({m.group(1).lower() for m in WORDS.finditer(a["text"] + " " + (a.get("quote") or ""))})
                if found:
                    out.append((n, RULE_WORDS, "it names: " + ", ".join(found) + " (provisional, until an evaluator has read it)"))
    return out


def mark(store: GraphStore, dirs: dict | None) -> dict:
    """Mark everything that is due. Safe to call after any write: it adds nothing twice."""
    by = code_stamp("tools.kgraph.platform_scope")
    due = _due(store, dirs)
    counts: dict[str, int] = {}
    edges = []
    for n, rule, why in due:
        counts[rule] = counts.get(rule, 0) + 1
        edges.append(link("MEMBER_OF", n["id"], SCOPE_ID, rule=rule, why=why))
    res = store.write([scope_node()], edges, written_by=by)
    return {"new": len(edges), "by_rule": counts, "marked_now": len(members(store)), "written": res}


def pending(store: GraphStore, dirs: dict | None) -> list[str]:
    """What should be marked and is not, one line each (for `python3 -m tools.kgraph check`): a claim
    written by some path that did not call `mark`."""
    return [f"{n['type']} {n['id']} belongs to the tastytrade platform ({rule}: {why}) and is not marked: "
            "run python3 -m tools.kgraph.platform_scope mark" for n, rule, why in _due(store, dirs)]


def untie(store: GraphStore, node_id: str, greg_words: str, by: str) -> dict:
    """Lift a mark on Greg's word. His own words are required and are kept on the line."""
    if not greg_words or not greg_words.strip():
        raise schema.Refused("a mark is lifted only on Greg's word: give his own words (a provisional mark is lifted "
                             "by an evaluator's answer instead)")
    eid = edge_id("MEMBER_OF", node_id, SCOPE_ID, "")
    return store.withdraw_edge(eid, reason=f"Greg: \"{greg_words.strip()}\" (recorded by {by})",
                               written_by=by if by.startswith("run:") else code_stamp("tools.kgraph.platform_scope"))


# ---- the evaluator --------------------------------------------------------------------------------
EVALUATOR_BRIEF = """You are an EVALUATOR of DavisAI Markets. Rubric: "tastytrade platform, v1". Below is every claim of the
knowledge graph that is not already firmly marked, one a line: `<claim id> | <kind> | <who said it> | <the claim>`.
A line that ends with `[P]` is provisionally marked because of a word in it; you confirm or lift that.

Greg's ruling: what the tastytrade sandbox does and what its thin feed lacks are parked; nothing new is to be
built on them. Your job is to say which claims BELONG TO THAT, so that nothing new rests on them. Nothing is
removed: a claim you mark stays in the graph.

MARK a claim (put it under "tied") when it is about:
 (a) how the tastytrade sandbox or its API behaved: an order refused, a fill and the price it filled at, a server
     error, a status that stayed Live, a cancel, a dry run, the account left short, what the sandbox lists or accepts;
 (b) what its feed carries or lacks: 900 seconds behind, prints with no side, no single orders, a quote seen only
     at a print, day volume ahead of the prints, the feed's timestamps;
 (c) something that exists ONLY because of (a) or (b): a stand-in, a late close, a strategy or a reading made for
     the print with no side, a rule that cannot run on this feed, how a rule reads this feed;
 (d) a count or a figure measured on a sandbox run or a sandbox recording: how many prints, trades, orders, fills,
     opens, closes, seconds of delay.
Do NOT mark (put a provisionally marked one under "not_tied", and say nothing about the others):
 - a decision or a standing rule, whoever said it, even when it is about the platform ("no order goes to the
   sandbox", "nothing from the sandbox feed is scored", "runs are ledger-only");
 - where code, keys, files, branches or records are, or what was built, pushed, committed or tested;
 - the agent program, the graph, the plan and its stages, budgets, agent runs, HOLD, Greg's go;
 - anything about the 2023 tape, ROOT, Frankie, Native, Granite, the dipole and the exhaustion as formulas;
 - a strategy's own rule text where it does not depend on what this feed lacks.
When you are not sure, do not mark; for a `[P]` line you are not sure of, leave it out of both lists (it stays
provisionally marked).

Return JSON only: {"tied": [{"claim": "<id>", "why": "<a few words: which of a, b, c, d and what>"}],
"not_tied": [{"claim": "<id of a [P] line>", "why": "<a few words>"}]}
"""


def brief(store: GraphStore) -> str:
    """The evaluator's brief: every claim that is neither Greg's nor a rule nor firmly marked."""
    t = ties(store)
    rows = []
    for c in sorted(store.nodes("Claim"), key=lambda n: (n["attrs"].get("source") or "", n["attrs"].get("line_start") or 0, n["id"])):
        if exempt(c) or (c["id"] in t and t[c["id"]]["rule"] not in PROVISIONAL):
            continue
        a = c["attrs"]
        rows.append(f"{c['id']} | {a['statement_kind']} | {a.get('said_by') or '-'} | "
                    + _ws.sub(" ", a["text"]).strip() + (" [P]" if c["id"] in t else ""))
    return EVALUATOR_BRIEF + "\n" + "\n".join(rows) + "\n"


def apply(store: GraphStore, result: dict, run: str) -> dict:
    """Write the evaluator's answer. A claim it marks is marked by "the evaluator" (a provisional mark
    becomes that, its earlier line kept). A provisional mark it lifts is lifted, with its reason. A firm
    mark is never lifted here, and Greg's words and rules are never marked: each such line of the
    answer is reported back, not applied."""
    node = store.node(run)
    if node is None or node["type"] != "AgentRun":
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    by = code_stamp("tools.kgraph.platform_scope")
    now = ties(store)
    edges, out = [], {"marked": 0, "confirmed": 0, "lifted": 0, "not_applied": []}
    for item in result.get("tied", []):
        c = store.node(str(item.get("claim")))
        if c is None or c["type"] != "Claim":
            out["not_applied"].append({"item": item, "why": "not a claim of the graph"})
        elif exempt(c):
            out["not_applied"].append({"item": item, "why": "Greg's own words and standing rules are never marked"})
        elif c["id"] in now and now[c["id"]]["rule"] not in PROVISIONAL:
            out["not_applied"].append({"item": item, "why": f"already marked by {now[c['id']]['rule']}"})
        elif not item.get("why"):
            out["not_applied"].append({"item": item, "why": "it gives no reason"})
        else:
            out["confirmed" if c["id"] in now else "marked"] += 1
            edges.append(link("MEMBER_OF", c["id"], SCOPE_ID, rule=RULE_EVAL, why=item["why"], made_by=run,
                              rubric="tastytrade platform, v1"))
    store.write([scope_node()], edges, written_by=by)
    for item in result.get("not_tied", []):
        cid = str(item.get("claim"))
        if cid in now and now[cid]["rule"] in PROVISIONAL and item.get("why"):
            store.withdraw_edge(edge_id("MEMBER_OF", cid, SCOPE_ID, ""),
                                reason=f"the evaluator ({run}) read it: {item['why']}", written_by=by)
            out["lifted"] += 1
        else:
            out["not_applied"].append({"item": item, "why": "not a provisional mark (a firm mark is lifted only on Greg's word)"
                                       if cid in now else "it is not marked"})
    after = ties(store)
    out["still_provisional"] = sorted(c for c, t in after.items() if t["rule"] in PROVISIONAL)
    out["marked_now"] = len(after)
    return out


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
    p = sub.add_parser("brief")
    p.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--result", required=True)
    p.add_argument("--run", required=True)
    p = sub.add_parser("untie")
    p.add_argument("--node", required=True)
    p.add_argument("--greg", required=True, help="Greg's own words")
    p.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    if a.verb == "mark":
        print(json.dumps(mark(store, repo_dirs(store.data_root, a.markets, a.platform)), indent=1))
    elif a.verb == "list":
        for nid, t in sorted(ties(store).items()):
            n = store.node(nid)
            print(f"{nid} | {t['rule']} | {t['why']} | {(n['attrs'].get('text') or n['type'])[:110]}")
    elif a.verb == "brief":
        text = brief(store)
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"{a.out}: {len(text.splitlines())} lines, {len(text)} characters")
    elif a.verb == "apply":
        raw = Path(a.result).read_text(encoding="utf-8")
        print(json.dumps(apply(store, json.loads(raw[raw.find("{"):raw.rfind("}") + 1]), a.run), indent=1))
    else:
        print(json.dumps(untie(store, a.node, a.greg, a.by)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
