"""Stage 5b: Frankie's packet built from the graph: the opt-in input path `graph_v1`.

BUILT BESIDE the current path (`stacked_v1`), NOT SWITCHED ON. Nothing of Frankie calls this module
and nothing here changes Frankie's inputs, calculations, planes, adapter or replay. Switching his
input to it is Greg's decision alone.

What a `graph_v1` packet is: for one dipole event, at the event's moment, the event itself and the
earlier events of its trade day, read from the knowledge graph, newest first, within a declared token
budget, each line carrying the node id it came from.

THE MOMENT is `native_known_second_ns`: the start of the second from which Native says the event can
be known. It is NOT the time Native's line for the event was written, which the graph does not hold.
The reviewer of run 35 measured that line written 1.0 to 107.8 seconds after this second on the four
trade days, and before it in two cases; ordered by either time the events come in the same order
(markets-data graph/reviews/review-notes-20261124.md, F2.2). A packet is therefore what could be shown
no earlier than this second; when the writing time is in the graph, the moment should be that time.

THE RULE THAT GOVERNS IT: nothing that could only be known after the event's own moment may be in its
packet. So:
  - only events made known BEFORE the anchor's moment are in it;
  - only the columns in SHOWN are shown. It is an allow-list: a column that is in none of the three
    groups below is hidden and named as not placed, so a column added to the workbook later stays
    hidden until someone places it. Every column is in exactly one group, with the reason:
      SHOWN       known at the moment, and why (the birth second's ticks are complete one second after
                  the birth, and every event of the four trade days is made known 6 to 50 seconds
                  after its birth; the check asserts it on every included event);
      HELD_BACK   Native's polarity, magnitude, threshold, baseline and prominence, and the one column
                  made from the polarity. Native works them out at the known second by its own
                  note, and the line that carries them (the closing line) was written 4 to 1,028
                  seconds later on the four trade days (the same review, F2.1). Which reading governs
                  is Greg's to say; until he does they are not shown;
      AFTERWARDS  what happened after the event (the seconds to the next dipole, the picture): the
                  answer key, never shown;
  - `seconds_since_dipole_before` is shown on a line only when the dipole before it by birth was
    itself made known before the anchor's moment (on the four trade days it always was);
  - no peak is in it: the graph holds the time of a peak's high, not the time the peak became
    known, and a peak is known later than its high. Until that time is in the graph, peaks stay out;
  - no claim read from a handoff or a note is in it: those were written after the four trade days.

`leakage_check` verifies a built packet against the rule: which events are in it, that each one's birth
second had ended, that every `column=value` on a line is a SHOWN column carrying that event's own
stored cell (so a later cell under an allowed name is caught), and the budget.
WHAT IT CANNOT SEE: whether a stored cell was itself worked out with later ticks. That is the prefix
invariance of the calculation that made the column, and it is checked where the column is made (ROOT),
not here.

Anchoring a packet on a dipole event (Frankie's current packet is cut by rows up to a cursor) is
Claude's reading: it is what the graph holds today. Greg's to strike.

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

NS_PER_SECOND = 10**9
GAP_COLUMN = "seconds_since_dipole_before"

# Every column of the "dipoles <trade day>" sheets (root/dipole_renders.py, PIN_COLUMNS) is in exactly
# one of the three groups, with the reason. The order of SHOWN is the order of a line.
_OWN = "the event's own name and times, known when it is made known"
_BIRTH = ("counted on the ticks of the birth second, which is complete one second after the birth "
          "(root/dipole_renders.py, pin: the ticks from the birth to the birth plus one second)")
_FLOW_BEFORE = "our 20-second flow on the last tick received before the birth second"
_FLOW_END = ("our 20-second flow on the last tick received before the END of the birth second; the "
             "'after' in the name is after the birth second, not after the event was made known")
SHOWN = {
    "born_eastern": _OWN, "dipole": _OWN, "native_birth_ns": _OWN, "native_known_second_ns": _OWN,
    "first_position_in_birth_second": _BIRTH, "last_position_in_birth_second": _BIRTH,
    "ticks_in_birth_second": _BIRTH, "trades_in_birth_second": _BIRTH, "bought_in_birth_second": _BIRTH,
    "sold_in_birth_second": _BIRTH, "no_side_in_birth_second": _BIRTH,
    "our_flow_bought_20s_before": _FLOW_BEFORE, "our_flow_sold_20s_before": _FLOW_BEFORE,
    "our_flow_bought_20s_after": _FLOW_END, "our_flow_sold_20s_after": _FLOW_END,
    "our_flow_fully_one_sided_after": _FLOW_END,
    GAP_COLUMN: "the birth of the dipole before to this birth; shown on a line only when that dipole "
                "was itself made known before the anchor's moment",
}
_NATIVE_LATER = ("Native works it out at the known second by its own note; the line that carries it (the "
                 "closing line) was written later. Which reading governs is Greg's to say")
HELD_BACK = {
    "native_polarity": _NATIVE_LATER, "native_magnitude": _NATIVE_LATER, "native_threshold": _NATIVE_LATER,
    "native_baseline": _NATIVE_LATER, "native_prominence": _NATIVE_LATER,
    "our_flow_on_native_side_after": "made from Native's polarity, so it follows the polarity",
}
AFTERWARDS = {
    "seconds_to_dipole_after": "the birth of the next dipole is later than this event",
    "render": "the picture was made afterwards and shows what followed",
}
KNOWN_AT_THE_MOMENT = tuple(SHOWN)
STACKED_V1_ON_RECORD = {
    "rows": 3262, "input_tokens": 92427,
    "source": "Markets CLAUDE.md, 'Token figures': the proven packet is 92,427 input tokens at 3,262 rows (stacked_v1)",
}


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _known_ns(node: dict) -> int:
    return int(node["attrs"]["pinned"]["native_known_second_ns"])


def _birth_ns(node: dict) -> int:
    return int(node["attrs"]["pinned"]["native_birth_ns"])


def _before_by_birth(nodes: list[dict]) -> dict:
    """For each event of one trade day, the event born just before it (None for the first)."""
    order = sorted(nodes, key=lambda n: (_birth_ns(n), n["id"]))
    return {n["id"]: (order[i - 1] if i else None) for i, n in enumerate(order)}


def _gap_is_known(node: dict, before: dict, moment: int) -> bool:
    """The gap to the dipole before is known at `moment` when there is no dipole before, or when the
    dipole before was itself made known before `moment`."""
    prev = before.get(node["id"])
    return prev is None or _known_ns(prev) < moment


def _line(node: dict, before: dict, moment: int) -> str:
    pinned = node["attrs"]["pinned"]
    cols = [c for c in SHOWN if c in pinned and (c != GAP_COLUMN or _gap_is_known(node, before, moment))]
    return node["id"] + " | " + "; ".join(f"{c}={pinned[c]}" for c in cols)


def build_packet(store: GraphStore, dipole_id: str, budget_tokens: int) -> dict:
    anchor = store.node(dipole_id)
    if anchor is None or anchor["type"] != "DipoleEvent":
        raise ValueError(f"{dipole_id} is not a dipole event of the graph")
    day, known = anchor["attrs"]["trade_day"], _known_ns(anchor)
    of_day = [n for n in store.nodes("DipoleEvent") if n["attrs"]["trade_day"] == day]
    before = _before_by_birth(of_day)
    columns = sorted({c for n in of_day for c in n["attrs"]["pinned"]})
    held = [c for c in columns if c in HELD_BACK]
    after = [c for c in columns if c in AFTERWARDS]
    unplaced = [c for c in columns if c not in SHOWN and c not in HELD_BACK and c not in AFTERWARDS]
    earlier = [n for n in of_day if n["id"] != dipole_id and _known_ns(n) < known]
    earlier.sort(key=lambda n: (_known_ns(n), n["id"]), reverse=True)        # newest first

    head = [f"PACKET {PATH_NAME} | anchor {dipole_id} | trade day {day} | moment {known} ns "
            "(the start of the second from which Native says the event can be known)",
            "Each line: node id | <column>=<value>; ... Only what was known before the anchor's moment is here.",
            "THE EVENT:", _line(anchor, before, known), "EARLIER EVENTS OF THE TRADE DAY, NEWEST FIRST:"]

    def foot(cut: int, shown: list) -> list[str]:
        no_gap = [n["id"] for n in [anchor, *shown] if not _gap_is_known(n, before, known)]
        out = ["NOT IN THIS PACKET:",
               f"- {cut} earlier events are not shown for want of budget (the oldest are cut first).",
               "- every event made known at or after the anchor's moment.",
               "- held back until Greg says which reading governs (Native works them out at the known second; "
               "the line that carries them was written later): " + ", ".join(held) + ".",
               "- what happened afterwards, the answer key: " + ", ".join(after) + "."]
        if unplaced:
            out.append("- columns nobody has placed yet, hidden until someone does: " + ", ".join(unplaced) + ".")
        if no_gap:
            out.append(f"- {GAP_COLUMN} on {len(no_gap)} lines: the dipole before by birth was not yet made known.")
        out += ["- peaks: the graph does not hold the time a peak became known.",
                "- claims read from handoffs and notes: they were written after the trade days."]
        return out

    budget_chars = budget_tokens * CHARS_PER_TOKEN
    used = len("\n".join(head + foot(len(earlier), []))) + 2
    shown = []
    for n in earlier:
        ln = _line(n, before, known)
        if used + len(ln) + 1 > budget_chars:
            break
        shown.append(n)
        used += len(ln) + 1
    cut = earlier[len(shown):]
    text = "\n".join(head + [_line(n, before, known) for n in shown] + foot(len(cut), shown)) + "\n"
    included = [dipole_id] + [n["id"] for n in shown]
    return {
        "path": PATH_NAME, "anchor": dipole_id, "trade_day": day, "known_ns": known, "text": text,
        "rows": len(included), "tokens_estimated": estimate_tokens(text), "budget_tokens": budget_tokens,
        "included": included, "cut": [n["id"] for n in cut],
        "hidden_columns": sorted(held + after + unplaced), "held_back_columns": held, "after_columns": after,
        "unplaced_columns": unplaced,
        "gap_not_shown": [n["id"] for n in [anchor, *shown] if not _gap_is_known(n, before, known)],
        "left_out": {"later_events": "all", "peaks": "all: no known-time in the graph", "document_claims": "all"},
        # the link each line can be cited by: the event's PINNED_AT link to its trade day
        "citations": {i: edge_id("PINNED_AT", i, f"tradeday:{day}") for i in included},
    }


def leakage_check(store: GraphStore, packet: dict) -> list[str]:
    """Every breach of the rule in a built packet, one line each. Empty when there is none. It reads the
    packet's own text against the graph, so a text that was changed after it was built is caught too."""
    out = []
    moment, day = packet["known_ns"], packet["trade_day"]
    of_day = [n for n in store.nodes("DipoleEvent") if n["attrs"]["trade_day"] == day]
    before = _before_by_birth(of_day)
    for nid in packet["included"]:
        node = store.node(nid)
        if node is None:
            out.append(f"{nid} is in the packet and not in the graph")
            continue
        if nid != packet["anchor"] and _known_ns(node) >= moment:
            out.append(f"{nid} was made known at {_known_ns(node)}, not before the anchor's moment {moment}")
        if node["attrs"]["trade_day"] != day:
            out.append(f"{nid} is of trade day {node['attrs']['trade_day']}, not {day}")
        if _birth_ns(node) + NS_PER_SECOND > moment:
            out.append(f"{nid}: its birth second ends at {_birth_ns(node) + NS_PER_SECOND}, after the anchor's "
                       f"moment {moment}, so its birth-second columns were not complete")
    body = packet["text"].split("NOT IN THIS PACKET")[0]
    on_lines = set()
    for ln in body.splitlines():
        if not ln.startswith("dipole:") or " | " not in ln:
            continue
        nid, rest = ln.split(" | ", 1)
        on_lines.add(nid)
        node = store.node(nid)
        if nid not in packet["included"] or node is None:
            out.append(f"{nid} has a line in the packet and is not one of its events")
            continue
        pinned = node["attrs"]["pinned"]
        for pair in rest.split("; "):
            col, eq, value = pair.partition("=")
            if not eq or col not in SHOWN:
                out.append(f"{nid}: {col!r} is on its line and is not a column that may be shown")
            elif col not in pinned or value != f"{pinned[col]}":
                out.append(f"{nid}: {col}={value} is not that event's stored cell ({col}={pinned.get(col)})")
            elif col == GAP_COLUMN and not _gap_is_known(node, before, moment):
                out.append(f"{nid}: {GAP_COLUMN} is shown and the dipole before it by birth was not yet made known")
    for nid in packet["included"]:
        if nid not in on_lines:
            out.append(f"{nid} is listed as in the packet and has no line in it")
    for col in packet["hidden_columns"]:
        if col in body:
            out.append(f"the hidden column {col} is in the packet's body")
    if packet["tokens_estimated"] > packet["budget_tokens"] or estimate_tokens(packet["text"]) > packet["budget_tokens"]:
        out.append(f"the packet is {estimate_tokens(packet['text'])} estimated tokens, over its budget {packet['budget_tokens']}")
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
