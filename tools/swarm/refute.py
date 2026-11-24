"""The refute wave: an attempt to contradict each claim sent to review, from the event's own cells only.

`build_refute_brief(store, claim_ids)` writes the refuter's brief: each claim with its event's numbered
cells (the same numbering the worker saw). `load_refute_result(store, result, run, brief_claims)` keeps each check as
an Evaluation node with an EVALUATES link to its claim; where the check returned a contradiction and
the cells it cites verify, the counter-statement is written as its own Claim (cells of one node, the
same checks as a worker's claim) with a CONTRADICTS link to the first. Both claims stay. There is no
verdict word: an Evaluation says what was checked, what was observed and what remains open.

A check is taken only for a claim that was in the brief the refuter answered and that is a swarm claim
(it has `about`); any other check, and any check whose handling raises, is kept as a Task line with the
reason, and the other checks go on. A counter-statement is read like a worker's claim: every figure a
`column=value` pair of a cell it cites. The refuter's "why" is refused if it carries one of the words that
rank, add up, grade or label (the same list as a worker's text).
"""

from __future__ import annotations

from tools.kgraph import schema
from tools.kgraph.sources import code_stamp, link
from tools.kgraph.store import GraphStore, sha

from . import layers as L
from . import reduce as R

RUBRIC = "refute wave v1: an attempt to contradict the claim from the event's own cells"

REFUTE_SYSTEM = """You are a REFUTER of DavisAI Markets. You are given one or more dipole events, each with its stored cells
(one a line: <n>| <node id> | <column> = <value>) and, for each event, claims a worker wrote about it. For each claim
you try to contradict it from THOSE CELLS ONLY: read the cells the claim cites and the others of its event, and say
whether any stored cell says something that does not agree with the claim's sentence. You do not use any outside
knowledge, you do not grade the worker, and you do not judge whether the claim is interesting. Return JSON only.

Return: {"checks": [ {"claim": "<claim id>", "contradicted": true or false, "cells": [n, ...], "why": "..."} ]}
One check for each claim, in the order given.
- "contradicted": true only when a stored cell disagrees with the sentence; false when you found none.
- "cells": the numbers n (of the event section the claim is in) of the cells you looked at. When "contradicted" is
  true they are cells of ONE node only (one sheet row).
- "why": one plain sentence saying what you compared and what the cells store. Every figure you write in it is
  a `column=value` pair copied exactly as the cell stores it, of one of the cells you list. When "contradicted" is true
  this sentence is the counter-statement and stands as a claim of its own: write it so it can be read alone,
  naming the column by its exact stored name. When it is false, say what you compared and what you saw.
- Do not write the cell numbers n in the sentence. No averages, counts or differences made by you, and none of
  these words (in any letter case): total, sum, mean, average, median, most, least, largest, smallest, highest,
  lowest, biggest, best, worst, better, worse, good, bad, strong, stronger, strongest, weak, weaker, weakest,
  winner, loser, win, loss, rank, ranked, top, bottom, mid, midpoint, middle, net, profit, fee, cost, correct,
  incorrect, right, wrong, accurate, inaccurate, agrees, pass, fail, refuted, confirmed, proven, proves.
- When "contradicted" is true, the sentence is written like a worker's claim: every figure as a pair
  `column=value` (the exact stored column name, the value copied as the cell stores it, for a cell you list), no
  number outside such pairs and no number written as a word. For example "native_baseline=0.1461538461538462 is
  stored for dipole:dip-19632-1696206142" (a real form from one event; write what YOUR cells store).
"""

REFUTE_SCHEMA = {
    "type": "object",
    "properties": {"checks": {"type": "array", "items": {
        "type": "object",
        "properties": {"claim": {"type": "string"}, "contradicted": {"type": "boolean"},
                       "cells": {"type": "array", "items": {"type": "integer"}}, "why": {"type": "string"}},
        "required": ["claim", "contradicted", "cells", "why"], "additionalProperties": False}}},
    "required": ["checks"], "additionalProperties": False,
}


def _claims(store: GraphStore, claim_ids: list[str]) -> list[dict]:
    out = []
    for cid in claim_ids:
        c = store.node(cid)
        if c is None or c["type"] != "Claim":
            raise schema.Refused(f"{cid} is not a Claim of the graph")
        out.append(c)
    return out


