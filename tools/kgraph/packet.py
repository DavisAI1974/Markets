"""Stage 5b: Frankie's packet built from the graph: the opt-in input path `graph_v1`.

BUILT BESIDE the current path (`stacked_v1`), NOT SWITCHED ON. Nothing of Frankie calls this module
and nothing here changes Frankie's inputs, calculations, planes, adapter or replay. Switching his
input to it is Greg's decision alone.

What a `graph_v1` packet is: for one dipole event, at the moment the event is made known, the event
itself and the earlier events of its trade day, read from the knowledge graph, newest first, within a
declared token budget, each line carrying the node id it came from.

THE RULE THAT GOVERNS IT: nothing that could only be known after the event's own moment may be in its
packet. So:
  - only events made known BEFORE the anchor's moment (`native_known_second_ns`) are in it;
  - only the columns in KNOWN_AT_THE_MOMENT are shown. It is an allow-list: a column that is not on it
    is hidden, so a column added to the workbook later stays hidden until someone puts it on the list.
    The columns that describe what happened after the event (the `_after` columns, the seconds to
    the next dipole, the picture made afterwards) are the answer key and are never shown;
  - no peak is in it: the graph holds the time of a peak's high, not the time the peak became
    known, and a peak is known later than its high. Until that time is in the graph, peaks stay out;
  - no claim read from a handoff or a note is in it: those were written after the four trade days.
`leakage_check` verifies a packet against the rule, and the checks build each packet twice, once
from a graph with the future taken away, and require the same text.

Which columns are known at the moment is Claude's reading of the workbook's column names, Greg's to
strike. Anchoring a packet on a dipole event (Frankie's current packet is cut by rows up to a cursor)
is also Claude's reading: it is what the graph holds today.

The side by side against stacked_v1 (plan 5b) is NOT made here and no saving is claimed: stacked_v1's
code is on Markets branch `ccr-d2f8f826-iefeah-frankie`, running it is under HOLD, and the one figure
on record for it (92,427 input tokens at 3,262 rows) is for a different moment. `compare` writes the
two down beside each other and says they are not comparable. The loop that would shrink the packet
has its control file (LOOP_PROGRAM) with no figure chosen: that choice is Greg's.

  python3 -m tools.kgraph.packet --event dipole:dip-19632-1696206142 --budget 4000 [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .store import GraphStore, edge_id

PATH_NAME = "graph_v1"
CHARS_PER_TOKEN = 4
LOOP_PROGRAM = Path(__file__).resolve().parents[1] / "ratchet" / "programs" / "packet_graph_v1.md"

# Columns of the "dipoles <trade day>" sheets that are known when the event is made known.
KNOWN_AT_THE_MOMENT = (
    "born_eastern", "dipole", "native_polarity", "native_birth_ns", "native_known_second_ns",
    "native_magnitude", "native_threshold", "native_baseline", "native_prominence",
    "first_position_in_birth_second", "last_position_in_birth_second", "ticks_in_birth_second",
    "trades_in_birth_second", "bought_in_birth_second", "sold_in_birth_second", "no_side_in_birth_second",
    "our_flow_bought_20s_before", "our_flow_sold_20s_before", "seconds_since_dipole_before",
)
STACKED_V1_ON_RECORD = {
    "rows": 3262, "input_tokens": 92427,
    "source": "Markets CLAUDE.md, 'Token figures': the proven packet is 92,427 input tokens at 3,262 rows (stacked_v1)",
}


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _known_ns(node: dict) -> int:
    return int(node["attrs"]["pinned"]["native_known_second_ns"])


def _line(node: dict) -> str:
    pinned = node["attrs"]["pinned"]
    return node["id"] + " | " + "; ".join(f"{c}={pinned[c]}" for c in KNOWN_AT_THE_MOMENT if c in pinned)


def build_packet(store: GraphStore, dipole_id: str, budget_tokens: int) -> dict:
    anchor = store.node(dipole_id)
    if anchor is None or anchor["type"] != "DipoleEvent":
        raise ValueError(f"{dipole_id} is not a dipole event of the graph")
    day, known = anchor["attrs"]["trade_day"], _known_ns(anchor)
    hidden = sorted(c for c in anchor["attrs"]["pinned"] if c not in KNOWN_AT_THE_MOMENT)
    earlier = [n for n in store.nodes("DipoleEvent")
               if n["attrs"]["trade_day"] == day and n["id"] != dipole_id and _known_ns(n) < known]
    earlier.sort(key=lambda n: (_known_ns(n), n["id"]), reverse=True)        # newest first

    head = [f"PACKET {PATH_NAME} | anchor {dipole_id} | trade day {day} | made known at {known} ns",
            "Each line: node id | <column>=<value>; ... Only what was known before the anchor's moment is here.",
            "THE EVENT:", _line(anchor), "EARLIER EVENTS OF THE TRADE DAY, NEWEST FIRST:"]

    def foot(cut: int) -> list[str]:
        return ["NOT IN THIS PACKET:",
                f"- {cut} earlier events are not shown for want of budget (the oldest are cut first).",
                "- every event made known at or after the anchor's moment.",
                "- the columns that describe what happened afterwards: " + ", ".join(hidden) + ".",
                "- peaks: the graph does not hold the time a peak became known.",
                "- claims read from handoffs and notes: they were written after the trade days."]

    budget_chars = budget_tokens * CHARS_PER_TOKEN
    used = len("\n".join(head + foot(len(earlier)))) + 2
    shown = []
    for n in earlier:
        ln = _line(n)
        if used + len(ln) + 1 > budget_chars:
            break
        shown.append(n)
        used += len(ln) + 1
    cut = earlier[len(shown):]
    text = "\n".join(head + [_line(n) for n in shown] + foot(len(cut))) + "\n"
    included = [dipole_id] + [n["id"] for n in shown]
    return {
        "path": PATH_NAME, "anchor": dipole_id, "trade_day": day, "known_ns": known, "text": text,
        "rows": len(included), "tokens_estimated": estimate_tokens(text), "budget_tokens": budget_tokens,
        "included": included, "cut": [n["id"] for n in cut], "hidden_columns": hidden,
        "left_out": {"later_events": "all", "peaks": "all: no known-time in the graph", "document_claims": "all"},
        # the link each line can be cited by: the event's PINNED_AT link to its trade day
        "citations": {i: edge_id("PINNED_AT", i, f"tradeday:{day}") for i in included},
    }


def leakage_check(store: GraphStore, packet: dict) -> list[str]:
    """Every breach of the rule in a built packet, one line each. Empty when there is none."""
    out = []
    for nid in packet["included"]:
        node = store.node(nid)
        if node is None:
            out.append(f"{nid} is in the packet and not in the graph")
        elif nid != packet["anchor"] and _known_ns(node) >= packet["known_ns"]:
            out.append(f"{nid} was made known at {_known_ns(node)}, not before the anchor's moment {packet['known_ns']}")
        elif node["attrs"]["trade_day"] != packet["trade_day"]:
            out.append(f"{nid} is of trade day {node['attrs']['trade_day']}, not {packet['trade_day']}")
    body = packet["text"].split("NOT IN THIS PACKET")[0]
    for col in packet["hidden_columns"]:
        if col in body:
            out.append(f"the hidden column {col} is in the packet's body")
    if packet["tokens_estimated"] > packet["budget_tokens"]:
        out.append(f"the packet is {packet['tokens_estimated']} estimated tokens, over its budget {packet['budget_tokens']}")
    return out


def compare(packet: dict) -> dict:
    """The graph packet and the one figure on record for stacked_v1, written down beside each other.
    They are not the same moment through two paths, so nothing is worked out from the pair."""
    return {
        PATH_NAME: {"anchor": packet["anchor"], "rows": packet["rows"], "tokens_estimated": packet["tokens_estimated"],
                    "note": f"estimated at {CHARS_PER_TOKEN} characters a token; rows are dipole events, one a line"},
        "stacked_v1": dict(STACKED_V1_ON_RECORD, note="rows are native context rows; counted by Granite's tokenizer"),
        "comparable": False,
        "why_not": "the two figures are not the same moment through both paths, the rows are different things and "
                   "the tokens were counted two ways. A side by side needs stacked_v1 built for the same moment, "
                   "which is on another branch and under HOLD.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--graph-dir")
    ap.add_argument("--event", required=True)
    ap.add_argument("--budget", type=int, required=True, help="tokens")
    ap.add_argument("--json", action="store_true", help="print the figures as one JSON line (for the loop harness)")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    p = build_packet(store, a.event, a.budget)
    breaches = leakage_check(store, p)
    if breaches:
        print("\n".join(breaches), file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps({"anchor": p["anchor"], "rows": p["rows"], "tokens_estimated": p["tokens_estimated"],
                          "cut": len(p["cut"]), "leakage_breaches": 0}))
    else:
        sys.stdout.write(p["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
