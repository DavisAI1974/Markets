"""What one worker reads for one dipole event: taken from the saved graph, no model, no tick.

The event's own node (every pinned cell as stored), its trade day, the dipole just before it and just
after it on the same trade day (by birth time), and every Peak of that trade day whose `high_eastern`
lies from the earlier neighbour's `born_eastern` to the later neighbour's `born_eastern`, both ends
included. At the first or last dipole of a trade day the span runs to the first or last peak of the
trade day. The span is set by the neighbouring events, never by a number of seconds or rows (Greg:
no predetermined windows).

A worker is the researcher of the four trade days, so it reads every stored column; this is not
Frankie's packet and nothing is hidden here.
"""

from __future__ import annotations

import bisect
import json
import math

from tools.kgraph.store import GraphStore

# ---- the instructions -------------------------------------------------------------------------

WORKER_SYSTEM = """You are a WORKER of DavisAI Markets: the researcher of ONE natural gas dipole event on one trade day.
You are given the stored cells of the event, of the dipole just before it, of the dipole just after it, and
of every peak between those two dipoles' birth times. Every cell is one line:
  <n>| <node id> | <column> = <value>
You state what the cells say. You do not trade, forecast, grade or compare events. Return JSON only, no
words around it.

Return: {"event": "<the event's node id>", "claims": [ ... ]}
Each claim has exactly these fields:
- "k": 1, 2, 3 ... in the order you write them.
- "cells": the numbers n of the cells it stands on (a list; an empty list for an inference).
- "text": one plain sentence that can be read alone.
- "statement_kind": "measurement" (a stored figure), "state" (what a stored cell says is the case) or
  "definition" (what a stored column or value means, only as the cells themselves say).
- "inference": false or true.
- "rests_on": the k of earlier claims an inference stands on (a list; empty for a claim that is not one).
- "confidence": a number from 0 to 1, how sure you are that the sentence is right.

Rules (a claim that breaks one is thrown out by code and kept as a note; it is not believed):
1. A claim that is NOT an inference cites cells of ONE node only (one row of one sheet). Every number in its
   text is copied exactly as the cell stores it (a cell value of 0.1461538461538462 is written
   0.1461538461538462, not 0.146) and is the value of one of the cells it cites. Write a column by its exact
   stored name. Never write the cell numbers n in a text.
2. A sentence that combines several nodes (the event and a neighbour, the event and a peak), or reads a
   meaning into the cells, is an INFERENCE. It cites no cells; it lists in "rests_on" the earlier claims of
   this answer it stands on, and every number in its text is a number of the cells those claims cite.
3. No averages, sums, counts, ranks or differences made by you, and no labels such as winner, loser, strong,
   weak, best, worst. A figure the cells do not store is not written.
4. No trade, fee, price target or execution idea. The numbers are gross stored figures.
5. Say it when you are less sure: give a confidence under 0.7 for a sentence you are not sure of.
6. Write between 6 and 12 claims, one fact each. A cell with the value null is a stored null; you may say
   so (the sentence names the column and says no value is stored).
"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "event": {"type": "string"},
        "claims": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "k": {"type": "integer"},
                "cells": {"type": "array", "items": {"type": "integer"}},
                "text": {"type": "string"},
                "statement_kind": {"type": "string", "enum": ["measurement", "state", "definition"]},
                "inference": {"type": "boolean"},
                "rests_on": {"type": "array", "items": {"type": "integer"}},
                "confidence": {"type": "number"},
            },
            "required": ["k", "cells", "text", "statement_kind", "inference", "rests_on", "confidence"],
            "additionalProperties": False}},
    },
    "required": ["event", "claims"],
    "additionalProperties": False,
}


# ---- the index of dipoles and peaks of each trade day -----------------------------------------

def _index(store: GraphStore) -> dict:
    """Dipoles by trade day (by birth, then id) and peaks by trade day (by time, then position).
    Built once for a store; the saved events and peaks do not change during a run."""
    idx = getattr(store, "_swarm_index", None)
    if idx is not None:
        return idx
    dips: dict[str, list] = {}
    for n in store.nodes("DipoleEvent"):
        dips.setdefault(n["attrs"]["trade_day"], []).append(n)
    for d in dips.values():
        d.sort(key=lambda n: (n["attrs"]["birth_ns"], n["id"]))
    peaks: dict[str, list] = {}
    for n in store.nodes("Peak"):
        peaks.setdefault(n["attrs"]["trade_day"], []).append(n)
    keys: dict[str, list] = {}
    for day, p in peaks.items():
        p.sort(key=lambda n: (n["attrs"]["high_eastern"], n["attrs"]["position_on_tape"]))
        keys[day] = [n["attrs"]["high_eastern"] for n in p]
    idx = {"dipoles": dips, "peaks": peaks, "peak_keys": keys,
           "position": {n["id"]: (day, i) for day, d in dips.items() for i, n in enumerate(d)}}
    store._swarm_index = idx
    return idx


def event_ids(store: GraphStore, trade_day: str) -> list[str]:
    """The dipole events of one trade day, in birth order."""
    return [n["id"] for n in _index(store)["dipoles"].get(trade_day, [])]


def event_layers(store: GraphStore, dipole_id: str) -> dict:
    idx = _index(store)
    if dipole_id not in idx["position"]:
        raise KeyError(f"{dipole_id} is not a DipoleEvent of the graph")
    day, i = idx["position"][dipole_id]
    dips = idx["dipoles"][day]
    me = dips[i]
    before = dips[i - 1] if i > 0 else None
    after = dips[i + 1] if i + 1 < len(dips) else None
    peaks = idx["peaks"].get(day, [])
    keys = idx["peak_keys"].get(day, [])
    lo_t = before["attrs"]["pinned"]["born_eastern"] if before else None
    hi_t = after["attrs"]["pinned"]["born_eastern"] if after else None
    a = 0 if lo_t is None else bisect.bisect_left(keys, lo_t)
    b = len(peaks) if hi_t is None else bisect.bisect_right(keys, hi_t)
    td = store.node(f"tradeday:{day}")
    return {
        "event": me, "trade_day": td, "before": before, "after": after,
        "peaks": peaks[a:b],
        "span": {"from_born_eastern": lo_t, "to_born_eastern": hi_t,
                 "from": ("the born_eastern of the dipole just before" if before else "the first peak of the trade day"),
                 "to": ("the born_eastern of the dipole just after" if after else "the last peak of the trade day")},
    }


# ---- the cells --------------------------------------------------------------------------------

def render(value) -> str:
    """A stored cell value as written in the brief and in a quote: JSON, so a string keeps its quotes
    and null, true and false are as stored."""
    return json.dumps(value, ensure_ascii=False)


def _nodes_in_order(layers: dict) -> list[tuple[str, dict]]:
    out = [("the event", layers["event"])]
    if layers["before"]:
        out.append(("the dipole just before", layers["before"]))
    if layers["after"]:
        out.append(("the dipole just after", layers["after"]))
    out += [("a peak in the span", p) for p in layers["peaks"]]
    return out


def cells(layers: dict) -> list[dict]:
    """The layers as numbered cells, in a fixed order: the event, the dipole before, the dipole after,
    then the peaks by time; within a node the columns in the order the graph file keeps them (by column
    name: the store writes its lines with sorted keys), the same every time."""
    out, n = [], 0
    for _role, node in _nodes_in_order(layers):
        for col, val in node["attrs"]["pinned"].items():
            n += 1
            out.append({"n": n, "node": node["id"], "sheet": node["attrs"]["sheet"],
                        "row": node["attrs"]["row"], "column": col, "value": val})
    return out


def build_brief_parts(layers: dict) -> tuple[str, str]:
    """(the worker's instructions, the cells). The instructions never change, so they can sit in the
    system prompt; the cells are the user's message."""
    td = layers["trade_day"]["attrs"] if layers["trade_day"] else {}
    head = [f"EVENT: {layers['event']['id']}",
            f"TRADE DAY: {td.get('date')} (from {td.get('starts_et')} to {td.get('ends_et')}; context only, not a cell)",
            f"PEAKS: every peak of this trade day whose high_eastern lies from {layers['span']['from']}"
            f" ({layers['span']['from_born_eastern']}) to {layers['span']['to']} ({layers['span']['to_born_eastern']}),"
            " both ends included."]
    body, n = [], 0
    for role, node in _nodes_in_order(layers):
        a = node["attrs"]
        body.append(f"--- {role}: {node['id']} (sheet {a['sheet']!r}, row {a['row']}) ---")
        for col, val in a["pinned"].items():
            n += 1
            body.append(f"{n}| {node['id']} | {col} = {render(val)}")
    return WORKER_SYSTEM, "\n".join(head + [""] + body + ["", "Return the JSON now."])


def build_brief(layers: dict) -> str:
    s, u = build_brief_parts(layers)
    return s + "\n\n" + u


def estimate_tokens(text: str) -> int:
    """An ESTIMATE: characters divided by four, rounded up. It is not a count; the model's own usage
    figure is the measured one."""
    return math.ceil(len(text) / 4)