def build_refute_brief_parts(store: GraphStore, claim_ids: list[str]) -> tuple[str, str]:
    by_event: dict[str, list[dict]] = {}
    for c in _claims(store, claim_ids):
        by_event.setdefault(c["attrs"]["about"], []).append(c)
    body = []
    for ev, claims in by_event.items():
        ctx = R.event_context(store, ev)
        body.append(f"===== EVENT {ev} (cell numbers below belong to this event) =====")
        last = None
        for cell in ctx["cells"]:
            if cell["node"] != last:
                last = cell["node"]
                body.append(f"--- {cell['node']} (sheet {cell['sheet']!r}, row {cell['row']}) ---")
            body.append(f"{cell['n']}| {cell['node']} | {cell['column']} = {L.render(cell['value'])}")
        body.append("")
        body.append(f"CLAIMS about {ev}:")
        for c in claims:
            a = c["attrs"]
            how = ("an inference resting on claims " + ", ".join(
                e["dst"] for e in store.edges("DERIVED_FROM") if e["src"] == c["id"])) if a["inference"] \
                else f"cites cells {a['cells']} of {a['cited_node']}"
            body.append(f"claim {c['id']} | {a['text']} | {how}")
        body.append("")
    return REFUTE_SYSTEM, "\n".join(body + ["Return the JSON now."])


def build_refute_brief(store: GraphStore, claim_ids: list[str]) -> str:
    s, u = build_refute_brief_parts(store, claim_ids)
    return s + "\n\n" + u


def _task(store, run, why, returned, key, claim=None, event=None):
    tid = "task:thrown-out:" + sha([run, "refute check", key, returned])
    attrs = {"text": f"A refute check returned by {run} was not written as an Evaluation: {why}.",
             "state": "blocked", "reason": why, "returned": returned}
    if event is not None:
        attrs.update(source=event["attrs"]["source"], about=event["id"])
    return {"id": tid, "type": "Task", "attrs": attrs}, link("PRODUCED", run, tid)


def _one_check(store: GraphStore, run: str, ck, i: int, brief_claims: set, stamp: str) -> dict:
    """One check, on its own: {"nodes", "edges", "outcome"} where outcome is ("thrown", why),
    ("evaluation", claim id, eval id, counter id or None, counter_note or None, reason it was not written or None).
    It writes nothing to the store; a check that raises is turned into a Task line by the caller."""
    why = None
    claim = event = ctx = None
    if not isinstance(ck, dict):
        why = "the check is not an object"
    else:
        claim = store.node(ck.get("claim")) if isinstance(ck.get("claim"), str) else None
        if claim is None or claim["type"] != "Claim":
            why = "the check names no claim of the graph"
        elif claim["id"] not in brief_claims:
            why = "the check names a claim that was not in the brief this refuter answered"
        elif not isinstance(claim["attrs"].get("about"), str) or store.node(claim["attrs"]["about"]) is None:
            why = "the check names a claim that is not a swarm claim about a dipole event (it has no `about`)"
        elif not isinstance(ck.get("contradicted"), bool):
            why = "contradicted is not true or false"
        elif not isinstance(ck.get("why"), str) or not ck["why"].strip():
            why = "no sentence in why"
        elif R.banned_word(ck["why"]):
            why = f"the sentence carries the word {R.banned_word(ck['why'])!r}: a check says what was compared and what was seen"
    if not why:
        event = store.node(claim["attrs"]["about"])
        ctx = R.event_context(store, event["id"])
        cites = ck.get("cells")
        if not isinstance(cites, list) or any(isinstance(n, bool) or not isinstance(n, int) or n not in ctx["by_n"] for n in cites):
            why = "cells is not a list of cells of the claim's event"
    if why:
        t, e = _task(store, run, why, ck, i, claim, event)
        return {"nodes": [t], "edges": [e], "thrown": why}
    nodes, edges = [], []
    got = sorted({ctx["by_n"][n]["n"]: ctx["by_n"][n] for n in ck["cells"]}.values(), key=lambda g: g["n"])
    counter_id, counter_note, not_written = None, None, None
    if ck["contradicted"]:
        c = {"k": 1, "text": ck["why"], "statement_kind": "measurement", "inference": False,
             "cells": [g["n"] for g in got], "rests_on": []}
        problem, prep = R.prepare_claim(ctx, c, {}, need_confidence=False)
        if problem:
            counter_note = f"the counter-statement was not written as a claim: {problem}"
            t, e = _task(store, run, problem, ck, i, claim, event)
            nodes.append(t)
            edges.append(e)
            not_written = {"claim": claim["id"], "reason": problem}
        else:
            counter_id, cnode, es = R.claim_nodes(
                store, ctx, prep, c, run, None, salt=f"|counter to {claim['id']}",
                extra={"counter_to": claim["id"], "claim_k": 0})
            nodes.append(cnode)
            edges += es
            edges.append(link("CONTRADICTS", counter_id, claim["id"]))
    a = claim["attrs"]
    observed = [("the refuter returned a contradiction, citing cells " if ck["contradicted"]
                 else "the refuter returned no contradiction, having looked at cells ") + R.quote_of(got)
                if got else
                ("the refuter returned a contradiction and cited no cell" if ck["contradicted"]
                 else "the refuter returned no contradiction and cited no cell"),
                ck["why"]]
    open_ = ["whether the refuter read the cells rightly is for a reader: code checked only that the cited cells "
             "exist in the claim's event and, for a counter-statement, that they are one node's and that every "
             "figure in the sentence is a column=value pair equal to one of them"]
    if counter_note:
        open_.append(counter_note)
    if not ck["contradicted"]:
        open_.append("a refuter that looked at the cells and found nothing is not a proof that the claim is right")
    eid = "eval:" + sha([claim["id"], claim["rev"], RUBRIC, run, ck["cells"], ck["contradicted"], ck["why"]])
    nodes.append({"id": eid, "type": "Evaluation", "attrs": {
        "rubric": RUBRIC,
        "what_was_checked": [f"an attempt to contradict claim {claim['id']} ({a['text']}) from the stored cells of {event['id']}"],
        "what_was_observed": observed,
        "what_remains_open": open_,
        "check_type": "model-assisted", "method": "tools.swarm.refute", "method_version": stamp,
        "claim_revision": claim["rev"], "input_hash": claim["content_sha"], "reviewer": run,
        "scope": "the stored cells of this one event, its neighbours and the peaks between them",
        "location": event["id"], "expected_observation": "a stored cell that disagrees with the sentence, if there is one",
        "contradiction_returned": ck["contradicted"],
        "cells": [{"n": g["n"], "node": g["node"], "column": g["column"], "value": g["value"]} for g in got],
        "returned": ck, "counter_statement": counter_id}})
    edges += [link("EVALUATES", eid, claim["id"]), link("PRODUCED", run, eid)]
    return {"nodes": nodes, "edges": edges, "evaluation": {"claim": claim["id"], "evaluation": eid,
                                                           "counter_statement": counter_id},
            "counter_not_written": not_written}


