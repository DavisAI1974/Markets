"""The swarm's command line: `plan` (no model call) and `go` (a run; needs Greg's go).

    python3 -m tools.swarm.run plan --trade-day 2023-10-02 [--events <id> ...] --cutoff 0.7 \
        --budget-tokens N [--max-model-calls ...] --out plan.json
    python3 -m tools.swarm.run go --plan plan.json --caller anthropic|files --greg-go "<his words>" \
        [--files-dir DIR] [--out result.json]

`plan` builds every brief, estimates, checks the plan against its own budget and writes it. It makes no
model call and reads nothing but the saved graph.

`go` refuses to start without `--greg-go` (a run of the swarm needs Greg's go, said to him first with its
budget) and without a plan that passes `check`. When it runs: the workers, at most `max_concurrent_workers`
at a time, each call recorded as an AgentRun; the budget enforced as it goes (on exhaustion it stops and
returns the completed events, the unresolved events and the reason); then the reducer (code), the refute
wave on the claims sent to review, and the synthesis. One event's failure in the reduce or refute step
(an exception, a refused answer) is recorded for that event in `unresolved` with its reason, and the run goes
on with the others. No check of this repository exercises the command `go` beyond its refusals; the check of
`run_plan` uses real answers put in files for the FileCaller.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import sys
import threading
import time
from pathlib import Path

from tools.kgraph import schema
from tools.kgraph.sources import code_stamp, link
from tools.kgraph.store import GraphStore, sha

from . import layers as L
from . import model as M
from . import plan as P
from . import reduce as R
from . import refute as F


# ---- the budget, enforced as the run goes ---------------------------------------------------------

class Budget:
    """Counts what the plan declared. Thread-safe: workers reserve before a call and settle after it."""

    def __init__(self, declared: dict):
        self.d, self.lock, self.t0 = declared, threading.Lock(), time.monotonic()
        self.calls = self.retries = self.sub_agents = self.tokens_used = self.reserved = self.graph_writes = 0
        self.tool_calls = 0          # no tool is used by the swarm; the declared figure is kept for the record

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def reason_exhausted(self) -> str | None:
        d = self.d
        if self.elapsed() >= d["max_wall_clock_s"]:
            return f"max_wall_clock_s of {d['max_wall_clock_s']} was reached"
        if self.graph_writes >= d["max_graph_writes"]:
            return f"max_graph_writes of {d['max_graph_writes']} was reached"
        if self.calls >= d["max_model_calls"]:
            return f"max_model_calls of {d['max_model_calls']} was reached"
        if self.tokens_used + self.reserved >= d["max_tokens"]:
            return f"max_tokens of {d['max_tokens']} was reached"
        return None

    def reserve(self, tokens: int, new_agent: bool) -> str | None:
        """Take one call (and, for a new worker or refuter, one sub-agent). A reason, or None when taken."""
        with self.lock:
            why = self.reason_exhausted()
            if why is None and self.tokens_used + self.reserved + tokens > self.d["max_tokens"]:
                why = (f"max_tokens of {self.d['max_tokens']}: {self.tokens_used} used and {self.reserved} "
                       f"reserved, and this call needs up to {tokens}")
            if why is None and new_agent and self.sub_agents >= self.d["max_sub_agents"]:
                why = f"max_sub_agents of {self.d['max_sub_agents']} was reached"
            if why:
                return why
            self.calls += 1
            self.sub_agents += 1 if new_agent else 0
            self.reserved += tokens
            return None

    def settle(self, reserved: int, actual: int) -> None:
        with self.lock:
            self.reserved -= reserved
            self.tokens_used += actual

    def take_retry(self) -> bool:
        with self.lock:
            if self.retries >= self.d["max_retries"]:
                return False
            self.retries += 1
            return True

    def count_writes(self, n: int) -> None:
        with self.lock:
            self.graph_writes += n

    def snapshot(self) -> dict:
        with self.lock:
            return {"model_calls": self.calls, "sub_agents": self.sub_agents, "retries": self.retries,
                    "tool_calls": self.tool_calls, "tokens_used": self.tokens_used,
                    "graph_writes": self.graph_writes, "wall_clock_s": round(self.elapsed(), 3),
                    "declared": dict(self.d)}


def _tokens_of(r: dict, est_in: int) -> int:
    u = r["usage"]
    if all(u.get(k) is not None for k in M.USAGE_KEYS):
        return sum(int(u[k]) for k in M.USAGE_KEYS)
    return est_in + math.ceil(len(r.get("text") or "") / 4)      # a caller that reports no usage: the estimate


def _counting(store: GraphStore, budget: Budget) -> None:
    orig = store.write

    def counted(nodes=(), edges=(), *, written_by):
        nodes, edges = list(nodes), list(edges)
        out = orig(nodes, edges, written_by=written_by)
        budget.count_writes(len(nodes) + len(edges))
        return out
    store.write = counted


# ---- one model call, with the budget -------------------------------------------------------------

def _call_job(caller, budget: Budget, job: dict, first_reserved: int) -> dict:
    """Runs in a worker thread: no graph write here (the graph is written from the main thread only)."""
    est_in = L.estimate_tokens(job["system"] + job["user"])
    need = est_in + job["max_out"]
    reserved, attempts = first_reserved, 0
    while True:
        attempts += 1
        try:
            r = caller.call(job["model"], job["system"], job["user"], job["max_out"], job["effort"], job["schema"])
        except M.ModelCallFailed as e:
            budget.settle(reserved, 0)
            if e.retryable and budget.take_retry():
                why = budget.reserve(need, new_agent=False)
                if why is None:
                    reserved = need
                    continue
                return {"failed": f"{e}; a retry was not made: {why}", "attempts": attempts}
            return {"failed": str(e), "attempts": attempts}
        except Exception as e:      # a caller bug is reported, never swallowed
            budget.settle(reserved, 0)
            return {"failed": f"{type(e).__name__}: {e}", "attempts": attempts}
        budget.settle(reserved, _tokens_of(r, est_in))
        return {"r": r, "attempts": attempts}


def _record_run(store: GraphStore, plan, role: str, task: str, key: str, out: dict, job: dict) -> str:
    rid = f"run:swarm-{plan.name}-{role.split()[-1]}-{sha([key])}"
    a = {"role": role, "task": task, "plan": plan.name, "attempts": out.get("attempts")}
    if "r" in out:
        r = out["r"]
        u = r["usage"]
        outcome = {"end_turn": "returned", "max_tokens": "cut off at max_tokens: not read as an answer",
                   "refusal": "refusal: not read as an answer"}.get(r["stop_reason"], f"stop_reason {r['stop_reason']}")
        a.update(model=r["model"] or job["model"], input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                 cache_creation_input_tokens=u["cache_creation_input_tokens"],
                 cache_read_input_tokens=u["cache_read_input_tokens"],
                 wall_clock_ms=int(round(r["wall_clock_s"] * 1000)), stop_reason=r["stop_reason"], outcome=outcome)
    else:
        a.update(model=job["model"], input_tokens=None, output_tokens=None, wall_clock_ms=None,
                 outcome="no answer: " + out["failed"])
    store.write([{"id": rid, "type": "AgentRun", "attrs": a}], [], written_by=code_stamp("tools.swarm.run"))
    return rid


def _parse(out: dict) -> tuple[dict | None, str | None]:
    """(the answer's JSON, None) or (None, why it is not read)."""
    if "r" not in out:
        return None, out["failed"]
    r = out["r"]
    if r["stop_reason"] != "end_turn":
        return None, f"stop_reason {r['stop_reason']}: the output is not read as an answer"
    try:
        j = json.loads(r["text"])
    except json.JSONDecodeError as e:
        return None, f"the output is not JSON ({e})"
    if not isinstance(j, dict):
        return None, "the output is JSON but not an object"
    return j, None


def _fan_out(jobs: list[dict], caller, budget: Budget, max_concurrent: int, on_done) -> tuple[list[dict], str | None]:
    """Run the jobs with at most `max_concurrent` calls at a time. `on_done(job, out)` runs in the main
    thread. Returns (the jobs never started, the reason launching stopped or None)."""
    pending, running, stop = list(jobs), {}, None
    with cf.ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        while pending or running:
            while pending and len(running) < max_concurrent and stop is None:
                job = pending[0]
                need = L.estimate_tokens(job["system"] + job["user"]) + job["max_out"]
                why = budget.reserve(need, new_agent=True)
                if why:
                    stop = why
                    break
                pending.pop(0)
                running[pool.submit(_call_job, caller, budget, job, need)] = job
            if not running:
                break
            done, _ = cf.wait(list(running), return_when=cf.FIRST_COMPLETED)
            for f in done:
                on_done(running.pop(f), f.result())
            if stop is None and pending:        # a budget used up with nothing left to do is not a stop
                stop = budget.reason_exhausted()
    return pending, stop


# ---- the run ---------------------------------------------------------------------------------------

def run_plan(plan: P.RunPlan, caller, store: GraphStore) -> dict:
    P.check(plan)
    if not plan.greg_go.strip():
        raise P.PlanRefused("the plan carries no go from Greg (greg_go is empty)")
    budget = Budget(plan.budget)
    _counting(store, budget)
    completed, unresolved, reasons = [], {}, []
    runs = {"workers": [], "refuters": []}

    # 1. the workers
    jobs = []
    for ev in plan.events:
        system, user = L.build_brief_parts(L.event_layers(store, ev))
        jobs.append({"key": ev, "model": plan.models["worker"], "system": system, "user": user,
                     "schema": L.ANSWER_SCHEMA, "effort": plan.efforts["worker"],
                     "max_out": plan.max_output_tokens["worker"]})

    def worker_done(job, out):
        ev = job["key"]
        rid = _record_run(store, plan, "swarm worker", f"read {ev}", ev, out, job)
        runs["workers"].append(rid)
        j, why = _parse(out)
        if j is None:
            unresolved[ev] = why
            return
        if j.get("event") != ev:
            unresolved[ev] = f"the answer names {j.get('event')!r}, not {ev}"
            return
        try:
            rep = R.load_worker_result(store, j, rid, cutoff=plan.cutoff)
        except schema.Refused as e:
            unresolved[ev] = f"the answer was refused: {e}"
            return
        except Exception as e:              # one event's reduce step never stops the others
            unresolved[ev] = f"the reduce step raised {type(e).__name__}: {e}"
            return
        completed.append(ev)
        runs.setdefault("reports", {})[ev] = {k: v for k, v in rep.items() if k not in ("claims", "thrown")}

    never, stop = _fan_out(jobs, caller, budget, int(plan.budget["max_concurrent_workers"]), worker_done)
    for j in never:
        unresolved[j["key"]] = "not started: " + (stop or "the budget")
    if stop:
        reasons.append("workers: " + stop)

    # 2. the refute wave on the claims sent to review (one call for each event that has some)
    refuted = []
    if not stop:
        rjobs = []
        for ev in completed:
            ids = R.review_set(store, [ev], plan.cutoff)
            if ids:
                s, u = F.build_refute_brief_parts(store, ids)
                rjobs.append({"key": ev, "model": plan.models["refute"], "system": s, "user": u,
                              "schema": F.REFUTE_SCHEMA, "effort": plan.efforts["refute"],
                              "max_out": plan.max_output_tokens["refute"], "claim_ids": ids})

        def refute_done(job, out):
            rid = _record_run(store, plan, "swarm refuter", f"try to contradict the claims of {job['key']}",
                              job["key"], out, job)
            runs["refuters"].append(rid)
            j, why = _parse(out)
            if j is None:
                unresolved.setdefault("refute:" + job["key"], why)
                return
            try:
                F.load_refute_result(store, j, rid, job["claim_ids"])
                refuted.append(job["key"])
            except schema.Refused as e:
                unresolved["refute:" + job["key"]] = f"the answer was refused: {e}"
            except Exception as e:          # one event's refute step never stops the others
                unresolved["refute:" + job["key"]] = f"the refute step raised {type(e).__name__}: {e}"

        rnever, rstop = _fan_out(rjobs, caller, budget, int(plan.budget["max_concurrent_workers"]), refute_done)
        for j in rnever:
            unresolved["refute:" + j["key"]] = "not started: " + (rstop or "the budget")
        if rstop:
            reasons.append("refute wave: " + rstop)

    # 3. the synthesis, event by event
    text = R.synthesis(store, completed)
    return {"plan": plan.name, "completed_events": completed, "unresolved": unresolved,
            "stopped_because": "; ".join(reasons) or None, "refute_wave_events": refuted,
            "agent_runs": runs, "budget_used": budget.snapshot(), "synthesis": text}


# ---- the command line ------------------------------------------------------------------------------

def _store(args) -> GraphStore:
    return GraphStore(args.data_root, graph_dir=args.graph_dir)


def cmd_plan(args) -> int:
    store = _store(args)
    events = []
    for d in args.trade_day or []:
        ids = L.event_ids(store, d)
        if not ids:
            print(f"refused: no dipole events on trade day {d} in the graph", file=sys.stderr)
            return 2
        events += ids
    if args.events:
        if args.trade_day:
            wrong = [e for e in args.events if e not in events]
            if wrong:
                print("refused: not events of the named trade days: " + ", ".join(wrong), file=sys.stderr)
                return 2
            events = list(args.events)
        else:
            events = list(args.events)
    if not events:
        print("refused: name --trade-day or --events", file=sys.stderr)
        return 2
    n = len(events)
    budget = {
        "max_model_calls": args.max_model_calls if args.max_model_calls is not None else 2 * n,
        "max_sub_agents": args.max_sub_agents if args.max_sub_agents is not None else 2 * n,
        "max_concurrent_workers": args.max_concurrent_workers,
        "max_tool_calls": args.max_tool_calls,
        "max_tokens": args.budget_tokens,
        "max_wall_clock_s": args.max_wall_clock_s,
        "max_retries": args.max_retries,
        "max_graph_writes": args.max_graph_writes if args.max_graph_writes is not None else 200 * n,
    }
    name = args.name or "swarm-" + "-".join(args.trade_day or ["events"]) + "-" + sha(events, 6)
    plan = P.make_plan(store, name=name, workload=args.workload or
                       f"one worker for each of {n} dipole events, then a refute wave on the claims sent to review",
                       events=events, cutoff=args.cutoff, budget=budget,
                       graph_dir=str(args.graph_dir) if args.graph_dir else None)
    try:
        P.check(plan)
    except P.PlanRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    plan.write(args.out)
    print(f"plan written to {args.out}: {n} briefs, estimated worker input {plan.estimate_total_input_tokens} tokens "
          f"(an estimate: characters / 4), declared max_tokens {budget['max_tokens']}. No model call was made.")
    return 0


def cmd_go(args) -> int:
    if not (args.greg_go or "").strip():
        print("refused: a run of the swarm needs Greg's go, said to him first with its budget "
              "(pass his words as --greg-go)", file=sys.stderr)
        return 2
    plan = P.RunPlan.load(args.plan)
    try:
        P.check(plan)
    except P.PlanRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    plan.greg_go = args.greg_go.strip()
    if args.caller == "anthropic":
        caller = M.AnthropicCaller(max_retries=0)       # retries are counted by the budget, not hidden in the SDK
    else:
        if not args.files_dir:
            print("refused: --caller files needs --files-dir", file=sys.stderr)
            return 2
        caller = M.FileCaller(args.files_dir)
    store = GraphStore(args.data_root, graph_dir=args.graph_dir or plan.graph_dir)
    result = run_plan(plan, caller, store)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["synthesis"])
    print(json.dumps({k: v for k, v in result.items() if k != "synthesis"}, indent=1, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.swarm.run")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--graph-dir", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="build every brief, estimate, write the plan; no model call")
    p.add_argument("--trade-day", action="append")
    p.add_argument("--events", nargs="*")
    p.add_argument("--cutoff", type=float, required=True)
    p.add_argument("--budget-tokens", type=int, required=True)
    p.add_argument("--max-model-calls", type=int)
    p.add_argument("--max-sub-agents", type=int)
    p.add_argument("--max-concurrent-workers", type=int, default=4)
    p.add_argument("--max-tool-calls", type=int, default=0)
    p.add_argument("--max-wall-clock-s", type=int, default=7200)
    p.add_argument("--max-retries", type=int, default=2)
    p.add_argument("--max-graph-writes", type=int)
    p.add_argument("--name")
    p.add_argument("--workload")
    p.add_argument("--out", required=True)
    g = sub.add_parser("go", help="run the plan (needs Greg's go)")
    g.add_argument("--plan", required=True)
    g.add_argument("--caller", choices=("anthropic", "files"), required=True)
    g.add_argument("--greg-go", default="")
    g.add_argument("--files-dir")
    g.add_argument("--out")
    args = ap.parse_args(argv)
    return cmd_plan(args) if args.cmd == "plan" else cmd_go(args)


if __name__ == "__main__":
    sys.exit(main())
