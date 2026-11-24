"""The reducer (defined before any fan-out): what a worker returned becomes claims only where the
cells it cites are the event's own cells and every number it writes is a number of those cells.

A claim that passes becomes a Claim node tied to the workbook by a SUPPORTS link (or, for an inference,
to the claims it rests on by DERIVED_FROM links). A claim that fails is NOT written as a claim: it is
kept as a Task line with the reason and the returned object, so nothing a worker returned is lost and
nothing unchecked is believed. Nothing is averaged, ranked, pooled or dropped; the cutoff on confidence
only decides which claims are SENT TO REVIEW; a claim under it is written and kept.

  `load_worker_result(store, result, run, cutoff=...)`  -> report
  `review_set(store, event_ids, cutoff)`                -> claim ids sent to review
  `synthesis(store, event_ids)`                         -> text, each event on its own
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from tools.kgraph import schema
from tools.kgraph.extract import claim_id
from tools.kgraph.sources import code_stamp, link
from tools.kgraph.store import GraphStore, sha

from . import layers as L

WORKER_KINDS = ("measurement", "state", "definition")
SENT = "sent to review"
HELD = "held under the cutoff {cutoff}"

# labels and statistics a worker may not write (the brief says so; the loader enforces it), and the
# status words the graph never carries.
BANNED = ("winner", "loser", "strong", "weak", "strongest", "weakest", "best", "worst", "average", "averaged",
          "median", "rank", "ranked", "pass", "passed", "fail", "failed", "refuted", "confirmed", "mid price")
_banned_re = re.compile(r"\b(" + "|".join(re.escape(b) for b in BANNED) + r")\b", re.I)

_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def banned_word(text: str) -> str | None:
    m = _banned_re.search(text)
    return m.group(1) if m else None


def numbers(text: str, names=()) -> list[Decimal]:
    """The numbers written in a text. Column names and node ids named in the text are taken out first:
    their digits are part of a name, not a figure."""
    for name in sorted({n for n in names if n}, key=len, reverse=True):
        text = text.replace(name, " ")
    out = []
    for tok in _NUM.findall(text):
        try:
            out.append(Decimal(tok))
        except InvalidOperation:       # cannot happen for the pattern; kept so nothing is silently skipped
            raise ValueError(f"not a number: {tok!r}")
    return out


def cell_numbers(cell: dict) -> set[Decimal]:
    return set(numbers(L.render(cell["value"])))


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ---- one claim: checked against the event's own cells -------------------------------------------

def event_context(store: GraphStore, event_id: str) -> dict:
    node = store.node(event_id)
    if node is None or node["type"] != "DipoleEvent":
        raise schema.Refused(f"{event_id} is not a DipoleEvent of the graph")
    cl = L.cells(L.event_layers(store, event_id))
    names = {c["column"] for c in cl} | {c["node"] for c in cl} | {event_id}
    return {"event": node, "cells": cl, "by_n": {c["n"]: c for c in cl}, "names": names}


def prepare_claim(ctx: dict, c: dict, written: dict, *, need_confidence: bool = True) -> tuple[str | None, dict | None]:
    """(reason it is thrown out, None) or (None, what the Claim needs). `written` maps the k of each
    claim already written in this answer to {"id", "cells" (the n it stands on), "inference"}."""
    if not isinstance(c, dict):
        return "the claim is not an object", None
    k, text = c.get("k"), c.get("text")
    if isinstance(k, bool) or not isinstance(k, int):
        return "k is not a whole number", None
    if not isinstance(text, str) or not text.strip():
        return "no text", None
    if c.get("statement_kind") not in WORKER_KINDS:
        return f"statement_kind {c.get('statement_kind')!r} is not one of {WORKER_KINDS}", None
    inference = c.get("inference")
    if not isinstance(inference, bool):
        return "inference is not true or false", None
    conf = c.get("confidence")
    if need_confidence and (not _is_num(conf) or not (0 <= conf <= 1)):
        return "confidence is not a number between 0 and 1", None
    w = banned_word(text)
    if w:
        return f"the text carries the word {w!r}: a worker states what the cells say, with no label or statistic", None
    cites, rests = c.get("cells") or [], c.get("rests_on") or []
    if not isinstance(cites, list) or not isinstance(rests, list):
        return "cells and rests_on must be lists", None
    if k in written:
        return f"k {k} was already used in this answer", None
    name_scan = ctx["names"]
    if inference:
        if cites:
            return "an inference cites no cells; it lists the earlier claims it rests on", None
        if not rests:
            return "an inference rests on no earlier claim", None
        have, ids = set(), []
        for r in rests:
            if isinstance(r, bool) or not isinstance(r, int) or r not in written:
                return f"rests_on {r!r} is not an earlier claim of this answer that was written", None
            have |= written[r]["cells"]
            ids.append(written[r]["id"])
        allowed = set().union(*(cell_numbers(ctx["by_n"][n]) for n in have))
        for num in numbers(text, name_scan):
            if num not in allowed:
                return f"the number {num} in the text is not a number of the cells the claims it rests on cite", None
        return None, {"k": k, "inference": True, "cells": sorted(have), "rests_ids": ids, "node": None}
    if rests:
        return "a claim that is not an inference rests on no claim; it cites cells", None
    if not cites:
        return "a claim that is not an inference cites no cells", None
    got = []
    for n in cites:
        if isinstance(n, bool) or not isinstance(n, int) or n not in ctx["by_n"]:
            return f"cell {n!r} is not a cell of this event's brief", None
        got.append(ctx["by_n"][n])
    nodes = {g["node"] for g in got}
    if len(nodes) != 1:
        return "a claim that is not an inference cites cells of one node only; this one cites " + ", ".join(sorted(nodes)), None
    got = sorted({g["n"]: g for g in got}.values(), key=lambda g: g["n"])
    allowed = set().union(*(cell_numbers(g) for g in got))
    for num in numbers(text, name_scan):
        if num not in allowed:
            return f"the number {num} in the text is not the value of a cell it cites", None
    return None, {"k": k, "inference": False, "cells": [g["n"] for g in got], "rests_ids": [],
                  "node": got[0]["node"], "got": got}


def quote_of(got: list[dict]) -> str:
    return "; ".join(f"{g['column']}={L.render(g['value'])}" for g in got)


def claim_nodes(store: GraphStore, ctx: dict, prep: dict, c: dict, run: str, cutoff: float | None, *,
                extra: dict | None = None, salt: str = "") -> tuple[str, dict, list[dict]]:
    """(claim id, the Claim node, its links) for a claim that passed `prepare_claim`."""
    ev = ctx["event"]
    sid, event_id = ev["attrs"]["source"], ev["id"]
    conf = c.get("confidence")
    attrs = {"text": c["text"], "statement_kind": c["statement_kind"], "inference": prep["inference"],
             "confidence": conf, "claim_k": prep["k"], "about": event_id,
             "trade_day": ev["attrs"]["trade_day"], "cells": prep["cells"], "extracted_by": run,
             "proposer": run}
    if cutoff is None:
        attrs["review"] = SENT
    else:
        attrs["review"] = SENT if conf >= cutoff else HELD.format(cutoff=cutoff)
    edges = []
    if prep["inference"]:
        # the id carries the event and the claims it rests on, so one wording on two events is two claims
        cid = claim_id(sid, f"{event_id}|inference|{','.join(prep['rests_ids'])}{salt}", c["text"])
        attrs.update(line_start=ev["attrs"]["row"], line_end=ev["attrs"]["row"], sheet=ev["attrs"]["sheet"])
        for rid in prep["rests_ids"]:
            edges.append(link("DERIVED_FROM", cid, rid))
    else:
        node = store.node(prep["node"])
        quote = quote_of(prep["got"])
        # the node and the event are in the id, because "native_polarity=1" stands on many rows and a
        # peak sits in the span of several events
        cid = claim_id(sid, f"{event_id}|{prep['node']}|{quote}{salt}", c["text"])
        attrs.update(source=node["attrs"]["source"], sheet=node["attrs"]["sheet"],
                     line_start=node["attrs"]["row"], line_end=node["attrs"]["row"], quote=quote,
                     cited_node=prep["node"], cited_cells=[
                         {"n": g["n"], "column": g["column"], "value": g["value"]} for g in prep["got"]])
        edges.append(link("SUPPORTS", node["attrs"]["source"], cid, line_start=node["attrs"]["row"],
                          line_end=node["attrs"]["row"]))
    attrs.update(extra or {})
    edges.append(link("MENTIONS", cid, event_id))
    edges.append(link("PRODUCED", run, cid))
    return cid, {"id": cid, "type": "Claim", "attrs": attrs}, edges


def _need_run(store: GraphStore, run: str) -> None:
    n = store.node(run)
    if n is None or n["type"] != "AgentRun":
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")


def thrown_task(ev_node: dict, run: str, why: str, returned, key, what: str) -> tuple[dict, dict]:
    tid = "task:thrown-out:" + sha([run, ev_node["id"], what, key, returned])
    node = {"id": tid, "type": "Task", "attrs": {
        "text": f"A {what} returned for {ev_node['id']} was not written as a claim: {why}.",
        "state": "blocked", "reason": why, "returned": returned, "source": ev_node["attrs"]["source"],
        "about": ev_node["id"]}}
    return node, link("PRODUCED", run, tid)


def load_worker_result(store: GraphStore, result: dict, run: str, *, cutoff: float = 0.7) -> dict:
    """Write what one worker returned. `run` is its AgentRun (it must already be in the graph)."""
    _need_run(store, run)
    if not isinstance(result, dict) or not isinstance(result.get("event"), str):
        raise schema.Refused("a worker's answer names its event: {\"event\": \"dipole:...\", \"claims\": [...]}")
    ctx = event_context(store, result["event"])
    ev = ctx["event"]
    returned = result.get("claims")
    if not isinstance(returned, list):
        raise schema.Refused("a worker's answer has a list of claims")
    nodes, edges, written, report = [], [], {}, {
        "event": ev["id"], "returned": len(returned), "claims_written": 0, "thrown_out": 0,
        "sent_to_review": 0, "held_under_the_cutoff": 0, "claims": [], "thrown": []}
    seen_ids = set()
    for i, c in enumerate(returned):
        why, prep = prepare_claim(ctx, c, written)
        if not why:
            cid, node, es = claim_nodes(store, ctx, prep, c, run, cutoff)
            if cid in seen_ids:
                why = "the same claim (same cells, same text) is already written from this answer"
        if why:
            t, e = thrown_task(ev, run, why, c, i, "claim")
            nodes.append(t)
            edges.append(e)
            report["thrown_out"] += 1
            report["thrown"].append({"k": c.get("k") if isinstance(c, dict) else None, "reason": why})
            continue
        seen_ids.add(cid)
        written[prep["k"]] = {"id": cid, "cells": set(prep["cells"]), "inference": prep["inference"]}
        nodes.append(node)
        edges += es
        report["claims_written"] += 1
        report["sent_to_review" if node["attrs"]["review"] == SENT else "held_under_the_cutoff"] += 1
        report["claims"].append({"k": prep["k"], "id": cid, "review": node["attrs"]["review"]})
    store.write(nodes, edges, written_by=code_stamp("tools.swarm.reduce"))
    return report


# ---- what goes to review, and the synthesis -------------------------------------------------------

def _claims_of(store: GraphStore, event_id: str) -> list[dict]:
    out = [c for c in store.nodes("Claim") if c["attrs"].get("about") == event_id]
    out.sort(key=lambda c: (c["attrs"].get("claim_k") or 0, c["id"]))
    return out


def review_set(store: GraphStore, event_ids: list[str], cutoff: float) -> list[str]:
    """The claims sent to review: a worker's claims of these events with a confidence of the cutoff or
    more, event by event in the order given. A counter-statement of the refute wave is not sent again."""
    out = []
    for ev in event_ids:
        for c in _claims_of(store, ev):
            a = c["attrs"]
            if a.get("counter_to") or a.get("confidence") is None:
                continue
            if a["confidence"] >= cutoff:
                out.append(c["id"])
    return out


def synthesis(store: GraphStore, event_ids: list[str]) -> str:
    """Each event on its own: its claims sent to review, each with its id, the id of its SUPPORTS or
    DERIVED_FROM link and the ids of the Evaluations of it. A claim with a CONTRADICTS link is listed
    with the claim that contradicts it. Nothing is added up across events or claims."""
    ed_in: dict[str, list[dict]] = {}
    for e in store.edges():
        if e["type"] in ("SUPPORTS", "DERIVED_FROM", "EVALUATES", "CONTRADICTS"):
            key = e["src"] if e["type"] == "DERIVED_FROM" else e["dst"]
            ed_in.setdefault(key, []).append(e)
    out = []
    for ev in event_ids:
        node = store.node(ev)
        a = node["attrs"]
        out.append(f"== {ev} (trade day {a['trade_day']}, sheet {a['sheet']!r}, row {a['row']}) ==")
        claims = _claims_of(store, ev)
        counters = {c["id"]: c for c in claims if c["attrs"].get("counter_to")}
        held = []
        for c in claims:
            at = c["attrs"]
            if at.get("counter_to"):
                continue
            if at["review"] != SENT:
                held.append(c["id"])
                continue
            links = [e["id"] for e in ed_in.get(c["id"], []) if e["type"] == "SUPPORTS"]
            links += [e["id"] for e in store.edges("DERIVED_FROM") if e["src"] == c["id"]]
            evals = [e["src"] for e in ed_in.get(c["id"], []) if e["type"] == "EVALUATES"]
            kind = "an inference" if at["inference"] else "cells of " + str(at.get("cited_node"))
            out.append(f"claim {c['id']} | {at['text']} | {kind} | confidence {at['confidence']}")
            out.append(f"    link {', '.join(sorted(links)) or 'none'} | evaluations {', '.join(sorted(evals)) or 'none'}")
            for e in ed_in.get(c["id"], []):
                if e["type"] == "CONTRADICTS" and e["src"] in counters:
                    cc = counters[e["src"]]
                    out.append(f"    contradicted by claim {cc['id']} | {cc['attrs']['text']} | "
                               f"cells of {cc['attrs'].get('cited_node')} | link {e['id']}")
        if held:
            out.append("    held under the cutoff (kept in the graph, not sent): " + ", ".join(held))
        out.append("")
    return "\n".join(out)