def load_refute_result(store: GraphStore, result: dict, run: str, brief_claims) -> dict:
    """Write what one refuter returned. `brief_claims` are the ids of the claims in the brief it answered:
    a check is taken only for one of them, and only for a swarm claim (one with `about`). Any other check,
    and any check whose own handling raises, is kept as a Task line with the reason; one bad check never
    stops the others."""
    R._need_run(store, run)
    checks = result.get("checks") if isinstance(result, dict) else None
    if not isinstance(checks, list):
        raise schema.Refused("a refuter's answer has a list of checks: {\"checks\": [...]}")
    brief_claims = set(brief_claims)
    stamp = code_stamp("tools.swarm.refute")
    nodes, edges = [], []
    rep = {"returned": len(checks), "evaluations_written": 0, "thrown_out": 0, "counter_statements_written": 0,
           "counter_statements_not_written": [], "thrown": [], "evaluations": []}
    for i, ck in enumerate(checks):
        try:
            one = _one_check(store, run, ck, i, brief_claims, stamp)
        except Exception as e:                      # one bad check cannot stop the others
            why = f"the check could not be handled: {type(e).__name__}: {e}"
            t, tl = _task(store, run, why, ck, i)
            one = {"nodes": [t], "edges": [tl], "thrown": why}
        nodes += one["nodes"]
        edges += one["edges"]
        if "thrown" in one:
            rep["thrown_out"] += 1
            rep["thrown"].append(one["thrown"])
            continue
        rep["evaluations_written"] += 1
        rep["evaluations"].append(one["evaluation"])
        if one["counter_not_written"]:
            rep["counter_statements_not_written"].append(one["counter_not_written"])
        elif one["evaluation"]["counter_statement"]:
            rep["counter_statements_written"] += 1
    store.write(nodes, edges, written_by=stamp)
    # every path that writes a claim marks what belongs to the tastytrade platform (Greg, 2026-11-24)
    from tools.kgraph import platform_scope
    platform_scope.mark(store, None)
    return rep
