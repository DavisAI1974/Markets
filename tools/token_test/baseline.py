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
(`trade_day_assigned_by`). THE MARKER PLACES THE CALL AND IT IS NOT THE CALL'S START: a box marker is the
first line of observations.jsonl (after the job was accepted, so later than the start), a spool marker is the
provider's `created` (the END of the call). A call near 17:00 or 18:00 ET can therefore land on the other side
of a boundary; that is said, not fixed.
With strict_start=True no call is assigned (none has a start time): all are listed apart. A call with no time
marker at all is listed apart (`no_start_time`), never dropped.

A trade day is 18:00 ET the evening before to 17:00 ET on the named date, Monday to Friday (the real boundaries of
the four trade days of the plan are in the graph: GraphStore(...).nodes("TradeDay")). So:
  Sunday 18:00 ET to Monday 17:00 ET   trade day Monday (and so on to Friday 17:00 ET)
  17:00 to 18:00 ET, Monday to Thursday  the daily halt: neither trade day, listed apart (`halt`)
  Friday 17:00 ET to Sunday 18:00 ET   no trade day: listed apart (`outside_any_trade_day`), never under a Saturday

NEVER DROPPED holds for every folder under the receipts folder: a folder that holds a request.json or a
dispatch.json is read, and if either cannot be read it is listed under `unreadable` with its path and the reason;
one that reads but is not a Granite record, and a folder with neither file and no sub-folder, is listed under
`not_a_granite_record` with its path and reason. A folder with sub-folders and no file of its own is a container.
Every line carries `job_path`.

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
    outside_any_trade_day: list
    unreadable: list
    not_a_granite_record: list

    def __init__(self, *a):
        super().__init__(*a)
        self.reason, self.no_start_time, self.halt, self.other_days = None, [], [], []
        self.outside_any_trade_day, self.unreadable, self.not_a_granite_record = [], [], []


def _load(path: Path):
    try:
        return json.loads(path.read_bytes())
    except Exception:
        return None


def _load_why(path: Path):
    """(parsed, None) or (None, the reason it could not be read)."""
    try:
        return json.loads(path.read_bytes()), None
    except Exception as e:
        return None, f"{path.name}: {type(e).__name__}: {e}"


def _line_of(path: Path, needle: str) -> int:
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle in line:
                return i
    except OSError:
        pass
    return 1


def trade_day_of(epoch: float):
    """('day', 'YYYY-MM-DD') | ('halt', None) | ('outside', None).

    18:00 ET the evening before to 17:00 ET on the date, Monday to Friday. 17:00 to 18:00 ET Monday to Thursday is
    the halt. From Friday 17:00 ET to Sunday 18:00 ET there is no trade day ('outside'); Sunday 18:00 ET on is
    trade day Monday. `epoch` is the marker (it places a call; it is not the call's start).
    """
    t = dt.datetime.fromtimestamp(epoch, ET)
    wd = t.weekday()                       # Monday 0 .. Sunday 6
    if t.hour >= 18:
        return ("outside", None) if wd in (4, 5) else ("day", (t.date() + dt.timedelta(days=1)).isoformat())
    if t.hour == 17:
        return ("halt", None) if wd < 4 else ("outside", None)
    if wd in (5, 6):
        return "outside", None
    return "day", t.date().isoformat()


def _spool_result(out: dict):
    try:
        return json.loads(base64.b64decode(out["body_base64"]))
    except Exception:
        return None


def _call_box(d: Path, req: dict, out: dict | None, observations: Path) -> dict:
    out = out or {}
    # The tokens: the raw service result is saved as result.json (frankie_box_boss_session.py:2530) and holds the
    # vLLM `usage`. outcome.json carries `usage` for every HTTP-200 result (:2572-2575, set after the try/except,
    # so normal, incomplete and unparseable alike); only the non-200 branch (:2557-2560) returns without it.
    # Read result.json first and outcome.json second.
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
        "writer": "box_job", "call_id": req.get("job_id") or d.name, "job_directory": d.name, "job_path": str(d),
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
        "job_path": str(d),
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


def scan_all(receipts_dir) -> tuple[list[dict], str | None, list[dict], list[dict]]:
    """Every Granite call under the folder, no day filter, and every folder that could not be made a call.

    Returns (calls, reason when none, unreadable, not_a_granite_record). Every folder that holds a request.json or a
    dispatch.json, and every folder with no file of its own and no sub-folder, is in exactly one of the three lists.
    """
    root = Path(receipts_dir)
    if not root.is_dir():
        return [], f"receipts folder does not exist: {root}", [], []
    calls, unreadable, not_rec = [], [], []
    for cur, dirs, files in os.walk(root):
        dirs.sort()
        d = Path(cur)
        if "request.json" not in files and "dispatch.json" not in files:
            if not dirs and d != root:
                not_rec.append({"path": str(d), "reason": "no request.json and no dispatch.json, and no sub-folder"})
            continue
        req = disp = None
        bad = []
        if "request.json" in files:
            req, why = _load_why(d / "request.json")
            if why:
                bad.append(why)
        else:
            bad.append("request.json: not present")
        out = _load(d / "outcome.json") if "outcome.json" in files else None
        if "dispatch.json" in files:
            disp, why = _load_why(d / "dispatch.json")
            if why:
                bad.append(why)
        if req is not None and not isinstance(req, dict):
            bad.append("request.json: not a JSON object")
        if disp is not None and not isinstance(disp, dict):
            bad.append("dispatch.json: not a JSON object")
        if isinstance(req, dict) and req.get("schema") == BOX_REQ and not bad:
            calls.append(_finish(_call_box(d, req, out, d / "observations.jsonl")))
        elif bad:
            unreadable.append({"path": str(d), "reason": "; ".join(bad)})
        elif isinstance(disp, dict) and (disp.get("binding") or {}).get("schema") == SPOOL:
            calls.append(_finish(_call_spool(d, disp, req, out)))
        else:
            not_rec.append({"path": str(d), "reason": "files read, but neither the box job schema nor the critic spool binding schema"})
    if not calls:
        return [], f"no Granite job record (box job or critic spool) found under {root}", unreadable, not_rec
    calls.sort(key=lambda c: (c["time_marker"] is None, c["time_marker"] or 0, c["call_id"]))
    return calls, None, unreadable, not_rec


def scan(receipts_dir) -> tuple[list[dict], str | None]:
    """Every Granite call under the folder, no day filter. Returns (calls, reason when none)."""
    c, r, _, _ = scan_all(receipts_dir)
    return c, r


def read_calls(receipts_dir, trade_day: str, *, strict_start: bool = False) -> CallList:
    """The Granite calls of one trade day (`YYYY-MM-DD`), in the receipts' own order (time marker, then id)."""
    calls, reason, unreadable, not_rec = scan_all(receipts_dir)
    out = CallList()
    out.reason = reason
    out.unreadable, out.not_a_granite_record = unreadable, not_rec
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
        elif kind == "outside":
            c["set_apart_because"] = ("time marker from Friday 17:00 ET to Sunday 18:00 ET: "
                                      "belongs to no trade day")
            out.outside_any_trade_day.append(c)
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
                      f"{len(out.outside_any_trade_day)} outside any trade day, "
                      f"{len(out.other_days)} in other trade days")
    if not calls and out.reason is not None and (unreadable or not_rec):
        out.reason += f" ({len(unreadable)} unreadable folder(s), {len(not_rec)} not a Granite record)"
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
