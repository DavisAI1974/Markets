"""Stage 4c: the grounding check.

For a claim, look for its supporting path in the knowledge graph. Where a path is missing, say what
evidence is needed, in the plan's own shape:

    {"decision": "revise", "claim": ..., "reason": ..., "required_evidence": [...]}

A claim that is not a reading has three outcomes: null (the link is there and the words were read again
and stand, at their lines or moved: the result says which, with the new line), "unread" (the link is there
but the words could not be read again here: no local checkout, or a file on another branch) and "revise"
(a link or the words are missing). A claim that cites cells of a graph node (a swarm claim) has its quote
read again from that node's pinned cells in the graph, never by opening the workbook as text. A reading
is held up only by a DERIVED_FROM link to a claim that itself stands, or to a CalcOutput, a Metric, an
Evaluation, a DipoleEvent or a Peak; a link to anything else (an AgentRun, a Source, an Entity) does not
hold it up, and the result says so.

A sentence that is not a node (`text`) never returns null: with candidates it returns "read" (a reviewer
must read whether a candidate means the sentence); with none, or only candidates tied to the tastytrade
platform or with a later claim set over them, it returns "revise" with what is needed. Words are matched
as whole words, never as parts of words.

There is no verdict word and no score: a claim whose path is there is not called proven, and two claims
that contradict each other both stay (the contradiction is listed).

One implementation, three callers (plan 4c and 4a-bis): the reviewer agent, the check register of
Codex's verifier plan (a check kept with `record` is an Evaluation node with the register's fields),
and stage 7f (a rule version must rest on a claim).

What the code can settle on its own, it settles: the links, and whether the quoted words still stand
in the file. What needs reading (does this claim mean what that sentence says) is left to the
reviewer, and the result says so.

  python3 -m tools.kgraph.grounding claim <claim id>
  python3 -m tools.kgraph.grounding text "<a sentence from a plan or a report>"
  python3 -m tools.kgraph.grounding node <id of a rule version or other node>
  python3 -m tools.kgraph.grounding all [--record --reviewer run:00NN]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import platform_scope
from .extract import repo_dirs
from .resolve import canonical
from .sources import code_stamp, link
from .store import GraphStore, sha

RUBRIC = ("grounding check v1: a supporting path in the graph (a SUPPORTS link from the source a claim was "
          "read from, or for a reading a DERIVED_FROM link to what it rests on), and the quoted words still "
          "standing in the file")
MAX_DEPTH = 4
_ws = re.compile(r"\s+")
_num = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
_word = re.compile(r"[A-Za-z][A-Za-z0-9_/.\-]{3,}")
STOP = set("""that this with from have has were was been their there which when what will would should could into
than then them they these those only also each every more most some such very just over under about after
before while where whose because being does done not and the for are its his her our your but nor per via""".split())


def _norm(s: str) -> str:
    return _ws.sub(" ", s).strip()


HOLDS_A_READING_UP = ("CalcOutput", "Metric", "Evaluation", "DipoleEvent", "Peak")


def _result(target: dict, checked, observed, open_, paths, required, reason, adverse=(), superseded_by=(),
            decision=None) -> dict:
    decision = decision or ("revise" if required else None)
    return {
        "decision": decision,
        "claim": {"id": target["id"], "rev": target["rev"], "type": target["type"],
                  "text": target["attrs"].get("text") or target["attrs"].get("name")},
        "reason": reason if decision else None,
        "required_evidence": list(required),
        "what_was_checked": list(checked),
        "what_was_observed": list(observed),
        "what_remains_open": list(open_),
        "supporting_paths": [list(p) for p in paths],
        "adverse": list(adverse),
        "superseded_by": list(superseded_by),
    }


def _quote_now(store: GraphStore, claim: dict, dirs: dict | None) -> tuple[str, str | None]:
    """('stands' | 'moved' | 'gone' | 'not read', a sentence saying what was seen)."""
    a = claim["attrs"]
    if a.get("cited_node"):
        # a claim that cites cells of a graph node: read again from that node's pinned cells, in the graph
        node = store.node(a["cited_node"])
        if node is None or "pinned" not in node["attrs"]:
            return "not read", f"the node {a['cited_node']} with its pinned cells is not in the graph: the cells were not read again"
        cols = [c["column"] for c in (a.get("cited_cells") or [])]
        pinned = node["attrs"]["pinned"]
        if not cols or any(c not in pinned for c in cols):
            return "gone", f"the cited columns {cols} are not all among the pinned cells of {a['cited_node']}"
        now_ = "; ".join(f"{c}={json.dumps(pinned[c], ensure_ascii=False)}" for c in cols)
        if now_ == a["quote"]:
            return "stands", f"the quoted cells stand in the pinned cells of {a['cited_node']} ({now_})"
        return "gone", f"the pinned cells of {a['cited_node']} now read {now_}, not {a['quote']}"
    src = store.node(a["source"])
    if src is None:
        return "not read", f"the source {a['source']} is not a node of the graph"
    repo = a["source"].split(":", 2)[1]
    path = src["attrs"]["path"]
    if "@" in repo or not dirs or repo not in dirs or not (dirs[repo] / path).is_file():
        return "not read", f"{path} is not in a local checkout of {repo}: the words were not read again"
    lines = (dirs[repo] / path).read_text(encoding="utf-8", errors="replace").splitlines()
    quote = _norm(a["quote"])
    if quote in _norm(" ".join(lines[a["line_start"] - 1:a["line_end"]])):
        return "stands", f"the quoted words stand in {path} on lines {a['line_start']}-{a['line_end']}"
    span = a["line_end"] - a["line_start"] + 1
    for i in range(len(lines)):
        if quote in _norm(" ".join(lines[i:i + span + 1])):
            # the window is one line wider than the span: the words start at the last window that holds them
            while i + 1 < len(lines) and quote in _norm(" ".join(lines[i + 1:i + span + 2])):
                i += 1
            return "moved", f"the quoted words stand in {path}, now at line {i + 1} (read at lines {a['line_start']}-{a['line_end']})"
    return "gone", f"the quoted words are no longer in {path}"


def check_claim(store: GraphStore, claim_id: str, dirs: dict | None = None, _depth: int = 0, _seen=None) -> dict:
    claim = store.node(claim_id)
    if claim is None or claim["type"] != "Claim":
        raise ValueError(f"{claim_id} is not a claim of the graph")
    a = claim["attrs"]
    _seen = (_seen or set()) | {claim_id}
    tied = platform_scope.members(store)
    checked, observed, open_, paths, required, reason = [], [], [], [], [], None
    unread = []                          # what could not be read again here
    into = [e for e in store.edges() if e["dst"] == claim_id]
    out = [e for e in store.edges() if e["src"] == claim_id]
    own_source = a.get("source")

    checked.append("a SUPPORTS link from the source the claim was read from")
    sup = [e for e in into if e["type"] == "SUPPORTS" and e["src"] == own_source]
    if own_source:
        if sup:
            state, said = _quote_now(store, claim, dirs)
            checked.append("the quoted words in the file as it stands now")
            observed.append(said)
            if state == "gone":
                reason = said + "; the claim rests on a wording that is no longer there"
                required.append(f"the current wording of {store.node(own_source)['attrs']['path']} that states it, "
                                "or a later claim that takes this one's place (a SUPERSEDES link)")
            elif state == "not read":
                open_.append(said)
                unread.append(said)
            if state in ("stands", "moved", "not read") and not a["inference"]:
                paths.append([sup[0]["id"]])
        else:
            src_node = store.node(own_source)
            where = src_node["attrs"]["path"] if src_node else own_source
            reason = "the claim names a source but no SUPPORTS link from it stands in the graph"
            required.append(f"a SUPPORTS link from {where} (lines {a.get('line_start')}-{a.get('line_end')}) to this claim")

    if a["inference"]:
        # A reading is not held up by the place it is written down. It needs something it rests on: a claim
        # that itself stands, or a calc output, a figure, a check, a dipole or a peak.
        checked.append("for a reading: a DERIVED_FROM link to a claim that stands, a calc output, a figure, a check, "
                       "a dipole or a peak it rests on")
        rests = [e for e in out if e["type"] == "DERIVED_FROM"]
        rests += [e for e in into if e["type"] == "SUPPORTS" and e["src"] != own_source]
        good = []
        for e in rests:
            other = e["dst"] if e["src"] == claim_id else e["src"]
            node = store.node(other)
            if node is None:
                continue
            if node["type"] == "Claim":
                if other in _seen or _depth >= MAX_DEPTH:
                    open_.append(f"{other} was not followed further (a ring, or {MAX_DEPTH} steps deep)")
                    continue
                sub = check_claim(store, other, dirs, _depth + 1, _seen)
                if other in tied:
                    observed.append(f"it rests on {other}, which is tied to a tastytrade platform issue: that is not taken as what it rests on")
                elif sub["decision"] in (None, "unread"):
                    good += [[e["id"]] + p for p in sub["supporting_paths"]] or [[e["id"]]]
                    if sub["decision"] == "unread":
                        unread.append(f"{other}: its words were not read again here")
                else:
                    observed.append(f"it rests on {other}, which itself lacks a path: {sub['reason']}")
            elif node["type"] in HOLDS_A_READING_UP:
                good.append([e["id"]])
            else:
                observed.append(f"it is tied to {other} ({node['type']}), which does not hold a reading up: "
                                "it says where something was made, not what the reading rests on")
        if good:
            paths += good
            observed.append(f"the reading rests on {len(good)} path(s) that reach a claim that stands, a calc output, "
                            "a figure, a check, a dipole or a peak")
        elif not required:
            reason = ("the document marks this as a reading (an inference); nothing in the graph shows what it "
                      "rests on")
            required.append("a DERIVED_FROM link from this claim to the measurement, the decision or the calc "
                            "output the reading rests on")
            if a.get("said_by"):
                open_.append(f"it is {a['said_by']}'s reading; whether Greg struck it or let it stand is not in the graph")

    tie = platform_scope.ties(store).get(claim_id)
    if tie:
        checked.append("whether the claim is tied to a tastytrade platform issue (parked by Greg)")
        observed.append(f"it is tied to a tastytrade platform issue ({tie['why']}): it is kept, and nothing new may rest on it")
    adverse = [e["id"] for e in into + out if e["type"] == "CONTRADICTS"]
    if adverse:
        checked.append("CONTRADICTS links")
        open_.append(f"{len(adverse)} claim(s) contradict this one; both stand until someone decides")
    superseded = [e["src"] for e in into if e["type"] == "SUPERSEDES"]
    if superseded:
        observed.append("a later claim says otherwise: " + ", ".join(superseded) + " (nothing is replaced: this one stays, "
                        "marked, and is called last)")
    decision = None
    if not required and unread:
        decision = "unread"
        reason = "the link is there but the words could not be read again here: " + "; ".join(unread)
    return _result(claim, checked, observed, open_, paths, required, reason, adverse, superseded, decision)


def check_node(store: GraphStore, node_id: str, dirs: dict | None = None) -> dict:
    """A node that should rest on claims (a rule version: plan 7a, "the finding ids in the graph that
    the rule rests on"): it needs a DERIVED_FROM link to at least one claim, and each such claim is
    checked in turn."""
    node = store.node(node_id)
    if node is None:
        raise ValueError(f"{node_id} is not a node of the graph")
    if node["type"] == "Claim":
        return check_claim(store, node_id, dirs)
    checked = ["a DERIVED_FROM link from the node to the claim(s) it rests on"]
    observed, open_, paths, required, reason = [], [], [], [], None
    rests = [e for e in store.edges("DERIVED_FROM") if e["src"] == node_id and (store.node(e["dst"]) or {}).get("type") == "Claim"]
    other = [e for e in store.edges("DERIVED_FROM") if e["src"] == node_id and (store.node(e["dst"]) or {}).get("type") != "Claim"]
    if other:
        observed.append("it is tied to " + ", ".join(sorted({store.node(e['dst'])['type'] for e in other}))
                        + " (" + ", ".join(e["dst"] for e in other[:3]) + "), which says where it was made, not what it rests on")
    if not rests:
        name = node["attrs"].get("name") or node_id
        reason = f"nothing in the graph says which claim or finding {name} rests on"
        required.append(f"a DERIVED_FROM link from {node_id} to the claim or finding it rests on "
                        "(for a rule: the measurement or the decision the rule was written from)")
    tied = platform_scope.members(store)
    unread_rest = []
    for e in rests:
        sub = check_claim(store, e["dst"], dirs)
        if e["dst"] in tied:
            reason = reason or f"it rests on {e['dst']}, which is tied to a tastytrade platform issue (parked by Greg)"
            required.append("a finding that does not come from the tastytrade sandbox or its thin feed")
        elif sub["decision"] in (None, "unread"):
            paths += [[e["id"]] + p for p in sub["supporting_paths"]] or [[e["id"]]]
            if sub["decision"] == "unread":
                unread_rest.append(e["dst"])
        else:
            reason = reason or f"it rests on {e['dst']}, which itself lacks a path: {sub['reason']}"
            required += sub["required_evidence"]
    if not required and unread_rest:
        return _result(node, checked, observed, open_, paths, required,
                       "the links are there but the words of " + ", ".join(unread_rest) + " could not be read again here",
                       decision="unread")
    return _result(node, checked, observed, open_, paths, required, reason)


def _word_set(text: str) -> set[str]:
    """The words of a text as whole tokens, as `_tokens` writes them (a word is never found inside another)."""
    return {w.lower().strip(".-/") for w in _word.findall(text)}


def _tokens(text: str) -> tuple[list[str], list[str]]:
    numbers = [n.replace(",", "") for n in _num.findall(text)]
    words = [w.lower().strip(".-/") for w in _word.findall(text)]
    return numbers, [w for w in dict.fromkeys(words) if w not in STOP and not w.isdigit()]


def check_text(store: GraphStore, text: str, dirs: dict | None = None, top: int = 8) -> dict:
    """A sentence from a plan, a report or a synthesis that is not a node yet: which claims of the
    graph carry its own numbers and names. Every number in the sentence must be in a claim for that
    claim to count. The candidates are listed by how many of the sentence's words each one carries
    (a search order, nothing more); whether a candidate MEANS what the sentence says is for the
    reviewer to read."""
    numbers, words = _tokens(text)
    checked = ["claims of the graph that carry every number of the sentence",
               "claims of the graph that carry the sentence's own words and names"]
    superseded = {e["dst"] for e in store.edges("SUPERSEDES")}
    tied = platform_scope.members(store)
    cands = []
    for c in store.nodes("Claim"):
        a = c["attrs"]
        body = (a["text"] + " " + (a.get("quote") or ""))
        have_n = set(n.replace(",", "") for n in _num.findall(body))
        have_w = _word_set(body)
        n_hit = [n for n in numbers if n in have_n]
        w_hit = [w for w in words if w in have_w]
        if numbers and len(n_hit) < len(numbers):
            continue
        if len(w_hit) < max(1, (len(words) + 1) // 2):
            continue
        src = store.node(a["source"]) if a.get("source") else None
        cands.append({"claim": c["id"], "text": a["text"], "quote": a.get("quote"),
                      "where": f"{src['attrs']['path']}:{a['line_start']}" if src else "an inference with no source line",
                      "said_by": a.get("said_by"), "inference": a["inference"],
                      "numbers_carried": n_hit, "words_carried": w_hit, "superseded": c["id"] in superseded,
                      "platform_issue": c["id"] in tied})
    cands.sort(key=lambda x: (x["platform_issue"], x["superseded"], -len(x["words_carried"]), x["inference"], x["claim"]))
    target = {"id": "text:" + sha(text), "rev": 0, "type": "text", "attrs": {"text": text}}
    observed, open_, required, reason = [], [], [], None
    usable = [c for c in cands if not c["platform_issue"] and not c["superseded"]]
    decision = None
    if usable:
        decision = "read"
        observed.append(f"{len(cands)} claim(s) carry every number of the sentence and at least half of its words as whole words")
        reason = ("a reviewer must read whether a candidate means what the sentence says: the code matched numbers "
                  "and whole words only, and that is not the meaning")
        open_.append("whether a candidate means what the sentence says is for the reviewer to read")
        if all(c["inference"] for c in usable):
            open_.append("every candidate is itself marked as a reading")
    elif cands:
        n_plat = sum(c["platform_issue"] for c in cands)
        n_sup = sum(c["superseded"] and not c["platform_issue"] for c in cands)
        observed.append(f"{len(cands)} claim(s) carry it: {n_plat} tied to a tastytrade platform issue, {n_sup} with a later "
                        "claim set over it (they stay in the graph and are listed)")
        reason = ("the only claims that carry it are tied to a tastytrade platform issue (the sandbox or its thin "
                  "feed, which Greg parked) or have a later claim set over them: they are not taken as evidence")
        if n_plat:
            required.append("evidence that does not come from the tastytrade sandbox or its thin feed")
        if n_sup:
            required.append("a claim that states it and has no later claim set over it")
    else:
        have_all = set()
        for c in store.nodes("Claim"):
            have_all |= set(n.replace(",", "") for n in _num.findall(c["attrs"]["text"] + " " + (c["attrs"].get("quote") or "")))
        missing = [n for n in numbers if n not in have_all]
        reason = "no claim in the graph carries the sentence's numbers together with its words"
        for n in missing:
            required.append(f"a source line that states the figure {n} (no claim in the graph carries it at all)")
        if numbers and not missing:
            required.append("a source line that states " + ", ".join(numbers) + " together, about: " + ", ".join(words[:8]))
        if not numbers:
            required.append("a source line that states it, about: " + ", ".join(words[:8]))
    if decision is None:
        decision = "revise"
    res = _result(target, checked, observed, open_, [], required, reason, decision=decision)
    res["supporting_candidates"] = cands[:top]
    res["candidates_not_shown"] = max(0, len(cands) - top)
    return res


def record(store: GraphStore, result: dict, reviewer: str, run: str | None) -> str:
    """Keep one check as an Evaluation node (the check register's line) with an EVALUATES link to
    what it checked. The same check of the same revision is one line, however often it is run."""
    target = result["claim"]
    if store.node(target["id"]) is None:
        raise ValueError("only a check of a node of the graph is kept; a sentence is checked, then registered as a claim")
    node = store.node(target["id"])
    # two reviewers' checks of one thing are two nodes: neither revises the other (the reviewer and the
    # method are part of the id, with the target, its revision, the rubric and what was observed)
    method = "tools.kgraph.grounding"
    eid = "eval:" + sha([target["id"], target["rev"], RUBRIC, reviewer, method, result["decision"],
                         result["required_evidence"], result["what_was_observed"]])
    attrs = {
        "rubric": RUBRIC,
        "what_was_checked": result["what_was_checked"],
        "what_was_observed": result["what_was_observed"] or ["nothing beyond the links"],
        "what_remains_open": result["what_remains_open"] or ["nothing found open by this check"],
        "decision": result["decision"], "reason": result["reason"],
        "required_evidence": result["required_evidence"],
        "supporting_paths": result["supporting_paths"], "adverse": result["adverse"],
        # the check register's fields (Codex's verifier plan, section 5)
        "check_type": "deterministic", "method": method, "method_version": code_stamp("tools.kgraph.grounding"),
        "claim_revision": target["rev"], "input_hash": node["content_sha"], "location": "tools/kgraph/grounding.py",
        "scope": "the graph as it stood when the check ran, and the local checkouts",
        "expected_observation": "a supporting path, and the quoted words standing in the file",
        "reviewer": reviewer,
    }
    edges = [link("EVALUATES", eid, target["id"])]
    if run:
        edges.append(link("PRODUCED", run, eid))
    store.write([{"id": eid, "type": "Evaluation", "attrs": attrs}], edges,
                written_by=run or code_stamp("tools.kgraph.grounding"))
    return eid


def check_all(store: GraphStore, dirs: dict | None = None) -> dict:
    """Every claim and every rule version of the graph, each checked on its own. Returns each one
    that needs evidence, as its own entry; nothing is summed up beyond the counts of how many."""
    need, n = [], 0
    for c in store.nodes("Claim"):
        n += 1
        r = check_claim(store, c["id"], dirs)
        if r["decision"] == "revise":
            need.append(r)
    rules = [e for e in store.nodes("Entity") if e["attrs"].get("entity_kind") == "rule version"]
    for rv in rules:
        r = check_node(store, rv["id"], dirs)
        if r["decision"] == "revise":
            need.append(r)
    return {"claims_checked": n, "rule_versions_checked": len(rules), "need_evidence": need}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    for v in ("claim", "node"):
        sub.add_parser(v).add_argument("id")
    sub.add_parser("text").add_argument("sentence")
    p = sub.add_parser("all")
    p.add_argument("--record", action="store_true")
    p.add_argument("--reviewer", default=None)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dirs = repo_dirs(store.data_root, a.markets, a.platform)
    if a.verb == "claim":
        print(json.dumps(check_claim(store, a.id, dirs), indent=1, ensure_ascii=False))
    elif a.verb == "node":
        print(json.dumps(check_node(store, canonical(store, a.id), dirs), indent=1, ensure_ascii=False))
    elif a.verb == "text":
        print(json.dumps(check_text(store, a.sentence, dirs), indent=1, ensure_ascii=False))
    else:
        out = check_all(store, dirs)
        if a.record:
            for r in out["need_evidence"]:
                record(store, r, reviewer=a.reviewer or code_stamp("tools.kgraph.grounding"),
                       run=a.reviewer if (a.reviewer or "").startswith("run:") else None)
        print(json.dumps({"claims_checked": out["claims_checked"], "rule_versions_checked": out["rule_versions_checked"],
                          "need_evidence": len(out["need_evidence"]),
                          "each": [{"id": r["claim"]["id"], "reason": r["reason"], "required_evidence": r["required_evidence"]}
                                   for r in out["need_evidence"]]}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
