"""8b. The five arms as data, each built from ONE baseline call. Nothing here sends anything.

  A  Sonnet, the call's own stored prompt (the current packet).
  B  Haiku for a call whose purpose is a "reading" one, Sonnet for a "reasoning" one, the stored prompt.
  C  arm B with graph-built context in place of the full packet: `context_fn(call) -> str`, handed in by the caller
     (stage 5b's packet.build_packet can sit behind it). With no function, C and the arms built on it (D, E) are
     reported as NOT BUILT for this run; the full packet is never sent under C's name.
  D  arm C with prompt caching: calls sharing a conversation id share a prefix. The prefix is the longest text
     that EVERY call of that conversation has in common at its start (cut at a line end), so nothing that
     changes from call to call can lie before the one `cache_control` breakpoint. A conversation of one call, or
     with nothing in common, gets no breakpoint and says why.
  E  the arm C or D request sent as a batch, for calls that do not need an answer inside the trading session
     (ROUTING says which); a call that is urgent, or whose purpose is not in the table, is never batched and is
     listed as set apart. The Batches API rejects `fallbacks`, so a batch request carries none.

Routing tables: PURPOSE_FAMILIES maps the call NAMES Granite's own code gives (file and line in
GRANITE_RECEIPT_FIELDS.md) to a family; ROUTING maps a family to kind (reading | reasoning) and urgent.
THE TABLES ARE CLAUDE'S READING OF GRANITE'S PURPOSES, GREG'S TO STRIKE. A purpose not in the table is treated as
reasoning, urgent, and listed in the plan as "purpose not in the table"; it is never guessed.

Request shape (checked against the Claude API reference, cached 2026-11-03): no temperature or top_p, no
prefill, no forced tool_choice, `thinking` left out (adaptive), `output_config={"effort": ...}` set explicitly.
Sonnet direct calls go through `client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default")`;
Haiku through plain `client.messages.create`.
"""

from __future__ import annotations

import re
from typing import Callable

from tools.token_test.baseline import load_prompt
from tools.token_test.prices import HAIKU, SONNET

FALLBACK_BETA = "server-side-fallback-2026-07-01"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 16000   # Granite's output was "the remaining context"; a Claude call needs a number. Declared in the plan.

ARMS = ("A", "B", "C", "D", "E")

# Granite's call names -> family. Each regex is one name shape the code builds (file:line in GRANITE_RECEIPT_FIELDS.md).
PURPOSE_FAMILIES = [
    (r"read-\d{4}.*", "read-part"),                              # frankie_box_boss_session.py:4783 (+ -retry, -a, -b: :4802, :4809)
    (r"merge-\d+-(final|\d{4}).*", "merge-notes"),               # :4703, :4719
    (r"granite-self-assessment", "self-assessment"),             # :5276
    (r"staged-[0-9a-f]{16}-.+", "classroom-staged-part"),        # frankie_box_staged_session.py:117
]
CRITIC_FAMILY = "shadow-critic"                                  # the spool writer: no name is recorded (granite_durable_job_client.py:124)

ROUTING = {
    "read-part":             {"kind": "reading",   "urgent": False},
    "merge-notes":           {"kind": "reading",   "urgent": False},
    "classroom-staged-part": {"kind": "reasoning", "urgent": False},
    "self-assessment":       {"kind": "reasoning", "urgent": False},
    CRITIC_FAMILY:           {"kind": "reasoning", "urgent": True},
}
ROUTING_NOTE = ("Claude's reading of Granite's purposes, Greg's to strike. A family not in this table is reasoning and "
                "urgent (never batched), listed as 'purpose not in the table'.")


def purpose_family(call: dict) -> str | None:
    """The family of the call's purpose, or None when it is not in the table (never guessed)."""
    name = call.get("purpose")
    if name is None:
        return CRITIC_FAMILY if call.get("writer") == "critic_spool" else None
    for rx, fam in PURPOSE_FAMILIES:
        if re.fullmatch(rx, name):
            return fam
    return None


def route(call: dict) -> dict:
    fam = purpose_family(call)
    if fam is None:
        return {"family": None, "kind": "reasoning", "urgent": True, "in_table": False,
                "note": "purpose not in the table"}
    r = ROUTING[fam]
    return {"family": fam, "kind": r["kind"], "urgent": r["urgent"], "in_table": True, "note": None}


def _request(arm, call, model, text_blocks, *, effort, max_tokens, cache, batch, rt, context_source, extra=None):
    content = [{"type": "text", "text": t} for t, _ in text_blocks]
    for blk, (_, mark) in zip(content, text_blocks):
        if mark:
            blk["cache_control"] = {"type": "ephemeral"}
    params = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": content}],
              "output_config": {"effort": effort}}
    d = {"arm": arm, "call_id": call["call_id"], "conversation_id": call.get("conversation_id"),
         "purpose": call.get("purpose"), "purpose_family": rt["family"], "route": rt,
         "model": model, "batch": batch, "cache": cache, "context_source": context_source,
         "params": params,
         # how it is to be sent: direct Sonnet through the beta endpoint with fallbacks, Haiku plain, batch none
         "send": ("batch" if batch else ("beta_fallback" if model == SONNET else "plain")),
         "betas": None if (batch or model != SONNET) else [FALLBACK_BETA],
         "fallbacks": None if (batch or model != SONNET) else "default"}
    if extra:
        d.update(extra)
    return d


