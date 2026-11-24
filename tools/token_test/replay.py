"""8b. The replay: `plan` (sends nothing) and `go` (needs Greg's go, then sends).

  python3 -m tools.token_test.replay plan --receipts <dir> --trade-day 2026-09-15 --arms A,B,C,D,E \
        --budget-tokens N [--context-fn pkg.module:function] --out plan.json
  python3 -m tools.token_test.replay go --plan plan.json --out-dir <markets-data folder> --greg-go "<his words>"

8d, said plainly: in the replay the schedule of calls comes from the Granite receipts (their own order). The
LIVE trigger (Frankie's own state posting a task with its subgraph and budget) is NOT built here.

`plan` makes no client and creates no message. Tokens are counted with `client.messages.count_tokens` only when
a credential is in the environment (ANTHROPIC_API_KEY); otherwise they are estimated at 4 characters a token and
the plan SAYS which it did. Nothing in this module creates a message at import.

`go` refuses without --greg-go and without a plan whose own figures fit inside its declared budget. Every
call of every arm is sent in the receipts' order and recorded on its own line (JSON lines): arm, call id, model
asked for, model that served it, the four usage figures, wall clock, cost, stop reason, the output itself, and
Granite's output for the same call. The budget is enforced as it goes; on exhaustion it stops and returns the
completed calls, the unresolved calls and the reason. Arm E is sent as ONE batch (no `fallbacks`: the Batches
API rejects it) and its results are matched by custom_id, never by position. Each arm's run is pushed to the
experiment record (parent = the baseline's trial, status recorded).

Costs are the API's price for the tokens, a compute cost of the test, not a trade cost.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
from pathlib import Path

from tools.token_test import prices as P
from tools.token_test.arms import ARMS, build_arms
from tools.token_test.baseline import load_output, read_calls

PLAN_SCHEMA = "markets.token_test.plan.v1"
BUDGET_FIELDS = ("max_model_calls", "max_sub_agents", "max_concurrent_workers", "max_tool_calls", "max_tokens",
                 "max_wall_clock_s", "max_retries", "max_graph_writes")
CHARS_PER_TOKEN = 4
POLL_S = 30


class Refused(ValueError):
    pass


def _flat_text(params: dict) -> str:
    return "".join(b["text"] for m in params["messages"] for b in m["content"])


def count_tokens(req: dict, client=None) -> tuple[int, str]:
    """(input tokens, how). With a client: the API's own count. Without: len/4, said so."""
    if client is not None:
        p = req["params"]
        r = client.messages.count_tokens(model=p["model"], messages=p["messages"])
        return int(r.input_tokens), "count_tokens"
    return -(-len(_flat_text(req["params"])) // CHARS_PER_TOKEN), f"estimate at {CHARS_PER_TOKEN} characters a token"


def _load_fn(spec: str):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


def plan(receipts, trade_day, arms=ARMS, *, budget_tokens: int, context_fn=None, client=None, effort="medium",
         max_tokens_per_call=16000, max_wall_clock_s=6 * 3600, max_retries=2, max_graph_writes=0, e_base="D",
         out=None) -> dict:
    """Build every arm's request for every call and write the plan. No message is created."""
    calls = read_calls(receipts, trade_day)
    doc = {"schema": PLAN_SCHEMA, "receipts": str(receipts), "trade_day": trade_day, "arms": list(arms),
           "created_by": "tools.token_test.replay plan", "sends_nothing": True,
           "orders_from": "the Granite receipts (8d: the live trigger is not built)",
           "granite_calls_found": len(calls), "reason": calls.reason,
           "set_apart": {"baseline": {"no_start_time": len(calls.no_start_time), "halt": len(calls.halt),
                                      "other_trade_days": len(calls.other_days)}, "arms": {}},
           "effort": effort, "max_tokens_per_call": max_tokens_per_call, "requests": {}, "not_built": {},
           "token_count": {}, "prices": P.PRICES}
    if not calls:
        doc["budget"] = {f: 0 for f in BUDGET_FIELDS}
        doc["budget"]["max_tokens"] = int(budget_tokens)
        doc["planned"] = {"model_calls": 0, "input_tokens": 0, "output_reserved_tokens": 0}
        doc["note"] = "no Granite call was found for this trade day: nothing to replay (" + str(calls.reason) + ")"
        return _write(doc, out)
    built = build_arms(list(calls), arms, context_fn=context_fn, effort=effort, max_tokens=max_tokens_per_call,
                       e_base=e_base)
    doc["not_built"], doc["not_in_table"] = built["not_built"], built["not_in_table"]
    doc["set_apart"] = {"baseline": {"no_start_time": len(calls.no_start_time), "halt": len(calls.halt),
                                     "other_trade_days": len(calls.other_days)}, "arms": built["set_apart"]}
    n_calls = tokens_in = reserved = 0
    for arm, reqs in built["requests"].items():
        how = set()
        for r in reqs:
            r["input_tokens_planned"], h = count_tokens(r, client)
            how.add(h)
            tokens_in += r["input_tokens_planned"]
            reserved += r["params"]["max_tokens"]
            n_calls += 1
        doc["token_count"][arm] = sorted(how)
        doc["requests"][arm] = reqs
    doc["planned"] = {"model_calls": n_calls, "input_tokens": tokens_in, "output_reserved_tokens": reserved,
                      "note": "tokens the plan will spend if every call fills max_tokens: input + output reserved"}
    doc["budget"] = {"max_model_calls": n_calls, "max_sub_agents": 0, "max_concurrent_workers": 1, "max_tool_calls": 0,
                     "max_tokens": int(budget_tokens), "max_wall_clock_s": int(max_wall_clock_s),
                     "max_retries": int(max_retries), "max_graph_writes": int(max_graph_writes)}
    doc["fits_budget"] = tokens_in <= budget_tokens
    return _write(doc, out)


def _write(doc, out):
    if out:
        Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    return doc


# ---- go -----------------------------------------------------------------------------------------------------
def _text(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _usage(u) -> dict:
    return {k: int(getattr(u, k, 0) or 0) for k in P.USAGE_FIELDS}


def check_plan(plan_doc: dict) -> None:
    b = plan_doc.get("budget") or {}
    missing = [f for f in BUDGET_FIELDS if f not in b]
    if missing:
        raise Refused(f"the plan has no declared budget field(s) {missing}")
    if not plan_doc.get("requests"):
        raise Refused("the plan has no request to send (" + str(plan_doc.get("note") or plan_doc.get("reason")) + ")")
    pl = plan_doc["planned"]
    if pl["model_calls"] > b["max_model_calls"]:
        raise Refused("planned model calls are over max_model_calls")
    if pl["input_tokens"] > b["max_tokens"]:
        raise Refused(f"planned input tokens {pl['input_tokens']} are over max_tokens {b['max_tokens']}")


def go(plan_doc: dict, greg_go: str | None, *, out_dir, client=None, exp=None, baseline_trial: str | None = None) -> dict:
    """Send the plan. Refuses without Greg's go and without a plan inside its budget."""
    if not (greg_go and greg_go.strip()):
        raise Refused("a run of the token test needs Greg's go, said to him first with its budget: --greg-go \"<his words>\"")
    check_plan(plan_doc)
    b = plan_doc["budget"]
    if client is None:
        import anthropic
        client = anthropic.Anthropic(max_retries=int(b["max_retries"]))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lines_path = out_dir / f"token-test-calls-{plan_doc['trade_day']}-{stamp}.jsonl"
    calls = {c["call_id"]: c for c in read_calls(plan_doc["receipts"], plan_doc["trade_day"])}
    state = {"calls": 0, "tokens": 0, "t0": time.time(), "done": [], "stopped": None}
    per_arm: dict = {}

    def granite(cid):
        c = calls.get(cid)
        return (load_output(c) if c else None), (None if c else "the receipts are not readable now")

    def stop_reason_if_over(r):
        if state["calls"] >= b["max_model_calls"]:
            return "max_model_calls reached"
        if time.time() - state["t0"] > b["max_wall_clock_s"]:
            return "max_wall_clock_s reached"
        if state["tokens"] + r["input_tokens_planned"] > b["max_tokens"]:
            return "max_tokens would be passed by the next call"
        return None

    def record(arm, r, msg, wall, batch):
        u = _usage(msg.usage)
        served = getattr(msg, "model", None) or r["model"]
        try:
            c = P.cost(served if served in P.PRICES["models"] else r["model"], u, batch=batch)
        except KeyError:
            c = {"error": f"{served} not in the price table"}
        go_out, why = granite(r["call_id"])
        line = {"arm": arm, "call_id": r["call_id"], "conversation_id": r.get("conversation_id"),
                "purpose": r.get("purpose"), "model_asked": r["model"], "model_served": served, "batch": batch,
                **u, "wall_clock_s": wall, "cost": c, "stop_reason": msg.stop_reason,
                "output": _text(msg) if msg.stop_reason not in ("refusal",) else None,
                "granite_output": go_out, "granite_output_missing_because": why}
        with lines_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        state["calls"] += 1
        state["tokens"] += sum(u.values())
        state["done"].append((arm, r["call_id"]))
        per_arm.setdefault(arm, []).append(line)

    for arm, reqs in plan_doc["requests"].items():
        if state["stopped"]:
            break
        if arm == "E":
            _run_batch(client, reqs, record, state, b)
            continue
        for r in reqs:
            why = stop_reason_if_over(r)
            if why:
                state["stopped"] = why
                break
            p = r["params"]
            t = time.time()
            if r["send"] == "beta_fallback":
                msg = client.beta.messages.create(betas=r["betas"], fallbacks=r["fallbacks"], **p)
            else:
                msg = client.messages.create(**p)
            record(arm, r, msg, time.time() - t, False)
    sent = set(state["done"])
    unresolved = [{"arm": a, "call_id": r["call_id"]} for a, rs in plan_doc["requests"].items() for r in rs
                  if (a, r["call_id"]) not in sent]
    result = {"completed": sorted(sent), "unresolved": unresolved,
              "stopped_because": state["stopped"] or ("all calls completed" if not unresolved else "batch did not end inside the wall clock"),
              "per_call_lines": str(lines_path)}
    result["trials"] = _push(exp, plan_doc, per_arm, result, baseline_trial)
    return result


def _run_batch(client, reqs, record, state, b):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    ids = {"E-" + r["call_id"][:60]: r for r in reqs}
    if len(ids) != len(reqs):
        raise Refused("two batch requests would share a custom_id")
    if len(reqs) + state["calls"] > b["max_model_calls"] or sum(r["input_tokens_planned"] for r in reqs) + state["tokens"] > b["max_tokens"]:
        state["stopped"] = "the batch would pass the budget; it was not sent"
        return
    batch = client.messages.batches.create(requests=[Request(custom_id=k, params=MessageCreateParamsNonStreaming(**r["params"]))
                                                      for k, r in ids.items()])
    t = time.time()
    while batch.processing_status != "ended":
        if time.time() - state["t0"] > b["max_wall_clock_s"]:
            state["stopped"] = f"max_wall_clock_s reached with batch {batch.id} still processing"
            return
        time.sleep(POLL_S)
        batch = client.messages.batches.retrieve(batch.id)
    for res in client.messages.batches.results(batch.id):
        r = ids.get(res.custom_id)
        if r is not None and res.result.type == "succeeded":
            record("E", r, res.result.message, time.time() - t, True)


def _push(exp, plan_doc, per_arm, result, baseline_trial):
    if exp is None:
        return {"pushed": False, "why": "no experiment record handed in"}
    by = "tools.token_test.replay"
    base = baseline_trial or exp.push(
        hypothesis=f"token test baseline: the Granite calls of trade day {plan_doc['trade_day']} read from the receipts",
        status="recorded", key="token-test-baseline-" + plan_doc["trade_day"] + "-" + hashlib.sha256(
            plan_doc["receipts"].encode()).hexdigest()[:8],
        metrics=[{"name": "granite_calls_found", "value": plan_doc["granite_calls_found"], "unit": "calls", "note": None}],
        written_by=by)
    out = {"baseline": base}
    for arm, lines in per_arm.items():
        m = [{"name": "calls_completed", "value": len(lines), "unit": "calls", "note": None}]
        for k in P.USAGE_FIELDS:
            m.append({"name": f"{k}_total", "value": sum(l[k] for l in lines), "unit": "tokens",
                      "note": "sum of this arm's own calls, not an average"})
        m.append({"name": "cost_usd_total", "value": sum(float((l["cost"] or {}).get("total") or 0) for l in lines),
                  "unit": "USD", "note": "API price of the tokens (compute cost of the test, not a trade cost)"})
        out[arm] = exp.push(hypothesis=f"token test arm {arm}, trade day {plan_doc['trade_day']}", status="recorded",
                            parent=base, metrics=m, note="per-call table: " + result["per_call_lines"], written_by=by)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools.token_test.replay")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--receipts", required=True)
    a.add_argument("--trade-day", required=True)
    a.add_argument("--arms", default="A,B,C,D,E")
    a.add_argument("--budget-tokens", type=int, required=True)
    a.add_argument("--context-fn", help="pkg.module:function building arm C's context from a call")
    a.add_argument("--effort", default="medium")
    a.add_argument("--max-tokens-per-call", type=int, default=16000)
    a.add_argument("--max-wall-clock-s", type=int, default=6 * 3600)
    a.add_argument("--max-retries", type=int, default=2)
    a.add_argument("--prices", help="a price table file replacing the built-in one")
    a.add_argument("--out", required=True)
    g = sub.add_parser("go")
    g.add_argument("--plan", required=True)
    g.add_argument("--out-dir", required=True)
    g.add_argument("--greg-go")
    g.add_argument("--data-root")
    args = ap.parse_args(argv)
    if args.cmd == "plan":
        if args.prices:
            P.PRICES.clear()
            P.PRICES.update(P.load_prices(args.prices))
        client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
        doc = plan(args.receipts, args.trade_day, tuple(args.arms.split(",")), budget_tokens=args.budget_tokens,
                   context_fn=_load_fn(args.context_fn) if args.context_fn else None, client=client,
                   effort=args.effort, max_tokens_per_call=args.max_tokens_per_call,
                   max_wall_clock_s=args.max_wall_clock_s, max_retries=args.max_retries, out=args.out)
        print(json.dumps({"granite_calls_found": doc["granite_calls_found"], "planned": doc["planned"],
                          "not_built": doc["not_built"], "reason": doc["reason"], "budget": doc["budget"]}, indent=1))
        return 0
    try:
        if not (args.greg_go and args.greg_go.strip()):
            raise Refused("a run of the token test needs Greg's go, said to him first with its budget: --greg-go \"<his words>\"")
        from tools.exp_dag import ExpDag
        plan_doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        res = go(plan_doc, args.greg_go, out_dir=args.out_dir, exp=ExpDag(args.data_root))
    except Refused as e:
        print("refused:", e, file=sys.stderr)
        return 2
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
