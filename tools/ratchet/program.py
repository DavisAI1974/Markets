"""The control file of one ratchet loop: `program.md`, YAML front matter between two `---` lines.

`load` parses and validates it into a `Program`. A file that lacks a required field, or names a field
that does not exist, is refused with the field named (`ProgramError`). See PROGRAM_TEMPLATE.md for
every field in plain words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

BUDGET_KEYS = ("max_trials", "max_wall_clock_s", "max_model_calls", "max_sub_agents",
               "max_concurrent_workers", "max_tool_calls", "max_tokens", "max_retries", "max_graph_writes")


class ProgramError(ValueError):
    pass


@dataclass
class Figure:
    name: str
    unit: str | None
    kind: str               # regex | json
    pattern: str | None = None
    group: int | str = 1
    key: str | None = None


@dataclass
class Program:
    loop: str
    repo: str
    mutable: list
    protected: list
    metric_name: str
    metric_direction: str | None      # higher | lower | None (no figure chosen: record every trial)
    metric_unit: str | None
    figures: list
    command: str
    cwd: str
    timeout_s: float
    env: dict
    budget: dict
    max_consecutive_crashes: int
    keep: str
    stop_after_trials: int | None
    stop_after_trials_without_a_keep: int | None
    escalate: list
    escalate_file: str | None
    data_root: str | None
    path: Path | None = None
    notes: str = ""
    proposer_kind: str = "plan"       # plan | file: what a proposer changes (one plan value, or one whole program file)

    def figure(self, name):
        return next(f for f in self.figures if f.name == name)


def _fields(d, where, required, optional=()):
    if not isinstance(d, dict):
        raise ProgramError(f"{where}: must be a mapping")
    for k in d:
        if k not in required and k not in optional:
            raise ProgramError(f"{where + '.' if where else ''}{k}: unknown field")
    for k in required:
        if k not in d:
            raise ProgramError(f"{where + '.' if where else ''}{k}: required field is missing")
    return d


def _list_of_str(v, where):
    if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
        raise ProgramError(f"{where}: must be a list of text values")
    return v


def _count(v, where, nullable=True, minimum=0):
    if v is None and nullable:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < minimum:
        raise ProgramError(f"{where}: must be a number >= {minimum}" + (" or null" if nullable else ""))
    return v


def parse(text: str, path: Path | None = None) -> Program:
    m = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", text, re.S)
    if not m:
        raise ProgramError("front matter: the file must open with a --- line and close it with another")
    try:
        d = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise ProgramError(f"front matter: not valid YAML ({e})")
    d = _fields(d, "", ("loop", "repo", "mutable", "protected", "metric", "figures", "run", "budget",
                        "crash", "stop"), ("keep", "escalate", "escalate_file", "record", "proposer"))
    if not isinstance(d["loop"], str) or not re.fullmatch(r"[A-Za-z0-9._-]+", d["loop"]):
        raise ProgramError("loop: a name of letters, digits, . _ - only (it names the branch)")
    if not isinstance(d["repo"], str) or not d["repo"]:
        raise ProgramError("repo: the path of the git repository")
    mutable = _list_of_str(d["mutable"], "mutable")
    if not mutable:
        raise ProgramError("mutable: at least one glob (a loop with nothing to change cannot run)")
    protected = _list_of_str(d["protected"], "protected")

    met = _fields(d["metric"], "metric", ("name", "direction"), ("unit",))
    if met["direction"] not in ("higher", "lower", None):
        raise ProgramError("metric.direction: higher, lower or null")

    if not isinstance(d["figures"], list) or not d["figures"]:
        raise ProgramError("figures: a list with at least one figure")
    figures = []
    for i, f in enumerate(d["figures"]):
        w = f"figures[{i}]"
        f = _fields(f, w, ("name", "parse"), ("unit",))
        p = _fields(f["parse"], w + ".parse", ("kind",), ("pattern", "group", "key"))
        if p["kind"] == "regex":
            _fields(p, w + ".parse", ("kind", "pattern"), ("group",))
            try:
                rx = re.compile(p["pattern"])
            except re.error as e:
                raise ProgramError(f"{w}.parse.pattern: not a regular expression ({e})")
            g = p.get("group", 1)
            if isinstance(g, int) and g > rx.groups:
                raise ProgramError(f"{w}.parse.group: the pattern has {rx.groups} groups")
            figures.append(Figure(f["name"], f.get("unit"), "regex", pattern=p["pattern"], group=g))
        elif p["kind"] == "json":
            _fields(p, w + ".parse", ("kind", "key"))
            figures.append(Figure(f["name"], f.get("unit"), "json", key=p["key"]))
        else:
            raise ProgramError(f"{w}.parse.kind: regex or json")
    names = [f.name for f in figures]
    if len(set(names)) != len(names):
        raise ProgramError("figures: two figures carry the same name")
    if met["name"] not in names:
        raise ProgramError("metric.name: must be the name of one of the figures")

    run = _fields(d["run"], "run", ("command", "timeout_s"), ("cwd", "env"))
    if not isinstance(run["command"], str) or not run["command"].strip():
        raise ProgramError("run.command: the command line to run")
    timeout = _count(run["timeout_s"], "run.timeout_s", nullable=False, minimum=1)
    env = run.get("env") or {}
    if not isinstance(env, dict):
        raise ProgramError("run.env: must be a mapping of names to values")

    bud = _fields(d["budget"], "budget", BUDGET_KEYS)
    for k in BUDGET_KEYS:
        _count(bud[k], f"budget.{k}")
    crash = _fields(d["crash"], "crash", ("max_consecutive_crashes",))
    mcc = _count(crash["max_consecutive_crashes"], "crash.max_consecutive_crashes", nullable=False, minimum=1)
    keep = d.get("keep", "strictly_better")
    if keep not in ("strictly_better", "better_or_equal"):
        raise ProgramError("keep: strictly_better or better_or_equal")
    stop = _fields(d["stop"], "stop", ("after_trials", "after_trials_without_a_keep"))
    esc = d.get("escalate") or []
    _list_of_str(esc, "escalate")
    rec = _fields(d.get("record") or {}, "record", (), ("data_root",))
    prop = _fields(d.get("proposer") or {"kind": "plan"}, "proposer", ("kind",))
    if prop["kind"] not in ("plan", "file"):
        raise ProgramError("proposer.kind: plan or file")
    return Program(
        loop=d["loop"], repo=d["repo"], mutable=mutable, protected=protected, metric_name=met["name"],
        metric_direction=met["direction"], metric_unit=met.get("unit"), figures=figures,
        command=run["command"], cwd=run.get("cwd") or ".", timeout_s=timeout,
        env={str(k): str(v) for k, v in env.items()}, budget={k: bud[k] for k in BUDGET_KEYS},
        max_consecutive_crashes=int(mcc), keep=keep,
        stop_after_trials=_count(stop["after_trials"], "stop.after_trials"),
        stop_after_trials_without_a_keep=_count(stop["after_trials_without_a_keep"],
                                                "stop.after_trials_without_a_keep"),
        escalate=esc, escalate_file=d.get("escalate_file"), data_root=rec.get("data_root"),
        path=path, notes=m.group(2), proposer_kind=prop["kind"])


def load(path) -> Program:
    p = Path(path)
    return parse(p.read_text(encoding="utf-8"), p)


def glob_match(pattern: str, rel: str) -> bool:
    """`**` crosses folders, `*` and `?` stay inside one folder name."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        out += "[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c)
        i += 1
    return re.fullmatch(out, rel) is not None
