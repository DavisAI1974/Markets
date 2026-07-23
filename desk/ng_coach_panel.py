"""Fail-closed HTMX panel for exact-source NG coach/VOXA streams.

Only ``ng_coach_message_stream.v1`` artifacts that retain the exact causal
source-gate contract are displayed. The panel is read-only: VOXA remains
adapter-only, CME event contracts remain SHADOW, tastytrade remains the broker
contract, and no execution or brain-mutation authority is introduced.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

COACH_STREAM_FILE = Path(
    os.getenv("NG_COACH_STREAM_FILE", "/var/lib/markets/ng_refine/coach_stream.json")
)
FRESH_AGE_S = float(os.getenv("NG_COACH_FRESH_AGE_S", "60"))
router = APIRouter()

MESSAGE_SCHEMA = "ng_coach_message.v1"
STREAM_SCHEMA = "ng_coach_message_stream.v1"
MESSAGE_AUTHORITY = "NG_COACH_PRESENTATION_ONLY"
STREAM_AUTHORITY = "NG_COACH_PRESENTATION_STREAM_ONLY"
SOURCE_GATE_SCHEMA = "ng_coach_voxa_source_gate.v1"
SOURCE_STATUS = "EXACT_SOURCE_AUTHORIZATION_BOUND"
VOXA_SCHEMA = "voxa.ng_coach_message.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _probabilities(value: Mapping[str, Any]) -> bool:
    try:
        numbers = [float(value[key]) for key in ("up", "flat", "down")]
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return all(math.isfinite(item) and item >= 0 for item in numbers) and abs(sum(numbers) - 1.0) <= 1e-8


def _message_valid(raw: Mapping[str, Any]) -> bool:
    message = copy.deepcopy(dict(raw))
    observed = message.pop("message_fingerprint", None)
    if not isinstance(observed, str) or observed != _fp(message):
        return False
    if message.get("schema") != MESSAGE_SCHEMA or message.get("authority") != MESSAGE_AUTHORITY:
        return False
    if message.get("material_change") is not True:
        return False
    for field in (
        "execution_authority",
        "may_update_ng_brain",
        "may_change_posterior",
        "may_change_blind_prior",
        "delivery_authority",
    ):
        if message.get(field) is not False:
            return False
    if message.get("transport_status") != "ADAPTER_ONLY_NOT_SENT":
        return False
    if not _probabilities(message.get("posterior") or {}):
        return False
    if not _probabilities(message.get("blind_prior") or {}):
        return False
    try:
        event_time = float(message.get("as_of_event_s"))
        sequence = int(message.get("sequence"))
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(event_time) or sequence < 1:
        return False
    voxa = dict(message.get("voxa_payload") or {})
    return (
        voxa.get("schema") == VOXA_SCHEMA
        and voxa.get("transport_status") == "ADAPTER_ONLY_NOT_SENT"
        and voxa.get("speech_text") == message.get("speech_text")
    )


def _stream_valid(raw: Mapping[str, Any]) -> bool:
    stream = copy.deepcopy(dict(raw))
    observed = stream.pop("stream_fingerprint", None)
    if not isinstance(observed, str) or observed != _fp(stream):
        return False
    if stream.get("schema") != STREAM_SCHEMA or stream.get("authority") != STREAM_AUTHORITY:
        return False
    if stream.get("source_gate_schema") != SOURCE_GATE_SCHEMA:
        return False
    if stream.get("source_authorization_status") != SOURCE_STATUS:
        return False
    if not stream.get("source_gate_fingerprint") or not stream.get("source_authorization_fingerprint"):
        return False
    for field in (
        "execution_authority",
        "may_update_ng_brain",
        "may_change_posterior",
        "may_change_blind_prior",
        "delivery_authority",
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "options_lane_started",
    ):
        if stream.get(field) is not False:
            return False
    if stream.get("one_signal_authority_preserved") is not True:
        return False
    if stream.get("blind_forecast_immutable") is not True:
        return False
    if stream.get("transport_status") != "ADAPTER_ONLY_NOT_SENT":
        return False
    if stream.get("cme_event_contracts_mode") != "SHADOW":
        return False
    if stream.get("brokerage_contract") != "tastytrade_not_ibkr":
        return False
    messages = list(stream.get("messages") or [])
    if int(stream.get("n_messages") or 0) != len(messages):
        return False
    if int(stream.get("n_posterior_outputs") or 0) != len(stream.get("audit") or []):
        return False
    previous: tuple[float, int] | None = None
    seen_messages: set[str] = set()
    seen_dedupe: set[str] = set()
    for message in messages:
        if not isinstance(message, Mapping) or not _message_valid(message):
            return False
        current = (float(message["as_of_event_s"]), int(message["sequence"]))
        if previous is not None and current <= previous:
            return False
        previous = current
        fingerprint = str(message.get("message_fingerprint") or "")
        dedupe_key = str(message.get("dedupe_key") or "")
        if not fingerprint or not dedupe_key or fingerprint in seen_messages or dedupe_key in seen_dedupe:
            return False
        seen_messages.add(fingerprint)
        seen_dedupe.add(dedupe_key)
    return True


def read_coach_stream(
    path: Path | None = None,
    *,
    now_s: float | None = None,
) -> dict[str, Any]:
    source = path or COACH_STREAM_FILE
    if not source.is_file():
        return {
            "panel_status": "OFFLINE",
            "panel_reason": "authorized coach stream not found",
            "execution_authority": False,
        }
    try:
        stream = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "panel_status": "INVALID",
            "panel_reason": str(error),
            "execution_authority": False,
        }
    if not isinstance(stream, dict) or not _stream_valid(stream):
        return {
            "panel_status": "INVALID",
            "panel_reason": "coach stream failed exact-source, fingerprint, or authority validation",
            "execution_authority": False,
        }

    messages = list(stream.get("messages") or [])
    audit = list(stream.get("audit") or [])
    latest_message = copy.deepcopy(messages[-1]) if messages else None
    event_times: list[float] = []
    for row in audit:
        try:
            event_times.append(float(row.get("as_of_event_s")))
        except (TypeError, ValueError, OverflowError):
            continue
    if latest_message is not None:
        event_times.append(float(latest_message["as_of_event_s"]))
    latest_event_s = max(event_times) if event_times else None
    current = time.time() if now_s is None else float(now_s)
    age_s = None if latest_event_s is None else max(0.0, current - latest_event_s)

    if latest_message is None:
        panel_status = "NO_MATERIAL_CHANGE"
    elif latest_message.get("event_type") == "STAND_DOWN":
        panel_status = "STAND_DOWN"
    elif age_s is not None and age_s <= FRESH_AGE_S:
        panel_status = "FRESH_SHADOW"
    else:
        panel_status = "HISTORICAL_REPLAY"

    return {
        "panel_status": panel_status,
        "panel_reason": None,
        "group": int(stream.get("group") or 0),
        "n_messages": len(messages),
        "n_suppressed": int(stream.get("n_suppressed") or 0),
        "n_posterior_outputs": int(stream.get("n_posterior_outputs") or 0),
        "latest_event_s": latest_event_s,
        "panel_age_s": age_s,
        "latest_message": latest_message,
        "terminal_state_by_day": copy.deepcopy(dict(stream.get("terminal_state_by_day") or {})),
        "source_gate_fingerprint": stream.get("source_gate_fingerprint"),
        "source_authorization_fingerprint": stream.get("source_authorization_fingerprint"),
        "stream_fingerprint": stream.get("stream_fingerprint"),
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "delivery_authority": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _esc(value: Any) -> str:
    return html.escape("--" if value is None else str(value))


def _number(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError, OverflowError):
        return "--"


def render_coach_panel(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("panel_status") or "OFFLINE")
    if status in {"OFFLINE", "INVALID"}:
        return f"""
