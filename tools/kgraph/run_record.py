"""A run's line, its report and its transcript, taken from the agent's own transcript (ticket 19).

The token plan (item 3) asks that every agent run is recorded with its model, input tokens, output
tokens, wall clock and outcome, so token use is measured per run and not estimated. Nothing here uses
a model; every figure is read from the transcript file, never typed in or estimated.

  python3 -m tools.kgraph.run_record figures --transcript <file.jsonl|.jsonl.gz>
  python3 -m tools.kgraph.run_record append  --data <markets-data> --run N --transcript <file> --agent-id ID --role R
        --stage "..." --task "..." --outcome "..." [--tokens-reported K] [--tickets a,b]
        [--code-commit C] [--corrects "..."] [--agent-type T]
  python3 -m tools.kgraph.run_record report  --transcript <file> --out <path> --title "..."
  python3 -m tools.kgraph.run_record keep    --data <markets-data> --run N --transcript <file> --agent-id ID
  python3 -m tools.kgraph.run_record missing --data <markets-data> [--live <folder of transcripts>]

`--data` names exactly the folder given; if it holds no agent-runs.jsonl the verb refuses (it never
falls through to another checkout). Only `append` and `keep` write, and only new files or a new line.

THE TIE OF A TRANSCRIPT TO A RUN: `append` and `keep` need `--agent-id`, the id the main session was given when it
started the agent. Every line of the transcript that carries `agentId` must hold it, else both refuse. When the
brief names a run it must be the `--run`; when it names none (runs 107 and 108 were general agents) the agent id
alone ties it and the line and sidecar say so. A run whose line, plan or kept sidecar already holds another
agent id refuses this one. THE LIMIT: where nothing on record names the run's agent id, the tie rests on the main
session passing the id it was given at launch; code cannot check that.

WHICH RUN A BRIEF NAMES: the number in the brief's opening, "agent run N" (any letter case) within its first
200 characters, where a brief that begins "You are the <agent>, agent run N" is run N's own even if it names
another run after that. Otherwise two different numbers there, or none, mean it names no run and `append` and `keep` refuse it;
a run named later in the brief does not count. `report` keeps every hand-back and drops nothing. `keep` never
writes over a kept file. A correcting line keeps the earlier line's `tokens_reported` unless it is given again.

TWO WALL CLOCKS EXIST: lines of the earlier session took the harness's own duration; `append` writes the
transcript's first-to-last timestamps. `missing` does not name a difference within 1,000 ms, and names more.

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
    # the run is the number in the brief's OPENING: "agent run N" (any letter case) in its first 200
    # characters; two different numbers there, or none, mean the transcript names no run
    opening = {int(x) for x in re.findall(r"agent run (\d+)", brief[:200], re.I)}
    # a brief that begins "You are the <agent>, agent run N" is that run's own, even when its first 200
    # characters name another run after that (run 135's brief names runs 131 and 123 there)
    own = re.match(r"\s*You are the [^,.\n]{1,60}, agent run (\d+)", brief, re.I)
    if own:
        opening = {int(own.group(1))}
    usage, models, texts, hand_backs, others, subs = {}, [], [], [], set(), set()
    seen_use, stamps, agent_ids, last_text, text_before_hb = set(), [], set(), "", ""
    for d in lines:
        if d.get("timestamp"):
            stamps.append(_ts(d["timestamp"]))
        if d.get("agentId"):
            agent_ids.add(d["agentId"])
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
                if it.get("text", "").strip():
                    last_text = it["text"]
            elif it.get("type") == "tool_use":
                uid = it.get("id") or json.dumps(it, sort_keys=True)
                if uid in seen_use:
                    continue
                seen_use.add(uid)
                if it.get("name") == HAND_BACK:
                    text_before_hb = last_text  # the agent's last text message before its last hand-back
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
        "run_named_in_brief": next(iter(opening)) if len(opening) == 1 else None,
        "brief_run_numbers": sorted(opening),
        "agent_id": next(iter(agent_ids)) if len(agent_ids) == 1 else None, "agent_ids": sorted(agent_ids), "models": models,
        "input_tokens_fresh": fresh, "input_tokens_cache_written": written,
        "input_tokens_cache_read": read, "output_tokens": out,
        "input_tokens": fresh + written + read, "model_replies": len(usage),
        "tool_calls": len(others), "hand_backs": len(hand_backs), "sub_agent_calls": len(subs),
        "first": iso(first), "last": iso(last), "wall_clock_ms": wall,
        "_hand_backs": hand_backs, "_text_before_last_hand_back": text_before_hb, "_texts": texts, "_lines": lines,
    }


def _public(f: dict) -> dict:
    return {k: v for k, v in f.items() if not k.startswith("_")}


def _paper(data: str) -> Path:
    base = Path(data) / PAPER
    if not (base / "agent-runs.jsonl").is_file():
        raise Refused(f"{base}/agent-runs.jsonl does not exist; --data is used exactly as given")
    return base


NO_RUN_NOTE = "the brief names no run: tied by the agent id given at launch"


def _tie(f: dict, run: int, agent_id: str, base: Path) -> str | None:
    """The transcript is run N's if its lines' agentId is the id given at launch and its brief does not name
    another run. Returns the tie note when the brief names no run (the agent id alone ties it)."""
    if f["agent_ids"] != [agent_id]:
        raise Refused(f"the transcript's lines carry agentId {f['agent_ids'] or 'none'}, not the --agent-id given ({agent_id})")
    nums = f["brief_run_numbers"]
    if len(nums) > 1:
        raise Refused(f"the transcript's brief names two different runs in its opening ({nums}); it cannot be tied to run {run}")
    if nums and nums[0] != run:
        raise Refused(f"the transcript's brief names agent run {nums[0]}, not run {run}")
    known = set()
    for r in _records(base):
        if r["run"] == run and r.get("agent_id"):
            known.add(r["agent_id"])
    for p in (base / "run-plans" / f"run-{run:04d}.json", base / "transcripts" / f"run-{run:04d}.json"):
        if p.exists():
            v = json.loads(p.read_text(encoding="utf-8")).get("agent_id")
            if v:
                known.add(v)
    if known and known != {agent_id}:
        raise Refused(f"run {run} is recorded with another agent id ({', '.join(sorted(known))}), not {agent_id}")
    return None if nums else NO_RUN_NOTE


def _records(base: Path) -> list:
    return [json.loads(x) for x in (base / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def cmd_figures(a):
    print(json.dumps(_public(figures_of(_read_bytes(a.transcript))), indent=1))


def cmd_append(a):
    base = _paper(a.data)
    f = figures_of(_read_bytes(a.transcript))
    tie_note = _tie(f, a.run, a.agent_id, base)
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
    earlier = next((r for r in reversed(_records(base)) if r["run"] == a.run), None) if a.corrects else None
    if a.tokens_reported is None and earlier and earlier.get("tokens_reported") is not None:
        tokens_reported, tokens_note = earlier["tokens_reported"], earlier.get("tokens_note")
    else:
        tokens_reported = a.tokens_reported
        tokens_note = ("the harness's total for the run when it ended (input and output together)" if a.tokens_reported is not None
                       else "the harness's total was not given")
    line = {"run": a.run, "agent_id": a.agent_id, "session": (plan or {}).get("session") or (f["_lines"][0].get("sessionId") if f["_lines"] else None),
            "stage": a.stage, "role": a.role,
            "model": f["models"][0] if len(f["models"]) == 1 else "+".join(f["models"]),
            "task": a.task}
    if plan:
        line["plan"] = f"run-plans/run-{a.run:04d}.json"
    line.update({
        "tokens_reported": tokens_reported, "tokens_note": tokens_note,
        "input_tokens": f["input_tokens"], "input_tokens_fresh": f["input_tokens_fresh"],
        "input_tokens_cache_written": f["input_tokens_cache_written"],
        "input_tokens_cache_read": f["input_tokens_cache_read"], "output_tokens": f["output_tokens"],
        "token_split_note": "read from the run's own transcript: the sum of every model reply's usage record, each reply counted once",
        "model_replies": f["model_replies"], "tool_calls": f["tool_calls"], "wall_clock_ms": f["wall_clock_ms"],
        "started_at": f["first"], "ended_at": f["last"], "hand_backs": f["hand_backs"],
        "sub_agent_calls": f["sub_agent_calls"]})
    if plan:
        line["budget_tokens"] = plan.get("max_tokens")
        line["budget_note"] = f"limits written before it started in run-plans/run-{a.run:04d}.json"
    if tie_note:
        line["tie_note"] = tie_note
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
    for k, h in enumerate(hb, 1):
        parts += [f"## Hand-back {k} of {len(hb)}", "", h, ""]
    above = f["_text_before_last_hand_back"]
    if hb and len(hb[-1]) < 600 and len(above) > len(hb[-1]):
        parts += ["## The message its last hand-back points at", "",
                  "The last hand-back is under 600 characters; the agent's last text message before it follows, nothing above is dropped.", "", above, ""]
    elif not hb and longest:
        parts += ["## No hand-back: its longest message", "", longest, ""]
    elif not hb:
        parts += ["## No hand-back", "",
                  f"This run made no hand-back and wrote no text; it made {f['model_replies']} model replies and {f['tool_calls']} tool calls.", ""]
    Path(a.out).write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {a.out}")


def cmd_keep(a):
    base = _paper(a.data)
    raw = _read_bytes(a.transcript)
    f = figures_of(raw)
    tie_note = _tie(f, a.run, a.agent_id, base)
    d = base / "transcripts"
    gz, js = d / f"run-{a.run:04d}.jsonl.gz", d / f"run-{a.run:04d}.json"
    sha = hashlib.sha256(raw).hexdigest()
    if gz.exists():
        # nothing kept is ever written over
        kept = hashlib.sha256(gzip.decompress(gz.read_bytes())).hexdigest()
        if kept != sha:
            raise Refused(f"run {a.run} already has a kept transcript with another sha256 ({kept}); nothing rewritten")
        if js.exists():
            print(f"run {a.run}: the same bytes are already kept; nothing new")
            return
        said = "the same bytes were already kept without a sidecar; sidecar written"
    else:
        if js.exists():
            old = json.loads(js.read_text(encoding="utf-8"))
            if old.get("sha256") != sha:
                raise Refused(f"run {a.run} already has a kept record with another sha256 ({old.get('sha256')}); nothing rewritten")
            raise Refused(f"run {a.run} has a sidecar and no gz; nothing rewritten, look at it by hand")
        d.mkdir(parents=True, exist_ok=True)
        gz.write_bytes(gzip.compress(raw, mtime=0))
        said = f"kept {gz} and {js}"
    first = f["_lines"][0] if f["_lines"] else {}
    plan_path = base / "run-plans" / f"run-{a.run:04d}.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
    meta = {"run": a.run, "agent_id": a.agent_id, "session": plan.get("session") or first.get("sessionId"),
            "bytes": len(raw), "lines": len(f["_lines"]), "sha256": sha,
            "kept_from": "the session's own sub-agent transcript folder; the gzip holds the file byte for byte"}
    if tie_note:
        meta["tie_note"] = tie_note
    js.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(said)


WALL_CLOCK_TOLERANCE_MS = 1000
COMPARED = ("input_tokens", "input_tokens_fresh", "input_tokens_cache_written", "input_tokens_cache_read",
            "output_tokens", "tool_calls", "model_replies", "wall_clock_ms")


def _differences(r: dict, f: dict) -> list:
    """Each figure of the line that differs from the transcript's, both values shown."""
    out = []
    for k in COMPARED:
        mine, theirs = r.get(k), f[k]
        if k == "model_replies":
            if mine is None:
                out.append(f"model_replies: the line holds none, transcript {theirs}")
            elif mine != theirs:
                out.append(f"model_replies: line {mine}, transcript {theirs}")
        elif mine is None or theirs is None:
            continue
        elif k == "wall_clock_ms":
            if abs(mine - theirs) > WALL_CLOCK_TOLERANCE_MS:
                out.append(f"wall_clock_ms: line {mine}, transcript {theirs}")
        elif mine != theirs:
            out.append(f"{k}: line {mine}, transcript {theirs}")
    if isinstance(r.get("model"), str) and f["models"] and r["model"] not in f["models"]:
        out.append(f"model: line {r['model']}, transcript {'+'.join(f['models'])}")
    return out


