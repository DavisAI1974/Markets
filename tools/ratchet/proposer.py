"""The proposer of the ratchet loop that an agent fills in, by files in a mailbox folder.

Python cannot call the session's agents. So each trial is a handshake in `<mailbox>/trial-<n>/`:

  brief.md      written here: the task, the one file that may change, the plan as it stands, every earlier
                trial as its own line, the session context from the graph, and the answer contract
  answer.json   written by the agent:  {"hypothesis", "change": {"path": [...], "value": ...},
                                        "rests_on": ["claim:<id>", ...], "inference": null | "<why>"}
                or {"stop": true, "reason": "..."}
  usage.json    written by the main session from the harness's own report, never by the agent:
                {"agent_run": "run:00NN", "model_calls", "tokens", "tool_calls", "sub_agents"}
  applied.json  written here once the one change is in the worktree: path, old and new value, what it rests
                on, and the grounding decision of each claim (read-only: nothing is recorded in the graph)

One change a trial: exactly one value, under `exit` or under one rule's entry in `rules`. A proposal with
no source and no stated inference is refused, and so is one that names a claim the graph does not hold. A
grounding decision of "revise" is reported and never a reason to refuse. The figures in the brief are
counts of what a trial wrote: no total, average, ranking or label is made of them here.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from tools.kgraph import context as kcontext
from tools.kgraph import grounding
from tools.kgraph.extract import repo_dirs
from tools.kgraph.store import GraphStore
from tools.ratchet.loop import ProposalFailed
from tools.ratchet.program import Program

USAGE_FIELDS = ("model_calls", "tokens", "tool_calls", "sub_agents")
DEFAULT_TASK = ("the exit and the rules' placement in the platform's loop-trial plan: the give-back fraction "
                "of the exit, and each rule's open and close style and offset in ticks")
WORKING_NOTE = "the runs of 2026-11-24 are recorded and are not scored"


def dump_plan(doc) -> str:
    """The layout of loop-trial.json: two-space indent, keys sorted, one newline at the end."""
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _leaves(obj, prefix=()):
    if isinstance(obj, dict):
        for k in obj:
            yield from _leaves(obj[k], prefix + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, prefix + (i,))
    else:
        yield prefix, obj


def _kind(v) -> str:
    return ("null" if v is None else "boolean" if isinstance(v, bool) else
            "number" if isinstance(v, (int, float)) else "text" if isinstance(v, str) else "structure")


def _compact(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class MailboxProposer:
    def __init__(self, mailbox, program: Program, *, data_root=None, graph_dir=None, context_budget=6000,
                 timeout_s=3600.0, poll_s=2.0, task=None, dirs=None):
        self.mailbox = Path(mailbox).resolve()
        self.program = program
        if len(program.mutable) != 1 or any(c in program.mutable[0] for c in "*?["):
            raise ValueError("the mailbox proposer changes exactly one named file: the control file's `mutable` "
                             "must list one path with no glob")
        self.plan_rel = program.mutable[0]
        self.data_root, self.graph_dir = data_root, graph_dir
        self.context_budget, self.timeout_s, self.poll_s = context_budget, timeout_s, poll_s
        self.task = task or DEFAULT_TASK
        self.dirs = dirs
        self._store = None

    # ---- graph, read-only -----------------------------------------------------------------------
    def store(self) -> GraphStore:
        if self._store is None:
            self._store = GraphStore(self.data_root or self.program.data_root, graph_dir=self.graph_dir)
        return self._store

    def _dirs(self):
        return self.dirs or repo_dirs(self.store().data_root, None, None)

    # ---- the brief -------------------------------------------------------------------------------
    def brief(self, plan: dict, history: list, n: int) -> tuple[str, list]:
        p = self.program
        ctx = kcontext.build(self.store(), self.task, self.context_budget, dirs=self._dirs())
        L = [f"# Brief for trial {n} of the loop {p.loop}", "",
             "Task: propose ONE change to the plan of Greg's own paper platform, as a hypothesis about the exit "
             "or about one rule's placement.",
             "You do not run anything: the loop runs the trial on the platform's stored tape after your change is applied.",
             "", "## What may change", "",
             f"Only the file `{self.plan_rel}`. One change a trial: exactly one value, under `exit` or under one "
             "rule's entry in `rules`. A path elsewhere, two values, or a value equal to the present one is refused.",
             "", "## The plan as it stands", "", f"exit: {_compact(plan.get('exit'))}", "", "rules:"]
        for rid in plan.get("rules", {}):
            L.append(f"- {rid}: {_compact(plan['rules'][rid])}")
        L += ["", "## Earlier trials, each its own line", ""]
        if not history:
            L.append("(none yet)")
        for h in history:
            figs = ", ".join(f"{k}={v}" for k, v in h["figures"].items()) or "no figures"
            L.append(f"- trial {h['n']}: status {h['status']}; hypothesis: {h['hypothesis']}; figures: {figs}; "
                     f"note: {h['note'] or 'none'}")
        L += ["", "The figures are counts of what each trial wrote, not results. Nothing is totalled, averaged, "
              "ranked or called good or bad here."]
        if p.metric_direction is None:
            L.append("No figure is chosen for keeping or reverting: every trial is recorded and none is kept or reverted.")
        else:
            L.append(f"The loop keeps or reverts by `{p.metric_name}` ({p.metric_direction}).")
        L.append(f"The runs of 2026-11-24 are not scored ({WORKING_NOTE}).")
        L += ["", f"## Session context from the graph (about {ctx['tokens_estimated']} tokens of {self.context_budget})", "",
              ctx["text"], "Claim ids in the text above: " + (", ".join(ctx["included"]) or "none"), "",
              "## How to answer", "",
              f"Write `{self.mailbox / f'trial-{n}' / 'answer.json'}`, nothing else:", "",
              '{"hypothesis": "<one sentence>",',
              ' "change": {"path": ["exit", "give_back_fraction"], "value": "0.25"},',
              ' "rests_on": ["claim:<id>", "..."],',
              ' "inference": null}', "",
              "`value` keeps the kind of the present value (text stays text, a number stays a number). "
              "`rests_on` lists the claim ids the change stands on; if no claim supports it, leave it empty and "
              'give `"inference"`: one sentence on why none does. A proposal with neither is refused. '
              "A claim id that is not in the graph is refused.",
              'To end the loop instead: {"stop": true, "reason": "..."}.',
              "The usage file is written by the main session from the harness's report; do not write it."]
        return "\n".join(L) + "\n", ctx["included"]

    # ---- the handshake ----------------------------------------------------------------------------
    def _wait(self, path: Path, deadline: float):
        err = None
        while True:
            if path.exists():
                try:
                    return _read_json(path)
                except (json.JSONDecodeError, OSError) as e:       # still being written, or not JSON
                    err = e
            if time.monotonic() >= deadline:
                if err:
                    raise ProposalFailed(f"{path.name} in {path.parent} is not valid JSON: {err}")
                raise ProposalFailed(f"timed out after {self.timeout_s}s: {path.name} is missing in {path.parent}")
            time.sleep(self.poll_s)

    def __call__(self, worktree, trial_no, history):
        folder = self.mailbox / f"trial-{trial_no}"
        folder.mkdir(parents=True, exist_ok=True)
        plan_path = Path(worktree) / self.plan_rel
        raw = plan_path.read_text(encoding="utf-8")
        plan = json.loads(raw)
        if dump_plan(plan) != raw:
            raise ProposalFailed(f"{self.plan_rel}: its layout is not reproduced by the writer, so a change "
                                 "would not be one value in the diff; nothing was changed")
        text, _ = self.brief(plan, history, trial_no)
        with (folder / "brief.md").open("x", encoding="utf-8") as f:
            f.write(text)
        deadline = time.monotonic() + self.timeout_s
        answer = self._wait(folder / "answer.json", deadline)
        if isinstance(answer, dict) and answer.get("stop") is True:
            return None
        usage_doc = self._wait(folder / "usage.json", deadline)
        hyp = answer.get("hypothesis") if isinstance(answer, dict) else None
        hyp = hyp if isinstance(hyp, str) and hyp.strip() else None
        usage, agent_run = self._usage(usage_doc, hyp)
        applied = self._apply(plan, plan_path, answer, hyp)
        (folder / "applied.json").write_text(json.dumps(applied, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"hypothesis": hyp, "agent_run": agent_run, "usage": usage, "proposal": applied}

    # ---- checks -----------------------------------------------------------------------------------
    @staticmethod
    def _usage(doc, hyp):
        if not isinstance(doc, dict):
            raise ProposalFailed("usage.json is not a JSON object", hyp)
        unknown = [k for k in doc if k not in USAGE_FIELDS + ("agent_run",)]
        if unknown:
            raise ProposalFailed(f"usage.json: unknown field {', '.join(unknown)}", hyp)
        usage = {}
        for k in USAGE_FIELDS:
            v = doc.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                raise ProposalFailed(f"usage.json: {k} must be a whole number or null", hyp)
            usage[k] = v
        run = doc.get("agent_run")
        if run is not None and not isinstance(run, str):
            raise ProposalFailed("usage.json: agent_run must be text like run:0053", hyp)
        return usage, run

    def _apply(self, plan: dict, plan_path: Path, answer, hyp):
        if not isinstance(answer, dict):
            raise ProposalFailed("answer.json is not a JSON object")
        if hyp is None:
            raise ProposalFailed("answer.json: `hypothesis` is missing or empty")
        ch = answer.get("change")
        if not isinstance(ch, dict) or set(ch) != {"path", "value"}:
            raise ProposalFailed("answer.json: `change` must hold exactly `path` and `value`", hyp)
        path, value = ch["path"], ch["value"]
        if not isinstance(path, list) or not path or not all(isinstance(k, (str, int)) and not isinstance(k, bool)
                                                              for k in path):
            raise ProposalFailed("the change path must be a list of names", hyp)
        top = path[0]
        if top == "exit":
            pass
        elif top == "rules":
            rid = path[1] if len(path) > 1 else None
            if rid not in plan.get("rules", {}):
                raise ProposalFailed(f"the change path names a rule that is not in the plan: {rid!r}", hyp)
        else:
            raise ProposalFailed(f"the change path {path} is outside `exit` and `rules.<rule id>`", hyp)
        if top == "rules" and len(path) < 3:
            raise ProposalFailed("the change path must lead to one value inside a rule's entry", hyp)
        if isinstance(value, (dict, list)):
            raise ProposalFailed("the change value must be one value (text, number, true/false or null), "
                                 "not a group of values", hyp)
        node = plan
        for k in path:
            try:
                node = node[k]
            except (KeyError, IndexError, TypeError):
                raise ProposalFailed(f"the change path {path} is not in the plan: only a value that is there "
                                     "can be changed", hyp)
        if isinstance(node, (dict, list)):
            raise ProposalFailed(f"the change path {path} leads to a group of values, not one value", hyp)
        old = node
        if _kind(value) != _kind(old):
            raise ProposalFailed(f"the new value is {_kind(value)} where the present value {old!r} is {_kind(old)}", hyp)
        if value == old and type(value) is type(old):
            raise ProposalFailed(f"the new value {value!r} is the present value: no change", hyp)

        rests_on, inference = answer.get("rests_on"), answer.get("inference")
        if rests_on is None:
            rests_on = []
        if not isinstance(rests_on, list) or not all(isinstance(c, str) for c in rests_on):
            raise ProposalFailed("`rests_on` must be a list of claim ids", hyp)
        if inference is not None and not (isinstance(inference, str) and inference.strip()):
            raise ProposalFailed("`inference` must be null or a sentence", hyp)
        if not rests_on and not inference:
            raise ProposalFailed("no source: `rests_on` is empty and `inference` is empty (every proposal has a "
                                 "source or is marked an inference)", hyp)
        store = self.store()
        for cid in rests_on:
            node_ = store.node(cid)
            if node_ is None or node_["type"] != "Claim":
                raise ProposalFailed(f"{cid} is not a claim of the graph", hyp)

        # the one change, written in the file's own layout
        new_plan = json.loads(json.dumps(plan))
        parent = new_plan
        for k in path[:-1]:
            parent = parent[k]
        parent[path[-1]] = value
        before = dict(_leaves(plan))
        after = dict(_leaves(new_plan))
        diff = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        if len(diff) != 1:
            raise ProposalFailed(f"the change would alter {len(diff)} values; exactly one is allowed", hyp)
        plan_path.write_text(dump_plan(new_plan), encoding="utf-8")

        grounded = []
        for cid in rests_on:
            try:
                r = grounding.check_claim(store, cid, self._dirs())
                grounded.append({"claim": cid, "decision": r["decision"], "reason": r["reason"]})
            except Exception as e:                      # a check that cannot run is said, never a refusal
                grounded.append({"claim": cid, "decision": "unchecked",
                                 "reason": f"the grounding check could not run: {type(e).__name__}: {e}"})
        return {"path": path, "old": old, "new": value, "rests_on": rests_on, "inference": inference,
                "grounding": grounded}
