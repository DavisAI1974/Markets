"""decider_v1: a written decider. One function, `decide(packet)`, take or skip, from the packet alone.

Pure: standard library only, no file, no clock, no store. It never raises. Taking is the default (the platform
today takes every signal); a skip always names its ground, one of four conditions below, each with what it rests
on written directly above it. The hold and the exit are not decided here. Nothing here was scored.
"""

import json
import re

TAKE_WHY = "no ground in the packet to skip; the rule's own signal stands"

# Rules whose SIDE text says "with" the move or the step the quote just made, so the price's drift has the
# trade's own sign. Each from its SIDE line: CL01 "BUY for the best offer up"; CL03 "BUY for the best offer up";
# CL06 "BUY when both stepped up"; CL10 "With the price"; CL13 "BUY when a buyer paid up"; CL15 "the ORIGINAL
# direction"; CL16 "with the step". Rules that read the dipole or exhaustion themselves (CL05, CL07, CL08) and
# rules that enter before a move or against it (CL02, CL04, CL09, CL11, CL12, CL14, CL17, CX*) are left out.
WITH_THE_MOVE = ("CL01", "CL03", "CL06", "CL10", "CL13", "CL15", "CL16")

# "strong divergence (<= -0.20)": Markets CLAUDE.md, "Dipole research (standing)", DIVERGENCE.
STRONG_DIVERGENCE = -0.20

_FIELD = re.compile(r"(?:^|; )(\w+)=")


def _fields(text):
    """The `name=value` pairs of a packet line (after its first ' | ')."""
    body = text.split(" | ", 1)[1] if " | " in text else text
    marks = list(_FIELD.finditer(body))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out[m.group(1)] = body[m.end():end].strip()
    return out


def _take(why_extra, packet_lines=()):
    why = TAKE_WHY + (f" ({why_extra})" if why_extra else "")
    ids = [l["source"] for l in packet_lines if isinstance(l, dict) and l.get("source")]
    return {"action": "take", "why": why, "rests_on": ids}


def _skip(why, ids):
    return {"action": "skip", "why": why, "rests_on": list(dict.fromkeys(ids))}


def _order(line):
    return (line.get("known_at_ns") or 0, line.get("sequence") or 0)


def decide(packet):
    try:
        return _decide(packet)
    except Exception as e:  # a packet this reader cannot read gives the plain take, with the reason said
        return {"action": "take", "why": f"{TAKE_WHY} (the packet could not be read: {type(e).__name__})",
                "rests_on": []}


def _decide(packet):
    lines = [l for l in packet.get("lines", []) if isinstance(l, dict) and l.get("text") and l.get("source")]
    sig = next((l for l in lines if l.get("section") == "signal"), None)
    if sig is None:
        return {"action": "take", "why": f"{TAKE_WHY} (the packet holds no signal line)", "rests_on": []}
    f = _fields(sig["text"])
    side = f.get("side")
    sig_id = sig["source"]
    rule = f.get("rule") or packet.get("rule")
    rows = [(l, _fields(l["text"])) for l in lines if l.get("row_kind") in ("signal", "paper order", "fill")]

    # CONDITION 1, a standing warning against adding on this side.
    # Rests on: CX13 "Suspend additions to the upward position" (released "if the bid first rises above q's
    # bid or exhaustion becomes nonnegative", ended by "an exit"); CX14 the same for the downward position.
    # A warning stands while the newest row of its trade_id is still its 'suspend additions' row. Applying it
    # to an opening signal of ANY rule on that side is an INFERENCE (the texts name the position they warn on).
    for ln, g in rows:
        if g.get("action") == "suspend additions" and g.get("side") == side and g.get("trade_id"):
            same = [l for l, h in rows if h.get("trade_id") == g["trade_id"]]
            if max(same, key=_order) is ln:
                return _skip(f"[suspended-additions] {g.get('rule')} suspended additions on the {side} side and "
                             "has not released or ended that warning.", [sig_id, ln["source"]])

    # CONDITION 2, a second opening of the same run of the quote by the same rule.
    # Rests on: CL16 "The same run of the quote never opens a second trade"; the rules' "OPENS AGAIN: at the
    # next run's start" (CL03, CL09) or "at the next run's second step" (CL01, CL02, CL10, CL11).
    # The run and quote come from the signal's journaled conditions.
    cond = _json(f.get("conditions"))
    if isinstance(cond, dict) and cond.get("run") is not None and cond.get("quote") is not None:
        for ln, g in rows:
            if ln.get("section") == "same_rule" and g.get("action") == "open" and g.get("rule") == rule:
                c2 = _json(g.get("conditions"))
                if isinstance(c2, dict) and c2.get("run") == cond["run"] and c2.get("quote") == cond["quote"]:
                    return _skip(f"[same-run] {rule} already opened a trade on run {cond['run']} of the "
                                 f"{cond['quote']}, and its text opens again only at the next run.",
                                 [sig_id, ln["source"]])

    # CONDITION 3, a quote that is crossed or locked at the signal.
    # Rests on: CL06 "Not while the best offer is at or below the best bid". Using it for every rule is an
    # INFERENCE (only CL06's text says it).
    bid, ask = _int(f.get("bid")), _int(f.get("ask"))
    if bid is not None and ask is not None and ask <= bid:
        return _skip(f"[crossed-quote] the best offer {ask} is at or below the best bid {bid} at the signal.",
                     [sig_id])

    # CONDITION 4, strong divergence on an entry made with the move.
    # Rests on: Markets CLAUDE.md "Dipole research (standing)": DIVERGENCE, "aligned_flow = imb_level x
    # sign(price_drift); strong divergence (<= -0.20) -> ~65% reversal"; the rule's SIDE text puts the drift's
    # sign on the trade's side for the rules in WITH_THE_MOVE. INFERENCES: that the 20-second flow carried on
    # the newest known dipole event (bought - sold over bought + sold, the 2026-11-23 formula) stands for the
    # line now, and that -0.20 is on that scale (CLAUDE.md does not state the scale of imb_level).
    if rule in WITH_THE_MOVE and side in ("buy", "sell"):
        dip = [l for l in lines if l.get("section") == "dipoles"]
        if dip:
            newest = max(dip, key=lambda l: l.get("known_at_ns") or 0)
            d = _fields(newest["text"])
            bought, sold = _num(d.get("our_flow_bought_20s_after")), _num(d.get("our_flow_sold_20s_after"))
            if bought is not None and sold is not None and bought + sold > 0:
                aligned = (bought - sold) / (bought + sold) * (1 if side == "buy" else -1)
                if aligned <= STRONG_DIVERGENCE:
                    return _skip(f"[divergence] {rule} goes {side} with the move while the 20-second flow of the "
                                 f"newest known dipole event ({bought} bought, {sold} sold) runs against it "
                                 f"(aligned flow {aligned:.2f}).", [sig_id, newest["source"]])

    rule_line = next((l for l in lines if l.get("section") == "rule"), None)
    out = _take("", [sig] + ([rule_line] if rule_line else []))
    return out


def _json(s):
    try:
        return json.loads(s) if s else None
    except ValueError:
        return None


def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
