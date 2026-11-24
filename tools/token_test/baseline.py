"""8a. The baseline: every Granite call of one trade day, each on its own line.

What a Granite call IS on disk is read from Granite's own writer code (GRANITE_RECEIPT_FIELDS.md has
the file and line of every field name). Two writers exist and are told apart by their schema, never by
a folder name:

  box job      <work>/boss-jobs/<job_id[:24]>/  request.json (schema FRANKIE_BOX_BOSS_JOB_V1), prompt.txt,
               result.json (the raw service result: the tokens are HERE), outcome.json (schema FRANKIE_BOX_BOSS_JOB_OUTCOME_V1), observations.jsonl
  critic spool <spool>/<hash>/  dispatch.json (binding.schema GRANITE_DURABLE_CLIENT_JOB_V1),
               request.json (the raw request body), outcome.json (usage only inside body_base64)

Neither writer saves a START time, an initiator or a purpose. So `started_at` and `started_by` are
`not_recorded` on every line, never filled. What IS recorded is carried under its own name:
  box job: `name` (the job name, the nearest thing to a purpose) and the time of the first line of
           observations.jsonl (`first_observation_at`, taken after the job was accepted: later than the start)
  spool:   the provider's `created` (when the response was made: the END of the call; there is no name)
A call belongs to the trade day its recorded time marker falls in, and the line says which marker did that
(`trade_day_assigned_by`). With strict_start=True no call is assigned (none has a start time): all are
listed apart. A call with no time marker at all is listed apart (`no_start_time`), never dropped. A marker
inside the daily halt (17:00 to 18:00 ET) belongs to neither trade day and is listed apart (`halt`).

`seconds` of a box job restarts when a job is resumed; a failed job has neither `seconds` nor `usage`.
session-receipts.json is NOT a baseline source: it leaves out the write-* calls by construction.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BOX_REQ, BOX_OUT = "FRANKIE_BOX_BOSS_JOB_V1", "FRANKIE_BOX_BOSS_JOB_OUTCOME_V1"
SPOOL = "GRANITE_DURABLE_CLIENT_JOB_V1"
PLAN_FIVE = ("started_by", "purpose", "input_tokens", "output_tokens", "wall_clock_s")


class CallList(list):
    """The calls of the trade day, plus what was set apart and why. A list, so `[]` means no call."""
    reason: str | None = None
    no_start_time: list
    halt: list
    other_days: list

    def __init__(self, *a):
        super().__init__(*a)
        self.reason, self.no_start_time, self.halt, self.other_days = None, [], [], []


def _load(path: Path):
    try:
        return json.loads(path.read_bytes())
    except Exception:
        return None


def _line_of(path: Path, needle: str) -> int:
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle in line:
                return i
    except OSError:
        pass
    return 1


def trade_day_of(epoch: float):
    """('day', 'YYYY-MM-DD') | ('halt', None). 18:00 ET the evening before to 17:00 ET on the date."""
    t = dt.datetime.fromtimestamp(epoch, ET)
    if t.hour >= 18:
        return "day", (t.date() + dt.timedelta(days=1)).isoformat()
    if t.hour == 17:
        return "halt", None
    return "day", t.date().isoformat()


def _spool_result(out: dict):
    try:
        return json.loads(base64.b64decode(out["body_base64"]))
    except Exception:
        return None


def _call_box(d: Path, req: dict, out: dict | None, observations: Path) -> dict:
    out = out or {}
    # The tokens: the raw service result is saved as result.json (frankie_box_boss_session.py:2530) and holds the
    # vLLM `usage`. outcome.json carries `usage` only when the completion could not be parsed (:2573). So read
    # result.json first and outcome.json second.
    raw = _load(d / "result.json") if (d / "result.json").exists() else None
    raw = raw if isinstance(raw, dict) else {}
    usage = raw.get("usage") or out.get("usage") or {}
    usage_file = "result.json" if raw.get("usage") else ("outcome.json" if out.get("usage") else None)
    first_at, first_line = None, None
    if observations.exists():
        for i, line in enumerate(observations.read_text(encoding="utf-8").splitlines(), 1):
            try:
                first_at, first_line = float(json.loads(line)["at"]), i
                break
            except Exception:
                continue
    call = {
        "writer": "box_job", "call_id": req.get("job_id") or d.name, "job_directory": d.name,
        "conversation_id": (req.get("attempt") or "").split(":", 1)[0] or None,
        "conversation_id_basis": "request_id part of request.json attempt (no conversation id is recorded)",
        "started_by": None, "purpose": req.get("name"),
        "purpose_basis": "job name in request.json (Granite records a name, not a purpose)",
        "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
        "estimated_input_tokens": req.get("estimated_input_tokens"),
        "wall_clock_s": out.get("seconds"), "started_at": None,
        "first_observation_at": first_at, "provider_created_at": raw.get("created"),
        "usage_read_from": usage_file,
        "model": out.get("model"), "served_model_name": req.get("served_model_name"),
        "incomplete": out.get("incomplete"), "error": out.get("error"),
        "prompt_path": str(d / "prompt.txt"), "prompt_stored": "prompt.txt beside request.json",
        "output_path": str(d / "outcome.json"), "output_stored": "outcome.json field text",
        "receipt_file": str(d / (usage_file or "outcome.json")),
        "receipt_line": _line_of(d / (usage_file or "outcome.json"), '"usage"'),
        "request_file": str(d / "request.json"), "request_line": _line_of(d / "request.json", '"name"'),
        "time_marker": first_at, "time_marker_name": "first_observation_at",
        "time_marker_line": first_line, "time_marker_file": str(observations) if first_at is not None else None,
    }
    return call


def _call_spool(d: Path, dispatch: dict, req: dict, out: dict | None) -> dict:
    binding = dispatch.get("binding") or {}
    result = _spool_result(out or {}) or {}
    usage = result.get("usage") or {}
    created = result.get("created")
    return {
        "writer": "critic_spool", "call_id": binding.get("job_id") or d.name, "job_directory": d.name,
        "conversation_id": binding.get("attempt_id"), "conversation_id_basis": "attempt_id in dispatch.json binding",
        "started_by": None, "purpose": None,
        "purpose_basis": "the spool writer records no job name; the folder is the shadow critic's spool",
        "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
        "estimated_input_tokens": (dispatch.get("admission") or {}).get("input_tokens"),
        "wall_clock_s": None, "started_at": None,
        "first_observation_at": None, "provider_created_at": created,
        "model": result.get("model"), "served_model_name": req.get("model"),
        "incomplete": None if not result else (result.get("choices") or [{}])[0].get("finish_reason") == "length",
        "error": None if (out or {}).get("status") == "response" else (out or {}).get("status", "no outcome.json"),
        "prompt_path": str(d / "request.json"), "prompt_stored": "request.json messages[0].content",
        "output_path": str(d / "outcome.json"), "output_stored": "outcome.json body_base64, choices[0].message.content",
        "receipt_file": str(d / "outcome.json"), "receipt_line": _line_of(d / "outcome.json", '"body_base64"'),
        "request_file": str(d / "request.json"), "request_line": 1,
        "time_marker": created, "time_marker_name": "provider_created_at",
        "time_marker_line": _line_of(d / "outcome.json", '"body_base64"'), "time_marker_file": str(d / "outcome.json"),
    }


def _finish(call: dict) -> dict:
    nr = [f for f in ("started_by", "purpose", "input_tokens", "output_tokens", "wall_clock_s", "started_at")
          if call.get(f) is None]
    call["not_recorded"] = nr
    return call


def scan(receipts_dir) -> tuple[list[dict], str | None]:
    """Every Granite call under the folder, no day filter. Returns (calls, reason when none)."""
    root = Path(receipts_dir)
    if not root.is_dir():
        return [], f"receipts folder does not exist: {root}"
    calls = []
    for cur, dirs, files in os.walk(root):
        dirs.sort()
        d = Path(cur)
        if "request.json" not in files:
            continue
        req = _load(d / "request.json")
        if not isinstance(req, dict):
            continue
        out = _load(d / "outcome.json") if "outcome.json" in files else None
        if req.get("schema") == BOX_REQ:
            calls.append(_finish(_call_box(d, req, out, d / "observations.jsonl")))
        elif "dispatch.json" in files:
            dispatch = _load(d / "dispatch.json") or {}
            if (dispatch.get("binding") or {}).get("schema") == SPOOL:
                calls.append(_finish(_call_spool(d, dispatch, req, out)))
    if not calls:
        return [], f"no Granite job record (box job or critic spool) found under {root}"
    calls.sort(key=lambda c: (c["time_marker"] is None, c["time_marker"] or 0, c["call_id"]))
    return calls, None


def read_calls(receipts_dir, trade_day: str, *, strict_start: bool = False) -> CallList:
    """The Granite calls of one trade day (`YYYY-MM-DD`), in the receipts' own order (time marker, then id)."""
    calls, reason = scan(receipts_dir)
    out = CallList()
    out.reason = reason
    for c in calls:
        c = dict(c)
        if c["time_marker"] is None:
            c["trade_day_assigned_by"] = None
            c["set_apart_because"] = "no time marker in the record"
            out.no_start_time.append(c)
            continue
        if strict_start:
            c["trade_day_assigned_by"] = None
            c["set_apart_because"] = "strict_start: no call has a recorded start time"
            out.no_start_time.append(c)
            continue
        kind, day = trade_day_of(float(c["time_marker"]))
        c["trade_day_assigned_by"] = c["time_marker_name"]
        if kind == "halt":
            c["set_apart_because"] = "time marker inside the 17:00 to 18:00 ET halt: belongs to neither trade day"
            out.halt.append(c)
        elif day == trade_day:
            c["trade_day"] = day
            out.append(c)
        else:
            c["trade_day"] = day
            c["set_apart_because"] = f"time marker falls in trade day {day}"
            out.other_days.append(c)
    if calls and not out and out.reason is None:
        out.reason = (f"{len(calls)} Granite call(s) found, none assigned to trade day {trade_day}: "
                      f"{len(out.no_start_time)} without a usable start time, {len(out.halt)} in the halt, "
                      f"{len(out.other_days)} in other trade days")
    return out


def load_prompt(call: dict) -> str:
    """The call's own stored prompt text."""
    p = Path(call["prompt_path"])
    if call["writer"] == "box_job":
        return p.read_text(encoding="utf-8")
    req = json.loads(p.read_bytes())
    return req["messages"][0]["content"]


def load_output(call: dict):
    """Granite's output text for the call, or None when the record holds none."""
    out = _load(Path(call["output_path"]))
    if not isinstance(out, dict):
        return None
    if call["writer"] == "box_job":
        return out.get("text")
    result = _spool_result(out)
    try:
        return result["choices"][0]["message"]["content"]
    except Exception:
        return None