<section class="coach-card coach-unavailable">
  <div class="coach-head"><div><span>REAL-TIME REFINE COACH</span><h2>Coach unavailable</h2></div><b>{_esc(status)}</b></div>
  <p>{_esc(payload.get('panel_reason'))}. The panel remains read-only and execution stays disabled.</p>
</section>"""

    message = dict(payload.get("latest_message") or {})
    if not message:
        return f"""
<section class="coach-card">
  <div class="coach-head"><div><span>EXACT-SOURCE COACH · VOXA ADAPTER ONLY</span><h2>No material change</h2></div><b>SHADOW</b></div>
  <p>{int(payload.get('n_posterior_outputs') or 0)} posterior outputs processed; {int(payload.get('n_suppressed') or 0)} non-material updates suppressed. No message was delivered.</p>
</section>"""

    posterior = dict(message.get("posterior") or {})
    prior = dict(message.get("blind_prior") or {})
    lag = dict(message.get("lag") or {})
    strongest = dict(message.get("strongest_attribution") or {}) if message.get("strongest_attribution") else {}
    reasons = list(message.get("stand_down_reasons") or [])
    direction = str(message.get("top_direction") or "--")
    lag_text = "no measured window"
    if lag.get("timing_claim_allowed") is True:
        lag_text = f"p50 {_number(lag.get('first_reprice_p50_ms'), 0)} ms · p90 {_number(lag.get('first_reprice_p90_ms'), 0)} ms"
    reason_html = "" if not reasons else f'<div class="coach-limits">{_esc(" · ".join(reasons))}</div>'
    return f"""
<section class="coach-card">
  <div class="coach-head">
    <div><span>EXACT-SOURCE COACH · VOXA ADAPTER ONLY</span><h2>{_esc(message.get('event_type'))} · {_esc(direction.upper())}</h2><p>{_esc(message.get('display_text'))}</p></div>
    <b>{_esc(status)}</b>
  </div>
  <div class="coach-metrics">
    <article><small>POSTERIOR</small><strong>{_number(100 * float(message.get('top_probability') or 0.0), 0)}%</strong><em>{_esc(direction)}</em></article>
    <article><small>BLIND PRIOR</small><strong>{_number(100 * float(prior.get(direction) or 0.0), 0)}%</strong><em>same direction</em></article>
    <article><small>UP / FLAT / DOWN</small><strong>{_number(100*float(posterior.get('up') or 0),0)} / {_number(100*float(posterior.get('flat') or 0),0)} / {_number(100*float(posterior.get('down') or 0),0)}</strong><em>probability percent</em></article>
    <article><small>PRODUCT LAG</small><strong>{_esc(lag.get('status'))}</strong><em>{_esc(lag_text)}</em></article>
    <article><small>STRONGEST INPUT</small><strong>{_esc(strongest.get('name'))}</strong><em>contribution {_number(strongest.get('contribution'),3)}</em></article>
  </div>
  <div class="coach-foot"><span>G{int(payload.get('group') or 0)} · {int(payload.get('n_messages') or 0)} material messages</span><span>{int(payload.get('n_suppressed') or 0)} suppressed</span><span>transport not sent</span><button disabled>Execution unavailable</button></div>
  {reason_html}
</section>"""


@router.get("/api/ng/coach")
def api_ng_coach() -> JSONResponse:
    return JSONResponse(read_coach_stream())


@router.get("/partials/ng-coach", response_class=HTMLResponse)
def ng_coach_partial() -> str:
    return render_coach_panel(read_coach_stream())