def _numbered(folder: Path, pattern: str, regex: str) -> set:
    if not folder.is_dir():
        return set()
    return {int(m.group(1)) for p in folder.glob(pattern) if (m := re.fullmatch(regex, p.name))}


def cmd_missing(a):
    base = _paper(a.data)
    newest = {}
    for r in _records(base):
        newest[r["run"]] = r
    kept_runs = _numbered(base / "transcripts", "run-*.jsonl.gz", r"run-(\d+)\.jsonl\.gz")
    plan_runs = _numbered(base / "run-plans", "run-*.json", r"run-(\d+)\.json")
    live = {}  # run -> [(path, figures)]
    unnamed = []
    if a.live:
        folder = Path(a.live)
        if not folder.is_dir():
            raise Refused(f"--live {folder} is not a folder")
        for p in sorted(folder.glob("*.jsonl*"), key=lambda q: q.stat().st_mtime):
            f = figures_of(_read_bytes(p))
            if f["run_named_in_brief"] is None:
                unnamed.append((p, f))
            else:
                live.setdefault(f["run_named_in_brief"], []).append((p, f))
    for p, f in unnamed:
        print(f"UNNAMED live {p.name} | agentId {f['agent_id'] or f['agent_ids'] or 'none'} | its brief names no single run")
    for run, got in sorted(live.items()):
        if len(got) > 1:
            print(f"DUPLICATE live run {run} | {len(got)} files name it: {', '.join(p.name for p, _ in got)}; none is taken")

    def transcript_of(run):
        if run in kept_runs:
            return figures_of(_read_bytes(base / "transcripts" / f"run-{run:04d}.jsonl.gz"))
        if run in live and len(live[run]) == 1:
            return live[run][0][1]
        return None

    lacks_n = {"model": 0, "input_tokens": 0, "output_tokens": 0, "wall_clock": 0, "outcome": 0}
    with_t = lacking_any = fillable = no_t_lacking = 0
    agreeing = differing_complete = complete_no_t = 0
    diffs = {}
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
        kept = run in kept_runs
        tf = transcript_of(run)
        diffs[run] = _differences(r, tf) if tf else []
        for k in lack:
            lacks_n[k] += 1
        with_t += kept
        if lack:
            lacking_any += 1
            if kept:
                fillable += 1
            else:
                no_t_lacking += 1
        else:
            if tf is None:
                complete_no_t += 1
            elif diffs[run]:
                differing_complete += 1
            else:
                agreeing += 1
        t = "a kept transcript exists that could fill it" if kept and lack else ("kept transcript exists" if kept else "no transcript kept; stays as it is")
        dif = f" | differs: {', '.join(x.split(':')[0] for x in diffs[run])}" if diffs[run] and not lack else ""
        print(f"run {run} | lacks: {', '.join(lack) if lack else 'nothing'}{dif} | {t}")
    no_line = sorted((plan_runs | kept_runs) - set(newest))
    for run in no_line:
        what = " and ".join(x for x, ok in (("plan", run in plan_runs), ("kept transcript", run in kept_runs)) if ok)
        print(f"NO LINE run {run} | has a {what} and no line in agent-runs.jsonl")
    live_no_line = sorted(set(live) - set(newest))
    for run in live_no_line:
        print(f"NO LINE run {run} | live transcript {', '.join(p.name for p, _ in live[run])} names it and the record has no line")
    live_not_kept = sorted(set(live) - kept_runs)
    for run in live_not_kept:
        print(f"NOT KEPT run {run} | live transcript {', '.join(p.name for p, _ in live[run])} is not kept yet")
    differing = 0
    for run in sorted(newest):
        for d in diffs[run]:
            print(f"DIFFERS run {run} | {d}")
            differing += 1
    print(f"COUNTS: runs {len(newest)}; lacking exact model {lacks_n['model']}; lacking input tokens {lacks_n['input_tokens']}; "
          f"lacking output tokens {lacks_n['output_tokens']}; lacking wall clock {lacks_n['wall_clock']}; lacking outcome {lacks_n['outcome']}; "
          f"with a kept transcript {with_t}; lacking something {lacking_any}, of which a kept transcript could fill {fillable} and none kept {no_t_lacking}; "
          f"complete and agreeing with a kept or live transcript: {agreeing}; complete, a figure differs: {differing_complete}; "
          f"complete, no transcript to compare: {complete_no_t}; "
          f"plan or kept transcript with no line {len(no_line)}; live transcripts {sum(len(v) for v in live.values())} "
          f"(naming no single run {len(unnamed)}), live transcripts with no line {len(live_no_line)}, "
          f"live transcripts not kept {len(live_not_kept)}; figures that differ {differing}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_record")
    sub = p.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("figures"); s.add_argument("--transcript", required=True); s.set_defaults(fn=cmd_figures)
    s = sub.add_parser("append")
    s.add_argument("--data", required=True); s.add_argument("--run", type=int, required=True)
    s.add_argument("--transcript", required=True); s.add_argument("--role", required=True)
    s.add_argument("--agent-id", required=True); s.add_argument("--stage", required=True); s.add_argument("--task", required=True)
    s.add_argument("--outcome", required=True); s.add_argument("--tokens-reported", type=int)
    s.add_argument("--tickets"); s.add_argument("--code-commit"); s.add_argument("--corrects")
    s.add_argument("--agent-type"); s.set_defaults(fn=cmd_append)
    s = sub.add_parser("report")
    s.add_argument("--transcript", required=True); s.add_argument("--out", required=True)
    s.add_argument("--title", required=True); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("keep")
    s.add_argument("--data", required=True); s.add_argument("--run", type=int, required=True)
    s.add_argument("--transcript", required=True); s.add_argument("--agent-id", required=True); s.set_defaults(fn=cmd_keep)
    s = sub.add_parser("missing"); s.add_argument("--data", required=True); s.add_argument("--live")
    s.set_defaults(fn=cmd_missing)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
