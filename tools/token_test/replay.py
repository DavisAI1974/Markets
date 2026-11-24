"""8b. The replay: `plan` (sends nothing, makes no client), `count` and `go` (both need Greg's go and send).

  python3 -m tools.token_test.replay plan --receipts <dir> --trade-day 2026-09-15 --arms A,B,C,D,E \
        --max-model-calls N --budget-tokens N [--context-fn pkg.module:function] --out plan.json
  python3 -m tools.token_test.replay count --plan plan.json --out counted.json --greg-go "<his words>"
  python3 -m tools.token_test.replay go --plan plan.json --out-dir <markets-data folder> --greg-go "<his words>"

8d, said plainly: in the replay the schedule of calls comes from the Granite receipts (their own order). The
LIVE trigger (Frankie's own state posting a task with its subgraph and budget) is NOT built here.

`plan` NEVER creates a client and sends nothing, whether or not ANTHROPIC_API_KEY is set. Counting tokens with the
API transmits Granite's prompts (Frankie's inputs) to it, so counting is part of a run and is behind Greg's go:
`plan` estimates at 4 characters a token and says so in the plan. `count` (needs --greg-go) writes a NEW plan file in
which each request carries the API's own count (`client.messages.count_tokens`); `go` counts as it runs any request
the plan has not yet counted.

THE BUDGET IS THE CALLER'S, never the plan's own count: `--max-model-calls` and `--budget-tokens` are required.
`plan` (and `count`) refuse, naming the figure, when the calls exceed the first or when the INPUT tokens plus the
OUTPUT RESERVED for each call (max_tokens_per_call) exceed the second. In `go` the reserve of the next call is
counted before it is sent; for arm E the whole batch's reserve is counted before the batch is created.

Greg's words are recorded in the plan JSON written by `count`, at the head of the per-call lines file, in the run's
receipt (token-test-receipt-*.json, beside the lines) and in the experiment record's trial (environment `greg_go`).

`go` refuses without --greg-go and without a plan whose figures fit inside its declared budget. Every call of every
arm is sent in the receipts' order and recorded on its own line (JSON lines): arm, call id, `granite_position` (the
call's place in the receipts' order), model asked for, model that served it, the four usage figures, wall clock, cost,
stop reason, the output itself, and Granite's output for the same call. A figure the API response does not carry is
null, never 0. A batch result that is not "succeeded" (errored, canceled, expired) is recorded on its own line with
its type and the reason the API gave; a refusal is recorded with stop_reason "refusal", the stop_details category and
explanation, and its output null with that note. Results whose custom_id matches no request are listed as
`unmatched_results`. `unresolved` holds only requests that got no result at all.
Arm E is sent as ONE batch (no `fallbacks`: the Batches API rejects it) and its results are matched by custom_id,
never by position. Each arm's run is pushed to the experiment record (parent = the baseline's trial, status
recorded): the count of calls, the count with no figure, and the last value of the arm's running sum for each token
figure and the cost, each named "running sum over the trade day's calls"; nothing else is summed, nothing averaged.

Costs are the API's price for the tokens, a compute cost of the test, not a trade cost.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path

from tools.token_test import prices as P
from tools.token_test.arms import ARMS, build_arms
from tools.token_test.baseline import load_output, read_calls
from tools.token_test.report import running_sums

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
    """(input tokens, how). With a client: the API's own count (this SENDS the prompt). Without: len/4, said so."""
    if client is not None:
        p = req["params"]
        r = client.messages.count_tokens(model=p["model"], messages=p["messages"])
        return int(r.input_tokens), "count_tokens"
    return -(-len(_flat_text(req["params"])) // CHARS_PER_TOKEN), f"estimate at {CHARS_PER_TOKEN} characters a token"


def _load_fn(spec: str):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


def _totals(requests: dict) -> dict:
    n = sum(len(v) for v in requests.values())
    tin = sum(r["input_tokens_planned"] for v in requests.values() for r in v)
    res = sum(r["params"]["max_tokens"] for v in requests.values() for r in v)
    return {"model_calls": n, "input_tokens": tin, "output_reserved_tokens": res,
            "input_plus_output_reserved_tokens": tin + res,
            "note": "tokens the plan will spend if every call fills max_tokens: input + output reserved"}


def _refuse_if_over(planned: dict, budget: dict) -> None:
    if planned["model_calls"] > budget["max_model_calls"]:
        raise Refused(f"planned model calls {planned['model_calls']} are over max_model_calls {budget['max_model_calls']}")
    spend = planned["input_tokens"] + planned["output_reserved_tokens"]
    if spend > budget["max_tokens"]:
        raise Refused(f"planned input tokens {planned['input_tokens']} plus output reserved "
                      f"{planned['output_reserved_tokens']} = {spend} are over max_tokens {budget['max_tokens']}")


def plan(receipts, trade_day, arms=ARMS, *, max_model_calls: int, budget_tokens: int, context_fn=None, effort="medium",
         max_tokens_per_call=16000, max_wall_clock_s=6 * 3600, max_retries=2, max_graph_writes=0, e_base="D",
         out=None) -> dict:
    """Build every arm's request for every call and write the plan. NO client is made and no message is created,
    key or no key. Tokens are estimated at 4 characters a token. Raises Refused (writing nothing) when the plan's
    calls or its input plus reserved output pass the caller's budget."""
    calls = read_calls(receipts, trade_day)
    budget = {"max_model_calls": int(max_model_calls), "max_sub_agents": 0, "max_concurrent_workers": 1,
              "max_tool_calls": 0, "max_tokens": int(budget_tokens), "max_wall_clock_s": int(max_wall_clock_s),
              "max_retries": int(max_retries), "max_graph_writes": int(max_graph_writes)}
    doc = {"schema": PLAN_SCHEMA, "receipts": str(receipts), "trade_day": trade_day, "arms": list(arms),
           "created_by": "tools.token_test.replay plan", "sends_nothing": True, "greg_go": None,
           "orders_from": "the Granite receipts (8d: the live trigger is not built)",
           "granite_calls_found": len(calls), "reason": calls.reason,
           "set_apart": {"baseline": _baseline_apart(calls), "arms": {}},
           "effort": effort, "max_tokens_per_call": max_tokens_per_call, "requests": {}, "not_built": {},
           "token_count": {}, "prices": P.PRICES, "budget": budget,
           "budget_is": "the caller's (--max-model-calls, --budget-tokens), not the plan's own count"}
    if not calls:
        doc["planned"] = {"model_calls": 0, "input_tokens": 0, "output_reserved_tokens": 0}
        doc["note"] = "no Granite call was found for this trade day: nothing to replay (" + str(calls.reason) + ")"
        return _write(doc, out)
    built = build_arms(list(calls), arms, context_fn=context_fn, effort=effort, max_tokens=max_tokens_per_call,
                       e_base=e_base)
    doc["not_built"], doc["not_in_table"] = built["not_built"], built["not_in_table"]
    doc["set_apart"]["arms"] = built["set_apart"]
    order = {c["call_id"]: i + 1 for i, c in enumerate(calls)}
    for arm, reqs in built["requests"].items():
        how = set()
        for r in reqs:
            r["input_tokens_planned"], r["input_tokens_how"] = count_tokens(r, None)
            r["granite_position"] = order[r["call_id"]]
            how.add(r["input_tokens_how"])
        doc["token_count"][arm] = sorted(how)
        doc["requests"][arm] = reqs
    doc["planned"] = _totals(doc["requests"])
    _refuse_if_over(doc["planned"], budget)
    doc["fits_budget"] = True
    return _write(doc, out)


def _baseline_apart(calls) -> dict:
    return {"no_start_time": len(calls.no_start_time), "halt": len(calls.halt),
            "outside_any_trade_day": len(calls.outside_any_trade_day), "other_trade_days": len(calls.other_days),
            "unreadable_folders": len(calls.unreadable), "not_a_granite_record": len(calls.not_a_granite_record)}


def _write(doc, out):
    if out:
        Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    return doc


def _need_words(greg_go, what):
    if not (greg_go and greg_go.strip()):
        raise Refused(f"{what} needs Greg's go, said to him first with its budget: --greg-go \"<his words>\"")


def _client(max_retries=2):
    import anthropic
    return anthropic.Anthropic(max_retries=int(max_retries))


def count(plan_doc: dict, greg_go: str | None, *, client=None, out=None) -> dict:
    """Fill the API's own token counts into a NEW copy of the plan. This SENDS each request's prompt to the API
    (count_tokens), so it needs Greg's words. Refuses, writing nothing, if the counted plan passes the budget."""
    _need_words(greg_go, "counting tokens with the API (it sends Granite's prompts out)")
    if not plan_doc.get("requests"):
        raise Refused("the plan has no request to count")
    if client is None:
        client = _client((plan_doc.get("budget") or {}).get("max_retries", 2))
    doc = json.loads(json.dumps(plan_doc))
    for arm, reqs in doc["requests"].items():
        how = set()
        for r in reqs:
            r["input_tokens_planned"], r["input_tokens_how"] = count_tokens(r, client)
            how.add(r["input_tokens_how"])
        doc["token_count"][arm] = sorted(how)
    doc["planned"] = _totals(doc["requests"])
    doc["greg_go"] = greg_go.strip()
    doc["counted_on_greg_go"] = greg_go.strip()
    _refuse_if_over(doc["planned"], doc["budget"])
    doc["sends_nothing"] = False
    doc["created_by"] = "tools.token_test.replay count (from a plan)"
    return _write(doc, out)


# ---- go -----------------------------------------------------------------------------------------------------
def _text(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _usage(u) -> dict:
    """The four figures the response carries; one it does not carry is None, never 0."""
    out = {}
    for k in P.USAGE_FIELDS:
        v = getattr(u, k, None)
        out[k] = None if v is None else int(v)
    return out


def check_plan(plan_doc: dict) -> None:
    b = plan_doc.get("budget") or {}
    missing = [f for f in BUDGET_FIELDS if f not in b]
    if missing:
        raise Refused(f"the plan has no declared budget field(s) {missing}")
    if not plan_doc.get("requests"):
        raise Refused("the plan has no request to send (" + str(plan_doc.get("note") or plan_doc.get("reason")) + ")")
    _refuse_if_over(_totals(plan_doc["requests"]), b)


def _stop_details(msg):
    d = getattr(msg, "stop_details", None)
    if d is None:
        return None
    get = (lambda k: d.get(k)) if isinstance(d, dict) else (lambda k: getattr(d, k, None))
    return {"category": get("category"), "explanation": get("explanation")}


def go(plan_doc: dict, greg_go: str | None, *, out_dir, client=None, exp=None, baseline_trial: str | None = None) -> dict:
    """Send the plan. Refuses without Greg's go and without a plan inside its budget."""
    _need_words(greg_go, "a run of the token test")
    check_plan(plan_doc)
    greg_go = greg_go.strip()
    b = plan_doc["budget"]
    if client is None:
        client = _client(b["max_retries"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lines_path = out_dir / f"token-test-calls-{plan_doc['trade_day']}-{stamp}.jsonl"
    receipt_path = out_dir / f"token-test-receipt-{plan_doc['trade_day']}-{stamp}.json"
    with lines_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"record": "head", "greg_go": greg_go, "trade_day": plan_doc["trade_day"],
                            "plan_schema": plan_doc.get("schema"), "budget": b}) + "\n")
    calls = {c["call_id"]: c for c in read_calls(plan_doc["receipts"], plan_doc["trade_day"])}
    state = {"calls": 0, "tokens": 0, "t0": time.time(), "done": [], "stopped": None, "unmatched": []}
    per_arm: dict = {}

    def granite(cid):
        c = calls.get(cid)
        return (load_output(c) if c else None), (None if c else "the receipts are not readable now")

    def counted(r):
        """The request's input tokens, counted by the API now if the plan only estimated them."""
        if r.get("input_tokens_how") != "count_tokens":
            r["input_tokens_planned"], r["input_tokens_how"] = count_tokens(r, client)
        return r["input_tokens_planned"]

    def stop_reason_if_over(r):
        if state["calls"] >= b["max_model_calls"]:
            return "max_model_calls reached"
        if time.time() - state["t0"] > b["max_wall_clock_s"]:
            return "max_wall_clock_s reached"
        # the next call's input plus the output reserved for it (its max_tokens) are counted before it is sent
        if state["tokens"] + counted(r) + r["params"]["max_tokens"] > b["max_tokens"]:
            return "max_tokens would be passed by the next call (its input plus the output reserved)"
        return None

    def base_line(arm, r, served, batch, wall):
        return {"arm": arm, "call_id": r["call_id"], "granite_position": r.get("granite_position"),
                "conversation_id": r.get("conversation_id"), "purpose": r.get("purpose"),
                "model_asked": r["model"], "model_served": served, "batch": batch, "wall_clock_s": wall}

    def write_line(arm, r, line, tokens_used):
        with lines_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        state["calls"] += 1
        state["tokens"] += tokens_used
        state["done"].append((arm, r["call_id"]))
        per_arm.setdefault(arm, []).append(line)

    def record(arm, r, msg, wall, batch):
        u = _usage(msg.usage)
        served = getattr(msg, "model", None) or r["model"]
        missing = [k for k, v in u.items() if v is None]
        if missing:
            c = {"total": None, "why": f"usage figure(s) not recorded: {missing}"}
        else:
            try:
                c = P.cost(served if served in P.PRICES["models"] else r["model"], u, batch=batch)
            except KeyError:
                c = {"total": None, "error": f"{served} not in the price table"}
        go_out, why = granite(r["call_id"])
        refused = msg.stop_reason == "refusal"
        line = base_line(arm, r, served, batch, wall)
        line.update(u)
        line.update({"cost": c, "stop_reason": msg.stop_reason,
                     "output": None if refused else _text(msg), "granite_output": go_out,
                     "granite_output_missing_because": why})
        if refused:
            line["stop_details"] = _stop_details(msg)
            line["output_not_given_because"] = "refusal: the model gave no output (stop_reason refusal)"
        write_line(arm, r, line, sum(v for v in u.values() if v is not None))

    def record_failed(arm, r, res, wall):
        rt = res.result
        reason = None
        err = getattr(rt, "error", None)
        if err is not None:
            e = getattr(err, "error", err)
            reason = {"error_type": getattr(e, "type", None) or getattr(err, "type", None),
                      "message": getattr(e, "message", None), "request_id": getattr(err, "request_id", None)}
        go_out, why = granite(r["call_id"])
        line = base_line(arm, r, None, True, wall)
        line.update({k: None for k in P.USAGE_FIELDS})
        line.update({"cost": {"total": None, "why": f"batch result {rt.type}: no usage"}, "stop_reason": None,
                     "result_type": rt.type, "result_reason": reason, "output": None,
                     "output_not_given_because": f"batch result {rt.type}", "granite_output": go_out,
                     "granite_output_missing_because": why})
        write_line(arm, r, line, 0)

    for arm, reqs in plan_doc["requests"].items():
        if state["stopped"]:
            break
        if arm == "E":
            _run_batch(client, reqs, record, record_failed, state, b, counted)
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
    result = {"completed": sorted(sent), "unresolved": unresolved, "unmatched_results": state["unmatched"],
              "stopped_because": state["stopped"] or ("all calls completed" if not unresolved else "batch did not end inside the wall clock"),
              "per_call_lines": str(lines_path), "greg_go": greg_go}
    result["trials"] = _push(exp, plan_doc, per_arm, result, baseline_trial, greg_go)
    receipt_path.write_text(json.dumps({"schema": "markets.token_test.receipt.v1", "greg_go": greg_go,
                                        "trade_day": plan_doc["trade_day"], "budget": b, "result": result},
                                       indent=1, sort_keys=True, default=str), encoding="utf-8")
    result["receipt"] = str(receipt_path)
    return result


def _run_batch(client, reqs, record, record_failed, state, b, counted):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    ids = {"E-" + r["call_id"][:60]: r for r in reqs}
    if len(ids) != len(reqs):
        raise Refused("two batch requests would share a custom_id")
    # the whole batch's reserve (input + each request's max_tokens) is counted before the batch is created
    batch_in = sum(counted(r) for r in reqs)
    batch_reserve = sum(r["params"]["max_tokens"] for r in reqs)
    if len(reqs) + state["calls"] > b["max_model_calls"] or batch_in + batch_reserve + state["tokens"] > b["max_tokens"]:
        state["stopped"] = (f"the batch would pass the budget (input {batch_in} + output reserved {batch_reserve} "
                            f"+ already spent {state['tokens']} against max_tokens {b['max_tokens']}); it was not sent")
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
        if r is None:
            state["unmatched"].append({"custom_id": res.custom_id, "result_type": res.result.type})
        elif res.result.type == "succeeded":
            record("E", r, res.result.message, time.time() - t, True)
        else:
            record_failed("E", r, res, time.time() - t)


def _push(exp, plan_doc, per_arm, result, baseline_trial, greg_go):
    if exp is None:
        return {"pushed": False, "why": "no experiment record handed in"}
    by = "tools.token_test.replay"
    env = {"greg_go": greg_go}
    base = baseline_trial or exp.push(
        hypothesis=f"token test baseline: the Granite calls of trade day {plan_doc['trade_day']} read from the receipts",
        status="recorded", key="token-test-baseline-" + plan_doc["trade_day"] + "-" + hashlib.sha256(
            plan_doc["receipts"].encode()).hexdigest()[:8],
        metrics=[{"name": "granite_calls_found", "value": plan_doc["granite_calls_found"], "unit": "calls", "note": None}],
        written_by=by)
    out = {"baseline": base}
    for arm, lines in per_arm.items():
        s = running_sums(lines)
        label = "running sum over the trade day's calls (last value)"
        m = [{"name": "calls_completed", "value": len(lines), "unit": "calls", "note": None},
             {"name": "calls_with_no_figure", "value": s["calls_with_no_figure"], "unit": "calls",
              "note": "calls whose usage input or output figure is not recorded (null, never 0)"}]
        for k in P.USAGE_FIELDS:
            m.append({"name": f"{k}_running_sum_last", "value": s["last"][k], "unit": "tokens",
                      "note": f"{label}; calls where this figure is not recorded add nothing"})
        m.append({"name": "cost_usd_running_sum_last", "value": s["last"]["cost_usd"], "unit": "USD",
                  "note": f"{label}; API price of the tokens (compute cost of the test, not a trade cost)"})
        out[arm] = exp.push(hypothesis=f"token test arm {arm}, trade day {plan_doc['trade_day']}", status="recorded",
                            parent=base, metrics=m, environment=env,
                            note="per-call table: " + result["per_call_lines"], written_by=by)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools.token_test.replay")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--receipts", required=True)
    a.add_argument("--trade-day", required=True)
    a.add_argument("--arms", default="A,B,C,D,E")
    a.add_argument("--max-model-calls", type=int, required=True)
    a.add_argument("--budget-tokens", type=int, required=True)
    a.add_argument("--context-fn", help="pkg.module:function building arm C's context from a call")
    a.add_argument("--effort", default="medium")
    a.add_argument("--max-tokens-per-call", type=int, default=16000)
    a.add_argument("--max-wall-clock-s", type=int, default=6 * 3600)
    a.add_argument("--max-retries", type=int, default=2)
    a.add_argument("--prices", help="a price table file replacing the built-in one")
    a.add_argument("--out", required=True)
    c = sub.add_parser("count")
    c.add_argument("--plan", required=True)
    c.add_argument("--out", required=True, help="a NEW plan file; the plan given is not changed")
    c.add_argument("--greg-go")
    g = sub.add_parser("go")
    g.add_argument("--plan", required=True)
    g.add_argument("--out-dir", required=True)
    g.add_argument("--greg-go")
    g.add_argument("--data-root")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "plan":
            if args.prices:
                P.PRICES.clear()
                P.PRICES.update(P.load_prices(args.prices))
            doc = plan(args.receipts, args.trade_day, tuple(args.arms.split(",")),
                       max_model_calls=args.max_model_calls, budget_tokens=args.budget_tokens,
                       context_fn=_load_fn(args.context_fn) if args.context_fn else None,
                       effort=args.effort, max_tokens_per_call=args.max_tokens_per_call,
                       max_wall_clock_s=args.max_wall_clock_s, max_retries=args.max_retries, out=args.out)
            print(json.dumps({"granite_calls_found": doc["granite_calls_found"], "planned": doc["planned"],
                              "token_count": doc["token_count"], "not_built": doc["not_built"],
                              "reason": doc["reason"], "budget": doc["budget"]}, indent=1))
            return 0
        plan_doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        if args.cmd == "count":
            doc = count(plan_doc, args.greg_go, out=args.out)
            print(json.dumps({"planned": doc["planned"], "token_count": doc["token_count"]}, indent=1))
            return 0
        _need_words(args.greg_go, "a run of the token test")
        from tools.exp_dag import ExpDag
        res = go(plan_doc, args.greg_go, out_dir=args.out_dir, exp=ExpDag(args.data_root))
    except Refused as e:
        print("refused:", e, file=sys.stderr)
        return 2
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