def _common_prefix(texts: list[str]) -> str:
    if not texts:
        return ""
    a, b = min(texts), max(texts)
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    p = a[:i]
    cut = p.rfind("\n")
    return p[:cut + 1] if cut >= 0 else ""


def build_arms(calls: list[dict], arms=ARMS, *, context_fn: Callable[[dict], str] | None = None,
               effort: str = DEFAULT_EFFORT, max_tokens: int = DEFAULT_MAX_TOKENS, e_base: str = "D") -> dict:
    """For each wanted arm the requests, in the receipts' order, and what was not built and why.

    Returns {"requests": {arm: [request, ...]}, "not_built": {arm: reason}, "set_apart": {arm: [{call_id, reason}]},
             "not_in_table": [{call_id, purpose}]}.
    """
    if e_base not in ("C", "D"):
        raise ValueError("arm E is built on C or D")
    out = {"requests": {}, "not_built": {}, "set_apart": {}, "not_in_table": []}
    routes = {c["call_id"]: route(c) for c in calls}
    for c in calls:
        if not routes[c["call_id"]]["in_table"]:
            out["not_in_table"].append({"call_id": c["call_id"], "purpose": c.get("purpose"),
                                        "note": "purpose not in the table"})
    prompts = {c["call_id"]: load_prompt(c) for c in calls} if ("A" in arms or "B" in arms) else {}

    def model_b(c):
        return HAIKU if routes[c["call_id"]]["kind"] == "reading" else SONNET

    if "A" in arms:
        out["requests"]["A"] = [_request("A", c, SONNET, [(prompts[c["call_id"]], False)], effort=effort,
                                         max_tokens=max_tokens, cache=False, batch=False, rt=routes[c["call_id"]],
                                         context_source="the call's own stored prompt") for c in calls]
    if "B" in arms:
        out["requests"]["B"] = [_request("B", c, model_b(c), [(prompts[c["call_id"]], False)], effort=effort,
                                         max_tokens=max_tokens, cache=False, batch=False, rt=routes[c["call_id"]],
                                         context_source="the call's own stored prompt") for c in calls]
    wants_c = [a for a in ("C", "D", "E") if a in arms]
    if wants_c and context_fn is None:
        for a in wants_c:
            out["not_built"][a] = "not built for this run: no context_fn was given (arm C needs graph-built context; the full packet is never run under C's name)"
        return out
    if not wants_c:
        return out
    ctx = {c["call_id"]: context_fn(c) for c in calls}
    if any(not isinstance(v, str) or not v for v in ctx.values()):
        bad = [k for k, v in ctx.items() if not isinstance(v, str) or not v]
        raise ValueError(f"context_fn gave no text for call(s) {bad[:5]}; no context is made up")
    if "C" in arms:
        out["requests"]["C"] = [_request("C", c, model_b(c), [(ctx[c["call_id"]], False)], effort=effort,
                                         max_tokens=max_tokens, cache=False, batch=False, rt=routes[c["call_id"]],
                                         context_source="context_fn(call)") for c in calls]
    # D (and E when it rides on D): shared prefix per conversation
    need_d = "D" in arms or ("E" in arms and e_base == "D")
    d_reqs = []
    if need_d:
        by_conv: dict = {}
        for c in calls:
            by_conv.setdefault(c.get("conversation_id") or ("call:" + c["call_id"]), []).append(c)
        prefix = {}
        for k, grp in by_conv.items():
            p = _common_prefix([ctx[g["call_id"]] for g in grp]) if len(grp) > 1 else ""
            prefix[k] = (p, "" if p else ("a conversation of one call" if len(grp) == 1 else "no common leading text"))
        for c in calls:
            k = c.get("conversation_id") or ("call:" + c["call_id"])
            p, why = prefix[k]
            t = ctx[c["call_id"]]
            if p:
                blocks, cache, info = [(p, True), (t[len(p):], False)], True, {"cache_prefix_chars": len(p)}
                if not t[len(p):]:
                    blocks, info = [(t, True)], {"cache_prefix_chars": len(t)}
            else:
                blocks, cache, info = [(t, False)], False, {"cache_prefix_chars": 0, "no_breakpoint_because": why}
            d_reqs.append(_request("D", c, model_b(c), blocks, effort=effort, max_tokens=max_tokens, cache=cache,
                                   batch=False, rt=routes[c["call_id"]], context_source="context_fn(call)",
                                   extra=info))
        if "D" in arms:
            out["requests"]["D"] = d_reqs
    if "E" in arms:
        base = d_reqs if e_base == "D" else out["requests"]["C"]
        e, apart = [], []
        for r in base:
            rt = routes[r["call_id"]]
            if not rt["in_table"]:
                apart.append({"call_id": r["call_id"], "reason": "purpose not in the table: urgent, never batched"})
            elif rt["urgent"]:
                apart.append({"call_id": r["call_id"], "reason": f"urgent ({rt['family']}): needs an answer inside the session"})
            else:
                e.append(dict(r, arm="E", batch=True, send="batch", betas=None, fallbacks=None, e_base=e_base))
        out["requests"]["E"], out["set_apart"]["E"] = e, apart
    return out
