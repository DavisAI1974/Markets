"""The proposer of the ratchet loop for a control file whose one mutable file is a whole program.

The same handshake as `MailboxProposer` (tools/ratchet/proposer.py, whose helpers are used from there), in
`<mailbox>/trial-<n>/`:

  brief.md       written here: the task, the one file that may change and its present content in full, the
                 contract of `decide(packet)`, the rules a decider program obeys, every earlier trial as its own
                 line, the paths of the records the last trial kept, the session context from the graph, and
                 the answer contract
  proposed.py    written by the agent: the whole new file (written FIRST)
  answer.json    written by the agent (LAST): {"hypothesis", "rests_on": ["claim:<id>", ...], "inference": null | "<why>"}
                 or {"stop": true, "reason": "..."}
  usage.json     written by the main session from the harness's own report, never by the agent
  applied.json   written here once the file is in the worktree: old and new sha256, the unified diff, what it
                 rests on, and each claim's grounding decision (read-only; a "revise" never refuses a trial)

A proposal is refused, with the reason, when: the file does not compile; it defines no `decide`; it is
byte-identical to the present file; it imports anything outside the standard library or names `open`, `os`,
`pathlib`, `subprocess`, `socket`, `importlib`, `__import__`, `eval` or `exec`; it has no source and no stated
inference; or a `rests_on` id is not a Claim of the graph.

THE SYNTAX-TREE CHECK IS A READ OF THE CODE, NOT A SANDBOX. It catches the plain ways of reaching a file, a process
or the network. A program that builds a name at run time can get around it. The door that runs the program
(tools/decider/serve.py) fences it only as far as its own docstring says.

The figures in the brief are counts of what each trial wrote: no total, average, ranking or label is made of
them here, and the records the last trial kept are named as paths, never summed up.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import shlex
import sys
import time
from pathlib import Path

from tools.kgraph import context as kcontext
from tools.kgraph import defend, outcome
from tools.kgraph import grounding
from tools.ratchet.loop import TRIAL_ID_FILE, ProposalFailed, keep_folder
from tools.ratchet.proposer import MailboxProposer, WORKING_NOTE

TASK = ("a decider program: the one file that answers take or skip at each opening signal of Greg's own paper "
        "platform, with no model call, from the packet it is handed")
FORBIDDEN = ("open", "os", "pathlib", "subprocess", "socket", "importlib", "__import__", "eval", "exec")
CONTRACT_FILE = "tools/decider/programs/README.md"

RULES = """- Every condition names what it rests on: a rule text, a claim id of the graph, or Greg's words. A condition with no source is marked INFERENCE in a comment.
- No number without a source: each number in the code has a comment saying where it comes from (a packet line, a claim, Greg's words).
- When the packet gives no ground for a condition, the answer is take (the platform as it runs today takes every signal).
- decide() never raises: a packet with a missing line or field still gets an answer.
- Standard library only. No file is opened, no process started, no network. Nothing of Markets is imported.
- The hold rule in force (hold until the trade gives back 20% of its highest open profit) is not yours to change.
- No trade cost, no mid price, nothing averaged, pooled, ranked or labelled good or bad."""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def source_problem(text: str, present: str) -> str | None:
    """The reason a proposed program is refused, or None."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError) as e:
        return f"the file does not compile: {type(e).__name__}: {e}"
    if not any(isinstance(n, ast.FunctionDef) and n.name == "decide" for n in tree.body):
        return "the file defines no `decide` function at its top level"
    if text.encode("utf-8") == present.encode("utf-8"):
        return "the file is byte-identical to the present file: no change"
    std = getattr(sys, "stdlib_module_names", frozenset())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for al in n.names:
                top = al.name.split(".")[0]
                if top in FORBIDDEN or top not in std:
                    return f"line {n.lineno}: imports {al.name!r}, which is not allowed (standard library only, and not {', '.join(FORBIDDEN[1:])})"
        elif isinstance(n, ast.ImportFrom):
            top = (n.module or "").split(".")[0]
            if n.level or top in FORBIDDEN or top not in std:
                return f"line {n.lineno}: imports from {'.' * n.level}{n.module or ''!r}, which is not allowed (standard library only)"
            for al in n.names:
                if al.name in FORBIDDEN:
                    return f"line {n.lineno}: imports the name {al.name!r}, which is not allowed"
        elif isinstance(n, ast.Name) and n.id in FORBIDDEN:
            return f"line {n.lineno}: uses the name {n.id!r}, which is not allowed (no file, process, network or dynamic code)"
        elif isinstance(n, ast.Attribute) and n.attr in FORBIDDEN:
            return f"line {n.lineno}: uses the attribute {n.attr!r}, which is not allowed (no file, process, network or dynamic code)"
    return None


class MailboxFileProposer(MailboxProposer):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.task = k.get("task") or TASK
        self.file_rel = self.plan_rel                      # the one mutable file, here a program

    # ---- the records the last trial kept, as paths ---------------------------------------------------
    def held(self, h: dict) -> list[str]:
        """The reasons the records of one earlier trial (a history row) are held back: one for each claim it rested on
        that is a REGISTERED claim (`defend register`) with no independent challenge of its current revision on record
        (tools/kgraph/outcome.py, the rule, no run named). A claim of the graph that is not registered holds nothing back."""
        store, out = self.store(), []
        for cid in h.get("rests_on") or []:
            n = store.node(cid)
            if n and n["type"] == "Claim" and n["attrs"].get("registration") == defend.REGISTRATION:
                ok, why = outcome.may_see_outcome(store, cid)
                if not ok:
                    out.append(why)
        return out

    def _rests_notes(self, h: dict) -> list[str]:
        if "rests_on" not in h:
            return ["no record of what it rested on"]
        store, out = self.store(), []
        for cid in h["rests_on"] or []:
            n = store.node(cid)
            if not (n and n["type"] == "Claim" and n["attrs"].get("registration") == defend.REGISTRATION):
                out.append(f"{cid}: not a registered claim: no rule applies")
        return out

    def kept_records(self, history=()) -> list[str]:
        """Paths of the run folders a trial kept, if the control file's command keeps them (`--keep <folder>`).
        A folder is tied to its trial by the trial's own id, which the loop wrote inside it (`trial-id`) when it
        recorded the trial; the id is looked up in `history`. Nothing is guessed by order or by time: a folder that
        carries no id, or an id that no row of `history` has, is named as not matched to a trial, with no path (it may
        be a held trial's). The folder of a trial that is held (`held`) is named as held with its reason, without
        its path. Nothing in a folder is read or summed here."""
        rows = {h["id"]: h for h in history if h.get("id")}
        keep = keep_folder(self.program.command)
        if keep is None or not keep.is_dir():
            return []
        out = []
        for r in sorted((p for p in keep.iterdir() if p.is_dir()), key=lambda p: p.name):
            tid = None
            try:
                tid = json.loads((r / TRIAL_ID_FILE).read_text(encoding="utf-8"))["id"]
            except (OSError, ValueError, KeyError, TypeError):
                tid = None
            h = rows.get(tid) if isinstance(tid, str) else None
            if h is None:
                out.append("- a folder in the kept records is not matched to a trial ("
                           + ("it carries no trial id" if tid is None else f"its trial id {tid} is in no row of the earlier trials")
                           + "): its path is not given")
                continue
            reasons = self.held(h)
            if reasons:
                out.append(f"- the folder made by trial {h['n']} is held: " + "; ".join(reasons))
                continue
            files = [f.name for f in sorted(r.iterdir()) if f.name in ("events.jsonl", "trades.jsonl", "decisions.jsonl")]
            out.append(f"- the folder made by trial {h['n']}: {r} holds "
                       f"{', '.join(files) or 'none of events.jsonl, trades.jsonl, decisions.jsonl'}")
        return out

    # ---- the brief -----------------------------------------------------------------------------------
    def brief(self, present: str, history: list, n: int, worktree) -> tuple[str, list]:
        p = self.program
        ctx = kcontext.build(self.store(), self.task, self.context_budget, dirs=self._dirs())
        contract = Path(worktree) / CONTRACT_FILE
        contract_text = contract.read_text(encoding="utf-8") if contract.is_file() else "(the contract file is not in the worktree)"
        folder = self.mailbox / f"trial-{n}"
        L = [f"# Brief for trial {n} of the loop {p.loop}", "",
             f"Task: write the whole of one program, {self.task}.",
             "You do not run anything: the loop runs a trial on the platform's stored tape after your file is applied.",
             "", "## The one file that may change", "",
             f"Only `{self.file_rel}`. A change anywhere else is refused. Its present content, in full:", "",
             "```python", present.rstrip("\n"), "```", "",
             "## The contract of decide(packet), from " + CONTRACT_FILE, "", contract_text.rstrip("\n"), "",
             "## The rules a decider program obeys", "", RULES, "",
             "## Earlier trials, each its own line", ""]
        if not history:
            L.append("(none yet)")
        for h in history:
            reasons = self.held(h)
            if reasons:                    # nothing of the trial but its number and why its records are held back
                L.append(f"- trial {h['n']}: held: " + "; ".join(reasons))
                continue
            figs = ", ".join(f"{k}={v}" for k, v in h["figures"].items()) or "no figures"
            L.append(f"- trial {h['n']}: status {h['status']}; hypothesis: {h['hypothesis']}; figures: {figs}; "
                     f"note: {h['note'] or 'none'}" + "".join(f"; {x}" for x in self._rests_notes(h)))
        L += ["", "The figures are counts of what each trial wrote, not results. Nothing is totalled, averaged, "
              "ranked or called good or bad here."]
        if p.metric_direction is None:
            L.append("No figure is chosen for keeping or reverting: every trial is recorded and none is kept or reverted.")
        else:
            L.append(f"The loop keeps or reverts by `{p.metric_name}` ({p.metric_direction}).")
        L.append(f"The runs of 2026-11-24 are not scored ({WORKING_NOTE}).")
        kept = self.kept_records(history)
        if kept:
            L += ["", "## Records the earlier trials kept (paths to read; each trade is its own line in trades.jsonl)", ""] + kept
        L += ["", f"## Session context from the graph (about {ctx['tokens_estimated']} tokens of {self.context_budget})", "",
              ctx["text"], "Claim ids in the text above: " + (", ".join(ctx["included"]) or "none"), "",
              "## How to answer", "",
              f"1. Write the whole new file to `{folder / 'proposed.py'}` FIRST.",
              f"2. Then write `{folder / 'answer.json'}`, nothing else in it:", "",
              '{"hypothesis": "<one sentence>",',
              ' "rests_on": ["claim:<id>", "..."],',
              ' "inference": null}', "",
              "`rests_on` lists the claim ids the change stands on; if no claim supports it, leave it empty and "
              'give `"inference"`: one sentence on why none does. A proposal with neither is refused. '
              "A claim id that is not in the graph is refused. A file that does not compile, defines no `decide`, "
              "is identical to the present one, imports outside the standard library, or names open, os, pathlib, "
              "subprocess, socket, importlib, __import__, eval or exec is refused.",
              'To end the loop instead: {"stop": true, "reason": "..."}.',
              "The usage file is written by the main session from the harness's report; do not write it."]
        return "\n".join(L) + "\n", ctx["included"]

    # ---- the handshake -------------------------------------------------------------------------------
    def __call__(self, worktree, trial_no, history):
        folder = self.mailbox / f"trial-{trial_no}"
        folder.mkdir(parents=True, exist_ok=True)
        path = Path(worktree) / self.file_rel
        present = path.read_text(encoding="utf-8")
        text, _ = self.brief(present, history, trial_no, worktree)
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
        proposed = folder / "proposed.py"
        while not proposed.exists():
            if time.monotonic() >= deadline:
                raise ProposalFailed(f"timed out after {self.timeout_s}s: proposed.py is missing in {folder}", hyp)
            time.sleep(self.poll_s)
        applied = self._apply_file(present, path, proposed, answer, hyp)
        (folder / "applied.json").write_text(json.dumps(applied, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"hypothesis": hyp, "agent_run": agent_run, "usage": usage, "proposal": applied}

    def _apply_file(self, present: str, path: Path, proposed: Path, answer, hyp):
        if not isinstance(answer, dict):
            raise ProposalFailed("answer.json is not a JSON object")
        if hyp is None:
            raise ProposalFailed("answer.json: `hypothesis` is missing or empty")
        try:
            raw = proposed.read_bytes()
            new = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ProposalFailed(f"proposed.py cannot be read as UTF-8 text: {e}", hyp)
        rests_on, inference = answer.get("rests_on"), answer.get("inference")
        if rests_on is None:
            rests_on = []
        if not isinstance(rests_on, list) or not all(isinstance(c, str) for c in rests_on):
            raise ProposalFailed("`rests_on` must be a list of claim ids", hyp)
        if inference is not None and not isinstance(inference, str):
            raise ProposalFailed("`inference` must be null or a sentence", hyp)
        if isinstance(inference, str) and not inference.strip():
            inference = None
        if not rests_on and not inference:
            raise ProposalFailed("no source: `rests_on` is empty and `inference` is empty (every proposal has a "
                                 "source or is marked an inference)", hyp)
        problem = source_problem(new, present)
        if problem:
            raise ProposalFailed(problem, hyp, rests_on)
        store = self.store()
        for cid in rests_on:
            node = store.node(cid)
            if node is None or node["type"] != "Claim":
                raise ProposalFailed(f"{cid} is not a claim of the graph", hyp, rests_on)
        path.write_bytes(raw)
        grounded = []
        for cid in rests_on:
            try:
                r = grounding.check_claim(store, cid, self._dirs())
                grounded.append({"claim": cid, "decision": r["decision"], "reason": r["reason"]})
            except Exception as e:                         # a check that cannot run is said, never a refusal
                grounded.append({"claim": cid, "decision": "unchecked",
                                 "reason": f"the grounding check could not run: {type(e).__name__}: {e}"})
        diff = "".join(difflib.unified_diff(present.splitlines(keepends=True), new.splitlines(keepends=True),
                                            f"a/{self.file_rel}", f"b/{self.file_rel}"))
        return {"path": self.file_rel, "old_sha256": sha(present.encode("utf-8")), "new_sha256": sha(raw),
                "diff": diff, "rests_on": rests_on, "inference": inference, "grounding": grounded}
