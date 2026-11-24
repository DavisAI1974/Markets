"""The plan of a run of the swarm, written as JSON BEFORE the run starts (plan, "Token plan" item 2).

It names the run, the workload, the model of each role, the confidence cutoff, the events, the declared
budget and the estimate for each event; `greg_go` holds Greg's words and stays empty until he gives them.
`check(plan)` refuses a plan whose estimate is over its budget and names the figure.

What the estimate covers, said in the plan itself: the INPUT of the workers' briefs (characters divided
by four, an estimate, not a count). It does not cover the workers' output, the reducer, the refute wave
or any retry; those are bounded by the budget as the run goes, and counted from the model's own usage
figures once it has run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.kgraph.store import GraphStore

from . import layers as L
from . import model as M

BUDGET_KEYS = ("max_model_calls", "max_sub_agents", "max_concurrent_workers", "max_tool_calls", "max_tokens",
               "max_wall_clock_s", "max_retries", "max_graph_writes")

NOT_ESTIMATED = ("the workers' output tokens", "the reducer (code, no model call)",
                 "the refute wave (its brief depends on the claims the workers write)",
                 "retries", "the model's own usage figures, which are the measured ones")


class PlanRefused(ValueError):
    """The plan is over its own budget, or is not complete. The message names the figure."""


@dataclass
class RunPlan:
    name: str
    workload: str
    models: dict                 # role -> exact model id
    efforts: dict                # role -> effort
    max_output_tokens: dict      # role -> max_tokens of one call
    cutoff: float
    events: list                 # dipole node ids
    budget: dict
    estimate_per_event: list     # [{"event", "brief_chars", "estimated_input_tokens"}]
    estimate_total_input_tokens: int
    estimate_note: str = "an estimate: characters divided by four, rounded up; worker input only"
    not_estimated: list = field(default_factory=lambda: list(NOT_ESTIMATED))
    graph_dir: str | None = None
    greg_go: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "RunPlan":
        return cls(**json.loads(text))

    @classmethod
    def load(cls, path) -> "RunPlan":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def write(self, path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


def estimates(store: GraphStore, event_ids: list[str]) -> list[dict]:
    out = []
    for ev in event_ids:
        brief = L.build_brief(L.event_layers(store, ev))
        out.append({"event": ev, "brief_chars": len(brief), "estimated_input_tokens": L.estimate_tokens(brief)})
    return out


def make_plan(store: GraphStore, *, name: str, workload: str, events: list[str], cutoff: float, budget: dict,
              models: dict | None = None, efforts: dict | None = None, max_output_tokens: dict | None = None,
              graph_dir: str | None = None) -> RunPlan:
    est = estimates(store, events)
    return RunPlan(
        name=name, workload=workload,
        models=models or {"worker": M.WORKER_MODEL, "reducer": M.REDUCER_MODEL, "refute": M.REFUTE_MODEL},
        efforts=efforts or {"worker": "low", "refute": "medium"},
        max_output_tokens=max_output_tokens or {"worker": 8000, "refute": 8000},
        cutoff=cutoff, events=list(events), budget=dict(budget), estimate_per_event=est,
        estimate_total_input_tokens=sum(e["estimated_input_tokens"] for e in est), graph_dir=graph_dir)


def check(plan: RunPlan) -> None:
    """Refuse a plan that is incomplete or whose estimate is over its budget; the message names the figure."""
    missing = [k for k in BUDGET_KEYS if not isinstance(plan.budget.get(k), (int, float)) or plan.budget[k] < 0]
    if missing:
        raise PlanRefused("the budget does not declare: " + ", ".join(missing))
    if not plan.events:
        raise PlanRefused("the plan has no events")
    if [e["event"] for e in plan.estimate_per_event] != list(plan.events):
        raise PlanRefused("the estimate is not for the plan's events, in order")
    if plan.estimate_total_input_tokens != sum(e["estimated_input_tokens"] for e in plan.estimate_per_event):
        raise PlanRefused("the estimated total is not the sum of the events' own estimates")
    for role, m in plan.models.items():
        if m not in M.MODELS:
            raise PlanRefused(f"the model of {role} is {m!r}, not one of {M.MODELS}")
    b, n = plan.budget, len(plan.events)
    if b["max_concurrent_workers"] < 1:
        raise PlanRefused("max_concurrent_workers is below 1")
    if plan.estimate_total_input_tokens > b["max_tokens"]:
        raise PlanRefused(f"the estimated input of the workers' briefs is {plan.estimate_total_input_tokens} tokens, "
                          f"over the declared max_tokens of {b['max_tokens']}")
    if n > b["max_model_calls"]:
        raise PlanRefused(f"{n} workers need {n} model calls, over the declared max_model_calls of {b['max_model_calls']}")
    if n > b["max_sub_agents"]:
        raise PlanRefused(f"{n} workers are {n} sub-agents, over the declared max_sub_agents of {b['max_sub_agents']}")
