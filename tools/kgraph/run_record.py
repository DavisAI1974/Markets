"""A run's line, its report and its transcript, taken from the agent's own transcript (ticket 19).

The token plan (item 3) asks that every agent run is recorded with its model, input tokens, output
tokens, wall clock and outcome, so token use is measured per run and not estimated. Nothing here uses
a model; every figure is read from the transcript file, never typed in or estimated.

  python3 -m tools.kgraph.run_record figures --transcript <file.jsonl|.jsonl.gz>
  python3 -m tools.kgraph.run_record append  --data <markets-data> --run N --transcript <file> --role R
        --stage "..." --task "..." --outcome "..." [--tokens-reported K] [--tickets a,b]
        [--code-commit C] [--corrects "..."] [--agent-type T]
  python3 -m tools.kgraph.run_record report  --transcript <file> --out <path> --title "..."
  python3 -m tools.kgraph.run_record keep    --data <markets-data> --run N --transcript <file>
  python3 -m tools.kgraph.run_record missing --data <markets-data>

`--data` names exactly the folder given; if it holds no agent-runs.jsonl the verb refuses (it never
falls through to another checkout). Only `append` and `keep` write, and only new files or a new line.

WHAT CODE CANNOT HOLD: the runs of earlier sessions (1 to 106) cannot be filled from this machine;
their transcripts were never kept. That is why `keep` exists: from now on a run's transcript is saved
in git, and `missing` names every run that still lacks a figure and says whether a kept transcript
could fill it. Nothing is estimated for a run with no transcript; it stays as it is.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

WORK = "tasks/family-research-20261022/research-union-current"
PAPER = f"{WORK}/paper-trading-20261123"
ROLES = ("scout", "builder", "reviewer", "frankie-performance-auditor")
HAND_BACK = "SubagentHandback"
SUB_AGENT = ("Agent", "Task")


class Refused(Exception):
    pass


def _read_bytes(path: Path) -> bytes:
    raw = Path(path).read_bytes()
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def _lines(raw: bytes) -> list:
    return [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def figures_of(raw: bytes) -> dict:
    lines = _lines(raw)
    brief = ""
    if lines:
        c = (lines[0].get("message") or {}).get("content")
        brief = c if isinstance(c, str) else json.dumps(c)
    m = re.search(r"agent run (\d+)", brief)
    usage, models, texts, hand_backs, others, subs = {}, [], [], [], set(), set()
    seen_use, stamps = set(), []
    for d in lines:
        if d.get("timestamp"):
            stamps.append(_ts(d["timestamp"]))
        msg = d.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        mid = msg.get("id")
        if mid is not None:
            usage[mid] = msg.get("usage") or {}
            if msg.get("model") and msg["model"] not in models:
                models.append(msg["model"])
        for it in msg.get("content") or []:
            if not isinstance(it, dict):
                continue
            if it.get("type") == "text":
                texts.append(it.get("text", ""))
            elif it.get("type") == "tool_use":
                uid = it.get("id") or json.dumps(it, sort_keys=True)
                if uid in seen_use:
                    continue
                seen_use.add(uid)
                if it.get("name") == HAND_BACK:
                    inp = it.get("input") or {}
                    hand_backs.append(inp.get("message") if isinstance(inp.get("message"), str)
                                      else max((v for v in inp.values() if isinstance(v, str)), key=len, default=""))
                else:
                    others.add(uid)
                    if it.get("name") in SUB_AGENT:
                        subs.add(uid)
    fresh = sum(u.get("input_tokens", 0) for u in usage.values())
    written = sum(u.get("cache_creation_input_tokens", 0) for u in usage.values())
    read = sum(u.get("cache_read_input_tokens", 0) for u in usage.values())
    out = sum(u.get("output_tokens", 0) for u in usage.values())
    first, last = (min(stamps), max(stamps)) if stamps else (None, None)
    wall = round((last - first).total_seconds() * 1000) if first else None
    iso = lambda t: t.isoformat().replace("+00:00", "Z") if t else None
    return {
        "run_named_in_brief": int(m.group(1)) if m else None, "models": models,
        "input_tokens_fresh": fresh, "input_tokens_cache_written": written,
        "input_tokens_cache_read": read, "output_tokens": out,
        "input_tokens": fresh + written + read, "model_replies": len(usage),
        "tool_calls": len(others), "hand_backs": len(hand_backs), "sub_agent_calls": len(subs),
        "first": iso(first), "last": iso(last), "wall_clock_ms": wall,
        "_hand_backs": hand_backs, "_texts": texts, "_lines": lines,
    }


def _public(f: dict) -> dict:
    return {k: v for k, v in f.items() if not k.startswith("_")}


def _paper(data: str) -> Path:
    base = Path(data) / PAPER
    if not (base / "agent-runs.jsonl").is_file():
        raise Refused(f"{base}/agent-runs.jsonl does not exist; --data is used exactly as given")
    return base


def _check_brief(f: dict, run: int):
    named = f["run_named_in_brief"]
    if named != run:
        raise Refused(f"the transcript's brief names {'no run' if named is None else 'agent run ' + str(named)}, not run {run}")


def _records(base: Path) -> list:
    return [json.loads(x) for x in (base / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def cmd_figures(a):
    print(json.dumps(_public(figures_of(_read_bytes(a.transcript))), indent=1))


def cmd_append(a):
    base = _paper(a.data)
    f = figures_of(_read_bytes(a.transcript))
    _check_brief(f, a.run)
    if not (a.outcome or "").strip():
        raise Refused("the outcome is empty")
    agent_type = a.agent_type or a.role
    for what, v in (("role", a.role), ("agent type", agent_type)):
        if v not in ROLES:
            raise Refused(f"{what} {v!r} is not one of {', '.join(ROLES)}")
    if any(r["run"] == a.run for r in _records(base)) and not a.corrects:
        raise Refused(f"run {a.run} already has a line; give --corrects to write its next revision")
    plan_path = base / "run-plans" / f"run-{a.run:04d}.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None
    line = {"run": a.run, "session": (plan or {}).get("session") or (f["_lines"][0].get("sessionId") if f["_lines"] else None),
            "stage": a.stage, "role": a.role,
            "model": f["models"][0] if len(f["models"]) == 1 else "+".join(f["models"]),
            "task": a.task}
    if plan:
        line["plan"] = f"run-plans/run-{a.run:04d}.json"
    line.update({
        "tokens_reported": a.tokens_reported,
        "tokens_note": "the harness's total for the run when it ended (input and output together)" if a.tokens_reported is not None else "the harness's total was not given",
        "input_tokens": f["input_tokens"], "input_tokens_fresh": f["input_tokens_fresh"],
        "input_tokens_cache_written": f["input_tokens_cache_written"],
        "input_tokens_cache_read": f["input_tokens_cache_read"], "output_tokens": f["output_tokens"],
        "token_split_note": "read from the run's own transcript: the sum of every model reply's usage record, each reply counted once",
        "model_replies": f["model_replies"], "tool_calls": f["tool_calls"], "wall_clock_ms": f["wall_clock_ms"]})
    if plan:
        line["budget_tokens"] = plan.get("max_tokens")
        line["budget_note"] = f"limits written before it started in run-plans/run-{a.run:04d}.json"
    line["outcome"] = a.outcome
    line["agent_type"] = agent_type
    if a.code_commit:
        line["code_commit"] = a.code_commit
    if a.tickets:
        line["tickets"] = [t for t in a.tickets.split(",") if t]
    if a.corrects:
        line["corrects"] = a.corrects
    with (base / "agent-runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"appended run {a.run} to {base / 'agent-runs.jsonl'}")


def cmd_report(a):
    f = figures_of(_read_bytes(a.transcript))
    hb, texts = f["_hand_backs"], f["_texts"]
    parts = [f"# {a.title}", "",
             "Everything below this line is the agent's own report, word for word; nothing below it is the main session's.", ""]
    longest = max(texts, key=len, default="")
    if hb and not (len(hb[-1]) < 600 and len(longest) > len(hb[-1])):
        parts += ["\n\n".join(hb)]
    elif longest:
        parts += ["The agent's last hand-back is under 600 characters and only points to its message above, so its longest text item stands in its place.", "", longest]
    else:
        raise Refused("the transcript holds no hand-back and no text")
    Path(a.out).write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


def cmd_keep(a):
    base = _paper(a.data)
    raw = _read_bytes(a.transcript)
    f = figures_of(raw)
    _check_brief(f, a.run)
    d = base / "transcripts"
    gz, js = d / f"run-{a.run:04d}.jsonl.gz", d / f"run-{a.run:04d}.json"
    sha = hashlib.sha256(raw).hexdigest()
    if js.exists():
        old = json.loads(js.read_text(encoding="utf-8"))
        if old.get("sha256") != sha:
            raise Refused(f"run {a.run} already has a kept transcript with another sha256 ({old.get('sha256')}); nothing rewritten")
        print(f"run {a.run}: the same bytes are already kept; nothing new")
        return
    d.mkdir(parents=True, exist_ok=True)
    gz.write_bytes(gzip.compress(raw, mtime=0))
    first = f["_lines"][0] if f["_lines"] else {}
    plan_path = base / "run-plans" / f"run-{a.run:04d}.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
    meta = {"run": a.run, "agent_id": first.get("agentId"), "session": plan.get("session") or first.get("sessionId"),
            "bytes": len(raw), "lines": len(f["_lines"]), "sha256": sha,
            "kept_from": "the session's own sub-agent transcript folder; the gzip holds the file byte for byte"}
    js.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"kept {gz} and {js}")


def cmd_missing(a):
    base = _paper(a.data)
    newest = {}
    for r in _records(base):
        newest[r["run"]] = r
    lacks_n = {"model": 0, "input_tokens": 0, "output_tokens": 0, "wall_clock": 0, "outcome": 0}
    with_t = lacking_any = fillable = no_t_lacking = 0
    for run in sorted(newest):
        r = newest[run]
        lack = []
        if not (isinstance(r.get("model"), str) and r["model"].startswith("claude-")):
            lack.append("model")
        if r.get("input_tokens") is None:
            lack.append("input_tokens")
        if r.get("output_tokens") is None:
            lack.append("output_tokens")
        if r.get("wall_clock_ms") is None:
            lack.append("wall_clock")
        if not (isinstance(r.get("outcome"), str) and r["outcome"].strip()):
            lack.append("outcome")
        kept = (base / "transcripts" / f"run-{run:04d}.jsonl.gz").exists()
        for k in lack:
            lacks_n[k] += 1
        with_t += kept
        if lack:
            lacking_any += 1
            if kept:
                fillable += 1
            else:
                no_t_lacking += 1
        t = "a kept transcript exists that could fill it" if kept and lack else ("kept transcript exists" if kept else "no transcript kept; stays as it is")
        print(f"run {run} | lacks: {', '.join(lack) if lack else 'nothing'} | {t}")
    print(f"COUNTS: runs {len(newest)}; lacking exact model {lacks_n['model']}; lacking input tokens {lacks_n['input_tokens']}; "
          f"lacking output tokens {lacks_n['output_tokens']}; lacking wall clock {lacks_n['wall_clock']}; lacking outcome {lacks_n['outcome']}; "
          f"with a kept transcript {with_t}; lacking something {lacking_any}, of which a kept transcript could fill {fillable} and none kept {no_t_lacking}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_record")
    sub = p.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("figures"); s.add_argument("--transcript", required=True); s.set_defaults(fn=cmd_figures)
    s = sub.add_parser("append")
    s.add_argument("--data", required=True); s.add_argument("--run", type=int, required=True)
    s.add_argument("--transcript", required=True); s.add_argument("--role", required=True)
    s.add_argument("--stage", required=True); s.add_argument("--task", required=True)
    s.add_argument("--outcome", required=True); s.add_argument("--tokens-reported", type=int)
    s.add_argument("--tickets"); s.add_argument("--code-commit"); s.add_argument("--corrects")
    s.add_argument("--agent-type"); s.set_defaults(fn=cmd_append)
    s = sub.add_parser("report")
    s.add_argument("--transcript", required=True); s.add_argument("--out", required=True)
    s.add_argument("--title", required=True); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("keep")
    s.add_argument("--data", required=True); s.add_argument("--run", type=int, required=True)
    s.add_argument("--transcript", required=True); s.set_defaults(fn=cmd_keep)
    s = sub.add_parser("missing"); s.add_argument("--data", required=True); s.set_defaults(fn=cmd_missing)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
